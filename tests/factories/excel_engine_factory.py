
import factory
from typing import List, Dict, Optional, Any, Union
from pathlib import Path

from tests.factories._base import PydanticModelFactory
from packages.excel_engine.src.config import (
    DynamicPathConfig,
    CellSequence,
    ModuleDefinition,
    SequentialExtractionRules,
    PathsConfig,
    StyleProperties,
    StyleDefinitionsConfig,
    ModelDefinitionsConfig,
    TextTransformation,
    TitlePatterns,
    DetailsPatterns,
    ExceptionJobConfig,
    RowLocator,
    ColumnLocator,
    FileLocator,
    CellLocator,
    TemplateReaderConfig,
    ParserConfig,
    PlanFinderSubConfig,
    PlanFinderConfig,
    DataJobConfig,
    ReportGeneratorJobConfig,
    ConditionalStyle,
    TitleDefinition,
    FontJobConfig,
    ReportInputs,
    ReportTextTemplates,
    ExcelEngineConfig
)

class DynamicPathConfigFactory(PydanticModelFactory):
    class Meta:
        model = DynamicPathConfig

    base_path = factory.Faker('file_path')
    subdirectory_pattern = factory.Faker('word')
    file_pattern = factory.Faker('word')

class CellSequenceFactory(PydanticModelFactory):
    class Meta:
        model = CellSequence

    start_cell = factory.Faker('bothify', text='A#')
    step = factory.Faker('random_int', min=1, max=10)
    end_row = factory.Faker('random_int', min=10, max=100)

class ModuleDefinitionFactory(PydanticModelFactory):
    class Meta:
        model = ModuleDefinition

    start_row = factory.Faker('random_int', min=1, max=10)
    step = factory.Faker('random_int', min=1, max=5)
    key_name = factory.Faker('word')

class SequentialExtractionRulesFactory(PydanticModelFactory):
    class Meta:
        model = SequentialExtractionRules

    modules_per_product = factory.Faker('random_int', min=1, max=5)
    module_definitions = factory.List([factory.SubFactory(ModuleDefinitionFactory) for _ in range(2)])

class PathsConfigFactory(PydanticModelFactory):
    class Meta:
        model = PathsConfig

    base_dir = factory.Faker('file_path')
    resources_dir = factory.Faker('file_path')
    temp_dir = factory.Faker('file_path')
    log_dir = factory.Faker('file_path')
    output_dir = factory.Faker('file_path')
    template_file = factory.Faker('file_name')
    temp_file = factory.Faker('file_name')
    output_file = factory.Faker('file_name')
    downloader_script_path = factory.Faker('file_path')
    downloader_python_executable = factory.Faker('file_path')
    content_generator_script_path = factory.Faker('file_path')
    style_generator_script_path = factory.Faker('file_path')

class StylePropertiesFactory(PydanticModelFactory):
    class Meta:
        model = StyleProperties

    font_name = factory.Faker('word')
    bold = factory.Faker('boolean')
    font_color = factory.Faker('hex_color')

class StyleDefinitionsConfigFactory(PydanticModelFactory):
    class Meta:
        model = StyleDefinitionsConfig

    part1_title_style = factory.SubFactory(StylePropertiesFactory)
    part1_content_style = factory.SubFactory(StylePropertiesFactory)
    part2_title_style = factory.SubFactory(StylePropertiesFactory)
    part2_content_style = factory.SubFactory(StylePropertiesFactory)
    subtitle_red_bold = factory.SubFactory(StylePropertiesFactory)
    subtitle_black_bold = factory.SubFactory(StylePropertiesFactory)
    subtitle_L3_bold = factory.SubFactory(StylePropertiesFactory)

class ModelDefinitionsConfigFactory(PydanticModelFactory):
    class Meta:
        model = ModelDefinitionsConfig

    source_file = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    pattern = factory.Faker('word')
    start_cell = factory.Faker('bothify', text='A#')
    step = factory.Faker('random_int', min=1, max=5)
    end_row = factory.Faker('random_int', min=10, max=100)

class TextTransformationFactory(PydanticModelFactory):
    class Meta:
        model = TextTransformation

    rule_name = factory.Faker('word')
    description = factory.Faker('sentence')
    source_pattern = factory.Faker('word')
    destination_pattern = factory.Faker('word')
    pattern = factory.Faker('word')
    replacement = factory.Faker('word')

