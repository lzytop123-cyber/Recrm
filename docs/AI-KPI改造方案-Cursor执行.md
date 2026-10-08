# 绩效模块扩展方案 · 加入 KPI 指标模板 · Cursor 执行文档

> **背景**：本仓库已有 `performance` 模块（月度考核 + 自评/主管评/校准/申诉/薪酬联动），已经跑通闭环。**这份方案不是新起 KPI 模块，是给现有绩效补两块拼图**：可配置的**指标模板**、细粒度的**多条 KPI 项**。
>
> **原型**：`docs/kpi-flow-prototype.html`（浏览器打开，7 屏可交互）。原型里的字段名/流程/交互，最终落到扩展后的 `performance_*` 表上，不用新起 `kpi_*` 命名。
>
> **交付给 Cursor**：这份 md + 原型 HTML。

---

## 0. 给 Cursor 的开场白

**把这段作为第一条指令：**

> 你要**扩展本仓库现有的绩效模块**（`app/models/performance.py`、`app/api/v1/performance.py`、`app/services/performance.py`），加两个能力：
> 1. HR 可配置的**指标模板**（HR 基础 → 部门 fork）
> 2. 每份考核单里的**细粒度 KPI 项**（现在只有 okr/kpi/behavior 三个大类分数）
>
> 严格按下面的**硬性约束**和**参考文件**来。**一次只做一个 Task**，做完让我验收再进下一个。遇到不确定直接问，不要猜。

### 硬性约束

- ✅ **用 Alembic** — 本仓库有 46 个 migration 在跑，新表新字段都写 migration，命名跟 `d6e7f8a9b0c1_create_performance.py` 对齐
- ✅ **接现有审批引擎** — `ApprovalRule` + `ApprovalInstance` + `ApprovalTask`（`models/approval_rule.py` / `models/approval_flow.py`），KPI 三条流程按 `AP-*` 命名规则加进 `seed.seed_approval_rules`
- ✅ **API 挂在 `/api/v1/performance/` 下扩展** — 不新建 router，不新起前缀
- ✅ **主管关系用 `user.manager_id`** — 见 `models/user.py:47`，隔级递归查
- ✅ **权限用 `PermissionChecker`** — 新增 `kpi:template:manage`、`kpi:template:write`、复用 `okr:view` 兜底
- ✅ **前端对齐 `views/okrs/`** 的风格，新建 `views/performance/`
- ✅ **保留现有字段** — `PerformanceAssessment.okr_score / kpi_score / behavior_score` 不删，改为**从 items 加权算出来的汇总缓存**
- ❌ **不新起 `kpi_*` 表名** — 全部 `performance_*` 前缀，避免与 `PerformanceAssessment.kpi_score` 语义冲突
- ❌ **不写自定义状态机** — `PerformanceAssessment.status` 派生自审批实例
- ❌ **不一次做完** — 按 §9 的 Task 分段，每个都跑起来再进

### 必读的现有代码

| 用途 | 文件 |
|---|---|
| 绩效模型 | `backend/app/models/performance.py` |
| 绩效服务 | `backend/app/services/performance.py` |
| 绩效 API | `backend/app/api/v1/performance.py` |
| 绩效 schema | `backend/app/schemas/performance.py` |
| 审批引擎模型 | `backend/app/models/approval_flow.py`、`backend/app/models/approval_rule.py` |
| 审批引擎 seed | `backend/app/seed_approval_flow.py`、`backend/app/seed.py` (搜 `seed_approval_rules`) |
| user 表主管字段 | `backend/app/models/user.py:47` |
| Alembic 迁移风格 | `backend/alembic/versions/d6e7f8a9b0c1_create_performance.py` |
| 前端绩效 API 层 | `frontend/src/api/performance.ts` |
| 前端 OKR view 风格 | `frontend/src/views/okrs/` |
| 前端 API 请求封装 | `frontend/src/api/request.ts`（通过 `import request from './request'` 用） |
| 前端布局 | `frontend/src/layouts/MainLayout.vue` |

---

## 1. 现状盘点 + 差距

### 已经有的（不动）

