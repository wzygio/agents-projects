# core/section_generators/anomaly_mgmt_section.py (V2.0 - 依赖注入重构版)
import logging
import pandas as pd
import math
import os 
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from pathlib import Path

from pptx.presentation import Presentation as PptxPresentationObject
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR

from packages.ppt_engine.src.infrastructure.excel_reader import ExcelReader
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from packages.ppt_engine.src.core.table_processor import TableProcessor
from packages.ppt_engine.src.utils.local_utils import Utils

# [Standard 4] Import Standard: 使用 TYPE_CHECKING 防止循环依赖
if TYPE_CHECKING:
    from packages.ppt_engine.src.config import PptEngineConfig

class AnomalyGenerator:
    """
    负责生成PPT第二章“CT异常闭环管理”相关的所有页面。
    """
    def __init__(self, prs: PptxPresentationObject, config: "PptEngineConfig"):
        """
        构造函数，初始化时会加载本章节专属的配置。
        
        Args:
            prs: PPT 演示文稿对象
            config: 强类型的配置对象 (Dependency Injection)
        """
        self.prs = prs
        self.config = config
        self.element_processor = ElementProcessor(self.config)
        
        # [Standard 3] Type Access (Hybrid Strategy):
        # 1. 访问 Config 对象下的 sections 属性 (点号访问)
        # 2. 将特定章节配置转换为字典 (Dict Conversion)，以兼容遗留的 .get() 逻辑
        section_config_obj = getattr(self.config.sections, 'anomaly_management')
        
        if hasattr(section_config_obj, 'model_dump'):
            self.cfg = section_config_obj.model_dump()
        elif hasattr(section_config_obj, 'dict'):
            self.cfg = section_config_obj.dict()
        else:
            self.cfg = dict(section_config_obj) if section_config_obj else {}

        self.processed_data: Dict[str, Any] = {}
        logging.info("AnomalyGenerator 已初始化。")

    def generate(self):
        """
        生成本章节所有页面的主方法。       
        """
        logging.info("开始生成第二章：CT异常闭环管理...")
        self._prepare_data()
        self._render_slides()
        logging.info("第二章生成完毕。")

    def _prepare_data(self):
        """
        [已实现] 私有方法，负责准备本章节所需的所有数据。
        """
        logging.info("开始准备第二章所需的数据...")
        try:
            # [Standard 3] Type Access: 使用点号访问全局路径配置
            paths = self.config.paths
            # [Global Purge] 不再依赖全局变量，从 config 提取路径
            resources_dir = Path(paths.resources_dir)
            cache_dir = Path(paths.data_cache_dir)

            source_excel_filename = paths.data_source_excel_anomaly
            dest_parquet_filename = paths.data_source_parquet_anomaly
            
            # 业务逻辑配置仍使用字典访问 (来自 __init__ 的转换)
            sheet_name = str(self.cfg.get('sheet_name'))

            # 获取当前时间并判断上午/下午
            now = datetime.now()
            if now.hour < 12:  # 上午（0-11时）
                default_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')  # 昨天的日期
            else:  # 下午（12-23时）
                default_date = now.strftime('%Y-%m-%d')  # 今天的日期

            date_str = self.cfg.get('specific_date') or default_date
            logging.info(f"使用日期: {date_str}")

            # 检查必要配置是否存在
            if not all([source_excel_filename, dest_parquet_filename, sheet_name, date_str]):
                logging.error(f"第二章配置缺失: source={source_excel_filename}, dest={dest_parquet_filename}, sheet={sheet_name}")
                return

            # [Standard 2] Explicit Interface: 显式传入 resources_dir
            source_excel_path = Utils.find_latest_matching_file(resources_dir, source_excel_filename)
            
            # 使用 pathlib 构建路径
            dest_parquet_path = cache_dir / dest_parquet_filename
            
            # 确保父目录存在
            dest_parquet_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换 Excel 到 Parquet
            ExcelReader.convert_to_parquet(str(source_excel_path), sheet_name, str(dest_parquet_path))
            full_df = pd.read_parquet(dest_parquet_path)
            
            if full_df.empty:
                raise ValueError("转换后的数据为空，请检查原始数据。")
            
            # 处理日期列
            date_col_name = self.cfg.get('summary_params', {}).get('date_column', '通报日期')
            if date_col_name not in full_df.columns:
                raise KeyError(f"未找到日期列: {date_col_name}")
            
            full_df[date_col_name] = pd.to_datetime(full_df[date_col_name], errors='coerce')
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            mask = (full_df[date_col_name].dt.date == target_date)
            daily_data_df = full_df[mask]

            if not daily_data_df.empty:
                # 裁剪列（按列名而非索引）
                cols_to_keep = daily_data_df.columns[1:16]
                if len(cols_to_keep) == 0:
                    raise ValueError("列裁剪后为空，请检查原始数据列数。")
                trimmed_df = daily_data_df[cols_to_keep]

                final_df = self._standardize_table(trimmed_df)
                self.processed_data['table'] = final_df
                
                logging.info("第二章所需数据已成功准备完毕。")
            else:
                logging.warning(f"没有找到指定日期的异常，请检查{source_excel_filename}。")

        except Exception as e:
            logging.error(f"在准备第二章数据时发生严重错误: {e}", exc_info=True)

    def _render_slides(self):
        """
        [已实现] 渲染本章节的所有幻灯片，包括分页逻辑。
        """
        logging.info("开始渲染第二章的PPT页面...")
        df = self.processed_data.get('table')
        if df is None:
            logging.warning("没有处理好的数据，无法渲染第二章页面。")
            return
            
        render_cfg = self.cfg.get('rendering_params', {})
        insert_at_index = render_cfg.get('insert_at_index', 6)
        rows_per_slide = render_cfg.get('rows_per_slide', 3)
        title_text = render_cfg.get('title_text', "CT异常闭环管理")

        blank_layout_index = self.element_processor.find_layout_index_by_name(self.prs, "BLANK")
        if blank_layout_index is None:
            logging.error("在PPT模板中未找到名为'BLANK'的版式，无法创建新页面。请检查模板文件。")
            return
        
        blank_layout = self.prs.slide_layouts[blank_layout_index]

        if df.empty:
            logging.warning("传入的数据为空，不生成任何新页面。")
            return

        summary_part1 = self._generate_summary_part1(df)
        summary_part2 = self._generate_summary_part2(df)
        summary_list = [summary_part1, summary_part2]

        initial_slide_count = len(self.prs.slides)
        num_data_rows = len(df)
        num_slides_to_create = math.ceil(num_data_rows / rows_per_slide)
        logging.info(f"数据共 {num_data_rows} 行，每页 {rows_per_slide} 行，共需生成 {num_slides_to_create} 个新页面。")
        
        # [Standard 3] Type Access & [Global Purge]
        paths = self.config.paths
        logo_filename = paths.logo_filename # 假设 Pydantic model 有此字段，或 paths.logo
        
        # [Global Purge] 替换 DATA_RAW_DIR，使用 config 定义的路径 (通常 logo 在 resources 或 raw 目录)
        logo_dir = Path(paths.data_raw_dir)
        # 检查 logo_filename 是否为 None 或非字符串类型
        if logo_filename is None:
            logging.error("logo_filename 为 None，无法构建 logo 路径")
            logo_path = None
        else:
            logo_path = logo_dir / logo_filename


        for i in range(num_slides_to_create):
            start_idx = i * rows_per_slide
            end_idx = start_idx + rows_per_slide
            df_chunk = df.iloc[start_idx:end_idx]
            
            slide = self.prs.slides.add_slide(blank_layout) # type: ignore
            
            layout_cfg = self.cfg.get('layout', {})
            # 使用动态获取的logo_path
            self.element_processor.add_logo(slide, str(logo_path), layout_cfg["logo"])
            self.element_processor.add_title(slide, title_text, layout_cfg["title"])
            self.element_processor.add_summary(slide, summary_list, layout_cfg["summary"])
            
            self._add_table(slide, df_chunk)

        num_new_slides = len(self.prs.slides) - initial_slide_count
        if num_new_slides > 0:
            self.element_processor.reorder_slides(self.prs, initial_slide_count, num_new_slides, insert_at_index)
        logging.info(f"成功生成并插入 {num_new_slides} 页表格。")

    @staticmethod
    def _standardize_table(df: pd.DataFrame) -> pd.DataFrame:
        """
        [内部静态方法] 接收一个DataFrame，将其指定列的数值转换为百分比字符串。
        """
        # 1. 创建一个副本进行操作，避免修改原始DataFrame
        processed_df = df.copy()

        # 2. 定义要格式化的列的索引 (第6、7、8、9列对应索引5、6、7、8)
        cols_to_format = [5, 6, 7, 8]

        # 3. 遍历需要格式化的列
        for col_idx in cols_to_format:
            if col_idx >= len(processed_df.columns):
                logging.warning(f"尝试格式化索引为 {col_idx} 的列失败，该索引超出范围。")
                continue

            col_name = processed_df.columns[col_idx]
            
            # a. 强制转换为数值，无法转换的值会变为NaN
            numeric_series = pd.to_numeric(processed_df[col_name], errors='coerce')
            
            # b. 对所有非NaN的值应用百分比格式化
            processed_df[col_name] = numeric_series.apply(
                lambda x: f'{x * 100:.2f}%' if pd.notna(x) else ''
            )

        return processed_df

    @staticmethod
    def _generate_summary_part1(df: pd.DataFrame, date_column: str = '通报日期') -> str:
        # 【核心修改】将列名作为默认参数
        if df.empty:
            today_str = datetime.now().strftime('%Y/%#m/%#d')
            return f"{today_str} 8:30 至 {today_str} 18:30 新增异常0项，共回复0项，未回0项；"
        try:
            df[date_column] = pd.to_datetime(df[date_column])
            report_date = df[date_column].iloc[0].date()
            date_str = f"{report_date.year}/{report_date.month}/{report_date.day}"
            start_str, end_str = f"{date_str} 8:30", f"{date_str} 18:30"
        except Exception: return "无法生成摘要：日期处理错误。"
        new_anomalies_count = len(df)
        summary_sentence = (f"{start_str} 至 {end_str} 新增异常{new_anomalies_count}项，共回复{new_anomalies_count}项，未回0项；")
        return summary_sentence
    
    @staticmethod
    def _generate_summary_part2(df: pd.DataFrame, group_by_col: str = '责任厂别') -> str:
        # 【核心修改】将列名作为默认参数
        if df.empty: return ""
        if group_by_col not in df.columns: return "无法生成分类摘要：缺少分组信息。"
        category_counts = df.groupby(group_by_col).size()
        summary_parts = []
        for category, count in category_counts.items():
            part = (f"{category}新增{count}项，已回复{count}项，未回复0项")
            summary_parts.append(part)
        if not summary_parts: return ""
        return "其中" + "；".join(summary_parts)
    
    @staticmethod
    def _get_status_font_color(text_value: str) -> RGBColor:
        """
        [新增] 根据单元格文本内容返回对应的字体颜色。
        """
        normalized_text = str(text_value).strip().lower()
        if normalized_text == "open":
            return RGBColor(255, 0, 0)  # 红色
        elif normalized_text == "close":
            return RGBColor(0, 0, 255)  # 蓝色
        else:
            return RGBColor(0, 0, 0)    # 黑色 (默认)

    def _add_table(self, slide, df: pd.DataFrame):
        """
        [新增] 在幻灯片上创建、填充并格式化一个完整的异常管理表格。
        """
        # 从配置中获取本表格的布局样式
        # 这里的 cfg 是在 __init__ 中转换过的字典
        cfg = self.cfg.get('table_layout', {}).get('base', {})
        if not cfg:
            logging.error("未找到表格布局配置，无法创建表格。")
            return

        if df.empty:
            logging.warning("传入的DataFrame为空，已跳过创建表格。")
            return

        # 1. 数据准备
        num_header_rows = df.columns.nlevels
        header_data = [df.columns.get_level_values(i).tolist() for i in range(num_header_rows)]
        body_data = df.values.tolist()
        total_rows, total_cols = num_header_rows + len(body_data), len(df.columns)
        
        # 2. 创建表格并应用样式ID
        table_shape = slide.shapes.add_table(
            total_rows, total_cols,
            Inches(cfg["left"]), Inches(cfg["top"]),
            Inches(cfg["width"]), Inches(cfg["height"])
        )
        ppt_table = table_shape.table
        ppt_table.style = 'E929F9F4-4A8F-4326-A1B4-22849713DDAB'

        # 3. 【调用工具箱】设置行高、列宽和边框
        TableProcessor._set_dimensions(ppt_table, cfg)
        TableProcessor._set_table_borders(ppt_table)
        TableProcessor._set_cell_margins_to_zero(ppt_table)
        
        # 4. 定义可复用的样式字典
        header_style = {
            "v_align": MSO_VERTICAL_ANCHOR.MIDDLE, "h_align": PP_ALIGN.CENTER,
            "fill_color": RGBColor(217, 217, 217), "font_size": Pt(cfg["header_font_size"]),
            "font_name": cfg["font_name"], "bold": True, "font_color": RGBColor(0, 0, 0)
        }
        body_style = {
            "v_align": MSO_VERTICAL_ANCHOR.MIDDLE, "h_align": PP_ALIGN.LEFT,
            "fill_color": RGBColor(255, 255, 255), "font_size": Pt(cfg["body_font_size"]),
            "font_name": cfg["font_name"], "bold": False, "font_color": RGBColor(0, 0, 0)
        }

        # 5. 填充表头
        for i, header_row_values in enumerate(header_data):
            for j, val in enumerate(header_row_values):
                header_style["text"] = str(val) if val is not None else ""
                TableProcessor.apply_cell_style(ppt_table.cell(i, j), header_style)

        # 6. 填充数据体
        for i, row_values in enumerate(body_data):
            for j, val in enumerate(row_values):
                row_idx, col_idx = i + num_header_rows, j
                current_style = body_style.copy()
                current_style["text"] = str(val) if val is not None else ""
                
                # 如果不是倒数第五列和倒数第六列，则设置为居中
                if j not in [total_cols - 5, total_cols - 6]:
                    current_style["h_align"] = PP_ALIGN.CENTER
                else:
                    current_style["h_align"] = PP_ALIGN.LEFT
                

                # 【核心业务逻辑】对最后一列应用条件格式化
                if j == total_cols - 1:
                    current_style["font_color"] = self._get_status_font_color(val)
                    current_style["h_align"] = PP_ALIGN.CENTER
                
                TableProcessor.apply_cell_style(ppt_table.cell(row_idx, col_idx), current_style)