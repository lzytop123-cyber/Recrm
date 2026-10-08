# 入职考核流程优化 · 前端对接说明（2026-10-08）

后端已完成入职考核 P0 优化，发起/详情页请按下列字段与动作对齐。

## 1. 流程变化

```
员工提交 → 主管评分 → 培训部评分/确认 → 复核 → 三方确认（主管+培训部+HR）→ 完成
```

- **M3** 即使没有培训部评分维度，主管提交后仍进入 `training_pending`（`training_ack_only=true`，培训部只需确认/签字，可不传 scores）。
- **完成条件**：入职单必须主管、培训部、HR 三方都确认；任一方未确认时 `status` 仍为 `employee_confirm_pending`。
- **无需员工确认**：入职结果由主管/培训部/HR 确认完成；员工可申诉，但不可 `result-confirm`。
- **合格线 75**：完成后写 `grade_label`=`合格`/`不合格`；不合格挂 `hr_followup`（人事跟进，不自动改雇佣）。

## 2. 新接口

`POST /api/v1/performance/assessments/{id}/party-confirm`

```json
{ "revision": 3, "party": "manager" }
```

`party`：`manager` | `training` | `hr`  

月度员工确认仍用：`POST .../result-confirm`（入职调用会 422）。

## 3. 详情新增字段（runtime-detail）

| 字段 | 说明 |
|------|------|
| `confirmations` | `{ manager, training, hr }`，已确认方为 `{user_id,name,at}`，未确认为 `null` |
| `grade_label` | 完成后有值：`合格` / `不合格` |
| `pass_score` | 入职固定 `75` |
| `hr_followup` | 不合格时：`{needed,resolved,reason,score,stage,...}` |
| `training_ack_only` | `true` 表示培训部节点只需确认（无培训维度，如 M3） |
| `training_required` | 入职单恒为 `true`（含 ack-only） |
| `next_step_label` | 确认阶段会显示「三方确认：主管确认、…」 |

`allowed_actions` 可能出现：`party_confirm`、`training_submit`、`appeal`、`resolve_appeal`（入职申诉培训部也可处理）。入职确认阶段不再给员工 `result_confirm`。

## 4. 前端建议

1. 确认阶段展示三方勾选状态（读 `confirmations`：主管 / 培训部 / HR）。
2. 主管/培训部/HR 按钮均调 `party-confirm`；**不要**给入职单展示「员工确认」。
3. `training_ack_only` 时培训部提交可只带 `revision` + `comment`，不必强求 scores。
4. 完成后展示合格结论；若有 `hr_followup.needed`，给 HR 入口提示「入职不合格待人事跟进」（待办里也会出现）。

## 5. 月度考核

不受影响：月度仍由**被考核人本人** `result-confirm` 直接完成，无三方确认。
