<template>
  <div class="crm-page contracts-workbench crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <h1>合同回款</h1>
        <p>合同台账、应收计划、到款认领与核销审批。</p>
      </div>
      <div class="sales-head-actions">
        <el-button type="primary" @click="contractCreateTick++">起草合同</el-button>
      </div>
    </header>

    <div class="crm-fit-body">
      <ContractListView :embedded="true" :open-create-signal="contractCreateTick" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ContractListView from '@/views/contracts/ContractListView.vue'

const contractCreateTick = ref(0)
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
</style>
