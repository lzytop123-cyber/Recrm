<template>
  <div class="crm-page todo-page" :class="{ 'is-compact': isCompact }" v-loading="loading">
    <header class="todo-head">
      <div class="todo-head-copy">
        <p class="todo-eyebrow">经营台</p>
        <h1>我的待办</h1>
        <p class="todo-head-desc">审批、工单、线索、任务、档期汇总一处；点击条目进入对应业务页处理。</p>
      </div>
      <div class="todo-head-actions">
        <el-button @click="reload">刷新</el-button>
      </div>
    </header>

    <section class="todo-kpis" aria-label="待办分类">
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
        :data-cat="chip.key"
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
        <div>
          <strong>{{ listTitle }}</strong>
          <p class="todo-panel-hint">按紧急程度与到期时间优先处理</p>
        </div>
        <span class="todo-count-chip">{{ filtered.length }} 项</span>
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
          <div class="todo-row-top">
            <span class="todo-cat" :data-cat="item.category">{{ item.category_label }}</span>
            <span v-if="item.status_label" class="todo-status">{{ item.status_label }}</span>
          </div>
          <div class="todo-row-main">
            <strong>{{ item.title }}</strong>
            <span v-if="item.subtitle" class="todo-sub">{{ item.subtitle }}</span>
          </div>
          <div class="todo-row-meta">
            <span v-if="item.due_at" class="todo-due">{{ formatDue(item.due_at) }}</span>
            <span v-else class="todo-due todo-due--empty" />
            <span class="todo-go">去处理</span>
          </div>
        </button>
      </div>

      <div v-else class="todo-empty">
        <p class="todo-empty-title">暂无待办</p>
        <p class="todo-empty-desc">当前分类没有需要处理的事项，可切换分类或稍后刷新。</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMyTodos, type TodoCategory, type TodoList } from '@/api/todos'
import { useMatchMedia } from '@/composables/useMatchMedia'

const router = useRouter()
const isCompact = useMatchMedia('(max-width: 768px)')
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
/* 对齐经营总览 · Cool Enterprise Ops Desk */
.todo-page {
  --td-ink: #0f172a;
  --td-ink-soft: #64748b;
  --td-ink-faint: #94a3b8;
  --td-line: #e2e8f0;
  --td-mist: #f1f5f9;
  --td-sky: #eff6ff;
  --td-sky-mid: #dbeafe;
  --td-blue: #1e40af;
  --td-blue-mid: #3b82f6;
  --td-amber: #d97706;
  --td-amber-soft: #fffbeb;
  --td-success: #047857;
  --td-success-soft: #ecfdf5;
  --td-danger: #dc2626;
  --td-danger-soft: #fef2f2;
  --td-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);
  --td-shadow-hover: 0 14px 28px rgba(15, 23, 42, 0.08);

  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.todo-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--td-line);
  border-radius: 16px;
  background:
    radial-gradient(ellipse 72% 100% at 0% 0%, rgba(59, 130, 246, 0.1), transparent 52%),
    radial-gradient(ellipse 50% 80% at 100% 0%, rgba(30, 64, 175, 0.05), transparent 48%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: var(--td-shadow);
}

.todo-eyebrow {
  margin: 0 0 6px;
  color: var(--td-blue-mid);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.16em;
  line-height: 1.2;
}

.todo-head-copy h1 {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', var(--crm-font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1.2;
  color: var(--td-ink);
}

.todo-head-copy p:last-child,
.todo-head-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--td-ink-soft);
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
  position: relative;
  border: 1px solid var(--td-line);
  background: #fff;
  border-radius: 14px;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
  min-width: 0;
  box-shadow: var(--td-shadow);
  transition:
    border-color 180ms var(--crm-ease-out),
    box-shadow 180ms var(--crm-ease-out),
    transform 180ms var(--crm-ease-out),
    background-color 180ms var(--crm-ease-out);
}

.todo-kpi:hover {
  border-color: color-mix(in oklab, var(--td-blue) 22%, var(--td-line));
  box-shadow: var(--td-shadow-hover);
  transform: translateY(-1px);
}

.todo-kpi:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--td-blue) 50%, white);
  outline-offset: 2px;
}

.todo-kpi.active {
  border-color: color-mix(in oklab, var(--td-blue-mid) 28%, var(--td-line));
  background: linear-gradient(160deg, rgba(239, 246, 255, 0.95), #fff 58%);
  box-shadow:
    0 10px 22px rgba(15, 23, 42, 0.06),
    inset 0 0 0 1px rgba(59, 130, 246, 0.12);
}

.todo-kpi.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: linear-gradient(180deg, #60a5fa, var(--td-blue));
}

.todo-kpi small {
  display: block;
  color: var(--td-ink-soft);
  font-size: 12px;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.todo-kpi b {
  display: block;
  font-family: var(--crm-font-data);
  font-size: 24px;
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--td-ink);
}

.todo-kpi b.danger {
  color: var(--td-danger);
}

.todo-panel {
  background: #fff;
  border: 1px solid var(--td-line);
  border-radius: 14px;
  padding: 16px 18px 14px;
  min-height: 240px;
  box-shadow: var(--td-shadow);
}

.todo-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.todo-panel-head strong {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--td-ink);
}

