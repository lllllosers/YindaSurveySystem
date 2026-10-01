# Windows portable build inputs

[portable-build-inputs.json](portable-build-inputs.json) 记录本次已验收输入身份；这些是本机构建输入，不是源码依赖。没有二进制文件提交进 Git，也没有移动旧输入。

- Python 3.12.9 x64 embed ZIP；SHA256 见 manifest。
- 后端完整 site-packages（FastAPI、uvicorn、SQLAlchemy、Alembic、psycopg、openpyxl），由 web/backend/requirements.txt 描述。
- PostgreSQL 17.11 Windows bin/lib/share；不能输入 data、旧 postmaster 状态或账号配置。
- 新编译的 YindaWebServerConsole.exe、最新 frontend/dist、shared 与14张 root模板。

本轮仍读取旧 ignored `web_center/release/python-3.12.9-embed-amd64.zip`、`web_center/backend/.venv/Lib/site-packages` 与 `web_center/build/portable-final-verify-20260929/runtime/postgres`。它们不应被当作永久来源。Phase 3 清理之前必须建立并核验可恢复、版本固定的独立来源；未落实之前禁止删除旧输入。

Desktop PyInstaller source smoke 使用原有完整 Desktop Python 3.12 环境及 desktop/requirements.txt 精确锁定的五项版本，不拼接多个 site-packages。正式 build_release 继续是 release/v1.2.0 专用入口，不能用于普通重构分支放行。
