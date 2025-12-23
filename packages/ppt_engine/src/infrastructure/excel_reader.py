import logging
import pandas as pd
import datetime as dt

from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, Optional, Union, List

# 导入openpyxl相关的模块
from openpyxl import load_workbook
from functools import singledispatch
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import column_index_from_string, range_boundaries

class ExcelReader:
    """
    一个用于读取Excel文件中特定内容的类。
    初始化时打开一个工作簿和工作表，后续方法都基于此进行操作。
    """

    def __init__(self, excel_path: str, sheet_name: str):
        """
        构造函数，在实例化时打开Excel文件和指定的工作表。
        这部分逻辑来自您的 load_sheet 函数。
        """
        self.excel_path = excel_path 
        self.sheet_name = sheet_name
        try:
            # data_only=True 表示只读取单元格的计算结果值，而不是公式本身
            self.wb = load_workbook(excel_path, data_only=True)
            self.ws: Worksheet = self.wb[sheet_name]
            logging.info(f"成功打开Excel文件 '{excel_path}' 的工作表 '{sheet_name}'")
        except FileNotFoundError:
            logging.error(f"Excel文件未找到: {excel_path}")
            raise
        except KeyError:
            logging.error(f"在文件 '{excel_path}' 中未找到名为 '{sheet_name}' 的工作表")
            raise

    # =================== 新增：上下文管理器协议 ===================
    def __enter__(self):
        """进入 with 语句块时返回实例自身"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 语句块时自动调用 close 方法"""
        self.close()
    # ==========================================================

    def locate_anchors(self, anchor_texts: List[str], search_column: str) -> Dict[str, str]:
        """
        在指定列中扫描工作表，查找所有“锚点”文本并返回它们的位置。

        :param anchor_texts: 需要查找的文本列表 (例如 ['直板LTPS', '折叠'])。
        :param search_column: 要在哪一列进行查找 (例如 'B')。
        :return: 一个字典，键是找到的锚点文本，值是它所在的单元格地址 (例如 {'直板LTPS': 'B4', '折叠': 'B20'})。
        """
        logging.info(f"开始在工作表 '{self.sheet_name}' 的 {search_column} 列中查找锚点...")
        found_anchors: Dict[str, str] = {}
        texts_to_find = set(anchor_texts) # 使用集合以提高查找效率

        # 遍历指定列中的所有单元格
        for cell in self.ws[search_column]:
            if cell.value in texts_to_find:
                anchor_text = cell.value
                anchor_coordinate = cell.coordinate
                
                found_anchors[anchor_text] = anchor_coordinate
                logging.info(f"  > 找到锚点: '{anchor_text}' -> 位置: {anchor_coordinate}")
                
                # 从待查找集合中移除已找到的，以提高效率
                texts_to_find.remove(anchor_text)
                # 如果全部找到了，就提前结束循环
                if not texts_to_find:
                    break
        
        if texts_to_find:
            logging.warning(f"未能找到以下锚点: {list(texts_to_find)}")
            
        logging.info(f"锚点定位完成，共找到 {len(found_anchors)} / {len(anchor_texts)} 个。")
        return found_anchors

    def read_images(self, output_dir: str, mapping: Dict[str, str]) -> Dict[str, str]:
        """
        把当前 worksheet 里所有浮动图片导出到 output_dir，
        并返回一个以类别为键，以保存路径为值的字典。

        :param output_dir: 图片保存的目标文件夹。
        :param mapping: 一个字典，键是类别名(如'直板LTPS')，值是单元格地址(如'C3')。
        :return: 一个字典，键是类别名，值是图片保存的绝对路径。
        """
        saved_paths_dict = {}
        # _images 是 openpyxl 的一个内部属性，用于访问所有图片
        all_images_in_sheet = self.ws._images # type: ignore
        if not all_images_in_sheet:
            logging.warning("在当前工作表中未发现任何图片。")
            return saved_paths_dict
        
        # 1. 为了提高效率，我们先预处理一遍所有图片的位置
        # 创建一个以单元格地址为键，图片对象为值的新字典
        image_locations = {}
        for img in all_images_in_sheet:
            row = img.anchor._from.row + 1
            col = img.anchor._from.col + 1
            addr = f"{get_column_letter(col)}{row}"
            image_locations[addr] = img

        # 2. 遍历我们传入的、以类别为键的 mapping 字典
        for category, target_addr in mapping.items():
            # 3. 在预处理好的图片位置中，查找这张图片
            target_image = image_locations.get(target_addr)
            
            if target_image:
                # 如果找到了图片，就保存它
                filename = f"{category}.png"
                save_path = Path(output_dir) / filename
                
                Path(output_dir).mkdir(exist_ok=True)

                with open(save_path, 'wb') as f:
                    f.write(target_image._data())
                
                # 将图片的类别名和它对应的保存路径存入返回字典
                saved_paths_dict[category] = str(save_path)
            else:
                # 如果在指定单元格找不到图片，打印一个警告
                logging.warning(f"未能在单元格 '{target_addr}' 找到期望的图片 (类别: '{category}')。")
        
        logging.info(f"图片抓取成功，共 {len(saved_paths_dict)} 张，已存入：{output_dir}")
        return saved_paths_dict

    def read_sentences(self, mapping: Dict[str, str]) -> Dict[str, str]:
        """
        从当前工作表里，按 mapping 读出每个地址的单元格文本。
        
        :param mapping: 一个字典，键是内容的类别名，值是单元格地址(如'B2')。
        :return: 一个字典，键是类别名，值是单元格中的文本。
        """
        sentences = {}
        for category, addr in mapping.items():
            # 直接取单元格的值，对于合并单元格，openpyxl会自动返回左上角单元格的值
            text = self.ws[addr].value
            # 处理None值和去除换行符
            if text is not None:
                text = str(text).replace('\n', '').replace('\r', '')
            sentences[category] = text if text is not None else '' # 如果单元格为空，返回空字符串
        
        logging.info(f"汇总语句抓取成功，共 {len(sentences)} 条。")
        return sentences



    # 对应您原有的 read_excel_range_from_worksheet 函数，返回二维列表
    def read_table_as_list(self, cell_range: str) -> Optional[List[List[Any]]]:
        """
        [实例方法] 从当前工作表(self.ws)的指定范围读取数据，并返回一个二维列表。
        """
        logging.info(f"从Worksheet实例的范围'{cell_range}'读取表格，返回二维列表。")
        try:
            data_matrix = [[cell.value for cell in row] for row in self.ws[cell_range]]

            if not data_matrix:
                logging.warning(f"在范围 {cell_range} 内没有找到任何数据。")
                return None
                
            return data_matrix
        except Exception as e:
            logging.error(f"从Worksheet对象提取数据为List时出错: {e}")
            return None
        
    @staticmethod
    def read_excel_range(
        excel_path: str,
        sheet_name: str,
        cell_range: str,
        columns_to_read: Optional[Union[List[str], List[int]]] = None
    ) -> Optional[pd.DataFrame]:
        """[静态方法] 直接从文件路径高效读取一个范围的数据，返回DataFrame。"""
        # ... (此方法逻辑来自您之前的 _from_path 函数) ...
        try:
            # ... (完整的实现代码) ...
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            if min_row is None or max_row is None:
                logging.warning(f"无法从范围 '{cell_range}' 中确定明确的行边界。")
                return None
            
            header_row_index = min_row - 1
            num_data_rows = max_row - min_row
            if num_data_rows < 0: return None

            df = pd.read_excel(
                excel_path, sheet_name=sheet_name, header=header_row_index,
                usecols=columns_to_read, nrows=num_data_rows
            )
            return df
        except Exception as e:
            logging.error(f"从路径读取表格时发生错误: {e}")
            return None
    
    @staticmethod
    def convert_to_parquet(source_excel_path: str, sheet_name: str, dest_parquet_path: str):
        """
        [静态工具方法] 读取指定的Excel工作表，进行数据清洗，并将其保存为Parquet格式。
        """
        logging.info(f"开始将 '{source_excel_path}' 转换为Parquet格式...")
        try:
            # 1. 读取Excel
            df = pd.read_excel(source_excel_path, sheet_name=sheet_name)
            
            # 2. 【核心】根据我们的诊断结果，一次性清洗所有object类型的列
            cols_to_clean = df.select_dtypes(include=['object']).columns
            
            if not cols_to_clean.empty:
                logging.info(f"发现 {len(cols_to_clean)} 个object类型列，将统一转换为字符串...")
                for col in cols_to_clean:
                    df[col] = df[col].astype(str)
            
            # 3. 保存为Parquet格式
            df.to_parquet(dest_parquet_path, index=False)
            logging.info(f"文件已成功转换为Parquet格式，并保存至: {dest_parquet_path}")

        except FileNotFoundError:
            logging.error(f"源Excel文件未找到: {source_excel_path}")
            raise # 重新抛出异常，让上层调用者知道发生了错误
        except Exception as e:
            logging.error(f"在转换为Parquet时发生未知错误: {e}")
            raise # 重新抛出异常
        
    ############## --- 其它备用方法（目前没有被使用） --- ##############
    def read_table_as_dataframe(self, cell_range: str) -> Optional[pd.DataFrame]:
        """
        [实例方法] 从当前工作表(self.ws)的指定范围读取数据，并返回一个DataFrame。
        """
        logging.info(f"从Worksheet实例的范围'{cell_range}'读取表格，返回DataFrame。")
        try:
            range_cells = self.ws[cell_range]
            data_matrix = [[cell.value for cell in row] for row in range_cells]

            if not data_matrix or not data_matrix[0]:
                logging.warning(f"在范围 {cell_range} 内没有找到任何数据。")
                return None

            columns = data_matrix[0]
            data = data_matrix[1:]
            df = pd.DataFrame(data, columns=columns)
            return df
        except Exception as e:
            logging.error(f"从Worksheet对象提取数据为DataFrame时出错: {e}")
            return None
        
    def read_range_as_dataframe(self, cell_range: str) -> Optional[pd.DataFrame]:
        """
        [实例方法] 从当前已打开的工作表(self.ws)的指定范围读取数据，并返回一个DataFrame。
        (此功能来自您原始的 _from_worksheet)
        """
        logging.info(f"从Worksheet实例的范围'{cell_range}'读取表格，返回DataFrame。")
        try:
            range_cells = self.ws[cell_range]
            data_matrix = [[cell.value for cell in row] for row in range_cells]
            if not data_matrix or not data_matrix[0]: return None
            
            df = pd.DataFrame(data_matrix[1:], columns=data_matrix[0])
            return df
        except Exception as e:
            logging.error(f"从Worksheet对象提取数据为DataFrame时出错: {e}")
            return None
        
    def read_date_specific_data(
        self,
        target_date: Optional[date] = None,
        date_column_name: str = '通报日期' # 【重要修改】我们现在按列名而不是列字母来操作，更稳健
    ) -> pd.DataFrame:
        """
        [高性能版] 从当前工作表中，高效读取当日的连续数据块。
        利用Pandas进行全表读取和快速筛选。
        """
        if target_date is None:
            target_date = datetime.now().date()
        
        logging.info(f"使用pandas高性能模式读取并筛选工作表 '{self.sheet_name}'...")
        
        try:
            # 1. 使用pandas直接从已打开的工作簿中读取整个工作表
            #    engine='openpyxl' 确保它能处理我们已经打开的wb对象
            #    我们假设第一行是表头
            full_df = pd.read_excel(self.wb, sheet_name=self.sheet_name, engine='openpyxl')

            # 2. 健壮性检查：确认日期列存在
            if date_column_name not in full_df.columns:
                logging.error(f"工作表中未找到指定的日期列: '{date_column_name}'")
                return pd.DataFrame()

            # 3. 将日期列转换为datetime对象，以便正确比较
            #    errors='coerce' 会让所有无法转换的日期变成 NaT (Not a Time)
            full_df[date_column_name] = pd.to_datetime(full_df[date_column_name], errors='coerce')

            # 4. 【核心】执行高性能的日期筛选
            #    .dt.date 会提取出日期部分，然后与我们的目标日期进行比较
            #    这会返回一个布尔值的Series，用于索引
            mask = (full_df[date_column_name].dt.date == target_date) # type: ignore
            
            # 5. 使用这个掩码来选取所有符合条件的行
            daily_df = full_df[mask]
            
            logging.info(f"成功筛选到 {len(daily_df)} 行日期为 {target_date} 的数据。")
            return daily_df

        except Exception as e:
            logging.error(f"使用pandas高性能模式读取数据时发生错误: {e}", exc_info=True)
            return pd.DataFrame()
        
    def close(self):
        """关闭工作簿以释放资源。"""
        if self.wb:
            self.wb.close()
            logging.info(f"Excel工作簿 '{self.excel_path}' 已关闭。")