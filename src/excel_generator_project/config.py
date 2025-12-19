# 文件路径：src\excel_generator_project\config.py
import yaml
from pathlib import Path
import sys, os, logging
from typing import Dict, Any

# --- 1. 基础设置与加载 ---
# 添加项目根目录到系统路径，以便导入模块
try:
    SRC_ROOT = Path(__file__).resolve().parent.parent
    PROJECT_ROOT = SRC_ROOT.parent
except NameError:
    PROJECT_ROOT = Path.cwd()
    SRC_ROOT = PROJECT_ROOT / "src"
    logging.warning(f"__file__ 未定义，假定项目根目录为: {PROJECT_ROOT}")

CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"
CONFIG: Dict[str, Any] = {}

def load_config(
    config_path: Path = CONFIG_FILE,
    ) -> Dict[str, Any]:
    """
    加载、处理并返回完整的配置字典。
    这是一个纯粹的工具函数，不产生任何全局副作用。
    """
    loaded_config = {} # 初始化为空字典

    # 1. 加载 YAML 文件 (如果存在)
    try:
        if config_path.is_file():
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if isinstance(yaml_config, dict):
                     loaded_config.update(yaml_config) # 合并 YAML 配置
                logging.info(f"YAML 配置文件已成功加载: {config_path}")
        else:
            logging.warning(f"YAML 配置文件未找到: {config_path}")
    except Exception as e:
        logging.error(f"加载或解析 YAML 文件 {config_path} 时出错: {e}")

    yaml_config['paths']['base_dir'] = str(PROJECT_ROOT)

    return yaml_config

CONFIG = load_config()

# --- 2. 导出配置常量 ---
PATHS = CONFIG.get("paths", {})
RESOURCES_DIR = PROJECT_ROOT / Path(PATHS.get("resources_dir", ""))
TEMP_DIR = PROJECT_ROOT / Path(PATHS.get("temp_dir", ""))
LOG_DIR = PROJECT_ROOT / Path(PATHS.get("log_dir", ""))
OUTPUT_DIR = PROJECT_ROOT / Path(PATHS.get("output_dir", ""))
TEMPLATE_PATH = RESOURCES_DIR / Path(PATHS.get("template_file", ""))
TEMP_PATH = OUTPUT_DIR / Path(PATHS.get("temp_file", ""))
OUTPUT_PATH = OUTPUT_DIR / Path(PATHS.get("output_file", ""))

DOWNLOADER_SCRIPT_PATH = Path(PATHS.get("downloader_script_path", ""))
DOWNLOADER_PYTHON_EXECUTABLE = Path(PATHS.get("downloader_python_executable", ""))

CONTENT_GENERATOR_SCRIPT_PATH = Path(PATHS.get("content_generator_script_path", ""))
STYLE_GENERATOR_SCRIPT_PATH = Path(PATHS.get("style_generator_script_path", ""))