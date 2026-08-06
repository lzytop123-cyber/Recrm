/**
 * 按钮/区块权限显隐。
 *
 * 用法：
 *   <el-button v-perm="'contract:approve'">审批</el-button>
 *   <el-button v-perm.any="['contract:approve', 'contract:manage']">审批</el-button>
 *   <el-button v-perm.all="['project:view', 'project:complete']">结项</el-button>
 *
 * 默认（无修饰符）= 全部满足（与 .all 相同）。
 * 权限管「谁能看」；业务状态仍用 v-if（如 status === 'accepted'）。
 * 仅隐藏前端不够，对应 API 须用同一权限码校验。
 */
import type { App, Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/stores/user'

type PermEl = HTMLElement & { __vPermOrigDisplay?: string }

function resolveCodes(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter(Boolean)
  }
  if (typeof value === 'string' && value.trim()) {
    return [value.trim()]
  }
  return []
}

function allowed(codes: string[], mode: 'all' | 'any'): boolean {
  if (!codes.length) return true
  const store = useUserStore()
  if (mode === 'any') {
    return codes.some((c) => store.hasPermission(c))
  }
  return codes.every((c) => store.hasPermission(c))
}

function apply(el: PermEl, binding: DirectiveBinding) {
  const codes = resolveCodes(binding.value)
  const mode: 'all' | 'any' = binding.modifiers.any ? 'any' : 'all'
  if (el.__vPermOrigDisplay === undefined) {
    el.__vPermOrigDisplay = el.style.display
  }
  el.style.display = allowed(codes, mode) ? el.__vPermOrigDisplay || '' : 'none'
}

const permDirective: Directive = {
  mounted: apply,
  updated: apply,
}

export function setupPermDirective(app: App) {
  app.directive('perm', permDirective)
}

export default permDirective
