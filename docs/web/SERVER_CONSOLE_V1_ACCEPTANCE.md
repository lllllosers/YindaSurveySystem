# Server Console V1 第一批交付与验收记录

日期：2026-11-07（Asia/Shanghai）。结论：**实际代码与可运行 Windows EXE 已交付，服务级现场验收尚未完成，不能标记为正式投产通过。**

## 本轮验收收口（基于 b40c83d）

本轮只完成第一批修正和验收准备，不进入第二批、不修改业务或 Desktop。原分支为 `feat/web-server-console-v1-foundation`，起点提交为 `b40c83de4d7b227da3a785ffa5251f741be0fd51`，原有 `.vscode/settings.json` 修改保留。

两项修正：

- 稳定 Windows Service ID 改为 `YindaWebCenterService`，显示名改为 `Yinda Web Center`，后续 Web 版本复用。部署专属命名事件/互斥量也使用稳定 Service ID 加配置路径摘要，不随应用版本变化。早期草案 `YindaWebCenterV1` 不会自动删除或迁移；如果测试机已安装草案服务，必须先核对归属，再由管理员使用原配置处理。
- 部署、安装、启动、重启和 GUI 向导共用一条旧任务提示：旧 `YindaWebCenter` 任务存在时（**包括已禁用**）拒绝部署/启动；先确认旧 Web 服务/进程停止，必要时导出任务配置，再由维护人员人工移除。任务查询失败时也不继续。程序没有新增自动删除历史任务的行为。

### 本轮已通过

| 项目 | 实际证据 |
|---|---|
| 当前机器与权限核对 | 2026-11-07 18:28:58 +08:00，Windows 11 10.0.26300 x64，`IsUserAnAdmin=0`；原始只读记录见 [环境证据](evidence/server-console-v1-closure-20261107.json) |
| SCM/任务只读核对 | `sc query YindaWebCenterService` 与 `sc query YindaWebCenterV1` 均返回 1060（服务未安装）；旧任务查询确认不存在。没有把权限错误当作不存在，没有安装或移除服务/任务 |
| 相关自动回归 | **48 passed**，`web/build/acceptance-closure-tests.log`；覆盖稳定 XML ID/显示名、部署专属事件、启用/禁用任务均阻断、查询拒绝访问不继续、四个操作入口同一提示且不复制程序/保存配置/控制服务/改任务，以及旧控制台回归 |
| 修正版 Windows EXE 构建 | 两个 PyInstaller onedir 程序构建及 EXE 启动/资源烟测成功，`web/build/acceptance-closure-build.log`；此烟测不连接数据库、不安装 SCM 服务 |
| 稳定 ID 的 WinSW XML 只读验证 | WinSW 实际读取隔离目录中生成的新 XML，`status` 退出 0、返回 `NonExistent`；`web/build/acceptance-closure-winsw.json`。仅证明配置可读和服务不存在，不代表安装或 LocalService 运行 |
| 包与文件核对 | 960 个归档文件，manifest 的 959 个文件哈希逐一匹配；人工步骤及模板与源码文档逐字节一致；无实际运行配置、数据库或成果目录，`web/build/acceptance-closure-artifact.json` |

本轮修正版：`web/release/server-console-v1/20261107-182757-589552/YindaWeb/`，同目录 `yinda-server-console-v1-windows-x64.zip` 为 **85,877,907 字节**，SHA256 为 `59ac04d2faceb40b85a1691a9ed3e159dd6a3e224aab47fd3965360075e72d77`。下方旧时间戳产物属于首轮，不应代替本轮修正版。完整解压后运行 `console/YindaServerConsole.exe`；人工验收步骤和未填写模板已随新包提供。

### 本轮失败

当前已执行的相关自动测试无失败。管理员权限不足属于下面的**未执行阻塞**，不能记录为服务安装成功或用模拟测试代替实际验收。

### 本轮未执行

