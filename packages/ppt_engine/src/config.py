import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Literal
import yaml

from pydantic import BaseModel, Field, field_validator, model_validator
from pptx.dml.color import RGBColor

# =============================================================================
# 1. 基础工具与布局计算器 (Infrastructure Logic)
# =============================================================================

class LayoutCalculator:
    """
    [纯逻辑] 负责计算表格的行高和列宽。
    不依赖 pptx 库，只负责数学运算。
    """
    @staticmethod
    def calculate_sizes(total_size: float, 
                        primary_item_size: float, 
                        primary_item_count: int, 
                        secondary_item_count: int, 
                        primary_is_first: bool = True) -> tuple[List[float], float]:
        """通用尺寸计算公式"""
        remaining_size = total_size - (primary_item_size * primary_item_count)
        if secondary_item_count > 0:
            secondary_item_size = remaining_size / secondary_item_count
        else:
            secondary_item_size = 0.0

        sizes = []
        if primary_is_first:
            sizes.extend([primary_item_size] * primary_item_count)
            sizes.extend([secondary_item_size] * secondary_item_count)
        else:
            sizes.extend([secondary_item_size] * secondary_item_count)
            sizes.extend([primary_item_size] * primary_item_count)
            
        return sizes, secondary_item_size

# =============================================================================
# 2. 基础配置模型 (Base Models) - 增强兼容版
# =============================================================================

class BaseConfig(BaseModel):
    """
    基础配置类 (增强版)。
    既支持 Pydantic 的强类型校验，
    又通过魔术方法完美模拟了 Python 字典的行为，以兼容旧代码。
    """
    class Config:
        # 关键设置：允许运行时添加模型中未定义的字段（解决 runtime_settings 报错）
        extra = 'allow' 
        # 允许通过字段名或别名填充
        populate_by_name = True

    # --- 1. 解决 config['key'] 读取 ---
    def __getitem__(self, item):
        return getattr(self, item)

    # --- 2. 解决 config['key'] = value 赋值 ---
    def __setitem__(self, key, value):
        setattr(self, key, value)

    # --- 3. 解决 'key' in config 判断 ---
    def __contains__(self, key):
        return hasattr(self, key)

    # --- 4. 解决 config.get('key', default) ---
    def get(self, key, default=None):
        return getattr(self, key, default)

    # --- 5. 解决 config.update({...}) ---
    def update(self, other_dict: Dict[str, Any]):
        for k, v in other_dict.items():
            setattr(self, k, v)

    # --- 6. 兜底方案：访问不存在的属性不报错 ---
    # 注意：这个方法要放在最后，且只有当找不到属性时才会触发
    # 它导致了之前的 "None cannot be called" 错误，所以我们需要小心处理
    def __getattr__(self, item):
        # 如果代码试图访问 __getstate__ 等内部方法，不要拦截
        if item.startswith('__'):
            return super().__getattribute__(item)
        return None

# 定义颜色类型，支持 [r, g, b] 列表自动转为 RGBColor 对象
ColorType = Union[List[int], RGBColor, None]

def convert_color(v: Any) -> ColorType:
    """Pydantic 验证器：将列表转为 RGBColor"""
    if isinstance(v, list) and len(v) == 3:
        return RGBColor(*v)
    return v

# =============================================================================
# 3. 详细子配置模型 (Detailed Sub-Models)
# =============================================================================

# --- Paths ---
class DailyReportTemplateConfig(BaseConfig):
    base_dir: str
    filename_format: str

class DataSourceItem(BaseConfig):
    key_name: str
    source_type: Literal['network', 'upload', 'local']
    filename: str
    network_subdir: Optional[str] = None
    path: Optional[str] = None  # 上传文件时用于存储临时路径

