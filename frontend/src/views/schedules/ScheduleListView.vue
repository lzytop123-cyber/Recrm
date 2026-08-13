<template>
  <div class="crm-page schedule-workbench crm-fit-page" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="wb-eyebrow">经营台</p>
        <h1>排期会议</h1>
        <p>一张表看档期：点空白格新建，点色块处理；同人同色；已取消不占格子；同人时间重叠才算冲突。</p>
      </div>
      <div class="sales-head-actions">
        <el-button type="primary" @click="openCreate()">＋ 新建排期</el-button>
      </div>
    </header>

    <div class="schedule-toolbar">
      <div class="schedule-tabs" aria-label="视图">
        <button
          v-for="item in viewModes"
          :key="item.key"
          type="button"
          class="schedule-tab"
          :class="{ active: viewMode === item.key }"
          @click="viewMode = item.key"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="schedule-tabs role-tabs" aria-label="角色筛选">
        <button
          v-for="item in roleFilters"
          :key="item.key"
          type="button"
          class="schedule-tab"
          :class="{ active: roleFilter === item.key }"
          @click="roleFilter = item.key"
        >
          {{ item.label }}
        </button>
      </div>
      <section class="schedule-summary" aria-label="当前范围统计">
        <div>
          <small>{{ viewMode === 'month' ? '有效事项' : '本周有效' }}</small>
          <b>{{ scopeStats.total }}</b>
        </div>
        <div>
          <small>待确认</small>
          <b>{{ scopeStats.pending }}</b>
        </div>
        <div :class="{ alert: scopeStats.conflict_count > 0 }">
          <small>冲突</small>
          <b class="danger">{{ scopeStats.conflict_count }}</b>
        </div>
      </section>
    </div>

    <div class="crm-fit-body" :class="{ 'is-scroll': isCompact || viewMode === 'month' }">
    <!-- 周视图 -->
    <div
      v-if="viewMode === 'week'"
      class="calendar-shell"
      :class="{ 'drawer-open': drawerVisible }"
    >
      <div class="calendar-main">
        <div class="calendar-nav">
          <el-button @click="shiftWeek(-1)">上一周</el-button>
          <h2>{{ weekLabel }}</h2>
          <div>
            <el-button @click="goThisWeek">本周</el-button>
            <el-button @click="shiftWeek(1)">下一周</el-button>
          </div>
        </div>
        <div v-if="visiblePeople.length" class="person-legend" aria-label="人员颜色">
          <span v-for="p in visiblePeople" :key="p.id" class="person-legend-item">
            <i :style="{ background: personColor(p.id) }" aria-hidden="true"></i>
            {{ p.name }}
          </span>
        </div>
        <div class="week-grid-wrap">
          <div class="week-grid">
            <div class="corner"></div>
            <div
              v-for="d in weekDays"
              :key="d.key"
              class="day-head"
              :class="{ weekend: d.weekend }"
            >
              <span>{{ d.weekday }}</span>
              <b>{{ d.day }}</b>
            </div>
            <template v-for="hour in workHours" :key="hour">
              <div class="hour-label">{{ String(hour).padStart(2, '0') }}:00</div>
              <div
                v-for="d in weekDays"
                :key="`${d.key}-${hour}`"
                class="day-col"
                :class="{ weekend: d.weekend }"
                :title="`${d.weekday} ${String(hour).padStart(2, '0')}:00 点击新建`"
                @click="openCreateFromSlot(d.date, hour)"
              >
                <button
                  v-for="lay in eventsAt(d.date, hour)"
                  :key="lay.ev.id"
                  type="button"
                  class="cal-event"
                  :class="[
                    lay.ev.status,
                    {
                      conflict: rowHasConflict(lay.ev),
                      capped: lay.capped,
                      narrow: lay.cols >= 3,
                    },
                  ]"
                  :style="eventStyle(lay, hour)"
                  :title="eventTooltip(lay)"
                  @click.stop="openDrawer(lay.ev)"
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
                  <span v-if="lay.cols < 3" class="cal-event-who">{{ lay.ev.employee_name }}</span>
                </button>
              </div>
            </template>
          </div>
          <div v-if="!weekHasVisibleEvents" class="week-empty">
            {{
              roleFilter === 'all'
                ? '本周暂无有效排期，可点击空白格子或右上角新建。'
                : `本周暂无「${roleFilterLabel}」排期，可点击空白格子或右上角新建。`
            }}
          </div>
        </div>
      </div>
      <aside v-show="!drawerVisible" class="calendar-side">
        <div class="side-card">
          <h3>需关注</h3>
          <template v-if="attentionItems.length">
            <button
              v-for="c in attentionItems"
              :key="`${c.kind}-${c.item.id}`"
              type="button"
              class="side-row side-row-btn"
              @click="openDrawer(c.item)"
            >
              <span>
                <i class="side-kind" :class="c.kind">{{ c.kind === 'conflict' ? '冲突' : '待确认' }}</i>
                {{ c.item.title }}
              </span>
              <b>{{ c.item.employee_name }}</b>
            </button>
          </template>
          <div v-else class="side-row">
            <span>暂无冲突或待确认</span>
            <b>—</b>
          </div>
        </div>
        <div class="side-card">
          <h3>人员负载</h3>
          <div
            v-for="r in sideLoads.slice(0, 6)"
            :key="r.employee_id"
            class="side-load"
            :style="{ '--person-color': personColor(r.employee_id) }"
          >
            <div class="side-row">
              <span>
                <i class="person-swatch" aria-hidden="true"></i>
                {{ r.employee_name }}
              </span>
              <b>{{ r.load_percent }}%</b>
            </div>
            <div class="load-meter" :class="{ high: r.load_percent >= 85 }">
              <i :style="{ width: `${Math.min(100, r.load_percent)}%` }"></i>
            </div>
            <div class="side-load-meta">{{ r.planned_hours }}h · {{ r.item_count }} 项</div>
          </div>
          <div v-if="!sideLoads.length" class="side-row">
            <span>暂无负载</span>
            <b>—</b>
          </div>
        </div>
      </aside>
    </div>

    <!-- 月视图 -->
    <div v-else class="calendar-main">
        <div class="calendar-nav">
          <el-button @click="shiftMonth(-1)">上一月</el-button>
          <h2>{{ monthLabel }}</h2>
          <div>
            <el-button @click="goThisMonth">本月</el-button>
            <el-button @click="shiftMonth(1)">下一月</el-button>
          </div>
        </div>
        <div v-if="visiblePeople.length" class="person-legend" aria-label="人员颜色">
          <span v-for="p in visiblePeople" :key="p.id" class="person-legend-item">
            <i :style="{ background: personColor(p.id) }" aria-hidden="true"></i>
            {{ p.name }}
          </span>
        </div>
        <div class="month-grid">
        <div v-for="w in ['一', '二', '三', '四', '五', '六', '日']" :key="w" class="day-head">周{{ w }}</div>
        <div
          v-for="cell in monthCells"
          :key="cell.key"
          class="month-cell"
          :class="{ muted: !cell.inMonth }"
          :title="`${cell.key} 点击新建`"
          @click="openCreateFromSlot(cell.date, 10)"
        >
          <div class="day-num">{{ cell.day }}</div>
          <button
            v-for="ev in cell.events.slice(0, 3)"
            :key="ev.id"
            type="button"
            class="month-event"
            :class="[ev.status, { conflict: rowHasConflict(ev) }]"
            :style="personChipStyle(ev.employee_id)"
            @click.stop="openDrawer(ev)"
          >
            {{ ev.title }}
          </button>
          <div
            v-if="cell.events.length > 3"
            class="month-more"
            @click.stop
          >
            +{{ cell.events.length - 3 }}
          </div>
        </div>
      </div>
    </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :size="isCompact ? '100%' : '440px'"
      destroy-on-close
      class="schedule-detail-drawer"
      :with-header="false"
    >
      <template v-if="drawer">
        <div class="sch-drawer">
          <header class="sch-drawer-hero">
            <div class="sch-drawer-top">
              <div class="sch-drawer-tags">
                <el-tag :type="statusTagType(drawer.status)" effect="light" size="small">
                  {{ SCHEDULE_STATUS_LABEL[drawer.status] || drawer.status }}
                </el-tag>
                <el-tag v-if="rowHasConflict(drawer)" type="danger" effect="light" size="small">冲突</el-tag>
                <el-tag type="info" effect="plain" size="small">{{ typeLabel(drawer.schedule_type) }}</el-tag>
                <el-tag effect="plain" size="small">{{ linkModeLabel(drawer) }}</el-tag>
              </div>
              <button type="button" class="sch-drawer-close" aria-label="关闭" @click="drawerVisible = false">
                ×
              </button>
            </div>
            <h2>{{ drawer.title || '排期详情' }}</h2>
            <p class="sch-drawer-meta">
              {{ drawer.employee_name || '未指定人员' }}
              <span> · {{ resourceLabel(drawer.resource_type) }}</span>
            </p>
            <p class="sch-drawer-time">
              {{ formatRange(drawer) }}
              <span v-if="drawer.planned_hours != null"> · {{ drawer.planned_hours }}h</span>
            </p>
          </header>

          <div class="sch-drawer-body">
            <div v-if="rowHasConflict(drawer)" class="sch-conflict">
              <div class="sch-conflict-title">时间冲突（同一人有效档期重叠）</div>
              <p class="sch-conflict-desc">请改时间、换人，或取消其中一条。已取消/已完成不参与冲突。</p>
              <button
                v-for="c in activeConflicts(drawer)"
                :key="c.id"
                type="button"
                class="sch-conflict-row"
                @click="openConflict(c)"
              >
                <span>
                  {{ c.title }}
                  <small>{{ formatTime(c.start_time) }} ~ {{ formatTime(c.end_time) }}</small>
                </span>
                <b>{{ SCHEDULE_STATUS_LABEL[c.status] || c.status }}</b>
              </button>
            </div>

            <dl class="sch-kv">
              <div class="sch-kv-row">
                <dt>关联方式</dt>
                <dd>{{ linkModeLabel(drawer) }}</dd>
              </div>
              <div class="sch-kv-row">
                <dt>地点</dt>
                <dd>{{ drawer.location || '—' }}</dd>
              </div>
              <div class="sch-kv-row">
                <dt>飞书同步</dt>
                <dd>{{ FEISHU_SYNC_LABEL[drawer.feishu_sync_status || 'none'] }}</dd>
              </div>
              <div v-if="drawer.project_id" class="sch-kv-row">
                <dt>项目</dt>
                <dd>
                  <el-button link type="primary" @click="$router.push(`/projects/${drawer.project_id}`)">
                    {{ drawer.project_no }} · {{ drawer.project_name }}
                  </el-button>
                </dd>
              </div>
              <div v-if="drawer.task_no" class="sch-kv-row">
                <dt>任务</dt>
                <dd>{{ drawer.task_no }} · {{ drawer.task_title }}</dd>
              </div>
              <div v-if="drawer.ticket_id" class="sch-kv-row">
                <dt>工单</dt>
                <dd>
                  <el-button link type="primary" @click="$router.push(`/tickets/${drawer.ticket_id}`)">
                    {{ drawer.ticket_no }}
                  </el-button>
                </dd>
              </div>
            </dl>

            <section v-if="drawer.content" class="sch-note">
              <h4>说明</h4>
              <p>{{ drawer.content }}</p>
            </section>
            <section v-if="drawer.coordination_note" class="sch-note">
              <h4>协调说明</h4>
              <p>{{ drawer.coordination_note }}</p>
            </section>
          </div>

          <footer class="sch-drawer-footer">
            <div class="sch-drawer-actions">
              <el-button v-if="drawer.status === 'pending'" type="primary" @click="onConfirm">
                确认本人档期
              </el-button>
              <el-button v-if="drawer.status === 'pending'" @click="onCoordinate">请求协调</el-button>
              <el-button v-if="drawer.status === 'confirmed'" type="primary" @click="onStart">开始执行</el-button>
              <el-button
                v-if="['confirmed', 'in_progress'].includes(drawer.status)"
                type="success"
                @click="openComplete"
              >
                完成并填工时
              </el-button>
            </div>
            <div class="sch-drawer-links">
              <el-button
                v-if="!['completed', 'cancelled'].includes(drawer.status)"
                type="danger"
                link
                @click="onCancel"
              >
                取消排期
              </el-button>
              <el-button link type="primary" @click="$router.push(`/schedules/${drawer.id}`)">
                完整详情
              </el-button>
            </div>
          </footer>
        </div>
      </template>
    </el-drawer>

    <!-- 新建 -->
    <el-dialog
      v-model="createVisible"
      title="新建排期"
      width="640px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="活动类型" prop="schedule_type">
          <el-radio-group v-model="form.schedule_type" class="schedule-type-group">
            <el-radio-button v-for="opt in SCHEDULE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="关联方式" prop="link_mode">
          <el-radio-group v-model="form.link_mode" class="schedule-type-group" @change="onLinkModeChange">
            <el-radio-button v-for="opt in LINK_MODE_OPTIONS" :key="opt.value" :value="opt.value">
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
          <div class="field-tip">用于排期分类筛选，与选人无关</div>
        </el-form-item>
        <el-form-item label="人员" prop="employee_id">
          <el-tree-select
            v-model="form.employee_id"
            :data="personTree"
            filterable
            check-strictly
            default-expand-all
            :render-after-expand="false"
            :loading="personTreeLoading"
            teleported
            :placement="isCompact ? 'top' : 'bottom'"
            popper-class="schedule-person-popper"
            placeholder="按组织架构选择人员"
            style="width: 100%"
            :props="{ label: 'label', value: 'value', children: 'children', disabled: 'disabled' }"
          />
          <div v-if="!personTreeLoading && !personTreeHasPeople" class="field-tip">
            组织架构暂无在职人员，请先在组织架构维护员工
          </div>
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
        <el-form-item v-if="form.link_mode !== 'none'" label="挂到项目" prop="project_id">
          <el-select
            v-model="form.project_id"
            clearable
            filterable
            remote
            :remote-method="searchProjects"
            :loading="projectLoading"
            :placeholder="
              form.link_mode === 'task'
                ? '请先选择项目，再选任务'
                : '挂到交付项目后，在交付执行里可见'
            "
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
        <el-form-item v-if="form.link_mode === 'task'" label="挂到任务" prop="project_task_id">
          <el-select
            v-model="form.project_task_id"
            clearable
            filterable
            :disabled="!form.project_id"
            placeholder="请选择所属任务"
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
    <el-dialog
      v-model="completeVisible"
      title="完成活动并填工时"
      width="480px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="活动结果" required>
          <el-input v-model="completeForm.result" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="实际工时" required>
          <el-input-number
            v-model="completeForm.actual_hours"
            :min="0.5"
            :max="24"
            :step="0.5"
            style="width: 100%"
          />
          <div class="field-tip">不等于排期时长自动覆盖</div>
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
import { useRoute } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
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
  fetchPersonTree,
  fetchResourceLoad,
  fetchScheduleDetail,
  fetchSchedules,
  startSchedule,
  type PersonTreeNode,
  type ResourceLoad,
  type Schedule,
  type ScheduleConflict,
} from '@/api/schedules'
import {
  fetchDirectoryProjects,
  fetchDirectoryProjectTasks,
  type DirectoryProject,
  type DirectoryProjectTask,
} from '@/api/directory'