- `PerformanceCycle` — 月度考核周期（`period_label = '2026-07'`，`rule_version`，状态机 `assessing → calibrating → locked → payroll → published`）
- `PerformanceAssessment` — 每个员工的考核单，包含 `self_score` / `okr_score` / `kpi_score` / `behavior_score` / `manager_score` / `final_score` / `grade` / `coefficient` / `bonus_amount`，状态机 `pending_self → pending_manager → pending_calibration → appealing → completed`
- `PerformanceAppeal` — 申诉
- API：`/performance/workbench`、`/performance/assessments/{id}/self-rate`、`/manager-rate`、`/appeals`、`/cycles/calibrate`、`/lock`、`/payroll/*`
- 前端：`api/performance.ts` 全套调用封装
- 审批引擎：完整可用（`ApprovalRule.nodes_json` 存节点，`ApprovalInstance` 跑实例，会签/驳回/自审跳过/超时都处理了）

### 缺的（要补）

1. **HR 可配置模板** — 现在指标是写死的三段（okr/kpi/behavior），加 `performance_templates` + `performance_template_items` 让 HR / 部门经理配指标名 · 权重 · 数据源 · 目标值
2. **细粒度指标** — 加 `performance_assessment_items`，一份 assessment 下 n 条真实指标（例如：销售额 40% + 回款率 20% + OKR 完成度 20% + 团队协作 10% + 客户满意度 10%）
3. **数据源自动取值** — customer/deals 聚合、OKR KR 完成率、手填三种数据源，落到 item 上冻结
4. **周期支持季度** — 现在只有月度（`period_label='2026-07'`），加个 `cycle_type='monthly'|'quarterly'` 字段
5. **前端 UI** — 现在 `views/performance/` 不存在（只有 `views/okrs/`），要补上 7 个 view + 二级路由

### 保留兼容

`PerformanceAssessment.okr_score / kpi_score / behavior_score / self_score` 全部**保留**，改为 **items 加权后的汇总缓存**：
- `okr_score` = 所有 `data_source='okr'` items 的加权和
- `kpi_score` = 所有 `data_source='system'` items 的加权和
- `behavior_score` = 所有 `data_source='manual'` 且需上级评的 items 的加权和
- `self_score` = 所有员工可填 items 的加权和（保留原语义）

这样：现有工作台/薪酬联动**代码零改动**能继续跑。

---

## 2. 数据模型改造

### A. `PerformanceCycle` — 加字段

```python
# 新增字段
cycle_type: Mapped[str] = mapped_column(String(20), default="monthly", index=True)
# 'monthly' | 'quarterly' | 'yearly'
default_template_id: Mapped[Optional[int]] = mapped_column(
    Integer, ForeignKey("performance_templates.id"), nullable=True
)
```

### B. `PerformanceAssessment` — 加字段

```python
# 新增字段
template_id: Mapped[Optional[int]] = mapped_column(
    Integer, ForeignKey("performance_templates.id"), nullable=True, index=True
)
approval_instance_id: Mapped[Optional[int]] = mapped_column(
    Integer, ForeignKey("approval_instances.id"), nullable=True, index=True
)
```

### C. 新增 `PerformanceTemplate`

```python
class PerformanceTemplate(Base):
    """绩效指标模板（HR 基础 + 部门派生）"""
    __tablename__ = "performance_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)

    base_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=True,
        comment="null=HR 基础模板；非 null=部门 fork 自哪份基础模板"
    )
    owner_type: Mapped[str] = mapped_column(String(20), default="hr", index=True)
    # 'hr' | 'dept'
    owner_dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True
    )

    cycle_type: Mapped[str] = mapped_column(String(20), default="monthly")
    # 'monthly' | 'quarterly' | 'yearly'

    rules_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="HR 基础模板才有：权重上下限 / 数据源白名单 / 评分规则"
    )
    # {"weight_bounds": {"system": [40, 60]}, "allowed_sources": ["system", "okr", "manual"]}

    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # 'draft' | 'pending_review' | 'approved' | 'archived'

    approval_instance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approval_instances.id"), nullable=True
    )

    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at, updated_at
```

### D. 新增 `PerformanceTemplateItem`

