import factory
from typing import List, Dict, Optional, Any
from pathlib import Path

from tests.factories._base import PydanticModelFactory
from packages.anomaly_monitor.src.config import (
    CommonConfig,
    DataFilesConfig,
    DataColumnsConfig,
    DataConfig,
    PathConfig,
    LedgerConfig,
    DailyReportConfig,
    AnomalyMonitorConfig
)


class CommonConfigFactory(PydanticModelFactory):
    class Meta:
        model = CommonConfig

    log_level = "INFO"
    headless_mode = True

class DataFilesConfigFactory(PydanticModelFactory):
    class Meta:
        model = DataFilesConfig

    hl_raw = factory.Faker('file_path')
    batch_yield = factory.Faker('file_path')
    hl_history = factory.Faker('file_path')
    ct_yield = factory.Faker('file_path')
    mwdl_raw = factory.Faker('file_path')
    defect_group_dict = factory.Faker('file_path')

class DataColumnsConfigFactory(PydanticModelFactory):
    class Meta:
        model = DataColumnsConfig

    prod_code = factory.Faker('word')
    defect_desc = factory.Faker('word')
    batch = factory.Faker('word')

class DataConfigFactory(PydanticModelFactory):
    class Meta:
        model = DataConfig

    files = factory.SubFactory(DataFilesConfigFactory)
    columns = factory.SubFactory(DataColumnsConfigFactory)

class PathConfigFactory(PydanticModelFactory):
    class Meta:
        model = PathConfig

    input_path = factory.Faker('file_path')
    data_cache_path = factory.Faker('file_path')
    data_raw_dir = factory.Faker('file_path')
    hl_resources_dir = factory.Faker('file_path')
    log_dir = factory.Faker('file_path')

class LedgerConfigFactory(PydanticModelFactory):
    class Meta:
        model = LedgerConfig

    path = factory.Faker('file_path')
    file_name = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    mapping = factory.Dict({'A': 'generated_report', 'B': 'hl_report'})

class DailyReportConfigFactory(PydanticModelFactory):
    class Meta:
        model = DailyReportConfig

    record_ledger = factory.SubFactory(LedgerConfigFactory)
    hl_ledger = factory.SubFactory(LedgerConfigFactory)

class AnomalyMonitorConfigFactory(PydanticModelFactory):
    class Meta:
        model = AnomalyMonitorConfig

    common = factory.SubFactory(CommonConfigFactory)
    data = factory.SubFactory(DataConfigFactory)
    path = factory.SubFactory(PathConfigFactory)
    daily_report = factory.SubFactory(DailyReportConfigFactory)
