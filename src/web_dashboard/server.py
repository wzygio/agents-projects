import asyncio
import uvicorn
import json
import datetime
import os, sys, logging
import subprocess
import atexit
from pathlib import Path
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.config import AppConfig

# --- 引入项目核心组件 ---
# 确保 PYTHONPATH 包含项目根目录，否则这几行导入会报错
sys.path.append(str(Path(__file__).resolve().parents[2])) 

# 1. 引入全局配置加载器 (假设 src/config.py 存在，如果没有则使用空字典兜底)
try:
    from src.config import load_config
except ImportError:
    load_config = lambda: {} # 兜底：如果找不到全局配置加载器，返回空字典，依赖 Adapter 的本地测试配置

# 2. 引入 PPT 适配器
from packages.ppt_engine.src.adapter import PPTEngineAdapter

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
PROJECT_ROOT = BASE_DIR.parent.parent 
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 3. 全局资源池 ---
# 用于执行阻塞式后台任务 (PPT生成、Excel处理)
executor = ThreadPoolExecutor(max_workers=3) 

# =============================================================================
# 核心组件：服务进程管理器 (Service Process Manager)
# =============================================================================
class ServiceManager:
    def __init__(self):
        self.services = {} 
        self.is_shutting_down = False

    def _kill_existing_process_on_port(self, port):
        """[工具] 强力查杀占用端口的旧进程"""
        try:
            if os.name == 'nt': # Windows
                cmd = f'netstat -aon | findstr :{port}'
                result = subprocess.check_output(cmd, shell=True).decode()
                if "LISTENING" in result:
                    for line in result.strip().split('\n'):
                        parts = line.split()
                        if len(parts) > 4:
                            pid = parts[-1]
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                            logger.info(f"已清理占用端口 {port} 的旧进程 PID: {pid}")
            else: # Linux/Mac
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
        except Exception:
            pass 

    def start_service(self, name: str, script_path: str, port: int):
        """启动 Streamlit 子服务"""
        self._kill_existing_process_on_port(port)
        
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            script_path,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ]
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        logger.info(f"正在启动子服务 [{name}] on Port {port}...")
        process = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.services[name] = process
        logger.info(f"✅ 服务 [{name}] 启动成功 (PID: {process.pid})")

    def stop_all(self):
        self.is_shutting_down = True
        for name, proc in self.services.items():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info(f"服务 [{name}] 已停止")

manager = ServiceManager()

# =============================================================================
# FastAPI 生命周期
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """启动时拉起 UI 控制台"""
    logger.info(">>> 主编排服务启动...")
    # 启动 PPT 控制台 (人工校准模式用)
    ppt_app_path = "packages/ppt_engine/src/interface/app.py"
    if (PROJECT_ROOT / ppt_app_path).exists():
        manager.start_service("PPT_Engine_UI", ppt_app_path, 8501)
    else:
        logger.warning(f"⚠️ 找不到 PPT UI 文件: {ppt_app_path}，跳过启动。")

@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_all()
    executor.shutdown(wait=False)

atexit.register(manager.stop_all)

# =============================================================================
# 业务逻辑：工作流配置
# =============================================================================

# 【关键配置】在这里切换 "auto" 或 "human" 模式
STEPS_CONFIG = {
    "daily_report": [
        # 步骤 1: 自动化数据准备 (演示：暂无真实 Adapter，仍用 Mock)
        {"id": 1, "name": "异常监控扫描", "type": "auto", "engine": "anomaly_monitor"},
        
        # 步骤 2: PPT 生成 (关键演示点)
        # -----------------------------------------------------------
        # 模式 A: 全自动模式 (Server 直接调用 PPT Adapter)
        # {"id": 2, "name": "PPT 自动生成", "detail": "正在调用 PPT 引擎...", "type": "auto", "engine": "ppt"},
        
        # 模式 B: 人工校准模式 (Server 引导用户去 UI)
        {"id": 2, "name": "PPT 画布生成", "detail": "等待人工调整...", "type": "human", 
         "action": {"label": "打开 PPT 控制台", "url": "http://localhost:8501"}},
        # -----------------------------------------------------------

        # 步骤 3: 归档 (Mock)
        {"id": 3, "name": "归档与分发", "detail": "正在发送邮件...", "type": "mock_auto"}
    ]
}

