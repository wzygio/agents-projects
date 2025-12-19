# 文件路径：packages\excel_engine\src\core\text_parser.py
import re

class TextParser:
    def __init__(self):
        pass

    def process_text_with_title_styling(
        self,
        text_content: str,
        definitions: list[dict],
        default_style_name: str = 'content_style'
    ) -> list[tuple[str, str]]:
        """
        [最终版-递归扫描] 根据可嵌套的定义规则，通过递归的 finditer 扫描，精确解析多层标题。
        此版本基于之前成功的 finditer 机制，并扩展以支持层级和条件化样式。
        """
        
        # 这是一个内部递归函数，是整个新引擎的核心
        def recursive_parser(text: str, current_definitions: list[dict], parent_title_text: str = ""):
            fragments = []
            
            # 1. 为当前层级的所有标题规则，构建一个组合正则表达式
            patterns = [f"(?P<{defn['name']}>{defn['pattern']})" for defn in current_definitions]
            if not patterns: # 递归的“出口”：如果没有更多子规则，则剩余文本都是内容
                if text:
                    fragments.append((text, default_style_name))
                return fragments

            combined_pattern = re.compile("|".join(patterns))
            name_to_defn_map = {defn['name']: defn for defn in current_definitions}
            
            last_end = 0
            # 2. 使用 finditer 扫描当前文本块中的所有本级标题
            for match in combined_pattern.finditer(text):
                # a. 上一个标题的结尾到当前标题的开头，是“中间内容”
                intermediate_content = text[last_end:match.start()]
                
                # b. 处理当前匹配到的标题本身
                title_text = match.group(0)
                matched_name = match.lastgroup
                current_defn = name_to_defn_map[matched_name]

                # c. 递归地解析“中间内容”
                # 我们需要找到这个“中间内容”应该使用哪套子规则来解析
                # 在这个设计中，它属于上一个标题的子内容
                # (为了简化，我们假设只有标题后的内容才包含子标题，标题前的内容都是正文)
                if intermediate_content:
                    fragments.append((intermediate_content, default_style_name))

                # d. 确定当前标题的样式（包含条件化逻辑）
                chosen_style = current_defn.get('default_style') or current_defn.get('style')
                if parent_title_text: # 只有在有父标题时才检查条件
                    for cond in current_defn.get('conditional_styles', []):
                        if cond['if_parent_contains'] in parent_title_text:
                            chosen_style = cond['style']
                            break
                fragments.append((title_text, chosen_style))

                # e. 更新扫描位置
                last_end = match.end()

            # 3. 处理最后一个标题之后剩余的文本
            remaining_content = text[last_end:]
            if remaining_content:
                # 同样，我们假设这部分内容是正文
                fragments.append((remaining_content, default_style_name))
            
            return fragments

        # -------------------------------------------------------------
        #  为了精确处理三级标题，我们需要一个更精细的“先分章节，再深入”的逻辑
        #  上面的纯递归逻辑过于理想化，下面是为您量身定制的、更稳健的实现
        # -------------------------------------------------------------
        
        final_fragments = []
        l1_def = definitions[0]
        l1_pattern = re.compile(l1_def['pattern'])
        
        last_end = 0
        # Pass 1: 扫描一级标题，将文本分为大的章节
        for l1_match in l1_pattern.finditer(text_content):
            # 添加一级标题前的内容
            content_before = text_content[last_end:l1_match.start()]
            if content_before: final_fragments.append((content_before, default_style_name))

            # 添加一级标题
            l1_title_text = l1_match.group(0)
            final_fragments.append((l1_title_text, l1_def['style']))
            
            # 定义当前章节的范围
            chapter_start = l1_match.end()
            next_l1_match = next(l1_pattern.finditer(text_content, pos=chapter_start), None)
            chapter_end = next_l1_match.start() if next_l1_match else len(text_content)
            chapter_content = text_content[chapter_start:chapter_end]
            
            # Pass 2 & 3: 在当前章节内，处理二级和三级标题
            if l1_def.get('sub_definitions'):
                final_fragments.extend(
                    self._parse_chapter(chapter_content, l1_def['sub_definitions'], l1_title_text, default_style_name)
                )
            else:
                if chapter_content:
                    final_fragments.append((chapter_content, default_style_name))

            last_end = chapter_end

        # 处理最后一个一级标题之后的内容
        final_content = text_content[last_end:]
        if final_content: final_fragments.append((final_content, default_style_name))

        # (这里的 pprint 仅用于调试，您可以保留或移除)
        print("\n" + "="*20 + " [最终版解析]生成的 fragments 列表 " + "="*20)
        print("="*65 + "\n")

        return final_fragments


    def parse_fragments_hierarchical(self, text_content: str, definitions: list[dict], default_style_name: str) -> list[tuple[str, str]]:
        """
        [策略二：分层解析] 完整保留并调用你的多级 finditer 解析引擎。
        """
        if not text_content or not str(text_content).strip(): return []
        if not definitions: return [(text_content, default_style_name)]

        # --- 这是你提供的、功能完备的多级解析器的入口 ---
        final_fragments = []
        l1_def = definitions[0]
        l1_pattern = re.compile(l1_def['pattern'], flags=re.MULTILINE)
        
        last_end = 0
        # Pass 1: 扫描一级标题，将文本分为大的章节
        for l1_match in l1_pattern.finditer(text_content):
            content_before = text_content[last_end:l1_match.start()]
            if content_before: final_fragments.append((content_before, default_style_name))

            l1_title_text = l1_match.group(0)
            final_fragments.append((l1_title_text, l1_def['style']))
            
            chapter_start = l1_match.end()
            next_l1_match = next(l1_pattern.finditer(text_content, pos=chapter_start), None)
            chapter_end = next_l1_match.start() if next_l1_match else len(text_content)
            chapter_content = text_content[chapter_start:chapter_end]
            
            if l1_def.get('sub_definitions'):
                final_fragments.extend(
                self._parse_chapter(chapter_content, l1_def['sub_definitions'], l1_title_text, default_style_name)
                )
            elif chapter_content:
                final_fragments.append((chapter_content, default_style_name))

            last_end = chapter_end

        final_content = text_content[last_end:]
        if final_content: final_fragments.append((final_content, default_style_name))

        if not final_fragments:
            return [(text_content, default_style_name)]
        
        return final_fragments


    def _parse_chapter(self, chapter_text: str, l2_definitions: list, parent_title_text: str, default_style: str):
        fragments = []
        l2_def = l2_definitions[0]
        l2_pattern = re.compile(l2_def['pattern'])
        
        last_end = 0
        # Pass 2: 扫描二级标题
        for l2_match in l2_pattern.finditer(chapter_text):
            content_before = chapter_text[last_end:l2_match.start()]
            
            l2_title_text = l2_match.group(0)
            
            # 确定二级标题的样式
            chosen_l2_style = l2_def['default_style']
            for cond in l2_def.get('conditional_styles', []):
                if cond['if_parent_contains'] in parent_title_text:
                    chosen_l2_style = cond['style']
                    break
            
            # Pass 3: 在二级标题前的文本中找三级标题
            if l2_def.get('sub_definitions'):
                fragments.extend(
                    self._parse_section(content_before, l2_def['sub_definitions'], default_style)
                )
            else:
                if content_before: fragments.append((content_before, default_style))

            fragments.append((l2_title_text, chosen_l2_style))
            last_end = l2_match.end()

        # 处理最后一个二级标题后的内容（这里面也可能包含三级标题）
        final_content = chapter_text[last_end:]
        if l2_def.get('sub_definitions'):
            fragments.extend(
                self._parse_section(final_content, l2_def['sub_definitions'], default_style)
            )
        else:
            if final_content: fragments.append((final_content, default_style))
        
        return fragments


    def _parse_section(self, section_text: str, l3_definitions: list, default_style: str):
        fragments = []
        l3_def = l3_definitions[0]
        l3_pattern = re.compile(l3_def['pattern'])
        
        last_end = 0
        # Pass 3: 扫描三级标题
        for l3_match in l3_pattern.finditer(section_text):
            content_before = section_text[last_end:l3_match.start()]
            if content_before: fragments.append((content_before, default_style))
            
            title_text = l3_match.group(0)
            fragments.append((title_text, l3_def['style']))
            last_end = l3_match.end()

        final_content = section_text[last_end:]
        if final_content: fragments.append((final_content, default_style))
        return fragments
    
default_text_parser = TextParser()