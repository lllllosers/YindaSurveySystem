# 引大灌区调查数据采集系统

用于引大入秦灌区现状调查数据的本地化录入、管理、查询与 Excel 成果导出。

## 当前版本

**V0.8.0 测试版**

V0.8.0 在 V0.7.0 多电脑调查闭环基础上，完成渠道物理实体与管理范围解耦、management scope 冻结任务范围、`SurveyRecord` 的 task + scope provenance、上级 issued-task 冻结快照权威校验以及 `.ydresult` V2 成果回收闭环，并已通过独立双数据库人工生产验收。

当前开发分支已完成渠道管理范围与跨库任务 provenance 模型收口：`CanalUnit` 仅表示物理渠道，管理责任统一由 `CanalManagementScope` 表达；调查任务使用冻结的 management scope 快照约束录入范围，成果回收按上级端原始下发任务快照核验来源。

## 当前已实现

- PySide6 + SQLite 单机本地化运行框架
- 项目与调查批次管理
- 组织机构与物理渠系基础资料
- CanalManagementScope 渠道管理范围模型
- 跨数据库稳定 UID
- `.ydtask` 调查任务包、冻结任务范围与本地任务工作区
- `.ydresult` V2 调查成果包、来源任务/分管范围校验、成果预检与事务化导入
- SurveyRecord 任务与管理范围来源追踪（`source_task_uid` + `source_management_scope_uid`）
- 工程业务编号
- EngineeringAsset 工程台账
- SurveyRecord 历次调查记录
- InspectionResult 分项评价结果
- 附表2.1～2.14工程现状调查完整接入
- A/B/C/D 与 A/B/C 两类分项评价体系
- 工程状况类别默认按最差分项自动判定，并支持人工调整
- 建筑物等级规范化录入：如 `3` → `3级`
- 混凝土强度规范化录入：如 `30` / `c30` / `C30` → `C30`
- 草稿保存、重新打开和继续编辑
- draft → completed 调查完成流程
- 已完成记录继续修改及完整性校验
- 重复工程/渠段调查保护
- 调查记录删除与孤立工程对象清理
- 连续录入、快捷键和未保存修改保护
- 当前调查批次工程调查列表、筛选和统计
- 工程调查入口独立滚动，录入页面新增/编辑自动回到顶部
- 工程类型统一由 Registry / Definition 显示中文名称
- 统一数据查询模块
- 跨调查批次、跨调查表查询
- 按当前表单动态使用 A/B/C 或 A/B/C/D 等级筛选
- 查询结果公共汇总 Excel 导出
- 单调查表详细数据汇总 Excel 导出
- 附表2.1～2.14单记录正式原表 Excel 导出
- SQLite 自动备份与数据库恢复维护工具
- 开发测试数据与正式运行数据分离
- 独立临时数据库自动化回归测试

## Engineering Form Framework

附表2.1～2.14已经统一进入声明式工程调查框架。

```text
EngineeringFormDefinition
├── core identity / fields / position / evaluation
├── ListDefinition
├── SummaryExportDefinition
└── OriginalFormExportDefinition
        │
        ↓
EngineeringFormRegistry
        │
        ├── GenericEngineeringSurveyPage
        │       ↓
        │   generic persistence
        │       ↓
        │   point / range common DB API
        │
        ├── GenericEngineeringListPage
        │       ↓
        │   EngineeringSurveyListPage
        │
        ├── Generic Engineering Summary Exporter
        └── Generic Original Form Exporter
```

`EngineeringFormRegistry` 是生产代码中工程调查表身份的统一注册入口。

每张工程调查表主要保留自身的：

- 正式字段和页面分区
- 工程位置类型
- 正式评价项目与标准
- 列表声明
- 详细汇总列声明
- 正式原表 Excel 映射
- 必要的纯 formatter

公共生命周期、当前调查批次列表行为、详细汇总执行流程和正式原表执行流程均由通用实现承担。

当前不再为每张附表复制：

- 专属录入页面
- 专属 CRUD / completion 流程
- 专属当前调查批次 List Page
- 专属 summary exporter
- 专属 original-form exporter

## 后续工程调查表扩展原则

标准附表2.x原则上只新增或补充：

1. `FORM_2_X` 正式定义；
2. 正式评价内容；
3. List / Summary / Original Form 声明；
4. 正式 Excel 模板；
5. 表级合同测试和业务 workflow 回归测试。

只有在真实业务差异无法由现有合同清晰表达时，才增加受控扩展点；不预先建设万能动态表单平台。

## 当前开发方向

附表2工程现状调查体系已经完成阶段性闭环，V0.8.0 已具备基于 `CanalManagementScope` 的任务下发、基层受控录入、成果上报、来源核验和上级事务化汇总链路。

任务范围 provenance 与成果回收校验已完成 Stage 14 自动化与人工双重验收：物理 `CanalUnit`、管理关系 `CanalManagementScope`、任务冻结范围、`SurveyRecord` 来源身份、`.ydresult` V2、上级原始下发快照校验和事务导入均已贯通。双数据库人工验收已覆盖同一物理渠道多 scope、重复成果幂等、以及 current master 变化后历史成果 warning-only 但仍可合法导入的场景。

当前正式产品范围收口为 **附表2.1～2.14工程现状调查**。附表1.1～1.15主要沿用甲方现行内业查档、统计整理和 Excel 汇总流程，本阶段不实施软件化录入；桌面端继续保留可见的“灌区综合与水土资源调查（附表1系列）”预留入口，底层 `series_1 / comprehensive` 扩展能力继续保留。后续只有在实际业务出现明确数字化需求时，再单独启动附表1领域开发。

下一阶段转入甲方反馈整改、产品化体验优化、稳定性回归和正式投产收口。

## 技术栈

- Python
- PySide6
- SQLite
- openpyxl

## 开发者

**Steven_Chen**

## 版本状态

当前项目处于 `0.x` 开发阶段，尚未进入正式 `1.0.0` 发布版本。
