import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from pathlib import Path

# --- 1. 定义基类：包含您的“方案一”魔法 ---
class BaseConfig(BaseModel):
    """
    所有配置类的基类。
    包含 __getattr__ 用于处理未定义的字段，防止编辑器爆红，
    同时允许代码在读取 YAML 中新增的临时字段时不报错。
    """

    def __getattr__(self, item) -> Any:
        # 这里可以选择返回 None，或者打印一个警告，或者直接 pass
        # 这样写之后，访问 config.path.undefined_field 不会报红线，只会返回 None
        return None

# --- 2. 定义各个子模块的配置模型 ---

class CommonConfig(BaseConfig):
    """
    通用配置类，继承自BaseConfig，包含常用的配置项
    """
    log_level: str = 'INFO'
    HEADLESS_MODE: bool = True

class DataFilesConfig(BaseConfig):
    """
    DataFilesConfig 类用于配置数据文件路径和相关设置
    继承自 BaseConfig 基类，用于定义数据文件的基本配置项
    """
    hl_raw: str  # 原始高层数据文件路径
    batch_yield: str  # 批量产量数据文件路径
    hl_history: str  # 高层历史数据文件路径
    ct_yield: str  # CT产量数据文件路径
    mwdl_raw: str = ''  # 给个默认值，因为 YAML 注释说可选

    # 原始MWDL数据文件路径，设为空字符串作为默认值，表示该配置项为可选
    defect_group_dict: str  # 缺陷分组字典文件路径

class DataColumnsConfig(BaseConfig):
    prod_code: str = 'prod_code'
    defect_desc: str = 'defect_desc'
    batch: str = 'batch'

class DataConfig(BaseConfig):
    files: DataFilesConfig
    columns: DataColumnsConfig

class PathConfig(BaseConfig):
    input_path: str
    data_cache_path: str
    data_raw_dir: str
    # 重点：这里显式声明了 hl_resources_dir，VS Code 绝对不会再报错了！
    hl_resources_dir: str 
    log_dir: str

class BrowserConfig(BaseConfig):
    headless: bool = False
    timeout: int = 30000
    slow_mo: int = 50

# --- 日报模块的复杂结构 ---

class LedgerMapping(BaseConfig):
    # 使用 Dict[str, str] 来接收 A: "generated_report" 这种映射
    # 或者如果不确定 key，也可以用 extra='allow'
    # 这里我们定义通用映射，如果字段不固定，Pydantic 默认允许额外字段
    pass 

class LedgerConfig(BaseConfig):
    path: str
    file_name: str
    sheet_name: str
    mapping: Dict[str, str] # 对应 YAML 中的 A: value, B: value...

class ReportItem(BaseConfig):
    name: str
    path: Optional[str] = None # 有些报表可能暂时没配路径

class DailyReportInputs(BaseConfig):
    product_models: List[str]
    reports: List[ReportItem]

class DailyReportConfig(BaseConfig):
    portal_url: str
    record_ledger: LedgerConfig
    hl_ledger: LedgerConfig
    inputs: DailyReportInputs

# --- 3. 最终的全局配置类 ---

class AppConfig(BaseConfig):
    common: CommonConfig
    data: DataConfig
    path: PathConfig
    browser: BrowserConfig
    daily_report: DailyReportConfig

# ==========================================================
# 加载逻辑 (单例模式)
# ==========================================================
import yaml

_config_instance: Optional[AppConfig] = None

def load_config(yaml_path: str = "config.yaml") -> AppConfig:
    """读取 YAML 并转换为强类型的 AppConfig 对象"""
    global _config_instance
    
    if _config_instance:
        return _config_instance

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"配置文件未找到: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        raw_data = yaml.safe_load(f)

    # Pydantic 会自动验证类型并填充数据
    _config_instance = AppConfig(**raw_data)
    return _config_instance

# 为了方便在其他文件直接导入使用
# 使用方法： from config import config
# 注意：这需要确保 config.yaml 在工作目录下，或者在 main 中先调用 load_config
# 这里为了不报错，先设为 None，由您在主程序入口初始化
config: AppConfig = None # type: ignore

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
except NameError:
    PROJECT_ROOT = Path.cwd()
