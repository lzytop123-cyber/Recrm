import type { Router } from 'vue-router'
import { nextTick } from 'vue'

/** 仅允许站内相对路径，避免开放重定向 / 外链 */
export function resolvePostLoginPath(raw: unknown, fallback = '/dashboard'): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string') return fallback
  const path = value.trim()
  if (!path.startsWith('/') || path.startsWith('//')) return fallback
  if (path === '/login' || path.startsWith('/login?') || path.startsWith('/login/')) {
    return fallback
  }
  return path
}

/**
 * 登录后跳转：优先 SPA replace；移动端 WebView 若未离开登录页则强制整页进入。
 */
export async function navigateAfterLogin(router: Router, rawPath: unknown, fallback = '/dashboard') {
  const target = resolvePostLoginPath(rawPath, fallback)
  try {
    await router.replace(target)
  } catch {
    // 导航被取消或重复时走硬跳
    window.location.assign(target)
    return
  }
  await nextTick()
  if (router.currentRoute.value.path === '/login') {
    window.location.assign(target)
  }
}
