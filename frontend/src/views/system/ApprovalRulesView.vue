<template>
  <div class="crm-page rules-page crm-fit-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>审批规则</h1>
        <p>维护审批流程节点配置（AP-xx）。已发布规则由引擎按业务类型与条件命中。</p>
      </div>
    </header>

    <el-card shadow="never" class="rules-card">
      <div class="rules-layout">
        <aside class="rules-sidebar">
          <div class="rules-toolbar">
            <el-select v-model="statusFilter" placeholder="状态" clearable size="small" @change="loadList">
              <el-option label="已发布" value="published" />
              <el-option label="草稿" value="draft" />
              <el-option label="已停用" value="disabled" />
            </el-select>
            <el-button v-if="canManage" type="primary" size="small" @click="openCreate">新建</el-button>
          </div>
          <ul class="rules-list">
            <li
              v-for="r in rules"
              :key="r.id"
              :class="['rules-item', { active: r.id === activeId }]"
              @click="selectRule(r)"
            >
              <b>{{ r.code }}</b>
              <span>{{ r.name }}</span>
              <el-tag size="small" :type="statusTag(r.status)">{{ statusLabel(r.status) }}</el-tag>
            </li>
          </ul>
        </aside>

        <section class="rules-editor" v-if="form">
          <div class="editor-toolbar">
            <h2>{{ form.code || '新规则' }}</h2>
            <div v-if="canManage" class="editor-actions">
              <el-button v-if="form.id && form.status !== 'published'" type="danger" plain @click="remove">删除</el-button>
              <el-button v-if="form.id && form.status === 'published'" @click="disable">停用</el-button>
              <el-button v-if="form.id && form.status !== 'published'" type="success" @click="publish">发布</el-button>
              <el-button type="primary" :loading="saving" @click="save">保存</el-button>
            </div>
          </div>
          <el-form label-width="100px" class="rules-form">
            <el-form-item label="编码"><el-input v-model="form.code" :disabled="!!form.id" /></el-form-item>
            <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
            <el-form-item label="业务类型"><el-input v-model="form.biz_type" placeholder="如 contract / receipt" /></el-form-item>
            <el-form-item label="超时(小时)"><el-input-number v-model="form.timeout_hours" :min="1" :max="8760" /></el-form-item>
            <el-form-item label="条件 JSON"><el-input v-model="form.conditions_json" type="textarea" :rows="4" placeholder='{"when":{"field":"amount","op":"gte","value":10000}}' /></el-form-item>
            <el-form-item label="节点 JSON"><el-input v-model="form.nodes_json" type="textarea" :rows="14" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
          </el-form>
        </section>
        <el-empty v-else description="请选择或新建规则" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  createApprovalRule,
  disableApprovalRule,
  deleteApprovalRule,
  getApprovalRule,
  listApprovalRules,
  publishApprovalRule,
  updateApprovalRule,
  type ApprovalRule,
} from '@/api/approvalRules'

const userStore = useUserStore()
const canManage = computed(() => userStore.hasPermission('system:manage'))

const loading = ref(false)
const saving = ref(false)
const rules = ref<ApprovalRule[]>([])
const activeId = ref<number | null>(null)
const statusFilter = ref<string | undefined>('published')
const form = ref<Partial<ApprovalRule> | null>(null)

const DEFAULT_NODES = JSON.stringify({
  nodes: [{ name: '部门负责人审批', type: 'approve', roles: ['dept_head'] }],
  cc: [],
}, null, 2)

function statusLabel(s: string) {
  return ({ published: '已发布', draft: '草稿', disabled: '已停用' } as Record<string, string>)[s] || s
}
function statusTag(s: string) {
  return ({ published: 'success', draft: 'info', disabled: 'danger' } as Record<string, string>)[s] || 'info'
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await listApprovalRules({ status: statusFilter.value, page_size: 100 })
    rules.value = data.items
    if (!rules.value.length) {
      // 筛选后无数据时清空右侧，避免残留旧规则
      if (activeId.value != null) {
        activeId.value = null
        form.value = null
      }
      return
    }
    const hit = activeId.value
      ? rules.value.find((x) => x.id === activeId.value)
      : undefined
    // 有列表时默认选中当前项或第一条，避免右侧空态与左侧列表并存
    await selectRule(hit ?? rules.value[0])
  } finally {
    loading.value = false
  }
}

async function selectRule(r: ApprovalRule) {
  activeId.value = r.id
  const { data } = await getApprovalRule(r.id)
  form.value = { ...data }
}

function openCreate() {
  activeId.value = null
  form.value = {
    code: '',
    name: '',
    biz_type: '',
    timeout_hours: 72,
    nodes_json: DEFAULT_NODES,
    conditions_json: '',
    remark: '',
  }
}

async function save() {
  if (!form.value?.code?.trim() || !form.value.name?.trim() || !form.value.biz_type?.trim()) {
    ElMessage.warning('请填写编码、名称、业务类型')
    return
  }
  if (!form.value.nodes_json?.trim()) {
    ElMessage.warning('请填写节点 JSON')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...form.value,
      conditions_json: form.value.conditions_json?.trim() || null,
    }
    if (form.value.id) {
      const { data } = await updateApprovalRule(form.value.id, payload)
      form.value = { ...data }
      ElMessage.success('已保存')
    } else {
      const { data } = await createApprovalRule(payload)
      form.value = { ...data }
      activeId.value = data.id
      ElMessage.success('已创建')
    }
    await loadList()
  } finally {
    saving.value = false
  }
}

async function publish() {
  if (!form.value?.id) return
  await publishApprovalRule(form.value.id)
  ElMessage.success('已发布')
  await loadList()
  await selectRule({ id: form.value.id } as ApprovalRule)
}

async function disable() {
  if (!form.value?.id) return
  await disableApprovalRule(form.value.id)
  ElMessage.success('已停用')
  await loadList()
}

async function remove() {
  if (!form.value?.id) return
  await ElMessageBox.confirm('确认删除该规则？', '删除')
  await deleteApprovalRule(form.value.id)
  form.value = null
  activeId.value = null
  ElMessage.success('已删除')
  await loadList()
}

onMounted(loadList)
</script>

<style scoped>
.rules-layout { display: flex; gap: 16px; min-height: 520px; }
.rules-sidebar { width: 280px; flex-shrink: 0; border-right: 1px solid var(--el-border-color-lighter); padding-right: 12px; }
.rules-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.rules-list { list-style: none; margin: 0; padding: 0; max-height: 60vh; overflow: auto; }
.rules-item { padding: 10px 8px; border-radius: 8px; cursor: pointer; display: flex; flex-direction: column; gap: 4px; }
.rules-item.active { background: var(--el-color-primary-light-9); }
.rules-editor { flex: 1; min-width: 0; }
.editor-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.editor-actions { display: flex; gap: 8px; }
</style>
