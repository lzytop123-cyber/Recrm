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
            <el-form-item label="编码">
              <el-input v-model="form.code" :disabled="!!form.id || !canManage" />
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="form.name" :disabled="!canManage" />
            </el-form-item>
            <el-form-item label="业务类型">
              <el-select
                v-model="form.biz_type"
                filterable
                allow-create
                default-first-option
                placeholder="选择或输入业务类型"
                :disabled="!canManage"
                style="width: 100%"
              >
                <el-option
                  v-for="opt in BIZ_TYPE_OPTIONS"
                  :key="opt.value"
                  :label="`${opt.label}（${opt.value}）`"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="超时(小时)">
              <el-input-number v-model="form.timeout_hours" :min="1" :max="8760" :disabled="!canManage" />
            </el-form-item>

            <el-divider content-position="left">命中条件</el-divider>
            <el-form-item label="条件">
              <div class="cond-row">
                <el-switch
                  v-model="editor.noCondition"
                  active-text="无条件（默认规则）"
                  :disabled="!canManage"
                  @change="onNoConditionChange"
                />
                <template v-if="!editor.noCondition">
                  <el-select v-model="editor.condField" :disabled="!canManage" style="width: 120px">
                    <el-option label="金额 amount" value="amount" />
                  </el-select>
                  <el-select v-model="editor.condOp" :disabled="!canManage" style="width: 110px">
                    <el-option label="<" value="lt" />
                    <el-option label="≤" value="lte" />
                    <el-option label=">" value="gt" />
                    <el-option label="≥" value="gte" />
                    <el-option label="=" value="eq" />
                  </el-select>
                  <el-input-number
                    v-model="editor.condValue"
                    :min="0"
                    :disabled="!canManage"
                    controls-position="right"
                  />
                </template>
              </div>
            </el-form-item>

            <el-divider content-position="left">审批节点</el-divider>
            <div class="nodes-block">
              <div v-for="(node, idx) in editor.nodes" :key="idx" class="node-card">
                <div class="node-card-head">
                  <span class="node-idx">节点 {{ idx + 1 }}</span>
                  <div v-if="canManage" class="node-card-actions">
                    <el-button text size="small" :disabled="idx === 0" @click="moveNode(idx, -1)">上移</el-button>
                    <el-button
                      text
                      size="small"
                      :disabled="idx === editor.nodes.length - 1"
                      @click="moveNode(idx, 1)"
                    >下移</el-button>
                    <el-button text type="danger" size="small" @click="removeNode(idx)">删除</el-button>
                  </div>
                </div>
                <el-form-item label="名称">
                  <el-input v-model="node.name" placeholder="如 部门负责人审批" :disabled="!canManage" />
                </el-form-item>
                <el-form-item label="类型">
                  <el-select v-model="node.type" :disabled="!canManage" style="width: 100%" @change="onNodeTypeChange(node)">
                    <el-option label="审批 approve" value="approve" />
                    <el-option label="执行 execute" value="execute" />
                    <el-option label="会签 countersign" value="countersign" />
                    <el-option label="指定人 assignee" value="assignee" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="node.type === 'approve' || node.type === 'execute'" label="角色">
                  <el-select
                    v-model="node.roles"
                    multiple
                    filterable
                    placeholder="选择审批角色"
                    :disabled="!canManage"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="role in roleOptions"
                      :key="role.code"
                      :label="`${role.name}（${role.code}）`"
                      :value="role.code"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="node.type === 'assignee'" label="指定人">
                  <el-select
                    v-model="node.assignee_id"
                    clearable
                    filterable
                    placeholder="选择具体审批人（可留空，用下方指定人键动态匹配）"
                    :disabled="!canManage"
                    style="width: 100%"
                  >
                    <el-option v-for="u in userOptions" :key="u.id" :label="u.name" :value="u.id" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="node.type === 'assignee'" label="指定人键">
                  <el-input
                    v-model="node.assignee_key"
                    placeholder="如 acceptor_id（发起时传入 facts；与上方指定人二选一）"
                    :disabled="!canManage"
                  />
                </el-form-item>
                <template v-if="node.type === 'countersign'">
                  <div v-for="(g, gIdx) in node.groups" :key="gIdx" class="group-row">
                    <el-input
                      v-model="g.label"
                      placeholder="组名"
                      :disabled="!canManage"
                      style="width: 120px"
                    />
                    <el-select
                      v-model="g.roles"
                      multiple
                      filterable
                      placeholder="角色"
                      :disabled="!canManage"
                      style="flex: 1"
                    >
                      <el-option
                        v-for="role in roleOptions"
                        :key="role.code"
                        :label="`${role.name}（${role.code}）`"
                        :value="role.code"
                      />
                    </el-select>
                    <el-button
                      v-if="canManage"
                      text
                      type="danger"
                      :disabled="node.groups.length <= 1"
                      @click="node.groups.splice(gIdx, 1)"
                    >删组</el-button>
                  </div>
                  <el-button v-if="canManage" size="small" @click="addGroup(node)">添加会签组</el-button>
                </template>
              </div>
              <el-button v-if="canManage" type="primary" plain @click="addNode">添加节点</el-button>
            </div>

            <el-divider content-position="left">抄送</el-divider>
            <el-form-item label="抄送角色">
              <el-select
                v-model="editor.cc"
                multiple
                filterable
                placeholder="可选"
                :disabled="!canManage"
                style="width: 100%"
              >
                <el-option
                  v-for="role in roleOptions"
                  :key="role.code"
                  :label="`${role.name}（${role.code}）`"
                  :value="role.code"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" :disabled="!canManage" />
            </el-form-item>

            <el-collapse>
              <el-collapse-item title="生成 JSON 预览（只读）" name="preview">
                <pre class="json-preview">{{ previewJson }}</pre>
              </el-collapse-item>
            </el-collapse>
          </el-form>
        </section>
        <el-empty v-else description="请选择或新建规则" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { fetchDirectoryPeople } from '@/api/directory'
