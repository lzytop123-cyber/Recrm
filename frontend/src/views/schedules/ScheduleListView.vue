<template>
  <div class="crm-page schedule-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-actions">
        <el-button type="primary" @click="openCreate">＋ 新建排期</el-button>
      </div>
    </header>

    <div class="schedule-tabs">
      <button
        v-for="item in tabs"
        :key="item.key"
        type="button"
        class="schedule-tab"
        :class="{ active: tab === item.key }"
        @click="setTab(item.key)"
      >
        {{ item.label }}
      </button>
    </div>

    <section class="schedule-summary">
      <div><small>{{ tab === 'month' ? '本月排期' : '本周排期' }}</small><b>{{ scopeStats.total }}</b></div>
      <div><small>待确认</small><b>{{ scopeStats.pending }}</b></div>
      <div><small>时间冲突</small><b class="danger">{{ scopeStats.conflict_count }}</b></div>
      <div><small>与我相关</small><b>{{ scopeStats.mine }}</b></div>
    </section>

    <!-- 周视图 -->
    <div v-if="tab === 'week'" class="calendar-shell">
      <div class="calendar-main">
        <div class="calendar-nav">
          <el-button @click="shiftWeek(-1)">上一周</el-button>
          <h2>{{ weekLabel }}</h2>
          <div>
            <el-button @click="goThisWeek">本周</el-button>
            <el-button @click="shiftWeek(1)">下一周</el-button>
          </div>
        </div>
        <div class="week-grid">
          <div class="corner"></div>
          <div v-for="d in weekDays" :key="d.key" class="day-head">
            <span>{{ d.weekday }}</span>
            <b>{{ d.day }}</b>
          </div>
          <template v-for="hour in workHours" :key="hour">
            <div class="hour-label">{{ String(hour).padStart(2, '0') }}:00</div>
            <div v-for="d in weekDays" :key="`${d.key}-${hour}`" class="day-col">
              <button
                v-for="lay in eventsAt(d.date, hour)"
                :key="lay.ev.id"
                type="button"
                class="cal-event"
                :class="[
                  lay.ev.status,
                  {
                    conflict: lay.ev.has_conflict,
                    capped: lay.capped,
                    narrow: lay.cols >= 3,
                  },
                ]"
                :style="eventStyle(lay, hour)"
                :title="eventTooltip(lay)"
                @click="openDrawer(lay.ev)"
              >
                <b>{{ lay.ev.title }}</b>
                <span class="cal-event-meta">
                  <template v-if="lay.capped">
                    {{ formatHm(lay.visStart) }}起 · 共{{ lay.totalHours }}h
                  </template>
                  <template v-else>
                    {{ formatHm(lay.visStart) }}–{{ formatHm(lay.visEnd) }}
                  </template>
                </span>
                <span v-if="!lay.narrow" class="cal-event-who">{{ lay.ev.employee_name }}</span>
              </button>
            </div>
          </template>
        </div>
      </div>
      <aside class="calendar-side">
        <div class="side-card">
          <h3>冲突提醒</h3>
          <div v-for="c in conflictItems.slice(0, 5)" :key="c.id" class="side-row">
            <span>{{ c.title }}</span>
            <b>{{ c.employee_name }}</b>
          </div>
          <div v-if="!conflictItems.length" class="side-row"><span>当前范围无冲突</span><b>—</b></div>
        </div>
        <div class="side-card">
          <h3>人员负载（本周）</h3>
          <div v-for="r in resourceLoads.slice(0, 5)" :key="r.employee_id" class="side-row">
            <span>{{ r.employee_name }}</span>
            <b>{{ r.load_percent }}%</b>
          </div>
          <div v-if="!resourceLoads.length" class="side-row"><span>暂无负载数据</span><b>—</b></div>
        </div>
      </aside>
    </div>

    <!-- 月视图 -->
    <div v-else-if="tab === 'month'" class="calendar-main">
      <div class="calendar-nav">
        <el-button @click="shiftMonth(-1)">上一月</el-button>
        <h2>{{ monthLabel }}</h2>
        <div>
          <el-button @click="goThisMonth">本月</el-button>
          <el-button @click="shiftMonth(1)">下一月</el-button>
        </div>
      </div>
      <div class="month-grid">
        <div v-for="w in ['一', '二', '三', '四', '五', '六', '日']" :key="w" class="day-head">周{{ w }}</div>
        <div
          v-for="cell in monthCells"
          :key="cell.key"
          class="month-cell"
          :class="{ muted: !cell.inMonth }"
        >
          <div class="day-num">{{ cell.day }}</div>
          <button
            v-for="ev in cell.events.slice(0, 3)"
            :key="ev.id"
            type="button"
            class="month-event"
            :class="[ev.status, { conflict: ev.has_conflict }]"
            @click="openDrawer(ev)"
          >
            {{ ev.title }}
          </button>
          <div v-if="cell.events.length > 3" style="font-size: 11px; color: var(--crm-ink-soft)">
            +{{ cell.events.length - 3 }}
          </div>
        </div>
      </div>
    </div>

    <!-- 讲师 / 主播 -->
    <template v-else-if="tab === 'instructor' || tab === 'streamer'">
      <div class="calendar-main" style="margin-bottom: 14px">
        <div class="calendar-nav">
          <el-button @click="shiftWeek(-1)">上一周</el-button>
          <h2>{{ weekLabel }}</h2>
          <div>
            <el-button @click="goThisWeek">本周</el-button>
            <el-button @click="shiftWeek(1)">下一周</el-button>
          </div>
        </div>
      </div>
      <div class="resource-load">
        <article v-for="r in resourceLoads" :key="r.employee_id" class="resource-card">
          <div class="top">
            <b>{{ r.employee_name }}</b>
            <span>{{ r.load_percent }}%</span>
          </div>
          <div class="load-meter" :class="{ high: r.load_percent >= 85 }">
            <i :style="{ width: `${r.load_percent}%` }"></i>
          </div>
          <div style="margin-top: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            {{ r.planned_hours }}h · {{ r.item_count }} 项
          </div>
        </article>
        <div v-if="!resourceLoads.length" style="color: var(--crm-ink-soft); font-size: 13px">
          当前范围暂无{{ tab === 'instructor' ? '讲师' : '主播' }}排期
        </div>
      </div>
      <el-table :data="resourceRows" stripe @row-click="openDrawer">
        <el-table-column prop="title" label="排期事项" min-width="160" />
        <el-table-column prop="employee_name" label="人员" width="100" />
        <el-table-column label="时间" min-width="220">
          <template #default="{ row }">{{ formatRange(row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}</el-tag>
            <el-tag v-if="row.has_conflict" type="danger" size="small" style="margin-left: 4px">冲突</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联" min-width="140">
          <template #default="{ row }">{{ relationText(row) }}</template>
        </el-table-column>
      </el-table>
      <p v-if="weekendCount > 0" class="schedule-weekend-hint">
        本周含 {{ weekendCount }} 条周末排期（统一周视图仅展示周一至周五，完整列表见本表）。
      </p>
    </template>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawer?.title || '排期详情'" size="480px" destroy-on-close>
      <template v-if="drawer">
        <div class="drawer-section">
          <el-tag size="small">{{ SCHEDULE_STATUS_LABEL[drawer.status] || drawer.status }}</el-tag>
          <el-tag v-if="drawer.has_conflict" type="danger" size="small" style="margin-left: 6px">冲突</el-tag>
          <el-tag size="small" type="info" style="margin-left: 6px">
            {{ typeLabel(drawer.schedule_type) }}
          </el-tag>
        </div>
        <div class="drawer-section">
          <h4>时间与人员</h4>
          <div class="drawer-grid">
            <div><small>人员</small><b>{{ drawer.employee_name || '—' }}</b></div>
            <div><small>角色</small><b>{{ resourceLabel(drawer.resource_type) }}</b></div>
            <div><small>开始</small><b>{{ formatTime(drawer.start_time) }}</b></div>
            <div><small>结束</small><b>{{ formatTime(drawer.end_time) }}</b></div>
            <div><small>计划工时</small><b>{{ drawer.planned_hours ?? '—' }}h</b></div>
            <div><small>地点</small><b>{{ drawer.location || '—' }}</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>关联业务</h4>
          <div class="drawer-grid">
            <div>
              <small>项目</small>
              <b>
                <el-button
                  v-if="drawer.project_id"
                  link
                  type="primary"
                  @click="$router.push(`/projects/${drawer.project_id}`)"
                >
                  {{ drawer.project_no }} · {{ drawer.project_name }}
                </el-button>
                <span v-else>—</span>
              </b>
            </div>
            <div><small>项目任务</small><b>{{ drawer.task_no ? `${drawer.task_no} · ${drawer.task_title}` : '—' }}</b></div>
            <div>
              <small>工单</small>
              <b>
                <el-button
                  v-if="drawer.ticket_id"
                  link
                  type="primary"
                  @click="$router.push(`/tickets/${drawer.ticket_id}`)"
                >
                  {{ drawer.ticket_no }}
                </el-button>
                <span v-else>—</span>
              </b>
            </div>
            <div>
              <small>飞书</small>
              <b>{{ FEISHU_SYNC_LABEL[drawer.feishu_sync_status || 'none'] }}</b>
            </div>
          </div>
        </div>
        <div v-if="drawer.coordination_note" class="drawer-section">
          <h4>协调说明</h4>
          <p style="margin: 0; white-space: pre-wrap">{{ drawer.coordination_note }}</p>
        </div>
        <div v-if="drawer.content" class="drawer-section">
          <h4>说明</h4>
          <p style="margin: 0; white-space: pre-wrap">{{ drawer.content }}</p>
        </div>
        <div v-if="drawer.has_conflict" class="drawer-section">
          <h4>冲突项</h4>
          <div v-for="c in drawer.conflicts || []" :key="c.id" class="side-row">
            <span>{{ c.title }}</span>
            <b>{{ SCHEDULE_STATUS_LABEL[c.status] || c.status }}</b>
          </div>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 8px">
          <el-button v-if="drawer.status === 'pending'" type="primary" @click="onConfirm">确认本人档期</el-button>
          <el-button v-if="drawer.status === 'pending'" @click="onCoordinate">请求协调</el-button>
          <el-button v-if="drawer.status === 'confirmed'" @click="onStart">开始执行</el-button>
          <el-button
            v-if="['confirmed', 'in_progress'].includes(drawer.status)"
            type="success"
            @click="openComplete"
          >
            完成并填工时
          </el-button>
          <el-button
            v-if="!['completed', 'cancelled'].includes(drawer.status)"
            type="danger"
            plain
            @click="onCancel"
          >
            取消排期
          </el-button>
          <el-button @click="$router.push(`/schedules/${drawer.id}`)">完整详情页</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="createVisible" title="新建排期" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="活动类型" prop="schedule_type">
          <el-radio-group v-model="form.schedule_type">
            <el-radio-button v-for="opt in SCHEDULE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="资源角色" prop="resource_type">
          <el-select v-model="form.resource_type" style="width: 100%">
            <el-option v-for="opt in SCHEDULE_RESOURCE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="人员" prop="employee_id">
          <el-select v-model="form.employee_id" filterable style="width: 100%">
            <el-option v-for="u in resources" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间" required>
          <el-date-picker
            v-model="form.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="关联项目">
          <el-select
            v-model="form.project_id"
            clearable
            filterable
            remote
            :remote-method="searchProjects"
            :loading="projectLoading"
            style="width: 100%"
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="`${p.project_no} · ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联任务">
          <el-select
            v-model="form.project_task_id"
            clearable
            filterable
            :disabled="!form.project_id"
            style="width: 100%"
          >
            <el-option
              v-for="t in taskOptions"
              :key="t.id"
              :label="`${t.task_no} · ${t.title}`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="线下地址或线上会议室" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.content" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">提交排期</el-button>
      </template>
    </el-dialog>

    <!-- 完成填工时 -->
    <el-dialog v-model="completeVisible" title="完成活动并填工时" width="480px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="活动结果" required>
          <el-input v-model="completeForm.result" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="实际工时" required>
          <el-input-number v-model="completeForm.actual_hours" :min="0.5" :max="24" :step="0.5" />
          <span style="margin-left: 8px; color: var(--crm-ink-soft); font-size: 12px">
            不等于排期时长自动覆盖
          </span>
        </el-form-item>
        <el-form-item label="生成工时">
          <el-switch v-model="completeForm.create_timesheet" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onComplete">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  FEISHU_SYNC_LABEL,
  SCHEDULE_RESOURCE_OPTIONS,
  SCHEDULE_STATUS_LABEL,
  SCHEDULE_TYPE_OPTIONS,
  cancelSchedule,
  completeSchedule,
  confirmSchedule,
  coordinateSchedule,
  createSchedule,
  fetchResourceLoad,
  fetchResourceOptions,
  fetchScheduleStats,
  fetchSchedules,
  startSchedule,
  type ResourceLoad,
  type ResourceOption,
  type Schedule,
  type ScheduleStats,
} from '@/api/schedules'
import { fetchProjects, fetchProjectTasks, type Project, type ProjectTask } from '@/api/projects'
import { useUserStore } from '@/stores/user'

