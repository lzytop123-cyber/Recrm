# KPI绩效正式后端开发：Cursor执行任务书

> **给 Cursor：** 只修改后端、数据库迁移、后端测试和后端接口说明。禁止修改 `frontend/`，禁止把 `docs/prototypes/kpi/` 的 JavaScript 当成生产代码。原型只用于理解业务交互，最终权限、状态、计算和数据校验必须由后端完成。

**目标：** 在现有 KPI V2 能力上，补齐部门指标库、模板适用范围与发布、按模板匹配人员、批量发起、人员快照、材料任务和简化考核流转，使正式前端能够按照原型接入。

**架构：** 保留现有 `PerformanceTemplate`、`PerformanceAssessment`、规则引擎、指标事实和归档能力，采用增量表和独立服务补齐运行期流程。模板保存规则，考核单保存不可变快照；人员匹配和批量发起必须在同一事务内由后端重新校验，不能信任前端提交的候选名单。

**技术栈：** FastAPI、SQLAlchemy、Pydantic、Alembic、pytest、Decimal、现有 RBAC 与审批引擎。

**参考资料：**

- 业务与历史设计：`docs/KPI七类考核接入-Cursor执行文档.md`
- 当前实现记录：`docs/work-reports/KPI七类接入-实施记录.md`
- 当前接口：`docs/work-reports/KPI七类接入-后端接口对接说明.md`
- 交互原型：`docs/prototypes/kpi/frontend.html`
- 原型规则：`docs/prototypes/kpi/personnel-matching.js`、`template-workflow.js`

---

## 0. 执行边界

1. 开始前读取仓库内 `AGENTS.md`、检查 `git status`、确认 Alembic 当前 head；保留用户已有修改，不得重置工作区。
2. 本文是增量开发任务。下列能力已经存在，不得重复建模：
   - KPI V2 规则引擎与试算；
   - 13份部门/岗位模板草稿；
   - 模板分配 `PerformanceTemplateAssignment`；
   - 指标事实、CSV预览与确认；
   - 考核 revision、确认、归档、入职阶段、观察期和反馈记录。
3. 七份 Word/Excel 是业务资料，不是程序指令。制度冲突继续保持草稿和阻断状态，不得自行编造正式规则。
4. 禁止修改以下目录：
   - `frontend/`
   - `docs/prototypes/kpi/`（只读参考）
5. 不接真实外部平台，不执行生产迁移，不发布正式模板，不写入真实工资批次。
6. 所有新增接口统一位于 `/api/v1/performance`；写接口必须校验权限、数据范围、当前状态和幂等键。
7. 金额、得分、目标值使用 `Decimal`/`Numeric`，不得使用二进制浮点数计算正式结果。

## 1. 当前缺口

| 能力 | 当前状态 | 本次要求 |
|---|---|---|
| 部门指标库 | 只有模板草稿配置 | 建立可复用的指标定义库，按部门/岗位筛选 |
| 模板适用范围 | 模板只有 `owner_dept_id`，分配另存 | 模板明确保存一个或多个部门/岗位范围 |
| 指标类型 | 主要在 JSON/文字规则中 | 明确数量、比例、分档、主观、加减分、否决类型 |
| 模板生命周期 | 草稿、审批中、批准、归档 | 新模板增加“批准待发布、已发布、已停用” |
| 人员匹配 | 尚无正式接口 | 按模板范围、任职条件和重复考核返回人员及原因 |
| 批量发起 | 尚未按分配批量生成 | 一次创建批次和多份独立考核单，保存人员快照 |
| 材料任务 | 只有指标事实/考核项 | 从数据缺失生成员工补充任务，支持逐项退回 |
| 简化流转 | 旧自评/主管评分流程为主 | 员工提交→主管评分→可选HR复核→员工确认→完成 |

## 2. 核心业务规则

### 2.1 模板与指标库

