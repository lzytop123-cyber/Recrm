<template>
  <div class="crm-page system-page crm-fit-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>系统设置</h1>
        <p>角色权限、账号绑定与经营台基础配置。</p>
      </div>
    </header>

    <div class="crm-stats" :style="{ '--crm-stats-cols': String(statCards.length) }">
      <button
        v-for="item in statCards"
        :key="item.label"
        type="button"
        class="crm-stat-tile is-static"
        disabled
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </div>

    <el-card class="system-main-card" shadow="never">
      <el-tabs v-model="tab" class="system-tabs">
        <el-tab-pane label="角色权限" name="roles">
          <div class="tab-pane-body">
            <div class="toolbar">
              <span class="hint">admin 角色受保护，不可改权限/删除</span>
              <el-button v-if="canManageSystem" type="primary" @click="openRoleCreate">新建角色</el-button>
            </div>
            <div class="crm-table-wrap">
              <el-table :data="roles" stripe height="100%">
                <el-table-column prop="name" label="角色" width="120" />
                <el-table-column prop="code" label="编码" width="130" />
                <el-table-column label="数据范围" width="120">
                  <template #default="{ row }">
                    {{ DATA_SCOPE_LABEL[row.data_scope] || row.data_scope }}
                    <span
                      v-if="row.module_scopes && Object.keys(row.module_scopes).length"
                      class="hint"
                    >
                      +{{ Object.keys(row.module_scopes).length }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="权限数" width="80">
                  <template #default="{ row }">{{ row.permission_ids?.length || 0 }}</template>
                </el-table-column>
                <el-table-column prop="user_count" label="用户数" width="80" />
                <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
                <el-table-column label="操作" width="140" fixed="right">
                  <template #default="{ row }">
                    <template v-if="canManageSystem">
                      <el-button link type="primary" @click="openRoleEdit(row)">编辑</el-button>
                      <el-button
                        v-if="row.code !== 'admin'"
                        link
                        type="danger"
                        @click="onDeleteRole(row)"
                      >
                        删除
                      </el-button>
                    </template>
                    <span v-else class="hint">只读</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="权限目录" name="permissions">
          <div class="tab-pane-body">
            <div class="crm-table-wrap">
              <el-table :data="permissions" stripe height="100%">
                <el-table-column prop="module" label="模块" width="120" />
                <el-table-column prop="name" label="名称" width="160" />
                <el-table-column prop="code" label="编码" width="180" />
                <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="审计日志" name="audits">
          <div class="tab-pane-body">
            <div class="toolbar">
              <div class="filters">
                <el-input
                  v-model="auditKeyword"
                  clearable
                  placeholder="用户名/详情"
                  style="width: 180px"
                  @keyup.enter="reloadAudits"
                />
                <el-input
                  v-model="auditModule"
                  clearable
                  placeholder="模块"
                  style="width: 120px"
                  @keyup.enter="reloadAudits"
                />
                <el-button type="primary" @click="reloadAudits">查询</el-button>
              </div>
            </div>
            <div class="crm-table-wrap">
              <el-table :data="audits" v-loading="auditLoading" stripe height="100%">
                <el-table-column prop="created_at" label="时间" width="170">
                  <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
                </el-table-column>
                <el-table-column prop="username" label="用户" width="100" />
                <el-table-column prop="module" label="模块" width="100" />
                <el-table-column prop="action" label="动作" width="100" />
                <el-table-column prop="ip" label="IP" width="120" />
                <el-table-column prop="detail" label="详情" min-width="180" show-overflow-tooltip />
              </el-table>
            </div>
            <div class="pager">
              <el-pagination
                v-model:current-page="auditPage"
                v-model:page-size="auditPageSize"
                :total="auditTotal"
                layout="total, prev, pager, next"
                @current-change="loadAudits"
                @size-change="loadAudits"
              />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="业务类型" name="businessTypes">
          <div class="tab-pane-body">
            <div class="toolbar">
              <span class="hint">
                项目类型 / 合同类型 / 线索需求方向共用此字典。编码 other 请保留。
              </span>
              <div v-if="canManageSystem" class="filters">
                <el-button @click="addBusinessTypeRow">新增类型</el-button>
                <el-button type="primary" :loading="dictSaving" @click="saveBusinessTypes">
                  保存
                </el-button>
              </div>
            </div>
            <div class="crm-table-wrap">
              <el-table :data="businessTypeRows" v-loading="dictLoading" stripe height="100%">
                <el-table-column label="编码" width="160">
                  <template #default="{ row }">
                    <el-input
                      v-model="row.value"
                      :disabled="row._locked || !canManageSystem"
                      placeholder="如 ai_product"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="名称" min-width="160">
                  <template #default="{ row }">
                    <el-input
                      v-model="row.label"
                      :disabled="!canManageSystem"
                      placeholder="显示名称"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="排序" width="110">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.sort"
                      :min="0"
                      :max="9999"
                      :disabled="!canManageSystem"
                      controls-position="right"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="90" align="center">
                  <template #default="{ row }">
                    <el-switch
                      v-model="row.enabled"
                      :disabled="row.value === 'other' || !canManageSystem"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="90" fixed="right">
                  <template #default="{ row, $index }">
                    <el-button
                      v-if="canManageSystem"
                      link
                      type="danger"
                      :disabled="row.value === 'other'"
                      @click="removeBusinessTypeRow($index)"
                    >
                      删除
                    </el-button>
                    <span v-else class="hint">—</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog
      v-model="roleVisible"
      :title="roleForm.id ? '编辑角色' : '新建角色'"
      width="800px"
      class="role-dialog"
      destroy-on-close
    >
      <el-form label-width="100px" class="role-form">
        <el-form-item label="名称">
          <el-input
            v-model="roleForm.name"
            :disabled="roleForm.code === 'admin'"
            @input="onRoleNameInput"
          />
        </el-form-item>
        <el-form-item v-if="!roleForm.id" label="编码">
          <el-input
            v-model="roleForm.code"
            placeholder="根据名称自动生成，可改"
            @input="onRoleCodeInput"
          />
          <div class="field-hint">保存后不可修改；英文名会转成小写蛇形，中文名生成 role_ 前缀编码</div>
        </el-form-item>
        <el-form-item label="默认范围">
          <el-select
            v-model="roleForm.data_scope"
            style="width: 100%"
            :disabled="roleForm.code === 'admin'"
          >
            <el-option
              v-for="(label, key) in DATA_SCOPE_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <div class="field-hint">未单独设置的模块使用此默认范围</div>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="按模块授权">
          <div class="perm-modules" :class="{ 'is-disabled': roleForm.code === 'admin' }">
            <div v-for="group in permissionModuleCards" :key="group.module" class="perm-card">
              <div class="perm-card-head">
                <div class="perm-card-title">
                  <strong>{{ group.label }}</strong>
                  <span class="perm-card-code">{{ group.module }}</span>
                </div>
                <div class="perm-card-actions">
                  <el-select
                    :model-value="moduleScopeValue(group.module)"
                    size="small"
                    style="width: 120px"
                    :disabled="roleForm.code === 'admin'"
                    @update:model-value="(v: string) => setModuleScope(group.module, v)"
                  >
                    <el-option label="跟随默认" value="__default__" />
                    <el-option
                      v-for="(label, key) in DATA_SCOPE_LABEL"
                      :key="key"
                      :label="label"
                      :value="key"
                    />
                  </el-select>
                  <el-checkbox
                    :model-value="isModuleFullyChecked(group)"
                    :indeterminate="isModulePartial(group)"
                    :disabled="roleForm.code === 'admin'"
                    @change="(checked: boolean | string | number) => toggleModule(group, !!checked)"
                  >
                    全选
                  </el-checkbox>
                </div>
              </div>
              <el-checkbox-group
                v-model="roleForm.permission_ids"
                :disabled="roleForm.code === 'admin'"
                class="perm-card-body"
              >
                <el-checkbox v-for="p in group.items" :key="p.id" :value="p.id" class="perm-item">
                  <span class="perm-name">{{ p.name }}</span>
                  <span class="perm-code">{{ p.code }}</span>
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DATA_SCOPE_LABEL,
  MODULE_LABEL,
  MODULE_ORDER,
  createSystemRole,
  deleteSystemRole,
  fetchAuditLogs,
  fetchPermissions,
  fetchSystemRoles,
  fetchSystemStats,
  updateSystemRole,
  type AuditLog,
  type PermissionItem,
  type SystemRole,
  type SystemStats,
} from '@/api/system'
import {
  BUSINESS_TYPE_DICT_CODE,
  DEFAULT_BUSINESS_TYPE_OPTIONS,
  fetchDictionary,
  invalidateBusinessTypeCache,
  updateDictionary,
  type DictionaryItem,
} from '@/api/dictionaries'
import { useUserStore } from '@/stores/user'

