<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <img class="login-logo" src="/ztxd-logo.png" alt="中泰旭鼎" width="56" height="56" />
        <h1 class="title">中泰旭鼎CRM</h1>
      </div>
      <p class="subtitle">公司内部经营管理系统</p>

      <el-button
        v-if="feishuEnabled"
        class="feishu-btn"
        :loading="feishuLoading"
        @click="onFeishuLogin"
      >
        飞书登录
      </el-button>

      <button
        v-if="feishuEnabled && !showPasswordForm"
        type="button"
        class="password-toggle"
        @click="showPasswordForm = true"
      >
        使用账号密码登录
      </button>

      <template v-if="!feishuEnabled || showPasswordForm">
        <div v-if="feishuEnabled" class="divider"><span>账号密码</span></div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="onSubmit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" clearable />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              clearable
            />
          </el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="onSubmit">
            登录
          </el-button>
        </el-form>

        <button
          v-if="feishuEnabled"
          type="button"
          class="password-toggle"
          @click="showPasswordForm = false"
        >
          收起
        </button>
      </template>

      <p class="hint">
        {{ feishuEnabled ? '未绑定飞书账号时请联系管理员' : '默认管理员：admin / admin123' }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { fetchFeishuAuthorizeUrlApi, fetchFeishuConfigApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const feishuLoading = ref(false)
const feishuEnabled = ref(false)
const showPasswordForm = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(async () => {
  for (let i = 0; i < 3; i++) {
    try {
      const { data } = await fetchFeishuConfigApi()
      feishuEnabled.value = data.enabled
      showPasswordForm.value = !data.enabled
      return
    } catch {
      if (i < 2) await new Promise((r) => setTimeout(r, 800))
    }
  }
  feishuEnabled.value = false
  showPasswordForm.value = true
})

async function onFeishuLogin() {
  feishuLoading.value = true
  try {
    const redirect = (route.query.redirect as string) || '/dashboard'
    const { data } = await fetchFeishuAuthorizeUrlApi(redirect)
    window.location.href = data.authorize_url
  } catch {
    // 错误已在 axios 拦截器提示
  } finally {
    feishuLoading.value = false
  }
}

async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || userStore.homePath
    router.replace(redirect)
  } catch {
    // 错误已在 axios 拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--crm-space-6);
  background:
    radial-gradient(circle at 18% 12%, rgba(196, 92, 38, 0.18), transparent 36%),
    linear-gradient(165deg, var(--crm-nav) 0%, #163556 52%, #1b4f8a 100%);
}

.login-card {
  width: min(400px, 100%);
  padding: var(--crm-space-8) var(--crm-space-6) var(--crm-space-6);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--crm-radius-lg);
  background: var(--crm-surface);
  box-shadow: 0 18px 48px rgba(15, 39, 68, 0.32);
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.login-logo {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  object-fit: cover;
  background: #000;
  box-shadow: 0 8px 20px oklch(0.2 0.04 252 / 0.25);
}

.title {
  margin: 0;
  color: var(--crm-ink);
  font-family: var(--crm-font-display);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-align: center;
}

.subtitle {
  margin: var(--crm-space-2) 0 var(--crm-space-6);
  color: var(--crm-ink-soft);
  font-size: 13px;
  text-align: center;
}

.feishu-btn {
  width: 100%;
  min-height: 40px;
  color: var(--crm-white);
  border: 0;
  background: var(--crm-primary);
}

.feishu-btn:hover {
  color: var(--crm-white);
  background: var(--crm-primary-strong);
}

@media (max-width: 480px) {
  .login-page {
    padding: var(--crm-space-4);
    place-items: stretch center;
    align-content: center;
  }

  .login-card {
    width: 100%;
    border-radius: var(--crm-radius-md);
  }
}

.password-toggle {
  display: block;
  width: 100%;
  margin-top: var(--crm-space-4);
  padding: 0;
  border: 0;
  color: var(--crm-ink-soft);
  font-size: 13px;
  text-align: center;
  background: transparent;
  cursor: pointer;
}

.password-toggle:hover {
  color: var(--crm-primary);
}

.divider {
  display: flex;
  align-items: center;
  gap: var(--crm-space-3);
  margin: var(--crm-space-5) 0;
  color: var(--crm-ink-faint);
  font-size: 12px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--crm-border);
}

.submit-btn {
  width: 100%;
  margin-top: var(--crm-space-2);
  min-height: 40px;
}

.hint {
  margin: var(--crm-space-5) 0 0;
  color: var(--crm-ink-faint);
  font-size: 12px;
  text-align: center;
}
</style>
