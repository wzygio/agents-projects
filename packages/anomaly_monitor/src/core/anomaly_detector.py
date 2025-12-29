import pandas as pd
import numpy as np
import logging
from packages.anomaly_monitor.src.core.concentration_analyzer import ConcentrationAnalyzer

logger = logging.getLogger(__name__)

class AnomalyDetector:
    """
    【核心判决器】真实异常判定引擎 (V2.0 CT基准版)
    """

    def __init__(self, df_yield_detail: pd.DataFrame):
        self.concentrator = ConcentrationAnalyzer(df_yield_detail)

    def check_is_real_anomaly(self, row: pd.Series, df_history: pd.DataFrame) -> dict:
        """
        判断单行数据是否为真实异常
        :return: {
            "is_real": bool,
            "anomaly_type": str, # [新增] "真实异常" 或 "当站超规"
            "reasons": list[str]
        }
        """
        result = {
            "is_real": False,   
            "anomaly_type": "", # 默认为空
            "reasons": []
        }

        # --- 0. 数据预处理 ---
        try:
            batch_ratio = float(row.get('batch_ratio', 0))
            lot_input_ratio = float(row.get('lot_input_ratio', 0))
            multiplier = float(row.get('multiplier', 0))
            ng_qty = int(float(row.get('ng_qty', 0)))
            # [新增] 获取当前站点，用于最终定性
            current_station = str(row.get('oper_group', '')).upper().strip()
        except (ValueError, TypeError):
            return result

        # ============================================================
        # 第一层：基础门槛 (Gatekeeper)
        # ============================================================
        # 1. 本批次 > 0.1%
        if not (batch_ratio > 0.001): return result
        # 2. 产出率 > 20%
        if not (lot_input_ratio > 0.2): return result
        # 3. 倍数 > 30%
        if not (multiplier > 0.3): return result
        # 4. ng_qty > 20
        if not (ng_qty > 20): return result
            
        result["reasons"].append("通过基础筛选")

        # ============================================================
        # 第二层：相对恶化判定 (Relative Worsening) - CT基准
        # ============================================================
        # 核心修改：无论当前是 MVI 还是 AVI，历史对比对象永远是 CT
        
        is_hit = False
        hist_max_ct = 0.0
        
        if not df_history.empty:
            # 1. 筛选 CT 站点的历史数据
            if 'oper_group' in df_history.columns:
                # 筛选 oper_group 为 CT 的行
                df_hist_ct = df_history[df_history['oper_group'].str.upper() == 'CT'].copy()
            else:
                # 如果历史表没站点字段，降级处理，使用全部
                df_hist_ct = df_history

            if not df_hist_ct.empty and 'ratio' in df_hist_ct.columns:
                hist_vals = pd.to_numeric(df_hist_ct['ratio'], errors='coerce').fillna(0)
                
                # A. CT 历史上限 (Max)
                hist_max_ct = hist_vals.max()
                
                # B. 前两批次 (排除当前批次后的最近两个)
                current_batch_date = str(row.get('batch', ''))[3:8] # 简易匹配
                
                # 取最近的两个非当前批次的数据  
                if len(hist_vals) >= 2:
                    prev_2_mean = hist_vals.head(2).mean()
                elif len(hist_vals) == 1:
                    prev_2_mean = hist_vals.iloc[0]

        # 逻辑修改：不再直接 return，而是标记命中
        if batch_ratio > hist_max_ct:
            is_hit = True
            result["reasons"].append(f"超过CT历史上限({hist_max_ct:.2%})")
            
        # --- 判定 2: 集中性 ---
        prod = str(row.get('prod_code', ''))
        defect = str(row.get('defect_code', ''))
        batch = str(row.get('batch', ''))
        
        conc_text = self.concentrator.analyze(prod, defect, batch)
        
        if "无明显集中性" not in conc_text:
            is_hit = True
            result["reasons"].append("存在集中性")
            result["conc_text"] = conc_text

        # --- 最终裁决 ---
        if is_hit:
            result["is_real"] = True
            
            # 定性 (根据站点)
            if current_station == 'CT':
                result["anomaly_type"] = "真实异常"
            else:
                result["anomaly_type"] = "当站超规"
                
        return result