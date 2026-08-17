<template>
  <div class="crm-page project-delivery crm-fit-page">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="wb-eyebrow">经营台</p>
        <h1>项目管理</h1>
        <p>{{ workbenchDesc }}</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="tab === 'initiation'" v-perm="'project:manage'" type="primary" @click="openInitiation">
          ＋ 发起项目立项
        </el-button>
        <el-button
          v-else-if="tab === 'execute' && executeMode === 'plan' && canManagePlan"
          type="primary"
          @click="onBaselineAction"
        >
          {{ planBaselineLocked ? '申请基线变更' : '确定计划基线' }}
        </el-button>
        <el-button
          v-else-if="tab === 'execute' && executeMode === 'tasks'"
          v-perm="'project:manage'"
          type="primary"
          @click="openTaskCreate"
        >
          ＋ 新建项目任务
        </el-button>
        <el-button
          v-else-if="tab === 'acceptance' && canSubmitAcceptance"
          v-perm.any="['project:accept_submit', 'project:manage']"
          type="primary"
          @click="openAcceptance"
        >
          ＋ 发起内部验收
        </el-button>
      </div>
    </header>

    <div class="project-tabs" role="tablist" aria-label="项目管理分区">
      <button
        type="button"
        class="project-tab"
        role="tab"
        :aria-selected="tab === 'portfolio'"
        :class="{ active: tab === 'portfolio' }"
        @click="setTab('portfolio')"
      >
        项目台账
      </button>
      <span class="project-tab-sep" aria-hidden="true">交付</span>
      <button
        v-for="item in deliveryTabs"
        :key="item.key"
        type="button"
        class="project-tab"
        role="tab"
        :aria-selected="tab === item.key"
        :class="{ active: tab === item.key }"
        @click="setTab(item.key)"
      >
        {{ item.label }}
      </button>
    </div>

    <div
      class="crm-fit-body"
      :class="{ 'is-scroll': isCompact || tab !== 'portfolio' || overviewMode === 'board' }"
    >
    <!-- 项目台账：同一批项目，列表 / 看板两种查看方式 -->
    <template v-if="tab === 'portfolio'">
      <div class="submode-bar">
        <el-radio-group v-model="overviewMode" size="small" @change="onOverviewModeChange">
          <el-radio-button value="list">列表</el-radio-button>
          <el-radio-button value="board">看板</el-radio-button>
        </el-radio-group>
        <span class="muted submode-hint">同一批项目 · 点击进入档案</span>
      </div>

      <section class="portfolio-hero">
        <button
          v-for="item in portfolioStatCards"
          :key="item.key"
          type="button"
          class="portfolio-mini"
          :class="{ active: portfolioStat === item.key }"
          @click="onPortfolioStatClick(item.key)"
        >
          <small>{{ item.label }}</small>
          <strong>{{ item.count }}</strong>
          <span>{{ item.note }}</span>
        </button>
      </section>

      <section class="crm-panel" :class="{ 'crm-fit-panel': overviewMode === 'list' && !isCompact }">
        <div class="toolbar">
          <div class="filters">
            <el-input
              v-model="keyword"
              placeholder="搜索项目编号/名称"
              clearable
              :style="isCompact ? { width: '100%' } : { width: '220px' }"
              @keyup.enter="loadProjects"
              @clear="loadProjects"
            />
            <el-select
              v-model="statusFilter"
              clearable
              placeholder="状态"
              :style="isCompact ? { width: '100%' } : { width: '140px' }"
              @change="onStatusFilterChange"
            >
              <el-option
                v-for="(label, key) in PROJECT_STATUS_LABEL"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
            <el-select
              v-model="portfolioType"
              clearable
              placeholder="交付类型"
              :style="isCompact ? { width: '100%' } : { width: '150px' }"
            >
              <el-option
                v-for="opt in businessTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-button @click="loadProjects">查询</el-button>
          </div>
          <div v-if="overviewMode === 'board'" class="board-legend">
            <span><i style="background: oklch(0.5 0.16 25)"></i>高风险</span>
            <span><i style="background: oklch(0.55 0.12 70)"></i>需关注</span>
            <span><i style="background: var(--crm-success)"></i>正常</span>
          </div>
        </div>

        <template v-if="overviewMode === 'list'">
          <div class="crm-table-wrap" :class="{ 'is-fit': !isCompact }">
            <el-table
              :data="listProjects"
              v-loading="loading"
              stripe
              :height="isCompact ? undefined : '100%'"
              @row-click="goDetail"
            >
              <el-table-column label="项目" min-width="200">
                <template #default="{ row }">
                  <b>{{ row.name }}</b>
                  <div class="muted">{{ row.project_no }}</div>
                </template>
              </el-table-column>
              <el-table-column label="交付类型" width="120">
                <template #default="{ row }">{{ typeLabel(row.project_type) }}</template>
              </el-table-column>
              <el-table-column prop="manager_name" label="项目负责人" width="110" />
              <el-table-column label="基线周期" width="160">
                <template #default="{ row }">
                  {{ formatRange(row.start_date, row.end_date) }}
                </template>
              </el-table-column>
              <el-table-column label="进度" width="140">
                <template #default="{ row }">
                  <el-progress :percentage="row.progress || 0" :stroke-width="10" />
                </template>
              </el-table-column>
              <el-table-column label="下一步" min-width="140" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ formatNextNode(row) }}
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="table-footer">
            <span class="muted">点击行查看项目档案</span>
            <span>共 {{ listProjectTotal }} 个项目</span>
          </div>
        </template>

        <template v-else>
          <div class="project-kanban-scroll" v-loading="loading">
            <section class="project-kanban">
              <article v-for="col in boardColumns" :key="col.key" class="project-kanban-column">
                <div class="project-kanban-head">
                  <span>
                    <i :style="{ background: col.color }"></i>
                    <b>{{ col.label }}</b>
                  </span>
                  <em>{{ col.items.length }} 项</em>
                </div>
                <div class="project-board-cards">
                  <button
                    v-for="row in col.items"
                    :key="row.id"
                    type="button"
                    class="project-board-card"
                    @click="goDetail(row)"
                  >
                    <span class="project-board-card-top">
                      <small>{{ row.project_no }}</small>
                      <span class="health-pill" :class="row.health || 'normal'">
                        {{ HEALTH_LABEL[row.health || 'normal'] }}
                      </span>
                    </span>
                    <h3>{{ row.name }}</h3>
                    <small>{{ typeLabel(row.project_type) }} · 负责人 {{ row.manager_name || '—' }}</small>
                    <span class="project-board-card-progress">
                      <span class="bar"><i :style="{ width: `${row.progress || 0}%` }"></i></span>
                      <b>{{ row.progress || 0 }}%</b>
                    </span>
                    <span class="project-board-card-meta">
                      <span>下一步</span>
                      <b>{{ formatNextNode(row) }}</b>
                    </span>
                  </button>
                  <div v-if="!col.items.length" class="project-board-empty">当前筛选条件下无项目</div>
                </div>
              </article>
            </section>
          </div>
          <div class="table-footer">
            <span class="muted">点击卡片查看项目档案</span>
            <span>共 {{ listProjectTotal }} 个项目</span>
          </div>
        </template>
      </section>
    </template>

    <!-- 交接与立项 -->
    <template v-else-if="tab === 'initiation'">
      <section class="handoff-grid">
        <article
          v-for="row in initiatingProjects"
          :key="row.id"
          class="handoff-card"
          :class="{ blocked: !handoffReady(row) }"
        >
          <div class="card-top">
            <div>
              <h3>{{ row.name }}</h3>
              <p class="sub">{{ row.contract_no || '未关联合同' }} · {{ typeLabel(row.project_type) }}</p>
            </div>
            <div class="card-top-tags">
              <el-tag v-if="deferPending(row)" type="warning" size="small">
                {{ row.contract_id ? '无到款待审' : '无合同待审' }}
              </el-tag>
              <el-tag v-else-if="deferRejected(row)" type="danger" size="small">
                {{ row.contract_id ? '无到款驳回' : '无合同驳回' }}
              </el-tag>
              <el-tag v-else-if="deferApproved(row) && !paymentOk(row)" type="warning" size="small">
                {{ row.contract_id ? '待首付款' : '无合同已通过' }}
              </el-tag>
              <el-tag :type="handoffReady(row) ? 'success' : 'danger'" size="small">
                {{ handoffReady(row) ? '可发起' : '条件未满足' }}
              </el-tag>
            </div>
          </div>
          <div class="handoff-checks">
            <template v-if="!row.contract_id">
              <span>◇ 无合同立项</span>
              <span
                :class="{
                  failed: !deferApproved(row),
                }"
              >
                {{
                  deferPending(row)
                    ? '◇ 无合同待审批'
                    : deferRejected(row)
                      ? '⚠ 无合同已驳回'
                      : deferApproved(row)
                        ? '✓ 无合同已通过'
                        : '⚠ 待提交审批'
                }}
              </span>
            </template>
            <template v-else>
              <span :class="{ failed: !row.contract_active_ok }">
                {{ row.contract_active_ok ? '✓' : '⚠' }} 合同已签署
              </span>
              <span :class="{ failed: !paymentOk(row) && !deferApproved(row) }">
                {{
                  paymentOk(row)
                    ? '✓ 已确认到账'
                    : deferPending(row)
                      ? '◇ 无到款待审批'
                      : deferRejected(row)
                        ? '⚠ 无到款已驳回'
                        : deferApproved(row)
                          ? '◇ 无到款已通过'
                          : '⚠ 已确认到账'
                }}
              </span>
            </template>
          </div>
          <p v-if="row.payment_deferred && row.payment_deferred_reason" class="sub deferred-reason">
            例外原因：{{ row.payment_deferred_reason }}
          </p>
          <p v-if="deferRejected(row) && row.payment_defer_reject_reason" class="sub deferred-reason">
            驳回原因：{{ row.payment_defer_reject_reason }}
          </p>
          <div class="handoff-meta">
            <div>
              <small>商务责任人</small>
              <b>{{ row.business_owner_name || row.creator_name || '—' }}</b>
            </div>
            <div>
              <small>建议负责人</small>
              <b>{{ row.manager_name || '—' }}</b>
            </div>
            <div>
              <small>计划启动</small>
              <b>{{ formatDate(row.start_date) || '待定' }}</b>
            </div>
          </div>
          <el-button type="primary" @click="advanceInitiating(row)">
            {{
              !handoffReady(row)
                ? '查看缺失项'
                : row.status === 'initiating'
                  ? '进入计划'
                  : '去编计划'
            }}
          </el-button>
        </article>
        <article v-if="!initiatingProjects.length" class="handoff-card">
          <h3>暂无待立项项目</h3>
          <p class="sub">点击右上角「发起项目立项」，或从已生效合同创建交付项目。</p>
        </article>
      </section>

      <section class="crm-panel">
        <div class="card-head" style="margin-bottom: 12px">
          <div>
            <b>待确认资源</b>
            <span class="muted" style="margin-left: 8px">
              计划投入即任务工时预算；确认后拆任务合计不可超过各部门投入之和
            </span>
          </div>
          <el-tag :type="resourcePendingCount ? 'warning' : 'success'" size="small">
            {{ resourcePendingCount ? `${resourcePendingCount} 项待处理` : '已全部确认' }}
          </el-tag>
        </div>
        <el-table :data="resourceNeeds" stripe v-loading="resourceLoading">
          <el-table-column label="立项申请" min-width="160">
            <template #default="{ row }">
              <b>{{ row.project_name || row.project_no }}</b>
              <div class="sub">{{ row.project_no }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="role_name" label="需求角色" width="120" />
          <el-table-column prop="department_name" label="涉及部门" width="110" />
          <el-table-column label="建议成员" width="110">
            <template #default="{ row }">
              {{ row.confirmed_user_name || row.suggested_user_name || '待指定' }}
            </template>
          </el-table-column>
          <el-table-column label="计划投入" width="100">
            <template #default="{ row }">{{ formatHours(row.planned_hours) }}h</template>
          </el-table-column>
          <el-table-column label="排期检查" width="110">
            <template #default="{ row }">
              <el-tag :type="scheduleTagType(row.schedule_status)" size="small">
                {{ scheduleLabel(row.schedule_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ resourceStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="handler_role" label="当前处理角色" width="120" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending'"
                link
                type="primary"
                @click="openResourceConfirm(row)"
              >
                确认
              </el-button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </template>

    <!-- 执行：计划 / 任务 -->
    <template v-else-if="tab === 'execute'">
      <div class="submode-bar">
        <el-radio-group v-model="executeMode" size="small" @change="onExecuteModeChange">
          <el-radio-button value="plan">计划基线</el-radio-button>
          <el-radio-button value="tasks">任务工时</el-radio-button>
        </el-radio-group>
      </div>

      <template v-if="executeMode === 'plan'">
      <div class="toolbar" style="margin-bottom: 12px">
        <el-select
          v-model="planProjectId"
          filterable
          placeholder="切换查看项目（非重新立项）"
          style="width: 360px"
          @change="loadPlanDetail"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="`${p.project_no} · ${p.name}`"
            :value="p.id"
          />
        </el-select>
      </div>

      <template v-if="planProject">
      <section
        class="plan-summary"
        :class="{
          'plan-summary--slim': !milestones.length,
          'plan-summary--compact': milestones.length > 0,
        }"
      >
        <article class="plan-title-card">
          <div class="plan-title-main">
            <el-tag size="small" type="info">{{ typeLabel(planProject.project_type) }}</el-tag>
            <h2>{{ planProject.name }}</h2>
            <p>
              {{ planProject.project_no }}
              <template v-if="planBaselineLocked">
                · 基线 {{ planProject.baseline_version || 'V1' }} 已生效
                <span v-if="planBaselineMeta?.effectiveAt">（{{ planBaselineMeta.effectiveAt }}）</span>
              </template>
              <template v-else>· 基线尚未确认</template>
            </p>
            <p v-if="milestones.length" class="plan-title-meta">
              节点 {{ planMilestoneDoneCount }} / {{ milestones.length }}
              · 证据待确认 {{ planEvidencePendingCount }}
              · 未挂任务 {{ planNodesWithoutTaskCount }}
            </p>
          </div>
          <div v-if="milestones.length" class="plan-health-ring">
            <svg viewBox="0 0 80 80" aria-hidden="true">
              <circle
                cx="40"
                cy="40"
                r="31"
                fill="none"
                stroke="var(--crm-surface-soft)"
                stroke-width="8"
              />
              <circle
                cx="40"
                cy="40"
                r="31"
                fill="none"
                stroke="var(--crm-primary)"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="planRingCirc"
                :stroke-dashoffset="planRingOffsetEffective"
                transform="rotate(-90 40 40)"
              />
            </svg>
            <div>
              <strong>{{ planEffectiveProgress }}%</strong>
              <small>{{ planProgressLabel }}</small>
            </div>
          </div>
          <div v-else class="plan-next-chip">
            <small>推荐下一步</small>
            <strong>{{ planBaselineLocked ? '去任务工时拆任务' : '先确认计划基线' }}</strong>
          </div>
        </article>
        <article v-if="!milestones.length" class="portfolio-mini">
          <small>推进方式</small>
          <strong>任务驱动</strong>
          <span>未使用计划节点</span>
        </article>
        <article class="portfolio-mini plan-hours-card" @click="goToTasksWorkbench">
          <small>任务计划 / 资源承诺</small>
          <strong :class="{ 'hours-over': hoursBudget?.over_budget }">
            {{ formatHours(hoursBudget?.task_planned_hours ?? taskHours.planned) }}
            /
            {{ formatHours(hoursBudget?.resource_budget_hours) }}h
          </strong>
          <span>
            实际 {{ formatHours(hoursBudget?.task_actual_hours ?? taskHours.actual) }}h
            · 剩余可拆 {{ formatHours(hoursBudget?.remaining_hours) }}h →
          </span>
        </article>
      </section>

      <section class="crm-panel plan-milestone-panel">
        <div class="card-head plan-panel-head">
          <div>
            <b>计划节点（可选）</b>
            <span class="muted" style="margin-left: 8px">
              复杂项目拆阶段；简单项目可跳过，直接用任务
            </span>
          </div>
          <div class="plan-panel-actions">
            <el-button v-if="canManagePlan && milestones.length" type="primary" @click="openMilestone">
              ＋ 添加节点
            </el-button>
          </div>
        </div>

        <div v-if="!milestones.length" class="plan-next-guide" v-loading="planLoading">
          <h3>{{ planBaselineLocked ? '基线已锁定，开始推进' : '确认「做什么」，再拆「怎么做」' }}</h3>
          <p>
            {{
              planBaselineLocked
                ? '还没有计划节点。简单项目直接去任务工时；需要分阶段验收再补节点。'
                : '先点「确定计划基线」。弹窗里可直接添加计划节点；简单项目也可跳过，确认后按任务推进。'
            }}
          </p>
          <div class="plan-next-actions">
            <el-button
              v-if="!planBaselineLocked && canManagePlan"
              type="primary"
              @click="onBaselineAction"
            >
              确定计划基线
            </el-button>
            <el-button
              v-if="planBaselineLocked"
              type="primary"
              @click="goToTasksWorkbench"
            >
              去任务工时
            </el-button>
            <el-button v-if="canManagePlan" @click="openMilestone">＋ 添加节点</el-button>
          </div>
        </div>

        <el-table v-else :data="milestones" v-loading="planLoading" stripe>
          <el-table-column label="节点" min-width="160">
            <template #default="{ row }">
              <b>{{ row.name }}</b>
              <div v-if="row.role" class="muted">{{ row.role }}</div>
            </template>
          </el-table-column>
          <el-table-column label="计划日期" width="150">
            <template #default="{ row }">
              {{
                row.start_date && row.deadline
                  ? `${formatShortDate(row.start_date)} ~ ${formatShortDate(row.deadline)}`
                  : formatShortDate(row.deadline || row.start_date)
              }}
            </template>
          </el-table-column>
          <el-table-column prop="deliverable" label="必交成果" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.deliverable || '—' }}</template>
          </el-table-column>
          <el-table-column label="任务" width="90">
            <template #default="{ row }">
              <span v-if="!(row.task_total || 0)" class="muted">无任务</span>
              <span
                v-else
                :class="{ 'text-warn': (row.task_done || 0) < (row.task_total || 0) }"
              >
                {{ row.task_done || 0 }}/{{ row.task_total || 0 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="证据" width="100">
            <template #default="{ row }">
              <button type="button" class="ms-status-pill" :class="evidenceTone(row)" @click="openEvidencePanel(row)">
                {{ evidenceStatusLabel(row) }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="下一步" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span
                :class="{
                  muted: !planInExecution || (row.status === 'done' && row.evidence_status === 'confirmed'),
                  'text-warn': planInExecution && row.status === 'done' && row.evidence_status !== 'confirmed',
                }"
              >
                {{ row.next_action || '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <div class="ms-row-actions">
                <button
                  v-if="milestonePrimaryActionLabel(row)"
                  type="button"
                  class="text-link"
                  @click="onMilestonePrimaryAction(row)"
                >
                  {{ milestonePrimaryActionLabel(row) }}
                </button>
                <button
                  v-if="canManagePlan"
                  type="button"
                  class="text-link text-danger"
                  @click="onDeleteMilestone(row)"
                >
                  删除
                </button>
                <span v-if="!milestonePrimaryActionLabel(row) && !canManagePlan" class="muted">—</span>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="milestones.length" class="plan-table-footer">
          <template v-if="!planInExecution">
            <span class="muted">当前仍在计划阶段：节点只作编排，进度不会因定义节点变成 100%</span>
            <el-button
              v-if="canManagePlan && !planBaselineLocked"
              type="primary"
              link
              @click="onBaselineAction"
            >
              去确认基线
            </el-button>
          </template>
          <template v-else>
            <span v-if="planEvidencePendingCount" class="text-warn">
              有 {{ planEvidencePendingCount }} 个节点证据待确认
            </span>
            <span v-else-if="planNodesWithoutTaskCount" class="muted">
              有节点尚未拆任务，建议先建任务再推进
            </span>
            <span v-else class="muted">节点与证据正常</span>
            <el-button type="primary" link @click="goToTasksWorkbench">去任务工时</el-button>
          </template>
        </div>
      </section>

      <div
        v-if="!showPlanExtras && !planExtrasOpen"
        class="plan-extras-toggle"
      >
        <button type="button" class="text-link" @click="planExtrasOpen = true">
          展开风险 / 变更记录 / 人员档期
        </button>
      </div>

      <template v-if="showPlanExtras || planExtrasOpen">
        <section class="plan-bottom">
          <article class="crm-panel plan-side-card">
            <div class="card-head plan-panel-head">
              <div class="plan-panel-copy">
                <b>风险与问题</b>
                <span class="plan-panel-desc">影响范围、责任人和处理期限可追溯</span>
              </div>
              <div class="plan-panel-actions">
                <button
                  v-if="canManagePlan"
                  type="button"
                  class="text-link"
                  @click="openRiskDialog"
                >
                  ＋ 新增
                </button>
              </div>
            </div>
            <div v-if="planRisks.length" class="plan-alert-list">
              <div
                v-for="item in planRisks"
                :key="item.id"
                class="plan-alert-row"
                :class="{ danger: item.level === '高' }"
              >
                <span class="plan-alert-symbol">{{ item.level === '高' ? '!' : '↗' }}</span>
                <span>
                  <b>{{ item.title }}</b>
                  <small>责任角色：{{ item.role }} · {{ item.response }}</small>
                </span>
                <span class="ms-status-pill" :class="item.level === '高' ? 'bad' : item.level === '中' ? 'warn' : ''">
                  {{ item.level }}
                </span>
              </div>
            </div>
            <div v-else class="plan-empty">
              {{ canManagePlan ? '暂无风险记录，点击右上角新增' : '暂无风险记录' }}
            </div>
          </article>

          <article class="crm-panel plan-side-card">
            <div class="card-head plan-panel-head">
              <div class="plan-panel-copy">
                <b>变更记录</b>
                <span class="plan-panel-desc">
                  {{
                    planBaselineLocked
                      ? '基线锁定后，改范围/工期走变更审批'
                      : '确认基线后，改范围请走变更审批'
                  }}
                </span>
              </div>
              <div class="plan-panel-actions">
                <button
                  v-if="canManagePlan"
                  type="button"
                  class="text-link"
                  @click="openChangeDialog"
                >
                  ＋ 申请变更
                </button>
              </div>
            </div>
            <div v-if="planChanges.length" class="plan-change-list">
              <div v-for="item in planChanges" :key="item.id" class="plan-change-row">
                <span>{{ item.code }} · {{ item.title }}</span>
                <span class="change-row-right">
                  <span class="ms-status-pill" :class="changeTone(item.status)">{{ item.status }}</span>
                  <template v-if="canManagePlan && (item.status === '审批中' || item.status === '待确认')">
                    <button type="button" class="text-link" @click="resolveChange(item, '已生效')">通过</button>
                    <button type="button" class="text-link text-warn" @click="resolveChange(item, '已驳回')">驳回</button>
                  </template>
                </span>
              </div>
            </div>
            <div v-else class="plan-empty">
              {{ canManagePlan ? '暂无变更申请，点击右上角发起' : '暂无变更申请' }}
            </div>
          </article>
        </section>

        <section class="crm-panel" style="margin-top: 14px">
          <div class="card-head plan-panel-head">
            <div class="plan-panel-copy">
              <b>人员档期</b>
              <span class="plan-panel-desc">
                谁在何时被占用（日历）；与上方「计划节点」不同，不影响进度
              </span>
            </div>
            <div class="plan-panel-actions">
              <el-button size="small" type="primary" @click="goCreateScheduleForProject">＋ 挂本项目档期</el-button>
              <el-button size="small" @click="$router.push('/schedules')">打开排期会议</el-button>
            </div>
          </div>
          <el-table
            :data="planSchedules"
            v-loading="planSchedulesLoading"
            stripe
            empty-text="暂无人员档期。需要约人时，点右上角挂到本项目。"
          >
            <el-table-column prop="title" label="排期" min-width="140" show-overflow-tooltip />
            <el-table-column label="时间" width="180">
              <template #default="{ row }">{{ formatScheduleRange(row) }}</template>
            </el-table-column>
            <el-table-column prop="employee_name" label="人员" width="90" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="scheduleStatusTag(row)">
                  {{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
                <el-tag v-if="row.has_conflict" type="danger" size="small" style="margin-left: 4px">
                  冲突
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="$router.push(`/schedules/${row.id}`)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </template>
      </template>

      <div v-else class="plan-empty-block">请选择项目后查看计划基线</div>
      </template>

      <template v-else>
      <section class="task-kpis">
        <div>
          <small>我的执行任务</small>
          <b>{{ taskStats?.mine ?? 0 }}</b>
        </div>
        <div>
          <small>逾期任务</small>
          <b :style="{ color: (taskStats?.overdue || 0) > 0 ? 'oklch(0.5 0.16 25)' : undefined }">
            {{ taskStats?.overdue ?? 0 }}
          </b>
        </div>
        <div :title="taskHoursBudgetHint">
          <small>{{ taskProjectFilter ? '任务计划 / 资源承诺' : '计划 / 实际工时' }}</small>
          <b :class="{ 'hours-over': taskProjectFilter && hoursBudget?.over_budget }">
            <template v-if="taskProjectFilter && hoursBudget">
              {{ formatHours(hoursBudget.task_planned_hours) }}
              /
              {{ formatHours(hoursBudget.resource_budget_hours) }}h
            </template>
            <template v-else>
              {{ formatHours(taskStats?.planned_hours) }} / {{ formatHours(taskStats?.actual_hours) }}h
            </template>
          </b>
        </div>
        <div
          class="kpi-clickable"
          :title="taskProjectFilter ? '查看本项目关联工单' : '先点所属项目聚焦，再看关联工单'"
          @click="focusLinkedTickets"
        >
          <small>关联工单</small>
          <b>{{ linkedTicketDisplayCount }}</b>
        </div>
      </section>

      <p class="task-logic-hint">
        <b>任务计划工时</b>计入立项「资源承诺」预算；合计不可超过各部门计划投入。
        <b>协作工单</b>管跨部门协助（状态独立，关工单不会自动完成任务）。
        点「所属项目」可聚焦到单项目，再看下方关联工单。
      </p>

      <section class="crm-panel">
        <div class="toolbar">
          <div class="filters">
            <el-input
              v-model="taskKeyword"
              placeholder="搜索任务/项目"
              clearable
              style="width: 220px"
              @keyup.enter="loadTasks"
              @clear="loadTasks"
            />
            <el-select v-model="taskStatus" clearable placeholder="状态" style="width: 140px" @change="loadTasks">
              <el-option label="进行中" value="doing" />
              <el-option label="待排期" value="pending" />
              <el-option label="已逾期" value="overdue" />
              <el-option label="已完成" value="done" />
            </el-select>
            <el-tag
              v-if="taskProjectFilter"
              closable
              type="info"
              style="margin-right: 8px"
              @close="clearTaskProjectFilter"
            >
              仅看：{{ taskProjectFilterName || '当前项目' }}
            </el-tag>
            <el-button @click="loadTasks">查询</el-button>
          </div>
        </div>
        <el-table :data="tasks" v-loading="taskLoading" stripe>
          <el-table-column label="项目任务" min-width="180">
            <template #default="{ row }">
              <b>{{ row.title }}</b>
              <div class="muted">{{ row.task_no }}</div>
            </template>
          </el-table-column>
          <el-table-column label="所属项目" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <el-button link type="primary" @click="filterTasksByProject(row)">
                {{ row.project_name || '—' }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="所属里程碑" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.milestone_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="assignee_name" label="责任人" width="100" />
          <el-table-column prop="department_name" label="部门" width="110" />
          <el-table-column label="计划日期" width="150">
            <template #default="{ row }">
              {{
                row.start_date && row.due_date
                  ? `${formatShortDate(row.start_date)} ~ ${formatShortDate(row.due_date)}`
                  : formatDate(row.due_date || row.start_date) || '—'
              }}
            </template>
          </el-table-column>
          <el-table-column label="计划/实际工时" width="120">
            <template #default="{ row }">
              {{ formatHours(row.planned_hours) }} / {{ formatHours(row.actual_hours) }}h
            </template>
          </el-table-column>
          <el-table-column label="人员档期" width="140">
            <template #default="{ row }">
              <el-button
                v-if="(row.schedule_booked || 0) + (row.schedule_completed || 0) > 0"
                link
                type="primary"
                @click="openTaskSchedules(row)"
              >
                已约 {{ row.schedule_booked || 0 }} · 完成 {{ row.schedule_completed || 0 }}
              </el-button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="协作工单" width="130">
            <template #default="{ row }">
              <el-button
                v-if="row.ticket_id"
                link
                type="primary"
                @click="$router.push(`/tickets/${row.ticket_id}`)"
              >
                {{ row.ticket_no || `工单#${row.ticket_id}` }}
              </el-button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.due_status === 'overdue' ? 'danger' : row.status === 'done' ? 'success' : 'info'"
              >
                {{ row.due_status === 'overdue' ? '已逾期' : TASK_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status !== 'done' && canCompleteTask(row)"
                link
                type="primary"
                @click="markTaskDone(row)"
              >
                完成
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section
        v-if="taskProjectFilter"
        ref="linkedTicketsPanelRef"
        class="crm-panel"
        style="margin-top: 14px"
      >
        <div class="toolbar">
          <div class="filters">
            <strong>本项目关联工单</strong>
            <span class="muted" style="margin-left: 8px">
              只看挂到「{{ taskProjectFilterName || '当前项目' }}」的协作；未挂任务的工单也会列出
            </span>
          </div>
          <div class="filters">
            <el-button
              type="primary"
              @click="
                $router.push({
                  path: '/tickets',
                  query: { create: '1', project_id: String(taskProjectFilter) },
                })
              "
            >
              发起协作
            </el-button>
            <el-button
              @click="
                $router.push({
                  path: '/tickets',
                  query: { project_id: String(taskProjectFilter) },
                })
              "
            >
              打开工单台
            </el-button>
          </div>
        </div>
        <el-table
          :data="linkedTickets"
          v-loading="linkedTicketsLoading"
          stripe
          empty-text="本项目暂无关联工单"
        >
          <el-table-column prop="ticket_no" label="编号" width="140" />
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="ticketStatusTag(row)">
                {{ TICKET_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assignee_name" label="处理人" width="100">
            <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="关联任务" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.task_no ? `${row.task_no} · ${row.task_title || ''}` : '仅挂项目' }}
            </template>
          </el-table-column>
          <el-table-column label="SLA" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.is_overdue" type="danger" size="small">已逾期</el-tag>
              <el-tag v-else-if="row.is_near_sla" type="warning" size="small">接近时限</el-tag>
              <span v-else class="muted">正常</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="$router.push(`/tickets/${row.id}`)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
      </template>
    </template>

    <!-- 验收与收尾 -->
    <template v-else>
      <section class="accept-kpis">
        <div>
          <small>待内部验收</small>
          <b>{{ (stats?.executing || 0) + (stats?.accepting || 0) }}</b>
        </div>
        <div>
          <small>未关闭遗留问题</small>
          <b>{{ stats?.leftover ?? 0 }}</b>
        </div>
        <div>
          <small>待结项</small>
          <b>{{ stats?.accepted ?? 0 }}</b>
        </div>
        <div>
          <small>续约提醒</small>
          <b>0</b>
        </div>
      </section>

      <section class="crm-panel">
        <el-table :data="acceptanceRows" v-loading="loading" stripe>
          <el-table-column label="项目" min-width="180">
            <template #default="{ row }">
              <el-button link type="primary" @click="goDetail(row)">
                <b>{{ row.name }}</b>
              </el-button>
              <div class="muted">{{ row.project_no }}</div>
            </template>
          </el-table-column>
          <el-table-column label="交付类型" width="120">
            <template #default="{ row }">{{ typeLabel(row.project_type) }}</template>
          </el-table-column>
          <el-table-column label="交付物完成" width="110">
            <template #default="{ row }">
              {{ row.milestone_done || 0 }}/{{ row.milestone_total || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="内部验收" width="120">
            <template #default="{ row }">
              <template v-if="row.acceptance_approval_status === 'pending'">验收审批中</template>
              <template v-else>
                {{
                  ACCEPTANCE_RESULT_LABEL[row.acceptance_result || ''] ||
                  (row.status === 'accepted' || row.status === 'completed' ? '已验收' : '未验收')
                }}
              </template>
            </template>
          </el-table-column>
          <el-table-column label="遗留问题" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <template v-if="row.leftover_summary">
                <el-button link type="primary" @click="openLeftover(row)">
                  查看遗留
                </el-button>
                <span v-if="row.leftover_closed" class="muted">（已关闭）</span>
                <span v-else class="leftover-open-hint">未关闭</span>
              </template>
              <template v-else>—</template>
            </template>
          </el-table-column>
          <el-table-column label="财务核对" min-width="140">
            <template #default="{ row }">
              <template v-if="row.finance_check_status === 'pending'">
                <div>审批中</div>
                <div class="sub" :class="{ 'text-warn': !row.contract_collection_complete }">
                  {{ financeSettleHint(row) }}
                </div>
              </template>
              <template v-else-if="row.finance_check_passed || row.finance_check_status === 'approved'">
                已通过
              </template>
              <template v-else-if="row.finance_check_status === 'rejected'">
                <div>已驳回</div>
                <div class="sub" :class="{ 'text-warn': !row.contract_collection_complete }">
                  {{ financeSettleHint(row) }}
                </div>
              </template>
              <template v-else-if="row.status === 'accepted' || row.status === 'completed'">
                <div>未提交</div>
                <div class="sub" :class="{ 'text-warn': !row.contract_collection_complete }">
                  {{ financeSettleHint(row) }}
                </div>
              </template>
              <template v-else>—</template>
            </template>
          </el-table-column>
          <el-table-column label="当前状态" width="140">
            <template #default="{ row }">
              <el-tag size="small">{{ PROJECT_STATUS_LABEL[row.status] || row.status }}</el-tag>
              <el-tag
                v-if="deferPending(row)"
                type="warning"
                size="small"
                style="margin-left: 4px"
              >
                无到款待审
              </el-tag>
              <el-tag
                v-else-if="deferApproved(row) && !paymentOk(row)"
                type="warning"
                size="small"
                style="margin-left: 4px"
              >
                待首付款
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <!-- 步骤：验收 → 财务核对 → 结项；只露出当前该做的一步 -->
              <el-button
                v-if="
                  (row.status === 'executing' || row.status === 'accepting') &&
                  row.acceptance_approval_status !== 'pending' &&
                  canSubmitAcceptance
                "
                v-perm.any="['project:accept_submit', 'project:manage']"
                link
                type="primary"
                @click="openAcceptance(row)"
              >
                发起验收
              </el-button>
              <span
                v-else-if="
                  (row.status === 'executing' || row.status === 'accepting') &&
                  row.acceptance_approval_status === 'pending'
                "
                class="muted"
              >
                验收审批中
              </span>
              <template v-else-if="row.status === 'accepted'">
                <el-button
                  v-if="row.leftover_summary && !row.leftover_closed"
                  link
                  type="warning"
                  @click="openLeftover(row, true)"
                >
                  关闭遗留
                </el-button>
                <el-button
                  v-if="
                    canSubmitFinanceCheck &&
                    !row.finance_check_passed &&
                    row.finance_check_status !== 'pending' &&
                    row.finance_check_status !== 'approved'
                  "
                  v-perm.any="['project:finance_submit', 'project:manage']"
                  link
                  type="warning"
                  @click="onFinanceCheck(row)"
                >
                  {{ row.finance_check_status === 'rejected' ? '重新提交财务核对' : '提交财务核对' }}
                </el-button>
                <span v-else-if="row.finance_check_status === 'pending'" class="muted">
                  财务核对审批中
                </span>
                <el-button
                  v-else-if="
                    canCompleteProject &&
                    (row.finance_check_passed || row.finance_check_status === 'approved') &&
                    row.contract_collection_complete
                  "
                  v-perm.any="['project:complete', 'project:manage']"
                  link
                  type="success"
                  @click="onComplete(row)"
                >
                  结项
                </el-button>
                <span
                  v-else-if="
                    (row.finance_check_passed || row.finance_check_status === 'approved') &&
                    !row.contract_collection_complete
                  "
                  class="muted text-warn"
                  :title="financeSettleHint(row)"
                >
                  回款未收齐，不可结项
                </span>
              </template>
              <span v-else-if="row.status === 'completed'" class="muted">已结项</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">
          <span>流程：内部验收通过 → 关闭遗留（如有）→ 提交财务核对（审批中心）→ 结项。点「查看遗留」可看具体事项。</span>
        </div>
      </section>
    </template>

    </div>

    <!-- 资源确认弹窗 -->
    <el-dialog
      v-model="resourceVisible"
      title="确认资源投入"
      width="560px"
      destroy-on-close
      class="claim-dialog resource-confirm-dialog"
    >
      <template v-if="resourceTarget">
        <p class="dialog-flow-hint">
          核对立项建议后选择处理方式：直接确认、调整后确认，或退回协调。
          计划投入是后续任务拆解的工时上限。
        </p>

        <div class="resource-summary">
          <div class="resource-summary-main">
            <small>需求角色</small>
            <b>{{ resourceTarget.role_name }}</b>
            <span class="resource-summary-project">
              {{ resourceTarget.project_name || resourceTarget.project_no || '—' }}
            </span>
          </div>
          <div class="resource-summary-grid">
            <div>
              <small>涉及部门</small>
              <b>{{ resourceTarget.department_name }}</b>
            </div>
            <div>
              <small>建议成员</small>
              <b>{{ resourceTarget.suggested_user_name || '待指定' }}</b>
            </div>
            <div>
              <small>计划投入</small>
              <b>{{ formatHours(resourceTarget.planned_hours) }}h</b>
            </div>
          </div>
        </div>

        <div class="resource-action-list" role="radiogroup" aria-label="处理方式">
          <button
            v-for="opt in resourceActionOptions"
            :key="opt.value"
            type="button"
            class="resource-action-card"
            :class="{
              active: resourceForm.action === opt.value,
              danger: opt.value === 'reject' && resourceForm.action === opt.value,
            }"
            role="radio"
            :aria-checked="resourceForm.action === opt.value"
            @click="resourceForm.action = opt.value"
          >
            <span class="resource-action-radio" aria-hidden="true" />
            <span class="resource-action-copy">
              <strong>{{ opt.title }}</strong>
              <small>{{ opt.desc }}</small>
            </span>
          </button>
        </div>

        <el-form
          class="resource-detail-form"
          :class="{ soft: resourceForm.action !== 'accept' }"
          label-position="top"
        >
          <template v-if="resourceForm.action === 'adjust'">
            <div class="resource-adjust-row">
              <el-form-item label="确认成员" required>
                <el-select
                  v-model="resourceForm.confirmed_user_id"
                  filterable
                  remote
                  :remote-method="searchEmployees"
                  :loading="empLoading"
                  placeholder="搜索并选择成员"
                  style="width: 100%"
                >
                  <el-option
                    v-for="e in employees"
                    :key="e.id"
                    :label="e.real_name || e.username"
                    :value="e.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="计划投入（小时）" required>
                <el-input-number
                  v-model="resourceForm.planned_hours"
                  :min="1"
                  :max="9999"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </div>
          </template>
          <el-form-item
            :label="resourceForm.action === 'reject' ? '拒绝说明' : '补充说明'"
            :required="resourceForm.action === 'reject'"
          >
            <el-input
              v-model="resourceForm.note"
              type="textarea"
              :rows="resourceForm.action === 'reject' ? 3 : 2"
              :placeholder="
                resourceForm.action === 'reject'
                  ? '必填：说明冲突原因，便于协调替代'
                  : '可选：补充排期、可用性或注意事项'
              "
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="resourceVisible = false">取消</el-button>
        <el-button
          :type="resourceForm.action === 'reject' ? 'danger' : 'primary'"
          :loading="saving"
          @click="onConfirmResource"
        >
          {{ resourceSubmitLabel }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 立项弹窗 -->
    <el-dialog
      v-model="initVisible"
      title="发起项目立项"
      width="680px"
      destroy-on-close
      class="claim-dialog init-dialog"
    >
      <p class="dialog-flow-hint">选合同（可选）→ 填目标 → 指定部门对接人</p>
      <el-form
        ref="initFormRef"
        class="init-dialog-form"
        :model="initForm"
        :rules="initRules"
        label-position="top"
      >
        <section class="form-block">
          <h3><span>1</span>合同与门槛</h3>
          <el-form-item label="客户合同" prop="contract_id">
            <el-select
              v-model="initForm.contract_id"
              filterable
              clearable
              remote
              :remote-method="searchContracts"
              :loading="contractLoading"
              placeholder="可选：我负责且尚未立项的已签署合同"
              style="width: 100%"
              @change="onContractPicked"
            >
              <el-option
                v-for="c in contractOptions"
                :key="c.id"
                :label="`${c.contract_no} · ${c.customer_name || c.title}`"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="交付类型" prop="project_type">
            <el-select v-model="initForm.project_type" style="width: 100%" @change="onProjectTypeChange">
              <el-option v-for="opt in businessTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="立项门槛">
            <div v-if="!initForm.contract_id" class="init-no-contract-box">
              <div class="handoff-checks init-gate-checks">
                <span>◇ 无合同立项（须负责人审批后才能进计划）</span>
              </div>
              <div class="sub" style="margin-top: 4px">
                不关联合同时将提交审批；通过后方可确认资源并进入计划。
              </div>
              <el-input
                v-model="initForm.payment_deferred_reason"
                type="textarea"
                :rows="2"
                maxlength="500"
                show-word-limit
                placeholder="必填：说明无合同立项的业务原因"
                style="margin-top: 8px"
              />
            </div>
            <template v-else>
              <div class="handoff-checks init-gate-checks">
                <span :class="{ failed: !initGate.contractOk }">
                  {{ initGate.contractOk ? '✓' : '⚠' }} 合同已签署
                </span>
                <span :class="{ failed: !initGate.paymentOk && !initForm.payment_deferred }">
                  {{
                    initGate.paymentOk
                      ? '✓ 已确认到账'
                      : initForm.payment_deferred
                        ? '◇ 无到款例外'
                        : '⚠ 已确认到账'
                  }}
                </span>
              </div>
              <div class="sub" style="margin-top: 4px">
                关联合同时默认须已签署且至少一笔确认到账；先干活后付款可勾选下方例外。
              </div>
              <div v-if="initGate.contractOk && !initGate.paymentOk" class="init-defer-box">
                <el-checkbox v-model="initForm.payment_deferred">
                  无到款立项（先干活后付款，需负责人审批）
                </el-checkbox>
                <el-input
                  v-if="initForm.payment_deferred"
                  v-model="initForm.payment_deferred_reason"
                  type="textarea"
                  :rows="2"
                  maxlength="500"
                  show-word-limit
                  placeholder="必填：说明客户约定或业务原因；提交后进审批中心，通过后才能进计划；结项仍须回款收齐"
                  style="margin-top: 8px"
                />
              </div>
            </template>
          </el-form-item>
        </section>
        <section class="form-block">
          <h3><span>2</span>项目信息</h3>
          <el-form-item label="项目名称 / 目标" prop="name">
            <el-input v-model="initForm.name" placeholder="项目目标简述" />
          </el-form-item>
          <el-form-item label="交付范围摘要" prop="scope_desc">
            <el-input v-model="initForm.scope_desc" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="建议项目负责人" prop="manager_id">
            <el-select
              v-model="initForm.manager_id"
              filterable
              remote
              :remote-method="searchEmployees"
              :loading="empLoading"
              style="width: 100%"
            >
              <el-option
                v-for="e in employees"
                :key="e.id"
                :label="e.real_name || e.username"
                :value="e.id"
              />
            </el-select>
          </el-form-item>
          <div class="init-date-row">
            <el-form-item label="计划开始">
              <el-date-picker v-model="initForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
            <el-form-item label="计划结束">
              <el-date-picker v-model="initForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </div>
        </section>
        <section class="form-block">
          <h3><span>3</span>资源安排</h3>
          <el-form-item label="所需部门" required>
            <div class="role-assign-list">
              <div class="role-assign-head">
                <span class="role-col-dept">部门</span>
                <span class="role-col-user">建议对接人</span>
                <span class="role-col-hours">计划投入(h)</span>
                <span class="role-col-action" />
              </div>
              <div v-for="(row, idx) in initForm.resource_roles" :key="idx" class="role-assign-row">
                <el-select
                  v-model="row.role_name"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择飞书部门"
                  class="role-col-dept"
                  @change="onRoleNameChange(row)"
                >
                  <el-option
                    v-for="r in roleOptions"
                    :key="r.role_name"
                    :label="roleOptionLabel(r)"
                    :value="r.role_name"
                  />
                </el-select>
                <el-select
                  v-model="row.suggested_user_id"
                  filterable
                  clearable
                  :disabled="!row.role_name"
                  :placeholder="row.role_name ? '可选，指定对接人' : '请先选部门'"
                  class="role-col-user"
                >
                  <el-option
                    v-for="m in membersForRole(row.role_name)"
                    :key="m.id"
                    :label="memberLabel(m)"
                    :value="m.id"
                    :disabled="isSuggestedUserTaken(m.id, idx)"
                  />
                </el-select>
                <el-input-number
                  v-model="row.planned_hours"
                  :min="1"
                  :max="9999"
                  :precision="0"
                  controls-position="right"
                  class="role-col-hours"
                />
                <el-button
                  class="role-col-action"
                  text
                  type="danger"
                  :disabled="initForm.resource_roles.length <= 1"
                  @click="removeRoleRow(idx)"
                >
                  移除
                </el-button>
              </div>
              <el-button type="primary" link @click="addRoleRow">+ 添加部门</el-button>
            </div>
            <div class="sub" style="margin-top: 6px">
              计划投入合计
              <b>{{ initResourceHoursTotal }}h</b>
              ，后续任务拆解的计划工时不可超过此预算。
              {{ roleOptionsHint || '指定对接人后，提交由该部门确认投入。' }}
            </div>
          </el-form-item>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="initVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreateProject">提交立项申请</el-button>
      </template>
    </el-dialog>

    <!-- 计划节点弹窗 -->
    <el-dialog
      v-model="msVisible"
      width="560px"
      destroy-on-close
      append-to-body
      class="claim-dialog ms-dialog"
    >
      <template #header>
        <div>
          <small class="dialog-eyebrow">计划编排</small>
          <h3 class="dialog-title">添加计划节点</h3>
        </div>
      </template>
      <p class="dialog-flow-hint">
        现在只定义节点与验收标准；确认基线进入执行后，再挂任务、交证据、算进度
      </p>
      <el-form class="ms-dialog-form" :model="msForm" label-position="top">
        <section class="form-block">
          <h3><span>1</span>节点是什么</h3>
          <el-form-item label="节点名称" required>
            <el-input
              v-model="msForm.name"
              maxlength="80"
              show-word-limit
              placeholder="如：需求确认、UAT 验收、正式上线"
            />
          </el-form-item>
          <div class="ms-meta-row">
            <el-form-item label="计划开始">
              <el-date-picker
                v-model="msForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="计划结束">
              <el-date-picker
                v-model="msForm.deadline"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                style="width: 100%"
              />
            </el-form-item>
          </div>
          <el-form-item label="责任角色">
            <el-select
              v-model="msForm.role"
              filterable
              allow-create
              default-first-option
              clearable
              :loading="resourceLoading"
              placeholder="从本项目资源安排选择"
              style="width: 100%"
            >
              <el-option
                v-for="opt in planMilestoneOwnerOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <div class="ms-owner-opt">
                  <span>{{ opt.label }}</span>
                  <small>{{ opt.hint }}</small>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <p class="sub ms-block-tip">
            {{
              planMilestoneOwnerOptions.length > 1
                ? '选项来自立项时的资源安排（部门/对接人），与待确认资源联动；也可手动输入。'
                : '暂无本项目资源安排，可手动输入；资源确认后会自动出现可选对接人。'
            }}
          </p>
        </section>
        <section class="form-block">
          <h3><span>2</span>怎么算完成</h3>
          <el-form-item label="必交成果">
            <el-input
              v-model="msForm.deliverable"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              placeholder="本阶段要交付什么？如：签字版需求说明书、UAT 通过报告"
            />
          </el-form-item>
          <el-form-item label="证据要求">
            <el-input
              v-model="msForm.evidence"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              placeholder="验收时用什么证明完成？如：客户签字验收单、演示录像链接"
            />
            <div class="sub" style="margin-top: 6px">
              这里写的是「要求」，真正提交证据在节点推进时完成，不是现在上传。
            </div>
          </el-form-item>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="msVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAddMilestone">添加节点</el-button>
      </template>
    </el-dialog>

    <!-- 制定执行基线 -->
    <el-dialog
      v-model="baselineVisible"
      width="680px"
      destroy-on-close
      class="claim-dialog"
    >
      <template #header>
        <div>
          <small class="dialog-eyebrow">计划基线</small>
          <h3 class="dialog-title">制定项目执行基线</h3>
        </div>
      </template>
      <div class="form-block">
        <h3><span>1</span>基线范围</h3>
        <el-form label-width="100px">
          <el-form-item label="项目">
            <el-input :model-value="baselineProjectLabel" disabled />
          </el-form-item>
          <el-form-item label="计划周期">
            <el-input :model-value="baselinePeriodLabel" disabled />
          </el-form-item>
          <el-form-item label="基线说明" required>
            <el-input
              v-model="baselineNote"
              type="textarea"
              :rows="3"
              placeholder="以已确认需求范围与客户验收口径作为执行基线。"
            />
          </el-form-item>
        </el-form>
      </div>
      <div class="form-block">
        <div class="baseline-section-head">
          <h3><span>2</span>计划节点（可选）</h3>
          <el-button
            v-if="canManagePlan"
            type="primary"
            link
            @click="openMilestoneFromBaseline"
          >
            ＋ 添加节点
          </el-button>
        </div>
        <div class="plan-check-list">
          <div v-for="row in baselineMilestoneChecks" :key="row.name" class="plan-check-row">
            <span :class="{ ok: row.ok }">{{ row.ok ? '✓' : '⚠' }} {{ row.name }}</span>
            <b>{{ row.detail }}</b>
          </div>
          <div v-if="!baselineMilestoneChecks.length" class="baseline-node-empty">
            <p>可不添加，确认后按任务推进；需要分阶段验收时，在这里直接加节点。</p>
          </div>
        </div>
      </div>
      <div class="form-block">
        <h3><span>3</span>发布检查</h3>
        <div class="plan-check-list">
          <div class="plan-check-row">
            <span :class="{ ok: baselineReleaseChecks.rolesOk, muted: !milestones.length }">
              {{
                !milestones.length
                  ? 'ⓘ 推进方式'
                  : baselineReleaseChecks.rolesOk
                    ? '✓ 项目角色'
                    : '⚠ 项目角色'
              }}
            </span>
            <b>{{
              !milestones.length
                ? '无节点：确认后去任务工时拆任务'
                : baselineReleaseChecks.rolesOk
                  ? '责任归属完整'
                  : '请给节点补齐责任角色'
            }}</b>
          </div>
          <div class="plan-check-row">
            <span :class="{ ok: baselineReleaseChecks.tasks }">
              {{ baselineReleaseChecks.tasks ? '✓' : 'ⓘ' }} 任务与工时
            </span>
            <b>{{ baselineReleaseChecks.tasks ? '已有计划工时' : '可确认后再在任务工时中拆解' }}</b>
          </div>
          <div class="plan-check-row">
            <span>ⓘ 生效后修改</span>
            <b>必须走变更流程</b>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="baselineVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmBaseline">
          {{ milestones.length ? '提交基线确认' : '确认基线（按任务推进）' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 申请基线变更 -->
    <el-dialog v-model="changeVisible" width="640px" destroy-on-close class="claim-dialog">
      <template #header>
        <div>
          <small class="dialog-eyebrow">基线变更</small>
          <h3 class="dialog-title">申请项目变更</h3>
        </div>
      </template>
      <div class="form-block">
        <h3><span>1</span>变更内容</h3>
        <el-form label-width="120px">
          <el-form-item label="当前基线">
            <el-input :model-value="changeCurrentBaselineLabel" disabled />
          </el-form-item>
          <el-form-item label="变更类型" required>
            <el-select v-model="changeForm.type" style="width: 100%">
              <el-option label="范围变更" value="范围变更" />
              <el-option label="时间变更" value="时间变更" />
              <el-option label="资源变更" value="资源变更" />
              <el-option label="验收口径变更" value="验收口径变更" />
            </el-select>
          </el-form-item>
          <el-form-item label="变更原因" required>
            <el-input
              v-model="changeForm.reason"
              type="textarea"
              :rows="2"
              placeholder="说明客户要求、依赖变化或内部原因"
            />
          </el-form-item>
        </el-form>
      </div>
      <div class="form-block">
        <h3><span>2</span>影响评估</h3>
        <el-form label-width="120px">
          <el-form-item label="影响说明" required>
            <el-input
              v-model="changeForm.impact"
              type="textarea"
              :rows="2"
              placeholder="列明计划、资源、成本和验收影响"
            />
          </el-form-item>
          <el-form-item label="计划延期天数">
            <el-input-number v-model="changeForm.delayDays" :min="0" style="width: 100%" />
          </el-form-item>
          <el-form-item label="新增预计工时">
            <el-input-number v-model="changeForm.extraHours" :min="0" style="width: 100%" />
          </el-form-item>
        </el-form>
      </div>
      <div class="form-block">
        <h3><span>3</span>提交后规则</h3>
        <div class="plan-check-list">
          <div class="plan-check-row">
            <span class="ok">✓ 当前基线 {{ planProject?.baseline_version || 'V1' }}</span>
            <b>继续有效</b>
          </div>
          <div class="plan-check-row">
            <span>ⓘ 变更批准后</span>
            <b>生成新版本，不覆盖原基线</b>
          </div>
          <div class="plan-check-row">
            <span>ⓘ 涉及客户承诺</span>
            <b>需要商务责任人同步确认</b>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="changeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitChange">提交变更申请</el-button>
      </template>
    </el-dialog>

    <!-- 新增风险 -->
    <el-dialog v-model="riskVisible" width="560px" destroy-on-close class="claim-dialog">
      <template #header>
        <div>
          <small class="dialog-eyebrow">风险与问题</small>
          <h3 class="dialog-title">新增项目风险</h3>
        </div>
      </template>
      <el-form label-width="110px">
        <el-form-item label="风险事项" required>
          <el-input v-model="riskForm.title" placeholder="描述可能影响计划或验收的事项" />
        </el-form-item>
        <el-form-item label="影响等级" required>
          <el-select v-model="riskForm.level" style="width: 100%">
            <el-option label="高" value="高" />
            <el-option label="中" value="中" />
            <el-option label="低" value="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="责任角色" required>
          <el-select v-model="riskForm.role" style="width: 100%" allow-create filterable>
            <el-option label="项目负责人" value="项目负责人" />
            <el-option label="技术负责人" value="技术负责人" />
            <el-option label="商务责任人" value="商务责任人" />
          </el-select>
        </el-form-item>
        <el-form-item label="影响与应对" required>
          <el-input
            v-model="riskForm.response"
            type="textarea"
            :rows="3"
            placeholder="说明影响范围、触发条件和应对计划"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="riskVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRisk">保存风险</el-button>
      </template>
    </el-dialog>

    <!-- 任务弹窗 -->
    <el-dialog v-model="taskVisible" title="新建项目任务" width="560px" destroy-on-close>
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="100px" class="task-create-form">
        <el-form-item label="所属项目" prop="project_id">
          <el-select
            v-model="taskForm.project_id"
            filterable
            style="width: 100%"
            @change="onTaskProjectChange"
          >
            <el-option
              v-for="p in projects"
              :key="p.id"
              :label="`${p.project_no} · ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属节点" prop="milestone_id">
          <el-select
            v-model="taskForm.milestone_id"
            filterable
            clearable
            style="width: 100%"
            :placeholder="taskNodePlaceholder"
            :loading="taskMilestoneLoading"
            @change="onTaskMilestoneChange"
          >
            <el-option
              v-for="m in taskMilestoneOptions"
              :key="m.id"
              :label="m.status === 'done' ? `${m.name}（已完成）` : m.name"
              :value="m.id"
              :disabled="m.status === 'done'"
            />
          </el-select>
          <div v-if="taskMilestoneOptions.length && !openTaskMilestones.length" class="muted" style="margin-top: 6px">
            现有节点均已完成，不可再挂新任务；可不选节点直接创建，或回计划基线新增节点
          </div>
        </el-form-item>
        <el-form-item label="任务名称" prop="title">
          <el-input v-model="taskForm.title" placeholder="一句话说清要做什么" />
        </el-form-item>
        <el-form-item label="完成标准" prop="criteria">
          <el-input
            v-model="taskForm.criteria"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="怎样算完成，可验收"
          />
        </el-form-item>
        <el-form-item label="责任人">
          <el-select
            v-model="taskForm.assignee_id"
            filterable
            remote
            clearable
            placeholder="默认带节点责任人，可改"
            :remote-method="searchEmployees"
            style="width: 100%"
          >
            <el-option
              v-for="e in employees"
              :key="e.id"
              :label="e.real_name || e.username"
              :value="e.id"
            />
          </el-select>
          <div v-if="taskAssigneeHint" class="muted" style="margin-top: 6px">{{ taskAssigneeHint }}</div>
        </el-form-item>
        <el-form-item label="计划时间" prop="dateRange">
          <el-date-picker
            v-model="taskForm.dateRange"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            format="YYYY-MM-DD HH:mm"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            :default-time="taskDefaultTime"
            style="width: 100%"
            @change="onTaskDateRangeChange"
          />
        </el-form-item>
        <el-form-item label="计划工时" prop="planned_hours">
          <div class="task-hours-field">
            <el-input-number
              v-model="taskForm.planned_hours"
              :min="0"
              :precision="1"
              :max="taskHoursMax > 0 ? taskHoursMax : undefined"
              controls-position="right"
              class="task-hours-input"
            />
            <span class="task-hours-unit">小时</span>
          </div>
        </el-form-item>
        <p v-if="taskFormHoursHint" class="sub task-budget-hint" :class="{ 'hours-over': taskFormOverBudget }">
          {{ taskFormHoursHint }}
        </p>
      </el-form>
      <template #footer>
        <el-button @click="taskVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreateTask">创建</el-button>
      </template>
    </el-dialog>

    <!-- 完成证据：提交 / 审核 -->
    <el-dialog
      v-model="evidenceVisible"
      :title="evidenceDialogTitle"
      width="600px"
      destroy-on-close
      class="claim-dialog"
    >
      <template v-if="evidenceTarget">
        <div class="evidence-dialog-meta">
          <div>
            <small>计划节点</small>
            <b>{{ evidenceTarget.name }}</b>
          </div>
          <div>
            <small>关联任务</small>
            <b>{{ evidenceTarget.task_done || 0 }}/{{ evidenceTarget.task_total || 0 }}</b>
          </div>
          <div>
            <small>状态</small>
            <span class="ms-status-pill" :class="evidenceTone(evidenceTarget)">
              {{ evidenceStatusLabel(evidenceTarget) }}
            </span>
          </div>
        </div>

        <template v-if="!planInExecution">
          <div class="evidence-review-box">
            <small>必交成果</small>
            <p>{{ evidenceTarget.deliverable || '未填写' }}</p>
            <small style="display: block; margin-top: 10px">证据要求</small>
            <p>{{ evidenceTarget.remark || '未填写' }}</p>
          </div>
          <p class="muted" style="margin: 12px 0 0">
            当前仍在计划阶段。确认基线进入执行后，再提交完成证据并计入进度。
          </p>
        </template>
        <template v-else-if="evidenceMode === 'review'">
          <div v-if="evidenceTarget.remark" class="evidence-review-box" style="margin-bottom: 10px">
            <small>证据要求</small>
            <p>{{ evidenceTarget.remark }}</p>
          </div>
          <div class="evidence-review-box">
            <small>完成说明</small>
            <p>{{ evidenceTarget.evidence || '尚未提交' }}</p>
            <template v-if="evidenceTarget.evidence_link">
              <small style="display: block; margin-top: 10px">相关链接</small>
              <p>
                <a :href="evidenceTarget.evidence_link" target="_blank" rel="noopener">
                  {{ evidenceTarget.evidence_link }}
                </a>
              </p>
            </template>
            <template v-if="evidenceTarget.evidence_attachment">
              <small style="display: block; margin-top: 10px">附件</small>
              <AttachmentPreview
                :filename="evidenceTarget.evidence_attachment"
                :path="evidenceTarget.evidence_attachment_path"
                size="md"
              />
            </template>
            <small v-if="evidenceTarget.evidence_reject_reason" class="evidence-reject">
              上次驳回：{{ evidenceTarget.evidence_reject_reason }}
            </small>
            <small v-else-if="evidenceTarget.evidence_confirmed_by_name" class="evidence-ok">
              {{ evidenceTarget.evidence_confirmed_by_name }} 已确认
            </small>
          </div>
          <p class="muted" style="margin: 12px 0 0">
            {{ evidenceTarget.next_action || '确认后，若无未完成关联任务将自动完成节点。' }}
          </p>
        </template>
        <template v-else>
          <div v-if="evidenceTarget.remark" class="evidence-review-box" style="margin-bottom: 12px">
            <small>证据要求</small>
            <p>{{ evidenceTarget.remark }}</p>
          </div>
          <p class="muted" style="margin: 0 0 12px">
            提交后由项目负责人确认。请填写说明，并至少提供链接或附件其一。
          </p>
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="完成说明" required>
              <el-input
                v-model="evidenceDraft"
                type="textarea"
                :rows="3"
                maxlength="1000"
                show-word-limit
                placeholder="对照证据要求，说明本节点已完成内容"
              />
            </el-form-item>
            <el-form-item label="相关链接">
              <el-input
                v-model="evidenceLinkDraft"
                placeholder="https:// 文档 / 评审纪要 / 测试报告链接"
              />
            </el-form-item>
            <el-form-item label="附件">
              <div class="accept-attach" :class="{ uploaded: !!evidenceAttachName }">
                <template v-if="evidenceAttachName">
                  <AttachmentPreview
                    :filename="evidenceAttachName"
                    :path="evidenceAttachPath || evidenceAttachPreviewUrl"
                    size="md"
                  />
                  <div class="accept-attach-actions">
                    <a
                      v-if="evidenceAttachPreviewUrl"
                      :href="evidenceAttachPreviewUrl"
                      target="_blank"
                      rel="noopener"
                    >
                      打开查看
                    </a>
                    <button type="button" class="text-link" @click="triggerEvidenceUpload">
                      重新选择
                    </button>
                    <button type="button" class="text-link" @click="clearEvidenceAttachment">
                      移除
                    </button>
                  </div>
                </template>
                <button v-else type="button" class="upload-box" @click="triggerEvidenceUpload">
                  <b>上传截图 / 报告 / 确认材料</b>
                  <small>支持 PDF、图片、Word、Excel、PPT、TXT · 单文件不超过 20MB</small>
                </button>
              </div>
              <input
                ref="evidenceFileRef"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
                style="display: none"
                @change="onEvidenceFileChange"
              />
            </el-form-item>
          </el-form>
          <p
            v-if="evidenceTarget.evidence_reject_reason"
            class="evidence-reject"
            style="margin-top: 8px"
          >
            驳回原因：{{ evidenceTarget.evidence_reject_reason }}
          </p>
        </template>
      </template>
      <template #footer>
        <el-button @click="evidenceVisible = false">{{ planInExecution ? '取消' : '关闭' }}</el-button>
        <template v-if="planInExecution && evidenceTarget && evidenceMode === 'review' && canConfirmEvidence(evidenceTarget)">
          <el-button :loading="saving" @click="rejectEvidence(evidenceTarget)">驳回</el-button>
          <el-button type="primary" :loading="saving" @click="confirmEvidence(evidenceTarget)">
            确认证据
          </el-button>
        </template>
        <template v-else-if="planInExecution && evidenceMode === 'review'">
          <el-button type="primary" @click="evidenceMode = 'fill'">修改并重提</el-button>
        </template>
        <el-button
          v-else-if="planInExecution"
          type="primary"
          :loading="saving || uploadingEvidence"
          @click="submitMilestoneEvidence"
        >
          提交证据
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="completeVisible" title="完成任务" width="480px" destroy-on-close>
      <p class="muted" style="margin: 0 0 12px" v-if="completeTarget">
        {{ completeTarget.title }} · 计划工时 {{ formatHours(completeTarget.planned_hours) }}h
      </p>
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="实际工时" required>
          <el-input-number
            v-model="completeActualHours"
            :min="0"
            :precision="1"
            :step="0.5"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onConfirmCompleteTask">确认完成</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="taskScheduleVisible"
      :title="taskScheduleTitle"
      size="520px"
      destroy-on-close
    >
      <p class="muted" style="margin: 0 0 12px">
        「完成」指挂到本任务上、状态为已完成的排期场次；排期填的工时进项目工时单，不会自动加到本任务「实际工时」。
      </p>
      <el-table :data="taskSchedules" v-loading="taskSchedulesLoading" stripe empty-text="暂无挂到本任务的人员档期">
        <el-table-column prop="title" label="排期" min-width="120" show-overflow-tooltip />
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatScheduleRange(row) }}</template>
        </el-table-column>
        <el-table-column prop="employee_name" label="人员" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="scheduleStatusTag(row)">
              {{ SCHEDULE_STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="工时" width="70">
          <template #default="{ row }">
            {{ row.actual_hours != null ? `${formatHours(row.actual_hours)}h` : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="" width="60" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/schedules/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 验收弹窗 -->
    <el-dialog
      v-model="leftoverVisible"
      width="560px"
      destroy-on-close
      class="claim-dialog"
    >
      <template #header>
        <div>
          <small class="dialog-eyebrow">验收与结项</small>
          <h3 class="dialog-title">
            {{ leftoverCanClose ? '关闭遗留问题' : '遗留问题' }}
          </h3>
        </div>
      </template>
      <template v-if="leftoverRow">
        <p class="dialog-flow-hint">
          项目：{{ leftoverRow.name }}（{{ leftoverRow.project_no }}）
        </p>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="状态">
            <el-tag
              size="small"
              :type="leftoverRow.leftover_closed ? 'success' : 'warning'"
            >
              {{ leftoverRow.leftover_closed ? '已关闭' : '未关闭' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="验收结论">
            {{ leftoverRow.acceptance_conclusion || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="遗留内容">
            <div class="leftover-content">{{ leftoverRow.leftover_summary }}</div>
          </el-descriptions-item>
        </el-descriptions>
        <p v-if="leftoverCanClose" class="dialog-flow-hint" style="margin-top: 12px">
          确认遗留事项已处理完毕后，再关闭；关闭后才可结项。
        </p>
      </template>
      <template #footer>
        <el-button @click="leftoverVisible = false">
          {{ leftoverCanClose ? '取消' : '关闭' }}
        </el-button>
        <el-button link type="primary" @click="leftoverRow && goDetail(leftoverRow)">
          打开项目详情
        </el-button>
        <el-button
          v-if="leftoverCanClose"
          type="primary"
          :loading="saving"
          @click="confirmCloseLeftover"
        >
          确认关闭遗留
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="acceptVisible" title="发起内部验收" width="640px" destroy-on-close>
      <p class="dialog-flow-hint">
        提交后进入审批中心；审批通过 → 财务核对 → 结项。有条件通过必须写清遗留问题。
      </p>
      <el-form ref="acceptFormRef" :model="acceptForm" :rules="acceptRules" label-width="100px">
        <el-form-item v-if="acceptProjectLocked" label="验收项目">
          <el-input :model-value="acceptProjectLabel" disabled />
        </el-form-item>
        <el-form-item v-else label="验收项目" prop="project_id">
          <el-select
            v-model="acceptForm.project_id"
            filterable
            placeholder="选择待验收项目"
            style="width: 100%"
          >
            <el-option
              v-for="p in acceptanceCandidates"
              :key="p.id"
              :label="`${p.project_no} · ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <div class="accept-meta-row">
          <el-form-item label="验收结果" prop="result">
            <el-select v-model="acceptForm.result" style="width: 100%" @change="onAcceptResultChange">
              <el-option label="验收通过" value="pass" />
              <el-option label="有条件通过" value="conditional" />
            </el-select>
          </el-form-item>
          <el-form-item label="验收日期" prop="accepted_at">
            <el-date-picker
              v-model="acceptForm.accepted_at"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
        </div>

        <div class="accept-meta-row">
          <el-form-item label="验收方式" prop="method">
            <el-select v-model="acceptForm.method" style="width: 100%">
              <el-option label="内部验收单" value="内部验收单" />
              <el-option label="部门负责人确认" value="部门负责人确认" />
              <el-option label="项目评审会议纪要" value="项目评审会议纪要" />
              <el-option label="其他可追溯方式" value="其他可追溯方式" />
            </el-select>
          </el-form-item>
          <el-form-item label="提交人">
            <el-input :model-value="userStore.displayName" disabled />
          </el-form-item>
        </div>

        <el-form-item label="验收结论" prop="conclusion">
          <el-input
            v-model="acceptForm.conclusion"
            type="textarea"
            :rows="2"
            placeholder="说明是否达到交付标准、主要验收意见"
          />
        </el-form-item>
        <el-form-item
          label="遗留问题"
          prop="leftover_summary"
          :required="acceptForm.result === 'conditional'"
        >
          <el-input
            v-model="acceptForm.leftover_summary"
            type="textarea"
            :rows="2"
            :placeholder="
              acceptForm.result === 'conditional'
                ? '必填：遗留事项、责任人、完成期限'
                : '无遗留可留空；有遗留请写清事项、责任人和期限'
            "
          />
        </el-form-item>
        <el-form-item label="验收附件" prop="attachment">
          <div class="accept-attach" :class="{ uploaded: !!acceptForm.attachment }">
            <template v-if="acceptForm.attachment && acceptAttachUrl">
              <div class="accept-attach-preview">
                <el-image
                  v-if="acceptAttachKind === 'image'"
                  :src="acceptAttachUrl"
                  :preview-src-list="[acceptAttachUrl]"
                  fit="contain"
                  class="accept-attach-image"
                  preview-teleported
                />
                <iframe
                  v-else-if="acceptAttachKind === 'pdf'"
                  :src="acceptAttachUrl"
                  class="accept-attach-pdf"
                  title="验收附件预览"
                />
                <div v-else class="accept-doc-card">
                  <span class="accept-doc-ext">{{ acceptAttachExt }}</span>
                  <div>
                    <strong>{{ acceptForm.attachment }}</strong>
                    <small>
                      {{ acceptAttachKindLabel }}
                      <template v-if="acceptAttachSizeLabel"> · {{ acceptAttachSizeLabel }}</template>
                    </small>
                  </div>
                </div>
              </div>
              <div class="accept-attach-actions">
                <a :href="acceptAttachUrl" target="_blank" rel="noopener">打开查看</a>
                <button type="button" class="text-link" @click="triggerAcceptUpload">重新选择</button>
              </div>
            </template>
            <button v-else type="button" class="upload-box" @click="triggerAcceptUpload">
              <b>上传内部验收单或评审材料</b>
              <small>支持 PDF、图片、Word、Excel、PPT、TXT · 单文件不超过 20MB</small>
            </button>
          </div>
          <input
            ref="acceptFileRef"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt"
            style="display: none"
            @change="onAcceptFileChange"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="acceptVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAccept">提交审批</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMatchMedia } from '@/composables/useMatchMedia'
import {
  ACCEPTANCE_RESULT_LABEL,
  HEALTH_LABEL,
  PROJECT_STATUS_LABEL,
  useBusinessTypes,
  TASK_STATUS_LABEL,
  acceptProject,
  addMilestone,
  deleteMilestone,
  completeProject,
  confirmProjectResource,
  createProject,
  createProjectTask,
  fetchProjectDetail,
  fetchProjectHoursBudget,
  fetchProjectResourceNeeds,
  fetchProjectStats,
  fetchProjectTaskStats,
  fetchProjectTasks,
  fetchProjects,
  fetchResourceRoleOptions,
  setProjectFinanceCheck,
  setProjectLeftoverClosed,
  startProjectPlanning,
  startProjectExecuting,
  updateMilestone,
  reviewMilestoneEvidence,
  updateProject,
  updateProjectTask,
  type Project,
  type ProjectHoursBudget,
  type ProjectMilestone,
  type ProjectResourceNeed,
  type ProjectStats,
  type ProjectTask,
  type ProjectTaskStats,
  type ResourceRoleMember,
  type ResourceRoleOption,
} from '@/api/projects'
import {
  fetchDirectoryContracts,
  fetchDirectoryPeople,
  type DirectoryContract,
  type DirectoryPerson,
} from '@/api/directory'
import { fetchSchedules, SCHEDULE_STATUS_LABEL, type Schedule } from '@/api/schedules'
import {
  fetchTickets,
  TICKET_STATUS_LABEL,
  type Ticket,
} from '@/api/tickets'
import { useUserStore } from '@/stores/user'
import { uploadFile } from '@/api/uploads'
import AttachmentPreview from '@/components/common/AttachmentPreview.vue'

const isCompact = useMatchMedia('(max-width: 768px)')
const { businessTypeOptions, businessTypeLabel } = useBusinessTypes()

type TabKey = 'portfolio' | 'initiation' | 'execute' | 'acceptance'
type OverviewMode = 'list' | 'board'
type ExecuteMode = 'plan' | 'tasks'
type Workbench = 'portfolio' | 'delivery'

const ALL_TABS: { key: TabKey; label: string }[] = [
  { key: 'portfolio', label: '项目台账' },
  { key: 'initiation', label: '交接与立项' },
  { key: 'execute', label: '执行' },
  { key: 'acceptance', label: '验收与收尾' },
]

const deliveryTabs = ALL_TABS.filter((t) => t.key !== 'portfolio')

/** 交付类型 → 匹配飞书部门名的关键词 */
const DEPT_HINTS: Record<string, string[]> = {
  ai_custom: ['讲师', '技术', '交付', '研发', '产品', 'AI'],
  ai_product: ['讲师', '交付', '实施'],
  media_ops: ['新媒体', '运营', '内容'],
  other: ['交付', '项目'],
}

type RoleAssignRow = {
  role_name: string
  suggested_user_id?: number
  planned_hours: number
}

const DEFAULT_ROLE_HOURS = 40

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const canSubmitAcceptance = computed(() =>
  userStore.hasAnyPermission('project:accept_submit', 'project:manage'),
)
const canSubmitFinanceCheck = computed(() =>
  userStore.hasAnyPermission('project:finance_submit', 'project:manage'),
)
const canCompleteProject = computed(() =>
  userStore.hasAnyPermission('project:complete', 'project:manage'),
)

/** 路径仍区分深链：/projects=台账，/projects/delivery=交付子页 */
const workbench = computed<Workbench>(() =>
  route.path.startsWith('/projects/delivery') ? 'delivery' : 'portfolio',
)
const workbenchDesc = computed(() => {
  if (tab.value === 'portfolio') return '同一批项目用列表或看板总览；点进去看档案。交付干活请切右侧三个 Tab。'
  if (tab.value === 'initiation') return '合同交接与立项发起；通过后进入执行做计划基线与任务。'
  if (tab.value === 'execute') return '计划基线、任务工时与日常推进；这是交付主战场。'
  return '内部验收、财务核对与结项收尾。'
})

const tab = ref<TabKey>('portfolio')
const overviewMode = ref<OverviewMode>('list')
const executeMode = ref<ExecuteMode>('plan')
const loading = ref(false)
const saving = ref(false)
const projects = ref<Project[]>([])
const projectTotal = ref(0)
const stats = ref<ProjectStats | null>(null)
const keyword = ref('')
const statusFilter = ref<string | undefined>()
type PortfolioStatKey = 'executing' | 'accepting' | 'accepted' | 'completed'
const portfolioStat = ref<PortfolioStatKey | null>(null)
const portfolioType = ref<string | undefined>()

const planProjectId = ref<number | undefined>()
const planProject = ref<Project | null>(null)
const milestones = ref<ProjectMilestone[]>([])
const planLoading = ref(false)
const planSchedules = ref<Schedule[]>([])
const planSchedulesLoading = ref(false)
const taskHours = ref({ planned: 0, actual: 0 })
const hoursBudget = ref<ProjectHoursBudget | null>(null)
const taskFormBudget = ref<ProjectHoursBudget | null>(null)

const tasks = ref<ProjectTask[]>([])
const taskStats = ref<ProjectTaskStats | null>(null)
const taskLoading = ref(false)
const taskKeyword = ref('')
const taskStatus = ref<string | undefined>()
const taskProjectFilter = ref<number | undefined>()
const linkedTickets = ref<Ticket[]>([])
const linkedTicketsLoading = ref(false)
const linkedTicketsTotal = ref(0)
const linkedTicketsPanelRef = ref<HTMLElement | null>(null)
const taskProjectFilterName = computed(() => {
  if (!taskProjectFilter.value) return ''
  const hit = tasks.value.find((t) => t.project_id === taskProjectFilter.value)
  if (hit?.project_name) return hit.project_name
  const fromList = projects.value.find((p) => p.id === taskProjectFilter.value)
  return fromList?.name || ''
})
const taskScheduleVisible = ref(false)
const taskSchedulesLoading = ref(false)
const taskSchedules = ref<Schedule[]>([])
const taskScheduleTarget = ref<ProjectTask | null>(null)
const taskScheduleTitle = computed(() => {
  const t = taskScheduleTarget.value
  if (!t) return '人员档期'
  return `${t.task_no || ''} · ${t.title}`.trim()
})

const initVisible = ref(false)
const resourceVisible = ref(false)
const resourceLoading = ref(false)
const resourceNeeds = ref<ProjectResourceNeed[]>([])
const resourcePendingCount = ref(0)
const resourceTarget = ref<ProjectResourceNeed | null>(null)
const msVisible = ref(false)
const baselineVisible = ref(false)
const changeVisible = ref(false)
const riskVisible = ref(false)
const baselineNote = ref('以已确认需求范围与客户验收口径作为执行基线。')
const planRisks = ref<PlanRiskItem[]>([])
const planChanges = ref<PlanChangeItem[]>([])
const planBaselineMeta = ref<PlanBaselineMeta | null>(null)

type PlanRiskItem = {
  id: string
  title: string
  level: '高' | '中' | '低'
  role: string
  response: string
}
type PlanChangeItem = {
  id: string
  code: string
  title: string
  status: string
  type: string
}
type PlanBaselineMeta = {
  locked: boolean
  note: string
  effectiveAt: string
  version: string
}

const changeForm = reactive({
  type: '范围变更',
  reason: '',
  impact: '',
  delayDays: 2,
  extraHours: 24,
})
const riskForm = reactive({
  title: '',
  level: '高' as '高' | '中' | '低',
  role: '项目负责人',
  response: '',
})
const taskVisible = ref(false)
const evidenceVisible = ref(false)
const evidenceMode = ref<'fill' | 'review'>('fill')
const evidenceTarget = ref<ProjectMilestone | null>(null)
const evidenceDraft = ref('')
const evidenceLinkDraft = ref('')
const evidenceAttachName = ref('')
const evidenceAttachPath = ref('')
const evidenceAttachPreviewUrl = ref('')
const evidenceFileRef = ref<HTMLInputElement | null>(null)
const uploadingEvidence = ref(false)
const evidenceAttachExt = computed(() => {
  const name = evidenceAttachName.value || ''
  const ext = name.includes('.') ? name.split('.').pop() : ''
  return (ext || 'FILE').toUpperCase()
})
const taskMilestoneOptions = ref<ProjectMilestone[]>([])
const openTaskMilestones = computed(() =>
  taskMilestoneOptions.value.filter((m) => m.status !== 'done'),
)
const taskNodePlaceholder = computed(() => {
  if (!taskMilestoneOptions.value.length) return '无节点时可直接建任务'
  if (!openTaskMilestones.value.length) return '节点均已完成，可不选'
  return '请选择计划节点'
})
const taskMilestoneLoading = ref(false)
/** 从计划节点「去拆任务」带入的节点 */
const preferredTaskMilestoneId = ref<number | undefined>()
const taskAssigneeHint = ref('')
const completeVisible = ref(false)
const completeTarget = ref<ProjectTask | null>(null)
const completeActualHours = ref(0)
const acceptVisible = ref(false)
const leftoverVisible = ref(false)
const leftoverCanClose = ref(false)
const leftoverRow = ref<Project | null>(null)
const initFormRef = ref<FormInstance>()
const taskFormRef = ref<FormInstance>()
const acceptFormRef = ref<FormInstance>()
const acceptFileRef = ref<HTMLInputElement | null>(null)
const acceptAttachUrl = ref('')
const acceptAttachSize = ref(0)
const contractLoading = ref(false)
const empLoading = ref(false)
const contractOptions = ref<DirectoryContract[]>([])
const employees = ref<DirectoryPerson[]>([])
const roleOptions = ref<ResourceRoleOption[]>([])
const roleEmployees = ref<ResourceRoleMember[]>([])
const roleOptionsHint = ref('')

const initForm = reactive({
  contract_id: undefined as number | undefined,
  project_type: 'ai_custom',
  name: '',
  scope_desc: '',
  manager_id: undefined as number | undefined,
  start_date: '',
  end_date: '',
  payment_deferred: false,
  payment_deferred_reason: '',
  resource_roles: [] as RoleAssignRow[],
})
const initRules: FormRules = {
  name: [{ required: true, message: '请填写项目目标', trigger: 'blur' }],
  scope_desc: [{ required: true, message: '请填写交付范围', trigger: 'blur' }],
  manager_id: [{ required: true, message: '请选择负责人', trigger: 'change' }],
}

const resourceForm = reactive({
  action: 'accept' as 'accept' | 'adjust' | 'reject',
  confirmed_user_id: undefined as number | undefined,
  planned_hours: 40,
  note: '',
})

const resourceActionOptions = [
  {
    value: 'accept' as const,
    title: '确认投入',
    desc: '按建议成员与计划投入直接确认',
  },
  {
    value: 'adjust' as const,
    title: '调整后确认',
    desc: '更换成员或修改投入小时后再确认',
  },
  {
    value: 'reject' as const,
    title: '暂不接受',
    desc: '说明冲突原因并退回协调',
  },
]

const resourceSubmitLabel = computed(() => {
  if (resourceForm.action === 'reject') return '退回协调'
  if (resourceForm.action === 'adjust') return '调整并确认'
  return '确认投入'
})

const msForm = reactive({
  name: '',
  role: '',
  start_date: '',
  deadline: '',
  deliverable: '',
  evidence: '',
})

/** 与排期会议一致：工作时段 08:00-19:00 */
const WORK_HOUR_START = 8
const WORK_HOUR_END = 19
const taskDefaultTime: [Date, Date] = [
  new Date(2000, 0, 1, WORK_HOUR_START, 0, 0),
  new Date(2000, 0, 1, WORK_HOUR_END, 0, 0),
]

const taskForm = reactive({
  project_id: undefined as number | undefined,
  milestone_id: undefined as number | undefined,
  title: '',
  criteria: '',
  assignee_id: undefined as number | undefined,
  dateRange: null as [string, string] | null,
  planned_hours: undefined as number | undefined,
})
const taskRules = computed<FormRules>(() => ({
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  milestone_id: openTaskMilestones.value.length
    ? [{ required: true, message: '请选择所属计划节点', trigger: 'change' }]
    : [],
  title: [{ required: true, message: '请填写任务名称', trigger: 'blur' }],
  criteria: [{ required: true, message: '请填写完成标准', trigger: 'blur' }],
  dateRange: [{ required: true, message: '请选择计划时间', trigger: 'change' }],
  planned_hours: [{ required: true, message: '请填写计划工时', trigger: 'blur' }],
}))

const acceptForm = reactive({
  project_id: undefined as number | undefined,
  result: 'pass',
  accepted_at: new Date().toISOString().slice(0, 10),
  method: '内部验收单',
  conclusion: '',
  leftover_summary: '',
  attachment: '',
  attachment_path: '',
})
const acceptProjectLocked = ref(false)
const acceptRules = computed<FormRules>(() => ({
  project_id: acceptProjectLocked.value
    ? []
    : [{ required: true, message: '请选择项目', trigger: 'change' }],
  result: [{ required: true, message: '请选择结果', trigger: 'change' }],
  accepted_at: [{ required: true, message: '请选择日期', trigger: 'change' }],
  method: [{ required: true, message: '请选择验收方式', trigger: 'change' }],
  conclusion: [{ required: true, message: '请填写验收结论', trigger: 'blur' }],
  leftover_summary:
    acceptForm.result === 'conditional'
      ? [{ required: true, message: '有条件通过须填写遗留问题', trigger: 'blur' }]
      : [],
  attachment: [{ required: true, message: '请上传验收附件', trigger: 'change' }],
}))
const acceptProjectLabel = computed(() => {
  const id = acceptForm.project_id
  if (!id) return '—'
  const p = projects.value.find((x) => x.id === id)
  return p ? `${p.project_no} · ${p.name}` : `项目 #${id}`
})

const portfolioStatCards = computed(() => [
  { key: 'executing' as const, label: '执行中', note: '交付推进中', count: stats.value?.executing ?? 0 },
  { key: 'accepting' as const, label: '待验收', note: '内部验收中', count: stats.value?.accepting ?? 0 },
  { key: 'accepted' as const, label: '待结项', note: '验收后收尾', count: stats.value?.accepted ?? 0 },
  { key: 'completed' as const, label: '已完成', note: '已结项归档', count: stats.value?.completed ?? 0 },
])

const listProjects = computed(() =>
  projects.value.filter((p) => !portfolioType.value || p.project_type === portfolioType.value),
)

const listProjectTotal = computed(() =>
  portfolioType.value ? listProjects.value.length : projectTotal.value,
)

const boardFiltered = computed(() =>
  listProjects.value.filter((p) => p.status !== 'terminated'),
)

const boardColumns = computed(() => {
  const defs = [
    { key: 'init', label: '待立项', color: '#8c8c8c', match: (s: string) => s === 'initiating' || s === 'planning' },
    { key: 'exec', label: '执行中', color: '#1677ff', match: (s: string) => s === 'executing' },
    { key: 'acc', label: '待内部验收', color: '#faad14', match: (s: string) => s === 'accepting' },
    { key: 'close', label: '待结项', color: '#fa8c16', match: (s: string) => s === 'accepted' },
    { key: 'done', label: '已完成', color: '#52c41a', match: (s: string) => s === 'completed' },
  ]
  return defs.map((d) => ({
    ...d,
    items: boardFiltered.value.filter((p) => d.match(p.status)),
  }))
})

const initiatingProjects = computed(() =>
  projects.value.filter((p) => p.status === 'initiating' || p.status === 'planning'),
)

const deliverableDone = computed(
  () => milestones.value.filter((m) => m.deliverable && m.status === 'done').length,
)

const deliverablePending = computed(
  () => milestones.value.filter((m) => !m.deliverable || !String(m.deliverable).trim()).length,
)

const milestoneOverdueCount = computed(
  () => milestones.value.filter((m) => isMilestoneOverdue(m)).length,
)

const planMilestoneDoneCount = computed(
  () =>
    milestones.value.filter(
      (m) => m.status === 'done' && (m.evidence_status || 'none') === 'confirmed',
    ).length,
)

const planEvidencePendingCount = computed(
  () => milestones.value.filter((m) => (m.evidence_status || 'none') === 'pending').length,
)

const planNodesWithoutTaskCount = computed(
  () => milestones.value.filter((m) => !(m.task_total || 0)).length,
)

/** 与后端生命周期进度一致：规划期固定筹备进度，不按节点完成数直接拉满 */
const planEffectiveProgress = computed(() => {
  const p = Number(planProject.value?.progress || 0)
  return Math.min(Math.max(p, 0), 100)
})

const planInExecution = computed(() =>
  ['executing', 'accepting', 'accepted', 'completed'].includes(planProject.value?.status || ''),
)

const planProgressLabel = computed(() => {
  if (!planInExecution.value) return '筹备进度'
  return '执行进度'
})

const hoursUsage = computed(() => {
  const planned = Number(taskHours.value.planned || 0)
  const actual = Number(taskHours.value.actual || 0)
  if (!planned) return actual ? 100 : 0
  return Math.round((actual / planned) * 1000) / 10
})

const planRingCirc = 2 * Math.PI * 31
const planRingOffset = computed(() => {
  const p = Math.min(Math.max(Number(planProject.value?.progress || 0), 0), 100)
  return planRingCirc * (1 - p / 100)
})
const planRingOffsetEffective = computed(() => {
  const p = Math.min(Math.max(Number(planEffectiveProgress.value || 0), 0), 100)
  return planRingCirc * (1 - p / 100)
})

const planBaselineLocked = computed(() => !!planBaselineMeta.value?.locked)
const planExtrasOpen = ref(false)
const showPlanExtras = computed(
  () =>
    planRisks.value.length > 0 ||
    planChanges.value.length > 0 ||
    planSchedules.value.length > 0,
)

const planBaselineLabel = computed(() => {
  const ver = planProject.value?.baseline_version || 'V1'
  if (!planBaselineLocked.value) return `${ver}（未确认）`
  const pending = planChanges.value.some((c) => c.status === '审批中' || c.status === '待确认')
  return pending ? `${ver} · 有变更审批中` : `${ver}已生效`
})

const baselineProjectLabel = computed(() => {
  if (!planProject.value) return ''
  return `${planProject.value.project_no} · ${planProject.value.name}`
})

const baselinePeriodLabel = computed(() => {
  if (!planProject.value) return '待定'
  const a = formatShortDate(planProject.value.start_date)
  const b = formatShortDate(planProject.value.end_date)
  if (a === '—' && b === '—') return '待定'
  return `${a} 至 ${b}`
})

const changeCurrentBaselineLabel = computed(() => {
  const ver = planProject.value?.baseline_version || 'V1'
  const at = planBaselineMeta.value?.effectiveAt
  return at ? `${ver} · ${at}生效` : ver
})

const baselineMilestoneChecks = computed(() =>
  milestones.value.map((m) => {
    const hasDeliverable = !!(m.deliverable && String(m.deliverable).trim())
    const hasOwnerDate = !!(m.role && m.deadline)
    const hasEvidence = !!(m.evidence && String(m.evidence).trim())
    const ok = hasDeliverable && hasOwnerDate
    let detail = '成果与验收标准已填写'
    if (!hasDeliverable) detail = '请填写必交成果'
    else if (!hasOwnerDate) detail = '请填写负责人和计划日期'
    else if (!hasEvidence) detail = '依赖和完成证据建议补充'
    return { name: m.name, ok, detail }
  }),
)

const baselineReleaseChecks = computed(() => ({
  rolesOk:
    milestones.value.length === 0 || milestones.value.every((m) => !!m.role),
  tasks: Number(taskHours.value.planned || 0) > 0,
}))

function clipMilestoneRole(text: string, max = 50) {
  const t = text.trim()
  if (!t) return ''
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

/** 计划节点责任角色：联动本项目资源安排 + 项目负责人 */
const planMilestoneOwnerOptions = computed(() => {
  const opts: { value: string; label: string; hint: string }[] = []
  const seen = new Set<string>()
  const push = (value: string, label: string, hint: string) => {
    const v = clipMilestoneRole(value)
    if (!v || seen.has(v)) return
    seen.add(v)
    opts.push({ value: v, label, hint })
  }

  const project = planProject.value
  if (project?.manager_name) {
    push(
      `项目负责人 · ${project.manager_name}`,
      `项目负责人 · ${project.manager_name}`,
      '项目经理',
    )
  } else {
    push('项目负责人', '项目负责人', '项目经理')
  }

  const pid = planProjectId.value
  for (const need of resourceNeeds.value) {
    if (pid && need.project_id !== pid) continue
    const dept = (need.department_name || need.role_name || '').trim()
    if (!dept) continue
    const person = (need.confirmed_user_name || need.suggested_user_name || '').trim()
    const status =
      need.status === 'accepted'
        ? '已确认投入'
        : need.status === 'rejected'
          ? '已退回'
          : '待确认'
    if (person) {
      push(`${person} · ${dept}`, `${dept} · ${person}`, status)
    } else {
      push(dept, dept, `${status} · 对接人待指定`)
    }
  }
  return opts
})

const acceptanceRows = computed(() =>
  projects.value.filter((p) =>
    ['executing', 'accepting', 'accepted', 'completed'].includes(p.status),
  ),
)

const acceptanceCandidates = computed(() =>
  projects.value.filter(
    (p) =>
      (p.status === 'executing' || p.status === 'accepting') &&
      p.acceptance_approval_status !== 'pending',
  ),
)

function typeLabel(code?: string) {
  return businessTypeLabel(code)
}

function scheduleLabel(s?: string) {
  if (s === 'clear') return '无冲突'
  if (s === 'conflict') return '存在冲突'
  return '待检查'
}

function scheduleTagType(s?: string) {
  if (s === 'clear') return 'success'
  if (s === 'conflict') return 'danger'
  return 'warning'
}

function resourceStatusLabel(s?: string) {
  if (s === 'accepted') return '已确认'
  if (s === 'rejected') return '已拒绝'
  return '待确认'
}

function formatDate(v?: string | null) {
  if (!v) return ''
  return String(v).slice(0, 10)
}

function formatScheduleRange(row: Schedule) {
  const s = row.start_time ? new Date(row.start_time) : null
  const e = row.end_time ? new Date(row.end_time) : null
  if (!s || !e || Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return '—'
  const d = s.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  const st = s.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  const et = e.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${d} ${st}-${et}`
}

function scheduleStatusTag(row: Schedule) {
  if (row.has_conflict) return 'danger'
  if (row.status === 'completed') return 'success'
  if (row.status === 'cancelled') return 'info'
  if (row.status === 'in_progress' || row.status === 'pending') return 'warning'
  return ''
}

function formatShortDate(v?: string | null) {
  const d = formatDate(v)
  if (!d) return '—'
  const parts = d.split('-')
  if (parts.length === 3) return `${parts[1]}-${parts[2]}`
  return d
}

function isMilestoneOverdue(row: ProjectMilestone) {
  if (row.status === 'done' || !row.deadline) return false
  const due = new Date(`${formatDate(row.deadline)}T23:59:59`)
  return Number.isFinite(due.getTime()) && due.getTime() < Date.now()
}

function changeTone(status: string) {
  if (status === '已生效') return 'good'
  if (status === '审批中' || status === '待确认') return 'warn'
  return ''
}

function planLocalKey(projectId: number) {
  return `crm_plan_baseline_${projectId}`
}

function loadPlanLocal(projectId: number) {
  try {
    const raw = localStorage.getItem(planLocalKey(projectId))
    if (!raw) {
      planRisks.value = []
      planChanges.value = []
      planBaselineMeta.value = null
      return
    }
    const data = JSON.parse(raw) as {
      risks?: PlanRiskItem[]
      changes?: PlanChangeItem[]
      baseline?: PlanBaselineMeta | null
    }
    planRisks.value = data.risks || []
    planChanges.value = data.changes || []
    planBaselineMeta.value = data.baseline || null
  } catch {
    planRisks.value = []
    planChanges.value = []
    planBaselineMeta.value = null
  }
}

function savePlanLocal(projectId?: number | null) {
  const id = projectId ?? planProjectId.value
  if (!id) return
  localStorage.setItem(
    planLocalKey(id),
    JSON.stringify({
      risks: planRisks.value,
      changes: planChanges.value,
      baseline: planBaselineMeta.value,
    }),
  )
}

function formatRange(a?: string | null, b?: string | null) {
  if (!a && !b) return '—'
  return `${formatDate(a) || '?'} ~ ${formatDate(b) || '?'}`
}

function formatHours(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? (n % 1 === 0 ? String(n) : n.toFixed(1)) : '0'
}

const initResourceHoursTotal = computed(() =>
  initForm.resource_roles.reduce((s, r) => s + Number(r.planned_hours || 0), 0),
)

const taskHoursBudgetHint = computed(() => {
  if (!taskProjectFilter.value || !hoursBudget.value) return ''
  const b = hoursBudget.value
  return `资源承诺 ${formatHours(b.resource_budget_hours)}h · 任务计划 ${formatHours(b.task_planned_hours)}h · 剩余 ${formatHours(b.remaining_hours)}h`
})

const taskHoursMax = computed(() => {
  const budget = Number(taskFormBudget.value?.resource_budget_hours || 0)
  if (budget <= 0) return 0
  const remaining = Number(taskFormBudget.value?.remaining_hours || 0)
  return Math.max(0, Math.round(remaining * 10) / 10)
})

const taskFormOverBudget = computed(() => {
  const budget = Number(taskFormBudget.value?.resource_budget_hours || 0)
  if (budget <= 0) return false
  return Number(taskForm.planned_hours || 0) > taskHoursMax.value + 1e-9
})

const taskFormHoursHint = computed(() => {
  const b = taskFormBudget.value
  if (!b) return ''
  const budget = Number(b.resource_budget_hours || 0)
  if (budget <= 0) return '该项目尚未设置资源投入，创建任务后将无法与立项预算对照。'
  const remain = Number(b.remaining_hours || 0)
  if (taskFormOverBudget.value) {
    return `超出可拆额度：资源承诺 ${formatHours(budget)}h，已拆 ${formatHours(b.task_planned_hours)}h，最多还可填 ${formatHours(remain)}h。`
  }
  return `资源承诺 ${formatHours(budget)}h · 已拆任务 ${formatHours(b.task_planned_hours)}h · 本任务最多 ${formatHours(remain)}h。`
})

async function loadHoursBudget(projectId?: number | null) {
  if (!projectId) {
    hoursBudget.value = null
    return
  }
  try {
    const { data } = await fetchProjectHoursBudget(projectId)
    hoursBudget.value = data
  } catch {
    hoursBudget.value = null
  }
}

async function loadTaskFormBudget(projectId?: number | null) {
  if (!projectId) {
    taskFormBudget.value = null
    return
  }
  try {
    const { data } = await fetchProjectHoursBudget(projectId)
    taskFormBudget.value = data
  } catch {
    taskFormBudget.value = null
  }
}

function formatRate(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? (n % 1 === 0 ? String(n) : n.toFixed(1)) : '0'
}

function paymentOk(row: Project) {
  return !!(row.payment_received_ok ?? row.payment_verified)
}

function deferPending(row: Project) {
  return !!(row.payment_deferred && row.payment_defer_status === 'pending' && !paymentOk(row))
}

function deferApproved(row: Project) {
  return !!(row.payment_deferred && row.payment_defer_status === 'approved')
}

function deferRejected(row: Project) {
  return !!(row.payment_deferred && row.payment_defer_status === 'rejected' && !paymentOk(row))
}

function handoffReady(row: Project) {
  // 无合同立项：须审批通过后才能进计划
  if (!row.contract_id) return deferApproved(row)
  return !!(row.contract_active_ok && (paymentOk(row) || deferApproved(row)))
}

const initGate = computed(() => {
  const c = contractOptions.value.find((x) => x.id === initForm.contract_id)
  if (!c) return { contractOk: false, paymentOk: false }
  const contractOk = ['signed', 'active', 'completed'].includes(c.status)
  const paid = Number(c.paid_amount || 0)
  return { contractOk, paymentOk: contractOk && paid > 0 }
})

function setTab(next: TabKey) {
  tab.value = next
  const path = next === 'portfolio' ? '/projects' : '/projects/delivery'
  const query: Record<string, string> = { tab: next }
  if (next === 'execute') {
    query.mode = executeMode.value === 'tasks' ? 'tasks' : 'plan'
    const pid =
      executeMode.value === 'tasks' && taskProjectFilter.value
        ? taskProjectFilter.value
        : planProjectId.value
    if (pid) query.project_id = String(pid)
  } else {
    // 离开「执行」时清掉 mode/筛选，避免再点回来被 URL 钉死在任务工时
    executeMode.value = 'plan'
    taskProjectFilter.value = undefined
  }
  router.replace({ path, query })
  if (next === 'execute') {
    if (executeMode.value === 'plan') ensurePlanProject()
    else {
      loadTasks()
      loadTaskStats()
    }
  }
  if (next === 'initiation') loadResourceNeeds()
}

function onOverviewModeChange(mode: string | number | boolean | undefined) {
  const next = mode === 'board' ? 'board' : 'list'
  overviewMode.value = next
  const path = workbench.value === 'portfolio' ? '/projects' : '/projects/delivery'
  const query = { ...route.query } as Record<string, string | undefined>
  if (next === 'board') query.tab = 'board'
  else delete query.tab
  router.replace({ path, query })
}

function syncExecuteRoute(mode: ExecuteMode) {
  const query: Record<string, string> = {
    tab: 'execute',
    mode,
  }
  if (mode === 'tasks') {
    if (taskProjectFilter.value) query.project_id = String(taskProjectFilter.value)
  } else if (planProjectId.value) {
    query.project_id = String(planProjectId.value)
  }
  router.replace({ path: '/projects/delivery', query })
}

function onExecuteModeChange(mode: string | number | boolean | undefined) {
  const next: ExecuteMode = mode === 'tasks' ? 'tasks' : 'plan'
  if (next === 'plan') {
    taskProjectFilter.value = undefined
    syncExecuteRoute('plan')
    ensurePlanProject()
  } else {
    syncExecuteRoute('tasks')
    loadTasks()
    loadTaskStats()
  }
}

function goToTasksWorkbench() {
  executeMode.value = 'tasks'
  // 从计划卡进入任务时，默认聚焦当前计划项目
  if (planProjectId.value) taskProjectFilter.value = planProjectId.value
  syncExecuteRoute('tasks')
  loadTasks()
  loadTaskStats()
  loadHoursBudget(planProjectId.value)
}

function goCreateScheduleForProject() {
  const query: Record<string, string> = { create: '1' }
  if (planProjectId.value) query.project_id = String(planProjectId.value)
  router.push({ path: '/schedules', query })
}

function goDetail(row: Project) {
  router.push(`/projects/${row.id}`)
}

function formatNextNode(row: Project) {
  if (row.status === 'completed' || row.status === 'terminated') return '—'
  return row.next_node || '—'
}

function onPortfolioStatClick(key: PortfolioStatKey) {
  if (portfolioStat.value === key) {
    portfolioStat.value = null
    statusFilter.value = undefined
  } else {
    portfolioStat.value = key
    statusFilter.value = key
  }
  loadProjects()
}

function onStatusFilterChange() {
  const s = statusFilter.value
  if (s === 'executing' || s === 'accepting' || s === 'accepted' || s === 'completed') {
    portfolioStat.value = s
  } else {
    portfolioStat.value = null
  }
  loadProjects()
}

async function loadStats() {
  const { data } = await fetchProjectStats()
  stats.value = data
}

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await fetchProjects({
      keyword: keyword.value || undefined,
      status: statusFilter.value,
      page: 1,
      page_size: 100,
    })
    projects.value = data.items
    projectTotal.value = data.total
    if (!planProjectId.value && data.items.length) {
      planProjectId.value = data.items[0].id
    }
  } finally {
    loading.value = false
  }
}

async function ensurePlanProject() {
  if (!planProjectId.value && projects.value.length) {
    planProjectId.value = projects.value[0].id
  }
  if (planProjectId.value) await loadPlanDetail()
}

async function loadPlanDetail() {
  if (!planProjectId.value) {
    planProject.value = null
    milestones.value = []
    planSchedules.value = []
    taskHours.value = { planned: 0, actual: 0 }
    hoursBudget.value = null
    return
  }
  planLoading.value = true
  planSchedulesLoading.value = true
  planExtrasOpen.value = false
  try {
    const [{ data }, { data: t }, { data: schedules }] = await Promise.all([
      fetchProjectDetail(planProjectId.value),
      fetchProjectTasks({
        project_id: planProjectId.value,
        page: 1,
        page_size: 100,
      }),
      fetchSchedules({
        project_id: planProjectId.value,
        page: 1,
        page_size: 50,
      }),
    ])
    planProject.value = data
    milestones.value = data.milestones || []
    loadPlanLocal(planProjectId.value)
    taskHours.value = {
      planned: t.items.reduce((s, x) => s + Number(x.planned_hours || 0), 0),
      actual: t.items.reduce((s, x) => s + Number(x.actual_hours || 0), 0),
    }
    planSchedules.value = schedules.items || []
    await loadHoursBudget(planProjectId.value)
  } finally {
    planLoading.value = false
    planSchedulesLoading.value = false
  }
}

async function loadTasks() {
  taskLoading.value = true
  try {
    const { data } = await fetchProjectTasks({
      project_id: taskProjectFilter.value,
      keyword: taskKeyword.value || undefined,
      status: taskStatus.value,
      page: 1,
      page_size: 50,
    })
    tasks.value = data.items
  } finally {
    taskLoading.value = false
  }
  await loadLinkedTickets()
}

function ticketStatusTag(row: Ticket) {
  if (row.is_overdue) return 'danger'
  if (row.status === 'closed' || row.status === 'completed') return 'success'
  if (row.status === 'processing' || row.status === 'pending_confirm') return 'warning'
  return 'info'
}

const OPEN_TICKET_STATUSES = new Set([
  'pending_assign',
  'pending_accept',
  'processing',
  'pending_confirm',
])

const linkedTicketDisplayCount = computed(() => {
  if (taskProjectFilter.value) return linkedTicketsTotal.value
  return taskStats.value?.linked_tickets ?? 0
})

async function loadLinkedTickets() {
  if (!taskProjectFilter.value) {
    linkedTickets.value = []
    linkedTicketsTotal.value = 0
    return
  }
  linkedTicketsLoading.value = true
  try {
    const { data } = await fetchTickets({
      project_id: taskProjectFilter.value,
      page: 1,
      page_size: 50,
    })
    linkedTickets.value = data.items
    linkedTicketsTotal.value = data.total
  } finally {
    linkedTicketsLoading.value = false
  }
}

function focusLinkedTickets() {
  if (!taskProjectFilter.value) {
    ElMessage.info('请先点任务表里的「所属项目」聚焦到单个项目，再看关联工单')
    return
  }
  linkedTicketsPanelRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function filterTasksByProject(row: ProjectTask) {
  if (!row.project_id) return
  taskProjectFilter.value = row.project_id
  executeMode.value = 'tasks'
  syncExecuteRoute('tasks')
  loadTasks()
  loadTaskStats()
  loadHoursBudget(row.project_id)
}

async function countOpenTickets(projectId: number) {
  const { data } = await fetchTickets({
    project_id: projectId,
    page: 1,
    page_size: 100,
  })
  return data.items.filter((t) => OPEN_TICKET_STATUSES.has(String(t.status))).length
}

async function openTaskSchedules(row: ProjectTask) {
  taskScheduleTarget.value = row
  taskScheduleVisible.value = true
  taskSchedulesLoading.value = true
  taskSchedules.value = []
  try {
    const { data } = await fetchSchedules({
      project_task_id: row.id,
      page: 1,
      page_size: 50,
    })
    taskSchedules.value = data.items || []
  } finally {
    taskSchedulesLoading.value = false
  }
}

async function loadTaskStats() {
  const { data } = await fetchProjectTaskStats()
  taskStats.value = data
}

async function searchContracts(q: string) {
  contractLoading.value = true
  try {
    const [{ data }, occupied] = await Promise.all([
      fetchDirectoryContracts({ keyword: q || undefined, mine: true, page: 1, page_size: 50 }),
      fetchProjects({ page: 1, page_size: 100 }),
    ])
    const busyContractIds = new Set(
      (occupied.data.items || [])
        .filter((p) => p.contract_id && p.status !== 'terminated')
        .map((p) => p.contract_id as number),
    )
    contractOptions.value = data.items.filter(
      (c) =>
        ['signed', 'active', 'completed'].includes(c.status) && !busyContractIds.has(c.id),
    )
  } finally {
    contractLoading.value = false
  }
}

async function searchEmployees(q: string) {
  empLoading.value = true
  try {
    const { data } = await fetchDirectoryPeople({ keyword: q || undefined, page: 1, page_size: 30 })
    employees.value = data.items
  } finally {
    empLoading.value = false
  }
}

function onContractPicked(id: number | undefined) {
  if (!id) {
    initForm.payment_deferred = false
    initForm.payment_deferred_reason = ''
    return
  }
  const c = contractOptions.value.find((x) => x.id === id)
  if (!c) return
  if (!initForm.name) initForm.name = `${c.customer_name || c.title} · 交付项目`
  if (c.contract_type) {
    initForm.project_type = c.contract_type
    onProjectTypeChange(c.contract_type)
  }
  // 换合同后重置例外勾选，避免误带到有到款的合同
  initForm.payment_deferred = false
  initForm.payment_deferred_reason = ''
}

function memberLabel(m: ResourceRoleMember) {
  const parts = [m.name]
  if (m.job_title) parts.push(m.job_title)
  if (m.department_name) parts.push(m.department_name)
  return parts.join(' · ')
}

function roleOptionLabel(r: ResourceRoleOption) {
  if (r.member_count > 0) return `${r.role_name}（${r.member_count}人在册）`
  return `${r.role_name}（暂无人员）`
}

function membersForRole(roleName: string): ResourceRoleMember[] {
  if (!roleName) return roleEmployees.value
  const opt = roleOptions.value.find((r) => r.role_name === roleName)
  // 已匹配飞书部门：只展示该部门成员，与「（N人在册）」一致
  if (opt) return opt.members || []
  // 手动创建的部门名：回退全员列表
  return roleEmployees.value
}

function buildDefaultRoleRows(type: string): RoleAssignRow[] {
  const hints = DEPT_HINTS[type] || DEPT_HINTS.other
  const available = roleOptions.value
  const picked: RoleAssignRow[] = []
  const used = new Set<string>()
  for (const hint of hints) {
    const match = available.find(
      (r) => !used.has(r.role_name) && r.role_name.includes(hint) && r.member_count > 0,
    )
    if (match) {
      used.add(match.role_name)
      picked.push({
        role_name: match.role_name,
        suggested_user_id: undefined,
        planned_hours: DEFAULT_ROLE_HOURS,
      })
    }
  }
  if (picked.length) return picked
  return [{ role_name: '', suggested_user_id: undefined, planned_hours: DEFAULT_ROLE_HOURS }]
}

async function loadRoleOptions() {
  try {
    const { data } = await fetchResourceRoleOptions()
    roleOptions.value = data.roles || []
    roleEmployees.value = data.employees || []
    roleOptionsHint.value = data.hint || ''
  } catch {
    roleOptions.value = []
    roleEmployees.value = []
    roleOptionsHint.value = '加载飞书部门失败，可手动输入部门并指定对接人。'
  }
}

function isSuggestedUserTaken(userId: number | undefined, currentIdx: number) {
  if (!userId) return false
  return initForm.resource_roles.some(
    (r, i) => i !== currentIdx && r.suggested_user_id === userId,
  )
}

function onRoleNameChange(row: RoleAssignRow) {
  const members = membersForRole(row.role_name)
  if (row.suggested_user_id && !members.some((m) => m.id === row.suggested_user_id)) {
    row.suggested_user_id = undefined
  }
}

function addRoleRow() {
  initForm.resource_roles.push({
    role_name: '',
    suggested_user_id: undefined,
    planned_hours: DEFAULT_ROLE_HOURS,
  })
}

function removeRoleRow(idx: number) {
  initForm.resource_roles.splice(idx, 1)
}

function onProjectTypeChange(type: string) {
  initForm.resource_roles = buildDefaultRoleRows(type)
}

async function openInitiation() {
  initForm.contract_id = undefined
  initForm.project_type = 'ai_custom'
  initForm.name = ''
  initForm.scope_desc = ''
  initForm.manager_id = userStore.user?.id
  initForm.start_date = ''
  initForm.end_date = ''
  initForm.payment_deferred = false
  initForm.payment_deferred_reason = ''
  await Promise.all([searchContracts(''), searchEmployees(''), loadRoleOptions()])
  initForm.resource_roles = buildDefaultRoleRows('ai_custom')
  initVisible.value = true
}

async function onCreateProject() {
  const ok = await initFormRef.value?.validate().catch(() => false)
  if (!ok) return
  const hasContract = !!initForm.contract_id
  if (hasContract && !initGate.value.contractOk) {
    ElMessage.warning('合同须已签署后才能立项')
    return
  }
  const useDefer = hasContract
    ? !initGate.value.paymentOk && initForm.payment_deferred
    : true
  if (hasContract && !initGate.value.paymentOk && !useDefer) {
    ElMessage.warning(
      '合同尚无确认到账：请先完成到款认领与财务复核，或勾选「无到款立项」并填写原因',
    )
    return
  }
  if (useDefer && !initForm.payment_deferred_reason.trim()) {
    ElMessage.warning(hasContract ? '无到款立项须填写原因' : '无合同立项须填写原因')
    return
  }
  const roles = initForm.resource_roles
    .map((r) => ({
      role_name: (r.role_name || '').trim(),
      suggested_user_id: r.suggested_user_id,
      planned_hours: Number(r.planned_hours || 0),
    }))
    .filter((r) => r.role_name)
  if (!roles.length) {
    ElMessage.warning('请至少添加一个所需部门')
    return
  }
  if (roles.some((r) => !(r.planned_hours > 0))) {
    ElMessage.warning('请为每个部门填写大于 0 的计划投入工时')
    return
  }
  const suggestedIds = roles
    .map((r) => r.suggested_user_id)
    .filter((id): id is number => id != null)
  if (new Set(suggestedIds).size !== suggestedIds.length) {
    ElMessage.warning('对接人不能重复')
    return
  }
  saving.value = true
  try {
    await createProject({
      name: initForm.name,
      contract_id: initForm.contract_id || undefined,
      project_type: initForm.project_type,
      scope_desc: initForm.scope_desc,
      manager_id: initForm.manager_id,
      start_date: initForm.start_date || undefined,
      end_date: initForm.end_date || undefined,
      business_owner_id: userStore.user?.id,
      resource_roles: roles,
      payment_deferred: useDefer,
      payment_deferred_reason: useDefer ? initForm.payment_deferred_reason.trim() : undefined,
    })
    ElMessage.success(
      useDefer
        ? hasContract
          ? '已提交无到款立项，请到审批中心处理；通过后并可确认资源后进入计划'
          : '已提交无合同立项，请到审批中心处理；通过后并可确认资源后进入计划'
        : '立项申请已提交，请在下方确认部门资源',
    )
    initVisible.value = false
    setTab('initiation')
    await reloadAll()
  } finally {
    saving.value = false
  }
}

async function goToPlanWorkbench(projectId: number) {
  executeMode.value = 'plan'
  planProjectId.value = projectId
  await router.push({
    path: '/projects/delivery',
    query: {
      tab: 'execute',
      mode: 'plan',
      project_id: String(projectId),
    },
  })
}

async function advanceInitiating(row: Project) {
  if (!handoffReady(row)) {
    const missing: string[] = []
    if (!row.contract_id) {
      if (deferPending(row)) missing.push('无合同立项审批通过（请到审批中心处理）')
      else if (deferRejected(row)) missing.push('无合同立项已被驳回，请重新发起或补充说明')
      else missing.push('无合同立项审批通过')
    } else {
      if (!row.contract_active_ok) missing.push('合同已签署')
      if (!paymentOk(row)) {
        if (deferPending(row)) missing.push('无到款立项审批通过（请到审批中心处理）')
        else if (deferRejected(row)) missing.push('到款认领（无到款立项已被驳回）')
        else missing.push('已确认到账（或申请无到款立项并获审批）')
      }
    }
    ElMessage.warning(`缺失：${missing.join('、') || '立项条件未满足'}`)
    return
  }
  if (row.status === 'initiating') {
    try {
      await startProjectPlanning(row.id)
      ElMessage.success('已进入计划编制，请完善计划基线')
      await goToPlanWorkbench(row.id)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (typeof detail === 'string' && detail.includes('资源')) {
        ElMessage.warning(detail)
        await loadResourceNeeds()
      }
    }
    return
  }
  if (['planning', 'executing'].includes(row.status)) {
    await goToPlanWorkbench(row.id)
    return
  }
  goDetail(row)
}

async function loadResourceNeeds() {
  resourceLoading.value = true
  try {
    const { data } = await fetchProjectResourceNeeds({ only_pending: false })
    resourceNeeds.value = data.items || []
    resourcePendingCount.value = data.pending_count ?? resourceNeeds.value.filter((x) => x.status === 'pending').length
  } catch {
    resourceNeeds.value = []
    resourcePendingCount.value = 0
  } finally {
    resourceLoading.value = false
  }
}

async function openResourceConfirm(row: ProjectResourceNeed) {
  resourceTarget.value = row
  resourceForm.action = 'accept'
  resourceForm.confirmed_user_id = row.suggested_user_id || undefined
  resourceForm.planned_hours = Number(row.planned_hours || 40)
  resourceForm.note = ''
  await searchEmployees('')
  resourceVisible.value = true
}

async function onConfirmResource() {
  if (!resourceTarget.value) return
  if (resourceForm.action === 'reject' && !resourceForm.note.trim()) {
    ElMessage.warning('请填写拒绝说明')
    return
  }
  if (resourceForm.action === 'adjust' && !resourceForm.confirmed_user_id) {
    ElMessage.warning('请选择确认成员')
    return
  }
  saving.value = true
  try {
    await confirmProjectResource(resourceTarget.value.id, {
      action: resourceForm.action,
      confirmed_user_id:
        resourceForm.action === 'adjust' ? resourceForm.confirmed_user_id : undefined,
      planned_hours: resourceForm.action === 'adjust' ? resourceForm.planned_hours : undefined,
      note: resourceForm.note.trim(),
    })
    ElMessage.success(
      resourceForm.action === 'reject' ? '已退回协调' : '资源投入已确认',
    )
    resourceVisible.value = false
    await loadResourceNeeds()
  } finally {
    saving.value = false
  }
}

async function onBaselineAction() {
  if (!planProject.value) {
    ElMessage.info('请先选择项目')
    return
  }
  if (['completed', 'terminated'].includes(planProject.value.status)) {
    ElMessage.warning('已结束项目不可制定或变更基线')
    return
  }
  if (planBaselineLocked.value) {
    openChangeDialog()
  } else {
    openBaselineDialog()
  }
}

function openBaselineDialog() {
  baselineNote.value =
    planBaselineMeta.value?.note ||
    '以已确认需求范围与客户验收口径作为执行基线。'
  baselineVisible.value = true
}

/** 基线弹窗内直接添加节点：叠开添加窗，基线确认不关 */
async function openMilestoneFromBaseline() {
  await openMilestone()
}

function openChangeDialog() {
  if (!planProject.value) return ElMessage.info('请先选择项目')
  if (!planBaselineLocked.value) {
    ElMessage.info('请先提交基线确认，再生效后的修改走变更流程')
    openBaselineDialog()
    return
  }
  changeForm.type = '范围变更'
  changeForm.reason = ''
  changeForm.impact = ''
  changeForm.delayDays = 2
  changeForm.extraHours = 24
  changeVisible.value = true
}

function openRiskDialog() {
  if (!planProject.value) return ElMessage.info('请先选择项目')
  riskForm.title = ''
  riskForm.level = '高'
  riskForm.role = '项目负责人'
  riskForm.response = ''
  riskVisible.value = true
}

async function confirmBaseline() {
  if (!planProject.value || !planProjectId.value) return
  if (!baselineNote.value.trim()) {
    ElMessage.warning('请填写基线说明')
    return
  }
  if (milestones.value.length && baselineMilestoneChecks.value.some((x) => !x.ok)) {
    ElMessage.warning('已添加的计划节点不完整，请补齐责任角色、计划日期和必交成果，或先删除再确认')
    return
  }
  if (!milestones.value.length) {
    try {
      await ElMessageBox.confirm(
        '当前未添加计划节点。确认后可直接用任务推进；复杂项目建议稍后补节点以便验收留证。',
        '无计划节点确认基线',
        { type: 'info', confirmButtonText: '仍要确认', cancelButtonText: '返回补节点' },
      )
    } catch {
      return
    }
  }
  saving.value = true
  try {
    const ver = planProject.value.baseline_version || 'V1'
    const today = formatShortDate(new Date().toISOString().slice(0, 10))
    await updateProject(planProject.value.id, { baseline_version: ver })
    if (['initiating', 'planning'].includes(planProject.value.status)) {
      await startProjectExecuting(planProject.value.id)
    }
    planBaselineMeta.value = {
      locked: true,
      note: baselineNote.value.trim(),
      effectiveAt: today,
      version: ver,
    }
    savePlanLocal()
    baselineVisible.value = false
    ElMessage.success('计划基线已提交确认，当前版本成为执行依据')
    await loadPlanDetail()
    await loadProjects()
  } finally {
    saving.value = false
  }
}

async function submitChange() {
  if (!planProject.value || !planProjectId.value) return
  if (!changeForm.reason.trim() || !changeForm.impact.trim()) {
    ElMessage.warning('变更原因和影响评估均为必填项')
    return
  }
  saving.value = true
  try {
    const stamp = new Date()
    const code = `CR-${String(stamp.getMonth() + 1).padStart(2, '0')}${String(stamp.getDate()).padStart(2, '0')}${String(stamp.getHours()).padStart(2, '0')}`
    planChanges.value = [
      {
        id: `${Date.now()}`,
        code,
        title: changeForm.type,
        status: '审批中',
        type: changeForm.type,
      },
      ...planChanges.value,
    ]
    savePlanLocal()
    changeVisible.value = false
    ElMessage.success(
      `${planProject.value.baseline_version || 'V1'}继续生效，变更申请已提交待确认`,
    )
  } finally {
    saving.value = false
  }
}

function submitRisk() {
  if (!riskForm.title.trim() || !riskForm.response.trim()) {
    ElMessage.warning('风险事项和应对措施均为必填项')
    return
  }
  planRisks.value = [
    {
      id: `${Date.now()}`,
      title: riskForm.title.trim(),
      level: riskForm.level,
      role: riskForm.role,
      response: riskForm.response.trim(),
    },
    ...planRisks.value,
  ]
  savePlanLocal()
  riskVisible.value = false
  ElMessage.success('项目风险已登记')
}

function evidenceStatusLabel(row: ProjectMilestone) {
  if (!planInExecution.value) {
    return row.remark ? '已定要求' : '待定要求'
  }
  const s = row.evidence_status || 'none'
  if (s === 'confirmed') return '已确认'
  if (s === 'rejected') return '已驳回'
  if (s === 'pending') return '待确认'
  return '未提交'
}

function evidenceTone(row: ProjectMilestone) {
  if (!planInExecution.value) return row.remark ? '' : 'warn'
  const s = row.evidence_status || 'none'
  if (s === 'confirmed') return 'good'
  if (s === 'rejected') return 'bad'
  if (s === 'pending') return 'warn'
  return ''
}

function canManagePlanForProject(project?: Project | null) {
  if (!project) return false
  if (userStore.hasPermission('*') || userStore.hasPermission('project:manage')) return true
  const codes = (userStore.user?.roles || []).map((r) => r.code)
  if (codes.includes('admin')) return true
  if (!codes.includes('dept_head')) return false
  const uidDept = userStore.user?.department_id
  if (project.department_id && uidDept && project.department_id !== uidDept) return false
  return true
}

const canManagePlan = computed(() => canManagePlanForProject(planProject.value))

function canConfirmEvidence(row: ProjectMilestone) {
  if (!planInExecution.value || !planProject.value || !row.evidence) return false
  if (row.evidence_status !== 'pending') return false
  return canManagePlan.value
}

const evidenceDialogTitle = computed(() => {
  if (!planInExecution.value) return '查看节点要求'
  if (evidenceMode.value === 'review') return '审核完成证据'
  return evidenceTarget.value?.evidence ? '修改完成证据' : '提交完成证据'
})

function milestonePrimaryActionLabel(row: ProjectMilestone) {
  if (!planInExecution.value) return '查看要求'
  if (row.status === 'done' && canConfirmEvidence(row)) return '审核证据'
  if (row.status === 'done') return '查看证据'
  // 常规：无任务时优先去拆任务；纯验收节点仍可直接交证据
  if (!(row.task_total || 0) && !row.evidence) return '去拆任务'
  if ((row.task_total || 0) > (row.task_done || 0) && !row.evidence) return '去完成任务'
  if (!row.evidence) return '提交证据'
  if (row.evidence_status === 'rejected') return '重提证据'
  if (canConfirmEvidence(row)) return '审核证据'
  if (row.can_complete && canManagePlan.value) return '标记完成'
  if ((row.task_total || 0) > (row.task_done || 0) && row.evidence_status === 'confirmed') {
    return '去完成任务'
  }
  if (row.evidence_status === 'pending') return '查看证据'
  return ''
}

function goToMilestoneTasks(row: ProjectMilestone) {
  preferredTaskMilestoneId.value = row.id
  taskProjectFilter.value = planProjectId.value
  taskKeyword.value = ''
  taskStatus.value = undefined
  executeMode.value = 'tasks'
  syncExecuteRoute('tasks')
  loadTasks()
  loadTaskStats()
  loadHoursBudget(planProjectId.value)
  openTaskCreate()
}

function clearTaskProjectFilter() {
  taskProjectFilter.value = undefined
  hoursBudget.value = null
  syncExecuteRoute('tasks')
  loadTasks()
}

function onMilestonePrimaryAction(row: ProjectMilestone) {
  if (!planInExecution.value) {
    openEvidencePanel(row)
    return
  }
  if (row.can_complete && row.status !== 'done' && canManagePlan.value) {
    markMilestoneDone(row)
    return
  }
  const needTasksFirst =
    (!(row.task_total || 0) && !row.evidence) ||
    ((row.task_total || 0) > (row.task_done || 0) && !row.evidence) ||
    ((row.task_total || 0) > (row.task_done || 0) && row.evidence_status === 'confirmed' && row.status !== 'done')
  if (needTasksFirst) {
    goToMilestoneTasks(row)
    return
  }
  openEvidencePanel(row)
}

function openEvidencePanel(row: ProjectMilestone) {
  evidenceTarget.value = row
  evidenceDraft.value = row.evidence || ''
  evidenceLinkDraft.value = row.evidence_link || ''
  evidenceAttachName.value = row.evidence_attachment || ''
  evidenceAttachPath.value = row.evidence_attachment_path || ''
  evidenceAttachPreviewUrl.value = evidenceAttachUrl(row)
  if (!planInExecution.value) {
    evidenceMode.value = 'review'
  } else if (!row.evidence || row.evidence_status === 'rejected') {
    evidenceMode.value = 'fill'
  } else if (canConfirmEvidence(row) || row.evidence_status === 'pending' || row.evidence_status === 'confirmed') {
    evidenceMode.value = 'review'
  } else {
    evidenceMode.value = 'fill'
  }
  evidenceVisible.value = true
}

function evidenceAttachUrl(row?: ProjectMilestone | null) {
  const path = (row?.evidence_attachment_path || evidenceAttachPath.value || '').trim()
  if (!path) return ''
  if (/^https?:\/\//i.test(path) || path.startsWith('/uploads/')) return path
  return `/uploads/${path.replace(/^\/+/, '')}`
}

function triggerEvidenceUpload() {
  evidenceFileRef.value?.click()
}

function clearEvidenceAttachment() {
  evidenceAttachName.value = ''
  evidenceAttachPath.value = ''
  evidenceAttachPreviewUrl.value = ''
}

async function onEvidenceFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploadingEvidence.value = true
  try {
    const { data } = await uploadFile(file, 'milestone_evidence')
    evidenceAttachName.value = data.filename
    evidenceAttachPath.value = data.path
    evidenceAttachPreviewUrl.value = data.url || evidenceAttachUrl()
  } catch {
    /* interceptor */
  } finally {
    uploadingEvidence.value = false
  }
}

async function confirmEvidence(row: ProjectMilestone) {
  if (!planProjectId.value) return
  saving.value = true
  try {
    const { data } = await reviewMilestoneEvidence(planProjectId.value, row.id, { action: 'confirm' })
    if (data.status === 'done') {
      ElMessage.success('证据已确认，里程碑已自动完成')
    } else {
      ElMessage.success('证据已确认；请完成剩余关联任务后将自动完成里程碑')
    }
    evidenceVisible.value = false
    await loadPlanDetail()
    await loadProjects()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

async function rejectEvidence(row: ProjectMilestone) {
  if (!planProjectId.value) return
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回完成证据', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：缺少客户确认截图',
      inputValidator: (v) => (!!v && !!String(v).trim()) || '请填写原因',
    })
    saving.value = true
    await reviewMilestoneEvidence(planProjectId.value, row.id, {
      action: 'reject',
      reason: String(value).trim(),
    })
    ElMessage.success('已驳回，请执行人按意见重提证据')
    evidenceVisible.value = false
    await loadPlanDetail()
  } catch {
    /* cancel or interceptor */
  } finally {
    saving.value = false
  }
}

function resolveChange(item: PlanChangeItem, status: string) {
  planChanges.value = planChanges.value.map((c) => (c.id === item.id ? { ...c, status } : c))
  savePlanLocal()
  ElMessage.success(status === '已生效' ? '变更已通过' : '变更已驳回')
}

async function markMilestoneDone(row: ProjectMilestone) {
  if (!planProjectId.value) return
  if (!canManagePlan.value) {
    ElMessage.warning('仅部门负责人或系统管理员可标记里程碑完成')
    return
  }
  if (!row.can_complete) {
    ElMessage.warning(row.next_action || '暂不可完成')
    return
  }
  try {
    await updateMilestone(planProjectId.value, row.id, { status: 'done' })
    ElMessage.success('里程碑已完成')
    await loadPlanDetail()
    await loadProjects()
  } catch {
    /* interceptor */
  }
}

async function submitMilestoneEvidence() {
  if (!planProjectId.value || !evidenceTarget.value) return
  const text = evidenceDraft.value.trim()
  const link = evidenceLinkDraft.value.trim()
  if (!text) {
    ElMessage.warning('请填写完成说明')
    return
  }
  if (!link && !evidenceAttachPath.value) {
    ElMessage.warning('请提供证据链接或上传附件')
    return
  }
  if (link && !/^https?:\/\//i.test(link)) {
    ElMessage.warning('证据链接请以 http:// 或 https:// 开头')
    return
  }
  saving.value = true
  try {
    await updateMilestone(planProjectId.value, evidenceTarget.value.id, {
      evidence: text,
      evidence_link: link || null,
      evidence_attachment: evidenceAttachName.value || null,
      evidence_attachment_path: evidenceAttachPath.value || null,
    })
    ElMessage.success('证据已提交，等待项目负责人确认')
    evidenceVisible.value = false
    evidenceTarget.value = null
    await loadPlanDetail()
    await loadProjects()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

async function openMilestone() {
  if (!planProjectId.value) return ElMessage.warning('请先选择项目')
  msForm.name = ''
  msForm.role = ''
  msForm.start_date = ''
  msForm.deadline = ''
  msForm.deliverable = ''
  msForm.evidence = ''
  const hasPlanResources = resourceNeeds.value.some((n) => n.project_id === planProjectId.value)
  if (!hasPlanResources) {
    await loadResourceNeeds()
  }
  msVisible.value = true
}

async function onAddMilestone() {
  if (!planProjectId.value) return ElMessage.warning('请先选择项目')
  if (!msForm.name.trim()) return ElMessage.warning('请填写节点名称')
  saving.value = true
  try {
    await addMilestone(planProjectId.value, {
      name: msForm.name.trim(),
      role: msForm.role.trim() || undefined,
      start_date: msForm.start_date || undefined,
      deadline: msForm.deadline || undefined,
      deliverable: msForm.deliverable.trim() || undefined,
      // 证据要求写入 remark；真正完成证据在执行阶段再提交
      remark: msForm.evidence.trim() || undefined,
    })
    ElMessage.success(
      baselineVisible.value ? '计划节点已添加，可继续确认基线' : '计划节点已添加',
    )
    msVisible.value = false
    await loadPlanDetail()
    await loadProjects()
  } finally {
    saving.value = false
  }
}

async function onDeleteMilestone(row: ProjectMilestone) {
  if (!planProjectId.value) return
  if (!canManagePlan.value) {
    ElMessage.warning('仅部门负责人或系统管理员可删除计划节点')
    return
  }
  const taskHint = row.task_total
    ? `该节点下有 ${row.task_total} 个任务，删除后任务会保留但不再挂在此节点下。`
    : '删除后不可恢复。'
  try {
    await ElMessageBox.confirm(`确认删除计划节点「${row.name}」？${taskHint}`, '删除计划节点', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  saving.value = true
  try {
    await deleteMilestone(planProjectId.value, row.id)
    ElMessage.success('计划节点已删除')
    await loadPlanDetail()
    await loadProjects()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

async function loadTaskMilestones(projectId?: number) {
  taskMilestoneOptions.value = []
  if (!projectId) return
  taskMilestoneLoading.value = true
  try {
    const { data } = await fetchProjectDetail(projectId)
    taskMilestoneOptions.value = data.milestones || []
  } finally {
    taskMilestoneLoading.value = false
  }
}

function findTaskMilestone(milestoneId?: number) {
  if (!milestoneId) return undefined
  return (
    taskMilestoneOptions.value.find((m) => m.id === milestoneId) ||
    milestones.value.find((m) => m.id === milestoneId)
  )
}

/** 从节点责任角色解析责任人：资源安排对接人 / 项目负责人 / 姓名匹配 */
function resolveAssigneeFromMilestone(ms?: ProjectMilestone | null): {
  id?: number
  name?: string
  source?: string
} {
  if (!ms?.role?.trim()) return {}
  const role = ms.role.trim()
  const pid = taskForm.project_id || planProjectId.value
  const project =
    (pid && projects.value.find((p) => p.id === pid)) || planProject.value || null

  if (role.includes('项目负责人') && project?.manager_id) {
    return {
      id: project.manager_id,
      name: project.manager_name || undefined,
      source: '节点责任方（项目负责人）',
    }
  }

  for (const need of resourceNeeds.value) {
    if (pid && need.project_id !== pid) continue
    const uid = need.confirmed_user_id || need.suggested_user_id || undefined
    if (!uid) continue
    const person = (need.confirmed_user_name || need.suggested_user_name || '').trim()
    const dept = (need.department_name || need.role_name || '').trim()
    const full = person && dept ? `${person} · ${dept}` : ''
    const hit =
      (full && (role === clipMilestoneRole(full) || role === full)) ||
      (person && role.includes(person)) ||
      (dept && role.includes(dept))
    if (hit) {
      return {
        id: uid,
        name: person || undefined,
        source: `节点责任方（${dept || person || '资源安排'}）`,
      }
    }
  }

  const personName = role.split(/\s*[·•・]\s*/)[0]?.trim()
  if (personName && personName !== role) {
    const emp = employees.value.find(
      (e) => (e.real_name || e.username) === personName || e.real_name === personName,
    )
    if (emp) {
      return {
        id: emp.id,
        name: emp.real_name || emp.username,
        source: '节点责任方',
      }
    }
    return { name: personName, source: '节点责任方' }
  }
  return {}
}

async function ensureAssigneeOption(userId: number, name?: string) {
  if (employees.value.some((e) => e.id === userId)) return
  if (name) await searchEmployees(name)
  if (employees.value.some((e) => e.id === userId)) return
  employees.value = [
    {
      id: userId,
      username: name || String(userId),
      real_name: name || String(userId),
      is_active: true,
    } as DirectoryPerson,
    ...employees.value,
  ]
}

async function applyAssigneeFromMilestone() {
  const ms = findTaskMilestone(taskForm.milestone_id)
  const resolved = resolveAssigneeFromMilestone(ms)
  if (resolved.id) {
    await ensureAssigneeOption(resolved.id, resolved.name)
    taskForm.assignee_id = resolved.id
    taskAssigneeHint.value = resolved.source
      ? `已按${resolved.source}带出，可改`
      : '已按节点责任方带出，可改'
    return
  }
  if (resolved.name) {
    await searchEmployees(resolved.name)
    const emp = employees.value.find(
      (e) => (e.real_name || e.username) === resolved.name,
    )
    if (emp) {
      taskForm.assignee_id = emp.id
      taskAssigneeHint.value = '已按节点责任方带出，可改'
      return
    }
  }
  // 无节点责任人时回退本人
  taskForm.assignee_id = userStore.user?.id
  taskAssigneeHint.value = ms?.role
    ? `未匹配到「${ms.role}」对应人员，已填当前账号，请手动选择`
    : '未选节点责任方，已填当前账号，可改'
}

async function onTaskMilestoneChange() {
  const ms = findTaskMilestone(taskForm.milestone_id)
  applyTaskDateFromMilestone(ms)
  await applyAssigneeFromMilestone()
}

function parseTaskDateTime(v: string) {
  const raw = v.includes('T') ? v : v.replace(' ', 'T')
  const d = new Date(raw.length === 10 ? `${raw}T00:00:00` : raw)
  return Number.isNaN(d.getTime()) ? null : d
}

function toTaskDateTime(day: string, hour: number, minute = 0) {
  const d = day.slice(0, 10)
  return `${d}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`
}

function applyTaskHoursFromRange(range?: [string, string] | null) {
  if (!range?.[0] || !range?.[1]) return
  const s = parseTaskDateTime(range[0])
  const e = parseTaskDateTime(range[1])
  if (!s || !e || e <= s) return
  // 选几点到几点，就按实际时长计工时
  let hours = (e.getTime() - s.getTime()) / 3600000
  const remain = Number(taskFormBudget.value?.remaining_hours || 0)
  const budget = Number(taskFormBudget.value?.resource_budget_hours || 0)
  if (budget > 0 && remain >= 0) {
    hours = Math.min(hours, remain)
  }
  taskForm.planned_hours = Math.round(hours * 10) / 10
}

function onTaskDateRangeChange(range: [string, string] | null) {
  applyTaskHoursFromRange(range)
}

function applyTaskDateFromMilestone(ms?: ProjectMilestone | null) {
  if (!ms) return
  const startDay = ms.start_date || ms.deadline
  const endDay = ms.deadline || ms.start_date
  if (!startDay || !endDay) return
  taskForm.dateRange = [
    toTaskDateTime(startDay, WORK_HOUR_START),
    toTaskDateTime(endDay, WORK_HOUR_END),
  ]
}

async function onTaskProjectChange(projectId: number) {
  taskForm.milestone_id = undefined
  preferredTaskMilestoneId.value = undefined
  await Promise.all([loadTaskMilestones(projectId), loadTaskFormBudget(projectId)])
  const open = taskMilestoneOptions.value.find((m) => m.status !== 'done')
  if (open) taskForm.milestone_id = open.id
  if (taskForm.planned_hours != null) {
    const remain = Number(taskFormBudget.value?.remaining_hours || 0)
    const budget = Number(taskFormBudget.value?.resource_budget_hours || 0)
    if (budget > 0 && remain >= 0) {
      taskForm.planned_hours = Math.min(Number(taskForm.planned_hours), remain)
    }
  }
  await onTaskMilestoneChange()
}

async function openTaskCreate() {
  taskForm.project_id = planProjectId.value || projects.value[0]?.id
  taskForm.milestone_id = undefined
  taskForm.title = ''
  taskForm.criteria = ''
  taskForm.assignee_id = undefined
  taskForm.dateRange = null
  taskForm.planned_hours = undefined
  taskAssigneeHint.value = ''
  const preferredId = preferredTaskMilestoneId.value
  preferredTaskMilestoneId.value = undefined
  await Promise.all([searchEmployees(''), loadResourceNeeds()])
  if (taskForm.project_id) {
    if (planProjectId.value === taskForm.project_id && milestones.value.length) {
      taskMilestoneOptions.value = milestones.value
    } else {
      await loadTaskMilestones(taskForm.project_id)
    }
    await loadTaskFormBudget(taskForm.project_id)
    const preferred = preferredId
      ? taskMilestoneOptions.value.find((m) => m.id === preferredId && m.status !== 'done')
      : undefined
    const open = preferred || taskMilestoneOptions.value.find((m) => m.status !== 'done')
    if (open) {
      taskForm.milestone_id = open.id
      applyTaskDateFromMilestone(open)
    }
    await applyAssigneeFromMilestone()
  } else {
    taskFormBudget.value = null
    taskForm.assignee_id = userStore.user?.id
    taskAssigneeHint.value = '已填当前账号，可改'
  }
  taskVisible.value = true
}

async function onCreateTask() {
  const ok = await taskFormRef.value?.validate().catch(() => false)
  if (!ok || !taskForm.project_id) return
  if (taskFormOverBudget.value) {
    ElMessage.warning(taskFormHoursHint.value || '计划工时超出资源承诺预算')
    return
  }
  saving.value = true
  try {
    await createProjectTask({
      project_id: taskForm.project_id,
      milestone_id: taskForm.milestone_id,
      title: taskForm.title,
      criteria: taskForm.criteria,
      assignee_id: taskForm.assignee_id,
      start_date: taskForm.dateRange?.[0]?.slice(0, 10) || undefined,
      due_date: taskForm.dateRange?.[1]?.slice(0, 10) || undefined,
      planned_hours: taskForm.planned_hours,
    })
    ElMessage.success('任务已创建')
    taskVisible.value = false
    await loadTasks()
    await loadTaskStats()
    if (taskProjectFilter.value === taskForm.project_id) {
      await loadHoursBudget(taskForm.project_id)
    }
    if (planProjectId.value === taskForm.project_id) await loadPlanDetail()
  } finally {
    saving.value = false
  }
}

async function markTaskDone(row: ProjectTask) {
  if (!canCompleteTask(row)) {
    ElMessage.warning('仅任务责任人或项目管理者可完成该任务')
    return
  }
  completeTarget.value = row
  completeActualHours.value = Number(row.actual_hours || row.planned_hours || 0)
  completeVisible.value = true
}

function canCompleteTask(row: ProjectTask) {
  const uid = userStore.user?.id
  if (!uid) return false
  if (row.assignee_id === uid) return true
  if (userStore.hasPermission('*')) return true
  const codes = (userStore.user?.roles || []).map((r) => r.code)
  if (
    codes.includes('admin') ||
    codes.includes('delivery_lead') ||
    codes.includes('middle_manager') ||
    codes.includes('executive')
  ) {
    return true
  }
  const p = projects.value.find((x) => x.id === row.project_id)
  if (p && (p.manager_id === uid || p.creator_id === uid)) return true
  return false
}

async function onConfirmCompleteTask() {
  if (!completeTarget.value) return
  if (completeActualHours.value == null || Number(completeActualHours.value) < 0) {
    ElMessage.warning('请填写实际工时')
    return
  }
  saving.value = true
  try {
    await updateProjectTask(completeTarget.value.id, {
      status: 'done',
      actual_hours: Number(completeActualHours.value),
    })
    ElMessage.success('任务已完成')
    const projectId = completeTarget.value.project_id
    completeVisible.value = false
    completeTarget.value = null
    await loadTasks()
    await loadTaskStats()
    if (planProjectId.value === projectId) await loadPlanDetail()
  } finally {
    saving.value = false
  }
}

function openAcceptance(row?: Project) {
  const fromRow = !!row
  const target = row || acceptanceCandidates.value[0]
  if (!target) {
    ElMessage.warning('暂无可验收项目')
    return
  }
  if (target.acceptance_approval_status === 'pending') {
    ElMessage.warning('该项目验收已在审批中')
    return
  }
  const done = target.milestone_done || 0
  const total = target.milestone_total || 0
  if (total > 0 && done < total) {
    ElMessage.warning(`还有 ${total - done} 个计划节点未完成，不可发起验收`)
    return
  }
  acceptProjectLocked.value = fromRow
  acceptForm.project_id = target.id
  acceptForm.result = 'pass'
  acceptForm.accepted_at = new Date().toISOString().slice(0, 10)
  acceptForm.method = '内部验收单'
  acceptForm.conclusion = ''
  acceptForm.leftover_summary = ''
  acceptForm.attachment = ''
  acceptForm.attachment_path = ''
  acceptAttachUrl.value = ''
  acceptAttachSize.value = 0
  acceptVisible.value = true
  void warnOpenTickets(target.id, target.name)
}

async function warnOpenTickets(projectId: number, projectName: string) {
  try {
    const n = await countOpenTickets(projectId)
    if (n > 0) {
      ElMessage.warning(
        `「${projectName}」还有 ${n} 张未关闭协作工单（不阻断验收，请知悉）`,
      )
    }
  } catch {
    /* ignore */
  }
}

function onAcceptResultChange() {
  acceptFormRef.value?.clearValidate(['leftover_summary'])
}

function acceptUploadsUrl(path?: string | null) {
  const p = (path || '').trim().replace(/^\/+/, '')
  if (!p) return ''
  if (/^https?:\/\//i.test(p) || p.startsWith('/uploads/')) return p
  return `/uploads/${p}`
}

function acceptFileKind(name: string): 'image' | 'pdf' | 'doc' | 'other' {
  const n = (name || '').toLowerCase()
  if (/\.(jpe?g|png|gif|webp|bmp)$/.test(n)) return 'image'
  if (n.endsWith('.pdf')) return 'pdf'
  if (/\.(docx?|xlsx?|pptx?|txt)$/.test(n)) return 'doc'
  return 'other'
}

const acceptAttachKind = computed(() => acceptFileKind(acceptForm.attachment))
const acceptAttachExt = computed(() => {
  const name = acceptForm.attachment || ''
  const ext = name.includes('.') ? name.split('.').pop() : ''
  return (ext || 'FILE').toUpperCase()
})
const acceptAttachKindLabel = computed(() => {
  const kind = acceptAttachKind.value
  if (kind === 'image') return '图片预览'
  if (kind === 'pdf') return 'PDF 预览'
  if (kind === 'doc') return '办公文档'
  return '附件'
})
const acceptAttachSizeLabel = computed(() => {
  const n = acceptAttachSize.value
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
})

function triggerAcceptUpload() {
  acceptFileRef.value?.click()
}

async function onAcceptFileChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  saving.value = true
  try {
    const { data } = await uploadFile(file, 'acceptance_proof')
    acceptForm.attachment = data.filename
    acceptForm.attachment_path = data.path
    acceptAttachUrl.value = data.url || acceptUploadsUrl(data.path)
    acceptAttachSize.value = Number(data.size || file.size || 0)
    acceptFormRef.value?.validateField('attachment')
  } finally {
    saving.value = false
  }
}

async function onAccept() {
  const ok = await acceptFormRef.value?.validate().catch(() => false)
  if (!ok || !acceptForm.project_id) return
  if (acceptForm.result === 'conditional' && !acceptForm.leftover_summary.trim()) {
    ElMessage.warning('有条件通过须填写遗留问题')
    return
  }
  saving.value = true
  try {
    await acceptProject(acceptForm.project_id, {
      result: acceptForm.result,
      accepted_at: acceptForm.accepted_at,
      method: acceptForm.method,
      conclusion: acceptForm.conclusion,
      leftover_summary: acceptForm.leftover_summary.trim() || undefined,
      attachment: acceptForm.attachment,
      attachment_path: acceptForm.attachment_path || undefined,
      owner_id: userStore.user?.id,
    })
    ElMessage.success('验收已提交，请到审批中心处理')
    acceptVisible.value = false
    await reloadAll()
  } finally {
    saving.value = false
  }
}

function financeMoney(v?: number | string | null) {
  const n = Number(v || 0)
  if (Number.isNaN(n)) return '0.00'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function financeSettleHint(row: Project) {
  const paid = financeMoney(row.contract_paid_amount)
  const amount = financeMoney(row.contract_amount)
  if (row.contract_collection_complete) return `回款已收齐 ¥${paid}`
  return `未收齐 ¥${paid} / ¥${amount}`
}

async function onFinanceCheck(row: Project) {
  if (row.finance_check_status === 'pending') {
    ElMessage.warning('财务核对已在审批中')
    return
  }
  const paid = financeMoney(row.contract_paid_amount)
  const amount = financeMoney(row.contract_amount)
  const complete = !!row.contract_collection_complete
  const message = complete
    ? `合同回款已收齐（¥${paid} / ¥${amount}）。\n确认提交「${row.name}」财务核对到审批中心？`
    : `合同回款尚未收齐（已到账 ¥${paid} / 合同金额 ¥${amount}）。\n仍可提交，但财务审批时未收齐将无法通过。\n确认提交「${row.name}」？`
  await ElMessageBox.confirm(message, '提交财务核对', {
    type: complete ? 'info' : 'warning',
    confirmButtonText: '提交审批',
    cancelButtonText: '取消',
    dangerouslyUseHTMLString: false,
  })
  await setProjectFinanceCheck(row.id)
  ElMessage.success(
    complete ? '财务核对已提交，请到审批中心处理' : '已提交；回款未收齐时财务无法通过，请先完成到款核销',
  )
  await reloadAll()
}

function openLeftover(row: Project, canClose = false) {
  leftoverRow.value = row
  leftoverCanClose.value = canClose && !!row.leftover_summary && !row.leftover_closed
  leftoverVisible.value = true
}

async function confirmCloseLeftover() {
  const row = leftoverRow.value
  if (!row) return
  saving.value = true
  try {
    await setProjectLeftoverClosed(row.id, true)
    ElMessage.success('遗留问题已关闭')
    leftoverVisible.value = false
    await reloadAll()
  } finally {
    saving.value = false
  }
}

async function onComplete(row: Project) {
  if (!row.finance_check_passed) {
    ElMessage.warning('财务核对未通过，不可结项')
    return
  }
  if (row.leftover_summary && !row.leftover_closed) {
    ElMessage.warning('遗留问题未关闭，不可结项')
    return
  }
  if (!row.contract_collection_complete) {
    ElMessage.warning(
      `合同回款尚未收齐（¥${financeMoney(row.contract_paid_amount)} / ¥${financeMoney(row.contract_amount)}），不可结项`,
    )
    return
  }
  await ElMessageBox.confirm(
    `确认结项「${row.name}」？\n回款已收齐 ¥${financeMoney(row.contract_paid_amount)} / ¥${financeMoney(row.contract_amount)}`,
    '结项确认',
    { type: 'warning' },
  )
  await completeProject(row.id)
  ElMessage.success('项目已结项')
  await reloadAll()
}

async function reloadAll() {
  await Promise.all([loadStats(), loadProjects()])
  if (tab.value === 'execute' && executeMode.value === 'plan') await loadPlanDetail()
  if (tab.value === 'execute' && executeMode.value === 'tasks') {
    await loadTasks()
    await loadTaskStats()
  }
  if (tab.value === 'initiation') await loadResourceNeeds()
}

function normalizeTab(raw?: string | null): TabKey {
  if (raw === 'board') return 'portfolio'
  if (raw === 'plan' || raw === 'tasks') return 'execute'
  if (ALL_TABS.some((t) => t.key === raw)) return raw as TabKey
  return workbench.value === 'delivery' ? 'initiation' : 'portfolio'
}

function syncWorkbenchRoute() {
  const raw = route.query.tab as string | undefined
  const lifecycleTabs: TabKey[] = ['initiation', 'execute', 'acceptance']
  if (raw === 'department') {
    router.replace({ path: '/', query: { focus: 'dept-monitor' } })
    return true
  }
  if (workbench.value === 'portfolio') {
    if (lifecycleTabs.includes(raw as TabKey) || raw === 'plan' || raw === 'tasks') {
      router.replace({
        path: '/projects/delivery',
        query: { ...route.query, tab: normalizeTab(raw) },
      })
      return true
    }
  } else if (raw === 'portfolio' || raw === 'board') {
    router.replace({
      path: '/projects',
      query: { ...route.query, tab: raw === 'portfolio' ? undefined : raw },
    })
    return true
  }
  return false
}

watch(
  () =>
    [
      route.path,
      String(route.query.tab || ''),
      String(route.query.mode || ''),
      String(route.query.project_id || ''),
    ] as const,
  async () => {
    if (syncWorkbenchRoute()) return
    await applyRouteTabAndLoad()
  },
  { immediate: true },
)

async function applyRouteTabAndLoad() {
  const raw = route.query.tab as string
  const mode = String(route.query.mode || '')
  if (raw === 'board') overviewMode.value = 'board'
  else if (workbench.value === 'portfolio') overviewMode.value = 'list'

  const nextTab = normalizeTab(raw)
  tab.value = nextTab

  if (nextTab === 'execute') {
    if (raw === 'tasks' || mode === 'tasks') executeMode.value = 'tasks'
    else if (raw === 'plan' || mode === 'plan' || !mode) executeMode.value = 'plan'
  } else {
    executeMode.value = 'plan'
    taskProjectFilter.value = undefined
  }

  const pid = Number(route.query.project_id)
  if (Number.isFinite(pid) && pid > 0) {
    planProjectId.value = pid
    if (nextTab === 'execute' && executeMode.value === 'tasks') {
      taskProjectFilter.value = pid
    }
  } else if (nextTab === 'execute' && executeMode.value === 'tasks') {
    // URL 未带项目时，不强制聚焦
  } else if (nextTab !== 'execute') {
    taskProjectFilter.value = undefined
  }

  await reloadAll()
  if (tab.value === 'execute') {
    if (executeMode.value === 'plan') {
      taskProjectFilter.value = undefined
      await ensurePlanProject()
    } else {
      await loadTasks()
      await loadTaskStats()
    }
  }
  if (tab.value === 'initiation') await loadResourceNeeds()
}
</script>

<style scoped>
.submode-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.submode-hint {
  margin-left: 12px;
}
.muted {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.table-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 12px;
  color: var(--crm-ink-soft);
}
.task-logic-hint {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--crm-surface-soft, #f7f7f7);
  color: var(--crm-ink-soft);
  font-size: 12px;
  line-height: 1.5;
}
.task-logic-hint b {
  color: var(--crm-ink, #303133);
  font-weight: 600;
}
.kpi-clickable {
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.15s ease;
}
.kpi-clickable:hover {
  background: var(--crm-surface-soft, #f5f7fa);
}
.card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}
.sub {
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.role-assign-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.role-assign-head,
.role-assign-row {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}
.role-assign-head {
  color: var(--crm-ink-soft);
  font-size: 12px;
  line-height: 1;
  padding: 0 2px;
}
.role-col-dept {
  flex: 1.1;
  min-width: 0;
}
.role-col-user {
  flex: 1;
  min-width: 0;
}
.role-col-hours {
  flex: 0 0 120px;
  width: 120px;
}
.role-col-action {
  flex: 0 0 44px;
  width: 44px;
  padding: 0 !important;
  justify-content: center;
}
.hours-over {
  color: oklch(0.5 0.16 25);
}
.task-budget-hint {
  margin: -4px 0 0;
  line-height: 1.4;
}
.dialog-flow-hint {
  margin: 0 0 12px;
  color: var(--crm-ink-soft);
  font-size: 12px;
}
.ms-dialog-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.ms-dialog-form :deep(.form-block) {
  margin-bottom: 12px;
  padding-bottom: 4px;
}
.ms-dialog-form :deep(.form-block h3) {
  margin-bottom: 10px;
}
.ms-meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.ms-block-tip {
  margin: -4px 0 0;
  line-height: 1.45;
}
.ms-owner-opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.ms-owner-opt small {
  color: var(--crm-ink-soft);
  font-size: 12px;
  flex: none;
}
.ms-row-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ms-row-actions .text-danger {
  color: #c45656;
}
.init-date-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.accept-meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.accept-meta-row :deep(.el-form-item) {
  margin-bottom: 12px;
}
.task-form-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: 8px;
  align-items: start;
}
.task-create-form :deep(.el-form-item) {
  margin-bottom: 16px;
}
.task-form-row :deep(.el-form-item) {
  margin-bottom: 0;
}
.task-form-row :deep(.el-form-item__content) {
  min-width: 0;
}
.task-hours-field {
  display: inline-flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 8px;
  white-space: nowrap;
}
.task-hours-input {
  width: 128px;
}
.task-hours-unit {
  flex: none;
  color: var(--crm-ink-soft);
  font-size: 13px;
  line-height: 32px;
  white-space: nowrap;
}
.init-dialog-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.init-dialog-form :deep(.form-block) {
  margin-bottom: 12px;
  padding-bottom: 8px;
}
.init-dialog-form :deep(.form-block h3) {
  margin-bottom: 8px;
}
.init-defer-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--crm-surface-soft, #f7f7f7);
  border: 1px dashed var(--el-color-warning-light-5, #f3d19e);
}
.card-top-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  align-items: center;
}
.deferred-reason {
  margin: 0 0 8px;
  line-height: 1.4;
}
.health-hint {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--crm-surface-soft, #f7f7f7);
  font-size: 12px;
  color: var(--crm-ink-soft);
}
.accept-attach {
  width: 100%;
}
.accept-attach.uploaded {
  border: 1px solid var(--el-color-success-light-5, #b3e19d);
  border-radius: 12px;
  padding: 12px;
  background: #f8fff6;
}
.accept-attach-preview {
  width: 100%;
  min-height: 160px;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--crm-border, #ebeef5);
}
.accept-attach-image {
  width: 100%;
  height: 220px;
  display: block;
  cursor: zoom-in;
  background: #f5f7fa;
}
.accept-attach-image :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.accept-attach-pdf {
  width: 100%;
  height: 280px;
  border: 0;
  display: block;
  background: #f5f7fa;
}
.accept-doc-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 120px;
  padding: 18px 16px;
}
.accept-doc-ext {
  flex: none;
  min-width: 56px;
  height: 56px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(145deg, #3b6ef5, #1f4fd6);
}
.accept-doc-card strong {
  display: block;
  font-size: 14px;
  line-height: 1.35;
  word-break: break-all;
}
.accept-doc-card small {
  display: block;
  margin-top: 6px;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
}
.accept-attach-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 10px;
}
.accept-attach-actions a {
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
}
.upload-box {
  border: 1.5px dashed var(--crm-border, #dcdfe6);
  border-radius: 12px;
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--crm-surface-soft, #f7f7f7);
  width: 100%;
  display: block;
  color: inherit;
  font: inherit;
}
.upload-box:hover {
  border-color: var(--el-color-primary);
}
.upload-box b {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
}
.upload-box small {
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
}

.resource-summary {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid var(--crm-border, #ebeef5);
  border-radius: 10px;
  background: var(--crm-surface-soft, #f7f8fa);
}
.resource-summary-main {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--crm-border, #e4e7ed);
}
.resource-summary-main small,
.resource-summary-grid small {
  display: block;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
  line-height: 1.2;
}
.resource-summary-main b {
  display: block;
  margin-top: 4px;
  font-size: 16px;
  line-height: 1.3;
  color: var(--crm-ink, #303133);
}
.resource-summary-project {
  display: block;
  margin-top: 4px;
  color: var(--crm-ink-soft, #909399);
  font-size: 12px;
  line-height: 1.4;
}
.resource-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.resource-summary-grid b {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.35;
  color: var(--crm-ink, #303133);
  word-break: break-word;
}
.resource-action-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.resource-action-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--crm-border, #dcdfe6);
  border-radius: 10px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.resource-action-card:hover {
  border-color: var(--el-color-primary-light-5, #a0cfff);
}
.resource-action-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9, #ecf5ff);
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
}
.resource-action-card.danger {
  border-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9, #fef0f0);
  box-shadow: inset 0 0 0 1px var(--el-color-danger);
}
.resource-action-radio {
  flex: none;
  width: 14px;
  height: 14px;
  margin-top: 3px;
  border: 1.5px solid var(--crm-border, #c0c4cc);
  border-radius: 50%;
  background: #fff;
  position: relative;
}
.resource-action-card.active .resource-action-radio {
  border-color: var(--el-color-primary);
}
.resource-action-card.danger .resource-action-radio {
  border-color: var(--el-color-danger);
}
.resource-action-card.active .resource-action-radio::after {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 50%;
  background: var(--el-color-primary);
}
.resource-action-card.danger .resource-action-radio::after {
  background: var(--el-color-danger);
}
.resource-action-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.resource-action-copy strong {
  font-size: 14px;
  font-weight: 600;
  color: var(--crm-ink, #303133);
  line-height: 1.3;
}
.resource-action-copy small {
  font-size: 12px;
  color: var(--crm-ink-soft, #909399);
  line-height: 1.4;
}
.resource-detail-form {
  margin-top: 2px;
}
.resource-detail-form.soft {
  margin-top: 4px;
  padding: 12px 12px 2px;
  border-radius: 10px;
  background: var(--crm-surface-soft, #f7f8fa);
  border: 1px solid var(--crm-border, #ebeef5);
}
.resource-detail-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.resource-adjust-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0 12px;
}
@media (max-width: 768px) {
  /* 解除一屏锁定，项目台账可整页滑动 */
  .project-delivery.crm-fit-page {
    height: auto;
    min-height: 100%;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  .project-delivery .crm-fit-body {
    flex: none;
    min-height: 0;
    overflow: visible;
  }

  .project-delivery .crm-fit-body.is-scroll {
    overflow: visible;
  }

  .project-delivery :deep(.crm-fit-panel),
  .project-delivery :deep(.crm-panel.crm-fit-panel) {
    flex: none;
    overflow: visible;
  }

  .project-delivery :deep(.crm-table-wrap.is-fit),
  .project-delivery :deep(.crm-table-wrap) {
    flex: none;
    min-height: 0;
    overflow-x: auto;
    overflow-y: visible;
    -webkit-overflow-scrolling: touch;
  }

  .submode-bar {
    margin-bottom: 10px;
  }

  .submode-hint {
    margin-left: 0;
    width: 100%;
  }

  .board-legend {
    width: 100%;
    justify-content: flex-start;
  }

  .table-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .ms-meta-row,
  .init-date-row,
  .accept-meta-row,
  .task-form-row,
  .resource-summary-grid,
  .resource-adjust-row {
    grid-template-columns: 1fr;
  }

  .task-hours-field {
    width: 100%;
    justify-content: flex-start;
  }

  .task-hours-input {
    width: 100%;
    max-width: 160px;
  }

  .card-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .ms-row-actions {
    width: 100%;
  }

  .resource-summary {
    gap: 10px;
  }
}
</style>
