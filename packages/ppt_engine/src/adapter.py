import logging
import traceback
from queue import Queue
from pathlib import Path
from typing import Dict, Any, Generator

# 1. 引入标准接口
# (确保您已经创建了 packages/common_utils/src/interfaces.py，参考上一条回答 Step 1)
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入 PPT 引擎核心组件
from pptx import Presentation
from packages.ppt_engine.src.config import PptEngineConfig
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from packages.ppt_engine.src.core.table_processor import TableProcessor
from packages.ppt_engine.src.application.yield_generator import YieldDataSectionGenerator

# 3. 简单的队列日志拦截器 (用于将 logging 转发到 Queue)
class QueueLoggingHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        # 设置一个简单的格式
        self.setFormatter(logging.Formatter('[%(asctime)s] [PPT] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.queue.put(msg)
        except Exception:
            self.handleError(record)

class PPTEngineAdapter(ITaskEngine):
    """
    [Adapter] PPT生成引擎适配器。
    它将通用的字典配置转换为强类型的 PptEngineConfig，并驱动核心生成逻辑。
    """

    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        """
        全自动执行入口。
        此方法会在单独的线程中运行，是阻塞的。
        """
        # --- A. 设置日志拦截 ---
        # 获取 PPT 引擎专用的 Logger (与 YieldDataSectionGenerator 中的 logger 名称对应)
        # 最好是拦截 root logger，这样能捕获所有子模块的日志
        logger = logging.getLogger()
        handler = QueueLoggingHandler(log_queue)
        logger.addHandler(handler)
        
        # 记录当前的 Level 以便恢复
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] PPT 引擎正在初始化...")

            # --- B. 加载配置 ---
            # 直接使用您 config.py 中的工厂方法
            # 这里的 config_dict 是全局 AppConfig，from_app_config 会自动提取 'ppt_engine' 字段
            ppt_config = PptEngineConfig.from_app_config(config_dict)
            
            # --- C. 准备资源 ---
            # 根据 config.py 的定义，base_dir 是可选的，如果没有则回退到 cwd
            project_root = Path(ppt_config.paths.base_dir) if ppt_config.paths.base_dir else Path.cwd()
            
            # 拼接模板路径
            # 这里的字段名与 config.py 中的 PathsConfig 对应
            template_path = project_root / ppt_config.paths.resources_dir / ppt_config.paths.output_template_ppt
            
            if not template_path.exists():
                raise FileNotFoundError(f"PPT模板文件未找到: {template_path}")
            
            log_queue.put(f"📂 加载模板: {template_path.name}")
            source_prs = Presentation(str(template_path))

            # --- D. 组装依赖 (Dependency Injection) ---
            # 实例化 ElementProcessor
            element_processor = ElementProcessor(ppt_config)
            table_processor = TableProcessor()
            
            # 实例化核心生成器 (YieldDataSectionGenerator)
            # 注意：这里我们暂时只调用了第一章的 Generator
            # 如果有多个章节，这里应该是一个 Orchestrator 或者按顺序实例化多个 Generator
            generator = YieldDataSectionGenerator(
                prs=source_prs,
                config=ppt_config,
                element_processor=element_processor,
                table_processor=table_processor
            )

            # --- E. 执行业务 ---
            log_queue.put("⚙️ 开始生成页面数据...")
            generator.generate()
            
            # --- F. 保存结果 ---
            output_dir = project_root / ppt_config.paths.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = output_dir / ppt_config.paths.output_ppt
            source_prs.save(str(output_path))
            
            log_queue.put(f"✅ 生成完毕! 文件已保存至: {output_path.name}")
            
            return {
                "status": "success",
                "output_path": str(output_path)
            }

        except Exception as e:
            # 捕获所有未处理异常，打印堆栈
            err_msg = f"❌ 执行失败: {str(e)}"
            log_queue.put(err_msg)
            
            # 打印详细堆栈到控制台（方便开发调试）
            traceback.print_exc()
            
            # 也发送给前端（可选，视安全策略而定）
            # log_queue.put(f"Debug: {traceback.format_exc()}")
            
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            # --- G. 清理环境 ---
            # 移除 Handler，防止内存泄漏或日志重复
            logger.removeHandler(handler)
            logger.setLevel(original_level)