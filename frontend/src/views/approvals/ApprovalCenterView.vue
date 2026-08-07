<template>
  <div class="crm-page approvals-page crm-fit-page" v-loading="loading">
    <header class="todo-head approvals-head">
      <div class="todo-head-copy">
        <h1>审批中心</h1>
        <p>汇总待我审批、我发起与已处理事项；通过后回各自业务模块生效。</p>
      </div>
    </header>

    <div class="crm-stats" style="--crm-stats-cols: 3">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="crm-stat-tile"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span>{{ tab.label }}</span>
        <strong>{{ stats[tab.statKey] ?? 0 }}</strong>
      </button>
    </div>

    <section class="crm-panel crm-fit-panel">
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

      <div class="crm-table-wrap">
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
          layout="total, prev, pager, next"
          @current-change="loadList"
        />
      </div>
    </section>

    <el-drawer
      v-model="detailVisible"
      :title="detailTitle"
      size="520px"
      destroy-on-close
      class="approval-detail-drawer"
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

            <section v-if="highlightAmount" class="amount-card">
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
                <div class="attach-preview">
                  <template v-for="(file, idx) in acceptanceAttachments" :key="`${file.name}-${idx}`">
                    <el-image
                      v-if="file.isImage && file.url"
                      :src="file.url"
                      :preview-src-list="acceptanceImageUrls"
                      :initial-index="acceptanceImageIndex(idx)"
                      fit="cover"
                      class="attach-thumb"
                      preview-teleported
                    />
                    <a
                      v-else-if="file.url"
                      class="attach-link"
                      :href="file.url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ file.name }}
                    </a>
                    <span v-else class="attach-name">{{ file.name }}</span>
                  </template>
                </div>
              </div>
              <div v-else-if="factValue('附件')" class="fact-row">
                <small>附件</small>
                <b>{{ factValue('附件') }}</b>
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
                <small>核对结论</small>
                <b>
                  <template v-if="detailProject?.finance_check_status === 'pending'">待核对</template>
                  <template v-else-if="detailProject?.finance_check_passed">已通过</template>
                  <template v-else-if="detailProject?.finance_check_status === 'rejected'">已驳回</template>
                  <template v-else>{{ detail.status_label || '—' }}</template>
                </b>
              </div>
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
              <h3>流程进度</h3>
              <ol class="approval-timeline">
                <li
                  v-for="(node, idx) in timelineNodes"
                  :key="`${node.name}-${idx}`"
                  :class="timelineClass(node.status)"
                >
                  <div class="tl-dot" />
                  <div class="tl-body">
                    <div class="tl-title">{{ node.name }}</div>
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

const router = useRouter()