class PathsConfig(BaseConfig):
    network_source_dir: str
    resources_dir: str
    data_cache_dir: str
    data_raw_dir: str
    log_dir: str
    output_dir: str
    output_ppt: str
    output_template_ppt: str
    main_py_path: str
    # 数据源快捷键
    data_source_excel_FPY: str
    data_source_excel_anomaly: str
    data_source_excel_risk: str
    data_source_parquet_anomaly: str
    logo: str
    
    daily_report_template: DailyReportTemplateConfig
    data_sources: List[DataSourceItem]
    
    # [新增] 兼容旧代码的 base_dir 字段，由 validator 自动填充
    base_dir: Optional[str] = None

# --- Layout Components ---
class ElementLayout(BaseConfig):
    left: float
    top: float
    width: float
    height: Optional[float] = None
    font_size: Optional[int] = None
    font_name: Optional[str] = None
    fill_color: ColorType = None
    placeholder_name: Optional[str] = None

    @field_validator('fill_color', mode='before')
    def validate_color(cls, v): return convert_color(v)

class TableBaseLayout(BaseConfig):
    left: float
    top: float
    width: float
    height: float
    font_name: str
    header_font_size: int
    body_font_size: int
    # 动态计算结果存储字段
    row_heights: Optional[List[float]] = None
    col_widths: Optional[List[float]] = None
    
    # 简单策略配置
    row_height_rules: Optional[Dict[str, float]] = None
    col_width_rules: Optional[Dict[str, Union[float, Dict[str, float]]]] = None

# --- Yield Data Section Specifics ---
class LocatorRule(BaseConfig):
    anchor_column: str
    image: Optional[Dict[str, int]] = None
    sentence: Optional[Dict[str, int]] = None
    section_data: Optional[Dict[str, int]] = None

class YieldDataLocators(BaseConfig):
    yield_trend_sheet: LocatorRule
    control_plan_sheet: LocatorRule
    excel_sections: Dict[str, List[int]]
    categories_titles: Dict[str, str]

class YieldDataConfig(BaseConfig):
    ppt_target_slides: List[int]
    sheet_names: Dict[str, str]
    categories: List[str]
    locators: YieldDataLocators

# --- Table Calculation Params (Complex) ---
class CalculationParams(BaseConfig):
    total_size: float
    primary_item_size: float
    primary_item_count: int
    secondary_item_count: int
    primary_is_first: bool = False

class AssemblyPart(BaseConfig):
    type: Literal['narrow', 'fixed']
    count: int
    value: Optional[float] = None

class ColWidthCalculation(BaseConfig):
    narrow_col_params: CalculationParams
    assembly_pattern: List[AssemblyPart]

class LayoutCalculations(BaseConfig):
    row_heights: Optional[CalculationParams] = None
    col_widths: Optional[ColWidthCalculation] = None

class TableLayoutConfig(BaseConfig):
    """
    专门对应 YAML 中 table_layout 下的结构
    base: ...
    calculations: ...
    """
    base: TableBaseLayout
    calculations: Optional[LayoutCalculations] = None
    
# --- Section Wrappers ---
class SectionConfig(BaseConfig):
    rendering_params: Optional[Dict[str, Any]] = None
    data_config: Optional[YieldDataConfig] = None
    layout_config: Optional[Dict[str, ElementLayout]] = None
    
    # [修改] 这里不再用 Dict，而是用明确定义的 TableLayoutConfig 类
    table_layout: Optional[TableLayoutConfig] = None

    # Anomaly Management Specifics
    sheet_name: Optional[str] = None
    specific_date: Optional[str] = None
    summary_params: Optional[Dict[str, str]] = None
    layout: Optional[Dict[str, ElementLayout]] = None 

    @model_validator(mode='after')
    def perform_layout_calculations(self):
        """
        [核心逻辑] 自动执行表格布局计算
        """
        # 1. 检查是否存在 table_layout 和 calculations
        # 注意：现在使用点号访问属性，而不是 get()，且类型非常明确
        if not self.table_layout or not self.table_layout.calculations:
            return self
        
        # 2. 获取对象引用
        # Pylance 现在非常清楚 base 就是 TableBaseLayout，row_heights 就是 List[float]
        base_layout = self.table_layout.base
        calculations = self.table_layout.calculations
        
        # 3. 计算行高
        if calculations.row_heights:
            row_heights, _ = LayoutCalculator.calculate_sizes(**calculations.row_heights.model_dump())
            # 赋值不再报错，因为 base_layout.row_heights 明确接受 List[float]
            base_layout.row_heights = row_heights

        # 4. 计算列宽
        if calculations.col_widths:
            cw_calc = calculations.col_widths
            # 先算窄列宽度
            _, narrow_width = LayoutCalculator.calculate_sizes(**cw_calc.narrow_col_params.model_dump())
            
            final_col_widths = []
            for part in cw_calc.assembly_pattern:
                if part.type == 'narrow':
                    final_col_widths.extend([narrow_width] * part.count)
                elif part.type == 'fixed' and part.value is not None:
                    final_col_widths.extend([part.value] * part.count)
            
            base_layout.col_widths = final_col_widths
            
        return self

