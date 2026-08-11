<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/timesheets')">返回列表</el-button>
      <div class="actions" v-if="item">
        <el-button
          v-if="['draft', 'rejected'].includes(item.status)"
          type="primary"
          @click="editVisible = true"
        >
          编辑
        </el-button>
        <el-button
          v-if="['draft', 'rejected'].includes(item.status)"
          type="warning"
          @click="onSubmit"
        >
          提交审批
        </el-button>
        <el-button
          v-if="item.status === 'submitted'"
          v-perm="'timesheet:approve'"
          type="success"
          @click="onApprove"
        >
          审批通过
        </el-button>
        <el-button
          v-if="item.status === 'submitted'"
          v-perm="'timesheet:approve'"
          type="danger"
          plain
          @click="onReject"
        >
          驳回
        </el-button>
      </div>
    </div>

    <el-card v-if="item">
      <template #header>
        <div class="card-header">
          <span>工时 #{{ item.id }} · {{ item.work_date }}</span>
          <el-tag :type="statusTag(item.status)" size="small">
            {{ TIMESHEET_STATUS_LABEL[item.status] || item.status }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="日期">{{ item.work_date }}</el-descriptions-item>
        <el-descriptions-item label="工时">{{ item.hours }} 小时</el-descriptions-item>
        <el-descriptions-item label="类型">{{ typeLabel(item.work_type) }}</el-descriptions-item>
        <el-descriptions-item label="填报人">{{ item.user_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目" :span="2">
          <el-button
            v-if="item.project_id"
            link
            type="primary"
            @click="$router.push(`/projects/${item.project_id}`)"
          >
            {{ item.project_no }} · {{ item.project_name }}
          </el-button>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="审批人">{{ item.approver_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批时间">{{ formatTime(item.approved_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="item.reject_reason" label="驳回原因" :span="3">
          {{ item.reject_reason }}
        </el-descriptions-item>
        <el-descriptions-item label="工作内容" :span="3">{{ item.content }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ item.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑工时" width="560px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="日期">
          <el-date-picker v-model="editForm.work_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工时">
          <el-input-number v-model="editForm.hours" :min="0.5" :max="24" :step="0.5" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="editForm.work_type" style="width: 100%">
            <el-option
              v-for="opt in TIMESHEET_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.work_type === 'project'" label="项目">
          <el-select
            v-model="editForm.project_id"
            filterable
            remote
            :remote-method="searchProjects"
            style="width: 100%"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="`${p.project_no} · ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工作内容">
          <el-input v-model="editForm.content" type="textarea" :rows="3" />
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  TIMESHEET_STATUS_LABEL,
  TIMESHEET_TYPE_OPTIONS,
  approveTimesheet,
  fetchTimesheetDetail,
  rejectTimesheet,
  submitTimesheet,
  updateTimesheet,
  type Timesheet,
} from '@/api/timesheets'
import { fetchDirectoryProjects, type DirectoryProject } from '@/api/directory'

const route = useRoute()
const loading = ref(false)
const saving = ref(false)
const item = ref<Timesheet | null>(null)
const editVisible = ref(false)
const projectOptions = ref<DirectoryProject[]>([])

const editForm = reactive({
  work_date: '',
  hours: 8,
  work_type: 'project',
  project_id: undefined as number | undefined,
  content: '',
  remark: '',
})

const tsId = computed(() => Number(route.params.id))

function typeLabel(code: string) {
  return TIMESHEET_TYPE_OPTIONS.find((x) => x.value === code)?.label || code
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    draft: 'info',
    submitted: 'warning',
    approved: 'success',
    rejected: 'danger',
  }
  return map[s] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function fillEdit() {
  if (!item.value) return
  editForm.work_date = item.value.work_date
  editForm.hours = Number(item.value.hours) || 8
  editForm.work_type = item.value.work_type
  editForm.project_id = item.value.project_id || undefined
  editForm.content = item.value.content
  editForm.remark = item.value.remark || ''
}

async function searchProjects(q: string) {
  const { data } = await fetchDirectoryProjects({ keyword: q || undefined, page: 1, page_size: 20 })
  projectOptions.value = data.items
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchTimesheetDetail(tsId.value)
    item.value = data
    fillEdit()
  } finally {
    loading.value = false
  }
}

watch(editVisible, async (v) => {
  if (v) {
    fillEdit()
    await searchProjects('')
  }
})

async function onSaveEdit() {
  if (!editForm.content.trim()) {
    ElMessage.warning('请填写工作内容')
    return
  }
  saving.value = true
  try {
    await updateTimesheet(tsId.value, {
      work_date: editForm.work_date,
      hours: editForm.hours,
      work_type: editForm.work_type,
      project_id: editForm.work_type === 'project' ? editForm.project_id : undefined,
      content: editForm.content,
      remark: editForm.remark || undefined,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onSubmit() {
  try {
    await ElMessageBox.confirm('确认提交审批？', '提交')
    await submitTimesheet(tsId.value)
    ElMessage.success('已提交')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onApprove() {
  try {
    await ElMessageBox.confirm('确认审批通过？', '审批')
    await approveTimesheet(tsId.value)
    ElMessage.success('已通过')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onReject() {
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回', {
      inputPlaceholder: '驳回原因',
      confirmButtonText: '驳回',
    })
    await rejectTimesheet(tsId.value, value || '驳回')
    ElMessage.success('已驳回')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

onMounted(loadDetail)
</script>


