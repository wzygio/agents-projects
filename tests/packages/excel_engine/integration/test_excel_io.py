import pytest
import pandas as pd
from openpyxl import load_workbook, Workbook
from packages.excel_engine.src.infrastructure.excel_io import ExcelHandler

class TestExcelIO:
    
    @pytest.fixture
    def setup_env(self, tmp_path):
        """
        [集成环境搭建]
        1. 创建测试目录
        2. 生成一个真实的 Excel 模板文件 (包含多 Sheet)
        """
        test_dir = tmp_path / "test_excel"
        test_dir.mkdir(exist_ok=True)

        template_path = test_dir / "template.xlsx"
        
        # 创建真实文件，包含数据和多个 Sheet
        wb = Workbook()
        ws1 = wb.active
        if ws1 is None:
            raise Exception("Workbook active sheet is None")
        ws1.title = "Sheet1"
        ws1["A1"] = "Initial Data"
        
        ws2 = wb.create_sheet("Sheet2")
        ws2["B2"] = "Sheet2 Data"
        
        wb.save(template_path)

        return {
            "root": test_dir,
            "template_path": str(template_path), # ExcelHandler 接收 str
            "output_path": str(test_dir / "output.xlsx"),
            "new_file_path": str(test_dir / "new_created.xlsx")
        }

    def test_load_template_success(self, setup_env):
        """测试加载模板"""
        handler = ExcelHandler(setup_env["template_path"])
        # 必须显式调用 load_template
        handler.load_template()
        
        assert handler.wb is not None
        assert handler.ws is not None
        assert handler.ws.title == "Sheet1" # 默认 active 是第一个

    def test_read_cell(self, setup_env):
        """测试读取单元格"""
        handler = ExcelHandler(setup_env["template_path"])
        handler.load_template()
        
        # 验证读取
        val = handler.read_cell("A1")
        assert val == "Initial Data"

    def test_write_cell_and_save(self, setup_env):
        """测试写入单元格并保存"""
        handler = ExcelHandler(setup_env["template_path"])
        handler.load_template()
        
        # 写入新值
        handler.write_cell("C3", "New Value")
        
        # 保存到新路径
        output_path = setup_env["output_path"]
        handler.save(output_path)
        
        # 验证保存结果 (读取保存后的文件进行验证)
        check_wb = load_workbook(output_path)
        assert check_wb["Sheet1"]["C3"].value == "New Value"
        check_wb.close()

    def test_set_active_sheet(self, setup_env):
        """测试切换工作表"""
        handler = ExcelHandler(setup_env["template_path"])
        handler.load_template()
        
        # 切换到 Sheet2
        handler.set_active_sheet("Sheet2")
        if handler.ws is None:
            raise Exception("切换工作表后，工作表对象为 None")
        assert handler.ws.title == "Sheet2"
        
        # 验证能读到 Sheet2 的数据
        assert handler.read_cell("B2") == "Sheet2 Data"

    def test_write_data_dataframe(self, setup_env):
        """测试写入 DataFrame 数据"""
        handler = ExcelHandler(setup_env["template_path"])
        handler.load_template()
        
        # 准备 DataFrame
        df = pd.DataFrame({
            'Col1': [1, 2],
            'Col2': ['A', 'B']
        })
        
        # 写入 (注意：write_data 接收的是 data 对象，且遍历 data.values)
        # 从第 5 行，第 1 列开始写
        handler.write_data(df, start_row=5, start_col=1)
        handler.save(setup_env["output_path"])
        
        # 验证
        check_wb = load_workbook(setup_env["output_path"])
        ws = check_wb["Sheet1"]
        # write_data 逻辑: row=5 -> values[0] -> [1, 'A']
        assert ws.cell(row=5, column=1).value == 1
        assert ws.cell(row=5, column=2).value == 'A'
        assert ws.cell(row=6, column=1).value == 2
        check_wb.close()

    def test_create_new_file(self, setup_env):
        """测试创建新文件功能"""
        handler = ExcelHandler() # 不需要模板路径
        
        target_path = setup_env["new_file_path"]
        handler.create_new_file(target_path, "Created Content", "D4")
        
        # 验证文件存在且内容正确
        check_wb = load_workbook(target_path)
        if check_wb.active is None:
            raise Exception("新创建的文件没有活动工作表")
        assert check_wb.active["D4"].value == "Created Content"
        check_wb.close()

    def test_error_handling(self):
        """测试异常处理"""
        # 测试文件不存在
        handler = ExcelHandler("non_existent.xlsx")
        with pytest.raises(ValueError, match="加载模板文件时出错"):
            handler.load_template()
            
        # 测试未加载时操作
        handler = ExcelHandler("dummy.xlsx")
        with pytest.raises(ValueError, match="请先加载模板文件"):
            handler.read_cell("A1")