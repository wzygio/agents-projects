# 文件路径: src/daily_report/core/generator.py
import pandas as pd
from src.anomaly_monitor.core.concentration_analyzer import ConcentrationAnalyzer

class ReportGenerator:
    """
    【核心组件】文本生成器
    
    职责：
    1. 接收单行异常数据 (Series)。
    2. 调用 Analyzer 获取集中性分析。
    3. 格式化数值 (百分比、日期)。
    4. 填充标准文本模板。
    """

    def __init__(self, analyzer: ConcentrationAnalyzer):
        self.analyzer = analyzer

    def generate_text(self, row: pd.Series) -> str:
        """
        生成单条异常通报文本
        :param row: hl_data 中的一行数据
        """
        # --- 1. 提取基础字段 (防御性获取，防止 KeyError) ---
        prod = str(row.get('prod_code', 'Unknown'))
        defect_desc = str(row.get('defect_desc', 'Unknown'))
        defect_code = str(row.get('defect_code', '')) # 用于关联 yield data
        station = str(row.get('oper_group', 'Unknown'))
        batch = str(row.get('batch', ''))
        
        # --- 2. 格式化日期与数值 ---
        # 时间格式化: 2025-12-02 10:00:00 -> 12/02 10:00
        first_report_time = str(row.get('interface_time', ''))
        if len(first_report_time) > 10:
             # 简单的字符串切片，适配 "YYYY-MM-DD HH:MM:SS" 或 "YYYY/MM/DD..."
             # 取月/日 HH:MM，通常在索引 5 到 16 之间
             # 更稳健的做法是用 pd.to_datetime，但在 DataLoader 已处理过，这里直接切
             try:
                 dt = pd.to_datetime(first_report_time)
                 first_report_str = dt.strftime('%m/%d %H:%M')
             except:
                 first_report_str = first_report_time[:16] # 降级处理
        else:
            first_report_str = first_report_time

        # 批次日期简写: "25/10/29..." -> "10/29"
        batch_date_short = row.get('batch_date_str', '')
        if not batch_date_short and len(batch) > 8:
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
        # 逻辑: 检查 "最新HL时间" 是否有值。有值 -> 是 (再发), 空 -> 否 (首发)
        # 注意: DataLoader 读取时可能将空值转为 nan (float) 或 NaT
        last_hl_time = row.get('最新HL时间', None)
        is_recurring = "否"
        if pd.notnull(last_hl_time) and str(last_hl_time).strip() != '' and str(last_hl_time).lower() != 'nan':
            is_recurring = "是"
        
        # B. 基础分析 (集中性) -> 调用 Analyzer
        # 传入 prod, defect_code (yield data通常用code), batch
        analysis_result = self.analyzer.analyze(prod, defect_code, batch)

        # C. 影响范围
        ng_qty = int(float(row.get('ng_qty', 0)))
        impact_scope = f"影响数量 {ng_qty} pcs"

        # --- 4. 模板填充 (F-String) ---
        # 这里的模板严格遵照您提供的格式
        template = f"""【产品型号】{prod}
【不良名称】{defect_desc}
【发生站点】{station}
【是否再发】{is_recurring}
【首次通报】{first_report_str}
【基础分析】{analysis_result}
【异常良损】当日良损{ratio_day}，当月良损{ratio_month}，批次良损{ratio_batch}，{batch_date_short}较上批次恶化{ratio_gap}
【异常原因】***
【Inline监控】若已监控到：明确监控到的站点/RS Code/恶化比例（数字化呈现 ）；若没监控到，给出后续 Inline监控如何优化的方案
【是否止血】***
【影响范围】{impact_scope}
【改善措施】要求有工艺改善的落地措施，无措施时需要当天上良率会进行汇报
【整合对接】刘力文
【责任部门】***
【责任科室】***"""

        return template.strip()