import asyncio
import uvicorn
import json
import datetime
import os
import sys
import subprocess
import logging
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
# 确保 PYTHONPATH 包含项目根目录
sys.path.append(str(Path(__file__).resolve().parents[2])) 

# 1. 引入全局配置加载器
try:
    from src.config import load_config 
except ImportError:
    load_config = lambda: {} 

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
        
        full_path = PROJECT_ROOT / script_path
        if not full_path.exists():
            logger.warning(f"⚠️ 服务 [{name}] 脚本不存在: {full_path}，跳过启动。")
            return

        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(full_path),
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
    
    # 1. 启动 PPT 控制台 (8501)
    manager.start_service(
        "PPT_Engine_UI", 
        "packages/ppt_engine/src/interface/app.py", 
        8501
    )
    
    # 2. [新增] 启动 Excel 控制台 (8502)
    manager.start_service(
        "Excel_Engine_UI", 
        "packages/excel_engine/src/interface/app.py", 
        8502
    )

    # 3. [新增] 启动 异常监控 控制台 (8503)
    manager.start_service(
        "Anomaly_Monitor_UI", 
        "packages/anomaly_monitor/src/interface/hl_app.py", 
        8503
    )

@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_all()
    executor.shutdown(wait=False)

atexit.register(manager.stop_all)

# =============================================================================
# 业务逻辑：工作流配置 (全流程)
# =============================================================================

STEPS_CONFIG = {
    "daily_report": [
        # Step 1: 异常监控 (数据源头)
        {
            "id": 1, 
            "name": "异常监控扫描", 
            "type": "hybrid", 
            "engine": "anomaly_monitor", 
            "action": {"label": "打开异常监控台", "url": "http://localhost:8503"} 
        },
        # Step 2: 报表自动下载 (新增)
        {
            "id": 2, 
            "name": "报表自动下载", 
            "type": "auto", 
            "engine": "web_automation" 
        },
        # Step 3: Excel 日报生成 (新增)
        {
            "id": 3,
            "name": "Excel 日报生成",
            "type": "hybrid",
            "engine": "excel",
            "action": {"label": "打开 Excel 控制台", "url": "http://localhost:8502"}
        },
        
        # Step 4: PPT 报告生成
        {
            "id": 4, 
            "name": "PPT 报告生成", 
            "type": "hybrid", 
            "engine": "ppt", 
            "action": {"label": "打开 PPT 控制台", "url": "http://localhost:8501"}
        },

        # Step 5: 归档 (Mock)
        # {"id": 5, "name": "归档与分发", "detail": "正在发送邮件...", "type": "mock_auto"}
    ]
}

# =============================================================================
# 接口定义 (支持 Hybrid 模式与多适配器)
# =============================================================================

