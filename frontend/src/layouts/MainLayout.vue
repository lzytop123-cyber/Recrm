<template>
  <el-container class="layout" :class="{ 'nav-open': navOpen }">
    <div v-if="navOpen" class="nav-backdrop" @click="navOpen = false" />

    <el-aside class="aside" width="220px">
      <div class="brand">
        <img class="brand-mark" src="/ztxd-logo.png" alt="" width="32" height="32" />
        <span class="brand-text">中泰旭鼎CRM</span>
      </div>

      <nav class="aside-nav" aria-label="主导航">
        <el-menu
          :key="activeMenu"
          :default-active="activeMenu"
          background-color="transparent"
          text-color="var(--crm-nav-text)"
          active-text-color="var(--crm-white)"
          router
          @select="onMenuSelect"
        >
          <el-menu-item v-for="item in userStore.menus" :key="item.path" :index="item.path">
            <el-icon v-if="item.icon">
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </nav>

      <div class="sidebar-foot">
        <button
          v-if="userStore.hasPermission('org:view')"
          type="button"
          class="sync-status-btn"
          :title="syncHint"
          @click="refreshSyncStatus"
        >
          <span class="sync-icon">↻</span>
          <span class="sync-copy">
            <b>{{ syncStatus?.overall_label || '飞书同步' }}</b>
            <small>{{ syncTimeLabel }}</small>
          </span>
        </button>
        <div class="account-wrap" ref="accountWrapRef">
          <button
            type="button"
            class="user-card"
            :aria-expanded="accountOpen"
            aria-controls="accountMenu"
            aria-label="打开账户菜单"
            @click.stop="toggleAccountMenu"
          >
            <span class="avatar">{{ avatarChar }}</span>
            <span class="user-copy">
              <b>{{ userStore.displayName }}</b>
              <small>{{ roleLabel }}</small>
            </span>
            <span class="account-more" aria-hidden="true">•••</span>
          </button>
          <div v-show="accountOpen" id="accountMenu" class="account-menu" @click.stop>
            <div class="account-menu-head">
              <b>{{ userStore.displayName }}</b>
              <small>{{ roleLabel }} · {{ scopeLongLabel }}</small>
            </div>
            <button type="button" @click="onAccountAction('profile')">
              <span>个人资料</span>
              <small>账号信息与飞书绑定</small>
            </button>
            <button
              v-if="userStore.hasPermission('approval:center')"
              type="button"
              @click="onAccountAction('notifications')"
            >
              <span>审批中心</span>
              <small>查看待我审批的事项</small>
            </button>
            <button type="button" @click="onAccountAction('permissions')">
              <span>权限与数据范围</span>
              <small>查看当前角色授权</small>
            </button>
            <button type="button" class="account-logout" @click="onAccountAction('logout')">
              <span>退出登录</span>
            </button>
          </div>
        </div>
      </div>
    </el-aside>

    <el-container class="content-shell">
      <el-header class="header">
        <div class="header-left">
          <button type="button" class="menu-toggle" aria-label="打开导航" @click="navOpen = !navOpen">
            <span />
            <span />
            <span />
          </button>
          <template v-if="salesCrumb">
            <span class="crumb-muted">销售中心</span>
            <b class="crumb-sep">/</b>
            <strong>{{ salesCrumb }}</strong>
          </template>
          <template v-else>
            <strong class="page-title">{{ currentTitle }}</strong>
          </template>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <el-dialog v-model="profileVisible" title="账户信息" width="480px" destroy-on-close>
      <div class="account-dialog-grid">
        <div class="account-cell"><small>姓名</small><b>{{ userStore.displayName }}</b></div>
        <div class="account-cell"><small>用户名</small><b>{{ userStore.user?.username || '—' }}</b></div>
        <div class="account-cell"><small>当前角色</small><b>{{ roleLabel }}</b></div>
        <div class="account-cell"><small>数据范围</small><b>{{ scopeLongLabel }}</b></div>
        <div class="account-cell"><small>手机</small><b>{{ userStore.user?.phone || '—' }}</b></div>
        <div class="account-cell"><small>邮箱</small><b>{{ userStore.user?.email || '—' }}</b></div>
      </div>
      <p class="account-dialog-note">个人资料变更由员工档案统一维护；飞书绑定信息在员工管理模块查看。</p>
      <template #footer>
        <el-button type="primary" @click="profileVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permVisible" title="权限与数据范围" width="480px" destroy-on-close>
      <div class="account-dialog-grid">
        <div class="account-cell"><small>系统角色</small><b>{{ roleLabel }}</b></div>
        <div class="account-cell"><small>数据范围</small><b>{{ scopeLongLabel }}</b></div>
      </div>
      <div class="account-perm-list">
        <div class="account-perm-row"><span>菜单与模块</span><b>按角色授权</b></div>
        <div class="account-perm-row"><span>经营、客户与项目数据</span><b>{{ scopeViewLabel }}</b></div>
        <div class="account-perm-row"><span>部门执行与员工工作数据</span><b>{{ scopeViewLabel }}</b></div>
        <div class="account-perm-row"><span>操作记录</span><b>全程留痕</b></div>
      </div>
      <template #footer>
        <el-button type="primary" @click="permVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { fetchFeishuSyncStatus, type FeishuSyncStatus } from '@/api/org'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const navOpen = ref(false)
