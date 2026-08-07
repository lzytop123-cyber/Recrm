<template>
  <div class="project-journey" v-if="project">
    <div class="journey-head">
      <div class="journey-title-row">
        <span class="journey-title">交付旅程</span>
        <el-tag v-if="isTerminated" type="danger" size="small" effect="plain">已终止</el-tag>
        <span v-if="nextHint" class="journey-next">下一步：{{ nextHint }}</span>
      </div>
      <div class="journey-links">
        <el-button
          v-if="project.customer_id"
          link
          type="primary"
          @click="goCustomer"
        >
          客户{{ project.customer_name ? ` · ${project.customer_name}` : '' }}
        </el-button>
        <el-button
          v-if="project.contract_id"
          link
          type="primary"
          @click="goContract"
        >
          合同{{ project.contract_no ? ` · ${project.contract_no}` : '' }}
        </el-button>
        <el-button
          v-if="!isClosed"
          link
          type="primary"
          @click="goDelivery()"
        >
          去交付执行
        </el-button>
        <el-button
          v-else
          link
          type="primary"
          @click="goDelivery('acceptance')"
        >
          查看交付记录
        </el-button>
      </div>
    </div>

    <div class="journey-track" role="list">
      <button
        v-for="(m, idx) in milestones"
        :key="m.key"
        type="button"
        class="journey-node"
        :class="[`is-${m.status}`, { 'is-clickable': m.clickable }]"
        role="listitem"
        :disabled="!m.clickable"
        :title="m.hint || undefined"
        @click="onNodeClick(m)"
      >
        <span class="node-dot" />
        <span class="node-label">{{ m.label }}</span>
        <span v-if="m.meta" class="node-meta">{{ m.meta }}</span>
        <span v-if="idx < milestones.length - 1" class="node-line" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Project } from '@/api/projects'

type NodeStatus = 'done' | 'current' | 'pending' | 'skipped'

interface JourneyNode {
  key: string
  label: string
  status: NodeStatus
  clickable: boolean
  hint?: string
  meta?: string
  tab?: string
  mode?: string
}

const props = defineProps<{
  project: Project
}>()

const router = useRouter()

const STATUS_RANK: Record<string, number> = {
  initiating: 0,
  planning: 1,
  executing: 2,
  accepting: 3,
  accepted: 4,
  completed: 5,
}

const isTerminated = computed(() => props.project.status === 'terminated')
const isClosed = computed(() =>
  ['completed', 'terminated'].includes(String(props.project.status || '')),
)

const progressMeta = computed(() => {
  const p = props.project
  const total = p.milestone_total ?? 0
  const done = p.milestone_done ?? 0
  if (total > 0) return `节点 ${done}/${total}`
  return `进度 ${p.progress ?? 0}%`
})

const nextHint = computed(() => {
  if (isTerminated.value) return props.project.terminate_reason || '项目已终止'
  const status = String(props.project.status || '')
  if (status === 'accepted') return closeoutHint(props.project)
  if (status === 'accepting' && props.project.acceptance_approval_status === 'pending') {
    return '等待验收审批'
  }
  if (status === 'accepting' && props.project.acceptance_approval_status === 'rejected') {
    return '验收已驳回，请修改后重新提交'
  }
  const n = (props.project.next_node || '').trim()
  return n && n !== '—' ? n : ''
})

