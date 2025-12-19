# 文件路径：src\excel_generator_project\app\app_setup.py
import sys, os
from pathlib import Path
import datetime
import streamlit as st
import subprocess
import time, logging, shutil
from typing import Optional

from excel_generator_project.config import TEMPLATE_PATH, TEMP_PATH, PROJECT_ROOT
from packages.excel_engine.src.utils.local_utils import Utils

class AppSetup:
    @staticmethod
    def initialize_app():
        """
        初始化应用的日志系统。
        """
        Utils.setup_logging("app.log")
        logging.info("Application setup complete (logging initialized).")

    @staticmethod
    def save_uploaded_file(uploaded_file, save_path: Path):
        """(已更新为先删除后保存的模式) 保存上传的文件到指定路径"""
        try:
            # --- 核心修改：在写入新文件前，先检查并删除已存在的旧文件 ---
            if save_path.exists():
                logging.info(f"检测到已存在的目标文件 '{save_path}'，正在删除...")
                save_path.unlink() # 使用 unlink 删除文件
                logging.info(f"旧文件已成功删除。")
            # --- 修改结束 ---

            # 将文件指针重置到开头
            uploaded_file.seek(0)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用 shutil.copyfileobj 进行流式复制
            with open(save_path, "wb") as f:
                shutil.copyfileobj(uploaded_file, f)
                
            logging.info(f"文件 '{uploaded_file.name}' 已成功保存到 '{save_path}'")
            return save_path
        except Exception as e:
            logging.error(f"保存上传文件时出错: {e}", exc_info=True)
            raise

    @staticmethod
    def generate_dynamic_filename() -> str:
        """根据当前时间段，生成动态的默认输出文件名。"""
        now = datetime.datetime.now()
        date_str = now.strftime('%Y%m%d')
        current_hour = now.hour

        if 0 <= current_hour < 12:
            # 规则1: 0点到12点之前，不添加时刻
            return f"V3屏体良率日报-{date_str}.xlsx"
        elif 12 <= current_hour < 16:
            # 规则2: 12点到16点之前，固定为14:00 (注意使用全角冒号)
            return f"V3屏体良率日报-{date_str}-14：00.xlsx"
        else: # 16:00 - 23:59
            # 规则3: 16点及以后，固定为16:00 (注意使用全角冒号)
            return f"V3屏体良率日报-{date_str}-16：00.xlsx"

    @staticmethod
    def run_subprocess(script_path: str, 
                    python_executable: str, # <-- 新增参数
                    template_path: Optional[str] = None, # 设为可选
                    output_path: Optional[str] = None):  # 设为可选
        """(已重构) 一个通用的、用于执行后台脚本的函数，允许指定Python解释器。"""
        st.info(f"正在执行脚本: {Path(script_path).name}...")
        
        process_env = os.environ.copy()
        # 只有在提供了路径时才添加到环境变量
        if template_path:
            st.write(f"  - 输入文件: {template_path}")
            process_env["TEMPLATE_PATH"] = str(template_path)
        if output_path:
            st.write(f"  - 输出文件: {output_path}")
            process_env["OUTPUT_PATH"] = str(output_path)
            
        process_env["PYTHONPATH"] = os.environ.get("PYTHONPATH", "") + os.pathsep + str(PROJECT_ROOT)
        process_env["PYTHONUTF8"] = "1"

        # --- 核心修改：使用传入的 python_executable ---
        return subprocess.run(
            [python_executable, script_path], # 使用指定的解释器
            env=process_env,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )