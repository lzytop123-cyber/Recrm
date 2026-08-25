<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/contracts')">返回列表</el-button>
      <div class="actions" v-if="contract">
        <el-button v-if="contract.status === 'draft'" type="primary" @click="editVisible = true">编辑</el-button>
        <el-button v-if="contract.status === 'draft'" type="warning" @click="onSubmit">提交审批</el-button>
        <el-tag
          v-if="contract.status === 'pending_approval' && !contract.approval_in_center && !canApproveContract"
          type="warning"
          effect="plain"
          style="margin-right: 8px"
        >
          已提交，等待财务 / 管理层审批
        </el-tag>
        <ApprovalCenterHint
          v-if="contract.approval_in_center"
          :label="approvalCenterLabel"
          :approval-id="contract.open_approval_id"
          biz-type="contract"
          :biz-id="contract.id"
        />
        <el-button
          v-if="contract.status === 'pending_approval' && canWithdraw"
          @click="onWithdraw"
        >
          撤回审批
        </el-button>
        <el-button
          v-if="contract.status === 'pending_approval' && canApproveContract && !contract.approval_in_center"
          v-perm="'contract:approve'"
          type="success"
          @click="onApprove"
        >
          审批通过
        </el-button>
        <el-button
          v-if="contract.status === 'pending_approval' && canApproveContract && !contract.approval_in_center"
          v-perm="'contract:approve'"
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
          @click="openSign"
        >
          签署
        </el-button>
        <el-button
          v-if="contract.status === 'signed' && canActivateContract && !contract.approval_in_center"
          type="primary"
          @click="onActivate"
        >
          进入执行
        </el-button>
        <el-button
          v-if="canModifyContract"
          type="warning"
          plain
          @click="openModify"
        >
          申请修改
        </el-button>
        <el-tag
          v-if="contract.modification_pending"
          type="warning"
          effect="plain"
          style="margin-right: 8px"
        >
          修改审批中（v{{ contract.revision }} → v{{ (contract.revision || 1) + 1 }}）
        </el-tag>
        <el-button
          v-if="contract.status === 'active' && canCompleteContract"
          :type="isCollectionCollected ? 'success' : 'info'"
          :plain="!isCollectionCollected"
          @click="onComplete"
        >
          完成
        </el-button>
        <el-button
          v-if="canTerminate && !contract.approval_in_center"
          v-perm.any="['contract:manage']"
          type="danger"
          plain
          @click="terminateVisible = true"
        >
          终止
        </el-button>
      </div>
    </div>

    <template v-if="contract">
      <el-card>
        <div class="detail-summary">
          <el-tag :type="statusTag(contract.status)" size="small">
            {{ CONTRACT_STATUS_LABEL[contract.status] || contract.status }}
          </el-tag>
          <el-tag v-if="(contract.revision || 1) > 1" type="info" size="small" effect="plain">
            修订 v{{ contract.revision }}
          </el-tag>
          <small>
            {{ contract.contract_no }} ·
            <el-button
              link
              type="primary"
              class="customer-link"
              @click="$router.push(`/customers/${contract.customer_id}`)"
            >
              {{ contract.customer_name || `客户#${contract.customer_id}` }}
            </el-button>
          </small>
        </div>
        <h2 class="contract-title">{{ contract.title }}</h2>
        <p
          v-if="showCollectionHint"
          class="collection-hint"
          :class="{ ok: isCollectionCollected }"
        >
          {{ collectionHintText }}
        </p>
        <SalesJourneyBar
          class="journey-in-card"
          :contract-id="contract.id"
          :sync-key="contract.status"
          hide-self-contract
        />
      </el-card>

      <el-card class="stack-gap">
        <template #header>合同摘要</template>
        <div class="detail-grid">
          <div class="detail-cell highlight">
            <small>合同金额</small>
            <b class="amount">{{ formatAmount(contract.amount) }} {{ contract.currency }}</b>
          </div>
          <div class="detail-cell">
            <small>合同类型</small>
            <b>{{ typeLabel(contract.contract_type) }}</b>
          </div>
          <div class="detail-cell">
            <small>负责人</small>
            <b>{{ contract.owner_name || '-' }}</b>
          </div>
          <div class="detail-cell">
            <small>付款方式</small>
            <b>{{ payLabel(contract.payment_method) }}</b>
          </div>
          <div class="detail-cell">
            <small>创建人</small>
            <b>{{ contract.creator_name || '-' }}</b>
          </div>
          <div class="detail-cell wide">
            <small>合同证明</small>
            <div class="proof-cell">
              <AttachmentPreview
                v-if="proofPreviewItems.length"
                :items="proofPreviewItems"
                size="md"
              />
              <span v-else class="muted-inline">未上传（提交审批前须补传）</span>
              <template v-if="contract.status === 'draft'">
                <el-button
                  link
                  type="primary"
                  :loading="uploadingProof"
                  @click="pickDetailProof"
                >
                  {{ proofPreviewItems.length ? '继续添加' : '上传证明' }}
                </el-button>
                <input
                  ref="detailProofInputRef"
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                  hidden
                  @change="onDetailProofSelected"
                />
              </template>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="stack-gap">
        <template #header>有效期</template>
        <div class="detail-grid cols-3">
          <div class="detail-cell">
            <small>签署日期</small>
            <b :class="{ placeholder: !contract.signed_date }">
              {{ contract.signed_date || '待签署' }}
            </b>
          </div>
          <div class="detail-cell">
            <small>生效日期</small>
            <b :class="{ placeholder: !contract.effective_date }">
              {{ contract.effective_date || '待填写' }}
            </b>
          </div>
          <div class="detail-cell">
            <small>到期日期</small>
            <b :class="{ placeholder: !contract.expire_date }">
              {{ contract.expire_date || '待填写' }}
            </b>
          </div>
        </div>
      </el-card>

      <el-card v-if="showApprovalSection" class="stack-gap">
        <template #header>审批信息</template>
        <div class="detail-grid">
          <div class="detail-cell">
            <small>审批人</small>
            <b :class="{ placeholder: !contract.approved_by_name }">
              {{ contract.approved_by_name || '等待审批' }}
            </b>
          </div>
          <div class="detail-cell">
            <small>审批时间</small>
            <b :class="{ placeholder: !contract.approved_at }">
              {{ contract.approved_at ? formatTime(contract.approved_at) : '—' }}
            </b>
          </div>
        </div>
      </el-card>

      <FlowActivityCard
        v-if="contract.id"
        :biz-type="['contract', 'contract_activate', 'contract_terminate', 'contract_modify']"
        :biz-id="contract.id"
        hide-when-empty
      />

      <el-card v-if="contract.remark || contract.terminate_reason" class="stack-gap">
        <template #header>备注与说明</template>
        <div class="detail-grid">
          <div v-if="contract.remark" class="detail-cell wide">
            <small>备注</small>
            <b>{{ contract.remark }}</b>
          </div>
          <div v-if="contract.terminate_reason" class="detail-cell wide">
            <small>终止原因</small>
            <b>{{ contract.terminate_reason }}</b>
          </div>
        </div>
      </el-card>
    </template>

    <el-dialog
      v-model="editVisible"
      title="编辑草稿"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :model="editForm"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="合同名称" required>
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="editForm.contract_type" style="width: 100%">
            <el-option
              v-for="opt in businessTypeOptions"
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
            :class="{ uploaded: editForm.proofs.length > 0 }"
            @click="pickEditProof"
          >
            <template v-if="editForm.proofs.length">
              <div class="proof-list" @click.stop>
                <div
                  v-for="(p, idx) in editForm.proofs"
                  :key="`${p.path}-${idx}`"
                  class="proof-chip"
                >
                  <AttachmentPreview :filename="p.filename" :path="p.path" size="sm" />
                  <el-button link type="danger" @click="removeEditProof(idx)">移除</el-button>
                </div>
              </div>
              <small>
                {{
                  uploadingProof
                    ? '上传中…'
                    : `已上传 ${editForm.proofs.length} 张 · 最多 ${CONTRACT_PROOF_MAX} 张，可继续添加`
                }}
              </small>
            </template>
            <template v-else>
              <b>上传合同照片或扫描件</b>
              <small>支持多选 · PDF、PNG或JPG · 单文件不超过10MB · 最多{{ CONTRACT_PROOF_MAX }}张</small>
            </template>
          </div>
          <input
            ref="editProofInputRef"
            type="file"
            multiple
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

    <el-dialog
      v-model="signVisible"
      title="签署合同"
      width="480px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <p v-if="contract" class="dialog-context">
        {{ contract.contract_no }} · {{ contract.title }}
      </p>
      <p class="dialog-hint">签署日期默认为今天；生效日未填则与签署日相同。到期日选填，但不能早于生效日。</p>
      <el-form
        :model="signForm"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="签署日期" required>
          <el-date-picker
            v-model="signForm.signed_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择签署日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker
            v-model="signForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认与签署日相同"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker
            v-model="signForm.expire_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选填"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSign">确认签署</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="modifyVisible"
      title="合同修改重审"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <p v-if="contract" class="dialog-context">
        {{ contract.contract_no }} · 当前修订 v{{ contract.revision || 1 }}
      </p>
      <p class="dialog-hint">仅填写需要变更的字段；提交后进入审批中心，通过后方生效。</p>
      <el-form :model="modifyForm" label-width="100px">
        <el-form-item label="合同名称">
          <el-input v-model="modifyForm.title" placeholder="不变更可留空" />
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="modifyForm.contract_type" clearable placeholder="不变更" style="width: 100%">
            <el-option
              v-for="opt in businessTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="合同金额">
          <el-input-number
            v-model="modifyForm.amount"
            :min="0"
            :precision="2"
            :controls="false"
            placeholder="不变更"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="modifyForm.payment_method" clearable placeholder="不变更" style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker
            v-model="modifyForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="不变更"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker
            v-model="modifyForm.expire_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="不变更"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="modifyForm.remark" type="textarea" :rows="2" placeholder="不变更可留空" />
        </el-form-item>
        <el-form-item label="修改原因" required>
          <el-input
            v-model="modifyForm.reason"
            type="textarea"
            :rows="3"
            placeholder="必填：说明修改原因与依据"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modifyVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onModify">提交修改审批</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="terminateVisible"
      title="终止合同"
      width="480px"
      :fullscreen="isCompact"
    >
      <el-input v-model="terminateReason" type="textarea" :rows="3" placeholder="请填写终止原因" />
      <template #footer>
        <el-button @click="terminateVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="onTerminate">确认终止</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import SalesJourneyBar from '@/components/sales/SalesJourneyBar.vue'