type TabKey = 'week' | 'month' | 'instructor' | 'streamer'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'week', label: '统一周视图' },
  { key: 'month', label: '统一月视图' },
  { key: 'instructor', label: '讲师排期' },
  { key: 'streamer', label: '主播排期' },
]

const loading = ref(false)
const saving = ref(false)
const projectLoading = ref(false)
const tab = ref<TabKey>('week')
const items = ref<Schedule[]>([])
const stats = ref<ScheduleStats | null>(null)
const userStore = useUserStore()
const resourceLoads = ref<ResourceLoad[]>([])
const resources = ref<ResourceOption[]>([])
const projectOptions = ref<Project[]>([])
const taskOptions = ref<ProjectTask[]>([])
const anchor = ref(startOfDay(new Date()))

const drawerVisible = ref(false)
const drawer = ref<Schedule | null>(null)
const createVisible = ref(false)
const completeVisible = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  title: '',
  schedule_type: 'internal_training',
  resource_type: 'instructor',
  employee_id: undefined as number | undefined,
  project_id: undefined as number | undefined,
  project_task_id: undefined as number | undefined,
  location: '',
  content: '',
  range: [] as string[],
})

const completeForm = reactive({
  result: '',
  actual_hours: 2,
  create_timesheet: true,
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  schedule_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  resource_type: [{ required: true, message: '请选择角色', trigger: 'change' }],
  employee_id: [{ required: true, message: '请选择人员', trigger: 'change' }],
}

const workHours = Array.from({ length: 14 }, (_, i) => i + 7) // 07-20，覆盖常见早晚场
const hourStart = workHours[0]
const hourEnd = workHours[workHours.length - 1]

const weekDays = computed(() => {
  const monday = startOfWeek(anchor.value)
  return Array.from({ length: 5 }, (_, i) => {
    const d = addDays(monday, i)
    return {
      key: fmtDate(d),
      date: d,
      weekday: ['周一', '周二', '周三', '周四', '周五'][i],
      day: `${d.getMonth() + 1}/${d.getDate()}`,
    }
  })
})

const weekLabel = computed(() => {
  const monday = startOfWeek(anchor.value)
  const sunday = addDays(monday, 6)
  return `${fmtDate(monday)} ~ ${fmtDate(sunday)}`
})

const monthLabel = computed(() => `${anchor.value.getFullYear()}年${anchor.value.getMonth() + 1}月`)

const monthCells = computed(() => {
  const year = anchor.value.getFullYear()
  const month = anchor.value.getMonth()
  const first = new Date(year, month, 1)
  const start = addDays(first, -((first.getDay() + 6) % 7))
  return Array.from({ length: 42 }, (_, i) => {
    const d = addDays(start, i)
    const key = fmtDate(d)
    const { start: dayStart, end: dayEnd } = dayBounds(d)
    return {
      key,
      day: d.getDate(),
      inMonth: d.getMonth() === month,
      events: items.value.filter((x) => {
        const s = parseDt(x.start_time)
        const e = parseDt(x.end_time)
        return s < dayEnd && e > dayStart
      }),
    }
  })
})

/** 顶部 KPI 按当前视图已加载数据统计，避免与周/月网格不一致 */
const scopeStats = computed(() => {
  const list = items.value
  const myId = userStore.user?.id
  return {
    total: list.length,
    pending: list.filter((x) => x.status === 'pending').length,
    conflict_count: list.filter((x) => x.has_conflict).length,
    mine: list.filter(
      (x) => x.employee_id === myId || x.creator_id === myId,
    ).length,
  }
})

const conflictItems = computed(() => items.value.filter((x) => x.has_conflict))
const resourceRows = computed(() =>
  items.value.filter((x) =>
    tab.value === 'instructor' ? x.resource_type === 'instructor' : x.resource_type === 'streamer',
  ),
)
const weekendCount = computed(
  () =>
    resourceRows.value.filter((x) => {
      const day = parseDt(x.start_time).getDay()
      return day === 0 || day === 6
    }).length,
)

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function startOfWeek(d: Date) {
  const day = (d.getDay() + 6) % 7
  return addDays(startOfDay(d), -day)
}

function addDays(d: Date, n: number) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

function fmtDate(d: Date) {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** 本地墙钟 → YYYY-MM-DDTHH:mm:ss（勿用 toISOString，会变成 UTC） */
function formatLocalDateTime(d: Date) {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** 表单本地时间字符串 → 带偏移的 ISO，避免后端把 naive 当 UTC */
function localWallToAwareIso(v: string) {
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return v
  const d = new Date(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4]),
    Number(m[5]),
    Number(m[6] || 0),
  )
  const offsetMin = -d.getTimezoneOffset()
  const sign = offsetMin >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMin)
  const oh = String(Math.floor(abs / 60)).padStart(2, '0')
  const om = String(abs % 60).padStart(2, '0')
  return `${formatLocalDateTime(d)}${sign}${oh}:${om}`
}

