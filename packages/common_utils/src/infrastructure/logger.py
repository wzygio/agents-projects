import sys
import logging
from pathlib import Path

from src.config import config

def setup_logging(log_filename: str = "app.log", log_dir: Path = Path("logs")):
    """
    初始化日志系统。
    :param log_filename: 日志文件路径
    """

    # 2. 拼接日志文件路径
    log_file_path = log_dir / log_filename

    # 强制重新配置日志系统，先清除现有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 配置日志系统
    logging.basicConfig(
        level=logging.INFO,  # 设置日志级别为 INFO
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", # 增加 %(name)s，这样如果是 logger 打印的，就会显示来源模块名
        handlers=[
            logging.FileHandler(log_file_path, mode='w', encoding="utf-8"),  # 覆盖模式写入日志文件
            logging.StreamHandler()  # 输出到控制台
        ]
    )
    logging.info(f"日志已初始化，写入到文件: {log_filename}")