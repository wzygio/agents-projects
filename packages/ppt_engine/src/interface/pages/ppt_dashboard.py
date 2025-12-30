import streamlit as st
import datetime
from datetime import timedelta
from pathlib import Path
import logging

# [修改 1] 导入配置加载器
from packages.ppt_engine.src.config import load_config

# [修改 2] 导入核心业务逻辑类 (不再是通过 subprocess 调用 main.py)
from packages.ppt_engine.src.application.ppt_generator import PPTGenerator
from packages.common_utils.src.interface.app_setup import AppSetup
from packages.ppt_engine.src.interface.components.app_utils import AppUtils

# 初始化配置对象
# 这确保了无论 Streamlit 何时重启，我们都能拿到最新的、正确的配置
config = load_config()

# 为了代码简洁，提取一些常用路径
RESOURCES_DIR = Path(config.path.resources_dir)
OUTPUT_DIR = Path(config.path.output_dir)

# 初始化日志记录器
logger = logging.getLogger("PPTDashboard")

@st.cache_resource
def init_portal_resources():
    AppSetup.initialize_app("ppt_dashboard.log")

init_portal_resources()

# ===================================================================
# --- 侧边栏 ---
# ===================================================================
st.set_page_config(page_title="PPT自动化报告生成器", layout="wide")
st.title("📊 PPT 自动化报告生成器")

with st.sidebar:
    st.header("⚙️ 报告生成配置")
    st.subheader("全局设置")
    
    # 绑定 config 对象的属性
    output_filename = st.text_input("1. 输出PPT文件名", value=config.path.output_ppt)
    
    # 时间逻辑
    now = datetime.datetime.now()
    if now.hour < 12:  # 上午（0-11时）
        default_date = datetime.date.today() - timedelta(days=1)
    else:  # 下午（12-23时）
        default_date = datetime.date.today()

    report_date = st.date_input("2. 数据日期", value=default_date)
    
    st.subheader("模板与章节")
    template_source = st.radio(
        "1. 选择PPT模板来源",
        options=["自动按日期查找", "手动上传新模板"],
        horizontal=True,
    )
    uploaded_template_file = None
    if template_source == "手动上传新模板":
        uploaded_template_file = st.file_uploader("请上传PPT模板", type=['pptx'], label_visibility="collapsed")
    
    st.info("请勾选本次报告需要生成的章节。")
    gen_yield_data = st.checkbox("良率数据章节", value=True)
    gen_anomaly_management = st.checkbox("异常管理章节", value=True) 
    gen_risk_control = st.checkbox("风险品管控章节", value=False)
    
    st.divider()
    generate_button = st.button("🚀 生成报告", type="primary", use_container_width=True)


# ===================================================================
# --- 主区域 ---
# ===================================================================

st.header("📂 数据源文件上传")
uploaded_files = {}
if gen_yield_data: uploaded_files['yield_data'] = st.file_uploader("1. 上传【良率数据】Excel文件 (可选)", type=['xlsx', 'xls'])
if gen_anomaly_management: uploaded_files['anomaly_management'] = st.file_uploader("2. 上传【异常管理】Excel文件 (可选)", type=['xlsx', 'xls'])
if gen_risk_control: uploaded_files['risk_control'] = st.file_uploader("3. 上传【风险品管控】Excel文件 (可选)", type=['xlsx', 'xls'])

 
# 状态管理
if 'last_run_result' not in st.session_state:
    st.session_state['last_run_result'] = None

