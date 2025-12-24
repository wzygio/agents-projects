#%%
import pandas as pd
import os, sys
from pathlib import Path
import time

try:
    sys.path.append(str(Path(__file__).resolve().parents[4]))
except IndexError:
    pass 
from src.config import config


# ================= 配置区域 =================
# 你的数据目录
HL_RESOURCES_DIR = Path(str(config.get("path.hl_resources_dir")))
DATA_RAW_DIR = Path(str(config.get("path.data_raw_dir")))

# 定义源文件 (xlsx) 和目标文件 (parquet)
# 键名方便后续引用，值为文件名
DATASETS = {
    "hl_data": "hl_data.csv",
    "hl_csv_data": "hl_csv_data.csv",
    "mwdl_data": "mwdl_data.csv",
    "yield_data": "ct_yield_data.csv",
    "batch_yield_data": "batch_yield_data.csv",
    "imp_ct_dft_group": "imp_ct_dft_group.csv",
    "spot_dwr_mes_productspec_v": "spot_dwr_mes_productspec_v.csv",
}
# ===========================================

def get_or_create_parquet(file_key, file_name):
    """
    智能加载策略：
    1. 检查是否存在同名的 .parquet 文件
    2. 如果存在，直接秒级读取
    3. 如果不存在，读取 .csv (慢)，保存为 .parquet，下次就快了
    """
    csv_path = (HL_RESOURCES_DIR / file_name).resolve()
    parquet_path = (DATA_RAW_DIR / (file_name.replace(".csv", ".parquet"))).resolve()
    
    if not csv_path.exists():
        print(f"❌ 错误：源文件不存在 -> {csv_path}")
        return None

    # 策略：优先读 Parquet
    if parquet_path.exists():
        try:
            print(f"⚡ [Hit Cache] 发现 Parquet 文件，正在快速加载: {parquet_path.name}")
            start_time = time.time()
            df = pd.read_parquet(parquet_path)
            print(f"   ✅ 加载耗时: {time.time() - start_time:.2f} 秒")
            return df
        except Exception as e:
            print(f"⚠️  Parquet 文件可能损坏: {e}")
            print("   🔄 将重新从 CSV 文件生成...")
            # 删除损坏的 parquet 文件
            try:
                parquet_path.unlink()
            except Exception as delete_error:
                print(f"   ⚠️  无法删除损坏的 Parquet 文件: {delete_error}")
    
    # 否则读取 CSV 并转换
    print(f"🐢 [Miss Cache] 未找到或 Parquet 文件损坏，正在读取 CSV (可能较慢): {csv_path.name} ...")
    start_time = time.time()
    try:
        # 尝试多种编码读取CSV
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
        df = None
        for encoding in encodings:
            try:
                df = pd.read_csv(csv_path, encoding=encoding)
                print(f"   📝 成功使用 {encoding} 编码读取文件")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("无法使用任何常见编码读取文件")
            
        # 强制将所有列转换为字符串，防止不同类型导致 Parquet 保存失败
        df = df.astype(str)
        
        print(f"   💾 正在转换为 Parquet 格式以加速后续读取...")
        # 确保目录存在
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)
        
        print(f"   ✅ 转换并加载完成，耗时: {time.time() - start_time:.2f} 秒")
        return df
    except Exception as e:
        print(f"❌ 读取或转换失败: {e}")
        return None



def inspect_dataset_structure():
    # 创建输出文件
    output_file = ( DATA_RAW_DIR / "dataset_structure_report.txt").resolve()
    
    pd.set_option('display.max_columns', None)  # 显示所有列
    pd.set_option('display.max_rows', 1)        # 只显示一行样本
    pd.set_option('display.width', 1000)        # 防止换行

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"📂 数据目录: {HL_RESOURCES_DIR}\n\n")
        
        for key, filename in DATASETS.items():
            f.write("=" * 80 + "\n")
            f.write(f"📊 分析数据集: 【{key}】\n")
            
            df = get_or_create_parquet(key, filename)
            
            if df is not None:
                f.write(f"   📏 数据规模: {df.shape[0]} 行, {df.shape[1]} 列\n")
                f.write("-" * 80 + "\n")
                
                # 1. 写入所有列名
                f.write("📋 【字段列表 (Columns)】:\n")
                f.write(str(df.columns.tolist()) + "\n")
                f.write("-" * 80 + "\n")
                
                # 2. 写入第一条非空数据
                f.write("👀 【数据样本 (Sample Data)】:\n")
                if not df.empty:
                    sample = df.iloc[0]
                    for col_name, val in sample.items():
                        f.write(f"   {col_name:<25} : {val}\n")
                else:
                    f.write("   (空表)\n")
            f.write("\n")
    
    print(f"✅ 报告已生成: {output_file}")


if __name__ == "__main__":
    inspect_dataset_structure()
# %%
