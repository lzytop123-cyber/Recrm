# KPI 七类接入实施记录

日期：2026-09-21

## 基线

现有绩效测试 13 项通过（模板、计分、周期、审批规则、KPI API）。未跑生产 seed，未改源考核文件，未改 `frontend/`。

## 已落地

- 规则引擎 `backend/app/services/performance_rule_engine.py`：签约扣分、线索低于 4 条为 0、缺失不算 0、110 分阻止发布、档位与满分冲突、个人目标不乘项目数、客资覆盖、无 998 与应续约 0 的区别、品宣 105 与造假强制不合格、基数缺失不用 5000、讲师超过 3 次才触发、观察期再次触发不解除。
- 模型与迁移 `p8q9r0s1t2u3`：新引擎字段、实例键 `(cycle_id, user_id, instance_key)`、事实/导入/阶段/观察期/反馈表。旧模板默认 `legacy_weighted`。
- 13 份草稿：`backend/app/data/performance_templates/catalog.py`，`load_drafts()` 可重复执行，状态保持草稿。
- 接口：校验、修订、试算、分配、台账、导入、考核试算、刷新、确认、归档、反馈、讲师投诉、阶段、观察期。权限 `kpi:template:manage`。归档金额写在考核单上。
- 迁移 `q9r0s1t2u3v4`：`confirmed_revision`。刷新后旧确认不能归档。
- 原型：`docs/prototypes/kpi/index.html` 与 12 张 PNG。对接说明：`docs/work-reports/KPI七类接入-后端接口对接说明.md`。

验证：`tests/services/test_performance_kpi_flows.py` 与原绩效服务测试，23 passed（含本批流程）。

## 未做

- 按分配批量生成考核单，以及把归档金额写入工资批次。
- 外部平台 API。迁移未在 Postgres 上执行 upgrade。
- 正式前端未改。有冲突的模板不能当正式制度发布。

---

## 2026-09-22 运行期增量（任务书 Task 1–8）

### 改动摘要

- 迁移 `r0s1t2u3v4w5`（`down_revision=q9r0s1t2u3v4`）：指标库、模板范围、批次、材料任务、流转审计；模板发布字段；考核 `batch_id`/`person_snapshot`/`current_handler` 等。
- 服务：`performance_scoring_schema`、`performance_indicator_catalog`、`performance_personnel_matcher`、`performance_assessment_batch`、`performance_materials`、`performance_assessment_flow`；扩展 `performance_template` 发布/停用。
- 接口：configuration、indicator-definitions、match-personnel、assessment-batches、材料任务、employee/manager/hr/confirm、runtime-appeals、actions、runtime-detail。
- 未修改 `frontend/` 与 `docs/prototypes/kpi/`。

### 验证命令（节选）

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/services/test_performance_runtime_models.py tests/services/test_performance_indicator_catalog.py tests/api/test_performance_configuration_api.py tests/services/test_performance_template_lifecycle.py tests/services/test_performance_personnel_matcher.py tests/services/test_performance_assessment_batch.py tests/services/test_performance_materials.py tests/services/test_performance_assessment_flow.py tests/api/test_performance_runtime_api.py tests/services/test_performance_kpi_flows.py tests/api/test_performance_kpi_api.py -q
```

### 未完成 / 未接通

- 外部 CRM/考勤平台实时取数未接；在岗天数优先飞书考勤日事实，无事实时按入职日估算。
- 市场部（C09）与入职培训（C11）仍阻断发布；其余 5 类（讲师/直播主播/直播投手/品宣/内容/AI运维）已按 2026-09 源表落库并可发布。
- 迁移未在生产库执行；未写真实工资批次。
- 旧 `/assessments/{id}/appeals` 与运行期 `/runtime-appeals` 并存（revision 冲突保护仅后者）。

### 2026-09-22 catalog 源表落库

- 源文件：`2026-09/讲师考核制度.docx`、`直播绩效考核表.xlsx`、`品宣团队考核表.xlsx`、`内容制作团队考核表.xlsx`、`AI技术运维考核表.xlsx`
- 约定：表体优先于备注；AI 运维满分取 110；内容制作产出/播放最高档对齐分值列 30；直播补齐区间端点；品宣私域目标取 50/10
- 重载：`load_drafts()` 会刷新 `nominal_total` 与模板项
