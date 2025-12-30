# 文件路径：packages/ppt_engine/src/application/ppt_generator.py
import logging, os, time
from pathlib import Path
from typing import Any, List, Dict, Optional, TYPE_CHECKING
from pptx import Presentation
from pptx.presentation import Presentation as PptxPresentationObject

# --- 1. 导入模块 ---
# load_config 仅用于模块底部的 standalone run 函数
from packages.ppt_engine.src.config import load_config

if TYPE_CHECKING:
    from packages.ppt_engine.src.config import PptEngineConfig, DataSourceItem

from packages.ppt_engine.src.core.file_path_processor import process_dynamic_settings
from packages.ppt_engine.src.core.canvas_processor import CanvasPreprocessor
from packages.ppt_engine.src.core.element_processor import ElementProcessor
from packages.ppt_engine.src.core.table_processor import TableProcessor
from packages.ppt_engine.src.application.yield_generator import YieldDataSectionGenerator
from packages.ppt_engine.src.application.anomaly_generator import AnomalyGenerator
from packages.ppt_engine.src.application.risk_generator import RiskControlSectionGenerator
from packages.ppt_engine.src.utils.local_utils import Utils

class PPTGenerator:
    """
    PPT生成器核心类 (Application Service)。
    
    [架构变更] 
    采用依赖注入模式：不再自行加载配置文件，而是被动接收配置对象。
    支持被 Streamlit (专家模式) 和 Adapter (自动化模式) 直接调用。
    """

    def __init__(self, config: "PptEngineConfig"):
        """
        初始化生成器。
        
        :param config: 已经加载并实例化的配置对象 (PptEngineConfig)
        """
        logging.info("--- 初始化 PPTGenerator (In-Memory Config Injection) ---")
        
        # 1. [Dependency Injection] 直接接收配置对象
        if not config:
            raise ValueError("必须注入有效的 PptEngineConfig 对象")
        self.config = config
        
        # 2. [Path Setup] 基于注入的配置提取路径
        # 注意：这里假设传入的 config 对象已经是处理过基础路径的 Pydantic 模型
        paths_cfg = self.config.path
        self.canvas_processor = CanvasPreprocessor(self.config)
        self.element_processor = ElementProcessor(self.config) # 假设 ElementProcessor 需要 config
        self.table_processor = TableProcessor() # 假设 TableProcessor 是无状态工具类或无需参数初始化

        if not paths_cfg.base_dir:
            raise ValueError("配置对象中缺少 base_dir 设置")
            
        self.base_dir = Path(paths_cfg.base_dir)
        self.resources_dir = self.base_dir / paths_cfg.resources_dir
        self.output_dir = self.base_dir / paths_cfg.output_dir
        
        # 网络路径处理
        self.network_dir = Path(paths_cfg.network_source_dir) if paths_cfg.network_source_dir else None

        # 3. 执行一次性基础校验
        self._validate_core_directories()
        
        # 4. 初始化状态属性
        self.prs: Optional[PptxPresentationObject] = None
        self.template_filename: str = ""

    def _validate_core_directories(self):
        """[Internal] 校验核心目录是否存在"""
        if not self.resources_dir.exists():
            # 尝试创建资源目录（如果是第一次运行）
            logging.warning(f"资源目录不存在: {self.resources_dir}，尝试创建...")
            self.resources_dir.mkdir(parents=True, exist_ok=True)
        
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
            # [Compatibility] process_dynamic_settings 会处理 ${today} 等占位符
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
        """确保 runtime_settings 初始化并填充默认生成章节"""
        if self.config.runtime_settings is None:
            self.config.runtime_settings = {}
        
        runtime = self.config.runtime_settings
        
        if not runtime.get('sections_to_generate'):
            logging.warning("未指定 'sections_to_generate'，将默认生成所有定义的章节。")
            
            # 动态获取 sections 下的所有 key
            if hasattr(self.config.sections, 'model_fields'):
                all_sections = list(self.config.sections.model_fields.keys())
            else:
                all_sections = list(self.config.sections.keys()) if self.config.sections else []
            
            runtime['sections_to_generate'] = all_sections
            logging.info(f"默认章节列表: {all_sections}")

    def _resolve_all_data_sources(self):
        """遍历配置中的数据源，确保所有文件都在本地资源目录就绪"""
        logging.info("--- 开始同步数据源文件 ---")
        paths_cfg = self.config.path
        
        for source_item in paths_cfg.data_sources:
            try:
                resolved_path = self._resolve_single_path(source_item)
                logging.info(f"数据源 '{source_item.key_name}' 就绪: {resolved_path}")
            except Exception as e:
                logging.error(f"数据源 '{source_item.key_name}' 同步失败: {e}")

    def _resolve_single_path(self, source_item: "DataSourceItem") -> Path:
        """处理单个数据源文件的定位与复制逻辑"""
        filename = source_item.filename
        key_name = source_item.key_name
        
        if not filename:
            if key_name == 'main_template': return Path('.')
            raise ValueError(f"数据源 '{key_name}' 缺少 filename 配置")

        # 1. 检查 UI 上传文件 (Priority 1)
        if source_item.source_type == 'uploaded':
            final_path_str = source_item.path
            if not final_path_str:
                raise ValueError(f"上传文件 '{filename}' 缺少 path 路径")
            final_path = Path(final_path_str)
            if final_path.exists():
                logging.info(f"使用上传文件: {final_path.name}")
                return final_path
            raise FileNotFoundError(f"上传文件未找到: {final_path}")

        # 2. 检查网络盘文件 (Priority 2)
        if source_item.source_type == 'network':
            if not self.network_dir:
                logging.warning(f"数据源 '{key_name}' 需要网络源，但未配置 network_source_dir")
            else:
                source_dir = self.network_dir
                if source_item.network_subdir:
                    source_dir = source_dir / source_item.network_subdir
                
                latest_file = Utils.find_latest_matching_file(source_dir, filename)
                if latest_file:
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

        # 3. 本地兜底检查 (Priority 3)
        latest_local = Utils.find_latest_matching_file(self.resources_dir, filename)
        if latest_local:
            final_local = self.resources_dir / latest_local.name
            if not final_local.exists():
                real_source = self.resources_dir / ('~$' + latest_local.name) if not latest_local.exists() else latest_local
                if Utils.safe_copy_file(real_source, final_local):
                    logging.info(f"本地文件已恢复: {latest_local.name}")
            
            logging.info(f"使用本地文件: {latest_local.name}")
            return final_local
            
        raise FileNotFoundError(f"文件 '{filename}' 在所有来源中均未找到")

    def _initialize_canvas(self):
        """加载主模板PPT并进行预处理"""
        logging.info("--- 初始化画布 ---")
        
        self.template_filename = ""
        for item in self.config.path.data_sources:
            if item.key_name == 'main_template':
                self.template_filename = item.filename
                if self.template_filename.startswith('~$'):
                    self.template_filename = self.template_filename[2:]
                break
        
        if not self.template_filename and self.config.path.output_template_ppt:
             self.template_filename = self.config.path.output_template_ppt

        if not self.template_filename:
            raise ValueError("无法确定主模板文件名")

        self.config.path.output_template_ppt = self.template_filename
        template_path = self.resources_dir / self.template_filename
        
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
            
        logging.info(f"加载模板: {template_path.name}")
        time.sleep(1)
        
        source_prs = Presentation(str(template_path))
        self.prs = self.canvas_processor.prepare_canvas(source_prs)

    def _generate_sections(self):
        """根据配置生成各章节内容"""
        logging.info("--- 生成章节内容 ---")
        
        generator_map = {
            'yield_data': YieldDataSectionGenerator,
            'anomaly_management': AnomalyGenerator,
            'risk_control': RiskControlSectionGenerator
        }
        
        tasks = []
        if not self.config.runtime_settings:
            raise ValueError("运行时设置未初始化")
        sections_to_gen = self.config.runtime_settings.get('sections_to_generate', [])
        
        for name in sections_to_gen:
            section_cfg = getattr(self.config.sections, name, None)
            static_idx = None
            if section_cfg:
                rendering = getattr(section_cfg, 'rendering_params', {})
                if isinstance(rendering, dict):
                    static_idx = rendering.get('insert_at_index')
                else:
                    static_idx = getattr(rendering, 'insert_at_index', None)
            
            runtime_idx = self.config.runtime_settings.get(f'{name}_insert_at_index')
            insert_at = runtime_idx if runtime_idx is not None else static_idx
            
            if insert_at is not None:
                tasks.append({'name': name, 'insert_at': insert_at})
        
        sorted_tasks = sorted(tasks, key=lambda x: x['insert_at'])
        offset = 0
        
        for task in sorted_tasks:
            name, original_idx = task['name'], task['insert_at']
            if name not in generator_map: continue
            
            actual_idx = original_idx + offset
            logging.info(f"生成章节: {name} (目标位置: {actual_idx})")
            
            self.config.runtime_settings[f'{name}_insert_at_index'] = actual_idx
            
            if self.prs is None: raise ValueError("Presentation object is not initialized")
            slide_count_start = len(self.prs.slides)

            GeneratorClass = generator_map[name]
            
            # [修改点] 统一依赖注入逻辑
            if name == 'yield_data':
                # YieldGenerator 需要全套处理器
                generator = GeneratorClass(
                    prs=self.prs, 
                    config=self.config,
                    element_processor=self.element_processor,
                    table_processor=self.table_processor
                )
            elif name == 'anomaly_management':
                # AnomalyGenerator 需要 ElementProcessor
                generator = GeneratorClass(
                    prs=self.prs, 
                    config=self.config, 
                    element_processor=self.element_processor
                )
            elif name == 'risk_control':
                # [新增] RiskGenerator 也完成重构，注入 ElementProcessor
                generator = GeneratorClass(
                    prs=self.prs, 
                    config=self.config, 
                    element_processor=self.element_processor
                )
            else:
                # 兜底：其他未重构的生成器 (如果有)
                generator = GeneratorClass(self.prs, self.config)

            generator.generate()
            
            new_slides = len(self.prs.slides) - slide_count_start
            offset += new_slides

    def _save_presentation(self):
        """保存生成的PPT文件"""
        output_filename = self.config.path.output_ppt
        output_path = self.output_dir / output_filename
        
        logging.info(f"正在保存 PPT 至: {output_path}")
        if self.prs is None:
            raise ValueError("Presentation object is not initialized")
        self.prs.save(str(output_path))

        logging.info("保存成功")

