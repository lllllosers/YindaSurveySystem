# Web Center 开发入口

Vue 3 + FastAPI + PostgreSQL。当前为 acceptance baseline / version pending，没有人工确认的正式 Web 产品版本。

源码目录是 `web/`；部署包内部和既有服务器目录继续使用 `web_center/`。DB `yinda_web_center`、source_channel `web_center` 和 `backup_web_center` CLI 不变。

在仓库根目录配置 `web/backend/.venv` 与独立开发 PostgreSQL，填写 `web/backend/.env`；分别运行 `web/backend/run_backend.bat`、`web/frontend/run_frontend.bat`，或使用 `web/run_dev.bat`。前端依赖在 `web/frontend` 执行 `npm ci`，构建执行 `npm run build`。

后端回归入口为根目录 `run_tests.py web`；使用专门测试数据库，不指向正式数据。源码只依赖 shared 和 root templates；不需要 desktop 目录。

构建顺序：

```powershell
python web/build_server_console.py
python web/build_deploy_bundle.py
python web/build_portable_windows.py --python-embed <zip> --site-packages <dir> --postgres-home <dir>
```

控制台构建需完整 `web/console-requirements.txt` 环境；后端运行时依赖来自 `web/backend/requirements.txt`。构建输出到 `web/release/`，包内仍是 `web_center/`。

参见 [部署说明](../docs/web/DEPLOY.md)、[便携 GUI 教程](../docs/web/便携包部署教程.md)、[历史验收内容](../docs/web/ACCEPTANCE.md)、[构建输入记录](../docs/architecture/BUILD_INPUTS.md)。
