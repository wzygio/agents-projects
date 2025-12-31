"""
PPT引擎测试配置文件

此文件存放仅供PPT模块使用的Fixtures，实现依赖隔离。
包含模拟PPT配置、演示文稿对象和处理器的Fixtures。
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_ppt_config():
    """
    模拟PptEngineConfig对象

    模拟完整的配置结构，特别是yield_data章节的配置，
    包括data_config.categories_titles和data_config.excel_sections层级，
    确保它们不为None。

    Returns:
        MagicMock: 模拟的PptEngineConfig对象
    """
    config = MagicMock()

    # 模拟路径配置
    config.path = MagicMock()
    config.path.resources_dir = Path("tests/resources")
    config.path.output_dir = Path("tests/output")
    config.path.templates_dir = Path("tests/resources/templates")

    # 模拟yield_data配置
    config.yield_data = MagicMock()

    # 模拟data_config配置
    config.yield_data.data_config = MagicMock()

    # 关键：确保categories_titles和excel_sections不为None
    config.yield_data.data_config.categories_titles = {
        "category1": "标题1",
        "category2": "标题2"
    }
    config.yield_data.data_config.excel_sections = {
        "section1": {
            "title": "章节1",
            "data_range": "A1:D10"
        },
        "section2": {
            "title": "章节2",
            "data_range": "A11:D20"
        }
    }

    # 其他可能需要的配置
    config.style = MagicMock()
    config.style.font = "Arial"
    config.style.font_size = 12

    return config


@pytest.fixture
def mock_prs():
    """
    模拟pptx.Presentation对象

    让prs.slides表现得像一个列表，并让add_slide()方法返回一个新的MagicMock对象。

    Returns:
        MagicMock: 模拟的Presentation对象
    """
    prs = MagicMock()

    # 模拟slides集合，让它表现得像一个列表
    slides_list = []
    prs.slides = MagicMock()
    prs.slides.__len__ = MagicMock(return_value=len(slides_list))
    prs.slides.__getitem__ = MagicMock(side_effect=lambda i: slides_list[i])
    prs.slides.__iter__ = MagicMock(return_value=iter(slides_list))

    # 模拟add_slide方法，返回一个新的MagicMock(Slide)
    def add_slide_side_effect(layout):
        slide = MagicMock()
        slides_list.append(slide)
        # 更新长度
        prs.slides.__len__ = MagicMock(return_value=len(slides_list))
        return slide

    prs.slides.add_slide = MagicMock(side_effect=add_slide_side_effect)

    return prs


@pytest.fixture
def mock_element_processor():
    """
    模拟元素处理器

    Returns:
        MagicMock: 模拟的ElementProcessor对象
    """
    processor = MagicMock()
    # 可以根据需要添加特定的方法模拟
    processor.process_element = MagicMock(return_value=None)
    return processor


@pytest.fixture
def mock_table_processor():
    """
    模拟表格处理器

    Returns:
        MagicMock: 模拟的TableProcessor对象
    """
    processor = MagicMock()
    # 可以根据需要添加特定的方法模拟
    processor.process_table = MagicMock(return_value=None)
    return processor
