import os
import logging
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

# =============================================================================
# 1. 基础配置类 (终极兼容版)
# =============================================================================
class BaseConfig(BaseModel):
    """
    基础配置类。
    完美模拟字典的所有行为：keys(), values(), items(), get(), [], in
    同时支持 Pydantic 的强类型校验。
    """
    class Config:
        extra = 'allow' # 允许额外字段
        populate_by_name = True

    # --- 1. 字典核心迭代方法 (解决 .keys() 报错) ---
    def keys(self):
        """模拟字典的 .keys()，返回所有字段名"""
        return self.model_dump(by_alias=True).keys()

    def values(self):
        """模拟字典的 .values()，返回所有字段值"""
        return [getattr(self, k) for k in self.keys()]

    def items(self):
        """模拟字典的 .items()，返回 (key, value) 元组"""
        return [(k, getattr(self, k)) for k in self.keys()]

    # --- 2. 安全的 get 方法 ---
    def get(self, key, default=None):
        """
        模拟字典的 .get()。
        增强逻辑：如果属性存在但值为 None，且 default 不为 None，则返回 default。
        """
        value = getattr(self, key, None)
        if value is None and default is not None:
            return default
        return value if value is not None else default

    # --- 3. 基础字典访问 ---
    def __getitem__(self, item):
        val = getattr(self, item, None)
        if val is None and item not in self.keys():
             # 为了兼容某些宽松的旧代码，这里可以选择返回 None 还是报错
             # 标准字典行为是报错，但您的方案一似乎倾向于返回 None
             # 这里我们采用标准字典行为，因为 extra='allow' 已经允许动态存取了
             raise KeyError(f"'{item}' not found in configuration")
        return val

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __contains__(self, key):
        return hasattr(self, key) or key in self.keys()

    # --- 4. 兜底方案 ---
    def __getattr__(self, item):
        if item.startswith('__'):
            return super().__getattribute__(item)
        return None

# =============================================================================
# 2. 通用子组件配置 (复用于多个模块)
# =============================================================================

class DynamicPathConfig(BaseConfig):
    """动态路径查找配置"""
    base_path: Optional[str] = None
    subdirectory_pattern: Optional[str] = None
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
    """样式定义集合"""
    part1_title_style: Optional[StyleProperties] = None
    part1_content_style: Optional[StyleProperties] = None
    part2_title_style: Optional[StyleProperties] = None
    part2_content_style: Optional[StyleProperties] = None
    subtitle_red_bold: Optional[StyleProperties] = None
    subtitle_black_bold: Optional[StyleProperties] = None
    subtitle_L3_bold: Optional[StyleProperties] = None
    
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

# --- Data Processing Jobs ---

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
    job_type: str
    description: Optional[str] = None
    output_key: Optional[str] = None
    
    source_path: Optional[str] = None
    source_file: Optional[str] = None
    sheet_name: Optional[str] = None
    pattern: Optional[str] = None
    cell_sequence: Optional[CellSequence] = None
    
    row_locator: Optional[RowLocator] = None
    column_locator: Optional[ColumnLocator] = None
    
    file_locator: Optional[FileLocator] = None
    cell_locator: Optional[CellLocator] = None
    
    template_reader_config: Optional[TemplateReaderConfig] = None
    parser_config: Optional[ParserConfig] = None
    plan_finder_config: Optional[PlanFinderConfig] = None
    
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

# --- Font Processing Jobs ---

class ConditionalStyle(BaseConfig):
    if_parent_contains: str
    style: str

class TitleDefinition(BaseConfig):
    name: str
    pattern: str
    style: Optional[str] = None
    default_style: Optional[str] = None
    conditional_styles: Optional[List[ConditionalStyle]] = None
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
# 4. 根配置类 (ExcelEngineConfig)
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

    @classmethod
    def from_app_config(cls, app_config_dict: Dict[str, Any]) -> 'ExcelEngineConfig':
        """
        工厂方法：从全局 AppConfig 字典中提取 'excel_engine' 部分
        """
        # 1. 提取 excel_engine 配置
        # 这里的 key 必须与 config.yaml 中的 includes key 一致
        excel_data = app_config_dict.get('excel_engine', {})
        
        # 2. 如果全局配置中有通用路径，可以在这里注入到 excel_data 中 (可选)
        # global_paths = app_config_dict.get('path', {})
        # if 'paths' in excel_data:
        #    excel_data['paths']['log_dir'] = global_paths.get('logs', 'logs')

        return cls(**excel_data)

# =============================================================================
# 5. 加载逻辑 (保留单例，但推荐使用依赖注入)
# =============================================================================

config: Optional[ExcelEngineConfig] = None 

# 为了兼容旧代码的路径引用
# 注意：在 config 未初始化前，这些变量是不可用的
# 我们将它们设为 Lazy Proxy 或者在 main 初始化后再引用
# 最佳实践是不要在模块级别直接计算 Path(config.x)

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]
except NameError:
    PROJECT_ROOT = Path.cwd()

# 保留旧的 load_config 以兼容独立运行测试
def load_config(yaml_path: str = "config/excel_engine_config.yaml") -> ExcelEngineConfig | None:
    global config
    if config: return config
    
    import yaml
    if not os.path.exists(yaml_path):
         # 尝试从 PROJECT_ROOT 找
         yaml_path = os.path.join(PROJECT_ROOT, yaml_path)
    
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        config = ExcelEngineConfig(**data)
        return config
    else:
        # 如果找不到文件，返回一个空的配置或者是 None，视情况而定
        logging.warning(f"Standalone config not found: {yaml_path}")
        return None