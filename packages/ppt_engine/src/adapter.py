import logging
import traceback
from queue import Queue
from typing import Dict, Any, Optional

# 1. 引入标准接口
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入配置类与生成器
from packages.ppt_engine.src.config import PptEngineConfig
# [核心修改] 直接导入 PPTGenerator (Application Service)
from packages.ppt_engine.src.application.ppt_generator import PPTGenerator

# 3. 日志拦截器
class QueueLoggingHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('[%(asctime)s] [PPT] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            self.queue.put(self.format(record))
        except Exception:
            self.handleError(record)

class PPTEngineAdapter(ITaskEngine):
    """
    [Adapter] PPT生成引擎适配器 (Server Mode Entry Point)。
    
    职责：
    1. 接收 Server 传递的 config_dict (包含全局配置 + 前端动态参数)。
    2. 将其转换为强类型的 PptEngineConfig 对象。
    3. 实例化 PPTGenerator 并调用其 .run() 方法。
    """

    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        """
        全自动执行入口。
        """
        # --- A. 设置日志拦截 ---
        # 拦截 root logger 以捕获所有子模块的输出
        logger = logging.getLogger()
        handler = QueueLoggingHandler(log_queue)
        logger.addHandler(handler)
        
        # 临时调整日志级别确保前端能看到信息
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] PPT 自动化引擎启动...")

            # --- B. 配置组装 (The Merger) ---
            # 这里的 config_dict 已经由 Server 进行了初步处理
            # 它是 Global Config 和 Runtime Params 的混合体
            
            # 1. 实例化配置对象 (Dependency Injection)
            log_queue.put("⚙️ 正在解析配置上下文...")
            ppt_config = PptEngineConfig.from_app_config(config_dict)
            
            # --- C. 核心调用 (The Invocation) ---
            # 直接实例化 Generator (Orchestrator)，注入配置对象
            log_queue.put("🤖 初始化核心生成器 (Memory Injection)...")
            generator = PPTGenerator(config=ppt_config)
            
            # 执行生成流程
            log_queue.put("▶️ 开始执行生成流程...")
            generator.run()
            
            # --- D. 结果构建 ---
            # 从 config 对象中获取输出路径 (Generator 会更新 config 中的路径)
            output_path = generator.output_dir / generator.config.paths.output_ppt
            
            log_queue.put(f"✅ PPT 生成完毕! 文件路径: {output_path.name}")
            
            return {
                "status": "success",
                "output_path": str(output_path),
                "message": "PPT Generated Successfully"
            }

        except Exception as e:
            err_msg = f"❌ [Adapter] PPT 生成失败: {str(e)}"
            log_queue.put(err_msg)
            log_queue.put(f"Debug Info:\n{traceback.format_exc()}") # 发送堆栈供调试
            
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            # --- E. 清理环境 ---
            logger.removeHandler(handler)
            logger.setLevel(original_level)