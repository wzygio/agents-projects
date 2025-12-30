# core/section_generators/risk_control_section.py (V2.0 - 依赖注入重构版)
import logging, re, math, os
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Dict, Any, List, Optional

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR
from pptx.presentation import Presentation as PptxPresentationObject

from packages.ppt_engine.src.config import PptEngineConfig
from packages.ppt_engine.src.infrastructure.excel_reader import ExcelReader
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from packages.ppt_engine.src.core.table_processor import TableProcessor

class RiskControlSectionGenerator:
    """
    负责生成PPT第三章“风险品释放管控”相关的所有页面。
    """
    def __init__(self, prs: PptxPresentationObject, config: PptEngineConfig, element_processor: ElementProcessor):
        """
        构造函数，初始化时会加载本章节专属的配置。
        
        Args:
            prs: PPT 演示文稿对象
            config: 强类型的配置对象
            element_processor: [Dependency Injection] 注入的元素处理器
        """
        # 添加类型检查
        if not isinstance(prs, PptxPresentationObject):
            raise TypeError("prs参数必须是PptxPresentationObject类型")
           
        self.prs = prs
        self.config = config # 保存传入的完整配置
        self.element_processor = element_processor
        
        # 从传入的config中，安全地获取本章节的配置字典
        self.cfg = self.config.sections.risk_control
        self.paths_cfg = self.config.path

        self.processed_data: Dict[str, Any] = {}
        logging.info("RiskControlSectionGenerator 已初始化。")

    def generate(self):
        """
        生成本章节所有页面的主方法。
        """
        logging.info("开始生成第三章：风险品释放管控...")
        self._prepare_data()
        self._render_slides()
        logging.info("第三章生成完毕。")

    def  _prepare_data(self):
        """
        [已实现] 私有方法，负责准备本章节所需的所有数据。
        """
        logging.info("开始准备第三章所需的数据...")
        try:
            if self.paths_cfg is None or self.cfg is None:
                logging.error("路径配置或章节配置为空，请检查config。")
                return
            base_dir = self.paths_cfg.get('base_dir', '.')
            resources_dir = self.paths_cfg.get('resources_dir', 'resources')
            excel_filename = self.paths_cfg.get('data_source_excel_risk')

            sheet_name = self.cfg.get('sheet_name')
            excel_range = self.cfg.get('excel_table_range')
            columns_to_keep = self.cfg.get('columns_to_keep')

            if not all([excel_filename, sheet_name, excel_range]):
                logging.error("第三章配置不完整，请检查config。")
                return
            
            excel_path = os.path.join(str(base_dir), str(resources_dir), str(excel_filename))
            
            raw_df = ExcelReader.read_excel_range(
                str(excel_path),
                sheet_name=sheet_name,
                cell_range=excel_range,
                columns_to_read=columns_to_keep
            )

            if raw_df is None or raw_df.empty:
                logging.warning("未能从Excel中读取到风险品数据，或数据为空。")
                self.processed_data['table'] = pd.DataFrame() # 确保processed_data中有table键
                return

            final_df = self._standardize_table(raw_df)
            self.processed_data['table'] = final_df
            logging.info("第三章所需数据已成功准备完毕。")

        except Exception as e:
            logging.error(f"在准备第三章数据时发生严重错误: {e}", exc_info=True)
    
    def _render_slides(self):
        """
        [已实现] 渲染本章节的所有幻灯片，包括分页逻辑。
        """
        logging.info("开始渲染第三章的PPT页面...")

         # 1. 获取数据源
        df = self.processed_data.get('table')
        if df is None or df.empty:
            logging.warning("没有风险品数据可供渲染，已跳过此章节。")
            return
        
        if self.paths_cfg is None or self.cfg is None:
            logging.error("路径配置为空，请检查config。")
            return

        # 2. 获取渲染参数
        render_cfg = self.cfg.get('rendering_params', {})
        insert_at_index = render_cfg.get('insert_at_index', 10) # 插入幻灯片位置
        rows_per_slide = render_cfg.get('rows_per_slide', 15) # 每页行数
        title_text = render_cfg.get('title_text', "风险品释放管控") # 标题
        summary_list = render_cfg.get('summary_texts', [" ", " "]) # 摘要文本
        
        # 3. 获取布局配置
        layout_cfg = self.cfg.get('layout', {})

        # 4. 查找空白幻灯片版式
        layout_index = self.element_processor.find_layout_index_by_name(self.prs, "BLANK")
        if layout_index is None:
            logging.error("找不到名为 'BLANK' 的幻灯片版式。")
            return
        blank_layout = self.prs.slide_layouts[layout_index]
        
        # 5. 记录初始幻灯片数量（用于后续排序）
        initial_slide_count = len(self.prs.slides)
        
        # 6. 计算分页数量
        num_data_rows = len(df)
        num_slides_to_create = math.ceil(num_data_rows / rows_per_slide)
        logging.info(f"数据共 {num_data_rows} 行，每页 {rows_per_slide} 行，共需生成 {num_slides_to_create} 个新页面。")
        
        self.paths_cfg = self.config.get('path', {})
        if self.paths_cfg is None:
            logging.error("路径配置为空，请检查config。")
            return
        logo_filename = self.paths_cfg.get('logo')
        logo_path = os.path.join(self.paths_cfg.data_raw_dir, logo_filename)

         # 7. 生成分页幻灯片
        for i in range(num_slides_to_create):
             # 计算数据分片范围
            start_idx, end_idx = i * rows_per_slide, (i + 1) * rows_per_slide
            df_chunk = df.iloc[start_idx:end_idx]
            
            # 创建新幻灯片
            slide = self.prs.slides.add_slide(blank_layout) # type: ignore
            # 添加元素 
            self.element_processor.add_logo(slide, str(logo_path), layout_cfg.get("logo", {})) # 添加logo
            self.element_processor.add_title(slide, title_text, layout_cfg.get("title", {})) # 添加标题
            self.element_processor.add_summary(slide, summary_list, layout_cfg.get("summary", {})) # 添加摘要
            self._add_table(slide, df_chunk) # 添加表格

        # 8. 重排幻灯片
        num_new_slides = len(self.prs.slides) - initial_slide_count
        if num_new_slides > 0:
            self.element_processor.reorder_slides(self.prs, initial_slide_count, num_new_slides, insert_at_index)
        logging.info(f"成功生成并插入 {num_new_slides} 页风险品管控表格。")
    
    def _add_table(self, slide, df: pd.DataFrame):
        """
        [最终修正版] 在幻灯片上创建、合并、填充并格式化一个完整的风险品表格。
        """
        # 1. 【核心修正】我们需要的【所有】表格相关配置，都在 table_layout.base 里
        # 我们直接把这个字典赋给 cfg，并在后续统一使用它
        if self.cfg is None:
            logging.error("配置文件未加载。")
            return
        cfg = self.cfg.get('table_layout', {}).get('base', {})
            
        # 2. 准备数据和表格对象
        # 获取列的多级索引层数（如普通表格为1层，多级表头可能为2层）    
        num_header_rows = df.columns.nlevels 
        # 将多级列索引转换为二维列表，用于生成表头
        header_data = [df.columns.get_level_values(i).tolist() for i in range(num_header_rows)]
        # 将DataFrame数据转换为二维列表，用于填充表格
        body_data = df.values.tolist()
        
        # 表格整体尺寸
        table_shape = slide.shapes.add_table(
            # 总行数=表头行数+数据行数，列数=DataFrame列数
            len(header_data) + len(body_data), len(df.columns),
            Inches(cfg["left"]), Inches(cfg["top"]), Inches(cfg["width"]), Inches(cfg["height"])
        )

        ppt_table = table_shape.table # 获取表格对象
        
        # 3. 渲染表格：所有渲染参数都从统一的 cfg 字典中获取
        ppt_table.style = cfg.get('style_id') # 应用预设表格样式
        TableProcessor._set_dimensions(ppt_table, cfg) # 调用工具类设置行高和列宽（支持逐行/列定制）
        master_cell_map = TableProcessor.merge_cells(ppt_table, [], extra_ranges=cfg.get('merge_ranges', [])) # 执行单元格合并操作，返回主单元格映射表
        TableProcessor._set_table_borders(ppt_table) # 统一设置表格边框样式（默认黑色细线）
        grades_map = self._prepare_color_grades(body_data, cfg.get('columns_to_colorize', [])) # 颜色映射等级
        
        # 4. 定义样式 (所有颜色也都从 cfg 获取)
        header_style = {"font_size": Pt(cfg["header_font_size"]), 
                        "font_name": cfg["font_name"], 
                        "bold": True, 
                        "v_align": MSO_VERTICAL_ANCHOR.MIDDLE, 
                        "h_align": PP_ALIGN.CENTER, 
                        "fill_color": cfg.get("fixed_fill_color"), 
                        "font_color": cfg.get("header_font_color")}
        body_style = {"font_size": Pt(cfg["body_font_size"]), 
                      "font_name": cfg["font_name"], 
                      "bold": False, 
                      "v_align": MSO_VERTICAL_ANCHOR.MIDDLE, 
                      "h_align": PP_ALIGN.LEFT}

        # 5. 填充表头
        for i, row in enumerate(header_data):
            for j, val in enumerate(row):
                # 仅处理合并单元格中的主单元格（避免合并单元格重复填充）
                if master_cell_map.get((i, j), (i, j)) == (i, j):
                    style = header_style.copy()
                    style["text"] = str(val) if val is not None else ""
                    TableProcessor.apply_cell_style(ppt_table.cell(i, j), style) # 应用样式并填充文本内容

        # 6. 填充数据体并应用条件格式化
        fixed_color_limit = cfg.get('fixed_color_cols_end_index', 0)

        for i, row_values in enumerate(body_data):
            for j, val in enumerate(row_values):
                row_idx = i + num_header_rows # 计算在表格中的实际行索引（跳过表头部分）

                if master_cell_map.get((row_idx, j), (row_idx, j)) == (row_idx, j):
                    # 仅处理主单元格
                    style = body_style.copy()
                    style["text"] = str(val) if val is not None else ""
                    
                    if j in grades_map: # 根据风险等级应用条件格式化颜色
                        grade = grades_map[j][i]
                        style["fill_color"] = self._get_color_from_grade(grade) or cfg.get("body_default_fill_color")
                        style["font_color"] = cfg.get("body_default_font_color")
                    elif j < fixed_color_limit: # 前N列使用固定颜色（如序号列）
                        style["fill_color"] = cfg.get("fixed_fill_color")
                        style["font_color"] = cfg.get("header_font_color")
                    else: # 注释：其余列使用默认样式
                        style["fill_color"] = cfg.get("body_default_fill_color")
                        style["font_color"] = cfg.get("body_default_font_color")

                    TableProcessor.apply_cell_style(ppt_table.cell(row_idx, j), style) # 注释：应用最终样式到单元格

    @staticmethod
    def _format_multi_date_cell(cell_value) -> str:
        """
        [内部静态方法] 处理包含日期、多日期、文本或混合内容的单个单元格。
        (此逻辑来自您提供的 format_multi_date_cell 函数)
        """
        # 检查 cell_value 是否为日期类型（包括 date, datetime, 或 pandas 的 Timestamp）
        if isinstance(cell_value, (date, datetime, pd.Timestamp)):
            # 如果是日期类型，格式化为 '%m-%d' 形式并返回
            return cell_value.strftime('%m-%d')
        
        # 如果 cell_value 不是字符串类型，或者其值为 NaN（pandas 中的缺失值），返回空字符串
        if not isinstance(cell_value, str) or pd.isna(cell_value):
            return ''

        # 假设 cell_value 是字符串类型，将其赋值给变量 date_string
        date_string = cell_value
        
        # 使用正则表达式将字符串按逗号、空格、换行符或分号分割成多个部分
        potential_parts = re.split(r'[,\s\n;]+', date_string)
        
        # 初始化一个列表，用于存储处理后的部分
        processed_parts = []
        
        # 遍历分割后的每个部分
        for part in potential_parts:
            # 去除当前部分的前后空白字符
            part = part.strip()
            
            # 如果去除空白后部分为空字符串，则跳过该部分
            if not part:
                continue
            
            try:
                # 尝试将当前部分转换为日期时间对象（使用 pandas 的 to_datetime 方法）
                dt_object = pd.to_datetime(part, errors='raise')
                
                # 如果转换成功，将其格式化为 '%m-%d' 形式，并添加到 processed_parts 列表中
                processed_parts.append(dt_object.strftime('%m-%d'))
            except ValueError:
                # 如果转换失败（即当前部分不是有效的日期格式），直接将原始部分添加到 processed_parts 列表中
                processed_parts.append(part)
        
        # 将处理后的所有部分用换行符连接成一个字符串，并返回
        return '\n'.join(processed_parts)


    def _standardize_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [内部方法] 对给定的DataFrame进行三项处理：填充序号、格式化百分比、格式化日期。
        (此逻辑来自您提供的 standardize_table_risky 函数)
        """
        if df.empty:
            logging.warning("传入的DataFrame为空，不做任何处理。")
            return df
        
        processed_df = df.copy()

        # 1. 填充序号
        try:
            first_col_name = processed_df.columns[0]
            if '序号' in first_col_name:
                processed_df[first_col_name] = range(1, len(processed_df) + 1)
        except IndexError:
            logging.error("DataFrame中没有任何列。")
            return processed_df
            
        # 2. 格式化百分比
        if len(processed_df.columns) > 6:
            col_indices_to_format = [4, 6]
            for idx in col_indices_to_format:
                col_name = processed_df.columns[idx]
                numeric_series = pd.to_numeric(processed_df[col_name], errors='coerce')
                processed_df[col_name] = numeric_series.apply(
                    lambda x: f'{x * 100:.2f}%' if pd.notna(x) else ''
                )

        # 3. 格式化倒数第二列的日期为“月-日”
        last_col_name = processed_df.columns[-2]
        # 调用本类中的另一个辅助方法
        processed_df[last_col_name] = processed_df[last_col_name].apply(self._format_multi_date_cell)

        logging.info("风险品表格数据处理完成。")
        return processed_df
    
    # VVVV--- “数字着色”流水线的所有函数，作为私有静态方法整合进来 ---VVVV
    @staticmethod
    def _try_parse_number(item: Any) -> Optional[float]:
        """一个内部辅助函数，尝试将各种格式的值解析为浮点数。"""
        try: return float(item)
        except (ValueError, TypeError):
            if isinstance(item, str) and item.strip().endswith('%'):
                try: return float(item.strip()[:-1]) / 100.0
                except (ValueError, TypeError): return None
            return None
    
    
    def _classify_by_quartiles(self, data_list: List[Any]) -> List[Optional[int]]:
        """【升级版】根据四分位数将一个列表中的数值数据划分为四个等级 (0, 1, 2, 3)。"""
        numeric_values = [num for item in data_list if (num := self._try_parse_number(item)) is not None]
        if not numeric_values: return [None] * len(data_list)
        
        q1, q2, q3 = np.percentile(numeric_values, [25, 50, 75])
        
        classifications = []
        for item in data_list:
            level = None
            num_val = self._try_parse_number(item)
            if num_val is not None:
                if num_val <= q1: level = 0
                elif q1 < num_val <= q2: level = 1
                elif q2 < num_val <= q3: level = 2
                else: level = 3
            classifications.append(level)
        return classifications

    @staticmethod
    def _get_color_from_grade(grade: Optional[int]) -> Optional[RGBColor]:
        """根据给定的等级 (0-3) 返回对应的RGB颜色对象。"""
        # 根据等级返回对应的颜色
        color_map = {
            # 颜色数值获取：颜色数值由ppt中对应单元格的“其它填充颜色”获取
            0: RGBColor(99, 190, 123),  # 绿色
            1: RGBColor(255, 229, 131), # 黄色
            2: RGBColor(253, 193, 124), # 橙色
            3: RGBColor(248, 105, 107), # 红色
        }
        return color_map.get(grade) if grade is not None else RGBColor(0, 0, 0)  # 返回一个默认颜色，例如白色

    
    def _prepare_color_grades(self, body_data: List[List[Any]], columns_to_colorize: List[int]) -> Dict[int, List[Optional[int]]]:
        """为指定的列预先计算好所有的颜色等级。"""
        grades_map = {}
        for col_idx in columns_to_colorize:
            try:
                column_data = [row[col_idx] for row in body_data]
                grades_map[col_idx] = self._classify_by_quartiles(column_data)
            except IndexError:
                logging.warning(f"列索引 {col_idx} 超出范围，已跳过该列的色阶计算。")
        return grades_map