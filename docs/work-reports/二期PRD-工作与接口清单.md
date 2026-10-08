# 二期 PRD 工作与接口清单

> 依据《CRM+OKR公司管理系统二期 PRD（V2.0，2026-09-10）》对照当前代码。  
> 一期销售/合同/项目/工单/排期/固定资产等业务接口已存在，**不在二期重写**。  
> 状态：`已有` = 可直接对接；`要做` = 后端需新写或补齐。  
> 前缀一律 `/api/v1`。

---

## 0. 怎么分工

| 角色 | 做什么 |
|------|--------|
| 后端 | 表、权限、状态机、取数、审批规则、AI 工具与场景接口 |
| 前端 | 页面、表单、列表、调接口、展示引用/草稿/看板 |
| 前端现在就能做 | 现有 CRM 页面、审批中心补退回/转交/重提（接口已有）、绩效现有流程打磨 |
| 前端要等接口 | 本文所有标「要做」的项 |

通用对话**不要**为每个场景再开一套 `/agent/chat`。聊天继续用已有接口；页面一键按钮走场景接口。

---

## 1. 方向一：AI Agent 智能化

### 1.1 企业知识库治理（补一期 FR-088～096）· P0

**要做的事**

- 来源台账：授权人/批准人/范围/状态；同步失败原因；重新同步；授权撤销后停止采集
- 条目状态机：待采集 → 处理中 → 待审核 → 已发布 → 已停用 → 已归档
- 审核发布、免审来源、纠错出新版本（禁止无痕覆盖）
- 采集/解析/向量化任务监控、失败重试（可接现有 `/system/jobs` 死信）
- 问答反馈、纠错处理、无结果缺失登记、运营统计
- 采集入库自动脱敏（身份证/银行卡/手机号）

**已有接口（不要重写）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge/workbench` | 工作台聚合 |
| POST | `/knowledge/ask` | 问答（已有 citations） |
| POST | `/knowledge/articles` | 手工录入 |
| POST | `/knowledge/sources` | 添加来源 |
| POST | `/knowledge/sources/{id}/authorize` | 同步飞书文档 |

**要做的接口**

| 方法 | 路径 | 说明 | 前端 |
|------|------|------|------|
| GET | `/knowledge/sources` | 来源列表 | 来源台账页 |
| GET | `/knowledge/sources/{id}` | 来源详情 | 详情 |
| GET | `/knowledge/sources/{id}/sync-status` | 最近同步、条目数、失败原因 | 状态条 |
| POST | `/knowledge/sources/{id}/resync` | 重新同步 | 按钮 |
| POST | `/knowledge/sources/{id}/revoke` | 失效/撤销授权 | 按钮 |
| GET | `/knowledge/entries` | 条目列表（来源/类型/状态/部门/时间） | 治理列表 |
| GET | `/knowledge/entries/{id}` | 详情：原文、分块、标签、权限 | 详情 |
| POST | `/knowledge/entries/{id}/review` | 审核 | 审核 |
| POST | `/knowledge/entries/{id}/publish` | 发布 | 发布 |
| POST | `/knowledge/entries/{id}/disable` | 停用 | 下架 |
| POST | `/knowledge/entries/{id}/archive` | 归档（不物理删除） | 归档 |
| GET | `/knowledge/entries/{id}/versions` | 版本列表 | 版本 |
| POST | `/knowledge/entries/{id}/corrections` | 纠错 → 新版本待审 | 纠错 |
| GET | `/knowledge/jobs` | 采集/解析/索引任务 | 任务监控 |
| POST | `/knowledge/jobs/{id}/retry` | 失败重试 | 重试 |
| POST | `/knowledge/ask/{ask_id}/feedback` | 有用/无用/纠错 | 问答底部 |
| GET | `/knowledge/feedback` | 反馈处理队列 | 管理员 |
| PATCH | `/knowledge/feedback/{id}` | 处理反馈 | 管理员 |
| GET | `/knowledge/gaps` | 知识缺失清单 | 运营 |
| GET | `/knowledge/stats` | 总量、热度、引用率、无结果率、部门贡献 | 统计 |

### 1.2 AI Agent 平台（新增 FR-201～210）· P1

**要做的事**

- 通用对话保持现有 SSE；补知识检索工具（对话里能答制度）
- 5 个场景：S1 问答升级、S2 日报、S3 跟进摘要、S4 工单推荐、S5 审批预审
- Prompt 模板版本化、调用审计、token 预算、场景一键停用
- AI 以当前用户身份调工具，禁止越权；问答必须引用来源，没把握就拒答

**已有接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/chat` | SSE 多轮对话 |
| POST | `/agent/confirm` | 写操作确认 |
| GET | `/agent/conversations` | 会话列表 |
| GET | `/agent/history/{id}` | 会话历史 |

