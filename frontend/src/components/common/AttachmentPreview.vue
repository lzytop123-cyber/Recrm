<template>
  <div v-if="files.length" class="attach-preview" :class="[`size-${size}`]">
    <template v-for="(file, idx) in files" :key="`${file.name}-${idx}`">
      <button
        v-if="file.url"
        type="button"
        class="attach-link"
        :class="{ 'attach-thumb-wrap': file.isImage && !brokenThumbs[idx] }"
        :title="`预览 ${file.name}`"
        @click="openPreview(file)"
      >
        <img
          v-if="file.isImage && !brokenThumbs[idx]"
          :src="file.url"
          :alt="file.name"
          class="attach-thumb"
          @error="brokenThumbs[idx] = true"
        />
        <span class="attach-link-text">{{ file.name }}</span>
      </button>
      <span v-else class="attach-name">{{ file.name }}</span>
    </template>
  </div>
  <span v-else class="attach-empty">{{ emptyText }}</span>

  <el-dialog
    v-model="previewVisible"
    :title="previewFile?.name || '附件预览'"
    width="860px"
    top="6vh"
    destroy-on-close
    append-to-body
    class="attach-preview-dialog"
  >
    <div v-if="previewFile" class="attach-preview-body">
      <img
        v-if="previewKind === 'image'"
        :src="previewFile.url"
        :alt="previewFile.name"
        class="attach-preview-image"
      />
      <iframe
        v-else-if="previewKind === 'pdf'"
        :src="previewFile.url"
        class="attach-preview-frame"
        title="附件预览"
      />
      <div v-else class="attach-preview-fallback">
        <p>该文件类型暂不支持在线预览，请下载后查看。</p>
        <el-button type="primary" @click="downloadCurrent">下载附件</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  parseAttachmentList,
  uploadsUrl,
  type AttachmentItem,
} from '@/utils/attachments'

const brokenThumbs = reactive<Record<number, boolean>>({})
const previewVisible = ref(false)
const previewFile = ref<AttachmentItem | null>(null)

const props = withDefaults(
  defineProps<{
    /** 已解析好的附件列表；优先于 filename/path */
    items?: AttachmentItem[] | null
    /** 显示文件名（可多文件拼接） */
    filename?: string | null
    /** 存储路径或 /uploads/... / 完整 URL */
    path?: string | null
    /** 仅传一个完整 URL 时使用 */
    url?: string | null
    size?: 'sm' | 'md' | 'lg'
    emptyText?: string
  }>(),
  {
    items: null,
    filename: null,
    path: null,
    url: null,
    size: 'md',
    emptyText: '—',
  },
)

const files = computed<AttachmentItem[]>(() => {
  if (props.items?.length) return props.items
  if (props.url) {
    const name = props.filename || props.url.split(/[/\\]/).pop() || '查看附件'
    const u = uploadsUrl(props.url)
    return [
      {
        name,
        url: u,
        isImage:
          /\.(jpe?g|png|gif|webp|bmp)$/i.test(name) ||
          /\.(jpe?g|png|gif|webp|bmp)(\?|$)/i.test(u),
      },
    ]
  }
  return parseAttachmentList(props.filename, props.path)
})

const previewKind = computed(() => {
  const name = previewFile.value?.name || ''
  const url = previewFile.value?.url || ''
  if (/\.(jpe?g|png|gif|webp|bmp)$/i.test(name) || /\.(jpe?g|png|gif|webp|bmp)(\?|$)/i.test(url)) {
    return 'image'
  }
  if (/\.pdf$/i.test(name) || /\.pdf(\?|$)/i.test(url)) return 'pdf'
  return 'other'
})

function openPreview(file: AttachmentItem) {
  if (!file.url) return
  previewFile.value = file
  previewVisible.value = true
}

function downloadCurrent() {
  if (!previewFile.value?.url) return
  const a = document.createElement('a')
  a.href = previewFile.value.url
  a.download = previewFile.value.name || 'attachment'
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}
</script>

<style scoped>
.attach-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.attach-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  word-break: break-all;
  text-decoration: none;
  line-height: 1.4;
  max-width: 100%;
  cursor: pointer;
  text-align: left;
}

.attach-link:hover {
  text-decoration: underline;
}

.attach-thumb-wrap {
  text-decoration: none;
}

.attach-thumb-wrap:hover .attach-link-text {
  text-decoration: underline;
}

.attach-thumb {
  display: block;
  flex-shrink: 0;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
  object-fit: cover;
}

.size-sm .attach-thumb {
  width: 48px;
  height: 48px;
}

.size-md .attach-thumb {
  width: 72px;
  height: 72px;
}

.size-lg .attach-thumb {
  width: 120px;
  height: 120px;
}

.attach-link-text {
  min-width: 0;
}

.attach-name {
  font-size: 13px;
  color: var(--el-text-color-regular);
  word-break: break-all;
}

.attach-empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.attach-preview-body {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.attach-preview-image {
  max-width: 100%;
  max-height: 72vh;
  object-fit: contain;
  border-radius: 8px;
}

.attach-preview-frame {
  width: 100%;
  height: 72vh;
  border: 0;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.attach-preview-fallback {
  text-align: center;
  color: var(--el-text-color-regular);
  padding: 32px 16px;
}

.attach-preview-fallback p {
  margin: 0 0 16px;
}
</style>
