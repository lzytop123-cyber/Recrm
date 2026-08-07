<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true">
      <div class="login-bg__void" />
      <div class="login-bg__horizon" />
      <div class="login-bg__orb login-bg__orb--a" />
      <div class="login-bg__orb login-bg__orb--b" />
      <div class="login-bg__grain" />
      <div class="login-bg__vignette" />
    </div>

    <div class="login-shell" role="main">
      <aside class="login-hero" aria-labelledby="login-brand-title">
        <div class="login-hero__content">
          <div class="login-brand">
            <img
              class="login-logo"
              src="/ztxd-logo.png"
              alt="中泰旭鼎"
              width="68"
              height="68"
            />
            <div>
              <p class="login-eyebrow">中泰旭鼎 · 经营台</p>
              <h1 id="login-brand-title" class="title">中泰旭鼎CRM</h1>
            </div>
          </div>

          <p class="hero-lead">把线索、合同、交付与考核收进同一条经营链路</p>

          <svg
            class="flow-path"
            viewBox="0 0 360 88"
            fill="none"
            role="img"
            aria-label="经营链路：线索到交付"
          >
            <path
              class="flow-path__line"
              d="M12 44 C 70 12, 110 76, 170 44 S 260 8, 348 44"
              stroke="url(#flowGrad)"
              stroke-width="1.6"
              stroke-linecap="round"
            />
            <g class="flow-path__nodes">
              <circle cx="12" cy="44" r="4.5" />
              <circle cx="120" cy="52" r="4.5" />
              <circle cx="230" cy="28" r="4.5" />
              <circle cx="348" cy="44" r="4.5" />
            </g>
            <defs>
              <linearGradient id="flowGrad" x1="0" y1="0" x2="360" y2="0">
                <stop offset="0%" stop-color="#e8a06e" stop-opacity="0.25" />
                <stop offset="45%" stop-color="#c45c26" />
                <stop offset="100%" stop-color="#7aa0c8" stop-opacity="0.55" />
              </linearGradient>
            </defs>
          </svg>

          <ol class="flow-labels">
            <li>线索</li>
            <li>客户</li>
            <li>合同</li>
            <li>交付</li>
          </ol>
        </div>
      </aside>

      <section class="login-panel" aria-labelledby="login-form-title">
        <div class="login-card">
          <header class="login-card__header">
            <h2 id="login-form-title" class="panel-title">进入工作台</h2>
            <p class="panel-desc">用飞书账号，或公司账号密码登录</p>
          </header>

          <el-button
            v-if="feishuEnabled"
            class="feishu-btn"
            size="large"
            :loading="feishuLoading"
            :aria-busy="feishuLoading"
            @click="onFeishuLogin"
          >
            <span class="feishu-btn__inner">
              <el-icon v-if="!feishuLoading" :size="18"><ChatDotRound /></el-icon>
              飞书登录
            </span>
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
            <div v-if="feishuEnabled" class="divider" role="separator">
              <span>账号密码</span>
            </div>

            <el-form
              ref="formRef"
              class="login-form"
              :model="form"
              :rules="rules"
              label-position="top"
              require-asterisk-position="right"
              @keyup.enter="onSubmit"
            >
              <el-form-item label="用户名" prop="username">
                <el-input
                  ref="usernameInputRef"
                  v-model="form.username"
                  size="large"
                  name="username"
                  autocomplete="username"
                  placeholder="请输入用户名"
                  clearable
                />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="form.password"
                  size="large"
                  type="password"
                  name="password"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                  show-password
                  clearable
                />
              </el-form-item>
              <el-button
                class="submit-btn"
                size="large"
                :loading="loading"
                :aria-busy="loading"
                @click="onSubmit"
              >
                登录
              </el-button>
            </el-form>

            <button
              v-if="feishuEnabled"
              type="button"
              class="password-toggle"
              @click="showPasswordForm = false"
            >
              收起账号密码
            </button>
          </template>

          <p class="hint" role="note">
            {{
              feishuEnabled
                ? '未绑定飞书时请联系管理员开通'
                : '默认管理员：admin / admin123'
            }}
          </p>

          <p class="trust-line">内部系统 · 权限分级 · 操作可追溯</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, InputInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { fetchFeishuAuthorizeUrlApi, fetchFeishuConfigApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const usernameInputRef = ref<InputInstance>()
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

async function focusUsername() {
  await nextTick()
  usernameInputRef.value?.focus?.()
}

watch(showPasswordForm, (visible) => {
  if (visible) void focusUsername()
})

onMounted(async () => {
  for (let i = 0; i < 3; i++) {
    try {
      const { data } = await fetchFeishuConfigApi()
      feishuEnabled.value = data.enabled
      showPasswordForm.value = !data.enabled
      if (!data.enabled) await focusUsername()
      return
    } catch {
      if (i < 2) await new Promise((r) => setTimeout(r, 800))
    }
  }
  feishuEnabled.value = false
  showPasswordForm.value = true
  await focusUsername()
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
/* 墨色经营台 · Midnight Ledger
   void #070d18 · ink #101c30 · steel #2a4a6e · copper #c45c26 · mist #a7b6c8 · paper #f3f6fa */
.login-page {
  --login-void: #070d18;
  --login-ink: #101c30;
  --login-steel: #2a4a6e;
  --login-copper: #c45c26;
  --login-copper-soft: #e8925a;
  --login-mist: #a7b6c8;
  --login-paper: #f3f6fa;
  --login-ease: cubic-bezier(0.16, 1, 0.3, 1);

  position: relative;
  isolation: isolate;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: clamp(16px, 3vw, 40px);
  overflow: hidden;
  color: var(--login-paper);
  background: var(--login-void);
}

.login-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.login-bg__void {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(165deg, #050a12 0%, #0c1628 42%, #13243d 72%, #1a3352 100%);
}

.login-bg__horizon {
  position: absolute;
  left: -10%;
  right: -10%;
  bottom: 18%;
  height: 42%;
  background:
    radial-gradient(ellipse 70% 55% at 50% 100%, rgba(196, 92, 38, 0.34), transparent 70%),
    radial-gradient(ellipse 45% 40% at 72% 80%, rgba(74, 122, 181, 0.22), transparent 65%);
  filter: blur(10px);
  animation: horizon-breathe 12s var(--login-ease) infinite alternate;
}

.login-bg__orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(4px);
}

.login-bg__orb--a {
  top: -8%;
  left: -6%;
  width: min(520px, 70vw);
  height: min(520px, 70vw);
  background: radial-gradient(circle at 40% 40%, rgba(232, 146, 90, 0.28), transparent 62%);
  animation: orb-a 16s ease-in-out infinite alternate;
}

.login-bg__orb--b {
  top: 8%;
  right: -10%;
  width: min(460px, 58vw);
  height: min(460px, 58vw);
  background: radial-gradient(circle at 45% 40%, rgba(90, 140, 200, 0.3), transparent 64%);
  animation: orb-b 18s ease-in-out infinite alternate;
}

.login-bg__grain {
  position: absolute;
  inset: 0;
  opacity: 0.05;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 200px 200px;
}

.login-bg__vignette {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 75% 70% at 50% 48%, transparent 30%, rgba(4, 8, 16, 0.72) 100%);
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: 1.12fr 0.88fr;
  min-height: min(560px, calc(100vh - 48px));
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 22px;
  background: color-mix(in oklab, var(--login-ink) 78%, transparent);
  backdrop-filter: blur(22px) saturate(1.2);
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  box-shadow:
    0 40px 100px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset,
    0 1px 0 rgba(255, 255, 255, 0.1) inset;
  animation: shell-enter 560ms var(--login-ease) both;
}

.login-hero {
  position: relative;
  padding: clamp(28px, 4vw, 48px);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.login-hero__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 22px;
  height: 100%;
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
}

.login-logo {
  width: 68px;
  height: 68px;
  flex-shrink: 0;
  border-radius: 16px;
  object-fit: cover;
  background: #000;
  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.35),
    0 0 0 1px rgba(255, 255, 255, 0.08);
}

.login-eyebrow {
  margin: 0 0 6px;
  color: var(--login-copper-soft);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.14em;
}

.title {
  margin: 0;
  color: #f7fafc;
  font-family: 'Noto Serif SC', 'Songti SC', 'Noto Sans SC', serif;
  font-size: clamp(28px, 3.4vw, 36px);
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.15;
}

.hero-lead {
  margin: 0;
  max-width: 28em;
  color: var(--login-mist);
  font-size: 15px;
  line-height: 1.65;
}

.flow-path {
  width: min(100%, 360px);
  height: auto;
  margin-top: auto;
}

.flow-path__line {
  stroke-dasharray: 420;
  stroke-dashoffset: 420;
  animation: draw-flow 1.4s var(--login-ease) 0.25s forwards;
}

.flow-path__nodes circle {
  fill: var(--login-copper-soft);
  opacity: 0;
  animation: node-in 420ms var(--login-ease) forwards;
}

.flow-path__nodes circle:nth-child(1) { animation-delay: 0.45s; }
.flow-path__nodes circle:nth-child(2) { animation-delay: 0.65s; }
.flow-path__nodes circle:nth-child(3) { animation-delay: 0.85s; }
.flow-path__nodes circle:nth-child(4) { animation-delay: 1.05s; }

.flow-labels {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  width: min(100%, 360px);
  margin: 0;
  padding: 0;
  list-style: none;
  color: rgba(167, 182, 200, 0.88);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.flow-labels li {
  text-align: center;
}

.login-panel {
  display: grid;
  place-items: center;
  padding: clamp(24px, 3vw, 40px) clamp(20px, 3vw, 36px);
  background:
    linear-gradient(180deg, rgba(243, 246, 250, 0.97), rgba(236, 241, 247, 0.98));
}

.login-card {
  width: min(352px, 100%);
}

.login-card__header {
  margin-bottom: 28px;
}

.panel-title {
  margin: 0;
  color: #0f2744;
  font-family: 'Noto Serif SC', 'Songti SC', 'Noto Sans SC', serif;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.panel-desc {
  margin: 8px 0 0;
  color: #5a6b7d;
  font-size: 13px;
  line-height: 1.5;
}

.feishu-btn {
  width: 100%;
  min-height: 46px;
  color: #fff !important;
  border: 0 !important;
  border-radius: 12px;
  background: linear-gradient(135deg, #1b4f8a, #143d6b) !important;
  box-shadow: 0 10px 24px rgba(20, 61, 107, 0.28);
  transition:
    transform 180ms var(--login-ease),
    box-shadow 180ms var(--login-ease),
    filter 180ms var(--login-ease);
}

.feishu-btn:hover {
  filter: brightness(1.06);
  box-shadow: 0 14px 28px rgba(20, 61, 107, 0.34);
}

.feishu-btn:active {
  transform: scale(0.985);
}

.feishu-btn__inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.password-toggle {
  display: block;
  width: 100%;
  margin-top: 16px;
  padding: 8px 0;
  border: 0;
  color: #5a6b7d;
  font-size: 13px;
  text-align: center;
  background: transparent;
  cursor: pointer;
  transition: color 160ms var(--login-ease);
}

.password-toggle:hover {
  color: #1b4f8a;
}

.password-toggle:focus-visible {
  outline: 2px solid #4a7ab5;
  outline-offset: 2px;
  border-radius: 6px;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 22px 0;
  color: #8a97a8;
  font-size: 12px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #d5dde7;
}

.login-form :deep(.el-form-item__label) {
  color: #0f2744;
  font-weight: 600;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #d5dde7 inset;
  transition: box-shadow 180ms var(--login-ease);
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #b8c2cf inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px #1b4f8a inset,
    0 0 0 3px rgba(74, 122, 181, 0.22);
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
  min-height: 46px;
  color: #fff !important;
  border: 0 !important;
  border-radius: 12px;
  background: linear-gradient(135deg, #c45c26, #a74a1c) !important;
  box-shadow:
    0 12px 28px rgba(196, 92, 38, 0.32),
    0 0 0 1px rgba(255, 255, 255, 0.08) inset;
  transition:
    transform 180ms var(--login-ease),
    box-shadow 180ms var(--login-ease),
    filter 180ms var(--login-ease);
}

.submit-btn:hover {
  filter: brightness(1.05);
  box-shadow: 0 16px 32px rgba(196, 92, 38, 0.38);
}

.submit-btn:active {
  transform: scale(0.985);
}

.hint {
  margin: 22px 0 0;
  color: #8a97a8;
  font-size: 12px;
  text-align: center;
  line-height: 1.5;
}

.trust-line {
  margin: 14px 0 0;
  color: #6b7c90;
  font-size: 12px;
  text-align: center;
  letter-spacing: 0.04em;
}

@keyframes shell-enter {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes draw-flow {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes node-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes horizon-breathe {
  from {
    opacity: 0.85;
    transform: translateY(6px) scale(1);
  }
  to {
    opacity: 1;
    transform: translateY(-4px) scale(1.04);
  }
}

@keyframes orb-a {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(24px, 30px, 0); }
}

@keyframes orb-b {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(-28px, 18px, 0); }
}

@media (max-width: 860px) {
  .login-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .login-hero {
    min-height: 200px;
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .flow-path,
  .flow-labels {
    display: none;
  }
}

@media (max-width: 480px) {
  .login-page {
    padding: 12px;
    place-items: stretch;
  }

  .login-shell {
    min-height: calc(100vh - 24px);
    border-radius: 18px;
  }

  .login-logo {
    width: 56px;
    height: 56px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-shell,
  .login-bg__horizon,
  .login-bg__orb,
  .flow-path__line,
  .flow-path__nodes circle {
    animation: none !important;
  }

  .flow-path__line {
    stroke-dashoffset: 0;
  }

  .flow-path__nodes circle {
    opacity: 1;
  }

  .feishu-btn,
  .submit-btn,
  .password-toggle,
  .login-form :deep(.el-input__wrapper) {
    transition: none;
  }
}
</style>