.todo-panel-head p,
.todo-panel-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--td-ink-faint);
}

.todo-count-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--td-sky-mid);
  border-radius: 999px;
  background: var(--td-sky);
  color: var(--td-blue);
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.todo-partial {
  margin-bottom: 12px;
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
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas: 'top main meta';
  align-items: center;
  gap: 12px 14px;
  padding: 13px 14px;
  border: 1px solid var(--td-line);
  border-radius: 12px;
  background: var(--td-mist);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 180ms var(--crm-ease-out),
    background-color 180ms var(--crm-ease-out),
    box-shadow 180ms var(--crm-ease-out);
}

.todo-row:hover {
  border-color: color-mix(in oklab, var(--td-blue) 22%, var(--td-line));
  background: #fff;
  box-shadow: var(--td-shadow-hover);
}

.todo-row:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--td-blue) 50%, white);
  outline-offset: 2px;
}

.todo-row.urgent {
  border-left: 3px solid var(--td-danger);
  background: color-mix(in oklab, var(--td-danger-soft) 55%, var(--td-mist));
}

.todo-row-top {
  grid-area: top;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}

.todo-cat {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--td-line);
  color: var(--td-ink-soft);
  font-size: 12px;
  white-space: nowrap;
}

.todo-cat[data-cat='approval'] {
  color: var(--td-danger);
  border-color: color-mix(in oklab, var(--td-danger) 28%, var(--td-line));
  background: var(--td-danger-soft);
}

.todo-cat[data-cat='ticket'] {
  color: var(--td-blue);
  border-color: color-mix(in oklab, var(--td-blue) 28%, var(--td-line));
  background: var(--td-sky);
}

.todo-cat[data-cat='lead'] {
  color: var(--td-amber);
  border-color: color-mix(in oklab, var(--td-amber) 28%, var(--td-line));
  background: var(--td-amber-soft);
}

.todo-cat[data-cat='task'] {
  color: var(--td-success);
  border-color: color-mix(in oklab, var(--td-success) 28%, var(--td-line));
  background: var(--td-success-soft);
}

.todo-cat[data-cat='schedule'],
.todo-cat[data-cat='resource'] {
  color: var(--td-blue-mid);
  border-color: color-mix(in oklab, var(--td-blue-mid) 22%, var(--td-line));
  background: var(--td-sky-mid);
}

.todo-row-main {
  grid-area: main;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.todo-row-main strong {
  font-size: 14px;
  font-weight: 650;
  color: var(--td-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-sub {
  font-size: 12px;
  color: var(--td-ink-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-row-meta {
  grid-area: meta;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
  font-size: 12px;
}

.todo-status {
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--td-line);
  color: var(--td-ink);
}

.todo-due {
  color: var(--td-ink-faint);
  font-variant-numeric: tabular-nums;
}

.todo-due--empty {
  display: none;
}

.todo-go {
  color: var(--td-blue);
  font-weight: 650;
  white-space: nowrap;
}

.todo-go::after {
  content: ' →';
}

.todo-empty {
  padding: 36px 12px 28px;
  text-align: center;
}

.todo-empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--td-ink);
}

.todo-empty-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--td-ink-faint);
  line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
  .todo-kpi,
  .todo-row {
    transition: none;
  }

  .todo-kpi:hover {
    transform: none;
  }
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
}

@media (max-width: 768px) {
  .todo-page {
    gap: 10px;
  }

  .todo-head {
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
  }

  .todo-head-copy h1 {
    font-size: 20px;
  }

  .todo-head-desc {
    display: none;
  }

  .todo-head-actions {
    width: 100%;
  }

  .todo-head-actions .el-button {
    width: 100%;
  }

  .todo-kpis {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding-bottom: 2px;
    scrollbar-width: none;
  }

  .todo-kpis::-webkit-scrollbar {
    display: none;
  }

  .todo-kpi {
    flex: 0 0 auto;
    min-width: 108px;
    padding: 10px 12px;
  }

  .todo-kpi:hover {
    transform: none;
  }

  .todo-kpi small {
    font-size: 11px;
    margin-bottom: 4px;
  }

  .todo-kpi b {
    font-size: 18px;
  }

  .todo-panel {
    padding: 12px 12px 10px;
    border-radius: 12px;
  }

  .todo-panel-hint {
    display: none;
  }

  .todo-row {
    grid-template-columns: 1fr;
    grid-template-areas:
      'top'
      'main'
      'meta';
    gap: 8px;
    padding: 12px;
  }

  .todo-row-top {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }

  .todo-row-main strong {
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .todo-sub {
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .todo-row-meta {
    justify-content: space-between;
    width: 100%;
  }

  .todo-due--empty {
    display: block;
  }

  .todo-go::after {
    content: '';
  }
}

@media (max-width: 640px) {
  .todo-kpi {
    min-width: 96px;
  }
}
</style>
