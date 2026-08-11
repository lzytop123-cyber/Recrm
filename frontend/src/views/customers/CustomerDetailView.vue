<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/customers')">返回列表</el-button>
      <div class="actions" v-if="customer">
        <el-button v-perm="'customer:manage'" type="primary" @click="editVisible = true">编辑</el-button>
        <el-button v-perm="'customer:manage'" @click="openFollow">客户跟进</el-button>
        <el-button
          v-perm="'opportunity:manage'"
          @click="
            $router.push({
              path: '/sales',
              query: { tab: 'opportunities', customer_id: String(customer.id), create: '1' },
            })
          "
        >
          新建商机
        </el-button>
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
          <el-descriptions-item label="最近活动">
            {{ formatTime(customer.last_activity_at || customer.last_followed_at) }}
          </el-descriptions-item>
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
        <template #header>
          <div class="card-header">
            <span>关联商机</span>
            <span class="muted">一客户可挂多单；推进阶段请进商机详情</span>
          </div>
        </template>
        <el-table
          v-if="customer.opportunities?.length"
          :data="customer.opportunities"
          stripe
          @row-click="(row) => $router.push(`/opportunities/${row.id}`)"
        >
          <el-table-column label="商机" min-width="200">
            <template #default="{ row }">
              <div class="opp-cell">
                <b>{{ row.title }}</b>
                <small>{{ row.opportunity_no }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="阶段" width="110">
            <template #default="{ row }">
              <el-tag :type="stageTag(row.stage)" size="small">
                {{ OPP_STAGE_LABEL[row.stage] || row.stage }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="预计金额" width="120" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.expected_amount) }}</template>
          </el-table-column>
          <el-table-column prop="owner_name" label="负责人" width="100" />
          <el-table-column label="下一步" min-width="140">
            <template #default="{ row }">
              {{ row.next_action_at ? formatTime(row.next_action_at) : '待安排' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="$router.push(`/opportunities/${row.id}`)">
                打开
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无商机，可点右上角新建" :image-size="64" />
      </el-card>

      <el-card class="stack-gap">
        <template #header>
          <div class="card-header timeline-head">
            <span>经营轨迹</span>
            <el-radio-group v-model="timelineFilter" size="small">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="lead">线索</el-radio-button>
              <el-radio-button value="opportunity">商机</el-radio-button>
              <el-radio-button value="customer">客户</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <p class="timeline-hint muted">
          线索跟进转化后只读归档；商机跟进负责推进漏斗；客户跟进仅用于跨商机的关系维护。
        </p>
        <el-timeline v-if="filteredTimeline.length">
          <el-timeline-item
            v-for="item in filteredTimeline"
            :key="item.key"
            :timestamp="formatTime(item.occurred_at)"
            placement="top"
            :type="timelineType(item.source)"
          >
            <div class="fu-item">
              <div class="fu-meta">
                <el-tag size="small" :type="sourceTag(item.source)">{{ sourceLabelOf(item.source) }}</el-tag>
                <el-tag size="small" effect="plain">{{ item.title }}</el-tag>
                <span class="muted">{{ item.user_name || '系统' }}</span>
                <el-button
                  v-if="item.opportunity_id"
                  link
                  type="primary"
                  @click="$router.push(`/opportunities/${item.opportunity_id}`)"
                >
                  {{ item.opportunity_title || `商机#${item.opportunity_id}` }}
                </el-button>
                <el-button
                  v-else-if="item.lead_id"
                  link
                  type="primary"
                  @click="$router.push(`/leads/${item.lead_id}`)"
                >
                  线索#{{ item.lead_id }}
                </el-button>
              </div>
              <p v-if="item.content">{{ item.content }}</p>
              <p v-if="item.evidence" class="muted">补充：{{ item.evidence }}</p>
              <p v-if="item.next_action_at" class="muted">下次：{{ formatTime(item.next_action_at) }}</p>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无轨迹。线索跟进、商机推进或客户跟进会出现在这里" :image-size="64" />
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

    <el-dialog v-model="followVisible" title="客户级跟进" width="520px" destroy-on-close>
      <p class="dialog-hint muted">
        仅记录不归属某一商机的客户沟通（关系维护、续约闲聊等）。要推进某单请到对应商机里写跟进。
      </p>
      <el-form :model="followForm" label-width="90px">
        <el-form-item label="方式">
          <el-select v-model="followForm.method" style="width: 100%">
            <el-option
              v-for="(label, key) in CUSTOMER_FOLLOW_METHOD_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <el-input v-model="followForm.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="下次跟进">
          <el-date-picker
            v-model="followForm.next_follow_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="可选"
            style="width: 100%"
          />
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
  CUSTOMER_FOLLOW_METHOD_LABEL,
  CUSTOMER_SOURCE_OPTIONS,
  CUSTOMER_STATUS_LABEL,
  createCustomerFollowUp,
  fetchCustomerDetail,
  updateCustomer,
  type CustomerDetail,
  type CustomerTimelineSource,
} from '@/api/customers'
import { OPP_STAGE_LABEL } from '@/api/opportunities'

const route = useRoute()
const loading = ref(false)
const saving = ref(false)
const customer = ref<CustomerDetail | null>(null)
const editVisible = ref(false)
const followVisible = ref(false)
const timelineFilter = ref<'all' | CustomerTimelineSource>('all')

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
  next_follow_at: '' as string,
})

const customerId = computed(() => Number(route.params.id))

const filteredTimeline = computed(() => {
  const list = customer.value?.timeline || []
  if (timelineFilter.value === 'all') return list
  return list.filter((x) => x.source === timelineFilter.value)
})

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

function stageTag(s: string) {
  const map: Record<string, string> = {
    need_confirm: 'info',
    proposal: '',
    negotiation: 'warning',
    won: 'success',
    lost: 'danger',
    paused: 'info',
    contact: 'info',
  }
  return map[s] || 'info'
}

function sourceTag(source: string) {
  if (source === 'lead') return 'warning'
  if (source === 'opportunity') return 'success'
  return 'info'
}

function timelineType(source: string) {
  if (source === 'opportunity') return 'success'
  if (source === 'lead') return 'warning'
  return 'primary'
}

function sourceLabelOf(source: string) {
  if (source === 'lead') return '线索'
  if (source === 'opportunity') return '商机'
  return '客户'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function formatAmount(v?: number | string | null) {
  const n = Number(v || 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
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

function openFollow() {
  followForm.method = 'phone'
  followForm.content = ''
  followForm.next_follow_at = ''
  followVisible.value = true
}

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
    await createCustomerFollowUp(customerId.value, {
      method: followForm.method,
      content: followForm.content,
      next_follow_at: followForm.next_follow_at || undefined,
    })
    ElMessage.success('客户跟进已记录')
    followVisible.value = false
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
.fu-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.opp-cell {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.opp-cell b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.opp-cell small {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.timeline-head {
  gap: 12px;
  flex-wrap: wrap;
}
.timeline-hint {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.5;
}
.dialog-hint {
  margin: 0 0 14px;
  font-size: 12px;
  line-height: 1.5;
}
</style>