const accountOpen = ref(false)
const accountWrapRef = ref<HTMLElement | null>(null)
const profileVisible = ref(false)
const permVisible = ref(false)
const syncStatus = ref<FeishuSyncStatus | null>(null)

const syncTimeLabel = computed(() => {
  const at = syncStatus.value?.last_sync_at
  if (!at) return '尚未同步'
  const d = new Date(at)
  if (Number.isNaN(d.getTime())) return '最近同步 —'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `最近同步 ${hh}:${mm}`
})
const syncHint = computed(() => {
  const items = syncStatus.value?.items || []
  return items.map((x) => `${x.key}: ${x.status}`).join(' · ') || '点击刷新同步状态'
})

async function refreshSyncStatus() {
  if (!userStore.hasPermission('org:view')) return
  try {
    const { data } = await fetchFeishuSyncStatus()
    syncStatus.value = data
  } catch {
    /* 侧栏状态失败时静默 */
  }
}

watch(
  () => route.fullPath,
  () => {
    navOpen.value = false
    accountOpen.value = false
  },
)

const activeMenu = computed(() => {
  const path = route.path
  const prefixes = [
    '/sales',
    '/leads',
    '/customers',
    '/opportunities',
    '/contracts',
    '/payments',
    '/projects',
    '/okrs',
    '/assets',
    '/timesheets',
    '/tickets',
    '/schedules',
    '/org',
    '/system',
    '/approvals',
  ]
  for (const p of prefixes) {
    if (path === p || path.startsWith(`${p}/`)) return p
  }
  return path
})
const currentTitle = computed(() => (route.meta.title as string) || '')
const salesCrumb = computed(() => {
  if (route.path !== '/sales' && !route.path.startsWith('/sales')) return ''
  const tab = String(route.query.tab || '')
  if (tab === 'mine') return '我的线索'
  if (tab === 'customers') return '客户与商机'
  if (tab === 'contracts') return '合同与回款'
  if (tab === 'pool') return '线索总览'
  return '线索总览'
})

const avatarChar = computed(() => {
  const name = userStore.displayName || '?'
  return name.slice(0, 1)
})
const roleLabel = computed(() => {
  const roles = userStore.user?.roles || []
  if (!roles.length) return '未分配角色'
  return roles.map((r) => r.name).join('、')
})
const scopeLongLabel = computed(() => {
  const scope = userStore.user?.data_scope
  if (scope === 'company') return '全公司'
  if (scope === 'department') return '本部门'
  if (scope === 'personal') return '仅个人'
  return scope || '—'
})
const scopeViewLabel = computed(() => {
  const scope = userStore.user?.data_scope
  if (scope === 'company') return '可查看'
  if (scope === 'department') return '本部门'
  return '本人相关'
})

function onMenuSelect() {
  navOpen.value = false
}

function toggleAccountMenu() {
  accountOpen.value = !accountOpen.value
}

function closeAccountMenu() {
  accountOpen.value = false
}

