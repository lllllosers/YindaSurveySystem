# Windows Service 人工验收步骤

适用范围：Server Console V1 第一批收口。稳定服务 ID 为 `YindaWebCenterService`，显示名 `Yinda Web Center`。本文件是待执行步骤，不是验收已通过的证明。结果填写在随附的 `SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE_RECORD.md`。

## 1. 由测试环境管理员准备

1. 使用授权的 Windows 11 x64 测试电脑，安排可注销和重启的测试时段。不能在有甲方真实业务实例的电脑上照本流程初始化、删任务或重启。无管理员令牌时停止服务级验收，交给有权限的测试人员；不绕过 UAC 或 Windows 权限。
2. 取得本轮完整交付 ZIP，记录 SHA256，解压到新的固定目录，例如 `C:\YindaWeb-Acceptance`。不要覆盖 b40c83d 的旧包或在旧安装目录里改 XML。
3. 使用独立 PostgreSQL 17 **测试集群**及其 Windows 服务，确认其开机自动启动。本轮向导可选择自动创建专用数据库与账号，无需 pgAdmin。测试时把名称明确设为未使用过的 `yinda_console_service_acceptance_日期` 及对应专用账号，管理凭据只临时输入。也可选择维护人员已准备的专用空测试库。记录实际主机、端口、库名和集群目录；不连接正式实例，不复用正式账号、密码或数据库。临时 pg_ctl 进程不能代替开机自动启动的 PostgreSQL 测试服务。
4. 为程序、持久化目录、PostgreSQL 数据和取证文件分别确定测试路径，持久化目录例如 `C:\YindaWeb-Acceptance\persistent`。确认旧数据不在这些目录。服务验收期间不要清空任何目录或数据库。
5. 在“服务”检查稳定 ID、早期草案 ID `YindaWebCenterV1` 是否已注册。发现同名服务时先核对完整 EXE 路径、归属和配置；不是本次测试的服务就停止操作。若是自己的旧草案服务，先留存配置和 `sc qc` 结果，由管理员使用**原配置与原 wrapper**停服并卸载，确认旧项消失后再从新目录安装。不能用新 XML 操作旧注册项，不自动迁移或删服务。

## 2. 旧计划任务处理

在任务计划程序中查看根目录下的 `YindaWebCenter`。只要该任务存在，无论启用还是禁用，新部署或启动都会被阻止。

处理顺序为：确认旧 Web 服务/进程已停止 → 必要时右键“导出”保留旧任务 XML → 核对任务归属并由维护人员人工移除该任务注册项。删除任务注册项不等于删除旧程序或成果目录；不要删除这些文件。任务已经禁用也必须按此流程移除。程序只做查询，不会自动删除甲方历史任务。若查询提示权限错误，先解决管理员权限，不能将查询失败记录为“无任务”。

只读核对命令（管理员终端可选）：

```powershell
sc.exe query YindaWebCenterService
sc.exe query YindaWebCenterV1
schtasks.exe /Query /TN YindaWebCenter /XML
```

“服务/任务不存在”是这里允许的预检查结果；记录退出码和原始错误文字。不要把 Access denied 当作不存在。

## 3. 通过图形界面部署并确认真实账户

1. 右键唯一 GUI `console\YindaServerConsole.exe`，选择“以管理员身份运行”。在“安装与设置”打开首次安装向导，选择本次新目录、正确测试集群端口，推荐自动创建专用测试库和普通账号。不得选择任何旧业务库；保留创建结果和账号非超级用户的证据。
2. 监听默认可选 `0.0.0.0`，Web 端口使用未占用测试端口，例如 `58137`；允许的主机包括 `127.0.0.1`、`localhost` 和测试机实际办公室 IPv4。明确选择内网 HTTP；不对公网映射，不开放 PostgreSQL 端口。
3. 选择初始化空测试库，创建独立测试管理员，执行部署。记录每一步提示和完成时间。如果失败，保留阶段标识和日志，修正同一测试部署后接续重试，不清库或换一个空库掩盖失败。
4. 在 Windows“服务”确认 `Yinda Web Center` 为运行中、自动（延迟启动），登录账户配置为 `NT AUTHORITY\LocalService`。再用下列只读命令核对注册路径和运行进程的**实际拥有者**；仅看到配置中的 StartName 不能证明实际运行账户。

