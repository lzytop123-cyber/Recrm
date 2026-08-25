<template>
  <div class="crm-page emp-detail" v-loading="loading">
    <div class="detail-head">
      <el-button @click="router.push('/org')">← 返回员工列表</el-button>
      <div class="identity" v-if="emp">
        <span class="avatar">{{ (emp.real_name || emp.username || '?').slice(0, 1) }}</span>
        <div>
          <div class="name-line">
            <h1>{{ emp.real_name || emp.username }}</h1>
            <el-tag size="small" :type="emp.employment_status === '正式' ? 'success' : 'warning'">
              {{ emp.employment_status || (emp.is_active ? '在职' : '离职') }}
            </el-tag>
          </div>
          <p>
            {{ emp.employee_no || emp.username }} · {{ emp.department_name || '—' }} ·
            {{ emp.job_title || '—' }}
          </p>
        </div>
      </div>
      <div class="head-meta" v-if="emp">
        <small>直属负责人</small>
        <b>{{ emp.manager_name || '—' }}</b>
        <small>入职日期</small>
        <b>{{ emp.hire_date || '—' }}</b>
      </div>
    </div>

    <div class="tabs-row">
      <el-radio-group v-model="tab" size="default">
        <el-radio-button value="overview">档案总览</el-radio-button>
        <el-radio-button value="history">任职经历</el-radio-button>
        <el-radio-button value="contract">合同与档案</el-radio-button>
        <el-radio-button value="attendance">飞书考勤</el-radio-button>
      </el-radio-group>
      <div class="tab-actions" v-if="canManageOrg && emp">
        <el-button @click="onTransfer">转岗</el-button>
        <el-button type="danger" plain @click="onResign">离职</el-button>
      </div>
    </div>

    <template v-if="emp && tab === 'overview'">
      <el-row :gutter="12">
        <el-col :span="mainCol">
          <el-card class="block">
            <template #header>
              <div class="card-head">
                <div>
                  <h3>基本资料</h3>
                  <p>敏感字段按权限脱敏展示</p>
                </div>
                <el-tag :type="emp.archive_status === '完整' ? 'success' : 'warning'" size="small">
                  {{ emp.archive_status === '完整' ? '档案完整' : '待补资料' }}
                </el-tag>
              </div>
            </template>
            <div class="info-grid">
              <div><small>员工编号</small><b>{{ emp.employee_no || emp.username }}</b></div>
              <div><small>姓名</small><b>{{ emp.real_name || emp.username }}</b></div>
              <div><small>在职状态</small><b>{{ emp.employment_status || '—' }}</b></div>
              <div><small>手机号码</small><b>{{ maskPhone(emp.phone) }}</b></div>
              <div><small>飞书账号</small><b>{{ emp.feishu_bound ? '已绑定' : '未绑定' }}</b></div>
              <div><small>身份同步</small><b>{{ emp.identity_sync || '—' }}</b></div>
            </div>
          </el-card>
          <el-card class="block">
            <template #header>
              <div class="card-head">
                <div>
                  <h3>任职信息</h3>
                  <p>当前有效的组织与岗位关系</p>
                </div>
              </div>
            </template>
            <div class="info-grid">
              <div><small>部门</small><b>{{ emp.department_name || '—' }}</b></div>
              <div><small>岗位</small><b>{{ emp.job_title || '—' }}</b></div>
              <div><small>直属负责人</small><b>{{ emp.manager_name || '—' }}</b></div>
              <div><small>入职日期</small><b>{{ emp.hire_date || '—' }}</b></div>
              <div><small>用工状态</small><b>{{ emp.employment_status || '—' }}</b></div>
              <div>
                <small>数据权限</small>
                <b>{{ emp.roles?.map((r) => r.name).join('、') || '按角色授权' }}</b>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="sideCol">
          <el-card class="block">
            <template #header>
              <div class="card-head">
                <div>
                  <h3>今日状态</h3>
                  <p>来自飞书考勤事实</p>
                </div>
                <el-tag size="small" :type="statusTag(emp.today_status)">
                  {{ emp.today_status || '暂无' }}
                </el-tag>
              </div>
            </template>
            <div class="side-stats">
              <div>
                <small>本月出勤</small>
                <b>{{ attendance?.actual_days ?? 0 }}/{{ attendance?.expected_days ?? 0 }} 天</b>
              </div>
              <div>
                <small>异常待确认</small>
                <b>{{ attendance?.exception_pending ?? 0 }} 项</b>
              </div>
            </div>
          </el-card>
          <el-card class="block">
            <template #header>
              <div class="card-head"><div><h3>待办提醒</h3></div></div>
            </template>
            <div class="todo-list">
              <div v-for="t in emp.todos || []" :key="t.key" class="todo-row">
                <span>{{ t.label }}</span>
                <el-tag size="small" :type="t.status === '正常' ? 'success' : 'warning'">{{ t.status }}</el-tag>
              </div>
              <div v-if="!(emp.todos && emp.todos.length)" class="empty">暂无待办</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <template v-else-if="emp && tab === 'history'">
      <el-card>
        <template #header>
          <div class="card-head">
            <div>
              <h3>任职经历</h3>
              <p>入职、转正、转岗和离职记录均保留历史版本</p>
            </div>
          </div>
        </template>
        <el-timeline v-if="history.length">
          <el-timeline-item
            v-for="(h, idx) in history"
            :key="h.id"
            :type="idx === 0 ? 'primary' : 'info'"
            :timestamp="formatDt(h.occurred_at)"
          >
            <b>{{ h.title }}</b>
            <div class="muted">{{ h.detail || '' }}</div>
          </el-timeline-item>
        </el-timeline>
        <div v-else class="empty">暂无转岗、离职或返聘记录</div>
      </el-card>
    </template>

    <template v-else-if="emp && tab === 'contract'">
      <el-row :gutter="12">
        <el-col :span="contractMainCol">
          <el-card>
            <template #header>
              <div class="card-head">
                <div>
                  <h3>劳动合同</h3>
                  <p>合同版本、期限与签署事实可追溯</p>
                </div>
                <el-tag size="small" type="success">{{ emp.contract_status || '生效中' }}</el-tag>
              </div>
            </template>
            <div class="info-grid">
              <div><small>合同类型</small><b>{{ emp.contract_type || '固定期限劳动合同' }}</b></div>
              <div><small>合同主体</small><b>中泰旭鼎</b></div>
              <div><small>开始日期</small><b>{{ emp.contract_start || emp.hire_date || '—' }}</b></div>
              <div><small>结束日期</small><b>{{ emp.contract_end || '—' }}</b></div>
              <div><small>签署状态</small><b>{{ emp.contract_status || '已签署' }}</b></div>
              <div><small>原件状态</small><b>本地归档</b></div>
            </div>
            <div v-if="canManageOrg" class="contract-edit">
              <el-button type="primary" link @click="editContract = true">维护合同信息</el-button>
            </div>
          </el-card>
        </el-col>
        <el-col :span="contractSideCol">
          <el-card>
            <template #header>
              <div class="card-head">
                <div>
                  <h3>档案附件</h3>
                  <p>仅记录归档状态，不公开证件明文</p>
                </div>
              </div>
            </template>
            <div class="archive-list">
              <div v-for="item in archiveItems" :key="item[0]" class="todo-row">
                <span>{{ item[0] }}</span>
                <el-tag size="small" :type="item[1] === '已归档' ? 'success' : 'warning'">{{ item[1] }}</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <template v-else-if="emp && tab === 'attendance'">
      <div class="attend-toolbar">
        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          placeholder="月份"
          @change="loadAttendance(true)"
        />
        <el-button :loading="attendLoading" @click="loadAttendance(true)">从飞书刷新</el-button>
      </div>
      <div class="crm-stats" :style="{ '--crm-stats-cols': '4' }">
        <button type="button" class="crm-stat-tile is-static" disabled>
          <span>本月应出勤</span>
          <strong>{{ attendance?.expected_days ?? 0 }}天</strong>
          <small>按飞书考勤组日历</small>
        </button>
        <button type="button" class="crm-stat-tile is-static" disabled>
          <span>实际出勤</span>
          <strong>{{ attendance?.actual_days ?? 0 }}天</strong>
          <small>不含请假与外出</small>
        </button>
        <button type="button" class="crm-stat-tile is-static" disabled>
          <span>请假 / 外出</span>
          <strong>{{ attendance?.leave_days ?? 0 }} / {{ attendance?.out_days ?? 0 }}</strong>
          <small>审批事实同步</small>
        </button>
        <button type="button" class="crm-stat-tile is-static" disabled>
          <span>异常待确认</span>
          <strong>{{ attendance?.exception_pending ?? 0 }}</strong>
          <small>迟到、缺卡或旷工</small>
        </button>
      </div>
      <el-card>
        <template #header>
          <div class="card-head">
            <div>
              <h3>近期考勤事实</h3>
              <p>系统使用飞书事实，不重复维护打卡规则</p>
            </div>
          </div>
        </template>
        <div class="attend-table-wrap">
          <el-table :data="attendance?.days || []" v-loading="attendLoading" stripe>
            <el-table-column prop="work_date" label="日期" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="首次打卡" width="110">
              <template #default="{ row }">{{ formatPunch(row.first_punch) }}</template>
            </el-table-column>
            <el-table-column label="末次打卡" width="110">
              <template #default="{ row }">{{ formatPunch(row.last_punch) }}</template>
            </el-table-column>
            <el-table-column prop="source" label="数据来源" min-width="120" />
          </el-table>
        </div>
      </el-card>
    </template>

    <el-dialog
      v-model="editContract"
      title="维护合同信息"
      width="480px"
      :fullscreen="isCompact"
      destroy-on-close
    >
      <el-form
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="合同类型">
          <el-input v-model="contractForm.contract_type" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="contractForm.contract_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="contractForm.contract_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="合同状态">
          <el-input v-model="contractForm.contract_status" />
        </el-form-item>
        <el-form-item label="档案状态">
          <el-select v-model="contractForm.archive_status" style="width: 100%">
            <el-option label="完整" value="完整" />
            <el-option label="待补" value="待补" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editContract = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveContract">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="transferVisible"
      title="转岗"
      width="460px"
      :fullscreen="isCompact"
      destroy-on-close
    >
      <el-form
        :label-width="isCompact ? 'auto' : '90px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="新岗位">
          <el-input v-model="transferForm.job_title" />
        </el-form-item>
        <el-form-item label="新部门">
          <el-tree-select
            v-model="transferForm.department_id"
            :data="deptTree"
            check-strictly
            :props="{ label: 'name', value: 'id', children: 'children' }"
            clearable
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTransfer">确认转岗</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { notifyError } from '@/utils/notify'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  fetchDepartments,
  fetchEmployee,
  fetchEmployeeAttendance,
  fetchEmployeeHistory,
  updateEmployee,
  type AttendanceSummary,
  type Department,
  type Employee,
  type EmployeeHistory,
} from '@/api/org'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCompact = useMatchMedia('(max-width: 768px)')
const canManageOrg = computed(() => userStore.hasPermission('org:manage'))
const mainCol = computed(() => (isCompact.value ? 24 : 16))
const sideCol = computed(() => (isCompact.value ? 24 : 8))
const contractMainCol = computed(() => (isCompact.value ? 24 : 14))
const contractSideCol = computed(() => (isCompact.value ? 24 : 10))

