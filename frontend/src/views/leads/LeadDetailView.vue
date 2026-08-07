<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/leads')">返回列表</el-button>
      <div class="actions" v-if="lead">
        <el-button
          v-if="isPublic && canAssign"
          type="warning"
          @click="openAssign"
        >
          分配
        </el-button>
        <el-button
          v-if="canAssign && !isPublic"
          @click="openAssign"
        >
          转派
        </el-button>
        <el-button v-if="canFollow" type="primary" @click="followVisible = true">写跟进</el-button>
        <el-button v-if="canFollow" @click="openReturn">退回待分配池</el-button>
        <el-button v-if="canFollow" type="success" @click="convertVisible = true">转化为客户与商机</el-button>
        <el-button v-if="canFollow" type="danger" plain @click="lostVisible = true">标记流失</el-button>
      </div>
    </div>

    <template v-if="lead">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>线索 #{{ lead.id }} · {{ lead.name }}</span>
            <el-tag :type="statusTag(lead.status)" size="small">
              {{ LEAD_STATUS_LABEL[lead.status] || lead.status }}
            </el-tag>
            <el-tag v-if="lead.is_protected" type="warning" size="small">保护中</el-tag>
          </div>
        </template>
        <SalesJourneyBar class="journey-in-card" :lead-id="lead.id" hide-self-lead />
        <el-descriptions :column="3" border class="stack-gap-sm">
          <el-descriptions-item label="联系人">{{ lead.name }}</el-descriptions-item>
          <el-descriptions-item label="公司">{{ lead.company_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ lead.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ lead.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ lead.region || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ sourceLabel(lead.source) }}</el-descriptions-item>
          <el-descriptions-item label="跟进人">{{ lead.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="录入人">{{ lead.creator_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="保护截止">{{ formatTime(lead.protect_until) }}</el-descriptions-item>
          <el-descriptions-item label="需求" :span="3">{{ lead.need_desc || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ lead.remark || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="lead.converted_opportunity_id" label="转化商机">
            <el-button
              link
              type="primary"
              @click="$router.push(`/opportunities/${lead.converted_opportunity_id}`)"
            >
              #{{ lead.converted_opportunity_id }}
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item v-if="lead.converted_customer_id" label="转化客户">
            <el-button link type="primary" @click="$router.push(`/customers/${lead.converted_customer_id}`)">
              #{{ lead.converted_customer_id }}
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item v-if="lead.lost_reason" label="流失原因" :span="2">
            {{ lead.lost_reason }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-row :gutter="12" class="stack-gap">
        <el-col :span="14">
          <el-card>
            <template #header>跟进记录</template>
            <el-timeline v-if="lead.follow_ups?.length">
              <el-timeline-item
                v-for="fu in lead.follow_ups"
                :key="fu.id"
                :timestamp="formatTime(fu.follow_at)"
                placement="top"
              >
                <div class="fu-item">
                  <el-tag size="small">{{ fu.method }}</el-tag>
                  <el-tag size="small" type="info">{{ resultLabel(fu.result) }}</el-tag>
                  <p>{{ fu.content }}</p>
                  <p v-if="fu.customer_feedback" class="muted">客户反馈：{{ fu.customer_feedback }}</p>
                  <p v-if="fu.next_follow_at" class="muted">下次跟进：{{ formatTime(fu.next_follow_at) }}</p>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无跟进记录" :image-size="64" />
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card>
            <template #header>操作日志</template>
            <el-timeline v-if="lead.logs?.length">
              <el-timeline-item
                v-for="log in lead.logs"
                :key="log.id"
                :timestamp="formatTime(log.created_at)"
                placement="top"
              >
                <strong>{{ log.username || '系统' }}</strong>
                · {{ actionLabel(log.action) }}
                <div class="muted">{{ log.detail }}</div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无日志" :image-size="64" />
          </el-card>
        </el-col>
      </el-row>
    </template>

    <!-- 写跟进 -->
    <el-dialog v-model="followVisible" title="写跟进" width="520px">
      <el-form :model="followForm" label-width="90px">
        <el-form-item label="方式">
          <el-select v-model="followForm.method" style="width: 100%">
            <el-option label="电话" value="phone" />
            <el-option label="微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="面谈" value="meeting" />
            <el-option label="会议" value="conference" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="followForm.result" style="width: 100%">
            <el-option label="推进" value="advance" />
            <el-option label="保持" value="keep" />
            <el-option label="退回" value="return" />
            <el-option label="流失" value="lost" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <el-input v-model="followForm.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="客户反馈">
          <el-input v-model="followForm.customer_feedback" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onFollow">提交</el-button>
      </template>
    </el-dialog>

    <!-- 转化 -->
    <el-dialog v-model="convertVisible" title="转化为客户与商机" width="520px">
      <el-form label-width="100px">
        <el-form-item label="客户名称">
          <el-input v-model="convertName" placeholder="默认用公司名或联系人" />
        </el-form-item>
        <el-form-item label="商机名称">
          <el-input v-model="convertOppTitle" placeholder="默认与客户名称相同" />
        </el-form-item>
        <el-form-item label="预计金额">
          <el-input-number v-model="convertAmount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="业务类型">
          <el-select v-model="convertBizType" style="width: 100%">
            <el-option label="AI产品销售" value="ai_product" />
            <el-option label="AI定制开发" value="ai_custom" />
            <el-option label="自媒体代运营" value="media_ops" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onConvert">确认转化</el-button>
      </template>
    </el-dialog>

    <!-- 流失 -->
    <el-dialog v-model="lostVisible" title="标记流失" width="420px">
      <el-input v-model="lostReason" type="textarea" :rows="3" placeholder="请填写流失原因（必填）" />
      <template #footer>
        <el-button @click="lostVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="onLost">确认流失</el-button>
      </template>
    </el-dialog>

    <!-- 抢领确认已废弃：正式流程为管理层分配 -->

    <!-- 退回待分配池 -->
    <el-dialog v-model="returnVisible" title="退回待分配池" width="480px">
      <el-form label-width="90px">
        <el-form-item label="原因类型" required>
          <el-select v-model="returnType" style="width: 100%" placeholder="请选择">
            <el-option
              v-for="opt in LEAD_RETURN_REASON_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input v-model="returnReason" type="textarea" :rows="3" placeholder="请填写退回说明" />
        </el-form-item>
        <el-alert
          v-if="quota"
          :title="`退回后进入 ${quota.cooldown_hours} 小时冷静期，并由管理层重新分配`"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="returnVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onReturn">确认退回</el-button>
      </template>
    </el-dialog>

    <!-- 分配 / 转派 -->
    <el-dialog v-model="assignVisible" :title="isPublic ? '分配线索' : '转派线索'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="当前负责人">
          <span>{{ lead?.owner_name || '公海待领取' }}</span>
        </el-form-item>
        <el-form-item label="接收人" required>
          <el-select
            v-model="assignOwnerId"
            filterable
            style="width: 100%"
            placeholder="选择员工"
            :loading="empLoading"
          >
            <el-option
              v-for="emp in employees"
              :key="emp.id"
              :label="`${emp.real_name || emp.username}${emp.department_name ? ' · ' + emp.department_name : ''}`"
              :value="emp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="assignReason" type="textarea" :rows="3" placeholder="请填写分配/转派原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAssign">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { fetchEmployees, type Employee } from '@/api/org'
import SalesJourneyBar from '@/components/sales/SalesJourneyBar.vue'
import {
  LEAD_RETURN_REASON_OPTIONS,
  LEAD_SOURCE_OPTIONS,
  LEAD_STATUS_LABEL,
  assignLead,
  convertLead,
  createFollowUp,
  fetchLeadDetail,
  fetchLeadQuota,
  markLeadLost,
  returnLead,
  transferLead,
  type LeadDetail,
  type LeadQuota,
} from '@/api/leads'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const saving = ref(false)
const empLoading = ref(false)
const lead = ref<LeadDetail | null>(null)
const quota = ref<LeadQuota | null>(null)
const employees = ref<Employee[]>([])

const followVisible = ref(false)
const convertVisible = ref(false)
const lostVisible = ref(false)
const returnVisible = ref(false)
const assignVisible = ref(false)
const convertName = ref('')
const convertOppTitle = ref('')
const convertAmount = ref(0)
const convertBizType = ref('other')
const lostReason = ref('')
const returnType = ref('other')
const returnReason = ref('')
const assignOwnerId = ref<number | undefined>()
const assignReason = ref('')
const followForm = reactive({
  method: 'phone',
  result: 'keep',
  content: '',
  customer_feedback: '',
})

const leadId = computed(() => Number(route.params.id))
const isPublic = computed(
  () => lead.value?.status === 'pending_assign' || lead.value?.status === 'returned',
)
const canFollow = computed(() => {
  if (!lead.value) return false
  if (['converted', 'lost', 'pending_assign', 'returned'].includes(lead.value.status)) return false
  const uid = userStore.user?.id
  if (userStore.hasPermission('lead:manage') || userStore.hasPermission('*')) return true
  return lead.value.owner_id === uid
})
const canAssign = computed(() => {
  if (!lead.value) return false
  if (['converted', 'lost'].includes(lead.value.status)) return false
  if (isPublic.value) {
    return userStore.hasPermission('lead:manage') || userStore.hasPermission('*')
  }
  return canFollow.value
})

function sourceLabel(code: string) {
  return LEAD_SOURCE_OPTIONS.find((x) => x.value === code)?.label || code
}
function statusTag(s: string) {
  const map: Record<string, string> = {
    pending_assign: 'info',
    assigned: '',
    following: 'warning',
    converted: 'success',
    returned: 'info',
    lost: 'danger',
  }
  return map[s] || 'info'
}
function resultLabel(r: string) {
  return ({ advance: '推进', keep: '保持', return: '退回', lost: '流失' } as Record<string, string>)[r] || r
}
function actionLabel(a: string) {
  return (
    {
      create: '录入',
      assign: '分配',
      claim: '领取',
      follow: '跟进',
      transfer: '流转',
      return: '退回',
      convert: '转化',
      lost: '流失',
      edit: '编辑',
    } as Record<string, string>
  )[a] || a
}
function formatTime(v?: string | null) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const { data } = await fetchLeadDetail(leadId.value)
    lead.value = data
    convertName.value = data.company_name || data.name
    convertOppTitle.value = data.company_name || data.name
    convertAmount.value = Number(data.budget || 0)
    convertBizType.value = data.business_type || 'other'
  } finally {
    loading.value = false
  }
}

async function openReturn() {
  const { data } = await fetchLeadQuota()
  quota.value = data
  returnVisible.value = true
}

async function onReturn() {
  if (!returnType.value) {
    ElMessage.warning('请选择原因类型')
    return
  }
  if (!returnReason.value.trim()) {
    ElMessage.warning('请填写退回说明')
    return
  }
  saving.value = true
  try {
    await returnLead(leadId.value, {
      reason_type: returnType.value,
      reason: returnReason.value.trim(),
    })
    ElMessage.success('已退回公海')
    returnVisible.value = false
    returnReason.value = ''
    load()
  } finally {
    saving.value = false
  }
}

async function openAssign() {
  assignOwnerId.value = undefined
  assignReason.value = ''
  assignVisible.value = true
  empLoading.value = true
  try {
    const { data } = await fetchEmployees({ page: 1, page_size: 100, is_active: true })
    employees.value = data.items
  } finally {
    empLoading.value = false
  }
}

async function onAssign() {
  if (!assignOwnerId.value) {
    ElMessage.warning('请选择接收人')
    return
  }
  if (!assignReason.value.trim()) {
    ElMessage.warning('请填写原因')
    return
  }
  saving.value = true
  try {
    if (isPublic.value) {
      await assignLead(leadId.value, assignOwnerId.value, assignReason.value.trim())
      ElMessage.success('分配成功')
    } else {
      await transferLead(leadId.value, assignOwnerId.value, assignReason.value.trim())
      ElMessage.success('转派成功')
    }
    assignVisible.value = false
    load()
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
    await createFollowUp(leadId.value, { ...followForm })
    ElMessage.success('跟进已保存')
    followVisible.value = false
    followForm.content = ''
    followForm.customer_feedback = ''
    followForm.result = 'keep'
    load()
  } finally {
    saving.value = false
  }
}

async function onConvert() {
  saving.value = true
  try {
    const { data } = await convertLead(leadId.value, {
      customer_name: convertName.value || undefined,
      opportunity_title: convertOppTitle.value || undefined,
      expected_amount: convertAmount.value || undefined,
      business_type: convertBizType.value,
    })
    ElMessage.success('已转化为客户与商机')
    convertVisible.value = false
    router.push(`/opportunities/${data.opportunity_id}`)
  } finally {
    saving.value = false
  }
}

async function onLost() {
  if (!lostReason.value.trim()) {
    ElMessage.warning('请填写流失原因')
    return
  }
  saving.value = true
  try {
    await markLeadLost(leadId.value, lostReason.value)
    ElMessage.success('已标记流失')
    lostVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.journey-in-card {
  margin: 12px 0;
}
.stack-gap-sm {
  margin-top: 12px;
}
.fu-item p {
  margin: 6px 0 0;
}
</style>
