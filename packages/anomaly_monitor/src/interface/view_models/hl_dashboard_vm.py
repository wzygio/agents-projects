# 文件路径：packages\anomaly_monitor\src\interface\charts\hl_app_charts.py
import streamlit as st
import pandas as pd
import logging
import sys
from pathlib import Path

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

# --- 0. 字段映射表 (Spotfire 1:1 还原) ---
COLUMN_MAPPING = {
    # ... 原有字段保持不变 ...
    "type_calc": "TYPE",
    "prod_code": "prod_code",
    "defect_desc": "defect_desc",
    "oper_group": "oper_group",
    "ratio": "日良损",
    "month_ratio": "CT月",
    "week_ratio": "CT周",
    "batch_ratio": "本批次",
    "worsening_text": "批次恶化",
    "lot_input_ratio": "批次产出率",
    "batch_gap": "本批次-上批次",
    "multiplier": "倍数",
    "hist_time": "最新HL时间",
    "hist_count": "HL次数",
    "hist_ng_qty": "ng_qty",
    "hist_reason": "HL原因",
    
    # [新增] 判定结果字段
    "is_real_anomaly": "AI判定", 
    "anomaly_type": "异常类型",   # [新增]
    "anomaly_reasons": "判定理由",
    "generated_report": "📝通报内容(可编辑)" # [新增] 核心交互列
}

COLUMN_CONFIG = {
    "✅": st.column_config.CheckboxColumn("选", width="small"),
    
    # [新增] 使用 Tag (标签) 来区分异常类型
    "异常类型": st.column_config.Column(
        "异常类型",
        width="small",
        help="CT站点=真实异常; 非CT站点=当站超规"
    ),
    # [新增] 真实性列配置
    "🤖真实性": st.column_config.CheckboxColumn(
        "AI判定",
        help="基于倍数、产出率、历史水位及集中性的综合判定",
        width="small",
        disabled=True # 只读
    ),
    "判定理由": st.column_config.TextColumn(
        "判定理由",
        width="medium",
        help="符合判定的具体规则细节"
    ),
    "通报内容(可编辑)": st.column_config.TextColumn(
        "通报内容(可编辑)",
        width="large",
        help="根据判定理由，生成通报内容"
    ),
    "TYPE": st.column_config.TextColumn("TYPE", width="small"),
    "prod_code": st.column_config.TextColumn("prod_code", width="small"),
    "defect_desc": st.column_config.TextColumn("defect_desc", width="medium"),
    "oper_group": st.column_config.TextColumn("oper_group", width="small"), # 确保站点列宽度合适
    "批次恶化": st.column_config.TextColumn("批次恶化", width="medium"),
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

# --- 2. 数据适配器 ---
def prepare_display_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    
    # A. 补全缺失列
    if 'type_calc' not in df.columns:
        if 'HL次数' in df.columns:
            df['TYPE'] = df['HL次数'].apply(lambda x: '批次首发' if x <= 1 else '非批次首发')
        else:
            df['TYPE'] = ""
    else:
        df['TYPE'] = df['type_calc'] # 显式赋值

    # [新增] 确保 boolean 列正确，否则 CheckboxColumn 会报错
    if 'is_real_anomaly' in df.columns:
        df['is_real_anomaly'] = df['is_real_anomaly'].fillna(False).astype(bool)
        
    # B. 插入勾选列
    df.insert(0, "✅", False)
    
    # === 🔍 新增：百分比数值修正 (x 100) ===
    # 定义所有需要展示为 % 的列名 (根据 COLUMN_MAPPING)
    pct_cols = [
        "ratio", "month_ratio", "week_ratio", "batch_ratio", 
        "lot_input_ratio", "batch_gap", "multiplier"
    ]
    
    for col in pct_cols:
        if col in df.columns:
            # 转换为 numeric，非数字变 NaN (fillna 0)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            # 乘以 100
            df[col] = df[col] * 100
            
    # C. 映射列名
    rename_dict = {k:v for k,v in COLUMN_MAPPING.items() if k in df.columns}
    df_display = df.rename(columns=rename_dict)
    
    # D. 排序: 确保显示的列都在 MAPPING 里
    final_cols = ["✅"]
    for k, v in COLUMN_MAPPING.items():
        if v in df_display.columns:
            final_cols.append(v)
            
    # 补充未匹配到的 TYPE
    if 'TYPE' in df.columns and 'TYPE' not in df_display.columns: # 如果前面没映射上
        if 'TYPE' not in final_cols:
            final_cols.insert(1, 'TYPE')

    return df_display[final_cols]