<template>
  <div class="crm-page performance-workbench" v-loading="loading">
    <header class="sales-head">
      <div class="sales-head-copy">
        <p class="wb-eyebrow">经营台</p>
        <h1>目标绩效</h1>
        <p>OKR 目标、月度考核、校准申诉与绩效工资批次。</p>
      </div>
      <div class="sales-head-actions">
        <el-button v-if="tab !== 'bi'" @click="rulesVisible = true">规则版本 V2026.07</el-button>
        <span v-if="tab === 'bi'" class="management-only-chip">管理层专属</span>
        <template v-else-if="tab === 'assessment'">
          <el-button @click="togglePendingFilter">
            {{ assessFilter === 'pending' ? '显示全部' : '只看待评' }}
          </el-button>
          <el-button v-if="canManagePerformance" plain type="danger" @click="onResetCycle">
            重置本周期
          </el-button>
        </template>
        <el-button
          v-else-if="tab === 'calibration'"
          type="primary"
          :disabled="cycle?.locked"
          @click="onCalibrationAction"
        >
          {{ cycle?.locked ? '绩效已锁定' : cycle?.calibration_started ? '锁定绩效' : '发起校准' }}
        </el-button>
        <el-button
          v-else-if="tab === 'payroll'"
          type="primary"
          :disabled="cycle?.payroll_published"
          @click="onPayrollAction"
        >
          {{ payrollActionLabel }}
        </el-button>
      </div>
    </header>

    <div class="performance-tabs" role="tablist">
      <button
        v-for="item in tabs"
        :key="item.key"
        type="button"
        class="performance-tab"
        :class="{ active: tab === item.key }"
        @click="tab = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <!-- BI 总览 -->
    <PerformanceBiPanel
      v-if="tab === 'bi'"
      :okr-stats="okrStats"
      :assessments="assessments"
      :grade-dist="gradeDist"
      :pending-appeals="cycle?.pending_appeals ?? 0"
      :pending-manager="cycle?.pending_manager ?? 0"
      :completed-count="cycle?.completed_count ?? 0"
      :total-assessments="cycle?.total_assessments ?? 0"
      :calibration-started="!!cycle?.calibration_started"
      :locked="!!cycle?.locked"
      @goto="onBiGoto"
    />

    <!-- 月度考核 -->
    <template v-else-if="tab === 'assessment'">
      <div class="performance-kpis">
        <article class="performance-kpi">
          <small>待员工自评</small>
          <strong>{{ cycle?.pending_self ?? assessCounts.pendingSelf }}</strong>
          <span>截止本月评价窗口</span>
        </article>
        <article class="performance-kpi">
          <small>待主管评价</small>
          <strong>{{ cycle?.pending_manager ?? 0 }}</strong>
          <span>已自动提醒直属负责人</span>
        </article>
        <article class="performance-kpi">
          <small>待综合校准</small>
          <strong>{{ assessCounts.pendingCalibration }}</strong>
          <span>部门评价完成后进入</span>
        </article>
        <article class="performance-kpi">
          <small>已完成</small>
          <strong>{{ cycle?.completed_count ?? 0 }}</strong>
          <span>完成率 {{ assessCompletionRate }}%</span>
        </article>
      </div>

      <article class="performance-card">
        <div class="card-head">
          <div>
            <h2>{{ periodLabel }} 月度考核</h2>
            <p>点选员工行打开抽屉打分；OKR 进度仅作建议分，最终以主管提交为准</p>
          </div>
          <el-tag :type="cycle?.locked ? 'success' : 'warning'" size="small">
            {{ cycle?.locked ? '已锁定' : '评价中' }}
          </el-tag>
        </div>
        <div class="rule-strip">
          <span class="rule-chip">OKR达成 <b>50%</b></span>
          <span class="rule-chip">岗位KPI <b>30%</b></span>
          <span class="rule-chip">协作与行为 <b>20%</b></span>
          <span class="rule-chip">当前版本 <b>{{ cycle?.rule_version || 'V2026.07' }}</b></span>
        </div>
        <el-table :data="filteredAssessments" stripe @row-click="openAssessmentDrawer">
          <el-table-column label="员工" min-width="180">
            <template #default="{ row }">
              <div class="person-cell">
                <span class="source-icon">{{ (row.user_name || '?')[0] }}</span>
                <span>
                  <b>{{ row.user_name || `用户#${row.user_id}` }}</b>
                  <small>{{ row.department_name || '—' }}</small>
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="自评分" width="90">
            <template #default="{ row }">
              <span class="score-number" :class="{ pending: row.self_score == null }">
                {{ row.self_score ?? '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="主管评分" width="100">
            <template #default="{ row }">
              <span class="score-number" :class="{ pending: row.manager_score == null }">
                {{ row.manager_score ?? '待评价' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="evidence_status" label="证据" width="90" />
          <el-table-column label="综合分" width="90">
            <template #default="{ row }">
              <span class="score-number" :class="{ pending: row.final_score == null }">
                {{ row.final_score ?? '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="等级" width="80">
            <template #default="{ row }">{{ row.grade || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="assessTag(row.status)">
                {{ ASSESS_STATUS_LABEL[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </article>
    </template>

    <!-- 校准与申诉 -->
    <template v-else-if="tab === 'calibration'">
      <div class="performance-kpis">
        <article class="performance-kpi">
          <small>校准范围</small>
          <strong>{{ cycle?.total_assessments ?? 0 }}人</strong>
          <span>覆盖当前周期考核名单</span>
        </article>
        <article class="performance-kpi">
          <small>待主管评价</small>
          <strong>{{ cycle?.pending_manager ?? 0 }}</strong>
          <span>完成后方可锁定</span>
        </article>
        <article class="performance-kpi">
          <small>申诉处理中</small>
          <strong>{{ cycle?.pending_appeals ?? 0 }}</strong>
          <span>综合管理部负责处理</span>
        </article>
        <article class="performance-kpi">
          <small>结果已锁定</small>
          <strong>{{ cycle?.locked ? cycle.total_assessments : 0 }}</strong>
          <span>锁定后进入财务流程</span>
        </article>
      </div>

      <div class="calibration-layout">
        <article class="performance-card">
          <div class="card-head">
            <div>
              <h2>综合校准</h2>
              <p>对比部门评分分布，保留调整原因和审批轨迹</p>
            </div>
            <el-tag
              size="small"
              :type="cycle?.locked ? 'success' : cycle?.calibration_started ? 'warning' : 'info'"
            >
              {{ cycle?.locked ? '已锁定' : cycle?.calibration_started ? '校准中' : '未发起' }}
            </el-tag>
          </div>
          <div class="workflow-banner">
            <span>
              <b>
                {{
                  cycle?.calibration_started
                    ? `批次 JZ-${periodLabel.replace('-', '')} 已建立`
                    : '尚未建立校准批次'
                }}
              </b>
              <small>
                {{
                  cycle?.calibration_started
                    ? '综合管理部可处理差异、申诉并锁定最终结果'
                    : '发起后冻结部门初评分，进入集中校准'
                }}
              </small>
            </span>
            <el-tag v-if="cycle?.calibration_started" type="info" size="small">综合管理部</el-tag>
          </div>
          <div class="distribution">
            <div class="distribution-row">
              <span>A+ / A</span>
              <span class="distribution-track">
                <span class="distribution-fill" :style="{ width: `${gradeDist['A+_A']}%` }" />
              </span>
              <b>{{ gradeDist['A+_A'] }}%</b>
            </div>
            <div class="distribution-row">
              <span>B</span>
              <span class="distribution-track">
                <span class="distribution-fill" :style="{ width: `${gradeDist.B}%` }" />
              </span>
              <b>{{ gradeDist.B }}%</b>
            </div>
            <div class="distribution-row">
              <span>C / D</span>
              <span class="distribution-track">
                <span class="distribution-fill" :style="{ width: `${gradeDist.C_D}%` }" />
              </span>
              <b>{{ gradeDist.C_D }}%</b>
            </div>
          </div>
          <div class="blocker-box">{{ lockHint }}</div>
        </article>

        <article class="performance-card">
          <div class="card-head">
            <div>
              <h2>申诉处理</h2>
              <p>员工申诉由综合管理部复核</p>
            </div>
            <el-tag size="small" :type="(cycle?.pending_appeals || 0) ? 'warning' : 'success'">
              {{ cycle?.pending_appeals || 0 }}项待处理
            </el-tag>
          </div>
          <div class="appeal-list">
            <button
              v-for="a in appeals"
              :key="a.id"
              type="button"
              class="appeal-card"
              @click="openAppealDrawer(a)"
            >
              <span>
                <b>{{ a.user_name || '员工' }} · {{ a.department_name || '—' }}</b>
                <small>当前 {{ a.current_score ?? '—' }} 分 · 申请复核至 {{ a.request_score }} 分</small>
              </span>
              <el-tag size="small" :type="a.status === 'pending' ? 'warning' : 'success'">
                {{ APPEAL_STATUS_LABEL[a.status] || a.status }}
              </el-tag>
            </button>
            <div v-if="!appeals.length" style="color: var(--crm-ink-soft); font-size: 13px">
              当前周期暂无申诉
            </div>
          </div>
        </article>
      </div>
    </template>

    <!-- 工资批次 -->
    <template v-else>
      <div class="performance-kpis">
        <article class="performance-kpi">
          <small>当前批次</small>
          <strong>{{ cycle?.payroll_batch_no || '未生成' }}</strong>
          <span>{{ cycle?.payroll_published ? '工资条已发布' : `${periodLabel} 工资` }}</span>
        </article>
        <article class="performance-kpi">
          <small>纳入员工</small>
          <strong>{{ cycle?.total_assessments ?? 0 }}人</strong>
          <span>正式考核名单</span>
        </article>
        <article class="performance-kpi">
          <small>绩效奖金预估</small>
          <strong>¥{{ bonusTotal }}</strong>
          <span>最终以财务核算为准</span>
        </article>
        <article class="performance-kpi">
          <small>待处理异常</small>
          <strong>{{ cycle?.locked ? 0 : (cycle?.pending_manager || 0) + (cycle?.pending_appeals || 0) }}</strong>
          <span>评价与申诉未完成</span>
        </article>
      </div>

      <article class="performance-card" style="margin-bottom: 14px">
        <div class="card-head">
          <div>
            <h2>工资核算与发布流程</h2>
            <p>综合管理部确认绩效，财务核算、复核并发布工资条</p>
          </div>
          <el-tag size="small" :type="payrollStatusTag">{{ payrollStatusText }}</el-tag>
        </div>
        <div class="payroll-flow">
          <div
            v-for="(step, idx) in payrollSteps"
            :key="step.title"
            class="payroll-step"
            :class="{ done: payrollStepIndex > idx, active: payrollStepIndex === idx }"
          >
            <small>0{{ idx + 1 }}</small>
            <b>{{ step.title }}</b>
            <small>
              {{ payrollStepIndex > idx ? '已完成' : payrollStepIndex === idx ? step.desc : '等待前序完成' }}
            </small>
          </div>
        </div>
      </article>

      <article class="performance-card">
        <div class="card-head">
          <div>
            <h2>{{ cycle?.payroll_created ? `${cycle.payroll_batch_no} 批次明细` : '绩效工资预览' }}</h2>
            <p>仅经营管理层、综合管理部和财务授权角色可查看</p>
          </div>
          <el-tag size="small" type="info">
            {{ cycle?.payroll_published ? '已发布' : cycle?.payroll_reviewed ? '已复核' : cycle?.payroll_created ? '核算中' : '预览' }}
          </el-tag>
        </div>
        <div class="sensitive-note">
          <span>敏感数据按角色授权，查看、导出和变更均写入审计记录</span>
          <b>当前账号受控查看</b>
        </div>
        <el-table :data="assessments" stripe>
          <el-table-column label="员工" min-width="120">
            <template #default="{ row }">{{ row.user_name || `用户#${row.user_id}` }}</template>
          </el-table-column>
          <el-table-column label="部门" min-width="120">
            <template #default="{ row }">{{ row.department_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="绩效分" width="90">
            <template #default="{ row }">{{ row.final_score ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="等级" width="80">
            <template #default="{ row }">{{ row.grade || '—' }}</template>
          </el-table-column>
          <el-table-column label="奖金系数" width="100">
            <template #default="{ row }">{{ row.coefficient ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="绩效奖金" width="120">
            <template #default="{ row }">
              {{
                row.bonus_amount != null
                  ? `¥${Number(row.bonus_amount).toLocaleString()}`
                  : ASSESS_STATUS_LABEL[row.status] || '—'
              }}
            </template>
          </el-table-column>
        </el-table>
      </article>
    </template>

    <!-- 目标详情 -->
    <el-drawer v-model="goalDrawerVisible" :title="goalDetail?.title || '目标详情'" size="480px" destroy-on-close>
      <template v-if="goalDetail">
        <div class="drawer-section">
          <el-tag size="small" type="info">{{ levelLabel(goalDetail.level) }}</el-tag>
          <span style="margin-left: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            负责人 {{ goalDetail.owner_name || '—' }} · 进度 {{ goalDetail.progress || 0 }}%
          </span>
        </div>
        <div class="drawer-section">
          <h4>目标对齐</h4>
          <div class="drawer-grid">
            <div><small>上级目标</small><b>{{ goalDetail.parent_title || '无（公司级）' }}</b></div>
            <div><small>考核周期</small><b>{{ goalDetail.period_label }}</b></div>
            <div><small>状态</small><b>{{ OKR_STATUS_LABEL[goalDetail.status] || goalDetail.status }}</b></div>
            <div><small>KR 数</small><b>{{ goalDetail.key_results?.length || 0 }}</b></div>
          </div>
        </div>
        <div class="drawer-section">
          <h4>关键结果</h4>
          <div class="kr-list">
            <div v-for="(kr, n) in goalDetail.key_results || []" :key="kr.id" class="kr-item">
              <div class="kr-top">
                <b>KR{{ n + 1 }} · {{ kr.title }}</b>
                <strong>{{ kr.progress ?? 0 }}%</strong>
              </div>
              <div class="goal-meter">
                <span class="track"><i class="fill" :style="{ width: `${kr.progress ?? 0}%` }" /></span>
              </div>
            </div>
            <div v-if="!(goalDetail.key_results || []).length" style="color: var(--crm-ink-soft); font-size: 13px">
              暂无关键结果
            </div>
          </div>
        </div>
        <el-button type="primary" @click="$router.push(`/okrs/${goalDetail.id}`)">打开详情页</el-button>
      </template>
    </el-drawer>

    <!-- 考核详情 / 主管评价 -->
    <el-drawer
      v-model="assessDrawerVisible"
      :title="assessDrawer ? `${assessDrawer.user_name || '员工'} · ${periodLabel}` : '月度考核'"
      size="480px"
      destroy-on-close
    >
      <template v-if="assessDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="assessTag(assessDrawer.status)">
            {{ ASSESS_STATUS_LABEL[assessDrawer.status] || assessDrawer.status }}
          </el-tag>
          <span style="margin-left: 8px; font-size: 12px; color: var(--crm-ink-soft)">
            {{ assessDrawer.department_name || '—' }} · {{ cycle?.rule_version }}
          </span>
        </div>
        <el-alert
          v-if="cycle?.locked"
          type="warning"
          :closable="false"
          show-icon
          title="本周期已锁定，不可再打分或申诉"
          style="margin-bottom: 12px"
        />
        <div class="drawer-section">
          <h4>评分汇总</h4>
          <div class="assessment-score-grid">
            <div class="assessment-score">
              <small>员工自评</small>
              <strong>{{ assessDrawer.self_score ?? '—' }}</strong>
            </div>
            <div class="assessment-score">
              <small>主管评价</small>
              <strong>{{ assessDrawer.manager_score ?? '—' }}</strong>
            </div>
            <div class="assessment-score">
              <small>当前综合分</small>
              <strong>{{ assessDrawer.final_score ?? '—' }}</strong>
            </div>
          </div>
          <div
            v-if="assessDrawer.okr_score != null"
            style="margin-top: 8px; font-size: 12px; color: var(--crm-ink-soft)"
          >
            构成：OKR {{ assessDrawer.okr_score }} · KPI {{ assessDrawer.kpi_score ?? '—' }} · 行为
            {{ assessDrawer.behavior_score ?? '—' }}
          </div>
        </div>
        <div class="drawer-section">
          <h4>评分构成（规则 V2026.07）</h4>
          <div class="rule-strip">
            <span class="rule-chip">OKR达成 <b>50%</b></span>
            <span class="rule-chip">岗位KPI <b>30%</b></span>
            <span class="rule-chip">协作与行为 <b>20%</b></span>
          </div>
          <p style="margin: 8px 0 0; font-size: 12px; color: var(--crm-ink-soft); line-height: 1.5">
            OKR 分可参考目标地图进度建议，KPI 与行为由主管填写；不与销售/项目自动挂钩。
          </p>
        </div>
        <div class="drawer-section">
          <h4>评价说明</h4>
          <p style="margin: 0; color: var(--crm-ink-soft); line-height: 1.6">
            {{ assessDrawer.manager_comment || '暂无主管评价说明' }}
          </p>
        </div>
        <el-alert
          v-if="
            !cycle?.locked &&
            assessDrawer.status === 'pending_self' &&
            !canSubmitSelfRate(assessDrawer)
          "
          type="info"
          :closable="false"
          show-icon
          title="当前为「待自评」：请该员工本人登录后点自己的行提交自评分"
          style="margin-bottom: 12px"
        />
        <div
          v-if="
            !cycle?.locked &&
            assessDrawer.status === 'pending_self' &&
            canSubmitSelfRate(assessDrawer)
          "
          class="drawer-section"
        >
          <h4>{{ isMyAssessment(assessDrawer) ? '提交员工自评' : '代提交员工自评' }}</h4>
          <p
            v-if="!isMyAssessment(assessDrawer)"
            style="margin: 0 0 8px; font-size: 12px; color: var(--crm-ink-soft)"
          >
            你以管理者身份代为提交；正式环境建议由员工本人完成。
          </p>
          <el-form label-position="top">
            <el-form-item label="自评分 (0-100)">
              <el-input-number v-model="selfForm.score" :min="0" :max="100" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="acting" @click="submitSelfRate">提交自评</el-button>
        </div>
        <el-alert
          v-if="
            !cycle?.locked &&
            assessDrawer.status === 'pending_manager' &&
            isMyAssessment(assessDrawer)
          "
          type="info"
          :closable="false"
          show-icon
          title="自评已提交，等待主管评价（主管打开本行后可打分）"
          style="margin-bottom: 12px"
        />
        <el-alert
          v-if="
            !cycle?.locked &&
            assessDrawer.status === 'pending_manager' &&
            !canManagePerformance &&
            !isMyAssessment(assessDrawer)
          "
          type="info"
          :closable="false"
          show-icon
          title="当前为「待主管评价」，需要具备主管/管理者角色才能打分"
          style="margin-bottom: 12px"
        />
        <div
          v-if="
            !cycle?.locked &&
            assessDrawer.status === 'pending_manager' &&
            canManagePerformance &&
            !isMyAssessment(assessDrawer)
          "
          class="drawer-section"
        >
          <h4>提交主管评价</h4>
          <el-alert
            v-if="assessDrawer.suggested_okr_count"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 10px"
            :title="`系统建议 OKR ${assessDrawer.suggested_okr_score} 分（来自 ${assessDrawer.suggested_okr_period} 共 ${assessDrawer.suggested_okr_count} 条个人目标进度均值）`"
          />
          <el-alert
            v-else
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 10px"
            :title="`暂无 ${assessDrawer.suggested_okr_period || okrPeriodLabel} 个人目标，请手工填写 OKR 分`"
          />
          <el-button
            v-if="assessDrawer.suggested_okr_score != null"
            size="small"
            style="margin-bottom: 10px"
            @click="applySuggestedOkr"
          >
            采用建议分
          </el-button>
          <div class="weight-score-row">
            <div>
              <b>OKR 目标达成</b>
              <small>权重 50%</small>
            </div>
            <el-input-number v-model="managerForm.okr" :min="0" :max="100" />
          </div>
          <div class="weight-score-row">
            <div>
              <b>岗位 KPI</b>
              <small>权重 30%</small>
            </div>
            <el-input-number v-model="managerForm.kpi" :min="0" :max="100" />
          </div>
          <div class="weight-score-row">
            <div>
              <b>协作与行为</b>
              <small>权重 20%</small>
            </div>
            <el-input-number v-model="managerForm.behavior" :min="0" :max="100" />
          </div>
          <div class="weight-preview">
            系统汇总综合分：<b>{{ weightedManagerScore }}</b>（四舍五入）
          </div>
          <el-form label-position="top">
            <el-form-item label="评价依据">
              <el-input v-model="managerForm.comment" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="acting" @click="submitManagerRate">提交评价</el-button>
        </div>
        <div
          v-if="
            !cycle?.locked &&
            assessDrawer.final_score != null &&
            ['pending_calibration', 'completed'].includes(assessDrawer.status) &&
            isMyAssessment(assessDrawer)
          "
          class="drawer-section"
        >
          <h4>发起申诉</h4>
          <el-form label-position="top">
            <el-form-item label="申请复核分">
              <el-input-number v-model="appealCreateForm.score" :min="0" :max="100" />
            </el-form-item>
            <el-form-item label="申诉理由">
              <el-input v-model="appealCreateForm.reason" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <el-button type="warning" :loading="acting" @click="submitCreateAppeal">提交申诉</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 申诉处理 -->
    <el-drawer
      v-model="appealDrawerVisible"
      :title="appealDrawer ? `${appealDrawer.user_name || '员工'} · 申诉` : '绩效申诉'"
      size="480px"
      destroy-on-close
    >
      <template v-if="appealDrawer">
        <div class="drawer-section">
          <el-tag size="small" :type="appealDrawer.status === 'pending' ? 'warning' : 'success'">
            {{ APPEAL_STATUS_LABEL[appealDrawer.status] || appealDrawer.status }}
          </el-tag>
        </div>
        <div class="drawer-section">
          <h4>申诉内容</h4>
          <div class="drawer-grid">
            <div><small>当前综合分</small><b>{{ appealDrawer.current_score ?? '—' }}</b></div>
            <div><small>申请复核分</small><b>{{ appealDrawer.request_score }}</b></div>
          </div>
          <p style="margin: 12px 0 0; line-height: 1.7; color: var(--crm-ink-soft)">{{ appealDrawer.reason }}</p>
        </div>
        <div v-if="appealDrawer.status === 'pending'" class="drawer-section">
          <h4>处理决定</h4>
          <el-input v-model="appealForm.resolution" type="textarea" :rows="3" placeholder="复核结论与依据" />
          <div style="margin-top: 12px; display: flex; gap: 8px">
            <el-button type="danger" :loading="acting" @click="submitAppeal(false)">维持原结果</el-button>
            <el-button type="primary" :loading="acting" @click="submitAppeal(true)">调整后通过</el-button>
          </div>
        </div>
        <div v-else class="drawer-section">
          <h4>处理结论</h4>
          <p style="margin: 0; color: var(--crm-ink-soft)">{{ appealDrawer.resolution || '—' }}</p>
        </div>
      </template>
    </el-drawer>

    <!-- 新建目标 -->
    <el-dialog v-model="createVisible" title="新建目标" width="560px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="目标名称" required>
          <el-input v-model="createForm.title" placeholder="描述明确、可衡量的结果" />
        </el-form-item>
        <el-form-item label="目标层级" required>
          <el-select v-model="createForm.level" style="width: 100%">
            <el-option
              v-for="opt in OKR_LEVEL_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="考核周期" required>
          <el-input v-model="createForm.period_label" />
        </el-form-item>
        <el-form-item v-if="createForm.level !== 'company'" label="上级目标" required>
          <el-select v-model="createForm.parent_id" filterable clearable style="width: 100%">
            <el-option
              v-for="p in parentOptions"
              :key="p.id"
              :label="`${levelShort(p.level)} · ${p.title}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="KR1" required>
          <el-input v-model="createForm.kr_title" placeholder="填写衡量标准和目标值" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreateGoal">创建目标</el-button>
      </template>
    </el-dialog>

    <!-- 规则说明 -->
    <el-dialog v-model="rulesVisible" title="绩效规则 · V2026.07" width="520px">
      <div class="drawer-section">
        <h4>评分构成</h4>
        <div class="compact-step done"><span class="step-dot">✓</span><span><b>OKR目标达成</b></span><b>50%</b></div>
        <div class="compact-step done"><span class="step-dot">✓</span><span><b>岗位KPI</b></span><b>30%</b></div>
        <div class="compact-step done"><span class="step-dot">✓</span><span><b>协作与行为</b></span><b>20%</b></div>
        <p style="margin: 10px 0 0; color: var(--crm-ink-soft); font-size: 13px; line-height: 1.5">
          目标地图进度到 100% 不会自动完成考核。主管评价时可参考系统根据个人 OKR 进度给出的建议分，最终以提交分为准。
        </p>
      </div>
      <div class="drawer-section">
        <h4>等级与工资系数</h4>
        <div class="compact-step"><span class="step-dot">A+</span><span><b>≥90</b></span><b>1.20</b></div>
        <div class="compact-step"><span class="step-dot">A</span><span><b>85–89</b></span><b>1.10</b></div>
        <div class="compact-step"><span class="step-dot">B</span><span><b>70–84</b></span><b>1.00</b></div>
        <div class="compact-step"><span class="step-dot">C</span><span><b>60–69</b></span><b>0.85</b></div>
      </div>
      <template #footer>
        <el-button type="primary" @click="rulesVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { notifyError } from '@/utils/notify'
import {
  createOkr,
  fetchOkrDetail,
  fetchOkrStats,
  fetchOkrs,
  OKR_LEVEL_OPTIONS,
  OKR_STATUS_LABEL,
  type Okr,
  type OkrDetail,
  type OkrStats,
} from '@/api/okrs'
import {
  APPEAL_STATUS_LABEL,
  ASSESS_STATUS_LABEL,
  createAppeal,
  fetchPerformanceWorkbench,
  generatePayroll,
  lockCycle,
  publishPayroll,
  rateManager,
  rateSelf,
  resolveAppeal,
  reviewPayroll,
  resetCycle,
  startCalibration,
  type Appeal,
  type Assessment,
  type PerformanceCycle,
} from '@/api/performance'
import { useUserStore } from '@/stores/user'
import PerformanceBiPanel from './panels/PerformanceBiPanel.vue'

type TabKey = 'bi' | 'assessment' | 'calibration' | 'payroll'

const tabs: { key: TabKey; label: string }[] = [
  { key: 'bi', label: 'BI总览' },
  { key: 'assessment', label: '月度考核' },
  { key: 'calibration', label: '校准与申诉' },
  { key: 'payroll', label: '工资批次' },
]

const periodLabel = '2026-07'
const okrPeriodLabel = '2026-Q3'

const userStore = useUserStore()
const loading = ref(false)
const acting = ref(false)
const tab = ref<TabKey>('bi')
const assessFilter = ref<'all' | 'pending'>('all')

const okrStats = ref<OkrStats | null>(null)
const okrs = ref<Okr[]>([])
const cycle = ref<PerformanceCycle | null>(null)
const assessments = ref<Assessment[]>([])
const appeals = ref<Appeal[]>([])
const gradeDist = ref({ 'A+_A': 0, B: 0, C_D: 0 })

const goalDrawerVisible = ref(false)
const goalDetail = ref<OkrDetail | null>(null)
const assessDrawerVisible = ref(false)
const assessDrawer = ref<Assessment | null>(null)
const appealDrawerVisible = ref(false)
const appealDrawer = ref<Appeal | null>(null)
const createVisible = ref(false)
const rulesVisible = ref(false)

const managerForm = reactive({ okr: 70, kpi: 70, behavior: 70, comment: '' })
const selfForm = reactive({ score: 80 })
const appealCreateForm = reactive({ score: 85, reason: '' })
const appealForm = reactive({ resolution: '' })
const createForm = reactive({
  title: '',
  level: 'personal',
  period_label: okrPeriodLabel,
  parent_id: undefined as number | undefined,
  kr_title: '',
})

const canManagePerformance = computed(() => {
  const roles = userStore.user?.roles?.map((r) => r.code) ?? []
  return roles.some((c) => ['admin', 'middle_manager', 'executive', 'hr'].includes(c))
})

const weightedManagerScore = computed(() =>
  Math.round(managerForm.okr * 0.5 + managerForm.kpi * 0.3 + managerForm.behavior * 0.2),
)

const filteredAssessments = computed(() => {
  if (assessFilter.value !== 'pending') return assessments.value
  return assessments.value.filter((x) =>
    ['pending_self', 'pending_manager', 'pending_calibration', 'appealing'].includes(x.status),
  )
})
const alignedCount = computed(() =>
  okrs.value.filter((x) => x.level === 'company' || x.parent_id).length,
)
const assessCounts = computed(() => ({
  pendingSelf: assessments.value.filter((x) => x.status === 'pending_self').length,
  pendingCalibration: assessments.value.filter((x) => x.status === 'pending_calibration').length,
}))
const assessCompletionRate = computed(() => {
  const total = cycle.value?.total_assessments || 0
  if (!total) return 0
  return Math.round(((cycle.value?.completed_count || 0) * 100) / total)
})
const bonusTotal = computed(() => {
  const sum = assessments.value.reduce((acc, x) => acc + (x.bonus_amount != null ? Number(x.bonus_amount) : 0), 0)
  return sum.toLocaleString()
})
const payrollStepIndex = computed(() => {
  if (cycle.value?.payroll_published) return 5
  if (cycle.value?.payroll_reviewed) return 4
  if (cycle.value?.payroll_created) return 3
  if (cycle.value?.locked) return 2
  return 0
})
const payrollSteps = [
  { title: '绩效锁定', desc: '等待综合管理部' },
  { title: '综合管理确认', desc: '确认规则与申诉' },
  { title: '财务核算', desc: '生成工资批次' },
  { title: '财务复核', desc: '双人复核金额' },
  { title: '工资条发布', desc: '向员工发布' },
]
const payrollStatusText = computed(() => {
  if (cycle.value?.payroll_published) return '已发布'
  if (cycle.value?.payroll_reviewed) return '待发布'
  if (cycle.value?.payroll_created) return '财务核算中'
  if (cycle.value?.locked) return '可生成'
  return '等待绩效锁定'
})
const payrollStatusTag = computed(() => {
  if (cycle.value?.payroll_published) return 'success'
  if (cycle.value?.locked) return 'info'
  return 'warning'
})
const payrollActionLabel = computed(() => {
  if (cycle.value?.payroll_published) return '工资条已发布'
  if (cycle.value?.payroll_reviewed) return '发布工资条'
  if (cycle.value?.payroll_created) return '提交财务复核'
  return '生成工资批次'
})
const lockHint = computed(() => {
  if (cycle.value?.locked) return '绩效结果已锁定，后续变更必须走例外授权并保留审计。'
  const ps = cycle.value?.pending_self || 0
  const pm = cycle.value?.pending_manager || 0
  const pa = cycle.value?.pending_appeals || 0
  if (cycle.value?.calibration_started && !ps && !pm && !pa) {
    return '所有前置事项已完成，可以锁定绩效结果。'
  }
  return `锁定前仍需完成：${ps}项自评、${pm}项主管评价、${pa}项申诉处理。`
})

const goalTree = computed(() => {
  const items = [...okrs.value]
  const byParent = new Map<number | null, Okr[]>()
  for (const o of items) {
    const key = o.parent_id ?? null
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key)!.push(o)
  }
  const order = { company: 0, department: 1, personal: 2 } as Record<string, number>
  const result: Okr[] = []
  function walk(parentId: number | null) {
    const kids = (byParent.get(parentId) || []).sort(
      (a, b) => (order[a.level] ?? 9) - (order[b.level] ?? 9) || a.id - b.id,
    )
    for (const k of kids) {
      result.push(k)
      walk(k.id)
    }
  }
  walk(null)
  // orphans (dept/personal without parent in list)
  for (const o of items) {
    if (!result.includes(o)) result.push(o)
  }
  return result
})

const parentOptions = computed(() => {
  if (createForm.level === 'department') return okrs.value.filter((x) => x.level === 'company')
  if (createForm.level === 'personal') return okrs.value.filter((x) => x.level === 'department')
  return []
})

function levelDepth(level: string) {
  if (level === 'company') return 1
  if (level === 'department') return 2
  return 3
}
function levelShort(level: string) {
  if (level === 'company') return '公司'
  if (level === 'department') return '部门'
  return '个人'
}
function levelLabel(level: string) {
  return OKR_LEVEL_OPTIONS.find((x) => x.value === level)?.label || level
}
function assessTag(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'appealing') return 'warning'
  return 'info'
}

async function loadObjectives() {
  const [statsRes, listRes] = await Promise.all([
    fetchOkrStats(okrPeriodLabel),
    fetchOkrs({ period_label: okrPeriodLabel, page: 1, page_size: 100 }),
  ])
  okrStats.value = statsRes.data
  okrs.value = listRes.data.items || []
}

async function loadPerformance() {
  const { data } = await fetchPerformanceWorkbench(periodLabel)
  cycle.value = data.cycle
  assessments.value = data.assessments || []
  appeals.value = data.appeals || []
  gradeDist.value = data.grade_distribution || { 'A+_A': 0, B: 0, C_D: 0 }
}

async function reload() {
  loading.value = true
  try {
    if (tab.value === 'bi') {
      await Promise.all([loadObjectives(), loadPerformance()])
    } else {
      await loadPerformance()
    }
  } catch (e: any) {
    notifyError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function onBiGoto(next: TabKey) {
  if (next === 'bi') return
  tab.value = next
}

function isMyAssessment(row: Assessment) {
  return Number(row.user_id) === Number(userStore.user?.id)
}

function canSubmitSelfRate(row: Assessment) {
  return isMyAssessment(row) || canManagePerformance.value
}

function togglePendingFilter() {
  assessFilter.value = assessFilter.value === 'pending' ? 'all' : 'pending'
}

function applySuggestedOkr() {
  if (assessDrawer.value?.suggested_okr_score != null) {
    managerForm.okr = assessDrawer.value.suggested_okr_score
  }
}

async function onResetCycle() {
  try {
    await ElMessageBox.confirm(
      '将清空本周期全部分数与申诉，名单回到「待自评」。确定重置？',
      '重置考核周期',
      { type: 'warning' },
    )
  } catch {
    return
  }
  acting.value = true
  try {
    await resetCycle(periodLabel)
    ElMessage.success('周期已重置，可重新自评与主管评价')
    assessFilter.value = 'pending'
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '重置失败')
  } finally {
    acting.value = false
  }
}

watch(tab, () => {
  reload()
})

onMounted(() => {
  reload()
})

async function openGoalDrawer(row: Okr) {
  try {
    const { data } = await fetchOkrDetail(row.id)
    goalDetail.value = data
    goalDrawerVisible.value = true
  } catch (e: any) {
    notifyError(e, '加载目标失败')
  }
}

function openCreateGoal() {
  createForm.title = ''
  createForm.level = 'personal'
  createForm.period_label = okrPeriodLabel
  createForm.parent_id = undefined
  createForm.kr_title = ''
  createVisible.value = true
}

async function submitCreateGoal() {
  if (!createForm.title.trim() || !createForm.kr_title.trim()) {
    ElMessage.warning('目标名称和 KR1 为必填')
    return
  }
  if (createForm.level !== 'company' && !createForm.parent_id) {
    ElMessage.warning('部门/个人目标必须选择上级目标')
    return
  }
  acting.value = true
  try {
    await createOkr({
      title: createForm.title.trim(),
      level: createForm.level,
      period_type: 'quarterly',
      period_label: createForm.period_label,
      parent_id: createForm.parent_id,
      key_results: [{ title: createForm.kr_title.trim(), target_value: 100, current_value: 0, weight: 100 }],
    })
    createVisible.value = false
    ElMessage.success('目标已创建')
    await loadObjectives()
  } catch (e: any) {
    notifyError(e, '创建失败')
  } finally {
    acting.value = false
  }
}

function openAssessmentDrawer(row: Assessment) {
  assessDrawer.value = row
  const suggested = row.suggested_okr_score
  const fallback = row.self_score ?? 70
  managerForm.okr = row.okr_score ?? suggested ?? fallback
  managerForm.kpi = row.kpi_score ?? fallback
  managerForm.behavior = row.behavior_score ?? fallback
  managerForm.comment = ''
  selfForm.score = row.self_score ?? 80
  appealCreateForm.score = Math.min(100, (row.final_score ?? 80) + 5)
  appealCreateForm.reason = ''
  assessDrawerVisible.value = true
}

async function submitSelfRate() {
  if (!assessDrawer.value) return
  acting.value = true
  try {
    await rateSelf(assessDrawer.value.id, { self_score: selfForm.score })
    ElMessage.success('自评已提交')
    assessDrawerVisible.value = false
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '提交失败')
  } finally {
    acting.value = false
  }
}

async function submitManagerRate() {
  if (!assessDrawer.value) return
  if (!managerForm.comment.trim()) {
    ElMessage.warning('请填写评价依据')
    return
  }
  acting.value = true
  try {
    await rateManager(assessDrawer.value.id, {
      okr_score: managerForm.okr,
      kpi_score: managerForm.kpi,
      behavior_score: managerForm.behavior,
      comment: managerForm.comment.trim(),
    })
    ElMessage.success('主管评价已提交')
    assessDrawerVisible.value = false
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '提交失败')
  } finally {
    acting.value = false
  }
}

async function submitCreateAppeal() {
  if (!assessDrawer.value) return
  if (!appealCreateForm.reason.trim()) {
    ElMessage.warning('请填写申诉理由')
    return
  }
  acting.value = true
  try {
    await createAppeal(assessDrawer.value.id, {
      reason: appealCreateForm.reason.trim(),
      request_score: appealCreateForm.score,
    })
    ElMessage.success('申诉已提交')
    assessDrawerVisible.value = false
    tab.value = 'calibration'
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '提交失败')
  } finally {
    acting.value = false
  }
}

function openAppealDrawer(row: Appeal) {
  appealDrawer.value = row
  appealForm.resolution = '已核验项目任务、排期工时和直属负责人意见，按规则版本 V2026.07 处理。'
  appealDrawerVisible.value = true
}

async function submitAppeal(approve: boolean) {
  if (!appealDrawer.value) return
  if (!appealForm.resolution.trim()) {
    ElMessage.warning('请填写复核结论')
    return
  }
  acting.value = true
  try {
    await resolveAppeal(appealDrawer.value.id, {
      approve,
      resolution: appealForm.resolution.trim(),
      final_score: approve ? appealDrawer.value.request_score : undefined,
    })
    ElMessage.success('申诉已处理')
    appealDrawerVisible.value = false
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '处理失败')
  } finally {
    acting.value = false
  }
}

async function onCalibrationAction() {
  if (!cycle.value || cycle.value.locked) return
  if (!cycle.value.calibration_started) {
    try {
      await ElMessageBox.confirm('发起后冻结部门初评分，进入集中校准。确认发起？', '综合校准')
      acting.value = true
      await startCalibration(periodLabel)
      ElMessage.success('校准批次已建立')
      await loadPerformance()
    } catch (e: any) {
      if (e !== 'cancel') notifyError(e, '发起失败')
    } finally {
      acting.value = false
    }
    return
  }
  try {
    await ElMessageBox.confirm(
      '锁定后绩效结果将进入工资核算；普通角色不能修改。确认锁定？',
      '结果锁定',
    )
    acting.value = true
    await lockCycle(periodLabel)
    ElMessage.success('绩效结果已锁定')
    tab.value = 'payroll'
    await loadPerformance()
  } catch (e: any) {
    if (e !== 'cancel') notifyError(e, '锁定失败')
  } finally {
    acting.value = false
  }
}

async function onPayrollAction() {
  if (!cycle.value || cycle.value.payroll_published) return
  acting.value = true
  try {
    if (!cycle.value.payroll_created) {
      await generatePayroll(periodLabel)
      ElMessage.success('工资批次已生成')
    } else if (!cycle.value.payroll_reviewed) {
      await reviewPayroll(periodLabel)
      ElMessage.success('财务复核已完成')
    } else {
      await publishPayroll(periodLabel)
      ElMessage.success('工资条已发布')
    }
    await loadPerformance()
  } catch (e: any) {
    notifyError(e, '操作失败')
  } finally {
    acting.value = false
  }
}
</script>