```python
class PerformanceTemplateItem(Base):
    """模板下的一条指标定义"""
    __tablename__ = "performance_template_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_templates.id"), nullable=False, index=True
    )
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # "销售额"
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # 40.00

    data_source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 'system' | 'okr' | 'manual' | 'self_manual'
    source_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # 'customer.deals' | 'customer.payments' | 'okr.kr_progress' | 'survey'

    target_value: Mapped[Optional[str]] = mapped_column(String(60))
    # "3000000" | "≥90%" | null
    score_rule: Mapped[Optional[str]] = mapped_column(String(200))
    # "达成率 × 100，上限 120" | "avg(kr.progress) × 100" | "问卷平均分"

    hint: Mapped[Optional[str]] = mapped_column(Text)
    created_at, updated_at
```

### E. 新增 `PerformanceAssessmentItem`

```python
class PerformanceAssessmentItem(Base):
    """一份考核单里的一条 KPI 项（从 template_item 复制 + 冻结实际值）"""
    __tablename__ = "performance_assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("performance_assessments.id"), nullable=False, index=True
    )
    template_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("performance_template_items.id"), nullable=True,
        comment="追溯来源，只读"
    )
    order_no: Mapped[int] = mapped_column(Integer, default=0)

    # 从 template_item 复制过来（冻结快照）
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(String(120))
    target_value: Mapped[Optional[str]] = mapped_column(String(60))
    score_rule: Mapped[Optional[str]] = mapped_column(String(200))

    # 运行时数据
    actual_value: Mapped[Optional[str]] = mapped_column(String(60))
    # 系统聚合值快照，例如 "2760000" 或 "87.3%"
    system_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    self_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    self_comment: Mapped[Optional[str]] = mapped_column(Text)
    leader_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    leader_comment: Mapped[Optional[str]] = mapped_column(Text)
    final_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    # 归档时冻结

    created_at, updated_at
```

### 关系图

```
PerformanceCycle 1 ──n PerformanceAssessment 1 ──n PerformanceAssessmentItem
   │ default_template_id       │ template_id                │ template_item_id (追溯)
   ▼                           ▼                            ▼
PerformanceTemplate 1 ────────────────────────────n PerformanceTemplateItem
   │ base_template_id → self
   │ owner_type: hr | dept
```

---

## 3. Alembic 迁移策略

### 一次性写一个 migration

命名对齐：`f0a1b2c3d4e5_extend_performance_templates.py`（八位 hash + 语义名，跟 `d6e7f8a9b0c1_create_performance.py` 一样）。

内容：
1. `op.create_table('performance_templates', ...)`
2. `op.create_table('performance_template_items', ...)`
3. `op.create_table('performance_assessment_items', ...)`
4. `op.add_column('performance_cycles', sa.Column('cycle_type', ...))`
5. `op.add_column('performance_cycles', sa.Column('default_template_id', ...))`
6. `op.add_column('performance_assessments', sa.Column('template_id', ...))`
7. `op.add_column('performance_assessments', sa.Column('approval_instance_id', ...))`

**SQLite `add_column` 用 batch mode**（跟仓库现有 migration 一致）：

```python
with op.batch_alter_table('performance_assessments') as batch:
    batch.add_column(sa.Column('template_id', sa.Integer, sa.ForeignKey('performance_templates.id'), nullable=True))
```

### Backfill 现有数据

同一个 migration 的 `upgrade()` 末尾：

```python
# 老 assessment 没 template_id，用 null 保留（老工作台代码继续读 okr_score/kpi_score/behavior_score 汇总字段）
# 新周期开始时才关联新模板
pass
```

不做数据迁移，老 assessment 继续按老三段字段跑，新 assessment（有 template_id 的）走细粒度 items。

### 回滚

`downgrade()`：drop table 三张 + drop column 四个。

---

## 4. 审批引擎接入

### 三条新 `ApprovalRule` 加进 `seed.seed_approval_rules`

用 `AP-*` 命名对齐现有规则（`AP-01/AP-02/AP-18/AP-21` 等）：