| 项目 | 原因 / 后续证据要求 |
|---|---|
| WinSW 安装、LocalService 实际运行和文件权限 | 当前令牌非管理员；需管理员安装后采集 SCM 配置、wrapper/后端实际 GetOwner、存储上传下载和 ACL |
| 控制台退出后真实 SCM 服务继续运行 | 新服务尚未安装；历史独立 Web 进程测试不算本项 |
| Windows 注销后服务继续运行 | 未注销当前电脑；需前后 PID/创建时间、SCM 和注销期间外部新请求证据 |
| 重启电脑后的 PG/Web 自动启动 | 未重启当前电脑；需无需打开控制台或人工启动的启动时间、服务状态、进程和请求证据 |
| 真实服务停止、启动、重启 | 新服务尚未安装；需 SCM 状态变化、进程退出/新建和 Uvicorn 优雅退出日志 |
| 上述生命周期后的测试业务数据与成果文件保留 | 本轮未连接数据库；需同一项目/成果 UID、业务引用和下载文件大小/SHA256 一致 |
| 办公室另一台电脑 LAN 访问 | 无其他办公室电脑可操作，明确列为人工待验；本机访问内网 IP 不替代此项 |

没有尝试提权绕过、服务安装、注销、重启、防火墙修改、连接或改写正式/测试数据库。人工步骤见 [Windows Service 验收步骤](SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE.md)，记录使用 [未填写验收模板](SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE_RECORD.md)；包含隔离 PG 测试边界、旧草案服务/旧任务处理、真实 LocalService 账户、生命周期、业务成果及故障取证要求。

**第二批条件：目前不满足。** 核心阻塞是尚无管理员完成真实服务安装、账户与生命周期验收。应先执行模板中的服务级项目并保留证据，修复直接相关缺陷；LAN 无法实测时保持人工待验，不宣称第一批现场验收全部通过。

## 首轮历史记录的基线与边界

以下保留首轮 b40c83d 的既有测试与产物记录。本轮没有重新执行其中的数据库/业务回归或独立冻结进程验收；这些历史结果不能证明稳定 Service ID 的 SCM 现场验收通过。

- 开始时本地 HEAD、fetch 后 origin/main 均为 `afb50c56a9f9b250443c211f9d6f800f2e25694b`，没有新增主线变更。
- 开发分支 `feat/web-server-console-v1-foundation`。原有 `.vscode/settings.json` 修改保留、不提交。
- 不修改 Desktop 稳定版、历史 tag 或正式发布资产，不合并 main。
- 所有数据库实测仅连接本轮新建的 `.test-runtime/server-console-v1-pg` 集群（PostgreSQL 17.11，127.0.0.1:56437）内专用 `yinda_console_*` 测试库。没有访问或修改现有业务数据库与真实运行实例。

## 实际实现

1. `Settings.file_base/storage_dir/backups_dir/frontend_dist` 统一后端资源与持久化路径。成果包、任务包、桌面交接包、在线影像、上传空间检查和备份 CLI 共用这一配置。数据库中的 `storage/...` 引用保持兼容。修复原同源 SPA 路径层级错误。正式模式禁用旧清空工具。
2. 独立 `deployment` 核心处理配置原子保存、无密码定位文件、数据库身份绑定、初始化阶段、专用空库检查、Alembic head 检查、同库部署互斥和安全接续。不会创建数据库；无法连接时不会建立替代空库。已有标识但 storage 目录丢失时拒绝继续，避免创建空目录替代已有成果。
3. 使用现有 Alembic 迁移、正式主数据种子、密码哈希和首位管理员创建。迁移环境增加显式传入连接支持，以便初始化在同一数据库连接和 advisory lock 下执行。接续保留管理员和业务数据。
4. 正式 Windows Service 管理：归属按 SCM 注册的精确 wrapper 路径判断；安装、启动、停止、重启、查询；自动启动、LocalService、目录权限设置、有限恢复策略、旧计划任务阻断。首轮曾使用草案 ID `YindaWebCenterV1`，本轮已修正为稳定的 `YindaWebCenterService`。独立 Server EXE 通过部署专属命名互斥量防重复，命名事件通知 Uvicorn 优雅停止，不按端口或任意 PID 杀进程。
5. 中文 PySide6 控制台，概览、运行管理、网络访问、日志与诊断、设置与关于，四步部署向导。数据备份、系统升级入口禁用；复杂操作放入线程。真实活动网卡 IPv4 通过 Windows API 读取，无 PowerShell、Python 或 Node 运行依赖。
6. 明确的生产内网 HTTP 配置，不切换为 development；保留会话、Argon2、CSRF、业务权限、精确 Host、生产安全头，关闭 API 文档和开发 CORS。界面记录 HTTP 不加密边界。
7. 双 PyInstaller onedir 程序 + WinSW + 编译后 Vue 页面、Shared、Alembic 和正式模板。构建只写自己新建的时间戳目录，不删除既有产物或业务文件。

