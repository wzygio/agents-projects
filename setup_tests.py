import os
from pathlib import Path

# 定义需要创建的目录结构
directories = [
    # 根目录结构
    "tests",
    "tests/factories",
    "tests/packages",
    "tests/resources",

    # Anomaly Monitor
    "tests/packages/anomaly_monitor",
    "tests/packages/anomaly_monitor/unit",
    "tests/packages/anomaly_monitor/unit/core",
    "tests/packages/anomaly_monitor/unit/application",
    "tests/packages/anomaly_monitor/integration",
    "tests/packages/anomaly_monitor/integration/workflows",

    # Common Utils
    "tests/packages/common_utils",
    "tests/packages/common_utils/unit",
    "tests/packages/common_utils/unit/infrastructure",
    "tests/packages/common_utils/unit/interface",
    "tests/packages/common_utils/unit/utils",
    "tests/packages/common_utils/integration",

    # Excel Engine
    "tests/packages/excel_engine",
    "tests/packages/excel_engine/unit",
    "tests/packages/excel_engine/unit/core",
    "tests/packages/excel_engine/unit/application",
    "tests/packages/excel_engine/unit/infrastructure",
    "tests/packages/excel_engine/unit/interface",
    "tests/packages/excel_engine/unit/utils",
    "tests/packages/excel_engine/integration",
    "tests/packages/excel_engine/integration/workflows",

    # PPT Engine
    "tests/packages/ppt_engine",
    "tests/packages/ppt_engine/unit",
    "tests/packages/ppt_engine/unit/core",
    "tests/packages/ppt_engine/unit/application",
    "tests/packages/ppt_engine/unit/infrastructure",
    "tests/packages/ppt_engine/unit/interface",
    "tests/packages/ppt_engine/unit/utils",
    "tests/packages/ppt_engine/integration",
    "tests/packages/ppt_engine/integration/workflows",

    # Web Automation
    "tests/packages/web_automation",
    "tests/packages/web_automation/unit",
    "tests/packages/web_automation/unit/core",
    "tests/packages/web_automation/unit/application",
    "tests/packages/web_automation/unit/infrastructure",
    "tests/packages/web_automation/integration",
    "tests/packages/web_automation/integration/workflows",

    # 静态资源目录
    "tests/resources/input",
    "tests/resources/output",
]

# 定义 pytest.ini 内容
pytest_ini_content = """[pytest]
minversion = 6.0
addopts = -ra -q
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
# 忽略详细的 DeprecationWarning，保持输出干净
filterwarnings =
    ignore::DeprecationWarning
markers =
    unit: Pure logic tests (fast, no I/O)
    integration: Component interaction tests (slower, allowed I/O)
    slow: Tests taking > 1s
"""

def create_structure():
    root = Path.cwd()
    print(f"🚀 开始在 {root} 下创建测试架构...")

    # 1. 创建目录
    for dir_path in directories:
        full_path = root / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ 创建目录: {dir_path}")
        else:
            print(f"🆗 目录已存在: {dir_path}")

        # 2. 递归确保所有父级 Python 包都有 __init__.py
        current = full_path
        while current != root:
            init_file = current / "__init__.py"
            if not init_file.exists():
                init_file.touch()
                print(f" 📄 创建: {init_file.relative_to(root)}")
            current = current.parent

    # 3. 创建 pytest.ini
    ini_path = root / "tests/pytest.ini"
    if not ini_path.exists():
        ini_path.write_text(pytest_ini_content, encoding='utf-8')
        print("✅ 创建配置文件: tests/pytest.ini")
    else:
        print("🆗 配置文件已存在: tests/pytest.ini")

    # 4. 创建各模块的 conftest.py
    modules = ["anomaly_monitor", "common_utils", "excel_engine", "ppt_engine", "web_automation"]
    for module in modules:
        conftest_path = root / f"tests/packages/{module}/conftest.py"
        if not conftest_path.exists():
            conftest_path.touch()
            print(f"✅ 创建模块配置: tests/packages/{module}/conftest.py")

    # 5. 创建工厂类文件
    base_factory = root / "tests/factories/_base.py"
    if not base_factory.exists():
        base_factory.touch()
        print("✅ 创建: tests/factories/_base.py")

    config_factory = root / "tests/factories/config_factory.py"
    if not config_factory.exists():
        config_factory.touch()
        print("✅ 创建: tests/factories/config_factory.py")

    print("\n✨ 测试架构创建完成！")

if __name__ == "__main__":
    create_structure()