```powershell
$yindaService = Get-CimInstance Win32_Service -Filter "Name='YindaWebCenterService'"
$yindaService | Select-Object Name, State, StartMode, StartName, ProcessId, PathName
sc.exe qc YindaWebCenterService
sc.exe queryex YindaWebCenterService
sc.exe qfailure YindaWebCenterService
if (-not $yindaService -or $yindaService.State -ne 'Running' -or $yindaService.ProcessId -eq 0) {
    throw '测试服务未运行；先记录错误，不继续账户与生命周期验收。'
}
$yindaQueue = @([uint32]$yindaService.ProcessId)
$yindaSeen = @()
while ($yindaQueue.Count -gt 0) {
    $yindaProcessId = $yindaQueue[0]
    $yindaQueue = @($yindaQueue | Select-Object -Skip 1)
    if ($yindaProcessId -eq 0 -or $yindaProcessId -in $yindaSeen) { continue }
    $yindaSeen += $yindaProcessId
    $yindaProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$yindaProcessId"
    if ($yindaProcess) {
        $yindaOwner = Invoke-CimMethod -InputObject $yindaProcess -MethodName GetOwner
        [pscustomobject]@{
            PID = $yindaProcess.ProcessId; ParentPID = $yindaProcess.ParentProcessId
            Path = $yindaProcess.ExecutablePath; Created = $yindaProcess.CreationDate
            Owner = "$($yindaOwner.Domain)\$($yindaOwner.User)"; OwnerQueryCode = $yindaOwner.ReturnValue
        }
        $yindaQueue += @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$yindaProcessId" |
            Select-Object -ExpandProperty ProcessId)
    }
}
```

应看到 WinSW wrapper 和 `YindaWebServer.exe`（包括其同名子进程，如有）路径属于本次安装，实际拥有者均为 LocalService / LOCAL SERVICE，GetOwner 返回值为 0。若账户、路径不符或无法取证，标记失败或待验，不扩大权限让服务改用 LocalSystem。

5. 访问 `http://127.0.0.1:58137/` 和 `/api/v1/health/database`。使用测试管理员登录，创建命名唯一的测试项目，通过现有任务/成果或在线影像流程保存一份小型测试文件。记录项目 UID、文件 UID、**真实** storage 相对路径、大小及 SHA256。仅放一个孤立探针文件不足以验收业务成果文件引用。记录初始化后的 Alembic 版本和部署 phase=ready，取证不包含密码。
6. 成果上传成功且可下载，说明低权限服务实际可写存储；同时采集 `icacls` 对程序目录、持久化目录和该成果文件的只读结果。不能仅因 ACL 命令成功就认定业务存储正常。

## 4. 生命周期与数据保留

