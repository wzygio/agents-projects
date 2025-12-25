import os
import logging
import yaml
from typing import List, Dict, Optional, Any
from pathlib import Path
from pydantic import BaseModel, Field

# =============================================================================
# 1. 基础配置基类
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

# =============================================================================
# 2. 子模块配置模型 (根据 YAML 结构拆解)
# =============================================================================

# --- Section: common ---
class CommonConfig(BaseConfig):
    log_level: str = "INFO"
    # 兼容 YAML 中的大写 HEADLESS_MODE
    headless_mode: bool = Field(default=True, alias="HEADLESS_MODE")

# --- Section: data ---
class DataFilesConfig(BaseConfig):
    hl_raw: str
    batch_yield: str
    hl_history: str
    ct_yield: str
    mwdl_raw: Optional[str] = None
    defect_group_dict: str

class DataColumnsConfig(BaseConfig):
    prod_code: str
    defect_desc: str
    batch: str

class DataConfig(BaseConfig):
    files: DataFilesConfig
    columns: Optional[DataColumnsConfig] = None

# --- Section: path ---
class PathConfig(BaseConfig):
    input_path: str
    data_cache_path: str
    data_raw_dir: str
    hl_resources_dir: str
    log_dir: str

# --- Section: daily_report (新增核心部分) ---
class LedgerConfig(BaseConfig):
    """
    对应 record_ledger 和 hl_ledger 的通用结构
    """
    path: str
    file_name: str
    sheet_name: str
    mapping: Dict[str, str] # 映射关系 A: "generated_report" 等

class DailyReportConfig(BaseConfig):
    record_ledger: Optional[LedgerConfig] = None
    hl_ledger: Optional[LedgerConfig] = None

# =============================================================================
# 3. 聚合配置类 (AnomalyMonitorConfig)
# =============================================================================

class AnomalyMonitorConfig(BaseConfig):
    """
    Anomaly Monitor 模块的主配置类
    """
    common: CommonConfig
    data: DataConfig
    paths: PathConfig
    daily_report: Optional[DailyReportConfig] = None # [新增] 关联 daily_report

    @classmethod
    def from_app_config(cls, app_config_dict: Optional[Dict[str, Any]] = None) -> 'AnomalyMonitorConfig':
        """
        [双模启动工厂]
        1. 集成模式：从全局 AppConfig 字典中提取 'anomaly_monitor' 部分。
        2. 独立模式：如果全局上下文缺失，加载本地 YAML。
        """
        # --- 模式一：集成模式 (Global Injection) ---
        if app_config_dict and 'anomaly_monitor' in app_config_dict:
            logging.info("[AnomalyMonitor] Initializing from Global AppConfig context...")
            monitor_data = app_config_dict['anomaly_monitor']
            return cls(**monitor_data)

        # --- 模式二：独立/调试模式 (Standalone Mode) ---
        logging.warning("[AnomalyMonitor] No global config context. Switching to Standalone Mode.")
        
        # 路径定位：packages/anomaly_monitor/src/config.py -> parents[2]
        try:
            package_root = Path(__file__).resolve().parents[2]
            local_config_path = package_root / "config" / "anomaly_monitor.yaml"
        except (NameError, IndexError):
            local_config_path = Path("config/anomaly_monitor.yaml")

        if local_config_path.exists():
            logging.info(f"[AnomalyMonitor] Loading local config from: {local_config_path}")
            with open(local_config_path, 'r', encoding='utf-8') as f:
                local_data = yaml.safe_load(f)
            return cls(**local_data)
        
        # --- 错误处理 ---
        raise ValueError(f"Cannot initialize AnomalyMonitorConfig: Global context missing and local file not found at {local_config_path}")

# =============================================================================
# 4. 全局单例 (CONFIG)
# =============================================================================

CONFIG: Optional[AnomalyMonitorConfig] = None 

def load_config() -> AnomalyMonitorConfig:
    """
    独立运行时的加载入口 (Fallback)
    """
    global CONFIG
    if CONFIG: return CONFIG
    
    try:
        # 尝试触发独立模式加载
        CONFIG = AnomalyMonitorConfig.from_app_config(None)
        return CONFIG
    except Exception as e:
        logging.error(f"AnomalyMonitor standalone load failed: {e}")
        raise