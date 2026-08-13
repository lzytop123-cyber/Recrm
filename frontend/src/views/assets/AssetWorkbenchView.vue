<template>
  <div class="crm-page asset-workbench crm-fit-page" v-loading="loading">
    <header class="asset-head">
      <div>
        <p class="wb-eyebrow">经营台</p>
        <h1>固定资产</h1>
        <p>{{ isEmployee ? '申请借用、查看本人记录与可借器材' : '管库存、审批借用；需要时再入库' }}</p>
      </div>
      <div class="asset-head-actions">
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
        <div v-if="availableSkuGroups.length" class="asset-chips">
          <button
            v-for="g in availableSkuGroups"
            :key="g.key"
            type="button"
            class="asset-chip"
            @click="openSkuRow(g)"
          >
            <b>{{ g.name }}<em v-if="g.qty > 1" class="qty-badge">×{{ g.qty }}</em></b>
            <small>{{ g.category }}{{ g.model ? ` · ${g.model}` : '' }}</small>
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
          <span class="muted">{{ ledgerCountText }}</span>
        </div>
        <section class="asset-panel crm-fit-panel">
          <div class="crm-table-wrap is-fit">
            <el-table
              :data="filteredSkuGroups"
              stripe
              empty-text="没有匹配的资产"
              height="100%"
              row-key="key"
              @row-click="onLedgerRowClick"
            >
              <el-table-column type="expand" width="40">
                <template #default="{ row }">
                  <div class="sku-units">
                    <button
                      v-for="u in row.units"
                      :key="u.id"
                      type="button"
                      class="sku-unit"
                      @click.stop="openAssetDrawer(u)"
                    >
                      <span>
                        <b>{{ u.asset_no }}</b>
                        <small>{{ u.serial_no || u.qr_code }}</small>
                      </span>
                      <el-tag size="small" :type="assetTag(u.status)">
                        {{ ASSET_STATUS_LABEL[u.status] || u.status }}
                      </el-tag>
                      <em>{{ u.holder_name || '—' }}</em>
                    </button>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="资产" min-width="180">
                <template #default="{ row }">
                  <b>{{ row.name }}</b>
                  <div class="muted">{{ row.model || '未填型号' }}</div>
                </template>
              </el-table-column>
              <el-table-column label="分类" width="90">
                <template #default="{ row }">{{ row.category }}</template>
              </el-table-column>
              <el-table-column label="数量" width="72" align="right">
                <template #default="{ row }">
                  <b class="qty-num">{{ row.qty }}</b>
                </template>
              </el-table-column>
              <el-table-column label="库存" min-width="160">
                <template #default="{ row }">
                  <span class="stock-pills">
                    <em class="ok">在库 {{ row.available }}</em>
                    <em v-if="row.occupied" class="out">占用 {{ row.occupied }}</em>
                    <em v-if="row.maintenance" class="bad">维保 {{ row.maintenance }}</em>
                    <em v-if="row.other" class="mute">其他 {{ row.other }}</em>
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="原值" width="120" align="right">
                <template #default="{ row }">
                  <span v-if="row.qty > 1">¥{{ money(row.original_value_sum) }}</span>
                  <span v-else>¥{{ money(row.original_value) }}</span>
                </template>
              </el-table-column>
              <el-table-column v-if="canManage" label="操作" width="72" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click.stop="openEditSku(row)">编辑</el-button>
                </template>
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
            <div><small>原值 / 净值</small><b>¥{{ money(assetDrawer.original_value) }} / ¥{{ money(assetDrawer.net_value) }}</b></div>
            <div><small>下次维保</small><b>{{ assetDrawer.next_maintenance || '—' }}</b></div>
            <div><small>关联档期</small><b>{{ assetDrawer.schedule_ref || '—' }}</b></div>
          </div>
        </div>
        <div class="drawer-actions">
          <el-button v-if="canManage" @click="openEditUnit(assetDrawer)">编辑资料</el-button>
          <el-button
            v-if="assetDrawer.status === 'available'"
            type="primary"
            @click="borrowThisAsset(assetDrawer)"
          >
            申请借用此器材
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 同型号库存 -->
    <el-drawer v-model="skuDrawerVisible" :title="skuDrawer?.name || '资产'" size="440px" destroy-on-close>
      <template v-if="skuDrawer">
        <div class="drawer-section">
          <el-tag size="small">{{ skuDrawer.category }}</el-tag>
          <span class="muted" style="margin-left: 8px">{{ skuDrawer.model || '未填型号' }} · {{ skuDrawer.qty }} 件</span>
        </div>
        <div class="drawer-section">
          <div class="drawer-grid">
            <div><small>在库 / 占用 / 维保</small><b>{{ skuDrawer.available }} / {{ skuDrawer.occupied }} / {{ skuDrawer.maintenance }}</b></div>
            <div><small>原值合计</small><b>¥{{ money(skuDrawer.original_value_sum) }}</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>实物编号</h4>
          <div class="sku-units is-drawer">
            <button
              v-for="u in skuDrawer.units"
              :key="u.id"
              type="button"
              class="sku-unit"
              @click="openAssetDrawer(u)"
            >
              <span>
                <b>{{ u.asset_no }}</b>
                <small>{{ u.serial_no || u.qr_code }}</small>
              </span>
              <el-tag size="small" :type="assetTag(u.status)">
                {{ ASSET_STATUS_LABEL[u.status] || u.status }}
              </el-tag>
              <em>{{ u.holder_name || '—' }}</em>
            </button>
          </div>
        </div>
        <div class="drawer-actions">
          <el-button v-if="canManage" @click="openEditSku(skuDrawer)">编辑本型号</el-button>
          <el-button
            v-if="skuDrawer.available > 0"
            type="primary"
            @click="borrowThisSku(skuDrawer)"
          >
            申请借用（可借 {{ skuDrawer.available }} 件）
          </el-button>
        </div>
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
            <div v-for="g in groupedBorrowDrawerItems" :key="g.name + g.category" class="linked-row">
              <b>{{ g.name }}<em v-if="g.items.length > 1" class="qty-badge">×{{ g.items.length }}</em></b>
              <small v-for="a in g.items" :key="a.asset_id">
                {{ a.asset_no }} · {{ ASSET_STATUS_LABEL[a.status] || a.status }}
              </small>
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

    <!-- 入库 / 编辑 -->
    <el-dialog
      v-model="createAssetVisible"
      :title="assetForm.mode === 'edit' ? '编辑资产' : '设备入库'"
      width="520px"
      destroy-on-close
    >
      <p class="borrow-hint">
        <template v-if="assetForm.mode === 'edit' && assetForm.applyToSku">
          将同步该型号资料；改数量会增加或减少在库件数。
        </template>
        <template v-else-if="assetForm.mode === 'edit'">
          可改资料和数量。数量调大会按此型号补入库，调小会删除多余在库件。
        </template>
        <template v-else>
          同型号多件填数量即可，台账合并为一行；每件仍有独立编号，可单独借还。
        </template>
      </p>
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
          <el-input v-model="assetForm.model" placeholder="用于合并同型号库存" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="assetForm.quantity" :min="1" :max="99" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="showSerialField" label="序列号">
          <el-input v-model="assetForm.serial_no" />
        </el-form-item>
        <el-form-item :label="assetForm.quantity > 1 ? '单价原值' : '原值'">
          <el-input-number v-model="assetForm.original_value" :min="0" :step="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createAssetVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitAssetForm">
          {{ assetSubmitLabel }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 借用申请 -->
    <el-dialog
      v-model="createBorrowVisible"
      title="申请借用"
      width="600px"
      destroy-on-close
      class="borrow-dialog"
      :fullscreen="isCompact"
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
            <!-- 手机用系统日期时间面板，避免 Element 双月面板超出屏幕 -->
            <div v-if="isCompact" class="borrow-range-native">
              <label class="borrow-range-field">
                <span>开始</span>
                <input
                  class="native-date-input"
                  type="datetime-local"
                  :value="toNativeDatetime(borrowForm.range[0])"
                  @input="onBorrowStartNative(($event.target as HTMLInputElement).value)"
                />
              </label>
              <label class="borrow-range-field">
                <span>归还</span>
                <input
                  class="native-date-input"
                  type="datetime-local"
                  :value="toNativeDatetime(borrowForm.range[1])"
                  :min="toNativeDatetime(borrowForm.range[0]) || undefined"
                  @input="onBorrowEndNative(($event.target as HTMLInputElement).value)"
                />
              </label>
            </div>
            <el-date-picker
              v-else
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
              placeholder="搜索器材名称 / 型号"
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
            <div
              v-for="g in filteredBorrowSkus"
              :key="g.key"
              class="asset-pick sku-pick"
              :class="{ selected: skuPickedQty(g) > 0 }"
              role="button"
              tabindex="0"
              @click="toggleSkuPick(g)"
              @keydown.enter.prevent="toggleSkuPick(g)"
            >
              <span class="asset-pick-body">
                <b>{{ g.name }}</b>
                <small>{{ g.category }}{{ g.model ? ` · ${g.model}` : '' }}</small>
              </span>
              <span class="sku-stock">可借 {{ g.available }}</span>
              <span class="qty-stepper" @click.stop>
                <button type="button" :disabled="skuPickedQty(g) <= 0" @click="setSkuQty(g, skuPickedQty(g) - 1)">−</button>
                <em>{{ skuPickedQty(g) }}</em>
                <button type="button" :disabled="skuPickedQty(g) >= g.available" @click="setSkuQty(g, skuPickedQty(g) + 1)">+</button>
              </span>
            </div>
            <div v-if="!filteredBorrowSkus.length" class="empty-hint">没有匹配的在库器材</div>
          </div>
          <div v-if="selectedBorrowSkus.length" class="selected-summary">
            已选：
            <el-tag
              v-for="g in selectedBorrowSkus"
              :key="g.key"
              size="small"
              closable
              style="margin: 2px 4px 2px 0"
              @close="setSkuQty(g, 0)"
            >
              {{ g.name }}{{ g.picked > 1 ? ` ×${g.picked}` : '' }}
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
  groupAssetsBySku,
  groupBorrowItems,
  rejectBorrow,
  returnBorrow,
  updateAsset,
  type AssetSkuGroup,
  type AssetStats,
  type BorrowRequest,
  type FixedAsset,
  type InventorySession,
} from '@/api/assets'
import { fetchSchedules, type Schedule } from '@/api/schedules'
import { useMatchMedia } from '@/composables/useMatchMedia'
import { useUserStore } from '@/stores/user'

