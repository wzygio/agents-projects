# 文件路径: src/config.py
import yaml
import os
import logging
from pathlib import Path
from dotenv import load_dotenv  # [新增] 导入 dotenv 库

# --- 1. 路径与环境设置 ---
try:
    SRC_ROOT = Path(__file__).resolve().parent
    PROJECT_ROOT = SRC_ROOT.parent
except NameError:
    PROJECT_ROOT = Path.cwd()
    logging.warning(f"无法确定 __file__ 路径，假定项目根目录为: {PROJECT_ROOT}")

# [新增] 加载 .env 文件到环境变量中
# override=True 表示如果 .env 中的变量与系统变量冲突，以 .env 为准
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    logging.warning(f"未找到 .env 文件: {env_path}，将仅使用系统环境变量")

class ConfigLoader:
    # ... (这部分单例模式和 __init__ 代码保持不变) ...
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file="config.yaml"):
        if hasattr(self, 'config'):
            return
        self.config_path = PROJECT_ROOT / "config" / config_file
        self._config_data = self._load_config()
        self._screen_size = None

    def _load_config(self):
        # ... (这部分加载 YAML 的代码保持不变) ...
        target_path = self.config_path
        if not target_path.exists() and Path("config/config.yaml").exists():
            target_path = Path("config/config.yaml")
        if not target_path.exists():
            logging.error(f"配置文件未找到: {target_path}")
            return {}
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"YAML解析失败: {e}")

    def get(self, key_path, default=None):
        keys = key_path.split(".")
        value = self._config_data
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    # =======================================================
    #  Core Properties (核心属性访问器)
    # =======================================================

    @property
    def download_path(self):
        return self.get("path.download_dir")
    
    @property
    def log_level(self):
        return self.get("common.log_level", "INFO")

    @property
    def headless(self):
        return self.get("browser.headless", False)
    
    @property
    def timeout(self):
        return self.get("browser.timeout", 30000)

    @property
    def slow_mo(self):
        return self.get("browser.slow_mo", 50)

    @property
    def portal_url(self):
        return self.get("daily_report.portal_url")

    # --- [修改] 账号密码：改为从环境变量读取 ---
    @property
    def username(self):
        """获取登录账号 (优先从环境变量读取)"""
        # os.getenv 的第二个参数是默认值
        # 这里逻辑是：先读环境变量，读不到再尝试读 YAML (作为后备)，再没有就返回 None
        return os.getenv("MES_USERNAME")
    
    @property
    def password(self):
        """获取登录密码 (优先从环境变量读取)"""
        return os.getenv("MES_PASSWORD")

    # ... (Report Names, Models 等其他属性保持不变) ...
    @property
    def report_names(self):
        return self.get("daily_report.inputs.report_names", [])

    @property
    def reports(self):
        """
        获取报表配置列表，返回格式为:
        [{'name': '报表A', 'path': '路径A'}, {'name': '报表B'}]
        """
        items = self.get("daily_report.inputs.reports", [])
        
        # 兼容旧代码：如果 YAML 里还是写的纯字符串列表，这里自动转成字典，防止报错
        cleaned_items = []
        for item in items:
            if isinstance(item, str):
                cleaned_items.append({"name": item, "path": None})
            else:
                cleaned_items.append(item)
        return cleaned_items
    
    @property
    def product_models(self):
        return self.get("daily_report.inputs.product_models", [])
    
    @property
    def screen_size(self):
        if self._screen_size is None:
            try:
                import pyautogui
                self._screen_size = pyautogui.size()
            except ImportError:
                self._screen_size = (1920, 1080)
        return self._screen_size

# 全局单例
config = ConfigLoader()