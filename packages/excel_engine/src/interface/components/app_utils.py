# 文件路径：src\excel_generator_project\app\app_setup.py
from pathlib import Path
import datetime
import time, logging, shutil


class AppUtils:
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
