import pandas as pd
import numpy as np
import logging
from ....common.infrastructure.hl_data_loader import HLDataLoader

logger = logging.getLogger(__name__)

class MWDLDataRepository:
    """
    【仓储层】MWDL 历史数据仓库
    职责：
    1. 提供历史批次良损数据的清洗与组装。
    2. 实现 "MWDL + DefectGroup + Yield" 的三表合一逻辑。
    """
    def __init__(self):
        self.loader = HLDataLoader()

    def get_processed_mwdl_data(self) -> pd.DataFrame:
        """
        生成完整的历史良损明细表
        """
        # 1. 加载三个源文件
        df_main = self.loader.load_raw_dataframe('mwdl_raw')         # 主表
        df_group = self.loader.load_raw_dataframe('defect_group_dict') # 字典表
        df_yield = self.loader.load_raw_dataframe('batch_yield')     # 产出表
        
        if df_main.empty: 
            return pd.DataFrame()

        # --- A. 基础清洗 ---
        # 确保数值列正确
        if 'ng_qty' in df_main.columns:
            df_main['ng_qty'] = pd.to_numeric(df_main['ng_qty'], errors='coerce').fillna(0)
        if 'input_qty' in df_main.columns:
            df_main['input_qty'] = pd.to_numeric(df_main['input_qty'], errors='coerce').fillna(0)
            
        # 处理 ratio_fanel (可能是 "3.70%" 字符串 或 0.037 数字)
        if 'ratio_fanel' in df_main.columns:
            # 先尝试转数字
            df_main['ratio_val'] = pd.to_numeric(df_main['ratio_fanel'].astype(str).str.rstrip('%'), errors='coerce')
            # 如果原数据是百分比字符串(3.70)，转完是3.70，需要除以100
            # 如果原数据是小数(0.037)，转完是0.037
            # 这里的判断比较 tricky，通常 mwdl 里的 ratio 列是纯小数
            if 'ratio' in df_main.columns:
                 df_main['ratio_val'] = pd.to_numeric(df_main['ratio'], errors='coerce').fillna(0)

        # --- B. 补全 defect_group (Join imp_ct_dft_group) ---
        if not df_group.empty and 'defect_code' in df_main.columns:
            # 准备字典
            cols_dict = ['defect_code', 'defect_group']
            cols_valid = [c for c in cols_dict if c in df_group.columns]
            
            # 去重：一个 code 可能对应多行，取第一条即可
            df_group_unique = df_group[cols_valid].groupby('defect_code', as_index=False).first()
            
            # Join
            df_main = pd.merge(df_main, df_group_unique, on='defect_code', how='left')

        # --- C. 补全 lot_input_ratio (Join batch_yield_data) ---
        # 关联键: prod_code + date_value (作为批次号)
        if not df_yield.empty and 'date_value' in df_main.columns:
            # 准备 Key
            df_main['k1'] = df_main['prod_code'].astype(str).str.strip()
            df_main['k2'] = df_main['date_value'].astype(str).str.strip()
            
            df_yield['k1'] = df_yield['prod_code'].astype(str).str.strip()
            b_col = 'sub_prod_id' if 'sub_prod_id' in df_yield.columns else 'batch'
            df_yield['k2'] = df_yield[b_col].astype(str).str.strip()
            
            # 选取列
            cols_y = ['k1', 'k2', 'lot_input_ratio']
            cols_y_valid = [c for c in cols_y if c in df_yield.columns]
            
            # Join
            df_main = pd.merge(df_main, df_yield[cols_y_valid], on=['k1', 'k2'], how='left')
            df_main.drop(columns=['k1', 'k2'], inplace=True)
            
            # 转换 input ratio 为数字
            if 'lot_input_ratio' in df_main.columns:
                df_main['lot_input_ratio'] = pd.to_numeric(df_main['lot_input_ratio'], errors='coerce')

        return df_main