const loading = ref(false)
const attendLoading = ref(false)
const saving = ref(false)
const emp = ref<Employee | null>(null)
const history = ref<EmployeeHistory[]>([])
const attendance = ref<AttendanceSummary | null>(null)
const deptTree = ref<Department[]>([])
const tab = ref('overview')
const month = ref(new Date().toISOString().slice(0, 7))
const editContract = ref(false)
const transferVisible = ref(false)
const contractForm = reactive({
  contract_type: '',
  contract_start: '',
  contract_end: '',
  contract_status: '',
  archive_status: '',
})
const transferForm = reactive({
  job_title: '',
  department_id: undefined as number | undefined,
})

const userId = computed(() => Number(route.params.id))

const archiveItems = computed(() => {
  const complete = emp.value?.archive_status === '完整'
  return [
    ['身份与入职资料', complete ? '已归档' : '待补充'],
    ['劳动合同', emp.value?.contract_end ? '已归档' : '待补充'],
    ['保密与知识产权协议', complete ? '已归档' : '待补充'],
    ['岗位或转岗确认材料', complete ? '已归档' : '待补充'],
  ] as [string, string][]
})

function maskPhone(phone?: string | null) {
  if (!phone) return '—'
  if (phone.length < 7) return '已脱敏 · 授权可见'
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

function statusTag(s?: string | null) {
  if (!s) return 'info'
  if (s === '正常') return 'success'
  if (['请假', '外出', '休息日'].includes(s)) return 'warning'
  return 'danger'
}

function formatDt(v: string) {
  return v?.replace('T', ' ').slice(0, 16) || ''
}

function formatPunch(v?: string | null) {
  if (!v) return '—'
  return String(v).slice(0, 8)
}

async function loadEmp() {
  loading.value = true
  try {
    const { data } = await fetchEmployee(userId.value)
    emp.value = data
    Object.assign(contractForm, {
      contract_type: data.contract_type || '',
      contract_start: data.contract_start || '',
      contract_end: data.contract_end || '',
      contract_status: data.contract_status || '',
      archive_status: data.archive_status || '完整',
    })
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  const { data } = await fetchEmployeeHistory(userId.value)
  history.value = data || []
}

async function loadAttendance(refresh = false) {
  attendLoading.value = true
  try {
    const { data } = await fetchEmployeeAttendance(userId.value, {
      month: month.value,
      refresh,
    })
    attendance.value = data
    if (emp.value) emp.value.today_status = data.today_status
  } catch (e: any) {
    notifyError(e, '考勤加载失败')
  } finally {
    attendLoading.value = false
  }
}

async function saveContract() {
  saving.value = true
  try {
    await updateEmployee(userId.value, { ...contractForm })
    editContract.value = false
    ElMessage.success('合同信息已更新')
    await loadEmp()
  } finally {
    saving.value = false
  }
}

function onTransfer() {
  transferForm.job_title = emp.value?.job_title || ''
  transferForm.department_id = emp.value?.department_id || undefined
  transferVisible.value = true
}

async function saveTransfer() {
  saving.value = true
  try {
    await updateEmployee(userId.value, {
      job_title: transferForm.job_title || undefined,
      department_id: transferForm.department_id ?? null,
    })
    transferVisible.value = false
    ElMessage.success('已转岗')
    await Promise.all([loadEmp(), loadHistory()])
  } finally {
    saving.value = false
  }
}

async function onResign() {
  await ElMessageBox.confirm('确认办理离职？账号将被停用并写入任职经历。', '离职')
  await updateEmployee(userId.value, { employment_status: '离职', is_active: false })
  ElMessage.success('已办理离职')
  await Promise.all([loadEmp(), loadHistory()])
}

watch(tab, (v) => {
  if (v === 'history' && !history.value.length) loadHistory()
  if (v === 'attendance' && !attendance.value) loadAttendance(false)
})

onMounted(async () => {
  const { data } = await fetchDepartments()
  deptTree.value = data || []
  await loadEmp()
  await loadAttendance(false)
  await loadHistory()
})
</script>

<style scoped>
.detail-head {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
.identity {
  display: flex;
  gap: 12px;
  align-items: center;
  flex: 1;
}
.avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #e8eef8;
  color: #2f5bb8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
}
.name-line {
  display: flex;
  gap: 8px;
  align-items: center;
}
.name-line h1 {
  margin: 0;
  font-size: 22px;
}
.identity p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.head-meta {
  display: grid;
  grid-template-columns: auto auto;
  gap: 4px 16px;
  font-size: 13px;
}
.head-meta small {
  color: var(--el-text-color-secondary);
}
.tabs-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.block {
  margin-bottom: 12px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.card-head h3 {
  margin: 0;
  font-size: 16px;
}
.card-head p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 18px;
}
.info-grid small {
  display: block;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-bottom: 4px;
}
.side-stats,
.todo-list,
.archive-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.todo-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-top: 4px;
}
.empty {
  color: var(--el-text-color-secondary);
  padding: 12px 0;
}
.attend-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.contract-edit {
  margin-top: 16px;
}
.crm-stat-tile small {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: 400;
}
.attend-table-wrap {
  min-width: 0;
}

@media (max-width: 768px) {
  .emp-detail {
    padding-bottom: 16px;
  }

  .detail-head {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .detail-head > .el-button {
    align-self: flex-start;
  }

  .identity {
    width: 100%;
  }

  .name-line h1 {
    font-size: 18px;
  }

  .head-meta {
    width: 100%;
    grid-template-columns: 1fr 1fr;
    gap: 8px 12px;
    padding: 10px 12px;
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 10px;
    background: var(--el-fill-color-blank);
  }

  .tabs-row {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .tabs-row :deep(.el-radio-group) {
    width: 100%;
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .tabs-row :deep(.el-radio-button) {
    flex: 1 0 auto;
  }

  .tabs-row :deep(.el-radio-button__inner) {
    width: 100%;
    padding: 8px 10px;
    white-space: nowrap;
  }

  .tab-actions {
    display: flex;
    gap: 8px;
  }

  .tab-actions .el-button {
    flex: 1 1 auto;
  }

  .card-head p {
    display: none;
  }

  .info-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .attend-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .attend-toolbar :deep(.el-date-editor) {
    width: 100% !important;
  }

  .emp-detail :deep(.crm-stats) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .attend-table-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
}
</style>
