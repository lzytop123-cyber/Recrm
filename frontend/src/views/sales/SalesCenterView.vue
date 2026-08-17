<template>
  <div class="crm-page sales-center crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="sales-eyebrow">经营台</p>
        <h1>销售中心</h1>
        <p>{{ headDesc }}</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="tab === 'pool' || tab === 'mine' || tab === 'created'" @click="importVisible = true">批量导入</el-button>
        <el-button v-if="tab === 'pool' || tab === 'mine' || tab === 'created'" type="primary" @click="leadCreateTick++">
          录入线索
        </el-button>
        <el-button v-else-if="tab === 'customers' && canManageCustomers" type="primary" @click="customerCreateTick++">
          录入客户
        </el-button>
        <el-button v-else-if="tab === 'opportunities' && canManageOpportunities" type="primary" @click="oppCreateTick++">
          新建商机
        </el-button>
      </div>
    </header>

    <div class="sales-tabs" role="tablist" aria-label="销售中心分区">
      <button
        v-for="item in visibleTabs"
        :key="item.key"
        type="button"
        class="sales-tab"
        role="tab"
        :aria-selected="tab === item.key"
        :class="{ active: tab === item.key }"
        @click="setTab(item.key)"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="crm-fit-body">
      <LeadListView
        v-if="tab === 'pool' || tab === 'mine' || tab === 'created'"
        :key="`${tab}-${leadReloadTick}`"
        :forced-pool="tab === 'pool' ? 'public' : tab === 'created' ? 'created' : 'mine'"
        :embedded="true"
        :open-create-signal="leadCreateTick"
      />
      <CustomerListView
        v-else-if="tab === 'customers'"
        :embedded="true"
        :open-create-signal="customerCreateTick"
      />
      <OpportunityListView
        v-else-if="tab === 'opportunities'"
        :embedded="true"
        :open-create-signal="oppCreateTick"
      />
    </div>

    <LeadImportDialog
      v-model:visible="importVisible"
      :self-follow="canSelfFollowOnCreate"
      @done="onImportDone"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import LeadListView from '@/views/leads/LeadListView.vue'
import CustomerListView from '@/views/customers/CustomerListView.vue'
import OpportunityListView from '@/views/opportunities/OpportunityListView.vue'
import LeadImportDialog from '@/components/leads/LeadImportDialog.vue'

type SalesTab = 'pool' | 'mine' | 'created' | 'customers' | 'opportunities'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const canManagePool = computed(
  () => userStore.hasPermission('lead:manage') || userStore.hasPermission('*'),
)
const canViewCustomers = computed(
  () => userStore.hasPermission('customer:view') || userStore.hasPermission('*'),
)
const canManageCustomers = computed(
  () => userStore.hasPermission('customer:manage') || userStore.hasPermission('*'),
)
const canViewOpportunities = computed(
  () => userStore.hasPermission('opportunity:view') || userStore.hasPermission('*'),
)
const canManageOpportunities = computed(
  () => userStore.hasPermission('opportunity:manage') || userStore.hasPermission('*'),
)
const canSelfFollowOnCreate = computed(() =>
  (userStore.user?.roles ?? []).some(
    (r) => r.code === 'sales' || (r.name ?? '').includes('销售'),
  ),
)

const allTabs: { key: SalesTab; label: string; visible: () => boolean }[] = [
  { key: 'pool', label: '线索总览', visible: () => canManagePool.value },
  { key: 'mine', label: '我的线索', visible: () => true },
  { key: 'created', label: '我录入', visible: () => true },
  { key: 'customers', label: '客户档案', visible: () => canViewCustomers.value },
  { key: 'opportunities', label: '商机', visible: () => canViewOpportunities.value },
]

const visibleTabs = computed(() => allTabs.filter((t) => t.visible()))

function normalizeTab(raw?: string | null): SalesTab {
  if (raw === 'pool' && canManagePool.value) return 'pool'
  if (raw === 'mine') return 'mine'
  if (raw === 'created') return 'created'
  if (raw === 'customers' && canViewCustomers.value) return 'customers'
  // 兼容旧「客户与商机」深链：无客户档案权限时落到商机
  if (raw === 'customers' && canViewOpportunities.value) return 'opportunities'
  if (raw === 'opportunities' && canViewOpportunities.value) return 'opportunities'
  return canManagePool.value ? 'pool' : 'mine'
}

const leadCreateTick = ref(0)
const leadReloadTick = ref(0)
const customerCreateTick = ref(0)
const oppCreateTick = ref(0)
const importVisible = ref(false)

const tab = ref<SalesTab>(normalizeTab(route.query.tab as string))

