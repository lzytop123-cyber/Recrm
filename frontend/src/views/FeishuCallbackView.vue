<template>
  <div class="callback-page">
    <el-result
      :icon="error ? 'error' : 'info'"
      :title="error ? '飞书登录失败' : '正在完成飞书登录…'"
      :sub-title="error || '请稍候'"
    >
      <template #extra>
        <el-button v-if="error" type="primary" @click="$router.replace('/login')">返回登录</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { feishuCallbackApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import { navigateAfterLogin } from '@/utils/postLoginNavigate'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const error = ref('')

onMounted(async () => {
  const code = String(route.query.code || '')
  const state = route.query.state ? String(route.query.state) : undefined
  if (!code) {
    error.value = '缺少授权码，请重新从登录页发起飞书登录'
    return
  }

  try {
    const { data } = await feishuCallbackApi(code, state)
    userStore.loginWithFeishuResult(data)
    ElMessage.success('飞书登录成功')
    await navigateAfterLogin(router, data.redirect || route.query.redirect, userStore.homePath)
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : '飞书登录失败，请重试或联系管理员'
  }
})
</script>

<style scoped>
.callback-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--crm-canvas);
}
</style>