const tabs = [
  { key: 'pending', label: '待我审批', statKey: 'pending' as const },
  { key: 'initiated', label: '我发起的', statKey: 'initiated' as const },
  { key: 'processed', label: '已处理', statKey: 'processed' as const },
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

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<ApprovalDetail | null>(null)
const detailProject = ref<Project | null>(null)

const detailTitle = computed(() => {
  if (!detail.value) return '审批详情'
  if (detail.value.type === 'project_acceptance') return '内部验收'
  if (detail.value.type === 'project_finance') return '财务核对'
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

const IMAGE_EXT_RE = /\.(jpe?g|png|gif|webp|bmp)$/i

function isImageName(name: string) {
  return IMAGE_EXT_RE.test(name)
}

function uploadsUrl(path?: string | null) {
  const p = (path || '').trim().replace(/^\/+/, '')
  if (!p) return ''
  if (/^https?:\/\//i.test(p) || p.startsWith('/uploads/')) return p
  return `/uploads/${p}`
}

const acceptanceAttachments = computed(() => {
  const p = detailProject.value
  if (!p) return [] as { name: string; url: string; isImage: boolean }[]
  const raw = (p.acceptance_attachment || '').trim()
  const path = (p.acceptance_attachment_path || '').trim()
  const url = uploadsUrl(path)
  const names = raw
    ? raw
        .split(/(?<=\.(?:jpg|jpeg|png|gif|webp|bmp|pdf|doc|docx|xls|xlsx|zip|rar|txt))\s*-\s*/i)
        .map((s) => s.trim())
        .filter(Boolean)
    : []
  if (!names.length && path) {
    const leaf = path.split(/[/\\]/).pop() || '查看附件'
    return [{ name: leaf, url, isImage: isImageName(leaf) }]
  }
  return names.map((name, idx) => ({
    name,
    url: idx === 0 ? url : '',
    isImage: isImageName(name),
  }))
})

const acceptanceImageUrls = computed(() =>
  acceptanceAttachments.value.filter((f) => f.isImage && f.url).map((f) => f.url),
)

function acceptanceImageIndex(fileIdx: number) {
  const files = acceptanceAttachments.value
  let imageIdx = 0
  for (let i = 0; i < fileIdx; i += 1) {
    if (files[i]?.isImage && files[i]?.url) imageIdx += 1
  }
  return imageIdx
}

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

const deepLinkLabel = computed(() => {
  const t = detail.value?.type
  if (t === 'receipt') return '查看到款合同'
  if (t === 'allocation') return '查看合同'
  if (t === 'contract') return '查看合同'
  if (t === 'project_acceptance' || t === 'project_finance') return '查看项目'
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
    if (data.type === 'project_acceptance' || data.type === 'project_finance') {
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
.approvals-head {
  margin-bottom: 12px;
  flex-shrink: 0;
}
.approvals-head h1 {
  margin: 0;
  font-size: 22px;
  color: var(--crm-ink);
}
.approvals-head p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--crm-ink-soft);
  max-width: 42em;
}
.approvals-page :deep(.crm-stats) {
  flex-shrink: 0;
  margin-bottom: 12px;
}
.approvals-page .crm-stat-tile.active {
  border-color: var(--el-color-primary);
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
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
}
.drawer-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.drawer-hero h2 {
  margin: 10px 0 6px;
  font-size: 18px;
  font-weight: 600;
  color: var(--crm-ink);
  line-height: 1.35;
}
.drawer-meta,
.drawer-node {
  margin: 0;
  font-size: 13px;
  color: var(--crm-ink-soft);
  line-height: 1.5;
}
.drawer-node {
  margin-top: 6px;
  color: var(--el-color-warning-dark-2, #b88230);
}
.amount-card {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(145deg, oklch(0.96 0.03 250), oklch(0.98 0.01 250));
  border: 1px solid oklch(0.9 0.03 250);
}
.amount-card small {
  display: block;
  font-size: 12px;
  color: var(--crm-ink-soft);
  margin-bottom: 4px;
}
.amount-card b {
  font-size: 28px;
  font-weight: 700;
  color: var(--crm-ink);
  letter-spacing: -0.02em;
}
.fact-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}
.fact-row {
  padding: 10px 12px;
  border: 1px solid var(--crm-border);
  border-radius: 10px;
  background: var(--crm-surface-soft, #f7f8fa);
}
.fact-row.wide {
  grid-column: 1 / -1;
}
.fact-row small {
  display: block;
  font-size: 12px;
  color: var(--crm-ink-soft);
  margin-bottom: 4px;
}
.fact-row b {
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink);
  line-height: 1.4;
  word-break: break-word;
}
.attach-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px;
}
.attach-thumb {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  border: 1px solid var(--crm-border);
  cursor: zoom-in;
  overflow: hidden;
  background: #fff;
}
.attach-thumb :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.attach-link {
  color: var(--crm-primary);
  font-size: 13px;
  font-weight: 600;
  word-break: break-all;
}
.attach-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
  word-break: break-all;
}
.timeline-block {
  margin-top: 4px;
}
.timeline-block h3 {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--crm-ink);
}
.approval-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.approval-timeline li {
  display: grid;
  grid-template-columns: 16px 1fr;
  gap: 10px;
  position: relative;
  padding-bottom: 16px;
}
.approval-timeline li:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 14px;
  bottom: 0;
  width: 2px;
  background: var(--crm-border);
}
.approval-timeline .tl-dot {
  width: 12px;
  height: 12px;
  margin-top: 4px;
  border-radius: 50%;
  border: 2px solid var(--crm-border);
  background: #fff;
  z-index: 1;
}
.approval-timeline .is-done .tl-dot {
  border-color: var(--crm-success, #389e0d);
  background: var(--crm-success, #389e0d);
}
.approval-timeline .is-current .tl-dot {
  border-color: var(--el-color-warning);
  background: var(--el-color-warning);
}
.approval-timeline .is-waiting .tl-dot {
  border-color: var(--crm-border);
  background: #fff;
}
.tl-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
}
.is-waiting .tl-title {
  color: var(--crm-ink-soft);
  font-weight: 500;
}
.tl-meta,
.tl-comment {
  font-size: 12px;
  color: var(--crm-ink-soft);
  margin-top: 2px;
  line-height: 1.4;
}
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--crm-border);
  background: #fff;
}
@media (max-width: 560px) {
  .fact-grid {
    grid-template-columns: 1fr;
  }
}
</style>
