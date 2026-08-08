<template>
  <div class="crm-page asset-workbench crm-fit-page" v-loading="loading">
    <header class="asset-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>固定资产</h1>
        <p>{{ isEmployee ? '申请借用、查看本人记录与可借器材' : '管库存、审批借用；需要时再入库或扫码' }}</p>
      </div>
      <div class="asset-head-actions">
        <el-button @click="openScanner()">扫码</el-button>
        <el-button v-if="canManage && isEmployee" @click="viewMode = 'admin'">返回管理</el-button>
        <el-button v-else-if="canManage" @click="viewMode = 'employee'">员工自助</el-button>
        <el-button v-if="!isEmployee && canManage" type="primary" @click="openCreateAsset">＋ 设备入库</el-button>
        <el-button v-else type="primary" @click="openCreateBorrow">＋ 申请借用</el-button>
      </div>
    </header>

    <div class="crm-fit-body" :class="{ 'is-scroll': isEmployee || tab === 'overview' }">
    <!-- 员工自助 -->
    <template v-if="isEmployee">
      <section class="asset-kpis">
        <button type="button" class="asset-kpi" @click="scrollTo('my-borrows')">
          <small>我的使用中</small>
          <b>{{ myCounts.inUse }}</b>
        </button>
        <button type="button" class="asset-kpi" @click="scrollTo('my-borrows')">
          <small>待审批</small>
          <b>{{ myCounts.pending }}</b>
        </button>
        <button type="button" class="asset-kpi" @click="scrollTo('my-borrows')">
          <small>待归还</small>
          <b :class="{ danger: myCounts.pendingReturn > 0 }">{{ myCounts.pendingReturn }}</b>
        </button>
        <button type="button" class="asset-kpi" @click="scrollTo('available-list')">
          <small>可借器材</small>
          <b>{{ availableAssets.length }}</b>
        </button>
      </section>

      <section id="my-borrows" class="asset-panel">
        <div class="panel-head">
          <h2>我的借用</h2>
          <el-button type="primary" size="small" @click="openCreateBorrow">申请借用</el-button>
        </div>
        <el-table :data="myBorrows" stripe empty-text="暂无借用记录" @row-click="openBorrowDrawer">
          <el-table-column label="用途" min-width="180">
            <template #default="{ row }">
              <b>{{ row.purpose }}</b>
              <div class="muted">{{ row.request_no }}</div>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="160">
            <template #default="{ row }">{{ formatPeriod(row) }}</template>
          </el-table-column>
          <el-table-column label="件数" width="70">
            <template #default="{ row }">{{ row.asset_count }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="borrowTag(row.status)">
                {{ BORROW_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section id="available-list" class="asset-panel">
        <div class="panel-head">
          <h2>可借器材</h2>
          <span class="muted">点选查看详情，或直接申请借用</span>
        </div>
        <div v-if="availableAssets.length" class="asset-chips">
          <button
            v-for="a in availableAssets"
            :key="a.id"
            type="button"
            class="asset-chip"
            @click="openAssetDrawer(a)"
          >
            <b>{{ a.name }}</b>
            <small>{{ a.category }} · {{ a.location || '未标注位置' }}</small>
          </button>
        </div>
        <div v-else class="empty-hint">暂无可借器材</div>
      </section>
    </template>

    <!-- 管理视角 -->
    <template v-else>
      <div class="asset-tabs" role="tablist">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          class="asset-tab"
          :class="{ active: tab === item.key }"
          @click="tab = item.key"
        >
          {{ item.label }}
          <em v-if="item.key === 'borrow' && borrowCounts.pending">{{ borrowCounts.pending }}</em>
        </button>
      </div>

      <!-- 总览：数字 + 待办 + 最近借用 -->
      <template v-if="tab === 'overview'">
        <section class="asset-kpis">
          <button type="button" class="asset-kpi" @click="tab = 'ledger'">
            <small>资产总数</small>
            <b>{{ stats?.total ?? 0 }}</b>
            <span>原值 ¥{{ money(stats?.original_value_sum) }}</span>
          </button>
          <button type="button" class="asset-kpi" @click="goLedger('available')">
            <small>当前可用</small>
            <b>{{ stats?.available ?? 0 }}</b>
            <span>可用率 {{ stats?.available_rate ?? 0 }}%</span>
          </button>
          <button type="button" class="asset-kpi" @click="goBorrow('in_use')">
            <small>借出 / 预占</small>
            <b>{{ stats?.borrowed_or_reserved ?? 0 }}</b>
            <span>今日到期 {{ stats?.due_today ?? 0 }}</span>
          </button>
          <button type="button" class="asset-kpi" @click="focusAlerts">
            <small>待处理</small>
            <b :class="{ danger: (stats?.alerts || 0) > 0 }">{{ stats?.alerts ?? 0 }}</b>
            <span>维保 {{ stats?.maintenance ?? 0 }} · 逾期 {{ stats?.overdue ?? 0 }}</span>
          </button>
        </section>

        <section v-if="alerts.length" id="asset-alerts" class="asset-panel">
          <div class="panel-head">
            <h2>待处理提醒</h2>
            <span class="muted">{{ alerts.length }} 项</span>
          </div>
          <div class="alert-list">
            <button v-for="(a, i) in alerts" :key="i" type="button" class="alert-row" @click="onAlertClick(a)">
              <i :class="alertDot(a.kind)" />
              <span>
                <b>{{ a.title }}</b>
                <small>{{ a.detail }}</small>
              </span>
              <em>{{ a.tag }}</em>
            </button>
          </div>
        </section>

        <section v-if="categoryUsage.length" class="asset-panel">
          <div class="panel-head">
            <h2>分类库存</h2>
            <span class="muted">点击跳转台账筛选</span>
          </div>
          <div class="cat-chips">
            <button
              v-for="c in categoryUsage"
              :key="c.category"
              type="button"
              class="cat-chip"
              @click="goLedgerByCategory(c.category)"
            >
              <b>{{ c.category }}</b>
              <span>{{ c.count }} 件</span>
            </button>
          </div>
        </section>

        <section class="asset-panel">
          <div class="panel-head">
            <h2>最近借用</h2>
            <el-button link type="primary" @click="tab = 'borrow'">全部记录</el-button>
          </div>
          <el-table
            :data="borrows.slice(0, 8)"
            stripe
            empty-text="暂无借用记录"
            @row-click="openBorrowDrawer"
          >
            <el-table-column label="用途" min-width="160">
              <template #default="{ row }">
                <b>{{ row.purpose }}</b>
                <div class="muted">{{ row.request_no }}</div>
              </template>
            </el-table-column>
            <el-table-column label="使用人" width="100">
              <template #default="{ row }">{{ row.applicant_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="时间" min-width="150">
              <template #default="{ row }">{{ formatPeriod(row) }}</template>
            </el-table-column>
            <el-table-column label="件数" width="70">
              <template #default="{ row }">{{ row.asset_count }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="borrowTag(row.status)">
                  {{ BORROW_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </template>

      <!-- 台账 -->
      <template v-else-if="tab === 'ledger'">
        <div class="asset-toolbar">
          <div class="filters">
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索编号 / 名称 / 型号"
              style="width: 220px"
            />
            <el-select v-model="filterCategory" clearable placeholder="分类" style="width: 130px">
              <el-option v-for="c in ASSET_CATEGORY_OPTIONS" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="filterStatus" clearable placeholder="状态" style="width: 130px">
              <el-option
                v-for="(label, key) in ASSET_STATUS_LABEL"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </div>
          <span class="muted">共 {{ filteredAssets.length }} 件</span>
        </div>
        <section class="asset-panel crm-fit-panel">
          <div class="crm-table-wrap is-fit">
            <el-table
              :data="filteredAssets"
              stripe
              empty-text="没有匹配的资产"
              height="100%"
              @row-click="openAssetDrawer"
            >
              <el-table-column label="资产" min-width="200">
                <template #default="{ row }">
                  <b>{{ row.name }}</b>
                  <div class="muted">{{ row.asset_no }}</div>
                </template>
              </el-table-column>
              <el-table-column label="分类" width="100">
                <template #default="{ row }">{{ row.category }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="assetTag(row.status)">
                    {{ ASSET_STATUS_LABEL[row.status] || row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="使用人" width="100">
                <template #default="{ row }">{{ row.holder_name || '—' }}</template>
              </el-table-column>
              <el-table-column prop="location" label="位置" min-width="120" show-overflow-tooltip />
              <el-table-column label="原值" width="110">
                <template #default="{ row }">¥{{ money(row.original_value) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </template>

      <!-- 借用归还 -->
      <template v-else>
        <div class="asset-toolbar">
          <el-radio-group v-model="borrowFilter" size="small">
            <el-radio-button value="all">全部 {{ borrows.length }}</el-radio-button>
            <el-radio-button value="pending">待审批 {{ borrowCounts.pending }}</el-radio-button>
            <el-radio-button value="in_use">使用中 {{ borrowCounts.inUse }}</el-radio-button>
            <el-radio-button value="pending_return">待归还 {{ borrowCounts.pendingReturn }}</el-radio-button>
          </el-radio-group>
          <el-button type="primary" @click="openCreateBorrow">＋ 新建借用</el-button>
        </div>
        <section class="asset-panel crm-fit-panel">
          <div class="crm-table-wrap is-fit">
            <el-table
              :data="filteredBorrows"
              stripe
              empty-text="暂无记录"
              height="100%"
              @row-click="openBorrowDrawer"
            >
              <el-table-column label="用途" min-width="170">
                <template #default="{ row }">
                  <b>{{ row.purpose }}</b>
                  <div class="muted">{{ row.request_no }}</div>
                </template>
              </el-table-column>
              <el-table-column label="使用人" width="100">
                <template #default="{ row }">{{ row.applicant_name || '—' }}</template>
              </el-table-column>
              <el-table-column label="时间" min-width="150">
                <template #default="{ row }">{{ formatPeriod(row) }}</template>
              </el-table-column>
              <el-table-column label="件数" width="70">
                <template #default="{ row }">{{ row.asset_count }}</template>
              </el-table-column>
              <el-table-column label="关联档期" width="110" show-overflow-tooltip>
                <template #default="{ row }">{{ row.schedule_ref || '—' }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="borrowTag(row.status)">
                    {{ BORROW_STATUS_LABEL[row.status] || row.status }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </template>
    </template>
    </div>

    <!-- 资产详情 -->
    <el-drawer v-model="assetDrawerVisible" :title="assetDrawer?.name || '资产详情'" size="420px" destroy-on-close>
      <template v-if="assetDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="assetTag(assetDrawer.status)">
            {{ ASSET_STATUS_LABEL[assetDrawer.status] || assetDrawer.status }}
          </el-tag>
          <span class="muted" style="margin-left: 8px">{{ assetDrawer.asset_no }}</span>
        </div>
        <div class="drawer-section">
          <div class="drawer-grid">
            <div><small>分类 / 型号</small><b>{{ assetDrawer.category }} · {{ assetDrawer.model || '—' }}</b></div>
            <div><small>使用人</small><b>{{ assetDrawer.holder_name || '—' }}</b></div>
            <div><small>位置</small><b>{{ assetDrawer.location || '—' }}</b></div>
            <div><small>原值 / 净值</small><b>¥{{ money(assetDrawer.original_value) }} / ¥{{ money(assetDrawer.net_value) }}</b></div>
            <div><small>下次维保</small><b>{{ assetDrawer.next_maintenance || '—' }}</b></div>
            <div><small>关联档期</small><b>{{ assetDrawer.schedule_ref || '—' }}</b></div>
          </div>
        </div>
        <el-button
          v-if="assetDrawer.status === 'available'"
          type="primary"
          style="width: 100%"
          @click="borrowThisAsset(assetDrawer)"
        >
          申请借用此器材
        </el-button>
      </template>
    </el-drawer>

    <!-- 借用详情 -->
    <el-drawer
      v-model="borrowDrawerVisible"
      :title="borrowDrawer?.request_no || '借用申请'"
      size="440px"
      destroy-on-close
    >
      <template v-if="borrowDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="borrowTag(borrowDrawer.status)">
            {{ BORROW_STATUS_LABEL[borrowDrawer.status] || borrowDrawer.status }}
          </el-tag>
          <span class="muted" style="margin-left: 8px">{{ formatPeriod(borrowDrawer) }}</span>
        </div>
        <div class="drawer-section">
          <h4>{{ borrowDrawer.purpose }}</h4>
          <div class="drawer-grid">
            <div><small>申请人</small><b>{{ borrowDrawer.applicant_name || '—' }}</b></div>
            <div><small>关联档期</small><b>{{ borrowDrawer.schedule_ref || '—' }}</b></div>
            <div><small>器材数量</small><b>{{ borrowDrawer.asset_count }} 件</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>器材清单</h4>
          <div class="linked-assets">
            <div v-for="a in borrowDrawer.assets" :key="a.asset_id" class="linked-row">
              <b>{{ a.name }}</b>
              <small>{{ a.asset_no }} · {{ ASSET_STATUS_LABEL[a.status] || a.status }}</small>
            </div>
          </div>
        </div>
        <div class="drawer-actions">
          <template v-if="borrowDrawer.status === 'pending' && canManage">
            <el-button type="danger" :loading="acting" @click="onReject">驳回</el-button>
            <el-button type="primary" :loading="acting" @click="onApprove">批准</el-button>
          </template>
          <template v-else-if="borrowDrawer.status === 'approved'">
            <el-button type="primary" :loading="acting" @click="onCheckout">确认领用</el-button>
          </template>
          <template v-else-if="['in_use', 'pending_return'].includes(borrowDrawer.status)">
            <el-button type="primary" :loading="acting" @click="onReturn">确认归还</el-button>
          </template>
        </div>
      </template>
    </el-drawer>

    <!-- 入库 -->
    <el-dialog v-model="createAssetVisible" title="设备入库" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="资产名称" required>
          <el-input v-model="assetForm.name" placeholder="例如：Sony FX3" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="assetForm.category" style="width: 100%">
            <el-option v-for="c in ASSET_CATEGORY_OPTIONS" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="品牌型号">
          <el-input v-model="assetForm.model" />
        </el-form-item>
        <el-form-item label="序列号">
          <el-input v-model="assetForm.serial_no" />
        </el-form-item>
        <el-form-item label="存放位置">
          <el-input v-model="assetForm.location" />
        </el-form-item>
        <el-form-item label="原值">
          <el-input-number v-model="assetForm.original_value" :min="0" :step="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createAssetVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreateAsset">保存</el-button>
      </template>
    </el-dialog>

    <!-- 借用申请 -->
    <el-dialog
      v-model="createBorrowVisible"
      title="申请借用"
      width="600px"
      destroy-on-close
      class="borrow-dialog"
    >
      <p class="borrow-hint">
        先定用途和时段，再选在库器材。若已有排期，选档期可自动带出时间。
      </p>
      <el-form label-position="top" class="borrow-form">
        <section class="borrow-block">
          <h3><span>1</span>用途与时段</h3>
          <el-form-item label="使用用途" required>
            <el-input
              v-model="borrowForm.purpose"
              maxlength="100"
              show-word-limit
              placeholder="例如：客户现场拍摄 / 活动跟拍"
            />
          </el-form-item>
          <el-form-item label="关联排期（可选）">
            <el-select
              v-model="borrowForm.schedule_id"
              clearable
              filterable
              remote
              :remote-method="searchSchedules"
              :loading="scheduleLoading"
              placeholder="搜索排期标题，选中后自动带时段"
              style="width: 100%"
              @visible-change="(open: boolean) => open && searchSchedules('')"
              @change="onSchedulePicked"
              @clear="onScheduleCleared"
            >
              <el-option
                v-for="s in scheduleOptions"
                :key="s.id"
                :label="scheduleOptionLabel(s)"
                :value="s.id"
              />
            </el-select>
            <div class="field-tip">不挂排期也可以借；挂上后便于从排期追溯器材。</div>
          </el-form-item>
          <el-form-item label="借用时段" required>
            <el-date-picker
              v-model="borrowForm.range"
              type="datetimerange"
              value-format="YYYY-MM-DDTHH:mm:ss"
              start-placeholder="开始"
              end-placeholder="归还"
              style="width: 100%"
            />
          </el-form-item>
        </section>

        <section class="borrow-block">
          <h3>
            <span>2</span>选择器材
            <em>已选 {{ borrowForm.asset_ids.length }} 件</em>
          </h3>
          <div class="borrow-asset-toolbar">
            <el-input
              v-model="borrowAssetKeyword"
              clearable
              placeholder="搜索器材名称"
              style="flex: 1"
            />
            <el-select
              v-model="borrowAssetCategory"
              clearable
              placeholder="分类"
              style="width: 120px"
            >
              <el-option v-for="c in ASSET_CATEGORY_OPTIONS" :key="c" :label="c" :value="c" />
            </el-select>
          </div>
          <div class="asset-choice-list">
            <button
              v-for="a in filteredBorrowAssets"
              :key="a.id"
              type="button"
              class="asset-pick"
              :class="{ selected: borrowForm.asset_ids.includes(a.id) }"
              @click="toggleAsset(a.id, !borrowForm.asset_ids.includes(a.id))"
            >
              <el-checkbox
                :model-value="borrowForm.asset_ids.includes(a.id)"
                @click.stop
                @change="(v: boolean | string | number) => toggleAsset(a.id, !!v)"
              />
              <span class="asset-pick-body">
                <b>{{ a.name }}</b>
                <small>{{ a.category }}{{ a.location ? ` · ${a.location}` : '' }}</small>
              </span>
              <el-tag size="small" type="success">可借</el-tag>
            </button>
            <div v-if="!filteredBorrowAssets.length" class="empty-hint">没有匹配的在库器材</div>
          </div>
          <div v-if="selectedBorrowAssets.length" class="selected-summary">
            已选：
            <el-tag
              v-for="a in selectedBorrowAssets"
              :key="a.id"
              size="small"
              closable
              style="margin: 2px 4px 2px 0"
              @close="toggleAsset(a.id, false)"
            >
              {{ a.name }}
            </el-tag>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="createBorrowVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreateBorrow">
          提交申请
        </el-button>
      </template>
    </el-dialog>

    <!-- 扫码 -->
    <el-dialog v-model="scannerVisible" title="扫码" width="400px" destroy-on-close>
      <div class="scan-box">
        <el-radio-group v-model="scanMode" size="small">
          <el-radio-button value="checkout">领用</el-radio-button>
          <el-radio-button value="return">归还</el-radio-button>
          <el-radio-button value="inventory">盘点</el-radio-button>
        </el-radio-group>
        <p class="muted" style="margin: 14px 0">演示环境：点击下方按钮模拟扫到一台设备</p>
        <div v-if="scanResult" class="scan-result">
          <b>{{ scanResult.asset?.name || '已扫码' }}</b>
          <small>{{ scanResult.message }}</small>
        </div>
        <el-button type="primary" style="width: 100%" :loading="acting" @click="doScan">模拟扫码</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ASSET_CATEGORY_OPTIONS,
  ASSET_STATUS_LABEL,
  BORROW_STATUS_LABEL,
  approveBorrow,
  checkoutBorrow,
  createAsset,
  createBorrow,
  fetchAssetWorkbench,
  rejectBorrow,
  returnBorrow,
  scanAsset,
  type AssetStats,
  type BorrowRequest,
  type FixedAsset,
  type InventorySession,
} from '@/api/assets'
import { fetchSchedules, type Schedule } from '@/api/schedules'
import { useUserStore } from '@/stores/user'

type TabKey = 'overview' | 'ledger' | 'borrow'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '总览' },
  { key: 'ledger', label: '台账' },
  { key: 'borrow', label: '借用' },
]

const userStore = useUserStore()
const route = useRoute()
const loading = ref(false)
const acting = ref(false)
const tab = ref<TabKey>('overview')
const viewMode = ref<'admin' | 'employee'>('admin')

const stats = ref<AssetStats | null>(null)
const assets = ref<FixedAsset[]>([])
const borrows = ref<BorrowRequest[]>([])
const inventory = ref<InventorySession | null>(null)
const categoryUsage = ref<Array<{ category: string; count: number; utilization: number }>>([])
const alerts = ref<
  Array<{
    kind: string
    title: string
    detail: string
    tag: string
    asset_id?: number | null
    request_id?: number | null
  }>
>([])
const canManage = ref(false)

const keyword = ref('')
const filterCategory = ref<string | undefined>()
const filterStatus = ref<string | undefined>()
const borrowFilter = ref('all')

const assetDrawerVisible = ref(false)
const assetDrawer = ref<FixedAsset | null>(null)
const borrowDrawerVisible = ref(false)
const borrowDrawer = ref<BorrowRequest | null>(null)
const createAssetVisible = ref(false)
const createBorrowVisible = ref(false)
const scannerVisible = ref(false)
const scanMode = ref('checkout')
const scanResult = ref<{ message: string; asset?: FixedAsset } | null>(null)
const scheduleLoading = ref(false)
const scheduleOptions = ref<Schedule[]>([])
const borrowAssetKeyword = ref('')
const borrowAssetCategory = ref<string | undefined>()

const assetForm = reactive({
  name: '',
  category: '相机',
  model: '',
  serial_no: '',
  location: '新媒体器材柜 A1',
  original_value: 10000,
})

const borrowForm = reactive({
  purpose: '',
  schedule_id: undefined as number | undefined,
  schedule_ref: '',
  range: [] as string[],
  asset_ids: [] as number[],
})

const isEmployee = computed(() => viewMode.value === 'employee' || !canManage.value)

const filteredAssets = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return assets.value.filter((a) => {
    if (filterCategory.value && a.category !== filterCategory.value) return false
    if (filterStatus.value && a.status !== filterStatus.value) return false
    if (!q) return true
    return `${a.asset_no}${a.name}${a.model || ''}${a.holder_name || ''}`.toLowerCase().includes(q)
  })
})

const filteredBorrows = computed(() => {
  if (borrowFilter.value === 'all') return borrows.value
  if (borrowFilter.value === 'in_use') {
    return borrows.value.filter((x) => x.status === 'in_use' || x.status === 'approved')
  }
  return borrows.value.filter((x) => x.status === borrowFilter.value)
})

const availableAssets = computed(() => assets.value.filter((x) => x.status === 'available'))
const filteredBorrowAssets = computed(() => {
  const q = borrowAssetKeyword.value.trim().toLowerCase()
  return availableAssets.value.filter((a) => {
    if (borrowAssetCategory.value && a.category !== borrowAssetCategory.value) return false
    if (!q) return true
    return `${a.name}${a.model || ''}${a.asset_no}`.toLowerCase().includes(q)
  })
})
const selectedBorrowAssets = computed(() =>
  availableAssets.value.filter((a) => borrowForm.asset_ids.includes(a.id)),
)
const myBorrows = computed(() =>
  borrows.value.filter((x) => x.applicant_id === userStore.user?.id),
)
const myCounts = computed(() => ({
  inUse: myBorrows.value.filter((x) => ['in_use', 'approved'].includes(x.status)).length,
  pending: myBorrows.value.filter((x) => x.status === 'pending').length,
  pendingReturn: myBorrows.value.filter((x) => x.status === 'pending_return').length,
}))
const borrowCounts = computed(() => ({
  pending: borrows.value.filter((x) => x.status === 'pending').length,
  inUse: borrows.value.filter((x) => ['in_use', 'approved'].includes(x.status)).length,
  pendingReturn: borrows.value.filter((x) => x.status === 'pending_return').length,
}))

function money(v: number | string | null | undefined) {
  return Number(v || 0).toLocaleString()
}
function assetTag(status: string) {
  if (status === 'available') return 'success'
  if (status === 'maintenance') return 'danger'
  if (status === 'reserved' || status === 'pending_return') return 'warning'
  return 'info'
}
function borrowTag(status: string) {
  if (status === 'returned' || status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'pending' || status === 'pending_return') return 'warning'
  return 'info'
}
function alertDot(kind: string) {
  if (kind.includes('maintenance')) return kind === 'maintenance' ? 'bad' : 'warn'
  if (kind === 'return') return 'warn'
  return ''
}
function formatPeriod(row: BorrowRequest) {
  const s = row.start_time?.slice(5, 16).replace('T', ' ') || ''
  const e = row.end_time?.slice(11, 16) || ''
  return s ? `${s}—${e}` : '—'
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function focusAlerts() {
  if (alerts.value.length) {
    document.getElementById('asset-alerts')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } else {
    ElMessage.info('暂无待处理提醒')
  }
}
function goLedger(status?: string) {
  tab.value = 'ledger'
  filterStatus.value = status
  filterCategory.value = undefined
}
function goLedgerByCategory(category: string) {
  tab.value = 'ledger'
  filterCategory.value = category
  filterStatus.value = undefined
}
function goBorrow(filter: string) {
  tab.value = 'borrow'
  borrowFilter.value = filter
}

async function reload() {
  loading.value = true
  try {
    const { data } = await fetchAssetWorkbench()
    stats.value = data.stats
    assets.value = data.assets || []
    borrows.value = data.borrows || []
    inventory.value = data.inventory || null
    categoryUsage.value = data.category_usage || []
    alerts.value = data.alerts || []
    canManage.value = data.can_manage
    if (!data.can_manage) viewMode.value = 'employee'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await reload()
  applyRouteFocus()
})

function applyRouteFocus() {
  if (route.query.tab === 'borrow') {
    tab.value = 'borrow'
    if (!route.query.borrow_id) borrowFilter.value = 'pending'
  }
  const bid = Number(route.query.borrow_id)
  if (!bid) return
  const row = borrows.value.find((x) => x.id === bid)
  if (row) {
    tab.value = 'borrow'
    openBorrowDrawer(row)
  }
}

function openAssetDrawer(row: FixedAsset) {
  assetDrawer.value = row
  assetDrawerVisible.value = true
}
function openBorrowDrawer(row: BorrowRequest) {
  borrowDrawer.value = row
  borrowDrawerVisible.value = true
}
function onAlertClick(a: { asset_id?: number | null; request_id?: number | null }) {
  if (a.asset_id) {
    const row = assets.value.find((x) => x.id === a.asset_id)
    if (row) openAssetDrawer(row)
  } else if (a.request_id) {
    const row = borrows.value.find((x) => x.id === a.request_id)
    if (row) openBorrowDrawer(row)
  }
}

function openCreateAsset() {
  assetForm.name = ''
  assetForm.category = '相机'
  assetForm.model = ''
  assetForm.serial_no = ''
  assetForm.location = '新媒体器材柜 A1'
  assetForm.original_value = 10000
  createAssetVisible.value = true
}

async function submitCreateAsset() {
  if (!assetForm.name.trim()) {
    ElMessage.warning('请填写资产名称')
    return
  }
  acting.value = true
  try {
    const { data } = await createAsset({ ...assetForm, name: assetForm.name.trim() })
    createAssetVisible.value = false
    ElMessage.success(`已入库：${data.asset_no}`)
    await reload()
    tab.value = 'ledger'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '入库失败')
  } finally {
    acting.value = false
  }
}

function openCreateBorrow() {
  borrowForm.purpose = ''
  borrowForm.schedule_id = undefined
  borrowForm.schedule_ref = ''
  borrowForm.range = []
  borrowForm.asset_ids = []
  borrowAssetKeyword.value = ''
  borrowAssetCategory.value = undefined
  createBorrowVisible.value = true
  void searchSchedules('')
}

function borrowThisAsset(row: FixedAsset) {
  assetDrawerVisible.value = false
  openCreateBorrow()
  borrowForm.asset_ids = [row.id]
}

function toggleAsset(id: number, checked: boolean) {
  if (checked) {
    if (!borrowForm.asset_ids.includes(id)) borrowForm.asset_ids.push(id)
  } else {
    borrowForm.asset_ids = borrowForm.asset_ids.filter((x) => x !== id)
  }
}

function toPickerTime(iso?: string | null) {
  if (!iso) return ''
  return iso.length >= 19 ? iso.slice(0, 19) : iso
}

function scheduleOptionLabel(s: Schedule) {
  const when = s.start_time ? s.start_time.slice(5, 16).replace('T', ' ') : ''
  const proj = s.project_name ? ` · ${s.project_name}` : ''
  return `${s.title}${when ? `（${when}）` : ''}${proj}`
}

async function searchSchedules(q: string) {
  scheduleLoading.value = true
  try {
    const { data } = await fetchSchedules({
      page: 1,
      page_size: 50,
    })
    const kw = (q || '').trim().toLowerCase()
    const active = (data.items || []).filter((s) =>
      ['pending', 'confirmed', 'in_progress'].includes(String(s.status)),
    )
    scheduleOptions.value = kw
      ? active.filter((s) =>
          `${s.title}${s.project_name || ''}${s.project_no || ''}`.toLowerCase().includes(kw),
        )
      : active
  } catch {
    scheduleOptions.value = []
  } finally {
    scheduleLoading.value = false
  }
}

function onSchedulePicked(id?: number) {
  if (!id) {
    onScheduleCleared()
    return
  }
  const s = scheduleOptions.value.find((x) => x.id === id)
  if (!s) return
  borrowForm.schedule_ref = s.title
  const start = toPickerTime(s.start_time)
  const end = toPickerTime(s.end_time)
  if (start && end) borrowForm.range = [start, end]
  if (!borrowForm.purpose.trim()) {
    borrowForm.purpose = s.project_name ? `${s.project_name} · ${s.title}` : s.title
  }
}

function onScheduleCleared() {
  borrowForm.schedule_id = undefined
  borrowForm.schedule_ref = ''
}

async function submitCreateBorrow() {
  if (!borrowForm.purpose.trim()) {
    ElMessage.warning('请填写使用用途')
    return
  }
  if (borrowForm.range.length < 2) {
    ElMessage.warning('请选择借用时段')
    return
  }
  if (!borrowForm.asset_ids.length) {
    ElMessage.warning('请至少选择一件器材')
    return
  }
  acting.value = true
  try {
    await createBorrow({
      purpose: borrowForm.purpose.trim(),
      asset_ids: borrowForm.asset_ids,
      start_time: borrowForm.range[0],
      end_time: borrowForm.range[1],
      schedule_ref: borrowForm.schedule_ref || undefined,
    })
    createBorrowVisible.value = false
    ElMessage.success('借用申请已提交')
    if (canManage.value) {
      viewMode.value = 'admin'
      tab.value = 'borrow'
      borrowFilter.value = 'pending'
    }
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    acting.value = false
  }
}

async function onApprove() {
  if (!borrowDrawer.value) return
  acting.value = true
  try {
    await approveBorrow(borrowDrawer.value.id)
    ElMessage.success('已批准')
    borrowDrawerVisible.value = false
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '批准失败')
  } finally {
    acting.value = false
  }
}

async function onReject() {
  if (!borrowDrawer.value) return
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回申请', {
      inputPlaceholder: '驳回原因',
    })
    if (!value?.trim()) return
    acting.value = true
    await rejectBorrow(borrowDrawer.value.id, value.trim())
    ElMessage.success('已驳回')
    borrowDrawerVisible.value = false
    await reload()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '驳回失败')
  } finally {
    acting.value = false
  }
}

async function onCheckout() {
  if (!borrowDrawer.value) return
  acting.value = true
  try {
    await checkoutBorrow(borrowDrawer.value.id)
    ElMessage.success('已确认领用')
    borrowDrawerVisible.value = false
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '领用失败')
  } finally {
    acting.value = false
  }
}

async function onReturn() {
  if (!borrowDrawer.value) return
  acting.value = true
  try {
    await returnBorrow(borrowDrawer.value.id)
    ElMessage.success('已确认归还')
    borrowDrawerVisible.value = false
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '归还失败')
  } finally {
    acting.value = false
  }
}

function openScanner(mode?: string) {
  if (typeof mode === 'string' && mode) scanMode.value = mode
  scanResult.value = null
  scannerVisible.value = true
}

async function doScan() {
  acting.value = true
  try {
    const { data } = await scanAsset({ mode: scanMode.value })
    scanResult.value = { message: data.message, asset: data.asset }
    if (data.inventory) inventory.value = data.inventory
    ElMessage.success(data.message)
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '扫码失败')
  } finally {
    acting.value = false
  }
}
</script>
