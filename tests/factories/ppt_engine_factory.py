
import factory
from typing import List, Dict, Optional, Any, Union, Literal
from pathlib import Path

from tests.factories._base import PydanticModelFactory
from packages.ppt_engine.src.config import (
    DailyReportTemplateConfig,
    DataSourceItem,
    PathsConfig,
    ElementLayout,
    TableBaseLayout,
    LocatorRule,
    YieldDataLocators,
    YieldDataConfig,
    CalculationParams,
    AssemblyPart,
    ColWidthCalculation,
    LayoutCalculations,
    TableLayoutConfig,
    SectionConfig,
    AppSettings,
    SectionMap,
    PptEngineConfig
)
from pptx.dml.color import RGBColor

class DailyReportTemplateConfigFactory(PydanticModelFactory):
    class Meta:
        model = DailyReportTemplateConfig

    base_dir = factory.Faker('file_path')
    filename_format = "daily_report_{date}.pptx"

class DataSourceItemFactory(PydanticModelFactory):
    class Meta:
        model = DataSourceItem

    key_name = factory.Faker('word')
    source_type = factory.Faker('random_element', elements=['network', 'upload', 'local'])
    filename = factory.Faker('file_name')
    network_subdir = factory.Faker('word')
    path = factory.Faker('file_path')

class PathsConfigFactory(PydanticModelFactory):
    class Meta:
        model = PathsConfig

    network_source_dir = factory.Faker('file_path')
    resources_dir = factory.Faker('file_path')
    data_cache_dir = factory.Faker('file_path')
    data_raw_dir = factory.Faker('file_path')
    log_dir = factory.Faker('file_path')
    output_dir = factory.Faker('file_path')
    output_ppt = factory.Faker('file_path')
    output_template_ppt = factory.Faker('file_path')
    main_py_path = factory.Faker('file_path')
    data_source_excel_FPY = factory.Faker('file_path')
    data_source_excel_anomaly = factory.Faker('file_path')
    data_source_excel_risk = factory.Faker('file_path')
    data_source_parquet_anomaly = factory.Faker('file_path')
    logo = factory.Faker('file_path')
    daily_report_template = factory.SubFactory(DailyReportTemplateConfigFactory)
    data_sources = factory.List([factory.SubFactory(DataSourceItemFactory) for _ in range(2)])
    base_dir = factory.Faker('file_path')

class ElementLayoutFactory(PydanticModelFactory):
    class Meta:
        model = ElementLayout

    left = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    top = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    width = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    height = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    font_size = factory.Faker('random_int', min=10, max=24)
    font_name = factory.Faker('word')
    fill_color = RGBColor(255, 255, 255)
    placeholder_name = factory.Faker('word')

class TableBaseLayoutFactory(PydanticModelFactory):
    class Meta:
        model = TableBaseLayout

    left = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    top = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    width = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    height = factory.Faker('pyfloat', min_value=0.0, max_value=10.0)
    font_name = factory.Faker('word')
    header_font_size = factory.Faker('random_int', min=10, max=16)
    body_font_size = factory.Faker('random_int', min=8, max=14)
    row_heights = factory.List([factory.Faker('pyfloat', min_value=0.5, max_value=2.0) for _ in range(3)])
    col_widths = factory.List([factory.Faker('pyfloat', min_value=0.5, max_value=5.0) for _ in range(3)])
    row_height_rules = factory.Dict({'header': 1.0, 'data': 0.8})
    col_width_rules = factory.Dict({'id': 1.0, 'name': 3.0})

class LocatorRuleFactory(PydanticModelFactory):
    class Meta:
        model = LocatorRule

    anchor_column = factory.Faker('word')
    image = factory.Dict({'row': 1, 'col': 1})
    sentence = factory.Dict({'row': 2, 'col': 2})
    section_data = factory.Dict({'row': 3, 'col': 3})

class YieldDataLocatorsFactory(PydanticModelFactory):
    class Meta:
        model = YieldDataLocators

    yield_trend_sheet = factory.SubFactory(LocatorRuleFactory)
    control_plan_sheet = factory.SubFactory(LocatorRuleFactory)

