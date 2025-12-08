import pandas as pd
from pathlib import Path
import os
from src.config import config

class FileAdapter:
    """
    负责底层文件 I/O，实现 CSV -> Parquet 的自动缓存机制
    """
    def __init__(self, input_dir: Path = Path(config.data_config['input_path']), cache_dir: Path = Path(config.data_config['cache_path'])):
        self.input_dir = input_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_dataframe(self, file_key: str) -> pd.DataFrame:
        """
        :param file_key: settings.yaml 中 files 下的键名 (如 'hl_raw', 'yield_detail')
        """
        filename = config.data_config['files'].get(file_key)
        if not filename:
            raise ValueError(f"配置中未找到文件键: {file_key}")

        csv_path = self.input_dir / filename
        parquet_name = Path(filename).stem + ".parquet"
        parquet_path = self.cache_dir / parquet_name

        # 1. 检查缓存策略 (如果 Parquet 存在且比 CSV 新，直接读)
        if parquet_path.exists():
            if not csv_path.exists() or (parquet_path.stat().st_mtime > csv_path.stat().st_mtime):
                print(f"⚡ [Cache Hit] 快速加载: {parquet_name}")
                return pd.read_parquet(parquet_path)

        # 2. 缓存未命中，读取原始 CSV
        if not csv_path.exists():
            # 尝试自动修正后缀 (兼容 .txt / .csv)
            alt_path = csv_path.with_suffix('.txt')
            if alt_path.exists():
                csv_path = alt_path
            else:
                print(f"❌ [Error] 源文件未找到: {filename}")
                return pd.DataFrame()

        print(f"🐢 [Cache Miss] 读取源文件并转换: {filename} ...")
        df = self._read_csv_safe(csv_path)

        # 3. 保存为 Parquet (加速下次读取)
        if not df.empty:
            # 转换为 string 防止类型推断错误导致 parquet 保存失败
            df.columns = df.columns.str.strip().str.lower()
            df.to_parquet(parquet_path, index=False)
        
        return df

    def _read_csv_safe(self, path: Path) -> pd.DataFrame:
        """尝试多种编码读取"""
        encodings = ['utf-8', 'gbk', 'utf-16']
        separators = [',', '\t']
        
        for enc in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str)
                    if len(df.columns) > 1:
                        return df
                except:
                    continue
        return pd.DataFrame()