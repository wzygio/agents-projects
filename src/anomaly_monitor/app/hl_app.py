import streamlit as st
import pandas as pd
import logging
import sys
from pathlib import Path

# 添加项目根目录到 path
try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError: pass

# --- 1. 初始化系统环境 ---
from src.anomaly_monitor.services.hl_report_service import HLReportService
from src.anomaly_monitor.app.charts.hl_app_charts import COLUMN_MAPPING, prepare_display_data
from src.common.utils.app_setup import AppSetup

# 使用 cache_resource 避免重复初始化
@st.cache_resource
def init_system():
    AppSetup.initialize_app()
init_system()

logger = logging.getLogger(__name__)

# --- 页面配置 ---
st.set_page_config(
    page_title="OLED 良率异常监控台",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. 增加 MWDL 的列映射 (用于下方列表展示)
MWDL_COLUMN_MAPPING = {
    "defect_desc": "defect_desc",
    "prod_code": "prod_code",
    "oper_group": "oper_group",
    "date_value": "date_value", # 批次号
    "ratio_val": "ratio_fanel", # 我们清洗过的数值列，显示为百分比
    "ng_qty": "ng_qty",
    "input_qty": "input_qty",
    "defect_group": "defect_group", # Join 来的
    "lot_input_ratio": "lot_input_ratio" # Join 来的
}

# --- 1. Service 加载 ---
@st.cache_resource(show_spinner="正在连接数据仓库...")
def get_service():
    service = HLReportService()
    try:
        service.load_resources()
    except Exception as e:
        st.error(f"严重错误: 服务启动失败 - {e}")
        return None
    return service



# --- 3. 主程序 ---
def main():
    service = get_service()
    if not service or service.df_hl is None:
        st.warning("数据未加载")
        return

    # ================= 🔍 修改区域：侧边栏过滤器 =================
    st.sidebar.title("📊 过滤器")
    
    # 1. 基础过滤
    show_worsening = st.sidebar.checkbox("只看恶化 (Gap > 0)", value=True)
    
    # 2. 产品筛选
    # 获取所有唯一产品并排序
    all_prods = ["全部"] + sorted(service.df_hl['prod_code'].astype(str).unique().tolist())
    sel_prod = st.sidebar.selectbox("产品型号", all_prods)

    # 3. 🔍 新增：站点筛选
    # 获取所有唯一站点并排序
    all_stations = ["全部"] + sorted(service.df_hl['oper_group'].astype(str).unique().tolist())
    sel_station = st.sidebar.selectbox("发生站点", all_stations)

    # ================= 🔍 修改区域：数据过滤与排序 =================
    df_view = service.df_hl.copy()
    
    # A. 应用过滤
    if show_worsening and 'batch_gap' in df_view.columns:
        df_view = df_view[df_view['batch_gap'] > 0]
        
    if sel_prod != "全部":
        df_view = df_view[df_view['prod_code'] == sel_prod]
        
    if sel_station != "全部":
        df_view = df_view[df_view['oper_group'] == sel_station]

    # B. 🔍 核心逻辑：自定义层级排序
    # 需求：产品(升序) -> 不良(升序) -> 站点(CT置顶)
    if not df_view.empty:
        # 1. 创建辅助列：如果是 CT 赋值 0，其他赋值 1
        # 使用 upper() 确保大小写不敏感
        df_view['_station_rank'] = df_view['oper_group'].astype(str).apply(
            lambda x: 0 if x.upper().strip() == 'CT' else 1
        )
        
        # 2. 执行排序
        # 优先级: 产品 -> 不良 -> 站点权重 -> 恶化程度(作为最后的Tie-breaker，可选)
        sort_cols = ['prod_code', 'defect_desc', '_station_rank', 'batch_gap']
        ascending_order = [True, True, True, False] # 产品升, 不良升, 权重升(0在1前), Gap降
        
        # 容错: 确保列存在
        valid_sort_cols = []
        valid_asc = []
        for col, asc in zip(sort_cols, ascending_order):
            if col in df_view.columns:
                valid_sort_cols.append(col)
                valid_asc.append(asc)
        
        df_view = df_view.sort_values(by=valid_sort_cols, ascending=valid_asc)
        
        # 3. 删除辅助列 (不展示给用户)
        df_view = df_view.drop(columns=['_station_rank'])

    # ==========================================================

    # 准备展示数据
    df_display = prepare_display_data(df_view)

    # --- 列配置 ---
    column_config = {
        "✅": st.column_config.CheckboxColumn("选", width="small"),
        "TYPE": st.column_config.TextColumn("TYPE", width="small"),
        "prod_code": st.column_config.TextColumn("prod_code", width="small"),
        "defect_desc": st.column_config.TextColumn("defect_desc", width="medium"),
        "oper_group": st.column_config.TextColumn("oper_group", width="small"), # 确保站点列宽度合适
        "批次恶化": st.column_config.TextColumn("批次恶化", width="large"),
        "日良损": st.column_config.NumberColumn("日良损", format="%.2f%%"),
        "CT月": st.column_config.NumberColumn("CT月", format="%.2f%%"),
        "CT周": st.column_config.NumberColumn("CT周", format="%.2f%%"),
        "本批次": st.column_config.NumberColumn("本批次", format="%.2f%%"),
        "本批次-上批次": st.column_config.NumberColumn("本批次-上批次", format="%.2f%%"),
        "批次产出率": st.column_config.NumberColumn("批次产出率", format="%.1f%%"),
        "倍数": st.column_config.NumberColumn("倍数", format="%.2f%%"),
        "HL次数": st.column_config.NumberColumn("HL次数", format="%d"),
        "ng_qty": st.column_config.NumberColumn("ng_qty", format="%d"),
        "最新HL时间": st.column_config.DatetimeColumn("最新HL时间", format="YYYY/MM/DD HH:mm"),
        "HL原因": st.column_config.TextColumn("HL原因")
    }

    st.subheader("🛡️ 异常监控列表 (Spotfire 视图)")
    
    # 渲染表格
    edited_df = st.data_editor(
        df_display,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=600,
        disabled=df_display.columns.drop("✅")
    )

    # 逻辑：当且仅当用户【勾选了唯一的 1 行】时，才展示历史趋势
    selected_rows = edited_df[edited_df["✅"] == True]
    
    if len(selected_rows) == 1:
        st.divider()
        st.subheader("📈 批次月周天数据 (历史趋势)")
        
        # 获取选中行的 key info
        idx = selected_rows.index[0]
        row_data = service.df_hl.loc[idx]
        prod = row_data['prod_code']
        defect = row_data['defect_desc']
        
        st.caption(f"当前分析对象: {prod} - {defect}")
        
        # 调用 Service 查询历史
        df_history = service.get_history_by_prod_defect(prod, defect)
        
        if not df_history.empty:
            # 适配器：重命名和筛选列
            cols_show = [c for c in MWDL_COLUMN_MAPPING.keys() if c in df_history.columns]
            df_hist_display = df_history[cols_show].rename(columns=MWDL_COLUMN_MAPPING)
            
            # === 🔍 新增：MWDL 百分比修正 ===
            # 这里对应的是 'ratio_fanel' (即 ratio_val) 和 'lot_input_ratio'
            mwdl_pct_cols = ["ratio_fanel", "lot_input_ratio"]
            for col in mwdl_pct_cols:
                if col in df_hist_display.columns:
                     # 确保是数字
                     df_hist_display[col] = pd.to_numeric(df_hist_display[col], errors='coerce').fillna(0)
                     # 乘以 100
                     df_hist_display[col] = df_hist_display[col] * 100

            # 配置显示的列格式
            hist_config = {
                "ratio_fanel": st.column_config.NumberColumn("ratio_fanel", format="%.2f%%"),
                "lot_input_ratio": st.column_config.NumberColumn("lot_input_ratio", format="%.1f%%"),
                "ng_qty": st.column_config.NumberColumn("ng_qty", format="%d"),
                "input_qty": st.column_config.NumberColumn("input_qty", format="%d"),
            }
            
            st.dataframe(
                df_hist_display, 
                column_config=hist_config, 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("暂无该不良的历史批次数据。")
            
    elif len(selected_rows) > 1:
        st.info("💡 请仅勾选 1 行以查看其详细历史趋势。")
    
    # 生成报告逻辑
    selected_rows = edited_df[edited_df["✅"] == True]
    if not selected_rows.empty:
        st.divider()
        if st.button(f"🚀 生成 {len(selected_rows)} 条报告", type="primary"):
            logger.info(f"👉 用户点击生成报告，共选中 {len(selected_rows)} 条")
            for idx in selected_rows.index:
                try:
                    # 使用原始索引反查数据
                    raw_row = service.df_hl.loc[idx]
                    report = service.generator.generate_text(raw_row) # type: ignore
                    
                    # 标题展示增加站点信息
                    header_text = f"{raw_row.get('prod_code')} - {raw_row.get('defect_desc')} ({raw_row.get('oper_group')})"
                    
                    with st.expander(header_text, expanded=True):
                        st.text_area("内容", report, height=300, key=f"rpt_{idx}")

                    logger.info(f"✅ 成功生成报告: Index {idx}")
                except Exception as e:
                    logger.error(f"❌ 生成失败: {e}")

if __name__ == "__main__":
    main()