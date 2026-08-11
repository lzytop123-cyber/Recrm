<template>
  <div class="crm-page ticket-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="wb-eyebrow">经营台</p>
        <h1>协作工单</h1>
        <p>
          跨部门请求：发起 → 分派/接单 → 处理 → 发起人确认关闭。
          可挂到交付项目，但不等于计划节点或人员档期。
        </p>
      </div>
      <div class="sales-head-actions">
        <el-button @click="slaVisible = true">时限规则</el-button>
        <el-button type="primary" @click="openCreate()">＋ 发起工单</el-button>
      </div>
    </header>

    <section class="ticket-kpis">
      <button
        type="button"
        class="ticket-kpi"
        :class="{ active: focusFilter === 'near_sla' }"
        @click="toggleFocus('near_sla')"
      >
        <small>接近时限</small>
        <b>{{ stats?.near_sla ?? 0 }}</b>
      </button>
      <button
        type="button"
        class="ticket-kpi"
        :class="{ active: focusFilter === 'overdue' }"
        @click="toggleFocus('overdue')"
      >
        <small>已逾期</small>
        <b class="danger">{{ stats?.overdue ?? 0 }}</b>
      </button>
      <button
        type="button"
        class="ticket-kpi"
        :class="{ active: focusFilter === 'pending_confirm' }"
        @click="toggleFocus('pending_confirm')"
      >
        <small>待发起人确认</small>
        <b>{{ stats?.pending_confirm ?? 0 }}</b>
      </button>
      <div class="ticket-kpi ticket-kpi--static">
        <small>本月满意度</small>
        <b>{{ stats?.satisfaction_avg != null ? `${stats.satisfaction_avg} / 5` : '暂无' }}</b>
      </div>
    </section>

    <div class="ticket-toolbar">
      <div class="filters">
        <el-select
          v-model="projectId"
          clearable
          filterable
          remote
          :remote-method="searchProjects"
          :loading="projectLoading"
          placeholder="全部项目"
          style="width: 220px"
          @change="reload"
        >
          <el-option
            v-for="p in projectOptions"
            :key="p.id"
            :label="`${p.project_no} · ${p.name}`"
            :value="p.id"
          />
        </el-select>
        <el-select
          v-model="departmentId"
          clearable
          filterable
          placeholder="全部部门"
          style="width: 180px"
          @change="reload"
        >
          <el-option
            v-for="d in departmentFlatOptions"
            :key="d.id"
            :label="d.label"
            :value="d.id"
          />
        </el-select>
        <el-select
          v-model="priority"
          clearable
          placeholder="全部优先级"
          style="width: 140px"
          @change="reload"
        >
          <el-option
            v-for="opt in TICKET_PRIORITY_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-input
          v-model="keyword"
          clearable
          placeholder="编号 / 标题"
          style="width: 160px"
          @keyup.enter="reload"
        />
        <el-button type="primary" @click="reload">查询</el-button>
        <el-button v-if="focusFilter" @click="clearFocus">清除快捷筛选</el-button>
      </div>
      <span class="ticket-chip">{{ focusHint }}</span>
    </div>

    <section class="ticket-board">
      <article v-for="col in boardColumns" :key="col.key" class="ticket-column">
        <div class="ticket-column-head">
          <b>
            <i :style="{ background: col.color }"></i>
            {{ col.label }}
          </b>
          <span>{{ col.items.length }} 张</span>
        </div>
        <div class="ticket-cards">
          <button
            v-for="row in col.items"
            :key="row.id"
            type="button"
            class="ticket-card"
            @click="goDetail(row)"
          >
            <div class="ticket-card-top">
              <small>{{ row.ticket_no }}</small>
              <span class="priority-pill" :class="row.priority">{{ priorityLabel(row.priority) }}</span>
            </div>
            <h3>{{ row.title }}</h3>
            <div class="ticket-card-meta">
              <span>承接 <b>{{ row.department_name || '—' }}</b></span>
              <span>处理人 <b>{{ assigneeDisplay(row) }}</b></span>
            </div>
            <div class="ticket-card-meta" style="margin-top: 4px">
              <span>{{ typeLabel(row.ticket_type) }}</span>
              <span v-if="row.project_name">· {{ row.project_name }}</span>
              <span v-if="row.task_no">· {{ row.task_no }}</span>
            </div>
            <div class="ticket-card-foot">
              <span>发起 {{ row.creator_name || '—' }}</span>
              <span class="ticket-sla" :class="slaClass(row)">
                <template v-if="(row.escalated_level || 0) > 0">已升级 L{{ row.escalated_level }} · </template>
                {{ slaText(row) }}
              </span>
            </div>
            <div v-if="row.next_actor_hint" class="ticket-card-hint">{{ row.next_actor_hint }}</div>
          </button>
          <div v-if="!col.items.length" class="ticket-empty">{{ col.empty }}</div>
        </div>
      </article>
    </section>

    <el-dialog
      v-model="createVisible"
      title="发起协作工单"
      width="640px"
      destroy-on-close
      class="claim-dialog"
      :fullscreen="isCompact"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :label-width="isCompact ? 'auto' : '110px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <section class="form-block">
          <h3><span>1</span>请求内容</h3>
          <el-form-item label="工单标题" prop="title">
            <el-input v-model="form.title" maxlength="200" placeholder="简述跨部门请求" />
          </el-form-item>
          <el-form-item label="承接部门" prop="department_id">
            <el-tree-select
              v-model="form.department_id"
              :data="departmentTreeForSelect"
              :props="{ label: 'name', value: 'id', children: 'children', disabled: 'disabled' }"
              filterable
              check-strictly
              :render-after-expand="false"
              default-expand-all
              placeholder="选择实际承接的业务部门"
              style="width: 100%"
              @change="onDepartmentChange"
            />
            <div class="field-tip">跨部门请求请选对方业务部门；不可选「总公司」根节点。</div>
          </el-form-item>
          <el-form-item label="工单分类" prop="ticket_type">
            <el-select v-model="form.ticket_type" style="width: 100%">
              <el-option
                v-for="opt in TICKET_TYPE_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <div class="field-tip">分类决定完成时限与升级规则（详见「时限规则」）。</div>
          </el-form-item>
          <el-form-item label="优先级" prop="priority">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option
                v-for="opt in TICKET_PRIORITY_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="请求说明" prop="content">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="4"
              placeholder="说明背景、期望结果与截止要求"
            />
          </el-form-item>
        </section>
        <section class="form-block">
          <h3><span>2</span>分派与挂接（可选）</h3>
          <el-form-item label="指定处理人">
            <el-select
              v-model="form.assignee_ids"
              multiple
              clearable
              filterable
              collapse-tags
              collapse-tags-tooltip
              :disabled="!form.department_id"
              :loading="assigneeLoading"
              :placeholder="assigneePlaceholder"
              style="width: 100%"
            >
              <el-option v-for="u in assignees" :key="u.id" :label="u.name" :value="u.id" />
            </el-select>
            <div class="field-tip">{{ assigneeFieldTip }}</div>
          </el-form-item>
          <el-form-item label="挂到项目">
            <el-select
              v-model="form.project_id"
              clearable
              filterable
              remote
              :remote-method="searchLinkableProjects"
              :loading="projectLoading"
              placeholder="输入编号/名称搜索；已结项/已终止项目不可挂"
              style="width: 100%"
              @visible-change="(open: boolean) => open && searchLinkableProjects('')"
              @change="onProjectChange"
            >
              <el-option
                v-for="p in linkableProjectOptions"
                :key="p.id"
                :label="projectOptionLabel(p)"
                :value="p.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="挂到任务">
            <el-select
              v-model="form.task_id"
              clearable
              filterable
              :disabled="!form.project_id"
              :loading="taskLoading"
              :placeholder="taskSelectPlaceholder"
              style="width: 100%"
            >
              <el-option
                v-for="t in taskOptions"
                :key="t.id"
                :label="taskOptionLabel(t)"
                :value="t.id"
              />
            </el-select>
            <div class="field-tip">{{ taskFieldTip }}</div>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" />
          </el-form-item>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">提交工单</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="slaVisible"
      title="工单时限规则"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <p style="margin: 0 0 12px; color: var(--crm-ink-soft); font-size: 13px">
        按工单分类计算完成时限；等待发起人确认期间暂停计时。
      </p>
      <div class="sla-rules-list">
        <div class="row"><span>交付协作工单</span><b>48 小时内完成</b></div>
        <div class="row"><span>普通跨部门协作</span><b>72 小时内完成</b></div>
        <div class="row"><span>紧急客户或生产问题</span><b>4 小时内完成</b></div>
        <div class="row"><span>反馈工单</span><b>24 小时内完成</b></div>
        <div class="row"><span>已使用时限 50% / 80%</span><b>提醒处理人（及负责人）</b></div>
        <div class="row"><span>超过处理时限</span><b>逐级升级通知</b></div>
        <div class="row"><span>等待发起人确认</span><b>暂停处理计时</b></div>
        <div class="row"><span>关闭后重开</span><b>3 个工作日内</b></div>
      </div>
      <template #footer>
        <el-button type="primary" @click="slaVisible = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  TICKET_PRIORITY_OPTIONS,
  TICKET_TYPE_OPTIONS,
  createTicket,
  fetchAssigneeOptions,
  fetchTicketStats,
  fetchTickets,
  type AssigneeOption,
  type Ticket,
  type TicketStats,
} from '@/api/tickets'
import { TASK_STATUS_LABEL } from '@/api/projects'
import {
  fetchDirectoryDepartments,
  fetchDirectoryProjects,
  fetchDirectoryProjectTasks,
  type DirectoryDepartment,
  type DirectoryProject,
  type DirectoryProjectTask,
} from '@/api/directory'

