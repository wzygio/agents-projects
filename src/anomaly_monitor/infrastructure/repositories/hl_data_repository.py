import pandas as pd
import numpy as np
import logging
from ..hl_data_loader import HLDataLoader

logger = logging.getLogger(__name__)

class HLDataRepository:
    """
    【仓储层】数据仓库 (Repository Layer)
    职责：
    1. 向 Service 层隐藏底层 I/O 细节。
    2. 负责“三表合一”的复杂业务逻辑 (复刻 Spotfire)。
    3. 提供 get_processed_hl_data() 和 get_yield_detail_data() 标准接口。
    """
    def __init__(self):
        # 依赖注入 Loader
        self.loader = HLDataLoader()

    def get_processed_hl_data(self) -> pd.DataFrame:
        """
        【核心逻辑】复刻 Spotfire 宽表生成过程
        Sources: hl_data + batch_yield_data + hl_csv_data
        """
        # 1. 从 Loader 获取原始数据
        df_hl = self.loader.load_raw_dataframe('hl_raw')          # 主表
        df_yield = self.loader.load_raw_dataframe('batch_yield')  # 产出表
        df_hist = self.loader.load_raw_dataframe('hl_history')    # 历史表
        
        if df_hl.empty: 
            logger.warning("主表 (hl_data) 为空，无法生成数据。")
            return pd.DataFrame()

        # --- A. 基础数值转换 ---
        num_cols = ['ratio', 'batch_ratio', 'lag_ratio', 'month_ratio', 'ng_qty']
        for col in num_cols:
            if col in df_hl.columns:
                df_hl[col] = pd.to_numeric(df_hl[col], errors='coerce').fillna(0)

        # --- B. 计算列: batch_gap ---
        if 'batch_ratio' in df_hl.columns and 'lag_ratio' in df_hl.columns:
            df_hl['batch_gap'] = df_hl['batch_ratio'] - df_hl['lag_ratio']
        else:
            df_hl['batch_gap'] = 0.0

        # --- C. 计算列: 批次恶化 (文本) ---
        if 'batch' in df_hl.columns:
            # Python slice [3:8] 对应 Spotfire substring(4,5)
            date_str = df_hl['batch'].astype(str).apply(lambda x: x[3:8] if len(x)>8 else x)
            gap_str = (df_hl['batch_gap'] * 100).map('{:,.2f}%'.format)
            df_hl['worsening_text'] = str(date_str) + "批次较上批次恶化" + gap_str

        # --- D. 计算列: 倍数 ---
        if 'month_ratio' in df_hl.columns:
            df_hl['multiplier'] = df_hl.apply(
                lambda x: x['batch_ratio'] / x['month_ratio'] if x['month_ratio'] != 0 else 0, 
                axis=1
            )

        # --- E. 筛选最新行 (DenseRank) ---
        if 'interface_time' in df_hl.columns:
            df_hl['dt'] = pd.to_datetime(df_hl['interface_time'], errors='coerce')
            df_hl = df_hl.sort_values('dt', ascending=False)
            # 按 prod + defect 分组取最新
            df_hl = df_hl.groupby(['prod_code', 'defect_desc'], as_index=False).first()
            df_hl.drop(columns=['dt'], inplace=True)

        # --- F. 连接历史数据 (Step 4 Logic) ---
        if not df_hist.empty:
            # 1. 历史表按时间降序去重
            hist_time_col = 'date_time' if 'date_time' in df_hist.columns else 'interface_time'
            if hist_time_col in df_hist.columns:
                df_hist['dt_h'] = pd.to_datetime(df_hist[hist_time_col], errors='coerce')
                df_hist = df_hist.sort_values('dt_h', ascending=False)
            
            # 2. 选取需要的列并去重
            cols_needed = ['prod_code', 'defect_desc', 'hl次数', '最新hl时间', 'hl原因']
            cols_exist = [c for c in cols_needed if c in df_hist.columns]
            
            if cols_exist:
                df_hist_unique = df_hist.groupby(['prod_code', 'defect_desc'], as_index=False).first()
                # Left Join
                df_hl = pd.merge(
                    df_hl,
                    df_hist_unique[cols_exist],
                    on=['prod_code', 'defect_desc'],
                    how='left'
                )
                # 数值转换
                if 'hl次数' in df_hl.columns:
                    df_hl['hl次数'] = pd.to_numeric(df_hl['hl次数'], errors='coerce').fillna(1)

        # --- G. 连接产出数据 (Step 5 Logic) ---
        if not df_yield.empty:
            # Join Key 清洗
            df_hl['k1'] = df_hl['prod_code'].astype(str).str.strip()
            df_hl['k2'] = df_hl['batch'].astype(str).str.strip()
            
            df_yield['k1'] = df_yield['prod_code'].astype(str).str.strip()
            # 兼容列名 sub_prod_id 或 batch
            b_col = 'sub_prod_id' if 'sub_prod_id' in df_yield.columns else 'batch'
            df_yield['k2'] = df_yield[b_col].astype(str).str.strip()
            
            # Join
            cols_y = ['k1', 'k2', 'lot_input_ratio']
            cols_y_valid = [c for c in cols_y if c in df_yield.columns]
            
            df_hl = pd.merge(df_hl, df_yield[cols_y_valid], on=['k1', 'k2'], how='left')
            df_hl.drop(columns=['k1', 'k2'], inplace=True)

        return df_hl

    def get_yield_detail_data(self) -> pd.DataFrame:
        """
        获取 Panel 级明细数据 (用于集中性分析)
        """
        df = self.loader.load_raw_dataframe('ct_yield')
        
        if df.empty: return pd.DataFrame()
        
        # 1. 过滤不良品
        if 'ng_qty' in df.columns:
            df['ng_qty'] = pd.to_numeric(df['ng_qty'], errors='coerce').fillna(0)
            df = df[df['ng_qty'] > 0].copy()
            
        # 2. 解析 Mapping 坐标 (Spotfire 的计算列逻辑)
        if 'panel_id' in df.columns:
            df['panel_id'] = df['panel_id'].astype(str).replace('nan', '')
            valid = df['panel_id'].str.len() > 4
            df = df[valid].copy()
            
            df['行'] = df['panel_id'].str[-4:-2]
            df['列'] = df['panel_id'].str[-2:]
            df['membrane_pos'] = str(df['行']) + "-" + df['列']
            
        return df