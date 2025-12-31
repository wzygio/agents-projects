
import pytest
from unittest.mock import MagicMock
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.factories.anomaly_monitor_factory import AnomalyMonitorConfigFactory


@pytest.fixture
def mock_config():
    """返回一个完整的 AnomalyMonitorConfig 对象 Mock"""
    return AnomalyMonitorConfigFactory.build()


@pytest.fixture
def mock_dataframe():
    """返回一个模拟的 DataFrame 对象"""
    return pd.DataFrame({
        'prod_code': ['A001', 'B002', 'C003'],
        'defect_desc': ['Defect A', 'Defect B', 'Defect C'],
        'batch': ['Batch1', 'Batch2', 'Batch3'],
        'date': ['2023-01-01', '2023-01-02', '2023-01-03']
    })


@pytest.fixture
def mock_driver():
    """返回一个模拟的 Selenium WebDriver 对象"""
    driver = MagicMock(spec=webdriver.Chrome)

    # 模拟 find_element 方法
    mock_element = MagicMock()
    mock_element.text = "Sample Text"
    mock_element.click = MagicMock()
    mock_element.send_keys = MagicMock()
    driver.find_element = MagicMock(return_value=mock_element)

    # 模拟 find_elements 方法
    driver.find_elements = MagicMock(return_value=[mock_element])

    # 模拟 get 方法
    driver.get = MagicMock()

    # 模拟 current_url 属性
    driver.current_url = "https://example.com"

    # 模拟 title 属性
    driver.title = "Example Page"

    return driver


@pytest.fixture
def mock_wait():
    """返回一个模拟的 WebDriverWait 对象"""
    wait = MagicMock(spec=WebDriverWait)

    # 模拟 until 方法
    mock_element = MagicMock()
    mock_element.text = "Sample Text"
    wait.until = MagicMock(return_value=mock_element)

    return wait


@pytest.fixture
def mock_excel_workbook():
    """返回一个模拟的 Excel Workbook 对象"""
    workbook = MagicMock()

    # 模拟工作表
    mock_sheet = MagicMock()
    mock_sheet.cell = MagicMock(side_effect=lambda row, column: MagicMock(
        value=f"Cell-{row}-{column}",
        coordinate=f"{chr(65+column)}{row}",
        row=row,
        column=column
    ))

    workbook.worksheets = [mock_sheet]
    workbook.active = mock_sheet
    workbook.sheetnames = ['Sheet1']
    workbook.__getitem__ = MagicMock(return_value=mock_sheet)

    return workbook
