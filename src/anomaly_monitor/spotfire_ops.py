import os
import time
import psutil
from pywinauto import Application

class SpotfireClient:
    def __init__(self):
        self.app = None
        self.main_window = None
        self.process_name = "Spotfire.Dxp.exe" 

    def _get_pid_by_name(self):
        """查找 Spotfire 进程 ID"""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if self.process_name.lower() in proc.info['name'].lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def open_analysis_file(self, file_path):
        """
        打开指定的 Spotfire 分析文件 (.dxp)
        支持本地路径和网络路径 (UNC Path)
        """
        print(f"准备打开文件: {file_path}")
        
        # 1. 检查文件是否存在 (网络路径可能需要一点时间来确认)
        if not os.path.exists(file_path):
            print(f"❌ 错误: 找不到文件。请检查路径或后缀名(.dxp)。\n路径: {file_path}")
            return

        # 2. 检查 Spotfire 是否已在运行
        pid = self._get_pid_by_name()
        if pid:
            print(f"⚠️ 检测到 Spotfire 已在运行 (PID: {pid})。")
            print("提示: 直接打开新文件可能会在现有窗口中打开，或者弹出'是否保存'提示。")
            # 在生产环境中，这里可能需要先 kill 掉旧进程，视你的业务逻辑而定
        
        # 3. 调用系统打开文件 (核心步骤)
        print("正在从共享盘加载文件 (os.startfile)...")
        try:
            os.startfile(file_path) 
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            return

        # 4. 循环等待进程 (网络文件加载慢，耐心等待)
        print("等待 Spotfire 进程响应...")
        for i in range(120): # <--- 延长到 120秒，防止网络卡顿
            pid = self._get_pid_by_name()
            if pid:
                # 稍微多等一下，确保它不是刚闪现就消失
                break
            time.sleep(1)
        
        if not pid:
            print("❌ 超时: 2分钟内未检测到进程启动。")
            return

        # 5. 连接并接管窗口
        try:
            print(f"进程已捕获 (PID: {pid})，正在尝试挂载自动化...")
            # 稍微 sleep 一下，让 Spotfire 有时间从网络读取 Header
            time.sleep(120) 
            
            self.app = Application(backend='uia').connect(process=pid)
            
            print("等待主窗口加载完毕 (Loading Data)...")
            # 寻找主窗口
            self.main_window = self.app.window(title_re=".*Spotfire.*")
            
            # Spotfire 加载大文件时窗口可能会“假死”或显示“无响应”，这是正常的
            # wait('ready') 可能不准，这里我们用 wait('visible') 配合较长的超时
            self.main_window.wait('visible', timeout=300) # <--- 给它 5分钟加载数据
            
            print(f"✅ 成功打开文件并接管窗口: {self.main_window.wrapper_object().window_text()}")
            
            if not self.main_window.has_focus():
                self.main_window.set_focus()
                
        except Exception as e:
            print(f"⚠️ 连接窗口阶段出现异常 (可能是加载太慢): {e}")

    def close_app(self):
        if self.app:
            self.app.kill()

# --- 单元测试入口 ---
if __name__ == "__main__":
    # 1. 定义网络路径 (注意前面的 r 表示 raw string)
    # 我在文件名后帮你加上了 .dxp，请确认原文件是否有这个后缀
    network_file_path = r"\\10.71.7.15\大数据共享\12.良率监控日报自动化\Spotfire-CT不良初步调查模板-HL-V4.dxp"
    
    # 2. 实例化并运行
    client = SpotfireClient()
    client.open_analysis_file(network_file_path)