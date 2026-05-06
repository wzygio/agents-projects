# src/web_dashboard/interfaces/api.py
import logging
import atexit
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# --- 导入路径处理 ---
# 确保能找到项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent # 指向 src/web_dashboard
PROJECT_ROOT = BASE_DIR.parent.parent         # 指向 agents-projects 根目录
sys.path.append(str(PROJECT_ROOT))

# --- 导入分层模块 ---
from src.web_dashboard.infrastructure.process_manager import ProcessManager
from src.web_dashboard.application.orchestrator import WorkflowOrchestrator
from src.config import load_config

# --- 初始化日志 ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger("API")

# --- 创建 FastAPI 实例 ---
app = FastAPI(title="Duty Automation Orchestrator")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件挂载
STATIC_DIR = BASE_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- 依赖注入 (Dependency Injection) ---
# 1. 加载全局配置
try:
    global_config_obj = load_config()
    global_config = global_config_obj.model_dump() if hasattr(global_config_obj, 'model_dump') else {}
except Exception:
    global_config = {}

# 2. 实例化核心服务
process_manager = ProcessManager(PROJECT_ROOT)
orchestrator = WorkflowOrchestrator(global_config)

# --- 生命周期钩子 ---
@app.on_event("startup")
async def startup_event():
    logger.info(">>> [System Startup] Initializing Sub-services...")
    
    # 启动 异常监控 (8511)
    process_manager.start_streamlit_service(
        "Anomaly_Monitor_UI", 
        "packages/anomaly_monitor/src/interface/pages/hl_dashboard.py", 
        8511
    )
    # 启动 Excel (8512)
    process_manager.start_streamlit_service(
        "Excel_Engine_UI", 
        "packages/excel_engine/src/interface/pages/excel_dashboard.py", 
        8512
    )
    # 启动 PPT (8513)
    process_manager.start_streamlit_service(
        "PPT_Engine_UI", 
        "packages/ppt_engine/src/interface/pages/ppt_dashboard.py", 
        8513
    )

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(">>> [System Shutdown] Cleaning up...")
    process_manager.stop_all()
    orchestrator.shutdown()

# 注册退出清理
atexit.register(process_manager.stop_all)

# --- 路由定义 (Routes) ---

@app.get("/start/{task_type}")
async def start_task(
    task_type: str, 
    mode: str = "human", 
    step_id: Optional[int] = Query(None)
):
    """
    启动任务接口：调用应用层的 Orchestrator
    """
    return StreamingResponse(
        orchestrator.execute_workflow(task_type, mode, step_id), 
        media_type="application/x-ndjson"
    )

@app.get("/")
async def main_page():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Dashboard is running. Please place index.html in static folder.</h1>")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())