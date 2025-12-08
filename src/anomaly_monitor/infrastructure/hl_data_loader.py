import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.config import ConfigLoader

logger = logging.getLogger(__name__)

class HLtDataLoader:
    """
    Infrastructure Layer: Spotfire 逻辑 1:1 复刻版 (三表合一)
    """
    def __init__(self):
        self.config = ConfigLoader()
        self.input_dir = Path(self.config.get("data.hl_resources_dir")) # type: ignore
        self.cache_dir = Path(self.config.get("data.cache_path")) # type: ignore
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_and_cache(self, file_key: str) -> pd.DataFrame:
        """通用读取方法：自动处理编码、分隔符、Parquet缓存"""
        filename = self.config.get(f"data.files.{file_key}")
        if not filename:
            # 尝试默认文件名，防止配置漏填
            defaults = {
                'hl_raw': 'hl_data.csv',
                'batch_yield': 'batch_yield_data.csv',
                'hl_history': 'hl_csv_data.csv',
                'ct_yield': 'ct_yield_data.csv'
            }
            filename = defaults.get(file_key, "")
            if not filename:
                return pd.DataFrame()

        csv_path = self.input_dir / filename # type: ignore
        parquet_path = self.cache_dir / (Path(filename).stem + ".parquet") # type: ignore

        # 1. 尝试读缓存
        if parquet_path.exists():
            if not csv_path.exists() or (parquet_path.stat().st_mtime > csv_path.stat().st_mtime):
                try:
                    return pd.read_parquet(parquet_path)
                except: pass

        if not csv_path.exists():
            # 尝试 .txt
            csv_path = csv_path.with_suffix('.txt')
            if not csv_path.exists():
                logger.warning(f"文件未找到: {filename}")
                return pd.DataFrame()

        # 2. 读取源文件
        df = pd.DataFrame()
        # 常见编码尝试
        for enc in ['utf-8', 'gbk', 'utf-16']:
            for sep in [',', '\t']:
                try:
                    # 全部读为str，防止精度丢失
                    temp = pd.read_csv(csv_path, sep=sep, encoding=enc, dtype=str)
                    if len(temp.columns) > 1:
                        df = temp
                        break
                except: continue
            if not df.empty: break
        
        if df.empty: return pd.DataFrame()

        # 3. 标准化
        df.columns = df.columns.str.strip().str.lower()
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 4. 写缓存
        try:
            df.to_parquet(parquet_path, index=False)
        except: pass
        
        return df

    def get_processed_hl_data(self) -> pd.DataFrame:
        """
        【核心业务逻辑】复刻 Spotfire 构建过程
        Sources: hl_data + batch_yield_data + hl_csv_data
        """
        # 1. 加载三个源文件
        df_hl = self._load_and_cache('hl_raw')          # 主表
        df_yield = self._load_and_cache('batch_yield')  # 产出表
        df_hist = self._load_and_cache('hl_history')    # 历史表 (关键!)
        
        if df_hl.empty: return pd.DataFrame()

        # --- A. 基础数值转换 (hl_data) ---
        # 确保 ng_qty 被正确转换为数字
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
            # substring([batch],4,5) -> Python slice [3:8]
            date_str = df_hl['batch'].astype(str).apply(lambda x: x[3:8] if len(x)>8 else x)
            gap_str = (df_hl['batch_gap'] * 100).map('{:,.2f}%'.format)
            df_hl['worsening_text'] = date_str + "批次较上批次恶化" + gap_str # type: ignore

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
        # 这里的关键是：hl_csv_data 包含了 'HL次数', '最新HL时间' 等字段
        if not df_hist.empty:
            # 1. 历史表也可能有重复，先按时间降序去重，取最新状态
            # 假设历史表有 'date_time' 或类似字段
            hist_time_col = 'date_time' if 'date_time' in df_hist.columns else 'interface_time'
            if hist_time_col in df_hist.columns:
                df_hist['dt_h'] = pd.to_datetime(df_hist[hist_time_col], errors='coerce')
                df_hist = df_hist.sort_values('dt_h', ascending=False)
                df_hist.drop(columns=['dt_h'], inplace=True)
            
            # 2. 按 prod + defect 去重 (模拟 Left Single Match)
            # 选取我们需要的历史列 (根据日志 Step 4 的 "添加的列")
            cols_needed = ['prod_code', 'defect_desc', 'hl次数', '最新hl时间', 'hl原因']
            # 检查列名是否存在 (忽略大小写差异，因为已经lower过了)
            cols_exist = [c for c in cols_needed if c in df_hist.columns]
            
            if cols_exist:
                # 去重
                df_hist_unique = df_hist.groupby(['prod_code', 'defect_desc'], as_index=False).first()
                
                # 执行 Left Join
                df_hl = pd.merge(
                    df_hl,
                    df_hist_unique[cols_exist],
                    on=['prod_code', 'defect_desc'],
                    how='left'
                )
                
                # 转换 HL次数 为数字
                if 'hl次数' in df_hl.columns:
                    df_hl['hl次数'] = pd.to_numeric(df_hl['hl次数'], errors='coerce').fillna(1) # 默认为1(首发)

        # --- G. 连接产出数据 (Step 5 Logic) ---
        if not df_yield.empty:
            # 准备 Join Key
            df_hl['k1'] = df_hl['prod_code'].astype(str).str.strip()
            df_hl['k2'] = df_hl['batch'].astype(str).str.strip()
            
            df_yield['k1'] = df_yield['prod_code'].astype(str).str.strip()
            # 找 sub_prod_id
            b_col = 'sub_prod_id' if 'sub_prod_id' in df_yield.columns else 'batch'
            df_yield['k2'] = df_yield[b_col].astype(str).str.strip()
            
            # Join
            cols_y = ['k1', 'k2', 'lot_input_ratio']
            cols_y_valid = [c for c in cols_y if c in df_yield.columns]
            
            df_hl = pd.merge(df_hl, df_yield[cols_y_valid], on=['k1', 'k2'], how='left')
            df_hl.drop(columns=['k1', 'k2'], inplace=True)

        return df_hl

    def get_yield_detail_data(self) -> pd.DataFrame:
        """读取明细数据 (逻辑保持不变)"""
        df = self._load_and_cache('ct_yield')
        if df.empty: return pd.DataFrame()
        
        if 'ng_qty' in df.columns:
            df['ng_qty'] = pd.to_numeric(df['ng_qty'], errors='coerce').fillna(0)
            df = df[df['ng_qty'] > 0].copy()
            
        if 'panel_id' in df.columns:
            df['panel_id'] = df['panel_id'].astype(str).replace('nan', '')
            valid = df['panel_id'].str.len() > 4
            df = df[valid].copy()
            df['行'] = df['panel_id'].str[-4:-2]
            df['列'] = df['panel_id'].str[-2:]
            df['membrane_pos'] = df['行'] + "-" + df['列'] # type: ignore
            
        return df