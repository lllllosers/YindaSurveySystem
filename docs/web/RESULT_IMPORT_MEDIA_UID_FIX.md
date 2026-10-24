# Web 正式成果入库修复验收记录

日期：2026-10-24。范围仅为正式成果入库，等待代码审查后进入集成发布。

## 基线与工作区

- WebCenter 原分支 main，HEAD 和 fetch 后 origin/main 均为 `23aa2bb85970c84244f319aeb90ed4dee8d4a31e`，与任务给定基线无差异。
- 修复分支：`fix/web-result-import-media-uid`，从 origin/main 创建。
- Desktop 工作区为 `release/v1.2.2`，HEAD `2ac54d9084cf69fb493b56132bc4edf10bcee1ea`，本次未改动。
- 两个工作区已有的 `.vscode/settings.json` 修改均保留，不纳入提交。
- 原 Alembic 唯一 head 为 `20260927_0213`；新增唯一 head 为 `20261024_0214`。
- 未推送、合并 main、移动 tag、制作发布包或连接生产数据库。

## 根因、修复及 UID 审查

桌面端 `survey_media.py` 以 `str(uuid.uuid4())` 生成36字符 UID；`survey_result_package.py` 原样写入影像身份、记录归属和文件清单。共享读取器校验 ZIP、manifest、哈希、大小及记录引用，接受该身份格式。Web 正式表 `central_survey_media.media_uid` 原为 VARCHAR(32)，导致提交时 PostgreSQL 抛出 StringDataRightTruncation。

本次仅将该列扩展至 VARCHAR(36)。不修改桌面协议或生成方式，不截断、转换或重新生成 UID；32字符旧值继续有效。唯一索引、记录归属、包内路径和文件元数据保持不变。

其他正式入库 UID 已检查：项目、批次、工程、记录等由桌面 `database.py` 使用 `lower(hex(randomblob(16)))` 生成；任务、成果、包 UID 使用共享 `new_stable_token()` 的32字符 hex；正式单位、渠道和分管范围使用共享确定性32字符身份规则，历史自建范围也使用 uuid4().hex。分项评价以记录 UID 与 item_code 标识。未发现需要扩列的其他生成端证据，因此未放宽其他约束。

正式入库保留现有提交行 FOR UPDATE 锁及单次提交：工程、记录、分项评价、影像、成果 imported 和任务 closed 在同一事务提交，异常整体回滚。同一成果重复或并发请求中，后续请求返回409，不重复写入。500响应只返回通用提示，详细异常写服务日志。

成功重复预检保留 accepted 及审核信息；发现真实冲突时保存 conflict、预检问题并清除失效审核。入库前复检冲突同样保存该状态，但不写正式数据。修复冲突后必须重新预检和审核。

前端仅正式入库 POST 使用120秒超时，其他请求仍沿用原配置。分别处理409、410、500、超时及网络中断；响应异常后 GET 查询服务器状态。超时/断网且未确认 imported 时提示“入库结果尚未确认”，禁用重复入库并提供状态刷新；不会自动重试 POST。页面重新加载继续读取服务器保存的状态。

## 修改文件

| 文件（仓库相对路径） | 内容 |
| --- | --- |
| web/backend/app/models/central_record.py | 影像 UID 36字符 |
| web/backend/alembic/versions/20261024_0214_central_media_uid.py | 新迁移及安全降级 |
| web/backend/app/services/result_workflow_service.py | 重复预检与失效审核处理 |
| web/backend/app/api/routes/result_submissions.py | 回滚后的安全500响应与日志 |
| web/backend/tests/test_result_workflow_api.py | 正式协议多记录影像、回滚、状态和并发回归 |
| web/backend/tests/test_media_uid_migration.py | PostgreSQL真实建表、故障复现、升级重试和降级保护 |
| web/frontend/src/api/results.ts | 正式入库独立超时 |
| web/frontend/src/api/resultImportOutcome.ts | 错误分类及状态查询 |
| web/frontend/src/views/ResultDetailView.vue | 接入查询、提示和重复提交保护 |
| web/frontend/tests/resultImportOutcome.test.ts | 前端错误与查询回归 |
| web/frontend/package.json | 无新增依赖的 Node 测试命令 |
| docs/web/RESULT_IMPORT_MEDIA_UID_FIX.md | 本验收记录 |