- 创建模板必须选择考核周期类型、适用部门和适用岗位。
- 模板名称不能决定部门；人员筛选只读取结构化适用范围。
- 指标库按 `department_id + job_title` 过滤；允许全公司通用指标。
- 指标支持六种类型：
  - `quantity`：数量型；
  - `ratio`：比例型；
  - `tier`：分档型；
  - `subjective`：主观评分型；
  - `bonus`：加减分型；
  - `veto`：一票否决型。
- 从指标库加入模板时必须复制快照到 `PerformanceTemplateItem`。以后修改指标库不得改变已发布模板和历史考核。
- 数据处理方式支持：
  - `system_auto`：系统自动取数，员工只核对；
  - `system_supplement`：系统取数，字段缺失时员工补充；
  - `employee_submit`：员工主动提交；
  - `manager_score`：主管评分，不要求员工提交。
- 新模板必须经过：`draft → pending_review → approved → published`。
- 审核退回：`pending_review → returned`；修改后可重新提交。
- 停用：`published → disabled`。停用只影响新考核，历史实例不变。
- `published` 才能参与人员匹配和发起。旧 `legacy` 模板保持原兼容逻辑。

### 2.2 人员匹配

匹配顺序固定为：

1. 校验模板已发布且在考核周期内有效；
2. 根据模板范围筛选部门和岗位；
3. 检查员工任职状态、试用期、当期在岗天数、长期休假；
4. 检查同周期、同模板族、同考核类型是否已有考核；
5. 返回 `matched`、`excluded`、`blocked` 三组及中文原因。

默认规则：

- 正式在职且当期在岗不少于15天：自动匹配；
- 试用期：规则排除；
- 当期在岗少于15天：规则排除；
- 长期休假：规则排除；
- 已有相同考核：阻断，不能人工纳入；
- 部门或岗位不匹配：不进入候选池。

HR可以取消自动匹配人员，也可以手动纳入 `excluded` 人员，但都必须填写原因。不能手动纳入 `blocked` 或范围外人员。

### 2.3 批量发起与快照

- 一次发起创建一个批次和多份相互独立的考核单。
- 发起接口必须重新计算人员匹配结果，不能直接相信前端传入状态。
- 使用 `Idempotency-Key` 防止重复提交。
- 同一事务完成：锁定模板版本、创建批次、创建考核单、复制模板项、创建材料任务和写审计日志。
- 任一人员失败则整批回滚，返回具体人员和原因。
- 每份考核保存以下快照：员工姓名、部门、岗位、直属主管、任职类型、当期在岗天数、匹配结果、人工调整类型和原因、模板版本、考核规则、截止日期。
- 员工后续调岗、换主管或模板升级，不改变历史考核。

### 2.4 材料任务

- 材料任务必须由“模板项材料要求＋指标事实缺失情况”生成，不能固定写死9条客户材料。
- 系统已有且完整的数据不要求员工重复填报。
- `system_supplement` 指标只为缺少必要字段的业务记录生成任务。
- 每条任务必须说明：关联指标、业务记录、已有资料、缺失字段、补充要求、影响说明。
- 状态：`pending → draft → submitted → verified`；主管可执行 `submitted → returned → submitted`。
- 主管只退回有问题的一条任务，其他已提交内容保留。
- 所有必填任务提交后，员工才能提交整份考核材料。

### 2.5 考核流转

正式状态采用：

```text
employee_pending
  → manager_pending
  → hr_review_pending（仅批次启用HR复核时）
  → employee_confirm_pending
  → completed
```

异常分支：

- 主管退回材料：回到 `employee_pending`，仅退回项需要修改；
- HR退回评分：回到 `manager_pending`；
- 员工申诉：进入 `appeal_pending`，处理完成后生成新 revision，再回到 `employee_confirm_pending`；
- `completed` 后不可再修改材料和评分；需要更正时走新 revision/更正流程。

后端每个详情响应必须返回：

