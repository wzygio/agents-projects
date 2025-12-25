import logging
import io
from typing import List, Union, Dict, Any
from pptx import Presentation
from pptx.presentation import Presentation as PptxPresentationObject

# 假设 Utils 在 common_utils 或 ppt_engine.utils 下
# 请根据实际路径调整 import
from packages.ppt_engine.src.utils.local_utils import Utils
from packages.ppt_engine.src.config import PptEngineConfig

logger = logging.getLogger("CanvasPreprocessor")

class CanvasPreprocessor:
    """
    [Core Component]
    负责在生成PPT之前对模板进行预处理：
    1. 查找并标记旧的幻灯片位置。
    2. 删除旧的幻灯片。
    3. 确保存在空白版式。
    4. 返回净化后的 PPT 对象。
    """

    def __init__(self, config: PptEngineConfig):
        self.config = config

    def prepare_canvas(self, prs: PptxPresentationObject) -> PptxPresentationObject:
        """
        画布预处理器的主入口。
        实现了统一的动态插入点逻辑。
        """
        logger.info("--- 开始进行画布预处理 (统一插入点逻辑版) ---")

        # 获取需要运行的章节列表
        # runtime_settings 是一个字典，所以用 .get() 是正确的
        sections_to_run = (self.config.runtime_settings or {}).get('sections_to_generate', [])
        
        # 如果 runtime_settings 为空，初始化它
        if self.config.runtime_settings is None:
            self.config.runtime_settings = {}

        all_indices_to_delete = []

        # 遍历配置中的章节，规划插入点和删除旧页
        # self.config.sections 是一个 SectionMap 对象，我们可以遍历它或者只遍历 sections_to_run
        for section_name in sections_to_run:
            # 获取该章节的配置对象
            # 注意：section_name 是字符串，我们需要从 section_map 中获取对应的 SectionConfig 对象
            # 由于 section_map 是 Pydantic 模型，我们用 getattr 安全获取
            section_cfg = getattr(self.config.sections, section_name, None)
            
            if not section_cfg:
                logger.warning(f"配置中找不到章节 '{section_name}' 的定义，跳过预处理。")
                continue

            # 获取 rendering_params (这是一个字典)
            render_params = section_cfg.rendering_params or {}
            title_to_find = render_params.get('title_text', [])

            if title_to_find:
                logger.info(f"正在为章节 '{section_name}' 查找标题为 {len(title_to_find)} 个的页面...")
                logger.debug(f"具体标题内容为: {title_to_find}")
            else:
                logger.info(f"章节 '{section_name}' 的配置中缺少 'title_text'，无法为其进行定位删除。")
                continue

            # 根据返回的索引列表，动态规划插入点和待删除页面
            # 这里的 "TextBox" 是我们约定用来识别标题的 Shape Name，通常模板里标题框叫这个
            indices = self._find_slides_by_title(prs, title_to_find, "TextBox")
            
            if indices:
                # 统一规则：插入点是所有待删除页面中，最靠前的那个
                insertion_point = min(indices)
                
                # 将计算结果存入 runtime_settings
                self.config.runtime_settings[f'{section_name}_insert_at_index'] = insertion_point
                
                all_indices_to_delete.extend(indices)
                logger.info(f"为章节 '{section_name}' 规划了 {len(indices)} 个待删除页面，索引为: {indices}。")
                logger.info(f"为章节 '{section_name}' 动态规划的插入点为索引: {insertion_point}")

        # 执行删除操作
        self._delete_slides(prs, all_indices_to_delete)
        
        # 确保有空白版式可用
        self._ensure_blank_layout(prs)

        logger.info("正在对修改后的PPT对象进行内存净化...")
        ppt_stream = io.BytesIO()
        prs.save(ppt_stream)
        ppt_stream.seek(0)
        sanitized_prs = Presentation(ppt_stream)
        
        logger.info("--- 画布预处理完毕 ---")
        return sanitized_prs

    def _find_slides_by_title(self, prs: PptxPresentationObject, target_text: Union[str, List[str]], shape_name: str) -> List[int]:
        """
        查找所有匹配目标文本的幻灯片索引。
        """
        # 将单个字符串转换为列表，统一处理
        if isinstance(target_text, str):
            target_texts = [target_text]
        else:
            target_texts = target_text
        
        found_indices = []
        for i, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                # 检查 shape.name 是否包含目标名称 (如 "TextBox") 且是一个文本框
                if shape_name in shape.name and shape.has_text_frame:
                    # 使用 Utils 工具类标准化文本 (去空格、转小写等)
                    slide_text = Utils.normalize_string(shape.text_frame.text) # type: ignore
                    
                    # 检查是否匹配任何一个目标文本
                    for target in target_texts:
                        if Utils.normalize_string(target) in slide_text:
                            if i not in found_indices:  # 避免重复添加
                                logger.info(f"找到一个标题为 '{target}' 的页面，位置索引为: {i}")
                                found_indices.append(i)
                            break  # 找到匹配后跳出内层循环 (一个页面只记录一次)

        if not found_indices:
            targets_str = "', '".join(target_texts)
            logger.warning(f"未能在PPT中找到任何标题为 '{targets_str}' 且形状名为 '{shape_name}' 的页面。")
        
        return found_indices

    def _delete_slides(self, prs: PptxPresentationObject, slides_to_delete: List[int]):
        """
        删除指定的幻灯片。
        注意：必须从后往前删，否则索引会乱。
        """
        # 去重并降序排序
        unique_indices = sorted(list(set(slides_to_delete)), reverse=True)
        
        if not unique_indices: return
        
        logger.info(f"计划删除以下索引的幻灯片: {unique_indices}")
        
        for slide_index in unique_indices:
            try:
                # python-pptx 没有直接的 delete_slide 方法，需要操作底层 XML
                xml_slides = prs.slides._sldIdLst
                slides = prs.slides
                
                # 获取关联ID并删除关系
                slide = slides[slide_index]
                rId = xml_slides[slide_index].rId
                prs.part.drop_rel(rId)
                
                # 删除幻灯片索引项
                del xml_slides[slide_index]
                
                logger.info(f"成功删除了索引为 {slide_index} (即第 {slide_index + 1} 页) 的幻灯片。")
            except Exception as e:
                logger.error(f"删除索引为 {slide_index} 的幻灯片时发生错误: {e}")

    def _ensure_blank_layout(self, prs: PptxPresentationObject):
        """
        确保模板中存在名为 "BLANK"/"Blank"/"空白" 的版式，
        并将其名称记录到 runtime_settings 中供后续使用。
        """
        layout_names_to_check = ["BLANK", "Blank", "空白"]
        
        for name in layout_names_to_check:
            for layout in prs.slide_layouts:
                if layout.name == name:
                    logger.info(f"找到了名为 '{name}' 的可用版式。")
                    
                    if self.config.runtime_settings is None:
                        self.config.runtime_settings = {}
                        
                    self.config.runtime_settings['blank_layout_name'] = name
                    return
                    
        # 如果没找到，抛出异常，因为后续生成必须依赖空白页
        raise NameError("模板中未找到任何可用的空白版式 (尝试了 'BLANK', 'Blank', '空白')。")