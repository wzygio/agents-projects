# 文件路径：src\ppt_generator_project\ppt_generator.py
import logging, os, sys, time
from pathlib import Path
from typing import Any
from pptx import Presentation
from pptx.presentation import Presentation as PptxPresentationObject

# 导入所有我们需要的自定义模块
from packages.ppt_engine.src.config import load_config, RESOURCES_DIR, OUTPUT_DIR
from packages.ppt_engine.src.core.file_path_processor import process_dynamic_settings
from packages.ppt_engine.src.core.canvas_preprocessor import prepare_canvas 
from packages.ppt_engine.src.application.yield_generator import YieldDataSectionGenerator
from packages.ppt_engine.src.application.anomaly_generator import AnomalyMgmtSectionGenerator
from packages.ppt_engine.src.application.risk_generator import RiskControlSectionGenerator
from packages.ppt_engine.src.utils.local_utils import Utils

def run(config_path: str):
    """
    这是本模块唯一的公共函数，是整个PPT生成流程的总入口，它负责编排所有预处理和生成步骤：
    1. 准备环境（加载配置、准备文件）
    2. 生成内容（调用章节生成器）
    """
    try:
        # 步骤1：准备好所有原材料（配置和PPT画布对象）
        prepared_prs, final_config = _prepare_environment(config_path)
        
        # 步骤2：使用准备好的原材料进行内容生产
        _generate_presentation(prepared_prs, final_config)
    
    except Exception as e:
        logging.error(f"PPT生成流程发生致命错误: {e}", exc_info=True)
        # 将异常向上抛出，由调用方（main.py）决定如何处理
        raise

# =======================================================
# 1. 预处理函数
# =======================================================
def _prepare_environment(config_path: str) -> tuple[PptxPresentationObject, Any]:
    """
    【预处理函数】负责所有准备工作：
    1. 加载配置
    2. 处理动态设置
    3. 准备数据源文件
    4. 预处理画布（删除旧章节）
    """
    logging.info("--- 步骤1：开始环境与数据源预处理 ---")
    
    # 1. 加载基础配置 (返回的是强类型 PptEngineConfig 对象)
    config = load_config(Path(config_path))
    
    # --- [关键修改] 使用对象属性访问替代字典访问 ---
    
    # 检查 runtime_settings 是否存在且有内容
    # 注意：在我们的 Config 定义中，runtime_settings 默认为 {}，所以不会是 None，直接访问即可
    if not (config.runtime_settings or {}).get('sections_to_generate'):
        logging.warning("配置中未指定要生成的章节 (sections_to_generate)，将默认生成所有在 'sections' 中定义的章节。")
        
        # 既然是对象，直接赋值即可
        if not config.runtime_settings:
            config.runtime_settings = {}
            
        # 从 sections 对象中提取所有章节名
        # config.sections 是 SectionMap 对象，我们在 BaseConfig 里实现了 keys() 方法
        all_defined_sections = list(config.sections.keys())
        
        config.runtime_settings['sections_to_generate'] = all_defined_sections
        logging.info(f"默认生成的章节列表为: {all_defined_sections}")
        
    # 2. 应用动态设置
    # 注意：process_dynamic_settings 需要支持 Pydantic 对象
    # 我们之前的 BaseConfig 兼容层在这里发挥作用，保证传进去的对象能像字典一样被读取
    config = process_dynamic_settings(config=config)
    
    # 3. 遍历数据源配置 (使用 config.paths.data_sources)
    # 注意：config.paths.data_sources 是一个 List[DataSourceItem] 对象列表
    for source_item in config.paths.data_sources:
        try:
            # _file_processor 内部可能还在用字典方式访问 source_item
            # 由于 DataSourceItem 继承自 BaseConfig，它支持 source_item['filename'] 这种写法
            path = _file_processor(source_item, config)
            logging.info(f"数据源 '{source_item.key_name}' 已就绪: {path}")
        except Exception as e:
            logging.error(f"数据源 '{source_item.key_name}' 同步失败: {e}")

    logging.info("--- 所有文件源已准备就绪 ---")

    # 4. 加载并预处理画布
    paths_cfg = config.paths # 直接获取 PathsConfig 对象
    local_resources_dir = Path(paths_cfg.base_dir) / paths_cfg.resources_dir
    
    # 查找主模板文件名
    template_filename = ""
    for item in paths_cfg.data_sources:
        if item.key_name == 'main_template':
            filename = item.filename
            # 处理临时文件名
            if filename.startswith('~$'):
                filename = filename[2:]
            template_filename = filename
            break
    
    if not template_filename:
        # 如果配置里没写，尝试用 paths 下的 output_template_ppt 作为兜底
        if paths_cfg.output_template_ppt:
            template_filename = paths_cfg.output_template_ppt
        else:
            raise ValueError("在配置处理后，无法确定最终的主模板文件名。")

    # 更新模板路径 (注意：Pydantic 字段赋值)
    # 这里的 template_ppt 可能是我们临时想存的一个字段，如果是 Config 定义里没有的
    # 因为我们在 BaseConfig 里设置了 extra='allow'，所以这里直接赋值是合法的！
    paths_cfg.output_template_ppt = template_filename 
    
    canvas_template_path = local_resources_dir / template_filename
    
    if not canvas_template_path.exists():
        raise FileNotFoundError(f"最终的画布模板文件在本地不存在: {canvas_template_path}")
    
    logging.info(f"文件 {canvas_template_path.name} 已复制，等待1秒以确保I/O句柄释放...")
    time.sleep(1) 

    source_prs = Presentation(canvas_template_path)
    canvas_prs = prepare_canvas(source_prs, config)
    
    logging.info("--- 环境与数据源预处理完毕 ---")
    return canvas_prs, config