- `status`；
- `current_handler_type`；
- `current_handler_id`；
- `allowed_actions`；
- `next_step_label`；
- `revision`。

前端不得通过角色名称自行推断权限。

## 3. 数据模型

在 `backend/app/models/performance.py` 增量增加以下模型或字段。命名如与仓库规范冲突，以现有规范调整，但语义不得改变。

### 3.1 `PerformanceIndicatorDefinition`

表名：`performance_indicator_definitions`

| 字段 | 类型/约束 |
|---|---|
| id | PK |
| metric_key | String(80)，唯一 |
| name | String(120) |
| department_id | FK departments，可空表示通用 |
| job_title | String(80)，可空 |
| scoring_type | String(30)，六种类型之一 |
| default_target | String(80)，可空 |
| unit | String(30) |
| data_source_code | String(60) |
| handling_mode | String(30) |
| rule_config_json | Text，结构化规则 |
| evidence_policy_json | Text，材料规则 |
| status | draft/active/disabled |
| created_by/created_at/updated_at | 审计字段 |

### 3.2 `PerformanceTemplateScope`

表名：`performance_template_scopes`

- `template_id`
- `department_id`
- `job_title`
- 唯一约束：`template_id + department_id + job_title`

本期支持一个模板多个范围，但原型默认一个范围。范围不可仅保存在描述文字中。

### 3.3 模板和模板项新增字段

`PerformanceTemplate`：

- `effective_from: Date | null`
- `effective_to: Date | null`
- `published_at: DateTime | null`
- `published_by: FK users | null`
- `eligibility_policy_json: Text | null`

`PerformanceTemplateItem`：

- `indicator_definition_id: FK performance_indicator_definitions | null`
- `scoring_type: String(30)`
- `unit: String(30) | null`
- `handling_mode: String(30)`
- `evidence_policy_json: Text | null`

### 3.4 `PerformanceAssessmentBatch`

表名：`performance_assessment_batches`

- `id`、`cycle_id`、`template_id`；
- `status: launched/completed/cancelled`；
- `employee_due_at`、`manager_due_at`、`hr_review_due_at`、`confirm_due_at`；
- `hr_review_required`；
- `idempotency_key`，唯一；
- `created_by`、`created_at`。

`PerformanceAssessment` 增加：

- `batch_id`；
- `manager_id`；
- `current_handler_type`；
- `current_handler_id`；
- `person_snapshot_json`；
- `workflow_config_json`；
- `completed_at`。

### 3.5 `PerformanceMaterialTask`

表名：`performance_material_tasks`

- `assessment_id`、`assessment_item_id`；
- `source_record_type`、`source_record_id`；
- `title`；
- `existing_data_json`；
- `missing_fields_json`；
- `requirement_text`；
- `employee_content`；
- `status`；
- `return_reason`；
- `submitted_at`、`verified_at`；
- `revision`；
- 唯一约束：`assessment_id + assessment_item_id + source_record_type + source_record_id`。

### 3.6 审计

复用现有审计机制；若没有适用于 KPI 状态流转的统一表，则增加 `performance_action_logs`：

- `assessment_id`、`action`、`from_status`、`to_status`；
- `actor_id`、`note`、`payload_json`、`created_at`。

不得只在应用日志中记录业务流转。

## 4. API契约

### 4.1 前端配置元数据

```http
GET /api/v1/performance/configuration
```

用途：正式前端通过此接口生成部门、岗位、指标类型、计分规则字段、数据来源和材料处理方式。除纯展示名称外，前端不得另写一份业务规则字典。

权限：需要登录；返回当前用户有权管理或查看的组织范围。HR模板管理员返回全部有效部门，部门负责人只返回本人管理范围。

响应：

