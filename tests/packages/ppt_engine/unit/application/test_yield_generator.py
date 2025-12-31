
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from packages.ppt_engine.src.application.yield_generator import YieldDataSectionGenerator
from packages.ppt_engine.src.config import PptEngineConfig
from packages.ppt_engine.src.core.table_processor import TableProcessor
from packages.ppt_engine.src.core.element_processor import ElementProcessor

class TestYieldDataSectionGenerator:
    """YieldDataSectionGenerator 的单元测试类"""

    # ==================== 纯函数逻辑测试 ====================

    @pytest.mark.parametrize("start_cell,row_offset,col_offset,expected", [
        # Happy Path: 基本偏移
        ("B2", 1, 1, "C3"),
        ("A1", 0, 0, "A1"),
        ("Z5", 1, 1, "AA6"),

        # Boundary: 跨列测试
        ("Z9", 0, 1, "AA9"),
        ("AZ3", 0, 1, "BA3"),
    ])
    
    def test_calculate_offset_cell_happy_path(self, start_cell, row_offset, col_offset, expected):
        """测试正常偏移计算"""
        result = YieldDataSectionGenerator._calculate_offset_cell(start_cell, row_offset, col_offset)
        assert result == expected

    def test_calculate_offset_cell_negative_offset(self):
        """测试负偏移量导致坐标非法"""
        with pytest.raises(ValueError, match="计算出的新行列号"):
            YieldDataSectionGenerator._calculate_offset_cell("B2", -2, 0)

    @pytest.mark.parametrize("header_tuple,expected", [
        # Happy Path: 正常元组
        (("Total", "GAP"), "GAP"),
        (("品类", "LTPO"), "品类"),
        (("产品", "型号"), "产品"),
        (("目标", "M12目标"), "目标"),

        # Boundary: 单元素元组
        (("GAP",), "GAP"),
        (("Total",), "Total"),
    ])
    def test_sanitize_header_happy_path(self, header_tuple, expected):
        """测试正常表头清洗"""
        result = YieldDataSectionGenerator._sanitize_header(header_tuple)
        assert result == expected

    def test_sanitize_header_boundary(self):
        """测试边界情况：空元组或None"""
        assert YieldDataSectionGenerator._sanitize_header(None) == ""
        assert YieldDataSectionGenerator._sanitize_header(()) == ""
        assert YieldDataSectionGenerator._sanitize_header(("Unnamed", "Unnamed", "Total")) == "Total"

    @pytest.mark.parametrize("value,expected", [
        # Happy Path: 正数
        (0.123, ("12.30%", False)),
        (0.5, ("50.00%", False)),
        (1.0, ("100.00%", False)),

        # Sad Path: 负数
        (-0.05, ("-5.00%", True)),
        (-0.5, ("-50.00%", True)),

        # 特殊情况
        (0, ("0.00%", False)),
        ("12.5%", ("12.5%", False)),
        ("-5.2%", ("-5.2%", True)),
        (None, ("", False)),
    ])
    def test_format_numeric_value(self, value, expected):
        """测试数值格式化"""
        result = YieldDataSectionGenerator._format_numeric_value(value)
        assert result == expected

    # ==================== 依赖 Mock 的业务流测试 ====================

    @patch('packages.ppt_engine.src.utils.local_utils.Utils.find_latest_matching_file')
    @patch('packages.ppt_engine.src.application.yield_generator.ExcelReader')
    @patch('packages.ppt_engine.src.application.yield_generator.PptReader')
    def test_prepare_data_logic_flow(self, mock_ppt_reader, mock_excel_reader, mock_find_file, mock_config):
        """测试数据准备流程，不使用真实文件IO"""
        # 1. 设置 Mock 返回值
        mock_find_file.return_value = Path('fake.xlsx')

        # 2. 配置 ExcelReader Mock
        mock_reader_instance = MagicMock()
        mock_reader_instance.read_images.return_value = {'category1': 'image1.png'}
        mock_reader_instance.read_sentences.return_value = {'category1': 'sentence1'}
        mock_reader_instance.read_table_as_list.return_value = [
            ['Header1', 'Header2', 'Header3'],
            ['Data1', 'Data2', 'Data3']
        ]
        mock_reader_instance.__enter__.return_value = mock_reader_instance
        mock_reader_instance.__exit__.return_value = None
        mock_excel_reader.return_value = mock_reader_instance

        # 3. 配置 PptReader Mock
        mock_ppt_instance = MagicMock()
        mock_ppt_instance.extract_ppt_tables.return_value = {'category1': 'table_data'}
        mock_ppt_instance.extract_ppt_text.return_value = {'category1': 'text_data'}
        mock_ppt_reader.return_value = mock_ppt_instance

        # 4. 创建 YieldDataSectionGenerator 实例
        mock_prs = MagicMock()
        mock_element_processor = MagicMock()
        mock_table_processor = MagicMock()

        generator = YieldDataSectionGenerator(
            prs=mock_prs,
            config=mock_config,
            element_processor=mock_element_processor,
            table_processor=mock_table_processor
        )

        # 5. 调用 _prepare_data 方法
        generator._prepare_data()

        # 6. 验证 processed_data 是否被正确填充
        assert "images" in generator.processed_data
        assert "sentences" in generator.processed_data
        assert "table_data" in generator.processed_data
        assert "titles" in generator.processed_data
        assert "illustration_texts" in generator.processed_data
        assert "safeguards_texts" in generator.processed_data

        # 7. 验证 Mock 调用
        mock_find_file.assert_called_once()
        mock_excel_reader.assert_called()
        mock_ppt_reader.assert_called()