内部工具已有：项目、OKR、审批查询/操作、客户。缺：知识检索、日报数据、工单相似检索。

**要做的接口**

| 场景 | 方法 | 路径 | 入参要点 | 出参要点 | 前端入口 |
|------|------|------|----------|----------|----------|
| S1 | POST | `/knowledge/ask/{ask_id}/feedback` | useful / useless / correction | — | 知识库问答 |
| S1 | — | Agent 内部工具 `search_knowledge` | 无独立 HTTP | 引用+拒答 | 悬浮助手 |
| S2 | POST | `/agent/scenes/daily-report` | `date` 或 `week` | 草稿：今日工作/明日计划/产出/工时/里程碑（全是系统事实） | 待办或助手「生成日报」 |
| S2 | POST | `/agent/scenes/daily-report/{id}/submit` | 确认后的正文 | 提交结果 | 草稿确认 |
| S3 | POST | `/agent/scenes/followup-summary` | `lead_id` / `customer_id` / `opportunity_id` | 摘要卡片+下一步建议（只提示不落业务动作） | 线索/客户/商机详情 |
| S4 | GET | `/tickets/{id}/recommendations` | — | 相似工单+知识方案+来源 | 工单详情 |
| S5 | GET | `/approvals/{id}/precheck` | — | 摘要、风险、同类参考、模型版本/时间 | 审批详情 |
| S5 | POST | `/approvals/{id}/auto-pass` | 可选；也可引擎内自动过 | L1 低风险自动通过 | 一般不给按钮 |

**平台管理（AI 管理员）**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/ai/prompts` | Prompt 模板列表/创建 |
| GET | `/ai/prompts/{id}` | 模板详情与版本 |
| POST | `/ai/prompts/{id}/publish` | 发布版本 |
| GET | `/ai/calls` | 调用审计（用户、场景、模型、token、耗时、摘要、成本） |
| GET | `/ai/calls/{id}` | 单次详情 |
| GET / PUT | `/ai/budgets` | 部门/人月度 token 限额 |
| GET | `/ai/scenes` | 场景清单与开关 |
| PATCH | `/ai/scenes/{code}` | 一键停用（停用后审批回退纯人工） |

### 1.3 智能审批（规则已有，智能层要做）· P0 规则补齐 / P1 预审

**要做的事**

- 规则：草稿/发布/停用、节点（依次/会签）、金额/类型/部门分支、时限催办、抄送 —— **CRUD 已有，超时未真正落 `due_at`**
- AI 预审报告挂在审批单上并留痕
- L1 低风险自动通过 + ≥10% 抽查；L2 预审+人工；L3 纯人工
- 智能催办：预测超时 → 飞书话术 → 深链回系统
- AI 挂了必须回退纯人工，不堵审批

**已有接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/approval-rules` | 列表/创建 |
| GET/PATCH/DELETE | `/approval-rules/{id}` | 详情/改/删 |
| POST | `/approval-rules/{id}/publish` | 发布 |
| POST | `/approval-rules/{id}/disable` | 停用 |
| GET | `/approvals`、`/approvals/stats`、`/approvals/{id}` | 中心列表/详情 |
| POST | `/approvals/{id}/approve\|reject\|return\|transfer\|remind\|withdraw\|resubmit` | 操作（前端尚未全部封装 return/transfer/resubmit） |

**要做的接口 / 补齐**

