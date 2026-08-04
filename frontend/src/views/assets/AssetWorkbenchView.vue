<template>
  <div class="crm-page asset-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-actions">
        <el-button @click="viewMode = viewMode === 'admin' ? 'employee' : 'admin'">
          {{ viewMode === 'admin' ? '管理员视角' : '员工视角' }} ⌄
        </el-button>
        <el-button v-if="viewMode === 'admin' && canManage" type="primary" @click="openCreateAsset">
          ＋ 设备入库
        </el-button>
        <el-button v-else type="primary" @click="openCreateBorrow">＋ 申请借用</el-button>
      </div>
    </header>

    <!-- 员工视角 -->
    <template v-if="viewMode === 'employee'">
      <section class="employee-asset-hero">
        <div>
          <small>普通员工视角</small>
          <h2>我的器材工作台</h2>
          <p>查询可借器材、处理本人借用与归还，不显示折旧和处置数据。</p>
        </div>
        <el-button type="primary" @click="openScanner">扫码领用 / 归还</el-button>
      </section>
      <section class="asset-mini-summary">
        <article>
          <small>我的使用中</small>
          <strong>{{ myCounts.inUse }}</strong>
          <span>含待归还验收</span>
        </article>
        <article>
          <small>待审批</small>
          <strong>{{ myCounts.pending }}</strong>
          <span>本人申请</span>
        </article>
        <article>
          <small>待归还</small>
          <strong>{{ myCounts.pendingReturn }}</strong>
          <span>请完成扫码归还</span>
        </article>
        <article>
          <small>可借器材</small>
          <strong>{{ stats?.available ?? 0 }}</strong>
          <span>覆盖 {{ categoryUsage.length }} 个分类</span>
        </article>
      </section>
      <article class="asset-panel">
        <div class="card-head">
          <div>
            <h2>我的申请与使用记录</h2>
            <p>仅展示当前登录人相关记录</p>
          </div>
          <el-button type="primary" @click="openCreateBorrow">＋ 申请借用</el-button>
        </div>
        <el-table :data="myBorrows" stripe @row-click="openBorrowDrawer">
          <el-table-column label="申请/用途" min-width="180">
            <template #default="{ row }">
              <b>{{ row.purpose }}</b>
              <div style="font-size: 12px; color: var(--crm-ink-soft)">{{ row.request_no }}</div>
            </template>
          </el-table-column>
          <el-table-column label="计划时间" min-width="180">
            <template #default="{ row }">{{ formatPeriod(row) }}</template>
          </el-table-column>
          <el-table-column label="器材" width="80">
            <template #default="{ row }">{{ row.asset_count }} 件</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="borrowTag(row.status)">
                {{ BORROW_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </article>
      <article class="asset-panel">
        <div class="card-head">
          <div>
            <h2>推荐可借器材</h2>
            <p>当前时段无占用冲突</p>
          </div>
        </div>
        <div class="available-assets">
          <button
            v-for="a in availableAssets"
            :key="a.id"
            type="button"
            @click="openAssetDrawer(a)"
          >
            <span>{{ a.category[0] }}</span>
            <b>{{ a.name }}</b>
            <small>{{ a.category }} · {{ a.location || '—' }}</small>
            <el-tag size="small" type="success">可申请</el-tag>
          </button>
        </div>
      </article>
    </template>

    <!-- 管理员视角 -->
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
        </button>
      </div>

      <!-- 总览 -->
      <template v-if="tab === 'overview'">
        <section class="asset-stat-grid">
          <article class="asset-stat">
            <span>资</span>
            <small>资产总数</small>
            <strong>{{ stats?.total ?? 0 }}</strong>
            <em>原值 ¥{{ money(stats?.original_value_sum) }}</em>
          </article>
          <article class="asset-stat">
            <span>用</span>
            <small>当前可用</small>
            <strong>{{ stats?.available ?? 0 }}</strong>
            <em>可用率 {{ stats?.available_rate ?? 0 }}%</em>
          </article>
          <article class="asset-stat">
            <span>借</span>
            <small>借出 / 预占</small>
            <strong>{{ stats?.borrowed_or_reserved ?? 0 }}</strong>
            <em>今日到期 {{ stats?.due_today ?? 0 }} 件</em>
          </article>
          <article class="asset-stat danger">
            <span>醒</span>
            <small>待处理提醒</small>
            <strong>{{ stats?.alerts ?? 0 }}</strong>
            <em>维保 {{ stats?.maintenance ?? 0 }} · 逾期 {{ stats?.overdue ?? 0 }}</em>
          </article>
        </section>
        <section class="asset-overview-grid">
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>器材使用态势</h2>
                <p>新媒体部门 · 最近30天</p>
              </div>
              <el-tag type="success" size="small">利用率 {{ stats?.utilization_rate ?? 0 }}%</el-tag>
            </div>
            <div class="asset-bars">
              <div v-for="c in categoryUsage" :key="c.category">
                <span><b>{{ c.category }}</b><small>{{ c.count }}件</small></span>
                <i><u :style="{ width: `${c.utilization}%` }" /></i>
                <strong>{{ c.utilization }}%</strong>
              </div>
            </div>
          </article>
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>今日提醒</h2>
                <p>按风险优先级排序</p>
              </div>
              <el-button link type="primary" @click="tab = 'inventory'">查看全部</el-button>
            </div>
            <div class="asset-alerts">
              <button
                v-for="(a, i) in alerts"
                :key="i"
                type="button"
                @click="onAlertClick(a)"
              >
                <i :class="alertDot(a.kind)" />
                <span>
                  <b>{{ a.title }}</b>
                  <small>{{ a.detail }}</small>
                </span>
                <em>{{ a.tag }}</em>
              </button>
              <div v-if="!alerts.length" style="color: var(--crm-ink-soft); font-size: 13px">暂无提醒</div>
            </div>
          </article>
        </section>
        <article class="asset-panel">
          <div class="card-head">
            <div>
              <h2>最近借用与使用记录</h2>
              <p>可追溯至人员、项目和拍摄档期</p>
            </div>
            <el-button @click="openScanner">移动端扫码</el-button>
          </div>
          <el-table :data="borrows.slice(0, 8)" stripe @row-click="openBorrowDrawer">
            <el-table-column label="申请/用途" min-width="180">
              <template #default="{ row }">
                <b>{{ row.purpose }}</b>
                <div style="font-size: 12px; color: var(--crm-ink-soft)">{{ row.request_no }}</div>
              </template>
            </el-table-column>
            <el-table-column label="使用人" width="100">
              <template #default="{ row }">{{ row.applicant_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="计划时间" min-width="170">
              <template #default="{ row }">{{ formatPeriod(row) }}</template>
            </el-table-column>
            <el-table-column label="器材" width="70">
              <template #default="{ row }">{{ row.asset_count }} 件</template>
            </el-table-column>
            <el-table-column label="关联档期" width="110">
              <template #default="{ row }">{{ row.schedule_ref || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="borrowTag(row.status)">
                  {{ BORROW_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </article>
      </template>

      <!-- 台账 -->
      <template v-else-if="tab === 'ledger'">
        <div class="asset-toolbar">
          <div class="filters">
            <el-input v-model="keyword" clearable placeholder="搜索编号/名称/型号" style="width: 220px" @keyup.enter="noop" />
            <el-select v-model="filterCategory" clearable placeholder="全部分类" style="width: 140px">
              <el-option v-for="c in ASSET_CATEGORY_OPTIONS" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="filterStatus" clearable placeholder="全部状态" style="width: 140px">
              <el-option
                v-for="(label, key) in ASSET_STATUS_LABEL"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </div>
          <el-button @click="openScanner">扫码查资产</el-button>
        </div>
        <article class="asset-panel">
          <el-table :data="filteredAssets" stripe @row-click="openAssetDrawer">
            <el-table-column label="资产" min-width="200">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <div style="font-size: 12px; color: var(--crm-ink-soft)">
                  {{ row.asset_no }} · {{ row.qr_code }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="分类/型号" width="140">
              <template #default="{ row }">
                {{ row.category }}
                <div style="font-size: 12px; color: var(--crm-ink-soft)">{{ row.model || '—' }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="assetTag(row.status)">
                  {{ ASSET_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="使用人" width="100">
              <template #default="{ row }">{{ row.holder_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="location" label="存放位置" min-width="140" />
            <el-table-column label="下次维保" width="120">
              <template #default="{ row }">{{ row.next_maintenance || '—' }}</template>
            </el-table-column>
            <el-table-column label="原值" width="110">
              <template #default="{ row }">
                <span class="money">¥{{ money(row.original_value) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </article>
      </template>

      <!-- 借用归还 -->
      <template v-else-if="tab === 'borrow'">
        <section class="asset-mini-summary">
          <article>
            <small>待我审批</small>
            <strong>{{ borrowCounts.pending }}</strong>
            <span>含拍摄档期关联</span>
          </article>
          <article>
            <small>使用中</small>
            <strong>{{ borrowCounts.inUse }}</strong>
            <span>今日到期 {{ stats?.due_today ?? 0 }} 项</span>
          </article>
          <article>
            <small>待归还验收</small>
            <strong>{{ borrowCounts.pendingReturn }}</strong>
            <span>需扫码核验</span>
          </article>
          <article>
            <small>本月按时归还</small>
            <strong>{{ stats?.on_time_return_rate ?? 0 }}%</strong>
            <span>逾期 {{ stats?.overdue ?? 0 }} 项</span>
          </article>
        </section>
        <div class="asset-toolbar">
          <el-radio-group v-model="borrowFilter" size="small">
            <el-radio-button value="all">全部记录</el-radio-button>
            <el-radio-button value="pending">待审批</el-radio-button>
            <el-radio-button value="in_use">使用中</el-radio-button>
            <el-radio-button value="pending_return">待归还</el-radio-button>
          </el-radio-group>
          <el-button type="primary" @click="openCreateBorrow">＋ 新建借用申请</el-button>
        </div>
        <article class="asset-panel">
          <el-table :data="filteredBorrows" stripe @row-click="openBorrowDrawer">
            <el-table-column label="申请/用途" min-width="180">
              <template #default="{ row }">
                <b>{{ row.purpose }}</b>
                <div style="font-size: 12px; color: var(--crm-ink-soft)">{{ row.request_no }}</div>
              </template>
            </el-table-column>
            <el-table-column label="使用人" width="100">
              <template #default="{ row }">{{ row.applicant_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="计划时间" min-width="170">
              <template #default="{ row }">{{ formatPeriod(row) }}</template>
            </el-table-column>
            <el-table-column label="器材" width="70">
              <template #default="{ row }">{{ row.asset_count }} 件</template>
            </el-table-column>
            <el-table-column label="关联档期" width="110">
              <template #default="{ row }">{{ row.schedule_ref || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="borrowTag(row.status)">
                  {{ BORROW_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </article>
      </template>

      <!-- 盘点维保 -->
      <template v-else-if="tab === 'inventory'">
        <section class="asset-overview-grid">
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>{{ inventory?.title || '本月器材盘点' }}</h2>
                <p>{{ inventory?.period_label || '—' }} · 器材室与使用人持有设备</p>
              </div>
              <el-tag type="info" size="small">进行中</el-tag>
            </div>
            <div class="inventory-progress">
              <strong>
                {{ inventory?.scanned_count ?? 0 }}
                <small>/ {{ inventory?.target_count ?? 0 }} 件已盘</small>
              </strong>
              <span><i :style="{ width: `${inventoryPercent}%` }" /></span>
              <em>{{ inventoryPercent }}%</em>
            </div>
            <div class="inventory-cells">
              <div>
                <small>账实一致</small>
                <b>{{ inventory?.matched_count ?? 0 }}</b>
              </div>
              <div>
                <small>状态异常</small>
                <b>{{ inventory?.anomaly_count ?? 0 }}</b>
              </div>
              <div>
                <small>待扫描</small>
                <b>{{ Math.max(0, (inventory?.target_count || 0) - (inventory?.scanned_count || 0)) }}</b>
              </div>
            </div>
            <el-button type="primary" style="width: 100%" @click="openScanner('inventory')">
              打开移动端扫码盘点
            </el-button>
          </article>
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>维保与库存预警</h2>
                <p>按计划日期与安全库存触发</p>
              </div>
              <el-tag type="warning" size="small">{{ alerts.length }}项待处理</el-tag>
            </div>
            <div class="asset-alerts">
              <button v-for="(a, i) in alerts" :key="i" type="button" @click="onAlertClick(a)">
                <i :class="alertDot(a.kind)" />
                <span>
                  <b>{{ a.title }}</b>
                  <small>{{ a.detail }}</small>
                </span>
                <em>{{ a.tag }}</em>
              </button>
            </div>
          </article>
        </section>
      </template>

      <!-- 折旧处置 -->
      <template v-else-if="tab === 'depreciation'">
        <section class="asset-rule-banner">
          <div>
            <small>当前折旧规则版本</small>
            <h2>固定资产直线法 · V2026.07</h2>
            <p>规则可配置；演示口径为使用年限5年、预计净残值率5%、按月计算。</p>
          </div>
          <el-button style="color: #fff; border-color: rgba(255, 255, 255, 0.35)">管理规则版本</el-button>
        </section>
        <article class="asset-panel">
          <div class="card-head">
            <div>
              <h2>本月折旧快照</h2>
              <p>历史快照不被新规则覆盖</p>
            </div>
            <el-tag type="warning" size="small">待复核</el-tag>
          </div>
          <el-table :data="assets.slice(0, 10)" stripe @row-click="openAssetDrawer">
            <el-table-column label="资产" min-width="180">
              <template #default="{ row }">
                <b>{{ row.name }}</b>
                <div style="font-size: 12px; color: var(--crm-ink-soft)">{{ row.asset_no }}</div>
              </template>
            </el-table-column>
            <el-table-column label="原值" width="110">
              <template #default="{ row }">¥{{ money(row.original_value) }}</template>
            </el-table-column>
            <el-table-column label="本月折旧" width="110">
              <template #default="{ row }">¥{{ money(row.monthly_depreciation) }}</template>
            </el-table-column>
            <el-table-column label="累计折旧" width="110">
              <template #default="{ row }">¥{{ money(row.accumulated_depreciation) }}</template>
            </el-table-column>
            <el-table-column label="当前净值" width="110">
              <template #default="{ row }">¥{{ money(row.net_value) }}</template>
            </el-table-column>
            <el-table-column label="处置状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'maintenance' ? 'warning' : 'success'">
                  {{ row.status === 'maintenance' ? '维修观察' : '正常' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </article>
      </template>

      <!-- 报表 -->
      <template v-else>
        <section class="asset-stat-grid">
          <article class="asset-stat">
            <small>资产原值</small>
            <strong>¥{{ moneyWan(stats?.original_value_sum) }}</strong>
            <em>净值 ¥{{ moneyWan(stats?.net_value_sum) }}</em>
          </article>
          <article class="asset-stat">
            <small>拍摄器材利用率</small>
            <strong>{{ stats?.utilization_rate ?? 0 }}%</strong>
            <em>近30天口径</em>
          </article>
          <article class="asset-stat">
            <small>按时归还率</small>
            <strong>{{ stats?.on_time_return_rate ?? 0 }}%</strong>
            <em>逾期 {{ stats?.overdue ?? 0 }} 项</em>
          </article>
          <article class="asset-stat">
            <small>维保成本</small>
            <strong>¥{{ money(stats?.maintenance_cost) }}</strong>
            <em>本季度</em>
          </article>
        </section>
        <section class="asset-overview-grid">
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>借用频次 TOP 5</h2>
                <p>按完成借用单统计</p>
              </div>
            </div>
            <div class="asset-bars">
              <div v-for="t in topBorrows" :key="t.asset_id">
                <span><b>{{ t.name }}</b><small>{{ t.count }}次</small></span>
                <i><u :style="{ width: `${t.score}%` }" /></i>
                <strong>{{ t.score }}%</strong>
              </div>
              <div v-if="!topBorrows.length" style="color: var(--crm-ink-soft); font-size: 13px">暂无统计</div>
            </div>
          </article>
          <article class="asset-panel" style="margin: 0">
            <div class="card-head">
              <div>
                <h2>运营风险分布</h2>
                <p>可下钻原始业务记录</p>
              </div>
            </div>
            <div class="report-donut">
              <div>
                <strong>{{ stats?.alerts ?? 0 }}</strong>
                <small>待处理</small>
              </div>
              <ul>
                <li><i class="warn" /><span>维保到期</span><b>{{ stats?.maintenance ?? 0 }}</b></li>
                <li><i class="bad" /><span>逾期未还</span><b>{{ stats?.overdue ?? 0 }}</b></li>
                <li><i /><span>库存不足</span><b>{{ Math.max(0, 3 - (stats?.available ?? 0)) }}</b></li>
                <li><i class="muted" /><span>盘点差异</span><b>{{ inventory?.anomaly_count ?? 0 }}</b></li>
              </ul>
            </div>
          </article>
        </section>
      </template>
    </template>

    <!-- 资产详情 -->
    <el-drawer v-model="assetDrawerVisible" :title="assetDrawer?.name || '资产详情'" size="460px" destroy-on-close>
      <template v-if="assetDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="assetTag(assetDrawer.status)">
            {{ ASSET_STATUS_LABEL[assetDrawer.status] || assetDrawer.status }}
          </el-tag>
          <span style="margin-left: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            {{ assetDrawer.asset_no }} · {{ assetDrawer.qr_code }}
          </span>
        </div>
        <div class="drawer-section">
          <h4>资产信息</h4>
          <div class="drawer-grid">
            <div><small>分类 / 型号</small><b>{{ assetDrawer.category }} · {{ assetDrawer.model || '—' }}</b></div>
            <div><small>当前使用人</small><b>{{ assetDrawer.holder_name || '—' }}</b></div>
            <div><small>存放位置</small><b>{{ assetDrawer.location || '—' }}</b></div>
            <div><small>资产原值</small><b>¥{{ money(assetDrawer.original_value) }}</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>当前用途</h4>
          <div class="drawer-grid">
            <div><small>使用用途</small><b>{{ assetDrawer.current_use || '—' }}</b></div>
            <div><small>关联拍摄档期</small><b>{{ assetDrawer.schedule_ref || '无' }}</b></div>
            <div><small>下次维保</small><b>{{ assetDrawer.next_maintenance || '—' }}</b></div>
            <div><small>净值</small><b>¥{{ money(assetDrawer.net_value) }}</b></div>
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- 借用详情 -->
    <el-drawer
      v-model="borrowDrawerVisible"
      :title="borrowDrawer?.request_no || '借用申请'"
      size="480px"
      destroy-on-close
    >
      <template v-if="borrowDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="borrowTag(borrowDrawer.status)">
            {{ BORROW_STATUS_LABEL[borrowDrawer.status] || borrowDrawer.status }}
          </el-tag>
          <span style="margin-left: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            {{ borrowDrawer.applicant_name }} · {{ formatPeriod(borrowDrawer) }}
          </span>
        </div>
        <div class="drawer-section">
          <h4>{{ borrowDrawer.purpose }}</h4>
          <div class="drawer-grid">
            <div><small>申请人</small><b>{{ borrowDrawer.applicant_name || '—' }}</b></div>
            <div><small>关联拍摄档期</small><b>{{ borrowDrawer.schedule_ref || '—' }}</b></div>
            <div><small>器材数量</small><b>{{ borrowDrawer.asset_count }} 件</b></div>
            <div><small>冲突校验</small><b>已通过</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>申请器材</h4>
          <div class="linked-assets">
            <div v-for="a in borrowDrawer.assets" :key="a.asset_id" class="linked-row">
              <span>{{ a.category[0] }}</span>
              <b>{{ a.name }}</b>
              <small>{{ a.asset_no }} · {{ ASSET_STATUS_LABEL[a.status] || a.status }}</small>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap">
          <template v-if="borrowDrawer.status === 'pending' && canManage">
            <el-button type="danger" :loading="acting" @click="onReject">驳回</el-button>
            <el-button type="primary" :loading="acting" @click="onApprove">批准并预占</el-button>
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
    <el-dialog v-model="createAssetVisible" title="设备登记入库" width="560px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="资产名称" required>
          <el-input v-model="assetForm.name" placeholder="例如：Sony FX3电影机" />
        </el-form-item>
        <el-form-item label="资产分类" required>
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
        <el-form-item label="资产原值">
          <el-input-number v-model="assetForm.original_value" :min="0" :step="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createAssetVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreateAsset">保存</el-button>
      </template>
    </el-dialog>

    <!-- 借用申请 -->
    <el-dialog v-model="createBorrowVisible" title="新建借用申请" width="580px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="使用用途" required>
          <el-input v-model="borrowForm.purpose" placeholder="说明拍摄或工作用途" />
        </el-form-item>
        <el-form-item label="关联拍摄档期">
          <el-input v-model="borrowForm.schedule_ref" placeholder="例如 PS-072904，可空" />
        </el-form-item>
        <el-form-item label="开始 / 归还时间" required>
          <el-date-picker
            v-model="borrowForm.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="选择器材" required>
          <div class="asset-choice-list">
            <label
              v-for="a in assets"
              :key="a.id"
              class="asset-choice"
              :class="{ disabled: a.status === 'maintenance' }"
            >
              <el-checkbox
                :model-value="borrowForm.asset_ids.includes(a.id)"
                :disabled="a.status === 'maintenance'"
                @change="(v: any) => toggleAsset(a.id, !!v)"
              />
              <span>{{ a.category[0] }}</span>
              <b>{{ a.name }}</b>
              <small>{{ ASSET_STATUS_LABEL[a.status] || a.status }}</small>
            </label>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createBorrowVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreateBorrow">提交审批</el-button>
      </template>
    </el-dialog>

    <!-- 扫码模拟 -->
    <el-dialog v-model="scannerVisible" title="移动端扫码" width="420px" destroy-on-close>
      <div class="phone-scanner">
        <div class="phone-status"><span>9:41</span><b>资产扫码</b><span>●●●</span></div>
        <div class="scan-mode">
          <button type="button" :class="{ active: scanMode === 'inventory' }" @click="scanMode = 'inventory'">
            盘点
          </button>
          <button type="button" :class="{ active: scanMode === 'checkout' }" @click="scanMode = 'checkout'">
            领用
          </button>
          <button type="button" :class="{ active: scanMode === 'return' }" @click="scanMode = 'return'">
            归还
          </button>
        </div>
        <div class="scan-view"><div>将设备二维码置于框内</div></div>
        <div class="scan-result">
          <small>{{ scanResult?.message || '当前任务' }}</small>
          <b>{{ scanResult?.asset?.name || inventory?.title || '器材盘点' }}</b>
          <span>
            {{
              scanResult?.asset
                ? `${scanResult.asset.asset_no} · ${ASSET_STATUS_LABEL[scanResult.asset.status] || ''}`
                : `已扫描 ${inventory?.scanned_count ?? 0} / ${inventory?.target_count ?? 0} 件`
            }}
          </span>
        </div>
        <el-button type="primary" style="width: 100%" :loading="acting" @click="doScan">
          模拟扫描二维码
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
import { useUserStore } from '@/stores/user'

type TabKey = 'overview' | 'ledger' | 'borrow' | 'inventory' | 'depreciation' | 'reports'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '资产总览' },
  { key: 'ledger', label: '资产台账' },
  { key: 'borrow', label: '借用归还' },
]

const userStore = useUserStore()
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
const topBorrows = ref<Array<{ asset_id: number; name: string; count: number; score: number }>>([])
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
const scanMode = ref('inventory')
const scanResult = ref<{ message: string; asset?: FixedAsset } | null>(null)

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
  schedule_ref: '',
  range: [] as string[],
  asset_ids: [] as number[],
})

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
const inventoryPercent = computed(() => {
  const t = inventory.value?.target_count || 0
  if (!t) return 0
  return Math.round(((inventory.value?.scanned_count || 0) * 100) / t)
})

function money(v: number | string | null | undefined) {
  return Number(v || 0).toLocaleString()
}
function moneyWan(v: number | string | null | undefined) {
  const n = Number(v || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return money(n)
}
function noop() {}
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
  return `${s}—${e}`
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
    topBorrows.value = data.top_borrows || []
    canManage.value = data.can_manage
    if (!data.can_manage) viewMode.value = 'employee'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(reload)

function openAssetDrawer(row: FixedAsset) {
  assetDrawer.value = row
  assetDrawerVisible.value = true
}

function openBorrowDrawer(row: BorrowRequest) {
  borrowDrawer.value = row
  borrowDrawerVisible.value = true
}

function onAlertClick(a: {
  asset_id?: number | null
  request_id?: number | null
}) {
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
    ElMessage.success(`设备已入库：${data.asset_no} / ${data.qr_code}`)
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
  borrowForm.schedule_ref = ''
  borrowForm.range = []
  borrowForm.asset_ids = availableAssets.value.slice(0, 1).map((x) => x.id)
  createBorrowVisible.value = true
}

function toggleAsset(id: number, checked: boolean) {
  if (checked) {
    if (!borrowForm.asset_ids.includes(id)) borrowForm.asset_ids.push(id)
  } else {
    borrowForm.asset_ids = borrowForm.asset_ids.filter((x) => x !== id)
  }
}

async function submitCreateBorrow() {
  if (!borrowForm.purpose.trim() || !borrowForm.asset_ids.length || borrowForm.range.length < 2) {
    ElMessage.warning('请完整填写用途、时间并选择器材')
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
    viewMode.value = 'admin'
    tab.value = 'borrow'
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
    ElMessage.success('已批准并预占器材')
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
  if (mode) scanMode.value = mode
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
