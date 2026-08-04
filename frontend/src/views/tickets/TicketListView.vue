<template>
  <div class="crm-page ticket-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-actions">
        <el-button @click="slaVisible = true">工单时限规则</el-button>
        <el-button type="primary" @click="openCreate">＋ 发起工单</el-button>
      </div>
    </header>

    <section class="ticket-kpis">
      <div>
        <small>接近时限</small>
        <b>{{ stats?.near_sla ?? 0 }}</b>
      </div>
      <div>
        <small>已逾期</small>
        <b class="danger">{{ stats?.overdue ?? 0 }}</b>
      </div>
      <div>
        <small>待发起人确认</small>
        <b>{{ stats?.pending_confirm ?? 0 }}</b>
      </div>
      <div>
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
          style="width: 160px"
          @change="reload"
        >
          <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
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
      </div>
      <span class="ticket-chip">分类时限 · 50%与80%提醒 · 超时逐级升级</span>
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
              <span>处理人 <b>{{ row.assignee_name || '待分派' }}</b></span>
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
          <div v-if="!col.items.length" class="ticket-empty">暂无工单</div>
        </div>
      </article>
    </section>

    <el-dialog v-model="createVisible" title="发起协作" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="关联项目">
          <el-select
            v-model="form.project_id"
            clearable
            filterable
            remote
            :remote-method="searchProjects"
            :loading="projectLoading"
            placeholder="可选，不关联项目"
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
        <el-form-item label="关联项目任务">
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
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="form.title" maxlength="200" placeholder="简述跨部门请求" />
        </el-form-item>
        <el-form-item label="承接部门" prop="department_id">
          <el-select v-model="form.department_id" filterable placeholder="请选择" style="width: 100%">
            <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
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
          <div style="margin-top: 4px; font-size: 12px; color: var(--crm-ink-soft)">
            分类决定响应、完成和升级规则。
          </div>
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
        <el-form-item label="指定处理人">
          <el-select
            v-model="form.assignee_id"
            clearable
            filterable
            placeholder="可选，稍后分派"
            style="width: 100%"
          >
            <el-option v-for="u in assignees" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求说明" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="4" placeholder="说明背景、期望结果与截止要求" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">提交工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="slaVisible" title="工单时限规则" width="560px" destroy-on-close>
      <p style="margin: 0 0 12px; color: var(--crm-ink-soft); font-size: 13px">
        系统根据工单分类计算响应和完成时限，并持续显示剩余时间。具体数值可由管理员配置。
      </p>
      <div class="sla-rules-list">
        <div class="row"><span>项目交付工单</span><b>48 小时内完成 · 按项目计划对齐</b></div>
        <div class="row"><span>普通跨部门协作</span><b>72 小时内完成</b></div>
        <div class="row"><span>紧急客户或生产问题</span><b>4 小时内完成</b></div>
        <div class="row"><span>反馈工单</span><b>24 小时内完成</b></div>
        <div class="row"><span>已使用时限达到 50%</span><b>提醒当前处理人</b></div>
        <div class="row"><span>已使用时限达到 80%</span><b>再次提醒处理人和负责人</b></div>
        <div class="row"><span>超过处理时限</span><b>逐级通知承接部门及业务负责人</b></div>
        <div class="row"><span>等待发起人验收期间</span><b>暂停处理计时</b></div>
        <div class="row"><span>关闭后重开窗口</span><b>3 个工作日</b></div>
        <div class="row"><span>满意度评价</span><b>关闭时 1–5 分</b></div>
      </div>
      <template #footer>
        <el-button type="primary" @click="slaVisible = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
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
import { fetchProjects, fetchProjectTasks, TASK_STATUS_LABEL, type Project, type ProjectTask } from '@/api/projects'
import { fetchDepartments, type Department } from '@/api/org'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const projectLoading = ref(false)
const taskLoading = ref(false)
const createVisible = ref(false)
const slaVisible = ref(false)
const items = ref<Ticket[]>([])
const stats = ref<TicketStats | null>(null)
const projectOptions = ref<Project[]>([])
const taskOptions = ref<ProjectTask[]>([])
const departments = ref<Department[]>([])
const assignees = ref<AssigneeOption[]>([])

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
  assignee_id: undefined as number | undefined,
  department_id: undefined as number | undefined,
  project_id: undefined as number | undefined,
  task_id: undefined as number | undefined,
  remark: '',
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  department_id: [{ required: true, message: '请选择承接部门', trigger: 'change' }],
  ticket_type: [{ required: true, message: '请选择分类', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  content: [{ required: true, message: '请填写请求说明', trigger: 'blur' }],
}

const boardColumns = computed(() => {
  const cols = [
    {
      key: 'receive',
      label: '待接收',
      color: '#8c8c8c',
      match: (s: string) => s === 'pending_assign' || s === 'pending_accept',
    },
    {
      key: 'processing',
      label: '处理中',
      color: '#1677ff',
      match: (s: string) => s === 'processing',
    },
    {
      key: 'confirm',
      label: '待确认',
      color: '#faad14',
      match: (s: string) => s === 'pending_confirm',
    },
    {
      key: 'closed',
      label: '已关闭',
      color: '#52c41a',
      match: (s: string) => s === 'completed' || s === 'closed',
    },
  ]
  return cols.map((col) => ({
    ...col,
    items: items.value.filter((t) => col.match(t.status)),
  }))
})

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

function goDetail(row: Ticket) {
  router.push(`/tickets/${row.id}`)
}

async function searchProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchProjects({ keyword: q || undefined, page: 1, page_size: 50 })
    projectOptions.value = data.items.filter(
      (p) => !['completed', 'terminated'].includes(p.status),
    )
  } finally {
    projectLoading.value = false
  }
}

