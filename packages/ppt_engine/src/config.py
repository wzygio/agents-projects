import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Literal, TYPE_CHECKING
import yaml

from pydantic import BaseModel, Field, field_validator, model_validator
from pptx.dml.color import RGBColor

from src.config import PROJECT_ROOT

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
# 2. 基础配置模型 (Base Models) - 终极兼容版
# =============================================================================

class BaseConfig(BaseModel):
    """
    基础配置类 (终极兼容版)。
    既支持 Pydantic 的强类型校验，
    又通过魔术方法完美模拟了 Python 字典的行为，以兼容旧代码。
    """
    class Config:
        # 关键设置：允许运行时添加模型中未定义的字段（解决 runtime_settings 报错）
        extra = 'allow' 
        # 允许通过字段名或别名填充
        populate_by_name = True

    # --- 1. 字典核心迭代方法 (解决 .keys() 报错) ---
    def keys(self):
        """模拟字典的 .keys()，返回所有字段名"""
        return self.model_dump(by_alias=True).keys()

    def values(self):
        """模拟字典的 .values()，返回所有字段值"""
        # 注意：这里我们返回 getattr 的结果，保持对象引用，而不是 dump 后的纯数据
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
             # 为了兼容旧代码，这里抛出 KeyError 是标准行为
             # 但如果您的代码习惯依赖 None 返回，可以改为 return None
             # 鉴于 extra='allow'，未定义字段应该能通过 setattr 添加进来
             raise KeyError(f"'{item}' not found in configuration")
        return val

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __contains__(self, key):
        return hasattr(self, key) or key in self.keys()

    # --- 4. 解决 config.update({...}) ---
    def update(self, other_dict: Dict[str, Any]):
        for k, v in other_dict.items():
            setattr(self, k, v)

    # --- 5. 兜底方案 ---
    def __getattr__(self, item):
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
    
    # [新增] 兼容旧代码的 base_dir 字段
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
    """
    base: TableBaseLayout
    calculations: Optional[LayoutCalculations] = None
    
# --- Section Wrappers ---
class SectionConfig(BaseConfig):
    rendering_params: Optional[Dict[str, Any]] = None
    data_config: Optional[YieldDataConfig] = None
    layout_config: Optional[Dict[str, ElementLayout]] = None
    
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
        if not self.table_layout or not self.table_layout.calculations:
            return self
        
        base_layout = self.table_layout.base
        calculations = self.table_layout.calculations
        
        if calculations.row_heights:
            row_heights, _ = LayoutCalculator.calculate_sizes(**calculations.row_heights.model_dump())
            base_layout.row_heights = row_heights

        if calculations.col_widths:
            cw_calc = calculations.col_widths
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
    model_config = {"extra": "allow"}

class PptEngineConfig(BaseConfig):
    paths: PathsConfig
    settings: AppSettings
    sections: SectionMap
    
    runtime_settings: Optional[Dict[str, Any]] = {}

    @classmethod
    def from_app_config(cls, app_config_dict: Optional[Dict[str, Any]] = None) -> 'PptEngineConfig':
        """
        [双模启动] 支持从全局集成启动，也支持作为独立脚本启动。
        """
        # 1. 模式一：集成模式 (Production Mode)
        # 如果主程序传来了有效的配置字典，直接提取使用
        if app_config_dict and 'ppt_engine' in app_config_dict:
            logging.info("Initializing from Global AppConfig...") # 记录来源
            return cls(**app_config_dict['ppt_engine']) # 标准实例化

        # 2. 模式二：独立/调试模式 (Standalone/Debug Mode)
        # 如果没有传入配置（比如直接运行了子模块脚本），则加载本地测试配置
        logging.warning("No global config found. Switching to Standalone Mode.") # 警告提示
        
        # 定义本地测试配置文件的路径
        local_test_config = Path(__file__).parents[3] / "config" / "ppt_engine_config.yaml" # 定位文件
        
        if local_test_config.exists():
            logging.info(f"Loading local dev config: {local_test_config}") # 记录加载动作
            with open(local_test_config, 'r', encoding='utf-8') as f:
                dev_data = yaml.safe_load(f) # 读取 YAML
            
            # 这里还可以注入一些为了方便调试的特殊参数
            dev_data['runtime_settings'] = {'debug_borders': True} # 开启调试边框
            
            return cls(**dev_data) # 返回测试用的配置对象
        
        # 3. 兜底：如果连测试配置都没找到，只能报错
        raise ValueError("Cannot initialize PptEngine: No global config and no local dev config found.") # 抛出异常

# =============================================================================
# 5. 加载逻辑 (单例与兼容)
# =============================================================================

# 全局单例
CONFIG: Optional[PptEngineConfig] = None

# 旧的加载逻辑保留用于独立测试
CONFIG_YAML_PATH = PROJECT_ROOT / "config" / "ppt_engine_config.yaml"
    
def load_config(yaml_path: Path = CONFIG_YAML_PATH) -> PptEngineConfig:
    global CONFIG
    if CONFIG: return CONFIG

    if not yaml_path.exists():
        # 尝试查找相对路径
        alt_path = Path("config/ppt_engine_config.yaml")
        if alt_path.exists():
            yaml_path = alt_path
        else:
             # 在统一配置模式下，可能不需要这个文件存在，而是从内存加载
             # 但为了兼容旧的独立运行脚本，我们还是报个警
            logging.warning(f"Standalone PPT config not found: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        raw_data = yaml.safe_load(f)

    if 'paths' in raw_data:
        raw_data['paths']['base_dir'] = str(PROJECT_ROOT)

    try:
        CONFIG = PptEngineConfig(**raw_data)
        logging.info(f"PPT Config loaded from file: {yaml_path}")
        return CONFIG
    except Exception as e:
        logging.error(f"PPT Config validation failed: {e}")
        raise

# =============================================================================
# 6. 动态常量导出 (The Magic)
# =============================================================================

# 1. 首先，【删除】原来的那些静态赋值语句！
# LOG_DIR = ... (删除)
# RESOURCES_DIR = ... (删除)
# ... (全部删除)

# 2. 定义映射关系：常量名 -> 如何从 CONFIG 对象中获取
_LAZY_MAPPING = {
    'LOG_DIR': lambda c: c.paths.log_dir,
    'RESOURCES_DIR': lambda c: c.paths.resources_dir,
    'DATA_RAW_DIR': lambda c: c.paths.data_raw_dir,
    'OUTPUT_DIR': lambda c: c.paths.output_dir,
    'MAIN_PY_PATH': lambda c: c.paths.main_py_path,
}

# 3. 定义模块级 __getattr__
def __getattr__(name: str):
    """
    当外部代码尝试 import LOG_DIR 时，如果 LOG_DIR 没定义，
    Python 会自动调用这个函数。
    """
    if name in _LAZY_MAPPING:
        # A. 检查 CONFIG 是否已加载
        global CONFIG
        if CONFIG is None:
            # 关键：如果还没加载，为了避免报错，我们在这里尝试“自动触发”加载
            # 这就是“懒加载”的精髓：用到的时候再加载
            try:
                # 尝试加载 (会触发 load_config 的查找逻辑)
                load_config()
            except Exception as e:
                logging.warning(f"Lazy load failed for {name}: {e}")
                # 如果加载失败，返回一个安全的默认值兜底，防止崩溃
                defaults = {
                    'LOG_DIR': 'logs',
                    'RESOURCES_DIR': 'resources',
                    'DATA_RAW_DIR': 'data/raw',
                    'OUTPUT_DIR': 'output',
                    'MAIN_PY_PATH': 'main.py'
                }
                return Path(defaults.get(name, '.'))

        # B. 从 CONFIG 中提取最新值
        value = _LAZY_MAPPING[name](CONFIG)
        
        # C. 统一转为 Path 对象 (兼容旧逻辑)
        return Path(value)

    # 如果请求的不是这些常量，抛出标准异常
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# =============================================================================
# 7. IDE 智能提示支持 (Type Hinting Stub)
# =============================================================================
# 上面的代码运行完美，但 PyCharm/VSCode 会以为 LOG_DIR 不存在而爆红。
# 下面的代码只在类型检查时运行，不会影响实际逻辑。

if TYPE_CHECKING:
    LOG_DIR: Path
    RESOURCES_DIR: Path
    DATA_RAW_DIR: Path
    OUTPUT_DIR: Path
    MAIN_PY_PATH: Path
