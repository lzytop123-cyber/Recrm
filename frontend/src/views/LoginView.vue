<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true">
      <div class="login-bg__image" />
      <div class="login-bg__vignette" />
    </div>

    <div class="login-stage" role="main">
      <section class="login-card-wrap" aria-label="登录">
        <div class="login-card">
          <div class="login-card__slot" aria-hidden="true" />
          <div class="login-card__tape" aria-hidden="true">高效办公 · 高效沟通</div>

          <header class="login-card__brand">
            <p class="login-card__product">CRM · OKR</p>
            <h1>中泰旭鼎集团</h1>
            <p class="login-card__en">ZHONGTAIXUDING GROUP</p>
          </header>

          <ul class="login-card__tags" aria-label="功能标签">
            <li>财务报表</li>
            <li>数据统计</li>
            <li>销售管理</li>
          </ul>

          <div class="login-card__rule" aria-hidden="true" />

          <div class="login-card__body">
            <button
              v-if="feishuEnabled"
              type="button"
              class="feishu-btn"
              :disabled="feishuLoading"
              :aria-busy="feishuLoading"
              @click="onFeishuLogin"
            >
              {{ feishuLoading ? '跳转中…' : '飞书登录' }}
            </button>

            <div v-if="feishuEnabled" class="login-card__divider" role="separator">
              <span>或使用账号密码</span>
            </div>

            <el-form
              ref="formRef"
              class="login-form"
              :model="form"
              :rules="rules"
              @keyup.enter="onSubmit"
            >
              <el-form-item prop="username">
                <el-input
                  ref="usernameInputRef"
                  v-model="form.username"
                  name="username"
                  autocomplete="username"
                  placeholder="用户名"
                  clearable
                />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="form.password"
                  type="password"
                  name="password"
                  autocomplete="current-password"
                  placeholder="密码"
                  show-password
                  clearable
                />
              </el-form-item>
              <button
                type="button"
                class="submit-btn"
                :class="{ 'is-secondary': feishuEnabled }"
                :disabled="loading"
                :aria-busy="loading"
                @click="onSubmit"
              >
                {{ loading ? '登录中…' : '登 录' }}
              </button>
            </el-form>
          </div>

          <p class="hint" role="note">{{ hintText }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, InputInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { fetchFeishuAuthorizeUrlApi, fetchFeishuConfigApi } from '@/api/auth'
import { getToken } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { navigateAfterLogin, resolvePostLoginPath } from '@/utils/postLoginNavigate'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const usernameInputRef = ref<InputInstance>()
const loading = ref(false)
const feishuLoading = ref(false)
const feishuEnabled = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'submit' }],
  password: [{ required: true, message: '请输入密码', trigger: 'submit' }],
}

const hintText = computed(() =>
  feishuEnabled.value ? '未绑定飞书时请联系管理员开通' : '默认管理员：admin / admin123',
)

async function focusUsername() {
  await nextTick()
  usernameInputRef.value?.focus?.()
}

onMounted(async () => {
  // 已有登录态时不要停在登录页（移动端返回 / WebView 残留常见）
  if (getToken()) {
    if (!userStore.user) {
      try {
        await userStore.fetchProfile()
      } catch {
        /* 交给下方表单重新登录 */
      }
    }
    if (userStore.user) {
      await navigateAfterLogin(router, route.query.redirect, userStore.homePath)
      return
    }
  }

  for (let i = 0; i < 3; i++) {
    try {
      const { data } = await fetchFeishuConfigApi()
      feishuEnabled.value = data.enabled
      if (!data.enabled) await focusUsername()
      return
    } catch {
      if (i < 2) await new Promise((r) => setTimeout(r, 800))
    }
  }
  feishuEnabled.value = false
  await focusUsername()
})

async function onFeishuLogin() {
  feishuLoading.value = true
  try {
    const redirect = resolvePostLoginPath(route.query.redirect, userStore.homePath || '/dashboard')
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
    await navigateAfterLogin(router, route.query.redirect, userStore.homePath)
  } catch {
    // 错误已在 axios 拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  --badge-bg: #d6d6d6;
  --badge-yellow: #ffc145;
  --badge-ink: #111111;
  --badge-muted: #6e6e6e;
  --badge-field: #f3f3f3;
  --badge-field-border: #3f3f3f;

  position: relative;
  isolation: isolate;
  min-height: 100vh;
  overflow: hidden;
  background: #070d18;
}

.login-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.login-bg__image {
  position: absolute;
  inset: 0;
  background: #070d18 url('/login-bg.png') center / cover no-repeat;
}

.login-bg__vignette {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 65% at 50% 45%, transparent 35%, rgba(4, 8, 16, 0.45) 100%);
}

.login-stage {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: 100vh;
}

.login-card-wrap {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: max(20px, env(safe-area-inset-top)) 20px max(24px, env(safe-area-inset-bottom));
}

.login-card {
  position: relative;
  width: min(420px, 100%);
  padding: 32px 28px 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 28px;
  color: var(--badge-ink);
  background:
    radial-gradient(ellipse 120% 80% at 50% 0%, rgba(255, 255, 255, 0.28), transparent 55%),
    var(--badge-bg);
  box-shadow:
    0 28px 70px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.35);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.login-card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.22;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 140px 140px;
  mix-blend-mode: soft-light;
  z-index: 0;
}

