# sanity_check.py
import sys
import os
from pathlib import Path

# 1. 打印环境信息
print(f"🐍 Python Executable: {sys.executable}")
print(f"📂 Current Working Dir: {os.getcwd()}")

# 2. 尝试导入并加载 Excel 引擎配置
try:
    print("\n[1/3] Testing Excel Engine Config...")
    from packages.excel_engine.src.config import load_config as load_excel
    excel_cfg = load_excel()
    print(f"✅ Excel Config Loaded! Output Dir: {excel_cfg.path.output_dir}")
except Exception as e:
    print(f"❌ Excel Config Failed: {e}")
    import traceback
    traceback.print_exc()

# 3. 尝试导入并加载 PPT 引擎配置
try:
    print("\n[2/3] Testing PPT Engine Config...")
    from packages.ppt_engine.src.config import load_config as load_ppt
    # PPT 引擎现在的 load_config 是个 wrapper，或者我们可以直接测试 PptEngineConfig.from_app_config(None)
    # 这里测试我们刚刚写好的独立运行逻辑
    ppt_cfg = load_ppt() 
    print(f"✅ PPT Config Loaded! Resource Dir: {ppt_cfg.path.resources_dir}")
except Exception as e:
    print(f"❌ PPT Config Failed: {e}")
    import traceback
    traceback.print_exc()

# 4. 尝试导入并加载 异常监控 配置
try:
    print("\n[3/3] Testing Anomaly Monitor Config...")
    from packages.anomaly_monitor.src.config import load_config as load_monitor
    # 注意：Anomaly Monitor 我们之前可能删除了 load_config，
    # 如果您删除了，这里应该用 AnomalyMonitorConfig.from_app_config(None)
    # 为了保险，我们先尝试导入类
    from packages.anomaly_monitor.src.config import AnomalyMonitorConfig
    monitor_cfg = AnomalyMonitorConfig.from_app_config(None)
    print(f"✅ Anomaly Config Loaded! Project Name: {monitor_cfg.common.project_name}")
except Exception as e:
    print(f"❌ Anomaly Config Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n✨ Sanity Check Finished.")