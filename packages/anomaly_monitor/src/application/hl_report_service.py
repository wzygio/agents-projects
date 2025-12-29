# file_path: packages/anomaly_monitor/src/application/hl_report_service.py
import logging, sys
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional

# 添加项目根目录到 path
try:
    sys.path.append(str(Path(__file__).resolve().parents[4]))
except IndexError: pass

# 导入基础设施层
from infrastructure.repositories.hl_data_repository import HLDataRepository
from infrastructure.repositories.mwdl_data_repository import MWDLDataRepository
from infrastructure.repositories.hl_ledger_repository import HLLedgerRepository

# 导入核心业务逻辑
from core.hl_report_writer import HLReportWriter
from core.concentration_analyzer import ConcentrationAnalyzer
from core.anomaly_detector import AnomalyDetector
from packages.anomaly_monitor.src.config import AnomalyMonitorConfig

# 设置日志
logger = logging.getLogger(__name__)

class HLReportService:
    def __init__(self, config: AnomalyMonitorConfig):
        if config is None:
            from packages.anomaly_monitor.src.config import load_config
            self.config = load_config()
        else:
            self.config = config


        # 链式校验：确保 self.config, daily_report 和 hl_ledger 都存在
        if not (self.config and self.config.daily_report and self.config.daily_report.hl_ledger and self.config.daily_report.record_ledger):
            # 统一抛出异常，提示配置链路中断
            raise ValueError("配置错误：初始化 HLLedgerRepository 失败，请检查 self.config.daily_report.hl_ledger 是否正确配置。")
        
        # 校验通过，直接初始化
        self.ledger_repo = HLLedgerRepository(self.config.daily_report.hl_ledger)
        self.record_repo = HLLedgerRepository(self.config.daily_report.record_ledger)

        self.hl_repo = HLDataRepository(self.config)
        self.mwdl_repo = MWDLDataRepository(self.config)
        
        # Components
        self.detector: Optional[AnomalyDetector] = None
        self.writer: Optional[HLReportWriter] = None

        # Data
        self.df_hl: Optional[pd.DataFrame] = None
        self.df_mwdl: Optional[pd.DataFrame] = None
        self._is_ready = False

    def load_resources(self):
        """加载资源并初始化所有组件"""
        logger.info("⏳ [Service] 开始加载所有资源...")
        try:
            # 1. 加载数据
            self.df_hl = self.hl_repo.get_processed_hl_data()
            df_yield_detail = self.hl_repo.get_yield_detail_data()
            self.df_mwdl = self.mwdl_repo.get_processed_mwdl_data()
            
            # 2. 初始化核心组件
            # Shared Analyzer (复用同一个分析器实例，节省内存)
            shared_analyzer = ConcentrationAnalyzer(df_yield_detail)
            
            # Detector (注入分析器)
            self.detector = AnomalyDetector(df_yield_detail)
            
            # Writer (注入分析器 - 用于兜底)
            self.writer = HLReportWriter(shared_analyzer) # [新增]
            
            self._is_ready = True
            logger.info(f"✅ [Service] 资源加载完毕. HL行数: {len(self.df_hl)}")
            
        except Exception as e:
            logger.error(f"❌ [Service] 初始化失败: {e}", exc_info=True)
            raise RuntimeError(f"Service Init Failed: {e}")

    def run_batch_anomaly_detection(self):
        """
        [核心升级] 批量判定 + 自动报告草拟
        """
        if not self.detector:
            self.load_resources()
        if not self.detector:
            raise RuntimeError("Failed to initialize anomaly detector")
        if self.df_hl is None or self.df_hl.empty:
            logger.warning("⚠️ HL数据未加载或为空，无法执行批量检测")
            return

        logger.info("🕵️‍♂️ [Service] 开始批量执行判定与报告生成...")
        
        # 结果容器
        is_real_list = []
        type_list = []
        reasons_list = []
        report_draft_list = []

        count_real = 0
        count_station = 0
        count_generated = 0

        for idx, row in self.df_hl.iterrows():
            prod = row.get('prod_code')
            defect = row.get('defect_desc')
            current_station = str(row.get('oper_group')).strip()
            
            # 1. 准备历史数据
            df_hist_subset = pd.DataFrame()
            if self.df_mwdl is not None:
                # 简单筛选，性能优化点
                df_hist_subset = self.df_mwdl[
                    (self.df_mwdl['prod_code'] == prod) & 
                    (self.df_mwdl['defect_desc'] == defect)
                ]
            
            # 2. 执行判定 (Detector)
            decision = self.detector.check_is_real_anomaly(row, df_hist_subset)
            
            # 提取结果
            is_real = decision['is_real']
            a_type = decision.get('anomaly_type', '')
            reasons = "; ".join(decision.get('reasons', []))
            
            # 存入列表
            is_real_list.append(is_real)
            type_list.append(a_type)
            reasons_list.append(reasons)
            
            # 统计
            if a_type == '真实异常': count_real += 1
            if a_type == '当站超规': count_station += 1
            
            # 3. 自动草拟报告
            if a_type == '真实异常':
                pre_calc_conc = decision.get('conc_text', None)
                
                # 直接调用！传入 full_df=self.df_hl，让 Writer 自己去查
                draft = self.writer.generate_text( # type: ignore
                    row, 
                    pre_calc_conc_text=pre_calc_conc,
                    full_df=self.df_hl  # 👈 关键：传入全量数据
                )
                
                report_draft_list.append(draft)
                count_generated += 1
            else:
                report_draft_list.append("")

        # 4. 批量回写 DataFrame
        self.df_hl['is_real_anomaly'] = is_real_list
        self.df_hl['anomaly_type'] = type_list
        self.df_hl['anomaly_reasons'] = reasons_list
        self.df_hl['generated_report'] = report_draft_list # [新增] 这一列将直接展示在 UI 上供编辑
        
        logger.info(f"✅ 判定完成。真实异常: {count_real}, 当站超规: {count_station}。已生成报告草稿: {count_generated} 份。")

    def get_history_by_prod_defect(self, prod: str, defect: str) -> pd.DataFrame:
        """
        【UI联动接口】根据产品和不良，查询历史批次记录 (含复杂排序)
        """
        if self.df_mwdl is None or self.df_mwdl.empty:
            return pd.DataFrame()
            
        # 1. 基础过滤
        mask = (self.df_mwdl['prod_code'] == prod) & \
               (self.df_mwdl['defect_desc'] == defect)
        df_filtered = self.df_mwdl[mask].copy()
        
        if df_filtered.empty:
            return df_filtered

        # 2. 核心排序逻辑
        
        # A. 站点权重 (CT置顶)
        if 'oper_group' in df_filtered.columns:
            df_filtered['_station_rank'] = df_filtered['oper_group'].astype(str).apply(
                lambda x: 0 if x.upper().strip() == 'CT' else 1
            )
        else:
            df_filtered['_station_rank'] = 1

        # B. 时间类型权重 (日 > 月 > 周 > 批次)
        # 假设 date_value 列存在
        def get_date_type_rank(val):
            s = str(val).strip()
            # 日: 8位纯数字 (20251209)
            if s.isdigit() and len(s) == 8: return 0
            # 月: 含 'M' (2025M12)
            if 'M' in s: return 1
            # 周: 含 'W' (2025W50)
            if 'W' in s: return 2
            # 批次: 其他所有情况
            return 3

        if 'date_value' in df_filtered.columns:
            df_filtered['_date_type_rank'] = df_filtered['date_value'].apply(get_date_type_rank)
        else:
            df_filtered['_date_type_rank'] = 99

        # 3. 执行排序
        # 优先级: 
        # 1. 站点权重 (Asc: 0->1)
        # 2. 站点名称 (Asc: A->Z)
        # 3. 时间类型 (Asc: 0->1->2->3)
        # 4. 时间值 (Desc: 最新的日期/批次排前面)
        sort_cols = ['_station_rank', 'oper_group', '_date_type_rank', 'date_value']
        asc_orders = [True, True, True, False]
        
        # 容错: 确保列存在
        valid_cols = []
        valid_asc = []
        for col, asc in zip(sort_cols, asc_orders):
            if col in df_filtered.columns:
                valid_cols.append(col)
                valid_asc.append(asc)
                
        df_sorted = df_filtered.sort_values(by=valid_cols, ascending=valid_asc)
        
        # 4. 清理辅助列
        return df_sorted.drop(columns=['_station_rank', '_date_type_rank'])


    def commit_reports_to_ledger(self, selected_df: pd.DataFrame) -> tuple[bool, str]:
        """
        [交互确认] 将数据双写到两个 Excel 文件 (带数据清洗)
        """
        if selected_df.empty:
            return False, "❌ 未选择任何需要录入的异常行"

        # 1. 预检查
        status1, msg1 = self.ledger_repo.check_file_status()
        if not status1: return False, f"[HL台账] {msg1}"
        
        status2, msg2 = self.record_repo.check_file_status()
        if not status2: return False, f"[汇总表] {msg2}"

        logger.info(f"💾 [Service] 准备双写 {len(selected_df)} 条数据...")

        # =========================================================
        # 🛠️ [核心修改] 数据清洗与预处理 (Data Cleaning)
        # =========================================================
        # 我们不直接 to_dict，而是先创建一个清洗后的副本
        df_clean = selected_df.copy()

        # 1. 清洗日期格式 (B列)
        # 目标格式: 2025/12/03 10:00 (YYYY/MM/DD HH:mm)
        if 'interface_time' in df_clean.columns:
            def clean_date(val):
                try:
                    # 尝试转为 datetime 对象
                    dt = pd.to_datetime(val)
                    # 格式化字符串
                    return dt.strftime('%Y/%m/%d %H:%M')
                except:
                    # 如果转换失败，保留原样或截取前16位
                    return str(val)[:16]
            
            df_clean['interface_time'] = df_clean['interface_time'].apply(clean_date)

        # 2. 强制数值类型 (解决 H 列百分比显示问题)
        # 确保 ratio 相关列是 float 类型，而不是 string
        # 如果是 float，Excel 的样式复制功能会自动把它显示为 %
        ratio_cols = ['ratio', 'month_ratio', 'week_ratio', 'batch_ratio']
        for col in ratio_cols:
            if col in df_clean.columns:
                # coerce 将无法转换的变为 NaN，fillna(0) 填补空值
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

        # 3. 转换数据
        records = df_clean.to_dict('records')
        # =========================================================

        # 3. 执行写入
        # 写入文件 A
        ok1, res1 = self.ledger_repo.append_records(records)
        if not ok1: 
            return False, f"写入HL台账失败: {res1}"
            
        # 写入文件 B
        ok2, res2 = self.record_repo.append_records(records)
        if not ok2:
            return True, f"⚠️ HL台账写入成功，但汇总表写入失败: {res2}"

        # 4. 全部成功
        final_msg = f"✅ 双写成功！\n1. HL台账: {res1}\n2. 汇总表: {res2}"
        return True, final_msg
    

