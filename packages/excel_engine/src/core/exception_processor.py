# src/exception_processor.py
import datetime
import logging, re, json
import pandas as pd
from pathlib import Path
from typing import Optional

from excel_generator_project.utils.utils import Utils
from excel_generator_project.config import TEMP_DIR
from excel_generator_project.infrastructure.excel_handler import ExcelHandler
from openpyxl.utils import get_column_letter

class ExceptionProcessor:
    """
    专门负责处理“CT良率异常波动管理表”相关业务逻辑的处理器。
    (已重构为调度器模式)
    """
    def __init__(self, config: dict):
        """
        初始化异常处理器。
        :param config: 完整的、从 config.yaml 加载的配置字典。
        """
        self.config = config
        self.templates = config.get('report_text_templates', {})
        self.processed_results = {}  # 用于存储本处理器所有任务的最终结果
        self.intermediate_data = {} 
        self.cache_dir = TEMP_DIR
        # ‘model_definitions’可以确保提取的产品型号是从最新日报中提取的
        self.product_models = Utils.extract_product_models(config.get('model_definitions', []))
        logging.info("ExceptionProcessor 初始化成功。")

    def run(self):
        """
        主调度方法。
        """
        logging.info("--- ExceptionProcessor 开始运行 ---")
        # --- 步骤 1: 准备输出文件和Excel处理器 ---
        
        jobs = self.config.get('exception_processing_jobs', [])
        logging.info(f"发现 {len(jobs)} 个异常处理任务...")

        for i, job_config in enumerate(jobs, 1):
            job_type = job_config.get("job_type")
            logging.info(f"--> 开始执行任务 {i}/{len(jobs)}: 类型 = {job_type}")

            if job_type == "extract_previous_exceptions": # 步骤1: 提取上一版日报中的异常记录
                self._execute_extract_previous_exceptions(job_config)
            elif job_type == "extract_daily_exception": # 步骤2: 提取当日异常内容
                self._execute_extract_daily_exception(job_config)
            elif job_type == "format_exception_report": # 步骤3: 当日异常格式化
                self._execute_format_exception_report(job_config)
            elif job_type == "merge_daily_into_previous": # 步骤4： 将当日异常到上一版日报中的异常记录中
                self._execute_merge_daily_into_previous(job_config)
            else:
                logging.warning(f"未知的任务类型 '{job_type}'，已跳过。")
        
        # --- 核心修改：将不安全的循环替换为直接打印整个结果字典 ---
        logging.info("--- 所有任务执行完毕，最终数据结构如下 ---")
        # 这会打印出所有被成功处理的产品的完整数据，更安全也更直观
        logging.info(json.dumps(self.processed_results, ensure_ascii=False, indent=2))

        logging.info("--- ExceptionProces   sor 运行结束 ---")
        return self.processed_results
        # --- 使用以下修正后的代码替换原方法 ---

    def _execute_extract_previous_exceptions(self, job_config: dict):
        """
        (任务3, 再次修正) 从上一版日报中，按顺序为每个产品提取原异常记录。
        """
        logging.info("  开始执行'提取昨日异常记录'任务...")

        current_hour = datetime.datetime.now().hour
        logging.info(f"    当前小时: {current_hour}点。文本转换将在12点后激活。")

        # --- 核心修改：采用“业务类查找 -> 工具类复制”的新模式 ---
        # 1. 调用专属的私有方法来定位远程源文件
        dynamic_path_cfg = job_config.get("dynamic_path_config", {})
        source_path = Utils.find_previous_report_file(dynamic_path_cfg)
        if not source_path:
            logging.error("    未能根据 dynamic_path_config 找到源文件，任务中止。")
            return
        
        # --- 核心修改 1: 将路径存入新的 intermediate_data 字典 ---
        self.intermediate_data['previous_exceptions_source_path'] = source_path
        logging.info(f"    已记录上一版日报的源文件路径: {source_path.name}")
        # --- 修改结束 ---

        # 2. 依次调用通用的Utils函数，进行路径净化和复制
        # (假设 resolve_lock_file 已存在于 Utils 中)
        source_path_resolved = Utils.resolve_lock_file(source_path)
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

        # --- 新增：从配置中获取转换规则 ---
        transformations = job_config.get('text_transformations', [])
        previous_product_models = Utils.extract_product_models(self.config.get('model_definitions', []), source_file_path) # 提取昨日产品型号
        for product_index, previous_model in enumerate(previous_product_models):
            extracted_modules = {}
            logging.info(f"    正在为产品 '{previous_model}' (序号 {product_index}) 提取旧有记录...")
            
            # (模块定义和循环部分代码不变)
            module_definitions = job_config.get('sequential_extraction_rules', {}).get('module_definitions', [])
            for module_def in module_definitions:
                target_df_index = (module_def['start_row'] - 2) + (product_index * module_def['step'])
                key_name = module_def['key_name']

                try:
                    # 步骤1: 提取旧有记录：使用 .iat 进行高性能、精确的单点值访问
                    cell_content = df.iat[target_df_index, data_column_index] # type: ignore
                    processed_content = cell_content
                    logging.info(f"      '{previous_model}' 的 '{key_name}' 模块提取完成。")

                    # 步骤 2: 应用复杂的文本转换规则
                    final_content = self._apply_text_transformations(processed_content, transformations) # type: ignore
                        
                    extracted_modules[key_name] = final_content
                except IndexError:
                    logging.error(f"      计算出的行索引 {target_df_index} 超出范围，无法为 '{previous_model}' 提取 '{key_name}'。")
                    extracted_modules[key_name] = "错误：行越界"

            if previous_model not in self.processed_results:
                self.processed_results[previous_model] = {}
            
            self.processed_results[previous_model]['previous_exceptions'] = extracted_modules
            logging.info(f"    -> 已为 '{previous_model}' 存入 {len(extracted_modules)} 个旧有记录模块。")
        
        # --- 核心修改：为今日新增的型号补全默认的异常模块结构 ---
        logging.info("    正在检查并补全新增型号的默认结构...")
        default_text = self.config['report_text_templates']['default_empty_exception_module']
        # 获取提取规则中定义的所有 key_name (例如 ['previous_module_1', 'previous_module_2'])
        module_definitions = job_config.get('sequential_extraction_rules', {}).get('module_definitions', [])
        
        if not default_text:
            logging.warning("    配置中未找到 'default_empty_exception_module' 模板，无法补全默认结构。")
        else:
            # 遍历今日所有需要处理的型号 (self.product_models 来自 config['model_definitions'])
            for model in self.product_models:
                clean_model = str(model).strip()
                
                # 如果该型号不在 processed_results 中，或者虽然在但没有 previous_exceptions
                if clean_model not in self.processed_results or 'previous_exceptions' not in self.processed_results[clean_model]:
                    logging.info(f"    -> 发现新增型号 '{clean_model}' (昨日无记录)，正在应用默认模板...")
                    
                    # 确保主字典存在
                    if clean_model not in self.processed_results:
                        self.processed_results[clean_model] = {}
                    
                    # 构建默认模块字典
                    default_modules = {}
                    for module_def in module_definitions:
                        key_name = module_def.get('key_name')
                        if key_name:
                            default_modules[key_name] = default_text
                    
                    self.processed_results[clean_model]['previous_exceptions'] = default_modules
                    logging.info(f"       已为 '{clean_model}' 补全了 {len(default_modules)} 个默认模块。")

    def _apply_text_transformations(self, text: str, transformations: list) -> str:
        """
        (已更新) 根据配置规则，对输入的文本进行一系列转换操作。
        使用替换函数来安全地处理包含特殊字符的文本。
        12点前只执行清理操作，不进行下移。
        """
        if not text:
            return ""

        # 获取当前小时
        current_hour = datetime.datetime.now().hour
        is_before_noon = current_hour < 12

        transformed_text = text
        for rule in transformations:
            rule_name = rule.get("rule_name")
            logging.info(f"      应用文本转换规则: '{rule_name}'")

            # 1. 先将昨日异常下移（12点后执行）
            if rule_name == "move_down_daily_exception" and not is_before_noon:
                source_pattern = rule.get('source_pattern')
                destination_pattern = rule.get('destination_pattern')
                
                if not source_pattern or not destination_pattern:
                    continue

                match = re.search(source_pattern, transformed_text)
                
                if match:
                    # 提取需要下移的文本块
                    block_to_move = match.group(2).strip()
                    block_to_move = re.sub(r'【异常】', '2.1', block_to_move) # 将 "【异常】" 替换为 "2.1"
                    text_after_cut = re.sub(source_pattern, r'\1\3', transformed_text, count=1).strip() 
                    
                    def replacer(match_obj):
                        # match_obj.group(1) 是 destination_pattern 匹配到的内容 (即 "2、各工厂还原时序\n")
                        # block_to_move 在这里被当作纯文本字符串，不会被re引擎解析
                        return f"{match_obj.group(1)}{block_to_move}\n"

                    final_text = re.sub(destination_pattern, replacer, text_after_cut, count=1)
                    transformed_text = final_text
            
            # 2. 清理昨日的当日异常（始终执行）
            elif rule_name == "cleanup_daily_exception_section":
                pattern = rule.get('pattern')
                replacement = rule.get('replacement')

                if pattern and replacement is not None:
                    transformed_text = re.sub(pattern, replacement, transformed_text)

        return transformed_text


    def _execute_extract_daily_exception(self, job_config: dict):
        """使用Parquet缓存高效地提取每日异常数据。"""
        try:
            # 1. 初始化和验证
            source_path = Utils.get_safe_source_path(job_config)
            if not source_path or not source_path.is_file():
                logging.error(f"未能获取有效的源文件路径，任务中止。")
                return

            # 2. 加载数据
            df = self._get_data_as_dataframe(source_path, job_config['sheet_name'])
            
            # 3. 应用时间筛选
            filtered_df = self._apply_time_filters(df, job_config)
            if filtered_df.empty:
                logging.info(f"在 '{source_path.name}' 中未找到符合条件的记录。")
                return

            # 4. 处理产品型号数据
            self._process_product_models(filtered_df, job_config)

            # 5. 记录统计信息
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
        
        # 1. 强制转换为字符串并清除首尾空格
        cleaned_date_series = df[date_col].astype(str).str.strip()
        # 2. 在清理后的数据上进行日期时间转换
        datetime_series = pd.to_datetime(cleaned_date_series, errors='coerce')
        
        if datetime_series.isnull().all():
            logging.warning(f"日期列 '{date_col}' 中所有值都无法解析为有效日期。")
            return pd.DataFrame()

        # 获取当前时间和日期
        now = datetime.datetime.now()
        today = now.date()
        
        # 默认不应用时间过滤器
        time_filter = pd.Series(True, index=df.index)
        
        # 根据时间确定筛选规则
        if now.hour <9:
            # 9点前：提取昨日数据
            target_date = today - datetime.timedelta(days=1)
            date_filter = (datetime_series.dt.date == target_date)
            logging.info(f"当前时间早于9点，正在提取昨日({target_date.strftime('%m/%d')})的异常数据...")
        else:
            # 9点后：提取今日数据
            date_filter = (datetime_series.dt.date == today)
            
            # 检查是否需要时间过滤
            previous_report_path = self.intermediate_data.get('previous_exceptions_source_path')
            if previous_report_path and "14：00" in previous_report_path.name:
                time_filter = (datetime_series.dt.time >= datetime.time(14, 30))
                logging.info(f"检测到上一版日报为 '{previous_report_path.name}'，已激活14:30之后的时间过滤器。")
        
        # 应用组合过滤器
        return df[date_filter & time_filter].copy()

    def _get_data_as_dataframe(self, excel_path: Path, sheet_name: str) -> pd.DataFrame:
        """
        (新增辅助方法)
        智能地从Excel或Parquet缓存中加载数据。
        如果缓存不存在或已过期，则从Excel转换并创建缓存。
        """
        if not excel_path.exists():
            raise FileNotFoundError(f"源Excel文件不存在: {excel_path}")

        # 根据源文件名和工作表名创建唯一的缓存文件名
        cache_file_name = f"{excel_path.stem}_{sheet_name}.parquet"
        cache_path = self.cache_dir / cache_file_name

        # 检查缓存是否有效
        is_cache_valid = False
        if cache_path.exists():
            excel_mtime = excel_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime
            if cache_mtime > excel_mtime:
                is_cache_valid = True

        if is_cache_valid:
            # 缓存有效，直接从Parquet读取
            logging.info(f"加载有效的缓存文件: {cache_path.name}")
            return pd.read_parquet(cache_path)
        else:
            # 缓存无效或不存在，从Excel读取并创建/更新缓存
            logging.warning(f"缓存无效或不存在，正在从源Excel文件 '{excel_path.name}' 创建缓存...")
            # 使用pandas读取Excel，更快
            df = pd.read_excel(excel_path, sheet_name=sheet_name)

            # --- 新增的修复代码 ---
            # 在保存为Parquet前，将所有object类型的列强制转换为字符串
            # 这是为了防止因列中混合了数字和文本而导致的 ArrowTypeError
            logging.info("正在进行数据类型预处理...")
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str)
            logging.info("数据类型预处理完成。")
            # --- 修复代码结束 ---
            
            # 保存为Parquet格式
            df.to_parquet(cache_path, index=False)
            logging.info(f"缓存已成功创建: {cache_path.name}")
            return df
        
    def _process_product_models(self, df: pd.DataFrame, job_config: dict):
        """处理每个产品型号的异常数据。"""
        product_model_col = job_config['product_model_column']
        
        # 清理产品型号列
        df[product_model_col] = df[product_model_col].astype(str).str.strip()

        # 处理每个产品型号
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
            # 提取基本信息
            factory = record.get(job_config['factory_column'], "")
            factory_str = "" if pd.isna(factory) else str(factory).upper().strip()

            # 解析标题和详情
            title_text = record[job_config['title_column']]
            details_text = record[job_config['details_column']]
            
            parsed_title = self._parse_text_with_patterns(title_text, job_config.get('title_patterns', {})) # type: ignore
            parsed_details = self._parse_text_with_patterns(details_text, job_config.get('details_patterns', {})) # type: ignore
            
            # 合并数据
            single_record_data = parsed_title | parsed_details
            single_record_data['factory'] = factory_str
            daily_records_list.append(single_record_data)

        # 存储结果
        if model not in self.processed_results:
            self.processed_results[model] = {}
        
        self.processed_results[model]['daily_records_list'] = daily_records_list
        self.processed_results[model]['raw_data'] = daily_records_list[0]  # 兼容性处理
        
        logging.info(f"'{model}' 解析完成，共缓存 {len(daily_records_list)} 条异常。")


    def _parse_text_with_patterns(self, text: str, patterns: dict) -> dict:
        """(辅助方法) 使用指定的正则表达式字典来解析一段文本。"""
        parsed_data = {}
        if not text:
            return parsed_data
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                parsed_data[key] = match.group(1).strip()
            else:
                parsed_data[key] = "/"
                logging.warning(f"配置的 '{key}' 正则表达式未在文本中找到匹配项。")
        return parsed_data
    
    
    def _execute_format_exception_report(self, job_config: dict):
        """(任务2, 已重构) 为每个产品生成报告段落（支持多条异常合并）。"""
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
             
            # 如果没有列表（可能是旧逻辑或某种异常），尝试回退到单条 raw_data 放入列表
            if not records_list and model_data.get('raw_data'):
                records_list = [model_data.get('raw_data')]
            
            if records_list:
                formatted_paragraphs = [] # 用于存储该产品所有格式化好的异常段落
                formatted_titles = []  # 用于存储该产品所有格式化好的title
                
                for i, raw_data in enumerate(records_list):
                    data_for_title = raw_data.copy()
                    
                    # 去掉单引号
                    if 'exception_name' in data_for_title:
                        data_for_title['exception_name'] = str(data_for_title['exception_name']).replace("'", "")
                    
                    # 统一序号 (目前统一用【异常】)
                    title_format_data = {'index': "【异常】", 'month_str': month_str, **data_for_title}
                    
                    title_part = Utils.format_string(title_template, title_format_data)
                    details_part = Utils.format_string(details_template, raw_data)
                    
                    # 存储title
                    clean_title = title_part.strip()
                    if clean_title.startswith("【异常】"):
                        clean_title = clean_title[4:].strip()  # 去掉"【异常】"前缀并再次清理空格
                    formatted_titles.append(clean_title)

                    # 单个异常的完整段落
                    single_paragraph = f"{title_part.strip()}\n{details_part.strip()}"
                    formatted_paragraphs.append(single_paragraph)
                
                # 拼接：将所有异常段落用换行符连接。这样 report_paragraph 依然是一个字符串，可以直接被后续的正则替换使用
                full_report_paragraph = "\n".join(formatted_paragraphs)
                
                self.processed_results[model]['report_paragraph'] = full_report_paragraph
                self.processed_results[model]['formatted_titles'] = formatted_titles
                logging.info(f"   --> 产品 '{model}' 已生成包含 {len(formatted_paragraphs)} 条异常的合并报告段落。")
                logging.info(f"   --> 产品 '{model}' 已生成包含 {len(formatted_titles)} 条异常的新增异常。")
    
    def _execute_merge_daily_into_previous(self, job_config: dict):
        """(任务4) 将当日异常根据厂别，合并到前一日的异常记录模块中。"""
        logging.info("  开始执行'合并当日异常'任务...")
        routing_rules = job_config.get('factory_routing_rules', {})
        insertion_pattern = job_config.get('insertion_pattern')

        if not routing_rules or not insertion_pattern:
            logging.error("  'factory_routing_rules' 或 'insertion_pattern' 配置缺失，任务中止。")
            return
        
        for model, model_data in self.processed_results.items():
            # 1. 获取该型号所需的所有数据
            raw_data = model_data.get('raw_data', {})
            factory = raw_data.get('factory', 'UNKNOWN')
            
            report_paragraph = model_data.get('report_paragraph')
            previous_exceptions = model_data.get('previous_exceptions')

            if not report_paragraph or not previous_exceptions:
                logging.info(f"    产品 '{model}'没有当日异常。")
                continue

            # 2. 根据厂别进行路由
            target_module_key = routing_rules.get(factory)
            if not target_module_key:
                logging.warning(f"    产品 '{model}' 的厂别 '{factory}' 没有匹配的路由规则，跳过合并。")
                continue
            
            # 3. 获取待修改的文本模块
            target_text = previous_exceptions.get(target_module_key)
            if target_text is None:
                logging.warning(f"    产品 '{model}' 在旧有记录中未找到目标模块 '{target_module_key}'，跳过合并。")
                continue

            # 4. 执行安全的插入操作
            logging.info(f"    正在将产品 '{model}' 的异常报告插入到 '{target_module_key}'...")
            def replacer(match_obj):
                # match_obj.group(1) 是捕获的 "1、当日异常\n"
                return f"{match_obj.group(1)}{report_paragraph}\n"
            
            # count=1 确保只替换第一个匹配项
            modified_text = re.sub(insertion_pattern, replacer, target_text, count=1)

            # 5. 将修改后的文本写回 self.processed_results
            self.processed_results[model]['previous_exceptions'][target_module_key] = modified_text

            