/** 后端存 UTC；无时区后缀时按 UTC 解析，避免被当成本地凌晨导致周视图丢件 */
function parseDt(v: string) {
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v)) {
    return new Date(`${v}Z`)
  }
  return new Date(v)
}

function clampHour(h: number) {
  return Math.min(hourEnd, Math.max(hourStart, h))
}

function dayBounds(day: Date) {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, 0, 0, 0)
  const end = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1, 0, 0, 0, 0)
  return { start, end }
}

function workBounds(day: Date) {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hourStart, 0, 0, 0)
  // hourEnd 格表示 [hourEnd, hourEnd+1)
  const end = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hourEnd + 1, 0, 0, 0)
  return { start, end }
}

/** 排期在某自然日内、落在工作时段内的可见片段 */
function segmentOnDay(ev: Schedule, day: Date) {
  const s = parseDt(ev.start_time)
  const e = parseDt(ev.end_time)
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime()) || e <= s) return null

  const { start: dayStart, end: dayEnd } = dayBounds(day)
  const segStart = new Date(Math.max(s.getTime(), dayStart.getTime()))
  const segEnd = new Date(Math.min(e.getTime(), dayEnd.getTime()))
  if (segEnd <= segStart) return null

  const wb = workBounds(day)
  let visStart = new Date(Math.max(segStart.getTime(), wb.start.getTime()))
  let visEnd = new Date(Math.min(segEnd.getTime(), wb.end.getTime()))

  // 整天都在工作时段外：钉在首/末格，避免丢件
  if (visEnd <= visStart) {
    if (segEnd <= wb.start) {
      visStart = wb.start
      visEnd = new Date(wb.start.getTime() + 30 * 60 * 1000)
    } else if (segStart >= wb.end) {
      visEnd = wb.end
      visStart = new Date(wb.end.getTime() - 30 * 60 * 1000)
    } else {
      return null
    }
  }
  return { visStart, visEnd }
}

