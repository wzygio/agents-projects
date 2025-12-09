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
        {"id": 1, "name": "数据读取 (Spotfire/Local)", "detail": "读取源文件..."},
        {"id": 2, "name": "异常识别 (AI分析)", "detail": "AI规则判定中..."},
        # 模拟产生一个网页链接
        {"id": 3, "name": "报告生成 (Summary)", "detail": "数据汇总...", 
         "mock_result": {"type": "link", "label": "View Report", "url": "https://google.com"}},
        {"id": 4, "name": "添加到HL记录表", "detail": "写入数据库..."},
        {"id": 5, "name": "添加到异常管理表", "detail": "更新台账..."},
        # 模拟产生一个文件下载
        {"id": 6, "name": "邮件通知责任人", "detail": "发送邮件...",
         "mock_result": {"type": "file", "label": "Email_Log.eml", "url": "#"}}
    ],
    "daily_report": [
        {"id": 1, "name": "生产报表下载", "detail": "获取数据...",
         "mock_result": {"type": "file", "label": "Raw_Data.csv", "url": "#"}},
        {"id": 2, "name": "PPT日报 (入库良率)", "detail": "生成幻灯片...",
         "mock_result": {"type": "file", "label": "Yield_Report_2025.pptx", "url": "#"}},
        {"id": 3, "name": "Excel日报 (过货影响)", "detail": "计算影响...",
         "mock_result": {"type": "file", "label": "Shipment_Impact.xlsx", "url": "#"}},
        {"id": 4, "name": "归档到公盘", "detail": "网络传输..."},
        {"id": 5, "name": "截取关键指标", "detail": "生成截图..."},
        {"id": 6, "name": "发送全员邮件", "detail": "分发中..."},
        {"id": 7, "name": "同步至Web系统", "detail": "API同步...",
         "mock_result": {"type": "link", "label": "Open System", "url": "https://google.com"}}
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
    uvicorn.run("server:app", host="10.72.26.31", port=8505, reload=True)