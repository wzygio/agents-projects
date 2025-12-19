# streamlit_app.py (V2.1 - 仅修改文件保存路径)
import yaml, os, sys, logging
import datetime
from datetime import timedelta
import subprocess
import tempfile
import shutil
from pathlib import Path
import streamlit as st

from ppt_generator_project.config import CONFIG, RESOURCES_DIR, MAIN_PY_PATH,  OUTPUT_DIR
from ppt_generator_project.app.setup import AppSetup
@st.cache_resource
def init_portal_resources():
    AppSetup.initialize_app()

# ===================================================================
# --- 侧边栏 ---
# ===================================================================
st.set_page_config(page_title="PPT自动化报告生成器", layout="wide")
st.title("📊 PPT 自动化报告生成器")

with st.sidebar:
    st.header("⚙️ 报告生成配置")
    st.subheader("全局设置")
    output_filename = st.text_input("1. 输出PPT文件名", value=CONFIG['paths']['output_ppt'])
    
    # 获取当前时间并判断上午/下午
    now = datetime.datetime.now()
    if now.hour < 12:  # 上午（0-11时）
        default_date = datetime.date.today() - timedelta(days=1)  # 昨天的日期
    else:  # 下午（12-23时）
        default_date = datetime.date.today()  # 今天的日期

    # 设置日期输入框
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
    gen_anomaly_management = st.checkbox("异常管理章节", value=True) # 使用了正确的长名称
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

 
# 1. 初始化session_state中的结果标记
if 'last_run_result' not in st.session_state:
    st.session_state['last_run_result'] = None

# 2. 当用户点击生成按钮时，执行任务并把结果存入session_state
if generate_button:
    st.session_state['last_run_result'] = None # 每次生成之前都清空上次的结果
    
    # 创建临时目录（自动清理）：我们仍然需要 temp_dir 来存放临时的 config.yaml
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            new_config = CONFIG.copy() # 复制基础配置

            # --- 1. 保存上传的日报模板文件并更新路径 ---
            if template_source == "手动上传新模板":
                if uploaded_template_file:
                    saved_path = AppSetup.save_uploaded_file(uploaded_template_file, RESOURCES_DIR) 

                    # 将上传的模板文件的路径保存到新的配置中
                    if 'template_ppt_source' not in new_config['paths']: new_config['paths']['template_ppt_source'] = {}
                    new_config['paths']['template_ppt_source'] = {'type': 'uploaded', 'path': saved_path, 'filename': uploaded_template_file.name}
                else:
                    st.error("错误：您选择了手动上传模板，但未上传任何文件。")
                    st.stop()
            
            # --- 2. 保存上传的数据文件并更新路径 ---
            # 将键名与它们在data_sources列表中的索引对应起来，例如：{'source1': 0, 'source2': 1}
            key_to_index_map = {item['key_name']: i for i, item in enumerate(new_config['paths']['data_sources'])}
            
            # 使用统一的、正确的键名 'anomaly_management'
            excel_uploads = {
                'yield_data': 'data_source_excel_FPY',
                'anomaly_management': 'data_source_excel_anomaly',
                'risk_control': 'data_source_excel_risk'
            }
            
            # 处理上传的Excel文件
            for section_key, uploader_key in excel_uploads.items():
                if uploaded_files.get(section_key):
                    if uploader_key in key_to_index_map:
                        idx = key_to_index_map[uploader_key]
                        if uploaded_files.get(section_key):
                            # 有上传文件的情况
                            saved_path = AppSetup.save_uploaded_file(uploaded_files[section_key], RESOURCES_DIR)
                            new_config['paths']['data_sources'][idx]['source_type'] = 'uploaded'
                            new_config['paths']['data_sources'][idx]['path'] = saved_path
                        else:
                            # 没有上传文件的情况，使用网络数据源
                            new_config['paths']['data_sources'][idx]['source_type'] = 'network'

            # 将设定的模板文件名和日期保存到新的配置中
            new_config['paths']['output_ppt'] = output_filename
            new_config['sections']['anomaly_management']['specific_date'] = report_date.strftime('%Y-%m-%d')
            
            # 各章节勾选结果（要生成的章节）
            required_sections = {
                'yield_data': gen_yield_data, 
                'anomaly_management': gen_anomaly_management, 
                'risk_control': gen_risk_control
            }
            new_config['runtime_settings'] = {'sections_to_generate': [name for name, checked in required_sections.items() if checked]}
            
            temp_config_path = os.path.join(temp_dir, 'temp_config.yaml')
            config_to_write = AppSetup.revert_colors_to_list(new_config)
            with open(temp_config_path, 'w', encoding='utf-8') as f: yaml.dump(config_to_write, f, allow_unicode=True)

            # --- 调用后台进程 ---
            with st.spinner("配置准备就绪，正在调用核心生成引擎..."):
                # 准备环境变量
                python_executable = sys.executable 
                process_env = os.environ.copy()
                process_env['PYTHONIOENCODING'] = 'utf-8'

                # 执行main.py脚本
                result = subprocess.run(
                    [python_executable, MAIN_PY_PATH, '--config', temp_config_path], 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8', 
                    env=process_env)

            # --- 将运行结果存入“长期记忆” session_state ---
            st.session_state['last_run_result'] = {
                "returncode": result.returncode, # 0表示成功，非0表示失败
                "stdout": result.stdout, # 标准输出
                "stderr": result.stderr, # 标准错误
                "output_dir": OUTPUT_DIR, # 输出目录
                "output_filename": output_filename # 输出文件名
            }
            # 强制页面刷新，以便立刻显示新存入的结果
            st.rerun()
        
        except Exception as e:
            st.error(f"应用发生了一个意料之外的错误: {e}")

# ===================================================================
# --- 日志输出 ---
# ===================================================================
# 3. 无论何时重新运行，都检查session_state并展示上一次的结果
if st.session_state['last_run_result']:
    st.divider() # 添加一条分割线，区分配置区和结果区

    col1, col2 = st.columns([0.85, 0.15]) # 创建两列，让标题和按钮在同一行
    with col1:
        st.header("运行结果")
    with col2:
        if st.button("清空结果", use_container_width=True):
            st.session_state['last_run_result'] = None
            st.rerun()

    result_data = st.session_state['last_run_result']
    
    if result_data["returncode"] == 0:
        st.success("🎉 报告生成成功！")
        
        # 展示下载按钮
        output_file_path = os.path.join(str(result_data['output_dir']), str(result_data['output_filename']))
        with open(output_file_path, "rb") as file:
            st.download_button(
                label="📥 点击下载生成的PPT报告", data=file, file_name=result_data['output_filename'],
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True
            )
    else:
        # 失败的运行，展示所有能获取到的信息
        st.error("报告生成失败！请查看下面的详细信息：")
        
        # 同时展示标准输出（我们的探针在这里）和标准错误（真正的Traceback）
        if result_data["stdout"]:
            with st.expander("点击查看后台标准输出（可能包含诊断线索）", expanded=True):
                st.code(result_data["stdout"], language='log')
        
        if result_data["stderr"]:
            with st.expander("点击查看后台错误输出", expanded=True):
                st.code(result_data["stderr"], language='bash')