<template>
  <div class="sales-journey" v-loading="loading">
    <div class="journey-head">
      <span class="journey-title">业务旅程</span>
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
          v-if="journey?.links.contract_id && showContractLink"
          link
          type="primary"
          @click="goContract"
        >
          合同{{ journey.links.contract_no ? ` · ${journey.links.contract_no}` : '' }}
        </el-button>
        <el-button
          v-if="journey?.links.project_id && showProjectLink"
          link
          type="primary"
          @click="goProject"
        >
          项目{{
            journey.links.project_no
              ? ` · ${journey.links.project_no}`
              : journey.links.project_name
                ? ` · ${journey.links.project_name}`
                : ''
          }}
        </el-button>
      </div>
    </div>

    <div ref="trackEl" v-if="milestones.length" class="journey-track" role="list">
      <button
        v-for="(m, idx) in milestones"
        :key="m.key"
        type="button"
        class="journey-node"
        :class="[`is-${m.status}`, { 'is-clickable': canJump(m) }]"
        :data-journey-key="m.key"
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
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchContractJourney,
  fetchLeadJourney,
  fetchOpportunityJourney,
  fetchProjectJourney,
  type SalesJourney,
  type SalesJourneyMilestone,
} from '@/api/salesJourney'

const props = withDefaults(
  defineProps<{
    leadId?: number | null
    opportunityId?: number | null
    contractId?: number | null
    projectId?: number | null
    /** 阶段/状态等变化时触发重载，避免详情已更新但旅程仍停在旧节点 */
    syncKey?: string | number | null
    /** 当前页已是线索时隐藏「线索」链，避免自跳 */
    hideSelfLead?: boolean
    /** 当前页已是商机时隐藏「商机」链 */
    hideSelfOpp?: boolean
    /** 当前页已是合同时隐藏「合同」链 */
    hideSelfContract?: boolean
    /** 当前页已是项目时隐藏「项目」链 */
    hideSelfProject?: boolean
  }>(),
  {
    leadId: null,
    opportunityId: null,
    contractId: null,
    projectId: null,
    syncKey: null,
    hideSelfLead: false,
    hideSelfOpp: false,
    hideSelfContract: false,
    hideSelfProject: false,
  },
)

const emit = defineEmits<{
  loaded: [journey: SalesJourney]
}>()

const router = useRouter()
const loading = ref(false)
const journey = ref<SalesJourney | null>(null)
const trackEl = ref<HTMLElement | null>(null)

function scrollCurrentIntoView() {
  const key = journey.value?.current_key
  const track = trackEl.value
  if (!key || !track) return
  const node = track.querySelector(`[data-journey-key="${key}"]`) as HTMLElement | null
  node?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
}

const milestones = computed(() => journey.value?.milestones || [])
const showLeadLink = computed(() => !props.hideSelfLead)
const showOppLink = computed(() => !props.hideSelfOpp)
const showContractLink = computed(() => !props.hideSelfContract)
const showProjectLink = computed(() => !props.hideSelfProject)
const hasLinks = computed(() => {
  const l = journey.value?.links
  if (!l) return false
  return !!(
    (l.lead_id && showLeadLink.value) ||
    l.customer_id ||
    (l.opportunity_id && showOppLink.value) ||
    (l.contract_id && showContractLink.value) ||
    (l.project_id && showProjectLink.value)
  )
})

function canJump(m: SalesJourneyMilestone) {
  if (m.status === 'pending' || m.status === 'skipped') return false
  if (!m.entity || !m.entity_id) return false
  if (m.entity === 'lead' && props.hideSelfLead) return false
  if (m.entity === 'opportunity' && props.hideSelfOpp) return false
  if (m.entity === 'contract' && props.hideSelfContract) return false
  if (m.entity === 'project' && props.hideSelfProject) return false
  return true
}

function onNodeClick(m: SalesJourneyMilestone) {
  if (!canJump(m) || !m.entity_id) return
  if (m.entity === 'lead') router.push(`/leads/${m.entity_id}`)
  else if (m.entity === 'customer') router.push(`/customers/${m.entity_id}`)
  else if (m.entity === 'opportunity') router.push(`/opportunities/${m.entity_id}`)
  else if (m.entity === 'contract') router.push(`/contracts/${m.entity_id}`)
  else if (m.entity === 'project') router.push(`/projects/${m.entity_id}`)
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
function goProject() {
  const id = journey.value?.links.project_id
  if (id) router.push(`/projects/${id}`)
}

async function load() {
  const leadId = props.leadId
  const oppId = props.opportunityId
  const contractId = props.contractId
  const projectId = props.projectId
  if (!leadId && !oppId && !contractId && !projectId) {
    journey.value = null
    return
  }
  loading.value = true
  try {
    const { data } = projectId
      ? await fetchProjectJourney(projectId)
      : contractId
        ? await fetchContractJourney(contractId)
        : leadId
          ? await fetchLeadJourney(leadId)
          : await fetchOpportunityJourney(oppId as number)
    journey.value = data
    emit('loaded', data)
    await nextTick()
    scrollCurrentIntoView()
  } catch {
    journey.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () =>
    [props.leadId, props.opportunityId, props.contractId, props.projectId, props.syncKey] as const,
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
  gap: 4px 8px;
}
.journey-track {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding-bottom: 2px;
  -webkit-overflow-scrolling: touch;
}
.journey-node {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 72px;
  padding: 0 8px;
  border: 0;
  background: transparent;
  cursor: default;
  color: inherit;
  font: inherit;
}
.journey-node.is-clickable {
  cursor: pointer;
}
.journey-node.is-clickable:hover .node-label {
  color: var(--el-color-primary);
}
.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--el-border-color);
  box-shadow: 0 0 0 3px #fff;
  z-index: 1;
}
.node-line {
  position: absolute;
  top: 4px;
  left: calc(50% + 8px);
  width: calc(100% - 16px);
  height: 2px;
  background: var(--el-border-color-lighter);
  z-index: 0;
}
.node-label {
  font-size: 12px;
  line-height: 1.3;
  text-align: center;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.journey-node.is-done .node-dot {
  background: var(--el-color-success);
}
.journey-node.is-done .node-line {
  background: var(--el-color-success-light-5);
}
.journey-node.is-done .node-label {
  color: var(--el-text-color-regular);
}
.journey-node.is-current .node-dot {
  background: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}
.journey-node.is-current .node-label {
  color: var(--el-color-primary);
  font-weight: 600;
}
.journey-node.is-skipped .node-dot {
  background: var(--el-border-color);
  opacity: 0.55;
}
.journey-node.is-skipped .node-label {
  color: var(--el-text-color-placeholder);
  opacity: 0.85;
}
.journey-node.is-skipped .node-line {
  background: var(--el-border-color-extra-light);
}
.journey-node.is-pending .node-label {
  color: var(--el-text-color-placeholder);
}

@media (max-width: 768px) {
  .sales-journey {
    padding: 10px 12px;
  }
  .journey-head {
    margin-bottom: 10px;
  }
  .journey-track {
    margin: 0 -4px;
    padding: 0 4px 4px;
  }
  .journey-node {
    min-width: 64px;
    padding: 0 6px;
  }
  .journey-node.is-current .node-dot {
    box-shadow: 0 0 0 3px var(--el-color-primary-light-7);
  }
}
</style>
