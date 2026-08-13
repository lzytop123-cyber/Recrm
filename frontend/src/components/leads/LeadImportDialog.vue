/**
 * 线索批量导入弹窗：下载 CSV 模板 → 上传预览查重 → 确认入库。
 */
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, type UploadFile, type UploadRawFile } from 'element-plus'
import {
  confirmLeadImport,
  downloadLeadImportTemplate,
  previewLeadImport,
  type LeadImportPreview,
  type LeadImportPreviewRow,
} from '@/api/leads'

const props = defineProps<{
  selfFollow?: boolean | null
}>()

const emit = defineEmits<{
  (e: 'done', successCount: number): void
}>()

const visible = defineModel<boolean>('visible', { default: false })

const uploading = ref(false)
const confirming = ref(false)
const preview = ref<LeadImportPreview | null>(null)
const selected = ref<Set<number>>(new Set())
const forceHard = ref<Record<number, boolean>>({})
const fileInputKey = ref(0)

const selectedCount = computed(() => selected.value.size)

function statusLabel(status: string) {
  if (status === 'ok') return '可导入'
  if (status === 'soft') return '疑似重复'
  if (status === 'hard') return '确定重复'
  return '错误'
}

function statusType(status: string) {
  if (status === 'ok') return 'success'
  if (status === 'soft') return 'warning'
  if (status === 'hard') return 'danger'
  return 'info'
}

function isSelected(rowNo: number) {
  return selected.value.has(rowNo)
}

function setSelected(rowNo: number, on: boolean) {
  const next = new Set(selected.value)
  if (on) next.add(rowNo)
  else next.delete(rowNo)
  selected.value = next
}

async function onDownloadTemplate() {
  try {
    const { data } = await downloadLeadImportTemplate()
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'lead_import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    /* interceptor */
  }
}

function resetPreview() {
  preview.value = null
  selected.value = new Set()
  forceHard.value = {}
  fileInputKey.value += 1
}

async function onFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw as UploadRawFile | undefined
  if (!raw) return
  uploading.value = true
  try {
    const { data } = await previewLeadImport(raw)
    preview.value = data
    selected.value = new Set(
      data.rows.filter((r) => r.status === 'ok' || r.status === 'soft').map((r) => r.row_no),
    )
    forceHard.value = {}
    ElMessage.success(`已解析 ${data.total} 行`)
  } catch {
    preview.value = null
  } finally {
    uploading.value = false
  }
}

function toggleForce(row: LeadImportPreviewRow, checked: boolean) {
  forceHard.value = { ...forceHard.value, [row.row_no]: checked }
  if (checked) setSelected(row.row_no, true)
  else if (row.status === 'hard') setSelected(row.row_no, false)
}

async function onConfirm() {
  const rows = (preview.value?.rows || []).filter((r) => selected.value.has(r.row_no))
  if (!rows.length) {
    ElMessage.warning('请至少勾选一行可导入数据')
    return
  }
  for (const row of rows) {
    if (row.status === 'error') {
      ElMessage.warning(`第 ${row.row_no} 行有错误，无法导入`)
      return
    }
    if (row.status === 'hard' && !forceHard.value[row.row_no]) {
      ElMessage.warning(`第 ${row.row_no} 行确定重复，请勾选「强制」或取消勾选`)
      return
    }
  }
  confirming.value = true
  try {
    const { data } = await confirmLeadImport({
      self_follow: props.selfFollow ?? null,
      rows: rows.map((r) => ({
        row_no: r.row_no,
        company_name: r.company_name,
        phone: r.phone,
        name: r.name,
        credit_code: r.credit_code,
        company_domain: r.company_domain,
        business_type: r.business_type,
        need_desc: r.need_desc,
        remark: r.remark,
        force: !!forceHard.value[r.row_no],
      })),
    })
    if (data.success_count) {
      ElMessage.success(
        `成功导入 ${data.success_count} 条` +
          (data.failed_count ? `，失败 ${data.failed_count} 条` : ''),
      )
      emit('done', data.success_count)
      visible.value = false
      resetPreview()
    } else {
      ElMessage.error(`导入失败 ${data.failed_count} 条`)
    }
  } catch {
    /* interceptor */
  } finally {
    confirming.value = false
  }
}

function onClosed() {
  resetPreview()
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="批量导入线索"
    width="920px"
    destroy-on-close
    class="lead-import-dialog"
    @closed="onClosed"
  >
    <div class="import-steps">
      <p>
        1. 下载 Excel 模板并填写（需求方向请用下拉，勿随意填写） → 2. 直接上传
        <b>.xlsx</b> 预览查重 → 3. 勾选后确认入库。单次最多 200 条。也支持 CSV。
      </p>
      <div class="import-actions">
        <el-button @click="onDownloadTemplate">下载 Excel 模板</el-button>
        <el-upload
          :key="fileInputKey"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xlsm,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
          :disabled="uploading"
          :on-change="onFileChange"
        >
          <el-button type="primary" :loading="uploading">上传 Excel / CSV</el-button>
        </el-upload>
      </div>
    </div>

    <div v-if="preview" class="import-summary">
      <span>共 {{ preview.total }} 行</span>
      <span class="ok">可导入 {{ preview.ok_count }}</span>
      <span class="soft">疑似 {{ preview.soft_count }}</span>
      <span class="hard">硬重复 {{ preview.hard_count }}</span>
      <span class="err">错误 {{ preview.error_count }}</span>
    </div>

    <el-table v-if="preview" :data="preview.rows" height="360" stripe empty-text="无数据">
      <el-table-column label="选" width="52" align="center">
        <template #default="{ row }">
          <el-checkbox
            :model-value="isSelected(row.row_no)"
            :disabled="row.status === 'error'"
            @change="(v: boolean | string | number) => setSelected(row.row_no, !!v)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="row_no" label="行" width="56" />
      <el-table-column prop="company_name" label="客户主体" min-width="140" show-overflow-tooltip />
      <el-table-column prop="phone" label="电话" width="120" />
      <el-table-column prop="name" label="联系人" width="90" show-overflow-tooltip />
      <el-table-column prop="business_type_label" label="需求方向" width="110" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
      <el-table-column label="强制" width="70" align="center">
        <template #default="{ row }">
          <el-checkbox
            v-if="row.status === 'hard'"
            :model-value="!!forceHard[row.row_no]"
            @change="(v: boolean | string | number) => toggleForce(row, !!v)"
          />
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="confirming" :disabled="!selectedCount" @click="onConfirm">
        确认导入（{{ selectedCount }}）
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.import-steps {
  margin-bottom: 12px;
}
.import-steps p {
  margin: 0 0 10px;
  color: var(--crm-ink-soft, #606266);
  font-size: 13px;
  line-height: 1.5;
}
.import-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.import-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 13px;
}
.import-summary .ok {
  color: #67c23a;
}
.import-summary .soft {
  color: #e6a23c;
}
.import-summary .hard,
.import-summary .err {
  color: #f56c6c;
}
.muted {
  color: #c0c4cc;
}
</style>
