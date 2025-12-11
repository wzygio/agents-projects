import uiautomation as auto
import time
import pyperclip
import ctypes

# 设置搜索等待时间
auto.SetGlobalSearchTimeout(3)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

class DingTalkMouseSender:
    def __init__(self):
        log("正在连接 V来家/钉钉 ...")
        # 1. 查找主窗口
        self.window = auto.WindowControl(searchDepth=1, SubName="V来家")
        if not self.window.Exists(0, 1):
             self.window = auto.WindowControl(searchDepth=1, SubName="钉钉")

    def right_click_paste(self, control):
        """核心黑科技：纯鼠标右键粘贴"""
        # 1. 移动鼠标到控件中心并右键
        log(f"正在右键点击控件: {control.Name}")
        control.RightClick()
        time.sleep(1.0) # 等待右键菜单弹出

        # 2. 尝试查找“粘贴”菜单项
        # 钉钉的右键菜单通常是一个独立的弹窗，Name="粘贴"
        # 这里的 searchDepth=2 是在桌面上找（因为菜单是顶层窗口）
        paste_menu = auto.MenuItemControl(searchDepth=4, Name="粘贴")
        
        if paste_menu.Exists(0, 1):
            log("👀 找到了'粘贴'菜单，点击！")
            paste_menu.Click()
        else:
            log("⚠️ 未识别到'粘贴'文字，尝试盲点方案...")
            # 备用方案：右键菜单通常出现在鼠标右下角
            # 我们直接移动鼠标，点击大概率是“粘贴”的位置
            # 假设粘贴是第1个或第2个选项，向下移动 10-20 像素点击
            # 获取当前鼠标位置
            x, y = auto.GetCursorPos()
            # 往右下稍微移一点点（避开边缘），点击第一个菜单项的位置
            auto.Click(x + 20, y + 20) 
        
        time.sleep(0.5)

    def send_msg(self, contact_name, message):
        if not self.window.Exists(0, 1):
            log("❌ 未找到窗口")
            return False

        # 1. 激活窗口 (尝试还原和置顶，方便点击)
        try:
            self.window.ShowWindow(9) # SW_RESTORE
            self.window.SetTopmost(True)
            time.sleep(0.5)
        except:
            pass

        # ----------------------
        # 步骤 1: 搜索联系人
        # ----------------------
        log("🔍 寻找搜索框...")
        # 搜索框通常在左上角，Name可能是"搜索"
        search_box = self.window.EditControl(Name="搜索")
        if not search_box.Exists(0, 1):
            # 如果找不到 Name="搜索"，尝试找左上角的第一个编辑框
            search_box = self.window.EditControl(searchDepth=5, foundIndex=1)
        
        # 复制名字
        pyperclip.copy(contact_name)
        
        # 执行右键粘贴
        self.right_click_paste(search_box)
        
        log("等待搜索结果...")
        time.sleep(2.0) # 搜索需要时间，如果是V来家，可能更慢

        # ----------------------
        # 步骤 2: 点击联系人
        # ----------------------
        # 搜索结果列表通常就在搜索框的正下方
        # 我们很难精确获取那个 List item，最稳的办法是：盲点搜索框下面一点点
        rect = search_box.BoundingRectangle
        # 计算点击位置：搜索框底部向下 60 像素（通常是第一个人的位置）
        click_x = (rect.left + rect.right) // 2
        click_y = rect.bottom + 60 
        
        log(f"🖱️ 点击第一个搜索结果: ({click_x}, {click_y})")
        auto.Click(click_x, click_y)
        time.sleep(1.0) # 等待聊天框打开

        # ----------------------
        # 步骤 3: 输入消息
        # ----------------------
        log("✍️ 寻找输入框...")
        # 输入框通常是界面里最大的那个编辑区，或者叫"输入消息"
        input_box = self.window.EditControl(Name="输入消息")
        if not input_box.Exists(0, 1):
            # 备用：找最后一个编辑框（通常是输入框）
            edits = self.window.GetChildren()
            # 这里简化处理，尝试找 Name 包含 "输入" 的
            input_box = self.window.EditControl(SubName="输入")
        
        if input_box.Exists(0, 1):
            pyperclip.copy(message)
            self.right_click_paste(input_box)
        else:
            log("❌ 找不到输入框，尝试直接点击窗口右下角区域...")
            # 极端的盲点备用方案
            win_rect = self.window.BoundingRectangle
            auto.Click(win_rect.right - 200, win_rect.bottom - 100)
            time.sleep(0.5)
            # 假设现在焦点在输入框了，模拟 Ctrl+V (如果不让用键，这一步可能失败)
            # 所以最好还是找到 input_box 控件
        
        time.sleep(0.5)

        # ----------------------
        # 步骤 4: 点击发送按钮
        # ----------------------
        log("🚀 寻找发送按钮...")
        # 按钮通常叫 "发送" 或 "发送(S)"
        send_btn = self.window.ButtonControl(SubName="发送")
        
        if send_btn.Exists(0, 1):
            log("点击发送按钮")
            send_btn.Click()
        else:
            log("⚠️ 找不到发送按钮，尝试盲点...")
            # 发送按钮通常在输入框右下角
            # 或者尝试按回车 (如果能按的话)
            # 这里我们尝试找包含 "Send" 的
            send_btn = self.window.ButtonControl(SubName="Send")
            if send_btn.Exists(0, 1):
                send_btn.Click()
            else:
                log("❌ 彻底找不到发送按钮，任务中止")
                self.window.SetTopmost(False)
                return False

        self.window.SetTopmost(False)
        log("✅ 流程结束")
        return True

if __name__ == "__main__":
    sender = DingTalkMouseSender()
    # 建议先测试文件传输助手
    sender.send_msg("文件传输助手", "【纯鼠标版】这是一条通过右键粘贴发送的消息")