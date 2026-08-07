<template>
  <div class="overview-page crm-page" v-loading="loading">
    <header class="sales-head ov-head">
      <div class="sales-head-copy">
        <p class="ov-eyebrow">经营台</p>
        <h1>经营总览</h1>
        <p>
          {{ greeting }}
          <template v-if="data?.as_of"> · 数据截至 {{ data.as_of }}</template>
        </p>
      </div>
      <div class="sales-head-actions">
        <span class="ov-scope-chip">{{ scopeLabel }}</span>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="onExport">导出简报</el-button>
      </div>
    </header>

    <section v-if="kpis.length" class="ov-kpi-grid" :style="{ '--kpi-cols': String(Math.min(kpis.length, 4)) }">
      <button
        v-for="kpi in kpis"
        :key="kpi.key"
        type="button"
        class="ov-kpi"
        :class="{ accent: kpi.accent }"
        @click="kpi.path && go(kpi.path)"
      >
        <div class="ov-kpi-top">
          <span class="ov-kpi-label">{{ kpi.label }}</span>
          <span class="ov-delta" :class="{ down: kpi.delta_tone === 'down' }">{{ kpi.delta }}</span>
        </div>
        <strong class="ov-kpi-value">{{ animatedDisplay(kpi) }}</strong>
        <span class="ov-kpi-note">{{ kpi.note }}</span>
      </button>
    </section>

    <section class="ov-grid">
      <article class="ov-card ov-chart-card">
        <div class="ov-card-head">
          <div>
            <h2>收入与回款</h2>
            <p>单位：万元 · 按自然月</p>
          </div>
          <div class="ov-chart-legend">
            <span><i class="ov-legend-dot income"></i>确认收入</span>
            <span><i class="ov-legend-dot cash"></i>已回款</span>
          </div>
        </div>
        <div v-if="revenueTrend.length" class="ov-line-chart" aria-label="收入与回款趋势图">
          <svg :viewBox="`0 0 ${chartW} ${chartH}`" role="img" preserveAspectRatio="none">
            <defs>
              <linearGradient id="ovAreaFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="var(--crm-primary)" stop-opacity=".18" />
                <stop offset="1" stop-color="var(--crm-primary)" stop-opacity="0" />
              </linearGradient>
            </defs>
            <template v-for="tick in yTicks" :key="tick">
              <line
                class="ov-grid-line"
                :x1="padX"
                :x2="chartW - padX"
                :y1="yScale(tick)"
                :y2="yScale(tick)"
              />
              <text class="ov-axis-label" x="4" :y="yScale(tick) + 4">{{ tick }}</text>
            </template>
            <path class="ov-chart-area" :d="incomeArea" />
            <path class="ov-chart-line" :d="incomePath" />
            <path class="ov-chart-line cash" :d="cashPath" />
            <circle
              v-for="pt in chartPoints"
              :key="`${pt.month}-cash`"
              class="ov-chart-point cash"
              :cx="pt.x"
              :cy="pt.cashY"
              r="3"
            >
              <title>{{ pt.label }} 已回款 {{ pt.cash }} 万元</title>
            </circle>
            <circle
              v-for="pt in chartPoints"
              :key="pt.month"
              class="ov-chart-point"
              :cx="pt.x"
              :cy="pt.incomeY"
              r="3.5"
            >
              <title>{{ pt.label }} 确认收入 {{ pt.income }} 万元</title>
            </circle>
            <text
              v-for="pt in chartPoints"
              :key="`${pt.month}-lbl`"
              class="ov-axis-label"
              text-anchor="middle"
              :x="pt.x"
              :y="chartH - 2"
            >
              {{ pt.label }}
            </text>
          </svg>
        </div>
        <div v-else class="ov-empty-note">暂无趋势数据</div>
      </article>

      <article class="ov-card ov-card-pad ov-funnel-card">
        <div class="ov-card-head">
          <div>
            <h2>销售漏斗</h2>
            <p>当前可见范围 · 线索去重</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/sales')">明细</button>
        </div>
        <div v-if="funnel.length" class="ov-funnel">
          <div v-for="step in funnel" :key="step.label" class="ov-funnel-row">
            <span>{{ step.label }}</span>
            <div class="ov-funnel-track">
              <div class="ov-funnel-fill" :style="{ width: funnelWidth(step.value) }" />
            </div>
            <b>{{ step.value }}</b>
          </div>
        </div>
        <div v-else class="ov-empty-note">暂无漏斗数据</div>
      </article>
    </section>

    <section class="ov-bottom-grid">
      <article class="ov-card ov-card-pad">
        <div class="ov-card-head">
          <div>
            <h2>待处理预警</h2>
            <p>按影响与时效排序</p>
          </div>
          <span class="ov-status-badge" :class="{ ok: !alerts.length }">
            {{ alerts.length ? `${alerts.length} 项` : '正常' }}
          </span>
        </div>
        <div v-if="alerts.length" class="ov-alert-list ov-alert-list--stack">
          <div
            v-for="item in alerts"
            :key="item.key"
            class="ov-alert-row"
            :class="{ danger: item.tone === 'danger' }"
          >
            <span class="ov-alert-symbol">{{ item.symbol }}</span>
            <span>
              <b>{{ item.title }}</b>
              <small>{{ item.detail }}</small>
            </span>
            <button type="button" class="ov-text-link" @click="go(item.path)">
              {{ item.action }}
            </button>
          </div>
        </div>
        <div v-else class="ov-empty-note">暂无待处理预警</div>
      </article>

      <article class="ov-card ov-card-pad">
        <div class="ov-card-head">
          <div>
            <h2>项目健康度</h2>
            <p>里程碑 · 任务 · 风险 · 验收</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/projects')">全部</button>
        </div>
        <div class="ov-project-health">
          <div class="ov-progress-ring">
            <svg viewBox="0 0 80 80" aria-hidden="true">
              <circle
                cx="40"
                cy="40"
                r="31"
                fill="none"
                stroke="var(--crm-surface-soft)"
                stroke-width="8"
              />
              <circle
                cx="40"
                cy="40"
                r="31"
                fill="none"
                stroke="var(--crm-primary)"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="ringCirc"
                :stroke-dashoffset="ringOffset"
              />
            </svg>
            <strong>{{ health.score }}%</strong>
          </div>
          <div class="ov-health-list">
            <div class="ov-health-row">
              <span><i class="up"></i>健康</span>
              <b>{{ health.healthy }}</b>
            </div>
            <div class="ov-health-row">
              <span><i class="warn"></i>需关注</span>
              <b>{{ health.watch }}</b>
            </div>
            <div class="ov-health-row">
              <span><i class="down"></i>高风险</span>
              <b>{{ health.risk }}</b>
            </div>
          </div>
        </div>
      </article>

      <article class="ov-card ov-card-pad">
        <div class="ov-card-head">
          <div>
            <h2>今日排期</h2>
            <p>会议 · 讲师 · 主播占用</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/schedules')">周视图</button>
        </div>
        <div v-if="todaySchedules.length" class="ov-schedule-list">
          <button
            v-for="item in todaySchedules"
            :key="item.id"
            type="button"
            class="ov-schedule-row"
            :class="{ external: item.external }"
            @click="go(item.path)"
          >
            <span class="ov-schedule-time">{{ item.time }}</span>
            <i class="ov-schedule-bar"></i>
            <span>
              <b>{{ item.title }}</b>
              <small>{{ item.subtitle }}</small>
            </span>
          </button>
        </div>
        <div v-else class="ov-empty-note">今日暂无排期</div>
      </article>
    </section>

    <section id="dept-monitor" class="ov-card ov-card-pad ov-dept" v-loading="deptLoading">
      <div class="ov-card-head">
        <div>
          <h2>{{ deptMonitor?.department_name || '本部门' }} · 执行监控</h2>
          <p>看人、看任务、看异常；项目档案请到「项目台账」</p>
        </div>
        <button
          type="button"
          class="ov-text-link"
          @click="go('/projects/delivery?tab=execute&mode=tasks')"
        >
          去任务工时
        </button>
      </div>

      <div class="ov-dept-kpis">
        <div class="ov-dept-kpi">
          <small>执行健康分</small>
          <strong>{{ deptMonitor?.health_score ?? 0 }}</strong>
        </div>
        <div class="ov-dept-kpi">
          <small>任务按期率</small>
          <strong>{{ formatRate(deptMonitor?.on_time_rate) }}%</strong>
          <span>逾期 {{ deptMonitor?.overdue_tasks ?? 0 }}</span>
        </div>
        <div class="ov-dept-kpi">
          <small>工时完整率</small>
          <strong>{{ formatRate(deptMonitor?.hours_complete_rate) }}%</strong>
          <span>缺失 {{ deptMonitor?.missing_hours ?? 0 }}</span>
        </div>
        <div class="ov-dept-kpi">
          <small>待处理异常</small>
          <strong>{{ (deptMonitor?.overdue_tasks ?? 0) + (deptMonitor?.missing_hours ?? 0) }}</strong>
          <span>逾期 + 缺报</span>
        </div>
      </div>

      <el-table :data="deptMonitor?.members || []" stripe empty-text="暂无本部门任务数据">
        <el-table-column prop="name" label="员工" min-width="100" />
        <el-table-column prop="planned_tasks" label="计划" width="72" />
        <el-table-column prop="done_tasks" label="完成" width="72" />
        <el-table-column prop="overdue_tasks" label="逾期" width="72">
          <template #default="{ row }">
            <span :class="{ 'ov-danger': row.overdue_tasks > 0 }">{{ row.overdue_tasks }}</span>
          </template>
        </el-table-column>
        <el-table-column label="计划 / 实际工时" min-width="130">
          <template #default="{ row }">
            {{ formatHours(row.planned_hours) }} / {{ formatHours(row.actual_hours) }}h
          </template>
        </el-table-column>
        <el-table-column label="工时完整" width="90">
          <template #default="{ row }">{{ formatRate(row.hours_complete_rate) }}%</template>
        </el-table-column>
        <el-table-column prop="open_tickets" label="待处理工单" width="100" />
      </el-table>
      <p v-if="!(deptMonitor?.members || []).length" class="ov-dept-hint">
        可在「交付执行 → 任务工时」中创建并指派责任人后查看汇总。
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  fetchDashboard,
  type AlertItem,
  type DashboardData,
  type FunnelStep,
  type OverviewKpi,
  type ProjectHealth,
  type RevenueTrendPoint,
  type TodayScheduleItem,
} from '@/api/dashboard'
import {
  fetchDepartmentMonitor,
  type DepartmentMonitor,
} from '@/api/projects'

