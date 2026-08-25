<template>
  <div class="crm-page org-page crm-fit-page">
    <div class="page-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>员工管理</h1>
        <p>管理入职、档案、转岗、离职、劳动合同和飞书考勤事实。</p>
      </div>
      <div class="head-actions">
        <el-button v-if="canManageOrg" @click="openDeptCreate()">新建部门</el-button>
        <el-dropdown v-if="canSyncOrg" trigger="click" @command="onSyncCommand">
          <el-button :loading="syncing || syncingAttend">
            同步飞书
            <span class="sync-caret">▾</span>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="contacts">同步飞书通讯录</el-dropdown-item>
              <el-dropdown-item command="attendance">同步飞书考勤</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button v-if="canManageOrg" type="primary" @click="openEmployeeCreate">＋ 新增员工</el-button>
      </div>
    </div>

    <div class="crm-stats" :style="{ '--crm-stats-cols': '4' }">
      <button
        v-for="item in statCards"
        :key="item.label"
        type="button"
        class="crm-stat-tile"
        :class="{ 'is-active': item.active }"
        @click="onStatClick(item.key)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small v-if="item.note">{{ item.note }}</small>
      </button>
    </div>

    <div class="org-layout">
      <el-card
        class="org-tree-panel"
        :class="{ 'is-collapsed': isCompact && !treeExpanded }"
        shadow="never"
      >
        <template #header>
          <div class="card-header">
            <button
              v-if="isCompact"
              type="button"
              class="tree-toggle"
              @click="treeExpanded = !treeExpanded"
            >
              <span>组织架构</span>
              <small>{{ selectedDeptName || '全部部门' }}</small>
              <span class="tree-caret" :class="{ 'is-open': treeExpanded }">▾</span>
            </button>
            <span v-else>组织架构</span>
            <div class="card-header-actions">
              <el-button link type="primary" size="small" @click="clearDeptFilter">全部</el-button>
            </div>
          </div>
        </template>
        <el-tree
          v-show="!isCompact || treeExpanded"
          ref="deptTreeRef"
          :data="deptTree"
          node-key="id"
          :current-node-key="selectedDeptId"
          :props="{ label: 'name', children: 'children' }"
          highlight-current
          default-expand-all
          @node-click="onDeptClick"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <span class="tree-label">{{ data.name }} ({{ data.user_count || 0 }})</span>
              <el-dropdown
                v-if="canManageOrg"
                trigger="click"
                @command="(cmd) => onDeptAction(String(cmd), data)"
              >
                <el-button link size="small" class="tree-more" @click.stop>⋯</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="child">新建子部门</el-dropdown-item>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item
                      v-if="data.code !== 'ROOT'"
                      command="delete"
                      divided
                    >
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-tree>
      </el-card>

      <el-card class="org-list-panel" shadow="never">
        <div class="toolbar">
          <div class="filters">
            <el-tag
              v-if="selectedDeptName && !isCompact"
              closable
              type="info"
              @close="clearDeptFilter"
            >
              {{ selectedDeptName }}
            </el-tag>
            <el-input
              v-model="keyword"
              clearable
              placeholder="姓名/工号/手机"
              style="width: 180px"
              @keyup.enter="reloadEmployees"
              @clear="reloadEmployees"
            />
            <el-select
              v-model="employmentFilter"
              clearable
              placeholder="用工状态"
              style="width: 120px"
              @change="reloadEmployees"
            >
              <el-option label="正式" value="正式" />
              <el-option label="试用" value="试用" />
              <el-option label="待入职" value="待入职" />
              <el-option label="离职" value="离职" />
            </el-select>
            <el-select
              v-model="activeFilter"
              clearable
              placeholder="账号状态"
              style="width: 110px"
              @change="reloadEmployees"
            >
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" @click="reloadEmployees">查询</el-button>
          </div>
        </div>

        <div v-if="isCompact" class="emp-card-list" v-loading="empLoading">
          <button
            v-for="row in employees"
            :key="row.id"
            type="button"
            class="emp-card"
            @click="goDetail(row)"
          >
            <span class="avatar">{{ (row.real_name || row.username || '?').slice(0, 1) }}</span>
            <div class="emp-card-main">
              <div class="emp-card-title">
                <b>{{ row.real_name || row.username }}</b>
                <el-tag size="small" :type="employmentTagType(row.employment_status, row.is_active)">
                  {{ row.employment_status || (row.is_active ? '正式' : '离职') }}
                </el-tag>
              </div>
              <p class="emp-card-meta">
                {{ row.employee_no || row.username }}
                <template v-if="row.department_name"> · {{ row.department_name }}</template>
                <template v-if="row.job_title"> · {{ row.job_title }}</template>
              </p>
            </div>
            <div class="emp-card-actions" @click.stop>
              <el-button
                v-if="canManageOrg"
                link
                type="primary"
                @click="openEmployeeEdit(row)"
              >
                编辑
              </el-button>
              <el-button v-else link type="primary" @click="goDetail(row)">档案</el-button>
            </div>
          </button>
          <div v-if="!empLoading && !employees.length" class="emp-card-empty">暂无员工</div>
        </div>

        <div v-else class="table-wrap">
          <el-table
            :data="employees"
            v-loading="empLoading"
            stripe
            size="small"
            height="100%"
            @row-click="goDetail"
          >
            <el-table-column label="员工" min-width="160">
              <template #default="{ row }">
                <div class="emp-cell">
                  <span class="avatar">{{ (row.real_name || row.username || '?').slice(0, 1) }}</span>
                  <div>
                    <b>{{ row.real_name || row.username }}</b>
                    <small>{{ row.employee_no || row.username }}</small>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              prop="department_name"
              label="部门"
              min-width="120"
              show-overflow-tooltip
            />
            <el-table-column prop="job_title" label="岗位" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.job_title || '—' }}</template>
            </el-table-column>
            <el-table-column label="今日状态" width="96">
              <template #default="{ row }">
                <el-tag size="small" :type="todayTagType(row.today_status)">
                  {{ row.today_status || '—' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="用工" width="88">
              <template #default="{ row }">
                <el-tag size="small" :type="employmentTagType(row.employment_status, row.is_active)">
                  {{ row.employment_status || (row.is_active ? '正式' : '离职') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <template v-if="canManageOrg">
                  <el-button link type="primary" @click.stop="openEmployeeEdit(row)">编辑</el-button>
                  <el-button link type="primary" @click.stop="openPasswordReset(row)">修改密码</el-button>
                </template>
                <el-button v-else link type="primary" @click.stop="goDetail(row)">档案</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :layout="isCompact ? 'total, prev, next' : 'total, prev, pager, next'"
            :pager-count="isCompact ? 3 : 7"
            @current-change="loadEmployees"
            @size-change="loadEmployees"
          />
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="deptVisible"
      :title="deptForm.id ? '编辑部门' : '新建部门'"
      width="420px"
      :fullscreen="isCompact"
      destroy-on-close
    >
      <el-form
        :label-width="isCompact ? 'auto' : '80px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="名称">
          <el-input v-model="deptForm.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="deptForm.code" :disabled="deptForm.code === 'ROOT' && !!deptForm.id" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="deptForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDept">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="empVisible"
      :title="empForm.id ? '编辑员工' : '新建员工'"
      width="560px"
      :fullscreen="isCompact"
      destroy-on-close
    >
      <el-form
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item v-if="!empForm.id" label="用户名">
          <el-input v-model="empForm.username" />
        </el-form-item>
        <el-form-item v-if="!empForm.id" label="初始密码">
          <el-input v-model="empForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="empForm.real_name" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="empForm.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="empForm.email" />
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="empForm.job_title" />
        </el-form-item>
        <el-form-item label="工号">
          <el-input v-model="empForm.employee_no" />
        </el-form-item>
        <el-form-item label="用工状态">
          <el-select v-model="empForm.employment_status" clearable style="width: 100%">
            <el-option label="正式" value="正式" />
            <el-option label="试用" value="试用" />
            <el-option label="待入职" value="待入职" />
            <el-option label="离职" value="离职" />
          </el-select>
        </el-form-item>
        <el-form-item label="入职日期">
          <el-date-picker v-model="empForm.hire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="合同到期">
          <el-date-picker v-model="empForm.contract_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="档案状态">
          <el-select v-model="empForm.archive_status" clearable style="width: 100%">
            <el-option label="完整" value="完整" />
            <el-option label="待补" value="待补" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="empForm.id" label="飞书 open_id">
          <el-input v-model="empForm.feishu_open_id" placeholder="ou_xxx" clearable />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="empForm.department_id"
            :data="deptTree"
            check-strictly
            :props="{ label: 'name', value: 'id', children: 'children' }"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="直属负责人">
          <el-select v-model="empForm.manager_id" filterable clearable style="width: 100%">
            <el-option
              v-for="e in managerOptions"
              :key="e.id"
              :label="e.real_name || e.username"
              :value="e.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="empForm.role_ids" multiple filterable style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="empVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEmployee">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pwdVisible"
      :title="pwdTarget ? `修改密码 · ${pwdTarget.real_name || pwdTarget.username}` : '修改密码'"
      width="420px"
      :fullscreen="isCompact"
      destroy-on-close
    >
      <el-form
        :label-width="isCompact ? 'auto' : '90px'"
        :label-position="isCompact ? 'top' : 'right'"
        @submit.prevent
      >
        <el-form-item label="新密码" required>
          <el-input
            v-model="pwdForm.password"
            type="password"
            show-password
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input
            v-model="pwdForm.confirm"
            type="password"
            show-password
            placeholder="再次输入新密码"
            autocomplete="new-password"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="submitPasswordReset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type ElTree } from 'element-plus'
import { notifyError } from '@/utils/notify'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  createDepartment,
  createEmployee,
  deleteDepartment,
  fetchDepartments,
  fetchEmployees,
  fetchOrgRoles,
  fetchOrgStats,
  resetEmployeePassword,
  syncFeishuAttendanceApi,
  syncFeishuContactsApi,
  updateDepartment,
  updateEmployee,
  type Department,
  type Employee,
  type OrgStats,
  type RoleBrief,
} from '@/api/org'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const isCompact = useMatchMedia('(max-width: 768px)')
const treeExpanded = ref(false)
const canManageOrg = computed(() => userStore.hasPermission('org:manage'))
const canSyncOrg = computed(() => userStore.hasPermission('org:sync'))

watch(
  isCompact,
  (compact) => {
    treeExpanded.value = !compact
  },
  { immediate: true },
)

const stats = reactive<OrgStats>({
  departments: 0,
  employees: 0,
  active_employees: 0,
  inactive_employees: 0,
  pending_onboard: 0,
  contract_expiring_30d: 0,
  today_attendance_ok: 0,
  today_attendance_total: 0,
})
const deptTree = ref<Department[]>([])
const deptTreeRef = ref<InstanceType<typeof ElTree>>()
const employees = ref<Employee[]>([])
const managerOptions = ref<Employee[]>([])
const roles = ref<RoleBrief[]>([])
const empLoading = ref(false)
const syncing = ref(false)
const syncingAttend = ref(false)
const saving = ref(false)
const keyword = ref('')
const selectedDeptId = ref<number | undefined>()
const selectedDeptName = ref('')
const activeFilter = ref<boolean | undefined>(true)
const employmentFilter = ref<string | undefined>()
const statFilter = ref<'active' | 'pending' | 'contract' | 'attendance' | null>(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const deptVisible = ref(false)
const empVisible = ref(false)
const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdTarget = ref<Employee | null>(null)
const pwdForm = reactive({
  password: '',
  confirm: '',
})
const deptForm = reactive({
  id: 0,
  name: '',
  code: '',
  description: '',
  parent_id: undefined as number | undefined,
})
const empForm = reactive({
  id: 0,
  username: '',
  password: '',
  real_name: '',
  phone: '',
  email: '',
  job_title: '',
  employee_no: '',
  employment_status: '' as string,
  hire_date: '' as string,
  contract_end: '' as string,
  archive_status: '' as string,
  feishu_open_id: '' as string,
  department_id: undefined as number | undefined,
  manager_id: undefined as number | undefined,
  role_ids: [] as number[],
})

const attendanceNote = computed(() => {
  const totalAttend = stats.today_attendance_total || 0
  if (!totalAttend) return '尚未同步'
  return '飞书同步'
})

const statCards = computed(() => [
  {
    key: 'active' as const,
    label: '在职员工',
    value: String(stats.active_employees),
    note: `停用 ${stats.inactive_employees}`,
    active: statFilter.value === 'active',
  },
  {
    key: 'pending' as const,
    label: '待入职',
    value: String(stats.pending_onboard || 0),
    note: '待办理入职',
    active: statFilter.value === 'pending',
  },
  {
    key: 'contract' as const,
    label: '合同即将到期',
    value: String(stats.contract_expiring_30d || 0),
    note: '30天内 · 见档案',
    active: false,
  },
  {
    key: 'attendance' as const,
    label: '今日出勤',
    value: `${stats.today_attendance_ok || 0}/${stats.today_attendance_total || 0}`,
    note: attendanceNote.value,
    active: false,
  },
])

function todayTagType(status?: string | null) {
  if (!status) return 'info'
  if (status === '正常') return 'success'
  if (status === '休息日') return 'info'
  if (['请假', '外出'].includes(status)) return 'warning'
  return 'danger'
}

function employmentTagType(status?: string | null, isActive?: boolean) {
  const s = status || (isActive ? '正式' : '离职')
  if (s === '正式') return 'success'
  if (s === '试用') return ''
  if (s === '待入职') return 'info'
  if (s === '离职') return 'danger'
  return 'info'
}

async function loadStats() {
  const { data } = await fetchOrgStats()
  Object.assign(stats, data)
}

async function loadDepts() {
  const { data } = await fetchDepartments()
  deptTree.value = data || []
}

async function loadEmployees() {
  empLoading.value = true
  try {
    const { data } = await fetchEmployees({
      keyword: keyword.value || undefined,
      department_id: selectedDeptId.value,
      is_active: activeFilter.value,
      employment_status: employmentFilter.value,
      page: page.value,
      page_size: pageSize.value,
    })
    employees.value = data.items || []
    total.value = data.total || 0
  } finally {
    empLoading.value = false
  }
}

async function loadManagerOptions() {
  const { data } = await fetchEmployees({ is_active: true, page: 1, page_size: 100 })
  managerOptions.value = data.items || []
}

function reloadEmployees() {
  page.value = 1
  loadEmployees()
}

function goDetail(row: Employee) {
  router.push(`/org/employees/${row.id}`)
}

function onDeptClick(data: Department) {
  selectedDeptId.value = data.id
  selectedDeptName.value = data.name
  if (isCompact.value) treeExpanded.value = false
  reloadEmployees()
}

function onDeptAction(command: string, data: Department) {
  if (command === 'child') openDeptCreate(data.id)
  else if (command === 'edit') openDeptEdit(data)
  else if (command === 'delete') onDeleteDept(data)
}

async function clearDeptFilter() {
  selectedDeptId.value = undefined
  selectedDeptName.value = ''
  await nextTick()
  deptTreeRef.value?.setCurrentKey(undefined as unknown as number)
  reloadEmployees()
}

function onStatClick(key: 'active' | 'pending' | 'contract' | 'attendance') {
  if (key === 'contract') {
    ElMessage.info('合同到期明细请在员工档案中查看')
    return
  }
  if (key === 'attendance') {
    if (!(stats.today_attendance_total || 0)) {
      ElMessage.info('今日出勤尚未同步，请先同步飞书考勤')
    }
    return
  }
  if (statFilter.value === key) {
    statFilter.value = null
    employmentFilter.value = undefined
    activeFilter.value = true
  } else if (key === 'active') {
    statFilter.value = 'active'
    employmentFilter.value = undefined
    activeFilter.value = true
  } else {
    statFilter.value = 'pending'
    employmentFilter.value = '待入职'
    activeFilter.value = undefined
  }
  reloadEmployees()
}

function openDeptCreate(parentId?: number) {
  Object.assign(deptForm, { id: 0, name: '', code: '', description: '', parent_id: parentId })
  deptVisible.value = true
}

function openDeptEdit(data: Department) {
  Object.assign(deptForm, {
    id: data.id,
    name: data.name,
    code: data.code || '',
    description: data.description || '',
    parent_id: data.parent_id || undefined,
  })
  deptVisible.value = true
}

async function saveDept() {
  saving.value = true
  try {
    if (deptForm.id) {
      await updateDepartment(deptForm.id, {
        name: deptForm.name,
        code: deptForm.code || undefined,
        description: deptForm.description,
      })
    } else {
      await createDepartment({
        name: deptForm.name,
        code: deptForm.code || undefined,
        description: deptForm.description,
        parent_id: deptForm.parent_id,
      })
    }
    deptVisible.value = false
    ElMessage.success('已保存')
    await loadDepts()
    await loadStats()
  } finally {
    saving.value = false
  }
}

async function onDeleteDept(data: Department) {
  await ElMessageBox.confirm(`确认删除部门「${data.name}」？`, '删除部门')
  await deleteDepartment(data.id)
  ElMessage.success('已删除')
  if (selectedDeptId.value === data.id) {
    await clearDeptFilter()
  }
  await loadDepts()
  await loadStats()
}

function openEmployeeCreate() {
  Object.assign(empForm, {
    id: 0,
    username: '',
    password: '',
    real_name: '',
    phone: '',
    email: '',
    job_title: '',
    employee_no: '',
    employment_status: '正式',
    hire_date: '',
    contract_end: '',
    archive_status: '完整',
    feishu_open_id: '',
    department_id: selectedDeptId.value,
    manager_id: undefined,
    role_ids: [],
  })
  empVisible.value = true
}

function openEmployeeEdit(row: Employee) {
  Object.assign(empForm, {
    id: row.id,
    username: row.username,
    password: '',
    real_name: row.real_name || '',
    phone: row.phone || '',
    email: row.email || '',
    job_title: row.job_title || '',
    employee_no: row.employee_no || '',
    employment_status: row.employment_status || '',
    hire_date: row.hire_date || '',
    contract_end: row.contract_end || '',
    archive_status: row.archive_status || '',
    feishu_open_id: row.feishu_open_id || '',
    department_id: row.department_id || undefined,
    manager_id: row.manager_id || undefined,
    role_ids: (row.roles || []).map((r) => r.id),
  })
  empVisible.value = true
}

function openPasswordReset(row: Employee) {
  pwdTarget.value = row
  pwdForm.password = ''
  pwdForm.confirm = ''
  pwdVisible.value = true
}

async function submitPasswordReset() {
  if (!pwdTarget.value) return
  const password = pwdForm.password.trim()
  if (password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (password !== pwdForm.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  pwdSaving.value = true
  try {
    await resetEmployeePassword(pwdTarget.value.id, password)
    pwdVisible.value = false
    ElMessage.success('密码已更新')
  } catch (e: any) {
    notifyError(e, '修改密码失败')
  } finally {
    pwdSaving.value = false
  }
}

async function saveEmployee() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      real_name: empForm.real_name || undefined,
      phone: empForm.phone || undefined,
      email: empForm.email || undefined,
      job_title: empForm.job_title || undefined,
      employee_no: empForm.employee_no || undefined,
      employment_status: empForm.employment_status || undefined,
      hire_date: empForm.hire_date || null,
      contract_end: empForm.contract_end || null,
      archive_status: empForm.archive_status || undefined,
      department_id: empForm.department_id ?? null,
      manager_id: empForm.manager_id ?? null,
      role_ids: empForm.role_ids,
    }
    if (empForm.id) {
      payload.feishu_open_id = empForm.feishu_open_id || null
      await updateEmployee(empForm.id, payload)
    } else {
      if (!empForm.username || !empForm.password) {
        ElMessage.warning('请填写用户名和初始密码')
        return
      }
      await createEmployee({
        ...payload,
        username: empForm.username,
        password: empForm.password,
        is_active: true,
      })
    }
    empVisible.value = false
    ElMessage.success('已保存')
    await loadEmployees()
    await loadStats()
    await loadManagerOptions()
  } finally {
    saving.value = false
  }
}

async function onSyncCommand(command: string) {
  if (command === 'contacts') await onSyncFeishu()
  else if (command === 'attendance') await onSyncAttendance()
}

async function onSyncFeishu() {
  await ElMessageBox.confirm(
    '将从飞书拉取部门与员工，按 open_id / 邮箱 / 手机匹配并更新本地组织数据。是否继续？',
    '同步飞书通讯录',
  )
  syncing.value = true
  try {
    const { data } = await syncFeishuContactsApi()
    const warn = data.warnings?.length ? `\n提示：${data.warnings.slice(0, 2).join('；')}` : ''
    ElMessage.success(
      `同步完成：新建员工 ${data.employees_created}，更新 ${data.employees_updated}，绑定 ${data.employees_bound}${warn}`,
    )
    await Promise.all([loadDepts(), loadEmployees(), loadStats(), loadManagerOptions()])
  } catch (e: any) {
    notifyError(e, '同步失败')
  } finally {
    syncing.value = false
  }
}

async function onSyncAttendance() {
  syncingAttend.value = true
  try {
    const { data } = await syncFeishuAttendanceApi()
    ElMessage.success(`考勤同步：${data.users_synced} 人，写入 ${data.days_upserted} 条日事实`)
    if (data.warnings?.length) {
      ElMessage.warning(data.warnings.slice(0, 2).join('；'))
    }
    await Promise.all([loadEmployees(), loadStats()])
  } catch (e: any) {
    notifyError(e, '考勤同步失败')
  } finally {
    syncingAttend.value = false
  }
}

onMounted(async () => {
  const { data: roleData } = await fetchOrgRoles()
  roles.value = roleData || []
  await Promise.all([loadStats(), loadDepts(), loadEmployees(), loadManagerOptions()])
})
</script>

<style scoped>
.org-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  gap: 14px;
}
.page-head {
  margin-bottom: 0;
  flex-shrink: 0;
}
.sync-caret {
  margin-left: 4px;
  font-size: 11px;
}
.org-page :deep(.crm-stats) {
  flex-shrink: 0;
  margin-bottom: 12px;
  gap: 10px;
}
.org-page :deep(.crm-stat-tile) {
  padding: 12px 14px;
}
.org-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 300px) 1fr;
  gap: 12px;
  align-items: stretch;
}
.org-tree-panel,
.org-list-panel {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.org-tree-panel :deep(.el-card__header) {
  flex-shrink: 0;
  padding: 10px 14px;
}
.org-tree-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px 10px 12px;
}
.org-list-panel :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px 14px;
}
.org-tree-panel :deep(.el-tree-node__content) {
  height: auto;
  min-height: 32px;
  align-items: flex-start;
  padding: 4px 4px 4px 0;
}
.org-tree-panel :deep(.el-tree-node__expand-icon) {
  margin-top: 4px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
  flex-shrink: 0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.card-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.tree-toggle {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.tree-toggle small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.tree-caret {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transition: transform 0.15s ease;
}
.tree-caret.is-open {
  transform: rotate(180deg);
}
.tree-node {
  display: flex;
  align-items: flex-start;
  width: 100%;
  gap: 4px;
  padding-right: 2px;
  line-height: 1.4;
}
.tree-label {
  flex: 1;
  min-width: 0;
  white-space: normal;
  word-break: break-all;
  font-size: 13px;
  color: var(--el-text-color-primary);
}
.tree-more {
  flex-shrink: 0;
  padding: 0 4px;
  height: 22px;
  margin-top: 1px;
  font-size: 16px;
  line-height: 1;
  color: var(--el-text-color-secondary);
}
.emp-cell {
  display: flex;
  gap: 10px;
  align-items: center;
}
.emp-cell .avatar,
.emp-card .avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e8eef8;
  color: #2f5bb8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}
.emp-cell .avatar {
  width: 28px;
  height: 28px;
  font-size: 12px;
}
.emp-cell small {
  display: block;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.emp-card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
}
.emp-card {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.emp-card:active {
  background: var(--el-fill-color-light);
}
.emp-card-main {
  flex: 1;
  min-width: 0;
}
.emp-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.emp-card-title b {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.emp-card-meta {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.emp-card-actions {
  flex-shrink: 0;
}
.emp-card-empty {
  padding: 28px 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.crm-stat-tile small {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: 400;
}
.crm-stat-tile.is-active {
  border-color: var(--el-color-primary);
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
}
@media (max-width: 960px) {
  .org-page.crm-fit-page {
    height: auto !important;
    max-height: none !important;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .org-layout {
    grid-template-columns: 1fr;
    flex: none;
    height: auto;
    min-height: 0;
    overflow: visible;
  }

  .org-tree-panel,
  .org-list-panel {
    height: auto;
    overflow: visible;
  }

  .org-tree-panel {
    max-height: 280px;
    overflow: hidden;
  }

  .org-tree-panel :deep(.el-card__body) {
    overflow: auto;
  }

  .org-list-panel :deep(.el-card__body) {
    overflow: visible;
  }

  .table-wrap {
    min-height: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
}

@media (max-width: 768px) {
  /* 解除一屏锁定：页面随内容增高，由自身纵向滚动 */
  .org-page.crm-fit-page {
    height: auto !important;
    max-height: none !important;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
    gap: 10px;
  }

  .org-page .page-head {
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
  }

  .org-page .page-head > div:first-child > p:not(.wb-eyebrow) {
    display: none;
  }

  .org-page .page-head h1 {
    font-size: 20px;
  }

  .org-page .head-actions {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .org-page .head-actions .el-button,
  .org-page .head-actions .el-dropdown {
    width: 100%;
    margin: 0;
  }

  .org-page .head-actions .el-dropdown .el-button {
    width: 100%;
  }

  .org-page .head-actions > .el-button--primary {
    grid-column: 1 / -1;
  }

  .org-page :deep(.crm-stats) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 0;
  }

  .org-page :deep(.crm-stat-tile) {
    padding: 10px 12px;
  }

  .org-page :deep(.crm-stat-tile strong) {
    font-size: 18px;
  }

  .org-page :deep(.crm-stat-tile small) {
    font-size: 11px;
    line-height: 1.3;
  }

  .org-layout {
    flex: none;
    height: auto;
    min-height: 0;
    overflow: visible;
    gap: 8px;
  }

  .org-tree-panel,
  .org-list-panel {
    height: auto;
    max-height: none;
    overflow: visible;
  }

  .org-tree-panel.is-collapsed :deep(.el-card__header) {
    padding: 10px 12px;
  }

  .org-tree-panel.is-collapsed :deep(.el-card__body) {
    display: none;
    padding: 0;
  }

  .org-tree-panel:not(.is-collapsed) {
    max-height: 240px;
    overflow: hidden;
  }

  .org-tree-panel:not(.is-collapsed) :deep(.el-card__body) {
    overflow: auto;
  }

  .org-list-panel :deep(.el-card__body) {
    overflow: visible;
    padding: 10px 12px;
  }

  .toolbar {
    margin-bottom: 8px;
  }

  .filters {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .filters > .el-input {
    grid-column: 1 / -1;
    width: 100% !important;
    min-width: 0;
  }

  .filters > .el-select {
    width: 100% !important;
    min-width: 0;
  }

  .filters > .el-button {
    grid-column: 1 / -1;
  }

  .pager {
    justify-content: center;
    margin-top: 8px;
  }

  .pager :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
    row-gap: 8px;
  }
}
</style>
