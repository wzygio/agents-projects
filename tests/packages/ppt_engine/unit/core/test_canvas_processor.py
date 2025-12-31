import pytest
from unittest.mock import MagicMock, patch, call
from packages.ppt_engine.src.core.canvas_processor import CanvasPreprocessor

class TestCanvasPreprocessor:
    def setup_method(self):
        # 1. 初始化 Config Mock
        self.mock_config = MagicMock()
        # 确保 runtime_settings 存在，避免 AttributeError
        self.mock_config.runtime_settings = {}
        
        # 2. 初始化被测对象 (SUT)
        # 根据源代码，__init__ 只接收 config
        self.canvas_processor = CanvasPreprocessor(self.mock_config)
        
        # 3. 准备一个通用的 mock_prs，测试方法中可以进一步定制它
        self.mock_prs = MagicMock()

    @patch('packages.ppt_engine.src.core.canvas_processor.Presentation') # Patch pptx.Presentation 类
    def test_prepare_canvas_happy_path(self, mock_pptx_cls):
        """测试画布预处理的主流程：查找 -> 删除 -> 确认版式 -> 净化"""
        
        # --- A. 数据准备 ---
        # 1. 模拟 runtime_settings，指定要运行 'yield_data' 章节
        self.mock_config.runtime_settings = {'sections_to_generate': ['yield_data']}
        
        # 2. 模拟章节配置 (config.sections.yield_data.rendering_params)
        mock_section_cfg = MagicMock()
        mock_section_cfg.rendering_params = {'title_text': ['Target Title']}
        self.mock_config.sections.yield_data = mock_section_cfg
        
        # 3. 模拟幻灯片内容 (用于 _find_slides_by_title)
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.name = "TextBox"
        mock_shape.has_text_frame = True
        mock_shape.text_frame.text = "Target Title"
        mock_slide.shapes = [mock_shape]
        
        # 让 prs.slides 表现得像列表
        slides_list = [mock_slide]
        self.mock_prs.slides = MagicMock()
        self.mock_prs.slides.__iter__.side_effect = lambda: iter(slides_list)
        self.mock_prs.slides.__getitem__.side_effect = lambda i: slides_list[i]
        self.mock_prs.slides.__len__.side_effect = lambda: len(slides_list)
        
        # 4. 模拟版式 (用于 _ensure_blank_layout)
        # 显式设置 .name 属性
        mock_layout = MagicMock()
        mock_layout.name = "BLANK"
        self.mock_prs.slide_layouts = [mock_layout]
        
        # 5. 模拟删除所需的底层对象 (用于 _delete_slides)
        self.mock_prs.slides._sldIdLst = MagicMock()
        self.mock_prs.slides._sldIdLst.__getitem__.return_value.rId = "rId1"
        self.mock_prs.part = MagicMock()

        # --- B. 执行测试 ---
        # Mock 掉 Utils，避免被字符串处理逻辑干扰
        with patch('packages.ppt_engine.src.core.canvas_processor.Utils.normalize_string', side_effect=lambda x: x):
            
            # 这里的返回值应该是 mock_pptx_cls() 的返回值，因为代码最后重新加载了 PPT
            result = self.canvas_processor.prepare_canvas(self.mock_prs)
            
            # --- C. 验证结果 ---
            # 1. 验证是否调用了 save (净化步骤)
            self.mock_prs.save.assert_called()
            
            # 2. 验证是否重新加载了 PPT
            mock_pptx_cls.assert_called()
            assert result == mock_pptx_cls.return_value
            
            # 3. 验证是否计算出了插入点并写入配置
            # 因为找到了索引 0，所以应该记录下来
            assert self.mock_config.runtime_settings['yield_data_insert_at_index'] == 0

    def test_delete_slides_logic(self):
        """专门测试 _delete_slides 的底层 XML 操作逻辑"""
        # 1. 模拟 3 张幻灯片
        mock_slides_list = [MagicMock(), MagicMock(), MagicMock()]
        self.mock_prs.slides.__len__.side_effect = lambda: len(mock_slides_list)
        self.mock_prs.slides.__getitem__.side_effect = lambda i: mock_slides_list[i]
        
        # 2. 模拟底层 XML 列表 (_sldIdLst)
        mock_xml_list = MagicMock()
        # 模拟通过 rId 获取关系ID
        mock_xml_item = MagicMock()
        mock_xml_item.rId = "some_rId"
        mock_xml_list.__getitem__.return_value = mock_xml_item
        
        self.mock_prs.slides._sldIdLst = mock_xml_list
        self.mock_prs.part = MagicMock()

        # 3. 执行删除：索引 0 和 2
        self.canvas_processor._delete_slides(self.mock_prs, [0, 2])
        
        # 4. 验证：
        # (1) 必须从后往前删 (先2后0)，否则索引会乱。
        # 检查 __delitem__ 的调用顺序
        assert mock_xml_list.__delitem__.call_args_list == [call(2), call(0)]
        
        # (2) 必须调用 drop_rel 删除关系
        assert self.mock_prs.part.drop_rel.call_count == 2

    def test_ensure_blank_layout_success(self):
        """测试找到空白版式 (支持中文 '空白')"""
        mock_layout = MagicMock()
        mock_layout.name = "空白" # 显式赋值属性
        self.mock_prs.slide_layouts = [mock_layout]
        
        self.canvas_processor._ensure_blank_layout(self.mock_prs)
        
        assert self.mock_config.runtime_settings['blank_layout_name'] == "空白"

    def test_ensure_blank_layout_failure(self):
        """测试找不到空白版式时抛出异常"""
        mock_layout = MagicMock()
        mock_layout.name = "Title Only"
        self.mock_prs.slide_layouts = [mock_layout]
        
        with pytest.raises(NameError, match="模板中未找到任何可用的空白版式"):
            self.canvas_processor._ensure_blank_layout(self.mock_prs)