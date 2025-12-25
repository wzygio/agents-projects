from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field

def get_project_root() -> Path:
    """Returns project root folder."""
    return Path(__file__).resolve().parents[3]

PROJECT_ROOT = get_project_root()

# =============================================================================
# 1. 基础配置基类 (复用您的方案一魔法)
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

# --- 对应 config.yaml 中的 daily_report ---
class DailyReportConfig(BaseConfig):
    """
    对应 YAML 中的 'daily_report' 根节点
    """
    portal_url: str

    product_models: List[str] = []
    reports: List[ReportItem] = []

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
