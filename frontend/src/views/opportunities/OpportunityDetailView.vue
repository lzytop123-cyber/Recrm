<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="goBack">返回</el-button>
      <div class="actions" v-if="opp">
        <el-button v-if="canEdit" type="primary" @click="openFollow">记录跟进</el-button>
        <el-button v-if="canDraft" @click="onDraftContract">发起合同</el-button>
        <el-button v-else-if="linkedContractId" @click="goLinkedContract">查看合同</el-button>
      </div>
    </div>

    <template v-if="opp">
      <el-card>
        <div class="detail-summary">
          <el-tag :type="stageTag(opp.stage)" size="small">
            {{ OPP_STAGE_LABEL[opp.stage] || opp.stage }}
          </el-tag>
          <small>{{ opp.opportunity_no }} · {{ opp.customer_name || `客户#${opp.customer_id}` }}</small>
          <el-button
            v-if="opp.source_lead_id"
            link
            type="primary"
            @click="goSourceLead"
          >
            来源线索 #{{ opp.source_lead_id }}
          </el-button>
        </div>
        <h2 class="opp-title">{{ opp.title }}</h2>
        <SalesJourneyBar
          class="journey-in-card"
          :opportunity-id="opp.id"
          :sync-key="opp.stage"
          hide-self-opp
        />
      </el-card>

      <el-card class="stack-gap">
        <template #header>销售摘要</template>
        <div class="detail-grid">
          <div class="detail-cell">
            <small>预计金额</small>
            <b>¥{{ formatAmount(opp.expected_amount) }}</b>
          </div>
          <div class="detail-cell">
            <small>业务类型</small>
            <b>{{ typeLabel(opp.business_type) }}</b>
          </div>
          <div class="detail-cell">
            <small>当前负责人</small>
            <b>{{ opp.owner_name || '-' }}</b>
          </div>
          <div class="detail-cell">
            <small>下一销售动作</small>
            <b>{{ opp.next_action_note || formatTime(opp.next_action_at) }}</b>
          </div>
          <div v-if="opp.linked_contract_no" class="detail-cell">
            <small>关联合同</small>
            <b>
              <el-button link type="primary" @click="goLinkedContract">
                {{ opp.linked_contract_no }}
              </el-button>
              <span class="muted">{{ contractStatusLabel(opp.linked_contract_status) }}</span>
            </b>
          </div>
          <div class="detail-cell wide">
            <small>需求与成交依据</small>
            <b>{{ opp.requirement_summary || '-' }}</b>
          </div>
        </div>
      </el-card>

      <el-card class="stack-gap">
        <template #header>阶段与操作轨迹</template>
        <el-timeline v-if="timelineItems.length">
          <el-timeline-item
            v-for="item in timelineItems"
            :key="item.key"
            :timestamp="item.timestamp"
            placement="top"
          >
            <div v-if="item.kind === 'activity'" class="fu-item">
              <el-tag size="small" :type="activityTag(item.activity!.activity_type)">
                {{ activityLabel(item.activity!.activity_type) }}
              </el-tag>
              <span class="muted">
                {{
                  item.activity!.user_name ||
                  (item.activity!.user_id ? `用户#${item.activity!.user_id}` : '系统')
                }}
              </span>
              <p>{{ item.activity!.content }}</p>
              <p v-if="item.activity!.evidence" class="muted">
                {{ item.activity!.activity_type === 'contract' ? '合同：' : '依据：' }}
                {{ item.activity!.evidence }}
              </p>
            </div>
            <div v-else class="contract-group">
              <div class="contract-group-head" @click="toggleContractGroup(item.key)">
                <el-tag size="small" type="success">合同</el-tag>
                <b>{{ item.contractNo || '关联合同' }}</b>
                <span class="muted">{{ item.summary }}</span>
                <el-button link type="primary">
                  {{ expandedContractKeys.has(item.key) ? '收起' : `展开 ${item.activities!.length} 条` }}
                </el-button>
              </div>
              <div v-if="expandedContractKeys.has(item.key)" class="contract-group-body">
                <div
                  v-for="act in item.activities"
                  :key="act.id"
                  class="contract-step"
                >
                  <small class="muted">{{ formatTime(act.created_at) }}</small>
                  <span>
                    {{ act.user_name || (act.user_id ? `用户#${act.user_id}` : '系统') }}
                    · {{ act.content }}
                  </span>
                </div>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无轨迹" :image-size="64" />
      </el-card>
    </template>

    <el-dialog
      v-model="followVisible"
      title="记录跟进"
      width="560px"
      destroy-on-close
      class="opp-follow-dialog"
      :fullscreen="isCompact"
    >
      <p class="dialog-hint">填写跟进结果；如需推进漏斗，可同步更新阶段。</p>
      <el-form :model="followForm" :label-width="isCompact ? 'auto' : '110px'" :label-position="isCompact ? 'top' : 'right'">
        <el-form-item label="结果与证据" required>
          <el-input
            v-model="followForm.evidence"
            type="textarea"
            :rows="3"
            placeholder="记录客户反馈、关键结论；若变更阶段，同时作为变更依据"
          />
        </el-form-item>
        <el-form-item label="销售阶段" required>
          <el-select v-model="followForm.stage" style="width: 100%">
            <el-option
              v-for="opt in stageOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <div v-if="stageChanged" class="field-tip">将同步更新销售阶段</div>
        </el-form-item>
        <el-form-item v-if="followForm.stage === 'lost'" label="输单原因" required>
          <el-input v-model="followForm.lost_reason" type="textarea" :rows="2" />
        </el-form-item>
        <template v-if="!isClosedStage">
          <el-form-item label="下一动作日期" required>
            <!-- 手机用系统日期面板，避免 Element 下拉被键盘挡住 -->
            <input
              v-if="isCompact"
              v-model="followForm.next_action_at"
              class="native-date-input"
              type="date"
              :min="minNextActionDate"
            />
            <el-date-picker
              v-else
              v-model="followForm.next_action_at"
              type="date"
              value-format="YYYY-MM-DD"
              placement="top-start"
              :editable="false"
              :clearable="true"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="下一动作">
            <el-select v-model="followForm.next_action_note" style="width: 100%" allow-create filterable>
              <el-option label="提交正式方案" value="提交正式方案" />
              <el-option label="发送报价" value="发送报价" />
              <el-option label="预约决策人会议" value="预约决策人会议" />
              <el-option label="持续跟进" value="持续跟进" />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="followVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onFollow">保存跟进</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import SalesJourneyBar from '@/components/sales/SalesJourneyBar.vue'
