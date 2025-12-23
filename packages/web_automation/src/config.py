from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# =============================================================================
# 1. 基础配置基类 (复用您的方案一魔法)
# =============================================================================

class BaseConfig(BaseModel):
    """
    基础配置类。
    包含 __getattr__ 用于处理未定义的字段，防止编辑器爆红，
    同时允许代码在读取 YAML 中新增的临时字段时不报错。
    """
    class Config:
        extra = 'ignore' # 忽略多余字段，只取包需要的

    def __getattr__(self, item) -> Any:
        return None

# =============================================================================
# 2. Web Automation 专属配置模型
#    (严格对齐您的 YAML 结构中 browser 和 daily_report 部分)
# =============================================================================

# --- 对应 config.yaml 中的 browser 部分 ---
class BrowserConfig(BaseConfig):
    headless: bool = False
    timeout: int = 30000
    slow_mo: int = 50
    # 允许额外参数 (如 Viewport)
    viewport_width: int = 1920
    viewport_height: int = 1080

# --- 对应 config.yaml 中的 daily_report.inputs.reports ---
class ReportItem(BaseConfig):
    name: str
    path: Optional[str] = None

# --- 对应 config.yaml 中的 daily_report ---
class PortalConfig(BaseConfig):
    portal_url: str
    
    # 您的 YAML 结构里 inputs 在 daily_report 下面
    inputs: Optional[Dict[str, Any]] = None 
    
    # 动态注入的字段 (config.yaml 本身没写 username/password，通常是运行时的 secrets)
    username: Optional[str] = None
    password: Optional[str] = None

# =============================================================================
# 3. 聚合配置类 (WebAutomationConfig)
# =============================================================================

class WebAutomationConfig(BaseConfig):
    """
    这是 WebAutomation 包内部使用的总配置类。
    它只提取它关心的两部分：browser 和 daily_report (portal)。
    """
    browser: BrowserConfig
    portal: PortalConfig
    
    # 下载目录 (通常在 path 配置里，这里我们允许独立传入)
    download_dir: str = "downloads"

    @classmethod
    def from_app_config(cls, app_config_dict: Dict[str, Any]) -> 'WebAutomationConfig':
        """
        工厂方法：从全局 AppConfig 字典中提取所需信息并构建对象。
        """
        # 1. 提取 browser 配置
        browser_data = app_config_dict.get('browser', {})
        
        # 2. 提取 daily_report 配置 (映射为 portal)
        daily_report_data = app_config_dict.get('daily_report', {})
        
        # 3. 提取路径配置 (如果有的话)
        path_data = app_config_dict.get('path', {})
        download_dir = path_data.get('input_path', 'downloads') # 暂时用 input_path 或默认值
        
        return cls(
            browser=BrowserConfig(**browser_data),
            portal=PortalConfig(**daily_report_data),
            download_dir=download_dir
        )