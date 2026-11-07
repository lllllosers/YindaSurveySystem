# 引大调查数据采集系统 · Web Center Windows 部署

正式交付为完整 Web Center，包含业务后端、Vue 正式页面、Shared 协议和资料、Alembic、14 类正式 Excel 模板、Windows 服务及统一控制台。正常使用无需 Python、Node、Git 或 pgAdmin。PostgreSQL 17 仍需独立安装。

## 第一次使用

1. 解压完整 `YindaWebCenter-Windows-x64.zip`，将 `YindaWebCenter` 文件夹放在固定位置。不要只复制主 EXE。
2. 从 [PostgreSQL 官方 Windows 安装入口](https://www.postgresql.org/download/windows/) 安装 **17 x64**。记住安装时设置的管理密码；无需用 pgAdmin 手动建库。
3. 双击根目录带引大调查图标的 `引大调查Web中心.exe`。首次安装后台服务时，退出后右键同一 EXE，选择“以管理员身份运行”。后续服务维护也需要相应 Windows 权限。
4. 点击“首次安装 / 运行配置”。确认“程序安装目录”和“数据存储目录”，默认数据文件夹为 `data`。
5. 数据库页会检测 PostgreSQL 17 和系统服务。默认选择“创建本系统专用数据库”，只需临时填写 PostgreSQL 安装时的管理密码。默认专用库 `yinda_web_center`、普通运行账号 `yinda_web_user`，运行密码为每次新安装独立生成的强随机密码，无需记住。
6. 选择访问方式：仅本机或默认的局域网。通常不需要展开高级设置。公网选项须配置 HTTPS 后才能启用，本向导不直接开放公网 HTTP。
7. 创建系统管理员账号，默认用户名 `admin`，自行设置并确认 8 至 128 位密码。这个账号用于网页登录，与 PostgreSQL 账号不同，没有固定默认密码。
8. 点击“完成配置并启动”，查看七步安装进度。不要关闭正在部署的程序。成功后显示“Web Center 已成功启动”、访问地址及“打开 Web Center”按钮；失败则显示具体阶段、处理建议和安装日志位置。
9. 返回同一个控制台管理启停、重启、环境检查、备份、自启及日志。退出控制台不会发送停服命令。

高级设置用于维护人员核对特殊端口、名称、已有空库、接续及网络地址，复用同一套安装流程。更改网络后仍需办公室其他电脑实际访问；本机检查通过不会显示为其他电脑已可达。

## 数据保护和失败重试

自动创建只支持本机 PostgreSQL，先检查同名数据库与账号，已有任一对象就停止，不覆盖内容或修改密码。管理密码只通过子进程标准输入临时使用，不进入配置、日志或命令行。运行密码保存到受 ACL 保护的 `data/config/runtime.env`。

创建失败保留对象与创建阶段；本次创建成功的资源只在部署身份和 OID 匹配时允许继续。不要删除数据库、账号或数据来重试，不会静默改用另一个空库。已登记部署可选择“接续本系统已有安装 / 修复配置”；已有管理员不会被重置。失败后保留安装日志及阶段，由维护人员核对后重试。

```text
YindaWebCenter/
  引大调查Web中心.exe                 # 唯一正式 GUI，直接运行
  _internal/                         # 主程序依赖、官方 Logo
  service/YindaWebService.exe         # WinSW
  service/YindaWebServer/             # 独立后端及业务资源
  config/deployment.json             # 无密码的配置定位文件
  data/                              # 新安装默认位置，可另选绝对路径
    storage/                         # 界面称“成果文件”
    backups/
    logs/install.log                 # 安装阶段及错误
    config/runtime.env               # 含运行密码，不得公开
    config/install-status.json
    config/deployment-state.json
    packages/
```

PostgreSQL 自己管理其数据库物理目录，不在程序更新范围内。内部 `storage/...` 数据库引用不变，由统一 `Settings.file_base` 解析。**新安装**记录 `DATA_LAYOUT=flat`，映射到 `data/storage`；**原 V1 配置没有 DATA_LAYOUT 时**按 `legacy` 解析到原 `persistent/data/storage`。不改名、不搬迁、不删除旧成果。布局与部署标识不一致会拒绝接续。

本向导只复制相同版本缺少的程序文件，拒绝覆盖目标的不同版本；不实现在线升级。程序替换只处理 EXE、`_internal`、`service` 等不可变资源，不覆盖根 `config`、数据存储目录或外部数据。旧源码/便携真实数据迁移仍需维护人员先制定离线备份方案，不在本轮范围。

## Windows 后台服务

稳定服务 ID `YindaWebCenterService`、显示名 `Yinda Web Center`，长期复用且不随应用版本变化。WinSW v2.12.0 x64（MIT）以 `NT AUTHORITY\LocalService` 延迟自动启动，程序目录只读执行，数据目录允许必要读写。停止使用部署专属 Windows 命名事件，优雅退出 Uvicorn。控制台按 SCM 注册路径核对归属，不按端口杀其他程序。

旧 `YindaWebCenter` 计划任务存在时，**包括已禁用任务**，新部署及启动都会拒绝。先确认旧 Web 服务/进程已停止，必要时导出旧任务 XML，再由维护人员核对并人工移除任务注册项。仅禁用不够。本程序不会自动删除历史任务。若存在早期 `YindaWebCenterV1` 草案服务，由管理员用原配置和原 wrapper 核对后处理，不能用新 XML 操作旧项。

默认生产内网 HTTP 保留会话、Argon2、CSRF、权限、精确 Host、安全头；生产 API 文档关闭，没有开发 CORS。内网 HTTP 不加密，不得映射到公网。控制台保留已有合法 HTTPS 地址检查，不提供证书或反向代理管理。控制台不更改路由器或防火墙，也不开放数据库端口。

立即备份会先停止本安装 Web 写入，转储数据库并复制完整成果文件，再恢复原运行状态。只有 dump、成果及完成标识齐全才显示完整备份；原服务停止则保持停止。旧备份无完成标识时显示待核对。恢复界面、定时备份及在线升级尚未开发。

## 开发机构建

在 Windows x64 Python 3.12 独立环境安装 `web/console-requirements.txt` 与 `web/backend/requirements-dev.txt`。在 `web/frontend` 执行 `npm ci`、`npm run build`。使用官方 WinSW v2.12.0 x64 和同版本 `LICENSE.txt`；构建脚本核对固定 SHA256。官方原 Logo 保存于 `web/assets`，`prepare_branding.py` 只做符号裁切及多尺寸 ICO 转换，不重新绘制。

```powershell
web/build/console-native-venv/Scripts/python.exe web/prepare_branding.py
web/build/console-native-venv/Scripts/python.exe web/build_formal_windows.py --winsw web/build/winsw-2.12.0/WinSW-x64.exe
```

每次输出独立 `web/release/web-center-windows/<时间戳>/YindaWebCenter/` 和 `YindaWebCenter-Windows-x64.zip`，不覆盖历史包。唯一构建实现为 `build_formal_windows.py`，唯一 GUI 源码 `launcher.py`，运维门面 `server_console_core.py`；`server_setup.py` 是同一 GUI 内的向导，`server_entry.py` 是后台维护程序，没有第二套 GUI 或临时启动器。manifest 登记入口与文件哈希。

实际结果见 [验收记录](SERVER_CONSOLE_V1_ACCEPTANCE.md)。非开发电脑需要按 [人工步骤](SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE.md) 完成管理员服务、注销、重启和其他电脑 LAN 验收，并填写 [空白记录模板](SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE_RECORD.md)。自动测试或独立进程运行不代表真实 Windows Service 已通过。