## 迁移与验证

升级链：`20260927_0213 -> 20261024_0214`。历史迁移未修改。升级只 ALTER COLUMN；降级在事务内持有表锁，先检查是否存在长度超过32的 UID；存在则抛出明确异常，数据及 Alembic 版本均不变，禁止静默截断。

实际验证环境：Windows、Python后端既有虚拟环境、PostgreSQL 17独立新建测试实例（127.0.0.1:55439）、独立测试库；未读取本机生产业务库。前端使用 Node 24.21.0及已有 node_modules，无新依赖。前端 `.ts` 测试使用 Node 原生类型擦除，需要 Node 22.18或更新的兼容版本。

| 检查 | 结果 |
| --- | --- |
| 工作流及迁移专项（含并发） | 13项 PASS，全部也纳入最终完整集 |
| 后端完整 `python -m pytest tests -q --tb=short` | 73项 PASS，0跳过 |
| Alembic current / heads | 均为唯一 `20261024_0214` |
| Alembic check | No new upgrade operations detected |
| 前端 `npm test` | 10项 PASS |
| 前端 `npm run build` | vue-tsc 类型检查及 Vite 生产构建 PASS |
| git diff --check | PASS |

成果测试通过真实 ZIP 上传、manifest和共享校验逻辑，覆盖10条记录、10条分项评价、25张影像及处级多基层来源，分别验证36和32字符 UID、数量及路径/哈希/大小/归属。五个写入阶段注入真实 PostgreSQL 语句错误，验证无部分正式数据、状态不误变及修复后可重试。并发请求验证200/409与唯一数据集合。

迁移测试另建随机命名临时数据库：从历史迁移建至0213，保存32字符影像快照，复现36字符直接写入截断及真实成果API入库500，确认正式数据回滚且成果仍 accepted、任务仍 result_received；升级0214后同一已接收成果直接重试成功，旧影像所有列及索引定义保持一致。存在长 UID 时降级拒绝且不丢数据；仅在临时库移除测试长值后，验证可安全降级再升级。

现有 FastAPI/Starlette TestClient 的 httpx 弃用提示和 Vite 大 chunk 提示仍存在，未在本阶段升级依赖或重构前端。未提供本次事故的原始成果文件，因此使用符合当前共享协议的同规模合成成果回归，原始包应在验收环境复核。本次没有真实网络浏览器端到端故障注入，前端错误恢复由自动化逻辑测试、类型检查及构建验证。

## 生产便携版升级注意事项（后续集成发布时执行）

1. 审查验收通过后再制作含后端、0214迁移和新前端 dist 的便携包。本次不制作包、不升级生产。
2. 停止写入并用现有控制台完整备份数据库和 storage，将同次备份转存独立磁盘；停止全部服务后覆盖程序文件。
3. 保留原 `data`、`web_center/backend/.env`、`storage`、`backups` 和运行配置，禁止清空或重建数据库。便携目录仍使用 web_center，不改成源码 web 路径。
4. 按现有便携控制台的升级路径运行“初始化便携环境”执行 Alembic 迁移；确认数据库到达唯一0214后再启动 Web。仅覆盖代码而未执行迁移不能解决故障。
5. 检查登录、健康检查、成果详情及正式库数量；对原失败且仍 accepted 的成果手工执行一次入库。若预检出现新冲突，先处理并重新审核；若浏览器超时或断网，先刷新确认状态，勿重复提交。
6. 已存在36字符 UID 后不能把数据库降回0213。需要回退时先评估程序与扩展列的兼容性，或按既有流程恢复同次数据库与 storage 备份；禁止缩短、改写或删除生产 UID 来强行降级。
