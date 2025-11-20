from src.workflow import AutomationWorkflow

if __name__ == "__main__":
    # 实例化业务流程类
    workflow = AutomationWorkflow()
    
    # 执行输入产品型号的任务
    workflow.search_and_select_report()