type BusinessTypeRow = DictionaryItem & { _locked?: boolean }

const userStore = useUserStore()
const canManageSystem = computed(
  () => userStore.hasPermission('system:manage') || userStore.hasPermission('*'),
)

const loading = ref(false)
const saving = ref(false)
const tab = ref('roles')
const stats = ref<SystemStats | null>(null)
const roles = ref<SystemRole[]>([])
const permissions = ref<PermissionItem[]>([])

const audits = ref<AuditLog[]>([])
const auditLoading = ref(false)
const auditKeyword = ref('')
const auditModule = ref('')
const auditPage = ref(1)
const auditPageSize = ref(20)
const auditTotal = ref(0)

const dictLoading = ref(false)
const dictSaving = ref(false)
const businessTypeRows = ref<BusinessTypeRow[]>([])
const businessTypeDictName = ref('业务类型')

const roleVisible = ref(false)
const roleCodeManual = ref(false)
const roleForm = reactive({
  id: 0,
  name: '',
  code: '',
  description: '',
  data_scope: 'personal',
  module_scopes: {} as Record<string, string>,
  permission_ids: [] as number[],
})

type PermModuleCard = {
  module: string
  label: string
  items: PermissionItem[]
}

/** 由名称生成角色编码：优先 ASCII 蛇形；纯中文则 role_ + 稳定短码 */
function nameToRoleCode(name: string): string {
  const raw = name.trim()
  if (!raw) return ''
  const ascii = raw
    .toLowerCase()
    .replace(/[\s\-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
  if (ascii.length >= 2) return ascii.slice(0, 50)
  let h = 0
  for (let i = 0; i < raw.length; i++) {
    h = (Math.imul(h, 31) + raw.charCodeAt(i)) >>> 0
  }
  return `role_${h.toString(36)}`.slice(0, 50)
}

function onRoleNameInput() {
  if (roleForm.id || roleCodeManual.value) return
  roleForm.code = nameToRoleCode(roleForm.name)
}

function onRoleCodeInput() {
  roleCodeManual.value = true
}

const statCards = computed(() => [
  { label: '角色', value: stats.value?.roles ?? 0 },
  { label: '权限', value: stats.value?.permissions ?? 0 },
  { label: '用户', value: stats.value?.users ?? 0 },
  { label: '审计日志', value: stats.value?.audit_logs ?? 0 },
])

const permissionModuleCards = computed((): PermModuleCard[] => {
  const map: Record<string, PermissionItem[]> = {}
  for (const p of permissions.value) {
    const key = p.module || 'other'
    if (!map[key]) map[key] = []
    map[key].push(p)
  }
  const keys = Object.keys(map)
  keys.sort((a, b) => {
    const ia = MODULE_ORDER.indexOf(a)
    const ib = MODULE_ORDER.indexOf(b)
    const sa = ia === -1 ? 999 : ia
    const sb = ib === -1 ? 999 : ib
    if (sa !== sb) return sa - sb
    return a.localeCompare(b)
  })
  return keys.map((module) => ({
    module,
    label: MODULE_LABEL[module] || module,
    items: map[module],
  }))
})

function moduleScopeValue(module: string) {
  return roleForm.module_scopes[module] || '__default__'
}

function setModuleScope(module: string, value: string) {
  if (value === '__default__') {
    const next = { ...roleForm.module_scopes }
    delete next[module]
    roleForm.module_scopes = next
    return
  }
  roleForm.module_scopes = { ...roleForm.module_scopes, [module]: value }
}

function isModuleFullyChecked(group: PermModuleCard) {
  return group.items.every((p) => roleForm.permission_ids.includes(p.id))
}

function isModulePartial(group: PermModuleCard) {
  const n = group.items.filter((p) => roleForm.permission_ids.includes(p.id)).length
  return n > 0 && n < group.items.length
}

function toggleModule(group: PermModuleCard, checked: boolean) {
  const ids = new Set(roleForm.permission_ids)
  if (checked) {
    for (const p of group.items) ids.add(p.id)
  } else {
    for (const p of group.items) ids.delete(p.id)
  }
  roleForm.permission_ids = [...ids]
}
function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

async function loadStats() {
  const { data } = await fetchSystemStats()
  stats.value = data
}

async function loadRoles() {
  const { data } = await fetchSystemRoles()
  roles.value = data
}

async function loadPermissions() {
  const { data } = await fetchPermissions()
  permissions.value = data
}

async function loadAudits() {
  auditLoading.value = true
  try {
    const { data } = await fetchAuditLogs({
      keyword: auditKeyword.value || undefined,
      module: auditModule.value || undefined,
      page: auditPage.value,
      page_size: auditPageSize.value,
    })
    audits.value = data.items
    auditTotal.value = data.total
  } finally {
    auditLoading.value = false
  }
}

function reloadAudits() {
  auditPage.value = 1
  loadAudits()
}

async function loadBusinessTypes() {
  dictLoading.value = true
  try {
    const { data } = await fetchDictionary(BUSINESS_TYPE_DICT_CODE)
    businessTypeDictName.value = data.name || '业务类型'
    const items =
      data.items?.length
        ? data.items
        : DEFAULT_BUSINESS_TYPE_OPTIONS
    businessTypeRows.value = items.map((x) => ({
      value: x.value,
      label: x.label,
      enabled: x.enabled !== false,
      sort: x.sort ?? 100,
      _locked: true,
    }))
  } catch {
    businessTypeRows.value = DEFAULT_BUSINESS_TYPE_OPTIONS.map((x) => ({
      ...x,
      enabled: true,
      _locked: true,
    }))
  } finally {
    dictLoading.value = false
  }
}

function addBusinessTypeRow() {
  businessTypeRows.value.push({
    value: '',
    label: '',
    enabled: true,
    sort: (businessTypeRows.value.length + 1) * 10,
    _locked: false,
  })
}

function removeBusinessTypeRow(index: number) {
  const row = businessTypeRows.value[index]
  if (row?.value === 'other') {
    ElMessage.warning('「其他」类型不可删除')
    return
  }
  businessTypeRows.value.splice(index, 1)
}

async function saveBusinessTypes() {
  const rows = businessTypeRows.value
  if (!rows.length) {
    ElMessage.warning('至少保留一个业务类型')
    return
  }
  for (const row of rows) {
    if (!row.value.trim() || !row.label.trim()) {
      ElMessage.warning('请完整填写编码和名称')
      return
    }
  }
  dictSaving.value = true
  try {
    await updateDictionary(BUSINESS_TYPE_DICT_CODE, {
      name: businessTypeDictName.value,
      items_json: JSON.stringify(
        rows.map((r) => ({
          value: r.value.trim(),
          label: r.label.trim(),
          enabled: r.enabled !== false,
          sort: Number(r.sort) || 0,
        })),
      ),
    })
    invalidateBusinessTypeCache()
    ElMessage.success('业务类型已保存')
    await loadBusinessTypes()
  } catch {
    /* interceptor */
  } finally {
    dictSaving.value = false
  }
}

function openRoleCreate() {
  roleForm.id = 0
  roleForm.name = ''
  roleForm.code = ''
  roleForm.description = ''
  roleForm.data_scope = 'personal'
  roleForm.module_scopes = {}
  roleForm.permission_ids = []
  roleCodeManual.value = false
  roleVisible.value = true
}

function openRoleEdit(row: SystemRole) {
  roleForm.id = row.id
  roleForm.name = row.name
  roleForm.code = row.code
  roleForm.description = row.description || ''
  roleForm.data_scope = row.data_scope
  roleForm.module_scopes = { ...(row.module_scopes || {}) }
  roleForm.permission_ids = [...(row.permission_ids || [])]
  roleVisible.value = true
}

async function saveRole() {
  if (!roleForm.name.trim()) {
    ElMessage.warning('请填写角色名称')
    return
  }
  if (!roleForm.id && !roleForm.code.trim()) {
    roleForm.code = nameToRoleCode(roleForm.name)
  }
  if (!roleForm.id && !roleForm.code.trim()) {
    ElMessage.warning('请填写角色编码')
    return
  }
  saving.value = true
  try {
    if (roleForm.id) {
      await updateSystemRole(roleForm.id, {
        name: roleForm.code === 'admin' ? undefined : roleForm.name,
        description: roleForm.description || undefined,
        data_scope: roleForm.code === 'admin' ? undefined : roleForm.data_scope,
        module_scopes: roleForm.code === 'admin' ? undefined : { ...roleForm.module_scopes },
        permission_ids: roleForm.code === 'admin' ? undefined : roleForm.permission_ids,
      })
    } else {
      await createSystemRole({
        name: roleForm.name,
        code: roleForm.code,
        description: roleForm.description || undefined,
        data_scope: roleForm.data_scope,
        module_scopes: { ...roleForm.module_scopes },
        permission_ids: roleForm.permission_ids,
      })
    }
    ElMessage.success('已保存')
    roleVisible.value = false
    await Promise.all([loadRoles(), loadStats()])
  } finally {
    saving.value = false
  }
}

async function onDeleteRole(row: SystemRole) {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '删除')
    await deleteSystemRole(row.id)
    ElMessage.success('已删除')
    await Promise.all([loadRoles(), loadStats()])
  } catch {
    /* cancel */
  }
}