import AttachmentPreview from '@/components/common/AttachmentPreview.vue'
import ApprovalCenterHint from '@/components/approval/ApprovalCenterHint.vue'
import FlowActivityCard from '@/components/approval/FlowActivityCard.vue'
import {
  CONTRACT_PROOF_MAX,
  CONTRACT_STATUS_LABEL,
  useBusinessTypes,
  PAYMENT_METHOD_OPTIONS,
  activateContract,
  approveContract,
  completeContract,
  fetchContractDetail,
  modifyContract,
  rejectContract,
  type ContractModifyPayload,
  signContract,
  submitContract,
  terminateContract,
  updateContract,
  withdrawContract,
  type Contract,
  type ContractProofFile,
} from '@/api/contracts'
import { uploadFile } from '@/api/uploads'
import { uploadsUrl, isImageName, type AttachmentItem } from '@/utils/attachments'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const isCompact = useMatchMedia('(max-width: 768px)')
const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()
const loading = ref(false)
const saving = ref(false)
const uploadingProof = ref(false)
const contract = ref<Contract | null>(null)
const editVisible = ref(false)
const signVisible = ref(false)
const modifyVisible = ref(false)
const terminateVisible = ref(false)
const terminateReason = ref('')
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
  proofs: [] as ContractProofFile[],
})

