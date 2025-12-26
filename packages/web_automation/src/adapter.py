import logging
import traceback
from queue import Queue
from typing import Dict, Any, List

# 1. 引入标准接口
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入本模块配置
from packages.web_automation.src.config import WebAutomationConfig

# 3. 引入核心业务服务
from packages.web_automation.src.application.download_service import DownloadService

# 4. 复用日志拦截器
class QueueLoggingHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('[%(asctime)s] [Web] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            self.queue.put(self.format(record))
        except Exception:
            self.handleError(record)

class WebAutomationAdapter(ITaskEngine):
    """
    [Adapter] Web 自动化下载模块适配器。
    负责初始化 Playwright 环境并执行下载任务。
    """

    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        """
        全自动执行入口。
        """
        # --- A. 设置日志 ---
        logger = logging.getLogger()
        handler = QueueLoggingHandler(log_queue)
        logger.addHandler(handler)
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] Web 自动化引擎正在启动...")

            # --- B. 加载配置 ---
            # 使用 Config 中提供的工厂方法
            web_config = WebAutomationConfig.from_app_config(config_dict)
            
            # --- C. 初始化服务 ---
            log_queue.put(f"🌍 目标门户: {web_config.daily_report.portal_url}")
            
            # 实例化 Service (它内部会初始化 BrowserManager)
            # 注意：DownloadService 的 __init__ 接收 global_config (对象或字典)
            # 这里我们传入已经转换好的 web_config 对象，DownloadService 内部有逻辑处理它
            service = DownloadService(web_config)

            # --- D. 执行核心业务 ---
            log_queue.put("⬇️ 开始执行报表下载任务...")
            
            # 提取产品型号列表 (用于过滤下载)
            target_models = web_config.daily_report.product_models
            
            # 执行下载 (阻塞调用)
            service.run_download_tasks(product_models=target_models)
            
            # --- E. 结果反馈 ---
            download_dir = web_config.download_dir
            log_queue.put(f"✅ 下载任务全部完成。保存目录: {download_dir}")
            
            return {
                "status": "success",
                "details": f"下载目录: {download_dir}"
            }

        except Exception as e:
            err_msg = f"❌ [Adapter] 执行失败: {str(e)}"
            log_queue.put(err_msg)
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            # --- F. 清理 ---
            logger.removeHandler(handler)
            logger.setLevel(original_level)