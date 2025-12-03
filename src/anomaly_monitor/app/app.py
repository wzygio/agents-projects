import logging, sys
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional
import streamlit as st


try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 
from src.config import config

# 导入我们的后端服务
from src.anomaly_monitor.services.hl_report_service import HLReportService

# --- 配置页面基础信息 ---
st.set_page_config(
    page_title="OLED 良率异常监控台",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. ViewModel 层: 资源加载与状态管理 ---

@st.cache_resource(show_spinner="正在连接数据仓库...")
def get_service():
    """
    单例模式加载 Service。
    使用 cache_resource 确保刷新页面时不会重新读取 CSV 文件 (135MB)，
    保证界面毫秒级响应。
    """
    service = HLReportService()
    try:
        service.load_resources()
    except Exception as e:
        st.error(f"严重错误: 服务启动失败 - {e}")
        return None
    return service

def get_display_dataframe(df_source: pd.DataFrame) -> pd.DataFrame:
    """
    数据适配器: 将后端原始数据转换为适合 UI 展示的格式。
    保留原始索引(Index)，以便后续回溯。
    """
    # 1. 复制数据，避免修改原始缓存
    df = df_source.copy()
    
    # 2. 插入勾选列 (默认不勾选)
    df.insert(0, "✅", False)
    
    # 3. 格式优化 (为了好看)
    # 确保数值列是 float，方便后面画进度条
    num_cols = ['batch_gap', 'ratio', 'batch_ratio', 'month_ratio']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # 4. 生成简短的批次显示 (保留原始 batch 用于生成报告)
    if 'batch' in df.columns:
        # 截取 "25/10/29..." -> "10/29"
        df['batch_short'] = df['batch'].astype(str).apply(lambda x: x[3:8] if len(x) > 8 else x)

    return df

# --- 2. View 层: 侧边栏过滤器 ---

def render_sidebar(df: pd.DataFrame):
    st.sidebar.title("📊 异常过滤器")
    
    # A. 恶化开关
    only_worsening = st.sidebar.checkbox("只看恶化批次 (Gap > 0)", value=True)
    
    # B. 恶化阈值滑块
    min_gap = 0.0
    if only_worsening:
        min_gap = st.sidebar.number_input(
            "最小恶化幅度 (%)", 
            min_value=0.0, 
            max_value=10.0, 
            value=0.1, 
            step=0.05,
            help="筛选 batch_gap 大于此值的项"
        ) / 100.0 # 转换为小数

    # C. 产品筛选
    all_prods = ["全部"] + sorted(df['prod_code'].dropna().unique().tolist())
    selected_prod = st.sidebar.selectbox("产品型号", all_prods)
    
    # D. 站点筛选 (如果有这个字段)
    selected_station = "全部"
    if 'oper_group' in df.columns:
        all_stations = ["全部"] + sorted(df['oper_group'].dropna().astype(str).unique().tolist())
        selected_station = st.sidebar.selectbox("发生站点", all_stations)

    st.sidebar.markdown("---")
    st.sidebar.caption(f"当前数据源版本: {pd.Timestamp.now().strftime('%H:%M:%S')}")
    
    if st.sidebar.button("🔄 刷新源数据"):
        st.cache_resource.clear()
        st.rerun()

    return {
        "only_worsening": only_worsening,
        "min_gap": min_gap,
        "prod": selected_prod,
        "station": selected_station
    }

# --- 3. View 层: 主界面逻辑 ---

def main():
    st.title("🛡️ OLED 良率异常监控台")
    st.markdown("通过勾选下方的异常条目，自动进行集中性分析并生成通报文本。")

    # 1. 加载服务
    service = get_service()
    if not service or service.df_hl is None:
        st.warning("数据未加载，请检查配置文件路径。")
        return

    # 2. 获取过滤器状态
    filters = render_sidebar(service.df_hl)

    # 3. 执行过滤 (逻辑在前端做，快速响应)
    # 保留原始 Index !!! 非常重要，用于后续反查
    df_filtered = service.df_hl.copy()
    
    # 按产品过滤
    if filters["prod"] != "全部":
        df_filtered = df_filtered[df_filtered['prod_code'] == filters["prod"]]
    
    # 按站点过滤
    if filters["station"] != "全部":
        df_filtered = df_filtered[df_filtered['oper_group'] == filters["station"]]
    
    # 按恶化幅度过滤
    if filters["only_worsening"]:
        if 'batch_gap' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['batch_gap'] >= filters["min_gap"]]

    # 默认按恶化程度降序
    if 'batch_gap' in df_filtered.columns:
        df_filtered = df_filtered.sort_values('batch_gap', ascending=False)

    # 4. 准备展示数据
    # 将过滤后的数据转换为 UI 友好格式 (增加复选框列)
    df_display = get_display_dataframe(df_filtered)
    
    # 定义显示的列及其顺序 (映射 Spotfire 的感觉)
    # key: 原始列名, value: 显示配置
    column_config = {
        "✅": st.column_config.CheckboxColumn(
            "选择",
            help="勾选以生成报告",
            default=False,
            width="small"
        ),
        "prod_code": st.column_config.TextColumn("产品", width="small"),
        "defect_desc": st.column_config.TextColumn("不良名称", width="medium"),
        "batch_short": st.column_config.TextColumn("批次", help="原始批次号的简写"),
        "batch_gap": st.column_config.ProgressColumn(
            "恶化幅度",
            format="%.2f%%",
            min_value=-0.05,
            max_value=0.05, # 根据实际数据范围调整
            help="本批次良损 - 上批次良损"
        ),
        "ratio": st.column_config.NumberColumn("日良损", format="%.2f%%"),
        "batch_ratio": st.column_config.NumberColumn("本批次", format="%.2f%%"),
        "month_ratio": st.column_config.NumberColumn("CT月", format="%.2f%%"),
        "oper_group": st.column_config.TextColumn("站点", width="small"),
        # 隐藏不需要展示但逻辑需要的列
        "batch": None, 
        "interface_time": None,
        "ng_qty": None
    }
    
    # 只要展示的列
    cols_to_show = ["✅", "prod_code", "defect_desc", "oper_group", "batch_short", "ratio", "batch_ratio", "month_ratio", "batch_gap"]
    
    # 5. 渲染可编辑表格 (Spotfire 核心体验)
    st.subheader(f"📋 异常列表 (共 {len(df_display)} 条)")
    
    edited_df = st.data_editor(
        df_display[cols_to_show], # 只传想要显示的列，但 Index 还在
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=400,
        key="data_editor" # 保持状态 key
    )

    # 6. 处理勾选逻辑
    # 筛选出被勾选的行
    selected_rows = edited_df[edited_df["✅"] == True]
    
    if not selected_rows.empty:
        st.divider()
        st.subheader(f"🚀 生成结果 ({len(selected_rows)} 条)")
        
        col1, col2 = st.columns([1, 6])
        if col1.button("开始生成报告", type="primary", use_container_width=True):
            
            progress_bar = st.progress(0)
            result_area = st.container()
            
            for i, (index, row_display) in enumerate(selected_rows.iterrows()):
                # --- 关键逻辑: 反查原始数据 ---
                # 使用 display dataframe 的 index (它继承自 filtered -> hl_data)
                # 去原始的 service.df_hl 中拿完整的一行 (包含 interface_time, ng_qty 等隐藏字段)
                try:
                    original_row = service.df_hl.loc[index] # type: ignore
                    
                    # 调用生成器
                    report_text = service.generator.generate_text(original_row) # type: ignore
                    
                    # 展示结果
                    with result_area:
                        with st.expander(f"📄 {original_row['prod_code']} - {original_row['defect_desc']} ({original_row['batch']})", expanded=True): # type: ignore
                            st.text_area("通报文本", value=report_text, height=350, key=f"txt_{index}")
                            # 提示: Streamlit 的 copy 功能通常依赖浏览器插件或 js hack，这里直接提供全选复制的文本框是最稳妥的
                            
                except KeyError:
                    st.error(f"无法找到索引为 {index} 的原始数据，可能源数据已变更。")
                except Exception as e:
                    st.error(f"生成失败: {e}")
                
                # 更新进度
                progress_bar.progress((i + 1) / len(selected_rows))
            
            st.success("✅ 所有报告生成完毕！")

    else:
        st.info("👆 请在上方表格中勾选需要汇报的异常条目。")

if __name__ == "__main__":
    main()