import logging, sys
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional

# 添加项目根目录到 path
try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError: pass

# 导入基础设施层
from src.anomaly_monitor.infrastructure.repositories.hl_data_repository import HLDataRepository
from src.anomaly_monitor.infrastructure.repositories.mwdl_data_repository import MWDLDataRepository

# 导入核心业务逻辑
from src.anomaly_monitor.core.hl_report_generator import HLReportGenerator
from src.anomaly_monitor.core.anomaly_detector import AnomalyDetector
from src.anomaly_monitor.core.ai_anomaly_detector import AIAnomalyDetector

# 设置日志
logger = logging.getLogger(__name__)

class HLReportService:
    def __init__(self):
        # Repositories
        self.hl_repo = HLDataRepository()
        self.mwdl_repo = MWDLDataRepository()
        
        # Core Components
        self.generator: Optional[HLReportGenerator] = None
        self.detector: Optional[AnomalyDetector] = None # [新增]
        # self.detector: Optional[AIAnomalyDetector] = None # 类型更新

        # Data Cache
        self.df_hl: Optional[pd.DataFrame] = None
        self.df_mwdl: Optional[pd.DataFrame] = None
        self._is_ready = False

    def load_resources(self):
        """
        加载所有必要数据并初始化核心组件
        """
        logger.info("⏳ [Service] 开始加载所有资源...")
        
        try:
            # 1. 加载数据 (Infrastructure Layer)
            self.df_hl = self.hl_repo.get_processed_hl_data()
            df_yield_detail = self.hl_repo.get_yield_detail_data() # 获取明细数据用于集中性分析
            self.df_mwdl = self.mwdl_repo.get_processed_mwdl_data() # 获取历史数据用于对比
            
            # 2. 初始化核心组件 (Core Layer)
            # Generator 需要 Analyzer，Detector 也需要 Analyzer (或内部集成)
            # 这里我们在 Detector 内部实例化了 Analyzer，传入 yield_detail
            self.detector = AnomalyDetector(df_yield_detail)
            # self.detector = AIAnomalyDetector(df_yield_detail)

            # 优化：其实 Detector 跑完后，Generator 可以直接用 Detector 的结果
            from src.anomaly_monitor.core.concentration_analyzer import ConcentrationAnalyzer
            analyzer = ConcentrationAnalyzer(df_yield_detail)
            self.generator = HLReportGenerator(analyzer)
            
            self._is_ready = True
            logger.info(f"✅ [Service] 资源加载完毕. HL行数: {len(self.df_hl)}")
            
        except Exception as e:
            logger.error(f"❌ [Service] 初始化失败: {e}", exc_info=True)
            raise RuntimeError(f"Service Init Failed: {e}")

    def run_batch_anomaly_detection(self):
        """
        [核心新功能] 对 df_hl 进行批量真实性判定
        结果会直接回写到 self.df_hl 的新列中 ('is_real_anomaly', 'anomaly_reasons')
        """
        if not self._is_ready or self.df_hl is None:
            self.load_resources()
            
        if self.df_hl is None or self.df_hl.empty: 
            return

        logger.info("🕵️‍♂️ [Service] 开始批量执行异常真实性判定 (CT基准)...")
        
        is_real_list = []
        type_list = []    # [新增]
        reasons_list = []
        
        for idx, row in self.df_hl.iterrows():
            prod = row.get('prod_code')
            defect = row.get('defect_desc')
            
            df_hist_subset = pd.DataFrame()
            if self.df_mwdl is not None:
                # 这里还是传该产品该不良的所有历史，由 Detector 内部去筛选 CT
                df_hist_subset = self.df_mwdl[
                    (self.df_mwdl['prod_code'] == prod) & 
                    (self.df_mwdl['defect_desc'] == defect)
                ]
            
            if self.detector is None:
                logger.error("❌ [Service] Detector 未初始化")
                raise RuntimeError("Detector 未初始化")
            decision = self.detector.check_is_real_anomaly(row, df_hist_subset)
            
            is_real_list.append(decision['is_real'])
            type_list.append(decision['anomaly_type']) # [新增]
            reasons_list.append("; ".join(decision['reasons']))

        # 回写结果
        self.df_hl['is_real_anomaly'] = is_real_list
        self.df_hl['anomaly_type'] = type_list # [新增]
        self.df_hl['anomaly_reasons'] = reasons_list
        
        # 统计日志
        real_ct = type_list.count("真实异常")
        real_station = type_list.count("当站超规")
        logger.info(f"✅ 判定完成. 真实异常(CT): {real_ct}, 当站超规: {real_station}")

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


    def generate_reports(self, 
                         only_worsening: bool = True, 
                         min_batch_gap: float = 0.0) -> List[Dict]:
        """
        执行日报生成任务
        
        :param only_worsening: 是否只看恶化的批次 (batch_gap > 0)
        :param min_batch_gap: 恶化阈值，默认 > 0 即生成
        :return: 包含生成的报告文本和元数据的列表
        """
        if not self._is_ready or self.df_hl is None:
            self.load_resources()

        if self.df_hl is None or self.df_hl.empty:
            logger.warning("⚠️ 没有 HL 数据，无法生成报告。")
            return []


        reports = []
        
        # 1. 筛选数据
        # 根据业务规则过滤: 例如只看 Gap > 0 的项
        target_df = self.df_hl.copy()
        
        if only_worsening:
            # 确保 batch_gap 是数字
            if 'batch_gap' in target_df.columns:
                target_df = target_df[target_df['batch_gap'] > min_batch_gap]
            else:
                logger.warning("⚠️ batch_gap 字段缺失，跳过筛选。")

        # 按批次恶化程度降序排列，优先展示最严重的
        if 'batch_gap' in target_df.columns:
            target_df = target_df.sort_values('batch_gap', ascending=False)

        logger.info(f"📊 开始生成报告，待处理条目: {len(target_df)}")

        # 2. 循环生成
        for index, row in target_df.iterrows():
            try:
                # 调用 Generator 生成文本
                report_text = self.generator.generate_text(row) if self.generator else "生成器未初始化"
                
                # 收集结果
                item = {
                    "id": index,
                    "prod": row.get('prod_code'),
                    "defect": row.get('defect_desc'),
                    "batch": row.get('batch'),
                    "gap": row.get('batch_gap', 0),
                    "text": report_text
                }
                reports.append(item)
                
            except Exception as e:
                logger.error(f"❌ 生成单条报告失败 (Prod: {row.get('prod_code')}): {e}")
                continue

        logger.info(f"✅ 生成完成，共生成 {len(reports)} 份报告。")
        return reports

# --- 调试入口 (Main) ---
if __name__ == "__main__":
    # 配置简单的日志输出以便调试
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    service = HLReportService()
    
    try:
        # 1. 运行生成
        # 这里的 min_batch_gap=0.001 代表只看恶化超过 0.1% 的
        results = service.generate_reports(only_worsening=True, min_batch_gap=0.001)
        
        print("\n" + "="*50)
        print(f"🎉 成功生成 {len(results)} 份异常通报")
        print("="*50 + "\n")
        
        # 2. 打印前 2 份看看效果
        for report in results[:2]:
            print(f"📄 报告预览 [{report['prod']} - {report['defect']}]:")
            print("-" * 30)
            print(report['text'])
            print("-" * 30 + "\n")
            
    except Exception as e:
        print(f"❌ 运行出错: {e}")