# core/dynamic_settings.py (V3.1 - 仅负责侦察路径版)
import logging
from typing import Dict
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Any, Union

def _find_monthly_template_dir(config: dict) -> tuple[Path, str]:
    """
    查找正确的月份文件夹路径，并返回它的【绝对路径】和【相对子目录名】。
    逻辑：
    1. 优先查找当前年月的文件夹（如 2024/05月）
    2. 如果不存在则查找上个月的文件夹（如 2024/04月）
    3. 返回格式：(Path("公共盘路径/2024/05月"), "2024/05月")
    """
    paths_cfg = config.get('paths', {})  # 获取配置中的路径信息
    network_base_dir = Path(paths_cfg.get('network_source_dir'))  # 公共盘基础路径
    report_base_dir_name = paths_cfg.get('daily_report_template', {}).get('base_dir')  # 模板基础目录
    full_base_path = network_base_dir / report_base_dir_name  # 完整基础路径

    today = date.today()  # 当前日期
    # 构建当前月份的完整路径（如 公共盘路径/模板基础目录/2024/05月）
    current_month_path = full_base_path / str(today.year) / f"{today.month}月"
    
    if current_month_path.is_dir():  # 当前月份文件夹存在
        # 计算相对路径（如 "2024/05月"）
        relative_subdir = current_month_path.relative_to(network_base_dir)
        return current_month_path, str(relative_subdir)

    # 当前月份文件夹不存在，尝试查找上个月
    first_day_of_current_month = today.replace(day=1)  # 当月第一天
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)  # 上个月最后一天
    previous_month_path = full_base_path / str(last_day_of_previous_month.year) / f"{last_day_of_previous_month.month}月"
    
    if previous_month_path.is_dir():  # 上个月文件夹存在
        relative_subdir = previous_month_path.relative_to(network_base_dir)
        return previous_month_path, str(relative_subdir)

    # 当月和上个月文件夹都不存在，抛出异常
    raise FileNotFoundError(f"未找到任何有效的模板文件夹（当月或上个月）")

def _find_daily_template_file(config: dict, search_dir: Path) -> str:
    """
    在给定的文件夹内，查找正确的日报文件名，只返回【文件名】字符串。
    新逻辑：
    1. 获取当天的日期字符串（MMDD格式）
    2. 查找所有包含该日期的文件（支持模糊匹配）
    3. 在匹配的文件中选择修改时间最新的一个
    4. 如果找不到当天文件，则依次向前查找，最多查找3天
    """
    today = date.today()
    
    # 循环查找最多3天
    for days_back in range(4):  # 包括当天，共查找4天
        current_date = today - timedelta(days=days_back)
        date_str = current_date.strftime('%m%d')
        
        # 获取目录中所有文件
        all_files = list(search_dir.glob(f"*{date_str}*"))
        
        if all_files:
            # 按修改时间排序，选择最新的文件
            latest_file = max(all_files, key=lambda f: f.stat().st_mtime)
            return latest_file.name
    
    # 3天内都未找到文件，抛出异常
    raise FileNotFoundError(f"在文件夹 '{search_dir.name}' 中，未找到最近3天内的日报文件。")



def process_dynamic_settings(config: Union[Dict[str, Any], Any]) -> Union[Dict[str, Any], Any]:
    # ... 原有代码 ...
    """
    【主函数】在data_sources配置中，动态地查找并更新主模板的路径和文件名信息。
    核心流程：
    1. 查找月份文件夹路径
    2. 在该文件夹下查找日报文件名
    3. 更新配置中主模板的路径和文件名
    4. 失败时使用后备方案
    """
    logging.info("--- 开始动态解析主模板配置 ---")
    
    try:
        # 1. 获取月份文件夹的绝对路径和相对路径
        found_dir_path, relative_subdir_str = _find_monthly_template_dir(config)
        
        # 2. 在该文件夹下获取正确的文件名
        found_filename = _find_daily_template_file(config, found_dir_path)

        # 3. 在data_sources列表中找到主模板条目并用【纯粹的字符串】更新它
        data_sources = config.get('paths', {}).get('data_sources', [])
        for item in data_sources:
            if item.get('key_name') == 'main_template':  # 找到主模板配置项
                item['filename'] = found_filename  # 更新文件名
                item['network_subdir'] = relative_subdir_str  # 更新子目录路径
                logging.info(f"已动态更新主模板配置: subdir='{item['network_subdir']}', filename='{item['filename']}'")
                break  # 找到后立即退出循环
        
    except FileNotFoundError as e:
        logging.warning(f"UI_WARNING: 动态模板查找失败 ({e})，将尝试使用本地后备文件。")
        # 即使公共盘查找失败，依然要填充预期的文件名，供本地后备逻辑使用
        today = date.today()
        filename_format = config.get('paths', {}).get('daily_report_template', {}).get('filename_format')
        expected_filename = filename_format.format(date=today.strftime('%m%d'))
        for item in config.get('paths', {}).get('data_sources', []):
            if item.get('key_name') == 'main_template':  # 找到主模板配置项
                item['filename'] = expected_filename  # 使用预期文件名
                item['network_subdir'] = ''  # 清空子目录路径（表示使用默认路径）
                break

    logging.info("--- 动态配置处理完毕 ---")
    return config  # 返回更新后的配置