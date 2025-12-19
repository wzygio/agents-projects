# packages/anomaly_monitor/src/interface/cli.py
import sys
from pathlib import Path
# 临时添加根目录到 path 以便测试
sys.path.append(str(Path(__file__).resolve().parents[4]))

import streamlit.web.cli as stcli
import sys

def run_standalone():
    """用于开发调试的独立启动入口"""
    sys.argv = ["streamlit", "run", "packages/anomaly_monitor/src/interface/dashboard.py"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    run_standalone()