type FocusFilter = 'near_sla' | 'overdue' | 'pending_confirm'

const router = useRouter()
const route = useRoute()
const isCompact = useMatchMedia('(max-width: 768px)')
const loading = ref(false)
const saving = ref(false)
const projectLoading = ref(false)
const taskLoading = ref(false)
const createVisible = ref(false)
const slaVisible = ref(false)
const items = ref<Ticket[]>([])
const stats = ref<TicketStats | null>(null)
const projectOptions = ref<DirectoryProject[]>([])
const linkableProjectOptions = ref<DirectoryProject[]>([])
const taskOptions = ref<DirectoryProjectTask[]>([])
const departments = ref<DirectoryDepartment[]>([])
const assignees = ref<AssigneeOption[]>([])
const assigneeLoading = ref(false)
const focusFilter = ref<FocusFilter | null>(null)

type DeptSelectNode = DirectoryDepartment & { disabled?: boolean }

function isRootDepartment(d: Pick<DirectoryDepartment, 'code' | 'name' | 'parent_id'>) {
  return (d.code || '').toUpperCase() === 'ROOT'
}

function markDepartmentTree(nodes: DirectoryDepartment[]): DeptSelectNode[] {
  return (nodes || []).map((n) => ({
    ...n,
    disabled: isRootDepartment(n),
    children: n.children?.length ? markDepartmentTree(n.children) : [],
  }))
}

