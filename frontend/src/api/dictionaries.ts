/**
 * 系统字典：业务类型等下拉选项
 */
import { onMounted, ref, type Ref } from 'vue'
import request from './request'

export interface DictionaryItem {
  value: string
  label: string
  enabled?: boolean
  sort?: number
}

export interface SystemDictionary {
  id: number
  code: string
  name: string
  items_json?: string | null
  updated_at: string
  items: DictionaryItem[]
}

export const BUSINESS_TYPE_DICT_CODE = 'business_type'

/** 离线/接口失败时的兜底选项 */
export const DEFAULT_BUSINESS_TYPE_OPTIONS: DictionaryItem[] = [
  { value: 'ai_product', label: 'AI产品销售', enabled: true, sort: 10 },
  { value: 'ai_custom', label: 'AI定制开发', enabled: true, sort: 20 },
  { value: 'media_ops', label: '自媒体代运营', enabled: true, sort: 30 },
  { value: 'other', label: '其他', enabled: true, sort: 90 },
]

let cachedAll: DictionaryItem[] | null = null
let inflight: Promise<DictionaryItem[]> | null = null

export function fetchDictionaries() {
  return request.get<SystemDictionary[]>('/system/dictionaries')
}

export function fetchDictionary(code: string) {
  return request.get<SystemDictionary>(`/system/dictionaries/${code}`)
}

export function updateDictionary(
  code: string,
  data: { name?: string; items_json?: string },
) {
  return request.patch<SystemDictionary>(`/system/dictionaries/${code}`, data)
}

export function fetchDictionaryItems(code: string, enabledOnly = true) {
  return request.get<DictionaryItem[]>(`/system/dictionaries/${code}/items`, {
    params: { enabled_only: enabledOnly },
  })
}

export async function loadBusinessTypeOptions(force = false): Promise<DictionaryItem[]> {
  if (!force && cachedAll) return cachedAll
  if (!force && inflight) return inflight
  inflight = (async () => {
    try {
      const { data } = await fetchDictionaryItems(BUSINESS_TYPE_DICT_CODE, false)
      cachedAll = Array.isArray(data) && data.length ? data : [...DEFAULT_BUSINESS_TYPE_OPTIONS]
    } catch {
      cachedAll = [...DEFAULT_BUSINESS_TYPE_OPTIONS]
    } finally {
      inflight = null
    }
    return cachedAll || [...DEFAULT_BUSINESS_TYPE_OPTIONS]
  })()
  return inflight
}

export function invalidateBusinessTypeCache() {
  cachedAll = null
  inflight = null
}

export function enabledBusinessTypeOptions(all?: DictionaryItem[] | null): DictionaryItem[] {
  const list = all ?? cachedAll ?? DEFAULT_BUSINESS_TYPE_OPTIONS
  return list.filter((x) => x.enabled !== false)
}

export function businessTypeLabel(code?: string | null): string {
  if (!code) return '—'
  const list = cachedAll ?? DEFAULT_BUSINESS_TYPE_OPTIONS
  return list.find((x) => x.value === code)?.label || code
}

/**
 * 页面内业务类型下拉：自动加载字典，失败回落默认值。
 */
export function useBusinessTypes() {
  const options: Ref<DictionaryItem[]> = ref(enabledBusinessTypeOptions())
  const allOptions: Ref<DictionaryItem[]> = ref([...(cachedAll ?? DEFAULT_BUSINESS_TYPE_OPTIONS)])
  const loading = ref(false)

  async function refresh(force = false) {
    loading.value = true
    try {
      const all = await loadBusinessTypeOptions(force)
      allOptions.value = all
      options.value = enabledBusinessTypeOptions(all)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void refresh()
  })

  return {
    businessTypeOptions: options,
    businessTypeAllOptions: allOptions,
    businessTypeLoading: loading,
    refreshBusinessTypes: refresh,
    businessTypeLabel,
  }
}
