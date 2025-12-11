# src/web_dashboard/server.py
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 配置步骤及其产物模拟
STEPS_CONFIG = {
    "monitor": [
        # --- Group 1: 数据获取 ---
        {"id": 1, "name": "Spotfire数据导出", "detail": "正在导出Spotfire数据..."},
        {"id": 2, "name": "数据清洗与预处理", "detail": "正在Merge HL/Yield/History数据表..."},
        
        # --- Group 2: 判定引擎 ---
        {"id": 3, "name": "L1: 基础筛选", "detail": "执行 Design Rule 基础过滤..."},
        {"id": 4, "name": "L2: 历史批次分析", "detail": "对比近14天历史均值与方差..."},
        {"id": 5, "name": "L3: 集中性分析", "detail": "调用 ConcentrationAnalyzer 算法..."},
        
        # --- Single: AI Agent ---
        {"id": 6, "name": "控制台启动", "detail": "Qwen-Max 正在识别异常...", 
         "mock_result": {"type": "link", "label": "异常监控平台", "url": "http://10.72.26.31:8506"}},
        
        # --- Group 3: 闭环处置 ---
        {"id": 7, "name": "生成 HL 通报摘要", "detail": "正在生成通报摘要..."},
        {"id": 8, "name": "写入 HL 电子台账", "detail": "Database Transaction..."},
        {"id": 9, "name": "更新异常管理清单", "detail": "追加长期追踪项..."},
        {"id": 10, "name": "EM通知责任人", "detail": "发送 SMTP EM..."}
    ],
    "daily_report": [
        # --- Group 1: 数据采集 ---
        {"id": 1, "name": "Playwright报表下载", "detail": "正在登录验证..."},
        {"id": 2, "name": "数据清洗与预处理", "detail": "Pandas DataFrame 预处理..."},
        
        # --- Group 2: Excel 引擎 ---
        {"id": 3, "name": "各产品当日数据汇总", "detail": "执行 ExcelRenderer 算法..."},
        {"id": 4, "name": "各产品当日异常报告", "detail": "执行 ExceptionProcessor 算法...",
         "mock_result": {"type": "link", "label": "Excel日报生成器", "url": "http://10.72.26.31:8502"}},
        
        # --- Group 3: PPT 引擎 ---
        {"id": 5, "name": "画布预处理 (Canvas Prep)", "detail": "调用 PowerPoint API...",},
        {"id": 6, "name": "数据注入与图表渲染", "detail": "调用 PowerPoint API...",
         "mock_result": {"type": "link", "label": "PPT日报生成器", "url": "http://10.72.26.31:8501"}},
        
        # --- Group 4: AI & 交付 ---
        {"id": 7, "name": "日报推送 (Email)", "detail": "调用 Outlook API..."},
        {"id": 8, "name": "EM通知群推送", "detail": "调用 Web API..."},
        {"id": 9, "name": "归档至公盘 (Archive)", "detail": "正在写入公盘..."}
    ]
}

async def event_generator(task_type: str):
    steps = STEPS_CONFIG.get(task_type, [])
    
    for step in steps:
        # 1. Running
        yield json.dumps({
            "status": "running",
            "step_id": step["id"],
            "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] EXEC: {step['detail']}"
        }) + "\n"
        
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        if random.random() > 0.6:
             yield json.dumps({
                "status": "log",
                "log": f"   >> info: processed chunk {random.randint(100,999)}..."
            }) + "\n"
             await asyncio.sleep(0.3)

        # 2. Completed (带产物)
        response_data = {
            "status": "completed",
            "step_id": step["id"],
            "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] OK: {step['name']} 完成."
        }
        
        # 如果该步骤配置了模拟产物，则一起发送给前端
        if "mock_result" in step:
            response_data["result"] = step["mock_result"]

        yield json.dumps(response_data) + "\n"

    yield json.dumps({"status": "done", "log": "Workflow Finished."}) + "\n"

@app.get("/start/{task_type}")
async def start_task(task_type: str):
    return StreamingResponse(event_generator(task_type), media_type="application/x-ndjson")

@app.get("/")
async def main():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    # 请确保host/port与您实际环境一致
    uvicorn.run("server:app", host="10.72.26.31", port=8507, reload=True)