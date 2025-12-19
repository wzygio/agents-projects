# 文件路径：packages/excel_engine/src/interface/pages/excel_dashboard.py
import streamlit as st
import sys
import time
import logging
import tempfile
from pathlib import Path

# --- 1. 导入重构后的模块 ---
from packages.excel_engine.src.config import CONFIG, TEMPLATE_PATH, TEMP_PATH, DOWNLOADER_SCRIPT_PATH, DOWNLOADER_PYTHON_EXECUTABLE
from interface.components.app_utils import AppUtils # 原 AppSetup
# 导入 UseCases (核心业务逻辑)
from application.generate_report import GenerateReportUseCase
from application.refine_styles import RefineStylesUseCase

from packages.common_utils.src.infrastructure.app_setup import AppSetup

# 使用 cache_resource 避免重复初始化
@st.cache_resource
def init_system():
    AppSetup.initialize_app("hl_dashboard.log")
init_system()

logger = logging.getLogger(__name__)

# ==========================================================
# --- Streamlit UI 界面 ---
# ==========================================================
# st.set_page_config 只能调用一次，建议放在 main.py 或者最外层
# 如果这是独立运行页面，保留它；如果是被 main.py 调用的，需要去掉
# st.set_page_config(page_title="Excel日报生成器", layout="wide") 

st.title("📊 Excel日报自动化生成工具")

# --- 状态管理初始化 ---
if 'step1_success' not in st.session_state:
    st.session_state.step1_success = False
if 'final_file_content' not in st.session_state:
    st.session_state.final_file_content = None
    st.session_state.final_filename = None

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 全局配置")
    
    if 'output_filename' not in st.session_state:
        st.session_state.output_filename = AppUtils.generate_dynamic_filename()
    
    st.session_state.output_filename = st.text_input(
        "最终输出文件名", 
        value=st.session_state.output_filename
    )
    
    st.divider()

    # --- 下载数据按钮 (暂时保留 Subprocess，除非您也重构了下载器) ---
    st.header("🔄 数据准备")
    if st.button("📥 下载最新数据文件", use_container_width=True):
        with st.spinner("正在运行下载脚本..."):
            if not DOWNLOADER_SCRIPT_PATH.exists():
                st.error(f"下载脚本未找到: {DOWNLOADER_SCRIPT_PATH}")
            else:
                # 这里的 run_subprocess 需要在 AppUtils 里保留一个简化版，或者直接用 subprocess
                import subprocess
                try:
                    res = subprocess.run(
                        [str(DOWNLOADER_PYTHON_EXECUTABLE), str(DOWNLOADER_SCRIPT_PATH)],
                        capture_output=True, text=True, encoding='utf-8'
                    )
                    if res.returncode == 0:
                        st.success("✅ 数据下载成功！")
                    else:
                        st.error("❌ 下载失败")
                        st.code(res.stderr)
                except Exception as e:
                    st.error(f"执行出错: {e}")

    st.divider()
    if st.button("🔄 重置状态", use_container_width=True):
        st.session_state.step1_success = False
        st.session_state.final_file_content = None
        st.rerun()

# --- 主界面 ---
tab1, tab2 = st.tabs(["生成基础日报", "渲染日报样式"])

