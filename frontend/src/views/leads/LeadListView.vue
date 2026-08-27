<template>
  <div class="crm-page leads-page" :class="{ embedded }">
    <!-- 线索总览：对齐原型 sales-permissions leadOverviewPanel -->
    <template v-if="embedded && pool === 'public'">
      <section class="allocation-summary">
        <button
          type="button"
          class="overview-card"
          :class="{ active: overviewQuick === 'all' }"
          @click="onOverviewClick('all')"
        >
          <small>全部线索</small>
          <strong>{{ overviewTotal }}</strong>
          <span>点击筛选全部</span>
        </button>
        <button
          type="button"
          class="overview-card"
          :class="{ active: overviewQuick === 'pending' }"
          @click="onOverviewClick('pending')"
        >
          <small>待分配</small>
          <strong>{{ stats?.public_pool ?? pageUnassignedCount }}</strong>
          <span>可勾选统一分配</span>
        </button>
        <button
          type="button"
          class="overview-card"
          :class="{ active: overviewQuick === 'owned' }"
          @click="onOverviewClick('owned')"
        >
          <small>已分配 / 跟进中</small>
          <strong>{{ overviewAssigned }}</strong>
          <span>按唯一主负责人统计</span>
        </button>
        <button
          type="button"
          class="overview-card"
          :class="{ active: overviewQuick === 'selected' }"
          @click="onOverviewClick('selected')"
        >
          <small>当前已勾选</small>
          <strong>{{ selectedIds.length }}</strong>
          <span>{{ selectedIds.length ? '可发起批量分配' : '仅待分配线索可勾选' }}</span>
        </button>
      </section>
    </template>

    <!-- 我的线索：对齐原型 quota-strip -->
    <template v-else-if="embedded && pool === 'mine'">
      <section class="sales-quota-strip">
        <div class="quota-item">
          <small>我的跟进中</small>
          <b>{{ stats?.following_mine ?? 0 }} 条</b>
        </div>
        <div class="quota-item">
          <small>保护中持有</small>
          <b>{{ quota?.protected_count ?? 0 }} / {{ quota?.protect_limit ?? 0 }}</b>
        </div>
        <div class="quota-item">
          <small>保护期将到期</small>
          <b>{{ stats?.protect_expiring ?? 0 }} 条</b>
        </div>
        <div class="quota-item">
          <small>本月已转化</small>
          <b>{{ stats?.converted_month ?? 0 }} 条</b>
        </div>
      </section>
    </template>

    <!-- 我录入：只看自己提交的线索，不套「我的线索」额度条 -->
    <template v-else-if="embedded && pool === 'created'">
      <section class="sales-quota-strip">
        <button
          type="button"
          class="quota-item is-button"
          :class="{ active: !status }"
          @click="onCreatedQuickFilter()"
        >
          <small>我录入</small>
          <b>{{ stats?.created ?? total }} 条</b>
        </button>
        <button
          type="button"
          class="quota-item is-button"
          :class="{ active: status === 'pending_assign' }"
          @click="onCreatedQuickFilter('pending_assign')"
        >
          <small>待分配</small>
          <b>{{ stats?.created_pending_assign ?? 0 }} 条</b>
        </button>
        <button
          type="button"
          class="quota-item is-button"
          :class="{ active: status === 'owned' }"
          @click="onCreatedQuickFilter('owned')"
        >
          <small>已分配 / 跟进中</small>
          <b>{{ (stats?.created_assigned ?? 0) + (stats?.created_following ?? 0) }} 条</b>
        </button>
        <button
          type="button"
          class="quota-item is-button"
          :class="{ active: status === 'converted' }"
          @click="onCreatedQuickFilter('converted')"
        >
          <small>已转化</small>
          <b>{{ stats?.created_converted ?? 0 }} 条</b>
        </button>
      </section>
    </template>

    <template v-else>
      <div class="crm-stats" :style="{ '--crm-stats-cols': String(statCards.length) }">
        <button
          v-for="item in statCards"
          :key="item.key"
          type="button"
          class="crm-stat-tile"
          :class="{ 'is-active': isStatActive(item) }"
          @click="onStatClick(item)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value ?? 0 }}</strong>
        </button>
      </div>

      <section v-if="quota && !canManagePool" class="crm-panel quota-strip">
        <div class="quota-item">
          <span>保护中持有</span>
          <strong>{{ quota.protected_count }} / {{ quota.protect_limit }}</strong>
        </div>
        <div class="quota-item">
          <span>保护期</span>
          <strong>{{ quota.protect_days }} 天</strong>
        </div>
        <div class="quota-item">
          <span>退回冷静期</span>
          <strong>{{ quota.cooldown_hours }} 小时</strong>
        </div>
        <div class="quota-item">
          <span>可见范围</span>
          <strong>仅我的线索</strong>
        </div>
      </section>
    </template>

    <section class="crm-panel" :class="{ 'allocation-panel': embedded && pool === 'public', 'crm-fit-panel': embedded }">
      <div
        class="toolbar"
        :class="{ 'allocation-toolbar': embedded && (pool === 'public' || pool === 'created' || pool === 'mine') }"
      >
        <div class="filters">
          <el-radio-group v-if="!embedded" v-model="pool" @change="onPoolChange">
            <el-radio-button v-if="canManagePool" value="public">线索总览</el-radio-button>
            <el-radio-button value="mine">我的</el-radio-button>
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="created">我录入</el-radio-button>
          </el-radio-group>
          <el-input
            v-model="keyword"
            :placeholder="
              embedded && pool === 'public'
                ? '搜索客户主体、需求、录入人或负责人'
                : '搜索姓名/公司/电话'
            "
            clearable
            style="width: 260px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-select
            v-if="embedded && pool === 'public'"
            v-model="status"
            clearable
            placeholder="全部状态"
            style="width: 130px"
            @change="onStatusFilterChange"
          >
            <el-option label="待分配" value="pending_assign" />
            <el-option label="已退回" value="returned" />
            <el-option label="已分配" value="assigned" />
            <el-option label="跟进中" value="following" />
            <el-option label="已转化" value="converted" />
            <el-option label="已流失" value="lost" />
          </el-select>
          <el-select
            v-if="embedded && pool === 'public'"
            v-model="businessType"
            clearable
            placeholder="全部业务类型"
            style="width: 150px"
            @change="reload"
          >
            <el-option
              v-for="opt in businessTypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-select
            v-if="!embedded || pool !== 'public'"
            v-model="status"
            clearable
            placeholder="状态"
            style="width: 140px"
            @change="reload"
          >
            <el-option
              v-for="(label, key) in LEAD_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-button v-if="!(embedded && pool === 'public')" @click="reload">查询</el-button>
        </div>
        <div class="toolbar-actions">
          <el-button
            v-if="canManagePool && pool === 'public'"
            type="primary"
            :disabled="!selectedIds.length"
            @click="openBatchAssign"
          >
            分配已选线索{{ selectedIds.length ? `（${selectedIds.length}）` : '' }}
          </el-button>
          <el-button v-if="!embedded" @click="importVisible = true">批量导入</el-button>
          <el-button v-if="!embedded" type="primary" @click="openCreate">录入线索</el-button>
        </div>
      </div>

      <div class="crm-table-wrap" :class="{ 'is-fit': embedded && !isCompact }">
      <el-table
        :data="items"
        v-loading="loading"
        stripe
        :height="embedded && !isCompact ? '100%' : undefined"
        :row-class-name="rowClassName"
        @row-click="goDetail"
        @selection-change="onSelectionChange"
      >
        <el-table-column
          v-if="canManagePool && pool === 'public'"
          type="selection"
          width="48"
          :selectable="(row) => isUnassigned(row)"
        />
        <el-table-column v-if="embedded" label="客户主体" min-width="200">
          <template #default="{ row }">
            <div class="entity">
              <span class="entity-icon">{{ entityIcon(row.company_name || row.name) }}</span>
              <span class="entity-text">
                <b>{{ row.company_name || row.name }}</b>
                <small>{{ leadCode(row) }}</small>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="embedded" prop="phone" label="联系电话" width="130" />
        <template v-else>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="联系人" width="100" />
          <el-table-column prop="company_name" label="公司" min-width="140" show-overflow-tooltip />
          <el-table-column prop="phone" label="电话" width="120" />
        </template>
        <el-table-column v-if="embedded" label="需求方向" width="120">
          <template #default="{ row }">{{ businessTypeLabel(row.business_type) }}</template>
        </el-table-column>
        <el-table-column v-if="embedded" label="录入来源" width="120">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column v-if="embedded && pool === 'mine'" prop="region" label="地区" width="100">
          <template #default="{ row }">{{ row.region || '待补充' }}</template>
        </el-table-column>
        <el-table-column v-if="!embedded" label="来源" width="100">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column
          v-if="embedded && pool === 'public'"
          prop="creator_name"
          label="录入人"
          width="100"
        />
        <el-table-column
          v-if="embedded && pool === 'public'"
          prop="owner_name"
          label="当前主负责人"
          width="120"
        >
          <template #default="{ row }">
            {{ isUnassigned(row) ? '尚未分配' : row.owner_name || '—' }}
          </template>
        </el-table-column>
        <el-table-column
          v-if="embedded && pool === 'mine'"
          prop="owner_name"
          label="负责人"
          width="100"
        />
        <el-table-column
          v-if="embedded && pool === 'created'"
          prop="owner_name"
          label="当前负责人"
          width="120"
        >
          <template #default="{ row }">
            {{ isUnassigned(row) ? '尚未分配' : row.owner_name || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">
              {{ LEAD_STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="embedded" label="最近更新" width="150">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column v-if="embedded" label="分级" width="90">
          <template #default="{ row }">
            <el-tag :type="gradeTag(row)" size="small" effect="plain">{{ gradeLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!embedded" prop="owner_name" label="跟进人" width="100" />
        <el-table-column v-if="!embedded" prop="creator_name" label="录入人" width="100" />
        <el-table-column v-if="!embedded" label="保护期" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_protected" type="warning" size="small">保护中</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="embedded" label="操作" :width="pool === 'public' ? 150 : 120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canEditLead(row)"
              size="small"
              link
              type="primary"
              @click.stop="openEdit(row)"
            >
              编辑
            </el-button>
            <template v-if="canManagePool && pool === 'public'">
              <el-button
                v-if="isUnassigned(row)"
                size="small"
                @click.stop="openBatchAssign([row.id])"
              >
                分配
              </el-button>
              <el-button v-else size="small" @click.stop="goDetail(row)">详情</el-button>
            </template>
            <el-button v-else size="small" @click.stop="goDetail(row)">详情</el-button>
          </template>
        </el-table-column>
        <el-table-column v-else label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button
              v-if="canEditLead(row)"
              link
              type="primary"
              @click.stop="openEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="canManagePool && isUnassigned(row)"
              link
              type="warning"
              @click.stop="openBatchAssign([row.id])"
            >
              分配
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <div v-if="embedded && pool === 'public'" class="table-footer">
        <span>共 {{ total }} 条线索 · 待分配 {{ pageUnassignedCount }} 条</span>
        <span>支持批量导入；所有操作保留录入人和负责人轨迹</span>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :layout="isCompact ? 'prev, pager, next' : 'total, prev, pager, next'"
          :pager-count="isCompact ? 5 : 7"
          @current-change="loadList"
          @size-change="loadList"
        />
      </div>
    </section>

    <el-dialog
      v-model="createVisible"
      :title="isEditMode ? '编辑线索' : '新增线索'"
      width="720px"
      destroy-on-close
      class="lead-create-dialog"
      @closed="editingLeadId = null"
    >
      <p class="dialog-eyebrow">{{ isEditMode ? '修改客户与需求信息' : '录入线索' }}</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="lead-create-form">
        <section class="form-block">
          <h3><span>1</span>客户信息</h3>
          <el-form-item label="客户主体" prop="company_name">
            <el-input v-model="form.company_name" placeholder="请输入企业或客户名称" @input="scheduleDupCheck" />
            <div class="field-hint">系统按主体名称、统一社会信用代码、手机号和企业域名组合自动查重。</div>
          </el-form-item>
          <div class="form-grid-2">
            <el-form-item label="统一社会信用代码">
              <el-input v-model="form.credit_code" placeholder="选填" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="企业域名">
              <el-input v-model="form.company_domain" placeholder="例如 example.com" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="联系人">
              <el-input v-model="form.name" placeholder="姓名" />
            </el-form-item>
            <el-form-item label="联系电话" prop="phone">
              <el-input v-model="form.phone" placeholder="手机号" @input="scheduleDupCheck" />
            </el-form-item>
            <el-form-item label="需求方向" prop="business_type">
              <el-select v-model="form.business_type" style="width: 100%">
                <el-option
                  v-for="opt in businessTypeOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="录入来源" prop="source">
              <el-select v-model="form.source" style="width: 100%">
                <el-option
                  v-for="opt in leadSourceOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="!isEditMode" label="录入人">
              <el-input :model-value="recorderName" disabled />
            </el-form-item>
          </div>
        </section>

        <section class="form-block">
          <h3><span>2</span>自动实时查重</h3>
          <div class="duplicate-result" :class="dupState">
            <span class="duplicate-mark">{{ dupMark }}</span>
            <div>
              <b>{{ dupTitle }}</b>
              <small>{{ dupDesc }}</small>
            </div>
          </div>
        </section>

        <section class="form-block">
          <h3><span>3</span>提交检查</h3>
          <div class="health-list">
            <div class="health-row">
              <span>{{ form.company_name.trim() ? '✓' : '⚠' }} 客户主体</span>
              <b>{{ form.company_name.trim() ? '已填写' : '待填写' }}</b>
            </div>
            <div class="health-row">
              <span>{{ form.phone.trim() ? '✓' : '⚠' }} 联系电话</span>
              <b>{{ form.phone.trim() ? '已填写' : '待填写' }}</b>
            </div>
            <div class="health-row">
              <span>{{ dupChecked ? '✓' : 'ⓘ' }} 自动查重</span>
              <b>{{ checkStatusText }}</b>
            </div>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!canSubmitLead" @click="onSubmitLead">
          {{ isEditMode ? '保存' : '提交线索' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchVisible" title="批量分配线索" width="640px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="已选线索">
          <div class="chip-wrap">
            <el-tag v-for="id in batchLeadIds" :key="id" class="chip">#{{ id }} · {{ leadTitle(id) }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="分配方式">
          <el-radio-group v-model="batchMethod">
            <el-radio-button value="average">平均分配</el-radio-button>
            <el-radio-button value="manual">逐条指定</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分配人" required>
          <el-select
            v-model="batchOwnerIds"
            multiple
            filterable
            style="width: 100%"
            placeholder="选择一名或多名员工"
            :loading="empLoading"
          >
            <el-option
              v-for="emp in employees"
              :key="emp.id"
              :label="`${emp.real_name || emp.username}${emp.department_name ? ' · ' + emp.department_name : ''}`"
              :value="emp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="batchMethod === 'manual'" label="逐条指定">
          <div class="manual-rows">
            <div v-for="id in batchLeadIds" :key="id" class="manual-row">
              <span>#{{ id }} {{ leadTitle(id) }}</span>
              <el-select v-model="manualOwnerMap[id]" placeholder="接收人" style="width: 200px">
                <el-option
                  v-for="oid in batchOwnerIds"
                  :key="oid"
                  :label="employeeLabel(oid)"
                  :value="oid"
                />
              </el-select>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-else label="预览">
          <div class="preview-rows">
            <div v-for="(row, idx) in averagePreview" :key="row.lead_id" class="preview-row">
              <span>#{{ row.lead_id }} {{ leadTitle(row.lead_id) }}</span>
              <i>→</i>
              <strong>{{ employeeLabel(row.owner_id) }}</strong>
              <small v-if="idx === 0">轮询起点</small>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="batchReason" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmBatchAssign">确认分配</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="drawerVisible"
      direction="rtl"
      :size="isCompact ? '100%' : '460px'"
      :with-header="false"
      class="lead-pool-drawer"
      destroy-on-close
    >
      <div v-loading="drawerLoading" class="drawer-inner">
        <div class="drawer-top">
          <div>
            <small class="drawer-eyebrow">{{ drawerEyebrow }}</small>
            <h2>{{ drawerLead?.company_name || drawerLead?.name || '线索详情' }}</h2>
          </div>
          <el-button text circle @click="drawerVisible = false">×</el-button>
        </div>

        <template v-if="drawerLead">
          <div class="detail-summary">
            <el-tag :type="drawerSummaryTag" size="small">{{ drawerSummaryLabel }}</el-tag>
            <small>
              {{ leadCode(drawerLead) }} ·
              {{ drawerIsUnassigned ? '仅管理层可见' : `来源：${sourceLabel(drawerLead.source)}` }}
            </small>
          </div>

          <section class="drawer-section">
            <SalesJourneyBar
              :lead-id="drawerLead.id"
              :sync-key="drawerLead.status"
              hide-self-lead
              @loaded="onDrawerJourneyLoaded"
            />
          </section>

          <section class="drawer-section">
            <h3>{{ drawerIsUnassigned ? '客户与需求' : '基本信息' }}</h3>
            <div class="detail-grid">
              <div class="detail-cell">
                <small>联系电话</small>
                <b>{{ drawerLead.phone || '—' }}</b>
              </div>
              <div class="detail-cell">
                <small>需求方向</small>
                <b>{{ businessTypeLabel(drawerLead.business_type) }}</b>
              </div>
              <div class="detail-cell">
                <small>录入来源</small>
                <b>{{ sourceLabel(drawerLead.source) }}{{ drawerLead.source_detail ? ` · ${drawerLead.source_detail}` : '' }}</b>
              </div>
              <div class="detail-cell">
                <small>客户地区</small>
                <b>{{ drawerLead.region || '待补充' }}</b>
              </div>
              <div v-if="drawerIsUnassigned" class="detail-cell">
                <small>录入人</small>
                <b>{{ drawerLead.creator_name || '-' }}</b>
              </div>
              <div class="detail-cell">
                <small>当前主负责人</small>
                <b>{{ drawerLead.owner_name || '尚未分配' }}</b>
              </div>
              <div class="detail-cell">
                <small>线索分级</small>
                <b>{{ gradeLabel(drawerLead) }}</b>
              </div>
              <div v-if="!drawerIsUnassigned" class="detail-cell">
                <small>保护期</small>
                <b>{{ protectRemainText(drawerLead) }}</b>
              </div>
              <div class="detail-cell">
                <small>查重结果</small>
                <b>无确定重复</b>
              </div>
            </div>
          </section>

          <section class="drawer-section">
            <div class="drawer-section-head">
              <h3>{{ drawerIsUnassigned ? '完整跟进与流转记录' : '操作轨迹' }}</h3>
              <el-radio-group
                v-if="drawerLogs.length"
                v-model="drawerLogFilter"
                size="small"
                class="drawer-log-filter"
              >
                <el-radio-button value="all">全部 {{ drawerLogs.length }}</el-radio-button>
                <el-radio-button value="flow">流转 {{ drawerFlowLogs.length }}</el-radio-button>
                <el-radio-button value="follow">跟进 {{ drawerFollowLogs.length }}</el-radio-button>
              </el-radio-group>
            </div>
            <el-timeline v-if="drawerTimelineLogs.length">
              <el-timeline-item
                v-for="log in drawerTimelineLogs"
                :key="log.id"
                :timestamp="formatTime(log.created_at)"
                placement="top"
                :type="log.action === 'follow' ? 'primary' : 'info'"
              >
                <div class="log-row">
                  <el-tag
                    size="small"
                    :type="log.action === 'follow' ? 'primary' : 'info'"
                    effect="plain"
                  >
                    {{ log.action === 'follow' ? '跟进' : '流转' }}
                  </el-tag>
                  <b>{{ logActionLabel(log.action) }}</b>
                </div>
                <small class="log-meta">
                  {{ log.username || '系统'
                  }}{{ log.detail ? ` · ${formatLogDetail(log.detail)}` : '' }}
                </small>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无轨迹" :image-size="56" />
          </section>
        </template>
      </div>

      <template #footer>
        <div class="drawer-footer" :class="{ 'drawer-footer-actions': !drawerIsUnassigned }">
          <template v-if="drawerIsUnassigned">
            <el-button @click="drawerVisible = false">关闭</el-button>
            <el-button
              v-if="drawerLead && canManagePool"
              type="primary"
              @click="allocateFromDrawer"
            >
              分配此线索
            </el-button>
          </template>
          <template v-else-if="drawerLead?.status === 'converted'">
            <el-button type="primary" @click="goConvertedOpportunity">查看商机</el-button>
            <el-button
              v-if="drawerLead.converted_customer_id"
              @click="goConvertedCustomer"
            >
              客户档案
            </el-button>
          </template>
          <template v-else>
            <el-button v-if="canManagePool" class="drawer-action-btn" @click="openDrawerTransfer">
              分配 / 转派
            </el-button>
            <el-button v-if="drawerCanWork" class="drawer-action-btn" @click="openDrawerFollow">
              新增跟进记录
            </el-button>
            <el-button v-if="drawerCanWork" class="drawer-action-btn" @click="openDrawerConvert">
              转客户与商机
            </el-button>
            <el-button
              v-if="drawerCanWork"
              class="drawer-action-btn drawer-action-danger"
              type="danger"
              plain
              @click="openDrawerReturn"
            >
              释放线索
            </el-button>
            <el-button v-if="!canManagePool && !drawerCanWork" @click="drawerVisible = false">
              关闭
            </el-button>
          </template>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="drawerFollowVisible" title="新增跟进记录" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="方式">
          <el-select v-model="drawerFollowForm.method" style="width: 100%">
            <el-option label="电话" value="phone" />
            <el-option label="微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="面谈" value="meeting" />
            <el-option label="会议" value="conference" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="drawerFollowForm.result" style="width: 100%">
            <el-option label="推进" value="advance" />
            <el-option label="保持" value="keep" />
            <el-option label="退回" value="return" />
            <el-option label="流失" value="lost" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <el-input v-model="drawerFollowForm.content" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerFollowVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDrawerFollow">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="drawerConvertVisible" title="转为客户与商机" width="520px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="客户名称">
          <el-input v-model="drawerConvertName" placeholder="默认用公司名或联系人" />
        </el-form-item>
        <el-form-item label="商机名称">
          <el-input v-model="drawerConvertOpp" placeholder="默认与客户名称相同" />
        </el-form-item>
        <el-form-item label="预计金额">
          <el-input-number v-model="drawerConvertAmount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerConvertVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDrawerConvert">确认转化</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="drawerReturnVisible" title="释放线索" width="480px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="原因类型" required>
          <el-select v-model="drawerReturnType" style="width: 100%" placeholder="请选择">
            <el-option
              v-for="opt in LEAD_RETURN_REASON_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input
            v-model="drawerReturnReason"
            type="textarea"
            :rows="3"
            placeholder="说明已完成的跟进和释放原因"
          />
        </el-form-item>
        <el-alert
          title="解除负责人关系后，线索将回到线索总览待分配池，历史记录完整保留。"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="drawerReturnVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="submitDrawerReturn">确认释放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="drawerTransferVisible" title="分配 / 转派" width="480px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="当前负责人">
          <span>{{ drawerLead?.owner_name || '尚未分配' }}</span>
        </el-form-item>
        <el-form-item label="新主负责人" required>
          <el-select
            v-model="drawerTransferOwnerId"
            filterable
            style="width: 100%"
            placeholder="选择员工"
            :loading="empLoading"
          >
            <el-option
              v-for="emp in employees"
              :key="emp.id"
              :label="`${emp.real_name || emp.username}${emp.department_name ? ' · ' + emp.department_name : ''}`"
              :value="emp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="变更原因" required>
          <el-input v-model="drawerTransferReason" type="textarea" :rows="3" placeholder="说明分配或转派依据" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerTransferVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDrawerTransfer">确认变更</el-button>
      </template>
    </el-dialog>

    <LeadImportDialog
      v-if="!embedded"
      v-model:visible="importVisible"
      :self-follow="canSelfFollowOnCreate"
      @done="onImportDone"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import { useUserStore } from '@/stores/user'
import { fetchDirectoryPeople, type DirectoryPerson } from '@/api/directory'
import SalesJourneyBar from '@/components/sales/SalesJourneyBar.vue'
import LeadImportDialog from '@/components/leads/LeadImportDialog.vue'
import type { SalesJourney } from '@/api/salesJourney'
import {
  LEAD_RETURN_REASON_OPTIONS,
  LEAD_STATUS_LABEL,
  batchAssignLeads,
  checkLeadDuplicates,
  convertLead,
  createFollowUp,
  createLead,
  fetchLeadDetail,
  fetchLeadQuota,
  fetchLeadStats,
  fetchLeads,
  returnLead,
  transferLead,
  updateLead,
  type Lead,
  type LeadDetail,
  type LeadQuota,
  type LeadStats,
} from '@/api/leads'
import { useBusinessTypes, useLeadSources } from '@/api/dictionaries'

const props = withDefaults(
  defineProps<{
    forcedPool?: string
    embedded?: boolean
    openCreateSignal?: number
  }>(),
  { embedded: false, openCreateSignal: 0 },
)

const router = useRouter()
const userStore = useUserStore()
const isCompact = useMatchMedia('(max-width: 768px)')
const canManagePool = computed(
  () => userStore.hasPermission('lead:manage') || userStore.hasPermission('*'),
)
/** 销售录入后直接自己跟进；管理层/其他岗仍进待分配池（与后端 can_self_follow_on_create 一致） */
const canSelfFollowOnCreate = computed(() =>
  (userStore.user?.roles ?? []).some(
    (r) => r.code === 'sales' || (r.name ?? '').includes('销售'),
  ),
)

const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()
const { leadSourceOptions, leadSourceLabel } = useLeadSources()

const loading = ref(false)
const saving = ref(false)
const empLoading = ref(false)
const importVisible = ref(false)
const items = ref<Lead[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const pool = ref(
  props.forcedPool || (canManagePool.value ? 'public' : 'mine'),
)
const status = ref<string | undefined>()
const keyword = ref('')
const businessType = ref<string | undefined>()
const gradeFilter = ref<string | undefined>()
const overviewQuick = ref<'all' | 'pending' | 'owned' | 'selected'>('all')
const stats = ref<LeadStats | null>(null)
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerLead = ref<LeadDetail | null>(null)
const drawerJourneyOppId = ref<number | null>(null)
const drawerLogFilter = ref<'all' | 'flow' | 'follow'>('all')
const drawerFollowVisible = ref(false)
const drawerConvertVisible = ref(false)
const drawerReturnVisible = ref(false)
const drawerTransferVisible = ref(false)
const drawerFollowForm = reactive({
  method: 'phone',
  result: 'advance',
  content: '',
})
const drawerConvertName = ref('')
const drawerConvertOpp = ref('')
const drawerConvertAmount = ref<number | undefined>()
const drawerReturnType = ref('')
const drawerReturnReason = ref('')
const drawerTransferOwnerId = ref<number | undefined>()
const drawerTransferReason = ref('')
const quota = ref<LeadQuota | null>(null)
const selectedIds = ref<number[]>([])

const createVisible = ref(false)
const editingLeadId = ref<number | null>(null)
const isEditMode = computed(() => editingLeadId.value != null)
const batchVisible = ref(false)
const batchLeadIds = ref<number[]>([])
const batchOwnerIds = ref<number[]>([])
const batchMethod = ref<'average' | 'manual'>('average')
const batchReason = ref('')
const manualOwnerMap = reactive<Record<number, number | undefined>>({})
const employees = ref<DirectoryPerson[]>([])
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  company_name: '',
  credit_code: '',
  company_domain: '',
  phone: '',
  business_type: 'ai_product',
  source: 'manual',
  need_desc: '',
  remark: '',
})
const rules: FormRules = {
  company_name: [{ required: true, message: '请填写客户主体', trigger: 'blur' }],
  phone: [{ required: true, message: '请填写联系电话', trigger: 'blur' }],
  business_type: [{ required: true, message: '请选择需求方向', trigger: 'change' }],
  source: [{ required: true, message: '请选择录入来源', trigger: 'change' }],
}

const dupChecking = ref(false)
const dupChecked = ref(false)
const dupReview = ref(false)
const dupHard = ref(false)
let dupTimer: ReturnType<typeof setTimeout> | null = null
let dupVersion = 0

const recorderName = computed(
  () => userStore.user?.real_name || userStore.user?.username || '当前用户',
)
const canSubmitLead = computed(
  () =>
    !!form.company_name.trim() &&
    !!form.phone.trim() &&
    !!form.business_type &&
    dupChecked.value &&
    !dupChecking.value,
)
const checkStatusText = computed(() => {
  if (dupChecking.value) return '正在自动查重'
  if (dupChecked.value) {
    if (dupHard.value) return '确定重复，需确认后强制提交'
    if (dupReview.value) return '疑似重复，转人工复核'
    return '未发现确定重复'
  }
  if (form.company_name.trim() && form.phone.trim()) return '等待自动查重'
  return '待填写'
})
const dupState = computed(() => {
  if (dupChecking.value) return 'checking'
  if (!dupChecked.value) return ''
  if (dupHard.value || dupReview.value) return 'review'
  return 'clear'
})
const dupMark = computed(() => {
  if (dupChecking.value) return '…'
  if (!dupChecked.value) return '查'
  if (dupHard.value || dupReview.value) return '审'
  return '✓'
})
const dupTitle = computed(() => {
  if (dupChecking.value) return '正在自动查重'
  if (!dupChecked.value) return '等待输入客户信息'
  if (dupHard.value) return '发现确定重复记录'
  if (dupReview.value) return '发现疑似重复记录'
  return '自动查重完成，未发现确定重复'
})
const dupDesc = computed(() => {
  if (dupChecking.value) return '正在比对客户主体、信用代码、手机号和企业域名。'
  if (!dupChecked.value) return '填写客户主体和联系电话后，系统自动执行查重。'
  if (dupHard.value) return '手机号或信用代码已存在；提交前需确认是否强制录入。'
  if (dupReview.value) return '不会自动合并；提交后写入操作记录并由管理层关注。'
  return '可以提交；本次查重条件和结果将写入操作记录。'
})

const statCards = computed(() => {
  const s = stats.value
  if (pool.value === 'created') {
    return [
      { key: 'created', label: '我录入', value: s?.created ?? 0, pool: 'created', status: undefined as string | undefined },
      { key: 'created_pending', label: '待分配', value: s?.created_pending_assign ?? 0, pool: 'created', status: 'pending_assign' },
      { key: 'created_assigned', label: '已分配', value: s?.created_assigned ?? 0, pool: 'created', status: 'assigned' },
      { key: 'created_following', label: '跟进中', value: s?.created_following ?? 0, pool: 'created', status: 'following' },
      { key: 'created_converted', label: '已转化', value: s?.created_converted ?? 0, pool: 'created', status: 'converted' },
    ]
  }
  const cards = [
    { key: 'mine', label: '我的', value: s?.mine ?? 0, pool: 'mine', status: undefined as string | undefined },
    { key: 'assigned', label: '已分配', value: s?.assigned ?? 0, pool: 'all', status: 'assigned' },
    { key: 'following', label: '跟进中', value: s?.following ?? 0, pool: 'all', status: 'following' },
    { key: 'converted', label: '已转化', value: s?.converted ?? 0, pool: 'all', status: 'converted' },
  ]
  if (canManagePool.value) {
    cards.unshift({
      key: 'public_pool',
      label: '待分配',
      value: s?.public_pool ?? 0,
      pool: 'public',
      status: undefined,
    })
  }
  return cards
})

const averagePreview = computed(() => {
  if (!batchOwnerIds.value.length) return []
  return batchLeadIds.value.map((lead_id, i) => ({
    lead_id,
    owner_id: batchOwnerIds.value[i % batchOwnerIds.value.length],
  }))
})

watch(batchOwnerIds, (ids) => {
  if (!ids.length) return
  for (const lid of batchLeadIds.value) {
    if (!manualOwnerMap[lid] || !ids.includes(manualOwnerMap[lid]!)) {
      manualOwnerMap[lid] = ids[0]
    }
  }
})

function sourceLabel(code?: string | null) {
  return leadSourceLabel(code)
}
function statusTag(s: string) {
  const map: Record<string, string> = {
    pending_assign: 'warning',
    assigned: 'success',
    following: 'success',
    converted: 'success',
    returned: 'warning',
    lost: 'danger',
  }
  return map[s] || 'info'
}
function isUnassigned(row: Lead) {
  return row.status === 'pending_assign' || row.status === 'returned'
}

function canEditLead(row: Lead) {
  return row.status !== 'converted'
}

const pageUnassignedCount = computed(
  () => items.value.filter((row) => isUnassigned(row)).length,
)
const overviewTotal = computed(() => stats.value?.total ?? total.value)
const overviewAssigned = computed(
  () => (stats.value?.assigned ?? 0) + (stats.value?.following ?? 0),
)
function leadTitle(id: number) {
  const row = items.value.find((x) => x.id === id)
  return row?.company_name || row?.name || ''
}
function employeeLabel(id: number) {
  const emp = employees.value.find((x) => x.id === id)
  return emp ? emp.real_name || emp.username : String(id)
}
function entityIcon(name?: string | null) {
  const text = (name || '客').trim()
  return text[0]
}
function leadCode(row: Lead) {
  return `XS-${String(row.id).padStart(6, '0')}`
}
function formatTime(v?: string | null) {
  if (!v) return '-'
  return new Date(v).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
function gradeLabel(row: Lead) {
  return row.business_type === 'ai_custom' ? '重点' : '普通'
}
function gradeTag(row: Lead) {
  return row.business_type === 'ai_custom' ? 'warning' : 'info'
}
function rowClassName({ row }: { row: Lead }) {
  if (pool.value === 'public' && selectedIds.value.includes(row.id)) return 'selected-row'
  return ''
}

function onPoolChange() {
  status.value = undefined
  page.value = 1
  reload()
}

function onCreatedQuickFilter(next?: string) {
  status.value = next
  page.value = 1
  reload()
}

function onStatClick(item: { pool?: string; status?: string }) {
  if (!props.embedded && item.pool) pool.value = item.pool
  status.value = item.status
  page.value = 1
  reload()
}

function isStatActive(item: { pool?: string; status?: string }) {
  const samePool = !item.pool || item.pool === pool.value
  return samePool && (item.status || '') === (status.value || '')
}

function resolveListStatus(): string | undefined {
  if (status.value) return status.value
  if (!(props.embedded && pool.value === 'public')) return undefined
  if (overviewQuick.value === 'pending') return 'unassigned'
  if (overviewQuick.value === 'owned') return 'owned'
  return undefined
}

function onOverviewClick(key: 'all' | 'pending' | 'owned' | 'selected') {
  if (key === 'selected') {
    overviewQuick.value = 'selected'
    if (!selectedIds.value.length) {
      ElMessage.info('请先勾选待分配线索')
      return
    }
    openBatchAssign()
    return
  }
  overviewQuick.value = key
  status.value = undefined
  page.value = 1
  reload()
}

function onStatusFilterChange() {
  if (!status.value) overviewQuick.value = 'all'
  else if (status.value === 'pending_assign' || status.value === 'returned') {
    overviewQuick.value = 'pending'
  } else if (status.value === 'assigned' || status.value === 'following') {
    overviewQuick.value = 'owned'
  } else {
    overviewQuick.value = 'all'
  }
  reload()
}

function onSelectionChange(rows: Lead[]) {
  selectedIds.value = rows.map((x) => x.id)
}

async function loadStats() {
  const { data } = await fetchLeadStats()
  stats.value = data
}
async function loadQuota() {
  const { data } = await fetchLeadQuota()
  quota.value = data
}
async function loadList() {
  loading.value = true
  try {
    const { data } = await fetchLeads({
      pool: pool.value,
      status: resolveListStatus(),
      keyword: keyword.value || undefined,
      business_type: businessType.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    let rows = data.items
    if (gradeFilter.value) {
      rows = rows.filter((row) => gradeLabel(row) === gradeFilter.value)
    }
    items.value = rows
    total.value = data.total
    selectedIds.value = []
  } finally {
    loading.value = false
  }
}

function onImportDone() {
  void loadList()
  void loadStats()
}function reload() {
  page.value = 1
  loadList()
  loadStats()
  loadQuota()
}

const drawerLogs = computed(() => drawerLead.value?.logs || [])
const drawerFlowLogs = computed(() => drawerLogs.value.filter((l) => l.action !== 'follow'))
const drawerFollowLogs = computed(() => drawerLogs.value.filter((l) => l.action === 'follow'))
const drawerTimelineLogs = computed(() => {
  const list =
    drawerLogFilter.value === 'follow'
      ? drawerFollowLogs.value
      : drawerLogFilter.value === 'flow'
        ? drawerFlowLogs.value
        : drawerLogs.value
  return [...list].sort((a, b) => {
    const ta = new Date(a.created_at).getTime()
    const tb = new Date(b.created_at).getTime()
    if (tb !== ta) return tb - ta
    return (b.id || 0) - (a.id || 0)
  })
})
const drawerIsUnassigned = computed(
  () => !!drawerLead.value && isUnassigned(drawerLead.value),
)
const drawerEyebrow = computed(() => (drawerIsUnassigned.value ? '待分配线索' : '线索详情'))
const drawerSummaryLabel = computed(() => {
  const lead = drawerLead.value
  if (!lead) return ''
  if (lead.status === 'converted') return '已转商机'
  if (lead.is_protected) return '保护中'
  return LEAD_STATUS_LABEL[lead.status] || lead.status
})
const drawerSummaryTag = computed(() => {
  const lead = drawerLead.value
  if (!lead) return 'info'
  if (lead.status === 'converted') return 'success'
  if (lead.is_protected || drawerIsUnassigned.value) return 'warning'
  return statusTag(lead.status)
})
const drawerCanWork = computed(() => {
  const lead = drawerLead.value
  if (!lead) return false
  if (['converted', 'lost', 'pending_assign', 'returned'].includes(String(lead.status))) {
    return false
  }
  return lead.owner_id === userStore.user?.id
})

function protectRemainText(lead: Lead) {
  if (!lead.protect_until) return lead.is_protected ? '保护中' : '无保护期'
  const end = new Date(lead.protect_until).getTime()
  if (Number.isNaN(end)) return '—'
  const days = Math.max(0, Math.ceil((end - Date.now()) / 86400000))
  return days > 0 ? `剩余 ${days} 天` : '已到期'
}

async function openPoolDrawer(row: Lead) {
  drawerVisible.value = true
  drawerLoading.value = true
  drawerLead.value = null
  drawerJourneyOppId.value = null
  drawerLogFilter.value = 'all'
  try {
    const { data } = await fetchLeadDetail(row.id)
    drawerLead.value = data
  } catch {
    drawerLead.value = row as LeadDetail
  } finally {
    drawerLoading.value = false
  }
}

function goDetail(row: Lead) {
  if (props.embedded) {
    void openPoolDrawer(row)
    return
  }
  router.push(`/leads/${row.id}`)
}

function allocateFromDrawer() {
  if (!drawerLead.value) return
  const id = drawerLead.value.id
  drawerVisible.value = false
  openBatchAssign([id])
}

function onDrawerJourneyLoaded(journey: SalesJourney) {
  drawerJourneyOppId.value = journey.links.opportunity_id ?? null
  if (
    drawerLead.value &&
    journey.links.opportunity_id &&
    !drawerLead.value.converted_opportunity_id
  ) {
    drawerLead.value.converted_opportunity_id = journey.links.opportunity_id
  }
}

function goConvertedOpportunity() {
  const oid =
    drawerLead.value?.converted_opportunity_id ||
    drawerJourneyOppId.value ||
    null
  const cid = drawerLead.value?.converted_customer_id
  drawerVisible.value = false
  if (oid) router.push(`/opportunities/${oid}`)
  else if (cid) router.push(`/customers/${cid}`)
  else router.push({ path: '/sales', query: { tab: 'opportunities' } })
}

function goConvertedCustomer() {
  const cid = drawerLead.value?.converted_customer_id
  drawerVisible.value = false
  if (cid) router.push(`/customers/${cid}`)
  else router.push({ path: '/sales', query: { tab: 'customers' } })
}

function openDrawerFollow() {
  drawerFollowForm.method = 'phone'
  drawerFollowForm.result = 'advance'
  drawerFollowForm.content = ''
  drawerFollowVisible.value = true
}

function openDrawerConvert() {
  const lead = drawerLead.value
  drawerConvertName.value = lead?.company_name || lead?.name || ''
  drawerConvertOpp.value = `${drawerConvertName.value} · ${businessTypeLabel(lead?.business_type)}`
  drawerConvertAmount.value = undefined
  drawerConvertVisible.value = true
}

function openDrawerReturn() {
  drawerReturnType.value = ''
  drawerReturnReason.value = ''
  drawerReturnVisible.value = true
}

async function openDrawerTransfer() {
  drawerTransferOwnerId.value = undefined
  drawerTransferReason.value = ''
  drawerTransferVisible.value = true
  if (!employees.value.length) {
    empLoading.value = true
    try {
      const { data } = await fetchDirectoryPeople({ page: 1, page_size: 100, is_active: true })
      employees.value = data.items || []
    } finally {
      empLoading.value = false
    }
  }
}

async function submitDrawerFollow() {
  if (!drawerLead.value) return
  if (!drawerFollowForm.content.trim()) {
    ElMessage.warning('请填写沟通内容')
    return
  }
  saving.value = true
  try {
    await createFollowUp(drawerLead.value.id, {
      method: drawerFollowForm.method,
      result: drawerFollowForm.result,
      content: drawerFollowForm.content.trim(),
    })
    ElMessage.success('跟进已记录')
    drawerFollowVisible.value = false
    await openPoolDrawer(drawerLead.value)
    reload()
  } finally {
    saving.value = false
  }
}

async function submitDrawerConvert() {
  if (!drawerLead.value) return
  saving.value = true
  try {
    const { data } = await convertLead(drawerLead.value.id, {
      customer_name: drawerConvertName.value || undefined,
      opportunity_title: drawerConvertOpp.value || undefined,
      expected_amount: drawerConvertAmount.value,
    })
    ElMessage.success('已转为客户与商机')
    drawerConvertVisible.value = false
    drawerVisible.value = false
    if (data.opportunity_id) {
      router.push({ path: '/sales', query: { tab: 'opportunities' } })
    } else if (data.customer_id) {
      router.push(`/customers/${data.customer_id}`)
    } else {
      reload()
    }
  } finally {
    saving.value = false
  }
}

async function submitDrawerReturn() {
  if (!drawerLead.value) return
  if (!drawerReturnType.value || !drawerReturnReason.value.trim()) {
    ElMessage.warning('请填写释放原因')
    return
  }
  saving.value = true
  try {
    await returnLead(drawerLead.value.id, {
      reason_type: drawerReturnType.value,
      reason: drawerReturnReason.value.trim(),
    })
    ElMessage.success('线索已释放，已回到待分配池')
    drawerReturnVisible.value = false
    drawerVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

async function submitDrawerTransfer() {
  if (!drawerLead.value || !drawerTransferOwnerId.value) {
    ElMessage.warning('请选择新主负责人')
    return
  }
  if (!drawerTransferReason.value.trim()) {
    ElMessage.warning('请填写变更原因')
    return
  }
  saving.value = true
  try {
    await transferLead(
      drawerLead.value.id,
      drawerTransferOwnerId.value,
      drawerTransferReason.value.trim(),
    )
    ElMessage.success('已完成转派')
    drawerTransferVisible.value = false
    drawerVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

function logActionLabel(action: string) {
  const map: Record<string, string> = {
    create: '员工录入线索',
    assign: '管理层分配线索',
    claim: '领取线索',
    follow: '跟进记录',
    transfer: '转移线索',
    return: '退回待分配池',
    convert: '转化为客户与商机',
    lost: '标记流失',
    edit: '编辑线索',
  }
  return map[action] || action
}

/** 历史轨迹里残留的英文码转中文展示 */
function formatLogDetail(detail: string) {
  if (!detail) return ''
  const methodMap: Record<string, string> = {
    phone: '电话',
    wechat: '微信',
    email: '邮件',
    meeting: '面谈',
    conference: '会议',
  }
  const resultMap: Record<string, string> = {
    advance: '推进',
    keep: '保持',
    return: '退回',
    lost: '流失',
  }
  let text = detail
  text = text.replace(/\b(phone|wechat|email|meeting|conference)\b/g, (m) => methodMap[m] || m)
  text = text.replace(/\b(advance|keep|return|lost)\b/g, (m) => resultMap[m] || m)
  text = text.replace(/方式=manual/g, '方式=逐条指定')
  text = text.replace(/方式=average/g, '方式=平均分配')
  text = text.replace(/(\S+)\/(\S+):\s*/g, '$1/$2：')
  return text
}
function resetLeadForm() {
  form.name = ''
  form.company_name = ''
  form.credit_code = ''
  form.company_domain = ''
  form.phone = ''
  form.business_type = 'ai_product'
  form.source = 'manual'
  form.need_desc = ''
  form.remark = ''
  dupChecking.value = false
  dupChecked.value = false
  dupReview.value = false
  dupHard.value = false
}

function fillLeadForm(lead: Lead) {
  form.name = lead.name || ''
  form.company_name = lead.company_name || ''
  form.credit_code = lead.credit_code || ''
  form.company_domain = lead.company_domain || ''
  form.phone = lead.phone || ''
  form.business_type = lead.business_type || 'ai_product'
  form.source = lead.source || 'manual'
  form.need_desc = lead.need_desc || ''
  form.remark = lead.remark || ''
}

function openCreate() {
  editingLeadId.value = null
  resetLeadForm()
  createVisible.value = true
}

async function openEdit(row: Lead) {
  if (!canEditLead(row)) {
    ElMessage.warning('已转化线索不可编辑')
    return
  }
  editingLeadId.value = row.id
  fillLeadForm(row)
  dupChecking.value = false
  dupChecked.value = false
  dupReview.value = false
  dupHard.value = false
  createVisible.value = true
  try {
    const { data } = await fetchLeadDetail(row.id)
    fillLeadForm(data)
  } catch {
    /* 列表字段足够时忽略 */
  }
  scheduleDupCheck()
}

function scheduleDupCheck() {
  if (dupTimer) clearTimeout(dupTimer)
  dupVersion += 1
  dupChecked.value = false
  dupReview.value = false
  dupHard.value = false
  const ready = !!form.company_name.trim() && !!form.phone.trim()
  if (!ready) {
    dupChecking.value = false
    return
  }
  dupChecking.value = true
  const version = dupVersion
  dupTimer = setTimeout(() => {
    void runDupCheck(version)
  }, 450)
}

async function runDupCheck(version: number) {
  try {
    const { data } = await checkLeadDuplicates({
      phone: form.phone.trim() || undefined,
      company_name: form.company_name.trim() || undefined,
      credit_code: form.credit_code.trim() || undefined,
      company_domain: form.company_domain.trim() || undefined,
    })
    if (version !== dupVersion) return
    const selfId = editingLeadId.value
    const byPhone = selfId ? data.by_phone.filter((x) => x.id !== selfId) : data.by_phone
    const byCredit = selfId ? data.by_credit.filter((x) => x.id !== selfId) : data.by_credit
    const byCompany = selfId ? data.by_company.filter((x) => x.id !== selfId) : data.by_company
    const byDomain = selfId ? data.by_domain.filter((x) => x.id !== selfId) : data.by_domain
    dupChecked.value = true
    dupHard.value = !!(byPhone.length || byCredit.length)
    dupReview.value = !!(byCompany.length || byDomain.length) && !dupHard.value
  } catch {
    if (version !== dupVersion) return
    dupChecked.value = true
    dupHard.value = false
    dupReview.value = false
  } finally {
    if (version === dupVersion) dupChecking.value = false
  }
}

async function onSubmitLead() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !canSubmitLead.value) return
  saving.value = true
  try {
    const payload = {
      name: form.name.trim() || undefined,
      company_name: form.company_name.trim(),
      credit_code: form.credit_code.trim() || undefined,
      company_domain: form.company_domain.trim() || undefined,
      phone: form.phone.trim(),
      business_type: form.business_type,
      source: form.source,
      need_desc: form.need_desc || undefined,
      remark: form.remark || undefined,
    }
    if (isEditMode.value && editingLeadId.value) {
      if (dupHard.value) {
        ElMessage.error('联系电话与其他线索冲突，请修改后再保存')
        return
      }
      const { data } = await updateLead(editingLeadId.value, payload)
      ElMessage.success('线索已更新')
      createVisible.value = false
      editingLeadId.value = null
      if (drawerLead.value?.id === data.id) {
        drawerLead.value = { ...drawerLead.value, ...data }
      }
      await loadList()
      return
    }
    const createPayload = { ...payload, self_follow: canSelfFollowOnCreate.value }
    const successMsg = canSelfFollowOnCreate.value
      ? '录入成功，已进入我的线索，可直接跟进'
      : '录入成功，已进入管理层待分配池'
    if (dupHard.value) {
      await ElMessageBox.confirm(
        '存在确定重复线索。确认强制录入？不会自动合并已有记录。',
        '重复提示',
        { type: 'warning' },
      )
      await createLead(createPayload, true)
      ElMessage.success(
        canSelfFollowOnCreate.value ? '已强制录入并进入我的线索' : '已强制录入，查重结果已留痕',
      )
    } else if (dupReview.value) {
      await createLead(createPayload)
      ElMessage.success(
        canSelfFollowOnCreate.value
          ? '已提交并进入我的线索；疑似重复已写入操作记录'
          : '已提交；疑似重复已写入操作记录，未发生强制合并',
      )
    } else {
      await createLead(createPayload)
      ElMessage.success(successMsg)
    }
    createVisible.value = false
    if (!props.forcedPool) {
      pool.value = canSelfFollowOnCreate.value
        ? 'mine'
        : canManagePool.value
          ? 'public'
          : 'created'
    }
    reload()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      try {
        await ElMessageBox.confirm(err.response.data?.detail || '存在重复，是否强制创建？', '重复提示', {
          type: 'warning',
        })
        await createLead(
          {
            name: form.name.trim() || undefined,
            company_name: form.company_name.trim(),
            credit_code: form.credit_code.trim() || undefined,
            company_domain: form.company_domain.trim() || undefined,
            phone: form.phone.trim(),
            business_type: form.business_type,
            source: form.source,
            self_follow: canSelfFollowOnCreate.value,
          },
          true,
        )
        ElMessage.success(
          canSelfFollowOnCreate.value ? '已强制录入并进入我的线索' : '已强制录入',
        )
        createVisible.value = false
        if (!props.forcedPool && canSelfFollowOnCreate.value) {
          pool.value = 'mine'
        }
        reload()
      } catch {
        /* cancel */
      }
    }
  } finally {
    saving.value = false
  }
}

async function openBatchAssign(ids?: number[]) {
  batchLeadIds.value = ids?.length ? [...ids] : [...selectedIds.value]
  if (!batchLeadIds.value.length) {
    ElMessage.warning('请先勾选待分配线索')
    return
  }
  batchMethod.value = 'average'
  batchOwnerIds.value = []
  batchReason.value = ''
  for (const key of Object.keys(manualOwnerMap)) delete manualOwnerMap[Number(key)]
  batchVisible.value = true
  empLoading.value = true
  try {
    const { data } = await fetchDirectoryPeople({ page: 1, page_size: 100, is_active: true })
    employees.value = data.items
  } finally {
    empLoading.value = false
  }
}

async function confirmBatchAssign() {
  if (!batchOwnerIds.value.length) {
    ElMessage.warning('请至少选择一名分配人')
    return
  }
  if (batchMethod.value === 'manual') {
    const missing = batchLeadIds.value.filter((id) => !manualOwnerMap[id])
    if (missing.length) {
      ElMessage.warning('请为每条线索指定接收人')
      return
    }
  }
  saving.value = true
  try {
    const { data } = await batchAssignLeads({
      lead_ids: batchLeadIds.value,
      owner_ids: batchOwnerIds.value,
      method: batchMethod.value,
      reason: batchReason.value || undefined,
      assignments:
        batchMethod.value === 'manual'
          ? batchLeadIds.value.map((lead_id) => ({
              lead_id,
              owner_id: manualOwnerMap[lead_id] as number,
            }))
          : [],
    })
    const msg = `成功 ${data.success_count} 条` + (data.failed_count ? `，失败 ${data.failed_count} 条` : '')
    if (data.failed_count) {
      ElMessage.warning(msg)
      console.warn('batch assign failed', data.failed)
    } else {
      ElMessage.success(msg)
    }
    batchVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (props.forcedPool) {
    pool.value = props.forcedPool
  } else if (!canManagePool.value) {
    pool.value = 'mine'
  }
  reload()
})

watch(
  () => props.openCreateSignal,
  (v, old) => {
    if (props.embedded && v && v !== old) openCreate()
  },
)

watch(
  () => props.forcedPool,
  (v) => {
    if (v) {
      pool.value = v
      reload()
    }
  },
)
</script>

<style scoped>
.quota-strip {
  margin-bottom: 12px;
  padding: 14px 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.quota-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.quota-item span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.quota-item strong {
  font-size: 18px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.manual-rows,
.preview-rows {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.manual-row,
.preview-row {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
}
.preview-row i {
  color: var(--el-text-color-secondary);
}
:deep(.selected-row) {
  background: var(--crm-primary-soft) !important;
}
.embedded.leads-page {
  max-width: none;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.embedded.leads-page > .allocation-summary,
.embedded.leads-page > .sales-quota-strip,
.embedded.leads-page > .crm-stats,
.embedded.leads-page > .quota-strip {
  flex-shrink: 0;
}
.embedded.leads-page > .crm-panel {
  flex: 1 1 auto;
  min-height: 0;
}
.embedded.leads-page .crm-table-wrap.is-fit {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.embedded.leads-page .pager,
.embedded.leads-page .table-footer {
  flex-shrink: 0;
}
@media (max-width: 768px) {
  .embedded.leads-page {
    height: auto;
    overflow: visible;
  }
  .embedded.leads-page > .crm-panel {
    flex: none;
    overflow: visible;
  }
  .embedded.leads-page .crm-table-wrap.is-fit,
  .embedded.leads-page .crm-table-wrap {
    flex: none;
    overflow-x: auto;
    overflow-y: visible;
    -webkit-overflow-scrolling: touch;
  }
  .toolbar-actions {
    width: 100%;
  }
  .toolbar-actions .el-button {
    width: 100%;
  }
  .table-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .pager {
    justify-content: center;
    overflow-x: auto;
  }
  .quota-strip {
    grid-template-columns: 1fr 1fr;
  }
  .drawer-top {
    align-items: flex-start;
  }
  .drawer-top h2 {
    font-size: 18px;
    line-height: 1.35;
    word-break: break-word;
  }
  .drawer-footer-actions .drawer-action-btn {
    flex: 1 1 100%;
  }
}
@media (max-width: 420px) {
  .quota-strip {
    grid-template-columns: 1fr;
  }
}
.drawer-inner {
  padding: 4px 4px 12px;
}
.drawer-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.drawer-eyebrow {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.drawer-top h2 {
  margin: 4px 0 0;
  font-size: 20px;
  line-height: 1.3;
}
.detail-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.detail-summary small {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.drawer-section {
  margin-bottom: 18px;
}
.drawer-section h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.detail-cell {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--crm-border);
  background: var(--crm-surface-soft);
}
.detail-cell small {
  display: block;
  color: var(--crm-ink-soft);
  font-size: 12px;
  margin-bottom: 4px;
}
.detail-cell b {
  font-size: 13px;
  font-weight: 600;
  color: var(--crm-ink);
}
.log-meta {
  display: block;
  margin-top: 4px;
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.drawer-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.drawer-section-head h3 {
  margin: 0;
}
.drawer-log-filter :deep(.el-radio-button__inner) {
  padding: 4px 8px;
  font-size: 12px;
}
.log-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
  flex-wrap: wrap;
}
.drawer-footer-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  width: 100%;
  justify-content: stretch;
}
.drawer-footer-actions .drawer-action-btn {
  margin: 0;
  flex: 1 1 0;
  min-width: 0;
  padding-left: 8px;
  padding-right: 8px;
}
.drawer-footer-actions .drawer-action-danger {
  --el-button-bg-color: color-mix(in oklab, var(--el-color-danger) 10%, #fff);
  --el-button-border-color: color-mix(in oklab, var(--el-color-danger) 35%, #fff);
  --el-button-text-color: var(--el-color-danger);
}
@media (max-width: 900px) {
  .quota-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .drawer-footer-actions {
    flex-wrap: wrap;
  }
  .drawer-footer-actions .drawer-action-btn {
    flex: 1 1 calc(50% - 8px);
  }
}

.dialog-eyebrow {
  margin: -4px 0 12px;
  color: var(--crm-ink-soft);
  font-size: 13px;
}
.lead-create-form :deep(.el-form-item) {
  margin-bottom: 14px;
}
.form-block {
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid var(--crm-border);
  border-radius: 12px;
  background: var(--crm-surface-soft);
}
.form-block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 14px;
}
.form-block h3 span {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--crm-primary);
  color: #fff;
  font-size: 12px;
}
.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}
.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--crm-ink-soft);
  line-height: 1.4;
}
.duplicate-result {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--crm-border);
}
.duplicate-result.clear {
  border-color: color-mix(in oklab, var(--crm-success) 35%, var(--crm-border));
  background: var(--crm-success-soft);
}
.duplicate-result.review {
  border-color: oklch(0.78 0.1 70);
  background: oklch(0.97 0.03 70);
}
.duplicate-result.checking {
  border-color: color-mix(in oklab, var(--crm-primary) 35%, var(--crm-border));
}
.duplicate-mark {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--crm-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.duplicate-result.clear .duplicate-mark {
  background: var(--crm-success);
}
.duplicate-result.review .duplicate-mark {
  background: oklch(0.62 0.12 55);
}
.duplicate-result b {
  display: block;
  margin-bottom: 4px;
}
.duplicate-result small {
  color: var(--crm-ink-soft);
  font-size: 12px;
  line-height: 1.4;
}
.health-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.health-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid var(--crm-border);
  font-size: 13px;
}
.health-row b {
  color: var(--crm-ink-soft);
  font-weight: 500;
}
@media (max-width: 640px) {
  .form-grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
