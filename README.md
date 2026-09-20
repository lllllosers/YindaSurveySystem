# 引大入秦工程现状调查采集系统

用于引大入秦灌区工程现状调查的本地化录入、任务分发、成果回收、查询、台账管理与 Excel 成果导出。

## 当前版本

**V1.0.2 正式版**

V1.0.2 为工程编号与成果增量汇总补丁版本，重点解决多调查组并行录入、同一具体渠道后续补录、成果重复汇总和正式编号收口问题。

V1.0.2 已完成：

- `EngineeringAsset / SurveyRecord` 增加 revision/source revision 合并基础，`.ydresult` 当前 schema 升级为 `2.2`；
- 累计成果包支持识别新增、已存在且一致、待更新、旧版本和冲突；
- 工程业务编号与稳定 UID、业务 revision 解耦，编号变化不再被误判为业务内容修改；
- 业务编号按“具体渠系 + 工程类型 + 桩号顺序”可重复整理，后续补录工程后可重新编号；
- 正式锁号前重新排序，并对附表2.1渠段重叠、间隔、超长和未完成记录执行预检；
- 不同具体渠道允许出现相同五段式业务编号；调查进行中的暂编编号允许临时重复；
- 成果接收端保留本地编号事实，不使用下级临时编号覆盖上级汇总后的编号；
- 调查录入模块修复隐藏表单 `sizeHint` 导致的窗口横向增宽，并将工程调查列表筛选区改为响应式网格布局；
- 正式锁号提示改为面向业务人员的中文说明。

截至 2026-09-20，Stage 3 全量自动化回归及编号人工生产场景验证通过。

当前桌面版仍未实现真正的“中心 → 处 → 所”父子任务链。V1.0.2 可继续采用现行业务中继方式：中心先生成全部所级任务包并保留完整 `local_data`，将含相同任务下发历史的副本交给处；所独立接收任务并录入，成果先由处汇总、核验、重新编号和锁号，再由处导出成果包返回中心。详细边界见 V1.0.2 发布说明。

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

附表1.1～1.15“灌区综合与水土资源调查”在 V1.0.2 中继续保留可见预留入口和 `series_1 / comprehensive` 底层扩展能力，但当前不启用软件化录入，继续采用现行业务中的内业查档、统计整理和 Excel 汇总流程。

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
- `docs/11_V1.0.2发布说明.md`：编号重排、增量成果合并、正式锁号及当前任务流转边界。

## 开发者

**Steven_Chen**
