<template>
  <div class="crm-page approvals-page crm-fit-page" :class="{ 'is-compact': isCompact }" v-loading="loading">
    <header class="approvals-head">
      <div class="approvals-head-copy">
        <p class="approvals-eyebrow">经营台</p>
        <h1>审批中心</h1>
        <p class="approvals-head-desc">汇总待我审批、我发起与已处理事项；通过后回各自业务模块生效。</p>
      </div>
      <div class="approvals-head-actions">
        <el-button @click="reload">刷新</el-button>
      </div>
    </header>

    <section class="approvals-kpis" style="--kpi-cols: 3" aria-label="审批分类">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="approvals-kpi"
        :class="{ active: activeTab === tab.key, accent: tab.key === 'pending' }"
        @click="switchTab(tab.key)"
      >
        <small>{{ tab.label }}</small>
        <b :class="{ danger: tab.key === 'pending' && (stats[tab.statKey] ?? 0) > 0 }">
          {{ stats[tab.statKey] ?? 0 }}
        </b>
        <span class="approvals-kpi-note">{{ tab.note }}</span>
      </button>
    </section>

    <section class="crm-panel crm-fit-panel approvals-panel">
      <div class="approvals-panel-head">
        <div>
          <strong>{{ listTitle }}</strong>
          <p class="approvals-panel-hint">按提交时间与业务类型筛选处理</p>
        </div>
        <span class="approvals-count-chip">{{ total }} 项</span>
      </div>

      <div class="toolbar">
        <div class="filters">
          <el-select v-model="category" clearable placeholder="业务类型" style="width: 140px" @change="reload">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索标题 / 编号 / 申请人"
            style="width: 240px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
        </div>
      </div>

      <div v-if="isCompact" class="approval-card-list">
        <article v-for="row in items" :key="row.id" class="approval-card">
          <button type="button" class="approval-card-body" @click="openItem(row)">
            <div class="approval-card-top">
              <el-tag size="small" type="info">{{ row.category }}</el-tag>
              <el-tag size="small" :type="statusTag(row.status_label)">{{ row.status_label }}</el-tag>
            </div>
            <strong class="approval-card-title">{{ row.title }}</strong>
            <p class="approval-card-meta">
              <span>{{ row.applicant_name || '—' }}</span>
              <span v-if="row.source_id"> · {{ row.source_id }}</span>
            </p>
            <p class="approval-card-sub">
              <span v-if="row.node">{{ row.node }}</span>
              <span v-if="row.submitted_at" class="approval-card-time">{{ formatTime(row.submitted_at) }}</span>
            </p>
            <p v-if="row.summary" class="approval-card-summary">{{ row.summary }}</p>
          </button>
          <div class="approval-card-actions">
            <el-button link type="primary" @click="openItem(row)">查看</el-button>
            <template v-if="activeTab === 'pending' && row.can_act">
              <el-button
                v-if="row.actions.includes('approve')"
                link
                type="success"
                :loading="actingId === row.id"
                @click="act(row, true)"
              >
                通过
              </el-button>
              <el-button
                v-if="row.actions.includes('reject')"
                link
                type="danger"
                :loading="actingId === row.id"
                @click="act(row, false)"
              >
                驳回
              </el-button>
            </template>
          </div>
        </article>
        <div v-if="!items.length" class="approval-card-empty">暂无审批事项</div>
      </div>

      <div v-else class="crm-table-wrap">
        <el-table :data="items" stripe empty-text="暂无审批事项" height="100%">
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="事项" min-width="200" show-overflow-tooltip />
          <el-table-column prop="source" label="来源" width="100" />
          <el-table-column prop="source_id" label="单号" width="130" show-overflow-tooltip />
          <el-table-column prop="applicant_name" label="申请人" width="100" />
          <el-table-column prop="node" label="当前节点" width="140" show-overflow-tooltip />
          <el-table-column prop="summary" label="摘要" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status_label)">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="提交时间" width="160">
            <template #default="{ row }">{{ formatTime(row.submitted_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openItem(row)">查看</el-button>
              <template v-if="activeTab === 'pending' && row.can_act">
                <el-button
                  v-if="row.actions.includes('approve')"
                  link
                  type="success"
                  :loading="actingId === row.id"
                  @click="act(row, true)"
                >
                  通过
                </el-button>
                <el-button
                  v-if="row.actions.includes('reject')"
                  link
                  type="danger"
                  :loading="actingId === row.id"
                  @click="act(row, false)"
                >
                  驳回
                </el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :layout="isCompact ? 'total, prev, next' : 'total, prev, pager, next'"
          :pager-count="isCompact ? 3 : 7"
          @current-change="loadList"
        />
      </div>
    </section>

    <el-drawer
      v-model="detailVisible"
      :title="detailTitle"
      :size="isCompact ? '100%' : '520px'"
      destroy-on-close
      class="approval-detail-drawer"
      :class="{ 'is-compact': isCompact }"
    >
      <div v-loading="detailLoading" class="approval-drawer">
        <template v-if="detail">
          <div class="drawer-scroll">
            <header class="drawer-hero">
              <div class="drawer-tags">
                <el-tag :type="statusTag(detail.status_label || '')" effect="light" size="small">
                  {{ detail.status_label || '—' }}
                </el-tag>
                <el-tag v-if="detail.source || detail.category" type="info" effect="plain" size="small">
                  {{ detail.source || detail.category }}
                </el-tag>
              </div>
              <h2>{{ detailHeadline }}</h2>
              <p class="drawer-meta">
                {{ detail.applicant_name || '—' }}
                <span v-if="detail.department_name"> · {{ detail.department_name }}</span>
                <span> · {{ formatTime(detail.submitted_at) }}</span>
              </p>
              <p v-if="detail.node" class="drawer-node">
                {{ activeTab === 'pending' && detail.can_act ? '待处理' : '当前节点' }}：{{ detail.node }}
              </p>
            </header>

            <section v-if="highlightAmount && detail.type !== 'project_payment_defer'" class="amount-card">
              <small>{{ highlightAmount.label }}</small>
              <b>{{ highlightAmount.value }}</b>
            </section>

            <!-- 内部验收 -->
            <div v-if="detail.type === 'project_acceptance'" class="fact-grid">
              <div class="fact-row">
                <small>项目</small>
                <b>
                  {{
                    detailProject
                      ? `${detailProject.project_no} · ${detailProject.name}`
                      : detail.source_id || detail.title
                  }}
                </b>
              </div>
              <div class="fact-row">
                <small>验收结果</small>
                <b>
                  {{
                    ACCEPTANCE_RESULT_LABEL[acceptanceResultKey] ||
                    acceptanceResultKey ||
                    '—'
                  }}
                </b>
              </div>
              <div class="fact-row">
                <small>验收日期</small>
                <b>{{ detailProject?.accepted_at || '—' }}</b>
              </div>
              <div class="fact-row wide">
                <small>结论 / 遗留</small>
                <b>{{ detailProject?.acceptance_conclusion || factValue('验收结论') || '—' }}</b>
              </div>
              <div v-if="factValue('验收方式')" class="fact-row">
                <small>验收方式</small>
                <b>{{ factValue('验收方式') }}</b>
              </div>
              <div v-if="acceptanceAttachments.length" class="fact-row wide">
                <small>附件</small>
                <AttachmentPreview :items="acceptanceAttachments" size="md" />
              </div>
              <div v-else-if="factValue('附件')" class="fact-row wide">
                <small>附件</small>
                <AttachmentPreview :filename="factValue('附件')" size="md" />
              </div>
            </div>

            <!-- 无到款立项 -->
            <div v-else-if="detail.type === 'project_payment_defer'" class="fact-grid">
              <div class="fact-row wide">
                <small>项目</small>
                <b>
                  {{
                    detailProject
                      ? `${detailProject.project_no} · ${detailProject.name}`
                      : detail.source_id || detail.title
                  }}
                </b>
              </div>
              <div class="fact-row">
                <small>合同金额</small>
                <b>¥{{ financeMoney(detailProject?.contract_amount ?? factValue('合同金额')) }}</b>
              </div>
              <div class="fact-row">
                <small>已确认到账</small>
                <b :class="{ 'text-warn': paymentDeferUnpaid }">
                  ¥{{ financeMoney(detailProject?.contract_paid_amount ?? factValue('已确认到账')) }}
                </b>
              </div>
              <div class="fact-row wide">
                <small>申请原因</small>
                <b>{{ detailProject?.payment_deferred_reason || factValue('申请原因') || '—' }}</b>
              </div>
              <div class="fact-row wide decision-hint">
                <small>审批要点</small>
                <b>
                  当前未确认到账 ¥{{ financeMoney(detailProject?.contract_paid_amount ?? factValue('已确认到账')) }}
                  ／合同 ¥{{ financeMoney(detailProject?.contract_amount ?? factValue('合同金额')) }}。
                  通过后可先进入计划与交付；结项财务核对仍须回款收齐。
                </b>
              </div>
            </div>

            <!-- 财务核对 -->
            <div v-else-if="detail.type === 'project_finance'" class="fact-grid">
              <div class="fact-row wide">
                <small>项目</small>
                <b>
                  {{
                    detailProject
                      ? `${detailProject.project_no} · ${detailProject.name}`
                      : detail.source_id || detail.title
                  }}
                </b>
              </div>
              <div class="fact-row">
                <small>合同金额</small>
                <b>¥{{ financeMoney(detailProject?.contract_amount ?? factValue('合同金额')) }}</b>
              </div>
              <div class="fact-row">
                <small>已确认到账</small>
                <b>¥{{ financeMoney(detailProject?.contract_paid_amount ?? factValue('已确认到账')) }}</b>
              </div>
              <div class="fact-row wide">
                <small>回款状态</small>
                <b :class="{ 'text-warn': !financeCollectionComplete }">
                  {{ financeCollectionLabel }}
                </b>
              </div>
              <div class="fact-row">
                <small>核对结论</small>
                <b>
                  <template v-if="detailProject?.finance_check_status === 'pending'">待核对</template>
                  <template v-else-if="detailProject?.finance_check_passed">已通过</template>
                  <template v-else-if="detailProject?.finance_check_status === 'rejected'">已驳回</template>
                  <template v-else>{{ detail.status_label || '—' }}</template>
                </b>
              </div>
              <p v-if="!financeCollectionComplete" class="finance-settle-warn">
                回款未收齐时系统不允许通过；请先到「合同回款」完成到款核销，或驳回本次核对。
              </p>
            </div>

            <!-- 资产借用 -->
            <div v-else-if="detail.type === 'asset_borrow'" class="fact-grid">
              <div class="fact-row wide">
                <small>借用器材</small>
                <b>{{ factValue('借用器材') || '—' }}</b>
              </div>
              <div class="fact-row">
                <small>用途说明</small>
                <b>{{ factValue('用途说明') || factValue('用途') || '—' }}</b>
              </div>
              <div class="fact-row">
                <small>申请单号</small>
                <b>{{ factValue('申请单号') || detail.source_id || '—' }}</b>
              </div>
              <div class="fact-row wide">
                <small>借用时段</small>
                <b>{{ factValue('借用时段') || '—' }}</b>
              </div>
              <div v-if="factValue('关联档期')" class="fact-row">
                <small>关联档期</small>
                <b>{{ factValue('关联档期') }}</b>
              </div>
              <div v-if="factValue('备注')" class="fact-row wide">
                <small>备注</small>
                <b>{{ factValue('备注') }}</b>
              </div>
              <div v-if="factValue('驳回原因')" class="fact-row wide">
                <small>驳回原因</small>
                <b>{{ factValue('驳回原因') }}</b>
              </div>
            </div>

            <!-- 通用业务字段 -->
            <div v-else class="fact-grid">
              <div
                v-for="fact in displayFacts"
                :key="fact.label"
                class="fact-row"
                :class="{ wide: fact.label.includes('证明') || fact.label.includes('合同') || fact.label.includes('器材') || fact.label.includes('时段') }"
              >
                <small>{{ fact.label }}</small>
                <b>{{ fact.value }}</b>
              </div>
              <div
                v-if="!displayFacts.length && detail.summary"
                class="fact-row wide"
              >
                <small>说明</small>
                <b>{{ detail.summary }}</b>
              </div>
            </div>

            <section v-if="timelineNodes.length" class="timeline-block">
              <div class="timeline-head">
                <h3>流程进度</h3>
                <span class="timeline-progress">{{ timelineProgressText }}</span>
              </div>
              <p v-if="timelineChainHint" class="timeline-chain-hint">{{ timelineChainHint }}</p>
              <ol class="approval-timeline">
                <li
                  v-for="(node, idx) in timelineNodes"
                  :key="`${node.name}-${idx}`"
                  :class="timelineClass(node.status)"
                >
                  <div class="tl-rail" aria-hidden="true">
                    <span class="tl-dot">{{ idx + 1 }}</span>
                  </div>
                  <div class="tl-body">
                    <div class="tl-title-row">
                      <div class="tl-title">{{ node.name }}</div>
                      <span class="tl-status">{{ timelineStatusLabel(node.status) }}</span>
                    </div>
                    <div v-if="node.actor_name || node.acted_at" class="tl-meta">
                      <span v-if="node.actor_name">{{ node.actor_name }}</span>
                      <span v-if="node.acted_at"> · {{ formatTime(node.acted_at) }}</span>
                    </div>
                    <div v-if="timelineComment(node)" class="tl-comment">
                      {{ timelineComment(node) }}
                    </div>
                  </div>
                </li>
              </ol>
            </section>
          </div>

          <div class="drawer-actions">
            <el-button @click="openDeepLink">{{ deepLinkLabel }}</el-button>
            <template v-if="activeTab === 'pending' && detail?.can_act">
              <el-button
                v-if="detail.actions.includes('approve')"
                v-perm="'approval:center'"
                type="success"
                :loading="actingId === detail.id"
                @click="act(detail, true)"
              >
                通过
              </el-button>
              <el-button
                v-if="detail.actions.includes('reject')"
                v-perm="'approval:center'"
                type="danger"
                :loading="actingId === detail.id"
                @click="act(detail, false)"
              >
                驳回
              </el-button>
            </template>
          </div>
        </template>
        <el-empty v-else-if="!detailLoading" description="暂无详情" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  approveApproval,
  fetchApprovalDetail,
  fetchApprovalStats,
  fetchApprovals,
  rejectApproval,
  type ApprovalDetail,
  type ApprovalItem,
  type ApprovalStats,
} from '@/api/approvals'
import {
  ACCEPTANCE_RESULT_LABEL,
  fetchProjectDetail,
  type Project,
} from '@/api/projects'
import AttachmentPreview from '@/components/common/AttachmentPreview.vue'
import { parseAttachmentList } from '@/utils/attachments'
import { useMatchMedia } from '@/composables/useMatchMedia'

