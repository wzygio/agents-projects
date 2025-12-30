import sys, logging

from packages.common_utils.src.infrastructure.logger import setup_logging

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
        
        # 3. 初始化日志系统
        setup_logging(log_filename = log_name)

        logging.info("✅ App environment initialized successfully.")
        logging.info(f"📂 Log file: {log_name}")