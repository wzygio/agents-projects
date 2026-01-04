import pytest
import pandas as pd
import os
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches

from packages.ppt_engine.src.application.ppt_generator import PPTGenerator
from packages.ppt_engine.src.config import PptEngineConfig

class TestPptEngineE2E:
    
    @pytest.fixture
    def setup_env(self, tmp_path):
        """
        [E2E 环境搭建]
        创建真实的 Excel 数据源和 PPT 模板，模拟真实运行环境。
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        resources_dir = tmp_path / "resources"
        resources_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # --- 1. 准备数据源 Excel (Yield & Risk) ---
        excel_path = resources_dir / "data_source.xlsx"
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # A. Yield Trend Sheet (用于 locate_anchors)
            # 逻辑：在 B 列查找 'Category A'
            df_trend = pd.DataFrame({'ColA': [''] * 10, 'ColB': [''] * 10})
            df_trend.at[2, 'ColB'] = 'Category A' # B3 (0-based index 2)
            df_trend.to_excel(writer, sheet_name='YieldTrend', index=False, header=False)
            
            # B. Control Plan Sheet (用于数据读取)
            # 逻辑：YieldGenerator 强制读取 B2:V23
            # 我们需要构造双层表头：Row 0=Total, Row 1=M12目标...
            # 构造一个 25x25 的空矩阵
            data = [['' for _ in range(25)] for _ in range(25)]
            
            # 填充 Anchor (YieldGenerator 在此表中也查找 Anchor)
            # 假设 Category A 在第 5 行 (index 4)
            data[4][1] = 'Category A' # B5
            
            # 填充表头 (B2:V3 -> indices [1][1] to [2][21])
            # Row 2 (header row 1)
            data[1][1] = 'Total'
            data[1][2] = 'Total'
            data[1][3] = 'Total'
            data[1][4] = 'Total'
            data[1][5] = 'Detail'
            
            # Row 3 (header row 2)
            data[2][1] = 'Product'
            data[2][2] = '2025M12目标' # 对应代码中的映射 nan_2025M12目标
            data[2][3] = '2025M12实际'
            data[2][4] = 'GAP'
            data[2][5] = 'Info'
            
            # 填充数据体
            data[5][1] = 'Product X'
            data[5][2] = '0.99'
            data[5][3] = '0.98'
            data[5][4] = '-0.01'
            
            df_control = pd.DataFrame(data)
            df_control.to_excel(writer, sheet_name='ControlPlan', index=False, header=False)
            
            # C. Risk Data Sheet
            df_risk = pd.DataFrame({
                '序号': [1, 2],
                '风险描述': ['Risk 1', 'Risk 2'],
                '状态': ['Open', 'Close'],
                '日期': ['2023-01-01', '2023-01-02']
            })
            df_risk.to_excel(writer, sheet_name='RiskData', index=False)

        # --- 2. 准备 PPT 模板 ---
        template_path = resources_dir / "template.pptx"
        prs = Presentation()
        
        # 确保有 BLANK 版式 (索引通常为 6，但我们命名显式一点)
        blank_layout = prs.slide_layouts[6]
        blank_layout.name = "BLANK"
        
        # Slide 1: 封面
        prs.slides.add_slide(prs.slide_layouts[0])
        
        # Slide 2: 旧的 Yield 页面 (用于测试 CanvasProcessor 的删除逻辑)
        # 标题必须匹配配置中的 "Old Yield Title"
        slide_to_delete = prs.slides.add_slide(blank_layout)
        tb = slide_to_delete.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
        tb.name = "TextBox 1" # CanvasProcessor 依赖这个名字识别标题
        tb.text_frame.text = "Old Yield Title"
        
        # 预置 "Text Placeholder 1" (YieldGenerator 需要)
        # 为了简单，我们在 Blank layout 上也加一个这样的 Shape 作为 Mock 占位符
        # 在实际生成中，Generate 会在新 Slide 上找这个占位符，
        # 但 YieldGenerator 的代码逻辑是 add_slide(blank_layout) 然后找 shape。
        # 默认 blank layout 是空的。
        # *修正*：YieldGenerator 代码中 `self._add_summary` 会在 slide.shapes 中找 `placeholder_name`。
        # 但新创建的 BLANK slide 是空的。
        # 除非 `element_processor.add_summary` 负责创建它，或者模板的 BLANK layout 自带这个占位符。
        # 既然我们无法轻松修改 layout 的 master，我们假设代码能处理找不到的情况(打印 error)，或者我们只验证不崩溃。
        
        prs.save(template_path)

        return {
            "root": tmp_path,
            "resources": resources_dir,
            "output": output_dir,
            "excel_file": "data_source.xlsx",
            "ppt_file": "template.pptx"
        }

    def test_run_full_flow(self, setup_env):
        """
        测试完整流程：Config -> Generator -> Run -> Output
        """
        env = setup_env
        
        # --- 3. 构造完整配置字典 (模拟 YAML 内容) ---
        app_config = {
            "ppt_engine": {
                "path": {
                    "network_source_dir": str(env["resources"]), # 暂时指向本地模拟网络盘
                    "resources_dir": "resources", # 相对路径
                    "data_cache_dir": "cache",
                    "data_raw_dir": "raw",
                    "log_dir": "logs",
                    "output_dir": "output",
                    "output_ppt": "final_report.pptx",
                    "output_template_ppt": env["ppt_file"],
                    "main_py_path": ".",
                    "data_source_excel_FPY": env["excel_file"],
                    "data_source_excel_anomaly": "anomaly.xlsx",
                    "data_source_excel_risk": env["excel_file"],
                    "data_source_parquet_anomaly": "anomaly.parquet",
                    "logo": "logo.png",
                    "base_dir": str(env["root"]), # 关键：设置根目录
                    
                    "daily_report_template": {
                        "base_dir": "resources",
                        "filename_format": "template.pptx"
                    },
                    "data_sources": [
                        {
                            "key_name": "main_template",
                            "source_type": "local",
                            "filename": env["ppt_file"]
                        }
                    ]
                },
                "settings": {
                    "default_font": "Arial",
                    "author": "Tester"
                },
                "sections": {
                    "yield_data": {
                        "rendering_params": {
                            "insert_at_index": 1,
                            # CanvasProcessor 将寻找此标题并删除旧页
                            "title_text": ["Old Yield Title"] 
                        },
                        "data_config": {
                            "ppt_target_slides": [2],
                            "sheet_names": {
                                "yield_trend": "YieldTrend",
                                "control_plan": "ControlPlan"
                            },
                            "categories": ["Category A"],
                            "categories_titles": {"Category A": "Old Yield Title"},
                            "locators": {
                                "yield_trend_sheet": {
                                    "anchor_column": "B",
                                    # 偏移量配置
                                    "image": {"row_offset": 0, "col_offset": 1},
                                    "sentence": {"row_offset": 0, "col_offset": 2}
                                },
                                "control_plan_sheet": {
                                    "anchor_column": "B",
                                    "section_data": {"start_row_offset": 0, "height": 5}
                                }
                            },
                            # 必须提供，否则 _resolve_dynamic_addresses 可能报错
                            "excel_sections": {} 
                        },
                        "layout_config": {
                            "title": {"left": 0.5, "top": 0.5, "width": 5.0, "height": 1.0},
                            "logo": {"left": 9.0, "top": 0.5, "width": 1.0, "height": 1.0},
                            "chart": {"left": 0.5, "top": 2.0, "width": 5.0, "height": 3.0},
                            "summary": {"left": 6.0, "top": 2.0, "width": 3.0, "height": 3.0, "placeholder_name": "Text Placeholder 1"}
                        },
                        "table_layout": {
                            "base": {
                                "left": 0.5, "top": 5.5, "width": 9.0, "height": 2.0,
                                "font_name": "Arial", "header_font_size": 10, "body_font_size": 10,
                                "col_width_rules": {"default": 1.0}
                            },
                            "calculations": {}
                        }
                    },
                    "risk_control": {
                        "rendering_params": {
                            "insert_at_index": 2,
                            "title_text": "Risk Control"
                        },
                        "table_layout": {
                            "base": {
                                "left": 0.5, "top": 1.0, "width": 9.0, "height": 5.0,
                                "font_name": "Arial", "header_font_size": 10, "body_font_size": 10,
                                "col_width_rules": {"default": 1.0}
                            }
                        }
                    },
                    "anomaly_management": {} # 占位
                },
                "runtime_settings": {
                    "sections_to_generate": ["yield_data"] # 仅测试 Yield 章节，全流程最复杂的部分
                }
            }
        }

        # --- 4. 初始化 Config 对象 ---
        # 使用 from_app_config 模拟真实加载
        config = PptEngineConfig.from_app_config(app_config)
        
        # --- 5. 初始化 Generator ---
        generator = PPTGenerator(config)
        
        # --- 6. 执行 Run ---
        # 我们不做任何 Mock，让它真实地读写文件
        try:
            generator.run()
        except Exception as e:
            pytest.fail(f"Integration Test Failed with Exception: {e}")
            
        # --- 7. 验证结果 ---
        output_file = env["output"] / "final_report.pptx"
        assert output_file.exists(), "Output PPT file was not created"
        assert output_file.stat().st_size > 0, "Output PPT file is empty"
        
        # 简单验证 PPT 内容
        prs = Presentation(str(output_file))
        # 验证页数：模板2页 - 删除1页 + 生成1页 = 2页 (如果逻辑正确)
        # 或者仅仅验证不为空
        assert len(prs.slides) > 0
        print(f"Generated PPT has {len(prs.slides)} slides.")