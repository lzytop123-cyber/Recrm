# KPI 七类接入 · 后端接口对接说明

前缀 `/api/v1`。除本人确认、本人看台账和反馈外，需要权限 `kpi:template:manage`。旧加权模板仍走原绩效路由。

分数用字符串小数，例如 `"15.00"`。空实际值是待补，不按 0 计算。正式总分在任一项待补时为 `null`。

## 模板

`POST /performance/templates/{id}/validate`

返回 `ok`、`engine_version`、`issues`。旧加权模板直接 `ok: true`。

`POST /performance/templates/{id}/revise`

从当前版本复制下一版草稿，编码 `{family}_V{n}`。不发布。版本已存在返回 409。

`POST /performance/templates/{id}/preview`

```json
{ "actuals": { "market.signed_clients": "3" } }
```

返回 `lines`（`metric_key`、`awarded_points`、`data_state`、`trace`）、`total_points`、`formal`。不创建考核单。旧加权模板返回 400。

## 分配与数据源

`GET /performance/template-assignments`

`POST /performance/template-assignments`

```json
{ "template_id": 1, "user_id": null, "department_id": null, "job_title": null, "assessment_kind": "monthly" }
```

优先级：指定人员 40，部门加岗位 30，仅部门 20，默认 10。同一优先级再配一条返回 409。还没有按分配批量生成考核单。

`GET /performance/metric-sources`

当前只有手工台账说明。外部平台未接。

## 事实与导入

`GET /performance/metric-facts`

管理员看全部，其他人只看自己的。

`POST /performance/metric-facts/{id}/review`

```json
{ "status": "confirmed" }
```

`status` 只接受 `confirmed` 或 `rejected`。

`POST /performance/imports/preview`

```json
{ "csv_text": "employee,metric_key,value,source_record_id,project_ref\n合成甲,market.signed_clients,4,SYN-1,P1\n", "employees": { "合成甲": 1 } }
```

有错误行时 `can_confirm` 为 false。重复来源标 `duplicate`。

`POST /performance/imports/{id}/confirm`

只能确认自己创建的批次。有错误整批不写。已确认再调返回 `idempotent: true`。

## 考核单

`POST /performance/assessments/{id}/preview-score`

请求体同模板试算。已归档返回 409。不改单据。

`POST /performance/assessments/{id}/refresh-data`

`revision` 加 1。已归档返回 409。旧的 `confirmed_revision` 保留，但不能再用于归档。

`POST /performance/assessments/{id}/confirm`

本人或有管理权限的人确认当前 `revision`。已归档返回 409。

`POST /performance/assessments/{id}/archive`

可选正文 `{ "fraud": true }`，只对品宣模板生效：先扣 26 再强制不合格。

- 确认版本不是当前版本：400
- 总分待补：400
- `payroll_eligible` 为 false（入职阶段）：归档成功，金额为 null，不用 5000
- 缺 `performance_base_snapshot`：400，不生成金额
- 市场：≥90 系数 1.00，≥80 为 0.80，≥60 为 0.60，否则 0
- 品宣：≥90 记优秀且系数为空不发金额，≥70 为 1.00，≥60 为 0.80，否则 0.50
- 105 分不压成 100

归档只写下考核单上的等级、系数和金额，不写工资批次。

## 反馈、阶段、观察期

`GET /performance/feedback-records`

`POST /performance/feedback-records`

```json
{ "form_type": "complaint", "subject_user_id": 1, "reviewer_user_id": 2, "anonymous": true, "score": "2" }
```

匿名记录对无管理权限的人隐藏 `reviewer_user_id`。

`GET /performance/lecturer-status/{user_id}`

只统计 `form_type=complaint` 且 `status=confirmed`。超过 3 次 `incompetent` 为 true，正好 3 次不是。

`GET /performance/stage-cases`

`POST /performance/stage-cases`

```json
{ "user_id": 1, "hire_event_id": 9, "stage": "D5", "role_kind": "sales", "cycle_id": 1 }
```

实例键 `onboarding:{hire_event_id}:{stage}`。同一人同一事件同一阶段再次调用不重复建单。新建考核 `payroll_eligible` 为 false。

`GET /performance/observation-cases`

`POST /performance/observation-cases`

```json
{ "user_id": 1, "end_score": "80", "retriggered": true }
```

期末分 ≥75 且未再次触发为 `released`。否则 `hr_todo`，文案写明不改基本工资。未给期末分为 `open`。

---

## 运行期增量（2026-09-22）

前缀仍为 `/api/v1/performance`。金额与得分用字符串小数。写接口校验权限、状态、`revision` 与数据范围。

### 配置与指标库

`GET /performance/configuration`

需登录。返回 `version`、`departments`（含真实岗位）、`scoring_types`（六种及 `field_schema`）、`data_sources`、`handling_modes`。部门范围按 KPI 模块 data_scope 过滤。

