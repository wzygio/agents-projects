# src/web_dashboard/main.py
import uvicorn
import os
import sys
from pathlib import Path

# 确保路径可见
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
sys.path.append(str(PROJECT_ROOT))

def main():
    """
    系统入口函数
    """
    print(f"🚀 Starting Duty Automation System on Port 8510...")
    print(f"📂 Project Root: {PROJECT_ROOT}")
    
    # 启动 Uvicorn 服务器
    # "interfaces.api:app" 指向 interfaces/api.py 中的 app 对象
    uvicorn.run(
        "interfaces.api:app", 
        host="0.0.0.0", 
        port=8510, 
        reload=False, # 生产环境建议关闭 reload
        app_dir=str(BASE_DIR) # 指定 App 所在目录
    )

if __name__ == "__main__":
    main()