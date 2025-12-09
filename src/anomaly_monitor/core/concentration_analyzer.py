# 文件路径: src/daily_report/core/analyzer.py
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ConcentrationAnalyzer:
    """
    【核心算法组件】集中性分析器
    
    职责：基于良率明细数据，判断是否存在 Lot/Map/Sheet 维度的集中性异常。
    算法策略：
    1. 门槛判定 (Gatekeeper): 使用 CR-5 (前三名累计占比) 和 Top-1 占比判断整体是否存在集中趋势。
    2. 名单生成 (Roll Call): 使用 20% 动态梯队法，列出具体的异常对象。
    """

    def __init__(self, df_yield_ng: pd.DataFrame):
        """
        :param df_yield_ng: 必须是已经过滤出 NG (ng_qty > 0) 且解析好坐标的 DataFrame
        """
        self.df = df_yield_ng
        
        # 预处理：确保坐标列存在 (防御性编程)
        if not self.df.empty and 'membrane_pos' not in self.df.columns:
            if '行' in self.df.columns and '列' in self.df.columns:
                 self.df['membrane_pos'] = self.df['行'].astype(str) + "-" + self.df['列'].astype(str)
            else:
                 logger.warning("Analyzer 初始化警告: 缺少 'membrane_pos' 或 '行/列' 字段，Map 分析将不可用。")

    def analyze(self, prod: str, defect: str, batch_name: str) -> str:
        """
        执行多维度集中性分析
        :return: 格式化的分析文本，例如 "Lot集中: L5...; Map集中: 2E-..."
        """
        if self.df.empty:
            return "Map/Lot无明显集中性 (无明细数据)"

        # 1. 极速筛选 (Boolean Indexing)
        # 确保类型一致，转为字符串并去空格
        batch_str = str(batch_name).strip()
        prod_str = str(prod).strip()
        defect_str = str(defect).strip()

        # 注意：这里假设 df_yield 中的 defect_code 与 hl_data 中的 defect_code 对齐
        # 如果 hl_data 传进来的是 defect_desc (中文)，这里可能需要映射，或者 yield data 里也有 desc
        # 目前假设 yield data 使用 defect_code，hl data 传入 defect_code
        mask = (
            (self.df['prod_code'] == prod_str) & 
            (self.df['defect_code'] == defect_str) & 
            (self.df['lot'] == batch_str)
        )
        subset = self.df[mask]
        
        if subset.empty:
            return "Map/Lot无明显集中性"

        total_ng = len(subset)
        
        # 定义分析维度: (显示名称, DataFrame列名)
        targets = {
            "Lot": "lot_id",
            "Map": "membrane_pos",
            "Sheet": "sheet_id"
        }
        
        report_parts = []
        
        # 2. 遍历维度进行分析
        for label, col in targets.items():
            if col not in subset.columns:
                continue
            
            # 聚合计数 (Value Counts 是 Pandas 性能最高的聚合方式)
            counts = subset[col].value_counts()
            if counts.empty:
                continue
            
            # --- 核心算法阶段 1: 整体态势判定 (Gatekeeper) ---
            
            top_1_count = counts.iloc[0]
            top_5_count = counts.head(5).sum()
            
            top_1_ratio = top_1_count / total_ng
            cr_5_ratio = top_5_count / total_ng # Cumulative Ratio Top 5
            
            is_concentrated = False
            
            if total_ng >= 20:
                if top_1_ratio >= 0.4:
                    is_concentrated = True
                elif cr_5_ratio >= 0.8:
                    is_concentrated = True
            elif total_ng > 0 and top_1_ratio > 0.6:
                 # 极小样本保护：一共坏2个，1个坏在这，也算集中
                 is_concentrated = True

            if not is_concentrated:
                continue

            # --- 核心算法阶段 2: 动态梯队名单生成 (Roll Call) ---
            
            candidates = []
            benchmark_count = top_1_count # 以第一名为基准
            
            # 遍历前 10 名
            for name, count in counts.head(10).items():
                # 过滤底噪: 绝对数量必须 >= 4 (除非总数极少)
                if count < 4: continue
                
                # 动态截断: 必须达到老大数量的 50% 才有资格入选
                if count < (benchmark_count * 0.4):
                    break 
                
                # 格式化: 名称(数量) 或 名称(占比)
                # 这里的格式可以根据您的偏好调整，目前仅输出名称以保持简洁
                candidates.append(f"{name}")
            
            if candidates:
                # 拼接文本
                txt = f"{label}集中: {'/'.join(candidates)}"
                report_parts.append(txt)
        
        # 5. 输出最终结论
        if not report_parts:
            return "Map/Lot无明显集中性"
        else:
            return "；".join(report_parts)