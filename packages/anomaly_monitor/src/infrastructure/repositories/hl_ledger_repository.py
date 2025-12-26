import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
from copy import copy
import logging
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# 请确保 AnomalyMonitorConfig 中定义了 LedgerConfig 类，或者它是通用的
from packages.anomaly_monitor.src.config import LedgerConfig 
from packages.common_utils.src.utils.misc import Utils

logger = logging.getLogger(__name__)

class HLLedgerRepository:
    """
    【基础设施层】HL 台账写入仓储 (依赖注入版)
    
    职责：
    1. 接收明确的配置对象，不再自己去查全局配置。
    2. 负责向 Excel 追加记录。
    """
    
    def __init__(self, config: LedgerConfig):
        """
        :param config: 具体的 LedgerConfig 对象 (包含 path, sheet_name, mapping 等)
        """
        if not config:
            raise ValueError("HLLedgerRepository requires a valid LedgerConfig object.")

        self.config = config
        
        # 1. 解析路径 (Path Resolution)
        raw_path = self.config.path
        file_name = self.config.file_name
        
        if raw_path:
            p = Path(raw_path)
            if p.is_file():
                # 如果配置的是具体文件
                self.file_path = p
            else:
                # 如果是目录，则搜索最新匹配文件
                self.file_path = Utils.find_latest_matching_file(p, str(file_name))
        else:
            self.file_path = None
            logger.warning("⚠️ HL Ledger Path not configured.")

        # 2. 解析其他参数
        self.sheet_name = self.config.sheet_name or "Sheet1"
        self.mapping = self.config.mapping or {}
        
        if not self.mapping:
            logger.warning("⚠️ 未配置 HL 台账的列映射 (mapping)，写入可能无法进行。")

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

            # 3. 计算真实的起始行
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
                        
                        # 4.2 格式继承 (Style Copy)
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
        """[辅助] 获取真实的最后一行数据行号"""
        try:
            if ws.max_row <= 1: return ws.max_row
            for row in range(ws.max_row, 0, -1):
                for cell in ws[row]:
                    if cell.value is not None:
                        return row
            return 1
        except Exception as e:
            logger.warning(f"真实行探测失败，回退到默认 max_row: {e}")
            return ws.max_row

    def _copy_cell_style(self, source_cell, target_cell):
        """[辅助] 复制单元格样式"""
        try:
            if source_cell.has_style:
                target_cell.font = copy(source_cell.font)
                target_cell.border = copy(source_cell.border)
                target_cell.fill = copy(source_cell.fill)
                target_cell.number_format = copy(source_cell.number_format)
                target_cell.protection = copy(source_cell.protection)
                target_cell.alignment = copy(source_cell.alignment)
        except Exception:
            pass

    def _verify_write(self, coords: str, expected_val) -> bool:
        """[辅助] 回读验证"""
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
        """检查文件状态"""
        if not self.file_path: return False, "❌ 文件路径未初始化"
        if not self.file_path.exists(): return False, f"❌ 文件不存在: {self.file_path}"
        try:
            with open(self.file_path, 'a'): pass
            return True, f"✅ 文件就绪: {self.file_path.name}"
        except PermissionError: return False, f"❌ 文件被占用: {self.file_path.name}"
        except Exception as e: return False, f"❌ 检查失败: {str(e)}"