import { fetchSystemRoles, type SystemRole } from '@/api/system'
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

const BIZ_TYPE_OPTIONS = [
  { value: 'contract', label: '合同审批' },
  { value: 'contract_activate', label: '合同激活' },
  { value: 'contract_modify', label: '合同修改' },
  { value: 'contract_terminate', label: '合同终止' },
  { value: 'project_no_contract', label: '无合同立项' },
  { value: 'project_initiation', label: '项目立项' },
  { value: 'project_handover', label: '项目交接' },
  { value: 'project_acceptance', label: '项目验收' },
  { value: 'project_settlement', label: '项目结项' },
  { value: 'project_terminate', label: '项目终止' },
  { value: 'timesheet', label: '工时审批' },
  { value: 'receipt', label: '收款到账' },
  { value: 'receipt_diff', label: '收款差异' },
  { value: 'refund', label: '退款' },
  { value: 'asset_borrow', label: '资产借用' },
  { value: 'asset_return', label: '资产归还' },
  { value: 'asset_maintenance', label: '资产维修' },
  { value: 'asset_inventory_diff', label: '盘点差异' },
  { value: 'asset_compensation', label: '资产赔偿' },
  { value: 'ticket', label: '协作工单' },
  { value: 'ticket_cross_accept', label: '跨部门验收' },
  { value: 'schedule', label: '排期会议' },
  { value: 'role_change', label: '角色权限变更' },
]

type NodeType = 'approve' | 'execute' | 'countersign' | 'assignee'

interface CountersignGroup {
  label: string
  roles: string[]
}

interface EditorNode {
  name: string
  type: NodeType
  roles: string[]
  groups: CountersignGroup[]
  assignee_key: string
  assignee_id: number | null
}

const loading = ref(false)
const saving = ref(false)
const rules = ref<ApprovalRule[]>([])
const activeId = ref<number | null>(null)
const statusFilter = ref<string | undefined>('published')
const form = ref<Partial<ApprovalRule> | null>(null)
const roleOptions = ref<SystemRole[]>([])
const userOptions = ref<{ id: number; name: string }[]>([])

async function loadUsers() {
  try {
    const people = await fetchDirectoryPeople()
    userOptions.value = people.map((p) => ({ id: p.id, name: p.real_name || p.username || `用户${p.id}` }))
  } catch {
    /* 目录不可用时静默，指定人下拉为空 */
  }
}

const editor = reactive({
  noCondition: true,
  condField: 'amount',
  condOp: 'lt' as string,
  condValue: 10000 as number | undefined,
  nodes: [] as EditorNode[],
  cc: [] as string[],
})

function emptyNode(): EditorNode {
  return {
    name: '部门负责人审批',
    type: 'approve',
    roles: ['dept_head'],
    groups: [{ label: '', roles: [] }],
    assignee_key: '',
    assignee_id: null,
  }
}

