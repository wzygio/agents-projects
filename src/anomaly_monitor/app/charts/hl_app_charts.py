import streamlit as st
import pandas as pd
import logging
import sys
from pathlib import Path

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
    "anomaly_reasons": "判定理由"
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