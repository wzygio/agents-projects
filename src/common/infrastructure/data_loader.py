import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.config import ConfigLoader

# 设置日志记录器
logger = logging.getLogger(__name__)

class DailyReportDataLoader:
    """
    基础设施层数据加载器 (Infrastructure Layer)
    
    职责：
    1. I/O 适配: 处理 CSV 编码/分隔符，实现 Parquet 自动缓存。
    2. 数据清洗: 强制类型转换，处理空值。
    3. 逻辑复刻: 1:1 复刻 Spotfire 的数据预处理逻辑 (Join, Calculate)。
    """

    def __init__(self):
        # 1. 加载配置
        self.config = ConfigLoader()
        
        # 2. 安全获取路径 (修复 Path(None) 崩溃漏洞)
        input_str = self.config.get("data.input_path")
        cache_str = self.config.get("data.cache_path")
        hl_resource_str = self.config.get("path.hl_resources_dir")
        
        if not input_str or not cache_str or not hl_resource_str:
            raise ValueError("❌ 配置文件错误: 未找到 data.input_path 或 data.cache_path")
        
        if not isinstance(input_str, str) or not isinstance(cache_str, str) or not isinstance(hl_resource_str, str):
            raise ValueError("❌ 配置文件错误: input_path 和 cache_path 必须是字符串类型")
        
        self.input_dir = Path(input_str)
        self.cache_dir = Path(cache_str)
        self.hl_resources_dir = Path(hl_resource_str)
        
        # 3. 初始化环境
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. 加载字段映射 (虽然代码中有探测逻辑，但预留配置入口)
        self.cols_map = self.config.get("data.columns", {})

    def _load_and_cache(self, file_key: str) -> pd.DataFrame:
        """
        [核心 I/O] 智能读取 + 缓存机制
        :param file_key: config.yaml 中 files 下的键名
        """
        filename = self.config.get(f"data.files.{file_key}")
        if not filename or not isinstance(filename, str):
            logger.error(f"⚠️ 配置缺失或类型错误: 无法找到文件键 data.files.{file_key}")
            return pd.DataFrame()

        csv_path = self.hl_resources_dir / filename
        parquet_path = self.cache_dir / (Path(filename).stem + ".parquet")

        # --- A. 尝试读取缓存 ---
        if parquet_path.exists():
            # 逻辑：如果源文件不存在(可能网络断了)，或者缓存比源文件新 -> 读缓存
            if not csv_path.exists() or (parquet_path.stat().st_mtime > csv_path.stat().st_mtime):
                logger.info(f"⚡ [Cache Hit] 快速加载: {parquet_path.name}")
                try:
                    return pd.read_parquet(parquet_path)
                except Exception as e:
                    logger.warning(f"⚠️ 缓存损坏，尝试重新读取源文件: {e}")

        # --- B. 读取源文件 ---
        # 容错：如果配置的是 .csv 但实际只有 .txt (常见于 Spotfire 导出)
        if not csv_path.exists():
            alt_path = csv_path.with_suffix('.txt')
            if alt_path.exists():
                csv_path = alt_path
            else:
                logger.error(f"❌ 源文件不存在: {filename}")
                return pd.DataFrame()

        logger.info(f"🐢 [Cache Miss] 读取源文件: {csv_path.name} ...")
        
        df = pd.DataFrame()
        # 暴力尝试常见编码和分隔符
        encodings = ['utf-8', 'gbk', 'utf-16']
        separators = [',', '\t']
        
        for enc in encodings:
            for sep in separators:
                try:
                    # 关键：dtype=str 防止 '001' 变成 1
                    temp_df = pd.read_csv(csv_path, sep=sep, encoding=enc, dtype=str)
                    if len(temp_df.columns) > 1: # 至少要有两列才算读对了吧
                        df = temp_df
                        break
                except Exception:
                    continue
            if not df.empty:
                break
        
        if df.empty:
            logger.error(f"❌ 读取失败 (格式或编码无法识别): {filename}")
            return pd.DataFrame()

        # --- C. 标准化与缓存 ---
        # 统一列名：小写 + 去空格
        df.columns = df.columns.str.strip().str.lower()
        # 统一数据：去空格 (针对字符串列)
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        try:
            df.to_parquet(parquet_path, index=False)
            logger.info(f"💾 缓存已生成: {parquet_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ 缓存生成失败 (需安装 pyarrow/fastparquet): {e}")

        return df

    def get_processed_hl_data(self) -> pd.DataFrame:
        """
        [业务逻辑] 生成异常主数据 (HL Data)
        对应: hl_data.csv + batch_yield_data.csv
        """
        df_hl = self._load_and_cache('hl_raw')
        df_batch = self._load_and_cache('batch_yield')
        
        if df_hl.empty:
            return pd.DataFrame()

        # 1. 数值清洗
        num_cols = ['ratio', 'batch_ratio', 'lag_ratio', 'ng_qty', 'hl次数']
        for col in num_cols:
            if col in df_hl.columns:
                df_hl[col] = pd.to_numeric(df_hl[col], errors='coerce').fillna(0)

        # 2. 计算 Batch Gap (本批次 - 上批次)
        # 逻辑修复：确保列存在
        if 'batch_ratio' in df_hl.columns and 'lag_ratio' in df_hl.columns:
            df_hl['batch_gap'] = df_hl['batch_ratio'] - df_hl['lag_ratio']
        else:
            df_hl['batch_gap'] = 0.0

        # 3. 筛选最新记录 (DenseRank)
        time_col = 'interface_time'
        if time_col in df_hl.columns:
            df_hl[time_col] = pd.to_datetime(df_hl[time_col], errors='coerce')
            # 按 (Product, Defect) 分组，取时间最新的
            df_hl = df_hl.sort_values(time_col, ascending=False)
            df_hl = df_hl.groupby(['prod_code', 'defect_desc'], as_index=False).first()

        # 4. Join Batch Yield (获取 lot_input_ratio 等辅助信息)
        if not df_batch.empty:
            # 探测 Batch 列名 (可能是 batch 或 sub_prod_id)
            right_batch_col = 'batch'
            if 'sub_prod_id' in df_batch.columns:
                right_batch_col = 'sub_prod_id'
            
            # 准备连接键
            df_hl['join_k1'] = df_hl['prod_code'].astype(str)
            df_hl['join_k2'] = df_hl['batch'].astype(str)
            
            df_batch['join_k1'] = df_batch['prod_code'].astype(str)
            df_batch['join_k2'] = df_batch[right_batch_col].astype(str)
            
            # 选择要合并的列
            cols_to_merge = ['join_k1', 'join_k2', 'lot_input_ratio', 'now_ct_qty']
            cols_available = [c for c in cols_to_merge if c in df_batch.columns]
            
            df_hl = pd.merge(
                df_hl,
                df_batch[cols_available],
                on=['join_k1', 'join_k2'],
                how='left'
            )
            # 清理临时键
            df_hl.drop(columns=['join_k1', 'join_k2'], inplace=True)

        # 5. 辅助列: 短日期字符串 (用于报告文本 "10/29")
        if 'batch' in df_hl.columns:
            # 假设 batch: "25/10/29xxx" -> 取 "10/29"
            # 容错：防止 batch 不是字符串
            df_hl['batch_date_str'] = df_hl['batch'].astype(str).apply(
                lambda x: x[3:8] if len(x) >= 8 else x
            )

        return df_hl

    def get_yield_detail_data(self) -> pd.DataFrame:
        """
        [业务逻辑] 生成 Panel 明细数据 (Yield Detail)
        对应: ct_yield_data.csv (即 spot_dwt_yield)
        """
        df = self._load_and_cache('ct_yield')
        
        if df.empty:
            return pd.DataFrame()

        # 1. 过滤不良品 (只分析 NG)
        if 'ng_qty' in df.columns:
            df['ng_qty'] = pd.to_numeric(df['ng_qty'], errors='coerce').fillna(0)
            df = df[df['ng_qty'] > 0].copy()

        # 2. 解析 Panel ID 获取坐标
        # 修复漏洞：强制转字符串，并处理 NaN
        if 'panel_id' in df.columns:
            # 确保是字符串
            df['panel_id'] = df['panel_id'].astype(str).replace('nan', '')
            
            # 过滤短 ID
            valid_mask = df['panel_id'].str.len() > 4
            df = df[valid_mask].copy()
            
            # 解析 (前2位行，后2位列)
            df['行'] = df['panel_id'].str[-4:-2]
            df['列'] = df['panel_id'].str[-2:]
            df['membrane_pos'] = df['行'].astype(str) + '-' + df['列'].astype(str)

            
        return df