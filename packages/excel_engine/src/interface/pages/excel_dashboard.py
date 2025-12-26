# 文件路径：packages/excel_engine/src/interface/pages/excel_dashboard.py
import streamlit as st
import logging
import tempfile
import subprocess
import shutil
from pathlib import Path

# --- 1. 仅导入类型定义或工厂，绝不导入全局实例 ---
# [Global Purge] 移除 'config' 对象导入，改为导入配置类定义
from packages.excel_engine.src.config import load_config
from interface.components.app_utils import AppUtils

# --- 2. 导入核心业务逻辑 (Use Cases) ---
from packages.excel_engine.src.application.report_genrator import GenerateReportUseCase
from packages.excel_engine.src.application.style_renderer import RefineStylesUseCase

# --- 3. 初始化系统 ---
from packages.common_utils.src.infrastructure.app_setup import AppSetup

# 使用 cache_resource 管理单例生命周期，而非依赖模块级全局变量
@st.cache_resource
def init_system():
    AppSetup.initialize_app("hl_dashboard.log")


# 初始化日志和配置
init_system()
logger = logging.getLogger(__name__)

# 获取当前会话的配置实例
cfg = load_config()

# ==========================================================
# --- Streamlit UI 界面 ---
# ==========================================================
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

    # --- 下载数据按钮 ---
    # [Locality Principle] 路径计算移至使用处，不依赖全局变量
    st.header("🔄 数据准备")
    if st.button("📥 下载最新数据文件", use_container_width=True):
        
        # [Type Access] 通过配置对象实例访问路径
        downloader_script = Path(cfg.paths.downloader_script_path)
        python_exec = Path(cfg.paths.downloader_python_executable)
        
        # 如果路径是相对路径，需要基于项目根目录解析（假设 cfg 中有 project_root 或自行解析）
        # 这里假设 cfg.paths 返回的是绝对路径或已正确处理的 Path 对象
        
        with st.spinner("正在运行下载脚本..."):
            if not downloader_script.exists():
                st.error(f"下载脚本未找到: {downloader_script}")
            else:
                try:
                    res = subprocess.run(
                        [str(python_exec), str(downloader_script)],
                        capture_output=True, 
                        text=True, 
                        encoding='utf-8'
                    )
                    
                    if res.returncode == 0:
                        st.success("✅ 数据下载成功！")
                    else:
                        st.error("❌ 下载失败")
                        st.expander("错误详情").code(res.stderr)
                except Exception as e:
                    st.error(f"执行出错: {e}")
                    logger.error(f"下载脚本执行异常: {e}", exc_info=True)

    st.divider()
    if st.button("🔄 重置状态", use_container_width=True):
        st.session_state.step1_success = False
        st.session_state.final_file_content = None
        st.rerun()

# --- 主界面 ---
tab1, tab2 = st.tabs(["生成基础日报", "渲染日报样式"])

# ==========================================================
# 选项卡一：生成日报
# ==========================================================
with tab1:
    st.header("生成基础日报")
    
    # [Type Access] 从 cfg 实例获取默认模板路径
    default_template_path = Path(cfg.paths.template_file)
    default_temp_output = Path(cfg.paths.temp_file)
    
    st.info(f"默认模板路径: {default_template_path}")
    
    uploaded_template_file = st.file_uploader("📥 上传新模板 (可选)", type=['xlsx'], key="initial_template_uploader")
    
    # 模板准备
    current_template_path = default_template_path
    if uploaded_template_file:
        try:
            AppUtils.save_uploaded_file(uploaded_template_file, default_template_path)
            st.success(f"已使用上传的模板覆盖默认模板")
        except Exception as e:
            st.error(f"模板保存失败: {e}")
            st.stop()

    if st.button("🎨 生成日报", type="primary", use_container_width=True, key="gen_base_report_btn"):
        with st.status("正在执行生成流程...", expanded=True) as status:
            try:
                st.write("⚙️ 初始化生成引擎...")
                # [Dependency Injection] 将本地实例化的 cfg 注入 UseCase
                use_case = GenerateReportUseCase(cfg)
                
                st.write("🏃‍♂️ 正在处理数据与写入Excel...")
                use_case.execute(
                    template_path=current_template_path,
                    output_path=default_temp_output
                )
                
                status.update(label="✅ 生成成功!", state="complete", expanded=False)
                st.session_state.step1_success = True
                
            except Exception as e:
                status.update(label="❌ 生成失败", state="error")
                st.error(f"核心逻辑错误: {str(e)}")
                logger.error("生成基础日报失败", exc_info=True)
                st.session_state.step1_success = False

    # --- 结果展示 ---
    if st.session_state.step1_success and default_temp_output.exists():
        st.divider()
        st.subheader("✅ 基础日报已就绪")
        
        with open(default_temp_output, "rb") as file:
            st.download_button(
                label="📥 下载中间文件",
                data=file,
                file_name=default_temp_output.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        st.warning("提示: 如果需要调整字体格式，请进行下一步'渲染日报样式'")

# ==========================================================
# 选项卡二：应用样式
# ==========================================================
with tab2:
    st.header("渲染日报样式")
    
    # 重新获取路径引用（为了代码局部性，也可直接复用上面的变量）
    default_temp_output = Path(cfg.paths.temp_file)
    
    uploaded_intermediate_file = st.file_uploader("📥 上传日报文件", type=['xlsx'], key="intermediate_uploader")
    
    target_input_path = None
    if uploaded_intermediate_file:
        target_input_path = uploaded_intermediate_file
    elif st.session_state.step1_success and default_temp_output.exists():
        st.info("检测到上一步生成的临时文件，将默认使用该文件。")
        target_input_path = default_temp_output

    if st.button("🎨 渲染最终样式", type="primary", use_container_width=True, key="gen_final_report_btn", disabled=not target_input_path):
        
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            
            input_file_path = work_dir / "input_for_style.xlsx"
            final_output_path = work_dir / st.session_state.output_filename

            if uploaded_intermediate_file:
                AppUtils.save_uploaded_file(uploaded_intermediate_file, input_file_path)
            else:
                shutil.copy(target_input_path, input_file_path) # type: ignore

            with st.status("正在应用样式...", expanded=True) as status:
                try:
                    st.write("🖌️ 初始化字体处理器...")
                    # [Dependency Injection] 注入 cfg 实例
                    style_use_case = RefineStylesUseCase(cfg)
                    
                    st.write("💅 正在注入富文本与对齐样式...")
                    style_use_case.execute(
                        input_path=input_file_path,
                        output_path=final_output_path
                    )
                    
                    status.update(label="✅ 渲染完成!", state="complete", expanded=False)
                    
                    if final_output_path.exists():
                        st.session_state.final_file_content = final_output_path.read_bytes()
                        st.session_state.final_filename = final_output_path.name
                    
                except Exception as e:
                    status.update(label="❌ 渲染失败", state="error")
                    st.error(f"样式处理错误: {str(e)}")
                    logger.error("样式处理失败", exc_info=True)

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