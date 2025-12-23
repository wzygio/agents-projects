import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel

# 导入各模块的配置定义 (各模块自己维护自己的 Config 类)
from packages.web_automation.src.config import WebAutomationConfig
from packages.ppt_engine.src.config import PptEngineConfig
# from packages.excel_engine.src.config import ExcelEngineConfig # (稍后定义)

# =============================================================================
# 1. 基础配置模型
# =============================================================================
class BaseConfig(BaseModel):
    class Config:
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

# =============================================================================
# 2. 根配置模型 (AppConfig)
# =============================================================================
class AppConfig(BaseConfig):
    """
    全局配置聚合根。
    它将包含所有子模块的配置对象。
    """
    common: CommonConfig
    path: PathConfig
    
    # 子模块配置 (通过 includes 动态加载后注入)
    web_automation: Optional[WebAutomationConfig] = None
    ppt_engine: Optional[PptEngineConfig] = None
    # excel_engine: Optional[ExcelEngineConfig] = None # (稍后开启)

# =============================================================================
# 3. 智能加载器 (The "Glue" Logic)
# =============================================================================
_config_instance: Optional[AppConfig] = None

# 自动定位项目根目录
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1] # 假设在 src/config.py
except NameError:
    PROJECT_ROOT = Path.cwd()

def _merge_config_files(root_config_path: Path) -> Dict[str, Any]:
    """
    [核心逻辑] 读取根配置，并递归读取 includes 中的子文件，合并为一个大字典
    """
    if not root_config_path.exists():
        raise FileNotFoundError(f"Root config not found: {root_config_path}")

    # 1. 读取根配置
    with open(root_config_path, 'r', encoding='utf-8') as f:
        main_data = yaml.safe_load(f) or {}

    # 2. 处理子文件引用
    includes = main_data.pop('includes', {})
    
    for module_key, file_rel_path in includes.items():
        # 解析子文件绝对路径
        sub_file_path = PROJECT_ROOT / file_rel_path
        
        if sub_file_path.exists():
            logging.info(f"Loading sub-config [{module_key}] from: {file_rel_path}")
            with open(sub_file_path, 'r', encoding='utf-8') as f:
                sub_data = yaml.safe_load(f) or {}
                
            # 3. 将子文件内容挂载到主字典的对应 key 下
            # 例如：把 ppt_engine.yaml 的内容塞进 main_data['ppt_engine']
            main_data[module_key] = sub_data
        else:
            logging.warning(f"Sub-config file missing: {sub_file_path}")
            # 可以选择报错，或者给个空字典
            main_data[module_key] = {}

    return main_data

def load_config(yaml_path: str = "config/config.yaml") -> AppConfig:
    global _config_instance
    if _config_instance:
        return _config_instance

    full_path = PROJECT_ROOT / yaml_path
    
    # 执行合并加载
    raw_data = _merge_config_files(full_path)
    
    # 转换为 Pydantic 对象
    _config_instance = AppConfig(**raw_data)
    logging.info("Global configuration loaded successfully.")
    return _config_instance

# 导出单例
config = load_config()