```python
# seed.py 里 seed_approval_rules 函数末尾追加
KPI_RULES = [
    {
        "code": "AP-KPI-01",
        "name": "KPI 考核评分流程",
        "biz_type": "kpi_review",
        "timeout_hours": 72,
        "nodes_json": json.dumps([
            {"seq": 1, "name": "员工自评", "node_type": "assignee",
             "roles": [], "assignee_expr": "biz.user_id"},
            {"seq": 2, "name": "上级评分", "node_type": "assignee",
             "roles": [], "assignee_expr": "biz.user.manager_id"},
            {"seq": 3, "name": "隔级复核", "node_type": "assignee",
             "roles": [], "assignee_expr": "biz.user.manager.manager_id"},
            {"seq": 4, "name": "HR 归档", "node_type": "approve",
             "roles": ["hr", "hr_manager"]},
        ], ensure_ascii=False),
    },
    {
        "code": "AP-KPI-02",
        "name": "绩效模板审批",
        "biz_type": "performance_template_review",
        "timeout_hours": 48,
        "nodes_json": json.dumps([
            {"seq": 1, "name": "HR 审核", "node_type": "approve",
             "roles": ["hr", "hr_manager"]},
        ], ensure_ascii=False),
    },
    {
        "code": "AP-KPI-03",
        "name": "KPI 申诉流程",
        "biz_type": "kpi_appeal",
        "timeout_hours": 96,
        "nodes_json": json.dumps([
            {"seq": 1, "name": "隔级复核", "node_type": "assignee",
             "roles": [], "assignee_expr": "biz.assessment.user.manager.manager_id"},
            {"seq": 2, "name": "HR 决议", "node_type": "approve",
             "roles": ["hr", "hr_manager"]},
        ], ensure_ascii=False),
    },
]
```

### 关键约定

- `PerformanceAssessment.approval_instance_id` 挂在 `AP-KPI-01` 的实例
- `PerformanceTemplate.approval_instance_id` 挂在 `AP-KPI-02` 的实例
- `PerformanceAppeal` 借助现有表，新增 `approval_instance_id` 字段挂 `AP-KPI-03`
- **`PerformanceAssessment.status` 从 `ApprovalInstance.current_seq` 派生**：
  - seq=1 → `pending_self`
  - seq=2 → `pending_manager`
  - seq=3 → `pending_manager`（隔级复核复用同状态）
  - seq=4 → `pending_calibration`
  - `INSTANCE_APPROVED` → `completed`

---

## 5. 数据源逻辑

新建 `services/performance_data_source.py`：

```python
def resolve_actual(item: PerformanceAssessmentItem, assessment: PerformanceAssessment, db) -> tuple[str | None, Decimal | None]:
    """返回 (实际值显示串, 系统得分)。手填项返回 (None, None)"""
    match item.data_source:
        case 'system':
            return _resolve_system(item, assessment, db)
        case 'okr':
            return _resolve_okr(item, assessment, db)
        case 'manual' | 'self_manual':
            return None, None
```

### `_resolve_system`

按 `source_ref` 派发到不同聚合：
- `customer.deals` → `SUM(deals.amount) WHERE deals.owner_id = assessment.user_id AND close_date BETWEEN cycle.start AND cycle.end` → 达成率 → 得分
- `customer.payments` → 到账/开票比 → 得分
- 其他 ref 一个 case 一个实现

### `_resolve_okr`

读现有 OKR 模块（`models/okr.py` 已存在）：
- `AVG(kr.progress) WHERE kr.owner_user_id = assessment.user_id AND kr.cycle_label overlaps cycle.period_label`

### 冻结时机

- **自评开启时**：跑一次写入 `actual_value` + `system_score`
- **归档（`ApprovalInstance` 通过时）**：再跑一次固化到 `final_score`，之后只读

---

## 6. API 扩展

**全部加到现有 `/api/v1/performance/` 路由下**，不新建 router。