const router = useRouter()
const isCompact = useMatchMedia('(max-width: 768px)')

const tabs = [
  { key: 'pending', label: '待我审批', statKey: 'pending' as const, note: '需尽快处理' },
  { key: 'initiated', label: '我发起的', statKey: 'initiated' as const, note: '跟踪进度' },
  { key: 'processed', label: '已处理', statKey: 'processed' as const, note: '历史记录' },
]

/** 与后端 category 对齐；目标绩效二期隐藏 */
const categories = ['全部业务', '销售合同', '到款复核', '收款核销', '固定资产', '项目交付']

const loading = ref(false)
const actingId = ref<string | null>(null)
const activeTab = ref('pending')
const category = ref<string>('全部业务')
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const items = ref<ApprovalItem[]>([])
const stats = reactive<ApprovalStats>({
  pending: 0,
  initiated: 0,
  processed: 0,
  cc: 0,
})

const listTitle = computed(
  () => tabs.find((t) => t.key === activeTab.value)?.label || '审批列表',
)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<ApprovalDetail | null>(null)
const detailProject = ref<Project | null>(null)

const detailTitle = computed(() => {
  if (!detail.value) return '审批详情'
  if (detail.value.type === 'project_acceptance') return '内部验收'
  if (detail.value.type === 'project_finance') return '财务核对'
  if (detail.value.type === 'project_payment_defer') return '无到款立项'
  if (detail.value.type === 'asset_borrow') return '资产借用审批'
  if (detail.value.type === 'contract') return '合同审批'
  if (detail.value.type === 'receipt') return '到款复核'
  if (detail.value.type === 'allocation') return '收款核销'
  if (detail.value.type === 'timesheet') return '工时审批'
  return detail.value.source || detail.value.category || '审批详情'
})

