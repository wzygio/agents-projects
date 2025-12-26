# src/web_dashboard/infrastructure/workflow_repository.py

# 这里集中管理所有的步骤配置，以后可以轻松改为从 YAML 读取
WORKFLOW_DEFINITIONS = {
    "automated_duty_system": [
        {
            "id": 1, 
            "name": "异常监控扫描", 
            "type": "hybrid", 
            "engine": "anomaly_monitor", 
            "action": {"label": "打开异常监控台", "url": "http://localhost:8511"} 
        },
        {
            "id": 2, 
            "name": "报表自动下载", 
            "type": "auto", 
            "engine": "web_automation" 
        },
        {
            "id": 3,
            "name": "Excel 日报生成",
            "type": "hybrid", 
            "engine": "excel",
            "action": {"label": "打开 Excel 控制台", "url": "http://localhost:8512"}
        },
        {
            "id": 4, 
            "name": "PPT 报告生成", 
            "type": "hybrid", 
            "engine": "ppt", 
            "action": {"label": "打开 PPT 控制台", "url": "http://localhost:8513"}
        }
    ]
}

class WorkflowRepository:
    """仓储模式：负责获取工作流定义"""
    @staticmethod
    def get_steps(task_type: str):
        return WORKFLOW_DEFINITIONS.get(task_type, [])