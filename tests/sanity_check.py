# sanity_check.py
import sys
import os
from pathlib import Path

# 1. 打印环境信息
print(f"🐍 Python Executable: {sys.executable}")
print(f"📂 Current Working Dir: {os.getcwd()}")

# 2. 尝试导入并加载 Excel 引擎配置
try:
    print("\n[1/4] Testing Excel Engine Config...")
    from packages.excel_engine.src.config import load_config as load_excel
    excel_cfg = load_excel()
    print(f"✅ Excel Config Loaded! Output Dir: {excel_cfg.path.output_dir}")
except Exception as e:
    print(f"❌ Excel Config Failed: {e}")
    import traceback
    traceback.print_exc()

# 3. 尝试导入并加载 PPT 引擎配置
try:
    print("\n[2/4] Testing PPT Engine Config...")
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
    print("\n[3/4] Testing Anomaly Monitor Config...")
    from packages.anomaly_monitor.src.config import load_config as load_monitor
    monitor_cfg = load_monitor()
    print(f"✅ Anomaly Config Loaded! Data Cache Path: {monitor_cfg.path.data_cache_path}")
except Exception as e:
    print(f"❌ Anomaly Config Failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n[4/4] Testing Web Automation...")
    from packages.web_automation.src.config import load_config as load_web
    web_cfg = load_web()
    print(f"✅ Web Automation Config Loaded! Portal URL: {web_cfg.daily_report.portal_url}")
except Exception as e:
    print(f"❌ Web Automation Config Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n✨ Sanity Check Finished.")