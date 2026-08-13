<template>
  <div class="detail-page" v-loading="loading">
    <div class="top-bar">
      <el-button @click="$router.push('/schedules')">返回列表</el-button>
      <div class="actions" v-if="item">
        <el-button v-if="item.status === 'pending'" type="success" @click="onConfirm">确认本人档期</el-button>
        <el-button v-if="item.status === 'confirmed'" type="primary" @click="onStart">开始</el-button>
        <el-button
          v-if="['confirmed', 'in_progress'].includes(item.status)"
          type="warning"
          @click="onComplete"
        >
          完成并填工时
        </el-button>
        <el-button
          v-if="!['completed', 'cancelled'].includes(item.status)"
          type="danger"
          plain
          @click="onCancel"
        >
          取消
        </el-button>
        <el-button v-if="isAdmin" type="danger" @click="onDelete">删除</el-button>
      </div>
    </div>

    <el-card v-if="item">
      <template #header>
        <div class="card-header">
          <span>{{ item.title }}</span>
          <el-tag :type="statusTag(item.status)" size="small">
            {{ SCHEDULE_STATUS_LABEL[item.status] || item.status }}
          </el-tag>
          <el-tag v-if="item.has_conflict" type="danger" size="small">存在冲突</el-tag>
        </div>
      </template>
      <el-descriptions :column="descCols" border>
        <el-descriptions-item label="资源类型">{{ resourceLabel(item.resource_type) }}</el-descriptions-item>
        <el-descriptions-item label="关联方式">{{ linkModeLabel(item) }}</el-descriptions-item>
        <el-descriptions-item label="人员">{{ item.employee_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ item.creator_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatTime(item.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatTime(item.end_time) }}</el-descriptions-item>
        <el-descriptions-item label="地点">{{ item.location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="挂到项目" :span="descCols > 1 ? 2 : 1">
          <el-button
            v-if="item.project_id"
            link
            type="primary"
            @click="$router.push(`/projects/${item.project_id}`)"
          >
            {{ item.project_no }} · {{ item.project_name }}
          </el-button>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="确认人">{{ item.confirmed_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ formatTime(item.confirmed_at) }}</el-descriptions-item>
        <el-descriptions-item label="说明" :span="descCols">{{ item.content || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="descCols">{{ item.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="item.cancel_reason" label="取消原因" :span="descCols">
          {{ item.cancel_reason }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="item?.has_conflict" class="stack-gap">
      <template #header>
        <span style="color: #f56c6c">冲突排期</span>
      </template>
      <div class="crm-table-wrap">
        <el-table :data="item.conflicts || []" size="small">
          <el-table-column prop="title" label="标题" min-width="120" />
          <el-table-column label="时间" min-width="180">
            <template #default="{ row }">
              {{ formatTime(row.start_time) }} ~ {{ formatTime(row.end_time) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              {{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push(`/schedules/${row.id}`)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import { useUserStore } from '@/stores/user'
import {
  SCHEDULE_RESOURCE_OPTIONS,
  SCHEDULE_STATUS_LABEL,
  cancelSchedule,
  completeSchedule,
  confirmSchedule,
  deleteSchedule,
  fetchScheduleDetail,
  startSchedule,
  type Schedule,
} from '@/api/schedules'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => (userStore.user?.roles ?? []).some((r) => r.code === 'admin'))
const isCompact = useMatchMedia('(max-width: 768px)')
const descCols = computed(() => (isCompact.value ? 1 : 3))
const loading = ref(false)
const item = ref<Schedule | null>(null)
const scheduleId = computed(() => Number(route.params.id))

function resourceLabel(code: string) {
  return SCHEDULE_RESOURCE_OPTIONS.find((x) => x.value === code)?.label || code
}

function linkModeLabel(row: Schedule) {
  if (row.project_task_id || row.task_no) return '任务排期'
  if (row.project_id) return '项目排期'
  return '一般活动'
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    confirmed: '',
    in_progress: 'success',
    completed: 'info',
    cancelled: 'info',
  }
  return map[s] || 'info'
}

function formatTime(v?: string | null) {
  if (!v) return '-'
  // 无时区后缀按 UTC；有偏移则按标准解析，再显示为本地时间
  const raw = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v) ? `${v}Z` : v
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return v.replace('T', ' ').slice(0, 19)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function loadDetail() {
  loading.value = true
  try {
    const { data } = await fetchScheduleDetail(scheduleId.value)
    item.value = data
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  try {
    await ElMessageBox.confirm(
      item.value?.has_conflict ? '存在冲突提示，仍要确认？' : '确认该排期并锁定资源？',
      '确认排期',
    )
    await confirmSchedule(scheduleId.value)
    ElMessage.success('已确认')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onStart() {
  try {
    await ElMessageBox.confirm('确认开始执行该排期？', '开始')
    await startSchedule(scheduleId.value)
    ElMessage.success('已开始')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onComplete() {
  try {
    const { value } = await ElMessageBox.prompt('请填写活动结果', '完成并填工时', {
      inputType: 'textarea',
      confirmButtonText: '完成',
    })
    if (!value?.trim()) {
      ElMessage.warning('请填写结果')
      return
    }
    const planned = Number(item.value?.planned_hours || 2)
    await completeSchedule(scheduleId.value, {
      result: value.trim(),
      actual_hours: planned,
      create_timesheet: true,
    })
    ElMessage.success('已完成并生成工时草稿')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onCancel() {
  try {
    const { value } = await ElMessageBox.prompt('取消原因（可选）', '取消排期', {
      inputPlaceholder: '原因',
      confirmButtonText: '取消排期',
    })
    await cancelSchedule(scheduleId.value, value || undefined)
    ElMessage.success('已取消')
    await loadDetail()
  } catch {
    /* cancel */
  }
}

async function onDelete() {
  try {
    await ElMessageBox.confirm(
      `确认删除排期「${item.value?.title || ''}」？已完成也会从日历移除，且不可恢复。`,
      '删除排期',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' },
    )
    await deleteSchedule(scheduleId.value)
    ElMessage.success('已删除')
    router.push('/schedules')
  } catch {
    /* cancel */
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.stack-gap {
  margin-top: 16px;
}
.crm-table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
@media (max-width: 768px) {
  .card-header {
    flex-wrap: wrap;
    gap: 6px;
  }
  .card-header > span {
    width: 100%;
    word-break: break-word;
    line-height: 1.35;
  }
}
</style>