class TitlePatternsFactory(PydanticModelFactory):
    class Meta:
        model = TitlePatterns

    exception_name = factory.Faker('word')
    daily_loss_rate = factory.Faker('word')
    monthly_loss_rate = factory.Faker('word')

class DetailsPatternsFactory(PydanticModelFactory):
    class Meta:
        model = DetailsPatterns

    exception_reason = factory.Faker('word')
    inline_monitoring = factory.Faker('word')
    is_stopped = factory.Faker('word')
    impact_scope = factory.Faker('word')
    improvement_measures = factory.Faker('word')

class ExceptionJobConfigFactory(PydanticModelFactory):
    class Meta:
        model = ExceptionJobConfig

    job_type = factory.Faker('word')
    description = factory.Faker('sentence')
    sheet_name = factory.Faker('word')
    data_column = factory.Faker('word')
    dynamic_path_config = factory.SubFactory(DynamicPathConfigFactory)
    sequential_extraction_rules = factory.SubFactory(SequentialExtractionRulesFactory)
    text_transformations = factory.List([factory.SubFactory(TextTransformationFactory) for _ in range(2)])
    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    date_column = factory.Faker('word')
    product_model_column = factory.Faker('word')
    title_column = factory.Faker('word')
    details_column = factory.Faker('word')
    factory_column = factory.Faker('word')
    title_patterns = factory.SubFactory(TitlePatternsFactory)
    details_patterns = factory.SubFactory(DetailsPatternsFactory)
    factory_routing_rules = factory.Dict({'key1': 'value1', 'key2': 'value2'})
    insertion_pattern = factory.Faker('word')

class RowLocatorFactory(PydanticModelFactory):
    class Meta:
        model = RowLocator

    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    search_column = factory.Faker('word')
    header_name = factory.Faker('word')
    occurrence = factory.Faker('random_int', min=1, max=5)

class ColumnLocatorFactory(PydanticModelFactory):
    class Meta:
        model = ColumnLocator

    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    search_row = factory.Faker('random_int', min=1, max=10)
    month_format = factory.Faker('word')
    production_yield_col = factory.Dict({'key1': 'value1', 'key2': 'value2'})
    monthly_yield_col = factory.Dict({'key1': 'value1', 'key2': 'value2'})

class FileLocatorFactory(PydanticModelFactory):
    class Meta:
        model = FileLocator

    base_path = factory.Faker('file_path')
    directory_rule = factory.Dict({'key1': 'value1', 'key2': 'value2'})
    name_contains = factory.Faker('word')

class CellLocatorFactory(PydanticModelFactory):
    class Meta:
        model = CellLocator

    sheet_name = factory.Faker('word')
    header_row = factory.Faker('random_int', min=1, max=10)
    row_locator = factory.SubFactory(RowLocatorFactory)
    column_locator = factory.SubFactory(ColumnLocatorFactory)

class TemplateReaderConfigFactory(PydanticModelFactory):
    class Meta:
        model = TemplateReaderConfig

    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    cell_sequence = factory.SubFactory(CellSequenceFactory)
    block_pattern = factory.Faker('word')

class ParserConfigFactory(PydanticModelFactory):
    class Meta:
        model = ParserConfig

    item_pattern = factory.Faker('word')
    item_pattern_2 = factory.Faker('word')
    item_pattern_3 = factory.Faker('word')
    item_pattern_4 = factory.Faker('word')

class PlanFinderSubConfigFactory(PydanticModelFactory):
    class Meta:
        model = PlanFinderSubConfig

    dynamic_path_config = factory.SubFactory(DynamicPathConfigFactory)
    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    product_model_column = factory.Faker('word')
    model_start_row = factory.Faker('random_int', min=1, max=10)
    model_step = factory.Faker('random_int', min=1, max=5)
    risk_content_column = factory.Faker('word')
    risk_content_offset = factory.Faker('random_int', min=0, max=5)
    block_pattern = factory.Faker('word')
    parser_pattern = factory.Faker('word')
    header_row = factory.Faker('random_int', min=1, max=10)
    risk_item_column = factory.Faker('word')
    release_plan_column = factory.Faker('word')

class PlanFinderConfigFactory(PydanticModelFactory):
    class Meta:
        model = PlanFinderConfig

    old_release_plan_finder = factory.SubFactory(PlanFinderSubConfigFactory)
    new_release_plan_finder = factory.SubFactory(PlanFinderSubConfigFactory)

