import logging, sys
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional

try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 
from src.config import config

# 导入底层设施
from src.anomaly_monitor.infrastructure.repositories.hl_data_repository import HLDataRepository
# 导入核心业务逻辑
from src.anomaly_monitor.core.concentration_analyzer import ConcentrationAnalyzer
from src.anomaly_monitor.core.hl_report_generator import ReportGenerator

# 设置日志
logger = logging.getLogger(__name__)

class HLReportService:
    """
    【服务编排层】OLED 良率日报生成服务
    
    它是外部调用（如 GUI、CLI、API）的统一入口。
    它负责协调 Data Load -> Analyze -> Generate 的全流程。
    """

    def __init__(self):
        # 初始化数据加载器 (此时尚未读取文件)
        self.repo = HLDataRepository()
        
        # 核心组件 (稍后在 load_resources 中初始化)
        self.analyzer: Optional[ConcentrationAnalyzer] = None
        self.generator: Optional[ReportGenerator] = None
        
        # 缓存数据
        self.df_hl: Optional[pd.DataFrame] = None
        self._is_ready = False

    def load_resources(self):
        """
        初始化资源：读取数据并装配核心组件
        注意：这可能需要几秒钟 (取决于 ct_yield_data 的大小)
        """
        logger.info("🚀正在启动日报服务，加载数据资源...")
        
        try:
            # 1. 加载数据 (利用 Infrastructure 层的缓存机制)
            # 加载异常主表
            self.df_hl = self.repo.get_processed_hl_data()
            
            # 加载明细数据 (135MB)
            logger.info("⏳ 正在加载明细数据 (Yield Detail)...")
            df_yield_detail = self.repo.get_yield_detail_data()
            
            # 2. 依赖注入 (Dependency Injection)
            # 将明细数据注入分析器
            self.analyzer = ConcentrationAnalyzer(df_yield_detail)
            
            # 将分析器注入生成器
            self.generator = ReportGenerator(self.analyzer)
            
            self._is_ready = True
            logger.info(f"✅ 服务就绪! HL数据行数: {len(self.df_hl)}, 明细数据行数: {len(df_yield_detail)}")
            
        except Exception as e:
            logger.error(f"❌ 服务启动失败: {e}", exc_info=True)
            raise RuntimeError(f"服务初始化失败: {e}")

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