/** 周视图单块最长视觉高度（小时），超长排期缩成短条 + 标注总时长，避免糊成整列 */
const MAX_VIS_HOURS = 2.5

type DayLayout = {
  ev: Schedule
  visStart: Date
  visEnd: Date
  renderHour: number
  col: number
  cols: number
  visHours: number
  totalHours: number
  capped: boolean
}

function formatHm(d: Date) {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}`
}

function layoutDay(day: Date): DayLayout[] {
  const segs: DayLayout[] = []
  for (const ev of items.value) {
    const seg = segmentOnDay(ev, day)
    if (!seg) continue
    const totalHours = Math.max(
      0.5,
      Math.round(((parseDt(ev.end_time).getTime() - parseDt(ev.start_time).getTime()) / 3600000) * 10) / 10,
    )
    const rawVis = (seg.visEnd.getTime() - seg.visStart.getTime()) / 3600000
    const capped = rawVis > MAX_VIS_HOURS
    segs.push({
      ev,
      visStart: seg.visStart,
      visEnd: seg.visEnd,
      renderHour: clampHour(seg.visStart.getHours()),
      col: 0,
      cols: 1,
      visHours: Math.max(0.5, Math.min(MAX_VIS_HOURS, rawVis)),
      totalHours,
      capped,
    })
  }
  segs.sort(
    (a, b) =>
      a.visStart.getTime() - b.visStart.getTime() ||
      b.visEnd.getTime() - a.visEnd.getTime() ||
      a.ev.id - b.ev.id,
  )

  // 重叠并排：贪心分栏（类似 Google 日历）
  const colEnd: number[] = []
  for (const s of segs) {
    let col = 0
    while (col < colEnd.length && colEnd[col] > s.visStart.getTime()) col += 1
    s.col = col
    colEnd[col] = s.visEnd.getTime()
  }
  for (const s of segs) {
    const peers = segs.filter((o) => o.visStart < s.visEnd && o.visEnd > s.visStart)
    s.cols = Math.max(1, ...peers.map((p) => p.col + 1))
  }
  return segs
}

const weekLayouts = computed(() => {
  const map = new Map<string, DayLayout[]>()
  for (const d of weekDays.value) {
    map.set(d.key, layoutDay(d.date))
  }
  return map
})

function eventsAt(day: Date, hour: number) {
  return (weekLayouts.value.get(fmtDate(day)) || []).filter((x) => x.renderHour === hour)
}

function eventTooltip(lay: DayLayout) {
  const range = `${formatTime(lay.ev.start_time)} ~ ${formatTime(lay.ev.end_time)}`
  const who = lay.ev.employee_name || ''
  const conflict = lay.ev.has_conflict ? '（冲突）' : ''
  return `${lay.ev.title}${conflict}\n${range}\n${who}`.trim()
}

function eventStyle(lay: DayLayout, hour: number) {
  const top = lay.visStart.getHours() === hour ? (lay.visStart.getMinutes() / 60) * 48 : 0
  const remain = hourEnd - hour + 1
  const heightHours = Math.min(lay.visHours, remain)
  const widthPct = 100 / lay.cols
  const leftPct = lay.col * widthPct
  return {
    top: `${top}px`,
    height: `${Math.max(28, heightHours * 48 - 4)}px`,
    left: `calc(${leftPct}% + 2px)`,
    width: `calc(${widthPct}% - 4px)`,
    right: 'auto',
    zIndex: String(3 + lay.col),
  }
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  const d = parseDt(v)
  if (Number.isNaN(d.getTime())) return v.replace('T', ' ').slice(0, 16)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day} ${hh}:${mm}`
}

