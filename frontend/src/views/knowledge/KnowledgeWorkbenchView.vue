<template>
  <div class="crm-page knowledge-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-actions">
        <el-button @click="authVisible = true">来源授权</el-button>
        <el-button v-if="canManage" type="primary" @click="openCreateSource">＋ 添加知识源</el-button>
      </div>
    </header>

    <section class="knowledge-layout">
      <aside class="knowledge-side">
        <div class="card-head">
          <div>
            <h2>知识空间</h2>
            <p>按权限显示可访问内容</p>
          </div>
        </div>
        <button
          v-for="sp in spaces"
          :key="sp.id"
          type="button"
          class="source-item"
          :class="{ active: activeSpaceId === sp.id }"
          @click="activeSpaceId = sp.id"
        >
          <span class="source-icon">{{ sp.icon }}</span>
          <span>
            <b>{{ sp.name }}</b>
            <small>
              {{
                sp.code === 'all'
                  ? `${formatCount(totalPublished)} 条已发布`
                  : `${formatCount(sp.article_count)} 条`
              }}
            </small>
          </span>
        </button>

        <div class="card-head" style="margin-top: 22px">
          <div><h3>采集状态</h3></div>
          <el-tag :type="syncStats?.status === '正常' ? 'success' : 'warning'" size="small">
            {{ syncStats?.status || '—' }}
          </el-tag>
        </div>
        <div class="knowledge-health">
          <div class="health-row">
            <span>授权工作群</span>
            <b>{{ syncStats?.authorized_chats ?? 0 }}</b>
          </div>
          <div class="health-row">
            <span>云文档目录</span>
            <b>{{ syncStats?.doc_dirs ?? 0 }}</b>
          </div>
          <div class="health-row">
            <span>待审核条目</span>
            <b>{{ syncStats?.pending_review ?? 0 }}</b>
          </div>
          <div class="health-row">
            <span>同步失败</span>
            <b :class="{ warn: (syncStats?.sync_failed ?? 0) > 0 }">{{ syncStats?.sync_failed ?? 0 }}</b>
          </div>
        </div>
      </aside>

      <div class="knowledge-main">
        <article class="knowledge-search">
          <h2>向企业知识库提问</h2>
          <p>答案仅基于你有权访问的内容，并附带来源、版本和更新时间。</p>
          <div class="ask-box">
            <el-input
              v-model="question"
              clearable
              placeholder="输入业务问题，例如：AI定制项目延期时需要走什么变更流程？"
              @keyup.enter="onAsk"
            />
            <el-button type="primary" :loading="asking" @click="onAsk">生成答案</el-button>
          </div>
        </article>

        <article v-if="answer" class="answer-card">
          <div class="answer-head">
            <span class="ai-mark">知</span>
            <div>
              <b>
                {{
                  answer.matched_count
                    ? `基于 ${answer.matched_count} 个已授权来源整理`
                    : '未命中已发布知识'
                }}
              </b>
              <small>
                检索时间 {{ answer.retrieved_at }} · 内容版本已校验 ·
                {{ answer.answer_mode === 'llm' ? '大模型整理' : '检索整理' }}
              </small>
            </div>
          </div>
          <div class="answer-copy" v-html="answer.answer_html" />
          <button
            v-for="(c, i) in answer.citations"
            :key="c.article_id"
            type="button"
            class="citation"
            @click="openArticle(c.article_id)"
          >
            <span class="source-icon">{{ i + 1 }}</span>
            <span>
              <b>{{ c.title }}</b>
              <small>
                {{ c.source_label }} · {{ c.version }}
                <template v-if="c.updated_at"> · 更新于 {{ c.updated_at }}</template>
              </small>
            </span>
          </button>
        </article>

        <article v-else class="answer-card">
          <div class="knowledge-empty">输入问题后生成带引用的答案。可先试试左侧空间中的交付规范相关问题。</div>
        </article>
      </div>
    </section>

    <!-- 来源授权列表 -->
    <el-drawer v-model="authVisible" title="来源授权" size="480px" destroy-on-close>
      <div v-for="s in sources" :key="s.id" class="citation" style="cursor: default; margin-bottom: 10px">
        <span class="source-icon">{{ sourceTypeIcon(s.source_type) }}</span>
        <span style="flex: 1">
          <b>{{ s.name }}</b>
          <small>
            {{ sourceTypeLabel(s.source_type) }} ·
            {{ s.authorized ? '已授权' : '未授权' }} ·
            {{ s.status }}
            <template v-if="s.sync_error"> · {{ s.sync_error }}</template>
          </small>
        </span>
        <el-button
          v-if="canManage && (!s.authorized || s.status === 'failed')"
          size="small"
          type="primary"
          :loading="acting"
          @click="onAuthorize(s)"
        >
          授权同步
        </el-button>
      </div>
    </el-drawer>

    <!-- 知识条目详情 -->
    <el-drawer v-model="articleVisible" :title="articleDetail?.title || '知识详情'" size="520px" destroy-on-close>
      <template v-if="articleDetail">
        <div style="margin-bottom: 14px">
          <el-tag size="small">{{ articleDetail.space_name || '—' }}</el-tag>
          <span style="margin-left: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            {{ articleDetail.source_label || '—' }} · {{ articleDetail.version }}
          </span>
        </div>
        <p style="line-height: 1.75; color: var(--crm-ink); white-space: pre-wrap">{{ articleDetail.content }}</p>
      </template>
    </el-drawer>

    <!-- 添加知识源 -->
    <el-dialog v-model="createVisible" title="添加知识源" width="560px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="知识源名称" required>
          <el-input v-model="sourceForm.name" placeholder="例如：项目交付规范云文档目录" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="sourceForm.source_type" style="width: 100%">
            <el-option
              v-for="opt in SOURCE_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="归属知识空间">
          <el-select v-model="sourceForm.space_id" clearable placeholder="可选" style="width: 100%">
            <el-option
              v-for="sp in spaces.filter((x) => x.code !== 'all')"
              :key="sp.id"
              :label="sp.name"
              :value="sp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="外部标识">
          <el-input v-model="sourceForm.external_ref" placeholder="飞书 chat_id / wiki token，可空" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="sourceForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitSource">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  SOURCE_TYPE_OPTIONS,
  askKnowledge,
  authorizeKnowledgeSource,
  createKnowledgeSource,
  fetchKnowledgeWorkbench,
  type KnowledgeArticle,
  type KnowledgeAskResult,
  type KnowledgeSource,
  type KnowledgeSpace,
  type KnowledgeSyncStats,
} from '@/api/knowledge'