function onDocClick(e: MouseEvent) {
  const el = accountWrapRef.value
  if (!el) return
  if (!el.contains(e.target as Node)) closeAccountMenu()
}

function onDocKey(e: KeyboardEvent) {
  if (e.key === 'Escape') closeAccountMenu()
}

async function onAccountAction(action: 'profile' | 'notifications' | 'permissions' | 'logout') {
  closeAccountMenu()
  if (action === 'profile') {
    profileVisible.value = true
    return
  }
  if (action === 'notifications') {
    router.push('/approvals')
    return
  }
  if (action === 'permissions') {
    permVisible.value = true
    return
  }
  try {
    await ElMessageBox.confirm(
      '退出后需要重新登录，当前未提交的表单内容不会保留。',
      '确认退出当前账号',
      {
        confirmButtonText: '确认退出',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await userStore.logout()
    router.push('/login')
  } catch {
    /* cancel */
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKey)
  refreshSyncStatus()
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKey)
})
</script>

<style scoped>
.layout {
  height: 100vh;
  background: var(--crm-canvas);
}

.aside {
  display: flex;
  flex-direction: column;
  background: var(--crm-nav);
  border-right: 1px solid var(--crm-nav-border);
  overflow: hidden;
  z-index: 40;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  height: var(--crm-header-height);
  padding: 0 var(--crm-space-4);
  border-bottom: 1px solid var(--crm-nav-border);
}