function statusLabel(s: string) {
  return ({ published: '已发布', draft: '草稿', disabled: '已停用' } as Record<string, string>)[s] || s
}
function statusTag(s: string) {
  return ({ published: 'success', draft: 'info', disabled: 'danger' } as Record<string, string>)[s] || 'info'
}

function parseNodesJson(raw?: string | null): { nodes: EditorNode[]; cc: string[] } {
  const fallback = { nodes: [emptyNode()], cc: [] as string[] }
  if (!raw?.trim()) return fallback
  try {
    const cfg = JSON.parse(raw)
    const list = Array.isArray(cfg?.nodes) ? cfg.nodes : Array.isArray(cfg) ? cfg : []
    const nodes: EditorNode[] = list.map((n: Record<string, unknown>) => {
      const type = (['approve', 'execute', 'countersign', 'assignee'].includes(String(n.type))
        ? String(n.type)
        : 'approve') as NodeType
      const groupsRaw = Array.isArray(n.groups) ? n.groups : []
      return {
        name: String(n.name || ''),
        type,
        roles: Array.isArray(n.roles) ? n.roles.map(String) : [],
        groups: groupsRaw.length
          ? groupsRaw.map((g: Record<string, unknown>) => ({
              label: String(g.label || ''),
              roles: Array.isArray(g.roles) ? g.roles.map(String) : [],
            }))
          : [{ label: '', roles: [] }],
        assignee_key: String(n.assignee_key || ''),
        assignee_id: n.assignee_id != null ? Number(n.assignee_id) : null,
      }
    })
    const cc = Array.isArray(cfg?.cc) ? cfg.cc.map(String) : []
    return { nodes: nodes.length ? nodes : [emptyNode()], cc }
  } catch {
    ElMessage.warning('节点 JSON 解析失败，已使用默认节点')
    return fallback
  }
}

function parseConditionsJson(raw?: string | null) {
  if (!raw?.trim()) {
    return { noCondition: true, field: 'amount', op: 'lt', value: 10000 }
  }
  try {
    const cfg = JSON.parse(raw)
    const when = cfg?.when
    if (!when || typeof when !== 'object') {
      return { noCondition: true, field: 'amount', op: 'lt', value: 10000 }
    }
    return {
      noCondition: false,
      field: String(when.field || 'amount'),
      op: String(when.op || 'lt'),
      value: Number(when.value ?? 10000),
    }
  } catch {
    ElMessage.warning('条件 JSON 解析失败，已设为无条件')
    return { noCondition: true, field: 'amount', op: 'lt', value: 10000 }
  }
}

function applyEditorFromRule(data: Partial<ApprovalRule>) {
  const parsed = parseNodesJson(data.nodes_json)
  editor.nodes = parsed.nodes
  editor.cc = parsed.cc
  const cond = parseConditionsJson(data.conditions_json)
  editor.noCondition = cond.noCondition
  editor.condField = cond.field
  editor.condOp = cond.op
  editor.condValue = cond.value
}

function serializeNodes(): string {
  const nodes = editor.nodes.map((n) => {
    if (n.type === 'countersign') {
      return {
        name: n.name.trim(),
        type: n.type,
        groups: n.groups
          .filter((g) => g.label.trim() || g.roles.length)
          .map((g) => ({ label: g.label.trim(), roles: g.roles })),
      }
    }
    if (n.type === 'assignee') {
      return {
        name: n.name.trim(),
        type: n.type,
        assignee_key: n.assignee_key.trim(),
        ...(n.assignee_id ? { assignee_id: n.assignee_id } : {}),
      }
    }
    return {
      name: n.name.trim(),
      type: n.type,
      roles: n.roles,
    }
  })
  return JSON.stringify({ nodes, cc: editor.cc }, null, 2)
}

function serializeConditions(): string | null {
  if (editor.noCondition) return null
  return JSON.stringify({
    when: {
      field: editor.condField,
      op: editor.condOp,
      value: editor.condValue ?? 0,
    },
  })
}

const previewJson = computed(() => {
  return JSON.stringify(
    {
      conditions: editor.noCondition
        ? null
        : { when: { field: editor.condField, op: editor.condOp, value: editor.condValue ?? 0 } },
      nodes: JSON.parse(serializeNodes()),
    },
    null,
    2,
  )
})

function onNoConditionChange() {
  if (!editor.noCondition && editor.condValue == null) editor.condValue = 10000
}

