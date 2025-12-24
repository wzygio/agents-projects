import pandas as pd
import numpy as np
import logging
from infrastructure.loader import HLDataLoader
from packages.anomaly_monitor.src.config import load_config


logger = logging.getLogger(__name__)

class HLDataRepository:
    """
    【仓储层】数据仓库 (Repository Layer)
    职责：
    1. 向 Service 层隐藏底层 I/O 细节。
    2. 负责“三表合一”的复杂业务逻辑 (复刻 Spotfire)。
    3. 修复数据互斥问题：确保 CT 和 检测站点 数据并存。
    """
    def __init__(self):
        self.config = load_config()
        self.loader = HLDataLoader(self.config)

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
        # 修复逻辑：使用 apply 逐行处理，防止整列数据被当做字符串拼接
        if 'batch' in df_hl.columns and 'batch_gap' in df_hl.columns:
            def generate_worsening_text(row):
                batch_val = str(row.get('batch', ''))
                # 截取日期: 25/10/29... -> 10/29
                date_part = batch_val[3:8] if len(batch_val) >= 8 else batch_val
                # 格式化百分比
                gap_val = row.get('batch_gap', 0)
                gap_part = f"{gap_val * 100:.2f}%"
                return f"{date_part}批次较上批次恶化{gap_part}"

            df_hl['worsening_text'] = df_hl.apply(generate_worsening_text, axis=1)
        else:
            df_hl['worsening_text'] = ""

        # --- D. 计算列: 倍数 ---
        if 'month_ratio' in df_hl.columns:
            df_hl['multiplier'] = df_hl.apply(
                lambda x: x['batch_ratio'] / x['month_ratio'] if x['month_ratio'] != 0 else 0, 
                axis=1
            )

        # --- E. 筛选最新行 (DenseRank) ---
        # 关键修复：将 oper_group 加入分组键，防止不同站点互斥
        if 'interface_time' in df_hl.columns:
            df_hl['dt'] = pd.to_datetime(df_hl['interface_time'], errors='coerce')
            df_hl = df_hl.sort_values('dt', ascending=False)
            
            # GroupBy Keys: 产品 + 不良 + 站点
            group_keys = ['prod_code', 'defect_desc']
            if 'oper_group' in df_hl.columns:
                group_keys.append('oper_group')
                
            df_hl = df_hl.groupby(group_keys, as_index=False).first()
            df_hl.drop(columns=['dt'], inplace=True)

        # --- F. 连接历史数据 (Step 4 Logic) ---
        if not df_hist.empty:
            # 1. 历史表处理：按时间降序
            hist_time_col = 'date_time' if 'date_time' in df_hist.columns else 'interface_time'
            if hist_time_col in df_hist.columns:
                df_hist['dt_h'] = pd.to_datetime(df_hist[hist_time_col], errors='coerce')
                df_hist = df_hist.sort_values('dt_h', ascending=False)
            
            # 2. 选取列并严格去重 (Prod + Defect 维度)
            # 注意：历史数据通常是全局维度的，所以这里我们只按 prod+defect 去重
            # 这样，无论是 CT 还是 MVI，都能匹配到同一个“历史次数”
            cols_needed = ['prod_code', 'defect_desc', 'HL次数', '最新hl时间', 'hl原因']
            cols_exist = [c for c in cols_needed if c in df_hist.columns]
            
            if cols_exist:
                # 严格去重，确保 1:N 关系，防止膨胀
                df_hist_unique = df_hist.groupby(['prod_code', 'defect_desc'], as_index=False).first()
                
                # Left Join
                df_hl = pd.merge(
                    df_hl,
                    df_hist_unique[cols_exist],
                    on=['prod_code', 'defect_desc'],
                    how='left'
                )
                
                # 数值转换
                if 'HL次数' in df_hl.columns:
                    df_hl['HL次数'] = pd.to_numeric(df_hl['HL次数'], errors='coerce').fillna(1)

        # --- G. 连接产出数据 (Step 5 Logic) ---
        if not df_yield.empty:
            # Join Key 清洗
            df_hl['k1'] = df_hl['prod_code'].astype(str).str.strip()
            df_hl['k2'] = df_hl['batch'].astype(str).str.strip()
            
            df_yield['k1'] = df_yield['prod_code'].astype(str).str.strip()
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
        # 1. 读取数据
        df = self.loader.load_raw_dataframe('ct_yield')
        
        if df.empty: return pd.DataFrame()
        
        # 2. 过滤不良品 (只保留 ng_qty > 0)
        if 'ng_qty' in df.columns:
            df['ng_qty'] = pd.to_numeric(df['ng_qty'], errors='coerce').fillna(0)
            df = df[df['ng_qty'] > 0].copy()
            
        # 3. 解析 Mapping 坐标
        if 'panel_id' in df.columns:
            # 确保是字符串
            df['panel_id'] = df['panel_id'].astype(str).replace('nan', '')
            
            # 过滤非法ID (长度不够切片的)
            valid = df['panel_id'].str.len() > 4
            df = df[valid].copy()
            
            # --- 核心修复区域 ---
            
            # A. 提取坐标 (使用 .str 访问器，这是 Pandas 专用的字符串向量化操作)
            # 假设 ID "L3...1A2B": 行=1A, 列=2B
            df['row_code'] = df['panel_id'].str[-4:-2]
            df['col_code'] = df['panel_id'].str[-2:]
            
            # B. 合成坐标 (Map Position)
            # 直接相加，Pandas 会自动对应行，绝不会出现整列拼接的情况
            df['membrane_pos'] = df['row_code'] + "-" + df['col_code'] # type: ignore
            
            # 为了兼容旧逻辑，保留中文列名 (如果 Analyzer 用到了)
            df['行'] = df['row_code']
            df['列'] = df['col_code']
            
        return df