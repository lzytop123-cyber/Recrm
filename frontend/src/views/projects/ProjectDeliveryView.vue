<template>
  <div class="crm-page project-delivery">
    <header class="sales-head">
      <div class="sales-head-copy">
        <h1>{{ workbench === 'portfolio' ? '项目台账' : '交付执行' }}</h1>
        <p>{{ workbenchDesc }}</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="workbench === 'portfolio'" type="primary" @click="openInitiation">
          ＋ 发起项目立项
        </el-button>
        <el-button v-else-if="tab === 'initiation'" type="primary" @click="openInitiation">
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

    <div v-if="workbench === 'delivery'" class="project-tabs">
      <button
        v-for="item in visibleTabs"
        :key="item.key"
        type="button"
        class="project-tab"
        :class="{ active: tab === item.key }"
        @click="setTab(item.key)"
      >
        {{ item.label }}
      </button>
    </div>

    <!-- 项目台账：列表 / 看板 / 本部门 -->
    <template v-if="tab === 'portfolio'">
      <div class="submode-bar">
        <el-radio-group v-model="overviewMode" size="small" @change="onOverviewModeChange">
          <el-radio-button value="list">列表</el-radio-button>
          <el-radio-button value="board">看板</el-radio-button>
          <el-radio-button value="department">本部门</el-radio-button>
        </el-radio-group>
      </div>

      <template v-if="overviewMode === 'board'">
      <div class="project-board-shell">
        <section class="project-board-summary">
          <article class="project-board-stat">
            <small>本期项目</small>
            <strong>{{ stats?.total ?? 0 }}</strong>
            <span>覆盖三类主营业务</span>
          </article>
          <article class="project-board-stat">
            <small>执行中</small>
            <strong>{{ stats?.executing ?? 0 }}</strong>
            <span>交付推进中</span>
          </article>
          <article class="project-board-stat">
            <small>进度偏差</small>
            <strong style="color: oklch(0.5 0.16 25)">{{ boardDeviation }}</strong>
            <span>健康度需关注或高风险</span>
          </article>
          <article class="project-board-stat">
            <small>待内部验收</small>
            <strong>{{ stats?.accepting ?? 0 }}</strong>
            <span>组织验收闭环</span>
          </article>
          <article class="project-board-stat">
            <small>待负责人介入</small>
            <strong style="color: oklch(0.5 0.12 70)">{{ (stats?.high_risk ?? 0) + (stats?.leftover ?? 0) }}</strong>
            <span>风险或遗留异常</span>
          </article>
        </section>

        <div class="project-board-toolbar">
          <div class="filters">
            <el-input
              v-model="keyword"
              placeholder="搜索项目、编号、负责人"
              clearable
              style="width: 250px"
            />
            <el-select v-model="boardType" clearable placeholder="全部业务" style="width: 160px">
              <el-option v-for="opt in PROJECT_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </div>
          <div class="board-legend">
            <span><i style="background: oklch(0.5 0.16 25)"></i>高风险</span>
            <span><i style="background: oklch(0.55 0.12 70)"></i>需关注</span>
            <span><i style="background: var(--crm-success)"></i>正常</span>
          </div>
        </div>

        <div class="project-kanban-scroll">
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
      </div>
      </template>

      <template v-else-if="overviewMode === 'list'">
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

      <section class="crm-panel">
        <div class="toolbar">
          <div class="filters">
            <el-input
              v-model="keyword"
              placeholder="搜索项目编号/名称"
              clearable
              style="width: 220px"
              @keyup.enter="loadProjects"
              @clear="loadProjects"
            />
            <el-select
              v-model="statusFilter"
              clearable
              placeholder="状态"
              style="width: 140px"
              @change="onStatusFilterChange"
            >
              <el-option v-for="(label, key) in PROJECT_STATUS_LABEL" :key="key" :label="label" :value="key" />
            </el-select>
            <el-button @click="loadProjects">查询</el-button>
          </div>
        </div>
        <el-table :data="listProjects" v-loading="loading" stripe @row-click="goDetail">
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
        <div class="table-footer">
          <span class="muted">点击行查看项目档案</span>
          <span>共 {{ listProjectTotal }} 个项目</span>
        </div>
      </section>
      </template>

      <template v-else>
      <section class="department-head" v-loading="deptLoading">
        <article class="dept-focus">
          <div>
            <el-tag size="small" type="info">部门负责人视角</el-tag>
            <h2>{{ deptMonitor?.department_name || '本部门' }} · 本周执行监控</h2>
            <p>从任务、工时、工单异常下钻到具体责任记录。</p>
          </div>
          <div class="dept-score">
            <strong>{{ deptMonitor?.health_score ?? 0 }}</strong>
            <small>执行健康分</small>
          </div>
        </article>
        <article class="portfolio-mini">
          <small>任务按期率</small>
          <strong>{{ formatRate(deptMonitor?.on_time_rate) }}%</strong>
          <span>逾期 {{ deptMonitor?.overdue_tasks ?? 0 }} 项</span>
        </article>
        <article class="portfolio-mini">
          <small>工时填报完整率</small>
          <strong>{{ formatRate(deptMonitor?.hours_complete_rate) }}%</strong>
          <span>缺失 {{ deptMonitor?.missing_hours ?? 0 }} 项</span>
        </article>
        <article class="portfolio-mini">
          <small>待处理异常</small>
          <strong>{{ (deptMonitor?.overdue_tasks ?? 0) + (deptMonitor?.missing_hours ?? 0) }}</strong>
          <span>逾期与缺报合计</span>
        </article>
      </section>

      <section class="crm-panel">
        <div class="card-head" style="margin-bottom: 12px">
          <div>
            <b>员工执行情况</b>
            <p class="muted" style="margin: 4px 0 0">仅展示本部门授权数据</p>
          </div>
        </div>
        <el-table :data="deptMonitor?.members || []" stripe>
          <el-table-column prop="name" label="员工" width="120" />
          <el-table-column prop="planned_tasks" label="计划任务" width="100" />
          <el-table-column prop="done_tasks" label="完成" width="80" />
          <el-table-column prop="overdue_tasks" label="逾期" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.overdue_tasks > 0 ? 'oklch(0.5 0.16 25)' : undefined }">
                {{ row.overdue_tasks }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="计划 / 实际工时" width="140">
            <template #default="{ row }">
              {{ formatHours(row.planned_hours) }} / {{ formatHours(row.actual_hours) }}h
            </template>
          </el-table-column>
          <el-table-column label="工时完整" width="100">
            <template #default="{ row }">{{ formatRate(row.hours_complete_rate) }}%</template>
          </el-table-column>
          <el-table-column prop="open_tickets" label="待处理工单" width="110" />
        </el-table>
        <div v-if="!(deptMonitor?.members || []).length" class="placeholder-panel" style="margin-top: 12px">
          暂无本部门任务数据。可在「执行 → 任务工时」中创建并指派责任人后查看汇总。
        </div>
      </section>
      </template>
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
            <el-tag :type="handoffReady(row) ? 'success' : 'danger'" size="small">
              {{ handoffReady(row) ? '可发起' : '条件未满足' }}
            </el-tag>
          </div>
          <div class="handoff-checks">
            <span :class="{ failed: !row.contract_active_ok }">
              {{ row.contract_active_ok ? '✓' : '⚠' }} 合同已签署
            </span>
            <span :class="{ failed: !paymentOk(row) }">
              {{ paymentOk(row) ? '✓' : '⚠' }} 已确认到账
            </span>
          </div>
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
              来自立项时勾选的所需角色，由部门负责人确认成员、投入和排期
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
              <small>有效进度</small>
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
          <small>计划 / 实际工时</small>
          <strong>{{ formatHours(taskHours.planned) }} / {{ formatHours(taskHours.actual) }}h</strong>
          <span>{{ taskHours.planned ? '在「任务工时」查看 →' : '尚未拆任务，点此去新建 →' }}</span>
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
          <h3>{{ planBaselineLocked ? '基线已锁定，可以开始执行' : '先确认基线，再决定怎么拆' }}</h3>
          <p>
            {{
              planBaselineLocked
                ? '当前未添加计划节点。简单项目建议直接拆任务；需要阶段验收时再补节点。'
                : '确认基线后，计划范围生效。之后改范围请用右上角「申请基线变更」。'
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
          <el-table-column label="计划日期" width="100">
            <template #default="{ row }">{{ formatShortDate(row.deadline) }}</template>
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
              <span :class="{ muted: row.status === 'done' && row.evidence_status === 'confirmed', 'text-warn': row.status === 'done' && row.evidence_status !== 'confirmed' }">
                {{ row.next_action || '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <button
                v-if="milestonePrimaryActionLabel(row)"
                type="button"
                class="text-link"
                @click="onMilestonePrimaryAction(row)"
              >
                {{ milestonePrimaryActionLabel(row) }}
              </button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="milestones.length && planBaselineLocked" class="plan-table-footer">
          <span v-if="planEvidencePendingCount" class="text-warn">
            有 {{ planEvidencePendingCount }} 个节点证据待确认
          </span>
          <span v-else-if="planNodesWithoutTaskCount" class="muted">
            有节点尚未拆任务，建议先建任务再推进
          </span>
          <span v-else class="muted">节点与证据正常</span>
          <el-button type="primary" link @click="goToTasksWorkbench">去任务工时</el-button>
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
              <div>
                <b>风险与问题</b>
                <span class="muted" style="display: block; margin-top: 4px; font-weight: 400">
                  影响范围、责任人和处理期限可追溯
                </span>
              </div>
              <button v-if="canManagePlan" type="button" class="text-link" @click="openRiskDialog">＋ 新增</button>
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
              <div>
                <b>变更记录</b>
                <span class="muted" style="display: block; margin-top: 4px; font-weight: 400">
                  改范围请用右上角「申请基线变更」
                </span>
              </div>
              <button
                v-if="canManagePlan && planBaselineLocked"
                type="button"
                class="text-link"
                @click="openChangeDialog"
              >
                ＋ 申请变更
              </button>
            </div>
            <div class="plan-change-list">
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
              <div v-if="!planChanges.length" class="plan-empty" style="border: 0; padding-top: 0">
                暂无变更申请
              </div>
            </div>
          </article>
        </section>

        <section class="crm-panel" style="margin-top: 14px">
          <div class="card-head plan-panel-head">
            <div>
              <b>人员档期</b>
              <span class="muted" style="margin-left: 8px">
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
        <div>
          <small>计划 / 实际工时</small>
          <b>{{ formatHours(taskStats?.planned_hours) }} / {{ formatHours(taskStats?.actual_hours) }}h</b>
        </div>
        <div>
          <small>关联工单</small>
          <b>{{ taskStats?.linked_tickets ?? 0 }}</b>
        </div>
      </section>

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
              仅看当前项目
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
          <el-table-column prop="project_name" label="所属项目" min-width="140" show-overflow-tooltip />
          <el-table-column label="所属里程碑" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.milestone_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="assignee_name" label="责任人" width="100" />
          <el-table-column prop="department_name" label="部门" width="110" />
          <el-table-column label="截止日期" width="110">
            <template #default="{ row }">{{ formatDate(row.due_date) || '—' }}</template>
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
              <b>{{ row.name }}</b>
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
          <el-table-column label="遗留问题" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.leftover_summary || '—' }}
              <span v-if="row.leftover_summary && row.leftover_closed">（已关闭）</span>
            </template>
          </el-table-column>
          <el-table-column label="财务核对" width="110">
            <template #default="{ row }">
              <template v-if="row.finance_check_status === 'pending'">审批中</template>
              <template v-else-if="row.finance_check_passed || row.finance_check_status === 'approved'">
                已通过
              </template>
              <template v-else-if="row.finance_check_status === 'rejected'">已驳回</template>
              <template v-else-if="row.status === 'accepted' || row.status === 'completed'">
                未提交
              </template>
              <template v-else>—</template>
            </template>
          </el-table-column>
          <el-table-column label="当前状态" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ PROJECT_STATUS_LABEL[row.status] || row.status }}</el-tag>
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
                  @click="onCloseLeftover(row)"
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
                    (row.finance_check_passed || row.finance_check_status === 'approved')
                  "
                  v-perm.any="['project:complete', 'project:manage']"
                  link
                  type="success"
                  @click="onComplete(row)"
                >
                  结项
                </el-button>
              </template>
              <span v-else-if="row.status === 'completed'" class="muted">已结项</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">
          <span>流程：内部验收通过 → 提交财务核对（审批中心）→ 结项</span>
        </div>
      </section>
    </template>

    <!-- 资源确认弹窗 -->
    <el-dialog
      v-model="resourceVisible"
      :title="resourceTarget ? `确认${resourceTarget.role_name}投入` : '部门资源确认'"
      width="560px"
      destroy-on-close
    >
      <template v-if="resourceTarget">
        <div class="handoff-meta" style="margin-bottom: 14px">
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
        <el-radio-group v-model="resourceForm.action" style="display: flex; flex-direction: column; gap: 8px">
          <el-radio value="accept" border>确认投入 — 按建议成员与投入量确认</el-radio>
          <el-radio value="adjust" border>调整后确认 — 更换成员或调整投入</el-radio>
          <el-radio value="reject" border>暂不接受 — 说明冲突并退回协调</el-radio>
        </el-radio-group>
        <el-form label-position="top" style="margin-top: 14px">
          <el-form-item v-if="resourceForm.action === 'adjust'" label="确认成员">
            <el-select
              v-model="resourceForm.confirmed_user_id"
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
          <el-form-item v-if="resourceForm.action === 'adjust'" label="计划投入（小时）">
            <el-input-number v-model="resourceForm.planned_hours" :min="1" :max="9999" style="width: 100%" />
          </el-form-item>
          <el-form-item
            :label="resourceForm.action === 'reject' ? '拒绝说明' : '确认说明'"
            :required="resourceForm.action === 'reject'"
          >
            <el-input
              v-model="resourceForm.note"
              type="textarea"
              :rows="3"
              :placeholder="
                resourceForm.action === 'reject'
                  ? '说明冲突原因，便于协调替代'
                  : '可选：补充排期、可用性或注意事项'
              "
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="resourceVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onConfirmResource">提交</el-button>
      </template>
    </el-dialog>

    <!-- 立项弹窗 -->
    <el-dialog v-model="initVisible" title="发起项目立项" width="680px" destroy-on-close class="claim-dialog">
      <p class="dialog-eyebrow">商务交接</p>
      <el-form ref="initFormRef" :model="initForm" :rules="initRules" label-position="top">
        <section class="form-block">
          <h3><span>1</span>客户合同与类型</h3>
          <el-form-item label="客户合同" prop="contract_id">
            <el-select
              v-model="initForm.contract_id"
              filterable
              remote
              :remote-method="searchContracts"
              :loading="contractLoading"
              placeholder="选择已签署且尚未立项的合同"
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
              <el-option v-for="opt in PROJECT_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
        </section>
        <section class="form-block">
          <h3><span>2</span>目标与范围</h3>
          <el-form-item label="项目名称 / 目标" prop="name">
            <el-input v-model="initForm.name" placeholder="项目目标简述" />
          </el-form-item>
          <el-form-item label="交付范围摘要" prop="scope_desc">
            <el-input v-model="initForm.scope_desc" type="textarea" :rows="3" />
          </el-form-item>
        </section>
        <section class="form-block">
          <h3><span>3</span>负责人、角色与周期</h3>
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
            <div class="sub" style="margin-top: 4px">由直属负责人或经营管理角色确认。</div>
          </el-form-item>
          <el-form-item label="所需部门" required>
            <div class="role-assign-list">
              <div v-for="(row, idx) in initForm.resource_roles" :key="idx" class="role-assign-row">
                <el-select
                  v-model="row.role_name"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="飞书部门"
                  style="flex: 1.1"
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
                  placeholder="指定人员"
                  style="flex: 1"
                >
                  <el-option
                    v-for="m in membersForRole(row.role_name)"
                    :key="m.id"
                    :label="memberLabel(m)"
                    :value="m.id"
                  />
                </el-select>
                <el-button text type="danger" @click="removeRoleRow(idx)">移除</el-button>
              </div>
              <el-button type="primary" link @click="addRoleRow">+ 添加角色</el-button>
            </div>
            <div class="sub" style="margin-top: 6px">
              {{ roleOptionsHint || '选项来自飞书通讯录真实部门，可指定具体人员；提交后进入「待确认资源」由部门确认。' }}
            </div>
          </el-form-item>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px">
            <el-form-item label="计划开始">
              <el-date-picker v-model="initForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
            <el-form-item label="计划结束">
              <el-date-picker v-model="initForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </div>
          <el-form-item label="立项门槛（系统核验）">
            <div class="handoff-checks init-gate-checks">
              <span :class="{ failed: !initGate.contractOk }">
                {{ initGate.contractOk ? '✓' : '⚠' }} 合同已签署
              </span>
              <span :class="{ failed: !initGate.paymentOk }">
                {{ initGate.paymentOk ? '✓' : '⚠' }} 已确认到账
              </span>
            </div>
            <div class="sub" style="margin-top: 6px">
              须选择已签署合同，且该合同在「到款核销」中至少有一笔财务已确认到账，才能提交立项。
            </div>
          </el-form-item>
          <div class="health-hint">
            <div><span>✓</span> 提交后由涉及部门确认资源投入</div>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="initVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreateProject">提交立项申请</el-button>
      </template>
    </el-dialog>

    <!-- 里程碑弹窗 -->
    <el-dialog v-model="msVisible" title="添加里程碑" width="520px" destroy-on-close>
      <el-form :model="msForm" label-width="100px">
        <el-form-item label="里程碑名称" required>
          <el-input v-model="msForm.name" />
        </el-form-item>
        <el-form-item label="责任角色">
          <el-input v-model="msForm.role" placeholder="如：交付经理" />
        </el-form-item>
        <el-form-item label="计划日期">
          <el-date-picker v-model="msForm.deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="必交成果">
          <el-input v-model="msForm.deliverable" />
        </el-form-item>
        <el-form-item label="完成证据">
          <el-input v-model="msForm.evidence" placeholder="文档/链接说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="msVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onAddMilestone">保存</el-button>
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
        <h3><span>2</span>计划节点（可选）</h3>
        <div class="plan-check-list">
          <div v-for="row in baselineMilestoneChecks" :key="row.name" class="plan-check-row">
            <span :class="{ ok: row.ok }">{{ row.ok ? '✓' : '⚠' }} {{ row.name }}</span>
            <b>{{ row.detail }}</b>
          </div>
          <div v-if="!baselineMilestoneChecks.length" class="plan-empty">
            未添加也可确认基线；复杂项目建议补节点，便于跟踪进度与验收证据
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
                  ? 'ⓘ 项目角色'
                  : baselineReleaseChecks.rolesOk
                    ? '✓ 项目角色'
                    : '⚠ 项目角色'
              }}
            </span>
            <b>{{
              !milestones.length
                ? '无计划节点，确认后按任务推进'
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
        <el-button @click="baselineVisible = false">保存草稿</el-button>
        <el-button type="primary" :loading="saving" @click="confirmBaseline">提交基线确认</el-button>
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
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-width="110px">
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
        <el-form-item
          label="所属节点"
          prop="milestone_id"
          :required="openTaskMilestones.length > 0"
        >
          <el-select
            v-model="taskForm.milestone_id"
            filterable
            clearable
            style="width: 100%"
            :placeholder="taskNodePlaceholder"
            :loading="taskMilestoneLoading"
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
          <el-input v-model="taskForm.title" />
        </el-form-item>
        <el-form-item label="完成标准" prop="criteria">
          <el-input v-model="taskForm.criteria" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-select
            v-model="taskForm.assignee_id"
            filterable
            remote
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
        </el-form-item>
        <el-form-item label="截止日期" prop="due_date">
          <el-date-picker v-model="taskForm.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="计划工时" prop="planned_hours">
          <el-input-number v-model="taskForm.planned_hours" :min="0" :precision="1" style="width: 100%" />
        </el-form-item>
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
      width="560px"
      destroy-on-close
      class="claim-dialog"
    >
      <template v-if="evidenceTarget">
        <div class="evidence-dialog-meta">
          <div>
            <small>里程碑</small>
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

        <template v-if="evidenceMode === 'review'">
          <div class="evidence-review-box">
            <small>证据内容</small>
            <p>{{ evidenceTarget.evidence }}</p>
            <small v-if="evidenceTarget.evidence_reject_reason" class="evidence-reject">
              上次驳回：{{ evidenceTarget.evidence_reject_reason }}
            </small>
            <small v-else-if="evidenceTarget.evidence_confirmed_by_name" class="evidence-ok">
              {{ evidenceTarget.evidence_confirmed_by_name }} 已确认
            </small>
          </div>
          <p class="muted" style="margin: 12px 0 0">
            {{ evidenceTarget.next_action || '确认后，若无未完成关联任务将自动完成里程碑。' }}
          </p>
        </template>
        <template v-else>
          <p class="muted" style="margin: 0 0 12px">
            提交后由项目负责人确认。可填文档说明或链接。
          </p>
          <el-input
            v-model="evidenceDraft"
            type="textarea"
            :rows="4"
            placeholder="例如：客户确认记录 / 评审纪要链接"
          />
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
        <el-button @click="evidenceVisible = false">取消</el-button>
        <template v-if="evidenceTarget && evidenceMode === 'review' && canConfirmEvidence(evidenceTarget)">
          <el-button :loading="saving" @click="rejectEvidence(evidenceTarget)">驳回</el-button>
          <el-button type="primary" :loading="saving" @click="confirmEvidence(evidenceTarget)">
            确认证据
          </el-button>
        </template>
        <template v-else-if="evidenceMode === 'review'">
          <el-button type="primary" @click="evidenceMode = 'fill'">修改并重提</el-button>
        </template>
        <el-button
          v-else
          type="primary"
          :loading="saving"
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
    <el-dialog v-model="acceptVisible" title="发起内部验收" width="640px" destroy-on-close>
      <el-form ref="acceptFormRef" :model="acceptForm" :rules="acceptRules" label-width="120px">
        <el-form-item label="验收项目" prop="project_id">
          <el-select v-model="acceptForm.project_id" filterable style="width: 100%">
            <el-option
              v-for="p in acceptanceCandidates"
              :key="p.id"
              :label="`${p.project_no} · ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="验收结果" prop="result">
          <el-select v-model="acceptForm.result" style="width: 100%">
            <el-option label="验收通过" value="pass" />
            <el-option label="有条件通过" value="conditional" />
            <el-option label="验收不通过" value="fail" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="验收日期" prop="accepted_at">
          <el-date-picker v-model="acceptForm.accepted_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="验收方式" prop="method">
          <el-select v-model="acceptForm.method" style="width: 100%">
            <el-option label="内部验收单" value="内部验收单" />
            <el-option label="部门负责人确认" value="部门负责人确认" />
            <el-option label="项目评审会议纪要" value="项目评审会议纪要" />
            <el-option label="其他可追溯方式" value="其他可追溯方式" />
          </el-select>
        </el-form-item>
        <el-form-item label="验收负责人">
          <el-input :model-value="userStore.displayName" disabled />
        </el-form-item>
        <el-form-item label="结论与遗留安排" prop="conclusion">
          <el-input
            v-model="acceptForm.conclusion"
            type="textarea"
            :rows="3"
            placeholder="记录内部验收结论、遗留问题、责任人和完成期限"
          />
        </el-form-item>
        <el-form-item label="遗留问题摘要">
          <el-input v-model="acceptForm.leftover_summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="验收附件" prop="attachment">
          <div
            class="upload-box"
            :class="{ uploaded: !!acceptForm.attachment }"
            @click="triggerAcceptUpload"
          >
            <template v-if="acceptForm.attachment">
              <b>{{ acceptForm.attachment }}</b>
              <small>已上传 · 点击可重新选择</small>
            </template>
            <template v-else>
              <b>上传内部验收单或评审材料</b>
              <small>PDF、PNG、JPG · 单文件不超过 20MB</small>
            </template>
          </div>
          <input
            ref="acceptFileRef"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
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
import {
  ACCEPTANCE_RESULT_LABEL,
  HEALTH_LABEL,
  PROJECT_STATUS_LABEL,
  PROJECT_TYPE_OPTIONS,
  TASK_STATUS_LABEL,
  acceptProject,
  addMilestone,
  completeProject,
  confirmProjectResource,
  createProject,
  createProjectTask,
  fetchDepartmentMonitor,
  fetchProjectDetail,
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
  type DepartmentMonitor,
  type Project,
  type ProjectMilestone,
  type ProjectResourceNeed,
  type ProjectStats,
  type ProjectTask,
  type ProjectTaskStats,
  type ResourceRoleMember,
  type ResourceRoleOption,
} from '@/api/projects'
import { fetchContracts, type Contract } from '@/api/contracts'
import { fetchEmployees, type Employee } from '@/api/org'
import { fetchSchedules, SCHEDULE_STATUS_LABEL, type Schedule } from '@/api/schedules'
import { useUserStore } from '@/stores/user'
import { uploadFile } from '@/api/uploads'

type TabKey = 'portfolio' | 'initiation' | 'execute' | 'acceptance'
type OverviewMode = 'list' | 'board' | 'department'
type ExecuteMode = 'plan' | 'tasks'
type Workbench = 'portfolio' | 'delivery'

const ALL_TABS: { key: TabKey; label: string }[] = [
  { key: 'portfolio', label: '项目台账' },
  { key: 'initiation', label: '交接与立项' },
  { key: 'execute', label: '执行' },
  { key: 'acceptance', label: '验收与收尾' },
]

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
}

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

const workbench = computed<Workbench>(() =>
  route.path.startsWith('/projects/delivery') ? 'delivery' : 'portfolio',
)
const visibleTabs = computed(() =>
  workbench.value === 'portfolio'
    ? ALL_TABS.filter((t) => t.key === 'portfolio')
    : ALL_TABS.filter((t) => t.key !== 'portfolio'),
)
const workbenchDesc = computed(() =>
  workbench.value === 'portfolio'
    ? '项目列表、看板与本部门负荷；查档案、看进度从这里进。'
    : '立项交接、计划基线、任务工时与验收结项；日常干活从这里进。',
)

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
const boardKeyword = keyword
const boardType = ref<string | undefined>()
const deptMonitor = ref<DepartmentMonitor | null>(null)
const deptLoading = ref(false)

const planProjectId = ref<number | undefined>()
const planProject = ref<Project | null>(null)
const milestones = ref<ProjectMilestone[]>([])
const planLoading = ref(false)
const planSchedules = ref<Schedule[]>([])
const planSchedulesLoading = ref(false)
const taskHours = ref({ planned: 0, actual: 0 })

const tasks = ref<ProjectTask[]>([])
const taskStats = ref<ProjectTaskStats | null>(null)
const taskLoading = ref(false)
const taskKeyword = ref('')
const taskStatus = ref<string | undefined>()
const taskProjectFilter = ref<number | undefined>()
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
const completeVisible = ref(false)
const completeTarget = ref<ProjectTask | null>(null)
const completeActualHours = ref(0)
const acceptVisible = ref(false)
const initFormRef = ref<FormInstance>()
const taskFormRef = ref<FormInstance>()
const acceptFormRef = ref<FormInstance>()
const acceptFileRef = ref<HTMLInputElement | null>(null)
const contractLoading = ref(false)
const empLoading = ref(false)
const contractOptions = ref<Contract[]>([])
const employees = ref<Employee[]>([])
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
  resource_roles: [] as RoleAssignRow[],
})
const initRules: FormRules = {
  contract_id: [{ required: true, message: '请选择合同', trigger: 'change' }],
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

const msForm = reactive({
  name: '',
  role: '',
  deadline: '',
  deliverable: '',
  evidence: '',
})

const taskForm = reactive({
  project_id: undefined as number | undefined,
  milestone_id: undefined as number | undefined,
  title: '',
  criteria: '',
  assignee_id: undefined as number | undefined,
  due_date: '',
  planned_hours: 8,
})
const taskRules: FormRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请填写任务名称', trigger: 'blur' }],
  criteria: [{ required: true, message: '请填写完成标准', trigger: 'blur' }],
  due_date: [{ required: true, message: '请选择截止日期', trigger: 'change' }],
  planned_hours: [{ required: true, message: '请填写计划工时', trigger: 'blur' }],
}

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
const acceptRules: FormRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  result: [{ required: true, message: '请选择结果', trigger: 'change' }],
  accepted_at: [{ required: true, message: '请选择日期', trigger: 'change' }],
  method: [{ required: true, message: '请选择验收方式', trigger: 'change' }],
  conclusion: [{ required: true, message: '请填写结论与遗留安排', trigger: 'blur' }],
  attachment: [{ required: true, message: '请上传验收附件', trigger: 'change' }],
}

