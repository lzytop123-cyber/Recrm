<template>
  <div class="crm-page payments-page">
    <div class="crm-stats" :style="{ '--crm-stats-cols': String(statCards.length) }">
      <button
        v-for="item in statCards"
        :key="item.key"
        type="button"
        class="crm-stat-tile"
        @click="onStatClick(item)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </div>

    <section class="crm-panel">
      <div class="toolbar">
        <div class="filters">
          <el-radio-group v-model="scope" @change="reload">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="mine">我的</el-radio-button>
          </el-radio-group>
          <el-select v-model="status" clearable placeholder="状态" style="width: 120px" @change="reload">
            <el-option
              v-for="(label, key) in PAYMENT_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-select v-model="dueStatus" clearable placeholder="到期情况" style="width: 130px" @change="reload">
            <el-option label="逾期" value="overdue" />
            <el-option label="即将到期" value="due_soon" />
            <el-option label="已到期" value="due" />
            <el-option label="未到期" value="not_due" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索合同/款项"
            clearable
            style="width: 200px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">登记应收</el-button>
      </div>

      <div class="crm-table-wrap">
        <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="款项" width="120" show-overflow-tooltip />
          <el-table-column prop="contract_no" label="合同编号" width="140" />
          <el-table-column prop="customer_name" label="客户" min-width="120" show-overflow-tooltip />
          <el-table-column label="金额" width="120">
            <template #default="{ row }">{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="due_date" label="应收日期" width="110" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">
                {{ PAYMENT_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="到期情况" width="100">
            <template #default="{ row }">
              <el-tag :type="dueTag(row.due_status)" size="small">
                {{ DUE_STATUS_LABEL[row.due_status || ''] || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="owner_name" label="登记人" width="100" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
              <el-button
                v-if="row.status === 'pending'"
                link
                type="success"
                @click.stop="quickConfirm(row)"
              >
                确认
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :layout="isCompact ? 'prev, pager, next' : 'total, prev, pager, next'"
          :pager-count="isCompact ? 5 : 7"
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </section>

    <el-dialog
      v-model="createVisible"
      title="登记应收"
      width="560px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :label-width="isCompact ? 'auto' : '100px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <el-form-item label="合同" prop="contract_id">
          <el-select
            v-model="form.contract_id"
            filterable
            remote
            :remote-method="searchContracts"
            :loading="contractLoading"
            placeholder="搜索合同编号/名称"
            style="width: 100%"
          >
            <el-option
              v-for="c in contractOptions"
              :key="c.id"
              :label="`${c.contract_no} · ${c.title}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="款项名称">
          <el-input v-model="form.title" placeholder="如：首付款 / 第二期" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="应收日期">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="form.method" clearable style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  DUE_STATUS_LABEL,
  PAYMENT_METHOD_OPTIONS,
  PAYMENT_STATUS_LABEL,
  confirmPayment,
  createPayment,
  fetchPaymentStats,
  fetchPayments,
  type Payment,
  type PaymentStats,
} from '@/api/payments'
import { fetchContracts, type Contract } from '@/api/contracts'

const router = useRouter()
const isCompact = useMatchMedia('(max-width: 768px)')
const loading = ref(false)
const saving = ref(false)
const contractLoading = ref(false)
const items = ref<Payment[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('all')
const status = ref<string | undefined>()
const dueStatus = ref<string | undefined>()
const keyword = ref('')
const stats = ref<PaymentStats | null>(null)
const contractOptions = ref<Contract[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  contract_id: undefined as number | undefined,
  title: '',
  amount: 0,
  due_date: '',
  method: '',
  remark: '',
})
const rules: FormRules = {
  contract_id: [{ required: true, message: '请选择合同', trigger: 'change' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
}

const statCards = computed(() => {
  const s = stats.value
  return [
    { key: 'total', label: '全部', value: s?.total ?? 0 },
    { key: 'pending', label: '待收款', value: s?.pending ?? 0, status: 'pending' },
    { key: 'overdue', label: '逾期', value: s?.overdue ?? 0, due_status: 'overdue' },
    { key: 'confirmed', label: '已确认', value: s?.confirmed ?? 0, status: 'confirmed' },
    {
      key: 'pending_amount',
      label: '待收金额',
      value: formatAmount(s?.pending_amount ?? 0),
      status: 'pending',
    },
    {
      key: 'confirmed_amount',
      label: '已收金额',
      value: formatAmount(s?.confirmed_amount ?? 0),
      status: 'confirmed',
    },
  ]
})

function formatAmount(v: number | string) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : String(v)
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
    pending: '',
  }
  return map[s || ''] || 'info'
}

function onStatClick(item: { status?: string; due_status?: string }) {
  status.value = item.status
  dueStatus.value = item.due_status
  page.value = 1
  reload()
}

async function searchContracts(q: string) {
  contractLoading.value = true
  try {
    const { data } = await fetchContracts({ keyword: q || undefined, page: 1, page_size: 20 })
    contractOptions.value = data.items
  } finally {
    contractLoading.value = false
  }
}

async function loadStats() {
  const { data } = await fetchPaymentStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchPayments({
      scope: scope.value,
      status: status.value,
      due_status: dueStatus.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  loadList()
  loadStats()
}

function goDetail(row: Payment) {
  router.push(`/payments/${row.id}`)
}

async function openCreate() {
  form.contract_id = undefined
  form.title = ''
  form.amount = 0
  form.due_date = ''
  form.method = ''
  form.remark = ''
  await searchContracts('')
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.contract_id) return
  saving.value = true
  try {
    await createPayment({
      contract_id: form.contract_id,
      title: form.title || undefined,
      amount: form.amount,
      due_date: form.due_date || undefined,
      method: form.method || undefined,
      remark: form.remark || undefined,
    })
    ElMessage.success('已登记')
    createVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

async function quickConfirm(row: Payment) {
  try {
    await ElMessageBox.confirm(`确认到账「${formatAmount(row.amount)}」？`, '确认收款')
    await confirmPayment(row.id)
    ElMessage.success('已确认到账')
    reload()
  } catch {
    /* cancel */
  }
}

onMounted(() => {
  reload()
})
</script>

<style scoped>
.crm-table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
@media (max-width: 768px) {
  .pager {
    justify-content: center;
    overflow-x: auto;
  }
}
</style>

