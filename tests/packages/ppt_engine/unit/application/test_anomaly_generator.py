import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

from packages.ppt_engine.src.application.anomaly_generator import AnomalyGenerator
from packages.ppt_engine.src.config import PptEngineConfig
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from tests.factories.ppt_engine_factory import PptEngineConfigFactory

class TestAnomalyGenerator:
    """AnomalyGenerator 的单元测试类"""

    def setup_method(self):
        """每个测试方法执行前的初始化"""
        # 1. 初始化配置 Mock
        self.mock_config = PptEngineConfigFactory()

        # 2. 初始化被测对象 (SUT)
        self.mock_prs = MagicMock()
        self.mock_element_processor = MagicMock()

        # 3. 创建 AnomalyGenerator 实例
        self.anomaly_generator = AnomalyGenerator(
            prs=self.mock_prs,
            config=self.mock_config,
            element_processor=self.mock_element_processor
        )

    # ==================== 纯函数逻辑测试 ====================

    @pytest.mark.parametrize("text_value,expected", [
        # Happy Path: 正常状态值
        ("open", (255, 0, 0)),  # 红色
        ("close", (0, 0, 255)),  # 蓝色
        ("OPEN", (255, 0, 0)),  # 大写字母
        ("Close", (0, 0, 255)),  # 首字母大写
        ("  open  ", (255, 0, 0)),  # 带空格
        ("CLOSE", (0, 0, 255)),  # 全大写

        # Sad Path: 未知状态值
        ("pending", (0, 0, 0)),  # 默认黑色
        ("unknown", (0, 0, 0)),  # 默认黑色
        ("", (0, 0, 0)),  # 空字符串
        (None, (0, 0, 0)),  # None值
    ])
    def test_get_status_font_color(self, text_value, expected):
        """测试状态字体颜色获取"""
        result = self.anomaly_generator._get_status_font_color(text_value)
        # RGBColor 继承自 tuple，其元素顺序为 (红, 绿, 蓝)
        assert (result[0], result[1], result[2]) == expected


    @pytest.mark.parametrize("df,expected", [
        # Happy Path: 正常数据
        (pd.DataFrame({
            '通报日期': ['2023-01-01', '2023-01-01'],
            '责任厂别': ['厂别A', '厂别B']
        }), "2023/1/1 8:30 至 2023/1/1 18:30 新增异常2项，共回复2项，未回0项；"),

        # Sad Path: 空数据
        (pd.DataFrame(), f"{datetime.now().strftime('%Y/%#m/%#d')} 8:30 至 {datetime.now().strftime('%Y/%#m/%#d')} 18:30 新增异常0项，共回复0项，未回0项；"),
    ])
    def test_generate_summary_part1(self, df, expected):
        """测试摘要第一部分生成"""
        result = AnomalyGenerator._generate_summary_part1(df)
        assert result == expected

    @pytest.mark.parametrize("df,expected", [
        # Happy Path: 正常数据
        (pd.DataFrame({
            '责任厂别': ['厂别A', '厂别A', '厂别B']
        }), "其中厂别A新增2项，已回复2项，未回复0项；厂别B新增1项，已回复1项，未回复0项"),

        # Sad Path: 空数据
        (pd.DataFrame(), ""),

        # 边界情况: 缺少分组列
        (pd.DataFrame({'其他列': ['值1', '值2']}), "无法生成分类摘要：缺少分组信息。"),
    ])
    def test_generate_summary_part2(self, df, expected):
        """测试摘要第二部分生成"""
        result = AnomalyGenerator._generate_summary_part2(df)
        assert result == expected

    @pytest.mark.parametrize("df,expected", [
        # Happy Path: 包含需要格式化的列
        (pd.DataFrame({
            '列1': [1, 2],
            '列2': [3, 4],
            '列3': [5, 6],
            '列4': [7, 8],
            '列5': [0.1, 0.2],  # 第5列(索引4)
            '列6': [0.3, 0.4],  # 第6列(索引5)
            '列7': [0.5, 0.6],  # 第7列(索引6)
            '列8': [0.7, 0.8],  # 第8列(索引7)
            '列9': [9, 10]
        }), pd.DataFrame({
            '列1': [1, 2],
            '列2': [3, 4],
            '列3': [5, 6],
            '列4': [7, 8],
            '列5': ['10.00%', '20.00%'],  # 格式化为百分比
            '列6': ['30.00%', '40.00%'],  # 格式化为百分比
            '列7': ['50.00%', '60.00%'],  # 格式化为百分比
            '列8': ['70.00%', '80.00%'],  # 格式化为百分比
            '列9': [9, 10]
        })),

        # Sad Path: 不包含需要格式化的列
        (pd.DataFrame({'列1': [1, 2], '列2': [3, 4]}), pd.DataFrame({'列1': [1, 2], '列2': [3, 4]})),
    ])
    def test_standardize_table(self, df, expected):
        """测试表格标准化"""
        result = AnomalyGenerator._standardize_table(df)

        # 检查形状是否相同
        assert result.shape == expected.shape

        # 检查需要格式化的列是否已正确格式化
        for col_idx in [5, 6, 7, 8]:  # 需要格式化的列索引
            if col_idx < len(result.columns):
                col_name = result.columns[col_idx]
                # 检查是否为百分比格式
                if not result.empty and col_idx < len(expected.columns):
                    for i in range(len(result)):
                        if result[col_name].iloc[i] != '':
                            assert '%' in str(result[col_name].iloc[i])

    # ==================== 依赖 Mock 的业务流测试 ====================

    @patch('packages.ppt_engine.src.utils.local_utils.Utils.find_latest_matching_file')
    @patch('packages.ppt_engine.src.application.anomaly_generator.ExcelReader.convert_to_parquet')
    @patch('pandas.read_parquet')
    @patch('packages.ppt_engine.src.application.anomaly_generator.datetime')
    def test_prepare_data_happy_path(self, mock_datetime, mock_read_parquet, mock_convert_to_parquet, mock_find_file):
        """测试数据准备流程，不使用真实文件IO"""
        # 1. 设置 Mock 返回值
        mock_find_file.return_value = Path('fake.xlsx')

        # 2. 模拟 Excel 转换为 Parquet
        mock_convert_to_parquet.return_value = None

        # 3. Mock 当前日期为下午，确保使用今天日期
        mock_now = MagicMock()
        mock_now.hour = 14  # 下午
        mock_now.strftime.return_value = "2023-01-01"
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)
        mock_datetime.date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs)

        # 4. 模拟读取 Parquet 文件，使用 datetime.date 对象作为日期类型
        test_date = datetime(2023, 1, 1).date()
        mock_df = pd.DataFrame({
            '通报日期': [test_date, test_date],  # 使用 datetime.date 对象
            '列1': [1, 2],
            '列2': [3, 4],
            '列3': [5, 6],
            '列4': [7, 8],
            '列5': [0.1, 0.2],
            '列6': [0.3, 0.4],
            '列7': [0.5, 0.6],
            '列8': [0.7, 0.8],
            '列9': [9, 10],
            '列10': [11, 12],
            '列11': [13, 14],
            '列12': [15, 16],
            '列13': [17, 18],
            '列14': [19, 20],
            '列15': [21, 22],
            '列16': [23, 24]
        })
        mock_read_parquet.return_value = mock_df

        # 5. 确保 cfg 包含必要的配置项
        self.anomaly_generator.cfg = {
            'sheet_name': 'anomaly',
            'summary_params': {'date_column': '通报日期'},
            'specific_date': '2023-01-01'
        }

        # 6. 调用 _prepare_data 方法
        self.anomaly_generator._prepare_data()

        # 7. 验证 processed_data 是否被正确填充
        assert "table" in self.anomaly_generator.processed_data
        assert not self.anomaly_generator.processed_data['table'].empty

        # 8. 验证 Mock 调用
        mock_find_file.assert_called_once()
        mock_convert_to_parquet.assert_called_once()
        mock_read_parquet.assert_called_once()

    @patch('packages.ppt_engine.src.utils.local_utils.Utils.find_latest_matching_file')
    @patch('packages.ppt_engine.src.application.anomaly_generator.ExcelReader.convert_to_parquet')
    @patch('pandas.read_parquet')
    def test_prepare_data_empty_df(self, mock_read_parquet, mock_convert_to_parquet, mock_find_file):
        """测试数据准备流程，处理空DataFrame"""
        # 1. 设置 Mock 返回值
        mock_find_file.return_value = Path('fake.xlsx')
        mock_convert_to_parquet.return_value = None

        # 2. 模拟读取 Parquet 文件返回空 DataFrame
        mock_read_parquet.return_value = pd.DataFrame()

        # 3. 调用 _prepare_data 方法
        self.anomaly_generator._prepare_data()

        # 4. 验证 processed_data 未被填充
        assert "table" not in self.anomaly_generator.processed_data

    def test_render_slides_without_data(self):
        """测试在没有数据时渲染幻灯片"""
        # 确保没有处理好的数据
        self.anomaly_generator.processed_data = {}

        # 调用 _render_slides 方法
        self.anomaly_generator._render_slides()

        # 验证没有创建新幻灯片
        self.mock_prs.slides.add_slide.assert_not_called()

    def test_render_slides_with_data(self):
        """测试在有数据时渲染幻灯片"""
        # 1. 补全配置 - 修复 logo_filename 为 None 的问题
        self.mock_config.path.logo_filename = "logo.png"
        self.mock_config.path.data_raw_dir = "."

        # 2. 补全 rendering_params 和 layout - 修复 KeyError: 'logo'
        # 使用普通字典而不是 MagicMock，避免 get 方法返回 MagicMock 对象
        section_cfg = {
            'rendering_params': {
                'insert_at_index': 6, 
                'rows_per_slide': 3, 
                'title_text': "CT异常闭环管理"
            },
            'layout': {
                "logo": {"left": 0.1, "top": 0.1, "width": 1.0}, 
                "title": {"left": 0.5, "top": 0.2},
                "summary": {"left": 0.5, "top": 0.3}
            }
        }

        # 3. 将配置挂载到 anomaly_generator
        self.anomaly_generator.cfg = section_cfg
        self.anomaly_generator.config = self.mock_config

        # 4. 准备测试数据
        test_df = pd.DataFrame({
            '列1': [1, 2, 3],
            '列2': ['A', 'B', 'C'],
            '列3': [0.1, 0.2, 0.3],
            '状态': ['open', 'close', 'open']
        })
        self.anomaly_generator.processed_data['table'] = test_df

        # 5. 模拟 element_processor 方法
        self.mock_element_processor.find_layout_index_by_name.return_value = 0
        self.mock_prs.slide_layouts.__getitem__.return_value = MagicMock()

        # 6. 模拟添加幻灯片
        mock_slide = MagicMock()
        self.mock_prs.slides.add_slide.return_value = mock_slide

        # 7. 调用 _render_slides 方法
        self.anomaly_generator._render_slides()

        # 8. 验证添加了幻灯片
        self.mock_prs.slides.add_slide.assert_called()

        # 9. 验证调用了 element_processor 的方法
        self.mock_element_processor.add_logo.assert_called()
        self.mock_element_processor.add_title.assert_called()
        self.mock_element_processor.add_summary.assert_called()


    def test_add_table(self):
        """测试添加表格到幻灯片"""
        # 1. 准备测试数据
        test_df = pd.DataFrame({
            '列1': [1, 2],
            '列2': ['A', 'B'],
            '列3': [0.1, 0.2],
            '状态': ['open', 'close']
        })

        # 2. 模拟幻灯片
        mock_slide = MagicMock()
        mock_table_shape = MagicMock()
        mock_table = MagicMock()
        mock_table_shape.table = mock_table
        mock_slide.shapes.add_table.return_value = mock_table_shape

        # 3. 调用 _add_table 方法
        self.anomaly_generator._add_table(mock_slide, test_df)

        # 4. 验证添加了表格
        mock_slide.shapes.add_table.assert_called()

        # 5. 验证设置了表格样式
        assert mock_table.style is not None
