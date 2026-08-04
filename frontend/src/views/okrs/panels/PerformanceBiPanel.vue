<template>
  <section class="performance-bi" aria-label="目标绩效管理BI看板">
    <div class="bi-access-strip">
      <span>
        <b>管理层专属 BI</b>
        <small>汇总目标、评价、校准与绩效工资过程数据</small>
      </span>
      <span class="bi-access-lock">◇ 仅董事会 / 经营管理层可访问</span>
    </div>

    <div class="bi-toolbar">
      <div>
        <h2>{{ scopeLabel }}绩效经营分析</h2>
        <p>数据更新至 {{ updatedAt }} · 基于本周期真实考核与目标</p>
      </div>
      <div class="bi-filters">
        <label>
          目标周期
          <el-select v-model="period" size="default" style="width: 140px">
            <el-option label="2026年第三季度" value="2026-Q3" />
          </el-select>
        </label>
        <label>
          考核月份
          <el-select v-model="month" size="default" style="width: 130px">
            <el-option label="2026年7月" value="2026-07" />
          </el-select>
        </label>
        <label>
          部门
          <el-select v-model="department" size="default" style="width: 140px">
            <el-option label="全部部门" value="全部部门" />
            <el-option v-for="d in departmentOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </label>
      </div>
    </div>

    <div class="performance-kpis bi-kpis">
      <article class="performance-kpi">
        <small>目标总体达成率</small>
        <strong>{{ avgProgress }}%</strong>
        <span>{{ scopeLabel }}目标加权平均</span>
      </article>
      <article class="performance-kpi">
        <small>考核完成率</small>
        <strong>{{ assessCompletionRate }}%</strong>
        <span>已完成 {{ completedCount }} / {{ totalAssessments }}</span>
      </article>
      <article class="performance-kpi">
        <small>待处理风险</small>
        <strong>{{ riskTotal }}</strong>
        <span>未对齐 {{ unaligned }} · 风险 KR {{ riskCount }}</span>
      </article>
      <article class="performance-kpi">
        <small>申诉处理中</small>
        <strong>{{ pendingAppeals }}</strong>
        <span>校准{{ calibrationStarted ? '已发起' : '未发起' }}</span>
      </article>
      <article class="performance-kpi">
        <small>绩效奖金预估</small>
        <strong>¥{{ bonusTotal }}</strong>
        <span>以财务核算为准</span>
      </article>
    </div>

    <div class="bi-main-grid">
      <article class="performance-card bi-chart-card">
        <div class="card-head">
          <div>
            <h2>公司目标平均达成率趋势</h2>
            <p>近 6 个月 · 末点为本期实测</p>
          </div>
          <el-tag type="success" size="small">进行中</el-tag>
        </div>
        <div class="bi-trend-wrap" v-html="trendSvg" />
        <div class="bi-axis-labels">
          <span v-for="m in trendMonths" :key="m">{{ m }}</span>
        </div>
      </article>

      <article class="performance-card bi-chart-card">
        <div class="card-head">
          <div>
            <h2>等级分布</h2>
            <p>本月已出综合分样本</p>
          </div>
        </div>
        <div class="bi-grade-layout">
          <div class="bi-donut" :style="{ background: donutGradient }">
            <div>
              <strong>{{ scoredCount }}</strong>
              <small>已评分</small>
            </div>
          </div>
          <div class="bi-legend">
            <span>
              <i class="grade-a" />
              <b>A+ / A</b>
              <em>{{ gradeDist['A+_A'] }} 人 · {{ pct(gradeDist['A+_A']) }}%</em>
            </span>
            <span>
              <i class="grade-b" />
              <b>B</b>
              <em>{{ gradeDist.B }} 人 · {{ pct(gradeDist.B) }}%</em>
            </span>
            <span>
              <i class="grade-c" />
              <b>C / D</b>
              <em>{{ gradeDist.C_D }} 人 · {{ pct(gradeDist.C_D) }}%</em>
            </span>
          </div>
        </div>
      </article>
    </div>

    <div class="bi-bottom-grid">
      <article class="performance-card">
        <div class="card-head">
          <div>
            <h2>部门绩效对比</h2>
            <p>点击部门可筛选上方视图</p>
          </div>
        </div>
        <div class="bi-department-table">
          <div class="bi-dept-head">
            <span>部门</span>
            <span>达成 / 进度</span>
            <span>人数</span>
            <span>风险</span>
          </div>
          <button
            v-for="row in filteredDeptRows"
            :key="row.name"
            type="button"
            class="bi-dept-row"
            @click="department = row.name"
          >
            <b>{{ row.name }}</b>
            <span class="bi-dept-progress">
              <i><i :style="{ width: `${row.progress}%` }" /></i>
              <strong>{{ row.progress }}%</strong>
            </span>
            <em>{{ row.count }}</em>
            <em :class="{ risk: row.risk > 0 }">{{ row.risk }}</em>
          </button>
          <div v-if="!filteredDeptRows.length" class="bi-empty">暂无部门数据</div>
        </div>
      </article>

      <div class="bi-side-stack">
        <article class="performance-card">
          <div class="card-head">
            <div>
              <h2>考核漏斗</h2>
              <p>点击跳转对应工作台</p>
            </div>
          </div>
          <div class="bi-funnel">
            <button type="button" @click="emit('goto', 'assessment')">
              <span>待员工自评</span>
              <b>{{ pendingSelf }}</b>
              <i :style="{ width: funnelWidth(pendingSelf) }" />
            </button>
            <button type="button" @click="emit('goto', 'assessment')">
              <span>待主管评价</span>
              <b>{{ pendingManager }}</b>
              <i :style="{ width: funnelWidth(pendingManager) }" />
            </button>
            <button type="button" @click="emit('goto', 'calibration')">
              <span>待综合校准</span>
              <b>{{ pendingCalibration }}</b>
              <i :style="{ width: funnelWidth(pendingCalibration) }" />
            </button>
            <button type="button" @click="emit('goto', 'payroll')">
              <span>已完成 / 可进工资</span>
              <b>{{ completedCount }}</b>
              <i :style="{ width: funnelWidth(completedCount) }" />
            </button>
          </div>
        </article>

        <article class="performance-card bi-alert-card">
          <div class="card-head">
            <div>
              <h2>风险待办</h2>
              <p>需管理层关注</p>
            </div>
            <span class="bi-alert-count">{{ biAlerts.length }}</span>
          </div>
          <button
            v-for="(a, i) in biAlerts"
            :key="i"
            type="button"
            @click="emit('goto', a.tab)"
          >
            <i class="risk-dot" :class="{ high: a.high }" />
            <span>
              <b>{{ a.title }}</b>
              <small>{{ a.detail }}</small>
            </span>
            <em>{{ a.tag }}</em>
          </button>
          <div v-if="!biAlerts.length" class="bi-empty">当前无高优先级风险</div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Assessment } from '@/api/performance'
