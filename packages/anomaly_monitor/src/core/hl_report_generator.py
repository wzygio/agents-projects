# 文件路径: src/anomaly_monitor/core/hl_report_generator.py
import logging
import pandas as pd
from typing import Optional

# 引入类型用于 Type Hint
from core.concentration_analyzer import ConcentrationAnalyzer
logger = logging.getLogger(__name__)

class HLReportGenerator:
    """
    【核心组件】HL 通报文本生成器 (V2.0 主动预生成版)
    
    职责：
    1. 接收单行异常数据 (Series)。
    2. 生成标准化的通报文本。
    3. 支持复用外部传入的 '集中性分析结果' (pre_calc_conc_text)，避免重复计算。
    """

    def __init__(self, analyzer: ConcentrationAnalyzer):
        self.analyzer = analyzer

    def generate_text(self, row: pd.Series, 
                      pre_calc_conc_text: Optional[str] = None, 
                      full_df: Optional[pd.DataFrame] = None) -> str: # [修改参数]
        """
        生成单条异常通报文本
        :param row: hl_data 中的一行数据
        :param pre_calc_conc_text: (可选) 预计算好的集中性文本。
                                如果在 Detector 阶段已经算过了，直接传进来，性能更高。
        """
        try:
            # --- 1. 提取基础字段 (防御性获取，防止 KeyError) ---
            prod = str(row.get('prod_code', 'Unknown'))
            defect_desc = str(row.get('defect_desc', 'Unknown'))
            defect_code = str(row.get('defect_code', '')) # 用于关联 yield data
            batch = str(row.get('batch', 'Unknown'))

            station = self._resolve_occurrence_station(row, full_df)
            
            # 3. 格式化日期与数值
            # 时间格式化: 2025-12-02 10:00:00 -> 12/02 10:00
            first_report_time = str(row.get('interface_time', ''))
            if len(first_report_time) > 10:
                try:
                    dt = pd.to_datetime(first_report_time)
                    first_report_str = dt.strftime('%m/%d %H:%M')
                except:
                    first_report_str = first_report_time[:16] # 降级处理
            else:
                first_report_str = first_report_time

            # 批次日期简写: "25/10/29..." -> "10/29"
            batch_date_short = row.get('batch_date_str', '')
            # 尝试从 date_value 或 batch 字段提取日期
            date_val = str(row.get('date_value', ''))
            if not batch_date_short:
                if len(date_val) > 5 and '/' in date_val: # 25/11/26 -> 11/26
                    # 假设格式是 YY/MM/DD
                    parts = date_val.split('/')
                    if len(parts) >= 3:
                        batch_date_short = f"{parts[1]}/{parts[2][:2]}" # 简单取中间两段
                elif len(batch) > 8:
                    batch_date_short = batch[3:8]

            # 百分比格式化函数
            def fmt_pct(val):
                try:
                    return "{:.2f}%".format(float(val) * 100)
                except (ValueError, TypeError):
                    return "0.00%"

            ratio_day = fmt_pct(row.get('ratio', 0))
            ratio_month = fmt_pct(row.get('month_ratio', 0))
            ratio_batch = fmt_pct(row.get('batch_ratio', 0))
            # 恶化比例 (batch_gap)
            gap_val = row.get('batch_gap', 0)
            ratio_gap = fmt_pct(gap_val)

            # --- 3. 逻辑判定 ---
            # A. 是否再发
            last_hl_time = row.get('hist_time', None) # 注意：Mapping里映射的是 'hist_time' -> '最新HL时间'
            is_recurring = "否"
            if pd.notnull(last_hl_time) and str(last_hl_time).strip() != '' and str(last_hl_time).lower() != 'nan':
                is_recurring = "是"
            
            # B. 基础分析 (集中性) -> [核心修改] 优先使用预计算结果
            if pre_calc_conc_text is not None:
                analysis_result = pre_calc_conc_text
            else:
                # 只有在没传的时候才调用 analyzer (兜底)
                # 注意：analyzer 内部处理异常，一般不会报错
                analysis_result = self.analyzer.analyze(prod, defect_code, batch)

            # C. 影响范围
            ng_qty = int(float(row.get('ng_qty', 0)))
            impact_scope = f"影响数量 {ng_qty} pcs"

            # --- 4. 模板填充 (F-String) ---
            lines = [
                f"【产品型号】{prod}",
                f"【不良名称】{defect_desc}",
                f"【发生站点】{station}",
                f"【是否再发】{is_recurring}",
                f"【首次通报】{first_report_str}",
                f"【基础分析】{analysis_result}",
                f"【异常良损】当日良损{ratio_day}，当月良损{ratio_month}，批次良损{ratio_batch}，{batch_date_short}较上批次恶化{ratio_gap}",
                f"【异常原因】***",
                f"【Inline监控】若已监控到：明确监控到的站点/RS Code/恶化比例（数字化呈现 ）；若没监控到，给出后续 Inline监控如何优化的方案",
                f"【是否止血】***",
                f"【影响范围】{impact_scope}",
                f"【改善措施】要求有工艺改善的落地措施，无措施时需要当天上良率会进行汇报",
                f"【整合对接】***",
                f"【责任部门】***",
                f"【责任科室】***"
            ]
            
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"报告生成失败: {e}", exc_info=True)
            return "生成失败，请检查数据格式"
        
    def _resolve_occurrence_station(self, row: pd.Series, full_df: Optional[pd.DataFrame]) -> str:
        """
        [内部工具] 孪生站点查找逻辑
        如果当前是 CT，尝试去全局数据中找它的孪生行 (MVI/AVI)
        """
        current_station = str(row.get('oper_group', 'Unknown')).strip()
        
        # 只有 CT 需要查，且必须提供了全量数据才能查
        if current_station == 'CT' and full_df is not None and not full_df.empty:
            try:
                prod = row.get('prod_code')
                defect = row.get('defect_desc')
                
                # 筛选: 同产品 & 同不良 & 站点不是CT
                twins = full_df[
                    (full_df['prod_code'] == prod) & 
                    (full_df['defect_desc'] == defect) & 
                    (full_df['oper_group'] != 'CT')
                ]
                
                if not twins.empty:
                    # 找到了，返回发生站点 (如 MVI)
                    return str(twins.iloc[0]['oper_group'])
            except Exception:
                pass # 查不到或出错，静默失败，用回原值
        
        # 默认返回原始站点
        return current_station
            