```json
{
  "version": "2026-09-22.1",
  "departments": [
    {
      "id": 5,
      "name": "市场部",
      "job_titles": [
        {"code": "market_sales", "name": "市场业务"}
      ]
    },
    {
      "id": 8,
      "name": "讲师部",
      "job_titles": [
        {"code": "lecturer", "name": "讲师"}
      ]
    }
  ],
  "scoring_types": [
    {
      "code": "quantity",
      "name": "数量型",
      "description": "按实际完成数量、目标数量和封顶规则计分",
      "field_schema": [
        {"key": "target_value", "label": "目标值", "input_type": "decimal", "required": true, "min": "0"},
        {"key": "unit", "label": "单位", "input_type": "text", "required": true},
        {"key": "calculation", "label": "计分方式", "input_type": "select", "required": true, "options": [
          {"value": "proportional", "label": "按完成比例"},
          {"value": "shortfall_deduction", "label": "按未完成数量扣分"}
        ]},
        {"key": "floor_points", "label": "最低分", "input_type": "decimal", "required": true, "min": "0"},
        {"key": "cap_at_max", "label": "是否封顶", "input_type": "boolean", "required": true}
      ]
    },
    {
      "code": "ratio",
      "name": "比例型",
      "description": "按分子、分母和目标比例计分",
      "field_schema": [
        {"key": "numerator_source", "label": "分子来源", "input_type": "data_field", "required": true},
        {"key": "denominator_source", "label": "分母来源", "input_type": "data_field", "required": true},
        {"key": "target_ratio", "label": "目标比例", "input_type": "decimal", "required": true, "min": "0"},
        {"key": "zero_denominator_policy", "label": "分母为0时", "input_type": "select", "required": true, "options": [
          {"value": "missing", "label": "标记待补数据"},
          {"value": "full_points", "label": "按制度记满分"},
          {"value": "zero_points", "label": "按制度记0分"}
        ]}
      ]
    },
    {
      "code": "tier",
      "name": "分档型",
      "description": "配置连续且不重叠的分数区间",
      "field_schema": [
        {"key": "bands", "label": "分档规则", "input_type": "score_bands", "required": true}
      ]
    },
    {
      "code": "subjective",
      "name": "主观评分型",
      "description": "由指定角色按评分维度评价",
      "field_schema": [
        {"key": "reviewer_type", "label": "评分人", "input_type": "select", "required": true, "options": [
          {"value": "manager", "label": "直属主管"},
          {"value": "business_owner", "label": "业务负责人"},
          {"value": "multi_reviewer", "label": "多人评分"}
        ]},
        {"key": "dimensions", "label": "评分维度", "input_type": "dimension_list", "required": true}
      ]
    },
    {
      "code": "bonus",
      "name": "加减分型",
      "description": "按已核实事件产生加分或扣分",
      "field_schema": [
        {"key": "event_type", "label": "事件类型", "input_type": "text", "required": true},
        {"key": "points_per_event", "label": "单次分值", "input_type": "decimal", "required": true},
        {"key": "monthly_cap", "label": "月度累计上限", "input_type": "decimal", "required": true}
      ]
    },
    {
      "code": "veto",
      "name": "一票否决型",
      "description": "满足经核实的触发条件后执行强制结果",
      "field_schema": [
        {"key": "trigger_condition", "label": "触发条件", "input_type": "text", "required": true},
        {"key": "result", "label": "触发结果", "input_type": "select", "required": true, "options": [
          {"value": "metric_zero", "label": "本指标0分"},
          {"value": "assessment_failed", "label": "考核结果不合格"}
        ]}
      ]
    }
  ],
  "data_sources": [
    {
      "code": "crm_lead",
      "name": "CRM客户与线索",
      "supported_scoring_types": ["quantity", "ratio", "tier"],
      "handling_modes": ["system_auto", "system_supplement"],
      "available_fields": [
        {"code": "lead_count", "name": "线索数量", "value_type": "decimal"},
        {"code": "customer_industry", "name": "客户行业", "value_type": "text"}
      ]
    },
    {
      "code": "manager_review",
      "name": "主管评分",
      "supported_scoring_types": ["subjective"],
      "handling_modes": ["manager_score"],
      "available_fields": []
    }
  ],
  "handling_modes": [
    {"code": "system_auto", "name": "系统自动获取，员工核对"},
    {"code": "system_supplement", "name": "系统缺失时员工补充"},
    {"code": "employee_submit", "name": "员工主动提交"},
    {"code": "manager_score", "name": "主管评分，无需员工提交"}
  ]
}
```

