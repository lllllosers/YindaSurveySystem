# Yinda Survey Web Center

`web_center/` 是“引大调查数据采集系统 / YindaSurveySystem”的 Web 中心实验实现。

当前阶段是 **Web + PySide6 桌面端混合架构 POC**。目标不是替代桌面端，而是验证中央 Web 与离线桌面端之间的职责边界和成果交换链路。

## 架构边界

### Web 中心负责

- 项目与调查批次管理；
- 用户、角色与权限；
- 操作审计；
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

## 当前明确暂停的模块

以下功能尚未进入正式实现：

- 正式组织机构主数据；
- 正式渠系主数据；
- CanalSegment 渠道分段；
- SurveyTask 调查任务；
- `.ydtask` Web 端生成与下发；
- `.ydresult` 的正式业务主数据预检；
- 冲突处理；
- 审核流；
- 正式成果入库；
- 中央统一正式编号；
- 汇总统计和“一张图”。

原因是桌面端的组织机构和渠系规范仍在调整。Web 不应提前建立第二套事实源。

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
- `manager`：项目、批次、成果上传/复检、审计；
- `reviewer`：项目、批次、成果只读；
- `viewer`：项目、批次、成果只读。

尚未实现的 `master_data`、`tasks`、`results.review` 等权限不会提前占位。

## 本地开发

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

Web POC 收口后先冻结。

待桌面端组织机构和渠系主数据稳定，再进入：

```text
正式主数据
  ↓
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
