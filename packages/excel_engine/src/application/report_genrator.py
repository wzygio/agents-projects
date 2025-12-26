# 文件路径：src\excel_generator_project\content_generator.py
import logging
import sys
import os
from pathlib import Path

from packages.excel_engine.src.config import ExcelEngineConfig
from packages.excel_engine.src.infrastructure.processor.data_processor import DataProcessor
from packages.excel_engine.src.infrastructure.processor.exception_processor import ExceptionProcessor
from packages.excel_engine.src.infrastructure.processor.report_processor import ReportGenerator

class GenerateReportUseCase:
    def __init__(self, config: ExcelEngineConfig):  # 修改参数类型注解
    # 使用配置对象
        self.config = config

    def execute(self, template_path: Path, output_path: Path):
        """
        执行报告生成的标准用例 (不含环境变量读取，只含逻辑)
        """
        logging.info("===== [Application] 开始执行生成用例 =====")
        
        # 1. 运行核心处理 (Core)
        exception_processor = ExceptionProcessor(self.config)
        exception_results = exception_processor.run()
        
        data_processor = DataProcessor(self.config, exception_results)
        data_results = data_processor.run()
        
        # 2. 组装数据
        generator_config = self.config.copy()
        generator_config['EXTERNAL_DATA'] = {
            'exceptions_data': exception_results,
            'yield_data': data_results
        }
        
        # 3. 调用基础设施写入 (Infra)
        report_writer = ReportGenerator(
            template_path=template_path,
            output_path=output_path,
            config=generator_config
        )
        report_writer.run()
