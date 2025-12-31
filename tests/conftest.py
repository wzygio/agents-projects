"""
conftest.py - 全局测试配置文件

此文件负责测试环境的全局设置，不包含具体业务逻辑的Mock。
主要功能：
1. 修正Python路径，确保测试可以导入项目模块
2. 提供全局Fixture，模拟基础配置
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# 获取项目根目录（tests文件夹的上一级）
# 使用pathlib动态获取路径，避免硬编码
PROJECT_ROOT = Path(__file__).parent.parent

# 将项目根目录加入Python搜索路径
# 这样所有测试文件都能直接使用 from packages.xxx import ...
sys.path.insert(0, str(PROJECT_ROOT))

# 确保环境变量中有项目根目录
os.environ["PROJECT_ROOT"] = str(PROJECT_ROOT)


@pytest.fixture(scope="session")
def mock_global_settings(monkeysession):
    """
    全局Fixture，模拟src.config中的基础设置

    这个fixture在所有测试开始前运行一次，用于模拟基础配置，
    防止测试时因读取不到环境变量而失败。

    Args:
        monkeysession: pytest-monkeypatch的session版本fixture，
                      允许在整个测试会话期间修改环境

    Returns:
        None
    """
    # 模拟基础配置
    monkeysession.setenv("PROJECT_ROOT", str(PROJECT_ROOT))

    # 模拟src.config模块中的PROJECT_ROOT
    with patch('src.config.PROJECT_ROOT', PROJECT_ROOT):
        # 模拟AppConfig对象，包含必要的配置项
        mock_config = MagicMock()
        mock_config.common = MagicMock()
        mock_config.common.project_name = "test_project"
        mock_config.common.log_level = "DEBUG"
        mock_config.common.headless_mode = True

        mock_config.path = MagicMock()
        mock_config.path.base_dir = str(PROJECT_ROOT)
        mock_config.path.input = str(PROJECT_ROOT / "input")
        mock_config.path.output = str(PROJECT_ROOT / "output")
        mock_config.path.logs = str(PROJECT_ROOT / "logs")
        mock_config.path.resources = str(PROJECT_ROOT / "resources")
        mock_config.path.cache = str(PROJECT_ROOT / "cache")
        mock_config.path.logs_dir = str(PROJECT_ROOT / "logs")

        # 模拟load_config函数，返回我们的mock配置
        with patch('src.config.load_config', return_value=mock_config):
            yield
