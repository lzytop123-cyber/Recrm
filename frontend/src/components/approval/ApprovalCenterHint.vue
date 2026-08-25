<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{
    label?: string
    linkText?: string
    /** 审批中心单据 id，如 approval_instance:12 */
    approvalId?: string | null
    /** 无 approvalId 时按业务实体解析 */
    bizType?: string
    bizId?: number | null
  }>(),
  {
    label: '审批进行中，请在审批中心处理',
    linkText: '去审批中心',
    approvalId: null,
    bizId: null,
  },
)

const router = useRouter()

function go() {
  const query: Record<string, string> = {}
  if (props.approvalId) {
    query.id = props.approvalId
  } else if (props.bizType && props.bizId) {
    query.biz = props.bizType
    query.bizId = String(props.bizId)
  }
  router.push({ path: '/approvals', query })
}
</script>

<template>
  <el-tag type="warning" effect="plain" style="margin-right: 8px">{{ label }}</el-tag>
  <el-button link type="primary" @click="go">{{ linkText }}</el-button>
</template>