const detailHeadline = computed(() => {
  if (!detail.value) return ''
  if (detailProject.value) return detailProject.value.name
  if (detail.value.type === 'asset_borrow') {
    return detail.value.title || `借用申请 ${detail.value.source_id || ''}`.trim()
  }
  return detail.value.title || '—'
})

const acceptanceResultKey = computed(() => {
  return detailProject.value?.acceptance_result || factValue('验收结果') || ''
})

function financeMoney(v?: number | string | null) {
  const n = Number(v || 0)
  if (Number.isNaN(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const financeCollectionComplete = computed(() => {
  if (detailProject.value) return !!detailProject.value.contract_collection_complete
  const label = factValue('回款状态')
  return label.includes('已收齐')
})

const financeCollectionLabel = computed(() => {
  if (detailProject.value) {
    const paid = financeMoney(detailProject.value.contract_paid_amount)
    const amount = financeMoney(detailProject.value.contract_amount)
    return detailProject.value.contract_collection_complete
      ? `已收齐（¥${paid} / ¥${amount}）`
      : `未收齐（¥${paid} / ¥${amount}）`
  }
  return factValue('回款状态') || '—'
})

const acceptanceAttachments = computed(() => {
  const p = detailProject.value
  if (!p) return []
  return parseAttachmentList(p.acceptance_attachment, p.acceptance_attachment_path)
})

const highlightAmount = computed(() => {
  const facts = detail.value?.facts || []
  const hit = facts.find((f) => f.label === '金额' || f.label === '核销金额' || f.label.includes('金额'))
  if (!hit) return null
  return hit
})

const displayFacts = computed(() => {
  const facts = detail.value?.facts || []
  if (!highlightAmount.value) return facts
  return facts.filter((f) => f.label !== highlightAmount.value!.label)
})

const timelineNodes = computed(() => {
  const d = detail.value
  if (!d) return []
  return d.timeline?.length ? d.timeline : d.nodes || []
})

const timelineProgressText = computed(() => {
  const nodes = timelineNodes.value
  if (!nodes.length) return ''
  const done = nodes.filter((n) => n.status === 'done').length
  const currentIdx = nodes.findIndex((n) => n.status === 'pending' || n.status === 'active')
  if (currentIdx >= 0) return `第 ${currentIdx + 1} / ${nodes.length} 步`
  if (done === nodes.length) return `已完成 ${nodes.length} 步`
  return `${done} / ${nodes.length} 步`
})

const timelineChainHint = computed(() => {
  const t = detail.value?.type
  if (t === 'project_payment_defer') {
    return '链路：提交申请 → 负责人审批 → 进入计划 → 结项仍须财务核对回款'
  }
  if (t === 'project_acceptance') return '链路：提交验收 → 审批 → 验收归档'
  if (t === 'project_finance') return '链路：提交核对 → 财务审批 → 项目结项'
  if (t === 'contract') return '链路：提交合同 → 审批 → 签署 / 执行'
  if (t === 'receipt') return '链路：登记到账 → 复核确认 → 核销到应收'
  if (t === 'allocation') return '链路：提交核销 → 审批 → 计入应收'
  return ''
})

const paymentDeferUnpaid = computed(() => {
  const paid = Number(detailProject.value?.contract_paid_amount ?? factValue('已确认到账') ?? 0)
  return !Number.isNaN(paid) && paid <= 0
})

const deepLinkLabel = computed(() => {
  const t = detail.value?.type
  if (t === 'receipt') return '查看到款合同'
  if (t === 'allocation') return '查看合同'
  if (t === 'contract') return '查看合同'
  if (t === 'project_acceptance' || t === 'project_finance' || t === 'project_payment_defer') {
    return '查看项目'
  }
  if (t === 'asset_borrow') return '打开借用单'
  return '查看原单'
})

function factValue(label: string): string {
  const hit = (detail.value?.facts || []).find((f) => f.label === label)
  return hit?.value || ''
}

function timelineComment(node: { status?: string; comment?: string | null; actor_name?: string | null }) {
  if (!node.comment || node.status === 'done') return ''
  // 兼容旧接口：摘要曾被塞进节点 comment，看起来像审批人
  if (detail.value?.summary && node.comment === detail.value.summary) {
    return node.status === 'pending' || node.status === 'active' ? '待审批人处理' : ''
  }
  return node.comment
}

function timelineStatusLabel(status?: string) {
  if (status === 'done') return '已完成'
  if (status === 'pending' || status === 'active') return '进行中'
  return '未开始'
}

function timelineClass(status?: string) {
  if (status === 'done') return 'is-done'
  if (status === 'pending' || status === 'active') return 'is-current'
  return 'is-waiting'
}

function statusTag(label: string) {
  if (label.includes('待')) return 'warning'
  if (label.includes('驳回') || label.includes('拒绝')) return 'danger'
  if (label.includes('通过') || label.includes('已')) return 'success'
  return 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 16)
}

function entityId(row: ApprovalItem): number {
  const id = row.meta?.entity_id
  return typeof id === 'number' ? id : Number(String(row.id).split(':')[1])
}

async function openItem(row: ApprovalItem) {
  detail.value = row
  detailProject.value = null
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await fetchApprovalDetail(row.id)
    detail.value = data
    if (
      data.type === 'project_acceptance' ||
      data.type === 'project_finance' ||
      data.type === 'project_payment_defer'
    ) {
      const id = entityId(data)
      if (id) {
        const { data: project } = await fetchProjectDetail(id)
        detailProject.value = project
      }
    }
  } catch {
    // 详情接口失败时仍展示列表行上的 facts
    detail.value = row
  } finally {
    detailLoading.value = false
  }
}

function openDeepLink() {
  if (!detail.value) return
  const link = detail.value.deep_link || '/'
  detailVisible.value = false
  if (link.includes('?')) {
    const [path, qs] = link.split('?')
    const query: Record<string, string> = {}
    new URLSearchParams(qs).forEach((val, key) => {
      query[key] = val
    })
    router.push({ path, query })
    return
  }
  router.push(link)
}

async function act(row: ApprovalItem, approve: boolean) {
  if (!approve) {
    try {
      const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回审批', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '驳回原因（必填）',
        inputValidator: (v) => (!!v && v.trim().length > 0) || '请填写原因',
      })
      await runAction(row, false, value.trim())
    } catch {
      /* cancel */
    }
    return
  }

  const needStrongConfirm = row.type === 'contract' || row.category === '销售合同'
  try {
    const { value } = await ElMessageBox.prompt(
      needStrongConfirm
        ? `确认通过「${row.title}」？可填写通过意见（可选）。`
        : `确认通过「${row.title}」？意见可选填。`,
      '通过审批',
      {
        confirmButtonText: '确认通过',
        cancelButtonText: '取消',
        inputPlaceholder: '通过意见（可选）',
        inputValue: '',
        distinguishCancelAndClose: true,
      },
    )
    await runAction(row, true, (value || '').trim())
  } catch {
    /* cancel */
  }
}

