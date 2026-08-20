<template>
  <div class="crm-page dict-page crm-fit-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>字典管理</h1>
        <p>维护线索来源、业务类型等基础数据字典。停用后下拉不再可选，历史值保留。</p>
      </div>
    </header>

    <el-card class="dict-main-card" shadow="never">
      <div class="dict-layout">
        <aside class="dict-sidebar">
          <div class="dict-sidebar-head">字典列表</div>
          <ul class="dict-list">
            <li
              v-for="d in dictionaries"
              :key="d.code"
              :class="['dict-list-item', { active: d.code === activeCode }]"
              @click="selectDict(d.code)"
            >
              <span class="dict-name">{{ d.name }}</span>
              <small class="dict-code">{{ d.code }}</small>
              <el-tag size="small" effect="plain">{{ d.items?.length ?? 0 }} 项</el-tag>
            </li>
          </ul>
        </aside>

        <section class="dict-editor">
          <template v-if="activeDict">
            <div class="editor-toolbar">
              <div class="editor-title">
                <h2>{{ activeDict.name }}</h2>
                <small>{{ dictHint }}</small>
              </div>
              <div v-if="canManage" class="editor-actions">
                <el-button @click="addRow">新增项</el-button>
                <el-button type="primary" :loading="saving" @click="save">保存</el-button>
              </div>
            </div>
            <div class="crm-table-wrap">
              <el-table :data="rows" v-loading="rowsLoading" stripe height="100%">
                <el-table-column label="编码" width="170">
                  <template #default="{ row }">
                    <el-input
                      v-model="row.value"
                      :disabled="row._locked || !canManage"
                      placeholder="如 website"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="名称" min-width="180">
                  <template #default="{ row }">
                    <el-input
                      v-model="row.label"
                      :disabled="!canManage"
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
                      :disabled="!canManage"
                      controls-position="right"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="90" align="center">
                  <template #default="{ row }">
                    <el-switch
                      v-model="row.enabled"
                      :disabled="row.value === lockedValue || !canManage"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="90" fixed="right">
                  <template #default="{ $index }">
                    <el-button
                      v-if="canManage"
                      link
                      type="danger"
                      :disabled="rows[$index]?.value === lockedValue"
                      @click="removeRow($index)"
                    >
                      删除
                    </el-button>
                    <span v-else class="hint">—</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
          <el-empty v-else description="请选择左侧字典" :image-size="80" />
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  BUSINESS_TYPE_DICT_CODE,
  DEFAULT_BUSINESS_TYPE_OPTIONS,
  DEFAULT_LEAD_SOURCE_OPTIONS,
  LEAD_SOURCE_DICT_CODE,
  fetchDictionaries,
  fetchDictionary,
  invalidateBusinessTypeCache,
  invalidateLeadSourceCache,
  updateDictionary,
  type DictionaryItem,
  type SystemDictionary,
} from '@/api/dictionaries'
import { useUserStore } from '@/stores/user'

type DictRow = DictionaryItem & { _locked?: boolean }

const userStore = useUserStore()
const canManage = computed(
  () => userStore.hasPermission('system:manage') || userStore.hasPermission('*'),
)

const loading = ref(false)
const rowsLoading = ref(false)
const saving = ref(false)
const dictionaries = ref<SystemDictionary[]>([])
const activeCode = ref<string>('')
const activeDict = ref<SystemDictionary | null>(null)
const rows = ref<DictRow[]>([])

/** 需要保留的兜底编码与提示，按字典编码配置 */
const dictMeta = computed(() => {
  if (activeCode.value === BUSINESS_TYPE_DICT_CODE)
    return { locked: 'other', hint: '项目类型 / 合同类型 / 线索需求方向共用此字典。编码 other 请保留。' }
  if (activeCode.value === LEAD_SOURCE_DICT_CODE)
    return { locked: '', hint: '线索录入 / 批量导入的「录入来源」下拉共用此字典。停用后不再可选，历史值保留。' }
  return { locked: '', hint: '编辑后保存生效。' }
})
const lockedValue = computed(() => dictMeta.value.locked)
const dictHint = computed(() => dictMeta.value.hint)

