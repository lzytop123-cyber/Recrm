<template>
  <div class="crm-page timesheets-page">
    <div class="crm-stats" :style="{ '--crm-stats-cols': String(statCards.length) }">
      <button
        v-for="item in statCards"
        :key="item.key"
        type="button"
        class="crm-stat-tile"
        @click="onStatClick(item)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </div>

    <section class="crm-panel">
      <div class="toolbar">
        <div class="filters">
          <el-radio-group v-model="scope" @change="reload">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="mine">我的</el-radio-button>
          </el-radio-group>
          <el-select v-model="status" clearable placeholder="状态" style="width: 120px" @change="reload">
            <el-option
              v-for="(label, key) in TIMESHEET_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-select v-model="workType" clearable placeholder="类型" style="width: 120px" @change="reload">
            <el-option
              v-for="opt in TIMESHEET_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始"
            end-placeholder="结束"
            @change="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">登记工时</el-button>
      </div>

      <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
        <el-table-column prop="work_date" label="日期" width="110" />
        <el-table-column prop="user_name" label="填报人" width="100" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ typeLabel(row.work_type) }}</template>
        </el-table-column>
        <el-table-column label="项目" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.project_name ? `${row.project_no} · ${row.project_name}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="工时" width="80">
          <template #default="{ row }">{{ row.hours }}h</template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">
              {{ TIMESHEET_STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button
              v-if="['draft', 'rejected'].includes(row.status)"
              link
              type="warning"
              @click.stop="quickSubmit(row)"
            >
              提交
            </el-button>
            <el-button
              v-if="row.status === 'submitted' && !row.approval_in_center"
              v-perm="'timesheet:approve'"
              link
              type="success"
              @click.stop="quickApprove(row)"
            >
              通过
            </el-button>
            <el-button
              v-if="row.status === 'submitted' && row.approval_in_center"
              link
              type="primary"
              @click.stop="router.push('/approvals')"
            >
              审批中心
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </section>

    <el-dialog v-model="createVisible" title="登记工时" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="日期" prop="work_date">
          <el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工时" prop="hours">
          <el-input-number v-model="form.hours" :min="0.5" :max="24" :step="0.5" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="类型" prop="work_type">
          <el-select v-model="form.work_type" style="width: 100%">
            <el-option
              v-for="opt in TIMESHEET_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.work_type === 'project'" label="项目" prop="project_id">
          <el-select
            v-model="form.project_id"
            filterable
            remote
            :remote-method="searchProjects"
            :loading="projectLoading"
            placeholder="搜索项目"
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
        <el-form-item label="工作内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">保存草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  TIMESHEET_STATUS_LABEL,
  TIMESHEET_TYPE_OPTIONS,
  approveTimesheet,
  createTimesheet,
  fetchTimesheetStats,
  fetchTimesheets,
  submitTimesheet,
  type Timesheet,
  type TimesheetStats,
} from '@/api/timesheets'
import { fetchDirectoryProjects, type DirectoryProject } from '@/api/directory'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const projectLoading = ref(false)
const items = ref<Timesheet[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('mine')
const status = ref<string | undefined>()
const workType = ref<string | undefined>()
const dateRange = ref<string[] | null>(null)
const stats = ref<TimesheetStats | null>(null)
const projectOptions = ref<DirectoryProject[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  work_date: new Date().toISOString().slice(0, 10),
  hours: 8,
  work_type: 'project',
  project_id: undefined as number | undefined,
  content: '',
  remark: '',
})
const rules: FormRules = {
  work_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  hours: [{ required: true, message: '请输入工时', trigger: 'blur' }],
  work_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  content: [{ required: true, message: '请填写工作内容', trigger: 'blur' }],
}

const statCards = computed(() => {
  const s = stats.value
  return [
    { key: 'total', label: '全部', value: s?.total ?? 0, scope: 'all' },
    { key: 'draft', label: '草稿', value: s?.draft ?? 0, status: 'draft' },
    { key: 'submitted', label: '待审批', value: s?.submitted ?? 0, status: 'submitted' },
    { key: 'approved', label: '已通过', value: s?.approved ?? 0, status: 'approved' },
    { key: 'my_hours', label: '我的工时', value: `${s?.my_hours ?? 0}h`, scope: 'mine' },
    { key: 'approved_hours', label: '已批工时', value: `${s?.approved_hours ?? 0}h`, status: 'approved' },
  ]
})

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

function onStatClick(item: { status?: string; scope?: string }) {
  if (item.scope) scope.value = item.scope
  status.value = item.status
  page.value = 1
  reload()
}

async function searchProjects(q: string) {
  projectLoading.value = true
  try {
    const { data } = await fetchDirectoryProjects({ keyword: q || undefined, page: 1, page_size: 20 })
    projectOptions.value = data.items
  } finally {
    projectLoading.value = false
  }
}

async function loadStats() {
  const { data } = await fetchTimesheetStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchTimesheets({
      scope: scope.value,
      status: status.value,
      work_type: workType.value,
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  loadList()
  loadStats()
}

function goDetail(row: Timesheet) {
  router.push(`/timesheets/${row.id}`)
}

async function openCreate() {
  form.work_date = new Date().toISOString().slice(0, 10)
  form.hours = 8
  form.work_type = 'project'
  form.project_id = undefined
  form.content = ''
  form.remark = ''
  await searchProjects('')
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createTimesheet({
      work_date: form.work_date,
      hours: form.hours,
      work_type: form.work_type,
      project_id: form.work_type === 'project' ? form.project_id : undefined,
      content: form.content,
      remark: form.remark || undefined,
    })
    ElMessage.success('已保存草稿')
    createVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

async function quickSubmit(row: Timesheet) {
  try {
    await ElMessageBox.confirm('确认提交审批？', '提交')
    await submitTimesheet(row.id)
    ElMessage.success('已提交')
    reload()
  } catch {
    /* cancel */
  }
}

async function quickApprove(row: Timesheet) {
  try {
    await ElMessageBox.confirm('确认审批通过？', '审批')
    await approveTimesheet(row.id)
    ElMessage.success('已通过')
    reload()
  } catch {
    /* cancel / no permission */
  }
}

onMounted(() => {
  reload()
})
</script>