async function runAction(row: ApprovalItem, approve: boolean, remark = '') {
  actingId.value = row.id
  try {
    if (approve) {
      await approveApproval(row.id, remark ? { comment: remark } : {})
    } else {
      await rejectApproval(row.id, { reason: remark, comment: remark })
    }
    ElMessage.success(approve ? '已通过' : '已驳回')
    detailVisible.value = false
    await reload()
  } finally {
    actingId.value = null
  }
}

async function loadStats() {
  const { data } = await fetchApprovalStats()
  Object.assign(stats, data)
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchApprovals({
      tab: activeTab.value,
      category: category.value === '全部业务' ? undefined : category.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = (data.items || []).filter((x) => x.category !== '目标绩效')
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function reload() {
  page.value = 1
  await Promise.all([loadStats(), loadList()])
}

function switchTab(key: string) {
  if (activeTab.value === key) return
  activeTab.value = key
  reload()
}

onMounted(reload)
</script>

<style scoped>
/* 对齐经营总览 · Cool Enterprise Ops Desk */
.approvals-page {
  --ap-ink: #0f172a;
  --ap-ink-soft: #64748b;
  --ap-ink-faint: #94a3b8;
  --ap-line: #e2e8f0;
  --ap-mist: #f1f5f9;
  --ap-sky: #eff6ff;
  --ap-sky-mid: #dbeafe;
  --ap-blue: #1e40af;
  --ap-blue-mid: #3b82f6;
  --ap-amber: #d97706;
  --ap-success: #047857;
  --ap-danger: #dc2626;
  --ap-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);
  --ap-shadow-hover: 0 14px 28px rgba(15, 23, 42, 0.08);

  gap: 14px;
}

.approvals-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 0;
  flex-shrink: 0;
  padding: 18px 20px;
  border: 1px solid var(--ap-line);
  border-radius: 16px;
  background:
    radial-gradient(ellipse 72% 100% at 0% 0%, rgba(59, 130, 246, 0.1), transparent 52%),
    radial-gradient(ellipse 50% 80% at 100% 0%, rgba(30, 64, 175, 0.05), transparent 48%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: var(--ap-shadow);
}

.approvals-eyebrow {
  margin: 0 0 6px;
  color: var(--ap-blue-mid);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.16em;
  line-height: 1.2;
}

.approvals-head-copy h1 {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', var(--crm-font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1.2;
  color: var(--ap-ink);
}

.approvals-head-copy p:last-child,
.approvals-head-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ap-ink-soft);
  max-width: 42em;
}