const signForm = reactive({
  signed_date: '',
  effective_date: '',
  expire_date: '',
})

const modifyForm = reactive({
  title: '' as string | undefined,
  contract_type: '' as string | undefined,
  amount: undefined as number | undefined,
  payment_method: '' as string | undefined,
  effective_date: '' as string | undefined,
  expire_date: '' as string | undefined,
  remark: '' as string | undefined,
  reason: '',
})

const contractId = computed(() => Number(route.params.id))

function contractProofs(c: Contract | null | undefined): ContractProofFile[] {
  if (!c) return []
  if (c.proofs?.length) {
    return c.proofs.map((p) => ({
      filename: p.filename,
      path: p.path,
      url: p.url || uploadsUrl(p.path),
    }))
  }
  if (c.proof_path) {
    return [
      {
        filename: c.proof_filename || c.proof_path.split('/').pop() || '合同证明',
        path: c.proof_path,
        url: c.proof_url || uploadsUrl(c.proof_path),
      },
    ]
  }
  return []
}

const proofPreviewItems = computed<AttachmentItem[]>(() =>
  contractProofs(contract.value).map((p) => ({
    name: p.filename,
    url: p.url || uploadsUrl(p.path),
    isImage: isImageName(p.filename),
  })),
)

const canTerminate = computed(() => {
  const s = contract.value?.status
  return s === 'signed' || s === 'active'
})