function formatRange(row: Schedule) {
  return `${formatTime(row.start_time)} ~ ${formatTime(row.end_time)}`
}

function typeLabel(v?: string | null) {
  return SCHEDULE_TYPE_OPTIONS.find((x) => x.value === v)?.label || v || '其他'
}

function resourceLabel(v: string) {
  return SCHEDULE_RESOURCE_OPTIONS.find((x) => x.value === v)?.label || v
}

function relationText(row: Schedule) {
  if (row.task_no) return `任务 · ${row.task_no}`
  if (row.ticket_no) return `工单 · ${row.ticket_no}`
  if (row.project_name) return `项目 · ${row.project_name}`
  return '—'
}

function rangeParams() {
  // 列表/负载按自然周周一～周日，避免周六日新建的排期在「本周」表格里消失
  if (tab.value === 'month') {
    const y = anchor.value.getFullYear()
    const m = anchor.value.getMonth()
    const from = new Date(y, m, 1, 0, 0, 0)
    const to = new Date(y, m + 1, 0, 23, 59, 59)
    return {
      date_from: localWallToAwareIso(formatLocalDateTime(from)),
      date_to: localWallToAwareIso(formatLocalDateTime(to)),
    }
  }
  const monday = startOfWeek(anchor.value)
  const sunday = addDays(monday, 6)
  sunday.setHours(23, 59, 59, 0)
  return {
    date_from: localWallToAwareIso(formatLocalDateTime(monday)),
    date_to: localWallToAwareIso(formatLocalDateTime(sunday)),
  }
}

