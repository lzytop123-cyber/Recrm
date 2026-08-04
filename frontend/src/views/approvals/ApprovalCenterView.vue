<template>
  <div class="crm-page approvals-page" v-loading="loading">
    <div class="crm-stats" style="--crm-stats-cols: 4">
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
      <div v-loading="detailLoading">
        <el-descriptions v-if="detailProject" :column="1" border>
          <el-descriptions-item label="项目">
            {{ detailProject.project_no }} · {{ detailProject.name }}
          </el-descriptions-item>
          <template v-if="detailRow?.type === 'project_acceptance'">
            <el-descriptions-item label="验收结果">
              {{ ACCEPTANCE_RESULT_LABEL[detailProject.acceptance_result || ''] || detailProject.acceptance_result || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="验收日期">{{ detailProject.accepted_at || '—' }}</el-descriptions-item>
            <el-descriptions-item label="验收方式">{{ detailProject.acceptance_method || '—' }}</el-descriptions-item>
            <el-descriptions-item label="验收负责人">
              {{ detailProject.acceptance_owner_name || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="申请人">{{ detailRow?.applicant_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="结论与遗留安排">
              {{ detailProject.acceptance_conclusion || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="遗留问题摘要">
              {{ detailProject.leftover_summary || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="验收附件">
              <a
                v-if="detailProject.acceptance_attachment_path"
                :href="`/uploads/${detailProject.acceptance_attachment_path}`"
                target="_blank"
                rel="noopener"
              >
                {{ detailProject.acceptance_attachment || '查看附件' }}
              </a>
              <span v-else>{{ detailProject.acceptance_attachment || '—' }}</span>
            </el-descriptions-item>
          </template>
          <template v-else-if="detailRow?.type === 'project_finance'">
            <el-descriptions-item label="验收结果">
              {{ ACCEPTANCE_RESULT_LABEL[detailProject.acceptance_result || ''] || detailProject.acceptance_result || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="财务核对状态">
              <template v-if="detailProject.finance_check_status === 'pending'">审批中</template>
              <template v-else-if="detailProject.finance_check_passed">已通过</template>
              <template v-else-if="detailProject.finance_check_status === 'rejected'">已驳回</template>
              <template v-else>未通过</template>
            </el-descriptions-item>
            <el-descriptions-item label="申请人">{{ detailRow?.applicant_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="提交时间">
              {{ formatTime(detailProject.finance_check_submitted_at) }}
            </el-descriptions-item>
          </template>
        </el-descriptions>
        <el-empty v-else-if="!detailLoading" description="暂无详情" />
        <div class="drawer-actions">
          <el-button @click="openDeepLink">打开项目详情</el-button>
          <template v-if="activeTab === 'pending' && detailRow?.can_act">
            <el-button
              v-if="detailRow.actions.includes('approve')"
              type="success"
              :loading="actingId === detailRow.id"
              @click="act(detailRow, true)"
            >
              通过
            </el-button>
            <el-button
              v-if="detailRow.actions.includes('reject')"
              type="danger"
              :loading="actingId === detailRow.id"
              @click="act(detailRow, false)"
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
  fetchApprovalStats,
  fetchApprovals,
  type ApprovalItem,
  type ApprovalStats,
} from '@/api/approvals'
import { approveContract, rejectContract } from '@/api/contracts'
import { approveBorrow, rejectBorrow } from '@/api/assets'
import { approveTimesheet, rejectTimesheet } from '@/api/timesheets'
import { reviewAllocation, reviewReceipt } from '@/api/finance'
import {
  ACCEPTANCE_RESULT_LABEL,
  fetchProjectDetail,
  reviewProjectAcceptance,
  reviewProjectFinanceCheck,
  type Project,
} from '@/api/projects'

const router = useRouter()

const tabs = [
  { key: 'pending', label: '待我审批', statKey: 'pending' as const },
  { key: 'initiated', label: '我发起的', statKey: 'initiated' as const },
  { key: 'processed', label: '已处理', statKey: 'processed' as const },
  { key: 'cc', label: '抄送我的', statKey: 'cc' as const },
]

const categories = ['全部业务', '销售合同', '固定资产', '项目交付', '目标绩效']

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
const detailRow = ref<ApprovalItem | null>(null)
const detailProject = ref<Project | null>(null)

const detailTitle = computed(() => {
  if (!detailRow.value) return '审批详情'
  if (detailRow.value.type === 'project_acceptance') return '内部验收申请'
  if (detailRow.value.type === 'project_finance') return '财务核对申请'
  return detailRow.value.title
})

function statusTag(label: string) {
  if (label.includes('待')) return 'warning'
  if (label.includes('已')) return 'success'
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
  if (row.type === 'project_acceptance' || row.type === 'project_finance') {
    detailRow.value = row
    detailProject.value = null
    detailVisible.value = true
    detailLoading.value = true
    try {
      const id = entityId(row)
      const { data } = await fetchProjectDetail(id)
      detailProject.value = data
    } catch {
      ElMessage.error('加载详情失败')
    } finally {
      detailLoading.value = false
    }
    return
  }
  const link = row.deep_link || '/'
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

function openDeepLink() {
  if (!detailRow.value) return
  const link = detailRow.value.deep_link || '/'
  detailVisible.value = false
  router.push(link)
}

async function act(row: ApprovalItem, approve: boolean) {
  if (!approve) {
    try {
      const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回审批', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '驳回原因',
        inputValidator: (v) => (!!v && v.trim().length > 0) || '请填写原因',
      })
      await runAction(row, false, value.trim())
    } catch {
      /* cancel */
    }
    return
  }
  await runAction(row, true)
}

async function runAction(row: ApprovalItem, approve: boolean, reason = '') {
  const id = entityId(row)
  if (!id) {
    ElMessage.error('缺少业务单号')
    return
  }
  actingId.value = row.id
  try {
    if (row.type === 'contract') {
      if (approve) await approveContract(id)
      else await rejectContract(id, reason)
    } else if (row.type === 'asset_borrow') {
      if (approve) await approveBorrow(id)
      else await rejectBorrow(id, reason)
    } else if (row.type === 'timesheet') {
      if (approve) await approveTimesheet(id)
      else await rejectTimesheet(id, reason)
    } else if (row.type === 'receipt') {
      const version = Number(row.meta?.version ?? 1)
      await reviewReceipt(id, approve, version, reason || undefined)
    } else if (row.type === 'allocation') {
      const version = Number(row.meta?.version ?? 1)
      await reviewAllocation(id, approve, version, reason || undefined)
    } else if (row.type === 'project_acceptance') {
      await reviewProjectAcceptance(id, approve, reason || undefined)
    } else if (row.type === 'project_finance') {
      await reviewProjectFinanceCheck(id, approve, reason || undefined)
    } else {
      openItem(row)
      return
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
    items.value = data.items
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
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
</style>
