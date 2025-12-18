import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
from copy import copy
import logging
import os
from pathlib import Path
from typing import List, Dict, Tuple

# 引入配置加载器
from src.config import config
from src.common.utils.utils import Utils

logger = logging.getLogger(__name__)

class HLLedgerRepository:
    """
    【基础设施层】HL 台账写入仓储 (终极增强版)
    
    修复点：
    1. 解决 max_row 虚高导致的“幽灵空行”问题。
    2. 解决新写入行格式丢失问题 (自动继承上一行格式)。
    3. 保留动态文件查找与回读验证。
    """
    
    def __init__(self, config_key: str = "daily_report.hl_ledger"):
        self.config = config
        
        # 1. 获取配置
        conf = self.config.get(config_key, {})
        if conf is None:
            logger.warning("⚠️ 未找到 HL 台账配置，使用默认值")
            conf = {}

        # 动态查找文件
        raw_path = conf.get("path")
        file_name = conf.get("file_name") # 增加默认文件名
        
        # 如果配置里直接给了完整路径，就尝试分离目录和文件名，或者直接用 find_latest
        if raw_path:
            p = Path(raw_path)
            if p.is_file():
                # 如果配置的就是具体文件，直接用
                self.file_path = p
            else:
                # 如果是目录，则搜索
                self.file_path = Utils.find_latest_matching_file(p, str(file_name))
        else:
            self.file_path = None

        self.sheet_name = conf.get("sheet_name", "Sheet1")
        self.mapping = conf.get("mapping", {}) 
        
        if not self.mapping:
            logger.warning("⚠️ 未配置 HL 台账的列映射 (hl_ledger.mapping)，写入可能无法进行。")

    def append_records(self, records: List[Dict]) -> Tuple[bool, str]:
        if not records:
            return True, "没有需要写入的数据"

        # 1. 路径检查
        if not self.file_path or not self.file_path.exists():
            return False, f"❌ 文件路径无效或文件不存在: {self.file_path}"

        wb = None
        try:
            logger.info(f"📂 [Ledger] 正在打开文件: {self.file_path}")
            # data_only=False 必须保留，否则读取时会丢失公式
            wb = openpyxl.load_workbook(self.file_path, keep_vba=False, data_only=False)
            
            # 2. Sheet 检查
            if self.sheet_name not in wb.sheetnames:
                actual_sheet = wb.sheetnames[0]
                logger.warning(f"⚠️ Sheet '{self.sheet_name}' 不存在，将写入第一个 Sheet: '{actual_sheet}'")
                ws = wb[actual_sheet]
            else:
                ws = wb[self.sheet_name]

            # 3. [修复] 计算真实的起始行 (Real Max Row)
            # 不再盲目信任 ws.max_row，而是通过探测去除尾部空行
            real_max_row = self._get_real_max_row(ws)
            start_row = real_max_row + 1
            
            logger.info(f"📍 [Ledger] 探测到真实数据结束于第 {real_max_row} 行，将从第 {start_row} 行写入")
            
            last_check_coords = None
            last_check_value = None

            # 4. 写入数据
            for i, record in enumerate(records):
                current_row = start_row + i
                
                for col_letter, field_key in self.mapping.items():
                    if field_key in record:
                        val = record[field_key]
                        
                        # 定位目标单元格
                        target_cell = ws[f"{col_letter}{current_row}"]
                        
                        # 4.1 写入值
                        target_cell.value = val
                        
                        # 4.2 [修复] 格式继承 (Style Copy)
                        # 尝试从上一行 (current_row - 1) 的同一列复制格式
                        # 只有当上一行不是表头(行号>1)时才复制
                        if current_row > 2:
                            source_cell = ws[f"{col_letter}{current_row - 1}"]
                            self._copy_cell_style(source_cell, target_cell)
                        
                        # 记录验证点
                        last_check_coords = f"{col_letter}{current_row}"
                        last_check_value = val

            # 5. 保存文件
            wb.save(self.file_path)
            wb.close() 
            
            # 6. 回读验证
            if last_check_coords:
                if not self._verify_write(last_check_coords, last_check_value):
                    return False, f"❌ 严重错误：写入操作完成但回读验证失败！(行号: {start_row})"
            
            msg = f"✅ 成功写入 {len(records)} 条数据！(写入位置: 第 {start_row} - {start_row + len(records) - 1} 行)"
            logger.info(msg)
            return True, msg

        except PermissionError:
            return False, f"❌ 文件被占用！请关闭 Excel [{self.file_path.name}] 后重试。"
        except Exception as e:
            logger.error(f"❌ 写入异常: {e}", exc_info=True)
            return False, f"写入异常: {str(e)}"
        finally:
            if wb: 
                try: wb.close() 
                except: pass

    def _get_real_max_row(self, ws) -> int:
        """
        [辅助方法] 获取真实的最后一行数据行号
        原理：从 openpyxl 认为的 max_row 开始倒序扫描，直到找到第一个非空行。
        """
        try:
            # 如果表是空的，返回1
            if ws.max_row <= 1:
                return ws.max_row
            
            # 倒序遍历
            for row in range(ws.max_row, 0, -1):
                # 检查该行所有单元格，只要有一个不是 None，就认为是有效行
                # 注意：这里我们只检查 mapping 中涉及的列可能会更快，但全行检查更安全
                for cell in ws[row]:
                    if cell.value is not None:
                        return row
            return 1
        except Exception as e:
            logger.warning(f"真实行探测失败，回退到默认 max_row: {e}")
            return ws.max_row

    def _copy_cell_style(self, source_cell, target_cell):
        """
        [辅助方法] 将源单元格的样式复制给目标单元格
        包括：字体、边框、填充、对齐、数字格式
        """
        try:
            if source_cell.has_style:
                target_cell.font = copy(source_cell.font)
                target_cell.border = copy(source_cell.border)
                target_cell.fill = copy(source_cell.fill)
                target_cell.number_format = copy(source_cell.number_format)
                target_cell.protection = copy(source_cell.protection)
                target_cell.alignment = copy(source_cell.alignment)
        except Exception:
            # 样式复制不是核心功能，出错了不要阻断流程
            pass

    def _verify_write(self, coords: str, expected_val) -> bool:
        """回读验证 (保持不变)"""
        if not self.file_path: return False
        try:
            wb_check = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
            sheet_names = wb_check.sheetnames
            target_sheet_name = self.sheet_name if self.sheet_name in sheet_names else sheet_names[0]
            ws_check = wb_check[target_sheet_name]
            
            actual_val = ws_check[coords].value
            wb_check.close()
            
            if str(actual_val) == str(expected_val): return True
            try:
                if float(actual_val) == float(expected_val): return True
            except: pass
                
            logger.error(f"verify failed: {coords} Expected '{expected_val}' but got '{actual_val}'")
            return False
        except Exception as e:
            logger.warning(f"回读验证出错: {e}")
            return False

    def check_file_status(self) -> Tuple[bool, str]:
        """检查文件状态 (保持不变)"""
        if not self.file_path: return False, "❌ 文件路径未初始化"
        if not self.file_path.exists(): return False, f"❌ 文件不存在: {self.file_path}"
        try:
            with open(self.file_path, 'a'): pass
            return True, f"✅ 文件就绪: {self.file_path.name}"
        except PermissionError: return False, f"❌ 文件被占用: {self.file_path.name}"
        except Exception as e: return False, f"❌ 检查失败: {str(e)}"