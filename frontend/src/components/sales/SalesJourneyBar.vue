<template>
  <div class="sales-journey" v-loading="loading">
    <div class="journey-head">
      <span class="journey-title">销售旅程</span>
      <div v-if="hasLinks" class="journey-links">
        <el-button
          v-if="journey?.links.lead_id && showLeadLink"
          link
          type="primary"
          @click="goLead"
        >
          线索{{ journey.links.lead_label ? ` · ${journey.links.lead_label}` : '' }}
        </el-button>
        <el-button
          v-if="journey?.links.customer_id"
          link
          type="primary"
          @click="goCustomer"
        >
          客户档案
        </el-button>
        <el-button
          v-if="journey?.links.opportunity_id && showOppLink"
          link
          type="primary"
          @click="goOpportunity"
        >
          商机{{ journey.links.opportunity_no ? ` · ${journey.links.opportunity_no}` : '' }}
        </el-button>
        <el-button
          v-if="journey?.links.contract_id"
          link
          type="primary"
          @click="goContract"
        >
          合同{{ journey.links.contract_no ? ` · ${journey.links.contract_no}` : '' }}
        </el-button>
      </div>
    </div>

    <div v-if="milestones.length" class="journey-track" role="list">
      <button
        v-for="(m, idx) in milestones"
        :key="m.key"
        type="button"
        class="journey-node"
        :class="[`is-${m.status}`, { 'is-clickable': canJump(m) }]"
        role="listitem"
        :disabled="!canJump(m)"
        @click="onNodeClick(m)"
      >
        <span class="node-dot" />
        <span class="node-label">{{ m.label }}</span>
        <span v-if="idx < milestones.length - 1" class="node-line" aria-hidden="true" />
      </button>
    </div>
    <el-empty v-else-if="!loading" description="暂无旅程" :image-size="48" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchLeadJourney,
  fetchOpportunityJourney,
  type SalesJourney,
  type SalesJourneyMilestone,
} from '@/api/salesJourney'

const props = withDefaults(
  defineProps<{
    leadId?: number | null
    opportunityId?: number | null
    /** 当前页已是线索时隐藏「线索」链，避免自跳 */
    hideSelfLead?: boolean
    /** 当前页已是商机时隐藏「商机」链 */
    hideSelfOpp?: boolean
  }>(),
  {
    leadId: null,
    opportunityId: null,
    hideSelfLead: false,
    hideSelfOpp: false,
  },
)

const emit = defineEmits<{
  loaded: [journey: SalesJourney]
}>()

const router = useRouter()
const loading = ref(false)
const journey = ref<SalesJourney | null>(null)

const milestones = computed(() => journey.value?.milestones || [])
const showLeadLink = computed(() => !props.hideSelfLead)
const showOppLink = computed(() => !props.hideSelfOpp)
const hasLinks = computed(() => {
  const l = journey.value?.links
  if (!l) return false
  return !!(
    (l.lead_id && showLeadLink.value) ||
    l.customer_id ||
    (l.opportunity_id && showOppLink.value) ||
    l.contract_id
  )
})

function canJump(m: SalesJourneyMilestone) {
  if (m.status === 'pending' || m.status === 'skipped') return false
  if (!m.entity || !m.entity_id) return false
  if (m.entity === 'lead' && props.hideSelfLead) return false
  if (m.entity === 'opportunity' && props.hideSelfOpp) return false
  return true
}

function onNodeClick(m: SalesJourneyMilestone) {
  if (!canJump(m) || !m.entity_id) return
  if (m.entity === 'lead') router.push(`/leads/${m.entity_id}`)
  else if (m.entity === 'customer') router.push(`/customers/${m.entity_id}`)
  else if (m.entity === 'opportunity') router.push(`/opportunities/${m.entity_id}`)
  else if (m.entity === 'contract') router.push(`/contracts/${m.entity_id}`)
}

function goLead() {
  const id = journey.value?.links.lead_id
  if (id) router.push(`/leads/${id}`)
}
function goCustomer() {
  const id = journey.value?.links.customer_id
  if (id) router.push(`/customers/${id}`)
}
function goOpportunity() {
  const id = journey.value?.links.opportunity_id
  if (id) router.push(`/opportunities/${id}`)
}
function goContract() {
  const id = journey.value?.links.contract_id
  if (id) router.push(`/contracts/${id}`)
}

async function load() {
  const leadId = props.leadId
  const oppId = props.opportunityId
  if (!leadId && !oppId) {
    journey.value = null
    return
  }
  loading.value = true
  try {
    const { data } = leadId
      ? await fetchLeadJourney(leadId)
      : await fetchOpportunityJourney(oppId as number)
    journey.value = data
    emit('loaded', data)
  } catch {
    journey.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.leadId, props.opportunityId] as const,
  () => {
    load()
  },
  { immediate: true },
)

defineExpose({ reload: load })
</script>

<style scoped>
.sales-journey {
  padding: 12px 14px;
  border: 1px solid var(--crm-border);
  border-radius: 10px;
  background: var(--crm-surface-soft, #f7f8fa);
}
.journey-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.journey-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
}
.journey-links {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
.journey-track {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding-bottom: 4px;
}
.journey-node {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 64px;
  flex: 1 0 64px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: default;
  color: var(--crm-ink-soft);
}
.journey-node.is-clickable {
  cursor: pointer;
}
.journey-node.is-clickable:hover .node-label {
  color: var(--crm-primary);
}
.node-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #c0c4cc;
  background: #fff;
  z-index: 1;
}
.node-line {
  position: absolute;
  top: 5px;
  left: calc(50% + 8px);
  width: calc(100% - 16px);
  height: 2px;
  background: #dcdfe6;
}
.node-label {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.3;
  text-align: center;
  max-width: 72px;
}
.journey-node.is-done .node-dot {
  border-color: var(--crm-primary, #409eff);
  background: var(--crm-primary, #409eff);
}
.journey-node.is-done .node-line {
  background: var(--crm-primary, #409eff);
}
.journey-node.is-done .node-label {
  color: var(--crm-ink);
}
.journey-node.is-current .node-dot {
  border-color: var(--crm-primary, #409eff);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.25);
}
.journey-node.is-current .node-label {
  color: var(--crm-primary, #409eff);
  font-weight: 600;
}
.journey-node.is-skipped .node-dot {
  border-color: #dcdfe6;
  background: #f0f0f0;
}
.journey-node.is-skipped .node-label {
  text-decoration: line-through;
  opacity: 0.7;
}
.journey-node.is-pending .node-label {
  opacity: 0.65;
}
</style>
