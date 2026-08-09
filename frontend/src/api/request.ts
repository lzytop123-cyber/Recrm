/**
 * Axios 封装：统一 baseURL、自动带 JWT、401 跳登录。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const TOKEN_KEY = 'crm_okr_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join('; ')
          : error.message || '请求失败'

    if (status === 401) {
      clearToken()
      if (router.currentRoute.value.path === '/login') {
        // 登录页上的 401（如密码错误）需要直接提示，不能静默
        ElMessage.error(message || '用户名或密码错误')
      } else {
        ElMessage.error('登录已失效，请重新登录')
        router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
      }
    } else {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)

export default request
