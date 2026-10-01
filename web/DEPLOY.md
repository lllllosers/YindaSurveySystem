# Web 中心部署与数据初始化

部署包由 `web_center/build_deploy_bundle.py` 生成，包含 Web 后端、编译后的页面、共享协议、正式主数据契约、在线表单规则、正式原表 Excel 模板和服务控制台。桌面调查 GUI、完整桌面源码、测试、`.venv`、`node_modules`、本地账号、上传文件和数据库备份均不进入部署包。

正式成果库的“导出查询结果”下载 CSV 汇总；每条记录的“导出原表”下载使用正式模板的 Excel 附表 2.1～2.14。两端共享 `EngineeringFormDefinition`、`OriginalFormExportDefinition` 和原表渲染函数；Web 从中央 PostgreSQL 正式记录及中央主数据快照取值，不读取桌面 SQLite。

## Windows 验收便携包

在开发机具备 Python 3.12 嵌入式运行时 ZIP、项目后端虚拟环境、PostgreSQL 17 Windows 二进制文件和最新服务控制台 EXE 时，可运行 `web_center/build_portable_windows.py` 生成 `web_center/release/yinda-web-windows-portable.zip`。便携包包含上述 Web 代码和本机运行环境，不包含账号及业务数据。将其完整解压到验收电脑的固定目录（例如 `C:\YindaWeb`），双击 `web_center\YindaWebServerConsole.exe`；首次在控制台点击“初始化便携环境”创建本机数据库和管理员，再点击“启动 Web 服务”。停止与备份也在控制台操作。包内《便携包部署教程.md》给出完整步骤，便携包不再使用启动批处理。

该便携包先在 `http://127.0.0.1:8000/` 提供本机访问。对外验收网址需要另行配置 HTTPS 公网入口；不要直接将数据库端口或 HTTP 端口暴露到公网。正式开放外网前，按下面“公网验收部署”配置 `.env`，由控制台运行生产预检并重启服务。便携包内 `data/`、`web_center/backend/.env`、`web_center/backend/storage/` 是需要一起备份和保留的本机状态。

## 公网验收部署

本阶段仅放测试数据，不放正式调查成果。旧 Windows 电脑上的 FastAPI 只监听 `127.0.0.1:8000`，PostgreSQL 只允许本机访问；Windows Firewall 不允许公网访问数据库 `5432`（便携包为 `55432`），也不开放原始 HTTP `8000`。对甲方只提供第三方隧道或反向代理产生的一个 HTTPS Web 地址。该入口仅用于验收，未来正式投产由甲方网络信息中心重新部署。

获得隧道提供的 HTTPS Host 后，在服务器自己的 `web_center/backend/.env` 填入真实值。下面是示例，尖括号内容必须替换，且不要把 `.env` 提交到 Git。便携包使用本机独立数据库端口 `55432`，普通 PostgreSQL 安装通常使用 `5432`；按实际部署填写。

```dotenv
APP_NAME=Yinda Survey Web Center API
APP_ENV=production
SESSION_COOKIE_SECURE=true
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=yinda_web_center
DB_USER=yinda_app
DB_PASSWORD=<strong-password>
ALLOWED_HOSTS=127.0.0.1,localhost,<public-host>
REGISTRATION_MODE=invite_only
ENABLE_HSTS=false
MAX_RESULT_UPLOAD_BYTES=2147483648
MAX_MEDIA_UPLOAD_BYTES=1073741824
MAX_TASK_UPLOAD_BYTES=536870912
MAX_DESKTOP_DATABASE_UPLOAD_BYTES=2147483648
MAX_API_REQUEST_BYTES=8388608
MAX_ZIP_FILE_COUNT=10000
MAX_ZIP_SINGLE_FILE_BYTES=2147483648
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES=8589934592
MAX_ZIP_JSON_BYTES=268435456
MIN_FREE_DISK_BYTES=5368709120
PUBLIC_BASE_URL=https://example.com
POSTGRES_SERVICE_NAME=postgresql-x64-17
```

`ALLOWED_HOSTS` 只填主机名，不填 `https://`、路径或端口，不使用 `*`。公网 Host 改变时只需修改 `.env` 并重启 Web 服务。生产启动会拒绝不安全 Cookie、示例数据库密码和空白/通配 Host。生产 API 文档关闭，开发环境仍有 `/docs`。前端与 API 同源，生产不开放开发 CORS。Element Plus 页面使用动态行内样式，因此生产 CSP 对样式保留 `'unsafe-inline'`；脚本仍限制为同源。HSTS 默认关闭，只有确认长期使用稳定 HTTPS Host 时再设 `ENABLE_HSTS=true`。

`PUBLIC_BASE_URL` 和 `POSTGRES_SERVICE_NAME` 是控制台可选配置。前者只填写 HTTPS 站点根地址，控制台检查其 `/api/v1/health`；未配置时显示“未配置公网访问地址”。后者填写 Windows PostgreSQL 服务名，仅用于状态显示；留空时显示“未指定”。控制台不存放数据库密码或隧道 Token。PostgreSQL 仍由 Windows Service 管理，不得暴露 5432（或便携包 55432）到公网。

ASGI 入口在 multipart 解析前限制请求体：有 `Content-Length` 时立即检查，没有时按接收流累计检查；普通 API、成果包、在线影像和两类桌面任务导入分别使用相应上限。上传前还会检查 storage 与系统临时目录所在磁盘的保留空间，业务落盘时再检查一次。若测试成果确需更大上限，先确认验收电脑内存和磁盘，再仅调整 `.env` 中相应数值。

