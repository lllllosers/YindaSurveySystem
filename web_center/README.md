# Yinda Survey Web Center

`web_center/` 是“引大调查数据采集系统 / YindaSurveySystem”的 Web 中心实验实现。

当前阶段是 **V1.2.0 Web Center Preview**。目标不是替代稳定桌面端，而是让中央管理人员先在浏览器中验收项目、批次、用户权限、成果接收、审计与正式主数据。

## 一键启动（推荐）

在仓库根目录双击：

```text
启动Web管理中心.bat
```

会打开深色服务控制台，并自动完成：

- 检查 PostgreSQL、后端环境、前端依赖和本地配置；
- 执行 Alembic 数据库迁移；
- 启动 FastAPI 后端和 Vue 前端；
- 持续显示三个服务的在线状态与运行日志；
- 服务就绪后自动打开浏览器；
- 支持一键打开 Web、API 文档，以及停止本次启动的服务。

如果已有服务占用端口，控制台会识别并复用，不会把外部启动的进程当作自己的进程关闭。

访问地址：

```text
Web:      http://127.0.0.1:8848
API Docs: http://127.0.0.1:8000/docs
```

使用已有管理员账户登录。如果忘记本机 Web 管理员密码，可关闭服务后双击根目录的 `重置Web管理员密码.bat`，按提示输入管理员用户名和新密码；输入过程不会显示密码字符，也不会把明文写入文件。

## 架构边界

### Web 中心负责

- 项目与调查批次管理；
- 用户、角色与权限；
- 操作审计；
- V1.2 正式组织、渠系和管理范围只读浏览；
- `.ydresult` 成果包接收；
- 成果包安全检查、SHA-256 留存和文件归档；
- 成果提交详情与服务器文件完整性复检。

### PySide6 桌面端继续负责

- 离线调查填报；
- 附表 2.1～2.14 业务表单；
- 本地 SQLite；
- 照片、视频等调查影像；
- 草稿和 completed 调查记录维护；
- 正式原表导出；
- `.ydtask` / `.ydresult` 本地包生成与使用。

Web 中心不直接共享或同步桌面端 SQLite。

## 当前已验证

POC 已经验证以下链路：

```text
Vue
  ↓
FastAPI
  ↓
PostgreSQL

桌面端 .ydresult
  ↓
Web 上传
  ↓
流式落盘
  ↓
SHA-256
  ↓
manifest / ZIP / payload 结构检查
  ↓
ResultSubmission
  ↓
详情 / 下载 / 文件完整性复检
  ↓
审计日志
```

同时已经具备：

- HttpOnly 会话 Cookie；
- Argon2 密码哈希；
- 登录失败锁定；
- CSRF 防护；
- admin / manager / reviewer / viewer 四类角色；
- 用户禁用、密码重置、会话撤销；
- PostgreSQL Alembic 迁移；
- 后端 pytest；
- Vue TypeScript production build。

## 当前验收范围

- 现代化登录页与中央工作台；
- 服务、数据库和业务统计概览；
- 项目和调查批次管理；
- 正式主数据查询：5 个管理处、20 个管理所、68 条渠道、63 条管理范围；
- 用户与角色权限管理；
- `.ydresult` 上传、检查、归档和完整性复检；
- 审计日志。

正式主数据读取 `shared/master_data/official_master_contract.json`，后端启动时会校验版本、唯一键、引用关系和范围模式，并为实体计算稳定 UID。自动测试会检查该契约与桌面端 V1.2 常量一致。

## 后续阶段模块

以下功能尚未进入正式实现：

- CanalSegment 渠道分段；
- SurveyTask 调查任务；
- `.ydtask` Web 端生成与下发；
- `.ydresult` 的正式业务主数据预检；
- 冲突处理；
- 审核流；
- 正式成果入库；
- 中央统一正式编号；
- 汇总统计和“一张图”。

这些模块尚未纳入本次可验收预览，避免在任务协议和业务审核规则确认前形成第二套事实源。

## `.ydresult` 协议说明

当前 Web 的 `result_package_inspection.py` 是 POC 阶段的独立只读检查器，用于证明 Web 可以安全接收桌面成果包。

桌面端已经拥有更完整的：

- `yd_package_reader`
- `survey_result_package_reader`

因此，**当前 Web 检查器不是长期协议事实源**。

在进入正式混合架构开发前，应将 `.ydtask / .ydresult` 协议定义和通用读取校验能力收口为共享协议层，避免桌面端和 Web 长期维护两套规则。

## 权限边界

当前仅保留已经真实实现的权限：

- `admin`：全部权限；
- `manager`：项目、批次、正式主数据、成果上传/复检、审计；
- `reviewer`：项目、批次、正式主数据、成果只读；
- `viewer`：项目、批次、正式主数据、成果只读。

尚未实现的 `tasks`、`results.review` 等权限不会提前占位。

## 分别启动（开发调试）

后端：

```bat
web_center\backend\run_backend.bat
```

前端：

```bat
web_center\frontend\run_frontend.bat
```

或统一启动：

```bat
web_center\run_dev.bat
```

开发地址：

```text
Frontend: http://127.0.0.1:8848
Backend:  http://127.0.0.1:8000
```

## 安全和部署边界

当前默认配置面向本机 HTTP 开发：

```text
SESSION_COOKIE_SECURE=false
```

正式 HTTPS 部署必须改为：

```text
SESSION_COOKIE_SECURE=true
```

PostgreSQL 不应直接暴露公网。

当前成果文件使用服务器本地文件系统：

```text
web_center/backend/storage/
```

该目录不进入 Git。

POC 阶段暂不引入 Redis、Celery、对象存储、微服务、复杂 RBAC、GIS 或自动化备份平台。

## 下一阶段入口

本次可验收预览确认后，按以下业务顺序继续：

```text
渠道分段
  ↓
调查任务
  ↓
.ydtask 下发
  ↓
桌面端离线调查
  ↓
.ydresult 回传
  ↓
业务预检 / 冲突检查
  ↓
审核 / 正式入库 / 统一编号
```
