from abc import ABC, abstractmethod
from typing import Dict, Any
from queue import Queue

class ITaskEngine(ABC):
    """
    [标准接口] 所有自动化引擎适配器必须遵循的协议。
    采用命令模式 (Command Pattern) 风格。
    """
    
    @abstractmethod
    def run(self, config_dict: Dict[str, Any], log_queue: Queue) -> Dict[str, Any]:
        """
        全自动运行入口。
        
        Args:
            config_dict: 从 Server 传来的原生字典配置 (通常是全局 config.yaml 的内容)
            log_queue: 用于回传实时日志的线程安全队列
            
        Returns:
            Dict: 执行结果摘要 (如: {"status": "success", "output_path": "..."})
        """
        pass