# 兼容性合同

| 合同 | 当前值 |
| --- | --- |
| Desktop | 1.2.0，正式版 |
| Web | acceptance baseline / version pending |
| .ydtask | 当前 3.0；兼容 2.0 |
| .ydresult | 当前 2.2；兼容 2.0、2.1 |
| master contract schema | 1.0 |
| master data | 2026-09-official-v1 |
| management scopes | 2026-09-official-canal-management-scope-v1 |
| form contract schema | 1.0 |
| form contract | 2026-09-v1.2.0；14表 version_code V2 |

Phase 2 只拆分源码与测试归属；SQLite schema、seed、migration、Alembic revisions、稳定 UID、协议键与版本、正式字段与模板坐标保持不变。

冻结 Desktop EXE 继续名为 YindaSurveySystem.exe。数据库继续在 exe 旁 `local_data/yinda_survey.db`，已安装原表模板继续在 exe 旁 `templates/excel/`。完整 ZIP 继续叫 `YindaSurveySystem_V1.2.0_Windows_x64.zip`；V1.1.1 → V1.2.0 update_payload/manifest 与保留 local_data 的升级合同不变。

源码开发环境的默认数据位置为 desktop/local_data；测试使用临时库。源码模板使用唯一 root templates/excel，不复制到产品源码目录。

Web source 在 web，部署 ZIP/portable ZIP 内仍在 web_center；已有 `D:\YindaWeb\web_center` 不改。DB name/source_channel/backup CLI 不改。便携 PostgreSQL 55432 与 Web 8000 的 GUI initialize/start/Stop All、隐藏进程与 CREATE_NO_WINDOW 行为保持。

冻结工程阶段 tag `pre-monorepo-20261001` 指向 cbe4c8b12abf122d1043e9e8f32e7218cf7845aa，不是产品 release。重构只在 refactor/monorepo-layout；完成验收后仍需人工批准合回 main。