def _file_processor(source_item: dict, config: dict) -> Path:
    """
    三级文件定位逻辑：上传文件 > 公共盘源 > 本地后备
    1. 优先使用用户上传的文件
    2. 公共盘路径同步（如NAS）
    3. 最后使用本地资源目录
    """
    paths_cfg = config.get('paths', {})
    local_resources_dir = RESOURCES_DIR
    network_base_dir = paths_cfg.get('network_source_dir') # 公共盘资源目录
    
    filename = source_item.get('filename') # 获取文件名
    if not filename:
        # 主模板允许无文件名（动态生成）
        if source_item.get('key_name') != 'main_template':
            raise ValueError(f"数据源配置项缺少'filename'键: {source_item}")
        else:
            return Path('.')  # 返回当前目录作为占位符

    # 1. 查看上传文件是否已被保存到本地
    if source_item.get('source_type') == 'uploaded':
        # 'path' 字段现在是最终的、在 local_resources_dir 中的路径
        final_path_str = source_item.get('path')
        if not final_path_str:
            raise ValueError(f"UI上传文件 '{filename}' 未在配置中提供 'path'。")
        
        final_path = Path(final_path_str)
        
        if final_path.exists():
            # 文件已由UI放在正确位置，无需复制，直接验证并返回
            logging.info(f"已确认使用UI上传的文件: '{final_path.name}' (位于 {final_path.parent})")
            return final_path
        else:
            raise FileNotFoundError(f"UI上传的文件 '{filename}' 在其指定路径 '{final_path}' 未找到。")
    
    # 2. 公共盘文件处理
    if source_item.get('source_type') == 'network':
        source_dir = Path(network_base_dir)
        if source_item.get('network_subdir'):
            source_dir = source_dir / source_item['network_subdir'] # 子目录处理
        
        # 使用模糊匹配查找最新文件
        latest_file = Utils.find_latest_matching_file(source_dir, filename)
        if latest_file:
            # 如果是临时文件，使用实际的临时文件路径
            actual_source_path = source_dir / ('~$' + latest_file.name) if not latest_file.exists() else latest_file
            final_local_path = local_resources_dir / latest_file.name
            
            if final_local_path.exists() and actual_source_path.samefile(final_local_path):
                logging.info(f"公共盘源文件 '{latest_file.name}' 已在目标位置，无需覆盖。")
            else:
                if Utils.safe_copy_file(actual_source_path, final_local_path):
                    logging.info(f"成功将公共盘文件 '{latest_file.name}' 复制并覆盖到本地。")
                    return final_local_path
                else:
                    logging.warning(f"公共盘文件复制失败，将尝试使用本地后备文件。")
        else:
            logging.warning(f"UI_WARNING: 未在公共盘上找到包含 '{filename}' 的文件，将尝试使用本地后备文件。")

    # 3. 最后检查本地是否存在（使用模糊匹配）
    latest_local_file = Utils.find_latest_matching_file(local_resources_dir, filename)
    if latest_local_file:
        final_local_path = local_resources_dir / latest_local_file.name
        if not final_local_path.exists():
            actual_source_path = local_resources_dir / ('~$' + latest_local_file.name) if not latest_local_file.exists() else latest_local_file
            if Utils.safe_copy_file(actual_source_path, final_local_path):
                logging.info(f"成功复制本地文件: '{latest_local_file.name}'")
        
        logging.info(f"确认使用本地文件: '{latest_local_file.name}' (可能为公共盘失败后的后备)")
        return final_local_path
    
    raise FileNotFoundError(f"关键文件 '{filename}' 在所有来源中均未找到！")