async function loadDictionaries() {
  loading.value = true
  try {
    const { data } = await fetchDictionaries()
    dictionaries.value = data
    if (!activeCode.value && data.length) {
      await selectDict(data[0].code)
    }
  } finally {
    loading.value = false
  }
}

async function selectDict(code: string) {
  activeCode.value = code
  rowsLoading.value = true
  try {
    const { data } = await fetchDictionary(code)
    activeDict.value = data
    const fallback =
      code === BUSINESS_TYPE_DICT_CODE
        ? DEFAULT_BUSINESS_TYPE_OPTIONS
        : code === LEAD_SOURCE_DICT_CODE
          ? DEFAULT_LEAD_SOURCE_OPTIONS
          : []
    const items = data.items?.length ? data.items : fallback
    rows.value = items.map((x) => ({
      value: x.value,
      label: x.label,
      enabled: x.enabled !== false,
      sort: x.sort ?? 100,
      _locked: true,
    }))
  } catch {
    activeDict.value = null
    rows.value = []
  } finally {
    rowsLoading.value = false
  }
}

function addRow() {
  rows.value.push({
    value: '',
    label: '',
    enabled: true,
    sort: (rows.value.length + 1) * 10,
    _locked: false,
  })
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
}

async function save() {
  const list = rows.value
  if (!list.length) {
    ElMessage.warning('至少保留一项')
    return
  }
  for (const row of list) {
    if (!row.value.trim() || !row.label.trim()) {
      ElMessage.warning('请完整填写编码和名称')
      return
    }
  }
  saving.value = true
  try {
    await updateDictionary(activeCode.value, {
      name: activeDict.value?.name,
      items_json: JSON.stringify(
        list.map((r) => ({
          value: r.value.trim(),
          label: r.label.trim(),
          enabled: r.enabled !== false,
          sort: Number(r.sort) || 0,
        })),
      ),
    })
    if (activeCode.value === BUSINESS_TYPE_DICT_CODE) invalidateBusinessTypeCache()
    if (activeCode.value === LEAD_SOURCE_DICT_CODE) invalidateLeadSourceCache()
    ElMessage.success('字典已保存')
    await selectDict(activeCode.value)
    await loadDictionaries()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

onMounted(loadDictionaries)
</script>

<style scoped>
.dict-page {
  gap: 14px;
}
.dict-page .page-head {
  margin-bottom: 0;
  flex-shrink: 0;
}
.dict-main-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}
.dict-main-card :deep(.el-card__body) {
  flex: 1 1 auto;
  min-height: 0;
  padding: 0;
}
.dict-layout {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
}
.dict-sidebar {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--crm-border, #e4e7ed);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dict-sidebar-head {
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink-soft, #606266);
  border-bottom: 1px solid var(--crm-border, #e4e7ed);
}
.dict-list {
  list-style: none;
  margin: 0;
  padding: 8px;
  overflow-y: auto;
  flex: 1 1 auto;
}
.dict-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.dict-list-item:hover {
  background: var(--crm-surface-soft, #f5f7fa);
}
.dict-list-item.active {
  background: var(--crm-primary-soft, #ecf5ff);
}
.dict-list-item.active .dict-name {
  color: var(--crm-primary, #409eff);
  font-weight: 600;
}
.dict-name {
  flex: 1 1 auto;
  font-size: 14px;
}
.dict-code {
  color: var(--crm-ink-soft, #909399);
  font-size: 11px;
}
.dict-editor {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}
.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.editor-title h2 {
  margin: 0;
  font-size: 16px;
}
.editor-title small {
  display: block;
  margin-top: 4px;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
}
.editor-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.dict-editor .crm-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.hint {
  color: var(--crm-ink-soft, #909399);
}
@media (max-width: 768px) {
  .dict-layout {
    flex-direction: column;
  }
  .dict-sidebar {
    width: 100%;
    max-height: 180px;
    border-right: none;
    border-bottom: 1px solid var(--crm-border, #e4e7ed);
  }
}
</style>
