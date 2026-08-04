/** 认证相关 API */
import request from './request'

export interface RoleBrief {
  id: number
  name: string
  code: string
  data_scope: string
}

export interface MenuItem {
  path: string
  title: string
  icon?: string | null
  permission?: string | null
}

export interface UserInfo {
  id: number
  username: string
  real_name?: string | null
  email?: string | null
  phone?: string | null
  department_id?: number | null
  is_active: boolean
  roles: RoleBrief[]
  permissions: string[]
  data_scope: string
  menus: MenuItem[]
  lead_entry_only?: boolean
  home_path?: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: UserInfo
  redirect?: string
}

export interface FeishuLoginConfig {
  enabled: boolean
  redirect_uri?: string | null
}

export function loginApi(username: string, password: string) {
  return request.post<LoginResult>('/auth/login', { username, password })
}

export function fetchMeApi() {
  return request.get<UserInfo>('/auth/me')
}

export function logoutApi() {
  return request.post<{ message: string }>('/auth/logout')
}

export function fetchFeishuConfigApi() {
  return request.get<FeishuLoginConfig>('/auth/feishu/config')
}

export function fetchFeishuAuthorizeUrlApi(redirect = '/dashboard') {
  return request.get<{ authorize_url: string; state: string }>('/auth/feishu/authorize', {
    params: { redirect },
  })
}

export function feishuCallbackApi(code: string, state?: string | null) {
  return request.post<LoginResult>('/auth/feishu/callback', { code, state })
}

export function registerApi(payload: {
  username: string
  password: string
  real_name?: string
  email?: string
}) {
  return request.post<UserInfo>('/auth/register', payload)
}
