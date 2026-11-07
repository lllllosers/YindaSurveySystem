# Server Console V1 · 正式部署基础

本路线独立于旧便携包。Windows x64 交付包包含两个 PyInstaller onedir 程序、Vue 正式页面、后端、Shared、Alembic、正式 Excel 模板和 WinSW。甲方运行不需要 Python、Git、Node。PostgreSQL 17 由独立 Windows 服务运行。

## 首次安装

1. 解压完整 `YindaWeb` 到固定程序目录。不要只复制 EXE。
2. 安装 PostgreSQL 17，使用其图形管理工具建立专用空数据库和具备该数据库 schema 建表权限的账号。向导不创建数据库、不连接其他数据库、不探测其他业务库。PostgreSQL 未安装时，向导提供官方下载入口。
3. 右键 `console/YindaServerConsole.exe`，以管理员身份运行。选择“首次部署 / 修复配置”，配置程序位置和持久化目录（默认 `YindaWeb/persistent`）。
4. 填写专用数据库连接、监听地址、Web 端口、允许的主机和管理员账号。新部署只接受空数据库和空成果目录。确认后执行正式 Alembic 迁移及现有管理员创建能力，安装服务并验证本机 HTTP。
5. 在“网络访问”复制候选内网地址，在办公室其他电脑实际访问。需要时由管理员在 Windows 防火墙中只允许办公室网络范围访问所选 Web TCP 端口。控制台不改防火墙、路由器，不开放数据库端口。

默认是明确选择的 `APP_ENV=production` + `TRANSPORT_MODE=lan_http`，Cookie 的 Secure=false；认证、Argon2 密码、会话、CSRF、业务权限、精确 TrustedHost、生产安全头继续有效。生产 API 文档关闭，无开发 CORS。内网 HTTP 传输不加密，只适合受信办公室网络，不能向公网映射。HTTPS 生产配置仍要求 Secure Cookie，第一批不包含证书、反向代理或 HTTPS 安装管理。

## 目录与升级边界

```text
YindaWeb/
  console/YindaServerConsole.exe + _internal/
  service/YindaWebService.exe + .xml       # WinSW wrapper + generated XML
  service/YindaWebServer/YindaWebServer.exe + _internal/
  releases/                              # 下一批版本管理接口
  config/deployment.json                 # 无密码的配置文件定位
  persistent/                            # 可另选独立绝对目录
    config/runtime.env                   # 唯一正式运行配置，含数据库密码
    config/deployment-state.json          # 数据库身份、数据目录、初始化阶段
    data/storage/                        # 成果包、任务包、在线照片和视频
    backups/
    logs/
    packages/
```

数据库数据目录由已安装 PostgreSQL 独立管理，不包含在发布目录。程序替换仅允许触及 console、service、releases；不得删除 config、persistent 或外部持久化目录。V1 向导仅复制缺失的相同版本程序，拒绝覆盖不同版本文件，不实现版本升级。

所有数据库文件引用继续保存 `storage/...`，只由统一的 Settings.file_base 解析到 `persistent/data`；源码开发未配置 DATA_ROOT 时保持 `backend/storage` 的旧行为。备份 CLI 也使用统一配置。旧清空 CLI 在正式持久化模式下禁用。源代码旧便携入口和历史验收记录保留，不再作为新路线的依赖。

已有旧源码或便携部署不能直接接管。维护人员须先停旧 Web/计划任务，离线备份并搬迁**完整 storage**，核对数据库 Alembic 版本及成果引用，然后登记部署标识。V1 向导不会猜测路径、自动复制部分业务文件或为失败连接创建空库。已由 V1 登记的部署可选“安全接续”，重复运行迁移和管理员检查，不重置数据或管理员。失败时保留 initializing 阶段；修正同一数据库连接后可接续重试。数据库身份和数据目录不能在同一安装上改绑。

## 服务机制

服务 ID 为 `YindaWebCenterV1`。WinSW v2.12.0 x64 使用 MIT 许可，官方来源和 SHA256 固定在构建脚本，许可证随包分发。Windows 11 自带 .NET Framework 4.x，WinSW v2 x64 的 .NET Framework 运行要求在正式目标机仍须实测。

服务开机延迟自动启动，以 `NT AUTHORITY\LocalService` 运行，不依赖登录或控制台。持久化目录仅授予管理员、SYSTEM 和 LocalService；程序目录对 LocalService 只读执行。安装需要管理员权限；启动、停止等 SCM 操作通常也需要管理员权限，普通控制台不会自行提升整个服务。

每次服务启动先检查 PostgreSQL 17、配置、部署标识、迁移 head、正式页面和监听端口。命名互斥量防重复实例，独占端口检测防误用端口；服务归属按 SCM 注册的精确 wrapper 路径判断，不按端口杀进程。停止由 WinSW 启动同账户 helper 发送部署专属 Windows 命名事件，Uvicorn 最多 30 秒优雅退出；WinSW 最多等待 45 秒后收回其子进程。异常最多连续自动重启三次，之后停止，连续正常一小时后重置计数。

发现旧 `YindaWebCenter` 任务即阻止部署和启动。维护人员需先停止旧实例并删除/导出保留该任务；即使任务禁用也应导出后删除，V1 保守地阻止任何同名任务。程序不会自动停止旧程序或其他端口占用者。

控制台所有耗时操作在工作线程执行；退出不发送停服命令。控制台只把本机 HTTP、数据库健康检查成功报告为已验证；局域网候选地址始终标记需要其他电脑实测。下一批可基于 deployment-state、releases、packages、backups 扩展升级、备份恢复和管理员维护。

## 开发机构建

在独立 Windows x64 Python 3.12 虚拟环境安装 `web/console-requirements.txt` 和 `web/backend/requirements-dev.txt`。先在 web/frontend 执行 `npm ci`、`npm run build`。从官方发布下载 `https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe`，旁边保存同版本的 LICENSE.txt。

```powershell
web/build/console-native-venv/Scripts/python.exe web/build_formal_windows.py --winsw web/build/winsw-2.12.0/WinSW-x64.exe
```

产物为 `web/release/server-console-v1/<时间戳>/YindaWeb/` 和同目录 ZIP。每次使用全新输出目录，不删除已有构建、不清理业务目录。构建后运行两个 EXE 的资源/启动烟测，再打 ZIP；包内只有显式程序资源，无 .env、PostgreSQL 数据、业务成果、生产密码或源码环境。build-manifest.json 记录文件哈希；完整依赖环境可用 `pip freeze` 留档。

实际验收结果另见 SERVER_CONSOLE_V1_ACCEPTANCE.md。注销、真实其他电脑访问等未执行检查不能以单元测试替代。