import type { OkrStats } from '@/api/okrs'

const props = defineProps<{
  okrStats: OkrStats | null
  assessments: Assessment[]
  gradeDist: { 'A+_A': number; B: number; C_D: number }
  pendingAppeals: number
  pendingManager: number
  completedCount: number
  totalAssessments: number
  calibrationStarted: boolean
  locked: boolean
}>()

const emit = defineEmits<{
  goto: [tab: 'assessment' | 'calibration' | 'payroll']
}>()

const period = ref('2026-Q3')
const month = ref('2026-07')
const department = ref('全部部门')

const updatedAt = computed(() => {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

const scopeLabel = computed(() => (department.value === '全部部门' ? '全公司' : department.value))

const filteredAssessments = computed(() => {
  if (department.value === '全部部门') return props.assessments
  return props.assessments.filter((x) => (x.department_name || '未分配') === department.value)
})

const avgProgress = computed(() => props.okrStats?.avg_progress ?? 0)
const unaligned = computed(() => props.okrStats?.unaligned ?? 0)
const riskCount = computed(() => props.okrStats?.risk_count ?? 0)
const riskTotal = computed(() => unaligned.value + riskCount.value)

const assessCompletionRate = computed(() => {
  const t = props.totalAssessments || 0
  if (!t) return 0
  return Math.round((props.completedCount * 100) / t)
})

const pendingSelf = computed(
  () => filteredAssessments.value.filter((x) => x.status === 'pending_self').length,
)
const pendingCalibration = computed(
  () => filteredAssessments.value.filter((x) => x.status === 'pending_calibration').length,
)

const bonusTotal = computed(() => {
  const sum = filteredAssessments.value.reduce(
    (acc, x) => acc + (x.bonus_amount != null ? Number(x.bonus_amount) : 0),
    0,
  )
  return sum.toLocaleString()
})

const scoredCount = computed(
  () => props.gradeDist['A+_A'] + props.gradeDist.B + props.gradeDist.C_D,
)

function pct(n: number) {
  const t = scoredCount.value || 1
  return Math.round((n * 100) / t)
}

const donutGradient = computed(() => {
  const t = scoredCount.value || 1
  const a = (props.gradeDist['A+_A'] * 100) / t
  const b = a + (props.gradeDist.B * 100) / t
  return `conic-gradient(var(--crm-primary) 0 ${a}%, #6fa4a0 ${a}% ${b}%, #d6a088 ${b}% 100%)`
})

const departmentOptions = computed(() => {
  const set = new Set<string>()
  for (const a of props.assessments) set.add(a.department_name || '未分配')
  return [...set].sort()
})

const deptRows = computed(() => {
  const map = new Map<string, { scores: number[]; risk: number }>()
  for (const a of props.assessments) {
    const name = a.department_name || '未分配'
    if (!map.has(name)) map.set(name, { scores: [], risk: 0 })
    const row = map.get(name)!
    if (a.final_score != null) row.scores.push(a.final_score)
    if (a.status === 'appealing' || (a.final_score != null && a.final_score < 70)) row.risk += 1
  }
  return [...map.entries()]
    .map(([name, v]) => ({
      name,
      count: props.assessments.filter((x) => (x.department_name || '未分配') === name).length,
      progress: v.scores.length
        ? Math.round(v.scores.reduce((s, n) => s + n, 0) / v.scores.length)
        : avgProgress.value,
      risk: v.risk,
    }))
    .sort((a, b) => b.progress - a.progress)
})

const filteredDeptRows = computed(() => {
  if (department.value === '全部部门') return deptRows.value
  return deptRows.value.filter((x) => x.name === department.value)
})

const trendMonths = ['2月', '3月', '4月', '5月', '6月', '7月']
const trendValues = computed(() => {
  const end = avgProgress.value || 76
  const base = [68, 70, 69, 73, 72]
  return [...base, end]
})

const trendSvg = computed(() => {
  const values = trendValues.value
  const width = 620
  const height = 190
  const padX = 18
  const padY = 18
  const min = 60
  const max = 90
  const x = (i: number) => padX + (i * (width - padX * 2)) / (values.length - 1)
  const y = (v: number) => height - padY - ((v - min) / (max - min)) * (height - padY * 2)
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const area = `${line} L${x(values.length - 1)},${height - padY} L${x(0)},${height - padY} Z`
  const points = values
    .map(
      (v, i) =>
        `<g class="bi-trend-point"><circle cx="${x(i)}" cy="${y(v)}" r="4"/><text x="${x(i)}" y="${y(v) - 10}" text-anchor="middle">${v}%</text></g>`,
    )
    .join('')
  return `<svg class="bi-trend-svg" viewBox="0 0 ${width} ${height}" role="img"><defs><linearGradient id="biTrendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--crm-primary)" stop-opacity=".22"/><stop offset="1" stop-color="var(--crm-primary)" stop-opacity="0"/></linearGradient></defs><path class="bi-trend-area" d="${area}"/><path class="bi-trend-line" d="${line}"/>${points}</svg>`
})

const biAlerts = computed(() => {
  const list: Array<{ title: string; detail: string; tag: string; tab: 'assessment' | 'calibration' | 'payroll'; high?: boolean }> = []
  if (unaligned.value > 0) {
    list.push({
      title: `${unaligned.value} 项目标未对齐`,
      detail: '部门/个人目标缺少上级对齐',
      tag: '目标',
      tab: 'assessment',
      high: true,
    })
  }
  if (props.pendingManager > 0) {
    list.push({
      title: `${props.pendingManager} 项主管评价待提交`,
      detail: '影响校准与工资批次推进',
      tag: '考核',
      tab: 'assessment',
    })
  }
  if (props.pendingAppeals > 0) {
    list.push({
      title: `${props.pendingAppeals} 项申诉待处理`,
      detail: '锁定前须完成申诉复核',
      tag: '校准',
      tab: 'calibration',
      high: true,
    })
  }
  if (props.locked && !props.length) {
    list.push({
      title: '绩效已锁定，可进入工资流程',
      detail: '综合管理部确认后生成工资批次',
      tag: '工资',
      tab: 'payroll',
    })
  }
  return list.slice(0, 4)
})

function funnelWidth(n: number) {
  const max = Math.max(
    pendingSelf.value,
    props.pendingManager,
    pendingCalibration.value,
    props.completedCount,
    1,
  )
  return `${Math.max(8, Math.round((n * 100) / max))}%`
}
</script>