const portfolioStatCards = computed(() => [
  { key: 'executing' as const, label: '执行中', note: '交付推进中', count: stats.value?.executing ?? 0 },
  { key: 'accepting' as const, label: '待验收', note: '内部验收中', count: stats.value?.accepting ?? 0 },
  { key: 'accepted' as const, label: '待结项', note: '验收后收尾', count: stats.value?.accepted ?? 0 },
  { key: 'completed' as const, label: '已完成', note: '已结项归档', count: stats.value?.completed ?? 0 },
])

const listProjects = computed(() => projects.value)

const listProjectTotal = computed(() => projectTotal.value)

const boardFiltered = computed(() => {
  const q = boardKeyword.value.trim().toLowerCase()
  return projects.value.filter((p) => {
    if (p.status === 'terminated') return false
    if (boardType.value && p.project_type !== boardType.value) return false
    if (!q) return true
    const hay = `${p.name}${p.project_no}${p.manager_name || ''}${p.next_node || ''}`.toLowerCase()
    return hay.includes(q)
  })
})

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

const boardDeviation = computed(
  () => boardFiltered.value.filter((p) => p.health === 'attention' || p.health === 'risk').length,
)
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

const planEffectiveProgress = computed(() => {
  if (!milestones.value.length) return planProject.value?.progress || 0
  return Math.round((planMilestoneDoneCount.value * 100) / milestones.value.length)
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
  return PROJECT_TYPE_OPTIONS.find((x) => x.value === code)?.label || code || '—'
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

function formatRate(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? (n % 1 === 0 ? String(n) : n.toFixed(1)) : '0'
}

function paymentOk(row: Project) {
  return !!(row.payment_received_ok ?? row.payment_verified)
}

function handoffReady(row: Project) {
  return !!(row.contract_active_ok && paymentOk(row))
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
  const query = { ...route.query, tab: next } as Record<string, string>
  if (next === 'portfolio') {
    // keep overview mode hints if present
  }
  router.replace({ path, query })
  if (next === 'execute') {
    if (executeMode.value === 'plan') ensurePlanProject()
    else {
      loadTasks()
      loadTaskStats()
    }
  }
  if (next === 'portfolio' && overviewMode.value === 'department') loadDeptMonitor()
  if (next === 'initiation') loadResourceNeeds()
}

function onOverviewModeChange(mode: string | number | boolean | undefined) {
  if (mode === 'department') loadDeptMonitor()
}

function onExecuteModeChange(mode: string | number | boolean | undefined) {
  if (mode === 'plan') ensurePlanProject()
  else if (mode === 'tasks') {
    loadTasks()
    loadTaskStats()
  }
}

function goToTasksWorkbench() {
  executeMode.value = 'tasks'
  onExecuteModeChange('tasks')
  const query: Record<string, string> = {
    tab: 'execute',
    mode: 'tasks',
  }
  if (planProjectId.value) query.project_id = String(planProjectId.value)
  router.replace({ path: '/projects/delivery', query })
}

function goCreateScheduleForProject() {
  const query: Record<string, string> = { create: '1' }
  if (planProjectId.value) query.project_id = String(planProjectId.value)
  router.push({ path: '/schedules', query })
}

async function loadDeptMonitor() {
  deptLoading.value = true
  try {
    const { data } = await fetchDepartmentMonitor()
    deptMonitor.value = data
  } catch {
    deptMonitor.value = null
  } finally {
    deptLoading.value = false
  }
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
      fetchContracts({ keyword: q || undefined, page: 1, page_size: 50 }),
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
    const { data } = await fetchEmployees({ keyword: q || undefined, page: 1, page_size: 30 })
    employees.value = data.items
  } finally {
    empLoading.value = false
  }
}

function onContractPicked(id: number) {
  const c = contractOptions.value.find((x) => x.id === id)
  if (!c) return
  if (!initForm.name) initForm.name = `${c.customer_name || c.title} · 交付项目`
  if (c.contract_type) {
    initForm.project_type = c.contract_type
    onProjectTypeChange(c.contract_type)
  }
}

function memberLabel(m: ResourceRoleMember) {
  const parts = [m.name]
  if (m.job_title) parts.push(m.job_title)
  if (m.department_name) parts.push(m.department_name)
  return parts.join(' · ')
}

function roleOptionLabel(r: ResourceRoleOption) {
  if (r.member_count > 0) return `${r.role_name}（${r.member_count}人）`
  return r.role_name
}

function membersForRole(roleName: string): ResourceRoleMember[] {
  const opt = roleOptions.value.find((r) => r.role_name === roleName)
  const preferred = opt?.members || []
  if (!preferred.length) return roleEmployees.value
  const preferredIds = new Set(preferred.map((m) => m.id))
  const rest = roleEmployees.value.filter((m) => !preferredIds.has(m.id))
  return [...preferred, ...rest]
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
      picked.push({ role_name: match.role_name, suggested_user_id: undefined })
    }
  }
  if (picked.length) return picked
  return [{ role_name: '', suggested_user_id: undefined }]
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
    roleOptionsHint.value = '加载飞书角色失败，可手动输入角色并指定人员。'
  }
}

