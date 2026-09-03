<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/projects')">返回列表</el-button>
      <div class="actions" v-if="project">
        <el-button
          v-if="!['completed', 'terminated'].includes(project.status)"
          v-perm="'project:manage'"
          type="primary"
          @click="editVisible = true"
        >
          编辑
        </el-button>
        <el-button
          v-if="project.status === 'initiating'"
          v-perm="'project:manage'"
          type="warning"
          @click="onPlan"
        >
          进入计划
        </el-button>
        <el-button
          v-if="['initiating', 'planning'].includes(project.status)"
          v-perm="'project:manage'"
          type="success"
          @click="onExecute"
        >
          进入执行
        </el-button>
        <el-button
          v-if="project.status === 'executing'"
          v-perm="'project:manage'"
          type="warning"
          @click="onAccepting"
        >
          进入验收
        </el-button>
        <el-button
          v-if="project.status === 'accepting' && project.acceptance_approval_status !== 'pending'"
          v-perm.any="['project:accept_submit', 'project:manage']"
          type="success"
          @click="goAcceptanceWorkbench"
        >
          提交验收审批
        </el-button>
        <el-tag
          v-if="project.acceptance_approval_status === 'pending'"
          type="warning"
          style="margin-right: 8px"
        >
          验收审批中
        </el-tag>
        <el-button
          v-if="project.status === 'accepted' && canGoCloseout"
          v-perm.any="['project:finance_submit', 'project:complete', 'project:manage']"
          type="success"
          @click="goAcceptanceWorkbench"
        >
          去结项
        </el-button>
        <el-button
          v-if="!['completed', 'terminated'].includes(project.status)"
          v-perm="'project:manage'"
          type="danger"
          plain
          @click="terminateVisible = true"
        >
          终止
        </el-button>
      </div>
    </div>

    <template v-if="project">
      <el-card>
        <template #header>
          <div class="card-header">
            <div class="title-block">
              <span>{{ project.project_no }} · {{ project.name }}</span>
              <p v-if="['completed', 'terminated'].includes(project.status)" class="archive-hint">
                项目已结束，本页为档案归档；可查看客户、合同与验收记录。
              </p>
              <p v-else class="archive-hint">
                项目档案页；日常立项 / 计划 / 任务 / 验收请在
                <el-button
                  link
                  type="primary"
                  @click="
                    $router.push({
                      path: '/projects/delivery',
                      query: { project_id: String(project.id) },
                    })
                  "
                >
                  交付执行
                </el-button>
                处理
              </p>
            </div>
            <div class="header-meta">
              <el-tag :type="statusTag(project.status)" size="small">
                {{ PROJECT_STATUS_LABEL[project.status] || project.status }}
              </el-tag>
            </div>
          </div>
        </template>
        <SalesJourneyBar
          class="journey-in-card"
          :project-id="project.id"
          :sync-key="project.status"
          hide-self-project
        />
        <ProjectJourneyBar class="journey-in-card" :project="project" />
        <el-descriptions :column="descCols" border class="stack-gap-sm">
          <el-descriptions-item label="项目编号">{{ project.project_no }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeLabel(project.project_type) }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <el-button
              v-if="project.customer_id"
              link
              type="primary"
              @click="$router.push(`/customers/${project.customer_id}`)"
            >
              {{ project.customer_name || `#${project.customer_id}` }}
            </el-button>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="合同">
            <el-button
              v-if="project.contract_id"
              link
              type="primary"
              @click="$router.push(`/contracts/${project.contract_id}`)"
            >
              {{ project.contract_no || `#${project.contract_id}` }}
            </el-button>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ project.manager_name || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="project.business_owner_name && project.business_owner_name !== project.manager_name" label="业务负责人">{{ project.business_owner_name }}</el-descriptions-item>
          <el-descriptions-item label="计划开始">{{ project.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="计划结束">{{ project.end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际结束">{{ project.actual_end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="交付范围" :span="descCols">{{ project.scope_desc || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="project.terminate_reason" label="终止原因" :span="descCols">
            {{ project.terminate_reason }}
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="descCols">{{ project.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card
        v-if="project.acceptance_result || project.acceptance_approval_status !== 'none'"
        class="stack-gap"
      >
        <template #header>
          <div class="card-header">
            <span>内部验收申请</span>
            <el-tag
              v-if="project.acceptance_approval_status === 'pending'"
              type="warning"
              size="small"
            >
              审批中
            </el-tag>
            <el-tag
              v-else-if="project.acceptance_approval_status === 'approved'"
              type="success"
              size="small"
            >
              已通过
            </el-tag>
            <el-tag
              v-else-if="project.acceptance_approval_status === 'rejected'"
              type="danger"
              size="small"
            >
              已驳回
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="acceptDescCols" border>
          <el-descriptions-item label="验收结果">
            {{ ACCEPTANCE_RESULT_LABEL[project.acceptance_result || ''] || project.acceptance_result || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="验收日期">{{ project.accepted_at || '—' }}</el-descriptions-item>
          <el-descriptions-item label="验收方式">{{ project.acceptance_method || '—' }}</el-descriptions-item>
          <el-descriptions-item label="验收负责人">
            {{ project.acceptance_owner_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="提交人">
            {{ project.acceptance_submitted_by_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">
            {{ formatDateTime(project.acceptance_submitted_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="结论与遗留安排" :span="acceptDescCols">
            {{ project.acceptance_conclusion || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="遗留问题摘要" :span="acceptDescCols">
            {{ project.leftover_summary || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="验收附件" :span="acceptDescCols">
            <AttachmentPreview
              :filename="project.acceptance_attachment"
              :path="project.acceptance_attachment_path"
              size="md"
            />
          </el-descriptions-item>
          <el-descriptions-item
            v-if="project.acceptance_reject_reason"
            label="驳回原因"
            :span="acceptDescCols"
          >
            {{ project.acceptance_reject_reason }}
          </el-descriptions-item>
          <el-descriptions-item label="财务核对">
            <template v-if="project.finance_check_status === 'pending'">审批中</template>
            <template v-else-if="project.finance_check_passed">已通过</template>
            <template v-else-if="project.finance_check_status === 'rejected'">已驳回</template>
            <template v-else>未通过</template>
          </el-descriptions-item>
          <el-descriptions-item label="遗留关闭">
            {{ project.leftover_summary ? (project.leftover_closed ? '已关闭' : '未关闭') : '无遗留' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="(project.milestones || []).length" class="stack-gap">
        <template #header>
          <div class="card-header">
            <span>计划节点</span>
            <el-button
              v-if="!['completed', 'terminated'].includes(project.status)"
              size="small"
              type="primary"
              @click="openMilestone"
            >
              添加节点
            </el-button>
          </div>
        </template>
        <el-table :data="project.milestones || []" stripe>
          <el-table-column prop="sort_order" label="序号" width="70" />
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="deadline" label="截止日期" width="120" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-select
                :model-value="row.status"
                size="small"
                style="width: 100px"
                :disabled="['completed', 'terminated'].includes(project!.status)"
                @change="(v: string) => onMilestoneStatus(row, v)"
              >
                <el-option
                  v-for="(label, key) in MILESTONE_STATUS_LABEL"
                  :key="key"
                  :label="label"
                  :value="key"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
        </el-table>
      </el-card>

      <el-card v-else-if="!['completed', 'terminated'].includes(project.status)" class="stack-gap">
        <div class="empty-inline">
          <span>本项目按任务推进，未使用计划节点。</span>
          <el-button
            link
            type="primary"
            @click="$router.push({ path: '/projects/delivery', query: { tab: 'execute', mode: 'plan', project_id: String(project.id) } })"
          >
            去交付执行补节点
          </el-button>
        </div>
      </el-card>

      <el-card v-if="schedules.length || schedulesLoading" class="stack-gap">
        <template #header>
          <div class="card-header">
            <span>人员档期</span>
            <el-button size="small" @click="$router.push('/schedules')">打开排期会议</el-button>
          </div>
        </template>
        <el-table :data="schedules" v-loading="schedulesLoading" stripe empty-text="暂无挂到本项目的排期">
          <el-table-column prop="title" label="排期" min-width="160" show-overflow-tooltip />
          <el-table-column label="时间" width="200">
            <template #default="{ row }">{{ formatScheduleRange(row) }}</template>
          </el-table-column>
          <el-table-column prop="employee_name" label="人员" width="100" />
          <el-table-column label="任务" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.task_no ? `${row.task_no} · ${row.task_title || ''}` : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="scheduleTag(row)">
                {{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
              <el-tag v-if="row.has_conflict" type="danger" size="small" style="margin-left: 4px">冲突</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push(`/schedules/${row.id}`)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="stack-gap">
        <template #header>
          <div class="card-header">
            <span>关联协作工单</span>
            <div class="header-actions">
              <el-button size="small" @click="$router.push({ path: '/tickets', query: { project_id: String(project.id) } })">
                打开工单台
              </el-button>
              <el-button
                v-if="!['completed', 'terminated'].includes(project.status)"
                size="small"
                type="primary"
                @click="
                  $router.push({
                    path: '/tickets',
                    query: { create: '1', project_id: String(project.id) },
                  })
                "
              >
                发起协作
              </el-button>
            </div>
          </div>
        </template>
        <p class="archive-hint" style="margin: 0 0 10px">
          工单用于跨部门协作追溯；完成工单不会自动完成项目任务。
        </p>
        <el-table :data="tickets" v-loading="ticketsLoading" stripe empty-text="暂无挂到本项目的工单">
          <el-table-column prop="ticket_no" label="编号" width="140" />
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="ticketStatusTag(row)">
                {{ TICKET_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assignee_name" label="处理人" width="100">
            <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="关联任务" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.task_no ? `${row.task_no} · ${row.task_title || ''}` : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="SLA" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.is_overdue" type="danger" size="small">已逾期</el-tag>
              <el-tag v-else-if="row.is_near_sla" type="warning" size="small">接近时限</el-tag>
              <span v-else class="muted">正常</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push(`/tickets/${row.id}`)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <FlowActivityCard
        v-if="project?.id"
        :biz-type="[
          'project_no_contract',
          'project_initiation',
          'project_handover',
          'project_acceptance',
          'project_settlement',
          'project_terminate',
        ]"
        :biz-id="project.id"
        hide-when-empty
      />
    </template>

    <el-dialog
      v-model="editVisible"
      title="编辑项目"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :model="editForm"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="项目名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="项目类型">
          <el-select v-model="editForm.project_type" style="width: 100%">
            <el-option
              v-for="opt in businessTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="进度">
          <el-slider v-model="editForm.progress" :max="100" show-input />
        </el-form-item>
        <el-form-item label="计划开始">
          <el-date-picker v-model="editForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划结束">
          <el-date-picker v-model="editForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="交付范围">
          <el-input v-model="editForm.scope_desc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="milestoneVisible"
      title="添加里程碑"
      width="480px"
      :fullscreen="isCompact"
    >
      <el-form
        :model="milestoneForm"
        :label-width="isCompact ? 'auto' : '90px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="名称" required>
          <el-input v-model="milestoneForm.name" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="milestoneForm.deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="序号">
          <el-input-number v-model="milestoneForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="milestoneForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="milestoneVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAddMilestone">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="terminateVisible"
      title="终止项目"
      width="480px"
      :fullscreen="isCompact"
    >
      <el-input v-model="terminateReason" type="textarea" :rows="3" placeholder="请填写终止原因" />
      <template #footer>
        <el-button @click="terminateVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="onTerminate">确认终止</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import FlowActivityCard from '@/components/approval/FlowActivityCard.vue'
import {
  ACCEPTANCE_RESULT_LABEL,
  MILESTONE_STATUS_LABEL,
  PROJECT_STATUS_LABEL,
  useBusinessTypes,
  addMilestone,
  fetchProjectDetail,
  startProjectAccepting,
  startProjectExecuting,
  startProjectPlanning,
  terminateProject,
  updateMilestone,
  updateProject,
  type ProjectDetail,
  type ProjectMilestone,
} from '@/api/projects'
import { fetchSchedules, SCHEDULE_STATUS_LABEL, type Schedule } from '@/api/schedules'
import { fetchTickets, TICKET_STATUS_LABEL, type Ticket } from '@/api/tickets'
import ProjectJourneyBar from '@/components/projects/ProjectJourneyBar.vue'
import SalesJourneyBar from '@/components/sales/SalesJourneyBar.vue'
import AttachmentPreview from '@/components/common/AttachmentPreview.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()
const isCompact = useMatchMedia('(max-width: 768px)')
const descCols = computed(() => (isCompact.value ? 1 : 3))
const acceptDescCols = computed(() => (isCompact.value ? 1 : 2))
const canGoCloseout = computed(() =>
  userStore.hasAnyPermission('project:finance_submit', 'project:complete', 'project:manage'),
)
const loading = ref(false)
const saving = ref(false)
const project = ref<ProjectDetail | null>(null)
const schedules = ref<Schedule[]>([])
const schedulesLoading = ref(false)
const tickets = ref<Ticket[]>([])
const ticketsLoading = ref(false)
const editVisible = ref(false)
const milestoneVisible = ref(false)
const terminateVisible = ref(false)
const terminateReason = ref('')

const editForm = reactive({
  name: '',
  project_type: 'other',
  progress: 0,
  start_date: '' as string | undefined,
  end_date: '' as string | undefined,
  scope_desc: '',
  remark: '',
})

const milestoneForm = reactive({
  name: '',
  deadline: '',
  sort_order: 0,
  remark: '',
})

const projectId = computed(() => Number(route.params.id))

function typeLabel(code: string) {
  return businessTypeLabel(code)
}

function formatDateTime(v?: string | null) {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 16)
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    initiating: 'info',
    planning: '',
    executing: 'warning',
    accepting: 'warning',
    accepted: 'success',
    completed: 'success',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function scheduleTag(row: Schedule) {
  if (row.status === 'completed') return 'success'
  if (row.status === 'cancelled') return 'info'
  if (row.has_conflict || row.status === 'pending') return 'warning'
  return ''
}

function formatScheduleRange(row: Schedule) {
  const s = row.start_time ? new Date(row.start_time) : null
  const e = row.end_time ? new Date(row.end_time) : null
  if (!s || !e) return '—'
  const d = s.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  const st = s.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  const et = e.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${d} ${st}-${et}`
}

function fillEdit() {
  if (!project.value) return
  const p = project.value
  editForm.name = p.name
  editForm.project_type = p.project_type
  editForm.progress = p.progress || 0
  editForm.start_date = p.start_date || undefined
  editForm.end_date = p.end_date || undefined
  editForm.scope_desc = p.scope_desc || ''
  editForm.remark = p.remark || ''
}

async function loadSchedules() {
  if (!projectId.value) return
  schedulesLoading.value = true
  try {
    const { data } = await fetchSchedules({
      project_id: projectId.value,
      page: 1,
      page_size: 50,
    })
    schedules.value = data.items
  } finally {
    schedulesLoading.value = false
  }
}

function ticketStatusTag(row: Ticket) {
  if (row.is_overdue) return 'danger'
  if (row.status === 'closed' || row.status === 'completed') return 'success'
  if (row.status === 'processing' || row.status === 'pending_confirm') return 'warning'
  return 'info'
}

async function loadTickets() {
  if (!projectId.value) return
  ticketsLoading.value = true
  try {
    const { data } = await fetchTickets({
      project_id: projectId.value,
      page: 1,
      page_size: 50,
    })
    tickets.value = data.items
  } finally {
    ticketsLoading.value = false
  }
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchProjectDetail(projectId.value)
    project.value = data
    fillEdit()
    await Promise.all([loadSchedules(), loadTickets()])
  } finally {
    loading.value = false
  }
}

watch(editVisible, (v) => {
  if (v) fillEdit()
})

async function onSaveEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('项目名称不能为空')
    return
  }
  saving.value = true
  try {
    await updateProject(projectId.value, {
      name: editForm.name,
      project_type: editForm.project_type,
      progress: editForm.progress,
      start_date: editForm.start_date || undefined,
      end_date: editForm.end_date || undefined,
      scope_desc: editForm.scope_desc || undefined,
      remark: editForm.remark || undefined,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function runTransition(fn: () => Promise<unknown>, okMsg: string, confirmMsg: string) {
  try {
    await ElMessageBox.confirm(confirmMsg, '确认')
    await fn()
    ElMessage.success(okMsg)
    await loadDetail()
  } catch {
    /* cancel */
  }
}

function onPlan() {
  return runTransition(() => startProjectPlanning(projectId.value), '已进入计划中', '确认进入计划中？')
}
function onExecute() {
  return runTransition(() => startProjectExecuting(projectId.value), '已进入执行中', '确认进入执行中？')
}
function onAccepting() {
  return runTransition(async () => {
    const openCount = tickets.value.filter((t) =>
      ['pending_assign', 'pending_accept', 'processing', 'pending_confirm'].includes(String(t.status)),
    ).length
    if (openCount > 0) {
      ElMessage.warning(`还有 ${openCount} 张未关闭协作工单（不阻断进入验收）`)
    }
    return startProjectAccepting(projectId.value)
  }, '已进入验收中', '确认进入验收中？')
}
function goAcceptanceWorkbench() {
  router.push({
    path: '/projects/delivery',
    query: { tab: 'acceptance', project_id: String(projectId.value) },
  })
}

function openMilestone() {
  milestoneForm.name = ''
  milestoneForm.deadline = ''
  milestoneForm.sort_order = (project.value?.milestones?.length || 0) + 1
  milestoneForm.remark = ''
  milestoneVisible.value = true
}

async function onAddMilestone() {
  if (!milestoneForm.name.trim()) {
    ElMessage.warning('请填写里程碑名称')
    return
  }
  saving.value = true
  try {
    await addMilestone(projectId.value, {
      name: milestoneForm.name,
      deadline: milestoneForm.deadline || undefined,
      sort_order: milestoneForm.sort_order,
      remark: milestoneForm.remark || undefined,
    })
    ElMessage.success('已添加')
    milestoneVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onMilestoneStatus(row: ProjectMilestone, status: string) {
  await updateMilestone(projectId.value, row.id, { status })
  ElMessage.success('里程碑已更新')
  await loadDetail()
}

async function onTerminate() {
  if (!terminateReason.value.trim()) {
    ElMessage.warning('请填写终止原因')
    return
  }
  saving.value = true
  try {
    await terminateProject(projectId.value, terminateReason.value.trim())
    ElMessage.success('项目已终止')
    terminateVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.muted {
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
}
.title-block {
  min-width: 0;
}
.archive-hint {
  margin: 6px 0 0;
  font-size: 12px;
  font-weight: 400;
  color: var(--crm-ink-soft, #909399);
  line-height: 1.4;
}
.header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.journey-in-card {
  margin-bottom: 14px;
}
.stack-gap-sm {
  margin-top: 12px;
}
.empty-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--crm-ink-soft, #909399);
  font-size: 13px;
}
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .header-actions,
  .header-meta {
    width: 100%;
    flex-wrap: wrap;
  }
  .title-block span {
    word-break: break-word;
    line-height: 1.35;
  }
}
</style>

