import re, os
import json
import logging
from pathlib import Path
import datetime
from datetime import datetime as dt
from typing import Dict, List, Any, Optional

import openpyxl

# 导入工具类
from utils.local_utils import Utils

# 导入配置类型用于 Type Hinting (仅用于类型检查，不用于运行时逻辑)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from packages.excel_engine.src.config import ExcelEngineConfig

class DataProcessor:
    """
    配置驱动的Excel报告处理器。
    """
    def __init__(self, config: 'ExcelEngineConfig', external_data: dict):
        """
        (已更新) 初始化处理器。
        """
        self.config = config
        self.excel_handler = None 
        self.calculated_data = {}
        self.external_data = external_data or {}
        
        # [重构 2] 显式获取并存储关键路径，供后续调用 Utils 使用
        # 假设 config.path 已经是一个 PathConfig 对象
        self.resources_dir = Path(self.config.path.resources_dir)
        self.cache_dir = Path(self.config.path.temp_dir) # 注意：这里使用 temp_dir 作为缓存目录

        # [重构 3] 调用 Utils 时传入 resources_dir
        # 注意：model_definitions 需要转为字典供 Utils 使用
        model_def_dict = self.config.model_definitions.model_dump() 
        self.product_models = Utils.extract_product_models(
            model_def_dict, 
            resources_dir=self.resources_dir
        ) 
        
    def run(self):
        """
        主调度方法。
        """
        logging.info(f"--- DataProcessor 开始运行 ---")

        # 调度并执行所有任务
        jobs = self.config.data_processing_jobs 
        logging.info(f"发现 {len(jobs)} 个待处理任务...")

        for i, job_config in enumerate(jobs, 1):
            # 将 Pydantic 对象转为字典，方便后续处理
            # 这是一个关键的兼容性步骤，因为现有逻辑大量依赖 dict.get()
            job_dict = job_config.model_dump()

            job_type = job_dict.get('job_type')
            logging.info(f"--> 开始执行任务 {i}/{len(jobs)}: 类型 = {job_type}")
    
            if job_type == "parse_text_from_cells": 
                self._execute_parse_text_from_cells_job(job_dict)
            elif job_type == "extract_tila_target": 
                self._execute_extract_tila_target_job(job_dict) 
            elif job_type == "extract_monthly_yield_estimate": 
                self._execute_extract_monthly_yield_estimate_job(job_dict) 
            elif job_type == "extract_risk_items": 
                self._execute_extract_risk_items_job(job_dict) 
            elif job_type == "prepare_summary_data":
                self._execute_prepare_summary_data(job_dict)
            else:
                logging.warning(f"未知的任务类型 '{job_type}'，已跳过。")

        logging.info(f"{json.dumps(self.calculated_data, ensure_ascii=False, indent=2)}")

        logging.info(f"--- DataProcessor 运行结束 ---")
        return self.calculated_data.get('summary_report_data')
    
    def _execute_prepare_summary_data(self, job_config: dict):
        """
        仅负责准备用于填充模板的数据，并将其存入 self.calculated_data。
        """
        logging.info("    开始执行“准备摘要数据”任务...")
        
        all_reports_data = self.__prepare_data_for_templating()
        
        if not all_reports_data:
            logging.warning("    没有可用于准备摘要的数据。")
            return
        
        self.calculated_data['summary_report_data'] = all_reports_data
        logging.info(f"    已成功为 {len(all_reports_data)} 个产品型号准备好摘要数据。")

    def __prepare_data_for_templating(self) -> list[dict]:
        """
        (已更新) 增加了"与提拉目标Gap"的衍生计算逻辑。
        """
        logging.info("开始准备模板数据...")
        all_reports_data = []
        num_models = len(self.product_models)
        logging.info(f"需要处理 {num_models} 个产品型号")

        dc = self.calculated_data
        daily_yield_list = dc.get('daily_yield_change', [])
        bp_target_list = dc.get('bp_target', [])
        tila_target_list = dc.get('tila_target', [])
        prod_yield_list = dc.get('production_yield_values', [])
        month_yield_list = dc.get('monthly_yield_values', []) 
        best_batch_list = dc.get('best_batch', [])
        latest_batch_list = dc.get('latest_batch', [])
        risk_items_map = dc.get('risk_items', "/") 

        for i, model in enumerate(self.product_models):
            logging.info(f"正在处理产品型号 {i+1}/{num_models}: {model}")
            
            # 1. 安全地获取原始数据
            estimated_yield_str = month_yield_list[i] if i < len(month_yield_list) else "／"
            tila_target_str = tila_target_list[i] if i < len(tila_target_list) else "／"
            
            formatted_titles = self.external_data.get(model, {}).get('formatted_titles', [])
            new_exceptions = '、'.join(formatted_titles) if formatted_titles else "/"

            # 2. 调用辅助函数进行安全转换
            float_yield = Utils.safe_convert_percent_to_float(estimated_yield_str)
            float_tila = Utils.safe_convert_percent_to_float(tila_target_str)

            # 3. 执行计算
            estimated_tila_gap_str = "／" 
            if float_yield is not None and float_tila is not None:
                gap_value = float_yield - float_tila
                estimated_tila_gap_str = f"{gap_value:.1%}"
                logging.info(f"型号 {model} 的Gap计算结果: {estimated_yield_str} - {tila_target_str} = {estimated_tila_gap_str}")

            # 构建数据字典
            report_data = {
                'model_name': model,
                'daily_yield_change': daily_yield_list[i] if i < len(daily_yield_list) else "／",
                'new_exceptions': new_exceptions,
                'known_exceptions': "/",
                'bp_target': bp_target_list[i] if i < len(bp_target_list) else "／",
                'tila_target': tila_target_str, 
                'prod_target': prod_yield_list[i] if i < len(prod_yield_list) else "／",
                'estimated_yield': estimated_yield_str, 
                'estimated_tila_gap': estimated_tila_gap_str, 
                'best_batch': best_batch_list[i] if i < len(bp_target_list) else "／",
                'latest_batch': latest_batch_list[i] if i < len(bp_target_list) else "／",
                'risk_items': risk_items_map.get(model, "/") if isinstance(risk_items_map, dict) else "/",
                'unique_exceptions': "/",
                'array_opportunities': "/",
                'oled_opportunities': "/",
                'tp_opportunities': "/"
            }
            all_reports_data.append(report_data)

        logging.info(f"模板数据准备完成，共处理 {len(all_reports_data)} 个产品型号的数据")
        return all_reports_data

    def _execute_parse_text_from_cells_job(self, job_config: dict):
        """
        (通用方法) 解析文本
        """
        output_key = job_config.get("output_key")
        if not output_key:
            logging.error(f"任务 '{job_config.get('description')}' 配置错误：缺少 'output_key'。")
            return

        # [重构 4] 传入 self.resources_dir
        source_path = Utils.get_safe_source_path(job_config, local_cache_dir=self.resources_dir)
        if not source_path or not source_path.is_file():
            logging.error(f"  未能获取有效的源文件路径，任务 '{output_key}' 中止。")
            return

        sheet_name = job_config.get("sheet_name")
        pattern = job_config.get("pattern")
        sequence = job_config.get("cell_sequence", {})
        start_cell = sequence.get("start_cell")
        step = sequence.get("step")
        end_row = sequence.get("end_row")

        if not all([source_path.is_file(), sheet_name, pattern, start_cell, isinstance(step, int), isinstance(end_row, int)]):
            logging.error(f"任务 '{output_key}' 配置不完整、类型错误或源文件不存在。")
            return

        try:
            source_wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
            source_ws = source_wb[str(sheet_name)]

            col_letter = ''.join(filter(str.isalpha, start_cell))
            current_row = int(''.join(filter(str.isdigit, start_cell)))

            extracted_list = []
            consecutive_none_count = 0
            logging.info(f"  任务 '{output_key}': 开始在 {source_path.name}[{sheet_name}] 中搜索...")
            
            while current_row <= end_row:
                cell_address = f"{col_letter}{current_row}"
                cell_value = source_ws[cell_address].value
                
                if cell_value is None:
                    consecutive_none_count += 1
                else:
                    consecutive_none_count = 0
                
                if consecutive_none_count >= 2:
                    logging.info(f"  检测到连续两次空值，提取在第 {current_row} 行提前终止。")
                    break

                if isinstance(cell_value, str):
                    match = re.search(str(pattern), cell_value)
                    if match:
                        extracted_value = match.group(1).strip()
                        logging.info(f"  在单元格 {cell_address} 找到匹配项: {extracted_value}")
                        extracted_list.append(extracted_value)

                current_row += step

            if extracted_list:
                self.calculated_data[output_key] = extracted_list
                logging.info(f"  数据提取成功: '{output_key}' 已存为包含 {len(extracted_list)} 个值的列表。")
            else:
                logging.warning(f"  未能在指定的单元格序列中找到与模式 '{pattern}' 匹配的数据。")

        except Exception as e:
            logging.error(f"  处理任务 '{output_key}' 时发生意外错误: {e}", exc_info=True)
        finally:
            if 'source_wb' in locals():
                source_wb.close()
    
    def _execute_extract_tila_target_job(self, job_config: dict):
        """
        (多步骤任务) 提取提拉良率目标
        """
        logging.info(" 开始执行“提取提拉良率目标”多步骤任务...")

        step2_config = job_config.get("row_locator", {})
        step3_config = job_config.get("column_locator", {})
        
        try:
            product_models = self.product_models
            logging.info(f" 第一步完成：提取到 {len(product_models)} 个产品型号。")
            
            # [重构 5] 传入 self.resources_dir
            s2_full_path = Utils.get_safe_source_path(step2_config, local_cache_dir=self.resources_dir)
            if not s2_full_path or not s2_full_path.is_file():
                logging.error(f"    未能获取有效的源文件路径，任务中止。")
                return

            s2_sheet_name = step2_config.get("sheet_name")
            source_wb = openpyxl.load_workbook(s2_full_path, read_only=True, data_only=True)
            source_ws = source_wb[s2_sheet_name]

            model_to_row_map = self.__tila_step2_find_model_rows(step2_config, product_models, source_ws)
            logging.info(f" 第二步完成：已为 {len(model_to_row_map)} 个型号定位到行。")

            target_column = self.__tila_step3_find_month_column(step3_config, source_ws)
            if not target_column:
                logging.error(" 第三步失败：未能在指定行找到当前月份列，任务中止。")
                return
            logging.info(f" 第三步完成：找到当前月份所在列为 '{target_column}'。")

            final_values = []
            for model in product_models:
                if model in model_to_row_map:
                    target_row = model_to_row_map[model]
                    cell_address = f"{target_column}{target_row}"
                    value = source_ws[cell_address].value
                    if isinstance(value, (int, float)):
                        final_values.append(f"{value:.1%}")
                    logging.info(f" -> 型号 '{model}' (行 {target_row}) 的目标值为: {value}")
                else:
                    final_values.append("/")
                    logging.warning(f" -> 型号 '{model}' 未在指定列中找到，结果记为 None。")
            
            self.calculated_data['tila_target'] = final_values
            logging.info(f" 任务完成: 'tila_target' 已存为包含 {len(final_values)} 个值的列表。")
        except Exception as e:
            logging.error(f" 处理任务 'extract_tila_target' 时发生意外错误: {e}", exc_info=True)

    def __tila_step2_find_model_rows(self, step2_config: dict, product_models: list, worksheet) -> dict:
        """
        辅助方法: 查找行号
        """
        search_col = step2_config.get("search_column")
        model_to_row_map = {}
        
        for row in range(1, 1001):
            cell_address = f"{search_col}{row}"
            cell_value = worksheet[cell_address].value
            
            if isinstance(cell_value, str):
                for model in product_models:
                    if model in cell_value and model not in model_to_row_map:
                        model_to_row_map[model] = row
                        if len(model_to_row_map) == len(product_models):
                            return model_to_row_map
        return model_to_row_map

    def __tila_step3_find_month_column(self, step3_config: dict, worksheet) -> Optional[str]:
        """
        辅助方法: 查找月份列
        """
        search_row = step3_config.get("search_row")
        month_format = step3_config.get("month_format")
        
        current_month = dt.now().month
        search_text = (month_format or "{month}月").format(month=current_month)
        logging.info(f" 第三步：正在第 {search_row} 行查找内容包含 '{search_text}' 的单元格...")

        for col in range(1, 50):
            cell = worksheet.cell(row=search_row, column=col)
            if cell.value and isinstance(cell.value, str) and search_text in cell.value:
                return cell.column_letter
        return None
    
    def _execute_extract_monthly_yield_estimate_job(self, job_config: dict):
        """
        (多步骤任务) 提取月度良率预估
        """
        logging.info("    开始执行“提取月度良率预估”任务...")
        
        try:
            # --- 步骤1: 动态定位源文件 ---
            file_locator_config = job_config.get("file_locator", {})
            initial_target_path = self.__find_latest_file(file_locator_config)
            if not initial_target_path:
                logging.error("    未能找到源文件，任务中止。")
                return
            
            source_path = Utils.resolve_lock_file(initial_target_path)
            
            # [重构 6] 使用 self.resources_dir
            source_file_path = Utils.get_local_copy(source_path, self.resources_dir)
            if not source_file_path:
                logging.error("    未能根据 file_locator 配置找到源文件，任务中止。")
                return

            # --- 步骤2: 加载工作簿和工作表 ---
            locator_config = job_config.get("cell_locator", {})
            sheet_name = locator_config.get("sheet_name")
            source_wb = openpyxl.load_workbook(source_file_path, read_only=True, data_only=True)
            source_ws = source_wb[sheet_name]
            header_row = locator_config.get("header_row", 1)

            # --- 步骤3: 定位所有需要的列 ---
            model_col_config = locator_config.get("row_locator", {})
            model_col = self.__find_column_by_header(source_ws, model_col_config, header_row)
            
            col_locator_config = locator_config.get("column_locator", {})
            prod_yield_col_config = col_locator_config.get("production_yield_col", {})
            month_yield_col_config = col_locator_config.get("monthly_yield_col", {})
            
            prod_yield_col = self.__find_column_by_header(source_ws, prod_yield_col_config, header_row)
            month_yield_col = self.__find_column_by_format(source_ws, month_yield_col_config, header_row)

            if not all([model_col, prod_yield_col, month_yield_col]):
                logging.error("    未能定位到所有必需的列（型号、排产、当月），任务中止。")
                return
            logging.info(f"    所有关键列定位成功: 型号列={model_col}, 排产良率列={prod_yield_col}, 当月预估列={month_yield_col}")

            # --- 步骤4: 遍历产品型号，查找行并提取数据 ---
            product_models = self.product_models
            if not product_models:
                logging.warning("    产品型号列表为空，无法进行数据提取。")
                return

            model_to_row_map = {}
            for row_idx in range(header_row + 1, source_ws.max_row + 1):
                cell_value = source_ws[f"{model_col}{row_idx}"].value
                if isinstance(cell_value, str):
                    for model in product_models:
                        if model in cell_value:
                            model_to_row_map[model] = row_idx
                            break 

            production_yield_list = []
            monthly_yield_list = []
            for model in product_models:
                if model in model_to_row_map:
                    target_row = model_to_row_map[model]
                    prod_value = source_ws[f"{prod_yield_col}{target_row}"].value
                    month_value = source_ws[f"{month_yield_col}{target_row}"].value
                    production_yield_list.append(f"{prod_value:.1%}")
                    monthly_yield_list.append(f"{month_value:.1%}")
                else:
                    production_yield_list.append("/")
                    monthly_yield_list.append("/")
                    logging.warning(f"      在 {model_col} 列中未找到型号 '{model}' 对应的行。")
            
            self.calculated_data['production_yield_values'] = production_yield_list
            self.calculated_data['monthly_yield_values'] = monthly_yield_list
            logging.info("    任务完成: 已成功提取'排产良率'和'当月预估'的数据列表。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_monthly_yield_estimate' 时发生意外错误: {e}", exc_info=True)

    def __find_latest_file(self, locator_config: dict) -> Path | None:
        """根据配置在目录中查找最新的匹配文件，包含二级动态目录查找。"""
        base_path = Path(locator_config.get("base_path", ""))
        name_contains = locator_config.get("name_contains", "")
        dir_rule = locator_config.get("directory_rule", {})

        if not base_path.is_dir():
            logging.error(f"    基础路径不存在或不是一个目录: {base_path}")
            return None

        # --- 第一阶段：查找最新子目录 ---
        if dir_rule:
            prefix = dir_rule.get("prefix")
            if prefix:
                current_week = datetime.datetime.now().isocalendar()[1]
                search_paths = []
                
                for week_offset in range(6): 
                    target_week = current_week - week_offset
                    if target_week < 0: continue
                        
                    dir_name = f"{prefix}{target_week}"
                    dir_path = base_path / dir_name
                    
                    if dir_path.is_dir():
                        search_paths.append(dir_path)
                        logging.info(f"    找到目录: {dir_name}")
                        found_file = self.__search_file_in_directory(dir_path, name_contains)
                        if found_file:
                            return found_file
                
                if not search_paths:
                    logging.warning(f"    未能在 '{base_path}' 下找到任何以 '{prefix}' 开头的子目录。")
                    return None

        # --- 第二阶段：在基础路径直接查找 ---
        return self.__search_file_in_directory(base_path, name_contains)


    def __search_file_in_directory(self, directory: Path, name_contains: str) -> Path | None:
        """在指定目录中查找最新的匹配文件"""
        if not name_contains: return None
        
        current_month = datetime.date.today().month
        month_string_to_find = f"{current_month}月"

        latest_file = None
        latest_time = 0

        logging.info(f"    正在目录 '{directory.name}' 中查找包含 '{name_contains}' 和 '{month_string_to_find}' 的最新文件...")
        try:
            for filename in os.listdir(directory):
                if (name_contains in filename and 
                    not filename.startswith('~$') and 
                    month_string_to_find in filename):
                    file_path = directory / filename
                    if file_path.is_file():
                        mod_time = file_path.stat().st_mtime
                        if mod_time > latest_time:
                            latest_time = mod_time
                            latest_file = file_path
        except OSError as e:
            logging.error(f"    遍历目录出错: {e}")
            return None
        
        if latest_file:
            logging.info(f"      -> 找到最新文件: {latest_file.name}")
        else:
            logging.warning(f"    未能找到包含 '{name_contains}' 的文件。")
        
        return latest_file

    def __find_column_by_header(self, worksheet, header_config: dict, header_row: int) -> Optional[str]:
        """(辅助) 根据表头名称查找列"""
        header_name = header_config.get("header_name")
        occurrence = header_config.get("occurrence", 1)
        count = 0
        for cell in worksheet[header_row]:
            if cell.value and isinstance(cell.value, str) and (header_name or "") in cell.value:
                count += 1
                if count == occurrence:
                    return cell.column_letter
        return None

    def __find_column_by_format(self, worksheet, format_config: dict, header_row: int) -> Optional[str]:
        """(辅助) 根据动态格式化的表头名称查找列"""
        header_format = format_config.get("header_format")
        current_month = dt.now().month
        search_text = (header_format or "{month}月").format(month=current_month)
        for cell in worksheet[header_row]:
            if cell.value and isinstance(cell.value, str) and search_text in cell.value:
                return cell.column_letter
        return None
    
    def _execute_extract_risk_items_job(self, job_config: dict):
        """
        (多步骤任务) 提取风险品信息
        """
        logging.info("    开始执行“提取风险品信息”任务...")
        
        reader_cfg = job_config.get("template_reader_config", {})
        parser_cfg = job_config.get("parser_config", {})
        plan_finder_cfg = job_config.get("plan_finder_config", {})
        
        model_text_map = {} 
        model_data_map = {} 
        
        try:
            # --- 步骤1: 提取风险品 ---
            # [重构 7] 传入 self.resources_dir
            source_path = Utils.get_safe_source_path(reader_cfg, local_cache_dir=self.resources_dir)
            if not source_path: 
                logging.error("无法获取模板文件，步骤1失败")
                return

            wb = openpyxl.load_workbook(str(source_path), read_only=True, data_only=True)
            ws = wb[reader_cfg.get("sheet_name")]
            cell_sequence = reader_cfg.get("cell_sequence", {})
            block_pattern = reader_cfg.get("block_pattern")
            
            col_letter = ''.join(filter(str.isalpha, cell_sequence.get('start_cell')))
            start_row = int(''.join(filter(str.isdigit, cell_sequence.get('start_cell'))))
            step = cell_sequence.get('step')

            patterns = [parser_cfg.get(k) for k in parser_cfg if k.startswith('item_pattern')]
            
            for i, model in enumerate(self.product_models):
                current_row = start_row + i * step
                cell_value = ws[f"{col_letter}{current_row}"].value
                
                if isinstance(cell_value, str):
                    block_match = re.search(block_pattern, cell_value, re.DOTALL)
                    if block_match:
                        text_block = block_match.group(1).strip()
                        model_text_map[model] = text_block 
                        
                        model_data_map[model] = []
                        for pat in patterns:
                            if pat:
                                matches = re.findall(pat, text_block)
                                model_data_map[model].extend(matches)
            wb.close()
            logging.info("      -> 步骤1完成：已从新模板中解析出风险品名称和良率。")

            # --- 步骤2: 获取“基线”释放计划 ---
            baseline_cfg = plan_finder_cfg.get("old_release_plan_finder", {})
            baseline_plan_map = self.__risk_items_build_baseline_plan_lookup(baseline_cfg)
            logging.info(f"      -> 步骤2完成：已获取 {len(baseline_plan_map)} 条“基线”释放计划。")

            # --- 步骤3: 获取“更新”释放计划 ---
            update_cfg = plan_finder_cfg.get("new_release_plan_finder", {})
            update_plan_map = self.__risk_items_build_update_plan_lookup(update_cfg)
            logging.info(f"      -> 步骤3完成：已获取 {len(update_plan_map)} 条“更新”释放计划。")

            # --- 步骤4: 合并释放计划 ---
            final_plan_map = baseline_plan_map.copy()
            final_plan_map.update(update_plan_map)
            logging.info(f"      -> 步骤4完成：已合并释放计划，共 {len(final_plan_map)} 条。")

            # --- 步骤5: 组装最终报告 ---
            final_report_strings = {}
            for model, text_block in model_text_map.items():
                modified_text_block = text_block
                
                for risk_name_raw, yield_str_raw in model_data_map.get(model, []):
                    risk_name = risk_name_raw.strip()
                    yield_str = yield_str_raw.strip()
                    
                    plan_str = final_plan_map.get((model, risk_name)) 
                    
                    if plan_str: 
                        original_line_pattern = re.compile(re.escape(risk_name) + r'\s*' + re.escape(yield_str))
                        replacement_line = f"{risk_name} {yield_str}：{plan_str}"
                        modified_text_block = original_line_pattern.sub(replacement_line, modified_text_block)
                
                final_report_strings[model] = modified_text_block
            
            if final_report_strings:
                self.calculated_data['risk_items'] = final_report_strings
                logging.info("      -> 步骤5完成：已生成最终的风险品信息字符串。")

        except Exception as e:
            logging.error(f"    处理任务 'extract_risk_items' 时发生意外错误: {e}", exc_info=True)
        finally:
            if 'wb' in locals() and wb: wb.close()
    
    def __risk_items_build_baseline_plan_lookup(self, config: dict) -> dict:
        """
        (新增) 步骤1：从“最近的旧日报”中，按产品型号匹配，提取“基线”释放计划。
        """
        baseline_plan_map = {}
        if not config:
            logging.warning("    未配置 'old_release_plan_finder'，跳过基线计划提取。")
            return baseline_plan_map

        # --- 1. 获取源文件 (保持不变) ---
        dynamic_path_cfg = config.get("dynamic_path_config", {})
        source_path = Utils.find_previous_report_file(dynamic_path_cfg) 
        if not source_path:
            logging.warning("    未能找到旧日报文件，无法提取基线计划。")
            return baseline_plan_map

        source_file_path = Utils.get_local_copy(source_path, self.cache_dir)
        if not source_file_path:
            logging.warning("    复制旧日报文件失败，无法提取基线计划。")
            return {}

        # =========================================================================
        # [统一处理] 参数清洗与类型断言区 (Sanitization Block)
        # 目的：将所有 Config 中的不确定类型，统一转换为确定的 int/str，并进行非空校验
        # =========================================================================
        try:
            # A. 提取原始值
            raw_sheet = config.get("sheet_name")
            raw_model_col = config.get("product_model_column")
            raw_start_row = config.get("model_start_row")
            raw_step = config.get("model_step")
            raw_risk_col = config.get("risk_content_column")
            raw_risk_offset = config.get("risk_content_offset")
            raw_block_pattern = config.get("block_pattern")
            raw_parser_pattern = config.get("parser_pattern")

            # B. 统一非空校验 (注意：risk_offset 可以是 0，所以必须用 is not None)
            # 只要有一个是 None，就抛出异常或返回
            required_raws = [
                raw_sheet, raw_model_col, raw_start_row, raw_step, 
                raw_risk_col, raw_risk_offset, raw_block_pattern, raw_parser_pattern
            ]
            if any(x is None for x in required_raws):
                logging.error(f"    'old_release_plan_finder' 配置不完整 (存在None值)。配置: {config}")
                return {}

            # C. 统一类型转换 (Type Casting)
            # 这里强制转换，既能通过 Pylance 检查，也能防止 YAML 解析出的奇怪类型
            sheet_name: str = str(raw_sheet)
            model_col: str = str(raw_model_col)
            risk_col: str = str(raw_risk_col)
            block_pattern: str = str(raw_block_pattern)
            parser_pattern: str = str(raw_parser_pattern)
            
            # 整数强制转换 (如果 YAML 里写的是 "5"，这里转为 5)
            start_row: int = int(raw_start_row) # type: ignore
            step: int = int(raw_step)           # type: ignore
            offset: int = int(raw_risk_offset)  # type: ignore

        except ValueError as e:
            logging.error(f"    配置参数类型错误 (无法转为整数): {e}")
            return {}
        except Exception as e:
            logging.error(f"    配置解析发生未知错误: {e}")
            return {}
        
        # =========================================================================
        # 业务逻辑区 (此时所有变量类型都是确定的，不会再报错)
        # =========================================================================

        try:
            wb = openpyxl.load_workbook(source_file_path, read_only=True, data_only=True)
            ws = wb[sheet_name]

            for model in self.product_models:
                found = False
                
                # 使用转换后的 'start_row' 和 'step'，Pylance 不会再报错
                for row_idx in range(start_row, ws.max_row + 1, step): 
                    
                    cell_value = ws[f"{model_col}{row_idx}"].value
                    
                    # 显式转为 str 比较，更加安全
                    if cell_value and str(model) in str(cell_value):
                        
                        # 使用转换后的 'offset'
                        risk_row = row_idx + offset 
                        risk_cell_value = ws[f"{risk_col}{risk_row}"].value
                        
                        if isinstance(risk_cell_value, str):
                            # 使用转换后的 'block_pattern'
                            block_match = re.search(block_pattern, risk_cell_value, re.DOTALL) 
                            if block_match:
                                text_block = block_match.group(1).strip()
                                # 使用转换后的 'parser_pattern'
                                matches = re.findall(parser_pattern, text_block) 
                                for risk_name_raw, plan_str_raw in matches:
                                    risk_name = risk_name_raw.strip()
                                    plan_str = plan_str_raw.strip()
                                    if risk_name and plan_str:
                                        baseline_plan_map[(model, risk_name)] = plan_str
                        found = True
                        break 
                
                if not found:
                    # logging.warning(f"    在旧日报的 {model_col} 列未找到型号 '{model}'。")
                    pass # 降噪，暂时不打印
            
            wb.close()
            return baseline_plan_map
            
        except Exception as e:
            logging.error(f"    提取“基线”释放计划时发生错误: {e}", exc_info=True)
            if 'wb' in locals() and wb: wb.close()
            return {}
        
    def __risk_items_build_update_plan_lookup(self, config: dict) -> dict:
        """
        (新增) 步骤2：从“风险品汇总表”中，提取“更新”释放计划。
        """
        update_plan_map = {}
        if not config:
            logging.warning("    未配置 'new_release_plan_finder'，跳过更新计划提取。")
            return update_plan_map
        
        # [重构 9] 传入 self.resources_dir
        source_path = Utils.get_safe_source_path(config, local_cache_dir=self.resources_dir)
        sheet_name = config.get("sheet_name")
        if not source_path or not sheet_name:
            logging.error(f"    未能获取有效的“风险品汇总表”路径，任务中止。")
            return {}

        try:
            worksheet = openpyxl.load_workbook(source_path, data_only=True)[sheet_name]
            
            header_row = config.get("header_row", 1)
            model_col_header = config.get("product_model_column")
            risk_col_header = config.get("risk_item_column")
            plan_col_header = config.get("release_plan_column")

            model_col = self.__find_column_by_header(worksheet, {'header_name': model_col_header}, header_row)
            risk_col = self.__find_column_by_header(worksheet, {'header_name': risk_col_header}, header_row)
            plan_col = self.__find_column_by_header(worksheet, {'header_name': plan_col_header}, header_row)
            if not all([model_col, risk_col, plan_col]):
                logging.error("    未能在“风险品汇总表”中定位到所有必需的列。")
                return {}

            for row_idx in range(header_row + 1, worksheet.max_row + 1):
                model = worksheet[f"{model_col}{row_idx}"].value
                risk = worksheet[f"{risk_col}{row_idx}"].value
                plan = worksheet[f"{plan_col}{row_idx}"].value
                if model and risk:
                    update_plan_map[(str(model).strip(), str(risk).strip())] = str(plan).strip() if plan else ""
            
            return update_plan_map
        except Exception as e:
            logging.error(f"    加载“风险品汇总表”时出错: {e}", exc_info=True)
            return {}