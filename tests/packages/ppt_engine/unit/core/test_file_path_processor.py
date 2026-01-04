import pytest
from unittest.mock import MagicMock, patch
from datetime import date
# 假设 file_path_processor 暴露了 _find_monthly_template_dir 函数
# 如果是类方法，请相应调整导入和调用
from packages.ppt_engine.src.core import file_path_processor

class TestFilePathProcessor:

    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    @patch('packages.ppt_engine.src.core.file_path_processor.Path')
    def test_find_monthly_template_dir_logic(self, mock_path_cls, mock_date):
        """
        纯逻辑测试：验证查找顺序（先找本月，再找上月）
        """
        # 1. Setup
        mock_date.today.return_value = date(2024, 5, 15)
        
        # 模拟路径结构
        # network_base / template_base / 2024 / 05月
        mock_network = MagicMock()
        mock_path_cls.return_value = mock_network
        
        mock_tpl_base = MagicMock()
        mock_year_dir = MagicMock()
        mock_month_dir_may = MagicMock() # 5月
        mock_month_dir_apr = MagicMock() # 4月
        
        # 链式调用模拟
        mock_network.__truediv__.return_value = mock_tpl_base
        mock_tpl_base.__truediv__.return_value = mock_year_dir
        
        # 关键：控制 is_dir 的返回值来模拟"存在"与"不存在"
        
        # 场景 A: 5月存在
        mock_year_dir.__truediv__.side_effect = lambda x: mock_month_dir_may if "5月" in str(x) else mock_month_dir_apr
        mock_month_dir_may.is_dir.return_value = True
        
        config = {'path': {'network_source_dir': 'N:', 'daily_report_template': {'base_dir': 'Tpl'}}}
        
        # Test A
        res, _ = file_path_processor._find_monthly_template_dir(config)
        assert res == mock_month_dir_may
        
        # 场景 B: 5月不存在，4月存在
        mock_month_dir_may.is_dir.return_value = False
        mock_month_dir_apr.is_dir.return_value = True
        
        # Test B
        res, _ = file_path_processor._find_monthly_template_dir(config)
        assert res == mock_month_dir_apr
        
        # 场景 C: 都不存在
        mock_month_dir_apr.is_dir.return_value = False
        with pytest.raises(FileNotFoundError):
            file_path_processor._find_monthly_template_dir(config)
            
    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    def test_find_monthly_template_dir_not_found(self, mock_date, tmp_path):
        """测试都找不到"""
        mock_date.today.return_value = date(2024, 5, 15)
        
        # 创建基础目录，但不创建月份文件夹
        base_dir = tmp_path / "templates"
        base_dir.mkdir()

        config = {
            'path': {
                'network_source_dir': str(tmp_path), 
                'daily_report_template': {'base_dir': 'templates'}
            }
        }

        # 验证抛出异常
        with pytest.raises(FileNotFoundError):
            file_path_processor._find_monthly_template_dir(config)

    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    def test_find_daily_template_file_today_found(self, mock_date):
        """测试找到当天文件的情况"""
        # 设置模拟
        mock_today = date(2024, 5, 15)
        mock_date.today.return_value = mock_today

        # 创建模拟文件
        mock_file1 = MagicMock()
        mock_file1.name = "report_0515_v1.pptx"
        mock_file1.stat.return_value.st_mtime = 1000

        mock_file2 = MagicMock()
        mock_file2.name = "report_0515_v2.pptx"
        mock_file2.stat.return_value.st_mtime = 2000  # 更新的文件

        # 创建模拟目录
        mock_search_dir = MagicMock()
        mock_search_dir.glob.return_value = [mock_file1, mock_file2]
        mock_search_dir.name = "test_dir"

        # 执行测试
        result = file_path_processor._find_daily_template_file({}, mock_search_dir)

        # 验证
        assert result == "report_0515_v2.pptx"  # 应该返回最新的文件
        mock_search_dir.glob.assert_called_once_with("*0515*")

    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    def test_find_daily_template_file_previous_day_found(self, mock_date):
        """测试当天没找到但前一天找到的情况"""
        # 设置模拟
        mock_today = date(2024, 5, 15)
        mock_date.today.return_value = mock_today

        # 创建模拟文件
        mock_file = MagicMock()
        mock_file.name = "report_0514.pptx"
        mock_file.stat.return_value.st_mtime = 1000

        # 创建模拟目录
        mock_search_dir = MagicMock()
        # 第一次调用返回空列表（当天没找到），第二次调用返回文件（前一天找到）
        mock_search_dir.glob.side_effect = [[], [mock_file]]
        mock_search_dir.name = "test_dir"

        # 执行测试
        result = file_path_processor._find_daily_template_file({}, mock_search_dir)

        # 验证
        assert result == "report_0514.pptx"
        assert mock_search_dir.glob.call_count == 2

    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    def test_find_daily_template_file_not_found(self, mock_date):
        """测试3天内都找不到文件的情况"""
        # 设置模拟
        mock_today = date(2024, 5, 15)
        mock_date.today.return_value = mock_today

        # 创建模拟目录
        mock_search_dir = MagicMock()
        mock_search_dir.glob.return_value = []  # 总是返回空列表
        mock_search_dir.name = "test_dir"

        # 执行测试并验证异常
        with pytest.raises(FileNotFoundError, match="未找到最近3天内的日报文件"):
            file_path_processor._find_daily_template_file({}, mock_search_dir)

    @patch('packages.ppt_engine.src.core.file_path_processor._find_daily_template_file')
    @patch('packages.ppt_engine.src.core.file_path_processor._find_monthly_template_dir')
    @patch('packages.ppt_engine.src.core.file_path_processor.logging')
    def test_process_dynamic_settings_success(self, mock_logging, mock_find_monthly, mock_find_daily):
        """测试成功处理动态设置的情况"""
        # 设置模拟
        mock_dir_path = MagicMock()
        mock_relative_subdir = "2024/05月"
        mock_find_monthly.return_value = (mock_dir_path, mock_relative_subdir)

        mock_filename = "report_0515.pptx"
        mock_find_daily.return_value = mock_filename

        # 准备测试数据
        config = {
            'path': {
                'data_sources': [
                    {'key_name': 'other_template', 'filename': 'other.pptx'},
                    {'key_name': 'main_template', 'filename': 'old.pptx'}
                ]
            }
        }

        # 执行测试
        result = file_path_processor.process_dynamic_settings(config)

        # 验证
        assert result == config
        mock_find_monthly.assert_called_once_with(config)
        mock_find_daily.assert_called_once_with(config, mock_dir_path)

        # 验证主模板配置已更新
        main_template = next(item for item in config['path']['data_sources'] if item['key_name'] == 'main_template')
        assert main_template['filename'] == mock_filename
        assert main_template['network_subdir'] == mock_relative_subdir

    @patch('packages.ppt_engine.src.core.file_path_processor.date')
    @patch('packages.ppt_engine.src.core.file_path_processor._find_daily_template_file')
    @patch('packages.ppt_engine.src.core.file_path_processor._find_monthly_template_dir')
    @patch('packages.ppt_engine.src.core.file_path_processor.logging')
    def test_process_dynamic_settings_fallback(self, mock_logging, mock_find_monthly, mock_find_daily, mock_date):
        """测试动态查找失败，使用后备方案的情况"""
        # 设置模拟
        mock_find_monthly.side_effect = FileNotFoundError("未找到文件夹")

        mock_today = date(2024, 5, 15)
        mock_date.today.return_value = mock_today

        # 准备测试数据
        config = {
            'path': {
                'daily_report_template': {
                    'filename_format': 'daily_report_{date}.pptx'
                },
                'data_sources': [
                    {'key_name': 'main_template', 'filename': 'old.pptx'}
                ]
            }
        }

        # 执行测试
        result = file_path_processor.process_dynamic_settings(config)

        # 验证
        assert result == config
        mock_find_monthly.assert_called_once_with(config)
        mock_find_daily.assert_not_called()

        # 验证主模板配置已更新为后备方案
        main_template = next(item for item in config['path']['data_sources'] if item['key_name'] == 'main_template')
        assert main_template['filename'] == 'daily_report_0515.pptx'
        assert main_template['network_subdir'] == ''