# =============================================================================
# 接口定义 (核心逻辑修改)
# =============================================================================

async def event_generator(task_type: str):
    """
    流式任务执行器 (支持 Real Adapter 和 Human Loop)
    """
    steps = STEPS_CONFIG.get(task_type, [])
    
        # 1. 加载全局配置 (用于传给 Adapter)
    try:
        global_config_obj = load_config()
        
        if isinstance(global_config_obj, AppConfig):
            global_config = global_config_obj.model_dump()
        else:
            # 如果是字典或其他类型，直接赋值
            global_config = global_config_obj if isinstance(global_config_obj, dict) else {}
    except Exception as e:
        logger.warning(f"加载全局配置失败: {e}，将使用 Adapter 默认测试配置。")
        global_config = {}


    for step in steps:
        # --- 发送步骤开始信号 ---
        yield json.dumps({
            "status": "running", 
            "step_id": step["id"], 
            "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 开始步骤: {step['name']}"
        }) + "\n"
        
        step_type = step.get("type")

        # === 分支 A: 真实自动化任务 (调用 Adapter) ===
        if step_type == "auto":
            engine_name = step.get("engine")
            
            if engine_name == "ppt":
                # 1. 创建通信队列
                log_queue = Queue()
                adapter = PPTEngineAdapter()
                
                # 2. 在线程池中提交任务 (非阻塞)
                # 注意：config 字典被传入
                future = executor.submit(adapter.run, global_config, log_queue)
                
                # 3. 循环读取日志并推送给前端
                while not future.done() or not log_queue.empty():
                    try:
                        # 非阻塞读取，防止死锁
                        log_msg = log_queue.get(timeout=0.1)
                        yield json.dumps({
                            "status": "running", 
                            "step_id": step["id"], 
                            "log": log_msg
                        }) + "\n"
                    except Empty:
                        # 队列空了，稍作休息等待任务产生新日志
                        await asyncio.sleep(0.1)
                
                # 4. 获取最终结果
                result = future.result() # 这里会抛出 Adapter 内部未捕获的异常
                
                if result.get("status") == "success":
                    yield json.dumps({
                        "status": "completed",
                        "step_id": step["id"],
                        "log": f"✅ {step['name']} 成功。产物: {result.get('output_path')}",
                        "result": {"type": "file", "label": "下载产物", "url": "#"} # 示例
                    }) + "\n"
                else:
                    yield json.dumps({
                        "status": "error",
                        "step_id": step["id"],
                        "log": f"❌ {step['name']} 失败: {result.get('message')}"
                    }) + "\n"

        # === 分支 B: 人工校准任务 (UI Link) ===
        elif step_type == "human":
            yield json.dumps({
                "status": "waiting_input",
                "step_id": step["id"],
                "log": f"请点击下方按钮进入 [{step['name']}] 进行操作。",
                "result": {
                    "type": "link", 
                    "label": step['action']['label'], 
                    "url": step['action']['url']
                }
            }) + "\n"
            
            # 模拟等待用户操作 (真实场景应通过 Webhook 唤醒)
            await asyncio.sleep(3) 

        # === 分支 C: Mock 任务 (用于演示) ===
        else:
            await asyncio.sleep(1) # 假装干活
            yield json.dumps({
                "status": "completed", 
                "step_id": step["id"], 
                "log": f"Mock 任务 [{step['name']}] 完成。"
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
    uvicorn.run("server:app", host="0.0.0.0", port=8507)