function flattenDepartments(
  nodes: DirectoryDepartment[],
  prefix = '',
): { id: number; label: string }[] {
  const out: { id: number; label: string }[] = []
  for (const n of nodes || []) {
    const root = isRootDepartment(n)
    const label = root ? n.name : prefix ? `${prefix} / ${n.name}` : n.name
    if (!root) out.push({ id: n.id, label })
    if (n.children?.length) {
      out.push(...flattenDepartments(n.children, root ? '' : label))
    }
  }
  return out
}

const departmentTreeForSelect = computed(() => markDepartmentTree(departments.value))
const departmentFlatOptions = computed(() => flattenDepartments(departments.value))

const projectId = ref<number | undefined>()
const departmentId = ref<number | undefined>()
const priority = ref<string | undefined>()
const keyword = ref('')

const formRef = ref<FormInstance>()
const form = reactive({
  title: '',
  ticket_type: 'collaboration',
  priority: 'normal',
  content: '',
  assignee_ids: [] as number[],
  department_id: undefined as number | undefined,
  project_id: undefined as number | undefined,
  task_id: undefined as number | undefined,
  remark: '',
})

const assigneePlaceholder = computed(() => {
  if (!form.department_id) return '请先选择承接部门'
  if (assigneeLoading.value) return '加载部门人员…'
  if (!assignees.value.length) return '该部门暂无在职人员'
  return '可多选；可不选，稍后由部门分派'
})

