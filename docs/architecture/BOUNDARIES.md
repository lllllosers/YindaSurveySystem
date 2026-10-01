# 产品与公共核心边界

`desktop → shared ← web`。禁止产品互相导入，禁止 shared 导入 Desktop/Web、Qt、FastAPI、SQLAlchemy 或数据库 adapter。

shared/forms/engineering 保存 14 张正式表的身份、字段、分区、位置、评价顺序和原表 Excel mapping。Desktop 的 forms/engineering 是 extension：添加 list_definition、summary_export_definition、固定列宽、按钮和查询绑定。Web 直接读 shared registry。

shared/evaluation 保存 14 套原样评价标准；shared/export 使用 openpyxl，从显式 record、record_data、evaluation_map 和 ownership/canal_lineage 输入渲染。SQLite 读取在 Desktop adapter 中，PostgreSQL/snapshot 读取在 Web adapter 中。

shared/protocol 继续维护 .ydtask/.ydresult 协议。shared/master_data 的 loader 仅读取现有 JSON，不 seed、不修数据。Desktop constants、稳定 UID、5处/20所/68渠与63 management scopes 的算法保留；当前等价检查继续存在于 Desktop 测试。尚未人工确认的骨干渠分段范围仍是技术债，Phase 2 不推断、不补齐。

测试属于 desktop/tests、shared/tests、web/backend/tests。shared-only checkout 另含 templates，Desktop sparse 包含 desktop/shared/templates/docs/desktop/docs/architecture，Web sparse 包含 web/shared/templates/docs/web/docs/architecture。各产品使用自己配置的 Python 依赖环境；源码中不借用另一产品。

历史文档按职责归档，早期文档中的旧源码路径属于当时记录；当前命令以根 README、web README 和本文为准。旧 ignored web_center/build、release、venv、runtime、logs 与业务数据留在原位置，禁止 Phase 2 清理。
