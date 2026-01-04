import pytest
import logging
import subprocess
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from packages.ppt_engine.src.utils.local_utils import Utils

class TestUtils:

    def test_normalize_string_logic(self):
        """
        测试字符串标准化逻辑 (根据源码：只去空格，不转小写)
        """
        # Case 1: 包含空格 -> 去除空格
        assert Utils.normalize_string("Hello World") == "HelloWorld"
        
        # Case 2: 包含换行符 -> 去除
        assert Utils.normalize_string("A\nB") == "AB"
        
        # Case 3: 全角字符标准化 (NFKC)
        # 例如：全角数字 '１' 应该变成半角 '1'
        assert Utils.normalize_string("１２３") == "123"
        
        # Case 4: None -> "none"
        assert Utils.normalize_string(None) == "none"

    def test_find_latest_matching_file_integration(self, tmp_path):
        """
        [集成测试] 验证文件查找功能 (真实文件系统)
        """
        # 1. 准备环境
        # 创建文件
        file_old = tmp_path / "report_old.xlsx"
        file_old.touch()
        # 修改 mtime (过去)
        os.utime(file_old, (1000, 1000))

        file_new = tmp_path / "report_new.xlsx"
        file_new.touch()
        # 修改 mtime (现在)
        os.utime(file_new, (2000, 2000))
        
        # 创建干扰项 (临时文件)
        file_temp = tmp_path / "~$report_temp.xlsx"
        file_temp.touch()
        os.utime(file_temp, (3000, 3000)) # 虽然最新，但逻辑优先选普通文件

        # 2. 执行查找 (找 "report")
        result = Utils.find_latest_matching_file(tmp_path, "report")

        # 3. 验证
        # 逻辑是：优先找普通文件。如果有普通文件，返回最新的普通文件。
        # 所以应该返回 report_new.xlsx，而不是 ~$report_temp.xlsx
        assert result is not None
        assert result.name == "report_new.xlsx"

    def test_find_latest_matching_file_temp_fallback(self, tmp_path):
        """
        [集成测试] 验证只有临时文件时的回退逻辑
        """
        # 只有临时文件
        file_temp = tmp_path / "~$report_temp.xlsx"
        file_temp.touch()
        
        result = Utils.find_latest_matching_file(tmp_path, "report")
        
        # 逻辑：如果没有普通文件，使用临时文件，并去掉 ~$ 前缀
        assert result is not None
        assert result.name == "report_temp.xlsx"

    @patch('packages.ppt_engine.src.utils.local_utils.subprocess.run')
    def test_safe_copy_file_mock_robocopy(self, mock_run, tmp_path):
        """
        [Mock测试] 验证 Robocopy 调用逻辑
        由于 robocopy 是外部命令，我们 Mock 它的执行结果来验证 Python 逻辑。
        """
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.touch() # 必须存在，否则 safe_copy 直接返回 False
        
        # 模拟 robocopy 成功 (返回码 1)
        mock_run.return_value.returncode = 1
        
        # 我们需要手动创建 dst 文件来模拟 robocopy 的副作用，
        # 否则 safe_copy 会检查 dst 是否存在，如果不存在会报错
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.touch()
        with open(dst, 'w') as f: f.write('dummy content')

        result = Utils.safe_copy_file(src, dst)
        
        assert result is True
        # 验证调用了 robocopy
        mock_run.assert_called()
        args = mock_run.call_args[0][0]
        assert 'robocopy' in args
        assert '/B' in args # 验证关键参数

    def test_setup_logging_smoke(self, tmp_path):
        """
        [冒烟测试] 验证 setup_logging 能够运行且不报错
        """
        log_file = tmp_path / "test.log"
        try:
            # 临时把日志目录指向 tmp_path
            Utils.setup_logging(log_dir=tmp_path, log_filename="test.log")
            
            # 验证日志文件被创建
            assert log_file.exists()
            
            # 验证 Logger 配置
            root = logging.getLogger()
            assert len(root.handlers) >= 1
            
        except Exception as e:
            pytest.fail(f"setup_logging failed: {e}")
        finally:
            # 清理 handlers 避免影响其他测试
            logging.getLogger().handlers = []