<template>
  <div class="crm-page projects-page">
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
          <el-select v-model="status" clearable placeholder="状态" style="width: 130px" @change="reload">
            <el-option
              v-for="(label, key) in PROJECT_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索编号/名称"
            clearable
            style="width: 200px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">项目立项</el-button>
      </div>

      <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
        <el-table-column prop="project_no" label="项目编号" width="150" />
        <el-table-column prop="name" label="项目名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" min-width="120" show-overflow-tooltip />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ typeLabel(row.project_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">
              {{ PROJECT_STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="manager_name" label="负责人" width="100" />
        <el-table-column label="操作" width="90" fixed="right">
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

    <el-dialog v-model="createVisible" title="项目立项" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="关联合同">
          <el-select
            v-model="form.contract_id"
            filterable
            remote
            clearable
            :remote-method="searchContracts"
            :loading="contractLoading"
            placeholder="可选，搜索合同"
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
        <el-form-item label="项目类型">
          <el-select v-model="form.project_type" style="width: 100%">
            <el-option
              v-for="opt in businessTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="计划开始">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划结束">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="交付范围">
          <el-input v-model="form.scope_desc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">立项</el-button>
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
  PROJECT_STATUS_LABEL,
  useBusinessTypes,
  createProject,
  fetchProjectStats,
  fetchProjects,
  type Project,
  type ProjectStats,
} from '@/api/projects'
import { fetchContracts, type Contract } from '@/api/contracts'

const router = useRouter()
const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()
const loading = ref(false)
const saving = ref(false)
const contractLoading = ref(false)
const items = ref<Project[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('all')
const status = ref<string | undefined>()
const keyword = ref('')
const stats = ref<ProjectStats | null>(null)
const contractOptions = ref<Contract[]>([])

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  contract_id: undefined as number | undefined,
  project_type: 'ai_custom',
  start_date: '',
  end_date: '',
  scope_desc: '',
  remark: '',
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
}

const statCards = computed(() => {
  const s = stats.value
  return [
    { key: 'total', label: '全部', value: s?.total ?? 0 },
    { key: 'initiating', label: '立项', value: s?.initiating ?? 0, status: 'initiating' },
    { key: 'planning', label: '计划中', value: s?.planning ?? 0, status: 'planning' },
    { key: 'executing', label: '执行中', value: s?.executing ?? 0, status: 'executing' },
    { key: 'accepting', label: '验收中', value: s?.accepting ?? 0, status: 'accepting' },
    { key: 'completed', label: '已完成', value: s?.completed ?? 0, status: 'completed' },
    { key: 'mine', label: '我的', value: s?.mine ?? 0, scope: 'mine' },
  ]
})

function typeLabel(code: string) {
  return businessTypeLabel(code)
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    initiating: 'info',
    planning: '',
    executing: 'warning',
    accepting: 'warning',
    accepted: 'success',
    completed: 'success',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function onStatClick(item: { status?: string; scope?: string }) {
  if (item.scope) scope.value = item.scope
  else scope.value = 'all'
  status.value = item.status
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
  const { data } = await fetchProjectStats()
  stats.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchProjects({
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

function goDetail(row: Project) {
  router.push(`/projects/${row.id}`)
}

async function openCreate() {
  form.name = ''
  form.contract_id = undefined
  form.project_type = 'ai_custom'
  form.start_date = ''
  form.end_date = ''
  form.scope_desc = ''
  form.remark = ''
  await searchContracts('')
  createVisible.value = true
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createProject({
      name: form.name,
      contract_id: form.contract_id,
      project_type: form.project_type,
      start_date: form.start_date || undefined,
      end_date: form.end_date || undefined,
      scope_desc: form.scope_desc || undefined,
      remark: form.remark || undefined,
    })
    ElMessage.success('立项成功')
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