.approvals-head-actions {
  flex-shrink: 0;
}

.approvals-kpis {
  display: grid;
  grid-template-columns: repeat(var(--kpi-cols, 3), minmax(0, 1fr));
  gap: 12px;
  flex-shrink: 0;
}

.approvals-kpi {
  appearance: none;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--ap-line);
  background: #fff;
  border-radius: 14px;
  padding: 16px 16px 14px;
  text-align: left;
  cursor: pointer;
  min-width: 0;
  min-height: 116px;
  box-shadow: var(--ap-shadow);
  transition:
    border-color 180ms var(--crm-ease-out),
    box-shadow 180ms var(--crm-ease-out),
    transform 180ms var(--crm-ease-out),
    background-color 180ms var(--crm-ease-out);
}

.approvals-kpi:hover {
  border-color: color-mix(in oklab, var(--ap-blue) 22%, var(--ap-line));
  box-shadow: var(--ap-shadow-hover);
  transform: translateY(-1px);
}

.approvals-kpi:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--ap-blue) 50%, white);
  outline-offset: 2px;
}

.approvals-kpi.accent:not(.active) {
  border-color: color-mix(in oklab, var(--ap-blue-mid) 18%, var(--ap-line));
  background: linear-gradient(160deg, rgba(239, 246, 255, 0.55), #fff 58%);
}

.approvals-kpi.active {
  border-color: color-mix(in oklab, var(--ap-blue-mid) 28%, var(--ap-line));
  background: linear-gradient(160deg, rgba(239, 246, 255, 0.95), #fff 58%);
  box-shadow:
    0 10px 22px rgba(15, 23, 42, 0.06),
    inset 0 0 0 1px rgba(59, 130, 246, 0.12);
}

.approvals-kpi.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, #60a5fa, var(--ap-blue));
}

.approvals-kpi small {
  display: block;
  color: var(--ap-ink-soft);
  font-size: 12px;
  font-weight: 500;
}

.approvals-kpi b {
  display: block;
  font-family: var(--crm-font-data);
  font-size: 26px;
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--ap-ink);
}

