# src/web_dashboard/infrastructure/process_manager.py
import subprocess
import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger("Infra.ProcessManager")

class ProcessManager:
    def __init__(self, project_root: Path):
        self.services = {}
        self.project_root = project_root

    def _kill_existing_process_on_port(self, port):
        """[工具] 强力查杀占用端口的旧进程"""
        try:
            if os.name == 'nt':  # Windows
                cmd = f'netstat -aon | findstr :{port}'
                try:
                    result = subprocess.check_output(cmd, shell=True).decode()
                except subprocess.CalledProcessError:
                    result = ""
                
                if "LISTENING" in result:
                    for line in result.strip().split('\n'):
                        parts = line.split()
                        if len(parts) > 4:
                            pid = parts[-1]
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                            logger.info(f"已清理占用端口 {port} 的旧进程 PID: {pid}")
            else:  # Linux/Mac
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
        except Exception:
            pass

    def start_streamlit_service(self, name: str, script_rel_path: str, port: int):
        """启动 Streamlit 子服务"""
        self._kill_existing_process_on_port(port)
        
        full_path = self.project_root / Path(script_rel_path)
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
        # 关键：设置 PYTHONPATH
        env["PYTHONPATH"] = str(self.project_root) + os.pathsep + env.get("PYTHONPATH", "")

        logger.info(f"正在启动子服务 [{name}] on Port {port}...")
        process = subprocess.Popen(
            cmd, cwd=str(self.project_root), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.services[name] = process
        logger.info(f"✅ 服务 [{name}] 启动成功 (PID: {process.pid})")

    def stop_all(self):
        for name, proc in self.services.items():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info(f"服务 [{name}] 已停止")