# 文件路径：src\common\utils\datasource_replicator.py
import pandas as pd
import numpy as np
from pathlib import Path
import os, sys

try:
    sys.path.append(str(Path(__file__).resolve().parents[4]))
except IndexError:
    pass 
from packages.anomaly_monitor.src.config import load_config

# ================= 配置区域 =================
# 共享盘路径 (源头)
config = load_config()
HL_RESOURCES_DIR = Path(str(config.paths.hl_resources_dir))

# 关键文件名 (根据你的截图和日志推断)
FILES = {
    "hl_source": "hl_data.csv",           
    "batch_yield": "batch_yield_data.csv", 
    "mwdl_source": "mwdl_data_sql (HL).csv", 
    "spot_source": "spot_dwt_yield (HL).csv"
}
# ===========================================

class SourceLogicReplicator:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        
    def _read_csv(self, filename):
        path = self.data_dir / filename
        # 共享盘文件，通常先试 GBK (中文常见)，再试 UTF-8
        # 容错：如果文件不存在，尝试找 txt
        if not path.exists():
            path_txt = path.with_suffix('.txt')
            if path_txt.exists():
                path = path_txt
            else:
                print(f"❌ 警告：找不到文件 {filename}")
                return None
                
        print(f"🔄 读取源文件: {path.name} ...")
        try:
            df = pd.read_csv(path, encoding='gbk', dtype=str)
        except:
            df = pd.read_csv(path, encoding='utf-8', dtype=str)
            
        # 标准化列名：去空格，转小写
        df.columns = df.columns.str.strip().str.lower()
        return df

    def run_pipeline(self):
        # 1. 加载原始数据
        df_hl = self._read_csv(FILES["hl_source"])
        df_batch_yield = self._read_csv(FILES["batch_yield"])
        
        if df_hl is None: return None

        print("⚙️ 开始执行 Spotfire 逻辑复刻...")
        
        # =================================================
        # 逻辑复刻 A: 类型转换 (Step 2 in Log)
        # =================================================
        num_cols = ['ratio', 'batch_ratio', 'lag_ratio', 'lag2_ratio']
        for col in num_cols:
            if col in df_hl.columns:
                df_hl[col] = pd.to_numeric(df_hl[col], errors='coerce').fillna(0)

        # =================================================
        # 逻辑复刻 B: 计算 batch_gap (Step 3 in Log)
        # 逻辑: (batch_ratio - lag_ratio)
        # =================================================
        if 'batch_gap' not in df_hl.columns: # 如果源文件里没算好
            print("   ➕ 计算列: batch_gap")
            df_hl['batch_gap'] = df_hl['batch_ratio'] - df_hl['lag_ratio']
        
        # =================================================
        # 逻辑复刻 C: 筛选最新行 (Step 4 in Log)
        # 逻辑: DenseRank([date_time] desc) = 1
        # =================================================
        if 'date_time' in df_hl.columns:
            print("   ✂️ 执行筛选: 保留每个产品+不良的最新时间记录")
            df_hl['dt_temp'] = pd.to_datetime(df_hl['date_time'], errors='coerce')
            # 按时间降序排序
            df_hl = df_hl.sort_values('dt_temp', ascending=False)
            # 分组取第一条 (即最新的一条)
            df_hl = df_hl.groupby(['prod_code', 'defect_desc'], as_index=False).first()
            # 删掉临时列
            df_hl = df_hl.drop(columns=['dt_temp'])

        # =================================================
        # 逻辑复刻 D: 表连接 Join (Step 5 in Log)
        # 逻辑: Left Join batch_yield_data ON (prod_code, batch=sub_prod_id)
        # =================================================
        if df_batch_yield is not None:
            print("   🔗 执行连接: Join [batch_yield_data]")
            # 准备连接键 (确保两边都是字符串且无空格)
            # 注意：Spotfire日志里说 batch 对应 sub_prod_id
            df_hl['join_key_1'] = df_hl['prod_code'].str.strip()
            df_hl['join_key_2'] = df_hl['batch'].str.strip()
            
            df_batch_yield['join_key_1'] = df_batch_yield['prod_code'].str.strip()
            # 假设 batch_yield 表里对应批次的列叫 'sub_prod_id' (根据日志)
            # 如果不是，请修改这里的列名
            join_col_right = 'sub_prod_id' 
            if join_col_right in df_batch_yield.columns:
                df_batch_yield['join_key_2'] = df_batch_yield[join_col_right].str.strip()
                
                # 执行 Merge
                # suffixes定义重名列后缀，防止冲突
                df_merged = pd.merge(
                    df_hl, 
                    df_batch_yield[['join_key_1', 'join_key_2', 'lot_input_ratio', 'now_ct_qty', 'interface_time']], # 只取需要的列
                    on=['join_key_1', 'join_key_2'], 
                    how='left',
                    suffixes=('', '_yield')
                )
                
                # 如果 hl 表原本就有 interface_time，优先用 yield 表的覆盖（模拟日志行为）
                # 或者保留两个，看实际需求。这里演示覆盖逻辑：
                if 'interface_time_yield' in df_merged.columns:
                    df_merged['interface_time'] = df_merged['interface_time_yield'].fillna(df_merged['interface_time'])
                
                df_hl = df_merged
            else:
                print(f"   ⚠️ 警告: batch_yield_data 中找不到 {join_col_right} 列，跳过连接。")

        # =================================================
        # 逻辑复刻 E: 动态文本生成 (Step 10 in Log)
        # 逻辑: 'xxx批次较上批次恶化 xx%'
        # =================================================
        print("   📝 生成文本列: 批次恶化描述")
        # 假设 batch 是 "25/10/23蒸镀批"，取日期部分
        # python str[3:8] 对应 substring 4,5 (Python索引从0开始)
        df_hl['batch_date_str'] = df_hl['batch'].astype(str).str[3:8] 

        df_hl['batch_gap'] = pd.to_numeric(df_hl['batch_gap'], errors='coerce').fillna(0)
        df_hl['gap_pct_str'] = (df_hl['batch_gap'] * 100).round(2).astype(str) + '%'
        
        df_hl['批次恶化'] = (
            df_hl['batch_date_str'].astype(str) + "批次较上批次恶化" + df_hl['gap_pct_str'].astype(str)
        )

        # 最终过滤：只看恶化的 (gap > 0)
        df_final = df_hl[df_hl['batch_gap'] > 0].copy()
        
        print(f"✅ 复刻完成！最终有效异常行数: {len(df_final)}")
        return df_final

# --- 执行验证 ---
replicator = SourceLogicReplicator(HL_RESOURCES_DIR)
df_reconstructed = replicator.run_pipeline()

if df_reconstructed is not None:
    # 打印前 3 行的关键列，看看是不是和之前 TXT 里的一样
    cols_to_show = ['prod_code', 'defect_desc', 'batch', 'batch_gap', '批次恶化']
    # 仅显示存在的列
    valid_cols = [c for c in cols_to_show if c in df_reconstructed.columns]
    
    # 设置pandas显示选项，确保完整显示所有列
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    # 打印数据
    print("\n前3行数据预览：")
    print(df_reconstructed[valid_cols].head(3).to_string())
