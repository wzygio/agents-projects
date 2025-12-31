
import factory
from typing import List, Dict, Optional, Any
from pathlib import Path

from tests.factories._base import PydanticModelFactory
from packages.web_automation.src.config import (
    BrowserConfig,
    LedgerConfig,
    ReportItem,
    DailyReportConfig,
    WebAutomationConfig
)

class BrowserConfigFactory(PydanticModelFactory):
    class Meta:
        model = BrowserConfig

    headless = factory.Faker('boolean')
    timeout = factory.Faker('random_int', min=10000, max=60000)
    slow_mo = factory.Faker('random_int', min=10, max=100)
    viewport_width = factory.Faker('random_int', min=800, max=1920)
    viewport_height = factory.Faker('random_int', min=600, max=1080)

class LedgerConfigFactory(PydanticModelFactory):
    class Meta:
        model = LedgerConfig

    path = factory.Faker('file_path')
    file_name = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    mapping = factory.Dict({'A': 'generated_report', 'B': 'hl_report'})

class ReportItemFactory(PydanticModelFactory):
    class Meta:
        model = ReportItem

    name = factory.Faker('word')
    path = factory.Faker('file_path')

class DailyReportConfigFactory(PydanticModelFactory):
    class Meta:
        model = DailyReportConfig

    portal_url = factory.Faker('url')
    product_models = factory.List([factory.Faker('word') for _ in range(2)])
    reports = factory.List([factory.SubFactory(ReportItemFactory) for _ in range(2)])
    username = factory.Faker('user_name')
    password = factory.Faker('password')

class WebAutomationConfigFactory(PydanticModelFactory):
    class Meta:
        model = WebAutomationConfig

    browser = factory.SubFactory(BrowserConfigFactory)
    daily_report = factory.SubFactory(DailyReportConfigFactory)
    download_dir = factory.Faker('file_path')