function onRoleNameChange(row: RoleAssignRow) {
  const members = membersForRole(row.role_name)
  if (row.suggested_user_id && !members.some((m) => m.id === row.suggested_user_id)) {
    row.suggested_user_id = undefined
  }
}

function addRoleRow() {
  initForm.resource_roles.push({ role_name: '', suggested_user_id: undefined })
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
  await Promise.all([searchContracts(''), searchEmployees(''), loadRoleOptions()])
  initForm.resource_roles = buildDefaultRoleRows('ai_custom')
  initVisible.value = true
}

async function onCreateProject() {
  const ok = await initFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!initForm.contract_id) {
    ElMessage.warning('请选择合同')
    return
  }
  if (!initGate.value.contractOk) {
    ElMessage.warning('合同须已签署后才能立项')
    return
  }
  if (!initGate.value.paymentOk) {
    ElMessage.warning('合同须有确认到账后才能立项，请先到「合同回款」完成到款认领与财务复核')
    return
  }
  const roles = initForm.resource_roles
    .map((r) => ({
      role_name: (r.role_name || '').trim(),
      suggested_user_id: r.suggested_user_id,
    }))
    .filter((r) => r.role_name)
  if (!roles.length) {
    ElMessage.warning('请至少添加一个所需部门')
    return
  }
  saving.value = true
  try {
    await createProject({
      name: initForm.name,
      contract_id: initForm.contract_id,
      project_type: initForm.project_type,
      scope_desc: initForm.scope_desc,
      manager_id: initForm.manager_id,
      start_date: initForm.start_date || undefined,
      end_date: initForm.end_date || undefined,
      business_owner_id: userStore.user?.id,
      resource_roles: roles,
    })
    ElMessage.success('立项申请已提交，请在下方确认部门资源')
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
    if (!row.contract_active_ok) missing.push('合同已签署')
    if (!paymentOk(row)) missing.push('已确认到账（请先完成到款认领与财务复核）')
    ElMessage.warning(`缺失：${missing.join('、')}`)
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
  const s = row.evidence_status || 'none'
  if (s === 'confirmed') return '已确认'
  if (s === 'rejected') return '已驳回'
  if (s === 'pending') return '待确认'
  return '未提交'
}