| 方法 | 路径 | 说明 |
|------|------|------|
| — | 引擎内：任务 `due_at`、实例 `next_due_at` | 列表可按逾期筛；`meta.due_at` / `overdue` |
| POST | `/approvals/{id}/remind` | **已有，要加 30 分钟频控 + 飞书推送** |
| GET | `/approvals/{id}/precheck` | 同 1.2 S5 |
| POST | `/approvals/{id}/auto-pass` | L1；限额走系统配置，调整留痕 |
| GET | `/approvals/spot-checks` | L1 事后抽查队列 |
| POST | `/approvals/spot-checks/{id}/review` | 抽查结论 |

---

## 2. 方向二：人事板块优化

### 2.1 劳动合同（补一期 FR-080～081）· P1

**要做的事**

- 独立合同台账（不要只用员工表上那几个字段）
- 到期前 90/30/7 天提醒本人+综合管理部；试用期到期提醒
- 续签审批、历史版本保留、扫描件受控下载

**已有**

员工字段 `contract_type / contract_start / contract_end / contract_status`，详情页只读展示，**没有台账接口**。

**要做的接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/hr/contracts` | 台账（部门、状态、到期区间） |
| POST | `/hr/contracts` | 新建 |
| GET | `/hr/contracts/{id}` | 详情 |
| PATCH | `/hr/contracts/{id}` | 编辑 |
| POST | `/hr/contracts/{id}/renew` | 发起续签（走审批中心） |
| GET | `/hr/contracts/expiring` | 到期预警列表 |
| GET | `/hr/contracts/{id}/file` | 受控下载（短时签名） |

### 2.2 转岗与离职（补一期 FR-082～083、086～087）· P1

**要做的事**

- 转岗：申请 → 双方负责人审批 → 改组织与数据权限 → 写入任职历史
- 离职交接单：线索/客户/商机转移、任务转派、资产归还待办、权限回收
- 未完结事项（线索、项目、工单、审批、资产、排期）清完才能完成交接
- 接收人逐项确认，部门负责人签字归档

**已有**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/org/employees/{id}/history` | 任职经历（转岗生效后往这里写） |
| PATCH | `/org/employees/{id}` | 改部门/状态（转岗生效由后端调，不要前端直改当流程） |

**要做的接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/hr/transfers` | 转岗申请 |
| GET | `/hr/transfers`、`GET /hr/transfers/{id}` | 列表/详情 |
| POST | `/hr/resignations` | 发起离职 |
| GET | `/hr/resignations/{id}` | 详情 |
| GET | `/hr/handovers/{id}` | 交接单+一致性检查结果 |
| POST | `/hr/handovers/{id}/items/{item_id}/assign` | 指定接收人 |
| POST | `/hr/handovers/{id}/items/{item_id}/confirm` | 接收人确认 |
| POST | `/hr/handovers/{id}/complete` | 完成交接（检查未通过则 400） |

离职生效时后端自动：禁用账号、清例外授权与委托（已有 `/system/delegations`）。

### 2.3 假勤（新增 FR-211～215）· P2

**要做的事**

- 请假/加班/补卡/外勤走审批中心
- 年假等余额台账、调入结转
- 飞书考勤事实 + 本系统审批单 → 月度汇总，供绩效出勤和工资加减项

**已有**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/org/employees/{id}/attendance` | 飞书考勤汇总 |
| POST | `/org/feishu/attendance/sync` | 拉飞书打卡 |

**要做的接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/hr/leave-requests` | 假勤申请列表/提交 |
| GET | `/hr/leave-requests/{id}` | 详情 |
| GET | `/hr/leave-balances` | 本人或（有权限）部门余额 |
| PATCH | `/hr/leave-balances/{id}` | 调入/结转（综合管理） |
| GET | `/hr/attendance/monthly` | 月度汇总 |

### 2.4 工资条（补一期 FR-077～079）· P0

**要做的事**

- 把现有「工资生成」结果做成员工可看的工资条：固定工资、绩效工资、加减项
- 锁定 + 财务复核后发布；员工本人查看/下载（短时地址+水印）
- 更正走新版本，原版保留；主管能否看明细待确认 D2

**已有（周期状态，不是工资条）**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/performance/cycles/payroll/generate` | 生成批次 |
| POST | `/performance/cycles/payroll/review` | 财务复核 |
| POST | `/performance/cycles/payroll/publish` | 发布标记 |

