<template>
  <div class="crm-page customers-page">
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
          <el-select v-model="status" clearable placeholder="状态" style="width: 140px" @change="reload">
            <el-option
              v-for="(label, key) in CUSTOMER_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索名称/联系人/电话"
            clearable
            style="width: 220px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">录入客户</el-button>
      </div>

      <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="客户名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="contact_name" label="联系人" width="100" />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column prop="industry" label="行业" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">
              {{ CUSTOMER_STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="负责人" width="100" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </section>

    <el-dialog v-model="createVisible" title="录入客户" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="form.name" placeholder="公司全称，必填" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="form.short_name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="form.industry" />
        </el-form-item>
        <el-form-item label="规模">
          <el-select v-model="form.company_size" clearable style="width: 100%">
            <el-option
              v-for="opt in COMPANY_SIZE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" style="width: 100%">
            <el-option
              v-for="opt in CUSTOMER_SOURCE_OPTIONS"
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
import { ElMessage } from 'element-plus'
import {
  COMPANY_SIZE_OPTIONS,
  CUSTOMER_SOURCE_OPTIONS,
  CUSTOMER_STATUS_LABEL,
  createCustomer,
  fetchCustomerStats,
  fetchCustomers,
  type Customer,
  type CustomerStats,
} from '@/api/customers'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const items = ref<Customer[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('all')
const status = ref<string | undefined>()
const keyword = ref('')
const stats = ref<CustomerStats | null>(null)

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  short_name: '',
  contact_name: '',
  phone: '',
  industry: '',
  company_size: '',
  source: 'manual',
  remark: '',
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
}

const statCards = computed(() => {
  const s = stats.value
  return [
    { key: 'total', label: '全部', value: s?.total ?? 0, scope: 'all', status: undefined },
    { key: 'mine', label: '我的', value: s?.mine ?? 0, scope: 'mine', status: undefined },
    { key: 'potential', label: '潜在', value: s?.potential ?? 0, scope: 'all', status: 'potential' },
    { key: 'active', label: '合作中', value: s?.active ?? 0, scope: 'all', status: 'active' },
    { key: 'paused', label: '暂停', value: s?.paused ?? 0, scope: 'all', status: 'paused' },
    { key: 'terminated', label: '终止', value: s?.terminated ?? 0, scope: 'all', status: 'terminated' },
  ]
})

function sourceLabel(code?: string | null) {
  if (!code) return '-'
  return CUSTOMER_SOURCE_OPTIONS.find((x) => x.value === code)?.label || code
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    potential: 'info',
    active: 'success',
    paused: 'warning',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function onStatClick(item: { scope?: string; status?: string }) {
  if (item.scope) scope.value = item.scope
  status.value = item.status
  page.value = 1
  reload()
}

async function loadStats() {
  const { data } = await fetchCustomerStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchCustomers({
      scope: scope.value,
      status: status.value,
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

function goDetail(row: Customer) {
  router.push(`/customers/${row.id}`)
}

function openCreate() {
  form.name = ''
  form.short_name = ''
  form.contact_name = ''
  form.phone = ''
  form.industry = ''
  form.company_size = ''
  form.source = 'manual'
  form.remark = ''
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createCustomer({
      ...form,
      company_size: form.company_size || undefined,
    })
    ElMessage.success('录入成功')
    createVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  reload()
})
</script>