function evidenceTone(row: ProjectMilestone) {
  const s = row.evidence_status || 'none'
  if (s === 'confirmed') return 'good'
  if (s === 'rejected') return 'bad'
  if (s === 'pending') return 'warn'
  return ''
}

function canManagePlanForProject(project?: Project | null) {
  if (!project) return false
  if (userStore.hasPermission('*')) return true
  const codes = (userStore.user?.roles || []).map((r) => r.code)
  if (codes.includes('admin')) return true
  if (!codes.includes('dept_head')) return false
  const uidDept = userStore.user?.department_id
  if (project.department_id && uidDept && project.department_id !== uidDept) return false
  return true
}

const canManagePlan = computed(() => canManagePlanForProject(planProject.value))

function canConfirmEvidence(row: ProjectMilestone) {
  if (!planProject.value || !row.evidence) return false
  if (row.evidence_status !== 'pending') return false
  return canManagePlan.value
}

const evidenceDialogTitle = computed(() => {
  if (evidenceMode.value === 'review') return '审核完成证据'
  return evidenceTarget.value?.evidence ? '修改完成证据' : '提交完成证据'
})

function milestonePrimaryActionLabel(row: ProjectMilestone) {
  if (row.status === 'done' && canConfirmEvidence(row)) return '审核证据'
  if (row.status === 'done') return '查看证据'
  if (!row.evidence) return '提交证据'
  if (row.evidence_status === 'rejected') return '重提证据'
  if (canConfirmEvidence(row)) return '审核证据'
  if (row.can_complete && canManagePlan.value) return '标记完成'
  if (
    (row.task_total || 0) > (row.task_done || 0) &&
    row.evidence_status === 'confirmed'
  ) {
    return '去完成任务'
  }
  if (row.evidence_status === 'pending') return '查看证据'
  return ''
}

