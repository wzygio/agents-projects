
import pytest
from unittest.mock import MagicMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from tests.factories.web_automation_factory import WebAutomationConfigFactory


@pytest.fixture
def mock_config():
    """返回一个完整的 WebAutomationConfig 对象 Mock"""
    return WebAutomationConfigFactory.build()


@pytest.fixture
def mock_driver():
    """返回一个模拟的 Selenium WebDriver 对象"""
    driver = MagicMock(spec=webdriver.Chrome)

    # 模拟 find_element 方法
    mock_element = MagicMock()
    mock_element.text = "Sample Text"
    mock_element.click = MagicMock()
    mock_element.send_keys = MagicMock()
    mock_element.is_displayed = MagicMock(return_value=True)
    mock_element.is_enabled = MagicMock(return_value=True)
    mock_element.get_attribute = MagicMock(return_value="attribute_value")
    driver.find_element = MagicMock(return_value=mock_element)

    # 模拟 find_elements 方法
    driver.find_elements = MagicMock(return_value=[mock_element])

    # 模拟 get 方法
    driver.get = MagicMock()

    # 模拟 current_url 属性
    driver.current_url = "https://example.com"

    # 模拟 title 属性
    driver.title = "Example Page"

    # 模拟 close 和 quit 方法
    driver.close = MagicMock()
    driver.quit = MagicMock()

    # 模拟 switch_to.window
    driver.switch_to = MagicMock()
    driver.switch_to.window = MagicMock()

    # 模拟 window_handles
    driver.window_handles = ["window1", "window2"]

    return driver


@pytest.fixture
def mock_wait():
    """返回一个模拟的 WebDriverWait 对象"""
    wait = MagicMock(spec=WebDriverWait)

    # 模拟 until 方法
    mock_element = MagicMock()
    mock_element.text = "Sample Text"
    mock_element.click = MagicMock()
    wait.until = MagicMock(return_value=mock_element)

    return wait


@pytest.fixture
def mock_chrome_options():
    """返回一个模拟的 Chrome Options 对象"""
    options = MagicMock(spec=Options)
    options.add_argument = MagicMock()
    options.add_experimental_option = MagicMock()
    return options


@pytest.fixture
def mock_element():
    """返回一个模拟的 WebElement 对象"""
    element = MagicMock()
    element.text = "Sample Text"
    element.click = MagicMock()
    element.send_keys = MagicMock()
    element.is_displayed = MagicMock(return_value=True)
    element.is_enabled = MagicMock(return_value=True)
    element.get_attribute = MagicMock(return_value="attribute_value")
    element.clear = MagicMock()
    element.tag_name = "div"
    return element


@pytest.fixture
def mock_alert():
    """返回一个模拟的 Alert 对象"""
    alert = MagicMock()
    alert.text = "Alert message"
    alert.accept = MagicMock()
    alert.dismiss = MagicMock()
    alert.send_keys = MagicMock()
    return alert
