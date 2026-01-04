import os
import logging
from typing import Optional, List, Tuple

from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as PptxPresentationObject

from packages.ppt_engine.src.config import PptEngineConfig, ElementLayout

logger = logging.getLogger("ElementProcessor")

class ElementProcessor:
    """
    [Core Component]
    负责处理 PPT 页面上的具体元素操作，如添加图片、文本、图表、重排页面等。
    """

    def __init__(self, config: Optional[PptEngineConfig] = None):
        self.config = config

    def add_logo(self, slide, logo_path, cfg: ElementLayout):
        """在幻灯片上添加Logo图片。"""
        if not logo_path or not os.path.exists(logo_path):
            logger.warning(f"Logo文件路径不存在或未提供: {logo_path}")
            return
            
        try:
            slide.shapes.add_picture(
                logo_path,
                Inches(cfg.left), Inches(cfg.top),
                width=Inches(cfg.width)
            )
        except KeyError as e:
            logger.error(f"Logo配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logger.error(f"添加Logo时发生错误: {e}")

    def add_title(self, slide, text: str, cfg: ElementLayout):
        """在幻灯片上添加格式化的标题文本框。"""
        try:
            box = slide.shapes.add_textbox(
                Inches(cfg.left), Inches(cfg.top),
                Inches(cfg.width), Inches(cfg.height or 0.6)
            )
            tf = box.text_frame
            tf.clear() 

            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT

            run = p.add_run()
            run.text = text
            
            font = run.font
            
            self._set_unified_font(font, cfg.font_name or "微软雅黑")
            
            font.size = Pt(cfg.font_size or 22)
            font.bold = cfg.get("bold", True)

        except KeyError as e:
            logger.error(f"标题配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logger.error(f"添加标题时发生错误: {e}")

    def _set_unified_font(self, font_object, font_name: str):
        """
        一个底层的、兼容所有python-pptx版本的字体设置函数。
        """
        # 获取底层的 <a:rPr> XML 元素
        rPr = font_object._element
        
        # --- 设置西文字体 ---
        latin_el = rPr.find(qn('a:latin'))
        if latin_el is None:
            latin_el = OxmlElement('a:latin')
            rPr.insert(0, latin_el)
        latin_el.set('typeface', font_name)

        # --- 设置东亚字体 ---
        ea_el = rPr.find(qn('a:ea'))
        if ea_el is None:
            ea_el = OxmlElement('a:ea')
            rPr.insert(0, ea_el)
        ea_el.set('typeface', font_name)

    def add_chart(self, slide, img_path: str, cfg: ElementLayout):
        """在幻灯片上添加一个图片（作为图表）。"""
        if not img_path or not os.path.exists(img_path):
            logger.warning(f"图表图片文件路径不存在或未提供: {img_path}")
            return

        try:
            slide.shapes.add_picture(
                img_path,
                Inches(cfg.left), Inches(cfg.top),
                width=Inches(cfg.width), height=Inches(cfg.height or 1.6)
            )
        except KeyError as e:
            logger.error(f"图表配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logger.error(f"添加图表时发生错误: {e}")

    def add_summary(self, slide, paragraphs: list, cfg: ElementLayout):
        """
        在一个预设的占位符中，为列表中的每个文本字符串插入一个带项目符号的段落。
        """
        try:
            placeholder_name = cfg.placeholder_name
            
            target_shape = None
            for shape in slide.shapes:
                if shape.name == placeholder_name:
                    target_shape = shape
                    break
            
            if target_shape is None:
                logger.error(f"在当前幻灯片上未找到名为 '{placeholder_name}' 的占位符。")
                return
            
            # 填充背景色
            if "fill_color" in cfg:
                target_shape.fill.solid()
                # 假设 fill_color 是 RGBColor 对象或元组，这里简化处理
                # 如果传入的是元组，需转换为 RGBColor
                if isinstance(cfg.fill_color, (list, tuple)):
                     target_shape.fill.fore_color.rgb = RGBColor(*cfg.fill_color or [183, 222, 232])
                else:
                     target_shape.fill.fore_color.rgb = cfg.fill_color
                target_shape.fill.fore_color.transparency = 0.9

            tf = target_shape.text_frame
            tf.word_wrap = True
            tf.clear()
            
            # 清理默认产生的空段落
            if tf.paragraphs:
                 # 注意：操作底层元素有风险，但在 python-pptx 中清空文本框通常需要这样
                 # 或者直接 tf.text = "" 也可以
                 pass

            # 3. 循环添加段落和文本
            for para_text in paragraphs:
                p = tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                p.level = 0
                p.line_spacing = cfg.get("line_spacing", 1.2)

                font = p.font
                font.name = cfg.get("font_name", "等线")
                font.size = Pt(cfg.font_size or 12)
                font.bold = cfg.get("bold", False)
                
                if "font_color" in cfg:
                    if isinstance(cfg["font_color"], (list, tuple)):
                        font.color.rgb = RGBColor(*(cfg["font_color"] or (0, 0, 0)))
                    else:
                        font.color.rgb = cfg["font_color"]

                bullet_run = p.add_run()
                bullet_run.text = "▶  "
                
                content_run = p.add_run()
                content_run.text = str(para_text)

        except KeyError as e:
            logger.error(f"摘要框配置项缺失: '{e}'。请检查cfg字典。")
        except Exception as e:
            logger.error(f"插入摘要时发生错误: {e}")

    def reorder_slides(self, prs: PptxPresentationObject, source_start_index: int, block_length: int, target_index: int):
        """
        对演示文稿中的幻灯片顺序进行重排。
        """
        if not isinstance(prs, PptxPresentationObject):
            raise TypeError("prs参数必须是PptxPresentationObject类型")
        if block_length <= 0:
            return

        logger.info(f"执行页面重排: 将从索引 {source_start_index} 开始的 {block_length} 页移动到索引 {target_index}。")
        
        try:
            slide_id_list = prs.slides._sldIdLst
            
            all_slide_ids = []
            for i in range(len(slide_id_list)):
                all_slide_ids.append(slide_id_list[i])

            block_to_move = all_slide_ids[source_start_index : source_start_index + block_length]
            if not block_to_move:
                logger.error(f"无法从索引 {source_start_index} 提取到要移动的页面区块，重排失败。")
                return
            
            remaining_slides = all_slide_ids[:source_start_index] + all_slide_ids[source_start_index + block_length:]
            final_order_list = remaining_slides[:target_index] + block_to_move + remaining_slides[target_index:]
            
            del slide_id_list[:]
            slide_id_list.extend(final_order_list)
            
            logger.info(f"重排操作完成。现在总页数为 {len(slide_id_list)}")

        except Exception as e:
            logger.error(f"执行 reorder_slides 时发生严重错误: {e}", exc_info=True)
            raise

    def find_layout_index_by_name(self, prs: PptxPresentationObject, layout_name: str) -> Optional[int]:
        """
        根据名称查找幻灯片版式的索引。
        """
        for i, layout in enumerate(prs.slide_layouts):
            if layout.name == layout_name:
                logger.info(f"成功找到名为 '{layout_name}' 的版式，索引为 {i}。")
                return i
        logger.warning(f"在模板中未找到名为 '{layout_name}' 的版式。")
        return None