watch(tab, (v) => {
  if (v === 'audits' && !audits.value.length) loadAudits()
  if (v === 'businessTypes' && !businessTypeRows.value.length) loadBusinessTypes()
})

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadStats(), loadRoles(), loadPermissions()])
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.system-page {
  gap: 14px;
}

.system-page .page-head {
  margin-bottom: 0;
  flex-shrink: 0;
}

.system-page :deep(.crm-stats) {
  flex-shrink: 0;
  margin-bottom: 0;
}

.system-main-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.system-main-card :deep(.el-card__body) {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px 16px 14px;
}

.system-tabs {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.system-tabs :deep(.el-tabs__header) {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.system-tabs :deep(.el-tabs__content) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.system-tabs :deep(.el-tab-pane) {
  height: 100%;
  flex: 1 1 auto;
  min-height: 0;
}

.tab-pane-body {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.hint {
  color: var(--crm-ink-soft, #909399);
  font-size: 13px;
  line-height: 1.4;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.crm-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
  flex-shrink: 0;
}

.perm-modules {
  width: 100%;
  max-height: 420px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}

.perm-modules.is-disabled {
  opacity: 0.72;
}

.perm-card {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
  background: var(--el-fill-color-blank, #fff);
  padding: 10px 12px;
}

.perm-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.perm-card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.perm-card-title strong {
  font-size: 14px;
}

.perm-card-code {
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
}

.perm-card-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.perm-card-body {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}

.perm-item {
  margin-right: 0 !important;
  height: auto;
  min-height: 28px;
  align-items: flex-start;
}

.perm-name {
  display: inline-block;
  line-height: 1.3;
}

.perm-code {
  display: block;
  color: var(--crm-ink-soft, #909399);
  font-size: 11px;
  line-height: 1.2;
  margin-top: 1px;
}

.field-hint {
  margin-top: 4px;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
  line-height: 1.4;
}

.role-form :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}
</style>