```python
# 模板管理
GET    /api/v1/performance/templates                       列表
POST   /api/v1/performance/templates                       建 (HR 基础)
POST   /api/v1/performance/templates/{id}/fork             部门派生
PUT    /api/v1/performance/templates/{id}                  编辑
POST   /api/v1/performance/templates/{id}/submit           部门提交审批
POST   /api/v1/performance/templates/{id}/approve          HR 审批

# 周期 · 复用现有 workbench/calibrate/lock，新增：
POST   /api/v1/performance/cycles                          建周期（选模板 + 类型）
POST   /api/v1/performance/cycles/{id}/generate            批量生成 assessment + items
GET    /api/v1/performance/cycles/{id}/detail              HR 归档明细页

# 考核单 · 扩展现有 self-rate / manager-rate（新老兼容）
POST   /api/v1/performance/assessments/{id}/self-rate      # ← 现有接口
                                                          # payload 增加 items: [{item_id, self_score, self_comment}]
POST   /api/v1/performance/assessments/{id}/manager-rate   # ← 现有接口
                                                          # payload 增加 items: [{item_id, leader_score, leader_comment}]

# 新增查询
GET    /api/v1/performance/assessments/mine                我的历史（含趋势 + items）
GET    /api/v1/performance/assessments/team                团队视图（?scope=direct|dept）
GET    /api/v1/performance/assessments/{id}/detail         明细含 items + 审批时间线
```

### schema 兼容策略

`SelfRateRequest` / `ManagerRateRequest` 加 `items: list[ItemRateIn] | None = None`。**旧客户端（不传 items）**：继续走原逻辑更新 `self_score` / `okr_score` 等汇总字段。**新客户端（传 items）**：写 item 明细，然后回填汇总字段。

---

## 7. 前端结构 + 路由

### 现状

- `frontend/src/api/performance.ts` ✅ 已有
- `frontend/src/views/performance/` ❌ 不存在
- `frontend/src/views/okrs/` ✅ 有（作为 view 风格参考）

### 新增结构

```
frontend/src/
├── api/
│   └── performance.ts                    # ← 扩展现有，加 templates/mine/team/detail
├── layouts/
│   └── PerformanceAdminLayout.vue        # 新增：HR 后台二级 Layout
├── views/performance/
│   ├── PerformanceMyView.vue             # 06 屏 · 我的绩效
│   ├── PerformanceSelfReviewView.vue     # 03 屏 · 自评
│   ├── PerformanceTeamView.vue           # 07 屏 · 团队
│   ├── PerformanceScoringView.vue        # 04 屏 · 上级评分
│   ├── PerformanceCyclesView.vue         # 01 屏 · 周期管理
│   ├── PerformanceCycleDetailView.vue    # 05 屏 · 归档校准
│   ├── PerformanceTemplatesView.vue      # 02 屏 · 模板列表
│   ├── PerformanceTemplateEditView.vue   # 02 屏 · 模板编辑
│   └── PerformanceDetailView.vue         # 共享只读详情
├── components/performance/
│   ├── PerformanceItemCard.vue           # 指标卡（三模式）
│   ├── PerformanceFlowStepper.vue        # 状态 stepper
│   ├── PerformanceTrendChart.vue         # 分数趋势 SVG
│   ├── PerformanceGradeBadge.vue         # A+/A/B/C/D 徽章（按现有 grade 值）
│   └── PerformanceApprovalTimeline.vue   # 审批时间线
├── stores/
│   └── performance.ts                    # Pinia
└── router/
    └── performance.ts                    # 挂进 router/index.ts
```

### 路由（`/performance/admin` 二级嵌套）

```ts
// router/performance.ts
export const performanceRoutes = [
  {
    path: '/performance',
    children: [
      { path: 'mine', component: () => import('@/views/performance/PerformanceMyView.vue') },
      { path: 'mine/assessments/:id', component: () => import('@/views/performance/PerformanceSelfReviewView.vue') },
      { path: 'team', component: () => import('@/views/performance/PerformanceTeamView.vue'),
        meta: { requiresHasSubordinates: true } },
      { path: 'team/assessments/:id/score', component: () => import('@/views/performance/PerformanceScoringView.vue') },
      { path: 'assessments/:id', component: () => import('@/views/performance/PerformanceDetailView.vue') },
      {
        path: 'admin',
        component: () => import('@/layouts/PerformanceAdminLayout.vue'),
        meta: { requiresPerm: 'kpi:template:manage' },
        children: [
          { path: '', redirect: '/performance/admin/cycles' },
          { path: 'cycles', component: () => import('@/views/performance/PerformanceCyclesView.vue') },
          { path: 'cycles/:id', component: () => import('@/views/performance/PerformanceCycleDetailView.vue') },
          { path: 'templates', component: () => import('@/views/performance/PerformanceTemplatesView.vue') },
          { path: 'templates/:id', component: () => import('@/views/performance/PerformanceTemplateEditView.vue') },
        ]
      }
    ]
  }
]
```

