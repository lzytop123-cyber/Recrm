"""
仅线索录入落地页：部门负责人 / 品宣 / 财务 / 综合管理主管 / 资产管理员等非销售岗。
"""
<template>
  <div class="crm-page lead-entry-page">
    <header class="entry-head">
      <div>
        <h1>线索录入</h1>
        <p>所有员工均可提交潜在客户信息；提交后按岗位权限进入对应流转。</p>
      </div>
      <div class="entry-actions">
        <el-button @click="importVisible = true">批量导入</el-button>
        <el-button type="primary" @click="openCreate">＋ 录入线索</el-button>
      </div>
    </header>

    <section class="entry-card">
      <h2>你当前只有线索录入权限</h2>
      <p>
        所有岗位录入后均进入管理层线索总览待分配池，由管理层统一分配。
      </p>
      <p>你不能查看未授权的线索、客户、商机、合同或回款数据。</p>
      <div class="entry-card-actions">
        <el-button type="primary" size="large" @click="openCreate">录入一条线索</el-button>
        <el-button size="large" @click="importVisible = true">批量导入</el-button>
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

    <LeadImportDialog v-model:visible="importVisible" :self-follow="false" />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { checkLeadDuplicates, createLead } from '@/api/leads'
import { useBusinessTypes } from '@/api/dictionaries'
import { useUserStore } from '@/stores/user'
import LeadImportDialog from '@/components/leads/LeadImportDialog.vue'

const { businessTypeOptions } = useBusinessTypes()
const userStore = useUserStore()
/** 与后端 can_self_follow_on_create 一致：销售录入自跟进，其他岗进待分配池 */
const canSelfFollowOnCreate = computed(() =>
  (userStore.user?.roles ?? []).some(
    (r) => r.code === 'sales' || (r.name ?? '').includes('销售'),
  ),
)

const createVisible = ref(false)
const importVisible = ref(false)
const saving = ref(false)
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
      } catch {
        /* cancel */
      }
    } else {
      ElMessage.error(err.response?.data?.detail || '提交失败')
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.lead-entry-page {
  max-width: 960px;
}

.entry-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
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

.entry-card {
  background: #fff;
  border: 1px solid var(--crm-border);
  border-radius: 16px;
  padding: 48px 36px;
  text-align: center;
  box-shadow: 0 8px 28px rgb(15 23 42 / 4%);
}

.entry-card h2 {
  margin: 0 0 14px;
  font-size: 22px;
  color: var(--crm-ink);
}

.entry-card p {
  margin: 0 auto 10px;
  max-width: 520px;
  color: var(--crm-ink-soft);
  font-size: 14px;
  line-height: 1.65;
}

.entry-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 18px;
}

.entry-card .el-button {
  margin-top: 0;
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
