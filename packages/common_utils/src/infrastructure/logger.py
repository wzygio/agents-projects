import logging
import sys
from pathlib import Path
from typing import Optional, Union

def setup_logging(
    log_dir: Union[str, Path] = Path("logs"), 
    log_filename: str = "app.log", 
    log_level: int = logging.INFO
):
    """
    [企业级通用日志配置]
    配置日志系统，实现文件(覆盖模式)和控制台(stderr)的双路输出。
    
    Args:
        log_dir: 日志目录路径 (自动创建)
        log_filename: 日志文件名
        log_level: 日志级别
    """
    # 1. 确保路径是 Path 对象
    if isinstance(log_dir, str):
        log_dir = Path(log_dir)
        
    # 2. 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / log_filename

    # 3. 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 4. [关键] 清除任何已存在的处理器
    # 防止在 Notebook 或多次调用时出现日志重复打印 (Duplicate Logs)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 5. 定义统一格式
    # 使用 %(name)s 可以显示完整的模块路径 (如 packages.ppt_engine.core)
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 6. 处理器 A: 文件输出
    # mode='w' 确保每次启动时清空旧日志，方便定位本次运行的问题
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 7. 处理器 B: 控制台输出 (Standard Error)
    # [关键架构决策] 使用 sys.stderr 而不是 stdout
    # 原因：在 subprocess 调用中，stderr 通常是非缓冲的，且更容易被父进程捕获用于实时流式传输
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    logging.info(f"✅ 日志系统初始化完成 | 输出路径: {log_file_path} | 级别: {logging.getLevelName(log_level)}")