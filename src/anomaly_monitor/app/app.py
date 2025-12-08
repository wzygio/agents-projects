# 导入我们的后端服务
import streamlit as st
import pandas as pd
import logging
import sys
from pathlib import Path

# 添加项目根目录到 path (防止找不到模块)
try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError: pass

# --- 1. 初始化系统环境 ---
from common.utils.app_setup import AppSetup

# 使用 cache_resource 避免重复初始化
@st.cache_resource
def init_global_resources():
    AppSetup.initialize_app(log_name="ela_main.log")
init_global_resources()

# 导入我们的后端服务
from src.anomaly_monitor.services.hl_report_service import HLReportService

# --- 页面配置 ---
st.set_page_config(
    page_title="OLED 良率异常监控台",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(level=logging.INFO)

# --- 0. 字段映射表 (Spotfire 1:1 还原) ---
# Key: data_loader 处理后的 DataFrame 列名 (全小写)
# Value: 界面显示的中文表头
COLUMN_MAPPING = {
    "type_calc": "TYPE",            # 之前缺少的 (loader中暂未计算type，可暂时忽略或补上)
    "prod_code": "prod_code",
    "defect_desc": "defect_desc",
    "oper_group": "oper_group",
    
    "ratio": "日良损",
    "month_ratio": "CT月",
    "week_ratio": "CT周",           # 假设源文件有
    "batch_ratio": "本批次",
    
    "worsening_text": "批次恶化",   # 我们自己拼的文本
    "lot_input_ratio": "批次产出率",
    
    "batch_gap": "本批次-上批次",
    "multiplier": "倍数",
    
    "最新hl时间": "最新HL时间",      # 来自 hl_csv_data
    "hl次数": "HL次数",             # 来自 hl_csv_data
    "ng_qty": "ng_qty",             # 来自 hl_data (主表)
    "hl原因": "HL原因"              # 来自 hl_csv_data
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

# --- 2. 数据适配器 ---
def prepare_display_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    
    # A. 补全缺失列 (如果 Infrastructure 没算出来)
    # TYPE: 简单的空值判断
    if 'type' not in df.columns:
        # 简易逻辑：如果 HL次数 <= 1 则为首发
        if 'hl次数' in df.columns:
            df['TYPE'] = df['hl次数'].apply(lambda x: '批次首发' if x <= 1 else '非批次首发')
        else:
            df['TYPE'] = ""

    # B. 插入勾选列
    df.insert(0, "✅", False)
    
    # C. 映射列名
    # 找出所有存在的列进行重命名
    rename_dict = {k:v for k,v in COLUMN_MAPPING.items() if k in df.columns}
    df_display = df.rename(columns=rename_dict)
    
    # D. 排序: 确保显示的列都在 MAPPING 里 (按顺序)
    final_cols = ["✅"]
    for k, v in COLUMN_MAPPING.items():
        if v in df_display.columns:
            final_cols.append(v)
    
    # 补充未匹配到的 TYPE 等
    if 'TYPE' in df.columns and 'TYPE' not in df_display.columns:
        df_display['TYPE'] = df['TYPE']
        final_cols.insert(1, 'TYPE')

    return df_display[final_cols]

# --- 3. 主程序 ---
def main():
    service = get_service()
    if not service or service.df_hl is None:
        st.warning("数据未加载，请检查 config/settings.yaml 中的文件路径配置。")
        return

    # --- 过滤器 ---
    st.sidebar.title("📊 过滤器")
    # 默认只看恶化
    show_worsening = st.sidebar.checkbox("只看恶化 (Gap > 0)", value=True)
    
    df_view = service.df_hl.copy()
    
    if show_worsening and 'batch_gap' in df_view.columns:
        df_view = df_view[df_view['batch_gap'] > 0]
        
    if 'batch_gap' in df_view.columns:
        df_view = df_view.sort_values('batch_gap', ascending=False)

    # 准备展示数据
    df_display = prepare_display_data(df_view)

    # --- 列配置 (Spotfire 风格) ---
    column_config = {
        "✅": st.column_config.CheckboxColumn("选", width="small"),
        
        # 文本信息
        "TYPE": st.column_config.TextColumn("TYPE", width="small"),
        "prod_code": st.column_config.TextColumn("prod_code", width="small"),
        "defect_desc": st.column_config.TextColumn("defect_desc", width="medium"),
        "批次恶化": st.column_config.TextColumn("批次恶化", width="large"),
        
        # 关键数值 (百分比)
        "日良损": st.column_config.NumberColumn("日良损", format="%.2f%%"),
        "CT月": st.column_config.NumberColumn("CT月", format="%.2f%%"),
        "CT周": st.column_config.NumberColumn("CT周", format="%.2f%%"),
        "本批次": st.column_config.NumberColumn("本批次", format="%.2f%%"),
        "本批次-上批次": st.column_config.NumberColumn("本批次-上批次", format="%.2f%%"),
        "批次产出率": st.column_config.NumberColumn("批次产出率", format="%.1f%%"),
        "倍数": st.column_config.NumberColumn("倍数", format="%.2f%%"),
        
        # 核心差异点：这两个列必须是整数
        "HL次数": st.column_config.NumberColumn("HL次数", format="%d"),
        "ng_qty": st.column_config.NumberColumn("ng_qty", format="%d"),
        
        "最新HL时间": st.column_config.DatetimeColumn("最新HL时间", format="YYYY/MM/DD HH:mm"),
        "HL原因": st.column_config.TextColumn("HL原因")
    }

    st.subheader("🛡️ 异常监控列表 (Spotfire 复刻版)")
    
    edited_df = st.data_editor(
        df_display,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=600,
        disabled=df_display.columns.drop("✅")
    )
    
    # 生成逻辑 (保持不变)
    selected_rows = edited_df[edited_df["✅"] == True]
    if not selected_rows.empty:
        st.divider()
        if st.button(f"🚀 生成 {len(selected_rows)} 条报告", type="primary"):
            for idx in selected_rows.index:
                try:
                    raw_row = service.df_hl.loc[idx]
                    report = service.generator.generate_text(raw_row) # type: ignore
                    with st.expander(f"{raw_row.get('prod_code')} - {raw_row.get('defect_desc')}", expanded=True):
                        st.text_area("内容", report, height=300, key=f"rpt_{idx}")
                except Exception as e:
                    st.error(f"生成出错: {e}")

if __name__ == "__main__":
    main()