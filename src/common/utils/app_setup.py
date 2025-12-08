import sys
import logging
from pathlib import Path

from src.config import config
from common.utils.log_utils import setup_logging

class AppSetup:
    """
    应用启动引导类
    职责：负责应用启动时的基础设施初始化（日志、配置检查、数据库预热等）
    """
    
    @staticmethod
    def initialize_app(log_name="app.log"):
        """
        初始化应用环境
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
        log_file_path = log_dir / log_name

        # 3. 初始化日志系统
        # 这里不需要 try-except，因为 setup_logging 如果失败，那就是代码写错了，应该让它爆出来
        setup_logging(log_filename=str(log_file_path))

        logging.info("✅ App environment initialized successfully.")
        logging.info(f"📂 Log file: {log_file_path}")