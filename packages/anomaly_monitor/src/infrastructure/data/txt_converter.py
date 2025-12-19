# 文件路径：src\common\utils\spotfire_txt_csv.py
import pandas as pd
import os, sys
from pathlib import Path

try:
    sys.path.append(str(Path(__file__).resolve().parents[3]))
except IndexError:
    pass 



# 定义需要转换的文件名列表
# 这里的名字必须和你最初从 Spotfire 导出的 txt 文件名一致
TXT_FILES = [
    "hl_data.txt",
    "mwdl_data_sql_hl.txt", 
    "spot_dwt_yield.txt"
]

# 我们重点关注且在 xlsx 中丢失的字段
MISSING_TARGETS = ['HL次数', '行', '列', 'ROW_ID', 'COL_ID']
# ===========================================

def convert_txt_to_csv(data_input_dir: Path):
    """
    将TXT文件转换为CSV格式
    """
    print(f"📂 工作目录: {data_input_dir}\n")
    
    for filename in TXT_FILES:
        txt_path = data_input_dir / filename
        csv_path = data_input_dir / f"{filename.replace('.txt', '_raw_converted.csv')}"
        
        print("=" * 80)
        print(f"🔄 正在处理原始文件: {filename}")
        
        if not txt_path.exists():
            print(f"❌ 错误: 文件未找到 -> {txt_path}")
            continue
            
        df = None
        # 尝试多种编码读取 (Spotfire 导出常见 utf-16 或 utf-8)
        encodings = ['utf-8', 'gbk', 'utf-16']
        for enc in encodings:
            try:
                # 默认 Spotfire 导出是 Tab 分隔 (\t)
                df = pd.read_csv(txt_path, sep='\t', encoding=enc, dtype=str)
                print(f"   ✅ 成功以 [{enc}] 编码读取")
                break
            except Exception:
                continue
        
        if df is None:
            print(f"❌ 读取失败: 无法识别文件编码或格式")
            continue

        # 清洗列名 (去空格，方便对比)
        df.columns = df.columns.str.strip()
        
        # 保存为 CSV (UTF-8 SIG, 也就是带 BOM 的 UTF-8，Excel 打开不乱码)
        try:
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"   💾 已转换为 CSV: {csv_path.name}")
        except Exception as e:
            print(f"   ❌ 保存 CSV 失败: {e}")
            
        print("\n")

def analyze_csv_fields(data_input_dir: Path):
    """
    分析CSV文件中的字段，并将结果输出到txt文件
    """
    output_file = (data_input_dir / "field_analysis_report.txt").resolve()
    
    # 设置pandas显示选项
    pd.set_option('display.max_columns', None)  # 显示所有列
    pd.set_option('display.max_rows', 1)        # 只显示一行样本
    pd.set_option('display.width', 1000)        # 防止换行

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"📂 工作目录: {data_input_dir}\n\n")
        
        for filename in TXT_FILES:
            csv_path = data_input_dir / f"{filename.replace('.txt', '_raw_converted.csv')}"
            
            f.write("=" * 80 + "\n")
            f.write(f"📊 分析文件: {filename}\n")
            
            if not csv_path.exists():
                f.write(f"❌ 错误: CSV文件未找到 -> {csv_path}\n")
                continue
            
            try:
                df = pd.read_csv(csv_path, dtype=str)
                
                # 数据规模
                f.write(f"   📏 数据规模: {df.shape[0]} 行, {df.shape[1]} 列\n")
                f.write("-" * 80 + "\n")
                
                # 核心任务：检查丢失字段是否存在
                f.write(f"   📋 字段总数: {len(df.columns)}\n")
                
                found_missing = []
                for target in MISSING_TARGETS:
                    # 模糊匹配，忽略大小写
                    matches = [col for col in df.columns if target.lower() in col.lower()]
                    if matches:
                        found_missing.extend(matches)
                
                if found_missing:
                    f.write(f"   🎉 惊喜发现！在原始 txt 中找到了这些 xlsx 缺失的字段:\n")
                    f.write(f"      {found_missing}\n")
                else:
                    f.write(f"   ⚠️ 未发现目标缺失字段 (可能使用了不同的列名)\n")

                f.write("-" * 80 + "\n")
                f.write("📋 【字段列表 (Columns)】:\n")
                f.write(str(df.columns.tolist()) + "\n")
                f.write("-" * 80 + "\n")
                
                # 数据样本
                f.write("👀 【数据样本 (Sample Data)】:\n")
                if not df.empty:
                    sample = df.iloc[0]
                    for col_name, val in sample.items():
                        f.write(f"   {col_name:<25} : {val}\n")
                else:
                    f.write("   (空表)\n")
                
            except Exception as e:
                f.write(f"❌ 分析失败: {e}\n")
            
            f.write("\n")
    
    print(f"✅ 分析报告已生成: {output_file}")

