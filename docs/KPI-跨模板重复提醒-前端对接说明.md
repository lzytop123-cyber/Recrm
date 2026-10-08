# 绩效考核 · 跨模板重复提醒（需求4）前端对接说明

| 项 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-10-08 |
| 适用范围 | 考核发起页 · 人员匹配结果展示 |
| 后端仓库 | Recrm（本仓库） |
| 相关接口 | `POST .../assessments/match-personnel`、`POST .../assessments/match-personnel-multi` |

---

## 1. 背景

同一考核周期内，员工可能已被**其它模板**生成考核单（例如讲师已由「讲师月度积分」覆盖，又被「培训部全员」模板匹配到）。

业务要求：

- **不要静默**给同一个人发第二张单而不提示
- **不要直接阻断**（发起人可自行决定是否仍纳入）
- 在匹配名单中给出**提醒标记**

同模板 / 同 family 的重复考核仍按原逻辑 **blocked**，与本需求无关。

---

## 2. 行为约定

| 场景 | `match_status` | 是否可勾选发起 | 说明 |
|---|---|---|---|
| 正常匹配 | `matched` | 是 | 无提醒 |
| 本周期已有**相同模板/同 family**考核 | `blocked` | 否 | `reason_code = duplicate_assessment` |
| 本周期已有**其它模板**考核 | 仍为 `matched`（或原 excluded 等） | 按原 `allowed_action` | 增加提醒字段，**不改** `match_status` |
| 缺主管等 | `blocked` | 否 | 原逻辑不变 |

---

## 3. 字段说明（以本文为准）

### 3.1 人员项 `people[]`

| 字段 | 类型 | 说明 |
|---|---|---|
| `has_other_template_assessment` | `boolean` | `true` = 需展示跨模板提醒 |
| `warnings` | `array` | 提醒列表；无提醒时为 `[]` |
| `warnings[].code` | `string` | 跨模板场景固定为 `"other_template_assessment"` |
| `warnings[].message` | `string` | 可直接展示的文案 |
| `warnings[].assessments` | `array` | 其它模板考核单详情 |
| `warnings[].assessments[].assessment_id` | `number` | 已有考核单 ID |
| `warnings[].assessments[].template_id` | `number \| null` | 其它模板 ID |
| `warnings[].assessments[].template_name` | `string \| null` | 其它模板名称 |
| `warnings[].assessments[].template_code` | `string \| null` | 其它模板 code |
| `warnings[].assessments[].assessment_kind` | `string` | 如 `monthly` |

原有字段不变：`match_status`、`reason_code`、`reason`、`allowed_action`、`existing_assessment_id` 等。

### 3.2 汇总 `summary`

| 字段 | 类型 | 说明 |
|---|---|---|
| `matched` / `excluded` / `blocked` | `number` | 原有计数 |
| `warned` | `number` | 带跨模板提醒的人数（`has_other_template_assessment === true`） |

### 3.3 请勿使用的猜测字段

以下**不是**当前后端返回，请不要作为主判断条件：

- `match_status: "warned"`
- 顶层或人员上的 `warned[]`（数组形态）
- `existing_template_name`
- `has_warning`
- 用 `reason_code === "other_template_assessment"` 判断提醒（跨模板时 `reason_code` 仍是正常匹配码，如 `scope_and_policy_matched`）

若前端已做多形态兜底，可保留兼容，但**以本文字段为准**。

---

## 4. 样例 JSON

```json
{
  "template": {
    "id": 12,
    "name": "培训部月度考核",
    "version": 1,
    "code": "TRAINING_DEPT_V1",
    "family_code": "TRAINING_DEPT"
  },
  "cycle": {
    "id": 3,
    "period_label": "2026-10"
  },
  "summary": {
    "matched": 3,
    "excluded": 0,
    "blocked": 0,
    "warned": 1
  },
  "people": [
    {
      "user_id": 21,
      "name": "王嘉琦",
      "department_id": 9,
      "department_name": "培训与项目交付中心",
      "job_title": "讲师",
      "manager_id": 5,
      "manager_name": "李亚龙",
      "employment_type": "regular",
      "employment_status": "正式",
      "days_in_period": 30,
      "match_status": "matched",
      "reason_code": "scope_and_policy_matched",
      "reason": "部门、岗位及在岗条件均符合",
      "allowed_action": "include_or_exclude",
      "existing_assessment_id": null,
      "has_other_template_assessment": true,
      "warnings": [
        {
          "code": "other_template_assessment",
          "message": "本周期已有其它模板考核：讲师月度积分",
          "assessments": [
            {
              "assessment_id": 101,
              "template_id": 8,
              "template_name": "讲师月度积分",
              "template_code": "LECTURER_MONTHLY_V1",
              "assessment_kind": "monthly"
            }
          ]
        }
      ]
    },
    {
      "user_id": 30,
      "name": "崔吉峰",
      "job_title": "培训总监",
      "match_status": "matched",
      "reason_code": "scope_and_policy_matched",
      "reason": "部门、岗位及在岗条件均符合",
      "allowed_action": "include_or_exclude",
      "existing_assessment_id": null,
      "has_other_template_assessment": false,
      "warnings": []
    }
  ]
}
```

---

## 5. 前端实现建议

1. 匹配名单每一行：当 `has_other_template_assessment === true` 时展示警告标或角标。
2. 文案优先用 `warnings[0].message`；需要详情时再读 `warnings[0].assessments`。
3. **不要**因该提醒禁用勾选；是否纳入仍由发起人决定。
4. 发起提交逻辑不变；后端仍允许纳入（除非另有 `blocked`）。
5. 列表顶部可用 `summary.warned` 展示「N 人已有其它模板考核」。

伪代码：

```ts
const needWarn = person.has_other_template_assessment === true;
const warnText = person.warnings?.[0]?.message ?? '';
// match_status === 'blocked' 才禁用勾选
const canSelect = person.match_status !== 'blocked' && person.allowed_action !== 'none';
```

---

## 6. 联调检查清单

- [ ] 仅有其它模板考核的人：`matched` + 提醒字段齐全，可勾选
- [ ] 同模板重复：`blocked` + `duplicate_assessment`，不可勾选
- [ ] 无跨模板情况：`has_other_template_assessment === false`，`warnings === []`，`summary.warned === 0`
- [ ] 多模板匹配接口返回的每段 `people` 结构一致

---

## 7. 联系与变更

字段以当前后端实现为准。若联调发现差异，请贴一段真实接口响应 JSON，再对齐一版。
