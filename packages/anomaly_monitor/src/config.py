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
    基础配置类。
    配置 extra='ignore' 以便在集成模式下忽略全局配置中不相关的字段。
    """
    class Config:
        extra = 'ignore'
        populate_by_name = True # 允许通过字段名或 alias 填充

    def __getattr__(self, item) -> Any:
        return None

# =============================================================================
# 2. Anomaly Monitor 专属配置模型
# =============================================================================

# --- 对应 anomaly_monitor.yaml -> common ---
class CommonConfig(BaseConfig):
    log_level: str = "INFO"
    # 使用 alias 兼容 YAML 中的大写命名，同时保持 Python 代码小写风格
    headless_mode: bool = Field(default=True, alias="HEADLESS_MODE")

# --- 对应 anomaly_monitor.yaml -> data.files ---
class DataFilesConfig(BaseConfig):
    hl_raw: str
    batch_yield: str
    hl_history: str
    ct_yield: str
    mwdl_raw: Optional[str] = None
    defect_group_dict: str

# --- 对应 anomaly_monitor.yaml -> data.columns ---
class DataColumnsConfig(BaseConfig):
    prod_code: str
    defect_desc: str
    batch: str

# --- 对应 anomaly_monitor.yaml -> data ---
class DataConfig(BaseConfig):
    files: DataFilesConfig
    columns: Optional[DataColumnsConfig] = None

# --- 对应 anomaly_monitor.yaml -> path ---
class PathConfig(BaseConfig):
    input_path: str
    data_cache_path: str
    data_raw_dir: str
    hl_resources_dir: str
    log_dir: str

# =============================================================================
# 3. 聚合配置类 (AnomalyMonitorConfig)
# =============================================================================

class AnomalyMonitorConfig(BaseConfig):
    """
    Anomaly Monitor 模块的主配置类
    """
    common: CommonConfig
    data: DataConfig
    path: PathConfig

    @classmethod
    def from_app_config(cls, app_config_dict: Optional[Dict[str, Any]] = None) -> 'AnomalyMonitorConfig':
        """
        [双模启动工厂]
        1. 集成模式：从全局 AppConfig 字典中提取 'anomaly_monitor' 部分。
        2. 独立模式：如果全局上下文缺失，加载本地 YAML。
        """
        # --- 模式一：集成模式 (Global Injection) ---
        # 假设全局 config.yaml 中通过 includes 加载了本模块配置，并挂载在 'anomaly_monitor' key 下
        if app_config_dict and 'anomaly_monitor' in app_config_dict:
            logging.info("[AnomalyMonitor] Initializing from Global AppConfig context...")
            monitor_data = app_config_dict['anomaly_monitor']
            
            # [Context Injection] 可选：如果模块配置中缺失通用路径，可从全局 path 注入
            # 但由于您的 yaml 自身包含了完整的 path 定义，这里直接使用模块内的配置即可
            
            return cls(**monitor_data)

        # --- 模式二：独立/调试模式 (Standalone Mode) ---
        logging.warning("[AnomalyMonitor] No global config context. Switching to Standalone Mode.")
        
        # 路径定位：packages/anomaly_monitor/src/config.py -> parents[2] = packages/anomaly_monitor
        # 假设配置文件位于 packages/anomaly_monitor/config/anomaly_monitor.yaml
        try:
            package_root = Path(__file__).resolve().parents[2]
            local_config_path = package_root / "config" / "anomaly_monitor.yaml"
        except (NameError, IndexError):
            # 兜底：假设在当前运行目录下
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

# 自动定位项目根目录 (辅助)
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
except (NameError, IndexError):
    PROJECT_ROOT = Path.cwd()

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

# 默认不自动执行，等待 orchestrator 或 main 调用
# CONFIG = load_config()