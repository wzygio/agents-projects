# 文件路径：packages/excel_engine/src/config.py
import yaml
from pathlib import Path
import logging
from typing import Dict, Any

# --- 1. 路径定义 (基于当前文件位置) ---
# 当前文件在: packages/excel_engine/src/config.py
# 所以 .parent 是 src, .parent.parent 是 excel_engine (包根目录)
SRC_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = SRC_ROOT.parent 
# 假设 workspace 结构：workspace_root/packages/excel_engine
WORKSPACE_ROOT = PACKAGE_ROOT.parent.parent 

# 定义全局资源目录 (假设在 workspace 根目录下的 assets 或 config)
# 您可以根据实际情况修改这里，指向 shared_kernel 或 workspace root
GLOBAL_CONFIG_DIR = WORKSPACE_ROOT / "config"
GLOBAL_ASSETS_DIR = WORKSPACE_ROOT / "assets"

CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

def load_config(config_path: Path = CONFIG_FILE) -> Dict[str, Any]:
    """加载 YAML 配置"""
    loaded_config = {}
    
    # 默认值
    loaded_config['paths'] = {
        'base_dir': str(WORKSPACE_ROOT),
        'output_dir': str(WORKSPACE_ROOT / "output"), # 默认输出目录
        'log_dir': str(WORKSPACE_ROOT / "logs")
    }

    try:
        if config_path.is_file():
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if isinstance(yaml_config, dict):
                    # 深度合并或更新
                    # 这里做简单的 update，实际可能需要 deep_merge
                    if 'paths' in yaml_config:
                        loaded_config['paths'].update(yaml_config['paths'])
                    loaded_config.update({k: v for k, v in yaml_config.items() if k != 'paths'})
                logging.info(f"YAML 配置已加载: {config_path}")
        else:
            logging.warning(f"YAML 配置未找到: {config_path}，将使用默认路径")
    except Exception as e:
        logging.error(f"加载配置文件出错: {e}")

    return loaded_config

# --- 2. 初始化配置单例 ---
CONFIG = load_config()

# --- 3. 导出常用路径常量 ---
PATHS = CONFIG.get("paths", {})

# 辅助函数：解析路径（如果是绝对路径则保持，如果是相对路径则相对于 WORKSPACE_ROOT）
def resolve_path(path_str: str, default_root: Path) -> Path:
    if not path_str:
        return Path(".")
    p = Path(path_str)
    if p.is_absolute():
        return p
    return default_root / p

LOG_DIR = resolve_path(PATHS.get("log_dir", "logs"), WORKSPACE_ROOT)
OUTPUT_DIR = resolve_path(PATHS.get("output_dir", "output"), WORKSPACE_ROOT)

# 模板文件通常在 assets 里
TEMPLATE_PATH = resolve_path(PATHS.get("template_file", "template.xlsx"), GLOBAL_ASSETS_DIR)
# 临时文件放在 output 里
TEMP_PATH = OUTPUT_DIR / "temp_report.xlsx"
OUTPUT_PATH = OUTPUT_DIR / "final_report.xlsx"

# 确保目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# [保留] 下载器脚本路径 (如果下载器还没重构，暂时保留)
DOWNLOADER_SCRIPT_PATH = resolve_path(PATHS.get("downloader_script_path", ""), WORKSPACE_ROOT)
DOWNLOADER_PYTHON_EXECUTABLE = Path(PATHS.get("downloader_python_executable", "python"))