import {
  OPP_STAGE_LABEL,
  changeOpportunityStage,
  createOpportunityActivity,
  draftContractFromOpportunity,
  fetchOpportunityDetail,
  type OpportunityActivity,
  type OpportunityDetail,
  useBusinessTypes,
} from '@/api/opportunities'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { businessTypeLabel } = useBusinessTypes()
const loading = ref(false)
const saving = ref(false)
const opp = ref<OpportunityDetail | null>(null)
const followVisible = ref(false)
const expandedContractKeys = ref(new Set<string>())
const isCompact = ref(false)
let compactMq: MediaQueryList | null = null

function syncCompact() {
  isCompact.value = !!compactMq?.matches
}

type TimelineItem = {
  key: string
  kind: 'activity' | 'contract_group'
  timestamp: string
  activity?: OpportunityActivity
  contractNo?: string
  summary?: string
  activities?: OpportunityActivity[]
  sortAt?: number
}

const timelineItems = computed<TimelineItem[]>(() => {
  const acts = opp.value?.activities || []
  if (!acts.length) return []

  const contractBuckets = new Map<string, OpportunityActivity[]>()
  const singles: OpportunityActivity[] = []
  for (const act of acts) {
    if (act.activity_type === 'contract') {
      const no = act.evidence || '合同'
      const bucket = contractBuckets.get(no) || []
      bucket.push(act)
      contractBuckets.set(no, bucket)
    } else {
      singles.push(act)
    }
  }

  const items: TimelineItem[] = singles.map((act) => ({
    key: `act-${act.id}`,
    kind: 'activity' as const,
    timestamp: formatTime(act.created_at),
    activity: act,
    sortAt: new Date(act.created_at).getTime(),
  }))

  for (const [contractNo, group] of contractBuckets) {
    const sorted = [...group].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    const latest = sorted[0]
    items.push({
      key: `contract-${contractNo}-${latest.id}`,
      kind: 'contract_group',
      timestamp: formatTime(latest.created_at),
      contractNo,
      summary: latest.content || `${sorted.length} 条合同节点`,
      activities: sorted,
      sortAt: new Date(latest.created_at).getTime(),
    })
  }

  return items.sort((a, b) => (b.sortAt || 0) - (a.sortAt || 0))
})