公网验收建议 `REGISTRATION_MODE=invite_only`：管理员先创建邀请口令，受邀人才能注册。`closed` 完全关闭注册；若甲方要验收普通申请注册，可临时设为 `open`，演示后恢复。保留原有注册审核和邀请码功能。管理员及验收账号实际密码建议至少 12 位并具有足够随机性，当前业务最低密码规则不变。

启动前执行（便携包在 `web_center/backend` 目录使用 `..\..\runtime\python\python.exe` 代替 `.venv\Scripts\python.exe`）：

```powershell
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.cli.production_check
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

预检输出 `PASS / WARNING / BLOCKER`；有 `BLOCKER` 时退出码非零，先修复后再对外开放。不要使用 `--forwarded-allow-ips="*"`。默认禁用 proxy headers，审计 IP 因而记录本机代理地址；如果以后需要真实客户端 IP，必须确认 HTTPS 入口会删除客户端自带的转发头并重新写入，再只信任明确的本机代理。不要把密码、Session/CSRF token、完整邀请口令或请求体写入日志。正常打开站点后，可用 `/api/v1/health` 检查存活；数据库健康检查只返回最小状态。

## 1. 在开发机生成部署包

在仓库根目录运行：

控制台建议使用独立的 Windows x64 Python 3.12 虚拟环境构建，避免 Conda 等环境中的 Qt DLL 冲突。

```powershell
cd web_center/frontend
npm ci
npm run build
cd ..
python -m venv build/console-venv
build/console-venv/Scripts/python.exe -m pip install -r console-requirements.txt
build/console-venv/Scripts/python.exe build_server_console.py
python build_deploy_bundle.py
```

生成的 `YindaWebServerConsole.exe` 和 ZIP 位于 `web_center/release/`。先构建 EXE 再打 ZIP，部署包会包含 EXE；没有 EXE 时仅包含控制台源码，服务器不能直接双击运行。控制台构建依赖不进入 Web 后端 requirements。桌面端继续使用现有 `.ydtask V3 / .ydresult 2.2`，不要单独修改部署包里的 `shared/` 或表单规则。

开发机可直接双击 `web_center/release/YindaWebServerConsole.exe`。控制台会识别仓库中的 `web_center` 目录；如需在开发机启动 Web 服务，还需按下文准备 `web_center/backend/.venv`、`.env` 和 `web_center/frontend/dist`。构建脚本会在生成 EXE 后实际启动一次控制台进行自检；如果 Qt 无法加载，构建会失败。

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
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

同一个后端服务提供 `/api/v1` 与编译后的网页。让 HTTPS 反向代理将网站根路径转发到 `127.0.0.1:8000`，并保持请求路径与 Cookie；外部访问只开放 HTTPS 入口。`/api/v1/health` 和 `/api/v1/health/database` 可用于检查服务与数据库。以上命令可用于首次确认；长期运行请双击 `web_center/YindaWebServerConsole.exe`，点击“生产环境预检”与“启动 Web 服务”。生产预检有 BLOCKER 时，启动被阻止，需先修复原因。后端始终只绑定 `127.0.0.1:8000`，不运行 Vite 8848。

控制台使用隐藏的独立 `pythonw.exe` 进程运行 Web；`web_center/.runtime/` 保存 PID、单实例锁和分开的 server、operations、preflight、backup 日志。GUI 通过 PID、可执行文件路径与进程创建时间核验身份，不会停止其他程序占用的 8000 端口。关闭窗口会收起到托盘；“退出控制台”仅退出 GUI，Web 持续运行。“停止 Web 服务”才停服。控制台可查看最近 100 行日志，点击“立即备份”会调用现有 `app.cli.backup_web_center`。

以管理员身份运行控制台并点击“设置开机自启”，会注册 Windows 任务计划程序 `YindaWebCenter`，以本机 SYSTEM 账户在开机时运行同一个隐藏服务入口。请确认该账户有部署目录、`.env`、storage 和 backups 的必要权限，并在任务计划程序中核对任务状态。PostgreSQL Windows Service 应设为自动启动；服务入口会短暂等待本机数据库端口，再执行生产预检。移动部署目录后须重新设置开机自启。当前实现不依赖 NSSM 等第三方服务程序。

## 3. 升级与恢复

升级前停止写入，备份数据库和 `backend/storage/`：

```powershell
.venv\Scripts\python.exe -m app.cli.backup_web_center
```

已有 `D:\YindaWeb` 测试部署可按此顺序升级：先在旧服务窗口停服并确认 `127.0.0.1:8000` 已释放；在旧版 `D:\YindaWeb\web_center\backend` 执行上述完整备份，并复制备份到独立磁盘；再将新的 `yinda-web-center.zip` 解压覆盖到 `D:\YindaWeb`。ZIP 不含 `.env`、storage、backups 或数据库，不要删除这些本机目录。随后执行：

```powershell
cd D:\YindaWeb\web_center\backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\alembic.exe upgrade head
```

最后双击 `D:\YindaWeb\web_center\YindaWebServerConsole.exe`，运行生产预检并启动 Web；需要开机自启时，以管理员身份点击相应按钮。检查本机及公网 `/api/v1/health`、正式成果库的 Excel 导出。若 8000 仍由旧服务占用，控制台会拒绝接管，请先人工核实旧进程。

若该目录来自便携包且没有后端 `.venv`，应在开发机构建包含新依赖的完整便携包，再按包内《便携包部署教程.md》升级；确认 `runtime/python/Lib/site-packages` 已包含 `openpyxl`。服务控制台会从便携运行时解析 `pythonw.exe`，并在“初始化便携环境”时升级数据库结构。

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
