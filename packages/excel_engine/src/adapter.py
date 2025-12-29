import logging
import traceback
from queue import Queue
from pathlib import Path
from typing import Dict, Any

# 1. 引入标准接口
from packages.common_utils.src.interface.interfaces import ITaskEngine

# 2. 引入本模块的配置
from packages.excel_engine.src.config import ExcelEngineConfig

# 3. 引入两个核心 UseCase
from packages.excel_engine.src.application.report_genrator import GenerateReportUseCase
from packages.excel_engine.src.application.style_renderer import RefineStylesUseCase


# 4. 复用日志拦截器
class QueueLoggingHandler(logging.Handler):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('[%(asctime)s] [Excel] %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            self.queue.put(self.format(record))
        except Exception:
            self.handleError(record)

class ExcelEngineAdapter(ITaskEngine):
    """
    [Adapter] Excel 报表生成引擎适配器。
    职责：编排 "内容生成" -> "样式渲染" 的流水线。
    """

    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        # --- A. 设置日志 ---
        logger = logging.getLogger()
        handler = QueueLoggingHandler(log_queue)
        logger.addHandler(handler)
        original_level = logger.level
        logger.setLevel(logging.INFO)

        try:
            log_queue.put("🚀 [Adapter] Excel 引擎正在启动...")

            # --- B. 加载配置 ---
            excel_config = ExcelEngineConfig.from_app_config(config_dict)
            path = excel_config.path

            # --- C. 路径准备 (Path Resolution) ---
            # 确定项目根目录 (优先使用配置中的 base_dir，否则用当前工作目录)
            project_root = Path(path.base_dir) if path.base_dir else Path.cwd()

            # 1. 输入：模板文件
            template_path = project_root / path.resources_dir / path.template_file
            if not template_path.exists():
                raise FileNotFoundError(f"模板文件未找到: {template_path}")

            # 2. 中间态：临时文件 (用于连接 Content 和 Style 两个步骤)
            temp_dir = project_root / path.temp_dir
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / path.temp_file

            # 3. 输出：最终文件
            output_dir = project_root / path.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            final_path = output_dir / path.output_file

            log_queue.put(f"📂 路径解析完成:\n  - 模板: {template_path.name}\n  - 临时: {temp_path.name}\n  - 输出: {final_path.name}")

            # --- D. 执行 Stage 1: 内容生成 (Content Generation) ---
            log_queue.put("⚙️ [Stage 1/2] 开始生成报表内容...")
            
            # 实例化 Content Generator
            content_use_case = GenerateReportUseCase(config=excel_config)
            
            # 执行: Template -> Temp File
            content_use_case.execute(template_path=template_path, output_path=temp_path)
            
            log_queue.put("✅ 内容生成完成，准备渲染样式...")

            # --- E. 执行 Stage 2: 样式渲染 (Style Refinement) ---
            log_queue.put("🎨 [Stage 2/2] 开始渲染报表样式...")
            
            # 实例化 Style Generator
            style_use_case = RefineStylesUseCase(config=excel_config)
            
            # 执行: Temp File -> Final Output
            # 注意：Style Generator 的输入是上一步的输出
            style_use_case.execute(input_path=temp_path, output_path=final_path)

            log_queue.put(f"✅ 样式渲染完成。")

            # --- F. 返回结果 ---
            return {
                "status": "success",
                "output_path": str(final_path),
                "details": "内容生成与样式渲染均已完成"
            }

        except Exception as e:
            err_msg = f"❌ [Adapter] 执行失败: {str(e)}"
            log_queue.put(err_msg)
            traceback.print_exc() # 打印到后台控制台
            # log_queue.put(f"Debug: {traceback.format_exc()}") # 可选：发送给前端
            
            return {
                "status": "error",
                "message": str(e)
            }
            
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)