const milestones = computed<JourneyNode[]>(() => {
  const p = props.project
  const status = String(p.status || '')
  const rank = STATUS_RANK[status]
  const terminated = status === 'terminated'

  const defs: Array<{
    key: string
    label: string
    stageRank: number
    tab: string
    mode?: string
    forceCurrent?: boolean
    meta?: string
    hint?: string
  }> = [
    {
      key: 'initiating',
      label: '立项',
      stageRank: 0,
      tab: 'initiation',
      hint: '立项与资源确认',
    },
    {
      key: 'planning',
      label: '计划',
      stageRank: 1,
      tab: 'execute',
      mode: 'plan',
      hint: '计划基线与节点',
    },
    {
      key: 'executing',
      label: '执行',
      stageRank: 2,
      tab: 'execute',
      mode: 'tasks',
      meta: rank !== undefined && rank >= 2 && !terminated ? progressMeta.value : undefined,
      hint: '任务推进',
    },
    {
      key: 'accepting',
      label: '验收',
      stageRank: 3,
      tab: 'acceptance',
      hint:
        p.acceptance_approval_status === 'pending'
          ? '验收审批中'
          : p.acceptance_approval_status === 'rejected'
            ? '验收已驳回，可重新提交'
            : '内部验收申请',
    },
    {
      key: 'accepted',
      label: '已验收',
      stageRank: 4,
      tab: 'acceptance',
      hint: '验收通过',
    },
    {
      key: 'completed',
      label: '结项',
      stageRank: 5,
      tab: 'acceptance',
      forceCurrent: status === 'accepted',
      hint: closeoutHint(p),
    },
  ]

  return defs.map((d) => {
    let nodeStatus: NodeStatus = 'pending'
    if (terminated) {
      nodeStatus = 'skipped'
    } else if (status === 'completed' || (rank !== undefined && rank > d.stageRank)) {
      nodeStatus = 'done'
    } else if (d.forceCurrent) {
      // 已验收：当前落在结项
      nodeStatus = 'current'
    } else if (rank !== undefined && rank === d.stageRank) {
      // 已验收时「已验收」视为完成，当前落在结项
      nodeStatus = status === 'accepted' && d.key === 'accepted' ? 'done' : 'current'
    } else {
      nodeStatus = 'pending'
    }

    const clickable =
      terminated || nodeStatus === 'done' || nodeStatus === 'current'

    return {
      key: d.key,
      label: d.label,
      status: nodeStatus,
      clickable,
      hint: d.hint,
      meta: d.meta,
      tab: d.tab,
      mode: d.mode,
    }
  })
})

function closeoutHint(p: Project) {
  if (p.status === 'completed') return '已结项'
  if (p.finance_check_status === 'pending') return '财务核对审批中'
  if (p.finance_check_status === 'rejected') return '财务核对已驳回'
  if (p.leftover_summary && !p.leftover_closed) return '有遗留待关闭'
  if (!p.finance_check_passed && p.finance_check_status !== 'approved') return '待财务核对后结项'
  return '可结项'
}

function goDelivery(tab?: string, mode?: string) {
  const query: Record<string, string> = {
    project_id: String(props.project.id),
  }
  if (tab) query.tab = tab
  if (mode) query.mode = mode
  if (!tab) {
    const status = String(props.project.status || '')
    if (status === 'initiating') query.tab = 'initiation'
    else if (status === 'planning') {
      query.tab = 'execute'
      query.mode = 'plan'
    } else if (status === 'executing') {
      query.tab = 'execute'
      query.mode = 'tasks'
    } else {
      query.tab = 'acceptance'
    }
  }
  router.push({ path: '/projects/delivery', query })
}

function onNodeClick(m: JourneyNode) {
  if (!m.clickable) return
  goDelivery(m.tab, m.mode)
}

function goCustomer() {
  if (props.project.customer_id) router.push(`/customers/${props.project.customer_id}`)
}

function goContract() {
  if (props.project.contract_id) router.push(`/contracts/${props.project.contract_id}`)
}
</script>

<style scoped>
.project-journey {
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
.journey-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.journey-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
}
.journey-next {
  font-size: 12px;
  color: var(--crm-ink-soft, #909399);
  line-height: 1.3;
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
  min-width: 72px;
  flex: 1 0 72px;
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
  max-width: 80px;
}
.node-meta {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.2;
  color: var(--crm-ink-soft, #909399);
  text-align: center;
  max-width: 88px;
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
.journey-node.is-current .node-meta {
  color: var(--crm-primary, #409eff);
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