# =============================================================================
# 4. 全局配置根模型 (Root AppConfig)
# =============================================================================

class AppSettings(BaseConfig):
    default_font: str
    author: str

class SectionMap(BaseConfig):
    yield_data: SectionConfig
    anomaly_management: SectionConfig
    # 允许额外章节
    model_config = {"extra": "allow"}

class PptEngineConfig(BaseConfig):
    paths: PathsConfig
    settings: AppSettings
    sections: SectionMap
    
    # 运行时动态设置
    runtime_settings: Optional[Dict[str, Any]] = {}

# =============================================================================
# 5. 加载与初始化逻辑 (Initialization)
# =============================================================================

# 确定项目根目录
try:
    # 假设当前文件在 packages/ppt_engine/src/config.py
    # 向上回溯 3 层到 project_root
    PROJECT_ROOT = Path(__file__).resolve().parents[4]
except NameError:
    PROJECT_ROOT = Path.cwd()

CONFIG_YAML_PATH = PROJECT_ROOT / "config" / "ppt_engine_config.yaml"

_config_instance: Optional[PptEngineConfig] = None

def load_config(yaml_path: Path = CONFIG_YAML_PATH) -> PptEngineConfig:
    """加载并返回强类型配置对象"""
    global _config_instance
    if _config_instance:
        return _config_instance

    if not yaml_path.exists():
        # Fallback 尝试
        alt_path = Path("config/ppt_engine_config.yaml")
        if alt_path.exists():
            yaml_path = alt_path
        else:
            raise FileNotFoundError(f"配置文件未找到: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        raw_data = yaml.safe_load(f)

    # 注入 base_dir (兼容旧逻辑)
    if 'paths' in raw_data:
        raw_data['paths']['base_dir'] = str(PROJECT_ROOT)

    try:
        _config_instance = PptEngineConfig(**raw_data)
        logging.info(f"配置加载成功: {yaml_path}")
        return _config_instance
    except Exception as e:
        logging.error(f"配置校验失败: {e}")
        raise

# =============================================================================
# 6. 导出全局对象与常量 (Exports)
# =============================================================================

# 预加载配置 (注意：这会立即执行加载，如果不需要立即加载可注释掉)
CONFIG = load_config()

# 兼容旧代码的常量导出
# 注意：CONFIG 现在的表现像个对象，但为了兼容 config['paths'] 写法，
# 建议在 BaseConfig 中保留 __getitem__ 或者直接迁移旧代码使用属性访问
LOG_DIR = PROJECT_ROOT / CONFIG.paths.log_dir
RESOURCES_DIR = PROJECT_ROOT / CONFIG.paths.resources_dir
DATA_RAW_DIR = PROJECT_ROOT / CONFIG.paths.data_raw_dir
OUTPUT_DIR = PROJECT_ROOT / CONFIG.paths.output_dir
MAIN_PY_PATH = PROJECT_ROOT / CONFIG.paths.main_py_path