async function loadStats() {
  const { data } = await fetchScheduleStats()
  stats.value = data
}

async function fetchScheduleItems() {
  loading.value = true
  try {
    const range = rangeParams()
    const resourceType =
      tab.value === 'instructor' ? 'instructor' : tab.value === 'streamer' ? 'streamer' : undefined
    const { data } = await fetchSchedules({
      ...range,
      resource_type: resourceType,
      page: 1,
      page_size: 100,
    })
    items.value = data.items
    if (tab.value === 'week' || tab.value === 'instructor' || tab.value === 'streamer') {
      const rt = tab.value === 'streamer' ? 'streamer' : 'instructor'
      const { data: load } = await fetchResourceLoad({
        resource_type: rt,
        date_from: range.date_from,
        date_to: range.date_to,
      })
      resourceLoads.value = load.items
    }
  } finally {
    loading.value = false
  }
}

async function reload() {
  await Promise.all([loadStats(), fetchScheduleItems()])
}

function setTab(key: TabKey) {
  tab.value = key
}

function shiftWeek(n: number) {
  anchor.value = addDays(anchor.value, n * 7)
}

function goThisWeek() {
  anchor.value = startOfDay(new Date())
}

function shiftMonth(n: number) {
  const d = new Date(anchor.value)
  d.setMonth(d.getMonth() + n)
  anchor.value = d
}

