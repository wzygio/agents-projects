import pytest
import pandas as pd
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, date
from openpyxl import Workbook
from packages.ppt_engine.src.infrastructure.excel_reader import ExcelReader

class TestExcelReader:
    
    def test_read_table_as_dataframe_integration(self, tmp_path):
        """
        [集成测试] 验证从指定范围读取 DataFrame (对应源码 read_table_as_dataframe)
        """
        # 1. 准备真实的 Excel 文件
        file_path = tmp_path / "test_data.xlsx"
        # 创建一个包含数据的 DataFrame
        df_source = pd.DataFrame({
            'Header1': ['A', 'B'],
            'Header2': [1, 2]
        })
        # pandas to_excel 默认从 A1 开始，Header 在第 1 行
        df_source.to_excel(file_path, index=False, sheet_name="Sheet1")
        
        # 2. 初始化 SUT
        # 使用上下文管理器 (with) 来测试 __enter__ / __exit__
        with ExcelReader(str(file_path), "Sheet1") as reader:
            # 3. 读取范围 (A1:B3 -> 包括表头和两行数据)
            result_df = reader.read_table_as_dataframe("A1:B3")
            
            # 4. 验证
            assert result_df is not None
            assert not result_df.empty
            assert list(result_df.columns) == ['Header1', 'Header2']
            assert len(result_df) == 2
            assert result_df.iloc[0]['Header1'] == 'A'

    def test_read_date_specific_data_integration(self, tmp_path):
        """
        [集成测试] 验证按日期筛选数据 (对应源码 read_date_specific_data)
        """
        # 1. 准备含日期列的数据
        today = datetime.now().date()
        file_path = tmp_path / "date_data.xlsx"
        df = pd.DataFrame({
            '通报日期': [today, date(2020, 1, 1)],
            'Value': ['Today', 'Old']
        })
        df.to_excel(file_path, index=False, sheet_name="Sheet1")
        
        # 2. 读取
        with ExcelReader(str(file_path), "Sheet1") as reader:
            # 目标日期设为今天
            filtered_df = reader.read_date_specific_data(target_date=today)
            
            # 3. 验证
            assert len(filtered_df) == 1
            assert filtered_df.iloc[0]['Value'] == 'Today'

    def test_locate_anchors_integration(self, tmp_path):
        """
        [集成测试] 验证锚点定位 (对应源码 locate_anchors)
        """
        file_path = tmp_path / "anchors.xlsx"
        # 构造数据：在 B 列放锚点
        # A列占位，B列数据
        wb = Workbook()
        ws = wb.active
        if ws is not None:
            ws.title = "Sheet1"
            ws['B2'] = "Anchor1"
            ws['B5'] = "Anchor2"
            wb.save(file_path)

        
        with ExcelReader(str(file_path), "Sheet1") as reader:
            anchors = reader.locate_anchors(['Anchor1', 'Anchor2'], 'B')
            
            assert anchors['Anchor1'] == 'B2'
            assert anchors['Anchor2'] == 'B5'

    def test_convert_to_parquet_integration(self, tmp_path):
        """
        [集成测试] 验证静态方法 convert_to_parquet
        """
        file_path = tmp_path / "source.xlsx"
        output_parquet = tmp_path / "output.parquet"
        
        # 准备带 object 列的数据 (测试清洗逻辑)
        df = pd.DataFrame({'Num': [1], 'Text': ['hello']})
        df.to_excel(file_path, index=False, sheet_name="Sheet1")
        
        # 调用静态方法
        ExcelReader.convert_to_parquet(str(file_path), "Sheet1", str(output_parquet))
        
        assert output_parquet.exists()
        # 验证能读回来
        df_loaded = pd.read_parquet(output_parquet)
        assert len(df_loaded) == 1

    def test_read_sentences_integration(self, tmp_path):
        """
        [集成测试] 验证 read_sentences
        """
        file_path = tmp_path / "sentences.xlsx"
        wb = Workbook()
        ws = wb.active
        if ws is not None:
            ws.title = "Sheet1"
            ws['A1'] = "Hello\nWorld" # 测试去换行
            ws['B2'] = "Simple"
            wb.save(file_path)
        
        with ExcelReader(str(file_path), "Sheet1") as reader:
            mapping = {'Key1': 'A1', 'Key2': 'B2'}
            sentences = reader.read_sentences(mapping)
            
            # 验证换行符被去除
            assert sentences['Key1'] == "HelloWorld" 
            assert sentences['Key2'] == "Simple"

    def test_init_file_not_found(self):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            ExcelReader("non_existent.xlsx", "Sheet1")

    def test_init_sheet_not_found(self, tmp_path):
        """测试 Sheet 不存在"""
        file_path = tmp_path / "empty.xlsx"
        pd.DataFrame().to_excel(file_path, sheet_name="Sheet1")
        
        with pytest.raises(KeyError):
            ExcelReader(str(file_path), "GhostSheet")