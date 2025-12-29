# input/ppt_reader.py (V3.0 - 强类型重构版)
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, TYPE_CHECKING
import pandas as pd

from pptx import Presentation
from pptx.shapes.graphfrm import GraphicFrame

from utils.local_utils import Utils

# [Standard 4] Import Standard: 使用 TYPE_CHECKING 防止循环依赖
if TYPE_CHECKING:
    from packages.ppt_engine.src.config import PptEngineConfig

class PptReader:
    """
    一个用于从PowerPoint(.pptx)文件中提取特定内容的类。
    """

    def __init__(self, config: "PptEngineConfig"):
        """
        构造函数。
        
        Args:
            config: 强类型的配置对象 (Dependency Injection)。
        """
        self.config = config
        
        try:
            # [Standard 3] Type Access: 使用点号访问 PathsConfig 属性
            paths_cfg = self.config.path
            template_location = paths_cfg.template_ppt
            
            # 智能路径判断逻辑 (Pathlib 风格)
            # 判断是否包含路径分隔符，或者是一个单纯的文件名
            if template_location is not None and (os.path.sep in template_location or '/' in template_location):
                 # 如果包含路径分隔符，视为绝对路径或相对路径
                template_path = Path(template_location)
            else:
                # 否则视为资源目录下的文件名
                # [Global Purge] 从 config 获取 base_dir 和 resources_dir
                base_dir = Path(paths_cfg.base_dir) if paths_cfg.base_dir is not None else Path(".")
                resources_dir = base_dir / paths_cfg.resources_dir
                template_path = resources_dir / template_location if template_location is not None else resources_dir

            # [Bug Defense 2] Path -> Str 强制转换，适配 python-pptx
            if not template_path.exists():
                 raise FileNotFoundError(f"PPT模板文件未找到: {template_path}")

            self.prs = Presentation(str(template_path))
            logging.info(f"PptReader 成功打开PPT文件: '{template_path}'")
            
        except Exception as e:
            logging.error(f"PptReader 打开PPT文件时出错: {e}")
            raise

    def extract_ppt_text(
        self, 
        categories: List[str], 
        target_slides: List[int], 
        shape_name: str, 
        keyword: str
    ) -> Dict[str, str]:
        """
        从指定的幻灯片页码中，查找特定名称的形状，并提取关键字后的文本。
        """
        if len(categories) != len(target_slides):
            logging.error("类别列表和目标幻灯片列表的长度不匹配，无法提取文本。")
            return {}

        # 1. 首先提取所有目标页面的标题
        slide_titles = self.extract_slide_titles(target_slides)
        
        # 2. 提取所有目标页面的文本
        found_texts = []
        for slide_num in target_slides:
            slide_idx = slide_num - 1  # 转换为0-based索引

            if not (0 <= slide_idx < len(self.prs.slides)):
                logging.warning(f"页码 {slide_num} 超出范围，已跳过。")
                continue
                
            slide = self.prs.slides[slide_idx] # type: ignore
            
            # 在当前幻灯片上寻找目标形状
            for shape in slide.shapes:
                if shape_name in shape.name and shape.has_text_frame:
                    full_text = shape.text_frame.text # type: ignore
                    
                    # 在形状的文本中寻找关键字
                    keyword_position = full_text.find(keyword)
                    
                    if keyword_position != -1:
                        # 从关键字后开始查找换行符
                        start_pos = keyword_position + len(keyword)
                        newline_pos = full_text.find('\n', start_pos)
                        
                        # 如果找到换行符，截取到换行符之前；否则截取到结尾
                        if newline_pos != -1:
                            demand_text = full_text[start_pos:newline_pos].strip()
                        else:
                            demand_text = full_text[start_pos:].strip()
                            
                        found_texts.append((slide_num, demand_text))  
                        logging.info(f"  > 在第 {slide_num} 页找到关键字 '{keyword}' 后的文本。")

                    break
        
        # 3. 建立"标题：文本"的映射
        title_to_text = {}
        for slide_num, text in found_texts:
            title = slide_titles.get(slide_num, "")
            if title:
                title_to_text[title] = text
                logging.info(f"为标题 '{title}' 建立了文本映射")
        
        # 4. 建立"类别：文本"的最终映射
        final_text_dict = {}
        
        # [Standard 3] Type Access: 获取 yield_data 章节配置
        # 这里为了安全访问复杂的嵌套结构，我们采用更稳健的写法
        yield_section = getattr(self.config.sections, 'yield_data', None)
        
        if not yield_section:
            logging.warning("未找到 'yield_data' 章节配置，无法建立类别映射。")
            return {}

        # 尝试从对象或字典中获取 rendering_params 和 data_config
        # 假设这些属性在 Config Model 中已定义
        rendering_params = getattr(yield_section, 'rendering_params', {})
        if not isinstance(rendering_params, dict): # 如果是 Pydantic 对象，转字典
             rendering_params = rendering_params.model_dump() if hasattr(rendering_params, 'model_dump') else dict(rendering_params)

        data_config = getattr(yield_section, 'data_config', {})
        if not isinstance(data_config, dict):
             data_config = data_config.model_dump() if hasattr(data_config, 'model_dump') else dict(data_config)

        config_titles = rendering_params.get('title_text', [])
        config_categories = data_config.get('categories', [])

        if not config_titles or not config_categories:
             logging.warning("'yield_data' 配置缺失 title_text 或 categories，映射失败。")
             return {}

        title_to_category = dict(zip(config_titles, config_categories))
        
        for title, text in title_to_text.items():
            # 使用标准化后的标题进行匹配
            normalized_title = Utils.normalize_string(title)
            for config_title, category in title_to_category.items():
                if normalized_title == Utils.normalize_string(config_title):
                    final_text_dict[category] = text
                    logging.info(f"成功将标题 '{title}' 映射到类别 '{category}'")
                    break
        
        # 检查是否有类别未匹配到文本
        unmatched_categories = set(categories) - set(final_text_dict.keys())
        if unmatched_categories:
            logging.warning(f"以下类别未能匹配到文本: {unmatched_categories}")

        logging.info(f"文本提取完成，共提取并映射了 {len(final_text_dict)} 条文本。")
        return final_text_dict

    def extract_ppt_tables(self, categories: List[str], target_slides: Optional[List[int]] = None) -> Dict[str, pd.DataFrame]:
        """
        [实例方法] 从已加载的演示文稿中提取表格。
        """
        if not target_slides:
            logging.warning("未提供目标页码，无法提取表格。")
            return {}

        # 1. 首先提取所有目标页面的标题
        slide_titles = self.extract_slide_titles(target_slides)
        
        # 2. 提取所有目标页面的表格
        found_dfs = []
        processed_slides = set()

        for i, slide in enumerate(self.prs.slides): # type: ignore
            slide_number = i + 1
            if slide_number not in target_slides:
                continue

            for shape in slide.shapes:
                if not isinstance(shape, GraphicFrame) or not shape.has_table:
                    continue

                table = shape.table
                table_data = [[cell.text for cell in row.cells] for row in table.rows]
                
                df = pd.DataFrame() 
                
                if len(table_data) >= 1:
                    header_df_temp = pd.DataFrame(table_data[0:1])
                    header_df_temp.replace('', pd.NA, inplace=True)
                    header_df_temp.ffill(axis=1, inplace=True)
                    
                    cleaned_header_arrays = header_df_temp.values.tolist()
                    multi_header = pd.MultiIndex.from_arrays(cleaned_header_arrays)
                    
                    body_data = table_data[1:]
                    df = pd.DataFrame(body_data, columns=multi_header)

                elif len(table_data) == 1:
                    df = pd.DataFrame(columns=table_data[0]) # type: ignore

                found_dfs.append((slide_number, df))
                processed_slides.add(slide_number)
                
        # 3. 建立"标题：表格"的映射
        title_to_table = {}
        for slide_num, df in found_dfs:
            title = slide_titles.get(slide_num, "")
            if title:
                title_to_table[title] = df
        
        # 4. 建立"类别：表格"的最终映射
        final_table_dict = {}
        
        # [Standard 3] 重复利用之前的 section 获取逻辑
        yield_section = getattr(self.config.sections, 'yield_data', None)
        if not yield_section:
             return {}
        
        # 这里的获取逻辑同 extract_ppt_text
        rendering_params = getattr(yield_section, 'rendering_params', {})
        if not isinstance(rendering_params, dict):
             rendering_params = rendering_params.model_dump() if hasattr(rendering_params, 'model_dump') else dict(rendering_params)
        
        data_config = getattr(yield_section, 'data_config', {})
        if not isinstance(data_config, dict):
             data_config = data_config.model_dump() if hasattr(data_config, 'model_dump') else dict(data_config)

        config_titles = rendering_params.get('title_text', [])
        config_categories = data_config.get('categories', [])
        
        title_to_category = dict(zip(config_titles, config_categories))
        
        for title, df in title_to_table.items():
            # 使用标准化后的标题进行匹配
            normalized_title = Utils.normalize_string(title)
            for config_title, category in title_to_category.items():
                if normalized_title == Utils.normalize_string(config_title):
                    final_table_dict[category] = df
                    logging.info(f"成功将标题 '{title}' 映射到类别 '{category}'")
                    break
        
        # 检查是否有类别未匹配到表格
        unmatched_categories = set(categories) - set(final_table_dict.keys())
        if unmatched_categories:
            logging.warning(f"以下类别未能匹配到表格: {unmatched_categories}")

        logging.info(f"PPT表格数据抓取成功，共提取并映射了 {len(final_table_dict)} 个表格。")
        return final_table_dict

    
    def extract_text_from_named_shapes(
        self,
        shape_name_prefix: str,
        target_slides: Optional[List[int]] = None
    ) -> Dict[int, List[str]]:
        """
        [实例方法] 从已加载的演示文稿中，只提取名称以特定前缀开头的形状内的文本。
        """
        extracted_data: Dict[int, List[str]] = {}

        if target_slides is None:
            # 如果未指定页面，则处理所有幻灯片
            slide_indices_to_process = range(len(self.prs.slides)) # type: ignore
        else:
            # 将用户提供的1-based页码转换为0-based索引
            slide_indices_to_process = [n - 1 for n in target_slides] # type: ignore

        for slide_idx in slide_indices_to_process:
            # 健壮性检查，防止传入的页码越界
            if not (0 <= slide_idx < len(self.prs.slides)):
                logging.warning(f"提供的页码 {slide_idx + 1} 超出范围，已跳过。")
                continue

            slide = self.prs.slides[slide_idx] # type: ignore
            slide_texts: List[str] = []

            for shape in slide.shapes:
                # 【核心逻辑】检查形状的名称是否以我们定义的前缀开头
                if shape.name.startswith(shape_name_prefix):
                    if shape.has_text_frame:
                        text = shape.text.strip()  # type: ignore
                        if text:
                            slide_texts.append(text)
            
            if slide_texts:
                extracted_data[slide_idx + 1] = slide_texts
        
        logging.info(f"按形状名称前缀 '{shape_name_prefix}' 提取文本成功，共在 {len(extracted_data)} 页中找到内容。")
        return extracted_data
    
    def extract_slide_titles(self, target_slides: List[int]) -> Dict[int, str]:
        """
        从指定的幻灯片页面中提取标题文本。
        """
        titles = {}
        for slide_num in target_slides:
            slide_idx = slide_num - 1  # 转换为0-based索引
            
            if not (0 <= slide_idx < len(self.prs.slides)):
                logging.warning(f"页码 {slide_num} 超出范围，已跳过。")
                continue
                
            slide = self.prs.slides[slide_idx] # type: ignore
            title = ""
            
            # 遍历页面中的所有形状，寻找标题
            for shape in slide.shapes:
                if "TextBox" in shape.name and shape.has_text_frame:
                    text = shape.text.strip() # type: ignore
                    if text:  # 只要有文本就认为是标题
                        title = text
                        break
                        
            if title:
                titles[slide_num] = title
                logging.info(f"在第 {slide_num} 页找到标题: {title}")
            else:
                logging.warning(f"在第 {slide_num} 页未找到标题")
                
        return titles