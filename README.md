# 引大入秦工程现状调查采集系统

用于引大入秦灌区工程现状调查的本地化录入、任务分发、成果回收、查询、台账管理与 Excel 成果导出。

## 当前版本

**V1.0.1 正式版**

V1.0.1 为 V1.0.0 的正式补丁版本，在保持既有工程调查、任务分发和成果回收机制不变的基础上，为附表2.1～2.14补充四项签字字段，并完成旧数据库升级、正式原表、详细汇总和成果包回传闭环。

V1.0.1 补丁验证：

- 四项签字字段保存、回填、正式原表和详细汇总导出通过；
- 调查人支持多人文本原样保存；
- `.ydresult` 当前 schema 为 `2.1`，V1.0.1 同时兼容读取正式 `2.0` 成果包；
- V1.0.0 → V1.0.1 SQLite 迁移、幂等和数据保留测试通过；
- 多管理单位任务分发—成果回收生产链重新回归通过。

截至 2026-09-19：

- 全量自动化回归测试通过；
- 多管理单位 `.ydtask → 独立调查端 → .ydresult → 总库归并` 自动化场景通过；
- 多单位分阶段成果回收联动验证通过；
- 人工模拟生产验收通过。

## 正式业务范围

当前正式软件业务范围为：

- 附表2.1～2.14工程现状调查；
- 项目与调查批次管理；
- 组织机构、物理渠系与分管范围维护；
- 工程调查录入、草稿、完成、修改与删除；
- 工程台账与历次调查；
- 数据查询与 Excel 汇总；
- 单记录正式原表导出；
- 调查任务分发与任务接收；
- 调查成果提交与成果接收；
- SQLite 自动备份与恢复。

附表1.1～1.15“灌区综合与水土资源调查”在 V1.0.1 中继续保留可见预留入口和 `series_1 / comprehensive` 底层扩展能力，但当前不启用软件化录入，继续采用现行业务中的内业查档、统计整理和 Excel 汇总流程。

## 任务与成果工作流

```text
上级总库
  ↓
任务分发
  ↓
.ydtask 调查任务包
  ↓
基层调查端接收任务
  ↓
冻结任务工作区 / 分管范围
  ↓
工程调查录入
  ↓
.ydresult 调查成果包
  ↓
上级总库成果预检
  ↓
导入前自动备份
  ↓
事务化导入
  ↓
工程台账 / 数据查询 / 首页统计统一汇总
```

任务和成果跨数据库传递使用稳定 UID。调查记录保存：

```text
source_task_uid
+
source_management_scope_uid
```

上级端按任务分发时保存的不可变 issued-task / issued-scope 冻结快照核验历史成果，不使用当前主数据反向改写历史任务事实。

## 核心数据模型

```text
Project
└── SurveyBatch
    ├── EngineeringAsset
    │   └── SurveyRecord
    │       ├── InspectionResult
    │       └── SurveyMedia
    └── Survey task / result exchange

OrganizationUnit
└── CanalManagementScope
    └── CanalUnit
```

其中：

- `CanalUnit` 只表示物理渠道；
- `CanalManagementScope` 表示管理责任和分管范围；
- 同一物理渠道允许存在多个独立分管范围；
- 历史任务范围以任务分发时冻结快照为准。

## Engineering Form Framework

附表2.1～2.14统一使用声明式工程调查框架：

```text
EngineeringFormDefinition
├── core identity / fields / position / evaluation
├── ListDefinition
├── SummaryExportDefinition
└── OriginalFormExportDefinition
        │
        ↓
EngineeringFormRegistry
        ├── GenericEngineeringSurveyPage
        ├── GenericEngineeringListPage
        ├── engineering_summary_export
        └── engineering_original_form_export
```

`EngineeringFormRegistry` 是生产代码中附表2工程调查表身份的统一注册入口。

## 首页统计口径

首页“已录记录完成率”定义为：

```text
录入完成记录数 ÷ 已录记录数
```

当前数据库没有权威的“某单位应调查工程总量”计划基准，因此该指标只描述**已经录入的数据中有多少完成录入**，不等于辖区最终工作量完成率。

任务分发历史中的“已有成果返回”也只表示该任务已有调查记录回到总库，不等于任务整体已经全部完成。

## 数据安全

系统采用 SQLite 本地数据库。正式成果导入前会自动创建数据库备份，并通过事务执行成果导入。

正式发布包不得携带开发数据库或 `local_data` 目录。跨电脑交换使用 `.ydtask` 与 `.ydresult` 文件。

## 开发与测试

开发环境：

```text
Python
PySide6
SQLite
openpyxl
```

运行完整测试：

```bat
run_tests.bat
```

开发环境启动：

```bat
.\.venv\Scripts\python.exe src\main.py
```

## 文档

- `docs/05_当前开发状态与路线图.md`：当前稳定状态和后续维护边界；
- `docs/06_甲方反馈整改清单.md`：V1.0 反馈整改收口；
- `docs/07_术语与界面文案规范.md`：正式界面术语规范；
- `docs/08_V1生产验收矩阵.md`：V1.0 多单位生产验收；
- `docs/09_V1.0.0发布说明.md`：正式版本范围、验收状态与已知边界。
- `docs/10_V1.0.1发布说明.md`：签字字段补丁、成果包兼容和升级说明。

## 开发者

**Steven_Chen**