function goToMilestoneTasks(row: ProjectMilestone) {
  taskProjectFilter.value = planProjectId.value
  taskKeyword.value = ''
  taskStatus.value = undefined
  executeMode.value = 'tasks'
  loadTasks()
  loadTaskStats()
  ElMessage.info(`已切换到任务工时：请完成「${row.name}」剩余任务`)
}

function clearTaskProjectFilter() {
  taskProjectFilter.value = undefined
  loadTasks()
}

function onMilestonePrimaryAction(row: ProjectMilestone) {
  if (row.can_complete && row.status !== 'done' && canManagePlan.value) {
    markMilestoneDone(row)
    return
  }
  if (
    (row.task_total || 0) > (row.task_done || 0) &&
    row.evidence_status === 'confirmed' &&
    row.status !== 'done'
  ) {
    goToMilestoneTasks(row)
    return
  }
  openEvidencePanel(row)
}

function openEvidencePanel(row: ProjectMilestone) {
  evidenceTarget.value = row
  evidenceDraft.value = row.evidence || ''
  if (!row.evidence || row.evidence_status === 'rejected') {
    evidenceMode.value = 'fill'
  } else if (canConfirmEvidence(row) || row.evidence_status === 'pending' || row.evidence_status === 'confirmed') {
    evidenceMode.value = 'review'
  } else {
    evidenceMode.value = 'fill'
  }
  evidenceVisible.value = true
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
  if (!evidenceDraft.value.trim()) {
    ElMessage.warning('请填写完成证据')
    return
  }
  saving.value = true
  try {
    await updateMilestone(planProjectId.value, evidenceTarget.value.id, {
      evidence: evidenceDraft.value.trim(),
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

function openMilestone() {
  if (!planProjectId.value) return ElMessage.warning('请先选择项目')
  msForm.name = ''
  msForm.role = ''
  msForm.deadline = ''
  msForm.deliverable = ''
  msForm.evidence = ''
  msVisible.value = true
}

async function onAddMilestone() {
  if (!planProjectId.value || !msForm.name.trim()) return
  saving.value = true
  try {
    await addMilestone(planProjectId.value, {
      name: msForm.name.trim(),
      role: msForm.role || undefined,
      deadline: msForm.deadline || undefined,
      deliverable: msForm.deliverable || undefined,
      evidence: msForm.evidence || undefined,
    })
    ElMessage.success('里程碑已添加')
    msVisible.value = false
    await loadPlanDetail()
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

async function onTaskProjectChange(projectId: number) {
  taskForm.milestone_id = undefined
  await loadTaskMilestones(projectId)
  const open = taskMilestoneOptions.value.find((m) => m.status !== 'done')
  if (open) taskForm.milestone_id = open.id
}

async function openTaskCreate() {
  taskForm.project_id = planProjectId.value || projects.value[0]?.id
  taskForm.milestone_id = undefined
  taskForm.title = ''
  taskForm.criteria = ''
  taskForm.assignee_id = userStore.user?.id
  taskForm.due_date = ''
  taskForm.planned_hours = 8
  await searchEmployees('')
  if (taskForm.project_id) {
    if (planProjectId.value === taskForm.project_id && milestones.value.length) {
      taskMilestoneOptions.value = milestones.value
    } else {
      await loadTaskMilestones(taskForm.project_id)
    }
    const open = taskMilestoneOptions.value.find((m) => m.status !== 'done')
    if (open) taskForm.milestone_id = open.id
  }
  taskVisible.value = true
}

async function onCreateTask() {
  const ok = await taskFormRef.value?.validate().catch(() => false)
  if (!ok || !taskForm.project_id) return
  if (openTaskMilestones.value.length && !taskForm.milestone_id) {
    ElMessage.warning('请选择所属计划节点')
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
      due_date: taskForm.due_date,
      planned_hours: taskForm.planned_hours,
    })
    ElMessage.success('任务已创建')
    taskVisible.value = false
    await loadTasks()
    await loadTaskStats()
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
  acceptForm.project_id = target.id
  acceptForm.result = 'pass'
  acceptForm.accepted_at = new Date().toISOString().slice(0, 10)
  acceptForm.method = '内部验收单'
  acceptForm.conclusion = ''
  acceptForm.leftover_summary = ''
  acceptForm.attachment = ''
  acceptForm.attachment_path = ''
  acceptVisible.value = true
}

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
    acceptFormRef.value?.validateField('attachment')
  } finally {
    saving.value = false
  }
}

async function onAccept() {
  const ok = await acceptFormRef.value?.validate().catch(() => false)
  if (!ok || !acceptForm.project_id) return
  if (acceptForm.result === 'fail') {
    ElMessage.warning('验收不通过不可提交审批')
    return
  }
  saving.value = true
  try {
    await acceptProject(acceptForm.project_id, {
      result: acceptForm.result,
      accepted_at: acceptForm.accepted_at,
      method: acceptForm.method,
      conclusion: acceptForm.conclusion,
      leftover_summary: acceptForm.leftover_summary || undefined,
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

async function onFinanceCheck(row: Project) {
  if (row.finance_check_status === 'pending') {
    ElMessage.warning('财务核对已在审批中')
    return
  }
  await ElMessageBox.confirm(
    `确认提交「${row.name}」财务核对到审批中心？`,
    '提交财务核对',
    { type: 'warning', confirmButtonText: '提交审批', cancelButtonText: '取消' },
  )
  await setProjectFinanceCheck(row.id)
  ElMessage.success('财务核对已提交，请到审批中心处理')
  await reloadAll()
}

async function onCloseLeftover(row: Project) {
  await ElMessageBox.confirm(`确认关闭「${row.name}」遗留问题？`, '关闭遗留', {
    type: 'warning',
  })
  await setProjectLeftoverClosed(row.id, true)
  ElMessage.success('遗留问题已关闭')
  await reloadAll()
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
  await ElMessageBox.confirm(`确认结项「${row.name}」？`, '结项确认', { type: 'warning' })
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
  if (tab.value === 'portfolio' && overviewMode.value === 'department') await loadDeptMonitor()
  if (tab.value === 'initiation') await loadResourceNeeds()
}

function normalizeTab(raw?: string | null): TabKey {
  if (raw === 'board' || raw === 'department') return 'portfolio'
  if (raw === 'plan' || raw === 'tasks') return 'execute'
  if (ALL_TABS.some((t) => t.key === raw)) return raw as TabKey
  return workbench.value === 'delivery' ? 'initiation' : 'portfolio'
}

function syncWorkbenchRoute() {
  const raw = route.query.tab as string | undefined
  const lifecycleTabs: TabKey[] = ['initiation', 'execute', 'acceptance']
  if (workbench.value === 'portfolio') {
    if (lifecycleTabs.includes(raw as TabKey) || raw === 'plan' || raw === 'tasks') {
      router.replace({
        path: '/projects/delivery',
        query: { ...route.query, tab: normalizeTab(raw) },
      })
      return true
    }
  } else if (raw === 'portfolio' || raw === 'board' || raw === 'department') {
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
  if (raw === 'department') overviewMode.value = 'department'
  if (raw === 'tasks' || mode === 'tasks') executeMode.value = 'tasks'
  if (raw === 'plan' || mode === 'plan') executeMode.value = 'plan'
  const pid = Number(route.query.project_id)
  if (Number.isFinite(pid) && pid > 0) planProjectId.value = pid
  tab.value = normalizeTab(raw)
  await reloadAll()
  if (tab.value === 'execute') {
    if (executeMode.value === 'plan') await ensurePlanProject()
    else {
      await loadTasks()
      await loadTaskStats()
    }
  }
  if (tab.value === 'portfolio' && overviewMode.value === 'department') await loadDeptMonitor()
  if (tab.value === 'initiation') await loadResourceNeeds()
}
</script>

<style scoped>
.submode-bar {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
}
.muted {
  color: var(--crm-ink-soft);
  font-size: 12px;
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
.role-assign-row {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}
.health-hint {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--crm-surface-soft, #f7f7f7);
  font-size: 12px;
  color: var(--crm-ink-soft);
}
.upload-box {
  border: 1.5px dashed var(--crm-border, #dcdfe6);
  border-radius: 12px;
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--crm-surface-soft, #f7f7f7);
  width: 100%;
}
.upload-box:hover {
  border-color: var(--el-color-primary);
}
.upload-box.uploaded {
  border-style: solid;
  border-color: var(--el-color-success);
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
</style>