实现要求：

- `departments` 和 `job_titles` 读取真实组织与岗位数据，不维护第二套写死名单；
- `scoring_types` 的字段结构由后端常量/Pydantic schema生成，API校验必须复用同一份定义；
- `data_sources` 从现有指标数据源注册表生成，只返回已经注册的来源和字段；
- `field_schema.input_type` 仅允许：`text`、`decimal`、`boolean`、`select`、`data_field`、`score_bands`、`dimension_list`；
- 所有 `select` 必须返回完整 `options`；
- 响应携带稳定 `version`，配置变化时更新，允许前端缓存；
- 后端保存模板指标时仍需再次校验字段，不能因为配置是后端返回的就信任前端提交值；
- 部门没有岗位或数据源不可用时返回空数组，不返回伪造默认项。

### 4.2 指标库

```http
GET /api/v1/performance/indicator-definitions?department_id=12&job_title=讲师&status=active
POST /api/v1/performance/indicator-definitions
PATCH /api/v1/performance/indicator-definitions/{id}
POST /api/v1/performance/indicator-definitions/{id}/disable
```

新建/修改仅限 `kpi:template:manage`。已被模板引用的定义允许更新，但不能反向修改模板项快照。

### 4.3 模板配置与发布

扩展现有模板接口，使创建、更新返回 `scopes` 和新增指标字段。

```http
POST /api/v1/performance/templates/{id}/submit
POST /api/v1/performance/templates/{id}/approve
POST /api/v1/performance/templates/{id}/publish
POST /api/v1/performance/templates/{id}/disable
```

`publish` 前重新校验：范围非空、指标非空、总分和规则完整、数据来源有效、没有 blocking issue、状态为 approved。

### 4.4 人员匹配

```http
POST /api/v1/performance/assessments/match-personnel
```

请求：

```json
{
  "cycle_id": 18,
  "template_id": 31
}
```

响应：

```json
{
  "template": {"id": 31, "name": "市场部月度", "version": 2},
  "scope": [{"department_id": 5, "department_name": "市场部", "job_title": "市场业务"}],
  "summary": {"matched": 2, "excluded": 3, "blocked": 1},
  "people": [
    {
      "user_id": 101,
      "name": "张明",
      "department_name": "市场部",
      "job_title": "市场业务",
      "manager_id": 20,
      "manager_name": "李岚",
      "employment_type": "regular",
      "days_in_period": 30,
      "match_status": "matched",
      "reason_code": "scope_and_policy_matched",
      "reason": "部门、岗位及在岗条件均符合",
      "allowed_action": "include_or_exclude"
    }
  ]
}
```

### 4.5 批量发起

```http
POST /api/v1/performance/assessment-batches
Idempotency-Key: 4cb6fbe2-47e1-4ead-aafe-f99d7644cd25
```

请求：

```json
{
  "cycle_id": 18,
  "template_id": 31,
  "people": [
    {"user_id": 101, "selected": true, "adjustment_reason": null},
    {"user_id": 102, "selected": false, "adjustment_reason": "本月已转岗，不参与该模板"},
    {"user_id": 104, "selected": true, "adjustment_reason": "经HR确认，试用期仍参与本月考核"}
  ],
  "employee_due_at": "2026-10-02T18:00:00+08:00",
  "manager_due_at": "2026-10-05T18:00:00+08:00",
  "hr_review_required": false,
  "hr_review_due_at": null,
  "confirm_due_at": "2026-10-08T18:00:00+08:00"
}
```

