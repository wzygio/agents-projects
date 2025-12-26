import logging
import pandas as pd
from typing import Dict, Any

# 引入 Service (您的核心逻辑)
from packages.anomaly_monitor.src.application.hl_report_service import HLReportService

logger = logging.getLogger(__name__)

class AnomalyMonitorGenerator:
    """
    [Application Service]
    异常监控全自动执行器。
    职责：封装 "加载 -> 判定 -> 自动筛选真实异常 -> 自动提交" 的闭环逻辑。
    """

    def __init__(self, service: HLReportService):
        self.service = service

    def generate(self) -> Dict[str, Any]:
        """
        执行全自动监控流程。
        
        Returns:
            Dict: 执行结果摘要 (包含处理数量、提交结果等)
        """
        logger.info("🤖 [Generator] 开始执行全自动异常监控流程...")

        # 1. 确保资源加载 (Lazy Loading)
        if self.service.df_hl is None or self.service.df_hl.empty:
            logger.info("⏳ [Generator] 正在加载数据资源...")
            self.service.load_resources()

        # 2. 执行批量 AI 判定
        # 这会填充 'is_real_anomaly' 和 'generated_report' (AI草稿) 列
        logger.info("🧠 [Generator] 正在执行 AI 批量判定...")
        self.service.run_batch_anomaly_detection()

        # 3. [自动化策略] 筛选目标数据
        # 策略：在全自动模式下，我们只关心并自动提交 "真实异常"
        df = self.service.df_hl
        if df is None or df.empty:
            logger.warning("⚠️ 数据资源加载失败，流程终止。")
            return {"status": "skipped", "reason": "data_loading_failed"}
        elif 'anomaly_type' not in df.columns:
            logger.warning("⚠️ 未找到判定结果列，流程终止。")
            return {"status": "skipped", "reason": "detection_failed"}

        target_df = df[df['anomaly_type'] == '真实异常'].copy()
        real_count = len(target_df)

        if target_df.empty:
            msg = "✅ [Generator] 本次扫描未发现真实异常，无需写入台账。"
            logger.info(msg)
            return {"status": "success", "message": msg, "count": 0}

        logger.info(f"🎯 [Generator] 发现 {real_count} 条真实异常，准备自动写入台账...")

        # 4. [自动化策略] 数据清洗与准备
        # 确保 'generated_report' 列有值，如果没有，再次强制生成
        # (双重保险，防止 run_batch_anomaly_detection 中的生成逻辑被跳过)
        mask_empty_report = (target_df['generated_report'] == "") | (target_df['generated_report'].isna())
        if mask_empty_report.any():
            logger.info(f"📝 [Generator] 为 {mask_empty_report.sum()} 条记录补充生成报告草稿...")
            for idx in target_df[mask_empty_report].index:
                row = target_df.loc[idx]
                # 调用 Service 内部的 generator 组件生成文本
                if self.service.writer is not None:
                    draft = self.service.writer.generate_text(row, full_df=self.service.df_hl)
                else:
                    logger.warning("HLReportWriter 未初始化，跳过生成文本。")
                    draft = None # 或者根据业务逻辑赋默认值
                target_df.loc[idx, 'generated_report'] = draft

        # 5. 执行自动提交 (Auto-Commit)
        # 直接调用 Service 的提交接口，跳过 UI 确认
        success, commit_msg = self.service.commit_reports_to_ledger(target_df)

        if success:
            logger.info(f"💾 [Generator] 自动提交成功: {commit_msg}")
            return {
                "status": "success",
                "message": commit_msg,
                "count": real_count
            }
        else:
            err_msg = f"❌ [Generator] 自动提交失败: {commit_msg}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)