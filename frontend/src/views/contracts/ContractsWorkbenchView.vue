<template>
  <div class="crm-page contracts-workbench crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="wb-eyebrow">经营台</p>
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
@media (max-width: 768px) {
  .contracts-workbench.crm-fit-page {
    height: auto;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .contracts-workbench .crm-fit-body {
    flex: none;
    min-height: 0;
    overflow: visible;
  }

  .contracts-workbench :deep(.embedded.contracts-page) {
    height: auto;
    overflow: visible;
  }

  .contracts-workbench :deep(.crm-fit-panel),
  .contracts-workbench :deep(.embedded .crm-panel) {
    flex: none;
    overflow: visible;
  }

  .contracts-workbench :deep(.crm-table-wrap.is-fit) {
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
}

@media (max-width: 480px) {
  .sales-head-copy h1 {
    font-size: 20px;
  }
}
</style>
