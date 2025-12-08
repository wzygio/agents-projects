import os
import sys
import logging


def setup_logging(log_filename="output/data_processor.log"):
    """
    初始化日志系统。
    :param log_filename: 日志文件路径
    """
    # 创建 output 目录（如果不存在）
    os.makedirs("output", exist_ok=True)

    # 强制重新配置日志系统
    # 先清除现有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 配置日志系统
    logging.basicConfig(
        level=logging.INFO,  # 设置日志级别为 INFO
        format="%(asctime)s [%(levelname)s] %(message)s",  # 日志格式
        handlers=[
            logging.FileHandler(log_filename, mode='w', encoding="utf-8"),  # 覆盖模式写入日志文件
            logging.StreamHandler()  # 输出到控制台
        ]
    )
    logging.info(f"日志已初始化，写入到文件: {log_filename}")