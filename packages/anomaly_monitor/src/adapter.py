import logging
import traceback
import sys
from queue import Queue
from typing import Dict, Any

# 1. 引入标准接口
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入配置类
from packages.anomaly_monitor.src.config import AnomalyMonitorConfig

# 3. 引入核心业务
from packages.anomaly_monitor.src.application.hl_report_service import HLReportService
from packages.anomaly_monitor.src.application.hl_generator import AnomalyMonitorGenerator

# 复用日志处理器
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
        
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] 异常监控引擎正在启动...")

            # --- B. 配置加载 (Pure Loading) ---
            # 1. 将字典转为强类型配置对象
            monitor_config = AnomalyMonitorConfig.from_app_config(config_dict)
            log_queue.put("⚙️ 配置对象已构建 (Dependency Injection Ready)")

            # --- C. 初始化服务 (Dependency Injection) ---
            # [核心修改] 直接将 config 对象注入 Service，不再修改全局变量
            service = HLReportService(config=monitor_config)
            
            # 实例化 Generator (注入 Service)
            generator = AnomalyMonitorGenerator(service)

            # --- D. 执行核心业务 ---
            log_queue.put("🤖 调用 Generator 执行全自动流程...")
            
            # 注意：generator.generate() 内部会调用 service 的方法
            # 此时 service 已经持有正确的 config，不需要再去 import 全局 CONFIG
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
            # 发送堆栈信息以便调试
            log_queue.put(f"Debug:\n{traceback.format_exc()}")
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)