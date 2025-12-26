import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel

# 导入各模块的配置定义 (各模块自己维护自己的 Config 类)
from packages.anomaly_monitor.src import config as anomaly_monitor_config_module
from packages.web_automation.src import config as web_config_module
from packages.excel_engine.src import config as excel_config_module
from packages.ppt_engine.src import config as ppt_config_module


# 为了 Pydantic 定义，我们需要具体的类
from packages.anomaly_monitor.src.config import AnomalyMonitorConfig
from packages.web_automation.src.config import WebAutomationConfig
from packages.excel_engine.src.config import ExcelEngineConfig
from packages.ppt_engine.src.config import PptEngineConfig

# =============================================================================
# 1. 基础配置模型
# =============================================================================
class BaseConfig(BaseModel):
    class Config:
        # 对于全局配置，通常忽略未知的顶层字段，保持整洁
        extra = "ignore"

class CommonConfig(BaseConfig):
    project_name: str
    log_level: str
    headless_mode: bool

class PathConfig(BaseConfig):
    base_dir: str
    input: str
    output: str
    logs: str
    resources: str
    cache: str
    logs_dir: str

# =============================================================================
# 2. 根配置模型 (AppConfig)
# =============================================================================
class AppConfig(BaseConfig):
    """
    全局配置聚合根。
    它将包含所有子模块的配置对象。
    """
    common: CommonConfig
    paths: PathConfig
    
    # 子模块配置 (通过 includes 动态加载后注入)
    anomaly_monitor: Optional[AnomalyMonitorConfig] = None
    web_automation: Optional[WebAutomationConfig] = None
    excel_engine: Optional[ExcelEngineConfig] = None
    ppt_engine: Optional[PptEngineConfig] = None

# =============================================================================
# 3. 智能加载器 (The "Glue" Logic)
# =============================================================================
_config_instance: Optional[AppConfig] = None

# 自动定位项目根目录
try:
    # src/config.py -> parent is src -> parent is project_root
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path.cwd()

def _merge_config_files(root_config_path: Path) -> Dict[str, Any]:
    """
    [核心逻辑] 读取根配置，并递归读取 includes 中的子文件，合并为一个大字典
    """
    if not root_config_path.exists():
        # 提供更明确的错误提示
        raise FileNotFoundError(f"Root config not found at: {root_config_path}")

    # 1. 读取根配置
    with open(root_config_path, 'r', encoding='utf-8') as f:
        main_data = yaml.safe_load(f) or {}

    # 2. 处理子文件引用
    # 约定：config.yaml 中有一个 keys 叫 'includes'，格式为 {'key_name': 'path/to/sub_config.yaml'}
    includes = main_data.pop('includes', {})
    
    for module_key, file_rel_path in includes.items():
        # 解析子文件绝对路径
        sub_file_path = PROJECT_ROOT / file_rel_path
        
        if sub_file_path.exists():
            logging.info(f"Loading sub-config [{module_key}] from: {file_rel_path}")
            with open(sub_file_path, 'r', encoding='utf-8') as f:
                sub_data = yaml.safe_load(f) or {}
            
            # 3. 将子文件内容挂载到主字典的对应 key 下
            # 这样 Pydantic 初始化 AppConfig 时，能自动识别到 ppt_engine 字段
            main_data[module_key] = sub_data
        else:
            logging.warning(f"Sub-config file missing: {sub_file_path}. Module [{module_key}] may not work.")
            # 保持为 None 或空字典取决于子模块是否允许 Optional
            main_data[module_key] = None

    return main_data

def load_config(yaml_path: str = "config/config.yaml") -> AppConfig:
    """
    加载并构建 AppConfig 对象。
    不再执行任何全局变量注入操作。
    """
    global _config_instance
    if _config_instance:
        return _config_instance

    full_path = PROJECT_ROOT / yaml_path
    
    try:
        # 1. 获取合并后的字典
        raw_data = _merge_config_files(full_path)
        
        # 2. 使用工厂方法实例化子模块配置
        # 这让子模块有机会从 raw_data 中读取全局字段(如 paths)
        
        if 'ppt_engine' in raw_data:
            raw_data['ppt_engine'] = PptEngineConfig.from_app_config(raw_data)
        
        if 'web_automation' in raw_data:
            raw_data['web_automation'] = WebAutomationConfig.from_app_config(raw_data)
            
        if 'excel_engine' in raw_data:
            raw_data['excel_engine'] = ExcelEngineConfig.from_app_config(raw_data)

        if 'anomaly_monitor' in raw_data:
             raw_data['anomaly_monitor'] = AnomalyMonitorConfig.from_app_config(raw_data)

        # 3. 创建对象
        _config_instance = AppConfig(**raw_data)
        
        logging.info("Global configuration loaded successfully (Dependency Injection Ready).")
        return _config_instance
        
    except Exception as e:
        logging.critical(f"Failed to load global configuration: {e}", exc_info=True)
        raise