.approvals-kpi b.danger {
  color: var(--ap-danger);
}

.approvals-kpi-note {
  margin-top: auto;
  color: var(--ap-ink-faint);
  font-size: 11px;
  line-height: 1.4;
}

.approvals-panel {
  border-color: var(--ap-line);
  border-radius: 14px;
  background: #fff;
  box-shadow: var(--ap-shadow);
}

.approvals-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-shrink: 0;
}

.approvals-panel-head strong {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--ap-ink);
}

.approvals-panel-head p,
.approvals-panel-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ap-ink-faint);
}

.approvals-count-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--ap-sky-mid);
  border-radius: 999px;
  background: var(--ap-sky);
  color: var(--ap-blue);
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  flex-shrink: 0;
}

.approval-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 240px;
}

:deep(.el-drawer__body) {
  display: flex;
  flex-direction: column;
  height: calc(100% - 55px);
  overflow: hidden;
  box-sizing: border-box;
}

.drawer-scroll {
  flex: 1;
  overflow: auto;
  padding-bottom: 12px;
}

.drawer-hero {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid var(--ap-line);
  border-radius: 14px;
  background:
    radial-gradient(ellipse 70% 100% at 0% 0%, rgba(59, 130, 246, 0.08), transparent 55%),
    linear-gradient(180deg, #fff, #f8fafc);
}

.drawer-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.drawer-hero h2 {
  margin: 10px 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--ap-ink);
  line-height: 1.35;
}

