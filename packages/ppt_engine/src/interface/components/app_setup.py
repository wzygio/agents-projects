# src/setup.py
import sys, logging, os
from typing import Any 
from pptx.dml.color import RGBColor 
from packages.ppt_engine.src.utils.local_utils import Utils

class AppSetup:
    @staticmethod
    def initialize_app():
        """
        初始化应用的日志系统。
        该方法用于配置应用程序的日志记录功能，将日志信息输出到指定的文件中。
        """

        Utils.setup_logging(log_filename="app.log")
        logging.info("Application setup complete (logging initialized).")

    @staticmethod
    def save_uploaded_file(uploaded_file, directory):
        """保存上传的文件到指定目录"""
        # 确保目标目录存在
        os.makedirs(directory, exist_ok=True)
        
        # 清空目录中的所有文件
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        
        # 保存新文件
        file_path = os.path.join(directory, uploaded_file.name)
        with open(file_path, "wb") as f: 
            f.write(uploaded_file.getbuffer())
        return file_path


    @staticmethod
    def revert_colors_to_list(data: Any) -> Any:
        """
        一个递归函数，用于将配置字典中所有的RGBColor对象转换回简单的列表。
        这是 _convert_colors 函数的逆操作。
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, RGBColor):
                    data[key] = list(value)
                else:
                    AppSetup.revert_colors_to_list(value)
        elif isinstance(data, list):
            for item in data:
                AppSetup.revert_colors_to_list(item)
        return data