type ViewMode = 'week' | 'month'
type RoleFilter = 'all' | 'instructor' | 'streamer' | 'shooting_edit'

const viewModes: { key: ViewMode; label: string }[] = [
  { key: 'week', label: '周' },
  { key: 'month', label: '月' },
]

const roleFilters: { key: RoleFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'instructor', label: '讲师' },
  { key: 'streamer', label: '主播' },
  { key: 'shooting_edit', label: '拍摄剪辑' },
]

const route = useRoute()
const isCompact = useMatchMedia('(max-width: 768px)')
const loading = ref(false)
const saving = ref(false)
const projectLoading = ref(false)
const viewMode = ref<ViewMode>('week')
const roleFilter = ref<RoleFilter>('all')
const items = ref<Schedule[]>([])
const resourceLoads = ref<ResourceLoad[]>([])
const personTree = ref<PersonTreeNode[]>([])
const personTreeLoading = ref(false)
const personTreeHasPeople = computed(() => {
  const walk = (nodes: PersonTreeNode[]): boolean => {
    for (const n of nodes) {
      if (n.is_person) return true
      if (n.children?.length && walk(n.children)) return true
    }
    return false
  }
  return walk(personTree.value)
})
const projectOptions = ref<DirectoryProject[]>([])
const taskOptions = ref<DirectoryProjectTask[]>([])
const anchor = ref(startOfDay(new Date()))

