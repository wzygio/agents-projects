import pandas as pd
import numpy as np
from src.common.infrastructure.file_io import FileAdapter

class DataRepository:
    """
    数据仓库：负责向业务层提供处理好的、干净的数据集。
    集成 SourceLogicReplicator 逻辑。
    """
    def __init__(self):
        self.adapter = FileAdapter()

    def get_processed_hl_data(self) -> pd.DataFrame:
        """
        获取处理后的 HL 数据 (复刻 Spotfire 逻辑)
        """
        # 1. 加载原始表
        df_hl = self.adapter.load_dataframe('hl_raw')
        df_batch = self.adapter.load_dataframe('batch_yield')
        
        if df_hl.empty: return pd.DataFrame()

        # 2. 数值转换
        num_cols = ['ratio', 'batch_ratio', 'lag_ratio', 'ng_qty', 'hl次数']
        for col in num_cols:
            if col in df_hl.columns:
                df_hl[col] = pd.to_numeric(df_hl[col], errors='coerce').fillna(0)

        # 3. 计算 batch_gap (Spotfire 逻辑)
        if 'batch_gap' not in df_hl.columns:
            df_hl['batch_gap'] = df_hl['batch_ratio'] - df_hl['lag_ratio']

        # 4. 筛选最新记录 (DenseRank 逻辑)
        if 'interface_time' in df_hl.columns:
            df_hl['dt'] = pd.to_datetime(df_hl['interface_time'], errors='coerce')
            df_hl = df_hl.sort_values('dt', ascending=False)
            df_hl = df_hl.groupby(['prod_code', 'defect_desc'], as_index=False).first()
            df_hl.drop(columns=['dt'], inplace=True)

        # 5. Join Batch Yield (如果有数据)
        if not df_batch.empty:
            # 确保 Join 键去空格
            df_hl['join_prod'] = df_hl['prod_code'].astype(str).str.strip()
            df_hl['join_batch'] = df_hl['batch'].astype(str).str.strip()
            
            # 假设 batch_yield 的批次列名为 'sub_prod_id' (需根据实际 csv 确认)
            # 这里做一个容错，找最像批次的列
            batch_col = 'sub_prod_id' if 'sub_prod_id' in df_batch.columns else 'batch'
            
            df_batch['join_prod'] = df_batch['prod_code'].astype(str).str.strip()
            df_batch['join_batch'] = df_batch[batch_col].astype(str).str.strip()
            
            df_hl = pd.merge(
                df_hl,
                df_batch[['join_prod', 'join_batch', 'lot_input_ratio', 'now_ct_qty']], # 只取需要的列
                on=['join_prod', 'join_batch'],
                how='left'
            )

        # 6. 生成文本所需的辅助列
        # 生成 "10/29"
        if 'batch' in df_hl.columns:
             df_hl['batch_date_str'] = df_hl['batch'].astype(str).str[3:8]
             
        return df_hl

    def get_yield_detail_data(self) -> pd.DataFrame:
        """
        获取 Panel 级明细数据 (已解析坐标)
        """
        df = self.adapter.load_dataframe('yield_detail') # 读取 ct_yield_data
        
        if df.empty: return pd.DataFrame()

        # 1. 过滤不良品
        if 'ng_qty' in df.columns:
            df['ng_qty'] = pd.to_numeric(df['ng_qty'], errors='coerce').fillna(0)
            df = df[df['ng_qty'] > 0].copy()

        # 2. 解析坐标 (从 Panel ID)
        if 'panel_id' in df.columns:
            # 规则：最后4位 (前2位行，后2位列)
            valid_mask = df['panel_id'].str.len() > 4
            df = df[valid_mask].copy()
            
            df['行'] = df['panel_id'].str[-4:-2]
            df['列'] = df['panel_id'].str[-2:]
            df['membrane_pos'] = df['行'] + "-" + df['列']

        return df