const assigneeFieldTip = computed(() => {
  if (!form.department_id) return '选定承接部门后，仅显示该部门人员。'
  if (!assignees.value.length) return '该部门下暂无可用人员，可先提交由部门负责人分派。'
  return '可多选为候选处理人；多人时谁先接单谁成为主责处理人。'
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  department_id: [{ required: true, message: '请选择承接部门', trigger: 'change' }],
  ticket_type: [{ required: true, message: '请选择分类', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  content: [{ required: true, message: '请填写请求说明', trigger: 'blur' }],
}

const filteredItems = computed(() => {
  const list = items.value
  if (focusFilter.value === 'near_sla') {
    return list.filter((t) => t.is_near_sla && !t.is_overdue)
  }
  if (focusFilter.value === 'overdue') {
    return list.filter((t) => t.is_overdue)
  }
  if (focusFilter.value === 'pending_confirm') {
    return list.filter((t) => t.status === 'pending_confirm')
  }
  return list
})

const focusHint = computed(() => {
  if (focusFilter.value === 'near_sla') return '快捷筛选：接近时限'
  if (focusFilter.value === 'overdue') return '快捷筛选：已逾期'
  if (focusFilter.value === 'pending_confirm') return '快捷筛选：待发起人确认'
  return '看板按处理阶段排列 · 点上方卡片可快捷筛选'
})

const boardColumns = computed(() => {
  const cols = [
    {
      key: 'receive',
      label: '待接收',
      color: '#8c8c8c',
      empty: '暂无待分派/待接单',
      match: (s: string) => s === 'pending_assign' || s === 'pending_accept',
    },
    {
      key: 'processing',
      label: '处理中',
      color: '#1677ff',
      empty: '暂无处理中工单',
      match: (s: string) => s === 'processing',
    },
    {
      key: 'confirm',
      label: '待确认',
      color: '#faad14',
      empty: '暂无待发起人确认',
      match: (s: string) => s === 'pending_confirm',
    },
    {
      key: 'closed',
      label: '已关闭',
      color: '#52c41a',
      empty: '暂无已关闭工单',
      match: (s: string) => s === 'completed' || s === 'closed',
    },
  ]
  return cols.map((col) => ({
    ...col,
    items: filteredItems.value.filter((t) => col.match(t.status)),
  }))
})

function toggleFocus(key: FocusFilter) {
  focusFilter.value = focusFilter.value === key ? null : key
}

function clearFocus() {
  focusFilter.value = null
}

function typeLabel(v: string) {
  return TICKET_TYPE_OPTIONS.find((x) => x.value === v)?.label || v
}

function priorityLabel(v: string) {
  return TICKET_PRIORITY_OPTIONS.find((x) => x.value === v)?.label || v
}

function formatDue(v?: string | null) {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 16)
}

function slaText(row: Ticket) {
  if (row.is_overdue) return '已逾期'
  if (row.is_near_sla) {
    const pct = Math.round((row.sla_used_ratio || 0) * 100)
    return `接近时限 ${pct}%`
  }
  return `截止 ${formatDue(row.due_at)}`
}

function slaClass(row: Ticket) {
  if (row.is_overdue) return 'overdue'
  if (row.is_near_sla) return 'near'
  return ''
}

function assigneeDisplay(row: Ticket) {
  if (row.assignee_name) return row.assignee_name
  const names = row.candidate_names || []
  if (names.length > 1) return `候选 ${names.length} 人`
  if (names.length === 1) return names[0]
  return '待分派'
}

function goDetail(row: Ticket) {
  router.push(`/tickets/${row.id}`)
}

async function searchProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchDirectoryProjects({
      keyword: q || undefined,
      page: 1,
      page_size: 50,
    })
    // 列表筛选：可看已结项项目上的历史工单；终止项目一般不再关注
    projectOptions.value = data.items.filter((p) => p.status !== 'terminated')
  } finally {
    projectLoading.value = false
  }
}

async function searchLinkableProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchDirectoryProjects({
      keyword: q || undefined,
      page: 1,
      page_size: 50,
    })
    // 与后端一致：已结项 / 已终止不可再挂协作工单
    linkableProjectOptions.value = data.items.filter(
      (p) => p.status !== 'terminated' && p.status !== 'completed',
    )
  } finally {
    projectLoading.value = false
  }
}

function projectOptionLabel(p: DirectoryProject) {
  const st =
    p.status === 'executing'
      ? '执行中'
      : p.status === 'accepted'
        ? '已验收'
        : p.status === 'accepting'
          ? '验收中'
          : p.status === 'planning'
            ? '计划中'
            : p.status === 'initiating'
              ? '立项'
              : p.status === 'completed'
                ? '已完成'
                : ''
  return st ? `${p.project_no} · ${p.name}（${st}）` : `${p.project_no} · ${p.name}`
}

const taskTotalForProject = ref(0)
const taskDoneForProject = ref(0)

function taskOptionLabel(t: DirectoryProjectTask) {
  const st = TASK_STATUS_LABEL[t.status] || t.status
  return `${t.task_no} · ${t.title}（${st}）`
}