.drawer-meta,
.drawer-node {
  margin: 0;
  font-size: 13px;
  color: var(--ap-ink-soft);
  line-height: 1.5;
}

.drawer-node {
  margin-top: 6px;
  color: var(--ap-amber);
}

.amount-card {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(145deg, var(--ap-sky), #f8fafc);
  border: 1px solid var(--ap-line);
}

.amount-card small {
  display: block;
  font-size: 12px;
  color: var(--ap-ink-faint);
  margin-bottom: 4px;
}

.amount-card b {
  font-size: 28px;
  font-weight: 750;
  color: var(--ap-ink);
  letter-spacing: -0.02em;
  font-family: var(--crm-font-data);
}

.fact-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}

.fact-row {
  padding: 10px 12px;
  border: 1px solid var(--ap-line);
  border-radius: 10px;
  background: var(--ap-mist);
}

.fact-row.wide {
  grid-column: 1 / -1;
}

.fact-row small {
  display: block;
  font-size: 12px;
  color: var(--ap-ink-faint);
  margin-bottom: 4px;
}

.fact-row b {
  font-size: 14px;
  font-weight: 600;
  color: var(--ap-ink);
  line-height: 1.4;
  word-break: break-word;
}

.fact-row b.text-warn,
.text-warn {
  color: #c45656;
}

.finance-settle-warn {
  grid-column: 1 / -1;
  margin: 4px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff7e8;
  color: #a15c00;
  font-size: 12px;
  line-height: 1.45;
}

.timeline-block {
  margin-top: 8px;
  padding: 12px 14px;
  border: 1px solid var(--ap-line);
  border-radius: 12px;
  background: var(--ap-surface-soft, #f8fafc);
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.timeline-block h3 {
  margin: 0;
  font-size: 14px;
  color: var(--ap-ink);
}

.timeline-progress {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--ap-blue);
}

.timeline-chain-hint {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--ap-ink-faint);
}

.approval-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}

.approval-timeline li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  position: relative;
  padding-bottom: 14px;
}

.approval-timeline li:last-child {
  padding-bottom: 0;
}

.approval-timeline li:not(:last-child) .tl-rail::after {
  content: '';
  position: absolute;
  left: 13px;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: var(--ap-line);
}

.approval-timeline .is-done:not(:last-child) .tl-rail::after {
  background: color-mix(in oklab, var(--ap-success) 55%, var(--ap-line));
}

.tl-rail {
  position: relative;
  display: flex;
  justify-content: center;
  z-index: 1;
}

.approval-timeline .tl-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--ap-line);
  background: #fff;
  color: var(--ap-ink-faint);
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  flex-shrink: 0;
}

.approval-timeline .is-done .tl-dot {
  border-color: var(--ap-success);
  background: var(--ap-success);
  color: #fff;
}

