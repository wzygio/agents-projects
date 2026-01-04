import pytest
from unittest.mock import MagicMock
from pptx import Presentation
from pptx.util import Inches
from packages.ppt_engine.src.infrastructure.ppt_reader import PptReader

class TestPptReader:
    
    @pytest.fixture
    def mock_config(self, tmp_path):
        """创建一个指向临时目录的 Mock 配置"""
        config = MagicMock()
        # 1. 路径配置
        config.path.output_template_ppt = "test_template.pptx"
        config.path.base_dir = str(tmp_path)
        config.path.resources_dir = "."
        
        # 2. 章节配置 (用于标题映射逻辑)
        # 模拟 sections.yield_data
        yield_section = MagicMock()
        
        # 模拟 rendering_params.title_text (PPT里的标题)
        rendering_params = {'title_text': ['Page Title 1']}
        # 支持 dict 访问和 model_dump
        yield_section.rendering_params = rendering_params
        
        # 模拟 data_config.categories (映射后的类别)
        data_config = {'categories': ['Category A']}
        yield_section.data_config = data_config
        
        config.sections.yield_data = yield_section
        
        return config

    def create_dummy_pptx(self, file_path):
        """
        创建一个包含符合 PptReader 逻辑的真实 PPTX 文件
        """
        prs = Presentation()
        # 使用空白版式
        slide_layout = prs.slide_layouts[5] 
        
        # --- Slide 1 (对应 Page Title 1) ---
        slide = prs.slides.add_slide(slide_layout)
        
        # 1. 添加标题 (PptReader 找 "TextBox" 作为标题)
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(5), Inches(1))
        title_box.name = "TextBox 1"
        title_box.text = "Page Title 1"
        
        # 2. 添加内容形状 (用于 extract_ppt_text)
        # 逻辑：找关键字 "Keyword:"，提取后面的内容
        content_box = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(5), Inches(2))
        content_box.name = "TargetShape 1"
        content_box.text = "Some prefix text. Keyword: Target Value\nNext line."
        
        # 3. 添加表格 (用于 extract_ppt_tables)
        table_shape = slide.shapes.add_table(rows=2, cols=2, left=Inches(0.5), top=Inches(4), width=Inches(4), height=Inches(2))
        table = table_shape.table
        table.cell(0, 0).text = "Col1"
        table.cell(0, 1).text = "Col2"
        table.cell(1, 0).text = "Val1"
        table.cell(1, 1).text = "Val2"
        
        # 4. 添加特定名称前缀形状 (用于 extract_text_from_named_shapes)
        named_box = slide.shapes.add_textbox(Inches(6), Inches(1), Inches(2), Inches(1))
        named_box.name = "Prefix_Shape_1"
        named_box.text = "Named Content"
        
        prs.save(file_path)

    def test_ppt_reader_integration(self, tmp_path, mock_config):
        """
        [集成测试] 验证 PptReader 的核心提取功能
        """
        # 1. 准备真实的 PPT 文件
        pptx_path = tmp_path / "test_template.pptx"
        self.create_dummy_pptx(pptx_path)
        
        # 2. 初始化 SUT
        # 这里的路径拼接逻辑已经被 create_dummy_pptx 和 mock_config 配合好了
        reader = PptReader(mock_config)
        
        # 3. 测试 extract_ppt_text (带关键字提取)
        # 参数: categories, target_slides, shape_name, keyword
        text_result = reader.extract_ppt_text(
            categories=['Category A'],
            target_slides=[1],
            shape_name="TargetShape",
            keyword="Keyword:"
        )
        # 验证：
        # 1. 标题 "Page Title 1" 映射到了 "Category A"
        # 2. 文本 "Keyword: Target Value\n" 提取出了 "Target Value" (strip后)
        assert "Category A" in text_result
        assert text_result["Category A"] == "Target Value"

    def test_extract_ppt_tables_integration(self, tmp_path, mock_config):
        """
        [集成测试] 验证表格提取
        """
        pptx_path = tmp_path / "test_template.pptx"
        self.create_dummy_pptx(pptx_path)
        reader = PptReader(mock_config)
        
        tables_result = reader.extract_ppt_tables(
            categories=['Category A'],
            target_slides=[1]
        )
        
        assert "Category A" in tables_result
        df = tables_result["Category A"]
        assert not df.empty
        # 验证表格内容 (Col1, Col2 是表头)
        assert "Val1" in df.values

    def test_extract_named_shapes_integration(self, tmp_path, mock_config):
        """
        [集成测试] 验证按名称前缀提取
        """
        pptx_path = tmp_path / "test_template.pptx"
        self.create_dummy_pptx(pptx_path)
        reader = PptReader(mock_config)
        
        # 提取前缀为 "Prefix_" 的形状
        result = reader.extract_text_from_named_shapes("Prefix_", target_slides=[1])
        
        # 结果是 {slide_index: [text_list]}
        assert 1 in result
        assert "Named Content" in result[1]

    def test_init_file_not_found_real(self, mock_config):
        """测试真实的文件不存在异常"""
        mock_config.path.output_template_ppt = "ghost.pptx"
        
        with pytest.raises(FileNotFoundError):
            PptReader(mock_config)