### 菜单挂载点（`MainLayout.vue` 里加）

| 菜单项 | 显示条件 | 跳转 |
|---|---|---|
| 我的绩效 | 所有登录用户 | `/performance/mine` |
| 团队绩效 | `user.hasSubordinates`（前端查 user.manager_id 判断） | `/performance/team` |
| 绩效中心 | 权限 `kpi:template:manage` 或 `okr:view` | `/performance/admin/cycles` |

---

## 8. 权限扩展

在 `seed_roles_v2.py` 里给对应角色加：

```python
# HR / HR 主管
"kpi:template:manage",   # 建 HR 基础模板 · 审批部门模板 · 归档周期
"kpi:cycle:manage",      # 建周期 · 批量生成 · 归档

# 部门经理
"kpi:template:write",    # fork + 改本部门模板

# 员工（默认，不用配）
# 走 assessment.user_id == current_user.id 判断

# 主管（默认，不用配）
# 走 assessment.user.manager_id == current_user.id 判断
```

**权限守卫**（`api/deps.py` 已有 `PermissionChecker`）：
- 模板/周期路由用 `PermissionChecker(["kpi:template:manage"])`
- 员工自评走业务判断（当前用户 == assessment.user_id）
- 主管评分走业务判断（当前用户 == assessment.user.manager_id）

---

## 9. 分阶段执行清单

### Task 1 · 后端模型 + Alembic migration

**做什么：**
- 改 `models/performance.py`：加 `PerformanceTemplate` / `PerformanceTemplateItem` / `PerformanceAssessmentItem` 三个类
- 给 `PerformanceCycle` 加 `cycle_type`、`default_template_id`
- 给 `PerformanceAssessment` 加 `template_id`、`approval_instance_id`
- 写 `alembic/versions/f0a1b2c3d4e5_extend_performance_templates.py`
- 更新 `models/__init__.py` 导出新类

**验收：**
- `alembic upgrade head` 无错
- 数据库能看到 3 张新表 + 4 个新字段
- 老 `PerformanceAssessment` 数据未被破坏

**别做：**
- 不加路由
- 不改业务逻辑

---

### Task 2 · 审批规则 seed

**做什么：**
- 修改 `seed.seed_approval_rules`，追加 `AP-KPI-01/02/03` 三条规则
- 修改 `PerformanceAppeal`：加 `approval_instance_id` 字段（新 migration `f1b2c3d4e5f6_appeal_approval_link.py`）

**验收：**
- `python -m app.seed_approval_flow` 执行后，`approval_rules` 表能看到 4+3=7 条 published 规则
- 单测：手动 create 一个 `ApprovalInstance(rule_code="AP-KPI-01", biz_type="kpi_review")` 能正确解析出 4 个 seq 的 tasks

---

### Task 3 · 后端 services 扩展

**做什么：**
- `services/performance.py` 里加：
  - `create_cycle(db, name, template_id, cycle_type, dates, scope)`
  - `generate_assessments(db, cycle_id)` — 批量建 `PerformanceAssessment` + 复制 items
  - `compute_weighted_score(items)` — 加权算分
  - `resolve_grade(score)` — 阈值（沿用现有 grade 命名 A+/A/B/C）
- 新建 `services/performance_template.py`：`create_template`、`fork_template`、`validate_weights`、`submit_for_review`
- 新建 `services/performance_data_source.py`：`resolve_actual`（system/okr/manual 分派）
- 扩展 `rate_self`：接受 `items` 字段，写 item 明细
- 扩展 `rate_manager`：接受 `items` 字段，触发审批推进

**验收：**
- `tests/services/test_performance_scoring.py` 通过（加权、grade 阈值）
- `tests/services/test_performance_cycle.py` 通过（建周期 → 生成 assessment → 每份 assessment 都有对应 items）
- `tests/services/test_performance_template.py` 通过（fork 保留基础规则、权重合计校验）
- 审批实例能正确创建与推进

---

### Task 4 · 后端 API 扩展

