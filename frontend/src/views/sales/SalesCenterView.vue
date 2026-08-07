<template>
  <div class="crm-page sales-center crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="sales-eyebrow">经营台</p>
        <h1>销售中心</h1>
        <p>{{ headDesc }}</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="tab === 'pool' && canManagePool" @click="onImport">批量录入</el-button>
        <el-button v-if="tab === 'pool' || tab === 'mine'" type="primary" @click="leadCreateTick++">
          录入线索
        </el-button>
        <el-button v-else-if="tab === 'customers'" type="primary" @click="oppCreateTick++">
          新建商机
        </el-button>
      </div>
    </header>

    <div class="sales-tabs" role="tablist" aria-label="销售中心分区">
      <button
        v-if="canManagePool"
        type="button"
        class="sales-tab"
        role="tab"
        :aria-selected="tab === 'pool'"
        :class="{ active: tab === 'pool' }"
        @click="setTab('pool')"
      >
        线索总览
      </button>
      <button
        type="button"
        class="sales-tab"
        role="tab"
        :aria-selected="tab === 'mine'"
        :class="{ active: tab === 'mine' }"
        @click="setTab('mine')"
      >
        我的线索
      </button>
      <button
        v-if="canViewOpportunities"
        type="button"
        class="sales-tab"
        role="tab"
        :aria-selected="tab === 'customers'"
        :class="{ active: tab === 'customers' }"
        @click="setTab('customers')"
      >
        客户与商机
      </button>
    </div>

    <div class="crm-fit-body">
      <LeadListView
        v-if="tab === 'pool' || tab === 'mine'"
        :key="tab"
        :forced-pool="tab === 'pool' ? 'public' : 'mine'"
        :embedded="true"
        :open-create-signal="leadCreateTick"
      />
      <OpportunityListView
        v-else-if="tab === 'customers'"
        :embedded="true"
        :open-create-signal="oppCreateTick"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import LeadListView from '@/views/leads/LeadListView.vue'
import OpportunityListView from '@/views/opportunities/OpportunityListView.vue'

type SalesTab = 'pool' | 'mine' | 'customers'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const canManagePool = computed(
  () => userStore.hasPermission('lead:manage') || userStore.hasPermission('*'),
)
const canViewOpportunities = computed(
  () => userStore.hasPermission('opportunity:view') || userStore.hasPermission('*'),
)

function normalizeTab(raw?: string | null): SalesTab {
  if (raw === 'pool' && canManagePool.value) return 'pool'
  if (raw === 'mine') return 'mine'
  if (raw === 'customers' && canViewOpportunities.value) return 'customers'
  return canManagePool.value ? 'pool' : 'mine'
}

const leadCreateTick = ref(0)
const oppCreateTick = ref(0)

const tab = ref<SalesTab>(normalizeTab(route.query.tab as string))

const headDesc = computed(() => {
  if (tab.value === 'pool') return '查看全公司线索状态，并对待分配线索执行批量或逐条分配。'
  if (tab.value === 'mine') return '查看分配给当前登录人的线索并持续跟进、转化或释放。'
  return '维护客户档案与商机阶段，推进方案报价与赢单。'
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
  () => [canManagePool.value, canViewOpportunities.value],
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
  router.replace({ path: '/sales', query: { tab: next } })
}

function onImport() {
  ElMessage.info('批量录入将在下一迭代接入正式模板与校验流程')
}
</script>

<style scoped>
.sales-center {
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
  border: 1px solid #e4ebf3;
  border-radius: 16px;
  background:
    radial-gradient(ellipse 70% 90% at 0% 0%, rgba(196, 92, 38, 0.07), transparent 50%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: 0 10px 28px rgba(15, 39, 68, 0.04);
}

.sales-eyebrow {
  margin: 0 0 6px;
  color: #c45c26;
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
  color: #0f2744;
}

.sales-head-copy p:last-child {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: #5a6b7d;
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
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 0;
  padding: 4px;
  border: 1px solid #e4ebf3;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 6px 16px rgba(15, 39, 68, 0.04);
  flex-shrink: 0;
  width: fit-content;
  max-width: 100%;
}

.sales-tab {
  appearance: none;
  border: 0;
  background: transparent;
  color: #5a6b7d;
  padding: 9px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition:
    background-color 180ms var(--crm-ease-out),
    color 180ms var(--crm-ease-out),
    box-shadow 180ms var(--crm-ease-out);
}

.sales-tab:hover {
  color: #0f2744;
  background: #f4f7fb;
}

.sales-tab:focus-visible {
  outline: 2px solid color-mix(in oklab, #1b4f8a 50%, white);
  outline-offset: 1px;
}

.sales-tab.active {
  color: #0f2744;
  background: linear-gradient(160deg, rgba(248, 235, 227, 0.7), #fff 70%);
  font-weight: 650;
  box-shadow:
    0 4px 12px rgba(15, 39, 68, 0.06),
    inset 0 0 0 1px rgba(196, 92, 38, 0.12);
}

@media (prefers-reduced-motion: reduce) {
  .sales-tab {
    transition: none;
  }
}

@media (max-width: 640px) {
  .sales-head {
    flex-direction: column;
    padding: 14px 16px;
  }

  .sales-tabs {
    width: 100%;
  }

  .sales-tab {
    flex: 1 1 auto;
    justify-content: center;
  }
}
</style>