**要做的接口**

| 方法 | 路径 | 说明 | 前端 |
|------|------|------|------|
| GET | `/payslips/me` | 本人工资条列表 | 员工端 |
| GET | `/payslips/{id}` | 明细 | 详情 |
| GET | `/payslips/{id}/download` | 短时下载 | 下载 |
| GET | `/payslips` | 全量（财务/经营） | 财务 |
| POST | `/payslips/{id}/correct` | 更正版本 | 财务 |

### 2.5 人事看板（新增 FR-216～218）· P2

编制在职、入离职率、合同到期分布、工时利用率、人工成本（脱敏）、离职交接异常。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/hr/dashboard` | 人事看板聚合 |

---

## 3. 方向三：KPI 与工作量量化

### 3.1 绩效规则引擎（补一期 FR-065～066）· P0

**要做的事**

- 指标定义库：编码、口径、单位、数据源、公式、版本
- 岗位权重可配（默认 KPI 60% / OKR 30% / 协作 10%，客观数据 ≥50%）
- 封顶保底、评分人、工资系数表（一期已定，直接用）
- 部门初始模板可配，**不改代码就能调指标**（KPI 表 I1 未提供，先占位）

**已有**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/performance/templates` | 模板列表/新建 |
| GET/PUT | `/performance/templates/{id}` | 详情/编辑 |
| POST | `/performance/templates/{id}/fork` | 部门派生 |
| POST | `/performance/templates/{id}/submit` | 提交审批 |
| POST | `/performance/templates/{id}/approve` | 审批模板 |

模板项已有 `data_source = system \| okr \| manual`，还不是独立指标库+绑定表。

**要做的接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/performance/indicators` | 指标定义库 |
| GET / PATCH | `/performance/indicators/{id}` | 详情/改口径（改则升版本） |
| POST | `/performance/indicators/{id}/bind` | 绑部门或岗位：目标值、权重 |
| GET | `/performance/indicator-bindings` | 某周期/部门绑定一览 |

### 3.2 自动取数与快照（新增 FR-220～227）· P0

**要做的事**

- 定量指标绑一期事实：工时、项目、线索/商机、合同/回款、工单 SLA、排期课时
- 周期锁定时生成每人每指标快照，不可回改；更正走新版本
- 环比超阈值打标，校准必须处理；造假一票否决；同一成果不重复计分
- 外部账号数据：填报+附件+审批，预留对接

**要做的接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/performance/cycles/{id}/snapshot` | 批量取数落快照 |
| GET | `/performance/snapshots` | 按周期/人查询 |
| POST | `/performance/snapshots/{id}/correct` | 更正版本 |
| POST | `/performance/external-entries` | 外部数据填报（走审批） |

### 3.3 考核周期（补一期 FR-065～079）· 大半已有

流程：创建 → 快照 → 自评 → 上级评 → 校准 → 确认/申诉 → 锁定 → 工资 → 复核 → 工资条。  
申诉未完成不得锁定、不得发工资条。

