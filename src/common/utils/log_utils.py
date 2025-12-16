import sys
import logging
from pathlib import Path

from src.config import config

def setup_logging(log_filename):
    """
    初始化日志系统。
    :param log_filename: 日志文件路径
    """
    log_dir = Path(str(config.get("path.log_dir")))
    # 1. 确保日志目录存在 (防御性编程)
    if not log_dir.exists():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # 如果连日志目录都创建不了，直接打印到控制台并退出
            print(f"❌ Fatal Error: Cannot create log directory at {log_dir}: {e}")
            sys.exit(1)

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