const taskTotalForProject = ref(0)
const taskDoneForProject = ref(0)

function taskOptionLabel(t: ProjectTask) {
  const st = TASK_STATUS_LABEL[t.status] || t.status
  return `${t.task_no} · ${t.title}（${st}）`
}

const taskSelectPlaceholder = computed(() => {
  if (!form.project_id) return '可选，先选项目'
  if (taskLoading.value) return '加载任务中…'
  if (taskTotalForProject.value === 0) return '该项目还没有任务'
  if (taskOptions.value.length === 0) return '暂无未完成任务可选'
  return '可选，关联到具体任务'
})

const taskFieldTip = computed(() => {
  if (!form.project_id) return '关联任务为可选项；不选也能提交工单。'
  if (taskTotalForProject.value === 0) {
    return '该项目尚未创建任务。可先不关联任务直接提交，或到「项目交付 → 执行 → 任务工时」新建任务后再选。'
  }
  if (taskOptions.value.length === 0 && taskDoneForProject.value > 0) {
    return `该项目任务均已完成（${taskDoneForProject.value} 条），不可再关联；可不选任务直接提交工单。`
  }
  return '仅列出未完成任务；任务标题叫「完成任务」不代表状态已完成。'
})

async function loadTasksForProject(pid?: number) {
  taskOptions.value = []
  taskTotalForProject.value = 0
  taskDoneForProject.value = 0
  if (!pid) return
  taskLoading.value = true
  try {
    const { data } = await fetchProjectTasks({ project_id: pid, page: 1, page_size: 100 })
    const items = data.items || []
    taskTotalForProject.value = items.length
    taskDoneForProject.value = items.filter((t) => t.status === 'done').length
    taskOptions.value = items.filter((t) => t.status !== 'done')
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

function openCreate() {
  form.title = ''
  form.ticket_type = 'collaboration'
  form.priority = 'normal'
  form.content = ''
  form.assignee_id = undefined
  form.department_id = departments.value[0]?.id
  form.project_id = projectId.value
  form.task_id = undefined
  form.remark = ''
  taskOptions.value = []
  if (form.project_id) loadTasksForProject(form.project_id)
  createVisible.value = true
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
      assignee_id: form.assignee_id,
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

onMounted(async () => {
  const [{ data: depts }, { data: users }] = await Promise.all([
    fetchDepartments(),
    fetchAssigneeOptions(),
    searchProjects(''),
  ])
  departments.value = depts
  assignees.value = users
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
</style>
