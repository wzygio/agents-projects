import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel

# 导入各模块的配置定义 (各模块自己维护自己的 Config 类)
# 注意：这里导入不仅仅是为了类型定义，也是为了后续注入单例
from packages.web_automation.src import config as web_config_module
from packages.ppt_engine.src import config as ppt_config_module
from packages.excel_engine.src import config as excel_config_module


# 为了 Pydantic 定义，我们需要具体的类
from packages.web_automation.src.config import WebAutomationConfig
from packages.ppt_engine.src.config import PptEngineConfig
from packages.excel_engine.src.config import ExcelEngineConfig

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
    excel_engine: Optional[ExcelEngineConfig] = None

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

def _sync_submodules(app_config: AppConfig):
    """
    [关键修复] 将加载好的配置实例，反向注入到各子模块的全局变量中。
    确保子模块内部代码 (如 import config) 能获取到由全局统一加载的配置。
    """
    # 1. Sync PPT Engine
    if app_config.ppt_engine:
        # 直接赋值给子模块的全局变量 CONFIG
        ppt_config_module.CONFIG = app_config.ppt_engine
        logging.info("Synced PptEngineConfig to packages.ppt_engine.src.config.CONFIG")

    # 2. Sync Web Automation
    if app_config.web_automation:
        # 假设 Web 模块也有类似的 CONFIG 变量
        web_config_module.CONFIG = app_config.web_automation
        logging.info("Synced WebAutomationConfig to packages.web_automation.src.config.CONFIG")
        pass

    # 3. Sync Excel Engine
    if app_config.excel_engine:
        excel_config_module.CONFIG = app_config.excel_engine
        logging.info("Synced ExcelEngineConfig to packages.excel_engine.src.config.CONFIG")
        pass

def load_config(yaml_path: str = "config/config.yaml") -> AppConfig:
    global _config_instance
    if _config_instance:
        return _config_instance

    full_path = PROJECT_ROOT / yaml_path
    
    try:
        # 1. 获取原始的大字典 (Raw Dictionary)
        # 此时 raw_data 包含了 common, path, ppt_engine(字典形式) 等所有数据
        raw_data = _merge_config_files(full_path)
        
        # =========================================================================
        # [关键步骤] 激活工厂方法 (Activate Factory Methods)
        # =========================================================================
        
        # 我们不让 AppConfig 自动转换 ppt_engine，而是手动调用工厂
        # 目的：为了让 from_app_config 有机会读取 raw_data 中的全局字段 (如 paths, common)
        
        if 'ppt_engine' in raw_data:
            logging.info("Initializing PPT Engine via Factory Method...")
            # 调用工厂方法，把整个 raw_data 传进去，而不只是 ppt_engine 那一部分
            ppt_instance = PptEngineConfig.from_app_config(raw_data)
            
            # [核心] 用实例化后的对象，替换掉字典里的原始数据
            # Pydantic 非常智能：如果在初始化时字段已经是对象了，它就会直接使用，不再重新校验
            raw_data['ppt_engine'] = ppt_instance

        # 同样的处理也可以用于其他模块
        if 'web_automation' in raw_data:
             web_instance = WebAutomationConfig.from_app_config(raw_data)
             raw_data['web_automation'] = web_instance
             pass
        
        if 'excel_engine' in raw_data:
             excel_instance = ExcelEngineConfig.from_app_config(raw_data)
             raw_data['excel_engine'] = excel_instance
             pass

        # =========================================================================
        # 2. 创建全局配置对象
        # =========================================================================
        
        # 此时传入的 raw_data 中，'ppt_engine' 已经是一个清洗好的 PptEngineConfig 对象了
        _config_instance = AppConfig(**raw_data)
        
        # 3. 同步单例到子模块 (保留之前的逻辑)
        _sync_submodules(_config_instance)
        
        logging.info("Global configuration loaded and synced successfully.")
        return _config_instance
        
    except Exception as e:
        logging.critical(f"Failed to load global configuration: {e}", exc_info=True)
        raise

# 导出单例 (注意：直接执行可能会在没有日志配置时就运行，建议在 main 中显式调用 load_config)
# 为了方便 import，这里保留自动加载，但建议由 entry point 控制初始化时机
try:
    config = load_config()
except Exception:
    # 允许在某些测试环境下导入时不报错，但 config 会是 None
    config = None