const SCOPE_LABEL: Record<string, string> = {
  company: '全公司',
  department: '本部门',
  personal: '本人',
}

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const data = ref<DashboardData | null>(null)
const animValues = ref<Record<string, number>>({})
const deptLoading = ref(false)
const deptMonitor = ref<DepartmentMonitor | null>(null)

const kpis = computed<OverviewKpi[]>(() => data.value?.kpis ?? [])
const revenueTrend = computed<RevenueTrendPoint[]>(() => data.value?.revenue_trend ?? [])
const funnel = computed<FunnelStep[]>(() => data.value?.funnel ?? [])
const alerts = computed<AlertItem[]>(() => data.value?.alerts ?? [])
const health = computed<ProjectHealth>(
  () => data.value?.project_health ?? { score: 0, healthy: 0, watch: 0, risk: 0 },
)
const todaySchedules = computed<TodayScheduleItem[]>(() => data.value?.today_schedules ?? [])

const scopeLabel = computed(() => SCOPE_LABEL[data.value?.data_scope || ''] || '可见范围')
const greeting = computed(() => {
  const name = data.value?.display_name
  return name ? `${name}，欢迎回来` : '集中查看经营、回款、项目与执行'
})

function formatHours(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? String(Math.round(n * 10) / 10) : '0'
}

