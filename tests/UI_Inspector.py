import uiautomation as auto
import time

def inspect_ui():
    print("👉 请在 3 秒内，将鼠标移动到钉钉左上角的【搜索框】中间，并保持不动！")
    for i in range(3, 0, -1):
        print(f"倒计时: {i}...")
        time.sleep(1)
    
    print("📸 正在拍照分析...")
    # 获取鼠标下的控件
    control = auto.ControlFromCursor()
    
    print("\n" + "="*30)
    print("🔍 控件身份信息 (请把下面这些发给我)")
    print("="*30)
    print(f"Name (名字):      [{control.Name}]")
    print(f"ControlType:     {control.ControlTypeName} ({control.ControlType})")
    print(f"ClassName:       {control.ClassName}")
    print(f"AutomationId:    {control.AutomationId}")
    print("="*30)
    
    # 顺便看看它的父级（有时候搜索框外面还包了一层）
    parent = control.GetParentControl()
    if parent:
        print(f"父级 Name:        [{parent.Name}]")
        print(f"父级 ControlType: {parent.ControlTypeName}")
    print("="*30)

if __name__ == "__main__":
    inspect_ui()