.brand-mark {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  object-fit: cover;
  background: #000;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.brand-text {
  color: var(--crm-white);
  font-family: var(--crm-font-display);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.aside-nav {
  flex: 1;
  min-height: 0;
  padding: var(--crm-space-3) 0 var(--crm-space-4);
  overflow-y: auto;
}

.aside :deep(.el-menu) {
  width: 100%;
  border-right: 0;
  background: transparent;
}

.aside :deep(.el-menu-item) {
  height: 42px;
  margin: 2px var(--crm-space-3);
  padding: 0 var(--crm-space-3) !important;
  border-radius: var(--crm-radius-md);
  color: var(--crm-nav-text);
  transition:
    background-color var(--crm-duration-fast) var(--crm-ease-out),
    color var(--crm-duration-fast) var(--crm-ease-out);
}

.aside :deep(.el-menu-item .el-icon) {
  margin-right: var(--crm-space-2);
  font-size: 16px;
  color: inherit;
}

.aside :deep(.el-menu-item span) {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
}

.aside :deep(.el-menu-item:hover) {
  background: var(--crm-nav-hover) !important;
  color: var(--crm-white) !important;
}

.aside :deep(.el-menu-item.is-active) {
  background: var(--crm-primary) !important;
  color: var(--crm-white) !important;
  font-weight: 600;
  box-shadow: 0 6px 16px rgba(27, 79, 138, 0.28);
}

.aside :deep(.el-menu-item.is-active .el-icon) {
  color: var(--crm-white);
}

.sidebar-foot {
  flex-shrink: 0;
  margin-top: auto;
  padding: 10px 12px 14px;
  border-top: 1px solid var(--crm-nav-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sync-status-btn {
  width: 100%;
  border: 0;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--crm-nav-text);
  padding: 8px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  cursor: pointer;
}
.sync-status-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}
.sync-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.sync-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sync-copy b {
  font-size: 12px;
  font-weight: 650;
}
.sync-copy small {
  font-size: 11px;
  opacity: 0.72;
}

.account-wrap {
  position: relative;
}

.user-card {
  width: 100%;
  min-height: 50px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: var(--crm-nav-text);
  padding: 8px 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  cursor: pointer;
}

.user-card:hover,
.user-card[aria-expanded='true'] {
  background: rgba(255, 255, 255, 0.055);
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: color-mix(in oklab, var(--crm-primary) 22%, #fff);
  color: var(--crm-primary);
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.user-copy {
  min-width: 0;
  flex: 1;
}

.user-copy b,
.user-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-copy b {
  color: #edf6f4;
  font-size: 13px;
  font-weight: 650;
}

.user-copy small {
  font-size: 11px;
  margin-top: 2px;
  color: color-mix(in oklab, var(--crm-nav-text) 80%, transparent);
}

.account-more {
  color: #7f9692;
  font-size: 13px;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.account-menu {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 58px;
  z-index: 70;
  padding: 7px;
  border: 1px solid rgba(16, 38, 38, 0.1);
  border-radius: 13px;
  background: var(--crm-surface);
  color: var(--crm-ink);
  box-shadow: 0 18px 44px rgba(5, 24, 22, 0.28);
}

.account-menu-head {
  padding: 9px 10px 10px;
  border-bottom: 1px solid var(--crm-border);
  margin-bottom: 4px;
}

.account-menu-head b,
.account-menu-head small {
  display: block;
}

.account-menu-head b {
  font-size: 13px;
}

.account-menu-head small {
  font-size: 11px;
  color: var(--crm-ink-soft);
  margin-top: 3px;
}

.account-menu > button {
  width: 100%;
  border: 0;
  border-radius: 9px;
  background: transparent;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  color: inherit;
}

.account-menu > button:hover {
  background: var(--crm-surface-soft);
}

.account-menu > button span,
.account-menu > button small {
  display: block;
}

.account-menu > button span {
  font-size: 13px;
  font-weight: 650;
}

.account-menu > button small {
  font-size: 11px;
  color: var(--crm-ink-soft);
  margin-top: 2px;
}

.account-logout {
  margin-top: 4px;
  border-top: 1px solid var(--crm-border) !important;
  border-radius: 0 0 9px 9px !important;
  color: var(--el-color-danger) !important;
}

.account-logout span {
  padding-top: 4px;
}

.content-shell {
  min-width: 0;
  background: var(--crm-canvas);
}

.header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--crm-space-3);
  height: var(--crm-header-height);
  padding: 0 var(--crm-space-6);
  background: var(--crm-surface);
  border-bottom: 1px solid var(--crm-border);
  box-shadow: 0 1px 2px rgba(15, 39, 68, 0.03);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--crm-ink);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.page-title {
  font-family: var(--crm-font-display);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crumb-muted {
  color: var(--crm-ink-soft);
  font-weight: 500;
}

.crumb-sep {
  color: var(--crm-ink-soft);
  font-weight: 400;
}

.menu-toggle {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 36px;
  height: 36px;
  padding: 8px;
  border: 1px solid var(--crm-border);
  border-radius: var(--crm-radius-sm);
  background: var(--crm-surface);
  cursor: pointer;
  flex-shrink: 0;
}

.menu-toggle span {
  display: block;
  height: 2px;
  width: 100%;
  background: var(--crm-ink);
  border-radius: 1px;
}

.nav-backdrop {
  display: none;
}

.main {
  min-width: 0;
  padding: var(--crm-space-5) var(--crm-space-6);
  background: var(--crm-canvas);
  overflow-x: hidden;
}

.account-dialog-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.account-cell {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--crm-border);
  background: var(--crm-surface-soft);
}

.account-cell small {
  display: block;
  color: var(--crm-ink-soft);
  font-size: 12px;
  margin-bottom: 4px;
}

.account-cell b {
  font-size: 13px;
  font-weight: 600;
}

.account-dialog-note {
  margin: 14px 0 0;
  font-size: 12px;
  color: var(--crm-ink-soft);
  line-height: 1.5;
}

.account-perm-list {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.account-perm-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--crm-surface-soft);
  border: 1px solid var(--crm-border);
  font-size: 13px;
}

.account-perm-row span {
  color: var(--crm-ink-soft);
}

.account-perm-row b {
  font-weight: 600;
}

@media (max-width: 960px) {
  .aside {
    position: fixed;
    inset: 0 auto 0 0;
    width: var(--crm-aside-width) !important;
    transform: translateX(-100%);
    transition: transform var(--crm-duration-fast) var(--crm-ease-out);
  }

  .layout.nav-open .aside {
    transform: translateX(0);
  }

  .nav-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 30;
    background: rgba(15, 39, 68, 0.4);
  }

  .menu-toggle {
    display: inline-flex;
  }

  .header {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
    min-height: var(--crm-header-height);
    padding: 10px var(--crm-space-4);
  }

  .main {
    padding: var(--crm-space-4);
  }
}
</style>