**做什么：**
- 修改 `api/v1/performance.py`，加所有 §6 列出的路由
- 修改现有 `SelfRateRequest` / `ManagerRateRequest` schema 加 `items` 可选字段
- 修改 `PerformanceCycleOut` / `AssessmentOut` schema 暴露新字段（`template_id`、`items` 等）
- 加权限校验（`PermissionChecker(["kpi:template:manage"])` 用在模板/周期路由）

**验收：**
- swagger 上能看到新增路由
- Postman 完整跑：建模板 → 建周期 → 生成 → 张三自评 → 李四评分 → 王五复核 → HR 归档
- 每步 `GET /assessments/{id}/detail` 能看到审批时间线

---

### Task 5 · 前端 · 路由 + Layout + API 层

**做什么：**
- 扩展 `frontend/src/api/performance.ts`，加 §6 所有新接口的调用函数（对齐 `fetchPerformanceWorkbench` 风格）
- 新建 `frontend/src/router/performance.ts`（§7 的路由树），挂进 `router/index.ts`
- 新建 `frontend/src/layouts/PerformanceAdminLayout.vue`（顶部 el-tabs：周期 · 模板）
- 修改 `MainLayout.vue` 加 3 个菜单入口
- 每个 view 都创建占位空文件（`<template><div>TODO</div></template>`），路由能跳转

**验收：**
- 三个入口能进去
- 二级路由能跳
- 权限守卫生效（无 `kpi:template:manage` 进不去 admin）
- `npm run build` 无 TS 错误

---

### Task 6 · 前端 · HR 视图（01 · 02 · 05 屏）

**做什么：**
- `PerformanceCyclesView.vue` — 参照原型 01 屏（周期列表 + 新建抽屉）
- `PerformanceTemplatesView.vue` + `PerformanceTemplateEditView.vue` — 参照 02 屏（权重条 + 指标表格）
- `PerformanceCycleDetailView.vue` — 参照 05 屏（分数分布 SVG + 排名表 + 校准建议）
- 用 Element Plus 组件（`el-table`、`el-drawer`、`el-form`）

**验收：**
- HR 可完整跑「建周期 → 选模板 → 生成 → 校准 → 归档」
- 分数分布图与实际数据一致
- 原型的字段名、状态命名与实现一致

---

### Task 7 · 前端 · 员工 + 主管视图（03 · 04 · 06 · 07 屏）

**做什么：**
- `PerformanceMyView.vue` — 06 屏（趋势图 + 历史卡片）
- `PerformanceSelfReviewView.vue` — 03 屏（指标卡组件 + 加权总分实时算）
- `PerformanceTeamView.vue` — 07 屏（直属/部门切换 + 待办卡 + 表格）
- `PerformanceScoringView.vue` — 04 屏（评分表 + 审批时间线）
- `PerformanceDetailView.vue` — 只读详情（复用 ItemCard 只读模式）
- 5 个 `components/performance/*.vue` 抽出来共用

**验收：**
- 员工提交自评 → 数据库看到 items 明细 + 汇总字段回填
- 主管评分 → 审批实例推进到下一 seq
- 员工能看历史 + 趋势图
- 主管能切换直属/部门看不同数据
- 端到端与原型对齐

---

## 10. 与其他模块耦合点

| 已有模块 | KPI 扩展怎么用 |
|---|---|
| **审批引擎** | seed 三条 rule，`PerformanceAssessment/Template/Appeal.approval_instance_id` 挂实例 |
| **OKR (`models/okr.py`)** | `performance_data_source._resolve_okr` 读 KR 完成率 |
| **customer / deals** | `_resolve_system` 聚合销售额、回款率 |
| **user / dept** | `user.manager_id` 判主管关系；递归查隔级 |
| **薪酬** | 现有 `bonus_amount` + `payroll_batch_no` 保留，item 化不影响 |
| **飞书通知** | `services/feishu_client.py` 复用；新增触发点：自评开启、评分待办、归档结果 |

---

## 11. 附录

### A · HR 基础模板 seed 样例

