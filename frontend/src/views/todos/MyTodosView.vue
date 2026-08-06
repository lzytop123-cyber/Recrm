<template>
  <div class="crm-page todo-page" v-loading="loading">
    <header class="todo-head">
      <div class="todo-head-copy">
        <h1>我的待办</h1>
        <p>审批、工单、线索、任务、档期汇总一处；点击条目进入对应业务页处理。</p>
      </div>
      <div class="todo-head-actions">
        <el-button @click="reload">刷新</el-button>
      </div>
    </header>

    <section class="todo-kpis">
      <button
        type="button"
        class="todo-kpi"
        :class="{ active: category === 'all' }"
        @click="category = 'all'"
      >
        <small>全部待办</small>
        <b>{{ data?.total ?? 0 }}</b>
      </button>
      <button
        v-for="chip in categoryChips"
        :key="chip.key"
        type="button"
        class="todo-kpi"
        :class="{ active: category === chip.key }"
        @click="category = chip.key"
      >
        <small>{{ chip.label }}</small>
        <b :class="{ danger: chip.key === 'approval' && (counts[chip.key] || 0) > 0 }">
          {{ counts[chip.key] ?? 0 }}
        </b>
      </button>
    </section>

    <section class="todo-panel">
      <div class="todo-panel-head">
        <strong>{{ listTitle }}</strong>
        <span>{{ filtered.length }} 项</span>
      </div>

      <el-alert
        v-if="data?.partial_errors?.length"
        type="warning"
        :closable="false"
        show-icon
        class="todo-partial"
        :title="`部分数据源暂不可用：${data.partial_errors.join('、')}`"
      />

      <div v-if="filtered.length" class="todo-list">
        <button
          v-for="item in filtered"
          :key="item.id"
          type="button"
          class="todo-row"
          :class="{ urgent: item.urgency === 'high' }"
          @click="go(item.path)"
        >
          <span class="todo-cat" :data-cat="item.category">{{ item.category_label }}</span>
          <div class="todo-row-main">
            <strong>{{ item.title }}</strong>
            <span v-if="item.subtitle" class="todo-sub">{{ item.subtitle }}</span>
          </div>
          <div class="todo-row-meta">
            <span v-if="item.due_at" class="todo-due">{{ formatDue(item.due_at) }}</span>
            <span v-if="item.status_label" class="todo-status">{{ item.status_label }}</span>
            <span class="todo-go">去处理</span>
          </div>
        </button>
      </div>

      <el-empty v-else description="当前没有待办，清闲得很。" :image-size="72" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMyTodos, type TodoCategory, type TodoList } from '@/api/todos'

const router = useRouter()
const loading = ref(false)
const data = ref<TodoList | null>(null)
const category = ref<'all' | TodoCategory>('all')

const categoryChips: { key: TodoCategory; label: string }[] = [
  { key: 'approval', label: '待我审批' },
  { key: 'ticket', label: '协作工单' },
  { key: 'lead', label: '我的线索' },
  { key: 'task', label: '项目任务' },
  { key: 'schedule', label: '人员档期' },
  { key: 'resource', label: '资源确认' },
]

const counts = computed(
  () =>
    data.value?.counts || {
      approval: 0,
      ticket: 0,
      lead: 0,
      task: 0,
      schedule: 0,
      resource: 0,
    },
)

const listTitle = computed(() => {
  if (category.value === 'all') return '待办列表'
  return categoryChips.find((c) => c.key === category.value)?.label || '待办列表'
})

const filtered = computed(() => {
  const items = data.value?.items || []
  if (category.value === 'all') return items
  return items.filter((x) => x.category === category.value)
})

function formatDue(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const hasTime = d.getHours() !== 0 || d.getMinutes() !== 0
  return hasTime ? `${mm}-${dd} ${hh}:${mi}` : `${mm}-${dd}`
}

