import os
import yaml
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field

# =============================================================================
# 1. 基础配置类 (核心兜底机制)
# =============================================================================
class BaseConfig(BaseModel):
    """
    基础配置类。
    实现 __getattr__ 以允许访问未显式定义的字段，
    避免因为 YAML 中临时新增字段而导致代码报错（方案一的核心）。
    """
    def __getattr__(self, item) -> Any:
        return None

# =============================================================================
# 2. 通用子组件配置 (复用于多个模块)
# =============================================================================

class DynamicPathConfig(BaseConfig):
    """动态路径查找配置"""
    base_path: Optional[str] = None
    subdirectory_pattern: Optional[str] = None # e.g., "{year}M{month:02d}"
    file_pattern: Optional[str] = None

class CellSequence(BaseConfig):
    """单元格序列遍历配置"""
    start_cell: str
    step: int
    end_row: int

class ModuleDefinition(BaseConfig):
    """模块定义 (用于分块提取)"""
    start_row: int
    step: int
    key_name: str

class SequentialExtractionRules(BaseConfig):
    """顺序提取规则"""
    modules_per_product: int
    module_definitions: List[ModuleDefinition]

# =============================================================================
# 3. 各大板块详细配置
# =============================================================================

# --- Paths ---
class PathsConfig(BaseConfig):
    base_dir: str
    resources_dir: str
    temp_dir: str
    log_dir: str
    output_dir: str
    template_file: str
    temp_file: str
    output_file: str
    downloader_script_path: str
    downloader_python_executable: str
    content_generator_script_path: str
    style_generator_script_path: str

# --- Styles ---
class StyleProperties(BaseConfig):
    """具体的样式属性"""
    font_name: Optional[str] = None
    bold: Optional[bool] = None
    font_color: Optional[str] = None

class StyleDefinitionsConfig(BaseConfig):
    """样式定义集合，为了获得更好的补全，我们显式列出已知样式"""
    part1_title_style: Optional[StyleProperties] = None
    part1_content_style: Optional[StyleProperties] = None
    part2_title_style: Optional[StyleProperties] = None
    part2_content_style: Optional[StyleProperties] = None
    subtitle_red_bold: Optional[StyleProperties] = None
    subtitle_black_bold: Optional[StyleProperties] = None
    subtitle_L3_bold: Optional[StyleProperties] = None
    
    # 允许额外的自定义样式
    model_config = {"extra": "allow"}

# --- Model Definitions ---
class ModelDefinitionsConfig(BaseConfig):
    source_file: str
    sheet_name: str
    pattern: str
    start_cell: str
    step: int
    end_row: int

# --- Exception Processing Jobs ---
class TextTransformation(BaseConfig):
    rule_name: str
    description: Optional[str] = None
    source_pattern: Optional[str] = None
    destination_pattern: Optional[str] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None

class TitlePatterns(BaseConfig):
    exception_name: str
    daily_loss_rate: str
    monthly_loss_rate: str

class DetailsPatterns(BaseConfig):
    exception_reason: str
    inline_monitoring: str
    is_stopped: str
    impact_scope: str
    improvement_measures: str

class ExceptionJobConfig(BaseConfig):
    """
    异常处理任务配置。
    包含所有可能的字段，根据 job_type 使用不同的字段。
    """
    job_type: str
    description: Optional[str] = None
    sheet_name: Optional[str] = None
    
    # 提取旧异常相关
    data_column: Optional[str] = None
    dynamic_path_config: Optional[DynamicPathConfig] = None
    sequential_extraction_rules: Optional[SequentialExtractionRules] = None
    text_transformations: Optional[List[TextTransformation]] = None
    
    # 提取当日异常相关
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    date_column: Optional[str] = None
    product_model_column: Optional[str] = None
    title_column: Optional[str] = None
    details_column: Optional[str] = None
    factory_column: Optional[str] = None
    title_patterns: Optional[TitlePatterns] = None
    details_patterns: Optional[DetailsPatterns] = None
    
    # 合并任务相关
    factory_routing_rules: Optional[Dict[str, str]] = None
    insertion_pattern: Optional[str] = None

# --- Data Processing Jobs (非常复杂的部分) ---

class RowLocator(BaseConfig):
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    sheet_name: Optional[str] = None
    search_column: Optional[str] = None
    header_name: Optional[str] = None
    occurrence: Optional[int] = None

class ColumnLocator(BaseConfig):
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    search_row: Optional[int] = None
    month_format: Optional[str] = None
    # 针对 extract_monthly_yield_estimate
    production_yield_col: Optional[Dict[str, str]] = None
    monthly_yield_col: Optional[Dict[str, str]] = None

class FileLocator(BaseConfig):
    base_path: str
    directory_rule: Optional[Dict[str, str]] = None
    name_contains: Optional[str] = None

class CellLocator(BaseConfig):
    sheet_name: str
    header_row: int
    row_locator: Optional[RowLocator] = None
    column_locator: Optional[ColumnLocator] = None

