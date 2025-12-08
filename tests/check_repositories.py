import sys
import os
from pathlib import Path
import pandas as pd

# 将 src 加入 Python 路径，确保能 import 到 anomaly_monitor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# 根据您的结构尝试导入 (Agent 开发完成后这些导入应该能成功)
try:
    from src.anomaly_monitor.infrastructure.repositories.hl_data_repository import HLDataRepository
    # from anomaly_monitor.app.infrastructure.repositories.mwdl_repository import MWDLRepository
    print("✅ 成功导入 Repository 模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("提示: 请检查 __init__.py 是否已正确创建")
    sys.exit(1)

def test_hl_loading():
    print("\n--- 测试 HL 数据读取 ---")
    repo = HLDataRepository()
    try:
        df = repo.load_data() # type: ignore
        if df is not None and not df.empty:
            print(f"✅ HL Data 读取成功: {len(df)} 行")
            # 验证关键列是否存在 (根据您的逻辑图)
            required_cols = ["产品型号", "不良名称"]
            for col in required_cols:
                if col not in df.columns:
                    print(f"⚠️ 警告: 缺失关键列 {col}")
        else:
            print("❌ HL Data 为空")
    except Exception as e:
        print(f"❌ HL Data 读取报错: {e}")

if __name__ == "__main__":
    # 确保 data/input 下有测试文件再运行
    test_hl_loading()
    # 可以在这里添加其他 Repo 的测试