```python
# 可以直接塞进 seed.py 或新建 seed_performance_templates.py
SALES_QUARTERLY_TEMPLATE = {
    "code": "TPL-SALES-Q",
    "name": "销售岗季度基础模板",
    "owner_type": "hr",
    "cycle_type": "quarterly",
    "rules_json": json.dumps({
        "weight_bounds": {"system": [40, 60], "manual": [0, 30]},
        "allowed_sources": ["system", "okr", "manual", "self_manual"]
    }, ensure_ascii=False),
    "status": "approved",
    "items": [
        {"order_no": 1, "name": "销售额", "weight": 40, "data_source": "system",
         "source_ref": "customer.deals", "target_value": "3000000",
         "score_rule": "达成率 × 100，上限 120"},
        {"order_no": 2, "name": "回款率", "weight": 20, "data_source": "system",
         "source_ref": "customer.payments", "target_value": "≥ 90%",
         "score_rule": "达成率 × 100"},
        {"order_no": 3, "name": "关联 OKR 完成度", "weight": 20, "data_source": "okr",
         "source_ref": "okr.kr_progress", "score_rule": "avg(kr.progress) × 100"},
        {"order_no": 4, "name": "团队协作", "weight": 10, "data_source": "manual",
         "score_rule": "1-5 星 × 20"},
        {"order_no": 5, "name": "客户满意度", "weight": 10, "data_source": "self_manual",
         "target_value": "≥ 85", "score_rule": "问卷平均分"},
    ]
}
```

### B · 评级阈值（跟现有 grade 一致）

现仓库前端 `ASSESS_STATUS_LABEL` 和 `grade_distribution` 用的是 `A+_A / B / C_D`。**沿用现有阈值**，不新起 S/A/B/C/D 命名：

```python
def grade_of(score: Decimal) -> str:
    if score >= 95: return "A+"
    if score >= 85: return "A"
    if score >= 75: return "B"
    if score >= 65: return "C"
    return "D"
```

原型里显示的 S/A/B/C/D 是我早期草图，落地时**映射到 A+/A/B/C/D**（S → A+）。

### C · 常见坑（提醒 Cursor 别踩）

1. **模板改了不能影响历史** — `PerformanceAssessment.template_id` 只用于追溯，指标全部复制到 `performance_assessment_items`
2. **汇总字段是缓存不是真身** — `okr_score` / `kpi_score` / `behavior_score` / `self_score` 由 items 加权算出来后回填，别当权威数据
3. **老 assessment 兼容** — `template_id IS NULL` 的走老逻辑，前端要能显示（不带 items 的旧视图）
4. **状态不要双写** — `PerformanceAssessment.status` 完全从 `ApprovalInstance.current_seq` 派生；不要自己 setattr
5. **主管范围** — `direct` = `user.manager_id == current_user.id`；`dept` = 递归 `manager_id` 链下所有人
6. **数据源批量聚合** — 别在 loop 里逐个 sheet 查 customer 表，用 `IN (user_ids)` 一次拿完
7. **申诉不改原 assessment** — 走 `AP-KPI-03` 审批实例，通过后由服务改 `final_score` 并留痕

---

## 12. 原型对照

原型 HTML：`docs/kpi-flow-prototype.html`

| 原型屏 | 对应 view |
|---|---|
| 01 · 周期管理 | `PerformanceCyclesView.vue` |
| 02 · 模板配置 | `PerformanceTemplatesView.vue` + `PerformanceTemplateEditView.vue` |
| 03 · 员工自评 | `PerformanceSelfReviewView.vue` |
| 04 · 上级评分 | `PerformanceScoringView.vue` |
| 05 · 归档校准 | `PerformanceCycleDetailView.vue` |
| 06 · 我的 KPI（=我的绩效） | `PerformanceMyView.vue` |
| 07 · 团队 KPI（=团队绩效） | `PerformanceTeamView.vue` |

**命名映射**：原型里的「KPI」在实现里全部叫「绩效 / performance」，别用 `kpi_*` 表名或组件名。字段名、颜色、状态转换都可以从原型 HTML 直接搬。

---

## 13. 执行原则

- **跑起来 > 全 > 优雅**：每个 Task 提交前必须能启动服务 + 有测试通过
- **老逻辑不动**：现有 `PerformanceAssessment` 老三段分数、workbench、薪酬联动全部零改动兼容
- **不确定就问**：模型字段增删、审批流节点顺序、权限码命名，任何模糊就停下问用户
