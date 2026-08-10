<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true">
      <ColorBendsMount
        v-if="showLanyard"
        :colors="loginBgColors"
        :transparent="true"
      />
      <div v-else class="login-bg__image" />
      <div class="login-bg__vignette" />
    </div>

    <div class="login-stage" role="main">
      <LanyardMount
        v-if="showLanyard"
        class="login-lanyard"
        with-login
        :position="[0, 0, 11.85]"
        :gravity="[0, -32, 0]"
        :fov="17"
        :transparent="true"
        :feishu-enabled="feishuEnabled"
        :loading="loading"
        :feishu-loading="feishuLoading"
        :hint="hintText"
        @submit="onCardSubmit"
        @feishu="onFeishuLogin"
      />

      <!-- reduced-motion：平面工牌，视觉与 3D 卡面一致 -->
      <section v-else class="login-fallback" aria-label="登录">
        <div class="login-fallback__card">
          <div class="login-fallback__slot" aria-hidden="true" />
          <div class="login-fallback__tape" aria-hidden="true">高效办公 高效沟通</div>

          <header class="login-fallback__header">
            <div class="login-fallback__mark" aria-hidden="true">
              <span>CRM</span>
              <span>OKR</span>
            </div>
            <div class="login-fallback__seal" aria-hidden="true">
              <span>企业经营</span>
              <span>工作台</span>
            </div>
          </header>

          <div class="login-fallback__title">
            <h1>中泰旭鼎集团</h1>
            <p>ZHONGTAIXUDING GROUP</p>
          </div>

          <ul class="login-fallback__tags" aria-label="功能标签">
            <li>财务报表</li>
            <li>数据统计</li>
            <li>销售管理</li>
          </ul>

          <div class="login-fallback__rule" aria-hidden="true" />

          <div class="login-fallback__body">
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
                  placeholder="密  码"
                  show-password
                  clearable
                />
              </el-form-item>
              <button
                type="button"
                class="submit-btn"
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
import { computed, defineAsyncComponent, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, InputInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { fetchFeishuAuthorizeUrlApi, fetchFeishuConfigApi } from '@/api/auth'
import { getToken } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { navigateAfterLogin, resolvePostLoginPath } from '@/utils/postLoginNavigate'

const LanyardMount = defineAsyncComponent(() => import('@/components/lanyard/LanyardMount.vue'))
const ColorBendsMount = defineAsyncComponent(
  () => import('@/components/backgrounds/ColorBendsMount.vue'),
)

const loginBgColors = ['#29ffdb', '#bc719d', '#7cff67', '#da0b0b']

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const usernameInputRef = ref<InputInstance>()
const loading = ref(false)
const feishuLoading = ref(false)
const feishuEnabled = ref(false)
const showLanyard = ref(
  typeof window !== 'undefined' &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
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
      if (!data.enabled && !showLanyard.value) await focusUsername()
      return
    } catch {
      if (i < 2) await new Promise((r) => setTimeout(r, 800))
    }
  }
  feishuEnabled.value = false
  if (!showLanyard.value) await focusUsername()
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

/** 3D 工牌表单提交：走同一套 login 接口 */
async function onCardSubmit(username: string, password: string) {
  loading.value = true
  try {
    await userStore.login(username, password)
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
  --badge-bg: #d1d1d1;
  --badge-yellow: #ffc145;
  --badge-ink: #0a0a0a;
  --badge-muted: #9a9a9a;
  --badge-field: #c8c8c8;
  --badge-field-border: #5a5a5a;

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
    radial-gradient(ellipse 70% 65% at 50% 45%, transparent 35%, rgba(4, 8, 16, 0.4) 100%);
}

.login-stage {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100vh;
  min-height: 560px;
}

.login-lanyard {
  width: 100%;
  height: 100%;
}

.login-fallback {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 24px;
}

.login-fallback__card {
  position: relative;
  width: min(340px, 100%);
  min-height: 520px;
  padding: 28px 22px 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 28px;
  color: var(--badge-ink);
  background:
    radial-gradient(ellipse 120% 80% at 50% 0%, rgba(255, 255, 255, 0.22), transparent 55%),
    var(--badge-bg);
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.45);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.login-fallback__card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.28;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 140px 140px;
  mix-blend-mode: soft-light;
  z-index: 0;
}

.login-fallback__card > * {
  position: relative;
  z-index: 1;
}

.login-fallback__slot {
  width: 52px;
  height: 14px;
  margin: 0 auto 10px;
  border-radius: 999px;
  background: #1a1a1a;
  box-shadow:
    inset 0 2px 4px rgba(0, 0, 0, 0.55),
    0 1px 0 rgba(255, 255, 255, 0.35);
}

.login-fallback__tape {
  position: absolute;
  top: 18px;
  right: -10px;
  z-index: 2;
  width: 132px;
  padding: 6px 12px;
  background: var(--badge-yellow);
  color: var(--badge-ink);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.01em;
  line-height: 1.15;
  text-align: center;
  white-space: nowrap;
  transform: rotate(-20deg);
  box-shadow: 1px 3px 6px rgba(0, 0, 0, 0.22);
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

.login-fallback__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-right: 6px;
  margin-top: 4px;
}

.login-fallback__mark {
  display: flex;
  flex-direction: column;
  font-size: 32px;
  font-weight: 900;
  line-height: 0.9;
  letter-spacing: -0.03em;
}

.login-fallback__seal {
  width: 70px;
  height: 70px;
  margin-top: 4px;
  margin-right: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  border-radius: 50%;
  background: var(--badge-yellow);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.25);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.2;
  text-align: center;
  letter-spacing: 0.06em;
}

.login-fallback__title {
  margin-top: 18px;
  text-align: center;
}

.login-fallback__title h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: 0.06em;
}

.login-fallback__title p {
  margin: 5px 0 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  line-height: 1.2;
}

.login-fallback__tags {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}

.login-fallback__tags li {
  min-width: 72px;
  padding: 6px 10px;
  background: var(--badge-yellow);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: center;
  line-height: 1.2;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.16);
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

.login-fallback__rule {
  height: 4px;
  margin: 18px 4px 16px;
  background: var(--badge-yellow);
  border-radius: 0;
}

.login-fallback__body {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feishu-btn,
.submit-btn {
  display: block;
  width: 100%;
  min-height: 44px;
  border: 0;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
}

.feishu-btn {
  color: #fff;
  background: #0a0a0a;
  letter-spacing: 0.12em;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}

.feishu-btn:disabled,
.submit-btn:disabled {
  opacity: 0.72;
  cursor: wait;
}

.submit-btn {
  color: var(--badge-ink);
  background: var(--badge-yellow);
  letter-spacing: 0.35em;
  text-indent: 0.35em;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
}

.login-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.login-form :deep(.el-form-item__error) {
  padding-top: 2px;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 999px;
  background: var(--badge-field) !important;
  box-shadow: 0 0 0 1.5px var(--badge-field-border) inset !important;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1.5px #111 inset,
    0 0 0 2px rgba(255, 193, 69, 0.45) !important;
}

.login-form :deep(.el-input__inner) {
  color: var(--badge-ink);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #2a2a2a;
  opacity: 0.85;
}

.hint {
  margin: 14px 0 0;
  color: var(--badge-muted);
  font-size: 11px;
  font-weight: 500;
  text-align: center;
  line-height: 1.4;
  letter-spacing: 0.02em;
}
</style>
