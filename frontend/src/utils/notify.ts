/** API 错误提示：拦截器已弹过则不再重复。 */
import { ElMessage } from 'element-plus'

export function isApiToastShown(error: unknown): boolean {
  return !!(error as { __toastShown?: boolean } | null)?.__toastShown
}

export function notifyError(error: unknown, fallback = '操作失败') {
  if (error === 'cancel' || error === 'close') return
  if (isApiToastShown(error)) return
  const detail = (error as { response?: { data?: { detail?: unknown } }; message?: string })
    ?.response?.data?.detail
  const message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join('; ')
        : (error as { message?: string })?.message || fallback
  ElMessage.error(message || fallback)
}