function go(path: string) {
  if (!path) return
  router.push(path)
}

async function reload() {
  loading.value = true
  try {
    const { data: res } = await fetchMyTodos()
    data.value = res
  } catch {
    // 错误提示由 request 拦截器统一处理
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.todo-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.todo-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.todo-head-copy h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  color: var(--crm-ink);
}

.todo-head-copy p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--crm-ink-soft);
  max-width: 42em;
}

.todo-head-actions {
  flex-shrink: 0;
}

.todo-kpis {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
}

.todo-kpi {
  appearance: none;
  border: 1px solid var(--crm-border);
  background: var(--crm-surface);
  border-radius: 12px;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
  min-width: 0;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.todo-kpi:hover {
  border-color: color-mix(in oklab, var(--crm-primary) 45%, var(--crm-border));
}

.todo-kpi.active {
  border-color: var(--crm-primary);
  box-shadow: inset 0 0 0 1px var(--crm-primary);
}

.todo-kpi small {
  display: block;
  color: var(--crm-ink-soft);
  font-size: 12px;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.todo-kpi b {
  display: block;
  font-family: var(--crm-font-data);
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--crm-ink);
}

.todo-kpi b.danger {
  color: var(--crm-danger);
}

.todo-panel {
  background: var(--crm-surface);
  border: 1px solid var(--crm-border);
  border-radius: 14px;
  padding: 14px 16px 12px;
  min-height: 220px;
}

.todo-panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.todo-panel-head strong {
  font-size: 14px;
  color: var(--crm-ink);
}

.todo-panel-head span {
  font-size: 12px;
  color: var(--crm-ink-soft);
}

.todo-partial {
  margin-bottom: 10px;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.todo-row {
  appearance: none;
  width: 100%;
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px 14px;
  padding: 12px 14px;
  border: 1px solid var(--crm-border);
  border-radius: 12px;
  background: var(--crm-surface-soft);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.todo-row:hover {
  border-color: color-mix(in oklab, var(--crm-primary) 45%, var(--crm-border));
  background: var(--crm-primary-soft);
}

.todo-row.urgent {
  border-left: 3px solid var(--crm-danger);
}

.todo-cat {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 8px;
  border-radius: 8px;
  background: var(--crm-surface);
  border: 1px solid var(--crm-border);
  color: var(--crm-ink-soft);
  font-size: 12px;
  white-space: nowrap;
}

.todo-cat[data-cat='approval'] {
  color: var(--crm-danger);
  border-color: color-mix(in oklab, var(--crm-danger) 30%, var(--crm-border));
  background: var(--crm-danger-soft);
}

.todo-cat[data-cat='ticket'] {
  color: var(--crm-primary);
  border-color: color-mix(in oklab, var(--crm-primary) 30%, var(--crm-border));
  background: var(--crm-primary-soft);
}

.todo-cat[data-cat='lead'] {
  color: var(--crm-flow);
  border-color: color-mix(in oklab, var(--crm-flow) 30%, var(--crm-border));
  background: var(--crm-flow-soft);
}

.todo-row-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.todo-row-main strong {
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-sub {
  font-size: 12px;
  color: var(--crm-ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-row-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
  font-size: 13px;
}

.todo-status {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--crm-surface);
  border: 1px solid var(--crm-border);
  color: var(--crm-ink);
}

.todo-due {
  color: var(--crm-ink-soft);
  font-variant-numeric: tabular-nums;
}

.todo-go {
  color: var(--crm-primary);
  font-weight: 600;
  white-space: nowrap;
}

.todo-go::after {
  content: ' →';
}

@media (max-width: 1200px) {
  .todo-kpis {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .todo-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .todo-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .todo-cat {
    justify-self: start;
  }

  .todo-row-meta {
    justify-content: space-between;
    width: 100%;
  }
}

@media (max-width: 640px) {
  .todo-head {
    flex-direction: column;
  }

  .todo-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
