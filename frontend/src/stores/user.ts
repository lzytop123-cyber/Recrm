/**
 * 用户状态：登录信息、菜单权限、登出。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchMeApi, loginApi, logoutApi, type LoginResult, type MenuItem, type UserInfo } from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/request'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(getToken())
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const menus = computed<MenuItem[]>(() => user.value?.menus ?? [])
  const displayName = computed(
    () => user.value?.real_name || user.value?.username || '未登录',
  )

  function applyLoginResult(data: LoginResult) {
    token.value = data.access_token
    setToken(data.access_token)
    user.value = data.user
    return data.user
  }

  async function login(username: string, password: string) {
    const { data } = await loginApi(username, password)
    return applyLoginResult(data)
  }

  async function loginWithFeishuResult(data: LoginResult) {
    return applyLoginResult(data)
  }

  /** 刷新用户信息与菜单（页面刷新后调用） */
  async function fetchProfile() {
    if (!token.value) return null
    const { data } = await fetchMeApi()
    user.value = data
    return data
  }

  async function logout() {
    try {
      if (token.value) await logoutApi()
    } catch {
      // 本地清理优先，接口失败不阻断退出
    }
    token.value = null
    user.value = null
    clearToken()
  }

  function hasPermission(code: string) {
    const perms = user.value?.permissions ?? []
    if (perms.includes('*')) return true
    return perms.includes(code)
  }

  /** 任一权限满足即可（用于 v-perm.any / 组合按钮） */
  function hasAnyPermission(...codes: string[]) {
    return codes.some((c) => hasPermission(c))
  }

  /** 全部权限均需满足 */
  function hasAllPermissions(...codes: string[]) {
    return codes.every((c) => hasPermission(c))
  }

  const homePath = computed(() => user.value?.home_path || '/dashboard')
  const leadEntryOnly = computed(() => !!user.value?.lead_entry_only)

  return {
    token,
    user,
    isLoggedIn,
    menus,
    displayName,
    homePath,
    leadEntryOnly,
    login,
    loginWithFeishuResult,
    fetchProfile,
    logout,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  }
})
