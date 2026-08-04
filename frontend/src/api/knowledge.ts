/**
 * AI 知识库 API
 */
import request from './request'

export interface KnowledgeSpace {
  id: number
  code: string
  name: string
  icon: string
  description?: string | null
  sort_order: number
  article_count: number
}

export interface KnowledgeSource {
  id: number
  name: string
  source_type: string
  space_id?: number | null
  space_name?: string | null
  external_ref?: string | null
  status: string
  authorized: boolean
  last_sync_at?: string | null
  sync_error?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeArticle {
  id: number
  title: string
  space_id: number
  space_name?: string | null
  source_id?: number | null
  content: string
  summary?: string | null
  keywords?: string | null
  version: string
  status: string
  source_label?: string | null
  published_at?: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeSyncStats {
  authorized_chats: number
  doc_dirs: number
  pending_review: number
  sync_failed: number
  status: string
}

export interface KnowledgeWorkbench {
  spaces: KnowledgeSpace[]
  sources: KnowledgeSource[]
  articles: KnowledgeArticle[]
  sync_stats: KnowledgeSyncStats
  total_published: number
  can_manage: boolean
}

export interface KnowledgeCitation {
  article_id: number
  title: string
  source_label: string
  version: string
  updated_at?: string | null
  snippet?: string | null
}

export interface KnowledgeAskResult {
  question: string
  answer_html: string
  citations: KnowledgeCitation[]
  retrieved_at: string
  matched_count: number
  /** llm=DeepSeek 生成；retrieve=检索拼接或未命中 */
  answer_mode?: 'llm' | 'retrieve'
}

export const SOURCE_TYPE_OPTIONS = [
  { value: 'feishu_doc', label: '飞书云文档' },
  { value: 'feishu_chat', label: '飞书工作群' },
  { value: 'manual', label: '人工录入目录' },
]

export function fetchKnowledgeWorkbench() {
  return request.get<KnowledgeWorkbench>('/knowledge/workbench')
}

export function askKnowledge(data: { question: string; space_id?: number }) {
  return request.post<KnowledgeAskResult>('/knowledge/ask', data)
}

export function createKnowledgeSource(data: {
  name: string
  source_type: string
  space_id?: number
  external_ref?: string
  remark?: string
}) {
  return request.post<KnowledgeSource>('/knowledge/sources', data)
}

export function authorizeKnowledgeSource(id: number) {
  return request.post<KnowledgeSource>(`/knowledge/sources/${id}/authorize`)
}
