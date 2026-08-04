# 首页经营看板改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将首页改为 A 型经营总览布局，并用真实权限范围内数据加入近 6 个月回款趋势图。

**Architecture:** 继续复用单一 dashboard 聚合接口，在后端响应中新增六个月回款序列；前端用 Vue 计算 SVG 坐标并将原有分组指标重排为主内容区和操作侧栏。设计令牌集中在项目根目录 `tokens.css`，页面样式只消费语义令牌。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、pytest、Vue 3、TypeScript、Element Plus、原生 SVG、Vite

## Global Constraints

- 趋势数据必须来自当前用户可见的已确认收款记录，连续 6 个月且缺失月份补 0。
- 不增加图表依赖，不制造同比、环比或预测值。
- 保留现有路由、权限、菜单和所有原有业务指标。
- 生产 CSS 新增颜色使用 OKLCH 语义令牌，并支持键盘焦点和减少动态效果。
- 按用户要求不执行任何 Git 操作。

---

### Task 1: 回款趋势聚合

**Files:**
- Modify: `backend/app/services/dashboard.py`
- Modify: `backend/app/schemas/dashboard.py`

**Interfaces:**
- Consumes: `payment_service.list_payments(db, user, page=1, page_size=10000)`
- Produces: `build_payment_trend(db, user, today=None) -> list[dict]` 和响应字段 `payment_trend: List[PaymentTrendPoint]`

- [x] **Step 1: Implement aggregation**

  新增月份位移函数与 `build_payment_trend`，复用现有权限过滤后的收款列表；Schema 增加 `PaymentTrendPoint` 和默认空列表。

- [x] **Step 2: Verify through frontend production build and code review**

### Task 2: 看板结构与设计令牌

**Files:**
- Create: `tokens.css`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/api/dashboard.ts`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/styles/index.css`
- Create: `.hallmark/preflight.json`
- Create: `.hallmark/log.json`

**Interfaces:**
- Consumes: `DashboardData.payment_trend: PaymentTrendPoint[]`
- Produces: 主内容 + 右侧行动栏、SVG 趋势图、核心指标和完整业务分组。

- [x] **Step 1: Implement approved dashboard**

  添加语义令牌和 Hallmark 记录；在 API 类型中加入趋势点；重写 DashboardView 布局、真实数据映射及 SVG；微调主布局宽度与背景。

- [x] **Step 2: Review responsive, focus, empty and loading states**

### Task 3: 生产构建验证

**Files:**
- Modify only if verification exposes an implementation defect.

**Interfaces:**
- Consumes: Task 1 and Task 2 complete implementation.
- Produces: 可发布的前后端改版结果。

- [x] **Step 1: Run frontend production build**

  Run: `npm run build`
  Working directory: `frontend`
  Expected: `vue-tsc` and Vite exit 0.

- [x] **Step 2: Run Hallmark pre-emit review**

  逐项检查信息层级、真实数据、无障碍、响应式、语义令牌、无虚构指标和无大范围全局覆盖；将结果写入 `.hallmark/log.json`。

## Self-Review

- Spec coverage: 趋势数据、A+B 布局、全量指标、权限、无障碍和构建验证分别由 Task 1–3 覆盖。自动化测试步骤按用户明确要求移除。
- Placeholder scan: 未包含 TBD、TODO 或未定义实现步骤。
- Type consistency: 后端 `payment_trend` 与前端 `PaymentTrendPoint[]` 命名一致，字段统一为 `month`、`label`、`amount`。
