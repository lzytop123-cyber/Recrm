<template>
  <el-card shadow="never">
    <template #header>
      <span>{{ title }}（占位）</span>
    </template>
    <el-empty :description="`${moduleName}模块尚未实现业务功能，仅作骨架占位`" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => (route.meta.title as string) || '模块')
const moduleName = computed(() => (route.meta.module as string) || title.value)
</script>
