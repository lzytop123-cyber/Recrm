<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/customers')">返回列表</el-button>
      <div class="actions" v-if="customer">
        <el-button type="primary" @click="editVisible = true">编辑</el-button>
        <el-button @click="followVisible = true">写跟进</el-button>
        <el-button @click="$router.push(`/sales?tab=customers&customer_id=${customer.id}`)">关联商机</el-button>
      </div>
    </div>

    <template v-if="customer">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>客户 #{{ customer.id }} · {{ customer.name }}</span>
            <el-tag :type="statusTag(customer.status)" size="small">
              {{ CUSTOMER_STATUS_LABEL[customer.status] || customer.status }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="客户名称">{{ customer.name }}</el-descriptions-item>
          <el-descriptions-item label="简称">{{ customer.short_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系人">{{ customer.contact_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ customer.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ customer.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ customer.industry || '-' }}</el-descriptions-item>
          <el-descriptions-item label="规模">{{ sizeLabel(customer.company_size) }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ sourceLabel(customer.source) }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ customer.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ customer.creator_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最近跟进">{{ formatTime(customer.last_followed_at) }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="3">{{ customer.address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ customer.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="customer.source_lead_id" label="来源线索">
            <el-button link type="primary" @click="$router.push(`/leads/${customer.source_lead_id}`)">
              #{{ customer.source_lead_id }}
            </el-button>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="stack-gap">
        <template #header>跟进记录</template>
        <el-timeline v-if="customer.follow_ups?.length">
          <el-timeline-item
            v-for="fu in customer.follow_ups"
            :key="fu.id"
            :timestamp="formatTime(fu.follow_at)"
            placement="top"
          >
            <div class="fu-item">
              <el-tag size="small">{{ fu.method }}</el-tag>
              <span class="muted">{{ fu.user_name || `用户#${fu.user_id}` }}</span>
              <p>{{ fu.content }}</p>
              <p v-if="fu.next_follow_at" class="muted">下次跟进：{{ formatTime(fu.next_follow_at) }}</p>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无跟进记录" :image-size="64" />
      </el-card>
    </template>

    <el-dialog v-model="editVisible" title="编辑客户" width="560px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="客户名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="editForm.short_name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="editForm.contact_name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="editForm.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="editForm.industry" />
        </el-form-item>
        <el-form-item label="规模">
          <el-select v-model="editForm.company_size" clearable style="width: 100%">
            <el-option
              v-for="opt in COMPANY_SIZE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option
              v-for="(label, key) in CUSTOMER_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="editForm.address" />
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

    <el-dialog v-model="followVisible" title="写跟进" width="520px">
      <el-form :model="followForm" label-width="90px">
        <el-form-item label="方式">
          <el-select v-model="followForm.method" style="width: 100%">
            <el-option label="电话" value="phone" />
            <el-option label="微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="面谈" value="meeting" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <el-input v-model="followForm.content" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onFollow">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  COMPANY_SIZE_OPTIONS,
  CUSTOMER_SOURCE_OPTIONS,
  CUSTOMER_STATUS_LABEL,
  createCustomerFollowUp,
  fetchCustomerDetail,
  updateCustomer,
  type CustomerDetail,
} from '@/api/customers'

const route = useRoute()
const loading = ref(false)
const saving = ref(false)
const customer = ref<CustomerDetail | null>(null)
const editVisible = ref(false)
const followVisible = ref(false)

const editForm = reactive({
  name: '',
  short_name: '',
  contact_name: '',
  phone: '',
  email: '',
  industry: '',
  company_size: '' as string | undefined,
  status: 'potential',
  address: '',
  remark: '',
})

const followForm = reactive({
  method: 'phone',
  content: '',
})

const customerId = computed(() => Number(route.params.id))

function sourceLabel(code?: string | null) {
  if (!code) return '-'
  return CUSTOMER_SOURCE_OPTIONS.find((x) => x.value === code)?.label || code
}

function sizeLabel(code?: string | null) {
  if (!code) return '-'
  return COMPANY_SIZE_OPTIONS.find((x) => x.value === code)?.label || code
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

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function fillEditForm() {
  if (!customer.value) return
  const c = customer.value
  editForm.name = c.name
  editForm.short_name = c.short_name || ''
  editForm.contact_name = c.contact_name || ''
  editForm.phone = c.phone || ''
  editForm.email = c.email || ''
  editForm.industry = c.industry || ''
  editForm.company_size = c.company_size || undefined
  editForm.status = c.status
  editForm.address = c.address || ''
  editForm.remark = c.remark || ''
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchCustomerDetail(customerId.value)
    customer.value = data
    fillEditForm()
  } finally {
    loading.value = false
  }
}

watch(editVisible, (v) => {
  if (v) fillEditForm()
})

async function onSaveEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('客户名称不能为空')
    return
  }
  saving.value = true
  try {
    await updateCustomer(customerId.value, {
      ...editForm,
      company_size: editForm.company_size || undefined,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onFollow() {
  if (!followForm.content.trim()) {
    ElMessage.warning('请填写沟通内容')
    return
  }
  saving.value = true
  try {
    await createCustomerFollowUp(customerId.value, { ...followForm })
    ElMessage.success('跟进已记录')
    followVisible.value = false
    followForm.content = ''
    await loadDetail()
  } finally {
    saving.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.fu-item p {
  margin: 6px 0 0;
}
</style>
