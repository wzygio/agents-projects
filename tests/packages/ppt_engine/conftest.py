
import pytest
from unittest.mock import MagicMock
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from tests.factories.ppt_engine_factory import PptEngineConfigFactory


@pytest.fixture
def mock_config():
    """返回一个完整的 PptEngineConfig 对象 Mock"""
    return PptEngineConfigFactory.build()


@pytest.fixture
def mock_prs():
    """返回一个模拟的 PowerPoint Presentation 对象"""
    prs = MagicMock(spec=Presentation)

    # 模拟幻灯片
    mock_slide = MagicMock()
    mock_slide.shapes = []
    prs.slides = [mock_slide]

    return prs


@pytest.fixture
def mock_slide():
    """返回一个模拟的幻灯片对象"""
    slide = MagicMock()
    slide.shapes = []
    return slide


@pytest.fixture
def mock_shape():
    """返回一个模拟的形状对象"""
    shape = MagicMock()
    shape.shape_type = MSO_SHAPE_TYPE.TEXT_BOX
    shape.text_frame = MagicMock()
    shape.text = ""
    return shape


@pytest.fixture
def mock_table():
    """返回一个模拟的表格对象"""
    table = MagicMock()
    table.rows = [MagicMock() for _ in range(5)]
    table.columns = [MagicMock() for _ in range(3)]

    # 模拟单元格
    table.cell = MagicMock(side_effect=lambda row, col: MagicMock(
        text=f"Cell-{row}-{col}",
        margin_left=0,
        margin_right=0,
        margin_top=0,
        margin_bottom=0,
        fill=MagicMock(),
        text_frame=MagicMock()
    ))

    return table