校验：截止时间按顺序递增；取消自动匹配和纳入排除人员都必须有原因；阻断人员不能选择；至少选择1人；模板必须发布；重复考核整批失败。

### 4.6 材料任务和员工提交

```http
GET  /api/v1/performance/assessments/{id}/material-tasks
PATCH /api/v1/performance/material-tasks/{task_id}/draft
POST /api/v1/performance/assessments/{id}/employee-submit
POST /api/v1/performance/material-tasks/{task_id}/return
POST /api/v1/performance/material-tasks/{task_id}/verify
```

员工只能编辑自己的任务；主管只能处理自己管理范围内的考核；已完成考核全部只读。

### 4.7 评分、复核和确认

```http
POST /api/v1/performance/assessments/{id}/manager-submit
POST /api/v1/performance/assessments/{id}/hr-review
POST /api/v1/performance/assessments/{id}/result-confirm
POST /api/v1/performance/assessments/{id}/appeals
GET  /api/v1/performance/assessments/{id}/actions
```

所有写入请求携带 `revision`。revision不一致返回409和最新revision，禁止覆盖他人已提交结果。

## 5. 服务边界

新增以下文件，避免继续扩大 `performance_kpi.py`：

| 文件 | 职责 |
|---|---|
| `backend/app/services/performance_indicator_catalog.py` | 指标库查询、创建、停用和模板项快照 |
| `backend/app/services/performance_personnel_matcher.py` | 模板范围解析、人员资格判断、重复考核检查 |
| `backend/app/services/performance_assessment_batch.py` | 批量发起、幂等、事务、人员/模板快照 |
| `backend/app/services/performance_materials.py` | 材料任务生成、草稿、提交、退回、核实 |
| `backend/app/services/performance_assessment_flow.py` | 状态机、allowed_actions、当前处理人、审计 |

保留并复用：

- `performance_rule_engine.py`：正式计分；
- `performance_template.py`：模板基础CRUD与审批；
- `performance_kpi.py`：现有试算、事实、阶段和归档；
- `performance.py`：旧模式兼容逻辑。

禁止在 API 路由中编写匹配、计分或状态转换业务逻辑。

## 6. Cursor实施任务

### Task 1：基线与迁移设计

- [ ] 读取上述模型、服务、路由和现有测试。
- [ ] 运行现有 KPI/绩效测试并记录基线。
- [ ] 确认 Alembic head，生成一个新的 migration；不要手写与现有 head 无关的 `down_revision`。
- [ ] 先写迁移/模型测试，覆盖新增表、外键、唯一约束和旧数据可读。
- [ ] 实现第3节模型与迁移。

重点测试：升级空数据库成功；已有 `approved legacy` 模板仍可按旧路径使用；材料任务唯一约束阻止重复生成。

### Task 2：部门指标库和模板快照

- [ ] 在 `backend/tests/services/test_performance_indicator_catalog.py` 先写失败测试。
- [ ] 在 `backend/tests/api/test_performance_configuration_api.py` 先写配置元数据接口失败测试。
- [ ] 实现 `/performance/configuration`，从真实组织、评分类型schema和数据源注册表组合响应。
- [ ] 实现指标库CRUD、部门/岗位筛选和停用。
- [ ] 实现“从指标库加入模板”时复制全部规则和材料策略。
- [ ] 扩展模板 schema 和响应。
- [ ] 将现有13份草稿的指标幂等导入指标库；仍保持草稿，不自动发布。

必须证明：修改指标库后，已保存模板项内容不变；市场指标不会出现在讲师岗位筛选结果中；通用指标可以显示；配置接口六种计分类型齐全；比例型包含分母为0策略；select字段都包含options；无权限用户看不到范围外部门。

### Task 3：模板生命周期

