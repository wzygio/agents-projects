# utils/helpers.py
import sys, logging
import logging
import os, shutil, re
import subprocess
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import unicodedata 

from ppt_generator_project.config import LOG_DIR

class Utils:
    @staticmethod
    def setup_logging(log_filename: str = 'app.log', log_level=logging.INFO):
        """
        (已重构) 配置日志系统，实现文件和控制台的双路输出。
        """
        # 1. 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # 2. 清除任何已存在的处理器，防止日志重复输出
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        # 3. 创建一个统一的日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(module)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 4. 创建处理器 1: 写入到文件
        log_dir = LOG_DIR  # 使用项目根目录下的logs目录
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / log_filename
        # 新增：清空现有日志文件
        if log_file_path.exists():
            log_file_path.write_text('', encoding='utf-8')

        file_handler = logging.FileHandler(log_dir / log_filename, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # 5. 创建处理器 2: 输出到标准错误流 (stderr)
        #    这是让 subprocess 能够捕获到日志的关键
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        logging.info(f"日志系统已初始化，将同时输出到文件 '{log_filename}' 和控制台。")

    @staticmethod
    def is_valid_pptx(file_path):
        """检查文件是否是有效的PPTX文件"""
        if not os.path.exists(file_path):
            return False
        try:
            with ZipFile(file_path, 'r') as zip_file:
                # 检查是否包含必要的PPTX文件结构
                return '[Content_Types].xml' in zip_file.namelist()
        except BadZipFile:
            return False
    
    
    @staticmethod
    def find_latest_matching_file(directory: Path, file_name: str) -> Path | None:
        """
        在目录中查找包含file_name的最新文件，支持模糊匹配，优先使用非临时文件。
        
        :param directory: 要搜索的目录路径
        :param file_name: 用于模糊匹配的关键字
        :return: 匹配到的最新文件的Path对象，如果未找到则返回None
        """
        # 检查目录是否存在
        if not directory.exists():
            logging.error(f"资源目录 '{directory}' 不存在。")
            return None

        try:
            # 分离普通文件和临时文件
            normal_files = []
            temp_files = []
            
            for f in directory.iterdir():
                if not f.is_file():
                    continue
                if file_name in f.name:
                    if f.name.startswith('~$'):
                        temp_files.append(f)
                    else:
                        normal_files.append(f)
            
            # 优先使用普通文件
            if normal_files:
                latest_file = max(normal_files, key=lambda x: x.stat().st_mtime) # 获取最新的普通文件
                logging.info(f"找到匹配的文件：'{latest_file.name}'")
                return latest_file
                
            # 如果没有普通文件，使用临时文件
            if temp_files:
                latest_temp = max(temp_files, key=lambda x: x.stat().st_mtime) # 获取最新的临时文件
                # 从临时文件名恢复原始文件名（去掉~$前缀）
                original_name = latest_temp.name[2:]
                latest_file = latest_temp.with_name(original_name)
                logging.info(f"找到匹配的临时文件：'{latest_file.name}'")
                return latest_file
                
            logging.error(f"未找到包含关键字 '{file_name}' 的文件。")
            return None
            
        except Exception as e:
            logging.error(f"无法读取资源目录 '{directory}'：{e}")
            return None

    
    @staticmethod
    def safe_copy_file(src: Path, dst: Path) -> bool:
        """
        [V3 - 最终健壮版] 安全地复制文件。
        使用 robocopy 来解决 shutil.copy2 在 subprocess 中复制网络锁定文件时的环境 Bug。
        """
        try:
            # 确保目标目录存在
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # 1. 检查源文件是否存在 (robocopy 需要这个)
            if not src.exists():
                logging.error(f"Robocopy 失败：源文件不存在 {src}")
                return False

            # 2. 准备 robocopy 参数
            src_dir = str(src.parent)
            dst_dir = str(dst.parent)
            src_file = str(src.name)
            
            logging.info(f"正在使用 robocopy 复制 (解决 subprocess I/O 问题): {src_file}")

            # /B :: 使用“备份模式”，允许复制被“写锁定”的文件（“读”权限仍然是有的）
            # /Z :: 可重启模式，适用于网络
            # /R:1 :: 失败后重试1次
            # /W:2 :: 每次重试等待2秒
            # /NFL /NDL /NP :: 减少控制台日志噪音
            
            cmd = [
                'robocopy',
                src_dir,
                dst_dir,
                src_file,
                '/B',    # <--- [关键] 备份模式
                '/Z',    # <--- [关键] 可重启模式
                '/R:1',
                '/W:2',
                '/NFL', '/NDL', '/NP'
            ]

            # 3. 执行
            # 我们使用 latin-1 编码，因为 robocopy 的输出不是 UTF-8
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='latin-1')

            # 4. 检查结果
            # Robocopy 的返回码 0-7 都算“成功”（例如 1 表示已复制文件）
            if result.returncode < 8:
                if dst.exists() and dst.stat().st_size > 0:
                    logging.info(f"Robocopy 成功: {dst.name}")
                    return True
                else:
                    logging.error(f"Robocopy 报告成功，但本地文件验证失败 (大小为0或不存在): {dst}")
                    logging.error(f"Robocopy STDOUT: {result.stdout}")
                    logging.error(f"Robocopy STDERR: {result.stderr}")
                    return False
            else:
                # 8 或 16 表示严重失败
                logging.error(f"Robocopy 复制失败，返回码: {result.returncode}")
                logging.error(f"Robocopy STDOUT: {result.stdout}")
                logging.error(f"Robocopy STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            logging.error(f"调用 robocopy 时发生 Python 错误 (e.g., robocopy.exe not found?): {e}")
            return False

    @staticmethod
    def normalize_string(text: str) -> str:
        """
        对字符串进行深度清洗和标准化，以便进行可靠的比较。
        1. 使用NFKC进行Unicode标准化 (例如，将全角字符转为半角)。
        2. 移除所有类型的空白字符。
        3. 转换为小写。
        """
        try:
            # 确保输入是字符串
            text = str(text)
            # 1. Unicode NFKC 标准化
            normalized_text = unicodedata.normalize('NFKC', text)
            # 2. 使用正则表达式移除所有空白字符 (包括空格, tab, 换行, 全角空格等)
            no_whitespace_text = re.sub(r'\s+', '', normalized_text)
            # 3. 转换为小写
            return no_whitespace_text
        except Exception:
            # 如果出现任何意外，返回原始字符串的小写形式作为备用
            return str(text)