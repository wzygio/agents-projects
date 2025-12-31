# 🛠️ 项目：OLED自动化系统 - 自动化测试架构规范 (v1.1)

## 1. 核心原则 (Core Principles)

* **镜像策略 (Mirror Strategy)**：测试目录结构必须严格复刻源代码的 `packages/` 结构。找不到对应源文件的测试文件是“二等公民”。
* **测试分层 (Testing Pyramid)**：
* **Unit (L1)**: 纯逻辑验证。**绝对禁止**文件 I/O、数据库连接或外部 API 调用。所有依赖必须 Mock。
* **Integration (L2)**: 验证组件间协作（如 Generator 调用 DataProcessor）。允许受控的 I/O（如读写临时文件）。


* **数据工厂 (Factory Pattern)**：禁止在 Test Case 中手写复杂的 Config 字典。必须通过 `factories` 生成 Pydantic 对象，确保测试数据的一致性与可维护性。
* **无副作用 (Stateless)**：每个测试用例执行前后，环境（Env/DB/File System）状态必须一致。

## 2. 目录结构蓝图 (Directory Blueprint)

```text
项目根目录/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # [Root] 全局共享 Fixtures (通用 Mock, Env设置)
│   ├── pytest.ini                  # [Config] 标记(Markers)、覆盖率配置、CLI参数
│   ├── factories/                  # [Data] 数据工厂层
│   │   ├── __init__.py
│   │   ├── _base.py                # 定义 PydanticModelFactory 基类
│   │   └── config_factory.py       # 生产 PptEngineConfig, SlideConfig 等
│   ├── packages/                   # [Mirror] 业务模块镜像
│   │   ├── __init__.py
│   │   └── ppt_engine/
│   │       ├── __init__.py
│   │       ├── conftest.py         # [Module] 仅该模块可见的 Fixtures (如特定 PPT 模板)
│   │       ├── unit/               # [L1] 单元测试
│   │       │   ├── core/           # 对应 src/packages/ppt_engine/core
│   │       │   └── application/
│   │       └── integration/        # [L2] 集成测试
│   │           └── workflows/      # 测试完整生成流程
│   └── resources/                  # [Assets] 静态资源
│       ├── input/                  # 只读：Excel 数据源, PPT 母版
│       └── output/                 # 临时：测试生成的产物 (应在 .gitignore 中)

```

## 3. 技术选型 (Tech Stack)

* **Runner**: `pytest`
* **Mocking**: `pytest-mock` (标准化使用 `mocker` fixture)
* **Data Generation**: `factory_boy` (配合 Pydantic)
* **Assertion**: 标准 `assert` 语句 + `pytest.raises` (异常断言)
* **Coverage**: `pytest-cov` (监控代码覆盖率)

## 4. 关键文件职责 (Responsibilities)

### 4.1 `tests/conftest.py` (全局配置)

* **路径修补**: 自动将 `src` 加入 `sys.path`。
* **Global Fixtures**:
* `temp_workspace`: 自动创建并清理的临时目录（基于 `tmp_path`），用于所有涉及文件操作的测试。
* `mock_logger`: 拦截日志输出，防止测试跑数时控制台被污染。



### 4.2 `tests/factories/config_factory.py` (数据工厂)

* **Pydantic 适配**: 必须使用 `factory.ConstructableFactory` 或自定义 Meta 类，以支持 Pydantic 的 `__init__` 验证机制。
* **示例代码规范**:
```python
class PptEngineConfigFactory(factory.Factory):
    class Meta:
        model = PptEngineConfig

    # 使用 Sequence 防止命名冲突
    job_id = factory.Sequence(lambda n: f"job_{n}")
    output_path = factory.Faker('file_path', extension='pptx')

```



### 4.3 `tests/packages/.../unit/` (单元测试)

* **Mock 范围**: 针对 `python-pptx` 的 `Presentation`, `Slide`, `Shape` 对象必须 Mock，不应真实创建 PPT 对象（速度慢且依赖环境）。

## 5. 命名与编写规范 (Conventions)

### 5.1 命名约定

* **文件**: `test_<模块名>.py` (如 `test_slide_renderer.py`)
* **类**: `Test<被测类名>` (如 `TestSlideRenderer`)
* **函数**: `test_<方法名>_<条件>_<预期>`
* ✅ `test_render_chart_with_empty_data_raises_value_error`
* ❌ `test_render_chart_error` (语焉不详)



### 5.2 标记 (Markers) - 在 `pytest.ini` 中定义

* `@pytest.mark.unit`: 纯逻辑测试，必须能在 0.1s 内完成。
* `@pytest.mark.integration`: 集成测试，涉及文件读写。
* `@pytest.mark.slow`: 耗时超过 1s 的测试。

## 6. IO 与 资源管理规范 (Critical)

### 6.1 读写控制

* **禁止原地修改**: 测试中严禁修改 `resources/input/` 下的文件。
* **临时沙箱**: 所有文件生成必须指向 `tmp_path` (Pytest 内置 fixture) 或 `tests/resources/output/`。
* **自动清理**: 使用 Fixture 的 `yield` 机制确保测试结束后清理生成的临时文件。

### 6.2 样本数据

* **最小化原则**: 测试用的 Excel/PPT 样本应尽可能小（例如只保留 1 页 Slide，1 行 Excel 数据），仅包含触发测试逻辑的必要内容。

## 7. 验证清单 (Checklist)

在提交代码前，必须通过以下检查：

1. [ ] 所有测试通过 (`pytest`)。
2. [ ] 无 `DeprecationWarning` 或资源未关闭警告。
3. [ ] 单元测试不产生任何实际的 `.pptx` 文件。
4. [ ] 工厂类生成的 Config 对象能通过 Pydantic 的校验。
