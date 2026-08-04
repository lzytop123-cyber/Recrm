<template>
  <div class="overview-page crm-page" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-actions">
        <el-button disabled>本月 ▾</el-button>
        <el-button type="primary" @click="onExport">导出经营简报</el-button>
      </div>
    </header>

    <section v-if="kpis.length" class="ov-kpi-grid">
      <button
        v-for="kpi in kpis"
        :key="kpi.key"
        type="button"
        class="ov-kpi ov-reveal"
        :class="{ 'top-accent': kpi.accent }"
        @click="kpi.path && go(kpi.path)"
      >
        <div class="ov-kpi-top">
          <span class="ov-kpi-icon">{{ kpi.icon }}</span>
          <span class="ov-delta" :class="{ down: kpi.delta_tone === 'down' }">{{ kpi.delta }}</span>
        </div>
        <span class="ov-kpi-label">{{ kpi.label }}</span>
        <strong class="ov-kpi-value">{{ animatedDisplay(kpi) }}</strong>
        <span class="ov-kpi-note">{{ kpi.note }}</span>
      </button>
    </section>

    <section class="ov-grid">
      <article class="ov-card ov-chart-card ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>收入与回款趋势</h2>
            <p>单位：万元，按自然月统计</p>
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
                <stop offset="0" stop-color="var(--crm-primary)" stop-opacity=".22" />
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
              :key="pt.month"
              class="ov-chart-point"
              :cx="pt.x"
              :cy="pt.incomeY"
              r="4"
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
        <div v-else class="ov-empty-note">暂无收入与回款趋势数据</div>
      </article>

      <article class="ov-card ov-card-pad ov-funnel-card ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>销售转化漏斗</h2>
            <p>当前可见范围 · 线索去重后</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/sales')">查看明细</button>
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

    <section class="ov-alerts-wrap">
      <article class="ov-card ov-card-pad ov-alerts-card ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>待处理预警</h2>
            <p>按影响和时效排序</p>
          </div>
          <span class="ov-status-badge" :class="{ ok: !alerts.length }">
            {{ alerts.length ? `${alerts.length} 项` : '正常' }}
          </span>
        </div>
        <div v-if="alerts.length" class="ov-alert-list">
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
        <div v-else class="ov-empty-note">当前没有待处理预警</div>
      </article>
    </section>

    <section class="ov-bottom-grid">
      <article class="ov-card ov-card-pad ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>项目健康度</h2>
            <p>由里程碑、任务、风险和验收共同计算</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/projects')">全部项目</button>
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

      <article class="ov-card ov-card-pad ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>今日排期</h2>
            <p>会议、讲师和主播统一占用</p>
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

      <article class="ov-card ov-card-pad ov-reveal">
        <div class="ov-card-head">
          <div>
            <h2>组织执行</h2>
            <p>部门目标与员工任务汇总</p>
          </div>
          <button type="button" class="ov-text-link" @click="go('/okrs')">查看目标</button>
        </div>
        <div v-if="orgExecution.length" class="ov-score-bars">
          <div v-for="row in orgExecution" :key="row.name" class="ov-score-row">
            <span>{{ row.name }}</span>
            <div class="ov-progress-track">
              <div class="ov-progress-fill" :style="{ width: `${row.score}%` }" />
            </div>
            <b>{{ row.score }}</b>
          </div>
        </div>
        <div v-else class="ov-empty-note">暂无组织目标数据</div>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  fetchDashboard,
  type AlertItem,
  type DashboardData,
  type FunnelStep,
  type OrgScoreItem,
  type OverviewKpi,
  type ProjectHealth,
  type RevenueTrendPoint,
  type TodayScheduleItem,
} from '@/api/dashboard'

const router = useRouter()
const loading = ref(false)
const data = ref<DashboardData | null>(null)
const animValues = ref<Record<string, number>>({})

const kpis = computed<OverviewKpi[]>(() => data.value?.kpis ?? [])
const revenueTrend = computed<RevenueTrendPoint[]>(() => data.value?.revenue_trend ?? [])
const funnel = computed<FunnelStep[]>(() => data.value?.funnel ?? [])
const alerts = computed<AlertItem[]>(() => data.value?.alerts ?? [])
const health = computed<ProjectHealth>(
  () => data.value?.project_health ?? { score: 0, healthy: 0, watch: 0, risk: 0 },
)
const todaySchedules = computed<TodayScheduleItem[]>(() => data.value?.today_schedules ?? [])
const orgExecution = computed<OrgScoreItem[]>(() => data.value?.org_execution ?? [])

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
    const p = Math.min(1, (now - start) / 850)
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
    const { data: response } = await fetchDashboard()
    data.value = response
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