class YieldDataConfigFactory(PydanticModelFactory):
    class Meta:
        model = YieldDataConfig

    ppt_target_slides = factory.List([factory.Faker('random_int', min=1, max=10) for _ in range(2)])
    sheet_names = factory.Dict({'trend': 'YieldTrend', 'control': 'ControlPlan'})
    categories = factory.List([factory.Faker('word') for _ in range(3)])
    locators = factory.SubFactory(YieldDataLocatorsFactory)
    excel_sections = factory.Dict({'section1': [1, 2], 'section2': [3, 4]})
    categories_titles = factory.Dict({'category1': 'Category One', 'category2': 'Category Two'})

class CalculationParamsFactory(PydanticModelFactory):
    class Meta:
        model = CalculationParams

    total_size = factory.Faker('pyfloat', min_value=10.0, max_value=20.0)
    primary_item_size = factory.Faker('pyfloat', min_value=1.0, max_value=5.0)
    primary_item_count = factory.Faker('random_int', min=1, max=5)
    secondary_item_count = factory.Faker('random_int', min=1, max=5)
    primary_is_first = factory.Faker('boolean')

class AssemblyPartFactory(PydanticModelFactory):
    class Meta:
        model = AssemblyPart

    type = factory.Faker('random_element', elements=['narrow', 'fixed'])
    count = factory.Faker('random_int', min=1, max=5)
    value = factory.Faker('pyfloat', min_value=1.0, max_value=5.0)

class ColWidthCalculationFactory(PydanticModelFactory):
    class Meta:
        model = ColWidthCalculation

    narrow_col_params = factory.SubFactory(CalculationParamsFactory)
    assembly_pattern = factory.List([factory.SubFactory(AssemblyPartFactory) for _ in range(2)])

class LayoutCalculationsFactory(PydanticModelFactory):
    class Meta:
        model = LayoutCalculations

    row_heights = factory.SubFactory(CalculationParamsFactory)
    col_widths = factory.SubFactory(ColWidthCalculationFactory)

class TableLayoutConfigFactory(PydanticModelFactory):
    class Meta:
        model = TableLayoutConfig

    base = factory.SubFactory(TableBaseLayoutFactory)
    calculations = factory.SubFactory(LayoutCalculationsFactory)

class SectionConfigFactory(PydanticModelFactory):
    class Meta:
        model = SectionConfig

    rendering_params = factory.Dict({'param1': 'value1', 'param2': 'value2'})
    data_config = factory.SubFactory(YieldDataConfigFactory)
    layout_config = factory.Dict({'element1': factory.SubFactory(ElementLayoutFactory), 
                                  'element2': factory.SubFactory(ElementLayoutFactory)})
    table_layout = factory.SubFactory(TableLayoutConfigFactory)
    sheet_name = factory.Faker('word')
    specific_date = factory.Faker('date')
    summary_params = factory.Dict({'title': 'Summary', 'subtitle': 'Details'})
    layout = factory.Dict({'layout1': factory.SubFactory(ElementLayoutFactory), 
                          'layout2': factory.SubFactory(ElementLayoutFactory)})

class AppSettingsFactory(PydanticModelFactory):
    class Meta:
        model = AppSettings

    default_font = factory.Faker('word')
    author = factory.Faker('name')

class SectionMapFactory(PydanticModelFactory):
    class Meta:
        model = SectionMap

    yield_data = factory.SubFactory(SectionConfigFactory)
    anomaly_management = factory.SubFactory(SectionConfigFactory)

class PptEngineConfigFactory(PydanticModelFactory):
    class Meta:
        model = PptEngineConfig

    path = factory.SubFactory(PathsConfigFactory)
    settings = factory.SubFactory(AppSettingsFactory)
    sections = factory.SubFactory(SectionMapFactory)
    runtime_settings = factory.Dict({'debug': True, 'verbose': False})