旧 `launcher.py/server_console_core.py/server_worker.py/portable_runtime.py` 和旧便携构建仍保留，供历史验收复现，不作为正式路线依赖，也未新增便携功能。服务逻辑与新 GUI 分离，未调整任何业务流程或权限规则。

## 产物与运行目录

最终目录：`web/release/server-console-v1/20261107-180912-755842/YindaWeb/`。

- 控制台：`console/YindaServerConsole.exe`，需要同目录 `_internal`。
- 服务程序：`service/YindaWebServer/YindaWebServer.exe`，需要其 `_internal`。
- WinSW：`service/YindaWebService.exe`，生成的同名 XML 指向独立服务程序。
- ZIP：同时间戳目录下 `yinda-server-console-v1-windows-x64.zip`，85,867,166 字节。
- ZIP SHA256：`a3e6c717f2e7fa29b7d3ea1a3c16f11b7f4623cb44a9b255f4b3bf1f4a9219ef`。
- ZIP 共 958 个文件；manifest 登记 957 个文件（不含自身）。已检查无实际 runtime.env、storage、数据库、业务成果、测试目录、node_modules、.venv 或生产密码。

运行时使用 `config/deployment.json` 定位持久化目录中的 `config/runtime.env`；`data/storage`、`backups`、`logs`、`packages` 与程序目录分离。PostgreSQL 数据由独立安装管理。完整目录、操作步骤和构建命令见 [SERVER_CONSOLE_V1.md](SERVER_CONSOLE_V1.md)。

构建环境：Windows 11 x64（10.0.26300）、独立 CPython 3.12.14、PyInstaller 6.22.2、PySide6 6.11.2、PostgreSQL 17.11。依赖快照留在 ignored 的 `web/build/formal-v1-dependencies.txt`。WinSW 官方 v2.12.0 x64 构建输入已校验固定 SHA256，MIT 许可证随交付包提供。

## 通过

| 验证 | 结果与证据 |
|---|---|
| Web 后端完整回归 | 99 passed、1 skipped；`web/build/formal-regression-final.log` |
| 显式隔离数据库集成 | 1 passed；执行首次迁移、拒绝重复初始化、接续保留管理员哈希、业务表与成果文件。默认全套中跳过的正是这个需显式授权隔离库的用例，已单独执行通过 |
| Shared 回归 | 56 passed；`web/build/shared-regression.log` |
| Vue 前端测试 | 28 passed |
| Vue 正式构建 | 成功；保留现有大 chunk 提示，无构建错误 |
| 两个 Windows EXE | PyInstaller 构建成功、二进制资源烟测成功；`web/build/formal-v1-build-final.log` |
| 无开发工具 PATH | 将子进程 PATH 限制为 Windows/System32 并移除 PYTHONPATH、PYTHONHOME、Qt 插件环境后，两个最终 EXE 烟测均退出 0 |
| 实际窗口 | 使用 computer-use 打开 EXE、检查中文概览、打开并取消首次部署向导，再关闭控制台。不是截图模型或 UI mock |
| WinSW 本体 | Windows 实际运行 `status` 返回 `NonExistent`，退出码 0；说明固定版本本体能运行并读取生成的 XML |
| 非管理员处理 | 实际查询服务不存在；安装操作被明确的管理员权限检查阻止，没有生成半安装服务 |
| 文件与归属保护 | 自动测试覆盖配置往返、路径迁移兼容、明确生产 LAN HTTP、旧任务阻断、外来服务拒绝控制、真实端口占用不误杀、已有部署拒绝初始化 |

