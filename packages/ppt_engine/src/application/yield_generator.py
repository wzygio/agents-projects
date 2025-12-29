import logging, re, os
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from pathlib import Path

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_VERTICAL_ANCHOR
from pptx.presentation import Presentation as PptxPresentationObject
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

# 引入已重构的类
from packages.ppt_engine.src.utils.local_utils import Utils
from packages.ppt_engine.src.core.table_processor import TableProcessor
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from packages.ppt_engine.src.infrastructure.excel_reader import ExcelReader
from packages.ppt_engine.src.infrastructure.ppt_reader import PptReader
from packages.ppt_engine.src.config import PptEngineConfig, ElementLayout, TableBaseLayout

# 设置 Pandas 的显示选项
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)
pd.set_option("display.max_colwidth", None)

logger = logging.getLogger("YieldDataSectionGenerator")

class YieldDataSectionGenerator:
    """
    [Application Service]
    负责生成PPT第一章“各品类良率数据”相关的所有页面。
    """
    
    DEFAULT_COLORS = {
        'header': RGBColor(217, 217, 217),
        'body': RGBColor(255, 255, 255),
        'white': RGBColor(255, 255, 255),
        'black': RGBColor(0, 0, 0)
    }

    def __init__(self, 
                 prs: PptxPresentationObject, 
                 config: PptEngineConfig,
                 element_processor: ElementProcessor,
                 table_processor: TableProcessor):
        """
        :param prs: PPT对象
        :param config: 强类型配置对象
        :param element_processor: 注入的元素处理器实例
        """
        self.prs = prs
        self.config = config
        self.element_processor = element_processor
        # TableProcessor 目前多为静态方法，但未来若改为实例，这里预留接口
        self.table_processor = table_processor 

        # 预先获取本章节的配置对象 (YieldDataConfig)。注意：这里使用属性访问 config.sections.yield_data
        self.section_cfg = self.config.sections.yield_data
        self.data_cfg = self.section_cfg.data_config
        self.layout_cfg = self.section_cfg.layout_config or {}
        
        # table_layout 也是个复杂对象，我们取其 base 部分
        if self.section_cfg.table_layout:
            self.table_layout_base = self.section_cfg.table_layout.base
        else:
            self.table_layout_base = None

        self.processed_data: Dict[str, Any] = {}
        logger.info("YieldDataSectionGenerator 已初始化。")

    def generate(self):
        """【最终实现】生成本章节所有页面的主方法。"""
        logger.info("开始生成第一章：各品类良率数据...")
        
        # 第一步：准备所有数据
        self._prepare_data()
        
        # 第二步：根据准备好的数据，渲染所有页面
        self._render_slides()
        
        logger.info("第一章生成完毕。")

    def _prepare_data(self):
        """数据准备阶段的总调度方法。"""
        logger.info("开始准备第一章所需的数据...")

        # 1. 查找Excel文件
        # 使用 self.config.path 替代 config.get('path')
        self.paths_cfg = self.config.path
        
        # 显式拼接路径，消除全局变量依赖
        project_root = Path(self.paths_cfg.base_dir) if self.paths_cfg.base_dir else Path.cwd()
        resources_dir = project_root / self.paths_cfg.resources_dir
        data_cache_dir = project_root / self.paths_cfg.data_cache_dir
        excel_keyword = self.paths_cfg.data_source_excel_FPY or '入库良率'
        
        # 调用 Utils 时传入明确路径
        excel_filename = Utils.find_latest_matching_file(resources_dir, excel_keyword)
        if not excel_filename:
            return
        excel_path = resources_dir / excel_filename

        # 2. 【核心】调用地址解析器
        address_maps = self._resolve_dynamic_addresses(str(excel_path))
        
        # 3. 读取数据
        # data_cfg 是 YieldDataConfig 对象，访问 sheet_names 字典
        if self.data_cfg is None:
            raise ValueError("Data configuration object is not initialized")
        sheet_names = self.data_cfg.sheet_names

        
        with ExcelReader(str(excel_path), sheet_names.get("yield_trend", "Sheet1")) as reader1:
            image_paths = reader1.read_images(str(data_cache_dir), address_maps['image_addresses'])
            sentences = reader1.read_sentences(address_maps['sentence_addresses'])

        with ExcelReader(str(excel_path), sheet_names.get("control_plan", "Sheet1")) as reader2:
            full_data_list = reader2.read_table_as_list('B2:V23')

        if full_data_list is None:
            logger.error("未能从Excel中读取到表格数据，终止本章生成。")
            return
        
        # 1. 提取公共表头 (前两行)
        common_header_rows = full_data_list[:2]

        _, matrix_start_row = coordinate_from_string('B2')
        excel_data_lists = self._split_table_by_rows(full_data_list, address_maps['excel_sections'], matrix_start_row)
        
        excel_data_dfs = {}
        for category, body_rows in excel_data_lists.items():
            complete_table = common_header_rows + body_rows
            standardized_df = self._standardize_table(complete_table)
            excel_data_dfs[category] = standardized_df

        # 4. 读取PPT模板中的数据 (使用注入的 config)
        ppt_reader = PptReader(config=self.config)
        ppt_data_dict = ppt_reader.extract_ppt_tables(
            self.data_cfg.categories, 
            self.data_cfg.ppt_target_slides
        )

        illustration_texts = ppt_reader.extract_ppt_text(
            categories=self.data_cfg.categories,
            target_slides=self.data_cfg.ppt_target_slides,
            shape_name="Text Placeholder 1",
            keyword="当日良率不达目标说明："        
        )
        safeguards_texts = ppt_reader.extract_ppt_text(
            categories=self.data_cfg.categories,
            target_slides=self.data_cfg.ppt_target_slides,
            shape_name="Text Placeholder 1",
            keyword="月度良率达标保障措施："
        )
        
        # 5. 数据融合
        final_table_data = self._update_data_by_factory(excel_data_dfs, ppt_data_dict, self.data_cfg.categories)

        self.processed_data = {
            "images": image_paths,
            "sentences": sentences,
            'table_data': final_table_data,
            "titles": self.data_cfg.locators.categories_titles, # 访问深层对象属性
            "illustration_texts": illustration_texts,
            "safeguards_texts": safeguards_texts
        }
        logger.info("第一章所需数据已成功准备完毕。")

    def _resolve_dynamic_addresses(self, excel_path: str) -> Dict[str, Any]:
        """动态地址解析器。"""
        # 使用对象属性访问
        if self.data_cfg is not None:
            categories = self.data_cfg.categories
            logger.info(f"开始解析动态地址，共涉及 {len(categories)} 个品类...")
            locators = self.data_cfg.locators
            sheet_names = self.data_cfg.sheet_names
        else:
            raise ValueError("Data configuration object is not initialized")
        
        resolved_maps = {
            'image_addresses': {},
            'sentence_addresses': {},
            'excel_sections': locators.excel_sections # 直接获取
        }

        # 3. 在“入库良率趋势”表中定位
        trend_sheet_name = sheet_names.get('yield_trend')
        # locatorRule 对象
        trend_locator = locators.yield_trend_sheet
        
        if trend_sheet_name and trend_locator:
            with ExcelReader(excel_path, trend_sheet_name) as reader:
                anchor_map = reader.locate_anchors(categories, trend_locator.anchor_column)
                
                # img/sent 是字典或 None
                img_offset = trend_locator.image
                sent_offset = trend_locator.sentence
                
                for category, anchor_cell in anchor_map.items():
                    if img_offset:
                        resolved_maps['image_addresses'][category] = self._calculate_offset_cell(
                            anchor_cell, img_offset.get('row_offset', 0), img_offset.get('col_offset', 0)
                        )
                    if sent_offset:
                        resolved_maps['sentence_addresses'][category] = self._calculate_offset_cell(
                            anchor_cell, sent_offset.get('row_offset', 0), sent_offset.get('col_offset', 0)
                        )

        # 4. 在“良率提升管控”表中定位
        control_sheet_name = sheet_names.get('control_plan')
        control_locator = locators.control_plan_sheet
        
        if control_sheet_name and control_locator:
            with ExcelReader(excel_path, control_sheet_name) as reader:
                anchor_map = reader.locate_anchors(categories, control_locator.anchor_column)
                section_rule = control_locator.section_data
                
                start_offset = section_rule.get('start_row_offset', 0) if section_rule else 0
                height = section_rule.get('height', 1) if section_rule else 1
                
                for category, anchor_cell in anchor_map.items():
                    _, start_row = coordinate_from_string(anchor_cell)
                    final_start_row = start_row + start_offset
                    final_end_row = final_start_row + height - 1
                    resolved_maps['excel_sections'][category] = [final_start_row, final_end_row]
        
        logger.info(f"Excel Sections: {resolved_maps['excel_sections']}")
        return resolved_maps
    
    @staticmethod
    def _calculate_offset_cell(start_cell: str, row_offset: int, col_offset: int) -> str:
        """
        根据起始单元格地址和行列偏移量，计算新的单元格地址。
        例如: _calculate_offset_cell('B4', row_offset=6, col_offset=1) -> 'C10'
        """
        col_str, row_idx = coordinate_from_string(start_cell)
        col_idx = column_index_from_string(col_str)
        
        new_row_idx = row_idx + row_offset
        new_col_idx = col_idx + col_offset
        
        # 健壮性检查，防止行列小于1
        if new_row_idx < 1 or new_col_idx < 1:
            raise ValueError(f"计算出的新行列号({new_row_idx}, {new_col_idx})无效。")
            
        new_col_str = get_column_letter(new_col_idx)
        return f"{new_col_str}{new_row_idx}"
    
    
    @staticmethod
    def _split_table_by_rows(
        data_matrix: list[list],
        sections_addr: dict[str, tuple[int, int]],
        matrix_start_row: int
    ) -> dict[str, list[list]]:
        """[内部静态方法] 根据绝对行号，将一个数据矩阵拆分为多个子表。"""
        sub_tables: dict[str, list[list]] = {}
        for category, (sec_start_abs, sec_end_abs) in sections_addr.items():
            relative_start_idx = sec_start_abs - matrix_start_row
            relative_end_idx = sec_end_abs - matrix_start_row
            sub_tables[category] = data_matrix[relative_start_idx : relative_end_idx + 1]
        logger.info("数据矩阵已成功按行拆分为子表。")
        return sub_tables
    
    
    @staticmethod
    def _standardize_table(table_data: List[List[str]]) -> pd.DataFrame:
        """
        [重构版] 将带有多级表头的 list[list] 转换为 扁平化列名的 DataFrame。
        输入: Header Row 1 + Header Row 2 + Body Rows...
        输出: DataFrame (Columns: "Total_GAP", "Total_M12目标"...)
        """
        if not table_data or len(table_data) < 3:
            logger.warning("表格数据不足以构成表头和内容，返回空DF。")
            return pd.DataFrame()

        # 1. 分离表头和数据
        header_rows = table_data[:2]
        body_rows = table_data[2:]
        
        try:
            # 2. 构建 MultiIndex DataFrame
            cols = pd.MultiIndex.from_arrays(header_rows)
            df = pd.DataFrame(body_rows, columns=cols)
            
            # 3. 调用辅助方法扁平化表头 (Total_GAP)
            # 确保 YieldDataSectionGenerator 类中有 _flatten_excel_header 方法
            df = YieldDataSectionGenerator._flatten_excel_header(df)
            
        except Exception as e:
            logger.error(f"标准表头解析失败: {e}")
            return pd.DataFrame()

        # 4. 数据清洗：去除空行
        df.dropna(how='all', inplace=True)
        return df
    
    @staticmethod
    def _flatten_excel_header(df: pd.DataFrame) -> pd.DataFrame:
        """
        [新功能] 将Excel的前两行多级表头合并为单行表头。
        例如：
            Row 0: | Total    | Total    | ...
            Row 1: | M12目标  | GAP      | ...
        合并后:
            Columns: "Total_M12目标", "Total_GAP", ...
        """
        # 假设读取时已经设置 header=[0, 1]，此时 columns 是 MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            new_columns = []
            for col in df.columns:
                # 过滤掉 "Unnamed" (通常是合并单元格产生的空占位)
                parts = [str(c).strip() for c in col if "Unnamed" not in str(c) and str(c).strip()]
                # 用下划线连接，例如 "Total_M12目标"
                new_name = "_".join(parts)
                new_columns.append(new_name)
            df.columns = new_columns
        return df

    # ==============================================================================
    #  更新PPT表格数据 (目标/实际/GAP)
    # ==============================================================================
    def _update_data_by_factory(self, excel_data_dfs, ppt_data_dict, categories):
        """
        根据 "Total" 区域的数据（第一组列）更新PPT数据。
        """
        # 1. 【核心修正】定义脏表头映射
        col_map = {
            "m12_target": "nan_2025M12目标",
            "m12_actual": "nan_2025M12实际",
            "gap":        "nan_GAP"
        }

        updated_data = {}  # 改为字典格式

        for category in categories:
            # 获取该品类对应的 DataFrame
            df = excel_data_dfs.get(category)
            
            if df is None or df.empty:
                logger.warning(f"品类 {category} 没有对应的Excel数据，跳过。")
                continue

            # 2. 【关键防御】处理列名重复问题
            df = df.loc[:, ~df.columns.duplicated(keep='first')].copy()

            # 3. 提取数据
            try:
                row_data = df.iloc[0] 
            except IndexError:
                continue

            # 获取 PPT 数据
            ppt_df = ppt_data_dict.get(category)
            if ppt_df is None:
                continue

            # 更新 PPT 数据
            ppt_df.iloc[:, 2] = row_data.get(col_map["m12_target"])
            ppt_df.iloc[:, 3] = row_data.get(col_map["m12_actual"])
            ppt_df.iloc[:, 4] = row_data.get(col_map["gap"])

            # 保存更新后的 DataFrame
            updated_data[category] = ppt_df

        return updated_data

    # =======================================================
    #  3、 内部渲染阶段 (Internal Rendering Stage)
    # =======================================================
    def _render_slides(self):
        """
        渲染PPT幻灯片的主方法
        该方法根据处理后的数据为每个品类创建一张幻灯片，并添加Logo、标题、图表、摘要和数据表格等元素
        """
        logger.info("开始渲染第一章的PPT页面...")
        if not self.processed_data: # 如果processed_data为空，则说明数据尚未准备好
            logger.error("数据尚未准备好，无法渲染页面。")
            return
        
        # 获取BLANK版式
        blank_layout_idx = self.element_processor.find_layout_index_by_name(self.prs, "BLANK")
        if blank_layout_idx is None:
            raise ValueError("模板中未找到名为 'BLANK' 的版式!")
        blank_layout = self.prs.slide_layouts[blank_layout_idx]
        
        # 获取渲染配置
        render_cfg = self.config.get('rendering_params', {}) # 获取渲染参数
        initial_slide_count = len(self.prs.slides) # 获取当前幻灯片总页数
        insert_at_index = render_cfg.get('insert_at_index', 2) if render_cfg is not None else 2
        categories = self.processed_data.get("titles", {}).keys() # 获取所有品类名称列表

        # 获取路径配置
        logo_filename = self.paths_cfg.get('logo') if self.paths_cfg is not None else None # Logo文件名
        logo_path = os.path.join(str(self.paths_cfg.data_raw_dir), str(logo_filename)) # 拼接完整的logo路径

        # 为每个品类生成页面
        for category in reversed(list(categories)): # 倒序处理以保证插入顺序
            slide = self.prs.slides.add_slide(blank_layout) # 添加新幻灯片
            
            print("-" * 20 + f" 诊断幻灯片上的形状 (品类: {category}) " + "-" * 20)
            if not slide.shapes:
                print("  >> 警告: 这张新幻灯片上没有任何形状或占位符!")
            else:
                print("  >> 在这张新幻灯片上找到了以下形状:")
                for shape in slide.shapes:
                    # 使用 repr() 来明确显示任何隐藏的空格
                    print(f"     - 名称: {repr(shape.name)}, 类型: {shape.shape_type}")
            print("-" * 70)
            
            # 添加Logo、标题、图表
            self.element_processor.add_logo(slide, str(logo_path), self.layout_cfg["logo"])
            self.element_processor.add_title(slide, self.processed_data["titles"].get(category, ""), self.layout_cfg["title"])
            self.element_processor.add_chart(slide, self.processed_data["images"].get(category, ""), self.layout_cfg["chart"])
            
            # 添加摘要文本
            illustration_text = self.processed_data.get("illustration_texts", {}).get(category, "")
            summary_text = self.processed_data["sentences"].get(category, "")
            safeguards_text = self.processed_data.get("safeguards_texts", {}).get(category, "")
            self._add_summary(slide, illustration_text, summary_text, safeguards_text, self.layout_cfg["summary"])
            
            # 添加数据表格
            df = self.processed_data.get("table_data", {}).get(category) # 获取表格数据
            if df is not None:
                self._add_table(slide, df)

        num_new_slides = len(self.prs.slides) - initial_slide_count
        if num_new_slides > 0:
            self.element_processor.reorder_slides(self.prs, initial_slide_count, num_new_slides, insert_at_index)

    @staticmethod
    def _add_summary(slide, illustration_text: str, summary_text: str, safeguards_text: str, cfg: ElementLayout):
        """
        [主控方法] FPY章节汇总生成入口。
        负责定位文本框，并按顺序调度三个板块的绘制。
        """
        # --- 1. 基础准备 ---
        placeholder_name = cfg["placeholder_name"]
        target_shape = next((s for s in slide.shapes if s.name == placeholder_name), None)
        
        if not target_shape:
            logger.error(f"未找到占位符: {placeholder_name}")
            return

        # 设置背景
        if "fill_color" in cfg:
            target_shape.fill.solid()
            target_shape.fill.fore_color.rgb = cfg["fill_color"]
            target_shape.fill.fore_color.transparency = 0.9

        # 初始化文本框
        tf = target_shape.text_frame
        tf.word_wrap = True
        tf.clear()
        if tf.paragraphs:
            tf._element.remove(tf.paragraphs[0]._p)

        # --- 2. 调度三个独立的业务板块 ---
        # 依次写入，依靠自然段落换行，不额外增加间距
        
        # 板块一：说明 (蓝色高亮)
        YieldDataSectionGenerator._add_illustration_section(tf, illustration_text)
        
        # 板块二：摘要 (黑色列表，GAP标红)
        YieldDataSectionGenerator._add_summary_section(tf, summary_text)
        
        # 板块三：保障措施 (蓝色高亮)
        YieldDataSectionGenerator._add_safeguards_section(tf, safeguards_text)

    @staticmethod
    def _add_illustration_section(tf, text):
        """板块一：绘制当日良率说明"""
        from pptx.dml.color import RGBColor

        p = tf.add_paragraph()
        
        # 添加标签 (默认色/黑，加粗)
        YieldDataSectionGenerator._add_styled_run(p, "▶  当日良率不达目标说明：", bold=True)
        # 添加内容 (蓝，加粗)
        YieldDataSectionGenerator._add_styled_run(p, f" {text}", bold=True, color=RGBColor(0,0,255))

    @staticmethod
    def _add_summary_section(tf, raw_text):
        """板块二：绘制摘要列表"""
        from pptx.dml.color import RGBColor
        
        paras = YieldDataSectionGenerator._parse_summary_paragraphs(raw_text)
        
        for parts in paras:
            p = tf.add_paragraph()
            
            # 列表Bullet 
            # 【关键】显式重置 bold=False 和 color=Black，
            # 确保紧接在上一段蓝色文字后，这里能恢复正常样式
            YieldDataSectionGenerator._add_styled_run(p, "▶  ", bold=False, color=RGBColor(0,0,0))
            
            for segment, is_gap in parts:
                if is_gap:
                    # GAP部分：红
                    YieldDataSectionGenerator._add_styled_run(p, segment, bold=True, color=RGBColor(255,0,0))
                else:
                    # 普通文本：显式设为黑、非粗
                    YieldDataSectionGenerator._add_styled_run(p, segment, bold=False, color=RGBColor(0,0,0))

    @staticmethod
    def _add_safeguards_section(tf, text):
        """板块三：绘制保障措施"""
        from pptx.dml.color import RGBColor

        p = tf.add_paragraph()
        
        # 添加标签 (显式设为黑，防止继承上一段可能的红色)
        YieldDataSectionGenerator._add_styled_run(p, "▶  月度良率达标保障措施：", bold=True, color=RGBColor(0,0,0))
        # 添加内容 (蓝，加粗)
        YieldDataSectionGenerator._add_styled_run(p, f" {text}", bold=True, color=RGBColor(0,0,255))

    @staticmethod
    def _add_styled_run(paragraph, text, bold=False, color=None):
        """
        [原子方法] 基础样式运行创建器。
        不设置 font.size，由模板自动控制。
        """
        run = paragraph.add_run()
        run.text = str(text)
        run.font.bold = bold
        # 仅当有颜色传入时才设置，否则跟随默认
        if color:
            run.font.color.rgb = color
    
    @staticmethod
    def _parse_summary_paragraphs(text: str) -> list[list[tuple[str, bool]]]:
        """
        [内部静态方法] 将汇总语句拆分为多个段落，每个段落由若干 (segment, is_gap) 组成。
        """
        # 在每个 'Array：' 前插入换行符的逻辑可以根据需要调整
        text = text.replace("Array：", "；Array：")
        
        # 仅匹配形如 GAP：-12.34% 或 GAP：12.34% 的文本
        gap_pattern = re.compile(r"(GAP：)(-?\+?\d+(\.\d+)?%?)")
        parts: list[tuple[str, bool]] = []
        last_end = 0

        for m in gap_pattern.finditer(text):
            # 添加 "GAP：" 前的普通文本
            if m.start() > last_end:
                parts.append((text[last_end:m.start()], False))
            
            # 添加 "GAP：" 前缀（不标红）
            parts.append((m.group(1), False))
            
            # 提取数字部分并判断正负
            number_str = m.group(2)
            # 去除百分号并转换为数值
            number = float(number_str.replace("%", ""))
            
            # 标红条件：数字大于 0（正数）
            is_red = number < 0
            
            # 添加数字部分（根据正负决定是否标红）
            parts.append((number_str, is_red))
            last_end = m.end()
        
        # 添加剩余文本（无 "GAP：" 的部分）
        if last_end < len(text):
            parts.append((text[last_end:], False))
        
        # 返回单段落结构（与原逻辑兼容）
        return [parts]

    
    def _add_table(self, slide, df: pd.DataFrame):
        """
        [内部实例方法] 在幻灯片上创建表格。
        集成【表头净化】功能，解决 ('Total', 'GAP') 等元组显示问题。
        """
        # --- 0. 基础配置与判空 ---\
        cfg = self.table_layout_base
        if df.empty or cfg is None:
            raise ValueError("df cannot be empty and cfg cannot be None")

        # 生成清洗后的表头列表
        clean_header_row = [self._sanitize_header(col) for col in df.columns]
        
        # --- 2. 数据准备 ---
        # 强制将表头包装为二维列表 (单行表头)
        header_data = [clean_header_row]
        body_data = df.values.tolist()
        table_data = header_data + body_data
        
        total_rows = len(table_data)
        total_cols = len(clean_header_row)

        # --- 3. 智能设置尺寸 ---
        # 计算尺寸 (传入原始 df 即可，列名匹配逻辑依然有效)
        smart_dims = self._compute_smart_dimensions(df)
        
        cfg["col_widths"] = smart_dims["col_widths"]
        cfg["row_heights"] = smart_dims["row_heights"]
        

        current_widths = cfg["col_widths"]
        if current_widths is None:
            raise ValueError("current_widths cannot be None")   
        if len(current_widths) < total_cols:
             current_widths += [current_widths[-1]] * (total_cols - len(current_widths))
        
        current_heights = cfg["row_heights"]
        if current_heights is None:
            raise ValueError("current_heights cannot be None")
        if len(current_heights) < total_rows:
            current_heights += [current_heights[-1]] * (total_rows - len(current_heights))

        total_width = sum(current_widths[:total_cols])
        total_height = sum(current_heights[:total_rows])
        
        # --- 4. 创建表格 ---
        table_shape = slide.shapes.add_table(
            total_rows, total_cols,
            Inches(cfg.left), Inches(cfg.top),
            Inches(total_width), Inches(total_height)
        )
        ppt_table = table_shape.table
        
        # --- 5. 应用物理尺寸 ---
        cfg["col_widths"] = current_widths[:total_cols]
        cfg["row_heights"] = current_heights[:total_rows]
        TableProcessor._set_dimensions(ppt_table, cfg)
        
        # --- 6. 合并单元格 ---
        header_ranges = [] 
        # 数据体合并 (前5列)
        body_ranges = self._generate_body_merges(body_data, num_header_rows=len(header_data))
        
        master_cell_map = TableProcessor.merge_cells(
            ppt_table, table_data, extra_ranges=(header_ranges + body_ranges)
        )
        
        # 设置边框和边距
        TableProcessor._set_table_borders(ppt_table)
        TableProcessor._set_cell_margins_to_zero(ppt_table)
        
        # --- 7. 定义样式 ---
        header_style, body_style = self._get_style_config(cfg)

        # --- 8. 统一填充数据 ---
        for i, row in enumerate(table_data):
            for j, val in enumerate(row):
                # 越界保护
                if i >= total_rows or j >= total_cols:
                    continue
                
                # 跳过合并格
                if master_cell_map.get((i, j)) and master_cell_map[(i, j)] != (i, j):
                    continue

                cell = ppt_table.cell(i, j)
                is_header = i < len(header_data)
                
                style = header_style.copy() if is_header else body_style.copy()
                
                # 【关键逻辑】填充文本：此时 row[j] 已经是被 _sanitize_header 处理过的干净字符串(如果是表头行)或者原始数据(如果是数据行)
                if is_header:
                    style["text"] = str(val) if val is not None else ""
                else:
                    formatted_text, is_negative = self._format_numeric_value(val)
                    style["text"] = formatted_text
                    if is_negative:
                        style["font_color"] = RGBColor(255, 0, 0)
                    if j != 7:
                        style["h_align"] = PP_ALIGN.CENTER
                
                TableProcessor.apply_cell_style(cell, style)

    def _sanitize_header(self, col):
            # 如果不是元组，直接转字符串
            if not isinstance(col, tuple):
                return str(col)
            
            # 过滤掉 'Unnamed' 和 空字符串
            parts = [str(p) for p in col if str(p).strip() and 'Unnamed' not in str(p)]
            
            if not parts:
                return ""
            
            # 策略 A: 优先保留非 'Total' 的部分 (针对 ('Total', 'GAP') -> 'GAP')
            if 'Total' in parts and len(parts) > 1:
                return next(p for p in reversed(parts) if p != 'Total')
            
            # 策略 B: 优先保留 '品类'/'产品' (针对 ('品类', 'LTPO') -> '品类')
            # 这是一个保护性策略，防止Excel数据行混入表头
            priority_keywords = ['品类', '产品', '目标', '实际', 'GAP']
            for kw in priority_keywords:
                for p in parts:
                    if kw in p:
                        return p
            
            # 策略 C: 默认取最后一个非空部分 (通常是具体指标名)
            return parts[-1]
    
    def _compute_smart_dimensions(self, df: pd.DataFrame) -> dict:
        """
        [新功能] 根据 DataFrame 的列名和 Config 规则，智能计算行高和列宽列表。
        """
        layout_cfg = self.table_layout_base
        if layout_cfg is None:
            raise ValueError("layout_cfg canot be None")
        rules = layout_cfg.col_width_rules
        if rules is None:
            raise ValueError("col_width_rules is not initialized")
        default_width = rules.get('default', 0.6)
        overrides = rules.get('overrides', {})
        
        # 1. 计算列宽列表
        col_widths = []
        if not df.empty:
            for col_name in df.columns:
                col_str = str(col_name)
                width = default_width
                
                # 关键词匹配
                if not isinstance(overrides, dict):
                    raise TypeError("overrides must be a dictionary")
                for keyword, distinct_width in overrides.items():
                    if keyword in col_str:
                        width = distinct_width
                        break 
                col_widths.append(width)
        
        # 2. 计算行高列表 (单行表头 + 数据行)
        rh_rules = layout_cfg.get('row_height_rules', {})
        if rh_rules is None:
            raise ValueError("rh_rules is not initialized")
        h_height = rh_rules.get('header', 0.5)
        b_height = rh_rules.get('body', 0.35)
        
        # 1行表头 + N行数据
        row_heights = [h_height] + [b_height] * len(df)
        
        return {
            "col_widths": col_widths,
            "row_heights": row_heights
        }
    

    @staticmethod
    def _generate_body_merges(
        body_data: List[List[str]], 
        num_header_rows: int
    ) -> List[Tuple[int, int, int, int]]:
        """[内部静态方法] 根据数据体内容，动态生成合并指令(仅合并前5列)。"""
        if not body_data:
            return []

        all_ranges = []
        num_body_rows = len(body_data)
        total_cols = len(body_data[0]) if num_body_rows > 0 else 0
        body_start_row = num_header_rows

        # 规则：完全垂直合并 (仅限前5列)
        full_merge_cols = [0, 1, 2, 3, 4] # 品类, 产品, 目标, 实际, GAP
        last_row_idx = body_start_row + num_body_rows - 1
        
        if num_body_rows > 1:
            for col_idx in full_merge_cols:
                if col_idx < total_cols:
                    # 只有当该列所有值都相同时，或者我们强制认为这一大块是同一组数据时
                    # 根据您图3的逻辑，只要是同一品类的表格，前5列直接垂直合并到底
                    all_ranges.append((body_start_row, col_idx, last_row_idx, col_idx))
                
        return all_ranges
    

    @classmethod
    def _get_style_config(cls, cfg: TableBaseLayout) -> tuple[dict, dict]:
        """生成表头和数据体的样式配置"""
        header_style = {
            "v_align": MSO_VERTICAL_ANCHOR.MIDDLE,
            "h_align": PP_ALIGN.CENTER,
            "fill_color": cls.DEFAULT_COLORS['header'],
            "font_size": Pt(cfg.header_font_size),
            "font_name": cfg["font_name"],
            "bold": True,
            "font_color": cls.DEFAULT_COLORS['black']
        }
        
        body_style = {
            "v_align": MSO_VERTICAL_ANCHOR.MIDDLE,
            "fill_color": cls.DEFAULT_COLORS['body'],
            "font_size": Pt(cfg.body_font_size),
            "font_name": cfg["font_name"],
            "bold": False
        }
        
        return header_style, body_style
    
    @staticmethod
    def _format_numeric_value(val: Any) -> Tuple[str, bool]:
        """
        [内部静态方法] 格式化数值为百分比字符串，并返回是否为负数。
        支持以下输入：
        - 数值类型 (int/float)：转换为百分比字符串（保留两位小数）。
        - 字符串类型（含百分比符号）：尝试解析为数值并判断正负。
        - 其他类型（如 None）：返回空字符串和 False。
        """
        # 处理数值类型
        if isinstance(val, (int, float)):
            formatted = f"{val * 100:.2f}%"  # 转换为百分比字符串
            is_negative = val < 0           # 判断是否为负数
            return (formatted, is_negative)

        # 处理字符串类型
        elif isinstance(val, str):
            # 去除百分号并尝试转换为数值
            try:
                cleaned = val.replace("%", "").strip()  # 去除百分号和空格
                number = float(cleaned)                 # 转换为浮点数
                is_negative = number < 0                # 判断是否为负数
                return (val, is_negative)               # 返回原始字符串和判断结果
            except ValueError:
                # 无法解析的字符串（如非数字文本）
                return (str(val), False)
        
        # 处理其他类型（如 None）
        else:
            return ("" if val is None else str(val), False)
        