# ==========================================================
# 选项卡一：生成日报 (直接调用 Application Layer)
# ==========================================================
with tab1:
    st.header("生成基础日报")
    st.info(f"默认模板路径: {TEMPLATE_PATH}")
    
    uploaded_template_file = st.file_uploader("📥 上传新模板 (可选)", type=['xlsx'], key="initial_template_uploader")
    
    # 模板准备
    current_template_path = TEMPLATE_PATH
    if uploaded_template_file:
        # 保存上传的模板
        try:
            AppUtils.save_uploaded_file(uploaded_template_file, TEMPLATE_PATH)
            st.success(f"已使用上传的模板覆盖默认模板")
        except Exception as e:
            st.error(f"模板保存失败: {e}")
            st.stop()

    if st.button("🎨 生成日报", type="primary", use_container_width=True, key="gen_base_report_btn"):
        with st.status("正在执行生成流程...", expanded=True) as status:
            try:
                # 1. 初始化用例
                st.write("⚙️ 初始化生成引擎...")
                use_case = GenerateReportUseCase(CONFIG)
                
                # 2. 执行用例 (Direct Call!)
                st.write("🏃‍♂️ 正在处理数据与写入Excel...")
                use_case.execute(
                    template_path=current_template_path,
                    output_path=TEMP_PATH
                )
                
                status.update(label="✅ 生成成功!", state="complete", expanded=False)
                st.session_state.step1_success = True
                
            except Exception as e:
                status.update(label="❌ 生成失败", state="error")
                st.error(f"核心逻辑错误: {str(e)}")
                logging.error("生成失败", exc_info=True)
                st.session_state.step1_success = False

    # --- 结果展示 ---
    if st.session_state.step1_success and TEMP_PATH.exists():
        st.divider()
        st.subheader("✅ 基础日报已就绪")
        
        with open(TEMP_PATH, "rb") as file:
            st.download_button(
                label="📥 下载中间文件",
                data=file,
                file_name=TEMP_PATH.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        st.warning("提示: 如果需要调整字体格式，请进行下一步'渲染日报样式'")

# ==========================================================
# 选项卡二：应用样式 (直接调用 Application Layer)
# ==========================================================
with tab2:
    st.header("渲染日报样式")
    
    uploaded_intermediate_file = st.file_uploader("📥 上传日报文件", type=['xlsx'], key="intermediate_uploader")
    
    # 如果用户刚刚生成了第一步，自动提示使用刚才的文件
    target_input_path = None
    if uploaded_intermediate_file:
        target_input_path = uploaded_intermediate_file
    elif st.session_state.step1_success and TEMP_PATH.exists():
        st.info("检测到上一步生成的临时文件，将默认使用该文件。")
        # 这里逻辑稍微特殊，如果没上传，就用 TEMP_PATH，但 UseCase 需要路径
        # 为了安全，我们通常建议用户显式上传，或者拷贝一份
        target_input_path = TEMP_PATH

    if st.button("🎨 渲染最终样式", type="primary", use_container_width=True, key="gen_final_report_btn", disabled=not target_input_path):
        
        # 使用临时目录处理，避免文件占用冲突
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            
            # 1. 准备输入文件
            input_file_path = work_dir / "input_for_style.xlsx"
            final_output_path = work_dir / st.session_state.output_filename

            if uploaded_intermediate_file:
                # 如果是 UploadedFile 对象，需要保存
                AppUtils.save_uploaded_file(uploaded_intermediate_file, input_file_path)
            else:
                # 如果是 Path 对象 (TEMP_PATH)，直接复制
                import shutil
                shutil.copy(target_input_path, input_file_path) # type: ignore

            # 2. 执行渲染
            with st.status("正在应用样式...", expanded=True) as status:
                try:
                    st.write("🖌️ 初始化字体处理器...")
                    style_use_case = RefineStylesUseCase(CONFIG)
                    
                    st.write("💅 正在注入富文本与对齐样式...")
                    style_use_case.execute(
                        input_path=input_file_path,
                        output_path=final_output_path
                    )
                    
                    status.update(label="✅ 渲染完成!", state="complete", expanded=False)
                    
                    # 读取结果到内存，以便下载
                    if final_output_path.exists():
                        st.session_state.final_file_content = final_output_path.read_bytes()
                        st.session_state.final_filename = final_output_path.name
                    
                except Exception as e:
                    status.update(label="❌ 渲染失败", state="error")
                    st.error(f"样式处理错误: {str(e)}")
                    logging.error("样式处理失败", exc_info=True)

    # --- 结果展示 ---
    if st.session_state.final_file_content:
        st.divider()
        st.subheader("🎉 最终日报已生成！")
        st.download_button(
            label=f"🏆 下载: {st.session_state.final_filename}",
            data=st.session_state.final_file_content,
            file_name=st.session_state.final_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )