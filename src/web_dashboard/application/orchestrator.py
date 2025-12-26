# src/web_dashboard/application/orchestrator.py
import json
import datetime
import asyncio
import logging
from typing import AsyncGenerator
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

# 引入下层依赖
from src.web_dashboard.infrastructure.workflow_repository import WorkflowRepository

logger = logging.getLogger("App.Orchestrator")

class WorkflowOrchestrator:
    def __init__(self, global_config: Dict[str, Any]):
        self.global_config = global_config
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.repo = WorkflowRepository()

    async def execute_workflow(self, task_type: str, run_mode: str, target_step_id: Optional[int] = None):
        """
        核心生成器逻辑：Yields JSON lines
        """
        steps = self.repo.get_steps(task_type)
        
        for step in steps:
            # 1. 过滤逻辑
            if target_step_id is not None and step["id"] != target_step_id:
                continue

            step_id = step["id"]
            step_name = step["name"]
            
            # 2. 发送开始信号
            yield self._fmt_msg("running", step_id, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 开始步骤: {step_name} (模式: {run_mode})")

            # 3. 模式判定
            current_step_type = step.get("type")
            if current_step_type == "hybrid":
                current_step_type = "auto" if run_mode == "auto" else "human"

            # 4. 执行分支
            if current_step_type == "auto":
                async for msg in self._run_auto_step(step, step_id, step_name):
                    yield msg
            elif current_step_type == "human":
                async for msg in self._run_human_step(step, step_id, step_name):
                    yield msg
            elif current_step_type == "mock_auto":
                await asyncio.sleep(1)
                yield self._fmt_msg("completed", step_id, f"Mock 任务 [{step_name}] 完成。")
            else:
                yield self._fmt_msg("error", step_id, f"未知类型: {current_step_type}")

        yield json.dumps({"status": "done", "log": "Workflow Finished."}) + "\n"

    async def _run_auto_step(self, step, step_id, step_name) -> AsyncGenerator[str, None]:

        """执行自动化适配器的逻辑"""
        engine_name = step.get("engine")
        log_queue = Queue()
        adapter = None
        
        # 动态导入 (为了避免循环依赖，且按需加载)
        try:
            if engine_name == "anomaly_monitor":
                from packages.anomaly_monitor.src.adapter import AnomalyMonitorAdapter
                adapter = AnomalyMonitorAdapter()
            elif engine_name == "web_automation":
                from packages.web_automation.src.adapter import WebAutomationAdapter
                adapter = WebAutomationAdapter()
            elif engine_name == "excel":
                from packages.excel_engine.src.adapter import ExcelEngineAdapter
                adapter = ExcelEngineAdapter()
            elif engine_name == "ppt":
                from packages.ppt_engine.src.adapter import PPTEngineAdapter
                adapter = PPTEngineAdapter()
        except ImportError as e:
            yield self._fmt_msg("error", step_id, f"❌ 模块导入失败: {e}")
            return

        if adapter:
            # 提交到线程池
            future = self.executor.submit(adapter.run, self.global_config, log_queue)
            
            # 日志泵 (Log Pump)
            while not future.done() or not log_queue.empty():
                try:
                    log_msg = log_queue.get(timeout=0.05)
                    yield self._fmt_msg("running", step_id, log_msg)
                except Empty:
                    await asyncio.sleep(0.05)
            
            # 结果处理
            try:
                result = future.result()
                if result.get("status") == "success":
                    log_text = f"✅ {step_name} 执行成功。"
                    if result.get("output_path"):
                        log_text += f" 产物: {result['output_path']}"
                    
                    yield self._fmt_msg(
                        "completed", step_id, log_text,
                        result={"type": "file", "label": "查看产物", "url": "#"} if result.get("output_path") else None
                    )
                else:
                    yield self._fmt_msg("error", step_id, f"❌ 业务失败: {result.get('message')}")
            except Exception as e:
                yield self._fmt_msg("error", step_id, f"❌ 系统异常: {str(e)}")

    async def _run_human_step(self, step, step_id, step_name) -> AsyncGenerator[str, None]:
        """执行人工交互逻辑"""
        action = step.get("action")
        if action:
            yield self._fmt_msg(
                "waiting_input", step_id, 
                f"请点击下方按钮进入 [{step_name}] 进行人工校准。",
                result={"type": "link", "label": action['label'], "url": action['url']}
            )
            await asyncio.sleep(1) # 模拟一点延迟，不用挂太久，因为前端会有按钮
            yield self._fmt_msg("completed", step_id, f"等待用户在 [{step_name}] 中操作...")
        else:
            yield self._fmt_msg("error", step_id, "配置错误：缺少 action 链接")

    def _fmt_msg(self, status, step_id, log, result=None):
        data = {"status": status, "step_id": step_id, "log": log}
        if result: data["result"] = result
        return json.dumps(data) + "\n"
    
    def shutdown(self):
        self.executor.shutdown(wait=False)