**已有接口**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/performance/cycles` | 周期列表/创建 |
| POST | `/performance/cycles/{id}/generate` | 批量生成考核单 |
| GET | `/performance/cycles/{id}/detail` | 归档明细 |
| GET | `/performance/assessments/mine` | 我的 |
| GET | `/performance/assessments/team` | 团队 |
| GET | `/performance/assessments/{id}/detail` | 明细（含分项） |
| POST | `/performance/assessments/{id}/self-rate` | 自评 |
| POST | `/performance/assessments/{id}/manager-rate` | 上级评 |
| POST | `/performance/assessments/{id}/appeals` | 申诉 |
| POST | `/performance/appeals/{id}/resolve` | 处理申诉 |
| POST | `/performance/cycles/calibrate` | 校准 |
| POST | `/performance/cycles/lock` | 锁定 |
| POST | `/performance/cycles/reset` | 重置 |
| POST | `/performance/cycles/payroll/*` | 工资三步 |

**要补的行为（不一定新路径）**

- `lock`：有未结申诉则 409
- `detail`：原始分与校准分分列（表里已有字段，核对返回）
- 提成录入（待确认 D3）：建议 `POST /performance/commissions`

### 3.4 工作量看板（新增 FR-228～231）· P2

| 方法 | 路径 | 说明 | 受众 |
|------|------|------|------|
| GET | `/workload/me` | 工时分布、任务、项目贡献、指标趋势 | 本人、直属上级 |
| GET | `/workload/department` | 人均产出、负荷、完成率、校准前后 | 部门负责人 |
| GET | `/workload/company` | 各部门分布、人效、异常 | 经营层 |

---

## 4. 前端对照（给前端同事）

| 页面/入口 | 等哪些新接口 | 可先用已有 |
|-----------|--------------|------------|
| 知识库治理 | `/knowledge/sources*`、`/entries*`、`/jobs`、`/feedback`、`/stats` | workbench / ask / 手工录入 |
| 悬浮 AI 助手 | 可先不动；S2 加「生成日报」按钮 | `/agent/chat` 等 4 个 |
| 审批详情 | `/approvals/{id}/precheck`；列表展示逾期 | 通过/驳回/撤回/催办 |
| 审批中心补操作 | 无新后端 | 封装 `return` / `transfer` / `resubmit` |
| 工单详情 | `GET /tickets/{id}/recommendations` | 现有工单 CRUD |
| 线索/客户详情 | `POST /agent/scenes/followup-summary` | 现有跟进 |
| 劳动合同台账 | `/hr/contracts*` | 员工详情只读字段可先留 |
| 转岗离职 | `/hr/transfers`、`/resignations`、`/handovers*` | 任职历史只读 |
| 假勤 | `/hr/leave-*`、`/attendance/monthly` | 飞书考勤汇总 |
| 我的工资条 | `/payslips/me` | 无 |
| 人事看板 | `/hr/dashboard` | `/org/stats` 仅组织人数 |
| 绩效规则 | `/performance/indicators*` | 现有 templates |
| 考核流程 | 快照、申诉阻断锁定 | 自评/上级评/校准/锁定已通 |
| 工作量看板 | `/workload/*` | 无 |
| AI 配置（管理员） | `/ai/prompts`、`/calls`、`/budgets`、`/scenes` | 无 |

---

## 5. 建议开发批次（与 PRD 第八章一致）

| 批次 | 周次 | 后端先做 | 前端跟上 |
|------|------|----------|----------|
| **P0** | 1–6 | 知识治理接口；指标库+快照；工资条；审批 `due_at` | 知识审核页、工资条页、绩效模板/周期打磨 |
| **P1** | 5–12 | S1 知识工具+反馈；S2～S5 场景；合同/转岗离职 | 助手按钮、审批预审、工单推荐、人事流程页 |
| **P2** | 10–16 | 假勤、人事看板、工作量看板 | 三个看板 + 假勤申请 |
---


## 6. 开发前未决（不阻塞搭接口，会卡住规则数值）


| 编号 | 问题 | 影响 |
|------|------|------|
| I1 / D1 | 各部门现行 KPI 表 | 指标库先占位模板 |
| I2 / D2 | 主管能否看本部门工资明细 | `/payslips` 权限 |
| I3 / D3 | 市场部项目提成怎么录 | `/performance/commissions` |
| I4 / D4 | 跨部门项目 KPI 归属 | 快照拆分规则 |
| I5 / D5 | 模型选型与预算 | `/ai/budgets`、网关 |
| I6 / D6 | L1 自动通过限额 | auto-pass 配置 |

---

## 7. 明确不做（二期边界）

多租户、完整招聘、社保公积金/总账/个税、自由拖拽流程设计器、AI 替代高风险审批、采集飞书个人聊天、外部客户登录。


知识库首页的一个页面
来源台账