async def event_generator(task_type: str, run_mode: str = "human"):
    """
    流式任务执行器
    :param task_type: 任务类型
    :param run_mode: 'auto' | 'human'
    """
    steps = STEPS_CONFIG.get(task_type, [])
    
    # 加载全局配置
    try:
        global_config_obj = load_config()
        if isinstance(global_config_obj, AppConfig):
            global_config = global_config_obj.model_dump()
        elif isinstance(global_config_obj, dict):
            global_config = global_config_obj
        else:
            global_config = {}
    except Exception as e:
        logger.warning(f"加载全局配置失败: {e}，将使用 Adapter 默认测试配置。")
        global_config = {}

    for step in steps:
        step_id = step["id"]
        step_name = step["name"]
        
        yield json.dumps({
            "status": "running", 
            "step_id": step_id, 
            "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 开始步骤: {step_name} (模式: {run_mode})"
        }) + "\n"
        
        # === 动态类型判定 ===
        current_step_type = step.get("type")
        if current_step_type == "hybrid":
            current_step_type = "auto" if run_mode == "auto" else "human"

        # =========================================================
        # 分支 A: 自动化任务 (调用 Adapter)
        # =========================================================
        if current_step_type == "auto":
            engine_name = step.get("engine")
            
            log_queue = Queue()
            adapter = None
            
            # --- 1. 路由选择 ---
            if engine_name == "anomaly_monitor":
                try:
                    from packages.anomaly_monitor.src.adapter import AnomalyMonitorAdapter
                    adapter = AnomalyMonitorAdapter()
                except ImportError as e:
                    yield json.dumps({"status": "error", "step_id": step_id, "log": f"❌ 导入异常监控模块失败: {e}"}) + "\n"
                    continue
            
            elif engine_name == "web_automation":
                try:
                    from packages.web_automation.src.adapter import WebAutomationAdapter
                    adapter = WebAutomationAdapter()
                except ImportError as e:
                    yield json.dumps({"status": "error", "step_id": step_id, "log": f"❌ 导入 Web 模块失败: {e}"}) + "\n"
                    continue
            # [新增] Excel 引擎路由
            elif engine_name == "excel":
                try:
                    from packages.excel_engine.src.adapter import ExcelEngineAdapter
                    adapter = ExcelEngineAdapter()
                except ImportError as e:
                    yield json.dumps({"status": "error", "step_id": step_id, "log": f"❌ 导入 Excel 引擎模块失败: {e}"}) + "\n"
                    continue

            elif engine_name == "ppt":
                try:
                    from packages.ppt_engine.src.adapter import PPTEngineAdapter
                    adapter = PPTEngineAdapter()
                except ImportError as e:
                    yield json.dumps({"status": "error", "step_id": step_id, "log": f"❌ 导入 PPT 引擎模块失败: {e}"}) + "\n"
                    continue
            
            # elif engine_name == "mock_archiver":
            #     await asyncio.sleep(1)
            #     yield json.dumps({"status": "completed", "step_id": step_id, "log": "✅ 模拟归档完成"}) + "\n"
            #     continue
            
            # --- 2. 执行 Adapter ---
            if adapter:
                future = executor.submit(adapter.run, global_config, log_queue)
                
                # Log Pump
                while not future.done() or not log_queue.empty():
                    try:
                        log_msg = log_queue.get(timeout=0.05)
                        yield json.dumps({"status": "running", "step_id": step_id, "log": log_msg}) + "\n"
                    except Empty:
                        await asyncio.sleep(0.05)
                
                # 获取结果
                try:
                    result = future.result()
                    if result.get("status") == "success":
                        success_log = f"✅ {step_name} 执行成功。"
                        if result.get("output_path"):
                            success_log += f" 产物: {Path(result['output_path']).name}"
                        
                        yield json.dumps({
                            "status": "completed",
                            "step_id": step_id,
                            "log": success_log,
                            "result": {"type": "file", "label": "查看产物", "url": "#"} if result.get("output_path") else None
                        }) + "\n"
                    else:
                        yield json.dumps({
                            "status": "error",
                            "step_id": step_id,
                            "log": f"❌ {step_name} 业务失败: {result.get('message')}"
                        }) + "\n"
                except Exception as e:
                    yield json.dumps({"status": "error", "step_id": step_id, "log": f"❌ {step_name} 系统异常: {str(e)}"}) + "\n"

        # =========================================================
        # 分支 B: 人工任务 (引导至 UI)
        # =========================================================
        elif current_step_type == "human":
            action = step.get("action")
            if action:
                yield json.dumps({
                    "status": "waiting_input",
                    "step_id": step_id,
                    "log": f"请点击下方按钮进入 [{step_name}] 进行人工校准。",
                    "result": {
                        "type": "link", 
                        "label": action['label'], 
                        "url": action['url']
                    }
                }) + "\n"
                await asyncio.sleep(3) 
                yield json.dumps({"status": "completed", "step_id": step_id, "log": f"用户操作 [{step_name}] 已完成 (模拟)。"}) + "\n"
            else:
                 yield json.dumps({"status": "error", "step_id": step_id, "log": "配置错误：缺少 action 链接"}) + "\n"

        # =========================================================
        # 分支 C: 纯 Mock 任务
        # =========================================================
        elif current_step_type == "mock_auto":
            await asyncio.sleep(1)
            yield json.dumps({"status": "completed", "step_id": step_id, "log": f"Mock 任务 [{step_name}] 完成。"}) + "\n"
        
        else:
             yield json.dumps({"status": "error", "step_id": step_id, "log": f"未知的步骤类型: {current_step_type}"}) + "\n"

    yield json.dumps({"status": "done", "log": "Workflow Finished."}) + "\n"

@app.get("/start/{task_type}")
async def start_task(task_type: str, mode: str = "human"):
    return StreamingResponse(event_generator(task_type, mode), media_type="application/x-ndjson")

@app.get("/")
async def main():
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return HTMLResponse("<h1>Dashboard is running. Please place index.html in static folder.</h1>")
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8507)