class TemplateReaderConfig(BaseConfig):
    source_path: str
    source_file: str
    sheet_name: str
    cell_sequence: CellSequence
    block_pattern: str

class ParserConfig(BaseConfig):
    item_pattern: Optional[str] = None
    item_pattern_2: Optional[str] = None
    item_pattern_3: Optional[str] = None
    item_pattern_4: Optional[str] = None

class PlanFinderSubConfig(BaseConfig):
    # 复用 DynamicPathConfig 或直接定义字段
    dynamic_path_config: Optional[DynamicPathConfig] = None
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    sheet_name: str
    product_model_column: Optional[str] = None
    model_start_row: Optional[int] = None
    model_step: Optional[int] = None
    risk_content_column: Optional[str] = None
    risk_content_offset: Optional[int] = None
    block_pattern: Optional[str] = None
    parser_pattern: Optional[str] = None
    header_row: Optional[int] = None
    risk_item_column: Optional[str] = None
    release_plan_column: Optional[str] = None

class PlanFinderConfig(BaseConfig):
    old_release_plan_finder: Optional[PlanFinderSubConfig] = None
    new_release_plan_finder: Optional[PlanFinderSubConfig] = None

class DataJobConfig(BaseConfig):
    """
    数据处理任务配置 (Fat Model)。
    """
    job_type: str
    description: Optional[str] = None
    output_key: Optional[str] = None
    
    # parse_text_from_cells 相关
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    sheet_name: Optional[str] = None
    pattern: Optional[str] = None
    cell_sequence: Optional[CellSequence] = None
    
    # extract_tila_target 相关
    row_locator: Optional[RowLocator] = None
    column_locator: Optional[ColumnLocator] = None
    
    # extract_monthly_yield_estimate 相关
    file_locator: Optional[FileLocator] = None
    cell_locator: Optional[CellLocator] = None
    
    # extract_risk_items 相关
    template_reader_config: Optional[TemplateReaderConfig] = None
    parser_config: Optional[ParserConfig] = None
    plan_finder_config: Optional[PlanFinderConfig] = None
    
    # prepare_summary_data 相关
    template_name: Optional[str] = None

# --- Report Generator Jobs ---
class ReportGeneratorJobConfig(BaseConfig):
    job_type: str
    description: Optional[str] = None
    data_source_key: Optional[str] = None
    sheet_name: Optional[str] = None
    data_column: Optional[str] = None
    sequential_extraction_rules: Optional[SequentialExtractionRules] = None
    template_name: Optional[str] = None
    target_cells: Optional[CellSequence] = None

# --- Font Processing Jobs (递归结构) ---

class ConditionalStyle(BaseConfig):
    if_parent_contains: str
    style: str

class TitleDefinition(BaseConfig):
    name: str
    pattern: str
    style: Optional[str] = None
    default_style: Optional[str] = None
    conditional_styles: Optional[List[ConditionalStyle]] = None
    # 递归定义：子标题
    sub_definitions: Optional[List['TitleDefinition']] = None 

class FontJobConfig(BaseConfig):
    job_name: str
    sheet_name: str
    cell_sequence: CellSequence
    title_definitions: List[TitleDefinition]

# --- Report Inputs & Templates ---
class ReportInputs(BaseConfig):
    report_date: str = ''
    sections_to_generate: List[str] = []

class ReportTextTemplates(BaseConfig):
    yield_summary: str
    exception_report_title: str
    exception_report_details: str
    default_empty_exception_module: str

# =============================================================================
# 4. 根配置类 (AppConfig)
# =============================================================================

class ExcelEngineConfig(BaseConfig):
    paths: PathsConfig
    style_definitions: StyleDefinitionsConfig
    model_definitions: ModelDefinitionsConfig
    exception_processing_jobs: List[ExceptionJobConfig]
    data_processing_jobs: List[DataJobConfig]
    report_generator_jobs: List[ReportGeneratorJobConfig]
    font_processing_jobs: List[FontJobConfig]
    report: ReportInputs
    report_text_templates: ReportTextTemplates

# =============================================================================
# 5. 加载逻辑
# =============================================================================

_config_instance: Optional[ExcelEngineConfig] = None

def load_config(yaml_path: str = "config/excel_engine_config.yaml") -> ExcelEngineConfig:
    """读取 YAML 并转换为强类型的 ExcelEngineConfig 对象"""
    global _config_instance
    
    if _config_instance:
        return _config_instance

    if not os.path.exists(yaml_path):
        # 尝试查找相对路径，防止路径错误
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 这里假设 config 在项目根目录的 config 文件夹下，根据实际情况调整
        alt_path = os.path.join(base_dir, "config", "excel_engine_config.yaml")
        if os.path.exists(alt_path):
            yaml_path = alt_path
        else:
            raise FileNotFoundError(f"配置文件未找到: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        raw_data = yaml.safe_load(f)

    _config_instance = ExcelEngineConfig(**raw_data)
    return _config_instance

# 全局单例对象，但在使用前建议先调用 load_config 确保路径正确
config: ExcelEngineConfig = None # type: ignore