const headDesc = computed(() => {
  if (tab.value === 'pool') return '查看全公司线索状态，并对待分配线索执行批量或逐条分配。'
  if (tab.value === 'mine') return '查看分配给当前登录人的线索并持续跟进、转化或释放。'
  if (tab.value === 'created') return '查看自己录入的线索及其当前状态（待分配/已分配等）。'
  if (tab.value === 'customers') return '维护客户主体档案，作为商机、合同与项目的统一挂载点。'
  return '推进商机阶段与赢单，商机必须关联已建档的客户主体。'
})

watch(
  () => route.query.tab,
  (v) => {
    if (v === 'contracts') {
      router.replace({ path: '/contracts' })
      return
    }
    tab.value = normalizeTab(v as string)
  },
  { immediate: true },
)

watch(
  () => [canManagePool.value, canViewCustomers.value, canViewOpportunities.value],
  () => {
    if (route.query.tab === 'contracts') return
    const next = normalizeTab(route.query.tab as string)
    if (next !== tab.value) tab.value = next
    if (!route.query.tab) {
      router.replace({ path: '/sales', query: { tab: next } })
    }
  },
  { immediate: true },
)

function setTab(next: SalesTab) {
  tab.value = next
  // 切换 Tab 时清掉仅对商机有意义的筛选参数，避免残留
  const query: Record<string, string> = { tab: next }
  router.replace({ path: '/sales', query })
}

function onImportDone() {
  leadReloadTick.value += 1
}
</script>

<style scoped>
.sales-center {
  --sc-ink: #0f172a;
  --sc-ink-soft: #64748b;
  --sc-line: #e2e8f0;
  --sc-mist: #f1f5f9;
  --sc-sky: #eff6ff;
  --sc-blue: #1e40af;
  --sc-blue-mid: #3b82f6;
  --sc-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);

  --crm-primary: var(--sc-blue);
  --crm-primary-soft: var(--sc-sky);
  --crm-surface-soft: var(--sc-mist);
  --crm-border: var(--sc-line);
  --crm-ink: var(--sc-ink);
  --crm-ink-soft: var(--sc-ink-soft);

  gap: 12px;
}

.sales-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 0;
  flex-shrink: 0;
  padding: 18px 20px;
  border: 1px solid var(--sc-line);
  border-radius: 16px;
  background:
    radial-gradient(ellipse 72% 100% at 0% 0%, rgba(59, 130, 246, 0.1), transparent 52%),
    radial-gradient(ellipse 50% 80% at 100% 0%, rgba(30, 64, 175, 0.05), transparent 48%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: var(--sc-shadow);
}

.sales-eyebrow {
  margin: 0 0 6px;
  color: var(--sc-blue-mid);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.16em;
  line-height: 1.2;
}

.sales-head-copy h1 {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', var(--crm-font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1.2;
  color: var(--sc-ink);
}

.sales-head-copy p:last-child {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--sc-ink-soft);
  max-width: 42em;
}

.sales-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.sales-tabs {
  width: fit-content;
  max-width: 100%;
  margin-bottom: 0;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  /* 解除一屏锁定，允许整页纵向滑动 */
  .sales-center.crm-fit-page {
    height: auto;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .sales-center .crm-fit-body {
    flex: none;
    min-height: 0;
    overflow: visible;
  }

  .sales-center :deep(.embedded.leads-page),
  .sales-center :deep(.embedded.customers-page),
  .sales-center :deep(.embedded.opportunities-page) {
    height: auto;
    overflow: visible;
  }

  .sales-center :deep(.crm-fit-panel),
  .sales-center :deep(.embedded .crm-panel) {
    flex: none;
    overflow: visible;
  }

  .sales-center :deep(.crm-table-wrap.is-fit) {
    flex: none;
    min-height: 0;
    overflow-x: auto;
    overflow-y: visible;
    -webkit-overflow-scrolling: touch;
  }

  .sales-head {
    flex-direction: column;
    padding: 14px 16px;
  }

  .sales-head-actions {
    width: 100%;
  }

  .sales-head-actions .el-button {
    flex: 1 1 auto;
  }

  .sales-head-copy h1 {
    font-size: 22px;
  }

  .sales-tabs {
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
  }

  .sales-tabs :deep(.sales-tab),
  .sales-tab {
    flex: 1 1 auto;
    justify-content: center;
    white-space: nowrap;
  }
}

@media (max-width: 480px) {
  .sales-head-copy h1 {
    font-size: 20px;
  }

  .sales-head-copy p:last-child {
    font-size: 12px;
  }
}
</style>