.login-card > * {
  position: relative;
  z-index: 1;
}

.login-card__slot {
  width: 56px;
  height: 14px;
  margin: 0 auto 18px;
  border-radius: 999px;
  background: #1a1a1a;
  box-shadow:
    inset 0 2px 4px rgba(0, 0, 0, 0.55),
    0 1px 0 rgba(255, 255, 255, 0.35);
}

.login-card__tape {
  position: absolute;
  top: 26px;
  right: -18px;
  z-index: 2;
  width: 148px;
  padding: 8px 16px;
  background: var(--badge-yellow);
  color: var(--badge-ink);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
  transform: rotate(-18deg);
  box-shadow: 1px 3px 6px rgba(0, 0, 0, 0.2);
  clip-path: polygon(
    0% 6%,
    4% 0%,
    4% 14%,
    0% 22%,
    4% 30%,
    0% 38%,
    4% 46%,
    0% 54%,
    4% 62%,
    0% 70%,
    4% 78%,
    0% 86%,
    4% 94%,
    0% 100%,
    96% 100%,
    100% 94%,
    96% 86%,
    100% 78%,
    96% 70%,
    100% 62%,
    96% 54%,
    100% 46%,
    96% 38%,
    100% 30%,
    96% 22%,
    100% 14%,
    96% 0%
  );
}

.login-card__brand {
  margin-top: 2px;
  padding-right: 64px;
  text-align: left;
}

.login-card__product {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #333;
}

.login-card__brand h1 {
  margin: 0;
  font-size: clamp(30px, 7vw, 34px);
  font-weight: 900;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

.login-card__en {
  margin: 8px 0 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  line-height: 1.3;
  color: #3a3a3a;
}

.login-card__tags {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}

.login-card__tags li {
  padding: 6px 11px;
  background: var(--badge-yellow);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: center;
  line-height: 1.2;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.14);
  clip-path: polygon(
    0% 10%,
    4% 0%,
    4% 20%,
    0% 30%,
    4% 40%,
    0% 50%,
    4% 60%,
    0% 70%,
    4% 80%,
    0% 90%,
    4% 100%,
    96% 100%,
    100% 90%,
    96% 80%,
    100% 70%,
    96% 60%,
    100% 50%,
    96% 40%,
    100% 30%,
    96% 20%,
    100% 10%,
    96% 0%
  );
}

.login-card__rule {
  height: 3px;
  margin: 18px 0 16px;
  background: var(--badge-yellow);
}

.login-card__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.login-card__divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--badge-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.login-card__divider::before,
.login-card__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.18);
}

.feishu-btn,
.submit-btn {
  display: block;
  width: 100%;
  min-height: 50px;
  border: 0;
  border-radius: 999px;
  font-size: 16px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  transition:
    transform 120ms ease,
    opacity 120ms ease,
    background-color 120ms ease,
    box-shadow 120ms ease;
}

.feishu-btn:hover:not(:disabled),
.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.feishu-btn:active:not(:disabled),
.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.feishu-btn {
  color: #fff;
  background: #0a0a0a;
  letter-spacing: 0.14em;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.28);
}

.feishu-btn:disabled,
.submit-btn:disabled {
  opacity: 0.72;
  cursor: wait;
}

.submit-btn {
  margin-top: 2px;
  color: var(--badge-ink);
  background: var(--badge-yellow);
  letter-spacing: 0.28em;
  text-indent: 0.28em;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.18);
}

.submit-btn.is-secondary {
  background: transparent;
  box-shadow: none;
  border: 1.5px solid #222;
  letter-spacing: 0.2em;
  text-indent: 0.2em;
}

.submit-btn.is-secondary:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.05);
}

.login-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.login-form :deep(.el-form-item__error) {
  position: static;
  margin-top: 6px;
  padding: 0 4px;
  font-size: 13px;
  line-height: 1.35;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 50px;
  padding: 0 18px;
  border-radius: 999px;
  background: var(--badge-field) !important;
  box-shadow: 0 0 0 1.5px var(--badge-field-border) inset !important;
  transition: box-shadow 140ms ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1.5px #1a1a1a inset !important;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1.5px #111 inset,
    0 0 0 3px rgba(255, 193, 69, 0.4) !important;
}

.login-form :deep(.el-input__inner) {
  color: var(--badge-ink);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #666;
  font-weight: 500;
  opacity: 1;
}

.hint {
  margin: 18px 0 0;
  color: var(--badge-muted);
  font-size: 12px;
  font-weight: 500;
  text-align: center;
  line-height: 1.45;
  letter-spacing: 0.02em;
}

@media (prefers-reduced-motion: reduce) {
  .feishu-btn,
  .submit-btn,
  .login-form :deep(.el-input__wrapper) {
    transition: none;
  }
}

@media (max-width: 480px) {
  .login-card {
    padding: 26px 20px 18px;
    border-radius: 24px;
  }

  .login-card__brand {
    padding-right: 52px;
  }

  .login-card__tape {
    width: 132px;
    right: -22px;
    font-size: 10px;
  }
}
</style>