const followForm = reactive({
  evidence: '',
  stage: '',
  lost_reason: '',
  next_action_at: '',
  next_action_note: '持续跟进',
})

const minNextActionDate = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
})

const stageOptions = [
  { label: '需求确认', value: 'need_confirm' },
  { label: '方案报价', value: 'proposal' },
  { label: '商务谈判', value: 'negotiation' },
  { label: '赢单', value: 'won' },
  { label: '输单', value: 'lost' },
]

const opportunityId = computed(() => Number(route.params.id))
const canEdit = computed(
  () =>
    !!opp.value &&
    !['won', 'lost'].includes(opp.value.stage) &&
    (userStore.hasPermission('opportunity:manage') || userStore.hasPermission('*')),
)
const linkedContractId = computed(() => opp.value?.linked_contract_id || null)
const canDraft = computed(
  () =>
    !!opp.value &&
    (opp.value.stage === 'negotiation' || opp.value.stage === 'won') &&
    !linkedContractId.value &&
    (userStore.hasPermission('opportunity:manage') ||
      userStore.hasPermission('contract:manage') ||
      userStore.hasPermission('*')),
)

function goLinkedContract() {
  if (linkedContractId.value) router.push(`/contracts/${linkedContractId.value}`)
}

function goSourceLead() {
  if (opp.value?.source_lead_id) router.push(`/leads/${opp.value.source_lead_id}`)
}

