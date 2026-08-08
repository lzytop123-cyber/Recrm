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
