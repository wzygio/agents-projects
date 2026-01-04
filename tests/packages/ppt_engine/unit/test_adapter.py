import pytest
from unittest.mock import MagicMock, patch, Mock
from queue import Queue
import logging

from packages.ppt_engine.src.adapter import PPTEngineAdapter, QueueLoggingHandler
from packages.ppt_engine.src.config import PptEngineConfig
from tests.factories.ppt_engine_factory import PptEngineConfigFactory


class TestQueueLoggingHandler:
    """测试 QueueLoggingHandler 类的功能"""

    def test_init(self):
        """测试初始化"""
        mock_queue = Queue()
        handler = QueueLoggingHandler(mock_queue)

        assert handler.queue == mock_queue
        assert handler.formatter._fmt == '[%(asctime)s] [PPT] %(message)s' # type: ignore
        assert handler.formatter.datefmt == '%H:%M:%S' # type: ignore

    def test_emit(self):
        """测试发送日志记录"""
        mock_queue = Queue()
        handler = QueueLoggingHandler(mock_queue)

        # 创建日志记录
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )

        # 执行测试
        handler.emit(record)

        # 验证
        assert not mock_queue.empty()
        assert 'Test message' in mock_queue.get()


class TestPPTEngineAdapter:
    """测试 PPTEngineAdapter 类的功能"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.adapter = PPTEngineAdapter()
        self.config_dict = PptEngineConfigFactory.build().dict()
        self.log_queue = Queue()

    @patch('packages.ppt_engine.src.adapter.PPTGenerator')
    @patch('packages.ppt_engine.src.adapter.PptEngineConfig')
    @patch('packages.ppt_engine.src.adapter.logging.getLogger')
    def test_run_success(self, mock_get_logger, mock_config_class, mock_generator_class):
        """测试成功运行适配器"""
        # 设置模拟 Logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        # 模拟当前级别是 WARNING (30)
        mock_logger.level = logging.WARNING
        # 模拟 getEffectiveLevel 也返回 WARNING
        mock_logger.getEffectiveLevel.return_value = logging.WARNING

        # 模拟 Config
        mock_config = MagicMock()
        mock_config_class.from_app_config.return_value = mock_config

        # 模拟 Generator
        mock_generator = MagicMock()
        mock_generator.config.path.output_ppt = 'test.pptx'
        mock_generator_class.return_value = mock_generator

        # 执行测试
        result = self.adapter.run(self.config_dict, self.log_queue)

        # 验证结果
        assert result['status'] == 'success'
        assert 'output_path' in result
        assert result['message'] == 'PPT Generated Successfully'

        # 验证日志处理
        # 关键修正：使用 assert_any_call，允许代码后续恢复日志级别
        mock_logger.setLevel.assert_any_call(logging.INFO)
        mock_logger.addHandler.assert_called()

    @patch('packages.ppt_engine.src.adapter.PPTGenerator')
    @patch('packages.ppt_engine.src.adapter.PptEngineConfig')
    @patch('packages.ppt_engine.src.adapter.logging.getLogger')
    def test_run_error(self, mock_get_logger, mock_config_class, mock_generator_class):
        """测试运行适配器时发生配置错误"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_logger.getEffectiveLevel.return_value = logging.WARNING

        # 模拟 Config 初始化抛出异常
        mock_config_class.from_app_config.side_effect = Exception("Config Error")

        result = self.adapter.run(self.config_dict, self.log_queue)

        assert result['status'] == 'error'
        assert result['message'] == 'Config Error'

        # 关键修正
        mock_logger.setLevel.assert_any_call(logging.INFO)

    @patch('packages.ppt_engine.src.adapter.PPTGenerator')
    @patch('packages.ppt_engine.src.adapter.PptEngineConfig')
    @patch('packages.ppt_engine.src.adapter.logging.getLogger')
    def test_run_generator_exception(self, mock_get_logger, mock_config_class, mock_generator_class):
        """测试生成器运行时发生异常"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_logger.getEffectiveLevel.return_value = logging.WARNING

        mock_config = MagicMock()
        mock_config_class.from_app_config.return_value = mock_config

        # 模拟 Generator.run 抛出异常
        mock_generator = MagicMock()
        mock_generator.run.side_effect = Exception("Generator Error")
        mock_generator_class.return_value = mock_generator

        result = self.adapter.run(self.config_dict, self.log_queue)

        assert result['status'] == 'error'
        assert result['message'] == 'Generator Error'

        # 关键修正
        mock_logger.setLevel.assert_any_call(logging.INFO)

    @patch('packages.ppt_engine.src.adapter.PPTGenerator')
    @patch('packages.ppt_engine.src.adapter.PptEngineConfig')
    @patch('packages.ppt_engine.src.adapter.logging.getLogger')
    def test_run_logs(self, mock_get_logger, mock_config_class, mock_generator_class):
        """测试运行适配器时的日志记录"""
        # 设置模拟
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_logger.level = logging.WARNING

        mock_config = MagicMock()
        mock_config_class.from_app_config.return_value = mock_config

        mock_generator = MagicMock()
        mock_generator.output_dir = MagicMock()
        mock_generator.config.path.output_ppt = 'test.pptx'
        mock_generator_class.return_value = mock_generator

        # 执行测试
        self.adapter.run(self.config_dict, self.log_queue)

        # 验证日志队列中的消息
        messages = []
        while not self.log_queue.empty():
            messages.append(self.log_queue.get())

        assert any("PPT 自动化引擎启动" in msg for msg in messages)
        assert any("正在解析配置上下文" in msg for msg in messages)
        assert any("初始化核心生成器" in msg for msg in messages)
        assert any("开始执行生成流程" in msg for msg in messages)
        assert any("PPT 生成完毕" in msg for msg in messages)