const isCompact = useMatchMedia('(max-width: 768px)')

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
const skuDrawerVisible = ref(false)
const skuDrawer = ref<AssetSkuGroup | null>(null)
const borrowDrawerVisible = ref(false)
const borrowDrawer = ref<BorrowRequest | null>(null)
const createAssetVisible = ref(false)
const createBorrowVisible = ref(false)
const scheduleLoading = ref(false)
const scheduleOptions = ref<Schedule[]>([])
const borrowAssetKeyword = ref('')
const borrowAssetCategory = ref<string | undefined>()

const assetForm = reactive({
  mode: 'create' as 'create' | 'edit',
  applyToSku: false,
  assetId: null as number | null,
  skuQty: 1,
  name: '',
  category: '相机',
  model: '',
  serial_no: '',
  original_value: 10000,
  quantity: 1,
})

const borrowForm = reactive({
  purpose: '',
  schedule_id: undefined as number | undefined,
  schedule_ref: '',
  range: [] as string[],
  asset_ids: [] as number[],
})

const isEmployee = computed(() => viewMode.value === 'employee' || !canManage.value)
const showSerialField = computed(() => assetForm.quantity === 1)
const assetSubmitLabel = computed(() => {
  if (assetForm.mode === 'edit') {
    return assetForm.applyToSku && assetForm.skuQty > 1 ? `保存 ${assetForm.skuQty} 件` : '保存'
  }
  return assetForm.quantity > 1 ? `入库 ${assetForm.quantity} 件` : '保存'
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
const filteredSkuGroups = computed(() => groupAssetsBySku(filteredAssets.value))
const ledgerCountText = computed(() => {
  const kinds = filteredSkuGroups.value.length
  const pieces = filteredAssets.value.length
  if (!pieces) return '共 0 件'
  return kinds === pieces ? `共 ${pieces} 件` : `共 ${kinds} 种 · ${pieces} 件`
})
const groupedBorrowDrawerItems = computed(() => groupBorrowItems(borrowDrawer.value?.assets || []))

const filteredBorrows = computed(() => {
  if (borrowFilter.value === 'all') return borrows.value
  if (borrowFilter.value === 'in_use') {
    return borrows.value.filter((x) => x.status === 'in_use' || x.status === 'approved')
  }
  return borrows.value.filter((x) => x.status === borrowFilter.value)
})

const availableAssets = computed(() => assets.value.filter((x) => x.status === 'available'))
const availableSkuGroups = computed(() => groupAssetsBySku(availableAssets.value))
const filteredBorrowSkus = computed(() => {
  const q = borrowAssetKeyword.value.trim().toLowerCase()
  return availableSkuGroups.value.filter((g) => {
    if (borrowAssetCategory.value && g.category !== borrowAssetCategory.value) return false
    if (!q) return true
    const nos = g.units.map((u) => u.asset_no).join('')
    return `${g.name}${g.model}${g.category}${nos}`.toLowerCase().includes(q)
  })
})
const selectedBorrowSkus = computed(() =>
  availableSkuGroups.value
    .map((g) => ({ ...g, picked: skuPickedQty(g) }))
    .filter((g) => g.picked > 0),
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
function openSkuDrawer(row: AssetSkuGroup) {
  skuDrawer.value = row
  skuDrawerVisible.value = true
}
function openSkuRow(row: AssetSkuGroup) {
  if (row.qty === 1) openAssetDrawer(row.units[0])
  else openSkuDrawer(row)
}
function onLedgerRowClick(row: AssetSkuGroup, _col?: unknown, ev?: Event) {
  const t = ev?.target as HTMLElement | null
  if (t?.closest('.el-table__expand-icon, .sku-units, .el-button')) return
  openSkuRow(row)
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
  assetForm.mode = 'create'
  assetForm.applyToSku = false
  assetForm.assetId = null
  assetForm.skuQty = 1
  assetForm.name = ''
  assetForm.category = '相机'
  assetForm.model = ''
  assetForm.serial_no = ''
  assetForm.original_value = 10000
  assetForm.quantity = 1
  createAssetVisible.value = true
}

function fillAssetForm(row: FixedAsset, applyToSku: boolean, skuQty = 1) {
  assetForm.mode = 'edit'
  assetForm.applyToSku = applyToSku
  assetForm.assetId = row.id
  assetForm.skuQty = skuQty
  assetForm.name = row.name
  assetForm.category = row.category
  assetForm.model = row.model || ''
  assetForm.serial_no = row.serial_no || ''
  assetForm.original_value = Number(row.original_value || 0)
  assetForm.quantity = skuQty
  createAssetVisible.value = true
}

function openEditUnit(row: FixedAsset) {
  fillAssetForm(row, false, 1)
}

function openEditSku(row: AssetSkuGroup) {
  fillAssetForm(row.units[0], row.qty > 1, row.qty)
}

async function submitAssetForm() {
  if (!assetForm.name.trim()) {
    ElMessage.warning('请填写资产名称')
    return
  }
  acting.value = true
  try {
    if (assetForm.mode === 'edit') {
      if (!assetForm.assetId) return
      await updateAsset(assetForm.assetId, {
        name: assetForm.name.trim(),
        category: assetForm.category,
        model: assetForm.model.trim() || null,
        serial_no: assetForm.quantity === 1 ? (assetForm.serial_no.trim() || null) : undefined,
        original_value: assetForm.original_value,
        apply_to_same_model: assetForm.applyToSku,
        quantity: assetForm.quantity || 1,
      })
      createAssetVisible.value = false
      assetDrawerVisible.value = false
      skuDrawerVisible.value = false
      ElMessage.success(`已保存，当前 ${assetForm.quantity || 1} 件`)
      await reload()
      return
    }
    const qty = assetForm.quantity || 1
    await createAsset({
      name: assetForm.name.trim(),
      category: assetForm.category,
      model: assetForm.model,
      serial_no: qty === 1 ? assetForm.serial_no : undefined,
      original_value: assetForm.original_value,
      quantity: qty,
    })
    createAssetVisible.value = false
    ElMessage.success(qty > 1 ? `已入库 ${qty} 件，台账按型号合并` : '已入库')
    await reload()
    tab.value = 'ledger'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || (assetForm.mode === 'edit' ? '保存失败' : '入库失败'))
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
  skuDrawerVisible.value = false
  openCreateBorrow()
  borrowForm.asset_ids = [row.id]
}

function borrowThisSku(row: AssetSkuGroup) {
  skuDrawerVisible.value = false
  openCreateBorrow()
  const first = row.units.find((u) => u.status === 'available')
  borrowForm.asset_ids = first ? [first.id] : []
}

function skuPickedQty(g: AssetSkuGroup) {
  const ids = new Set(g.units.map((u) => u.id))
  return borrowForm.asset_ids.filter((id) => ids.has(id)).length
}

function setSkuQty(g: AssetSkuGroup, n: number) {
  const availableIds = g.units.filter((u) => u.status === 'available').map((u) => u.id)
  const next = Math.max(0, Math.min(n, availableIds.length))
  const picked = new Set(availableIds.slice(0, next))
  borrowForm.asset_ids = [
    ...borrowForm.asset_ids.filter((id) => !availableIds.includes(id)),
    ...availableIds.filter((id) => picked.has(id)),
  ]
}

function toggleSkuPick(g: AssetSkuGroup) {
  setSkuQty(g, skuPickedQty(g) > 0 ? 0 : 1)
}

function toPickerTime(iso?: string | null) {
  if (!iso) return ''
  return iso.length >= 19 ? iso.slice(0, 19) : iso
}

/** datetime-local 只需到分钟 */
function toNativeDatetime(iso?: string | null) {
  if (!iso) return ''
  return iso.length >= 16 ? iso.slice(0, 16) : iso
}

function fromNativeDatetime(v: string) {
  if (!v) return ''
  return v.length === 16 ? `${v}:00` : v
}

function onBorrowStartNative(v: string) {
  const start = fromNativeDatetime(v)
  const end = borrowForm.range[1] || ''
  borrowForm.range = start || end ? [start, end] : []
}

function onBorrowEndNative(v: string) {
  const start = borrowForm.range[0] || ''
  const end = fromNativeDatetime(v)
  borrowForm.range = start || end ? [start, end] : []
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
  if (!borrowForm.range[0] || !borrowForm.range[1]) {
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
</script>
