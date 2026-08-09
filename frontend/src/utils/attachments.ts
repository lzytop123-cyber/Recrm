/** 附件展示工具：统一 uploads URL / 图片判断 / 文件列表解析 */

const IMAGE_EXT_RE = /\.(jpe?g|png|gif|webp|bmp)$/i

export interface AttachmentItem {
  name: string
  url: string
  isImage: boolean
}

export function isImageName(name?: string | null): boolean {
  return !!name && IMAGE_EXT_RE.test(name)
}

export function uploadsUrl(path?: string | null): string {
  const p = (path || '').trim()
  if (!p) return ''
  if (/^https?:\/\//i.test(p) || p.startsWith('/uploads/')) return p
  return `/uploads/${p.replace(/^\/+/, '')}`
}

/** 从「文件名」+「存储路径」解析可展示附件列表（兼容多文件用 " - " 拼接的历史数据） */
export function parseAttachmentList(
  filename?: string | null,
  path?: string | null,
): AttachmentItem[] {
  const raw = (filename || '').trim()
  const storePath = (path || '').trim()
  const url = uploadsUrl(storePath)
  const names = raw
    ? raw
        .split(
          /(?<=\.(?:jpg|jpeg|png|gif|webp|bmp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|txt))\s*-\s*/i,
        )
        .map((s) => s.trim())
        .filter(Boolean)
    : []

  if (!names.length && storePath) {
    const leaf = storePath.split(/[/\\]/).pop() || '查看附件'
    return [{ name: leaf, url, isImage: isImageName(leaf) }]
  }

  return names.map((name, idx) => ({
    name,
    url: idx === 0 ? url : '',
    isImage: isImageName(name),
  }))
}

export function attachmentPreviewUrls(files: AttachmentItem[]): string[] {
  return files.filter((f) => f.isImage && f.url).map((f) => f.url)
}