/** 进入执行：管理权或负责人/创建人 */
const canActivateContract = computed(() => {
  if (!contract.value || contract.value.status !== 'signed') return false
  if (userStore.hasAnyPermission('contract:manage')) return true
  const uid = userStore.user?.id
  return contract.value.owner_id === uid || contract.value.creator_id === uid
})

const canWithdraw = computed(() => {
  if (!contract.value || contract.value.status !== 'pending_approval') return false
  if (userStore.hasPermission('contract:manage') || userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  if (roles.has('admin')) return true
  const uid = userStore.user?.id
  return contract.value.owner_id === uid || contract.value.creator_id === uid
})

/** 与后端一致：contract:approve / contract:manage */
const canApproveContract = computed(() =>
  userStore.hasAnyPermission('contract:approve', 'contract:manage'),
)

const approvalCenterLabel = computed(() => {
  if (!contract.value) return '审批进行中，请在审批中心处理'
  if (contract.value.modification_pending) return '合同修改审批进行中'
  if (contract.value.terminate_reason && contract.value.approval_in_center) {
    return '合同终止审批进行中'
  }
  if (contract.value.status === 'signed' && contract.value.approval_in_center) {
    return '激活确认审批进行中'
  }
  if (contract.value.status === 'pending_approval') return '合同分级审批进行中'
  return '审批进行中，请在审批中心处理'
})

const canModifyContract = computed(() => {
  const c = contract.value
  if (!c) return false
  if (!['approved', 'signed', 'active'].includes(c.status)) return false
  if (c.modification_pending || c.approval_in_center) return false
  if (userStore.hasAnyPermission('contract:manage')) return true
  const uid = userStore.user?.id
  return c.owner_id === uid || c.creator_id === uid
})

/** 仅合同负责人可签署（线索分配到谁，起草后负责人即谁）；admin 可代签 */
const canSignContract = computed(() => {
  if (!contract.value) return false
  if (userStore.hasPermission('*')) return true
  const roles = new Set((userStore.user?.roles || []).map((r) => r.code))
  if (roles.has('admin')) return true
  return contract.value.owner_id === userStore.user?.id
})

/** 回款已齐才可完成 */
const canCompleteContract = computed(() =>
  userStore.hasAnyPermission('contract:complete', 'contract:manage'),
)

const isCollectionCollected = computed(
  () => contract.value?.collection_status === 'collected',
)

/** 签署后进入执行阶段才展示回款进度提示 */
const showCollectionHint = computed(() => {
  const s = contract.value?.status
  return s === 'signed' || s === 'active' || s === 'completed'
})

const collectionHintText = computed(() => {
  const c = contract.value
  if (!c) return ''
  const paid = Number(c.paid_amount ?? 0)
  const amount = Number(c.amount ?? 0)
  const paidText = formatAmount(paid)
  const amountText = formatAmount(amount)
  const currency = c.currency || 'CNY'
  if (c.status === 'completed' || isCollectionCollected.value) {
    return `回款进度：已收齐 ${paidText} / ${amountText} ${currency}，可以完成合同`
  }
  return `回款进度：已核销 ${paidText} / 合同金额 ${amountText} ${currency} · 未收齐，收齐后才能点「完成」`
})

/** 草稿阶段不展示审批区块，避免一堆空字段 */
const showApprovalSection = computed(() => {
  const s = contract.value?.status
  return !!s && s !== 'draft'
})

function typeLabel(code: string) {
  return businessTypeLabel(code)
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
  editForm.proofs = contractProofs(c).map((p) => ({
    filename: p.filename,
    path: p.path,
  }))
}

function pickEditProof() {
  if (uploadingProof.value) return
  if (editForm.proofs.length >= CONTRACT_PROOF_MAX) {
    ElMessage.warning(`最多上传 ${CONTRACT_PROOF_MAX} 张`)
    return
  }
  editProofInputRef.value?.click()
}

function removeEditProof(idx: number) {
  editForm.proofs.splice(idx, 1)
}

function pickDetailProof() {
  if (uploadingProof.value) return
  if (contractProofs(contract.value).length >= CONTRACT_PROOF_MAX) {
    ElMessage.warning(`最多上传 ${CONTRACT_PROOF_MAX} 张`)
    return
  }
  detailProofInputRef.value?.click()
}

async function uploadProofFiles(
  files: File[],
  current: ContractProofFile[],
): Promise<ContractProofFile[]> {
  const remain = CONTRACT_PROOF_MAX - current.length
  if (remain <= 0) {
    ElMessage.warning(`最多上传 ${CONTRACT_PROOF_MAX} 张`)
    return current
  }
  const picked = files.slice(0, remain)
  if (files.length > remain) {
    ElMessage.warning(`最多再上传 ${remain} 张，已自动截取`)
  }
  const next = [...current]
  for (const file of picked) {
    if (file.size > 10 * 1024 * 1024) {
      ElMessage.warning(`${file.name} 超过 10MB，已跳过`)
      continue
    }
    const { data } = await uploadFile(file, 'contract_proof')
    next.push({ filename: data.filename, path: data.path })
  }
  return next
}

async function onDetailProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length || !contract.value) return
  uploadingProof.value = true
  try {
    const next = await uploadProofFiles(files, contractProofs(contract.value))
    await updateContract(contractId.value, {
      proofs: next.map((p) => ({ filename: p.filename, path: p.path })),
    })
    ElMessage.success('合同证明已更新')
    await loadDetail()
  } finally {
    uploadingProof.value = false
    input.value = ''
  }
}