| 操作 | 必须观察和记录的结果 |
|---|---|
| 退出控制台 | 使用窗口关闭按钮，确认 GUI 进程退出；不要使用“停止服务”。SCM 仍为 Running，本机新请求及数据库健康检查成功，项目、成果可查询下载。记录 wrapper/后端 PID 与创建时间 |
| 停止服务 | 重新以管理员身份打开控制台，点停止。SCM 到 Stopped，原 wrapper/后端退出；日志出现 Uvicorn shutdown 完成，端口不再由本服务监听。不能只凭某个端口不通推断停服成功 |
| 启动及重启 | 启动后登录并校验原项目 UID、成果引用和下载 SHA256。再点重启，记录新旧 PID/创建时间和退出日志；重新请求成功、测试数据和文件保持一致 |
| 立即备份 | 确认停服提示后开始，观察真实服务先停止、数据库与成果完整备份、完成后恢复原运行状态；记录 manifest、dump、成果副本 SHA256 和恢复后的 SCM/进程/新请求。原先已停止的服务应保持停止；故障时保存备份日志和是否恢复运行的证据 |
| Windows 注销 | 记录注销前 PID、创建时间和时间戳，关闭控制台后由测试人员注销 Windows。优先由另一台电脑在注销期间持续发新请求并保存时间记录。重新登录后再次取证服务及进程；PID 与创建时间未改变可证明进程跨注销保留。只有登录后页面能打开，不能证明整个注销期间可达；没有外部请求证据时，将“注销期间 HTTP 连续可达”单列待验 |
| Windows 重启自启 | 记录关机前时间和数据摘要，由测试人员重启。重启后不要打开控制台或手动启动服务；等待延迟启动窗口（建议观察至 3 分钟并记录实际耗时），采集系统启动时间、PG 服务和 Web 服务状态及进程创建时间，发新请求、登录并下载同一成果校验 SHA256。若手动启动过，本轮不能算自动启动通过 |

注销、重启由测试人员亲自执行；本流程不会在当前 Codex 会话中代办或安排自动任务。异常时仅修复直接相关缺陷，保留失败现场和日志。先记录失败，再进行修复重试，不用手动启动掩盖自动启动失败。

## 5. 办公室另一台电脑访问

记录客户端电脑、时间、服务器内网地址和 Web 端口。在客户端用控制台给出的候选内网 URL 发新请求，检查首页、登录、项目与成果下载；在服务器退出控制台和注销期间重复。如有必要，由测试管理员手工仅允许办公室网络范围访问选定 Web TCP 端口，不开放 PostgreSQL，不改路由器映射。

无法接触另一台电脑时，明确写“人工待验：未接触办公室其他电脑”。本机访问服务器内网 IP 不能替代此项；虚拟客户端或 loopback 自动测试也不能替代。

## 6. 故障取证和退出

失败时填写模板中的步骤、期望、实际、时间和退出码。至少收集：

- 新交付 ZIP 的 SHA256、代码提交、Windows 版本、管理员令牌结果、程序和持久化绝对目录、数据库测试边界；不记录测试或正式密码。
- 控制台完整错误文字、发生步骤及截图，WinSW 安装/启动/停止命令的退出码和原文（如有人工使用），`sc qc/queryex/qfailure` 输出。路径和服务名称要完整保留。
- `persistent\logs` 中对应时间段的 WinSW wrapper/out/err 日志。若安装在 XML 生成前就失败，同时查看本次 `service` 目录产生的 WinSW 日志。保留停止与启动前后时间段，不仅截取最后一句。
- 事件查看器“Windows 日志 → 系统 → Service Control Manager”中本次 Yinda 服务的事件时间、ID 和完整错误；必要时采集“应用程序”中的 WinSW/.NET 崩溃事件。
- wrapper 和后端实际账户、PID、创建时间、EXE 路径；程序/存储 ACL 的只读输出；端口被占用时仅收集该端口监听者 PID/路径，不结束未知进程。
- PG **测试服务**状态、测试库地址/端口/名称、连接失败或迁移错误的已脱敏信息、部署 phase 和 Alembic revision；不要发 `runtime.env`、密码哈希、Cookie、CSRF token 或整个数据库目录。
- 生命周期前后项目 UID、成果 UID/相对路径、下载文件大小和 SHA256；LAN 失败时记录客户端地址、请求 URL、时间、HTTP 状态/浏览器错误及服务器同步日志。

日志发出前脱敏凭据，不能为了完整取证分享密码或会话。保留隔离测试数据以便复核；测试结束后由维护人员决定停服及保留期限，本流程不自动删除服务、任务、数据库或文件。
