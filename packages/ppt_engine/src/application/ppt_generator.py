# 文件路径：src/ppt_generator_project/ppt_generator.py
import logging, os, time
from pathlib import Path
from typing import Any, List, Dict, Optional, TYPE_CHECKING
from pptx import Presentation
from pptx.presentation import Presentation as PptxPresentationObject

# --- 1. 导入模块 ---
from packages.ppt_engine.src.config import load_config
# [Standard 4] Import Standard: 使用 TYPE_CHECKING 导入配置类
if TYPE_CHECKING:
    from packages.ppt_engine.src.config import PptEngineConfig, DataSourceItem

from packages.ppt_engine.src.core.file_path_processor import process_dynamic_settings
from packages.ppt_engine.src.core.canvas_processor import CanvasPreprocessor
from packages.ppt_engine.src.application.yield_generator import YieldDataSectionGenerator
from packages.ppt_engine.src.application.anomaly_generator import AnomalyGenerator
from packages.ppt_engine.src.application.risk_generator import RiskControlSectionGenerator
from packages.ppt_engine.src.utils.local_utils import Utils

class PPTGenerator:
    """
    PPT生成器核心类。
    负责编排整个PPT生成流程：环境准备 -> 数据源解析 -> 画布预处理 -> 内容生成 -> 保存。
    """

    def __init__(self, config_path: str):
        """
        初始化生成器。
        在此阶段完成配置加载、核心路径计算及基础校验。
        """
        logging.info("--- 初始化 PPTGenerator ---")
        
        self.config_path = config_path
        self.config: "PptEngineConfig" = load_config(self.config_path)
        
        # 2. [Path Validation] 提取并校验核心路径，转为类属性供后续复用
        # [Type Access] 使用点号访问 config.paths
        paths_cfg = self.config.paths
        self.canvas_processor = CanvasPreprocessor(self.config)

        if not paths_cfg.base_dir:
            raise ValueError("配置文件中缺少 base_dir 设置")
        self.base_dir = Path(paths_cfg.base_dir)
        self.resources_dir = self.base_dir / paths_cfg.resources_dir
        self.output_dir = self.base_dir / paths_cfg.output_dir
        
        # 网络路径可能是可选的
        self.network_dir = Path(paths_cfg.network_source_dir) if paths_cfg.network_source_dir else None

        # 3. 执行一次性基础校验
        self._validate_core_directories()
        
        # 4. 初始化状态属性
        self.prs: Optional[PptxPresentationObject] = None
        self.template_filename: str = ""

    def _validate_core_directories(self):
        """
        [Internal] 校验核心目录是否存在，避免后续重复检查。
        """
        if not self.resources_dir.exists():
            raise FileNotFoundError(f"资源目录不存在: {self.resources_dir}")
        
        # 自动创建输出目录
        if not self.output_dir.exists():
            logging.info(f"输出目录不存在，正在创建: {self.output_dir}")
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        """
        [Public Interface] 执行PPT生成的标准流程。
        """
        try:
            logging.info("=== 开始执行 PPT 生成流程 ===")
            
            # 步骤 1: 准备运行时设置 (处理 sections_to_generate)
            self._prepare_runtime_settings()
            
            # 步骤 2: 应用动态设置
            # [Compatibility] 更新 self.config 对象
            self.config = process_dynamic_settings(config=self.config)
            
            # 步骤 3: 准备所有数据源文件
            self._resolve_all_data_sources()
            
            # 步骤 4: 初始化画布 (加载模板 + 预处理)
            self._initialize_canvas()
            
            # 步骤 5: 生成各章节内容
            self._generate_sections()
            
            # 步骤 6: 保存结果
            self._save_presentation()
            
            logging.info("=== PPT 生成流程圆满结束 ===")

        except Exception as e:
            logging.error(f"PPT生成流程发生致命错误: {e}", exc_info=True)
            raise

    def _prepare_runtime_settings(self):
        """
        确保 runtime_settings 初始化并填充默认生成章节。
        """
        runtime = self.config.runtime_settings
        if not runtime:
            runtime = self.config.runtime_settings = {}
        
        if not runtime.get('sections_to_generate'):
            logging.warning("未指定 'sections_to_generate'，将默认生成所有定义的章节。")
            
            # [Type Access] 动态获取 sections 下的所有 key
            if hasattr(self.config.sections, 'model_fields'):
                 all_sections = list(self.config.sections.model_fields.keys())
            else:
                 all_sections = list(self.config.sections.keys()) if self.config.sections else []
            
            if self.config.runtime_settings is None:
                self.config.runtime_settings = {}
            self.config.runtime_settings['sections_to_generate'] = all_sections

            logging.info(f"默认章节列表: {all_sections}")

    def _resolve_all_data_sources(self):
        """
        遍历配置中的数据源，确保所有文件都在本地资源目录就绪。
        """
        logging.info("--- 开始同步数据源文件 ---")
        paths_cfg = self.config.paths
        
        for source_item in paths_cfg.data_sources:
            try:
                # [Optimization] 直接使用类属性 self.resources_dir，无需传参
                resolved_path = self._resolve_single_path(source_item)
                logging.info(f"数据源 '{source_item.key_name}' 就绪: {resolved_path}")
            except Exception as e:
                logging.error(f"数据源 '{source_item.key_name}' 同步失败: {e}")

    def _resolve_single_path(self, source_item: "DataSourceItem") -> Path:
        """
        处理单个数据源文件的定位与复制逻辑。
        利用 self.resources_dir 和 self.network_dir 属性。
        """
        filename = source_item.filename
        key_name = source_item.key_name
        
        # 特殊处理主模板无文件名的情况
        if not filename:
            if key_name == 'main_template':
                return Path('.')
            raise ValueError(f"数据源 '{key_name}' 缺少 filename 配置")

        # 1. 检查 UI 上传文件
        if source_item.source_type == 'uploaded':
            final_path_str = source_item.path
            if not final_path_str:
                raise ValueError(f"上传文件 '{filename}' 缺少 path 路径")
            
            final_path = Path(final_path_str)
            if final_path.exists():
                logging.info(f"使用上传文件: {final_path.name}")
                return final_path
            raise FileNotFoundError(f"上传文件未找到: {final_path}")

        # 2. 检查网络盘文件
        if source_item.source_type == 'network':
            if not self.network_dir:
                 logging.warning(f"数据源 '{key_name}' 需要网络源，但未配置 network_source_dir")
            else:
                # 拼接子目录
                source_dir = self.network_dir
                if source_item.network_subdir:
                    source_dir = source_dir / source_item.network_subdir
                
                # 查找并同步
                latest_file = Utils.find_latest_matching_file(source_dir, filename)
                if latest_file:
                    # 处理临时文件前缀 ~$
                    real_source = source_dir / ('~$' + latest_file.name) if not latest_file.exists() else latest_file
                    target_local = self.resources_dir / latest_file.name
                    
                    if target_local.exists() and real_source.samefile(target_local):
                        logging.info(f"网络文件 '{latest_file.name}' 已存在，跳过复制")
                    else:
                        if Utils.safe_copy_file(real_source, target_local):
                            logging.info(f"网络文件已同步: {latest_file.name}")
                            return target_local
                        else:
                            logging.warning("网络文件复制失败，尝试使用本地备份")
                else:
                    logging.warning(f"网络路径未找到包含 '{filename}' 的文件")

        # 3. 本地兜底检查 (使用 self.resources_dir)
        latest_local = Utils.find_latest_matching_file(self.resources_dir, filename)
        if latest_local:
            final_local = self.resources_dir / latest_local.name
            
            # 如果找到的是临时文件，需要尝试恢复或复制
            if not final_local.exists():
                real_source = self.resources_dir / ('~$' + latest_local.name) if not latest_local.exists() else latest_local
                if Utils.safe_copy_file(real_source, final_local):
                    logging.info(f"本地文件已恢复: {latest_local.name}")
            
            logging.info(f"使用本地文件: {latest_local.name}")
            return final_local
            
        raise FileNotFoundError(f"文件 '{filename}' 在所有来源中均未找到")

    def _initialize_canvas(self):
        """
        加载主模板PPT并进行预处理。
        """
        logging.info("--- 初始化画布 ---")
        
        # 确定模板文件名
        self.template_filename = ""
        for item in self.config.paths.data_sources:
            if item.key_name == 'main_template':
                self.template_filename = item.filename
                if self.template_filename.startswith('~$'):
                    self.template_filename = self.template_filename[2:]
                break
        
        # 兜底
        if not self.template_filename and self.config.paths.output_template_ppt:
             self.template_filename = self.config.paths.output_template_ppt

        if not self.template_filename:
            raise ValueError("无法确定主模板文件名")

        # 更新配置中的模板名
        self.config.paths.output_template_ppt = self.template_filename
        
        # 构建完整路径 (使用类属性)
        template_path = self.resources_dir / self.template_filename
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
            
        logging.info(f"加载模板: {template_path.name}")
        time.sleep(1) # I/O Wait
        
        source_prs = Presentation(str(template_path))
        
        # [Dependency Injection] 传递 self.config
        self.prs = self.canvas_processor.prepare_canvas(source_prs)

    def _generate_sections(self):
        """
        根据配置生成各章节内容。
        """
        logging.info("--- 生成章节内容 ---")
        
        generator_map = {
            'yield_data': YieldDataSectionGenerator,
            'anomaly_management': AnomalyGenerator,
            'risk_control': RiskControlSectionGenerator
        }
        
        tasks = []
        if self.config.runtime_settings is None:
            self.config.runtime_settings = {}
        sections_to_gen = self.config.runtime_settings.get('sections_to_generate', [])

        
        for name in sections_to_gen:
            # 安全获取章节配置
            section_cfg = getattr(self.config.sections, name, None)
            
            # 获取静态插入位置
            static_idx = None
            if section_cfg:
                # 兼容 Pydantic 对象或 Dict
                rendering = getattr(section_cfg, 'rendering_params', {})
                if isinstance(rendering, dict):
                    static_idx = rendering.get('insert_at_index')
                else: # Pydantic model
                    static_idx = getattr(rendering, 'insert_at_index', None)
            
            # 获取最终插入位置 (Runtime 优先)
            runtime_idx = self.config.runtime_settings.get(f'{name}_insert_at_index')
            insert_at = runtime_idx if runtime_idx is not None else static_idx
            
            if insert_at is not None:
                tasks.append({'name': name, 'insert_at': insert_at})
        
        # 排序并执行
        sorted_tasks = sorted(tasks, key=lambda x: x['insert_at'])
        offset = 0
        
        for task in sorted_tasks:
            name, original_idx = task['name'], task['insert_at']
            if name not in generator_map: continue
            
            actual_idx = original_idx + offset
            logging.info(f"生成章节: {name} (目标位置: {actual_idx})")
            
            # 更新运行时配置供生成器使用
            self.config.runtime_settings[f'{name}_insert_at_index'] = actual_idx
            
            if self.prs is None:
                raise ValueError("Presentation object is not initialized")
            slide_count_start = len(self.prs.slides)

            GeneratorClass = generator_map[name]
            
            # [Dependency Injection] 注入 self.config
            generator = GeneratorClass(self.prs, self.config)
            generator.generate()
            
            new_slides = len(self.prs.slides) - slide_count_start
            offset += new_slides

    def _save_presentation(self):
        """
        保存生成的PPT文件。
        """
        output_filename = self.config.paths.output_ppt
        output_path = self.output_dir / output_filename
        
        logging.info(f"正在保存 PPT 至: {output_path}")
        if self.prs is None:
            raise ValueError("Presentation object is not initialized")
        self.prs.save(str(output_path))

        logging.info("保存成功")

# =======================================================
# 模块入口 (保持兼容性)
# =======================================================
def run(config_path: str):
    """
    为了保持 main.py 的调用兼容性，保留此函数作为 wrapper。
    """
    generator = PPTGenerator(config_path)
    generator.run()