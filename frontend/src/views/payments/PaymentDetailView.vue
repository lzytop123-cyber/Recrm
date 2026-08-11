<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/payments')">返回列表</el-button>
      <div class="actions" v-if="payment">
        <el-button
          v-if="payment.status === 'pending'"
          v-perm="'payment:manage'"
          type="primary"
          @click="editVisible = true"
        >
          编辑
        </el-button>
        <el-button
          v-if="payment.status === 'pending'"
          v-perm.any="['payment:confirm', 'payment:manage']"
          type="success"
          @click="confirmVisible = true"
        >
          确认到账
        </el-button>
        <el-button
          v-if="payment.status === 'confirmed'"
          v-perm.any="['payment:refund', 'payment:manage']"
          type="danger"
          plain
          @click="onRefund"
        >
          退款
        </el-button>
      </div>
    </div>

    <el-card v-if="payment">
      <template #header>
        <div class="card-header">
          <span>收款 #{{ payment.id }} · {{ payment.title || '款项' }}</span>
          <el-tag :type="statusTag(payment.status)" size="small">
            {{ PAYMENT_STATUS_LABEL[payment.status] || payment.status }}
          </el-tag>
          <el-tag :type="dueTag(payment.due_status)" size="small">
            {{ DUE_STATUS_LABEL[payment.due_status || ''] || '-' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="descCols" border>
        <el-descriptions-item label="款项">{{ payment.title || '-' }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatAmount(payment.amount) }}</el-descriptions-item>
        <el-descriptions-item label="收款方式">{{ methodLabel(payment.method) }}</el-descriptions-item>
        <el-descriptions-item label="合同">
          <el-button link type="primary" @click="$router.push(`/contracts/${payment.contract_id}`)">
            {{ payment.contract_no || `#${payment.contract_id}` }}
          </el-button>
        </el-descriptions-item>
        <el-descriptions-item label="合同名称">{{ payment.contract_title || '-' }}</el-descriptions-item>
        <el-descriptions-item label="客户">
          <el-button
            v-if="payment.customer_id"
            link
            type="primary"
            @click="$router.push(`/customers/${payment.customer_id}`)"
          >
            {{ payment.customer_name || `#${payment.customer_id}` }}
          </el-button>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="应收日期">{{ payment.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到账日期">{{ payment.paid_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="登记人">{{ payment.owner_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="确认人">{{ payment.confirmed_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ formatTime(payment.confirmed_at) }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="descCols">{{ payment.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog
      v-model="editVisible"
      title="编辑应收"
      width="520px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        :model="editForm"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="款项名称">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="editForm.amount" :min="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="应收日期">
          <el-date-picker v-model="editForm.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="editForm.method" clearable style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
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
      v-model="confirmVisible"
      title="确认到账"
      width="480px"
      :fullscreen="isCompact"
    >
      <el-form
        :model="confirmForm"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="到账日期">
          <el-date-picker v-model="confirmForm.paid_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="confirmForm.method" clearable style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="confirmForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="success" :loading="saving" @click="onConfirm">确认到账</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  DUE_STATUS_LABEL,
  PAYMENT_METHOD_OPTIONS,
  PAYMENT_STATUS_LABEL,
  confirmPayment,
  fetchPaymentDetail,
  refundPayment,
  updatePayment,
  type Payment,
} from '@/api/payments'

const route = useRoute()
const isCompact = useMatchMedia('(max-width: 768px)')
const descCols = computed(() => (isCompact.value ? 1 : 3))
const loading = ref(false)
const saving = ref(false)
const payment = ref<Payment | null>(null)
const editVisible = ref(false)
const confirmVisible = ref(false)

const editForm = reactive({
  title: '',
  amount: 0,
  due_date: '' as string | undefined,
  method: '' as string | undefined,
  remark: '',
})

const confirmForm = reactive({
  paid_date: '',
  method: '',
  remark: '',
})

const paymentId = computed(() => Number(route.params.id))

function formatAmount(v: number | string) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : String(v)
}

function methodLabel(code?: string | null) {
  if (!code) return '-'
  return PAYMENT_METHOD_OPTIONS.find((x) => x.value === code)?.label || code
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    confirmed: 'success',
    refunded: 'info',
  }
  return map[s] || 'info'
}

function dueTag(s?: string | null) {
  const map: Record<string, string> = {
    overdue: 'danger',
    due: 'warning',
    due_soon: 'warning',
    not_due: 'info',
    settled: 'success',
    refunded: 'info',
  }
  return map[s || ''] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function fillEdit() {
  if (!payment.value) return
  const p = payment.value
  editForm.title = p.title || ''
  editForm.amount = Number(p.amount) || 0
  editForm.due_date = p.due_date || undefined
  editForm.method = p.method || undefined
  editForm.remark = p.remark || ''
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchPaymentDetail(paymentId.value)
    payment.value = data
    fillEdit()
  } finally {
    loading.value = false
  }
}

watch(editVisible, (v) => {
  if (v) fillEdit()
})

async function onSaveEdit() {
  saving.value = true
  try {
    await updatePayment(paymentId.value, {
      title: editForm.title || undefined,
      amount: editForm.amount,
      due_date: editForm.due_date || undefined,
      method: editForm.method || undefined,
      remark: editForm.remark || undefined,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onConfirm() {
  saving.value = true
  try {
    await confirmPayment(paymentId.value, {
      paid_date: confirmForm.paid_date || undefined,
      method: confirmForm.method || undefined,
      remark: confirmForm.remark || undefined,
    })
    ElMessage.success('已确认到账')
    confirmVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onRefund() {
  try {
    const { value } = await ElMessageBox.prompt('请填写退款原因', '退款', {
      inputPlaceholder: '退款原因',
      confirmButtonText: '确认退款',
    })
    await refundPayment(paymentId.value, value || undefined)
    ElMessage.success('已退款')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

onMounted(loadDetail)
</script>

<style scoped>
@media (max-width: 768px) {
  .card-header {
    gap: 6px;
  }
}
</style>

