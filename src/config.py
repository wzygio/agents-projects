import yaml
import sys, os, logging
import pyautogui
from pathlib import Path

# --- 1. 基础设置与加载 ---
# 添加项目根目录到系统路径，以便导入模块
try:
    SRC_ROOT = Path(__file__).resolve().parent
    PROJECT_ROOT = SRC_ROOT.parent
except NameError:
    PROJECT_ROOT = Path.cwd()
    SRC_ROOT = PROJECT_ROOT / "src"
    logging.warning(f"__file__ 未定义，假定项目根目录为: {PROJECT_ROOT}")

# --- 将 SRC_ROOT 添加到 sys.path (保持不变) ---
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
    logging.debug(f"将 SRC_ROOT 添加到 sys.path: {SRC_ROOT}")

CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"
if not CONFIG_FILE.exists():
    logging.error(f"配置文件不存在: {CONFIG_FILE}")
else:
    logging.info(f"加载配置文件: {CONFIG_FILE}")

class ConfigLoader:
    def __init__(self, config_path="config/config.yaml"):
        """
        初始化配置加载器，加载并解析配置文件。
        
        :param config_path: 配置文件路径
        """
        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件未找到：{config_path}")
        
        try:
            # 尝试打开并读取配置文件
            with open(config_path, "r", encoding="utf-8") as f:
                # 使用yaml.safe_load解析配置文件内容
                self.config = yaml.safe_load(f)
        except Exception as e:
            # 如果解析过程中出现异常，抛出ValueError
            raise ValueError(f"配置文件解析失败：{e}")
        
        # 加载屏幕尺寸
        self.screen_width, self.screen_height = pyautogui.size()
        
        # 加载图片路径
        self.search_icon_image = self.get("image_paths.search_icon")
        self.search_box_image = self.get("image_paths.search_box")
        self.report_images = self.get("image_paths.report_images", [])
        self.product_model_box_image = self.get("image_paths.product_model_box")
        self.product_model_box_image_2 = self.get("image_paths.product_model_box_2")
        self.cancel_icon_image = self.get("image_paths.cancel_icon")

        # 加载输入文本
        self.file_name_text = (self.get("input_texts.file_name_text") or "").split()
        self.product_model_text = (self.get("input_texts.product_model_text") or "").split()

        # 加载区域
        self.region_left = (0, 0, int(self.screen_width/3), self.screen_height)
        self.region_top = (0, 0, self.screen_width, int(self.screen_height/3))
        self.region_top_left = (0, 0, int(self.screen_width/3), int(self.screen_height/3))
    
    def get(self, key, default=None):
        """
        获取配置参数。
        
        :param key: 参数键名（支持点号分隔的嵌套键，例如 "image_paths.product_model_box"）
        :param default: 默认值（如果键不存在时返回）
        :return: 参数值
        """
        # 将键按点号分割成多个部分，支持嵌套键访问
        keys = key.split(".")
        value = self.config
        
        # 遍历键的各个部分，逐层获取值
        for k in keys:
            # 检查当前值是否为字典且包含当前键
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # 如果键不存在，返回默认值
                return default
        
        # 返回找到的值
        return value    
    
    def __getattr__(self, key):
        """
        支持通过属性访问配置参数。
        
        :param key: 参数键名
        :return: 参数值
        """
        # 检查键是否存在于配置中
        if key in self.config:
            return self.config[key]
        # 如果键不存在，抛出AttributeError
        raise AttributeError(f"配置中未找到参数：{key}")

# 全局配置对象
config = ConfigLoader()