function goThisMonth() {
  const now = new Date()
  anchor.value = new Date(now.getFullYear(), now.getMonth(), 1)
}

function openDrawer(row: Schedule) {
  drawer.value = row
  drawerVisible.value = true
}

async function searchProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchProjects({ keyword: q || undefined, page: 1, page_size: 30 })
    projectOptions.value = data.items
  } finally {
    projectLoading.value = false
  }
}

async function onProjectChange(pid?: number) {
  form.project_task_id = undefined
  taskOptions.value = []
  if (!pid) return
  const { data } = await fetchProjectTasks({ project_id: pid, page: 1, page_size: 100 })
  taskOptions.value = data.items
}

function openCreate() {
  form.title = ''
  form.schedule_type = 'internal_training'
  form.resource_type = tab.value === 'streamer' ? 'streamer' : 'instructor'
  form.employee_id = resources.value[0]?.id
  form.project_id = undefined
  form.project_task_id = undefined
  form.location = ''
  form.content = ''
  const start = new Date()
  start.setMinutes(0, 0, 0)
  start.setHours(10)
  const end = new Date(start)
  end.setHours(12)
  form.range = [formatLocalDateTime(start), formatLocalDateTime(end)]
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.employee_id || form.range.length !== 2) {
    ElMessage.warning('请完整填写必填项与时间')
    return
  }
  saving.value = true
  try {
    const { data } = await createSchedule({
      title: form.title.trim(),
      schedule_type: form.schedule_type,
      resource_type: form.resource_type,
      employee_id: form.employee_id,
      project_id: form.project_id,
      project_task_id: form.project_task_id,
      start_time: localWallToAwareIso(form.range[0]),
      end_time: localWallToAwareIso(form.range[1]),
      location: form.location || undefined,
      content: form.content || undefined,
    })
    ElMessage.success('排期已创建')
    createVisible.value = false
    // 跳到该排期所在周，避免周末/跨周新建后在当前周表格里找不到
    const start = parseDt(data.start_time)
    if (!Number.isNaN(start.getTime())) {
      anchor.value = startOfDay(start)
    }
    if (
      (tab.value === 'instructor' && data.resource_type !== 'instructor') ||
      (tab.value === 'streamer' && data.resource_type !== 'streamer')
    ) {
      ElMessage.info(
        `当前在「${tab.value === 'streamer' ? '主播' : '讲师'}排期」页，该条资源角色为「${resourceLabel(data.resource_type)}」，请切换对应页签查看`,
      )
    }
    await reload()
    openDrawer(data)
  } finally {
    saving.value = false
  }
}