# ===================================================================
# --- 核心逻辑：执行生成 ---
# ===================================================================
if generate_button:
    st.session_state['last_run_result'] = None 
    
    # [核心修改] 不再深拷贝字典，而是直接修改内存中的 config 对象
    # 因为 Streamlit 的运行机制是脚本重跑，每次 config = load_config() 都会拿到新的（或者缓存的）对象
    # 为了安全起见，我们还是建议做一次 model_copy()，但这里为了演示直接修改
    
    try:
        # --- 1. 处理模板上传 ---
        if template_source == "手动上传新模板":
            if uploaded_template_file:
                saved_path = AppUtils.save_uploaded_file(uploaded_template_file, RESOURCES_DIR)
                # 更新 config 对象中的 path 属性
                # 注意：这里假设 config.path.template_ppt_source 是一个 DataSourceItem 对象
                # 如果它不存在，我们需要构造一个
                # 为简化逻辑，我们直接修改 data_sources 列表中的 main_template 项
                
                # 寻找 main_template 项并修改
                found = False
                for item in config.path.data_sources:
                    if item.key_name == 'main_template':
                        item.source_type = 'upload'
                        item.path = str(saved_path)
                        item.filename = uploaded_template_file.name
                        found = True
                        break
                
                if not found:
                     st.warning("配置中未找到 main_template 数据源定义，可能导致模板加载失败。")
            else:
                st.error("错误：您选择了手动上传模板，但未上传任何文件。")
                st.stop()
        
        # --- 2. 处理数据文件上传 ---
        # 建立映射关系: section_key -> config_key_name
        excel_uploads_map = {
            'yield_data': 'data_source_excel_FPY',
            'anomaly_management': 'data_source_excel_anomaly',
            'risk_control': 'data_source_excel_risk'
        }
        
        for section_key, config_key_name in excel_uploads_map.items():
            uploaded_file = uploaded_files.get(section_key)
            
            # 在 config.path.data_sources 中找到对应的项
            target_item = next((item for item in config.path.data_sources if item.key_name == config_key_name), None)
            
            if target_item:
                if uploaded_file:
                    # 如果用户上传了文件 -> 保存并更新配置为 'uploaded'
                    saved_path = AppUtils.save_uploaded_file(uploaded_file, RESOURCES_DIR)
                    target_item.source_type = 'upload'
                    target_item.path = str(saved_path)
                    # 也可以更新 filename，虽然 processing 逻辑主要看 path
                    # target_item.filename = uploaded_file.name 
                else:
                    # 如果没上传 -> 保持默认 (或强制设为 network/local)
                    # 这里我们保持原样，或者显式设为 network
                    if target_item.source_type == 'upload':
                         target_item.source_type = 'network' # 回退

        # --- 3. 更新其他运行时参数 ---
        config.path.output_ppt = output_filename
        
        # 更新日期 (假设在 sections.anomaly_management 下有 specific_date)
        if config.sections.anomaly_management:
             config.sections.anomaly_management.specific_date = report_date.strftime('%Y-%m-%d')
        
        # 更新章节生成列表
        required_sections = {
            'yield_data': gen_yield_data, 
            'anomaly_management': gen_anomaly_management, 
            'risk_control': gen_risk_control
        }
        
        if config.runtime_settings is None:
             config.runtime_settings = {}
             
        config.runtime_settings['sections_to_generate'] = [name for name, checked in required_sections.items() if checked]

        # --- 4. [核心修改] 直接调用 Generator ---
        with st.status("正在执行核心生成引擎...", expanded=True) as status:
            st.write("🔧 初始化 PPT 生成器 (Memory Injection Mode)...")
            
            # [Dependency Injection] 直接传入修改后的 config 对象
            generator = PPTGenerator(config)
            
            st.write("🏃‍♂️ 开始生成各章节...")
            generator.run()
            
            status.update(label="✅ 生成成功!", state="complete", expanded=False)
            
            # 记录成功状态
            st.session_state['last_run_result'] = {
                "success": True,
                "output_dir": str(OUTPUT_DIR),
                "output_filename": output_filename
            }
            st.rerun()
            
    except Exception as e:
        st.error(f"生成过程中发生错误: {e}")
        logger.error("PPT生成失败", exc_info=True)
        st.session_state['last_run_result'] = {
            "success": False,
            "error_msg": str(e)
        }

# ===================================================================
# --- 结果展示区 ---
# ===================================================================
if st.session_state['last_run_result']:
    st.divider()
    result = st.session_state['last_run_result']
    
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.header("运行结果")
    with col2:
        if st.button("清空结果", use_container_width=True):
            st.session_state['last_run_result'] = None
            st.rerun()

    if result.get("success"):
        st.success("🎉 报告生成成功！")
        
        output_file_path = Path(result['output_dir']) / result['output_filename']
        if output_file_path.exists():
            with open(output_file_path, "rb") as file:
                st.download_button(
                    label="📥 点击下载生成的PPT报告", 
                    data=file, 
                    file_name=result['output_filename'],
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", 
                    use_container_width=True,
                    type="primary"
                )
        else:
            st.warning(f"逻辑显示成功，但未找到文件：{output_file_path}")
    else:
        st.error("❌ 报告生成失败")
        with st.expander("查看错误详情", expanded=True):
            st.code(result.get("error_msg", "未知错误"), language='bash')