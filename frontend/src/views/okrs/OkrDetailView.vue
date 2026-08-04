<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/okrs')">返回列表</el-button>
      <div class="actions" v-if="okr">
        <el-button
          v-if="!['completed', 'terminated'].includes(okr.status)"
          type="primary"
          @click="editVisible = true"
        >
          编辑
        </el-button>
        <el-button v-if="okr.status === 'pending'" type="success" @click="onConfirm">确认目标</el-button>
        <el-button
          v-if="['pending', 'active'].includes(okr.status)"
          type="success"
          @click="onComplete"
        >
          完成
        </el-button>
        <el-button
          v-if="!['completed', 'terminated'].includes(okr.status)"
          type="danger"
          plain
          @click="onTerminate"
        >
          终止
        </el-button>
      </div>
    </div>

    <template v-if="okr">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>#{{ okr.id }} · {{ okr.title }}</span>
            <el-tag :type="statusTag(okr.status)" size="small">
              {{ OKR_STATUS_LABEL[okr.status] || okr.status }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="层级">{{ levelLabel(okr.level) }}</el-descriptions-item>
          <el-descriptions-item label="周期">{{ okr.period_label }}</el-descriptions-item>
          <el-descriptions-item label="周期类型">{{ periodLabel(okr.period_type) }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ okr.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="对齐目标">{{ okr.parent_title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="进度">
            <el-progress :percentage="okr.progress || 0" style="max-width: 240px" />
          </el-descriptions-item>
          <el-descriptions-item label="说明" :span="3">{{ okr.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ okr.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="stack-gap">
        <template #header>
          <div class="card-header">
            <span>关键结果</span>
            <el-button
              v-if="!['completed', 'terminated'].includes(okr.status)"
              size="small"
              type="primary"
              @click="openKr"
            >
              添加 KR
            </el-button>
          </div>
        </template>
        <el-table :data="okr.key_results || []" stripe>
          <el-table-column prop="title" label="关键结果" min-width="180" />
          <el-table-column label="当前/目标" width="160">
            <template #default="{ row }">
              {{ row.current_value }} / {{ row.target_value }} {{ row.unit || '' }}
            </template>
          </el-table-column>
          <el-table-column label="进度" width="150">
            <template #default="{ row }">
              <el-progress :percentage="row.progress || 0" :stroke-width="10" />
            </template>
          </el-table-column>
          <el-table-column prop="weight" label="权重" width="70" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="!['completed', 'terminated'].includes(okr!.status)"
                link
                type="primary"
                @click="openUpdateKr(row)"
              >
                更新进度
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!(okr.key_results || []).length" description="暂无关键结果" :image-size="64" />
      </el-card>
    </template>

    <el-dialog v-model="editVisible" title="编辑目标" width="520px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="目标" required>
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="周期标识">
          <el-input v-model="editForm.period_label" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="krVisible" :title="krEditingId ? '更新进度' : '添加关键结果'" width="480px">
      <el-form :model="krForm" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="krForm.title" :disabled="!!krEditingId" />
        </el-form-item>
        <el-form-item label="目标值">
          <el-input-number v-model="krForm.target_value" :min="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="当前值">
          <el-input-number v-model="krForm.current_value" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="krForm.unit" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="krVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveKr">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  OKR_LEVEL_OPTIONS,
  OKR_PERIOD_OPTIONS,
  OKR_STATUS_LABEL,
  addKeyResult,
  completeOkr,
  confirmOkr,
  fetchOkrDetail,
  terminateOkr,
  updateKeyResult,
  updateOkr,
  type KeyResult,
  type OkrDetail,
} from '@/api/okrs'

const route = useRoute()
const loading = ref(false)
const saving = ref(false)
const okr = ref<OkrDetail | null>(null)
const editVisible = ref(false)
const krVisible = ref(false)
const krEditingId = ref<number | null>(null)

const editForm = reactive({
  title: '',
  period_label: '',
  description: '',
  remark: '',
})

const krForm = reactive({
  title: '',
  target_value: 100,
  current_value: 0,
  unit: '%',
})

const okrId = computed(() => Number(route.params.id))

function levelLabel(code: string) {
  return OKR_LEVEL_OPTIONS.find((x) => x.value === code)?.label || code
}

function periodLabel(code: string) {
  return OKR_PERIOD_OPTIONS.find((x) => x.value === code)?.label || code
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    pending: 'info',
    active: 'warning',
    completed: 'success',
    adjusted: '',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

function fillEdit() {
  if (!okr.value) return
  editForm.title = okr.value.title
  editForm.period_label = okr.value.period_label
  editForm.description = okr.value.description || ''
  editForm.remark = okr.value.remark || ''
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchOkrDetail(okrId.value)
    okr.value = data
    fillEdit()
  } finally {
    loading.value = false
  }
}

watch(editVisible, (v) => {
  if (v) fillEdit()
})

async function onSaveEdit() {
  if (!editForm.title.trim()) {
    ElMessage.warning('目标不能为空')
    return
  }
  saving.value = true
  try {
    await updateOkr(okrId.value, {
      title: editForm.title,
      period_label: editForm.period_label,
      description: editForm.description || undefined,
      remark: editForm.remark || undefined,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

async function onConfirm() {
  try {
    await ElMessageBox.confirm('确认后进入进行中，是否继续？', '确认目标')
    await confirmOkr(okrId.value)
    ElMessage.success('已确认')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onComplete() {
  try {
    await ElMessageBox.confirm('确认完成该目标？', '完成')
    await completeOkr(okrId.value)
    ElMessage.success('已完成')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onTerminate() {
  try {
    const { value } = await ElMessageBox.prompt('请填写终止原因（可选）', '终止目标', {
      inputPlaceholder: '终止原因',
    })
    await terminateOkr(okrId.value, value || undefined)
    ElMessage.success('已终止')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

function openKr() {
  krEditingId.value = null
  krForm.title = ''
  krForm.target_value = 100
  krForm.current_value = 0
  krForm.unit = '%'
  krVisible.value = true
}

function openUpdateKr(row: KeyResult) {
  krEditingId.value = row.id
  krForm.title = row.title
  krForm.target_value = Number(row.target_value) || 100
  krForm.current_value = Number(row.current_value) || 0
  krForm.unit = row.unit || '%'
  krVisible.value = true
}

async function onSaveKr() {
  if (!krForm.title.trim()) {
    ElMessage.warning('请填写关键结果')
    return
  }
  saving.value = true
  try {
    if (krEditingId.value) {
      await updateKeyResult(okrId.value, krEditingId.value, {
        target_value: krForm.target_value,
        current_value: krForm.current_value,
        unit: krForm.unit,
      })
      ElMessage.success('进度已更新')
    } else {
      await addKeyResult(okrId.value, {
        title: krForm.title,
        target_value: krForm.target_value,
        current_value: krForm.current_value,
        unit: krForm.unit,
      })
      ElMessage.success('已添加')
    }
    krVisible.value = false
    await loadDetail()
  } finally {
    saving.value = false
  }
}

onMounted(loadDetail)
</script>


