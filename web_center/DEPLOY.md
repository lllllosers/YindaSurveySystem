# Web 中心部署与数据初始化

部署包由 `web_center/build_deploy_bundle.py` 生成，只包含 Web 后端、编译后的页面、共享协议、正式主数据契约及在线表单所需的规则文件。桌面 GUI、完整桌面源码、测试、`.venv`、`node_modules`、本地账号、上传文件和数据库备份均不进入部署包。

## 1. 在开发机生成部署包

在仓库根目录运行：

```powershell
cd web_center/frontend
npm ci
npm run build
cd ..
python build_deploy_bundle.py
```

生成的 ZIP 位于 `web_center/release/`。桌面端继续使用现有 `.ydtask V3 / .ydresult 2.2`，不要单独修改部署包里的 `shared/` 或表单规则。

## 2. 在服务器首次安装

准备 PostgreSQL、Python、PostgreSQL 客户端 `pg_dump`，解压部署包到固定目录。本机验证环境为 Python 3.12.14、PostgreSQL 17.11；首次部署建议使用相同大版本。数据库仅允许应用服务器访问，为 Web 中心创建独立数据库及仅供该应用使用的账号。以下命令在解压目录的 `web_center/backend` 中执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 中的 `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`。正式 HTTPS 环境设置 `APP_ENV=production`、`SESSION_COOKIE_SECURE=true`，限制 `.env` 的文件读取权限。随后执行：

```powershell
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.cli.create_admin
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

同一个后端服务提供 `/api/v1` 与编译后的网页。让 HTTPS 反向代理将网站根路径转发到 `127.0.0.1:8000`，并保持请求路径与 Cookie；外部访问只开放 HTTPS 入口。`/api/v1/health` 和 `/api/v1/health/database` 可用于检查服务与数据库。以上启动命令用于首次确认，长期运行时应交给服务器的服务管理器，并设置开机启动及失败重启。

## 3. 升级与恢复

升级前停止写入，备份数据库和 `backend/storage/`：

```powershell
.venv\Scripts\python.exe -m app.cli.backup_web_center
```

把完整备份移到独立磁盘。替换程序文件时保留服务器自己的 `.env`、`storage/` 和备份目录；运行 `alembic upgrade head` 后重启服务。恢复时停止服务，将同一次备份中的 PostgreSQL 自定义格式数据库文件和 `storage/` 成套恢复，再按备份对应的程序版本启动。不要只恢复数据库而丢失成果文件。

## 4. 新系统清空测试数据

**仅在准备以空白 Web 业务库正式启用时执行。** 该操作清除 Web 账号、注册邀请、项目、批次、任务、在线记录、成果包、正式成果、审计记录和上传文件；保留 Alembic 结构版本，并从正式契约重新初始化管理处、管理所、渠道和分管范围。桌面端数据库及文件不受影响。

```powershell
.venv\Scripts\python.exe -m app.cli.reset_web_data
.venv\Scripts\python.exe -m app.cli.reset_web_data --execute --confirm yinda_web_center
.venv\Scripts\python.exe -m app.cli.create_admin
```

第一条只显示当前各表数量。第二条会再次执行完整备份，`--confirm` 必须与 `.env` 中当前数据库名相同。执行时暂停 Web 服务写入；完成后立即创建新的首位管理员。已有正式业务数据时不要使用这个命令，使用页面上的停用、取消、归档及受约束的删除操作。

## 删除规则

- 可以删除从未提交的在线草稿及其影像、未进入审核或入库的成果包，以及未参与业务的非当前账号。
- 项目、批次在无引用时可删除；基础资料需先停用且无任务和成果引用。
- 已下发任务使用“取消”，已有成果的项目和批次使用“归档/结束”；审核及正式成果历史不提供日常硬删除。