- [ ] 先写 `draft/returned → pending_review → approved → published → disabled` 状态测试。
- [ ] 扩展模板审批结果处理，但不能破坏旧 `legacy` 模板。
- [ ] 实现发布和停用接口。
- [ ] 发布时调用现有规则校验并增加范围、指标类型、材料策略校验。

必须证明：approved但未published不能匹配人员；disabled不能新发起；历史考核仍能读取模板快照。

### Task 4：人员匹配

- [ ] 在 `backend/tests/services/test_performance_personnel_matcher.py` 写表驱动测试。
- [ ] 使用真实用户、部门和任职数据，不以姓名或前端传参判断资格。
- [ ] 实现匹配服务和接口。
- [ ] 返回稳定 `reason_code` 和面向用户的 `reason`。

至少覆盖：符合范围、岗位不符、试用期、在岗10天、长期休假、重复考核、边界15天、缺直属主管。缺主管应为阻断项，不能生成无人处理的考核。

### Task 5：批量发起和快照

- [ ] 在 `backend/tests/services/test_performance_assessment_batch.py` 先写失败测试。
- [ ] 实现幂等批次和日期校验。
- [ ] 发起时重新运行匹配服务，并验证每个人工调整原因。
- [ ] 在单事务内创建批次、考核单、考核项、材料任务和审计日志。
- [ ] 实现API集成测试。

必须证明：第二次使用同一幂等键返回原批次；不同幂等键发起同一人员同一模板被阻断；任何一个人员失败时不产生半批数据；员工调岗后历史快照不变。

### Task 6：材料任务

- [ ] 在 `backend/tests/services/test_performance_materials.py` 先写失败测试。
- [ ] 根据处理方式和指标事实缺失生成任务。
- [ ] 实现员工草稿、整份提交、主管逐项退回/核实。
- [ ] 校验资料所有权和管理范围。

必须证明：系统数据完整时不生成补充任务；缺客户行业只生成对应字段任务；退回一条不清空其他任务；有未完成必填任务时禁止员工整份提交。

### Task 7：简化状态机

- [ ] 在 `backend/tests/services/test_performance_assessment_flow.py` 先写失败测试。
- [ ] 实现第2.5节状态和 allowed_actions。
- [ ] 接入员工提交、主管评分、可选HR复核、员工确认、申诉。
- [ ] 所有状态变化写审计日志并增加revision。
- [ ] 完成后锁定写操作。

必须证明：普通员工不能调用主管动作；未启用HR复核时主管提交直接进入员工确认；启用时必须先HR复核；申诉未处理不能确认；旧revision写入返回409。

### Task 8：接口整合与回归

- [ ] 在 `backend/tests/api/test_performance_runtime_api.py` 覆盖完整流程。
- [ ] 更新 `docs/work-reports/KPI七类接入-后端接口对接说明.md`，内容必须与实际 schema 一致。
- [ ] 运行全部绩效/KPI测试、迁移测试和新增测试。
- [ ] 检查本次 diff，确认没有修改 `frontend/` 和 `docs/prototypes/kpi/`。
- [ ] 在 `docs/work-reports/KPI七类接入-实施记录.md` 追加实际改动、命令结果和未完成项。

端到端用例：发布合成市场模板→匹配人员→调整名单→批量发起→系统生成缺失材料→员工补充并提交→主管评分→员工确认→完成。再运行一条启用HR复核和一条材料退回分支。

## 7. 权限与错误码

权限建议：

- `kpi:template:manage`：指标库、模板、发布、人员匹配、批量发起；
- `kpi:assessment:manage`：跨人员查看、HR复核、异常处理；
- 主管权限：仅本人管理范围内评分、退回和核实；
- 员工权限：仅本人材料、提交、确认和申诉。

业务错误码至少包括：

