# 引大调查系统 / YindaSurveySystem

同一源码主线包含三个独立边界：

```text
Desktop 离线调查端 ──→ Shared contracts ←── Web Center 中心端
```

- [Desktop](desktop/README.md)：PySide6 + SQLite，正式版本 1.2.0。
- [Web Center](web/README.md)：Vue 3 + FastAPI + PostgreSQL；acceptance baseline / version pending。
- [Shared](docs/architecture/BOUNDARIES.md)：交换协议、正式表定义、评价标准与原表渲染规则。

源代码分别位于 `desktop/`、`web/`、`shared/`。正式 Excel 模板唯一位于 `templates/excel/`。产品之间不互相导入，shared 不依赖产品、数据库 adapter 或 UI/Web framework。

开发与测试环境按产品建立，不复用另一产品的源码：

```powershell
python -m venv desktop/.venv
desktop/.venv/Scripts/python.exe -m pip install -r desktop/requirements-dev.txt
desktop/.venv/Scripts/python.exe run_tests.py desktop
desktop/.venv/Scripts/python.exe run_tests.py shared

python -m venv web/backend/.venv
web/backend/.venv/Scripts/python.exe -m pip install -r web/backend/requirements-dev.txt
# Web tests need a dedicated test PostgreSQL database and explicit DB_* environment.
web/backend/.venv/Scripts/python.exe run_tests.py web
```

`run_tests.py` 只分派独立 pytest 子进程；`all` 可用 `YINDA_DESKTOP_TEST_PYTHON`、`YINDA_SHARED_TEST_PYTHON`、`YINDA_WEB_TEST_PYTHON` 分别指定完整环境。Web 数据库参数由环境提供，勿对正式数据库运行测试。

版本与已安装用户兼容合同见 [COMPATIBILITY](docs/architecture/COMPATIBILITY.md)，便携构建输入见 [BUILD_INPUTS](docs/architecture/BUILD_INPUTS.md)。[Desktop 历史文档](docs/desktop/05_当前开发状态与路线图.md)与 [Web 验收记录](docs/web/ACCEPTANCE.md)保留原发布/验收历史。

Phase 2 不清理旧 ignored 环境、数据或构建目录；Phase 3 前须落实独立可恢复的二进制构建输入来源。
