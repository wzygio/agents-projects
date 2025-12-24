from typing import List, Optional, Dict, Any, Union
from pathlib import Path
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
        populate_by_name = True

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

# --- 对应 config.yaml 中的 daily_report.hl_ledger / record_ledger ---
class LedgerConfig(BaseConfig):
    path: str
    file_name: str
    sheet_name: str
    mapping: Dict[str, str]

# --- 对应 config.yaml 中的 daily_report.inputs.reports ---
class ReportItem(BaseConfig):
    name: str
    path: str

# --- 对应 config.yaml 中的 daily_report.inputs ---
class DailyReportInputs(BaseConfig):
    product_models: List[str] = []
    reports: List[ReportItem] = []

# --- 对应 config.yaml 中的 daily_report ---
class DailyReportConfig(BaseConfig):
    """
    对应 YAML 中的 'daily_report' 根节点
    """
    portal_url: str
    
    # 嵌套配置
    record_ledger: Optional[LedgerConfig] = None
    hl_ledger: Optional[LedgerConfig] = None
    inputs: Optional[DailyReportInputs] = None
    
    # 动态注入的字段 (config.yaml 本身没写 username/password，通常是运行时的 secrets)
    username: Optional[str] = None
    password: Optional[str] = None

# =============================================================================
# 3. 聚合配置类 (WebAutomationConfig)
# =============================================================================

class WebAutomationConfig(BaseConfig):
    """
    这是 WebAutomation 包内部使用的总配置类。
    它只提取它关心的两部分：browser 和 daily_report。
    """
    browser: BrowserConfig
    daily_report: DailyReportConfig
    
    # 下载目录 (通常在 path 配置里，这里我们允许独立传入)
    download_dir: str = "downloads"

    @classmethod
    def from_app_config(cls, app_config_dict: Dict[str, Any]) -> 'WebAutomationConfig':
        """
        工厂方法：从全局 AppConfig 字典中提取所需信息并构建对象。
        """
        # 1. 提取 browser 配置
        browser_data = app_config_dict.get('browser', {})
        
        # 2. 提取 daily_report 配置
        daily_report_data = app_config_dict.get('daily_report', {})
        
        # 3. 提取路径配置 (如果有的话)
        # 注意：这里需要兼容 YAML 中 'path.input_path' 的命名
        path_data = app_config_dict.get('path', {})
        
        # 优先取 input_path，如果没有取 input，再没有取默认值
        input_dir = path_data.get('input_path') or path_data.get('input', 'downloads')
        
        return cls(
            browser=BrowserConfig(**browser_data),
            daily_report=DailyReportConfig(**daily_report_data),
            download_dir=str(input_dir)
        )

# =============================================================================
# 4. 全局单例 (CONFIG)
# =============================================================================

CONFIG: Optional[WebAutomationConfig] = None 

# 自动定位项目根目录 (用于脚本内部引用)
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
except (NameError, IndexError):
    PROJECT_ROOT = Path.cwd()

def load_config() -> WebAutomationConfig | None:
    """
    独立运行时的加载逻辑 (Fallback)
    """
    global CONFIG
    if CONFIG: return CONFIG
    
    # 这里为了简单，假设总是由主程序注入。
    # 如果您需要独立运行 web_automation 的脚本，可以在这里加类似 PPT/Excel 的 yaml 加载逻辑
    # 目前仅做占位
    return CONFIG
