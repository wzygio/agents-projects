# core/canvas_preprocessor.py (V3.2 - 统一插入点逻辑版)
import logging, io
from typing import List
from pptx import Presentation
from pptx.presentation import Presentation as PptxPresentationObject

from utils.local_utils import Utils

@staticmethod
def _find_slides_by_title(prs: PptxPresentationObject, target_text: str | List[str], shape_name: str) -> List[int]:
    """
    查找所有匹配目标文本的幻灯片索引。
    
    Args:
        prs: PowerPoint演示文稿对象
        target_text: 要查找的文本，可以是字符串或字符串列表
        shape_name: 要匹配的形状名称    
    
    Returns:
        List[int]: 所有匹配幻灯片的索引列表
    """
    # 将单个字符串转换为列表，统一处理
    if isinstance(target_text, str):
        target_texts = [target_text]
    else:
        target_texts = target_text
    
    found_indices = []
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape_name in shape.name and shape.has_text_frame:
                slide_text = Utils.normalize_string(shape.text_frame.text) # type: ignore
                
                # 检查是否匹配任何一个目标文本
                for target in target_texts:
                    if Utils.normalize_string(target) in slide_text:
                        if i not in found_indices:  # 避免重复添加
                            logging.info(f"找到一个标题为 '{target}' 的页面，位置索引为: {i}")
                            found_indices.append(i)
                        break  # 找到匹配后跳出内层循环

    if not found_indices:
        targets_str = "', '".join(target_texts)
        logging.warning(f"未能在PPT中找到任何标题为 '{targets_str}' 且形状名为 '{shape_name}' 的页面。")
    
    return found_indices


@staticmethod
def _delete_slides(prs: PptxPresentationObject, slides_to_delete: list):
    unique_indices = sorted(list(set(slides_to_delete)), reverse=True)
    if not unique_indices: return
    logging.info(f"计划删除以下索引的幻灯片: {unique_indices}")
    for slide_index in unique_indices:
        try:
            rId = prs.slides._sldIdLst[slide_index].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[slide_index]
            logging.info(f"成功删除了索引为 {slide_index} (即第 {slide_index + 1} 页) 的幻灯片。")
        except Exception as e:
            logging.error(f"删除索引为 {slide_index} 的幻灯片时发生错误: {e}")


@staticmethod
def _ensure_blank_layout(prs: PptxPresentationObject, config: dict):
    layout_names_to_check = ["BLANK", "Blank", "空白"]
    for name in layout_names_to_check:
        for layout in prs.slide_layouts:
            if layout.name == name:
                logging.info(f"找到了名为 '{name}' 的可用版式。")
                if 'runtime_settings' not in config: config['runtime_settings'] = {}
                config['runtime_settings']['blank_layout_name'] = name
                return
    raise NameError("模板中未找到任何可用的空白版式 (尝试了 'BLANK', 'Blank', '空白')。")


def prepare_canvas(prs: PptxPresentationObject, config: dict) -> PptxPresentationObject:
    """画布预处理器的主函数，实现了统一的动态插入点逻辑。"""
    logging.info("--- 开始进行画布预处理 (统一插入点逻辑版) ---")

    sections_to_run = config.get('runtime_settings', {}).get('sections_to_generate', [])
    all_indices_to_delete = []
    if 'runtime_settings' not in config: config['runtimWe_settings'] = {}

    for section_name in sections_to_run:
        section_cfg = config.get('sections', {}).get(section_name, {})
        render_params = section_cfg.get('rendering_params', {})
        title_to_find = render_params.get('title_text', [])
        if title_to_find:
            logging.info(f"正在为章节 '{section_name}' 查找标题为 {len(title_to_find)} 个的页面...")
            logging.info(f"具体标题内容为: {title_to_find}")  # 新增日志
        else:
            logging.info(f"章节 '{section_name}' 的配置中缺少 'title_text'，无法为其进行定位删除。")
            continue

        # 根据返回的索引列表，动态规划插入点和待删除页面
        indices = _find_slides_by_title(prs, title_to_find, "TextBox")
        if indices:
            # 统一规则：插入点是所有待删除页面中，最靠前的那个
            insertion_point = min(indices)
            config['runtime_settings'][f'{section_name}_insert_at_index'] = insertion_point
            
            all_indices_to_delete.extend(indices)
            logging.info(f"为章节 '{section_name}' 规划了 {len(indices)} 个待删除页面，索引为: {indices}。")
            logging.info(f"为章节 '{section_name}' 动态规划的插入点为索引: {insertion_point}")

    _delete_slides(prs, all_indices_to_delete)
    _ensure_blank_layout(prs, config)

    logging.info("正在对修改后的PPT对象进行内存净化...")
    ppt_stream = io.BytesIO()
    prs.save(ppt_stream)
    ppt_stream.seek(0)
    sanitized_prs = Presentation(ppt_stream)
    
    logging.info("--- 画布预处理完毕 ---")
    return sanitized_prs

