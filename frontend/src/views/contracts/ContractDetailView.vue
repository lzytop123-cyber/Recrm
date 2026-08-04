<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/contracts')">返回列表</el-button>
      <div class="actions" v-if="contract">
        <el-button v-if="contract.status === 'draft'" type="primary" @click="editVisible = true">编辑</el-button>
        <el-button v-if="contract.status === 'draft'" type="warning" @click="onSubmit">提交审批</el-button>
        <el-tag
          v-if="contract.status === 'pending_approval' && !canApproveContract"
          type="warning"
          effect="plain"
          style="margin-right: 8px"
        >
          已提交，等待财务 / 管理层审批
        </el-tag>
        <el-button
          v-if="contract.status === 'pending_approval' && canWithdraw"
          @click="onWithdraw"
        >
          撤回审批
        </el-button>
        <el-button
          v-if="contract.status === 'pending_approval' && canApproveContract"
          type="success"
          @click="onApprove"
        >
          审批通过
        </el-button>
        <el-button
          v-if="contract.status === 'pending_approval' && canApproveContract"
          @click="onReject"
        >
          驳回
        </el-button>
        <el-tag
          v-if="contract.status === 'approved' && !canSignContract"
          type="success"
          effect="plain"
          style="margin-right: 8px"
        >
          已审批，等待负责人（{{ contract.owner_name || '—' }}）签署
        </el-tag>
        <el-button
          v-if="contract.status === 'approved' && canSignContract"
          type="success"
          @click="signVisible = true"
        >
          签署
        </el-button>
        <el-button v-if="contract.status === 'signed'" type="primary" @click="onActivate">进入执行</el-button>
        <el-button v-if="contract.status === 'active'" type="success" @click="onComplete">完成</el-button>
        <el-button
          v-if="canTerminate"
          type="danger"
          plain
          @click="terminateVisible = true"
        >
          终止
        </el-button>
      </div>
    </div>

    <el-card v-if="contract">
      <template #header>
        <div class="card-header">
          <span>{{ contract.contract_no }} · {{ contract.title }}</span>
          <el-tag :type="statusTag(contract.status)" size="small">
            {{ CONTRACT_STATUS_LABEL[contract.status] || contract.status }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="合同编号">{{ contract.contract_no }}</el-descriptions-item>
        <el-descriptions-item label="合同名称">{{ contract.title }}</el-descriptions-item>
        <el-descriptions-item label="客户">
          <el-button link type="primary" @click="$router.push(`/customers/${contract.customer_id}`)">
            {{ contract.customer_name || `#${contract.customer_id}` }}
          </el-button>
        </el-descriptions-item>
        <el-descriptions-item label="类型">{{ typeLabel(contract.contract_type) }}</el-descriptions-item>
        <el-descriptions-item label="金额">
          {{ formatAmount(contract.amount) }} {{ contract.currency }}
        </el-descriptions-item>
        <el-descriptions-item label="付款方式">{{ payLabel(contract.payment_method) }}</el-descriptions-item>
        <el-descriptions-item label="签署日期">{{ contract.signed_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="生效日期">{{ contract.effective_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ contract.expire_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ contract.owner_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ contract.creator_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批人">{{ contract.approved_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批时间">{{ formatTime(contract.approved_at) }}</el-descriptions-item>
        <el-descriptions-item label="合同证明" :span="2">
          <div class="proof-cell">
            <template v-if="contract.proof_url">
              <a :href="contract.proof_url" target="_blank" rel="noopener">
                {{ contract.proof_filename || '查看附件' }}
              </a>
            </template>
            <span v-else class="muted">未上传（提交审批前须补传）</span>
            <template v-if="contract.status === 'draft'">
              <el-button
                link
                type="primary"
                :loading="uploadingProof"
                @click="pickDetailProof"
              >
                {{ contract.proof_url ? '重新上传' : '上传证明' }}
              </el-button>
              <input
                ref="detailProofInputRef"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                hidden
                @change="onDetailProofSelected"
              />
            </template>
          </div>
        </el-descriptions-item>
        <el-descriptions-item v-if="contract.terminate_reason" label="终止原因" :span="2">
          {{ contract.terminate_reason }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ contract.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑草稿" width="560px" destroy-on-close>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="合同名称" required>
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="editForm.contract_type" style="width: 100%">
            <el-option
              v-for="opt in CONTRACT_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="editForm.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="editForm.payment_method" clearable style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker v-model="editForm.effective_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker v-model="editForm.expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="合同证明" required>
          <div
            class="upload-box"
            :class="{ uploaded: !!editForm.proof_filename }"
            @click="pickEditProof"
          >
            <template v-if="editForm.proof_filename">
              <b>{{ editForm.proof_filename }}</b>
              <small>{{ uploadingProof ? '上传中…' : '已上传 · 可重新选择' }}</small>
            </template>
            <template v-else>
              <b>上传合同照片或扫描件</b>
              <small>PDF、PNG或JPG · 单文件不超过10MB</small>
            </template>
          </div>
          <input
            ref="editProofInputRef"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            hidden
            @change="onEditProofSelected"
          />
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

    <el-dialog v-model="signVisible" title="签署合同" width="480px">
      <el-form :model="signForm" label-width="100px">
        <el-form-item label="签署日期">
          <el-date-picker v-model="signForm.signed_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker v-model="signForm.effective_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker v-model="signForm.expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSign">确认签署</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="terminateVisible" title="终止合同" width="480px">
      <el-input v-model="terminateReason" type="textarea" :rows="3" placeholder="请填写终止原因" />
      <template #footer>
        <el-button @click="terminateVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="onTerminate">确认终止</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="forceCompleteVisible" title="特批完成合同" width="480px" destroy-on-close>
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="回款尚未收齐。特批完成后合同将标为已完成，请填写原因。"
        style="margin-bottom: 12px"
      />
      <el-input
        v-model="forceCompleteReason"
        type="textarea"
        :rows="3"
        placeholder="特批原因（必填）"
      />
      <template #footer>
        <el-button @click="forceCompleteVisible = false">取消</el-button>
        <el-button type="warning" :loading="saving" @click="onForceComplete">确认特批完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CONTRACT_STATUS_LABEL,
  CONTRACT_TYPE_OPTIONS,
  PAYMENT_METHOD_OPTIONS,
  activateContract,
  approveContract,
  completeContract,
  fetchContractDetail,
  rejectContract,
  signContract,
  submitContract,
  terminateContract,
  updateContract,
  withdrawContract,
  type Contract,
} from '@/api/contracts'
import { uploadFile } from '@/api/uploads'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const uploadingProof = ref(false)
const contract = ref<Contract | null>(null)
const editVisible = ref(false)
const signVisible = ref(false)
const terminateVisible = ref(false)
const terminateReason = ref('')
const forceCompleteVisible = ref(false)
const forceCompleteReason = ref('')
const editProofInputRef = ref<HTMLInputElement>()
const detailProofInputRef = ref<HTMLInputElement>()

const editForm = reactive({
  title: '',
  contract_type: 'other',
  amount: 0,
  payment_method: '' as string | undefined,
  effective_date: '' as string | undefined,
  expire_date: '' as string | undefined,
  remark: '',
  proof_filename: '',
  proof_path: '',
})

const signForm = reactive({
  signed_date: '',
  effective_date: '',
  expire_date: '',
})

const contractId = computed(() => Number(route.params.id))

const canTerminate = computed(() => {
  const s = contract.value?.status
  return s === 'signed' || s === 'active'
})

const canWithdraw = computed(() => {
  if (!contract.value || contract.value.status !== 'pending_approval') return false
  if (userStore.hasPermission('contract:manage') || userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  if (roles.has('admin')) return true
  const uid = userStore.user?.id
  return contract.value.owner_id === uid || contract.value.creator_id === uid
})

/** 与后端一致：admin / contract:manage / 财务 / 管理层可审批；销售仅能提交 */
const canApproveContract = computed(() => {
  if (userStore.hasPermission('contract:manage') || userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  return roles.has('admin') || roles.has('finance') || roles.has('executive')
})

/** 仅合同负责人可签署（线索分配到谁，起草后负责人即谁）；admin 可代签 */
const canSignContract = computed(() => {
  if (!contract.value) return false
  if (userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  if (roles.has('admin')) return true
  return contract.value.owner_id === userStore.user?.id
})

/** 回款未收齐时特批完成：admin / 财务 / 管理层 / contract:manage / payment:manage */
const canForceComplete = computed(() => {
  if (userStore.hasPermission('contract:manage') || userStore.hasPermission('payment:manage')) {
    return true
  }
  if (userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  return roles.has('admin') || roles.has('finance') || roles.has('executive')
})

function typeLabel(code: string) {
  return CONTRACT_TYPE_OPTIONS.find((x) => x.value === code)?.label || code
}

function payLabel(code?: string | null) {
  if (!code) return '-'
  return PAYMENT_METHOD_OPTIONS.find((x) => x.value === code)?.label || code
}

function formatAmount(v: number | string) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : v
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    draft: 'info',
    pending_approval: 'warning',
    approved: '',
    signed: 'success',
    active: 'success',
    completed: 'success',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function fillEdit() {
  if (!contract.value) return
  const c = contract.value
  editForm.title = c.title
  editForm.contract_type = c.contract_type
  editForm.amount = Number(c.amount) || 0
  editForm.payment_method = c.payment_method || undefined
  editForm.effective_date = c.effective_date || undefined
  editForm.expire_date = c.expire_date || undefined
  editForm.remark = c.remark || ''
  editForm.proof_filename = c.proof_filename || ''
  editForm.proof_path = c.proof_path || ''
}

function pickEditProof() {
  if (uploadingProof.value) return
  editProofInputRef.value?.click()
}

function pickDetailProof() {
  if (uploadingProof.value) return
  detailProofInputRef.value?.click()
}

async function onDetailProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !contract.value) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('单文件不超过 10MB')
    input.value = ''
    return
  }
  uploadingProof.value = true
  try {
    const { data } = await uploadFile(file, 'contract_proof')
    await updateContract(contractId.value, {
      proof_filename: data.filename,
      proof_path: data.path,
    })
    ElMessage.success('合同证明已上传')
    await loadDetail()
  } finally {
    uploadingProof.value = false
    input.value = ''
  }
}

async function onEditProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('单文件不超过 10MB')
    input.value = ''
    return
  }
  uploadingProof.value = true
  try {
    const { data } = await uploadFile(file, 'contract_proof')
    editForm.proof_filename = data.filename
    editForm.proof_path = data.path
  } finally {
    uploadingProof.value = false
    input.value = ''
  }
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchContractDetail(contractId.value)
    contract.value = data
    fillEdit()
  } finally {
    loading.value = false
  }
}

watch(editVisible, (v) => {
  if (v) fillEdit()
})

async function onSaveEdit() {
  if (!editForm.title.trim()) {
    ElMessage.warning('合同名称不能为空')
    return
  }
  if (!editForm.proof_filename || !editForm.proof_path) {
    ElMessage.warning('请上传合同照片或证明')
    return
  }
  saving.value = true
  try {
    await updateContract(contractId.value, {
      title: editForm.title,
      contract_type: editForm.contract_type,
      amount: editForm.amount,
      payment_method: editForm.payment_method || undefined,
      effective_date: editForm.effective_date || undefined,
      expire_date: editForm.expire_date || undefined,
      remark: editForm.remark || undefined,
      proof_filename: editForm.proof_filename,
      proof_path: editForm.proof_path,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onSubmit() {
  if (!contract.value?.proof_path) {
    ElMessage.warning('请先上传合同照片或证明')
    pickDetailProof()
    return
  }
  try {
    await ElMessageBox.confirm('确认提交审批？提交后将不可编辑。', '提交审批')
    await submitContract(contractId.value)
    ElMessage.success('已提交审批')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onWithdraw() {
  try {
    await ElMessageBox.confirm('撤回后合同将回到草稿，可继续修改后再提交。', '撤回审批')
    await withdrawContract(contractId.value)
    ElMessage.success('已撤回为草稿')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onApprove() {
  try {
    await ElMessageBox.confirm('确认审批通过？', '审批')
    await approveContract(contractId.value)
    ElMessage.success('审批通过')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onReject() {
  try {
    const { value } = await ElMessageBox.prompt('请输入驳回原因（可选）', '驳回', {
      inputPlaceholder: '驳回原因',
      confirmButtonText: '驳回',
    })
    await rejectContract(contractId.value, value || undefined)
    ElMessage.success('已驳回为草稿')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onSign() {
  saving.value = true
  try {
    await signContract(contractId.value, {
      signed_date: signForm.signed_date || undefined,
      effective_date: signForm.effective_date || undefined,
      expire_date: signForm.expire_date || undefined,
    })
    ElMessage.success('已签署')
    signVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onActivate() {
  try {
    await ElMessageBox.confirm('确认进入执行中？', '进入执行')
    await activateContract(contractId.value)
    ElMessage.success('已进入执行')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onComplete() {
  if (contract.value?.collection_status === 'collected') {
    try {
      await ElMessageBox.confirm('回款已收齐，确认完成该合同？', '完成合同')
      await completeContract(contractId.value)
      ElMessage.success('合同已完成')
      await loadDetail()
    } catch {
      /* cancel */
    }
    return
  }
  if (!canForceComplete.value) {
    ElMessage.warning('回款尚未收齐，暂不能完成；请先完成到款核销，或联系财务/管理层特批')
    return
  }
  forceCompleteReason.value = ''
  forceCompleteVisible.value = true
}

async function onForceComplete() {
  if (!forceCompleteReason.value.trim()) {
    ElMessage.warning('请填写特批原因')
    return
  }
  saving.value = true
  try {
    await completeContract(contractId.value, {
      force: true,
      force_reason: forceCompleteReason.value.trim(),
    })
    ElMessage.success('已特批完成合同')
    forceCompleteVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onTerminate() {
  if (!terminateReason.value.trim()) {
    ElMessage.warning('请填写终止原因')
    return
  }
  saving.value = true
  try {
    await terminateContract(contractId.value, terminateReason.value.trim())
    ElMessage.success('合同已终止')
    terminateVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.muted {
  color: var(--crm-ink-soft);
}
.proof-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.upload-box {
  width: 100%;
  min-height: 88px;
  padding: 16px;
  border: 1px dashed var(--crm-border);
  border-radius: 10px;
  background: oklch(0.985 0.005 250);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  box-sizing: border-box;
}
.upload-box:hover {
  border-color: var(--crm-primary);
}
.upload-box.uploaded {
  border-style: solid;
  background: oklch(0.97 0.02 145);
}
.upload-box b {
  font-size: 14px;
  color: var(--crm-ink);
}
.upload-box small {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
</style>

