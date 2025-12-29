# --- 标准库导入 (Standard Library Imports) ---
import logging
from typing import Optional
from zipfile import ZipFile
from typing import Dict, List, Tuple, Any

# --- 第三方库导入 (Third-Party Library Imports) ---
from lxml import etree # type: ignore
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement

from packages.ppt_engine.src.config import TableBaseLayout, TableLayoutConfig


XML_PARSER = etree.XMLParser(remove_blank_text=True, encoding='utf-8')

class TableProcessor:
    """
    一个专门用于创建、格式化和填充PPT表格的类。
    """
    def __init__(self, cfg: Optional[TableLayoutConfig] = None):
        """
        TableProcessor的构造函数（目前作为占位符，未来会充实）。
        
        :param slide: 将要添加表格的幻灯片对象。
        :param data: 用于填充表格的数据 (例如 a pandas DataFrame)。
        :param cfg: 与表格相关的配置字典。
        """
        self.cfg = cfg                             
        logging.info("TableProcessor 实例已创建。")

    # ==============================================================================
    #  内部辅助方法 (Internal Helper Methods)
    # ==============================================================================

    @staticmethod
    def _calculate_sizes(
        total_size: float,
        primary_item_size: float,
        primary_item_count: int,
        secondary_item_count: int,
        primary_is_first: bool = False
    ) -> Tuple[List[float], float]:
        """
        [内部静态方法] 一个通用的尺寸计算函数。
        根据“主要项”和“次要项”的规格来计算尺寸列表。
        """
        if secondary_item_count <= 0:
            secondary_item_size = 0.0
        else:
            remaining_size = total_size - (primary_item_size * primary_item_count)
            if remaining_size < 0:
                logging.warning("主要项的总尺寸已超出总尺寸！")
                # 即使超出，也分配一个极小值而不是负值，避免后续错误
                remaining_size = 0.0
            secondary_item_size = remaining_size / secondary_item_count
            
        primary_list = [primary_item_size] * primary_item_count
        secondary_list = [secondary_item_size] * secondary_item_count
        
        if primary_is_first:
            return primary_list + secondary_list, secondary_item_size
        else:
            return secondary_list + primary_list, secondary_item_size
    

    @staticmethod
    def _set_dimensions(ppt_table, cfg:TableBaseLayout):
        """
        [内部静态方法] 根据cfg配置字典，自适应地设置一个PPT表格对象的行高和列宽。
        """
        # --- 设置行高 ---
        row_heights = cfg.get("row_heights", []) # 从配置中获取行高序列
        if row_heights:
            last_row_height = row_heights[-1]
            for i, row in enumerate(ppt_table.rows): # 遍历表格所有行
                # 如果当前行号小于配置列表长度，使用对应值；否则使用最后一个值
                height = row_heights[i] if i < len(row_heights) else last_row_height
                row.height = Inches(height)

        # --- 设置列宽 ---
        col_widths = cfg.get("col_widths", []) # 从配置中获取列宽列表
        if col_widths:
            last_col_width = col_widths[-1]
            for j, col in enumerate(ppt_table.columns): # 遍历表格所有列
                # 如果当前列号小于配置列表长度，使用对应值；否则使用最后一个值
                width = col_widths[j] if j < len(col_widths) else last_col_width
                col.width = Inches(width)

        logging.info("已根据配置自适应设置表格的行高和列宽。")

     # --- 样式相关 (新增) ---
    @staticmethod
    def _set_table_borders(table):
        """
        [内部静态方法] 通过直接操作底层XML，为一个表格的所有单元格设置黑色边框。
        """
        try:
            # 遍历所有单元格
            for cell in table.iter_cells():
                # 获取单元格属性 (tcPr)
                tcPr = cell._tc.get_or_add_tcPr() # type: ignore
                
                # 为四个边框(左、右、上、下)分别创建全新的XML元素
                for border_tag in ['lnL', 'lnR', 'lnT', 'lnB']:
                    
                    # 1. 根据 border_tag 创建带有正确标签的元素，例如 OxmlElement('a:lnL')
                    border_element = OxmlElement(f'a:{border_tag}')
                    
                    # 2. 为这个新元素设置属性
                    border_element.set('w', '6350')  # 宽度 6350 EMU = 0.5pt
                    
                    # 3. 为这个新元素设置颜色
                    solidFill = OxmlElement('a:solidFill')
                    srgbClr = OxmlElement('a:srgbClr')
                    srgbClr.set('val', '000000') # 黑色
                    solidFill.append(srgbClr)
                    border_element.append(solidFill)
                    
                    # 4. 将构建好的新元素附加到单元格属性中
                    tcPr.append(border_element)

        except Exception as e:
            logging.error(f"设置表格边框时发生未知错误: {e}")

    @staticmethod
    def _inspect_table_styles(ppt_path: str) -> List[Dict[str, str]]:
        """
        [静态方法] 诊断工具，用于解析并返回一个PPT文件中所有可用的表格样式。
        
        :param ppt_path: 要检查的PPT文件的路径。
        :return: 一个字典列表，每个字典包含一个表格样式的'styleId'和'styleName'。
        """
        styles_info = []
        logging.info(f"开始检查PPT文件 '{ppt_path}' 中的表格样式...")
        
        try:
            with ZipFile(ppt_path) as zf:
                # 检查 tableStyles.xml 是否存在
                if 'ppt/tableStyles.xml' not in zf.namelist():
                    logging.warning(f"文件 '{ppt_path}' 中没有找到 'ppt/tableStyles.xml'，无法提取表格样式。")
                    return styles_info
                    
                xml_bytes = zf.read('ppt/tableStyles.xml')
                
                # 直接将字节(bytes)和我们创建好的解析器传递给 fromstring；解析器会负责处理编码问题
                root = etree.fromstring(xml_bytes, parser=XML_PARSER)

            # 定义命名空间，用于在XML中查找带前缀的标签
            ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            style_elements = root.findall('.//a:tblStyle', ns)

            for s in style_elements:
                # .attrib 会返回一个包含所有属性的字典，例如 {'styleId': '{...}', 'styleName': '...'}
                styles_info.append(s.attrib)
                logging.info(f"找到样式: ID={s.attrib.get('styleId')}, 名称={s.attrib.get('styleName')}")

            logging.info(f"样式检查完成，共找到 {len(styles_info)} 个可用表格样式。")
            return styles_info

        except FileNotFoundError:
            logging.error(f"PPT文件未找到: {ppt_path}")
            return []
        except Exception as e:
            logging.error(f"检查表格样式时发生错误: {e}")
            return []
    
    # =================== 新增：合并单元格相关方法 ===================

    @staticmethod
    def merge_cells(
        table, 
        table_data_list: List[List[str]], 
        extra_ranges: Optional[List[Tuple[int, int, int, int]]] = None,
        auto: bool = False
    ) -> Dict:
        """
        [内部静态方法] 执行单元格合并，并返回一个“主单元格映射表”。
        """
        all_ranges = []
        if auto:
            # 调用本类中其他重命名后的静态方法
            v_ranges = TableProcessor._compute_vertical_merges(table_data_list)
            h_ranges = TableProcessor._compute_horizontal_merges(table_data_list)
            all_ranges.extend(v_ranges)
            all_ranges.extend(h_ranges)
        
        if extra_ranges:
            all_ranges.extend(extra_ranges)

        master_cell_map = {}
        for (r1, c1, r2, c2) in all_ranges:
            try:
                table.cell(r1, c1).merge(table.cell(r2, c2))
                master_cell = (r1, c1)
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        master_cell_map[(r, c)] = master_cell
            except Exception:
                # 在某些情况下，合并可能会失败（例如，试图合并一个已经被合并的单元格的一部分）
                # 我们选择忽略这些错误，继续执行
                continue
                
        return master_cell_map
    
    @staticmethod
    def _compute_vertical_merges(table_data: list[list]) -> list[tuple[int, int, int, int]]:
        """[内部静态方法] 计算“纵向合并”区间。"""
        # 不再需要内部的 is_empty 函数
        merge_ranges = []
        if not table_data:
            return merge_ranges

        n_rows, n_cols = len(table_data), len(table_data[0])

        for j in range(n_cols):
            i = 0
            while i < n_rows - 1:
                start = i
                # 向下查找连续满足条件的单元格
                # 【核心修改】调用 self._is_empty
                while (i < n_rows - 1 and
                       (table_data[i][j] == table_data[i+1][j] or
                        TableProcessor._is_empty(table_data[i][j]) or
                        TableProcessor._is_empty(table_data[i+1][j]))):
                    i += 1
                
                if i > start:
                    merge_ranges.append((start, j, i, j))
                i += 1
        return merge_ranges

    @staticmethod
    def _compute_horizontal_merges(table_data: list[list]) -> list[tuple[int,int,int,int]]:
        """
        计算“横向合并”区间。当同一行 i 上，列 j 与 j+1 的值相同，或其中一个是空（None 或 ""），
        就把这两个单元格合并 (i, j, i, j+1)。若连续多列满足条件，会生成多段合并区间，
        python-pptx 在执行 merge 时会把它们合并成更大的区域。
        """
        merge_ranges = []
        n_rows = len(table_data)
        if n_rows == 0:
            return merge_ranges

        n_cols = len(table_data[0])
        for i in range(n_rows):
            j = 0
            while j < n_cols - 1:
                a = table_data[i][j]
                b = table_data[i][j + 1]
                if a == b or TableProcessor._is_empty(a) or TableProcessor._is_empty(b):
                    # 找到横向相同或空值的起始列 start = j
                    start = j
                    val = a if not TableProcessor._is_empty(a) else b
                    end = j + 1
                    # 延伸范围：只要后面还满足“相等或空值”，继续往右
                    while end + 1 < n_cols:
                        nxt = table_data[i][end + 1]
                        curr = table_data[i][end]
                        if curr == nxt or TableProcessor._is_empty(curr) or TableProcessor._is_empty(nxt):
                            end += 1
                        else:
                            break
                    merge_ranges.append((i, start, i, end))
                    j = end + 1
                else:
                    j += 1
        return merge_ranges

    
    @staticmethod
    def _is_empty(val: Any) -> bool:
        """[内部静态方法] 检查一个值是否为空（None或空字符串）。"""
        return val is None or val == ""
    
    # =================== 新增：单元格样式设置方法 ===================
    @staticmethod
    def apply_cell_style(cell, style_config: dict):
        """
        [内部静态方法] 一个通用的辅助函数，用于对单元格应用文本和一系列样式。
        """
        try:
            # 步骤 1: 应用单元格级别的格式 (背景填充, 垂直对齐)
            if "fill_color" in style_config and style_config["fill_color"]:
                cell.fill.solid()
                # 假设颜色是(R, G, B)元组
                cell.fill.fore_color.rgb = RGBColor(*style_config["fill_color"])
            else:
                cell.fill.background()
            
            # 垂直对齐方式，例如 MSO_VERTICAL_ANCHOR.MIDDLE
            if "v_align" in style_config:
                cell.vertical_anchor = style_config["v_align"]

            # 步骤 2: 应用文本和字体相关的格式
            text_frame = cell.text_frame
            text_frame.clear()

            p = text_frame.paragraphs[0]
            p.clear()

            # 设置段落水平对齐，例如 PP_ALIGN.CENTER
            if "h_align" in style_config:
                p.alignment = style_config["h_align"]

            run = p.add_run()
            run.text = str(style_config.get("text", "")) # 使用.get确保安全，并转为str

            font = run.font
            if "font_color" in style_config and style_config["font_color"]:
                font.color.rgb = RGBColor(*style_config["font_color"])
            if "font_name" in style_config:
                font.name = style_config["font_name"]
            if "font_size" in style_config:
                font.size = style_config["font_size"]
            if "bold" in style_config:
                font.bold = style_config["bold"]
                
        except Exception as e:
            logging.error(f"应用单元格样式时发生错误: {e}")

    
    @staticmethod
    def _set_cell_margins_to_zero(table):
        """
        [V1.0 - 验证通过的实现]
        遍历表格中的所有单元格，并将它们的边距全部设置为0。
        """
        try:
            # 定义一个 0 磅的值，这是最精确的
            zero_margin = Pt(0) 
            
            # 遍历表格中的每一行
            for row in table.rows:
                # 遍历该行中的每一个单元格
                for cell in row.cells:
                    # 设置所有四个方向的边距
                    cell.margin_left = zero_margin
                    cell.margin_right = zero_margin
                    cell.margin_top = zero_margin
                    cell.margin_bottom = zero_margin
            
            logging.info(f"已将表格单元格边距设置为 0。")
            
        except Exception as e:
            logging.error(f"设置单元格边距为0时发生错误: {e}")