function onNodeTypeChange(node: EditorNode) {
  if (node.type === 'countersign' && !node.groups.length) {
    node.groups = [{ label: '', roles: [] }]
  }
}

function addNode() {
  editor.nodes.push(emptyNode())
}

function removeNode(idx: number) {
  if (editor.nodes.length <= 1) {
    ElMessage.warning('至少保留一个节点')
    return
  }
  editor.nodes.splice(idx, 1)
}

function moveNode(idx: number, delta: number) {
  const target = idx + delta
  if (target < 0 || target >= editor.nodes.length) return
  const tmp = editor.nodes[idx]
  editor.nodes[idx] = editor.nodes[target]
  editor.nodes[target] = tmp
}

function addGroup(node: EditorNode) {
  node.groups.push({ label: '', roles: [] })
}

async function loadRoles() {
  try {
    const { data } = await fetchSystemRoles()
    roleOptions.value = data
  } catch {
    roleOptions.value = []
  }
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await listApprovalRules({ status: statusFilter.value, page_size: 100 })
    rules.value = data.items
    if (!rules.value.length) {
      if (activeId.value != null) {
        activeId.value = null
        form.value = null
      }
      return
    }
    const hit = activeId.value
      ? rules.value.find((x) => x.id === activeId.value)
      : undefined
    await selectRule(hit ?? rules.value[0])
  } finally {
    loading.value = false
  }
}

async function selectRule(r: ApprovalRule) {
  activeId.value = r.id
  const { data } = await getApprovalRule(r.id)
  form.value = { ...data }
  applyEditorFromRule(data)
}

function openCreate() {
  activeId.value = null
  form.value = {
    code: '',
    name: '',
    biz_type: '',
    timeout_hours: 72,
    nodes_json: '',
    conditions_json: '',
    remark: '',
  }
  editor.noCondition = true
  editor.condField = 'amount'
  editor.condOp = 'lt'
  editor.condValue = 10000
  editor.nodes = [emptyNode()]
  editor.cc = []
}

function validateEditor(): string | null {
  if (!editor.nodes.length) return '请至少配置一个审批节点'
  for (let i = 0; i < editor.nodes.length; i++) {
    const n = editor.nodes[i]
    if (!n.name.trim()) return `节点 ${i + 1} 请填写名称`
    if ((n.type === 'approve' || n.type === 'execute') && !n.roles.length) {
      return `节点 ${i + 1} 请选择角色`
    }
    if (n.type === 'assignee' && !n.assignee_key.trim()) {
      return `节点 ${i + 1} 请填写指定人键`
    }
    if (n.type === 'countersign') {
      const valid = n.groups.filter((g) => g.label.trim() && g.roles.length)
      if (valid.length < 2) return `节点 ${i + 1} 会签至少需要 2 个有效组`
    }
  }
  if (!editor.noCondition && (editor.condValue == null || Number.isNaN(Number(editor.condValue)))) {
    return '请填写条件金额'
  }
  return null
}

async function save() {
  if (!form.value?.code?.trim() || !form.value.name?.trim() || !form.value.biz_type?.trim()) {
    ElMessage.warning('请填写编码、名称、业务类型')
    return
  }
  const err = validateEditor()
  if (err) {
    ElMessage.warning(err)
    return
  }
  saving.value = true
  try {
    const nodes_json = serializeNodes()
    const conditions_json = serializeConditions()
    const payload = {
      ...form.value,
      nodes_json,
      conditions_json,
    }
    if (form.value.id) {
      const { data } = await updateApprovalRule(form.value.id, payload)
      form.value = { ...data }
      applyEditorFromRule(data)
      ElMessage.success('已保存')
    } else {
      const { data } = await createApprovalRule(payload)
      form.value = { ...data }
      activeId.value = data.id
      applyEditorFromRule(data)
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

onMounted(async () => {
  await loadRoles()
  await loadUsers()
  await loadList()
})
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
.cond-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; width: 100%; }
.nodes-block { display: flex; flex-direction: column; gap: 12px; margin-bottom: 8px; padding-left: 100px; }
.node-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px 12px 4px;
  background: var(--el-fill-color-blank);
}
.node-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.node-idx { font-weight: 600; font-size: 13px; color: var(--el-text-color-regular); }
.node-card-actions { display: flex; gap: 2px; }
.group-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.json-preview {
  margin: 0;
  padding: 12px;
  max-height: 280px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
