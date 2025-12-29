# 文件路径：packages\excel_engine\src\application\style_renderer.py
from pathlib import Path

from packages.excel_engine.src.utils.local_utils import Utils
from packages.excel_engine.src.infrastructure.processor.font_processor import FontProcessor

class RefineStylesUseCase:
    def __init__(self, config):
        self.config = config

    def execute(self, input_path: Path, output_path: Path):
        # 调度 FontProcessor (Core)
        processor = FontProcessor(
            template_path=input_path, 
            output_path=output_path, 
            config=self.config
        )
        processor.run()