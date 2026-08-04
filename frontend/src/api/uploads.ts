/**
 * 通用附件上传
 */
import request from './request'

export interface UploadResult {
  filename: string
  path: string
  url: string
  size: number
}

export function uploadFile(file: File, category = 'contract_proof') {
  const form = new FormData()
  form.append('file', file)
  form.append('category', category)
  return request.post<UploadResult>('/uploads', form, {
    timeout: 60000,
  })
}
