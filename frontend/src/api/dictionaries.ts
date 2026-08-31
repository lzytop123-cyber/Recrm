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
export const LEAD_SOURCE_DICT_CODE = 'lead_source'

/** 离线/接口失败时的兜底选项 */
export const DEFAULT_BUSINESS_TYPE_OPTIONS: DictionaryItem[] = [
  { value: 'ai_product', label: 'AI产品销售', enabled: true, sort: 10 },
  { value: 'ai_custom', label: 'AI定制开发', enabled: true, sort: 20 },
  { value: 'media_ops', label: '自媒体代运营', enabled: true, sort: 30 },
  { value: 'other', label: '其他', enabled: true, sort: 90 },
]

export const DEFAULT_LEAD_SOURCE_OPTIONS: DictionaryItem[] = [
  { value: 'company', label: '公司', enabled: true, sort: 10 },
  { value: 'personal', label: '个人开发', enabled: true, sort: 20 },
]

/** 历史编码 / 旧默认值的中文回退（字典未配置时仍可读） */
const LEAD_SOURCE_LABEL_FALLBACK: Record<string, string> = {
  company: '公司',
  personal: '个人开发',
  manual: '手动录入',
  import: '批量导入',
  external: '外部筛选',
  website: '官网',
  ad: '广告投放',
  event: '展会/活动',
  referral: '转介绍',
  im: '飞书/企微',
  other: '其他',
}

let cachedAll: DictionaryItem[] | null = null
let inflight: Promise<DictionaryItem[]> | null = null
let cachedLeadSources: DictionaryItem[] | null = null
let leadSourceInflight: Promise<DictionaryItem[]> | null = null

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

export async function loadLeadSourceOptions(force = false): Promise<DictionaryItem[]> {
  if (!force && cachedLeadSources) return cachedLeadSources
  if (!force && leadSourceInflight) return leadSourceInflight
  leadSourceInflight = (async () => {
    try {
      const { data } = await fetchDictionaryItems(LEAD_SOURCE_DICT_CODE, false)
      cachedLeadSources = Array.isArray(data) && data.length ? data : [...DEFAULT_LEAD_SOURCE_OPTIONS]
    } catch {
      cachedLeadSources = [...DEFAULT_LEAD_SOURCE_OPTIONS]
    } finally {
      leadSourceInflight = null
    }
    return cachedLeadSources || [...DEFAULT_LEAD_SOURCE_OPTIONS]
  })()
  return leadSourceInflight
}

export function invalidateLeadSourceCache() {
  cachedLeadSources = null
  leadSourceInflight = null
}

export function enabledLeadSourceOptions(all?: DictionaryItem[] | null): DictionaryItem[] {
  const list = all ?? cachedLeadSources ?? DEFAULT_LEAD_SOURCE_OPTIONS
  return list.filter((x) => x.enabled !== false)
}

export function leadSourceLabel(code?: string | null): string {
  if (!code) return '公司'
  const list = cachedLeadSources ?? DEFAULT_LEAD_SOURCE_OPTIONS
  return (
    list.find((x) => x.value === code)?.label ||
    LEAD_SOURCE_LABEL_FALLBACK[code] ||
    code
  )
}

/** 新建线索时的默认来源：优先字典首项，否则公司 */
export function defaultLeadSource(): string {
  const opts = enabledLeadSourceOptions()
  if (opts.some((x) => x.value === 'company')) return 'company'
  return opts[0]?.value || 'company'
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

/**
 * 页面内线索来源下拉：自动加载字典，失败回落默认值。
 */
export function useLeadSources() {
  const options: Ref<DictionaryItem[]> = ref(enabledLeadSourceOptions())
  const allOptions: Ref<DictionaryItem[]> = ref([...(cachedLeadSources ?? DEFAULT_LEAD_SOURCE_OPTIONS)])
  const loading = ref(false)

  async function refresh(force = false) {
    loading.value = true
    try {
      const all = await loadLeadSourceOptions(force)
      allOptions.value = all
      options.value = enabledLeadSourceOptions(all)
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void refresh()
  })

  return {
    leadSourceOptions: options,
    leadSourceAllOptions: allOptions,
    leadSourceLoading: loading,
    refreshLeadSources: refresh,
    leadSourceLabel,
    defaultLeadSource,
  }
}
