<template>
  <div class="crm-page contracts-page" :class="{ embedded }">
    <template v-if="embedded">
      <div class="crm-stats finance-kpi" style="--crm-stats-cols: 4">
        <div class="crm-stat-tile is-static is-accent">
          <span>本月合同额</span>
          <strong>¥{{ formatAmount(financeStats?.month_contract_amount) }}</strong>
          <em>核销率 {{ formatRate(financeStats?.collection_rate) }}% · 已确认到账 ¥{{ formatAmount(financeStats?.confirmed_receipt_amount) }}</em>
        </div>
        <div class="crm-stat-tile is-static">
          <span>待收款</span>
          <strong>¥{{ formatAmount(financeStats?.outstanding_receivable_amount) }}</strong>
          <em>
            <span v-if="(financeStats?.overdue_count ?? 0) > 0" class="warn-text">{{ financeStats?.overdue_count }} 笔逾期 · ¥{{ formatAmount(financeStats?.overdue_amount) }}</span>
            <span v-else>暂无逾期</span>
          </em>
        </div>
        <div class="crm-stat-tile is-static">
          <span>待核销</span>
          <strong>¥{{ formatAmount(financeStats?.unallocated_receipt_amount) }}</strong>
          <em>{{ financeStats?.pending_review_count ?? 0 }} 笔待复核 · ¥{{ formatAmount(financeStats?.pending_review_amount) }}</em>
        </div>
        <div class="crm-stat-tile is-static">
          <span>项目毛利</span>
          <strong>{{ formatRate(financeStats?.forecast_gross_margin) }}%</strong>
          <em>预测值 · 非法定会计口径</em>
        </div>
      </div>

      <div class="finance-subtabs">
        <div class="subtab-group">
          <button
            type="button"
            class="subtab"
            :class="{ active: financeTab === 'contracts' }"
            @click="setFinanceTab('contracts')"
          >
            合同台账
          </button>
          <button
            type="button"
            class="subtab"
            :class="{ active: financeTab === 'receivables' }"
            @click="setFinanceTab('receivables')"
          >
            应收计划
          </button>
          <button
            type="button"
            class="subtab"
            :class="{ active: financeTab === 'reconciliation' }"
            @click="setFinanceTab('reconciliation')"
          >
            到款核销
          </button>
        </div>
        <div class="finance-actions">
          <el-button
            v-if="financeTab === 'receivables' && canManageReceivable"
            v-perm.any="['contract:manage', 'payment:manage']"
            @click="openReceivableCreate"
          >
            ＋ 新建应收计划
          </el-button>
          <el-button
            v-if="financeTab === 'reconciliation' && canClaimReceipt"
            v-perm.any="['payment:claim', 'payment:manage']"
            type="primary"
            @click="openClaim"
          >
            ＋ 提交到款认领
          </el-button>
        </div>
      </div>
    </template>

    <div v-else class="crm-stats" :style="{ '--crm-stats-cols': String(statCards.length) }">
      <button
        v-for="item in statCards"
        :key="item.key"
        type="button"
        class="crm-stat-tile"
        @click="onStatClick(item)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </div>

    <section class="crm-panel">
      <div class="toolbar">
        <div class="filters">
          <el-radio-group v-if="!embedded" v-model="scope" @change="reload">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="mine">我的</el-radio-button>
          </el-radio-group>
          <el-select
            v-if="!embedded || financeTab === 'contracts'"
            v-model="status"
            clearable
            placeholder="状态"
            style="width: 140px"
            @change="reload"
          >
            <el-option
              v-for="(label, key) in CONTRACT_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
          <el-input
            v-model="keyword"
            :placeholder="searchPlaceholder"
            clearable
            style="width: 220px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button @click="reload">查询</el-button>
        </div>
        <el-button v-if="!embedded" type="primary" @click="openCreate">起草合同</el-button>
      </div>

      <!-- 合同台账 -->
      <template v-if="!embedded || financeTab === 'contracts'">
        <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
          <el-table-column prop="contract_no" label="合同编号" width="150">
            <template #default="{ row }"><b>{{ row.contract_no }}</b></template>
          </el-table-column>
          <el-table-column prop="customer_name" label="客户" min-width="140" show-overflow-tooltip />
          <el-table-column label="业务类型" width="120">
            <template #default="{ row }">{{ typeLabel(row.contract_type) }}</template>
          </el-table-column>
          <el-table-column label="合同金额" width="130" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column v-if="embedded" label="已收金额" width="120" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.paid_amount) }}</template>
          </el-table-column>
          <el-table-column v-if="embedded" label="下一收款日" width="120">
            <template #default="{ row }">
              <span v-if="row.collection_status === 'collected'" class="muted">已完成</span>
              <span v-else>{{ formatShortDate(row.next_due_date) || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="!embedded" prop="title" label="合同名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="130">
            <template #default="{ row }">
              <div class="status-cell">
                <el-tag :type="statusTag(row.status)" size="small">
                  {{ CONTRACT_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
                <small
                  v-if="embedded && collectionHint(row)"
                  class="collection-hint"
                  :class="{ done: row.collection_status === 'collected' }"
                >
                  {{ collectionHint(row) }}
                </small>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="owner_name" label="负责人" width="100" />
          <el-table-column v-if="!embedded" label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 应收计划 -->
      <template v-else-if="financeTab === 'receivables'">
        <el-table :data="receivableItems" v-loading="loading" stripe>
          <el-table-column label="应收编号" width="150">
            <template #default="{ row }"><b>{{ `YS-${row.id}` }}</b></template>
          </el-table-column>
          <el-table-column prop="contract_no" label="合同" width="140" />
          <el-table-column prop="customer_name" label="客户" min-width="120" show-overflow-tooltip />
          <el-table-column label="收款节点" min-width="120">
            <template #default="{ row }">{{ row.title || '应收款' }}</template>
          </el-table-column>
          <el-table-column label="应收金额" width="120" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="已核销" width="110" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.allocated_amount) }}</template>
          </el-table-column>
          <el-table-column label="未收金额" width="110" align="right">
            <template #default="{ row }"><b>¥{{ formatAmount(row.outstanding_amount) }}</b></template>
          </el-table-column>
          <el-table-column label="计划日期" width="120">
            <template #default="{ row }">{{ formatShortDate(row.due_date) || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="receivableTag(row.effective_status)" size="small">
                {{ receivableStatusLabel(row.effective_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="owner_name" label="负责人" width="100" />
        </el-table>
        <div class="table-footer">
          <span>应收计划需手动创建；分期合同按节点拆成多笔</span>
          <span>合计金额不得超过合同总额</span>
        </div>
      </template>

      <!-- 到款核销 -->
      <template v-else>
        <el-table :data="receiptItems" v-loading="loading" stripe>
          <el-table-column label="到款认领单" width="150">
            <template #default="{ row }"><b>{{ row.receipt_no }}</b></template>
          </el-table-column>
          <el-table-column prop="contract_no" label="关联合同" width="140" />
          <el-table-column prop="payer_name" label="付款方" min-width="120" show-overflow-tooltip />
          <el-table-column label="到账金额" width="110" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="已核销" width="100" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.allocated_amount) }}</template>
          </el-table-column>
          <el-table-column label="未核销" width="100" align="right">
            <template #default="{ row }"><b>¥{{ formatAmount(row.available_amount) }}</b></template>
          </el-table-column>
          <el-table-column label="到款日期" width="120">
            <template #default="{ row }">{{ formatShortDate(row.paid_date) || '—' }}</template>
          </el-table-column>
          <el-table-column label="银行流水" width="120">
            <template #default="{ row }">{{ row.bank_reference || '—' }}</template>
          </el-table-column>
          <el-table-column label="处理状态" width="110">
            <template #default="{ row }">
              <el-tag :type="receiptTag(row)" size="small">
                {{ receiptStatusLabel(row) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending_review' && canConfirmClaim"
                v-perm.any="['payment:confirm', 'payment:manage']"
                link
                type="primary"
                @click.stop="onConfirmClaim(row)"
              >
                确认到账
              </el-button>
              <el-button
                v-else-if="row.status === 'confirmed' && Number(row.available_amount) > 0 && canAllocate"
                v-perm.any="['payment:allocate', 'payment:manage']"
                link
                type="success"
                @click.stop="openAllocation(row)"
              >
                核销
              </el-button>
              <el-button v-else link type="info" @click.stop="viewClaim(row)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-footer">
          <span>财务复核确认到账；核销提交后进入审批中心，通过后才计入应收</span>
          <span>本模块不生成法定会计凭证</span>
        </div>
      </template>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadCurrent"
          @size-change="loadCurrent"
        />
      </div>
    </section>

    <el-dialog v-model="createVisible" title="起草合同" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="合同名称" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="客户" prop="customer_id">
          <el-select
            v-model="form.customer_id"
            filterable
            remote
            :remote-method="searchCustomers"
            :loading="customerLoading"
            placeholder="搜索客户"
            style="width: 100%"
          >
            <el-option
              v-for="c in customerOptions"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="合同类型">
          <el-select v-model="form.contract_type" style="width: 100%">
            <el-option
              v-for="opt in CONTRACT_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="form.payment_method" clearable style="width: 100%">
            <el-option
              v-for="opt in PAYMENT_METHOD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker v-model="form.expire_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="合同证明" prop="proof_filename">
          <div
            class="upload-box"
            :class="{ uploaded: !!form.proof_filename }"
            @click="pickContractProof"
          >
            <template v-if="form.proof_filename">
              <b>{{ form.proof_filename }}</b>
              <small>{{ uploadingProof ? '上传中…' : '已上传 · 可重新选择' }}</small>
            </template>
            <template v-else>
              <b>上传合同照片或扫描件</b>
              <small>PDF、PNG或JPG · 单文件不超过10MB · 审批可追溯</small>
            </template>
          </div>
          <input
            ref="contractProofInputRef"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            hidden
            @change="onContractProofSelected"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">保存草稿</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="receivableVisible" title="新建应收计划（分期节点）" width="560px" destroy-on-close>
      <p class="dialog-hint">同一合同可建多笔；金额合计不超过合同总额。一次性付款建一笔即可，分期按首付/验收/尾款等拆开。</p>
      <el-form
        ref="receivableFormRef"
        :model="receivableForm"
        :rules="receivableRules"
        label-width="100px"
      >
        <el-form-item label="合同" prop="contract_id">
          <el-select v-model="receivableForm.contract_id" filterable style="width: 100%">
            <el-option
              v-for="c in claimContracts"
              :key="c.id"
              :label="`${c.contract_no} · ${c.customer_name || c.title}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="收款节点" prop="title">
          <el-input v-model="receivableForm.title" placeholder="如：首付款、验收款、尾款" />
        </el-form-item>
        <el-form-item label="应收金额" prop="amount">
          <el-input-number
            v-model="receivableForm.amount"
            :min="0.01"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="计划日期" prop="due_date">
          <el-date-picker
            v-model="receivableForm.due_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="receivableForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="receivableVisible = false">取消</el-button>
        <el-button type="primary" :loading="receivableSaving" @click="onCreateReceivable">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="claimVisible"
      title="提交到账信息"
      width="720px"
      destroy-on-close
      class="claim-dialog"
    >
      <p class="dialog-eyebrow">到款认领</p>
      <el-form ref="claimFormRef" :model="claimForm" :rules="claimRules" label-position="top" class="claim-form">
        <section class="form-block">
          <h3><span>1</span>关联合同</h3>
          <el-form-item label="合同" prop="contract_id">
            <el-select
              v-model="claimForm.contract_id"
              filterable
              placeholder="选择合同"
              style="width: 100%"
              @change="onClaimContractChange"
            >
              <el-option
                v-for="c in claimContracts"
                :key="c.id"
                :label="`${c.contract_no} · ${c.customer_name || c.title}`"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <div class="form-grid-2">
            <el-form-item label="认领金额" prop="amount">
              <el-input-number v-model="claimForm.amount" :min="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item label="到账日期" prop="paid_date">
              <el-date-picker
                v-model="claimForm.paid_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="付款方" prop="payer_name">
              <el-input v-model="claimForm.payer_name" placeholder="付款方名称" />
            </el-form-item>
            <el-form-item label="收款账户末四位">
              <el-input
                v-model="claimForm.account_tail"
                maxlength="4"
                placeholder="用于财务匹配"
              />
            </el-form-item>
          </div>
        </section>

        <section class="form-block">
          <h3><span>2</span>到账证明</h3>
          <el-form-item prop="proof_filename">
            <div
              class="upload-box"
              :class="{ uploaded: !!claimForm.proof_filename }"
              @click="pickProof"
            >
              <template v-if="claimForm.proof_filename">
                <b>{{ claimForm.proof_filename }}</b>
                <small>已选择 · 可重新选择</small>
              </template>
              <template v-else>
                <b>上传银行回单或到账截图</b>
                <small>PDF、PNG或JPG · 单文件不超过10MB · 财务复核可追溯</small>
              </template>
            </div>
            <input
              ref="proofInputRef"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              hidden
              @change="onProofSelected"
            />
          </el-form-item>
        </section>

        <section class="form-block">
          <h3><span>3</span>提交检查</h3>
          <div class="health-list">
            <div class="health-row">
              <span>ⓘ 关联合同</span>
              <b>{{ selectedClaimContractNo || '待选择' }}</b>
            </div>
            <div class="health-row">
              <span>ⓘ 到账确认</span>
              <b>提交后进入待复核队列，确认到账后再提交核销审批</b>
            </div>
            <div class="health-row">
              <span>✓ 审计记录</span>
              <b>保存提交人与附件版本</b>
            </div>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" :loading="claimSaving" @click="onSubmitClaim">提交财务复核</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="claimDetailVisible"
      title="到款认领详情"
      width="560px"
      destroy-on-close
    >
      <el-descriptions v-if="claimDetail" :column="2" border>
        <el-descriptions-item label="认领单号" :span="2">
          {{ claimDetail.receipt_no }}
        </el-descriptions-item>
        <el-descriptions-item label="关联合同" :span="2">
          {{ claimDetail.contract_no || '—' }}
          <span v-if="claimDetail.contract_title" class="muted"> · {{ claimDetail.contract_title }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付款方">{{ claimDetail.payer_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="认领金额">¥{{ formatAmount(claimDetail.amount) }}</el-descriptions-item>
        <el-descriptions-item label="到账日期">
          {{ formatShortDate(claimDetail.paid_date) || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="收款账户">
          {{ claimDetail.bank_reference || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="处理状态">
          <el-tag :type="receiptTag(claimDetail)" size="small">
            {{ receiptStatusLabel(claimDetail) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提交人">{{ claimDetail.submitted_by_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="到账证明" :span="2">
          {{ claimDetail.proof_filename || '未上传' }}
        </el-descriptions-item>
        <el-descriptions-item label="已核销金额">
          ¥{{ formatAmount(claimDetail.allocated_amount) }}
        </el-descriptions-item>
        <el-descriptions-item label="未核销余额">
          ¥{{ formatAmount(claimDetail.available_amount) }}
        </el-descriptions-item>
        <el-descriptions-item v-if="claimDetail.confirmed_by_name" label="确认人">
          {{ claimDetail.confirmed_by_name }}
        </el-descriptions-item>
        <el-descriptions-item v-if="claimDetail.confirmed_at" label="复核时间">
          {{ formatShortDate(claimDetail.confirmed_at) || claimDetail.confirmed_at }}
        </el-descriptions-item>
        <el-descriptions-item v-if="claimDetail.remark" label="备注" :span="2">
          {{ claimDetail.remark }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="claimDetailVisible = false">关闭</el-button>
        <el-button
          v-if="claimDetail?.status === 'pending_review' && canConfirmClaim"
          type="primary"
          @click="onConfirmClaimFromDetail"
        >
          确认到账
        </el-button>
        <el-button
          v-if="claimDetail?.status === 'confirmed' && Number(claimDetail.available_amount) > 0 && canAllocate"
          type="success"
          @click="openAllocationFromDetail"
        >
          提交核销
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="allocationVisible" title="提交收款核销" width="620px" destroy-on-close>
      <el-alert
        v-if="allocationReceipt"
        :title="`${allocationReceipt.receipt_no} 可核销余额：¥${formatAmount(allocationReceipt.available_amount)}（提交后进入审批中心）`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-form
        ref="allocationFormRef"
        :model="allocationForm"
        :rules="allocationRules"
        label-width="110px"
      >
        <el-form-item label="核销到应收" prop="receivable_plan_id">
          <el-select v-model="allocationForm.receivable_plan_id" style="width: 100%">
            <el-option
              v-for="item in allocationReceivables"
              :key="item.id"
              :label="`${item.title} · 未收 ¥${formatAmount(item.outstanding_amount)} · ${formatShortDate(item.due_date)}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="本次核销金额" prop="amount">
          <el-input-number
            v-model="allocationForm.amount"
            :min="0.01"
            :max="allocationMaxAmount"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="allocationVisible = false">取消</el-button>
        <el-button type="primary" :loading="allocationSaving" @click="onAllocate">
          提交审批
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CONTRACT_STATUS_LABEL,
  CONTRACT_TYPE_OPTIONS,
  PAYMENT_METHOD_OPTIONS,
  createContract,
  fetchContractStats,
  fetchContracts,
  type Contract,
  type ContractStats,
} from '@/api/contracts'
import { fetchCustomers, type Customer } from '@/api/customers'
import {
  createAllocation,
  createReceipt,
  createReceivable,
  fetchFinanceStats,
  fetchReceiptWorkbench,
  fetchReceivableWorkbench,
  fetchReceivables,
  reviewReceipt,
  type FinanceStats,
  type Receipt,
  type Receivable,
} from '@/api/finance'
import { uploadFile } from '@/api/uploads'
import { useUserStore } from '@/stores/user'

/** HTTP 非 localhost 下 crypto.randomUUID 不可用，幂等键用兼容实现 */
function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

const props = withDefaults(
  defineProps<{
    embedded?: boolean
    openCreateSignal?: number
    openClaimSignal?: number
  }>(),
  { embedded: false, openCreateSignal: 0, openClaimSignal: 0 },
)

const router = useRouter()
const userStore = useUserStore()

const canConfirmClaim = computed(() =>
  userStore.hasAnyPermission('payment:confirm', 'payment:manage'),
)
const canAllocate = computed(() =>
  userStore.hasAnyPermission('payment:allocate', 'payment:manage'),
)
const canClaimReceipt = computed(() =>
  userStore.hasAnyPermission('payment:claim', 'payment:manage'),
)
const canManageReceivable = computed(() =>
  userStore.hasAnyPermission('contract:manage', 'payment:manage'),
)
const loading = ref(false)
const saving = ref(false)
const claimSaving = ref(false)
const receivableSaving = ref(false)
const allocationSaving = ref(false)
const customerLoading = ref(false)
const items = ref<Contract[]>([])
const receivableItems = ref<Receivable[]>([])
const receiptItems = ref<Receipt[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('all')
const status = ref<string | undefined>()
const keyword = ref('')
const stats = ref<ContractStats | null>(null)
const financeStats = ref<FinanceStats | null>(null)
const financeTab = ref<'contracts' | 'receivables' | 'reconciliation'>('contracts')
const customerOptions = ref<Customer[]>([])
const claimContracts = ref<Contract[]>([])

const createVisible = ref(false)
const claimVisible = ref(false)
const claimDetailVisible = ref(false)
const receivableVisible = ref(false)
const allocationVisible = ref(false)
const claimDetail = ref<Receipt | null>(null)
const allocationReceipt = ref<Receipt | null>(null)
const allocationReceivables = ref<Receivable[]>([])
const formRef = ref<FormInstance>()
const claimFormRef = ref<FormInstance>()
const receivableFormRef = ref<FormInstance>()
const allocationFormRef = ref<FormInstance>()
const proofInputRef = ref<HTMLInputElement>()
const contractProofInputRef = ref<HTMLInputElement>()
const uploadingProof = ref(false)

const form = reactive({
  title: '',
  customer_id: undefined as number | undefined,
  contract_type: 'ai_product',
  amount: 0,
  payment_method: '',
  effective_date: '',
  expire_date: '',
  remark: '',
  proof_filename: '',
  proof_path: '',
})
const rules: FormRules = {
  title: [{ required: true, message: '请输入合同名称', trigger: 'blur' }],
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }],
  proof_filename: [{ required: true, message: '请上传合同照片或证明', trigger: 'change' }],
}

const claimForm = reactive({
  contract_id: undefined as number | undefined,
  amount: undefined as number | undefined,
  paid_date: new Date().toISOString().slice(0, 10),
  payer_name: '',
  account_tail: '',
  proof_filename: '',
})
const receivableForm = reactive({
  contract_id: undefined as number | undefined,
  title: '',
  amount: undefined as number | undefined,
  due_date: '',
  remark: '',
})
const allocationForm = reactive({
  receivable_plan_id: undefined as number | undefined,
  amount: undefined as number | undefined,
})
const claimRules: FormRules = {
  contract_id: [{ required: true, message: '请选择合同', trigger: 'change' }],
  amount: [{ required: true, message: '请输入认领金额', trigger: 'blur' }],
  paid_date: [{ required: true, message: '请选择到账日期', trigger: 'change' }],
  payer_name: [{ required: true, message: '请输入付款方', trigger: 'blur' }],
  proof_filename: [{ required: true, message: '请上传到账证明', trigger: 'change' }],
}
const receivableRules: FormRules = {
  contract_id: [{ required: true, message: '请选择合同', trigger: 'change' }],
  title: [{ required: true, message: '请输入收款节点', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入应收金额', trigger: 'blur' }],
  due_date: [{ required: true, message: '请选择计划日期', trigger: 'change' }],
}
const allocationRules: FormRules = {
  receivable_plan_id: [{ required: true, message: '请选择应收计划', trigger: 'change' }],
  amount: [{ required: true, message: '请输入核销金额', trigger: 'blur' }],
}

const selectedClaimContractNo = computed(() => {
  const c = claimContracts.value.find((x) => x.id === claimForm.contract_id)
  return c?.contract_no || ''
})

const allocationMaxAmount = computed(() => {
  const receiptAvailable = Number(allocationReceipt.value?.available_amount || 0)
  const receivable = allocationReceivables.value.find(
    (item) => item.id === allocationForm.receivable_plan_id,
  )
  return Math.min(receiptAvailable, Number(receivable?.outstanding_amount || 0))
})

const searchPlaceholder = computed(() => {
  if (financeTab.value === 'receivables') return '搜索应收编号/合同'
  if (financeTab.value === 'reconciliation') return '搜索认领单/付款方'
  return '搜索编号/标题'
})

const statCards = computed(() => {
  const s = stats.value
  return [
    { key: 'total', label: '全部', value: s?.total ?? 0, status: undefined },
    { key: 'draft', label: '草稿', value: s?.draft ?? 0, status: 'draft' },
    { key: 'pending', label: '待审批', value: s?.pending_approval ?? 0, status: 'pending_approval' },
    { key: 'approved', label: '已审批', value: s?.approved ?? 0, status: 'approved' },
    { key: 'signed', label: '已签署', value: s?.signed ?? 0, status: 'signed' },
    { key: 'active', label: '执行中', value: s?.active ?? 0, status: 'active' },
    { key: 'completed', label: '已完成', value: s?.completed ?? 0, status: 'completed' },
    { key: 'mine', label: '我的', value: s?.mine ?? 0, scope: 'mine', status: undefined },
  ]
})

function typeLabel(code: string) {
  return CONTRACT_TYPE_OPTIONS.find((x) => x.value === code)?.label || code
}

function formatAmount(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n)
    ? n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
    : '0'
}

function formatRate(v?: number | string | null) {
  const n = Number(v || 0)
  return Number.isFinite(n) ? n.toFixed(n % 1 === 0 ? 0 : 1) : '0'
}

function formatShortDate(v?: string | null) {
  if (!v) return ''
  const d = v.slice(5, 10)
  return d.replace('-', '-')
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    draft: 'info',
    pending_approval: 'warning',
    approved: '',
    signed: 'success',
    active: '',
    completed: 'success',
    terminated: 'danger',
  }
  return map[s] || 'info'
}

/** 销售中心附带回款提示：仅对已签署/执行中/已完成有意义 */
function collectionHint(row: Contract) {
  if (!['signed', 'active', 'completed'].includes(row.status)) return ''
  if (row.collection_status === 'collected' || row.status === 'completed') return '回款已收齐'
  const paid = Number(row.paid_amount || 0)
  if (paid > 0) return '回款中'
  return '待回款'
}

function receivableTag(status: string) {
  if (status === 'overdue') return 'danger'
  if (status === 'partially_paid') return 'warning'
  if (status === 'paid') return 'success'
  return 'info'
}

function receivableStatusLabel(status: string) {
  const labels: Record<string, string> = {
    unpaid: '待收款',
    partially_paid: '部分核销',
    paid: '已收齐',
    overdue: '已逾期',
    cancelled: '已取消',
  }
  return labels[status] || status
}

function receiptStatusLabel(row: Receipt) {
  if (row.status === 'pending_review') return '待确认到账'
  if (row.status === 'rejected') return '已驳回'
  if (row.status === 'cancelled') return '已取消'
  const pending = Number(row.pending_allocation_amount || 0)
  if (row.status === 'confirmed' && pending > 0 && Number(row.available_amount) <= 0) {
    return '核销审批中'
  }
  if (row.status === 'confirmed' && pending > 0) return '部分核销审批中'
  if (row.status === 'confirmed' && Number(row.available_amount) <= 0) return '已全部核销'
  if (row.status === 'confirmed' && Number(row.allocated_amount) > 0) return '部分核销'
  if (row.status === 'confirmed') return '待核销'
  return row.status
}

function receiptTag(row: Receipt) {
  if (row.status === 'rejected' || row.status === 'cancelled') return 'danger'
  if (row.status === 'pending_review') return 'info'
  if (Number(row.pending_allocation_amount || 0) > 0) return 'warning'
  if (Number(row.available_amount) <= 0) return 'success'
  if (Number(row.allocated_amount) > 0) return 'warning'
  return 'info'
}

function onStatClick(item: { status?: string; scope?: string }) {
  if (item.scope) scope.value = item.scope
  else scope.value = 'all'
  status.value = item.status
  page.value = 1
  reload()
}

function setFinanceTab(tab: typeof financeTab.value) {
  financeTab.value = tab
  page.value = 1
  status.value = undefined
  keyword.value = ''
  loadCurrent()
}

async function searchCustomers(q: string) {
  customerLoading.value = true
  try {
    const { data } = await fetchCustomers({ keyword: q || undefined, page: 1, page_size: 20 })
    customerOptions.value = data.items
  } finally {
    customerLoading.value = false
  }
}

async function loadStats() {
  const { data } = await fetchContractStats()
  stats.value = data
  if (props.embedded) {
    try {
      const { data: finance } = await fetchFinanceStats()
      financeStats.value = finance
    } catch {
      financeStats.value = null
    }
  }
}

async function loadContracts() {
  loading.value = true
  try {
    const { data } = await fetchContracts({
      scope: scope.value,
      status: status.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadReceivables() {
  loading.value = true
  try {
    const { data } = await fetchReceivableWorkbench({
      status: status.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    receivableItems.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadReceipts() {
  loading.value = true
  try {
    const { data } = await fetchReceiptWorkbench({
      status: status.value,
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    receiptItems.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function loadCurrent() {
  if (!props.embedded || financeTab.value === 'contracts') return loadContracts()
  if (financeTab.value === 'receivables') return loadReceivables()
  return loadReceipts()
}

function reload() {
  page.value = 1
  loadCurrent()
  loadStats()
}

function goDetail(row: Contract) {
  router.push(`/contracts/${row.id}`)
}

async function openCreate() {
  form.title = ''
  form.customer_id = undefined
  form.contract_type = 'ai_product'
  form.amount = 0
  form.payment_method = ''
  form.effective_date = ''
  form.expire_date = ''
  form.remark = ''
  form.proof_filename = ''
  form.proof_path = ''
  await searchCustomers('')
  createVisible.value = true
}

function pickContractProof() {
  if (uploadingProof.value) return
  contractProofInputRef.value?.click()
}

async function onContractProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('单文件不超过 10MB')
    input.value = ''
    return
  }
  uploadingProof.value = true
  try {
    const { data } = await uploadFile(file, 'contract_proof')
    form.proof_filename = data.filename
    form.proof_path = data.path
    formRef.value?.validateField('proof_filename')
  } finally {
    uploadingProof.value = false
    input.value = ''
  }
}

async function onCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.customer_id) return
  if (!form.proof_filename || !form.proof_path) {
    ElMessage.warning('请上传合同照片或证明')
    return
  }
  saving.value = true
  try {
    await createContract({
      title: form.title,
      customer_id: form.customer_id,
      contract_type: form.contract_type,
      amount: form.amount,
      payment_method: form.payment_method || undefined,
      effective_date: form.effective_date || undefined,
      expire_date: form.expire_date || undefined,
      remark: form.remark || undefined,
      proof_filename: form.proof_filename,
      proof_path: form.proof_path,
    })
    ElMessage.success('草稿已保存')
    createVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

async function openClaim() {
  claimForm.contract_id = undefined
  claimForm.amount = undefined
  claimForm.paid_date = new Date().toISOString().slice(0, 10)
  claimForm.payer_name = ''
  claimForm.account_tail = ''
  claimForm.proof_filename = ''
  const { data } = await fetchContracts({ page: 1, page_size: 100, scope: 'all' })
  claimContracts.value = data.items.filter((c) =>
    ['signed', 'active', 'approved', 'completed'].includes(c.status),
  )
  if (!claimContracts.value.length) claimContracts.value = data.items
  claimVisible.value = true
}

async function openReceivableCreate() {
  receivableForm.contract_id = undefined
  receivableForm.title = ''
  receivableForm.amount = undefined
  receivableForm.due_date = ''
  receivableForm.remark = ''
  const { data } = await fetchContracts({ page: 1, page_size: 100, scope: 'all' })
  claimContracts.value = data.items.filter((c) =>
    ['signed', 'active', 'approved'].includes(c.status),
  )
  if (!claimContracts.value.length) claimContracts.value = data.items
  receivableVisible.value = true
}

async function onCreateReceivable() {
  const ok = await receivableFormRef.value?.validate().catch(() => false)
  if (
    !ok ||
    !receivableForm.contract_id ||
    !receivableForm.amount ||
    !receivableForm.due_date
  ) return
  receivableSaving.value = true
  try {
    await createReceivable(receivableForm.contract_id, {
      title: receivableForm.title.trim(),
      amount: receivableForm.amount,
      due_date: receivableForm.due_date,
      remark: receivableForm.remark || undefined,
    })
    ElMessage.success('应收计划已创建')
    receivableVisible.value = false
    reload()
  } finally {
    receivableSaving.value = false
  }
}

function onClaimContractChange(id: number) {
  const c = claimContracts.value.find((x) => x.id === id)
  if (c?.customer_name) claimForm.payer_name = c.customer_name
}

function pickProof() {
  proofInputRef.value?.click()
}

function onProofSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('单文件不超过 10MB')
    input.value = ''
    return
  }
  claimForm.proof_filename = file.name
  input.value = ''
}

async function onSubmitClaim() {
  const ok = await claimFormRef.value?.validate().catch(() => false)
  if (!ok || !claimForm.contract_id || !claimForm.amount) return
  if (!claimForm.proof_filename) {
    ElMessage.warning('金额、日期、付款方和到账证明均为必填项')
    return
  }
  claimSaving.value = true
  try {
    await createReceipt({
      contract_id: claimForm.contract_id,
      amount: claimForm.amount,
      paid_date: claimForm.paid_date,
      payer_name: claimForm.payer_name.trim(),
      bank_reference: claimForm.account_tail || undefined,
      proof_filename: claimForm.proof_filename,
      idempotency_key: newIdempotencyKey(),
    })
    ElMessage.success('到款认领已提交，已进入财务复核队列')
    claimVisible.value = false
    financeTab.value = 'reconciliation'
    reload()
  } finally {
    claimSaving.value = false
  }
}

async function onConfirmClaim(row: Receipt) {
  await ElMessageBox.confirm(
    `确认认领单 ${row.receipt_no} 已实际到账？确认到账后仍需提交核销并经审批通过。`,
    '确认到账',
    { type: 'warning', confirmButtonText: '确认到账', cancelButtonText: '取消' },
  )
  await reviewReceipt(row.id, true, row.version)
  ElMessage.success('到账已确认，请继续提交核销审批')
  reload()
}

function viewClaim(row: Receipt) {
  claimDetail.value = row
  claimDetailVisible.value = true
}

async function onConfirmClaimFromDetail() {
  if (!claimDetail.value) return
  await onConfirmClaim(claimDetail.value)
  claimDetailVisible.value = false
}

async function openAllocation(row: Receipt) {
  allocationReceipt.value = row
  const { data } = await fetchReceivables(row.contract_id)
  allocationReceivables.value = data.filter(
    (item) => item.status !== 'cancelled' && Number(item.outstanding_amount) > 0,
  )
  if (!allocationReceivables.value.length) {
    ElMessage.warning('该合同没有可核销的应收计划，请先创建应收计划')
    return
  }
  allocationForm.receivable_plan_id = allocationReceivables.value[0].id
  allocationForm.amount = Math.min(
    Number(row.available_amount),
    Number(allocationReceivables.value[0].outstanding_amount),
  )
  allocationVisible.value = true
}

async function openAllocationFromDetail() {
  if (!claimDetail.value) return
  claimDetailVisible.value = false
  await openAllocation(claimDetail.value)
}

async function onAllocate() {
  const ok = await allocationFormRef.value?.validate().catch(() => false)
  if (
    !ok ||
    !allocationReceipt.value ||
    !allocationForm.receivable_plan_id ||
    !allocationForm.amount
  ) return
  allocationSaving.value = true
  try {
    await createAllocation(allocationReceipt.value.id, {
      receivable_plan_id: allocationForm.receivable_plan_id,
      amount: allocationForm.amount,
      idempotency_key: newIdempotencyKey(),
    })
    ElMessage.success('核销已提交，请到审批中心处理')
    allocationVisible.value = false
    reload()
  } finally {
    allocationSaving.value = false
  }
}

watch(
  () => allocationForm.receivable_plan_id,
  (id) => {
    if (!id || !allocationReceipt.value) return
    const item = allocationReceivables.value.find((row) => row.id === id)
    allocationForm.amount = Math.min(
      Number(allocationReceipt.value.available_amount),
      Number(item?.outstanding_amount || 0),
    )
  },
)

onMounted(() => {
  reload()
})

watch(
  () => props.openCreateSignal,
  (v, old) => {
    if (props.embedded && v && v !== old) openCreate()
  },
)

watch(
  () => props.openClaimSignal,
  (v, old) => {
    if (props.embedded && v && v !== old) openClaim()
  },
)
</script>

<style scoped>
.finance-kpi .is-accent {
  background: linear-gradient(145deg, #0b3d91, #062a66);
  color: #fff;
}
.finance-kpi .is-accent span,
.finance-kpi .is-accent em {
  color: #c9dbff;
}
.finance-kpi .is-accent strong {
  color: #fff;
}
.warn-text {
  color: oklch(0.55 0.16 25);
}
.muted {
  color: var(--crm-ink-soft);
}
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}
.collection-hint {
  color: var(--crm-ink-soft);
  font-size: 11px;
  line-height: 1.2;
}
.collection-hint.done {
  color: var(--crm-success, #389e0d);
}
.dialog-eyebrow {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--crm-primary);
  font-weight: 600;
}
.dialog-hint {
  margin: 0 0 14px;
  color: var(--crm-ink-soft);
  font-size: 13px;
  line-height: 1.5;
}
.form-block {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--crm-border);
}
.form-block:last-child {
  border-bottom: 0;
  margin-bottom: 0;
  padding-bottom: 0;
}
.form-block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 14px;
}
.form-block h3 span {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--crm-primary);
  color: #fff;
  font-size: 12px;
}
.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.upload-box {
  border: 1.5px dashed var(--crm-border);
  border-radius: 12px;
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--crm-surface-soft);
  transition: border-color 0.15s, background 0.15s;
}
.upload-box:hover {
  border-color: var(--crm-primary);
}
.upload-box.uploaded {
  border-style: solid;
  border-color: var(--crm-success);
  background: var(--crm-success-soft);
}
.upload-box b {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
}
.upload-box small {
  color: var(--crm-ink-soft);
  font-size: 12px;
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
  border-radius: 8px;
  background: var(--crm-surface-soft);
  font-size: 13px;
}
.health-row b {
  font-weight: 600;
  color: var(--crm-ink);
}
@media (max-width: 700px) {
  .form-grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
