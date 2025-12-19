# input/ppt_reader.py (V2.0 - 依赖注入重构版)
import logging, os
from typing import List, Optional, Dict
import pandas as pd

from pptx import Presentation
from pptx.shapes.graphfrm import GraphicFrame

from ppt_generator_project.utils.utils import Utils

class PptReader:
    """
    一个用于从PowerPoint(.pptx)文件中提取特定内容的类。
    """

    def __init__(self, config: dict):
        """
        构造函数，不再接收ppt_path，而是接收config对象。
        它会自己从config中解析出正确的模板路径来加载。
        """
        self.config = config
        
        try:
            # 从传入的config对象中获取模板位置信息
            template_location = self.config['paths']['template_ppt']
            
            # 使用与main.py中完全相同的智能路径判断逻辑
            # 这确保了无论UI传入的是临时文件的完整路径，还是一个默认文件名，都能正确处理
            if os.path.sep in template_location or '/' in template_location:
                template_path = template_location
            else:
                # 注意：这里我们从config中获取base_dir，而不是依赖全局变量
                base_dir = self.config['paths'].get('base_dir', '.')
                resources_dir = self.config['paths']['resources_dir']
                template_path = os.path.join(base_dir, resources_dir, template_location)

            self.prs = Presentation(template_path)
            logging.info(f"PptReader 成功打开PPT文件: '{template_path}'")
        except Exception as e:
            # 同样，如果出错，记录日志并向上抛出异常
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
        返回以类别为键的字典，但通过标题信息来确保映射的准确性。
        
        :param categories: 用于作为返回字典键的类别名列表。
        :param target_slides: 一个整数列表，指定要从哪些页码的幻灯片中提取。
        :param shape_name: 要查找的形状的固定名称 (例如, "TextBox 4")。
        :param keyword: 用于定位和截取文本的关键字 (例如, "诉求")。
        :return: 一个以类别名为键，以提取的文本为值的字典。
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
                
            slide = self.prs.slides[slide_idx]
            
            # 在当前幻灯片上寻找目标形状
            for shape in slide.shapes:
                if shape.name in shape_name and shape.has_text_frame:
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
        data_section = self.config['sections']['yield_data']
        title_to_category = dict(zip(data_section['rendering_params']['title_text'],
                                data_section['data_config']['categories']))
        
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
        可以正确处理双行表头 (Multi-level header)。
        
        :param categories: 用于作为返回字典键的类别名列表。
        :param target_slides: 一个可选的整数列表，指定只从这些页码的幻灯片中提取。
        :return: 一个以类别名为键，以提取的DataFrame为值的字典。
        """
        if not target_slides:
            logging.warning("未提供目标页码，无法提取表格。")
            return {}

        # 1. 首先提取所有目标页面的标题
        slide_titles = self.extract_slide_titles(target_slides)
        
        # 2. 提取所有目标页面的表格
        found_dfs = []
        processed_slides = set()

        for i, slide in enumerate(self.prs.slides):
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
                    df = pd.DataFrame(columns=table_data[0])

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
        data_section = self.config['sections']['yield_data']
        title_to_category = dict(zip(data_section['rendering_params']['title_text'],
                                   data_section['data_config']['categories']))
        
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

        :param shape_name_prefix: 目标形状的名称前缀，例如 "summary_box_"。
        :param target_slides: 目标幻灯片页码列表。如果为None，则处理所有页面。
        :return: 一个字典，键为页码，值为该页上所有匹配形状的文本列表。
        """
        extracted_data: Dict[int, List[str]] = {}

        if target_slides is None:
            # 如果未指定页面，则处理所有幻灯片
            slide_indices_to_process = range(len(self.prs.slides))
        else:
            # 将用户提供的1-based页码转换为0-based索引
            slide_indices_to_process = [n - 1 for n in target_slides]

        for slide_idx in slide_indices_to_process:
            # 健壮性检查，防止传入的页码越界
            if not (0 <= slide_idx < len(self.prs.slides)):
                logging.warning(f"提供的页码 {slide_idx + 1} 超出范围，已跳过。")
                continue

            slide = self.prs.slides[slide_idx]
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
        使用与_find_slides_by_title相同的文本处理逻辑，但方向相反。
        
        :param target_slides: 目标幻灯片页码列表（1-based）
        :return: 一个字典，键为页码，值为该页的标题文本
        """
        titles = {}
        for slide_num in target_slides:
            slide_idx = slide_num - 1  # 转换为0-based索引
            
            if not (0 <= slide_idx < len(self.prs.slides)):
                logging.warning(f"页码 {slide_num} 超出范围，已跳过。")
                continue
                
            slide = self.prs.slides[slide_idx]
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