# =======================================================
# 2. 内容生成
# =======================================================
def _generate_presentation(prs: PptxPresentationObject, config: dict):
    """
    核心内容生成流程：
    1. 初始化章节生成器映射
    2. 收集待生成任务
    3. 按插入位置排序
    4. 依次生成章节内容
    """
    
    logging.info("--- 步骤2：开始执行PPT内容生成 ---")
    try:
        # 1. 初始化章节生成器映射
        generator_map = {
            'yield_data': YieldDataSectionGenerator,
            'anomaly_management': AnomalyMgmtSectionGenerator,
            'risk_control': RiskControlSectionGenerator
        }
        tasks_to_run = []

        # 2. 根据勾选结果确定需要生成的章节
        for section_name in config.get('runtime_settings', {}).get('sections_to_generate', []):
            static_params = config.get('sections', {}).get(section_name, {}).get('rendering_params', {})
            # 获取插入位置（优先动态配置，其次静态配置）
            insert_at = config.get('runtime_settings', {}).get(f'{section_name}_insert_at_index', static_params.get('insert_at_index'))
            if insert_at is None: continue # 跳过无效插入位置
            tasks_to_run.append({'name': section_name, 'insert_at': insert_at}) # 记录生成任务
        
        # 按插入位置排序（保证章节顺序）
        sorted_tasks = sorted(tasks_to_run, key=lambda x: x['insert_at'])
        
        slide_index_offset = 0 # 幻灯片索引偏移量（用于动态调整插入位置）
        
        # 3. 依次生成章节内容
        for task in sorted_tasks:
            section_name, original_insert_at = task['name'], task['insert_at']
            adjusted_insert_at = original_insert_at + slide_index_offset # 计算实际插入位置
            
            if section_name not in generator_map: continue # 跳过无效章节
            
            # 保存实际位置
            logging.info(f"--- 开始处理章节：{section_name} (修正后目标位置: 索引 {adjusted_insert_at}) ---")
            config['runtime_settings'][f'{section_name}_insert_at_index'] = adjusted_insert_at 
            
            slide_count_before_gen = len(prs.slides) # 记录生成前幻灯片数量
            GeneratorClass = generator_map[section_name] # 获取每个章节对应的生成器
            generator = GeneratorClass(prs, config) # 实例化生成器
            generator.generate() # 调用生成器中的生成方法生成PPT内容

            num_new_slides = len(prs.slides) - slide_count_before_gen # 计算新增幻灯片数量
            slide_index_offset += num_new_slides  # 更新偏移量
    
        # 输出配置
        paths_cfg = config.get('paths', {})
        output_dir, output_filename = OUTPUT_DIR, paths_cfg.get('output_ppt')
        output_path = os.path.join(output_dir, output_filename)
        os.makedirs(output_dir, exist_ok=True) # 创建输出目录
        prs.save(output_path) # 保存最终PPT
        logging.info(f"所有章节已生成，PPT已成功保存至: {output_path}")

    except Exception as e:
        logging.error(f"内容生成主流程发生严重错误: {e}", exc_info=True)
        raise
