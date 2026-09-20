# 引大入秦工程现状调查采集系统

用于引大入秦灌区工程现状调查的本地化录入、任务分发、成果回收、查询、台账管理与 Excel 成果导出。

## 当前版本

**V1.1.0 正式版**

V1.1.0 在 V1.0.2 编号与增量成果汇总基础上，正式加入原生“中心 → 基层处 → 水管所 → 基层处 → 中心”三级任务与成果流转。

V1.1.0 已完成：

- `.ydtask` 引入 `task_uid / parent_task_uid / root_task_uid / task_depth` 任务谱系；
- 中心可直接向基层处下发父任务，父任务冻结该处所辖已选水管所分管范围集合；
- 基层处只能从父任务冻结范围派生所级子任务，服务层强制执行 `child scopes ⊆ parent frozen scopes`；
- 水管所继续使用独立 `local_data` 接收自己的子任务并录入调查数据；
- 所级成果回处后，调查记录继续保留真实 `source_task_uid + source_management_scope_uid`；
- 处级汇总成果使用 `submission_task_uid` 对父任务提交，不改写记录真实来源；
- 中心仅需验证自己实际下发过的处级父任务，不再要求中心伪造或持有所级子任务 issued history；
- 处级汇总自动按当前父任务冻结范围选择合法 completed 记录，并校验子任务、管理单位、分管范围与渠系一致性；
- 任务分发与成果提交 UI 已接入三级工作流，同时保留原中心直接向水管所下发的既有流程；
- 四套独立 `local_data` 的中心—处—两所—处—中心自动化往返及人工生产验收均通过。

截至 2026-09-20，Stage 4.1～4.5C、全量自动化回归及三级任务/成果人工生产验收全部通过。

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

附表1.1～1.15“灌区综合与水土资源调查”在 V1.1.0 中继续保留可见预留入口和 `series_1 / comprehensive` 底层扩展能力，但当前不启用软件化录入，继续采用现行业务中的内业查档、统计整理和 Excel 汇总流程。

## 任务与成果工作流

```text
中心
  ↓ 处级父任务 T1（.ydtask）
基层处
  ├─ 所A子任务 T2
  └─ 所B子任务 T3
        ↓
水管所独立调查
        ↓
所级 .ydresult
        ↓
基层处预检 / 导入 / 汇总
        ↓ submission_task_uid = T1
处级 .ydresult
        ↓
中心预检 / 事务化导入
        ↓
工程台账 / 数据查询 / 首页统计统一汇总
```

任务和成果跨数据库传递使用稳定 UID。调查记录继续保存：

```text
source_task_uid
+
source_management_scope_uid
```

表示真实调查来源；分级成果包使用：

```text
submission_task_uid
```

表示本次向上级提交所依据的任务。上级端按自己实际下发的不可变 issued-task / issued-scope 冻结快照验收，不伪造下级任务历史，也不使用当前主数据反向改写历史任务事实。

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
- `docs/11_V1.0.2发布说明.md`：编号重排、增量成果合并、正式锁号及当前任务流转边界。
- `docs/12_V1.1.0发布说明.md`：原生三级任务链、处级汇总和分级成果提交。

## 开发者

**Steven_Chen**