const loading = ref(false)
const asking = ref(false)
const acting = ref(false)
const canManage = ref(false)
const spaces = ref<KnowledgeSpace[]>([])
const sources = ref<KnowledgeSource[]>([])
const articles = ref<KnowledgeArticle[]>([])
const syncStats = ref<KnowledgeSyncStats | null>(null)
const totalPublished = ref(0)
const activeSpaceId = ref<number | null>(null)

const question = ref('AI定制项目延期时，需要走什么变更流程？')
const answer = ref<KnowledgeAskResult | null>(null)

const authVisible = ref(false)
const createVisible = ref(false)
const articleVisible = ref(false)
const articleDetail = ref<KnowledgeArticle | null>(null)

const sourceForm = reactive({
  name: '',
  source_type: 'feishu_doc',
  space_id: undefined as number | undefined,
  external_ref: '',
  remark: '',
})

const activeSpace = computed(() => spaces.value.find((x) => x.id === activeSpaceId.value) || null)

function formatCount(n: number) {
  return Number(n || 0).toLocaleString()
}

function sourceTypeLabel(t: string) {
  return SOURCE_TYPE_OPTIONS.find((x) => x.value === t)?.label || t
}

function sourceTypeIcon(t: string) {
  if (t === 'feishu_chat') return '群'
  if (t === 'feishu_doc') return '文'
  return '录'
}

async function reload() {
  loading.value = true
  try {
    const { data } = await fetchKnowledgeWorkbench()
    spaces.value = data.spaces || []
    sources.value = data.sources || []
    articles.value = data.articles || []
    syncStats.value = data.sync_stats
    totalPublished.value = data.total_published
    canManage.value = data.can_manage
    if (!activeSpaceId.value && spaces.value.length) {
      activeSpaceId.value = spaces.value[0].id
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onAsk() {
  const q = question.value.trim()
  if (q.length < 2) {
    ElMessage.warning('请输入问题')
    return
  }
  asking.value = true
  try {
    const space = activeSpace.value
    const spaceId = space && space.code !== 'all' ? space.id : undefined
    const { data } = await askKnowledge({ question: q, space_id: spaceId })
    answer.value = data
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '提问失败')
  } finally {
    asking.value = false
  }
}

function openArticle(id: number) {
  const row = articles.value.find((x) => x.id === id)
  if (!row) {
    ElMessage.info('条目详情暂不可用')
    return
  }
  articleDetail.value = row
  articleVisible.value = true
}

function openCreateSource() {
  sourceForm.name = ''
  sourceForm.source_type = 'feishu_doc'
  sourceForm.space_id = spaces.value.find((x) => x.code === 'delivery')?.id
  sourceForm.external_ref = ''
  sourceForm.remark = ''
  createVisible.value = true
}

async function submitSource() {
  if (!sourceForm.name.trim()) {
    ElMessage.warning('请填写知识源名称')
    return
  }
  acting.value = true
  try {
    await createKnowledgeSource({
      name: sourceForm.name.trim(),
      source_type: sourceForm.source_type,
      space_id: sourceForm.space_id,
      external_ref: sourceForm.external_ref || undefined,
      remark: sourceForm.remark || undefined,
    })
    createVisible.value = false
    ElMessage.success('知识源已添加')
    await reload()
    authVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    acting.value = false
  }
}

async function onAuthorize(s: KnowledgeSource) {
  acting.value = true
  try {
    await authorizeKnowledgeSource(s.id)
    ElMessage.success('已授权并标记为可同步')
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '授权失败')
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  await reload()
  // 进入页面按原型默认问题拉一次答案，便于验收
  await onAsk()
})
</script>
