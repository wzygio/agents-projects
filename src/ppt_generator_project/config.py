# core/config.py (V2.0 - 依赖注入重构版)
import yaml
import os, logging, sys
from pathlib import Path
from typing import Dict, Any
from pptx.dml.color import RGBColor

from ppt_generator_project.core.table_processor import TableProcessor
 
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    SRC_ROOT = PROJECT_ROOT / "src"
except NameError:
    PROJECT_ROOT = Path.cwd()
    SRC_ROOT = PROJECT_ROOT / "src"
    logging.warning(f"__file__ 未定义，假定项目根目录为: {PROJECT_ROOT}")

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
    logging.debug(f"将 SRC_ROOT 添加到 sys.path: {SRC_ROOT}")

CONFIG_FILE = Path(PROJECT_ROOT / "config" / "config.yaml")

def load_and_process_config(
    config_path: Path = CONFIG_FILE,
    ) -> Dict[str, Any]:
    """
    加载、处理并返回完整的配置字典。
    这是一个纯粹的工具函数，不产生任何全局副作用。
    """

    try:
        if config_path.is_file():
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                logging.info(f"YAML 配置文件已成功加载: {config_path}")
        else:
            raise FileNotFoundError(f"YAML 配置文件未找到: {config_path}")
            
        if not yaml_config:
            raise ValueError(f"YAML 配置文件为空: {config_path}")
            
        _calculate_table_layouts(yaml_config)
        _convert_colors(yaml_config)
        yaml_config['paths']['base_dir'] = str(PROJECT_ROOT)
        
    except Exception as e:
        logging.error(f"加载或解析 YAML 文件 {config_path} 时出错: {e}")
        raise

    return yaml_config


@staticmethod
def _calculate_table_layouts(config: Dict):
    # 检查配置中是否存在'sections'字段，若不存在则直接返回
    if 'sections' not in config: return

    # 遍历每个章节配置
    for section_cfg in config['sections'].values():
        # 从章节配置中提取表格布局的计算参数calculations
        calc_params = section_cfg.get('table_layout', {}).get('calculations')
        # 如果没有计算规则，跳过当前章节
        if not calc_params: continue

        # 处理行高计算
        if 'row_heights' in calc_params:
            # 获取行高计算参数
            rh_params = calc_params['row_heights']
            # 调用TableProcessor静态方法计算行高（返回行高列表）
            row_heights, _ = TableProcessor._calculate_sizes(**rh_params)
            # 将计算结果存入配置的base部分
            section_cfg['table_layout']['base']['row_heights'] = row_heights

        # 处理列宽计算
        if 'col_widths' in calc_params:
            # 获取列宽计算参数
            cw_params = calc_params['col_widths']
            # 计算窄列的基准宽度（忽略返回的宽度序列）
            _, narrow_col_width = TableProcessor._calculate_sizes(**cw_params['narrow_col_params'])
            
            # 自定义宽度序列
            col_widths = []
            # 根据组装模式生成列宽（如交替窄列和固定列）
            for part in cw_params.get('assembly_pattern', []):
                # 添加指定数量的窄列
                if part['type'] == 'narrow': col_widths.extend([narrow_col_width] * part['count'])
                # 添加指定数量的固定宽度列
                elif part['type'] == 'fixed': col_widths.extend([part['value']] * part['count'])
            # 将生成的列宽存入配置
            section_cfg['table_layout']['base']['col_widths'] = col_widths

        # 删除已处理的计算规则（避免重复处理）
        del section_cfg['table_layout']['calculations']

@staticmethod
def _convert_colors(data: Any) -> Any:
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'fill_color' and isinstance(value, list) and len(value) == 3:
                data[key] = RGBColor(*value)
            else: _convert_colors(value)
    elif isinstance(data, list):
        for item in data: _convert_colors(item)
    return data

# --- 执行加载 ---
CONFIG = load_and_process_config()

# --- 其他常用路径常量 (保持不变) ---
LOG_DIR = PROJECT_ROOT / Path(CONFIG['paths']['log_dir'])
RESOURCES_DIR = PROJECT_ROOT / Path(CONFIG['paths']['resources_dir'])
DATA_RAW_DIR = PROJECT_ROOT / Path(CONFIG['paths']['data_raw_dir'])
OUTPUT_DIR = PROJECT_ROOT / Path(CONFIG['paths']['output_dir'])
MAIN_PY_PATH = PROJECT_ROOT / Path(CONFIG['paths']['main_py_path'])
