import logging
import traceback
import sys
from queue import Queue
from typing import Dict, Any

# 1. 引入标准接口
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入本模块的配置
from packages.anomaly_monitor.src.config import AnomalyMonitorConfig
# [关键] 引入配置模块本身，以便注入全局 CONFIG
import packages.anomaly_monitor.src.config as config_module 

# 3. 引入核心业务
from packages.anomaly_monitor.src.application.hl_report_service import HLReportService
from packages.anomaly_monitor.src.application.hl_generator import AnomalyMonitorGenerator

# 复用 QueueLoggingHandler (如果 common_utils 里有就 import，没有就定义)
class QueueLoggingHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('[%(asctime)s] [Monitor] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            self.queue.put(self.format(record))
        except Exception:
            self.handleError(record)

class AnomalyMonitorAdapter(ITaskEngine):
    """
    [Adapter] 异常监控模块适配器。
    负责初始化环境、注入配置，并驱动 Generator 完成全自动流程。
    """

    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        # --- A. 设置日志 ---
        logger = logging.getLogger()
        handler = QueueLoggingHandler(log_queue)
        logger.addHandler(handler)
        
        # 临时捕获所有日志
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] 异常监控引擎正在启动...")

            # --- B. 配置注入 (Global Context Injection) ---
            # 1. 将字典转为对象
            monitor_config = AnomalyMonitorConfig.from_app_config(config_dict)
            
            # 2. [核心技巧] 注入到模块全局变量
            # 因为 HLReportService 内部的 Repository 可能直接使用了 config.CONFIG
            # 我们在这里手动赋值，确保底层能拿到 Server 传来的最新配置
            config_module.CONFIG = monitor_config
            log_queue.put("⚙️ 全局配置上下文已注入")

            # --- C. 初始化服务 ---
            # 实例化 Service (它会去读我们刚才注入的 Global CONFIG)
            service = HLReportService()
            
            # 实例化 Generator (注入 Service)
            generator = AnomalyMonitorGenerator(service)

            # --- D. 执行核心业务 ---
            log_queue.put("🤖 调用 Generator 执行全自动流程...")
            
            result = generator.generate()
            
            # --- E. 处理结果 ---
            status = result.get("status")
            if status == "success":
                msg = result.get("message", "执行成功")
                count = result.get("count", 0)
                log_queue.put(f"✅ {msg}")
                return {
                    "status": "success",
                    "details": f"自动处理了 {count} 条异常"
                }
            elif status == "skipped":
                log_queue.put("⏭️ 流程跳过: 数据检查未通过")
                return {"status": "success", "details": "无有效数据"}
            else:
                raise RuntimeError(f"Unknown status: {result}")

        except Exception as e:
            err_msg = f"❌ [Adapter] 执行失败: {str(e)}"
            log_queue.put(err_msg)
            # 发送堆栈信息
            log_queue.put(f"Debug:\n{traceback.format_exc()}")
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)