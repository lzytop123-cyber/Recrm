<script setup lang="ts">
import { useRouter } from 'vue-router'

withDefaults(
  defineProps<{
    label?: string
    linkText?: string
  }>(),
  {
    label: '审批进行中，请在审批中心处理',
    linkText: '去审批中心',
  },
)

const router = useRouter()

function go() {
  router.push('/approvals')
}
</script>

<template>
  <el-tag type="warning" effect="plain" style="margin-right: 8px">{{ label }}</el-tag>
  <el-button link type="primary" @click="go">{{ linkText }}</el-button>
</template>
