# utils/helpers.py
import sys, logging
import logging
import pandas as pd
from pathlib import Path

class Utils:
    @staticmethod
    def find_latest_matching_file(directory: Path, file_name: str, suffix: str = ".xlsx") -> Path | None:
        """
        在目录中查找包含关键字的最新文件。
        
        优化点：
        1. 忽略大小写匹配。
        2. 自动过滤临时文件(~$开头)。
        3. 增加后缀限制，防止匹配到非目标格式文件。
        
        :param directory: 搜索目录
        :param file_name: 关键字 (如 "HL_台账")
        :param suffix: 文件后缀筛选 (默认 ".xlsx")
        :return: 最新文件的 Path 对象，未找到返回 None
        """
        if not directory.exists():
            logging.error(f"资源目录 '{directory}' 不存在。")
            return None

        try:
            candidates = []
            
            # 1. 获取所有匹配后缀的文件 (先用 glob 粗筛，性能更好)
            # "*" + suffix 确保只看特定类型文件
            for f in directory.glob(f"*{suffix}"):
                
                # 2. 排除 Office 临时文件 (以 ~$ 开头)
                if f.name.startswith('~$'):
                    continue
                
                # 3. 模糊匹配 (忽略大小写)
                # 将文件名和关键字都转为小写进行比对
                if file_name.lower() in f.name.lower():
                    candidates.append(f)
            
            if not candidates:
                logging.warning(f"在 '{directory}' 中未找到包含 '{file_name}' 的 {suffix} 文件。")
                return None

            # 4. 按修改时间排序，取最新的
            # 使用 stat().st_mtime 获取最后修改时间戳
            latest_file = max(candidates, key=lambda x: x.stat().st_mtime)
            
            logging.info(f"🔍 锁定目标文件: '{latest_file.name}' (修改时间: {pd.to_datetime(latest_file.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M')})")
            return latest_file

        except Exception as e:
            logging.error(f"寻找文件时发生错误: {e}")
            return None