const taskSelectPlaceholder = computed(() => {
  if (!form.project_id) return '可选，先选项目'
  if (taskLoading.value) return '加载任务中…'
  if (taskTotalForProject.value === 0) return '该项目还没有任务'
  if (taskOptions.value.length === 0) return '暂无未完成任务可选'
  return '可选，挂到具体任务'
})

const taskFieldTip = computed(() => {
  if (!form.project_id) return '挂到任务为可选项；不选也能提交工单。'
  if (taskTotalForProject.value === 0) {
    return '该项目尚未创建任务。可先不挂任务直接提交，或到「交付执行 → 任务工时」新建后再选。'
  }
  if (taskOptions.value.length === 0 && taskDoneForProject.value > 0) {
    return `该项目任务均已完成（${taskDoneForProject.value} 条），可不挂任务直接提交。`
  }
  return '仅列出未完成任务。'
})

async function loadTasksForProject(pid?: number) {
  taskOptions.value = []
  taskTotalForProject.value = 0
  taskDoneForProject.value = 0
  if (!pid) return
  taskLoading.value = true
  try {
    const { data } = await fetchDirectoryProjectTasks({ project_id: pid, page: 1, page_size: 100 })
    const list = data.items || []
    taskTotalForProject.value = list.length
    taskDoneForProject.value = list.filter((t) => t.status === 'done').length
    taskOptions.value = list.filter((t) => t.status !== 'done')
  } finally {
    taskLoading.value = false
  }
}

async function onProjectChange(pid?: number) {
  form.task_id = undefined
  await loadTasksForProject(pid)
}

async function loadStats() {
  const { data } = await fetchTicketStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchTickets({
      keyword: keyword.value || undefined,
      priority: priority.value,
      project_id: projectId.value,
      department_id: departmentId.value,
      page: 1,
      page_size: 100,
    })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

async function reload() {
  await Promise.all([loadStats(), loadList()])
}

async function loadAssigneesForDepartment(deptId?: number) {
  assignees.value = []
  if (!deptId) return
  assigneeLoading.value = true
  try {
    const { data } = await fetchAssigneeOptions({ department_id: deptId })
    assignees.value = data
  } finally {
    assigneeLoading.value = false
  }
}

async function onDepartmentChange(deptId?: number) {
  form.assignee_ids = []
  await loadAssigneesForDepartment(deptId)
}

async function openCreate(presetProjectId?: number) {
  form.title = ''
  form.ticket_type = 'collaboration'
  form.priority = 'normal'
  form.content = ''
  form.assignee_ids = []
  form.department_id = undefined
  form.project_id = undefined
  form.task_id = undefined
  form.remark = ''
  assignees.value = []
  taskOptions.value = []
  createVisible.value = true
  await searchLinkableProjects('')
  const wantId = presetProjectId || projectId.value
  if (wantId && linkableProjectOptions.value.some((p) => p.id === wantId)) {
    form.project_id = wantId
    await loadTasksForProject(wantId)
  } else if (wantId) {
    ElMessage.warning('该项目已结项或已终止，不可再挂协作工单')
  }
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const { data } = await createTicket({
      title: form.title.trim(),
      ticket_type: form.ticket_type,
      priority: form.priority,
      content: form.content.trim(),
      assignee_ids: form.assignee_ids.length ? form.assignee_ids : undefined,
      department_id: form.department_id,
      project_id: form.project_id,
      task_id: form.task_id,
      remark: form.remark || undefined,
    })
    ElMessage.success(`工单已创建：${data.ticket_no}`)
    createVisible.value = false
    await reload()
  } finally {
    saving.value = false
  }
}

async function applyRouteQuery() {
  const pid = Number(route.query.project_id)
  if (Number.isFinite(pid) && pid > 0) {
    projectId.value = pid
    if (!projectOptions.value.some((p) => p.id === pid)) {
      await searchProjects('')
    }
  }
  if (String(route.query.create || '') === '1') {
    await openCreate(Number.isFinite(pid) && pid > 0 ? pid : undefined)
  }
}

onMounted(async () => {
  const [{ data: depts }] = await Promise.all([fetchDirectoryDepartments(), searchProjects('')])
  departments.value = depts
  await applyRouteQuery()
  await reload()
})
</script>

<style scoped>
.field-tip {
  margin-top: 4px;
  color: var(--crm-ink-soft);
  font-size: 12px;
  line-height: 1.4;
}
.form-block {
  margin-bottom: 8px;
}
.form-block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 14px;
}
.form-block h3 span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
}
</style>
