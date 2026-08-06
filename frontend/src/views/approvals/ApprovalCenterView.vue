<template>
  <div class="crm-page approvals-page" v-loading="loading">
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

    <section class="crm-panel">
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

      <el-table :data="items" stripe empty-text="暂无审批事项">
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

    <el-drawer v-model="detailVisible" :title="detailTitle" size="480px" destroy-on-close>
      <div v-loading="detailLoading" class="approval-drawer">
        <template v-if="detail">
          <header class="drawer-hero">
            <el-tag :type="statusTag(detail.status_label || '')" effect="light" size="small">
              {{ detail.status_label || '—' }}
            </el-tag>
            <h2>{{ detailHeadline }}</h2>
            <p class="drawer-meta">
              {{ detail.applicant_name || '—' }}
              <span v-if="detail.department_name"> · {{ detail.department_name }}</span>
              <span> · {{ formatTime(detail.submitted_at) }}</span>
            </p>
            <p v-if="activeTab === 'pending' && detail.node" class="drawer-node">
              待处理：{{ detail.node }}
            </p>
          </header>

          <el-descriptions :column="1" border class="drawer-body">
            <!-- 内部验收：只展示业务字段一次 -->
            <template v-if="detail.type === 'project_acceptance'">
              <el-descriptions-item label="项目">
                {{
                  detailProject
                    ? `${detailProject.project_no} · ${detailProject.name}`
                    : detail.source_id || detail.title
                }}
              </el-descriptions-item>
              <el-descriptions-item label="验收结果">
                {{
                  ACCEPTANCE_RESULT_LABEL[acceptanceResultKey] ||
                  acceptanceResultKey ||
                  '—'
                }}
              </el-descriptions-item>
              <el-descriptions-item label="验收日期">
                {{ detailProject?.accepted_at || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="结论 / 遗留">
                {{ detailProject?.acceptance_conclusion || factValue('验收结论') || '—' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="factValue('验收方式')" label="验收方式">
                {{ factValue('验收方式') }}
              </el-descriptions-item>
              <el-descriptions-item v-if="factValue('附件')" label="附件">
                {{ factValue('附件') }}
              </el-descriptions-item>
            </template>

            <!-- 财务核对 -->
            <template v-else-if="detail.type === 'project_finance'">
              <el-descriptions-item label="项目">
                {{
                  detailProject
                    ? `${detailProject.project_no} · ${detailProject.name}`
                    : detail.source_id || detail.title
                }}
              </el-descriptions-item>
              <el-descriptions-item label="核对结论">
                <template v-if="detailProject?.finance_check_status === 'pending'">待核对</template>
                <template v-else-if="detailProject?.finance_check_passed">已通过</template>
                <template v-else-if="detailProject?.finance_check_status === 'rejected'">已驳回</template>
                <template v-else>{{ detail.status_label || '—' }}</template>
              </el-descriptions-item>
            </template>

            <!-- 其他类型：通用 facts，去掉与标题/状态重复的摘要 -->
            <template v-else>
              <el-descriptions-item v-if="detail.category" label="业务分类">
                {{ detail.category }}
              </el-descriptions-item>
              <el-descriptions-item
                v-for="fact in detail.facts || []"
                :key="fact.label"
                :label="fact.label"
              >
                {{ fact.value }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="!(detail.facts || []).length && detail.summary"
                label="说明"
              >
                {{ detail.summary }}
              </el-descriptions-item>
            </template>
          </el-descriptions>
        </template>
        <el-empty v-else-if="!detailLoading" description="暂无详情" />

        <div class="drawer-actions">
          <el-button @click="openDeepLink">打开项目 / 原单</el-button>
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
  return detail.value.category || '审批详情'
})

const detailHeadline = computed(() => {
  if (!detail.value) return ''
  if (detailProject.value) return detailProject.value.name
  return detail.value.title || '—'
})

const acceptanceResultKey = computed(() => {
  return detailProject.value?.acceptance_result || factValue('验收结果') || ''
})

function factValue(label: string): string {
  const hit = (detail.value?.facts || []).find((f) => f.label === label)
  return hit?.value || ''
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
  margin-bottom: 16px;
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
  margin-top: 16px;
}
.approval-drawer {
  min-height: 120px;
}
.drawer-hero {
  margin-bottom: 16px;
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
.drawer-body {
  margin-top: 4px;
}
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
</style>
