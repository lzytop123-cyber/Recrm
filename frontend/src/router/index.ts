/**
 * 路由：登录页 + 主框架 + 各业务页。
 * 守卫：未登录跳转 /login；无权限跳转 /dashboard。
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getToken } from '@/api/request'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/login/feishu/callback',
    name: 'FeishuCallback',
    component: () => import('@/views/FeishuCallbackView.vue'),
    meta: { public: true, title: '飞书登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '经营总览', permission: 'dashboard:view' },
      },
      {
        path: 'todos',
        name: 'MyTodos',
        component: () => import('@/views/todos/MyTodosView.vue'),
        meta: { title: '我的待办' },
      },
      {
        path: 'approvals',
        name: 'Approvals',
        component: () => import('@/views/approvals/ApprovalCenterView.vue'),
        meta: { title: '审批中心', permission: 'approval:center' },
      },
      {
        path: 'sales',
        name: 'Sales',
        component: () => import('@/views/sales/SalesCenterView.vue'),
        meta: { title: '销售中心', permission: 'lead:view' },
      },
      {
        path: 'lead-entry',
        name: 'LeadEntry',
        component: () => import('@/views/leads/LeadEntryView.vue'),
        meta: { title: '线索录入', permission: 'lead:view' },
      },
      {
        path: 'leads',
        redirect: { path: '/sales', query: { tab: 'mine' } },
      },
      {
        path: 'leads/:id',
        name: 'LeadDetail',
        component: () => import('@/views/leads/LeadDetailView.vue'),
        meta: { title: '线索详情', permission: 'lead:view' },
      },
      {
        path: 'customers',
        redirect: { path: '/sales', query: { tab: 'customers' } },
      },
      {
        path: 'customers/:id',
        name: 'CustomerDetail',
        component: () => import('@/views/customers/CustomerDetailView.vue'),
        meta: { title: '客户详情', permission: 'customer:view' },
      },
      {
        path: 'opportunities',
        redirect: { path: '/sales', query: { tab: 'opportunities' } },
      },
      {
        path: 'opportunities/:id',
        name: 'OpportunityDetail',
        component: () => import('@/views/opportunities/OpportunityDetailView.vue'),
        meta: { title: '商机详情', permission: 'opportunity:view' },
      },
      {
        path: 'contracts',
        name: 'Contracts',
        component: () => import('@/views/contracts/ContractsWorkbenchView.vue'),
        meta: { title: '合同回款', permission: 'contract:view' },
      },
      {
        path: 'contracts/:id',
        name: 'ContractDetail',
        component: () => import('@/views/contracts/ContractDetailView.vue'),
        meta: { title: '合同详情', permission: 'contract:view' },
      },
      {
        path: 'payments',
        name: 'Payments',
        component: () => import('@/views/payments/PaymentListView.vue'),
        meta: { title: '收款', permission: 'payment:view' },
      },
      {
        path: 'payments/:id',
        name: 'PaymentDetail',
        component: () => import('@/views/payments/PaymentDetailView.vue'),
        meta: { title: '收款详情', permission: 'payment:view' },
      },
      {
        path: 'projects/delivery',
        name: 'ProjectDeliveryWork',
        component: () => import('@/views/projects/ProjectDeliveryView.vue'),
        meta: { title: '项目管理', permission: 'project:view' },
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/projects/ProjectDeliveryView.vue'),
        meta: { title: '项目管理', permission: 'project:view' },
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/projects/ProjectDetailView.vue'),
        meta: { title: '项目详情', permission: 'project:view' },
      },
      {
        path: 'okrs',
        name: 'Okrs',
        component: () => import('@/views/okrs/OkrListView.vue'),
        meta: { title: '目标绩效', permission: 'okr:view', phase2: true },
      },
      {
        path: 'okrs/:id',
        name: 'OkrDetail',
        component: () => import('@/views/okrs/OkrDetailView.vue'),
        meta: { title: 'OKR详情', permission: 'okr:view', phase2: true },
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/views/assets/AssetWorkbenchView.vue'),
        meta: { title: '固定资产', permission: 'asset:view' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/KnowledgeWorkbenchView.vue'),
        meta: { title: 'AI知识库', permission: 'knowledge:view' },
      },
      {
        path: 'timesheets',
        name: 'Timesheets',
        component: () => import('@/views/timesheets/TimesheetListView.vue'),
        meta: { title: '工时', permission: 'timesheet:view' },
      },
      {
        path: 'timesheets/:id',
        name: 'TimesheetDetail',
        component: () => import('@/views/timesheets/TimesheetDetailView.vue'),
        meta: { title: '工时详情', permission: 'timesheet:view' },
      },
      {
        path: 'tickets',
        name: 'Tickets',
        component: () => import('@/views/tickets/TicketListView.vue'),
        meta: { title: '协作工单', permission: 'ticket:view' },
      },
      {
        path: 'tickets/:id',
        name: 'TicketDetail',
        component: () => import('@/views/tickets/TicketDetailView.vue'),
        meta: { title: '协作工单详情', permission: 'ticket:view' },
      },
      {
        path: 'schedules',
        name: 'Schedules',
        component: () => import('@/views/schedules/ScheduleListView.vue'),
        meta: { title: '排期会议', permission: 'schedule:view' },
      },
      {
        path: 'schedules/:id',
        name: 'ScheduleDetail',
        component: () => import('@/views/schedules/ScheduleDetailView.vue'),
        meta: { title: '排期详情', permission: 'schedule:view' },
      },
      {
        path: 'org',
        name: 'Org',
        component: () => import('@/views/org/OrgView.vue'),
        meta: { title: '员工管理', permission: 'org:view' },
      },
      {
        path: 'org/employees/:id',
        name: 'EmployeeDetail',
        component: () => import('@/views/org/EmployeeDetailView.vue'),
        meta: { title: '员工档案', permission: 'org:view' },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/system/SystemView.vue'),
        meta: { title: '系统管理', permission: 'system:view' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  document.title = `${(to.meta.title as string) || '页面'} - 中泰旭鼎CRM`

  const token = getToken()
  const userStore = useUserStore()

  if (to.meta.public) {
    // 已登录访问登录页时直接进首页，避免移动端停在登录成功态
    if (to.path === '/login' && token) {
      if (!userStore.user) {
        try {
          await userStore.fetchProfile()
        } catch {
          userStore.logout()
          next()
          return
        }
      }
      next({ path: userStore.homePath || '/dashboard' })
      return
    }
    next()
    return
  }

  if (!token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  if (!userStore.user) {
    try {
      await userStore.fetchProfile()
    } catch {
      userStore.logout()
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
  }

  const required = to.meta.permission as string | undefined
  if (required && !userStore.hasPermission(required)) {
    ElMessage.warning('无权访问该页面')
    const fallback = userStore.homePath || '/todos'
    next({ path: fallback === to.path ? '/todos' : fallback })
    return
  }

  // 第二期模块：菜单已隐藏，直链访问也暂不开放
  if (to.meta.phase2) {
    ElMessage.info('目标绩效将在第二期开放')
    const fallback = userStore.homePath || '/todos'
    next({ path: fallback === to.path ? '/todos' : fallback })
    return
  }

  // 仅线索录入岗：禁止进销售中心（经营总览改由 dashboard:view 控制）
  if (userStore.leadEntryOnly) {
    if (to.path === '/sales' || to.path === '/') {
      next({ path: userStore.homePath })
      return
    }
  }

  next()
})

export default router