`GET /performance/indicator-definitions?department_id=&job_title=&status=active`

`POST /performance/indicator-definitions`

`PATCH /performance/indicator-definitions/{id}`

`POST /performance/indicator-definitions/{id}/disable`

需要 `kpi:template:manage`。从指标库加入模板：

`POST /performance/templates/{id}/items/from-indicator`

```json
{ "indicator_definition_id": 1, "weight": "20", "order_no": 1 }
```

会复制规则与材料策略快照；之后改指标库不影响已保存模板项。

### 模板发布

`POST /performance/templates/{id}/publish` — 仅 `approved`，范围/指标/阻断问题校验通过后变为 `published`

`POST /performance/templates/{id}/disable` — `published` → `disabled`，不影响历史考核

V2 审批驳回进入 `returned`；legacy 仍回 `draft`。模板 create/update 支持 `scopes`。

### 人员匹配与批量发起

`POST /performance/assessments/match-personnel`

```json
{ "cycle_id": 18, "template_id": 31 }
```

返回 `matched` / `excluded` / `blocked`、`reason_code`、`reason`。缺主管或重复考核为 `blocked`。

`POST /performance/assessments/match-personnel-multi`

```json
{ "cycle_id": 18, "template_ids": [31, 32, 33] }
```

一次返回多个模板的匹配结果：`{ "cycle_id", "results": [ ...单模板结果 ] }`。

`POST /performance/assessment-batches`  
Header：`Idempotency-Key`

```json
{
  "cycle_id": 18,
  "template_id": 31,
  "people": [
    {"user_id": 101, "selected": true, "adjustment_reason": null},
    {"user_id": 104, "selected": true, "adjustment_reason": "经HR确认试用期仍参与"}
  ],
  "employee_due_at": "2026-10-02T18:00:00+08:00",
  "manager_due_at": "2026-10-05T18:00:00+08:00",
  "hr_review_required": false,
  "hr_review_due_at": null,
  "confirm_due_at": "2026-10-08T18:00:00+08:00"
}
```

后端重新匹配；人工纳入/排除必须写原因；阻断人不能选；同键幂等返回原批次。

`POST /performance/assessment-batches/multi`  
Header：`Idempotency-Key`（整组幂等；子批次键为 `{key}|{index}|t{template_id}`）

```json
{
  "cycle_id": 18,
  "batches": [
    { "template_id": 31, "people": [{"user_id": 101, "selected": true}] },
    { "template_id": 32, "people": [{"user_id": 201, "selected": true}] }
  ],
  "employee_due_at": "2026-10-02T18:00:00+08:00",
  "manager_due_at": "2026-10-05T18:00:00+08:00",
  "hr_review_required": false,
  "confirm_due_at": "2026-10-08T18:00:00+08:00"
}
```

同一事务创建多个部门批次；任一失败整组回滚；同一人不能跨批次；同组幂等键重复提交返回原批次列表。

`GET /performance/assessment-batches?cycle_id=18`  
周期进度看板：`batches`（每批人数/待提交/待评分/已完成等）、`departments`（按部门汇总）、`totals`。

`GET /performance/assessment-batches/{batch_id}`  
单批次进度 + `people` 名单（assessment_id、状态、当前处理人）。

### 材料与简化流转

`GET /performance/assessments/{id}/material-tasks`

`PATCH /performance/material-tasks/{id}/draft` `{ "content": "..." }`

`POST /performance/material-tasks/{id}/return` `{ "reason": "..." }`

`POST /performance/material-tasks/{id}/verify`

`POST /performance/assessments/{id}/employee-submit` `{ "revision": 1 }`

`POST /performance/assessments/{id}/manager-submit`

```json
{ "revision": 2, "comment": "达标", "scores": [{"item_id": 1, "score": "85"}] }
```

`POST /performance/assessments/{id}/hr-review` `{ "revision": 3, "approve": true }`

`POST /performance/assessments/{id}/result-confirm` `{ "revision": 4 }`

`POST /performance/assessments/{id}/runtime-appeals` `{ "revision": 4, "reason": "...", "request_score": 90 }`

（旧加权申诉仍用 `/assessments/{id}/appeals`，不含 revision。）

`POST /performance/assessments/{id}/runtime-appeals/resolve`

`GET /performance/assessments/{id}/actions`

`GET /performance/assessments/{id}/runtime-detail`

详情固定含：`status`、`current_handler_*`、`next_step_label`、`allowed_actions`、`material_gaps`、`revision`。

状态：`employee_pending → manager_pending → [hr_review_pending] → employee_confirm_pending → completed`；申诉 `appeal_pending`。revision 不一致返回 409 `KPI_REVISION_CONFLICT`。