function toggleContractGroup(key: string) {
  const next = new Set(expandedContractKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedContractKeys.value = next
}
const stageChanged = computed(
  () => !!opp.value && !!followForm.stage && followForm.stage !== opp.value.stage,
)
const isClosedStage = computed(() => ['won', 'lost'].includes(followForm.stage))

function openFollow() {
  followForm.evidence = ''
  followForm.stage = opp.value?.stage || 'need_confirm'
  followForm.lost_reason = ''
  followForm.next_action_at = ''
  followForm.next_action_note = '持续跟进'
  followVisible.value = true
}

function goBack() {
  router.push({ path: '/sales', query: { tab: 'opportunities' } })
}

function typeLabel(code?: string) {
  return businessTypeLabel(code)
}

function formatAmount(v: number | string) {
  const n = Number(v || 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  return new Date(v).toLocaleString('zh-CN')
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

function activityLabel(t: string) {
  const map: Record<string, string> = {
    create: '创建',
    follow: '销售动作',
    stage_change: '阶段',
    contract: '合同',
  }
  return map[t] || t
}

function activityTag(t: string) {
  if (t === 'contract') return 'success'
  if (t === 'stage_change') return 'warning'
  return 'info'
}

function contractStatusLabel(s?: string | null) {
  const map: Record<string, string> = {
    draft: '草稿',
    pending_approval: '待审批',
    approved: '已审批',
    signed: '已签署',
    active: '执行中',
    completed: '已完成',
    terminated: '已终止',
  }
  return s ? map[s] || s : ''
}

async function load() {
  loading.value = true
  try {
    const { data } = await fetchOpportunityDetail(opportunityId.value)
    opp.value = data
  } finally {
    loading.value = false
  }
}

async function onFollow() {
  if (!followForm.evidence.trim()) {
    ElMessage.warning('请填写结果与证据')
    return
  }
  if (!followForm.stage) {
    ElMessage.warning('请选择销售阶段')
    return
  }
  if (followForm.stage === 'lost' && !followForm.lost_reason.trim()) {
    ElMessage.warning('请填写输单原因')
    return
  }
  if (!isClosedStage.value && !followForm.next_action_at) {
    ElMessage.warning('请填写下一动作日期')
    return
  }

  saving.value = true
  try {
    const stageLabel = OPP_STAGE_LABEL[followForm.stage] || followForm.stage
    const payload: {
      content: string
      evidence: string
      next_action_at?: string
      next_action_note?: string
    } = {
      content: stageChanged.value
        ? `跟进记录：阶段调整为${stageLabel}`
        : `跟进记录：${followForm.evidence.trim().slice(0, 80)}`,
      evidence: followForm.evidence,
    }
    if (!isClosedStage.value) {
      payload.next_action_at = followForm.next_action_at
      payload.next_action_note = followForm.next_action_note
    }

    await createOpportunityActivity(opportunityId.value, payload)

    if (stageChanged.value) {
      await changeOpportunityStage(opportunityId.value, {
        stage: followForm.stage,
        evidence: followForm.evidence,
        lost_reason: followForm.lost_reason || undefined,
      })
    }

    ElMessage.success(stageChanged.value ? '跟进已保存，阶段已更新' : '跟进已保存')
    followVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onDraftContract() {
  saving.value = true
  try {
    const { data } = await draftContractFromOpportunity(opportunityId.value)
    ElMessage.success('已发起合同草稿，请上传合同证明后再提交审批')
    router.push(`/contracts/${data.id}`)
  } finally {
    saving.value = false
  }
}

watch(opportunityId, load)
onMounted(() => {
  compactMq = window.matchMedia('(max-width: 720px)')
  syncCompact()
  compactMq.addEventListener('change', syncCompact)
  load()
})
onBeforeUnmount(() => {
  compactMq?.removeEventListener('change', syncCompact)
})
</script>

<style scoped>
.dialog-hint {
  margin: 0 0 14px;
  color: var(--crm-ink-soft);
  font-size: 13px;
  line-height: 1.5;
}
.field-tip {
  margin-top: 4px;
  color: var(--crm-primary);
  font-size: 12px;
}
.detail-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.detail-summary small {
  color: var(--crm-ink-soft);
}
.opp-title {
  margin: 0 0 12px;
  font-size: 20px;
}
.journey-in-card {
  margin-top: 4px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.detail-cell {
  padding: 12px;
  border: 1px solid var(--crm-border);
  border-radius: 10px;
  background: var(--crm-surface-soft);
}
.detail-cell.wide {
  grid-column: 1 / -1;
}
.detail-cell small {
  display: block;
  color: var(--crm-ink-soft);
  font-size: 12px;
  margin-bottom: 6px;
}
.detail-cell b {
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink);
  line-height: 1.4;
}
.stack-gap {
  margin-top: 16px;
}
.fu-item p {
  margin: 6px 0 0;
}
.muted {
  color: var(--crm-ink-soft);
  font-size: 13px;
  margin-left: 8px;
}
.contract-group-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  cursor: pointer;
}
.contract-group-body {
  margin-top: 10px;
  padding-left: 8px;
  border-left: 2px solid var(--crm-border);
}
.contract-step {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
  font-size: 13px;
}
.contract-step:last-child {
  margin-bottom: 0;
}

.native-date-input {
  box-sizing: border-box;
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base, 4px);
  background: var(--el-fill-color-blank, #fff);
  color: var(--el-text-color-primary);
  font-size: 16px; /* 避免 iOS 自动放大 */
  line-height: 40px;
  appearance: none;
}

.native-date-input:focus {
  outline: none;
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7, rgba(64, 158, 255, 0.2));
}

@media (max-width: 720px) {
  .detail-summary {
    flex-wrap: wrap;
    gap: 6px 10px;
  }
  .detail-summary small {
    width: 100%;
    order: 2;
  }
  .opp-title {
    font-size: 18px;
    line-height: 1.35;
    word-break: break-word;
  }
  .detail-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .detail-cell {
    padding: 10px 12px;
  }
  .contract-group-head {
    align-items: flex-start;
  }
  .contract-group-head .muted {
    margin-left: 0;
    width: 100%;
  }
}
</style>
