<template>
  <div class="crm-page opportunities-page" :class="{ embedded }">
    <div class="crm-stats" :style="{ '--crm-stats-cols': '4' }">
      <div class="crm-stat-tile is-static">
        <span>有效客户</span>
        <strong>{{ stats?.customer_count ?? 0 }}</strong>
        <em>潜在与合作客户合计</em>
      </div>
      <div class="crm-stat-tile is-static">
        <span>进行中商机</span>
        <strong>{{ stats?.open_count ?? 0 }}</strong>
        <em>预计金额 ¥{{ formatAmount(stats?.open_amount) }}</em>
      </div>
      <div class="crm-stat-tile is-static">
        <span>赢单合同额</span>
        <strong>¥{{ formatAmount(stats?.won_amount) }}</strong>
        <em>待生成合同 {{ stats?.pending_contract ?? 0 }} 单</em>
      </div>
      <div class="crm-stat-tile is-static">
        <span>逾期销售动作</span>
        <strong :class="{ danger: (stats?.overdue_actions ?? 0) > 0 }">{{ stats?.overdue_actions ?? 0 }}</strong>
        <em>按下一步计划统计</em>
      </div>
    </div>

    <section class="crm-panel" :class="{ 'crm-fit-panel': embedded }">
      <div class="toolbar">
        <div class="filters">
          <el-input
            v-model="keyword"
            placeholder="搜索客户、商机或负责人"
            clearable
            style="width: 240px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-select v-model="stage" clearable placeholder="全部销售阶段" style="width: 160px" @change="reload">
            <el-option label="需求确认" value="need_confirm" />
            <el-option label="方案报价" value="proposal" />
            <el-option label="商务谈判" value="negotiation" />
            <el-option label="赢单" value="won" />
            <el-option label="输单" value="lost" />
          </el-select>
          <el-button @click="reload">查询</el-button>
        </div>
        <el-button v-if="!embedded" type="primary" @click="openCreate">＋ 新建商机</el-button>
      </div>

      <div class="crm-table-wrap" :class="{ 'is-fit': embedded && !isCompact }">
        <el-table
          :data="items"
          v-loading="loading"
          stripe
          :height="embedded && !isCompact ? '100%' : undefined"
          @row-click="goDetail"
        >
        <el-table-column label="商机" min-width="220">
          <template #default="{ row }">
            <div class="entity">
              <span class="entity-icon">{{ entityIcon(row.opportunity_no) }}</span>
              <span class="entity-text">
                <b>{{ row.title }}</b>
                <small>{{ row.opportunity_no }}</small>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户主体" min-width="120" show-overflow-tooltip />
        <el-table-column label="业务类型" width="120">
          <template #default="{ row }">{{ typeLabel(row.business_type) }}</template>
        </el-table-column>
        <el-table-column label="销售阶段" width="110">
          <template #default="{ row }">
            <el-tag :type="stageTag(row.stage)" size="small">
              {{ OPP_STAGE_LABEL[row.stage] || row.stage }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预计金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.expected_amount) }}</template>
        </el-table-column>
        <el-table-column label="下一销售动作" min-width="140">
          <template #default="{ row }">
            <span v-if="row.next_action_note || row.next_action_at">
              {{ row.next_action_note || formatDate(row.next_action_at) }}
            </span>
            <span v-else class="muted">待安排</span>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="负责人" width="100" />
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="priorityTag(row.stage)" size="small" effect="plain">
              {{ priorityLabel(row.stage) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <div class="table-footer">
        <span>共 {{ total }} 个商机，本页显示 {{ items.length }} 条</span>
        <span class="muted">金额为销售预测，不等同于合同收入</span>
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
      title="创建客户商机"
      width="640px"
      destroy-on-close
      :fullscreen="isCompact"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        :label-width="isCompact ? 'auto' : '110px'"
        :label-position="isCompact ? 'top' : 'right'"
      >
        <p class="form-section">客户与负责人</p>
        <el-form-item label="客户主体" prop="customer_id">
          <el-select
            v-model="form.customer_id"
            filterable
            remote
            reserve-keyword
            placeholder="请选择已有客户"
            :remote-method="searchCustomers"
            :loading="customerLoading"
            style="width: 100%"
          >
            <el-option
              v-for="c in customerOptions"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
          <div class="field-hint">商机必须关联已完成查重的客户主体。</div>
        </el-form-item>
        <el-form-item label="业务类型" prop="business_type">
          <el-select v-model="form.business_type" style="width: 100%">
            <el-option
              v-for="opt in BUSINESS_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <p class="form-section">商机信息</p>
        <el-form-item label="商机名称" prop="title">
          <el-input v-model="form.title" placeholder="客户主体 + 需求项目" />
        </el-form-item>
        <el-form-item label="初始阶段" prop="stage">
          <el-select v-model="form.stage" style="width: 100%">
            <el-option label="需求确认" value="need_confirm" />
            <el-option label="方案报价" value="proposal" />
            <el-option label="商务谈判" value="negotiation" />
          </el-select>
        </el-form-item>
        <el-form-item label="预计金额">
          <el-input-number v-model="form.expected_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="需求与成交依据" prop="requirement_summary">
          <el-input
            v-model="form.requirement_summary"
            type="textarea"
            :rows="3"
            placeholder="记录需求范围、决策人、预算或关键时间点"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">创建商机</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import { fetchCustomers, type Customer } from '@/api/customers'
import {
  BUSINESS_TYPE_OPTIONS,
  OPP_STAGE_LABEL,
  createOpportunity,
  fetchOpportunities,
  fetchOpportunityStats,
  type Opportunity,
  type OpportunityStats,
} from '@/api/opportunities'

const props = withDefaults(
  defineProps<{
    embedded?: boolean
    openCreateSignal?: number
  }>(),
  { embedded: false, openCreateSignal: 0 },
)

const router = useRouter()
const route = useRoute()
const isCompact = useMatchMedia('(max-width: 768px)')
const loading = ref(false)
const saving = ref(false)
const customerLoading = ref(false)
const items = ref<Opportunity[]>([])
const customerOptions = ref<Customer[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const stage = ref<string | undefined>()
const keyword = ref('')
const stats = ref<OpportunityStats | null>(null)
const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  title: '',
  customer_id: undefined as number | undefined,
  business_type: 'ai_product',
  stage: 'need_confirm',
  expected_amount: 0,
  requirement_summary: '',
})
const rules: FormRules = {
  title: [{ required: true, message: '请输入商机名称', trigger: 'blur' }],
  customer_id: [{ required: true, message: '请选择客户主体', trigger: 'change' }],
  business_type: [{ required: true, message: '请选择业务类型', trigger: 'change' }],
  stage: [{ required: true, message: '请选择初始阶段', trigger: 'change' }],
  requirement_summary: [{ required: true, message: '请填写需求与成交依据', trigger: 'blur' }],
}

function typeLabel(code?: string) {
  return BUSINESS_TYPE_OPTIONS.find((x) => x.value === code)?.label || code || '-'
}

function formatAmount(v?: number | string | null) {
  const n = Number(v || 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function formatDate(v?: string | null) {
  if (!v) return '-'
  return new Date(v).toLocaleDateString('zh-CN')
}

function entityIcon(no?: string) {
  return (no || 'SJ').slice(-2)
}

function stageTag(s: string) {
  const map: Record<string, string> = {
    need_confirm: 'info',
    proposal: '',
    negotiation: 'warning',
    won: 'success',
    lost: 'danger',
  }
  return map[s] || 'info'
}

function priorityLabel(s: string) {
  if (s === 'negotiation') return '高'
  if (s === 'proposal') return '中'
  return '中'
}

function priorityTag(s: string) {
  return s === 'negotiation' ? 'danger' : 'info'
}

async function searchCustomers(q: string) {
  customerLoading.value = true
  try {
    const { data } = await fetchCustomers({ keyword: q || undefined, page: 1, page_size: 30 })
    customerOptions.value = data.items
  } finally {
    customerLoading.value = false
  }
}

async function loadStats() {
  const { data } = await fetchOpportunityStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchOpportunities({
      stage: stage.value,
      keyword: keyword.value || undefined,
      customer_id: route.query.customer_id ? Number(route.query.customer_id) : undefined,
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

function goDetail(row: Opportunity) {
  router.push(`/opportunities/${row.id}`)
}

function openCreate() {
  form.title = ''
  form.customer_id = route.query.customer_id ? Number(route.query.customer_id) : undefined
  form.business_type = 'ai_product'
  form.stage = 'need_confirm'
  form.expected_amount = 0
  form.requirement_summary = ''
  searchCustomers('')
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.customer_id) return
  saving.value = true
  try {
    const { data } = await createOpportunity({
      title: form.title,
      customer_id: form.customer_id,
      business_type: form.business_type,
      stage: form.stage,
      expected_amount: form.expected_amount,
      requirement_summary: form.requirement_summary,
    })
    ElMessage.success('商机已创建，已关联客户主体并设置唯一主负责人')
    createVisible.value = false
    router.push(`/opportunities/${data.id}`)
  } finally {
    saving.value = false
  }
}

watch(
  () => props.openCreateSignal,
  (v, old) => {
    if (props.embedded && v && v !== old) openCreate()
  },
)

onMounted(() => {
  reload()
})
</script>

<style scoped>
.crm-stat-tile em {
  font-style: normal;
  font-size: 12px;
  color: var(--crm-ink-soft);
}
.entity {
  display: flex;
  align-items: center;
  gap: 10px;
}
.entity-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: oklch(0.94 0.02 250);
  color: oklch(0.4 0.06 250);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.entity-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.entity-text b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.entity-text small {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.table-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 12px;
  color: var(--crm-ink-soft);
}
.muted {
  color: var(--crm-ink-soft);
}
.form-section {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
}
.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--crm-ink-soft);
  line-height: 1.4;
}
.embedded .crm-stats {
  margin-bottom: 12px;
  flex-shrink: 0;
}
.embedded.opportunities-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.embedded.opportunities-page > .crm-panel {
  flex: 1 1 auto;
  min-height: 0;
}
.embedded.opportunities-page .crm-table-wrap.is-fit {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.embedded.opportunities-page .pager,
.embedded.opportunities-page .table-footer {
  flex-shrink: 0;
}
@media (max-width: 768px) {
  .embedded.opportunities-page {
    height: auto;
    overflow: visible;
  }
  .embedded.opportunities-page > .crm-panel {
    flex: none;
    overflow: visible;
  }
  .embedded.opportunities-page .crm-table-wrap.is-fit,
  .embedded.opportunities-page .crm-table-wrap {
    flex: none;
    overflow-x: auto;
    overflow-y: visible;
    -webkit-overflow-scrolling: touch;
  }
  .table-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .pager {
    justify-content: center;
    overflow-x: auto;
  }
}
</style>
