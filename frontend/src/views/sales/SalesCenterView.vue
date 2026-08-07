<template>
  <div class="crm-page sales-center crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <h1>销售中心</h1>
        <p>{{ headDesc }}</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="tab === 'pool' && canManagePool" @click="onImport">批量录入</el-button>
        <el-button v-if="tab === 'pool' || tab === 'mine'" type="primary" @click="leadCreateTick++">
          ＋ 录入线索
        </el-button>
        <el-button v-else-if="tab === 'customers'" type="primary" @click="oppCreateTick++">
          ＋ 新建商机
        </el-button>
      </div>
    </header>

    <div class="sales-tabs">
      <button
        v-if="canManagePool"
        type="button"
        class="sales-tab"
        :class="{ active: tab === 'pool' }"
        @click="setTab('pool')"
      >
        线索总览
      </button>
      <button type="button" class="sales-tab" :class="{ active: tab === 'mine' }" @click="setTab('mine')">
        我的线索
      </button>
      <button
        v-if="canViewOpportunities"
        type="button"
        class="sales-tab"
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
.sales-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}
.sales-head-copy h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  color: var(--crm-ink);
}
.sales-head-copy p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--crm-ink-soft);
  max-width: 520px;
}
.sales-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.sales-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--crm-border);
  padding-bottom: 0;
  flex-shrink: 0;
}
.sales-tab {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--crm-ink-soft);
  padding: 10px 14px 12px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.sales-tab.active {
  color: var(--crm-primary);
  border-bottom-color: var(--crm-primary);
  font-weight: 600;
}
</style>
