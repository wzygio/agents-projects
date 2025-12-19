# 文件路径：src\excel_generator_project\style_generator.py
import logging
import sys
import os
from pathlib import Path

from excel_generator_project.config import CONFIG, TEMP_PATH, OUTPUT_PATH
from excel_generator_project.config import CONFIG
from packages.excel_engine.src.utils.local_utils import Utils
from packages.excel_engine.src.core.font_processor import FontProcessor

class RefineStylesUseCase:
    def __init__(self, config: dict):
        self.config = config

    def execute(self, input_path: Path, output_path: Path):
        # 调度 FontProcessor (Core)
        processor = FontProcessor(
            template_path=input_path, 
            output_path=output_path, 
            config=self.config
        )
        processor.run()