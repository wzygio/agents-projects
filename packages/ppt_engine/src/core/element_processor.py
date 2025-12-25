import os
import logging
from typing import Optional

from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.presentation import Presentation as PptxPresentationObject


# ==============================================================================
#  元素生成函数
# ==============================================================================
class ElementProcessor:

    @staticmethod
    def add_logo(slide, logo_path: str, cfg: dict):
        """在幻灯片上添加Logo图片。"""
        if not logo_path or not os.path.exists(logo_path):
            logging.warning(f"Logo文件路径不存在或未提供: {logo_path}")
            return
            
        try:
            slide.shapes.add_picture(
                logo_path,
                Inches(cfg["left"]), Inches(cfg["top"]),
                width=Inches(cfg["width"])
            )
        except KeyError as e:
            logging.error(f"Logo配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logging.error(f"添加Logo时发生错误: {e}")


    @staticmethod
    def add_title(slide, text: str, cfg: dict):
        """在幻灯片上添加格式化的标题文本框。"""
        try:
            box = slide.shapes.add_textbox(
                Inches(cfg["left"]), Inches(cfg["top"]),
                Inches(cfg["width"]), Inches(cfg.get("height", 0.6))
            )
            tf = box.text_frame
            tf.clear() 

            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT

            run = p.add_run()
            run.text = text
            
            font = run.font
            
            ElementProcessor._set_unified_font(font, cfg["font_name"])
            
            # 其他样式设置保持不变
            font.size = Pt(cfg["font_size"])
            font.bold = cfg.get("bold", True)

        except KeyError as e:
            logging.error(f"标题配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logging.error(f"添加标题时发生错误: {e}")

    @staticmethod
    def _set_unified_font(font_object, font_name: str):
        """
        一个底层的、兼容所有python-pptx版本的字体设置函数。
        它通过直接操作XML，为字体同时设置latin和east_asian两种字体。

        Args:
            font_object: 一个pptx的Font对象 (例如 run.font 或 p.font)。
            font_name: 您希望统一设置的字体名称 (例如 '微软雅黑')。
        """
        # 获取底层的 <a:rPr> XML 元素
        rPr = font_object._element
        
        # --- 设置西文字体 ---
        # 查找 <a:latin> 标签
        latin_el = rPr.find(qn('a:latin'))
        # 如果找不到，就创建一个
        if latin_el is None:
            latin_el = OxmlElement('a:latin')
            rPr.insert(0, latin_el)
        # 设置其 typeface 属性
        latin_el.set('typeface', font_name)

        # --- 设置东亚字体 ---
        # 查找 <a:ea> 标签
        ea_el = rPr.find(qn('a:ea'))
        # 如果找不到，就创建一个
        if ea_el is None:
            ea_el = OxmlElement('a:ea')
            rPr.insert(0, ea_el)
        # 设置其 typeface 属性
        ea_el.set('typeface', font_name)

    @staticmethod
    def add_chart(slide, img_path: str, cfg: dict):
        """在幻灯片上添加一个图片（作为图表）。"""
        if not img_path or not os.path.exists(img_path):
            logging.warning(f"图表图片文件路径不存在或未提供: {img_path}")
            return

        try:
            slide.shapes.add_picture(
                img_path,
                Inches(cfg["left"]), Inches(cfg["top"]),
                width=Inches(cfg["width"]), height=Inches(cfg["height"])
            )
        except KeyError as e:
            logging.error(f"图表配置项缺失: {e}。请检查cfg字典。")
        except Exception as e:
            logging.error(f"添加图表时发生错误: {e}")

    @staticmethod
    def add_summary(slide, paragraphs: list, cfg: dict):
        """
        在一个预设的占位符中，为列表中的每个文本字符串插入一个带项目符号的段落。
        """
        try:
            # 1. 从配置中获取我们要寻找的占位符名称
            placeholder_name = cfg["placeholder_name"]
            
            # 2. 在当前幻灯片上，按名称寻找这个占位符
            target_shape = None
            for shape in slide.shapes:
                if shape.name == placeholder_name:
                    target_shape = shape
                    break
            
            if target_shape is None:
                logging.error(f"在当前幻灯片上未找到名为 '{placeholder_name}' 的占位符。")
                return
            
            # --- 后续所有操作都针对找到的 target_shape ---
            if "fill_color" in cfg:
                target_shape.fill.solid()
                target_shape.fill.fore_color.rgb = cfg["fill_color"]
                target_shape.fill.fore_color.transparency = 0.9

            # --- 我们现在操作的是找到的占位符，而不是新创建的文本框 ---
            tf = target_shape.text_frame
            tf.word_wrap = True
            tf.clear()
            if tf.paragraphs:
                tf._element.remove(tf.paragraphs[0]._p) # type: ignore
            
            if len(tf.paragraphs) > 0:
                p_to_remove = tf.paragraphs[0]._p
                tf._element.remove(p_to_remove)

            # 3. 循环添加段落和文本
            for para_text in paragraphs:
                p = tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                p.level = 0
                p.line_spacing = cfg.get("line_spacing", 1.2)

                # 4. 【核心】在段落级别设置字体，这会应用到后续所有run
                font = p.font
                font.name = cfg.get("font_name", "等线")
                font.size = Pt(cfg.get("font_size", 12))
                font.bold = cfg.get("bold", False)
                if "font_color" in cfg and isinstance(cfg["font_color"], tuple):
                    font.color.rgb = RGBColor(*cfg["font_color"])

                # 5. 添加项目符号和内容 (它们会自动继承上面设置的字体)
                bullet_run = p.add_run()
                bullet_run.text = "▶  "
                
                content_run = p.add_run()
                content_run.text = str(para_text)

        except KeyError as e:
            logging.error(f"摘要框配置项缺失: '{e}'。请检查cfg字典。")
        except Exception as e:
            logging.error(f"插入摘要时发生错误: {e}")


    # ==============================================================================
    #  页面操控函数
    # ==============================================================================
    @staticmethod
    def reorder_slides(prs: PptxPresentationObject, source_start_index: int, block_length: int, target_index: int):
        """
        对演示文稿中的幻灯片顺序进行重排。
        """
        # 添加类型检查
        if not isinstance(prs, PptxPresentationObject):
            raise TypeError("prs参数必须是PptxPresentationObject类型")
        if block_length <= 0:
            return

        slide_id_list = prs.slides._sldIdLst
        total_slides_before = len(slide_id_list)
        # --- 诊断探针：显示操作参数 --
        print("\n" + "#"*20 + " 进入 reorder_slides 函数 " + "#"*20)
        print(f"# 接收到任务: 将从索引 {source_start_index} (第 {source_start_index + 1} 页) 开始的 {block_length} 个页面，")
        print(f"# 移动到索引 {target_index} (即第 {target_index + 1} 页的位置)。")
        total_slides_before = len(prs.slides)
        print(f"# 当前总页数: {total_slides_before + 1}")
        
        try:
            # --- 深度复制幻灯片ID列表 ---
            all_slide_ids = []
            for i in range(len(slide_id_list)):
                all_slide_ids.append(slide_id_list[i])

            # --- 提取要移动的页面区块 ---
            block_to_move = all_slide_ids[source_start_index : source_start_index + block_length]
            if not block_to_move:
                logging.error(f"无法从索引 {source_start_index} 提取到要移动的页面区块，重排失败。")
                return
            # --- 构建剩余幻灯片列表 --
            remaining_slides = all_slide_ids[:source_start_index] + all_slide_ids[source_start_index + block_length:]
            # --- 计算新顺序 ---
            final_order_list = remaining_slides[:target_index] + block_to_move + remaining_slides[target_index:]
            # --- 更新幻灯片列表 ---
            del slide_id_list[:]
            slide_id_list.extend(final_order_list)
            logging.info(f"重排操作完成。现在总页数为 {len(slide_id_list)}")

        except Exception as e:
            logging.error(f"执行 reorder_slides 时发生严重错误: {e}", exc_info=True)
            print("#"*60)
            print("# 执行 reorder_slides 时发生严重错误，请检查上面的参数和日志。")
            print("#"*60 + "\n")
            raise
        
        print("#"*60 + "\n")

    @staticmethod
    def find_layout_index_by_name(prs: PptxPresentationObject, layout_name: str) -> Optional[int]:
        """
        根据名称查找幻灯片版式的索引。
        :param prs: Presentation 对象。
        :param layout_name: 要查找的版式名称。
        :return: 版式的索引（整数），如果未找到则返回 None。
        """
        for i, layout in enumerate(prs.slide_layouts):
            if layout.name == layout_name:
                logging.info(f"成功找到名为 '{layout_name}' 的版式，索引为 {i}。")
                return i
        logging.warning(f"在模板中未找到名为 '{layout_name}' 的版式。")
        return None