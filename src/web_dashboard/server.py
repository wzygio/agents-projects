import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import datetime
import os
import sys
import subprocess
import time
import logging
import signal
import atexit
from pathlib import Path

# --- 1. 配置日志 ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger("Orchestrator")

app = FastAPI(title="Duty Automation Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. 路径配置 ---
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent # 回溯到 agents_projects 根目录
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# =============================================================================
# 核心组件：服务进程管理器 (Service Process Manager)
# 职责：像 Docker Compose 一样，确保 PPT 和 Excel 的 UI 服务一直活着
# =============================================================================
class ServiceManager:
    def __init__(self):
        self.services = {} # 存储子进程对象
        self.is_shutting_down = False

    def _kill_existing_process_on_port(self, port):
        """[工具] 强力查杀占用端口的旧进程 (Windows/Linux)"""
        try:
            if os.name == 'nt': # Windows
                # 查找占用端口的 PID
                cmd = f'netstat -aon | findstr :{port}'
                result = subprocess.check_output(cmd, shell=True).decode()
                if "LISTENING" in result:
                    lines = result.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        pid = parts[-1]
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        logger.info(f"已清理占用端口 {port} 的旧进程 PID: {pid}")
            else: # Linux/Mac
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
        except Exception:
            pass # 端口未被占用，忽略

    def start_service(self, name: str, script_path: str, port: int):
        """启动一个 Streamlit 服务"""
        self._kill_existing_process_on_port(port)
        
        # 构造启动命令
        # 注意：这里我们使用 sys.executable 确保使用当前的虚拟环境 Python
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            script_path,
            "--server.port", str(port),
            "--server.headless", "true", # 生产模式不自动弹窗
            "--browser.gatherUsageStats", "false"
        ]
        
        # 设置 PYTHONPATH，确保子进程能找到 packages
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        logger.info(f"正在启动服务 [{name}] on Port {port}...")
        
        # 异步非阻塞启动
        process = subprocess.Popen(
            cmd, 
            cwd=str(PROJECT_ROOT), # 关键：工作目录设为项目根目录
            env=env,
            stdout=subprocess.PIPE, # 可以在这里捕获日志做重定向
            stderr=subprocess.PIPE
        )
        self.services[name] = process
        logger.info(f"✅ 服务 [{name}] 启动成功 (PID: {process.pid})")

    def stop_all(self):
        """优雅关闭所有服务"""
        self.is_shutting_down = True
        logger.info("正在关闭所有子服务...")
        for name, proc in self.services.items():
            if proc.poll() is None: # 如果还在运行
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info(f"服务 [{name}] 已停止")

# 初始化管理器单例
manager = ServiceManager()

# =============================================================================
# FastAPI 生命周期钩子
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """服务器启动时，自动拉起 PPT 和 Excel 的 UI"""
    logger.info(">>> 主编排服务启动，正在唤醒子系统...")
    
    # 1. 启动 PPT 引擎 UI (Port 8501)
    # 注意：路径要指向您最新的 packages 结构
    ppt_app_path = "packages/ppt_engine/src/interface/app.py"
    manager.start_service("PPT_Engine_UI", ppt_app_path, 8501)
    
    # 2. 启动 Excel 引擎 UI (Port 8502)
    # 假设您也有对应的 app.py
    # excel_app_path = "packages/excel_engine/src/interface/app.py" 
    # manager.start_service("Excel_Engine_UI", excel_app_path, 8502)

@app.on_event("shutdown")
async def shutdown_event():
    """服务器关闭时，清理子进程"""
    manager.stop_all()

# 注册退出清理 (防止 Ctrl+C 导致的僵尸进程)
atexit.register(manager.stop_all)


# =============================================================================
# 业务逻辑：工作流配置
# =============================================================================

STEPS_CONFIG = {
    "daily_report": [
        # --- 阶段 1: 自动化数据准备 ---
        {"id": 1, "name": "数据采集与清洗", "detail": "Playwright 正在后台下载数据...", "type": "auto"},
        {"id": 2, "name": "基础数据校验", "detail": "正在检查数据完整性...", "type": "auto"},
        
        # --- 阶段 2: 人工介入 (Excel) ---
        # 这里的 URL 指向的是已经启动好的常驻服务
        {"id": 3, "name": "Excel 异常判定", "detail": "等待人工确认...", 
         "type": "human", 
         "action": {"label": "打开 Excel 控制台", "url": "http://localhost:8502"}},
        
        # --- 阶段 3: 人工介入 (PPT) ---
        {"id": 4, "name": "PPT 画布生成", "detail": "等待人工调整...", 
         "type": "human", 
         "action": {"label": "打开 PPT 控制台", "url": "http://localhost:8501"}},
         
        # --- 阶段 4: 最终交付 ---
        {"id": 5, "name": "归档与分发", "detail": "正在发送邮件...", "type": "auto"}
    ]
}

# =============================================================================
# 接口定义
# =============================================================================

async def event_generator(task_type: str):
    """
    流式任务执行器
    如果是 'auto' 类型，自动执行（调用后台函数）。
    如果是 'human' 类型，生成一个链接卡片，并暂停流程（或者等待回调）。
    """
    steps = STEPS_CONFIG.get(task_type, [])
    
    for step in steps:
        # 1. 发送步骤开始信号
        yield json.dumps({
            "status": "running", 
            "step_id": step["id"], 
            "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 开始步骤: {step['name']}"
        }) + "\n"
        
        # 模拟处理延迟
        await asyncio.sleep(1)

        # 2. 分支处理
        if step.get("type") == "human":
            # --- 人工步骤 ---
            # 我们向前端发送一个特殊状态，告诉前端“显示按钮”
            yield json.dumps({
                "status": "waiting_input", # 特殊状态：等待输入
                "step_id": step["id"],
                "log": f"请点击下方按钮进入 [{step['name']}] 进行操作。",
                "result": {
                    "type": "link", 
                    "label": step['action']['label'], 
                    "url": step['action']['url']
                }
            }) + "\n"
            
            # 在真实场景中，这里应该挂起（await future），直到用户在 Streamlit 点了“完成”并通过 Webhook 通知 Server
            # 这里为了演示，我们在 3 秒后自动视为完成
            await asyncio.sleep(3) 
            
        else:
            # --- 自动步骤 ---
            # 这里应该调用 packages.web_automation.download_service 等真实代码
            await asyncio.sleep(1)

        # 3. 发送步骤完成信号
        yield json.dumps({
            "status": "completed", 
            "step_id": step["id"],
            "log": f"步骤 [{step['name']}] 执行完毕。"
        }) + "\n"

    yield json.dumps({"status": "done", "log": "Workflow Finished."}) + "\n"

@app.get("/start/{task_type}")
async def start_task(task_type: str):
    return StreamingResponse(event_generator(task_type), media_type="application/x-ndjson")

@app.get("/")
async def main():
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return HTMLResponse("<h1>Dashboard is running. Please place index.html in static folder.</h1>")
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    # 启动主编排服务 (Port 8507)
    # 注意：这里不需要 reload=True，否则 Manager 可能会重复启动子进程
    uvicorn.run("server:app", host="0.0.0.0", port=8507)