function formatRate(v?: number | string | null) {
  const n = Number(v || 0)
  if (!Number.isFinite(n)) return '0'
  return String(Math.round(n * 10) / 10)
}

async function loadDeptMonitor() {
  deptLoading.value = true
  try {
    const { data: monitor } = await fetchDepartmentMonitor()
    deptMonitor.value = monitor
  } catch {
    deptMonitor.value = null
  } finally {
    deptLoading.value = false
  }
}

async function focusDeptMonitorIfNeeded() {
  if (String(route.query.focus || '') !== 'dept-monitor') return
  await nextTick()
  document.getElementById('dept-monitor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const chartW = 720
const chartH = 220
const padX = 40
const padY = 22

const chartMax = computed(() => {
  const vals = revenueTrend.value.flatMap((p) => [Number(p.income), Number(p.cash)])
  const raw = Math.max(...vals, 1)
  return Math.ceil(raw / 10) * 10 || 10
})

const yTicks = computed(() => {
  const max = chartMax.value
  const step = max / 4
  return [0, step, step * 2, step * 3, max].map((v) => Math.round(v))
})

function xScale(i: number) {
  const n = revenueTrend.value.length
  if (n <= 1) return chartW / 2
  return padX + (i * (chartW - padX * 2)) / (n - 1)
}

function yScale(v: number) {
  const max = chartMax.value || 1
  return chartH - padY - (v / max) * (chartH - padY * 2)
}

const chartPoints = computed(() =>
  revenueTrend.value.map((p, i) => ({
    ...p,
    x: xScale(i),
    incomeY: yScale(Number(p.income)),
    cashY: yScale(Number(p.cash)),
  })),
)

function linePath(getter: (p: (typeof chartPoints.value)[0]) => number) {
  const pts = chartPoints.value
  if (!pts.length) return ''
  return 'M' + pts.map((p, i) => `${xScale(i)},${getter(p)}`).join(' L')
}

const incomePath = computed(() => linePath((p) => p.incomeY))
const cashPath = computed(() => linePath((p) => p.cashY))
const incomeArea = computed(() => {
  const pts = chartPoints.value
  if (!pts.length) return ''
  const base = chartH - padY
  return `${incomePath.value} L${xScale(pts.length - 1)},${base} L${xScale(0)},${base} Z`
})

const funnelMax = computed(() => Math.max(...funnel.value.map((s) => s.value), 1))

function funnelWidth(value: number) {
  return `${(value / funnelMax.value) * 100}%`
}

const ringCirc = 2 * Math.PI * 31
const ringOffset = computed(() => ringCirc * (1 - Math.min(Math.max(health.value.score, 0), 100) / 100))

function animatedDisplay(kpi: OverviewKpi) {
  const current = animValues.value[kpi.key]
  if (current == null) return kpi.display
  if (kpi.key === 'month_income') {
    return `¥${Math.round(current).toLocaleString('zh-CN')}`
  }
  return String(Math.round(current))
}

function animateKpis(items: OverviewKpi[]) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const next: Record<string, number> = {}
    for (const kpi of items) next[kpi.key] = kpi.value
    animValues.value = next
    return
  }
  const start = performance.now()
  const from: Record<string, number> = { ...animValues.value }
  const targets: Record<string, number> = {}
  for (const kpi of items) {
    targets[kpi.key] = kpi.value
    if (from[kpi.key] == null) from[kpi.key] = 0
  }
  function tick(now: number) {
    const p = Math.min(1, (now - start) / 700)
    const eased = 1 - Math.pow(1 - p, 3)
    const next: Record<string, number> = {}
    for (const key of Object.keys(targets)) {
      next[key] = from[key] + (targets[key] - from[key]) * eased
    }
    animValues.value = next
    if (p < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

watch(
  kpis,
  (items) => {
    if (items.length) animateKpis(items)
  },
  { deep: true },
)

function go(path: string) {
  router.push(path)
}

function onExport() {
  ElMessage.info('经营简报导出即将开放，当前可在各业务模块查看明细。')
}

async function load() {
  loading.value = true
  try {
    const [{ data: response }] = await Promise.all([fetchDashboard(), loadDeptMonitor()])
    data.value = response
  } finally {
    loading.value = false
  }
}

watch(
  () => String(route.query.focus || ''),
  () => {
    focusDeptMonitorIfNeeded()
  },
)

onMounted(async () => {
  await load()
  await focusDeptMonitorIfNeeded()
})
</script>