冻结二进制独立验收脚本 `web/verify_formal_runtime.py` 在专用测试库执行，9 项全部通过，记录于 `.test-runtime/frozen-acceptance-final/acceptance.json` 与 `web/build/frozen-acceptance-final.log`：

1. 冻结程序首次连接 PostgreSQL 17，执行全量 Alembic 迁移、创建管理员。
2. 冻结程序部署预检通过。
3. 冻结 Web Server 启动，本机 HTTP 和数据库健康检查成功。
4. 启动并退出独立 Console EXE 后，Web **进程**继续响应。
5. Vue 页面可读取；生产文档 404；匿名接口 401；HTTP Cookie 可登录且保留 HttpOnly；无 CSRF 的写入 403；有效 CSRF 创建项目成功。
6. 再次启动同一部署被拒绝，原实例继续响应。
7. Windows 命名事件触发真实 Uvicorn 优雅停止，退出码 0。
8. 冻结程序重启后管理员可登录，已创建项目及 storage 探针文件保留。
9. 对已有部署再次选择“新初始化”被拒绝。

这里第 4 项验证的是独立程序生命周期，**不等同于 Windows SCM 服务退出控制台验收**；后者仍需管理员实机验证。

## 失败后已修复

- 第一次 pytest 使用受限的系统临时目录，出现权限错误；改用本仓库专属 basetemp 后通过。最终完整回归仍有 pytest 缓存目录权限提示，不影响 99 项断言。
- 冻结后首次真实初始化发现 `app.db.base` 未收集。原因是 PyInstaller 早期动态模块收集时未继承 backend 搜索路径；已提供明确 PYTHONPATH、补齐 Alembic 模块收集，并将 app.db.base 导入加入二进制烟测。最终真实初始化成功。
- Windows 控制台编码与 UTF-8 不同，已对 Server CLI 固定 UTF-8，系统工具使用 Windows 编码；错误信息不输出密码或完整数据库异常。
- 验收脚本一度将项目列表当作分页对象读取；按已有业务接口修正，仅改验收脚本，最终重启数据保留断言通过。

最终无未解决的自动测试失败。构建日志中被显式排除的 Alembic testing 子模块与平台可选依赖提示不代表运行依赖缺失；实际二进制运行验收通过。

## 未执行 / 未验证

当前执行令牌 `IsUserAnAdmin=0`；工具的 sandbox escalation 不会赋予 Windows 管理员令牌。本轮没有触发 UAC、安装系统服务或修改系统防火墙。因此下列不能报告为已验收：

- SCM 安装、LocalService 实际运行、目录 ACL 与服务启动/停止/重启的完整实测。
- 关闭控制台后**已安装 Windows Service**继续运行。
- Windows 注销后、重启电脑后服务持续运行或开机自启。
- 办公室真实其他电脑访问、二级分发网络隔离、防火墙规则和路由器环境。
- 完全未安装 Python/Node/Git 的另一台干净 Windows 11 机器运行。当前交付程序包含自身运行依赖，但这不替代干净目标机验收。
- 从旧便携或源码部署迁移真实历史数据；本轮明确不接管真实库，旧存储需离线完整迁移并登记，不能自动猜测。

## 第二批前的处理事项

1. 首先在授权的 Windows 11 测试机以管理员身份安装服务，实测 LocalService 文件权限、自动恢复、退出控制台、注销和重启。完成后才能判断正式后台服务路线全程通过。
2. 在办公室另一台电脑验证真实访问，手工按网络范围设置所需 Web 防火墙入站规则；不要开放 PostgreSQL 端口。
3. 旧版同名计划任务即使禁用也会被 V1 的保守检测阻止。维护人员应先确认旧 Web 服务/进程停止，必要时导出任务配置，再人工移除任务。代码、GUI 和文档本轮已统一，不再提示仅禁用任务。
4. 备份恢复、版本升级、管理员维护界面尚未实现；正式历史数据迁入前需要制定并演练完整备份及回退步骤。V1 的 releases/packages/backups 和部署状态是扩展入口。

开发分支提交与推送结果以本次最终回复和 Git 记录为准。无正式 tag、无 main 合并、无正式发布资产覆盖。