async function onConfirm() {
  if (!drawer.value) return
  try {
    await ElMessageBox.confirm('确认本人档期可用？', '确认排期')
    const { data } = await confirmSchedule(drawer.value.id)
    drawer.value = data
    ElMessage.success('已确认')
    await reload()
  } catch {
    /* cancel */
  }
}

async function onCoordinate() {
  if (!drawer.value) return
  try {
    const { value } = await ElMessageBox.prompt('请说明需要协调的原因', '请求协调', {
      inputType: 'textarea',
    })
    if (!value?.trim()) return
    const { data } = await coordinateSchedule(drawer.value.id, value.trim())
    drawer.value = data
    ElMessage.success('已提交协调请求')
    await reload()
  } catch {
    /* cancel */
  }
}

async function onStart() {
  if (!drawer.value) return
  const { data } = await startSchedule(drawer.value.id)
  drawer.value = data
  ElMessage.success('已开始')
  await reload()
}

function openComplete() {
  if (!drawer.value) return
  completeForm.result = ''
  completeForm.actual_hours = Number(drawer.value.planned_hours || 2)
  completeForm.create_timesheet = true
  completeVisible.value = true
}

async function onComplete() {
  if (!drawer.value || !completeForm.result.trim()) {
    ElMessage.warning('请填写活动结果')
    return
  }
  saving.value = true
  try {
    const { data } = await completeSchedule(drawer.value.id, {
      result: completeForm.result.trim(),
      actual_hours: completeForm.actual_hours,
      create_timesheet: completeForm.create_timesheet,
    })
    drawer.value = data
    completeVisible.value = false
    ElMessage.success(data.timesheet_id ? `已完成，工时草稿 #${data.timesheet_id}` : '已完成')
    await reload()
  } finally {
    saving.value = false
  }
}

async function onCancel() {
  if (!drawer.value) return
  try {
    const { value } = await ElMessageBox.prompt('可选填写取消原因', '取消排期', {
      inputType: 'textarea',
      confirmButtonText: '确认取消',
    })
    const { data } = await cancelSchedule(drawer.value.id, value || undefined)
    drawer.value = data
    ElMessage.success('已取消')
    await reload()
  } catch {
    /* cancel */
  }
}

watch([tab, anchor], () => {
  reload()
})

onMounted(async () => {
  const { data } = await fetchResourceOptions()
  resources.value = data
  await searchProjects('')
  await reload()
})
</script>