.approval-timeline .is-current .tl-dot {
  border-color: var(--ap-blue-mid);
  background: var(--ap-blue-mid);
  color: #fff;
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--ap-blue-mid) 22%, transparent);
}

.approval-timeline .is-waiting .tl-dot {
  border-color: var(--ap-line);
  background: #fff;
  color: var(--ap-ink-faint);
}

.tl-body {
  min-width: 0;
  padding: 2px 0;
}

.approval-timeline .is-current .tl-body {
  padding: 8px 10px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid color-mix(in oklab, var(--ap-blue-mid) 35%, var(--ap-line));
  box-shadow: 0 4px 12px rgba(15, 39, 68, 0.05);
}

.tl-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tl-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ap-ink);
}

.tl-status {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--ap-ink-faint);
}

.is-done .tl-status {
  color: var(--ap-success);
}

.is-current .tl-status {
  color: var(--ap-blue);
}

.is-waiting .tl-title {
  color: var(--ap-ink-faint);
  font-weight: 500;
}

.tl-meta,
.tl-comment {
  font-size: 12px;
  color: var(--ap-ink-faint);
  margin-top: 2px;
  line-height: 1.4;
}

.is-current .tl-comment {
  color: #b45309;
  font-weight: 600;
}

.decision-hint {
  border-color: color-mix(in oklab, #f59e0b 35%, var(--ap-line)) !important;
  background: color-mix(in oklab, #fff7ed 80%, #fff) !important;
}

.decision-hint b {
  font-weight: 500;
  line-height: 1.5;
}

.text-warn {
  color: #b45309 !important;
}

.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--ap-line);
  background: #fff;
}

.approval-card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
}

.approval-card {
  border: 1px solid var(--ap-line);
  border-radius: 12px;
  background: var(--ap-mist);
  overflow: hidden;
}

.approval-card-body {
  appearance: none;
  display: block;
  width: 100%;
  margin: 0;
  padding: 12px;
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.approval-card-body:active {
  background: #fff;
}

.approval-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.approval-card-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 14px;
  font-weight: 650;
  color: var(--ap-ink);
  line-height: 1.4;
}

.approval-card-meta,
.approval-card-sub,
.approval-card-summary {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ap-ink-faint);
  line-height: 1.4;
}

.approval-card-sub {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--ap-ink-soft);
}

.approval-card-time {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.approval-card-summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.approval-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0 8px 8px 4px;
  border-top: 1px solid color-mix(in oklab, var(--ap-line) 70%, transparent);
  background: #fff;
}

.approval-card-empty {
  padding: 36px 12px;
  text-align: center;
  color: var(--ap-ink-faint);
  font-size: 13px;
}

@media (prefers-reduced-motion: reduce) {
  .approvals-kpi {
    transition: none;
  }

  .approvals-kpi:hover {
    transform: none;
  }
}

@media (max-width: 768px) {
  /* 解除一屏锁定，整页可上下滑 */
  .approvals-page.crm-fit-page {
    height: auto;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .approvals-page .crm-fit-panel,
  .approvals-page.crm-fit-page .crm-panel.crm-fit-panel {
    flex: none;
    overflow: visible;
  }

  .approvals-page {
    gap: 10px;
  }

  .approvals-head {
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
  }

  .approvals-head-copy h1 {
    font-size: 20px;
  }

  .approvals-head-desc {
    display: none;
  }

  .approvals-head-actions {
    width: 100%;
  }

  .approvals-head-actions .el-button {
    width: 100%;
  }

  .approvals-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .approvals-kpi {
    min-height: 0;
    gap: 4px;
    padding: 10px 10px 8px;
  }

  .approvals-kpi:hover {
    transform: none;
  }

  .approvals-kpi small {
    font-size: 11px;
  }

  .approvals-kpi b {
    font-size: 18px;
  }

  .approvals-kpi-note {
    display: none;
  }

  .approvals-panel {
    padding: 12px;
  }

  .approvals-panel-hint {
    display: none;
  }

  .toolbar {
    margin-bottom: 10px;
  }

  .filters {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .filters > .el-input,
  .filters > .el-select {
    width: 100% !important;
  }

  .filters > .el-button {
    width: 100%;
  }

  .pager {
    justify-content: center;
    margin-top: 10px;
  }

  .drawer-hero h2 {
    font-size: 16px;
  }

  .amount-card b {
    font-size: 22px;
  }

  .drawer-actions {
    gap: 8px;
    padding: 12px 0 calc(12px + env(safe-area-inset-bottom, 0px));
  }

  .drawer-actions .el-button {
    flex: 1 1 calc(50% - 4px);
  }
}

@media (max-width: 560px) {
  .fact-grid {
    grid-template-columns: 1fr;
  }
}
</style>
