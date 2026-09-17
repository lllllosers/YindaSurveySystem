# 引大灌区调查数据采集系统

用于引大入秦灌区现状调查数据的本地化录入、管理、查询与 Excel 成果导出。

## 当前版本

**V0.6.0 测试版**

V0.6.0 完成附表2.1～2.14工程现状调查体系的完整接入，并完成一轮甲方生产验收反馈修正。

当前附表2系列已统一进入 Engineering Form Framework，具备录入、评价、草稿/完成、工程台账、数据查询、详细汇总和正式原表导出等完整业务闭环。

## 当前已实现

- PySide6 + SQLite 单机本地化运行框架
- 项目与调查批次管理
- 组织机构与渠系基础资料
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
- 当前批次工程调查列表、筛选和统计
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

公共生命周期、当前批次列表行为、详细汇总执行流程和正式原表执行流程均由通用实现承担。

当前不再为每张附表复制：

- 专属录入页面
- 专属 CRUD / completion 流程
- 专属当前批次 List Page
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

附表2工程现状调查体系已经完成阶段性闭环。

下一阶段不继续为附表2增加无需求的公共抽象，优先进行版本化测试发布、甲方实际数据试录和问题收集；附表1系列作为独立业务域后续单独设计数据模型和录入方式。

## 技术栈

- Python
- PySide6
- SQLite
- openpyxl

## 开发者

**Steven_Chen**

## 版本状态

当前项目处于 `0.x` 开发阶段，尚未进入正式 `1.0.0` 发布版本。
