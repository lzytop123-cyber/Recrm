"""
仅线索录入落地页：部门负责人 / 品宣 / 财务 / 综合管理主管 / 资产管理员等非销售岗。
"""
<template>
  <div class="crm-page lead-entry-page">
    <header class="entry-head">
      <div>
        <h1>线索录入</h1>
        <p>提交后进入管理层待分配池。本页只显示你自己录入的线索，其他人的记录不可见。</p>
      </div>
      <div class="entry-actions">
        <el-button @click="importVisible = true">批量导入</el-button>
        <el-button type="primary" @click="openCreate">＋ 录入线索</el-button>
      </div>
    </header>

    <section class="crm-panel my-leads-panel">
      <div class="toolbar">
        <strong>我录入的线索</strong>
        <span class="muted">共 {{ total }} 条</span>
      </div>
      <div class="crm-table-wrap">
        <el-table
          :data="items"
          v-loading="loading"
          stripe
          empty-text="还没有录入记录，点击右上角开始提交"
          @row-click="goDetail"
        >
          <el-table-column label="客户主体" min-width="180">
            <template #default="{ row }">
              <div class="entity">
                <b>{{ row.company_name || row.name }}</b>
                <small>XS-{{ String(row.id).padStart(6, '0') }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="联系电话" width="130" />
          <el-table-column label="需求方向" width="130">
            <template #default="{ row }">{{ businessTypeLabel(row.business_type) }}</template>
          </el-table-column>
          <el-table-column label="录入来源" width="120">
            <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">
                {{ LEAD_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="当前负责人" width="120">
            <template #default="{ row }">
              {{ isUnassigned(row) ? '尚未分配' : row.owner_name || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="录入时间" width="150">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadMyLeads"
          @size-change="loadMyLeads"
        />
      </div>
    </section>
    <el-dialog
      v-model="createVisible"
      title="新增线索"
      width="720px"
      destroy-on-close
      class="lead-create-dialog"
    >
      <p class="dialog-eyebrow">录入线索</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="lead-create-form">
        <section class="form-block">
          <h3><span>1</span>客户信息</h3>
          <el-form-item label="客户主体" prop="company_name">
            <el-input v-model="form.company_name" placeholder="请输入企业或客户名称" @input="scheduleDupCheck" />
            <div class="field-hint">系统按主体名称、统一社会信用代码、手机号和企业域名组合自动查重。</div>
          </el-form-item>
          <div class="form-grid-2">
            <el-form-item label="统一社会信用代码">
              <el-input v-model="form.credit_code" placeholder="选填" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="企业域名">
              <el-input v-model="form.company_domain" placeholder="例如 example.com" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="联系人">
              <el-input v-model="form.name" placeholder="姓名" />
            </el-form-item>
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="form.phone" placeholder="手机号" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="需求方向" prop="business_type">
              <el-select v-model="form.business_type" style="width: 100%">
                <el-option
                  v-for="opt in businessTypeOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="录入来源" prop="source">
              <el-select v-model="form.source" style="width: 100%">
                <el-option
                  v-for="opt in leadSourceOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="录入人">
              <el-input :model-value="recorderName" disabled />
            </el-form-item>
          </div>
        </section>

        <section class="form-block">
          <h3><span>2</span>自动实时查重</h3>
          <div class="duplicate-result" :class="dupState">
            <span class="duplicate-mark">{{ dupMark }}</span>
            <div>
              <b>{{ dupTitle }}</b>
              <small>{{ dupDesc }}</small>
            </div>
          </div>
        </section>

        <section class="form-block">
          <h3><span>3</span>提交检查</h3>
          <div class="health-list">
            <div class="health-row">
              <span>{{ form.company_name.trim() ? '✓' : '⚠' }} 客户主体</span>
              <b>{{ form.company_name.trim() ? '已填写' : '待填写' }}</b>
            </div>
            <div class="health-row">
              <span>{{ form.phone.trim() ? '✓' : '⚠' }} 联系电话</span>
              <b>{{ form.phone.trim() ? '已填写' : '待填写' }}</b>
            </div>
            <div class="health-row">
              <span>{{ dupChecked ? '✓' : 'ⓘ' }} 自动查重</span>
              <b>{{ checkStatusText }}</b>
            </div>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!canSubmitLead" @click="onCreate">
          提交线索
        </el-button>
      </template>
    </el-dialog>

    <LeadImportDialog v-model:visible="importVisible" :self-follow="false" @done="loadMyLeads" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { notifyError } from '@/utils/notify'
import {
  LEAD_STATUS_LABEL,
  checkLeadDuplicates,
  createLead,
  fetchLeads,
  type Lead,
} from '@/api/leads'
import { useBusinessTypes, useLeadSources } from '@/api/dictionaries'
import { useUserStore } from '@/stores/user'
import LeadImportDialog from '@/components/leads/LeadImportDialog.vue'

const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()
const { leadSourceOptions, leadSourceLabel } = useLeadSources()
const userStore = useUserStore()
const router = useRouter()
/** 与后端 can_self_follow_on_create 一致：销售录入自跟进，其他岗进待分配池 */
const canSelfFollowOnCreate = computed(() =>
  (userStore.user?.roles ?? []).some(
    (r) => r.code === 'sales' || (r.name ?? '').includes('销售'),
  ),
)

const createVisible = ref(false)
const importVisible = ref(false)
const saving = ref(false)
const loading = ref(false)
const items = ref<Lead[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  company_name: '',
  credit_code: '',
  company_domain: '',
  phone: '',
  business_type: 'ai_product',
  source: 'manual',
})
const rules: FormRules = {
  company_name: [{ required: true, message: '请填写客户主体', trigger: 'blur' }],
  phone: [{ required: true, message: '请填写联系电话', trigger: 'blur' }],
  business_type: [{ required: true, message: '请选择需求方向', trigger: 'change' }],
  source: [{ required: true, message: '请选择录入来源', trigger: 'change' }],
}

const dupChecking = ref(false)
const dupChecked = ref(false)
const dupReview = ref(false)
const dupHard = ref(false)
let dupTimer: ReturnType<typeof setTimeout> | null = null
let dupVersion = 0

const recorderName = computed(
  () => userStore.user?.real_name || userStore.user?.username || '当前用户',
)
const canSubmitLead = computed(
  () =>
    !!form.company_name.trim() &&
    !!form.phone.trim() &&
    !!form.business_type &&
    dupChecked.value &&
    !dupChecking.value,
)
const checkStatusText = computed(() => {
  if (dupChecking.value) return '正在自动查重'
  if (dupChecked.value) {
    if (dupHard.value) return '确定重复，需确认后强制提交'
    if (dupReview.value) return '疑似重复，转人工复核'
    return '未发现确定重复'
  }
  if (form.company_name.trim() && form.phone.trim()) return '等待自动查重'
  return '待填写'
})
const dupState = computed(() => {
  if (dupChecking.value) return 'checking'
  if (!dupChecked.value) return ''
  if (dupHard.value) return 'hard'
  if (dupReview.value) return 'soft'
  return 'ok'
})
const dupMark = computed(() => {
  if (dupChecking.value) return '…'
  if (!dupChecked.value) return '查'
  if (dupHard.value) return '!'
  if (dupReview.value) return '?'
  return '✓'
})
const dupTitle = computed(() => {
  if (dupChecking.value) return '正在查重'
  if (!dupChecked.value) return '等待输入客户信息'
  if (dupHard.value) return '发现确定重复'
  if (dupReview.value) return '发现疑似重复'
  return '未发现确定重复'
})
const dupDesc = computed(() => {
  if (dupChecking.value) return '正在按主体、信用代码、手机号和域名匹配。'
  if (!dupChecked.value) return '填写客户主体和联系电话后，系统自动执行查重。'
  if (dupHard.value) return '手机号或信用代码与已有线索冲突，确认后可强制录入。'
  if (dupReview.value) return '公司名或域名相近，提交后进入人工复核留痕。'
  return '可以继续提交。'
})

function isUnassigned(row: Lead) {
  return row.status === 'pending_assign' || row.status === 'returned'
}

function sourceLabel(code?: string | null) {
  return leadSourceLabel(code)
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    pending_assign: 'warning',
    assigned: 'success',
    following: 'success',
    converted: 'success',
    returned: 'warning',
    lost: 'danger',
  }
  return map[s] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  return new Date(v).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadMyLeads() {
  loading.value = true
  try {
    const { data } = await fetchLeads({
      pool: 'created',
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function goDetail(row: Lead) {
  router.push(`/leads/${row.id}`)
}

function openCreate() {
  form.name = ''
  form.company_name = ''
  form.credit_code = ''
  form.company_domain = ''
  form.phone = ''
  form.business_type = 'ai_product'
  form.source = 'manual'
  dupChecking.value = false
  dupChecked.value = false
  dupReview.value = false
  dupHard.value = false
  createVisible.value = true
}

function scheduleDupCheck() {
  if (dupTimer) clearTimeout(dupTimer)
  dupVersion += 1
  dupChecked.value = false
  dupReview.value = false
  dupHard.value = false
  const ready = !!form.company_name.trim() && !!form.phone.trim()
  if (!ready) {
    dupChecking.value = false
    return
  }
  dupChecking.value = true
  const version = dupVersion
  dupTimer = setTimeout(() => {
    void runDupCheck(version)
  }, 450)
}

async function runDupCheck(version: number) {
  try {
    const { data } = await checkLeadDuplicates({
      phone: form.phone.trim() || undefined,
      company_name: form.company_name.trim() || undefined,
      credit_code: form.credit_code.trim() || undefined,
      company_domain: form.company_domain.trim() || undefined,
    })
    if (version !== dupVersion) return
    dupChecked.value = true
    dupHard.value = !!data.is_hard_duplicate
    dupReview.value = !!data.has_duplicate && !data.is_hard_duplicate
  } catch {
    if (version !== dupVersion) return
    dupChecked.value = true
    dupHard.value = false
    dupReview.value = false
  } finally {
    if (version === dupVersion) dupChecking.value = false
  }
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !canSubmitLead.value) return
  saving.value = true
  try {
    const payload = {
      name: form.name.trim() || undefined,
      company_name: form.company_name.trim(),
      credit_code: form.credit_code.trim() || undefined,
      company_domain: form.company_domain.trim() || undefined,
      phone: form.phone.trim(),
      business_type: form.business_type,
      source: form.source,
      self_follow: canSelfFollowOnCreate.value,
    }
    if (dupHard.value) {
      await ElMessageBox.confirm(
        '存在确定重复线索。确认强制录入？不会自动合并已有记录。',
        '重复提示',
        { type: 'warning' },
      )
      await createLead(payload, true)
    } else {
      await createLead(payload)
    }
    ElMessage.success('录入成功，已进入管理层待分配池')
    createVisible.value = false
    await loadMyLeads()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      try {
        await ElMessageBox.confirm(err.response.data?.detail || '存在重复，是否强制创建？', '重复提示', {
          type: 'warning',
        })
        await createLead(
          {
            name: form.name.trim() || undefined,
            company_name: form.company_name.trim(),
            credit_code: form.credit_code.trim() || undefined,
            company_domain: form.company_domain.trim() || undefined,
            phone: form.phone.trim(),
            business_type: form.business_type,
            source: form.source,
            self_follow: canSelfFollowOnCreate.value,
          },
          true,
        )
        ElMessage.success('已强制录入')
        createVisible.value = false
        await loadMyLeads()
      } catch {
        /* cancel */
      }
    } else {
      notifyError(err, '提交失败')
    }
  } finally {
    saving.value = false
  }
}

onMounted(loadMyLeads)
</script>

<style scoped>
.lead-entry-page {
  max-width: 1100px;
}

.entry-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.entry-head h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: var(--crm-ink);
}

.entry-head p {
  margin: 8px 0 0;
  color: var(--crm-ink-soft);
  font-size: 14px;
  line-height: 1.5;
}

.my-leads-panel .toolbar {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.my-leads-panel .toolbar strong {
  font-size: 15px;
}

.muted {
  color: var(--crm-ink-soft);
  font-size: 13px;
}

.entity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.entity small {
  color: var(--crm-ink-soft);
  font-size: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.my-leads-panel :deep(.el-table__row) {
  cursor: pointer;
}

.dialog-eyebrow {
  margin: 0 0 12px;
  color: var(--crm-ink-soft);
  font-size: 13px;
}

.form-block {
  margin-bottom: 18px;
}

.form-block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 15px;
}

.form-block h3 span {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: oklch(0.35 0.06 250);
  color: #fff;
  font-size: 12px;
}

.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}

.field-hint {
  margin-top: 4px;
  color: var(--crm-ink-soft);
  font-size: 12px;
}

.duplicate-result {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 10px;
  background: oklch(0.97 0.01 250);
}

.duplicate-result.ok {
  background: oklch(0.96 0.03 150);
}

.duplicate-result.soft {
  background: oklch(0.97 0.04 90);
}

.duplicate-result.hard {
  background: oklch(0.96 0.04 25);
}

.duplicate-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  font-weight: 700;
}

.duplicate-result b {
  display: block;
}

.duplicate-result small {
  color: var(--crm-ink-soft);
}

.health-list {
  display: grid;
  gap: 8px;
}

.health-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--crm-border);
  font-size: 13px;
}

@media (max-width: 720px) {
  .entry-head {
    flex-direction: column;
  }

  .form-grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
