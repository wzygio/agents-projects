
import pytest
from unittest.mock import MagicMock
import pandas as pd
from openpyxl import Workbook, load_workbook

from tests.factories.excel_engine_factory import ExcelEngineConfigFactory


@pytest.fixture
def mock_config():
    """返回一个完整的 ExcelEngineConfig 对象 Mock"""
    return ExcelEngineConfigFactory.build()


@pytest.fixture
def mock_workbook():
    """返回一个模拟的 Excel Workbook 对象"""
    workbook = MagicMock(spec=Workbook)

    # 模拟工作表
    mock_sheet = MagicMock()
    mock_sheet.cell = MagicMock(side_effect=lambda row, column: MagicMock(
        value=f"Cell-{row}-{column}",
        coordinate=f"{chr(65+column)}{row}",
        row=row,
        column=column,
        font=MagicMock(),
        fill=MagicMock(),
        border=MagicMock(),
        alignment=MagicMock()
    ))

    mock_sheet.iter_rows = MagicMock(return_value=[
        [MagicMock(value=f"Row-{i}-Col-{j}") for j in range(3)]
        for i in range(5)
    ])

    mock_sheet.max_row = 5
    mock_sheet.max_column = 3

    workbook.worksheets = [mock_sheet]
    workbook.active = mock_sheet
    workbook.sheetnames = ['Sheet1']
    workbook.__getitem__ = MagicMock(return_value=mock_sheet)

    return workbook


@pytest.fixture
def mock_worksheet():
    """返回一个模拟的 Worksheet 对象"""
    worksheet = MagicMock()

    # 模拟单元格
    worksheet.cell = MagicMock(side_effect=lambda row, column: MagicMock(
        value=f"Cell-{row}-{column}",
        coordinate=f"{chr(65+column)}{row}",
        row=row,
        column=column,
        font=MagicMock(),
        fill=MagicMock(),
        border=MagicMock(),
        alignment=MagicMock()
    ))

    # 模拟行迭代
    worksheet.iter_rows = MagicMock(return_value=[
        [MagicMock(value=f"Row-{i}-Col-{j}") for j in range(3)]
        for i in range(5)
    ])

    worksheet.max_row = 5
    worksheet.max_column = 3

    return worksheet


@pytest.fixture
def mock_dataframe():
    """返回一个模拟的 DataFrame 对象"""
    return pd.DataFrame({
        'col1': ['A', 'B', 'C'],
        'col2': [1, 2, 3],
        'col3': [True, False, True]
    })


@pytest.fixture
def mock_cell():
    """返回一个模拟的单元格对象"""
    cell = MagicMock()
    cell.value = "Test Value"
    cell.coordinate = "A1"
    cell.row = 1
    cell.column = 1
    cell.font = MagicMock()
    cell.fill = MagicMock()
    cell.border = MagicMock()
    cell.alignment = MagicMock()
    return cell