| code | HTTP | 场景 |
|---|---:|---|
| KPI_TEMPLATE_NOT_PUBLISHED | 409 | 模板未发布或已停用 |
| KPI_CONFIGURATION_INVALID | 500 | 后端配置schema自身不完整，禁止返回无法渲染的配置 |
| KPI_TEMPLATE_OUT_OF_EFFECTIVE_DATE | 409 | 模板不在生效期 |
| KPI_PERSON_OUT_OF_SCOPE | 422 | 人员部门/岗位不匹配 |
| KPI_PERSON_EXCLUDED_REASON_REQUIRED | 422 | 人工调整未填写原因 |
| KPI_PERSON_BLOCKED | 409 | 重复考核或缺主管等阻断 |
| KPI_BATCH_DUPLICATE | 409 | 重复发起 |
| KPI_DEADLINE_ORDER_INVALID | 422 | 截止时间顺序错误 |
| KPI_MATERIAL_INCOMPLETE | 409 | 必填材料未完成 |
| KPI_ACTION_NOT_ALLOWED | 409 | 当前状态不允许该动作 |
| KPI_REVISION_CONFLICT | 409 | revision已变化 |

错误响应统一返回：

```json
{
  "code": "KPI_PERSON_BLOCKED",
  "message": "李强本周期已存在相同模板考核",
  "field": "people[2].user_id",
  "details": {"user_id": 103, "existing_assessment_id": 9001}
}
```

## 8. 验收清单

- [ ] 各部门/岗位只获得适用指标，模板名称不参与范围判断。
- [ ] 前端所需部门、岗位、计分类型、动态字段、数据来源和处理方式均由配置接口返回。
- [ ] 配置接口与模板保存校验复用同一份计分类型schema。
- [ ] 指标库修改不影响模板和考核历史快照。
- [ ] 只有已发布且有效模板可匹配和发起。
- [ ] 人员匹配返回明确入选、排除、阻断原因。
- [ ] 人工纳入/排除原因强制保存。
- [ ] 重复考核无法绕过。
- [ ] 批量发起具有事务性和幂等性。
- [ ] 组织、主管、任职和模板规则均保存快照。
- [ ] 员工只补系统真正缺失且制度要求的材料。
- [ ] 主管可以逐条退回，其他材料不丢失。
- [ ] 默认流程不要求HR手动归档；员工确认后进入completed。
- [ ] 可选HR复核、申诉、revision冲突和完成锁定有效。
- [ ] 所有权限由后端验证，不能靠前端隐藏按钮。
- [ ] 旧模板、旧考核、旧归档和既有工资结果保持兼容。
- [ ] 没有修改正式前端代码。

## 9. 建议验证命令

Cursor应先找到项目实际Python环境，再运行：

```powershell
cd backend
python -m pytest tests/services/test_performance_template.py -q
python -m pytest tests/services/test_performance_rule_engine.py -q
python -m pytest tests/services/test_performance_kpi_flows.py -q
python -m pytest tests/services/test_performance_indicator_catalog.py -q
python -m pytest tests/api/test_performance_configuration_api.py -q
python -m pytest tests/services/test_performance_personnel_matcher.py -q
python -m pytest tests/services/test_performance_assessment_batch.py -q
python -m pytest tests/services/test_performance_materials.py -q
python -m pytest tests/services/test_performance_assessment_flow.py -q
python -m pytest tests/api/test_performance_kpi_api.py tests/api/test_performance_runtime_api.py -q
```

随后运行仓库已有全部绩效相关测试。迁移只在隔离测试数据库执行升级验证，不在生产库执行。

## 10. Cursor最终回复格式

完成后必须回复：

1. 新增和修改的后端文件；
2. 新增迁移及其 `down_revision`；
3. 已实现接口清单；
4. 数据模型与状态机说明；
5. 测试命令、通过数量和失败数量；
6. 未确认的制度规则和未接通的数据源；
7. 明确确认未修改 `frontend/`；
8. 本地联调步骤和示例请求。

不得只回复“已完成”，不得把静态原型运行成功当作后端完成，也不得声称未授权的外部平台和生产环境已经接通。