class DataJobConfigFactory(PydanticModelFactory):
    class Meta:
        model = DataJobConfig

    job_type = factory.Faker('word')
    description = factory.Faker('sentence')
    output_key = factory.Faker('word')
    source_path = factory.Faker('file_path')
    source_file = factory.Faker('file_name')
    sheet_name = factory.Faker('word')
    pattern = factory.Faker('word')
    cell_sequence = factory.SubFactory(CellSequenceFactory)
    row_locator = factory.SubFactory(RowLocatorFactory)
    column_locator = factory.SubFactory(ColumnLocatorFactory)
    file_locator = factory.SubFactory(FileLocatorFactory)
    cell_locator = factory.SubFactory(CellLocatorFactory)
    template_reader_config = factory.SubFactory(TemplateReaderConfigFactory)
    parser_config = factory.SubFactory(ParserConfigFactory)
    plan_finder_config = factory.SubFactory(PlanFinderConfigFactory)
    template_name = factory.Faker('word')

class ReportGeneratorJobConfigFactory(PydanticModelFactory):
    class Meta:
        model = ReportGeneratorJobConfig

    job_type = factory.Faker('word')
    description = factory.Faker('sentence')
    data_source_key = factory.Faker('word')
    sheet_name = factory.Faker('word')
    data_column = factory.Faker('word')
    sequential_extraction_rules = factory.SubFactory(SequentialExtractionRulesFactory)
    template_name = factory.Faker('word')
    target_cells = factory.SubFactory(CellSequenceFactory)

class ConditionalStyleFactory(PydanticModelFactory):
    class Meta:
        model = ConditionalStyle

    if_parent_contains = factory.Faker('word')
    style = factory.Faker('word')

class TitleDefinitionFactory(PydanticModelFactory):
    class Meta:
        model = TitleDefinition

    name = factory.Faker('word')
    pattern = factory.Faker('word')
    style = factory.Faker('word')
    default_style = factory.Faker('word')
    conditional_styles = factory.List([factory.SubFactory(ConditionalStyleFactory) for _ in range(2)])
    # sub_definitions = factory.List([factory.SubFactory(TitleDefinitionFactory) for _ in range(2)])
    sub_definitions = factory.List([factory.SubFactory("tests.factories.excel_engine_factory.TitleDefinitionFactory") for _ in range(2)])

class FontJobConfigFactory(PydanticModelFactory):
    class Meta:
        model = FontJobConfig

    job_name = factory.Faker('word')
    sheet_name = factory.Faker('word')
    cell_sequence = factory.SubFactory(CellSequenceFactory)
    title_definitions = factory.List([factory.SubFactory(TitleDefinitionFactory) for _ in range(2)])

class ReportInputsFactory(PydanticModelFactory):
    class Meta:
        model = ReportInputs

    report_date = factory.Faker('date')
    sections_to_generate = factory.List([factory.Faker('word') for _ in range(2)])

class ReportTextTemplatesFactory(PydanticModelFactory):
    class Meta:
        model = ReportTextTemplates

    yield_summary = factory.Faker('sentence')
    exception_report_title = factory.Faker('sentence')
    exception_report_details = factory.Faker('sentence')
    default_empty_exception_module = factory.Faker('sentence')

class ExcelEngineConfigFactory(PydanticModelFactory):
    class Meta:
        model = ExcelEngineConfig

    path = factory.SubFactory(PathsConfigFactory)
    style_definitions = factory.SubFactory(StyleDefinitionsConfigFactory)
    model_definitions = factory.SubFactory(ModelDefinitionsConfigFactory)
    exception_processing_jobs = factory.List([factory.SubFactory(ExceptionJobConfigFactory) for _ in range(2)])
    data_processing_jobs = factory.List([factory.SubFactory(DataJobConfigFactory) for _ in range(2)])
    report_generator_jobs = factory.List([factory.SubFactory(ReportGeneratorJobConfigFactory) for _ in range(2)])
    font_processing_jobs = factory.List([factory.SubFactory(FontJobConfigFactory) for _ in range(2)])
    report = factory.SubFactory(ReportInputsFactory)
    report_text_templates = factory.SubFactory(ReportTextTemplatesFactory)
