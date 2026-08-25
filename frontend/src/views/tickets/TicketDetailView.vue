<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/tickets')">返回工单看板</el-button>
      <div class="actions" v-if="item">
        <el-button v-if="item.can_assign" type="primary" @click="openAssign">分派</el-button>
        <el-button v-if="item.can_accept" type="success" @click="onAccept">接单处理</el-button>
        <el-button v-if="item.can_transfer" @click="openTransfer">转派</el-button>
        <el-button v-if="item.can_complete" type="warning" @click="openComplete">提交处理结果</el-button>
        <el-button v-if="item.can_return" type="danger" plain @click="openReturn">退回处理</el-button>
        <el-button v-if="item.can_confirm && item.status === 'pending_confirm'" type="primary" @click="openConfirmClose">
          验收并关闭
        </el-button>
        <el-button v-if="item.can_confirm && item.status === 'completed'" type="primary" @click="openConfirmClose">
          评价并关闭
        </el-button>
        <el-button v-if="item.can_reopen" @click="openReopen">3个工作日内重开</el-button>
      </div>
    </div>

    <el-alert
      v-if="item?.next_actor_hint"
      type="info"
      :closable="false"
      show-icon
      :title="`下一步：${item.next_actor_hint}`"
      style="margin-bottom: 12px"
    />

    <el-card v-if="item">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span>{{ item.ticket_no }} · {{ item.title }}</span>
            <p class="flow-hint">流程：分派 → 接单 → 处理 → 发起人确认关闭</p>
          </div>
          <div class="header-tags">
            <el-tag :type="statusTag(item.status)" size="small">
              {{ TICKET_STATUS_LABEL[item.status] || item.status }}
            </el-tag>
            <el-tag v-if="item.is_overdue" type="danger" size="small">超时</el-tag>
            <el-tag v-else-if="item.is_near_sla" type="warning" size="small">接近时限</el-tag>
            <el-tag v-if="(item.escalated_level || 0) > 0" type="danger" effect="plain" size="small">
              已升级 L{{ item.escalated_level }}
            </el-tag>
          </div>
        </div>
      </template>
      <el-descriptions :column="descCols" border>
        <el-descriptions-item label="类型">{{ typeLabel(item.ticket_type) }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ priorityLabel(item.priority) }}</el-descriptions-item>
        <el-descriptions-item label="截止时间">{{ formatTime(item.due_at) }}</el-descriptions-item>
        <el-descriptions-item label="发起人">{{ item.creator_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ item.assignee_name || '-' }}</el-descriptions-item>
        <el-descriptions-item
          v-if="(item.candidate_names || []).length > 1 || ((item.candidate_names || []).length === 1 && !item.assignee_id)"
          label="候选处理人"
        >
          {{ (item.candidate_names || []).join('、') }}
        </el-descriptions-item>
        <el-descriptions-item label="承接部门">{{ item.department_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="挂到项目">
          <el-button
            v-if="item.project_id"
            link
            type="primary"
            @click="$router.push(`/projects/${item.project_id}`)"
          >
            {{ item.project_name || `#${item.project_id}` }}
          </el-button>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="挂到任务">
          <template v-if="item.task_id">
            <span>{{ item.task_no }} · {{ item.task_title }}</span>
            <div class="field-hint">完成工单不会自动完成该任务，需在交付执行中单独标记任务完成。</div>
          </template>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="SLA">
          <el-tag v-if="item.is_overdue" type="danger" size="small">已逾期</el-tag>
          <el-tag v-else-if="item.status === 'pending_confirm'" type="info" size="small">验收中暂停计时</el-tag>
          <el-tag v-else-if="item.is_near_sla" type="warning" size="small">
            接近时限 {{ Math.round((item.sla_used_ratio || 0) * 100) }}%
          </el-tag>
          <span v-else>正常</span>
        </el-descriptions-item>
        <el-descriptions-item label="受理时间">{{ formatTime(item.accepted_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatTime(item.completed_at) }}</el-descriptions-item>
        <el-descriptions-item label="关闭时间">{{ formatTime(item.closed_at) }}</el-descriptions-item>
        <el-descriptions-item label="满意度">
          <span v-if="item.satisfaction">{{ item.satisfaction }} / 5</span>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="评价备注" :span="descCols > 1 ? 2 : 1">
          {{ item.satisfaction_comment || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="descCols">{{ item.content }}</el-descriptions-item>
        <el-descriptions-item v-if="item.result" label="处理结果" :span="descCols">{{ item.result }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="descCols">{{ item.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="item" class="schedule-card">
      <template #header>
        <div class="card-header">
          <span>关联排期</span>
          <el-button
            v-if="canManageSchedule"
            size="small"
            type="primary"
            @click="openScheduleCreate"
          >
            添加排期
          </el-button>
        </div>
      </template>
      <el-table
        v-if="ticketSchedules.length"
        :data="ticketSchedules"
        stripe
        v-loading="scheduleLoading"
      >
        <el-table-column label="排期" min-width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/schedules?id=${row.id}`)">
              #{{ row.id }} · {{ row.title }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="被排期人" prop="employee_name" width="120" />
        <el-table-column label="开始" width="150">
          <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
        </el-table-column>
        <el-table-column label="结束" width="150">
          <template #default="{ row }">{{ formatTime(row.end_time) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无关联排期" :image-size="60" />
    </el-card>

    <el-card v-if="item" class="records-card">
      <template #header>处理记录</template>
      <div class="comment-box" v-if="item.status !== 'closed'">
        <el-input v-model="comment" type="textarea" :rows="2" placeholder="添加评论..." />
        <el-button type="primary" :loading="commenting" :disabled="!comment.trim()" @click="onComment">
          发送
        </el-button>
      </div>
      <el-timeline v-if="item.records?.length">
        <el-timeline-item
          v-for="r in [...(item.records || [])].reverse()"
          :key="r.id"
          :timestamp="formatTime(r.created_at)"
          placement="top"
        >
          <div class="record-item">
            <strong>{{ r.user_name || `用户#${r.user_id}` }}</strong>
            <el-tag size="small" type="info" style="margin-left: 6px">
              {{ TICKET_ACTION_LABEL[r.action] || r.action }}
            </el-tag>
            <div v-if="r.content" class="record-content">{{ r.content }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无记录" :image-size="60" />
    </el-card>

    <el-dialog
      v-model="assignVisible"
      title="分派工单"
      width="420px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :label-width="isCompact ? 'auto' : '80px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="处理人">
          <el-select v-model="assigneeId" filterable style="width: 100%">
            <el-option v-for="u in assignees" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="assignRemark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAssign">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="transferVisible"
      title="转派工单"
      width="420px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :label-width="isCompact ? 'auto' : '80px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="新处理人">
          <el-select v-model="assigneeId" filterable style="width: 100%">
            <el-option v-for="u in assignees" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="transferReason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onTransfer">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="confirmVisible"
      title="工单验收"
      width="520px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <p class="hint">确认结果并关闭。关闭后 3 个工作日内可重开；满意度计入本月协作统计。</p>
      <el-form
        :label-width="isCompact ? 'auto' : '90px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="满意度" required>
          <el-radio-group v-model="satisfaction" class="satisfaction-group">
            <el-radio-button :value="5">5 · 完全满足</el-radio-button>
            <el-radio-button :value="4">4 · 基本满足</el-radio-button>
            <el-radio-button :value="3">3 · 一般</el-radio-button>
            <el-radio-button :value="2">2 · 较差</el-radio-button>
            <el-radio-button :value="1">1 · 不满足</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="验收备注">
          <el-input v-model="satisfactionComment" type="textarea" :rows="3" placeholder="选填，记录差异或后续建议" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onConfirmClose">验收并关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="scheduleVisible"
      title="为工单添加排期"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :label-width="isCompact ? 'auto' : '90px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="排期标题" required>
          <el-input v-model="scheduleForm.title" placeholder="默认取工单标题" />
        </el-form-item>
        <el-form-item label="被排期人" required>
          <el-select v-model="scheduleForm.employee_id" filterable style="width: 100%">
            <el-option
              v-for="u in scheduleResources"
              :key="u.id"
              :label="u.department_name ? `${u.name} · ${u.department_name}` : u.name"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="scheduleForm.resource_type" style="width: 100%">
            <el-option
              v-for="o in SCHEDULE_RESOURCE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排期分类">
          <el-select v-model="scheduleForm.schedule_type" clearable style="width: 100%">
            <el-option
              v-for="o in SCHEDULE_TYPE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间段" required>
          <el-date-picker
            v-model="scheduleRange"
            type="datetimerange"
            style="width: 100%"
            range-separator="~"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="scheduleForm.location" placeholder="选填" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="scheduleForm.content" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleVisible = false">取消</el-button>
        <el-button type="primary" :loading="scheduleSaving" @click="onCreateSchedule">
          创建排期
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  TICKET_ACTION_LABEL,
  TICKET_PRIORITY_OPTIONS,
  TICKET_STATUS_LABEL,
  TICKET_TYPE_OPTIONS,
  acceptTicket,
  assignTicket,
  closeTicket,
  commentTicket,
  completeTicket,
  confirmTicket,
  fetchAssigneeOptions,
  fetchTicketDetail,
  reopenTicket,
  returnTicket,
  transferTicket,
  type AssigneeOption,
  type Ticket,
} from '@/api/tickets'
import {
  SCHEDULE_RESOURCE_OPTIONS,
  SCHEDULE_STATUS_LABEL,
  SCHEDULE_TYPE_OPTIONS,
  createSchedule,
  fetchResourceOptions,
  fetchSchedules,
  type ResourceOption,
  type Schedule,
} from '@/api/schedules'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const isCompact = useMatchMedia('(max-width: 768px)')
const descCols = computed(() => (isCompact.value ? 1 : 3))
const loading = ref(false)
const saving = ref(false)
const commenting = ref(false)
const item = ref<Ticket | null>(null)
const comment = ref('')
const assignees = ref<AssigneeOption[]>([])

const assignVisible = ref(false)
const transferVisible = ref(false)
const confirmVisible = ref(false)
const assigneeId = ref<number | undefined>()
const assignRemark = ref('')
const transferReason = ref('')
const satisfaction = ref(5)
const satisfactionComment = ref('')

const ticketId = computed(() => Number(route.params.id))

const userStore = useUserStore()
const canManageSchedule = computed(() =>
  ['pending_assign', 'pending_accept', 'processing', 'pending_confirm', 'completed'].includes(
    item.value?.status || '',
  ) && (userStore.hasPermission('schedule:view') || userStore.hasPermission('*')),
)

const ticketSchedules = ref<Schedule[]>([])
const scheduleLoading = ref(false)
const scheduleVisible = ref(false)
const scheduleSaving = ref(false)
const scheduleResources = ref<ResourceOption[]>([])
const scheduleRange = ref<[string, string] | null>(null)
const scheduleForm = reactive({
  title: '',
  employee_id: undefined as number | undefined,
  resource_type: 'other',
  schedule_type: '' as string,
  location: '',
  content: '',
})

function typeLabel(code: string) {
  return TICKET_TYPE_OPTIONS.find((x) => x.value === code)?.label || code
}

function priorityLabel(code: string) {
  return TICKET_PRIORITY_OPTIONS.find((x) => x.value === code)?.label || code
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    pending_assign: 'info',
    pending_accept: 'warning',
    processing: '',
    pending_confirm: 'warning',
    completed: 'success',
    closed: 'info',
  }
  return map[s] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

async function loadAssignees() {
  const { data } = await fetchAssigneeOptions()
  assignees.value = data
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchTicketDetail(ticketId.value)
    item.value = data
  } finally {
    loading.value = false
  }
  await loadTicketSchedules()
}

async function loadTicketSchedules() {
  if (!ticketId.value) return
  scheduleLoading.value = true
  try {
    const { data } = await fetchSchedules({
      ticket_id: ticketId.value,
      page: 1,
      page_size: 50,
    })
    ticketSchedules.value = data.items || []
  } catch {
    ticketSchedules.value = []
  } finally {
    scheduleLoading.value = false
  }
}

async function ensureScheduleResources() {
  if (scheduleResources.value.length) return
  try {
    const { data } = await fetchResourceOptions()
    scheduleResources.value = data
  } catch {
    scheduleResources.value = []
  }
}

async function openScheduleCreate() {
  await ensureScheduleResources()
  scheduleForm.title = item.value?.title || ''
  scheduleForm.employee_id = item.value?.assignee_id || undefined
  scheduleForm.resource_type = 'other'
  scheduleForm.schedule_type = ''
  scheduleForm.location = ''
  scheduleForm.content = ''
  scheduleRange.value = null
  scheduleVisible.value = true
}

async function onCreateSchedule() {
  if (!scheduleForm.title.trim()) {
    ElMessage.warning('请填写排期标题')
    return
  }
  if (!scheduleForm.employee_id) {
    ElMessage.warning('请选择被排期人')
    return
  }
  if (!scheduleRange.value || !scheduleRange.value[0] || !scheduleRange.value[1]) {
    ElMessage.warning('请选择时间段')
    return
  }
  scheduleSaving.value = true
  try {
    await createSchedule({
      title: scheduleForm.title.trim(),
      resource_type: scheduleForm.resource_type,
      schedule_type: scheduleForm.schedule_type || undefined,
      employee_id: scheduleForm.employee_id,
      ticket_id: ticketId.value,
      project_id: item.value?.project_id || undefined,
      project_task_id: item.value?.task_id || undefined,
      start_time: scheduleRange.value[0],
      end_time: scheduleRange.value[1],
      location: scheduleForm.location || undefined,
      content: scheduleForm.content || undefined,
    })
    ElMessage.success('已创建排期')
    scheduleVisible.value = false
    await loadTicketSchedules()
  } finally {
    scheduleSaving.value = false
  }
}

async function openAssign() {
  await loadAssignees()
  assigneeId.value = item.value?.assignee_id || undefined
  assignRemark.value = ''
  assignVisible.value = true
}

async function openTransfer() {
  await loadAssignees()
  assigneeId.value = undefined
  transferReason.value = ''
  transferVisible.value = true
}

function openConfirmClose() {
  satisfaction.value = item.value?.satisfaction || 5
  satisfactionComment.value = item.value?.satisfaction_comment || ''
  confirmVisible.value = true
}

async function onAssign() {
  if (!assigneeId.value) {
    ElMessage.warning('请选择处理人')
    return
  }
  saving.value = true
  try {
    await assignTicket(ticketId.value, assigneeId.value, assignRemark.value || undefined)
    ElMessage.success('已分派')
    assignVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onTransfer() {
  if (!assigneeId.value) {
    ElMessage.warning('请选择新处理人')
    return
  }
  saving.value = true
  try {
    await transferTicket(ticketId.value, assigneeId.value, transferReason.value || undefined)
    ElMessage.success('已转派')
    transferVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onAccept() {
  try {
    await ElMessageBox.confirm('确认接单并开始处理？', '接单处理')
    await acceptTicket(ticketId.value)
    ElMessage.success('已接单')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function openComplete() {
  try {
    const { value } = await ElMessageBox.prompt('请填写可验收的处理结果', '提交处理结果', {
      inputType: 'textarea',
      inputPlaceholder: '处理结果',
      confirmButtonText: '提交',
    })
    if (!value?.trim()) {
      ElMessage.warning('请填写处理结果')
      return
    }
    await completeTicket(ticketId.value, value.trim())
    ElMessage.success('已提交，等待发起人验收')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function openReturn() {
  try {
    const { value } = await ElMessageBox.prompt('请说明退回原因', '退回处理', {
      inputType: 'textarea',
      confirmButtonText: '退回',
    })
    if (!value?.trim()) {
      ElMessage.warning('请填写退回原因')
      return
    }
    await returnTicket(ticketId.value, value.trim())
    ElMessage.success('已退回处理')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onConfirmClose() {
  if (!satisfaction.value) {
    ElMessage.warning('请选择满意度')
    return
  }
  saving.value = true
  try {
    if (item.value?.status === 'pending_confirm') {
      await confirmTicket(ticketId.value, {
        satisfaction: satisfaction.value,
        comment: satisfactionComment.value || undefined,
        close: true,
      })
    } else {
      await closeTicket(ticketId.value, {
        satisfaction: satisfaction.value,
        comment: satisfactionComment.value || undefined,
      })
    }
    ElMessage.success('已验收关闭')
    confirmVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function openReopen() {
  try {
    const { value } = await ElMessageBox.prompt('请说明重开原因', '重开工单', {
      inputType: 'textarea',
      confirmButtonText: '重开',
    })
    if (!value?.trim()) {
      ElMessage.warning('请填写重开原因')
      return
    }
    await reopenTicket(ticketId.value, value.trim())
    ElMessage.success('工单已重开')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onComment() {
  if (!comment.value.trim()) return
  commenting.value = true
  try {
    await commentTicket(ticketId.value, comment.value.trim())
    comment.value = ''
    ElMessage.success('已评论')
    await loadDetail()
  } finally {
    commenting.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.top-bar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 8px;
  flex-wrap: wrap;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.schedule-card {
  margin-top: 12px;
}
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
}
.title-block {
  min-width: 0;
}
.flow-hint {
  margin: 6px 0 0;
  font-size: 12px;
  font-weight: 400;
  color: var(--crm-ink-soft, #909399);
}
.header-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.records-card {
  margin-top: 12px;
}
.comment-box {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.comment-box .el-input {
  flex: 1;
}
.record-item {
  line-height: 1.5;
}
.record-content {
  margin-top: 4px;
  color: #606266;
  white-space: pre-wrap;
}
.field-hint {
  margin-top: 4px;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
  line-height: 1.4;
}
.hint {
  margin: 0 0 12px;
  color: var(--crm-ink-soft, #909399);
  font-size: 13px;
  line-height: 1.5;
}
@media (max-width: 768px) {
  .top-bar {
    align-items: stretch;
  }
  .actions {
    width: 100%;
  }
  .actions .el-button {
    flex: 1 1 calc(50% - 8px);
  }
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .title-block span {
    word-break: break-word;
    line-height: 1.35;
  }
  .comment-box {
    flex-direction: column;
  }
  .comment-box .el-button {
    width: 100%;
  }
  .satisfaction-group {
    display: flex;
    flex-wrap: wrap;
    width: 100%;
  }
  .satisfaction-group :deep(.el-radio-button) {
    flex: 1 1 100%;
  }
  .satisfaction-group :deep(.el-radio-button__inner) {
    width: 100%;
  }
}
</style>
