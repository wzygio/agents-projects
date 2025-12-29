import datetime
import logging, re, json
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List

# 导入工具类
from packages.excel_engine.src.utils.local_utils import Utils

# [标准 1] 使用 TYPE_CHECKING 解决循环导入，同时保留 IDE 智能提示
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from packages.excel_engine.src.config import ExcelEngineConfig

class ExceptionProcessor:
    """
    专门负责处理“CT良率异常波动管理表”相关业务逻辑的处理器。
    (已重构：完全对齐 DataProcessor 的架构标准)
    """
    
    # [标准 2] 依赖注入类型修正：要求传入 ExcelEngineConfig 对象
    def __init__(self, config: 'ExcelEngineConfig'):
        """
        初始化异常处理器。
        :param config: Pydantic 配置对象 (ExcelEngineConfig)
        """
        self.config = config
        
        # [标准 3] 使用对象属性访问 (Attribute Access)
        # 相比 config.get(...)，这种写法如果有拼写错误，IDE 会直接报错，更安全
        self.templates = self.config.report_text_templates.model_dump() # 转为字典以适配 .get() 用法
        self.processed_results = {} 
        self.intermediate_data = {} 
        
        # 显式获取路径 (利用 Pydantic 的强类型)
        self.cache_dir = Path(self.config.path.temp_dir)
        self.resources_dir = Path(self.config.path.resources_dir)

        # 准备 Utils 所需的字典参数
        model_defs_dict = self.config.model_definitions.model_dump()
        
        # [标准 4] 显式传入 resources_dir
        self.product_models = Utils.extract_product_models(
            model_defs_dict, 
            resources_dir=self.resources_dir
        )
        logging.info("ExceptionProcessor 初始化成功。")

    def run(self):
        """
        主调度方法。
        """
        logging.info("--- ExceptionProcessor 开始运行 ---")
        
        # [标准 3] 对象属性访问
        jobs = self.config.exception_processing_jobs
        logging.info(f"发现 {len(jobs)} 个异常处理任务...")

        for i, job_config in enumerate(jobs, 1):
            # [关键步骤] 将 Pydantic 对象转为字典，以兼容后续的 .get() 逻辑
            # 这与 DataProcessor 的处理方式完全一致
            job_dict = job_config.model_dump()
            
            job_type = job_dict.get("job_type")
            logging.info(f"--> 开始执行任务 {i}/{len(jobs)}: 类型 = {job_type}")

            if job_type == "extract_previous_exceptions": 
                self._execute_extract_previous_exceptions(job_dict)
            elif job_type == "extract_daily_exception": 
                self._execute_extract_daily_exception(job_dict)
            elif job_type == "format_exception_report": 
                self._execute_format_exception_report(job_dict)
            elif job_type == "merge_daily_into_previous": 
                self._execute_merge_daily_into_previous(job_dict)
            else:
                logging.warning(f"未知的任务类型 '{job_type}'，已跳过。")
        
        logging.info("--- 所有任务执行完毕，最终数据结构如下 ---")
        logging.info(json.dumps(self.processed_results, ensure_ascii=False, indent=2))

        logging.info("--- ExceptionProcessor 运行结束 ---")
        return self.processed_results

    def _execute_extract_previous_exceptions(self, job_config: dict):
        """(任务3) 提取昨日异常记录"""
        logging.info("  开始执行'提取昨日异常记录'任务...")

        current_hour = datetime.datetime.now().hour
        logging.info(f"    当前小时: {current_hour}点。文本转换将在12点后激活。")

        # 1. 定位源文件
        dynamic_path_cfg = job_config.get("dynamic_path_config", {})
        source_path = Utils.find_previous_report_file(dynamic_path_cfg)
        if not source_path:
            logging.error("    未能根据 dynamic_path_config 找到源文件，任务中止。")
            return
        
        self.intermediate_data['previous_exceptions_source_path'] = source_path
        logging.info(f"    已记录上一版日报的源文件路径: {source_path.name}")

        # 2. 复制到本地
        source_path_resolved = Utils.resolve_lock_file(source_path)
        
        # [标准 4] 显式传入 self.cache_dir
        source_file_path = Utils.get_local_copy(source_path_resolved, self.cache_dir)
        if not source_file_path:
            logging.error("    复制远程文件到本地缓存失败，任务中止。")
            return

        try:
            df = self._get_data_as_dataframe(source_file_path, job_config['sheet_name'])
            data_column_index = df.columns.get_loc(job_config['data_column'])
        except Exception as e:
            logging.error(f"  加载数据或获取列索引失败: {e}")
            return

        transformations = job_config.get('text_transformations', [])
        
        # [标准 4] 显式传入 resources_dir (即使有 custom_path 也要传，保持接口一致)
        # 注意：这里需要传入字典格式的 model_definitions
        model_defs_dict = self.config.model_definitions.model_dump()
        previous_product_models = Utils.extract_product_models(
            model_defs_dict, 
            resources_dir=self.resources_dir,
            custom_path=source_file_path
        ) 
        
        for product_index, previous_model in enumerate(previous_product_models):
            extracted_modules = {}
            logging.info(f"    正在为产品 '{previous_model}' (序号 {product_index}) 提取旧有记录...")
            
            module_definitions = job_config.get('sequential_extraction_rules', {}).get('module_definitions', [])
            for module_def in module_definitions:
                target_df_index = (module_def['start_row'] - 2) + (product_index * module_def['step'])
                key_name = module_def['key_name']

                try:
                    # 修复 1：强制将索引转换为 int 类型
                    # df.iat 非常严格，只接受整数，而计算结果可能是 float 或 numpy 类型
                    cell_content = df.iat[int(target_df_index), int(data_column_index)] # type: ignore
                    
                    # 修复 2：将单元格内容强制转换为字符串
                    # df 里的内容可能是数字、NaN 或其他类型，必须转为 str 才能传给 _apply_text_transformations
                    processed_content = str(cell_content) if cell_content is not None else ""
                    
                    logging.info(f"      '{previous_model}' 的 '{key_name}' 模块提取完成。")

                    final_content = self._apply_text_transformations(processed_content, transformations) 
                    extracted_modules[key_name] = final_content
                except IndexError:
                    logging.error(f"      计算出的行索引 {target_df_index} 超出范围，无法为 '{previous_model}' 提取 '{key_name}'。")
                    extracted_modules[key_name] = "错误：行越界"

            if previous_model not in self.processed_results:
                self.processed_results[previous_model] = {}
            
            self.processed_results[previous_model]['previous_exceptions'] = extracted_modules
            logging.info(f"    -> 已为 '{previous_model}' 存入 {len(extracted_modules)} 个旧有记录模块。")
        
        # 补全默认结构
        logging.info("    正在检查并补全新增型号的默认结构...")
        # 注意：这里通过 model_dump 后的 self.templates 获取，或者直接访问 config 对象
        default_text = self.config.report_text_templates.default_empty_exception_module
        
        module_definitions = job_config.get('sequential_extraction_rules', {}).get('module_definitions', [])
        
        if not default_text:
            logging.warning("    配置中未找到 'default_empty_exception_module' 模板，无法补全默认结构。")
        else:
            for model in self.product_models:
                clean_model = str(model).strip()
                
                if clean_model not in self.processed_results or 'previous_exceptions' not in self.processed_results[clean_model]:
                    logging.info(f"    -> 发现新增型号 '{clean_model}' (昨日无记录)，正在应用默认模板...")
                    
                    if clean_model not in self.processed_results:
                        self.processed_results[clean_model] = {}
                    
                    default_modules = {}
                    for module_def in module_definitions:
                        key_name = module_def.get('key_name')
                        if key_name:
                            default_modules[key_name] = default_text
                    
                    self.processed_results[clean_model]['previous_exceptions'] = default_modules
                    logging.info(f"       已为 '{clean_model}' 补全了 {len(default_modules)} 个默认模块。")

    def _apply_text_transformations(self, text: str, transformations: list) -> str:
        """根据配置规则，对输入的文本进行一系列转换操作。"""
        if not text:
            return ""

        current_hour = datetime.datetime.now().hour
        is_before_noon = current_hour < 12

        transformed_text = text
        for rule in transformations:
            rule_name = rule.get("rule_name")
            logging.info(f"      应用文本转换规则: '{rule_name}'")

            if rule_name == "move_down_daily_exception" and not is_before_noon:
                source_pattern = rule.get('source_pattern')
                destination_pattern = rule.get('destination_pattern')
                
                if not source_pattern or not destination_pattern:
                    continue

                match = re.search(source_pattern, transformed_text)
                
                if match:
                    block_to_move = match.group(2).strip()
                    block_to_move = re.sub(r'【异常】', '2.1', block_to_move) 
                    text_after_cut = re.sub(source_pattern, r'\1\3', transformed_text, count=1).strip() 
                    
                    def replacer(match_obj):
                        return f"{match_obj.group(1)}{block_to_move}\n"

                    final_text = re.sub(destination_pattern, replacer, text_after_cut, count=1)
                    transformed_text = final_text
            
            elif rule_name == "cleanup_daily_exception_section":
                pattern = rule.get('pattern')
                replacement = rule.get('replacement')

                if pattern and replacement is not None:
                    transformed_text = re.sub(pattern, replacement, transformed_text)

        return transformed_text

    def _execute_extract_daily_exception(self, job_config: dict):
        """提取每日异常数据。"""
        try:
            # [标准 4] 显式传入 self.cache_dir
            source_path = Utils.get_safe_source_path(job_config, local_cache_dir=self.cache_dir)
            if not source_path or not source_path.is_file():
                logging.error(f"未能获取有效的源文件路径，任务中止。")
                return

            df = self._get_data_as_dataframe(source_path, job_config['sheet_name'])
            
            filtered_df = self._apply_time_filters(df, job_config)
            if filtered_df.empty:
                logging.info(f"在 '{source_path.name}' 中未找到符合条件的记录。")
                return

            self._process_product_models(filtered_df, job_config)

            total_exceptions = sum(
                len(data.get('daily_records_list', [])) 
                for data in self.processed_results.values()
            )
            logging.info(f"本日共提取到 {total_exceptions} 条异常记录")

        except Exception as e:
            logging.error(f"提取异常数据时发生错误: {e}", exc_info=True)

    def _apply_time_filters(self, df: pd.DataFrame, job_config: dict) -> pd.DataFrame:
        """根据时间规则筛选数据。"""
        date_col = job_config['date_column']
        cleaned_date_series = df[date_col].astype(str).str.strip()
        datetime_series = pd.to_datetime(cleaned_date_series, errors='coerce')
        
        if datetime_series.isnull().all():
            logging.warning(f"日期列 '{date_col}' 中所有值都无法解析为有效日期。")
            return pd.DataFrame()

        now = datetime.datetime.now()
        today = now.date()
        time_filter = pd.Series(True, index=df.index)
        
        if now.hour < 9:
            target_date = today - datetime.timedelta(days=1)
            date_filter = (datetime_series.dt.date == target_date)
            logging.info(f"当前时间早于9点，正在提取昨日({target_date.strftime('%m/%d')})的异常数据...")
        else:
            date_filter = (datetime_series.dt.date == today)
            previous_report_path = self.intermediate_data.get('previous_exceptions_source_path')
            if previous_report_path and isinstance(previous_report_path, Path) and "14：00" in previous_report_path.name:
                time_filter = (datetime_series.dt.time >= datetime.time(14, 30))
                logging.info(f"检测到上一版日报为 '{previous_report_path.name}'，已激活14:30之后的时间过滤器。")
        
        return df[date_filter & time_filter].copy()

    def _get_data_as_dataframe(self, excel_path: Path, sheet_name: str) -> pd.DataFrame:
        """加载数据(带缓存)。"""
        if not excel_path.exists():
            raise FileNotFoundError(f"源Excel文件不存在: {excel_path}")

        # 使用 self.cache_dir
        cache_file_name = f"{excel_path.stem}_{sheet_name}.parquet"
        cache_path = self.cache_dir / cache_file_name

        is_cache_valid = False
        if cache_path.exists():
            excel_mtime = excel_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime
            if cache_mtime > excel_mtime:
                is_cache_valid = True

        if is_cache_valid:
            logging.info(f"加载有效的缓存文件: {cache_path.name}")
            return pd.read_parquet(cache_path)
        else:
            logging.warning(f"缓存无效或不存在，正在从源Excel文件 '{excel_path.name}' 创建缓存...")
            df = pd.read_excel(excel_path, sheet_name=sheet_name)

            logging.info("正在进行数据类型预处理...")
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str)
            logging.info("数据类型预处理完成。")
            
            df.to_parquet(cache_path, index=False)
            logging.info(f"缓存已成功创建: {cache_path.name}")
            return df
        
    def _process_product_models(self, df: pd.DataFrame, job_config: dict):
        """处理每个产品型号的异常数据。"""
        product_model_col = job_config['product_model_column']
        df[product_model_col] = df[product_model_col].astype(str).str.strip()

        for model in self.product_models:
            clean_model = str(model).strip()
            model_data = df[df[product_model_col] == clean_model]
            
            if not model_data.empty:
                logging.info(f"找到 {len(model_data)} 条匹配 '{model}' 的记录，开始解析...")
                self._parse_model_records(model, model_data, job_config)

    def _parse_model_records(self, model: str, model_data: pd.DataFrame, job_config: dict):
        """解析单个产品型号的所有记录。"""
        daily_records_list = []
        for _, record in model_data.iterrows():
            factory = record.get(job_config['factory_column'], "")
            factory_str = "" if pd.isna(factory) else str(factory).upper().strip()

            title_text = record[job_config['title_column']]
            details_text = record[job_config['details_column']]
            
            parsed_title = self._parse_text_with_patterns(title_text, job_config.get('title_patterns', {})) 
            parsed_details = self._parse_text_with_patterns(details_text, job_config.get('details_patterns', {})) 
            
            single_record_data = parsed_title.copy()
            single_record_data.update(parsed_details)
            single_record_data['factory'] = factory_str
            daily_records_list.append(single_record_data)

        if model not in self.processed_results:
            self.processed_results[model] = {}
        
        self.processed_results[model]['daily_records_list'] = daily_records_list
        self.processed_results[model]['raw_data'] = daily_records_list[0] 
        logging.info(f"'{model}' 解析完成，共缓存 {len(daily_records_list)} 条异常。")

    def _parse_text_with_patterns(self, text: str, patterns: dict) -> dict:
        """(辅助方法) 正则解析。"""
        parsed_data = {}
        if not text:
            return parsed_data
        
        text_str = str(text)
        for key, pattern in patterns.items():
            match = re.search(pattern, text_str)
            if match:
                parsed_data[key] = match.group(1).strip()
            else:
                parsed_data[key] = "/"
                logging.warning(f"配置的 '{key}' 正则表达式未在文本中找到匹配项。")
        return parsed_data
    
    def _execute_format_exception_report(self, job_config: dict):
        """(任务2) 格式化报告。"""
        if not self.processed_results:
            logging.warning("没有可供格式化的原始数据，格式化任务已跳过。")
            return

        title_template = self.templates.get('exception_report_title')
        details_template = self.templates.get('exception_report_details')
        if not title_template or not details_template:
            logging.error("报告模板缺失。")
            return

        month_str = datetime.date.today().strftime('M%m')
        
        for model, model_data in self.processed_results.items():                        
            records_list = model_data.get('daily_records_list')
            if not records_list and model_data.get('raw_data'):
                records_list = [model_data.get('raw_data')]
            
            if records_list:
                formatted_paragraphs = [] 
                formatted_titles = []  
                
                for i, raw_data in enumerate(records_list):
                    data_for_title = raw_data.copy()
                    if 'exception_name' in data_for_title:
                        data_for_title['exception_name'] = str(data_for_title['exception_name']).replace("'", "")
                    
                    title_format_data = {'index': "【异常】", 'month_str': month_str, **data_for_title}
                    title_part = Utils.format_string(title_template, title_format_data)
                    details_part = Utils.format_string(details_template, raw_data)
                    
                    clean_title = title_part.strip()
                    if clean_title.startswith("【异常】"):
                        clean_title = clean_title[4:].strip() 
                    formatted_titles.append(clean_title)

                    single_paragraph = f"{title_part.strip()}\n{details_part.strip()}"
                    formatted_paragraphs.append(single_paragraph)
                
                full_report_paragraph = "\n".join(formatted_paragraphs)
                
                self.processed_results[model]['report_paragraph'] = full_report_paragraph
                self.processed_results[model]['formatted_titles'] = formatted_titles
                logging.info(f"   --> 产品 '{model}' 已生成包含 {len(formatted_paragraphs)} 条异常的合并报告段落。")
                logging.info(f"   --> 产品 '{model}' 已生成包含 {len(formatted_titles)} 条异常的新增异常。")
    
    def _execute_merge_daily_into_previous(self, job_config: dict):
        """(任务4) 合并异常。"""
        logging.info("  开始执行'合并当日异常'任务...")
        routing_rules = job_config.get('factory_routing_rules', {})
        insertion_pattern = job_config.get('insertion_pattern')

        if not routing_rules or not insertion_pattern:
            logging.error("  'factory_routing_rules' 或 'insertion_pattern' 配置缺失，任务中止。")
            return
        
        for model, model_data in self.processed_results.items():
            raw_data = model_data.get('raw_data', {})
            factory = raw_data.get('factory', 'UNKNOWN')
            
            report_paragraph = model_data.get('report_paragraph')
            previous_exceptions = model_data.get('previous_exceptions')

            if not report_paragraph or not previous_exceptions:
                logging.info(f"    产品 '{model}'没有当日异常。")
                continue

            target_module_key = routing_rules.get(factory)
            if not target_module_key:
                logging.warning(f"    产品 '{model}' 的厂别 '{factory}' 没有匹配的路由规则，跳过合并。")
                continue
            
            target_text = previous_exceptions.get(target_module_key)
            if target_text is None:
                logging.warning(f"    产品 '{model}' 在旧有记录中未找到目标模块 '{target_module_key}'，跳过合并。")
                continue

            logging.info(f"    正在将产品 '{model}' 的异常报告插入到 '{target_module_key}'...")
            def replacer(match_obj):
                return f"{match_obj.group(1)}{report_paragraph}\n"
            
            modified_text = re.sub(insertion_pattern, replacer, target_text, count=1)
            self.processed_results[model]['previous_exceptions'][target_module_key] = modified_text