const roleFilterLabel = computed(
  () => roleFilters.find((x) => x.key === roleFilter.value)?.label || '',
)

const drawerVisible = ref(false)
const drawer = ref<Schedule | null>(null)
const createVisible = ref(false)
const completeVisible = ref(false)
const formRef = ref<FormInstance>()

type LinkMode = 'none' | 'project' | 'task'

const LINK_MODE_OPTIONS: { value: LinkMode; label: string }[] = [
  { value: 'none', label: '一般活动' },
  { value: 'project', label: '项目排期' },
  { value: 'task', label: '任务排期' },
]

const form = reactive({
  title: '',
  schedule_type: 'internal_training',
  link_mode: 'none' as LinkMode,
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

const rules = computed<FormRules>(() => ({
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  schedule_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  link_mode: [{ required: true, message: '请选择关联方式', trigger: 'change' }],
  resource_type: [{ required: true, message: '请选择角色', trigger: 'change' }],
  employee_id: [{ required: true, message: '请选择人员', trigger: 'change' }],
  project_id:
    form.link_mode === 'none'
      ? []
      : [{ required: true, message: '请选择项目', trigger: 'change' }],
  project_task_id:
    form.link_mode === 'task'
      ? [{ required: true, message: '请选择任务', trigger: 'change' }]
      : [],
}))

const workHours = Array.from({ length: 11 }, (_, i) => i + 8) // 08-18，早上八点到晚上七点
const hourStart = workHours[0]
const hourEnd = workHours[workHours.length - 1]

const weekDays = computed(() => {
  const monday = startOfWeek(anchor.value)
  const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  return Array.from({ length: 7 }, (_, i) => {
    const d = addDays(monday, i)
    return {
      key: fmtDate(d),
      date: d,
      weekday: labels[i],
      day: `${d.getMonth() + 1}/${d.getDate()}`,
      weekend: i >= 5,
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
      date: d,
      day: d.getDate(),
      inMonth: d.getMonth() === month,
      events: visibleItems.value.filter((x) => {
        const s = parseDt(x.start_time)
        const e = parseDt(x.end_time)
        return s < dayEnd && e > dayStart
      }),
    }
  })
})

/** 有效排期：已取消不进表、不算冲突 */
const visibleItems = computed(() => items.value.filter((x) => x.status !== 'cancelled'))

function activeConflicts(row: Schedule): ScheduleConflict[] {
  return (row.conflicts || []).filter(
    (c) => c.status !== 'cancelled' && c.status !== 'completed',
  )
}

function rowHasConflict(row: Schedule) {
  if (row.status === 'cancelled' || row.status === 'completed') return false
  return activeConflicts(row).length > 0
}

function conflictHint(row: Schedule) {
  const cs = activeConflicts(row)
  if (!cs.length) return ''
  if (cs.length === 1) return `⚠ 与「${cs[0].title}」重叠`
  return `⚠ 与「${cs[0].title}」等 ${cs.length} 项重叠`
}

/** 顶部 KPI 按当前视图已加载数据统计，避免与周/月网格不一致 */
const scopeStats = computed(() => {
  const list = visibleItems.value
  return {
    total: list.length,
    pending: list.filter((x) => x.status === 'pending').length,
    conflict_count: list.filter((x) => rowHasConflict(x)).length,
  }
})

const attentionItems = computed(() => {
  const out: { kind: 'conflict' | 'pending'; item: Schedule }[] = []
  const seen = new Set<number>()
  for (const x of visibleItems.value) {
    if (rowHasConflict(x) && !seen.has(x.id)) {
      out.push({ kind: 'conflict', item: x })
      seen.add(x.id)
    }
  }
  for (const x of visibleItems.value) {
    if (x.status === 'pending' && !seen.has(x.id)) {
      out.push({ kind: 'pending', item: x })
      seen.add(x.id)
    }
    if (out.length >= 8) break
  }
  return out.slice(0, 8)
})

/** 侧栏负载：有角色筛选且接口有数据时用接口；否则按当前事项汇总 */
const sideLoads = computed((): ResourceLoad[] => {
  if (roleFilter.value !== 'all' && resourceLoads.value.length) {
    return resourceLoads.value
  }
  const capacity = 40
  const buckets = new Map<
    number,
    { employee_id: number; employee_name: string; planned_hours: number; item_count: number }
  >()
  for (const x of visibleItems.value) {
    const cur = buckets.get(x.employee_id) || {
      employee_id: x.employee_id,
      employee_name: x.employee_name || `#${x.employee_id}`,
      planned_hours: 0,
      item_count: 0,
    }
    const named = Number(x.planned_hours)
    const fromRange =
      (parseDt(x.end_time).getTime() - parseDt(x.start_time).getTime()) / 3600000
    const hours =
      Number.isFinite(named) && named > 0
        ? named
        : Number.isFinite(fromRange) && fromRange > 0
          ? fromRange
          : 0.5
    cur.planned_hours += hours
    cur.item_count += 1
    buckets.set(x.employee_id, cur)
  }
  return [...buckets.values()]
    .map((b) => {
      const hours = Math.round(b.planned_hours * 10) / 10
      return {
        employee_id: b.employee_id,
        employee_name: b.employee_name,
        resource_type: roleFilter.value === 'all' ? 'other' : roleFilter.value,
        planned_hours: hours,
        load_percent: Math.min(100, Math.round((hours * 100) / capacity)),
        item_count: b.item_count,
      }
    })
    .sort((a, b) => b.load_percent - a.load_percent)
})

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
  for (const ev of visibleItems.value) {
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

const weekHasVisibleEvents = computed(() => {
  for (const lays of weekLayouts.value.values()) {
    if (lays.length) return true
  }
  return false
})

function eventsAt(day: Date, hour: number) {
  return (weekLayouts.value.get(fmtDate(day)) || []).filter((x) => x.renderHour === hour)
}

function eventTooltip(lay: DayLayout) {
  const range = `${formatTime(lay.ev.start_time)} ~ ${formatTime(lay.ev.end_time)}`
  const who = lay.ev.employee_name || ''
  const status = SCHEDULE_STATUS_LABEL[lay.ev.status] || lay.ev.status
  const conflict = rowHasConflict(lay.ev) ? `\n${conflictHint(lay.ev)}` : ''
  return `${lay.ev.title}\n${status} · ${range}\n${who}${conflict}`.trim()
}

/** 每人一色：工号 × 黄金分割角，同一人跨周月不变，相邻工号色相也拉开 */
function personHue(employeeId: number) {
  return (Math.abs(employeeId) * 137.508) % 360
}

function personColor(employeeId?: number | null) {
  const id = Number(employeeId)
  if (!Number.isFinite(id) || id <= 0) return 'oklch(0.55 0.02 250)'
  const hue = personHue(id)
  const chroma = 0.14 + (id % 3) * 0.025
  const light = 0.5 + (id % 2) * 0.04
  return `oklch(${light.toFixed(2)} ${chroma.toFixed(2)} ${hue.toFixed(1)})`
}

function personColorSoft(employeeId?: number | null) {
  const id = Number(employeeId)
  if (!Number.isFinite(id) || id <= 0) return 'oklch(0.72 0.03 250 / 0.18)'
  const hue = personHue(id)
  const chroma = 0.12 + (id % 3) * 0.02
  return `oklch(0.86 ${chroma.toFixed(2)} ${hue.toFixed(1)} / 0.55)`
}

function personChipStyle(employeeId?: number | null) {
  const color = personColor(employeeId)
  return {
    '--person-color': color,
    borderLeftColor: color,
    background: personColorSoft(employeeId),
  }
}

const visiblePeople = computed(() => {
  const map = new Map<number, string>()
  for (const x of visibleItems.value) {
    if (!x.employee_id || map.has(x.employee_id)) continue
    map.set(x.employee_id, x.employee_name || `#${x.employee_id}`)
  }
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([id, name]) => ({ id, name }))
})

function eventStyle(lay: DayLayout, hour: number) {
  const top = lay.visStart.getHours() === hour ? (lay.visStart.getMinutes() / 60) * 48 : 0
  const remain = hourEnd - hour + 1
  const heightHours = Math.min(lay.visHours, remain)
  const widthPct = 100 / lay.cols
  const leftPct = lay.col * widthPct
  const color = personColor(lay.ev.employee_id)
  return {
    top: `${top}px`,
    height: `${Math.max(28, heightHours * 48 - 4)}px`,
    left: `calc(${leftPct}% + 2px)`,
    width: `calc(${widthPct}% - 4px)`,
    right: 'auto',
    zIndex: String(3 + lay.col),
    '--person-color': color,
    background: lay.ev.status === 'cancelled' ? '#94a3b8' : color,
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

function linkModeLabel(row: Schedule) {
  if (row.project_task_id || row.task_no) return '任务排期'
  if (row.project_id) return '项目排期'
  return '一般活动'
}

function resourceLabel(v: string) {
  return SCHEDULE_RESOURCE_OPTIONS.find((x) => x.value === v)?.label || v
}

function statusTagType(status?: string | null) {
  if (status === 'confirmed' || status === 'in_progress') return 'success'
  if (status === 'completed') return 'info'
  if (status === 'cancelled') return 'info'
  if (status === 'pending') return 'warning'
  return undefined
}

function rangeParams() {
  // 列表/负载按自然周周一～周日
  if (viewMode.value === 'month') {
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

async function fetchScheduleItems() {
  loading.value = true
  try {
    const range = rangeParams()
    const resourceType = roleFilter.value === 'all' ? undefined : roleFilter.value
    const { data } = await fetchSchedules({
      ...range,
      resource_type: resourceType,
      page: 1,
      page_size: 100,
    })
    items.value = data.items
    if (viewMode.value === 'week' && roleFilter.value !== 'all') {
      const { data: load } = await fetchResourceLoad({
        resource_type: roleFilter.value,
        date_from: range.date_from,
        date_to: range.date_to,
      })
      resourceLoads.value = load.items
    } else {
      resourceLoads.value = []
    }
  } finally {
    loading.value = false
  }
}

async function reload() {
  await fetchScheduleItems()
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

async function openConflict(c: ScheduleConflict) {
  const found = items.value.find((x) => x.id === c.id)
  if (found) {
    openDrawer(found)
    return
  }
  try {
    const { data } = await fetchScheduleDetail(c.id)
    openDrawer(data)
  } catch {
    ElMessage.warning('无法打开冲突排期')
  }
}

async function searchProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchDirectoryProjects({
      keyword: q || undefined,
      page: 1,
      page_size: 30,
    })
    projectOptions.value = data.items
  } finally {
    projectLoading.value = false
  }
}

async function onProjectChange(pid?: number) {
  form.project_task_id = undefined
  taskOptions.value = []
  if (!pid) return
  const { data } = await fetchDirectoryProjectTasks({ project_id: pid, page: 1, page_size: 100 })
  taskOptions.value = data.items
}

function onLinkModeChange(mode: LinkMode | string | number | boolean | undefined) {
  const next = (mode as LinkMode) || form.link_mode
  if (next === 'none') {
    form.project_id = undefined
    form.project_task_id = undefined
    taskOptions.value = []
  } else if (next === 'project') {
    form.project_task_id = undefined
  }
  formRef.value?.clearValidate(['project_id', 'project_task_id'])
}

function openCreateFromSlot(date: Date, hour: number) {
  void openCreate(undefined, { date, hour })
}

async function openCreate(presetProjectId?: number, slot?: { date: Date; hour: number }) {
  form.title = ''
  form.schedule_type = 'internal_training'
  form.link_mode = presetProjectId ? 'project' : 'none'
  form.resource_type = roleFilter.value === 'all' ? 'instructor' : roleFilter.value
  form.project_id = undefined
  form.project_task_id = undefined
  taskOptions.value = []
  form.location = ''
  form.content = ''
  if (slot) {
    const start = new Date(
      slot.date.getFullYear(),
      slot.date.getMonth(),
      slot.date.getDate(),
      slot.hour,
      0,
      0,
      0,
    )
    const end = new Date(start)
    end.setHours(slot.hour + 1)
    form.range = [formatLocalDateTime(start), formatLocalDateTime(end)]
  } else {
    const start = new Date()
    start.setMinutes(0, 0, 0)
    start.setHours(10)
    const end = new Date(start)
    end.setHours(12)
    form.range = [formatLocalDateTime(start), formatLocalDateTime(end)]
  }
  await loadPersonTree()
  form.employee_id = firstPersonId(personTree.value)
  createVisible.value = true
  if (presetProjectId) {
    form.link_mode = 'project'
    await searchProjects('')
    const hit = projectOptions.value.find((p) => p.id === presetProjectId)
    if (!hit) {
      const { data } = await fetchDirectoryProjects({ page: 1, page_size: 100 })
      projectOptions.value = data.items
    }
    if (projectOptions.value.some((p) => p.id === presetProjectId)) {
      form.project_id = presetProjectId
      await onProjectChange(presetProjectId)
    }
  }
}

async function applyCreateQuery() {
  if (String(route.query.create || '') !== '1') return
  const pid = Number(route.query.project_id)
  await openCreate(Number.isFinite(pid) && pid > 0 ? pid : undefined)
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.employee_id || form.range.length !== 2) {
    ElMessage.warning('请完整填写必填项与时间')
    return
  }
  let projectId = form.project_id
  let projectTaskId = form.project_task_id
  if (form.link_mode === 'none') {
    projectId = undefined
    projectTaskId = undefined
  } else if (form.link_mode === 'project') {
    projectTaskId = undefined
  }
  saving.value = true
  try {
    const { data } = await createSchedule({
      title: form.title.trim(),
      schedule_type: form.schedule_type,
      resource_type: form.resource_type,
      employee_id: form.employee_id,
      project_id: projectId,
      project_task_id: projectTaskId,
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
      roleFilter.value !== 'all' &&
      data.resource_type &&
      data.resource_type !== roleFilter.value
    ) {
      roleFilter.value = data.resource_type as RoleFilter
      ElMessage.info(`已切换到「${resourceLabel(data.resource_type)}」筛选以便查看刚创建的排期`)
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

watch([viewMode, roleFilter, anchor], () => {
  reload()
})

function firstPersonId(nodes: PersonTreeNode[]): number | undefined {
  for (const n of nodes) {
    if (n.is_person && typeof n.value === 'number') return n.value
    if (n.children?.length) {
      const hit = firstPersonId(n.children)
      if (hit != null) return hit
    }
  }
  return undefined
}

async function loadPersonTree() {
  personTreeLoading.value = true
  try {
    const { data } = await fetchPersonTree()
    personTree.value = data || []
  } catch {
    personTree.value = []
  } finally {
    personTreeLoading.value = false
  }
}

onMounted(async () => {
  await loadPersonTree()
  await searchProjects('')
  await reload()
  await applyCreateQuery()
})
</script>

<style scoped>
.field-tip {
  margin-top: 4px;
  color: var(--crm-ink-soft);
  font-size: 12px;
  line-height: 1.4;
}
@media (max-width: 768px) {
  .schedule-type-group {
    display: flex;
    flex-wrap: wrap;
    width: 100%;
  }
  .schedule-type-group :deep(.el-radio-button) {
    flex: 1 1 auto;
  }
  .schedule-type-group :deep(.el-radio-button__inner) {
    width: 100%;
  }
}
</style>

<!-- 树下拉挂到 body，需非 scoped -->
<style>
.schedule-person-popper.el-select__popper,
.schedule-person-popper.el-tree-select__popper,
.schedule-person-popper {
  max-width: min(92vw, 420px);
}
.schedule-person-popper .el-select-dropdown__wrap,
.schedule-person-popper .el-tree-select__popper .el-scrollbar__wrap,
.schedule-person-popper .el-scrollbar__wrap {
  max-height: min(320px, 50vh) !important;
  overflow-y: auto !important;
}
.schedule-person-popper .el-tree-node__content {
  height: auto;
  min-height: 32px;
  padding-top: 4px;
  padding-bottom: 4px;
  white-space: normal;
  line-height: 1.35;
}
.schedule-person-popper .el-tree-node.is-disabled > .el-tree-node__content {
  cursor: default;
  color: var(--crm-ink-soft, #64748b);
  font-weight: 600;
}
</style>

