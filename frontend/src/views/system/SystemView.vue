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
              <el-button type="primary" @click="openRoleCreate">新建角色</el-button>
            </div>
            <div class="crm-table-wrap">
              <el-table :data="roles" stripe height="100%">
                <el-table-column prop="name" label="角色" width="120" />
                <el-table-column prop="code" label="编码" width="130" />
                <el-table-column label="数据范围" width="100">
                  <template #default="{ row }">
                    {{ DATA_SCOPE_LABEL[row.data_scope] || row.data_scope }}
                  </template>
                </el-table-column>
                <el-table-column label="权限数" width="80">
                  <template #default="{ row }">{{ row.permission_ids?.length || 0 }}</template>
                </el-table-column>
                <el-table-column prop="user_count" label="用户数" width="80" />
                <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
                <el-table-column label="操作" width="140" fixed="right">
                  <template #default="{ row }">
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
              <div class="filters">
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
                      :disabled="row._locked"
                      placeholder="如 ai_product"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="名称" min-width="160">
                  <template #default="{ row }">
                    <el-input v-model="row.label" placeholder="显示名称" />
                  </template>
                </el-table-column>
                <el-table-column label="排序" width="110">
                  <template #default="{ row }">
                    <el-input-number v-model="row.sort" :min="0" :max="9999" controls-position="right" />
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="90" align="center">
                  <template #default="{ row }">
                    <el-switch v-model="row.enabled" :disabled="row.value === 'other'" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="90" fixed="right">
                  <template #default="{ row, $index }">
                    <el-button
                      link
                      type="danger"
                      :disabled="row.value === 'other'"
                      @click="removeBusinessTypeRow($index)"
                    >
                      删除
                    </el-button>
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
      width="640px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="roleForm.name" :disabled="roleForm.code === 'admin'" />
        </el-form-item>
        <el-form-item v-if="!roleForm.id" label="编码">
          <el-input v-model="roleForm.code" />
        </el-form-item>
        <el-form-item label="数据范围">
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
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="权限">
          <el-checkbox-group v-model="roleForm.permission_ids" :disabled="roleForm.code === 'admin'">
            <div v-for="(list, module) in permissionGroups" :key="module" class="perm-group">
              <div class="perm-module">{{ module || '其他' }}</div>
              <el-checkbox v-for="p in list" :key="p.id" :value="p.id">
                {{ p.name }} ({{ p.code }})
              </el-checkbox>
            </div>
          </el-checkbox-group>
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

type BusinessTypeRow = DictionaryItem & { _locked?: boolean }

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
const roleForm = reactive({
  id: 0,
  name: '',
  code: '',
  description: '',
  data_scope: 'personal',
  permission_ids: [] as number[],
})

const statCards = computed(() => [
  { label: '角色', value: stats.value?.roles ?? 0 },
  { label: '权限', value: stats.value?.permissions ?? 0 },
  { label: '用户', value: stats.value?.users ?? 0 },
  { label: '审计日志', value: stats.value?.audit_logs ?? 0 },
])

const permissionGroups = computed(() => {
  const map: Record<string, PermissionItem[]> = {}
  for (const p of permissions.value) {
    const key = p.module || 'other'
    if (!map[key]) map[key] = []
    map[key].push(p)
  }
  return map
})

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
  roleForm.permission_ids = []
  roleVisible.value = true
}

function openRoleEdit(row: SystemRole) {
  roleForm.id = row.id
  roleForm.name = row.name
  roleForm.code = row.code
  roleForm.description = row.description || ''
  roleForm.data_scope = row.data_scope
  roleForm.permission_ids = [...(row.permission_ids || [])]
  roleVisible.value = true
}

async function saveRole() {
  if (!roleForm.name.trim()) {
    ElMessage.warning('请填写角色名称')
    return
  }
  saving.value = true
  try {
    if (roleForm.id) {
      await updateSystemRole(roleForm.id, {
        name: roleForm.code === 'admin' ? undefined : roleForm.name,
        description: roleForm.description || undefined,
        data_scope: roleForm.code === 'admin' ? undefined : roleForm.data_scope,
        permission_ids: roleForm.code === 'admin' ? undefined : roleForm.permission_ids,
      })
    } else {
      if (!roleForm.code.trim()) {
        ElMessage.warning('请填写角色编码')
        return
      }
      await createSystemRole({
        name: roleForm.name,
        code: roleForm.code,
        description: roleForm.description || undefined,
        data_scope: roleForm.data_scope,
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

.perm-group {
  margin-bottom: 10px;
  width: 100%;
}
.perm-module {
  font-weight: 600;
  margin-bottom: 4px;
}
</style>

