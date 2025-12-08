import pandas as pd
import logging
from pathlib import Path
from src.config import ConfigLoader

logger = logging.getLogger(__name__)

class HLDataLoader:
    """
    【基础设施层】数据加载器 (Infrastructure Layer)
    职责：
    1. 负责底层文件 I/O (CSV 读取)。
    2. 处理编码 (GBK/UTF-8) 和类型安全。
    3. 实现 Parquet 自动缓存机制。
    注意：此类不包含任何业务逻辑 (如 Join, Calculate)。
    """
    def __init__(self):
        self.config = ConfigLoader()
        # 使用 get 配合默认值，防止配置缺失导致崩溃
        self.input_dir = Path(str(self.config.get("path.hl_resources_dir", "./data/input")))
        self.cache_dir = Path(str(self.config.get("path.cache_path", "./data/cache")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_raw_dataframe(self, file_key: str) -> pd.DataFrame:
        """
        通用读取方法：根据 file_key 读取 CSV (自动缓存为 Parquet)
        :param file_key: config 中 data.files 下的键名 (如 'hl_raw', 'batch_yield')
        """
        # 1. 获取文件名
        filename = self.config.get(f"data.files.{file_key}")
        if not filename:
            # 默认值兜底机制
            defaults = {
                'hl_raw': 'hl_data.csv',
                'batch_yield': 'batch_yield_data.csv',
                'hl_history': 'hl_csv_data.csv',
                'ct_yield': 'ct_yield_data.csv'
            }
            filename = defaults.get(file_key, "")
            if not filename:
                logger.warning(f"⚠️ 未找到文件配置: {file_key}")
                return pd.DataFrame()

        csv_path = self.input_dir / filename # type: ignore
        parquet_path = self.cache_dir / (Path(str(filename)).stem + ".parquet")

        # 2. 尝试读取缓存 (Parquet)
        if parquet_path.exists():
            # 只有当源文件不存在(无法更新) 或 缓存比源文件新时，才读缓存
            if not csv_path.exists() or (parquet_path.stat().st_mtime > csv_path.stat().st_mtime):
                try:
                    logger.info(f"⚡ [Cache Hit] 快速加载: {parquet_path.name}")
                    return pd.read_parquet(parquet_path)
                except Exception as e:
                    logger.warning(f"⚠️ 缓存损坏，回退到源文件: {e}")

        # 3. 读取源文件 (CSV)
        if not csv_path.exists():
            # 容错: 尝试找 .txt
            csv_path = csv_path.with_suffix('.txt')
            if not csv_path.exists():
                logger.error(f"❌ 源文件不存在: {filename}")
                return pd.DataFrame()

        logger.info(f"🐢 [Cache Miss] 读取源文件: {csv_path.name} ...")
        df = pd.DataFrame()
        
        # 暴力尝试编码和分隔符
        for enc in ['utf-8', 'gbk', 'utf-16']:
            for sep in [',', '\t']:
                try:
                    # 关键：dtype=str 防止 '001' 被转成 1，保持原始精度
                    temp = pd.read_csv(csv_path, sep=sep, encoding=enc, dtype=str)
                    if len(temp.columns) > 1:
                        df = temp
                        break
                except: continue
            if not df.empty: break
        
        if df.empty:
            logger.error(f"❌ 读取失败 (格式无法识别): {filename}")
            return pd.DataFrame()

        # 4. 标准化与写缓存
        # 统一列名：小写 + 去空格
        df.columns = df.columns.str.strip().str.lower()
        # 统一数据：去空格
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        try:
            df.to_parquet(parquet_path, index=False)
            logger.info(f"💾 缓存已生成: {parquet_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ 缓存写入失败: {e}")
        
        return df