async function onEditProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  uploadingProof.value = true
  try {
    editForm.proofs = await uploadProofFiles(files, editForm.proofs)
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
  if (!editForm.proofs.length) {
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
      proofs: editForm.proofs.map((p) => ({ filename: p.filename, path: p.path })),
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onSubmit() {
  if (!contractProofs(contract.value).length) {
    ElMessage.warning('请先上传合同照片或证明')
    pickDetailProof()
    return
  }
  try {
    await ElMessageBox.confirm('确认提交审批？提交后将不可编辑。', '提交审批')
    await submitContract(contractId.value)
    await loadDetail()
    if (contract.value?.approval_in_center) {
      ElMessage.success('已提交审批，请到审批中心处理')
    } else {
      ElMessage.success('已提交审批')
    }
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

function todayStr() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function openSign() {
  const today = todayStr()
  const c = contract.value
  signForm.signed_date = today
  signForm.effective_date = c?.effective_date || today
  signForm.expire_date = c?.expire_date || ''
  signVisible.value = true
}

async function onSign() {
  if (!signForm.signed_date) {
    ElMessage.warning('请选择签署日期')
    return
  }
  const effective = signForm.effective_date || signForm.signed_date
  if (signForm.expire_date && signForm.expire_date < effective) {
    ElMessage.warning('到期日期不能早于生效日期')
    return
  }
  saving.value = true
  try {
    await signContract(contractId.value, {
      signed_date: signForm.signed_date,
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

function openModify() {
  modifyForm.title = undefined
  modifyForm.contract_type = undefined
  modifyForm.amount = undefined
  modifyForm.payment_method = undefined
  modifyForm.effective_date = undefined
  modifyForm.expire_date = undefined
  modifyForm.remark = undefined
  modifyForm.reason = ''
  modifyVisible.value = true
}

async function onModify() {
  if (!modifyForm.reason.trim()) {
    ElMessage.warning('请填写修改原因')
    return
  }
  const payload: ContractModifyPayload = { reason: modifyForm.reason.trim() }
  if (modifyForm.title?.trim()) payload.title = modifyForm.title.trim()
  if (modifyForm.contract_type) payload.contract_type = modifyForm.contract_type
  if (modifyForm.amount != null) payload.amount = modifyForm.amount
  if (modifyForm.payment_method) payload.payment_method = modifyForm.payment_method
  if (modifyForm.effective_date) payload.effective_date = modifyForm.effective_date
  if (modifyForm.expire_date) payload.expire_date = modifyForm.expire_date
  if (modifyForm.remark?.trim()) payload.remark = modifyForm.remark.trim()
  if (Object.keys(payload).length <= 1) {
    ElMessage.warning('请填写至少一项修改内容')
    return
  }
  saving.value = true
  try {
    await modifyContract(contractId.value, payload)
    ElMessage.success('修改已提交，请到审批中心处理')
    modifyVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onActivate() {
  try {
    await ElMessageBox.confirm('确认进入执行中？', '进入执行')
    const { data } = await activateContract(contractId.value)
    if (data.approval_in_center) {
      ElMessage.success('已提交激活确认，请到审批中心处理')
    } else {
      ElMessage.success('已进入执行')
    }
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onComplete() {
  if (isCollectionCollected.value) {
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
  const paid = formatAmount(Number(contract.value?.paid_amount ?? 0))
  const amount = formatAmount(Number(contract.value?.amount ?? 0))
  ElMessage.warning(
    `回款尚未收齐（已核销 ${paid} / ${amount}），暂不能完成；请先完成到款核销`,
  )
}

async function onTerminate() {
  if (!terminateReason.value.trim()) {
    ElMessage.warning('请填写终止原因')
    return
  }
  saving.value = true
  try {
    const { data } = await terminateContract(contractId.value, terminateReason.value.trim())
    if (data.approval_in_center) {
      ElMessage.success('终止申请已提交，请到审批中心处理')
    } else {
      ElMessage.success('合同已终止')
    }
    terminateVisible.value = false
    terminateReason.value = ''
    await loadDetail()
  } finally {
    saving.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.dialog-context {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink);
  line-height: 1.4;
}
.dialog-hint {
  margin: 0 0 14px;
  color: var(--crm-ink-soft);
  font-size: 13px;
  line-height: 1.5;
}
.detail-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.detail-summary small {
  color: var(--crm-ink-soft);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.customer-link {
  padding: 0;
  height: auto;
  font-size: inherit;
}
.contract-title {
  margin: 0;
  font-size: 20px;
}
.journey-in-card {
  margin-top: 12px;
}
.collection-hint {
  margin: 10px 0 0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.45;
  color: #8a5a00;
  background: oklch(0.97 0.03 85);
  border: 1px solid oklch(0.9 0.05 85);
}
.collection-hint.ok {
  color: #1f6b3a;
  background: oklch(0.97 0.02 145);
  border-color: oklch(0.9 0.04 145);
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.detail-grid.cols-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.detail-cell {
  padding: 12px;
  border: 1px solid var(--crm-border);
  border-radius: 10px;
  background: var(--crm-surface-soft);
}
.detail-cell.wide {
  grid-column: 1 / -1;
}
.detail-cell.highlight {
  background: oklch(0.97 0.02 250);
  border-color: oklch(0.88 0.04 250);
}
.detail-cell small {
  display: block;
  color: var(--crm-ink-soft);
  font-size: 12px;
  margin-bottom: 6px;
}
.detail-cell b {
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink);
  line-height: 1.4;
}
.detail-cell b.amount {
  font-size: 18px;
}
.detail-cell b.placeholder {
  font-weight: 500;
  color: var(--crm-ink-soft);
}
.stack-gap {
  margin-top: 16px;
}
.muted-inline {
  color: var(--crm-ink-soft);
  font-size: 13px;
}
.proof-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.proof-thumb-link {
  display: block;
  flex-shrink: 0;
}
.proof-thumb {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--crm-border);
  display: block;
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
.proof-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.proof-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--crm-surface);
  border: 1px solid var(--crm-border);
}
@media (max-width: 768px) {
  .detail-summary {
    flex-wrap: wrap;
    gap: 6px 10px;
  }
  .detail-summary small {
    width: 100%;
  }
  .contract-title {
    font-size: 18px;
    line-height: 1.35;
    word-break: break-word;
  }
  .detail-grid,
  .detail-grid.cols-3 {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .detail-cell {
    padding: 10px 12px;
  }
  .proof-cell {
    align-items: flex-start;
  }
}
</style>

