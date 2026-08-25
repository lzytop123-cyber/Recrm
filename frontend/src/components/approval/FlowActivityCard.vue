<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElEmpty } from 'element-plus'
import { fetchFlowActivity, type FlowActivityItem } from '@/api/approvals'

const props = withDefaults(
  defineProps<{
    /** 单个 biz_type 或多个（同一实体多种审批流，如合同 [contract, contract_terminate, ...]） */
    bizType: string | string[]
    bizId?: number | null
    /** 卡片标题（默认"操作日志"，与工单页 records 合并卡一致） */
    title?: string
    /** 无数据时是否折叠隐藏（默认 false，仍显示"暂无"占位） */
    hideWhenEmpty?: boolean
  }>(),
  {
    bizId: null,
    title: '操作日志',
    hideWhenEmpty: false,
  },
)

const loading = ref(false)
const items = ref<FlowActivityItem[]>([])

async function load() {
  if (!props.bizId) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await fetchFlowActivity(props.bizType, props.bizId)
    items.value = data.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function actionTagType(action: string): 'success' | 'danger' | 'warning' | 'info' | '' {
  if (action.endsWith('approve') || action.endsWith('countersign')) return 'success'
  if (action.endsWith('reject')) return 'danger'
  if (action.endsWith('withdraw')) return 'warning'
  if (action.endsWith('admin_act')) return 'warning'
  if (action.endsWith('submit')) return 'info'
  return ''
}

function fmtTime(s: string): string {
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(load)
watch(() => props.bizId, load)
watch(() => props.bizType, load)

defineExpose({ reload: load })
</script>

<template>
  <el-card v-if="!(hideWhenEmpty && !items.length && !loading)" class="stack-gap">
    <template #header>{{ title }}</template>
    <div v-loading="loading">
      <el-empty
        v-if="!loading && !items.length"
        :image-size="64"
        description="暂无操作日志"
      />
      <el-timeline v-else>
        <el-timeline-item
          v-for="it in items"
          :key="it.id"
          :timestamp="fmtTime(it.created_at)"
          placement="top"
        >
          <div class="record-item">
            <strong>{{ it.actor_name || '系统' }}</strong>
            <el-tag :type="actionTagType(it.action)" size="small" style="margin-left: 6px">
              {{ it.action_label }}
            </el-tag>
            <span v-if="it.rule_code" class="source-hint">审批流 · {{ it.rule_code }}</span>
            <div v-if="it.detail" class="record-content">{{ it.detail }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-card>
</template>

<style scoped>
.record-item {
  line-height: 1.5;
}
.source-hint {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.record-content {
  margin-top: 4px;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
