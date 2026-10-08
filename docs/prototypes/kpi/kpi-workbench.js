'use strict';
// Standalone interaction prototype. All people, scores and changes are synthetic.
(function () {
  const app = document.getElementById('app');
  const overlay = document.getElementById('overlay');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icons = {
    chart: '<path d="M4 19h16M6 15V9m6 6V4m6 11v-6"/>',
    trophy: '<path d="M8 3h8v7a4 4 0 0 1-8 0V3Zm0 2H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4m-4 2v5m-4 2h8"/>',
    book: '<path d="M12 5c-3-2-7-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-2-1-6-1-9 1Zm0 0v15"/>',
    users: '<circle cx="9" cy="7" r="3"/><path d="M3 20v-3a6 6 0 0 1 12 0v3m1-15a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
    folder: '<path d="M3 6h7l2 3h9v11H3V6Z"/>',
    doc: '<path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6m-6 4h6"/>',
    bell: '<path d="M5 16h14l-2-3V8a5 5 0 0 0-10 0v5l-2 3Zm5 4h4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="m9 3 6 0 1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>'
  };
  const icon = name => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.doc) + '</svg>';
  const labels = { submit: '待员工提交', scoring: '待主管评分', review: '待 HR 复核', confirm: '待员工确认', done: '已完成' };
  const deptNames = ['市场部', 'AI技术运维', '内容制作团队', '品宣团队'];
  const roles = ['市场业务', '运维专员', '内容专员', '品牌策划'];
  const managers = ['李岚', '周宁', '陆可', '苏颖'];
  const names = [
    ['张明', '王芳', '李强', '陈晓', '赵敏', '林嘉'],
    ['陈浩', '许航', '杨帆', '周可', '刘洋', '方睿'],
    ['江雨', '苏瑶', '何静', '陆一', '郭晓', '徐宁'],
    ['顾晨', '宋晴', '唐悦', '沈舟', '程可', '叶珊']
  ];
  const statusSeeds = [
    ['submit', 'scoring', 'done', 'done', 'review', 'done'],
    ['done', 'done', 'scoring', 'confirm', 'done', 'done'],
    ['submit', 'submit', 'scoring', 'done', 'scoring', 'done'],
    ['review', 'done', 'done', 'scoring', 'submit', 'done']
  ];
  const templates = deptNames.map((department, i) => ({
    id: 'template-' + i, department, role: roles[i], name: ['市场业务月度考核', '运维服务月度考核', '内容交付月度考核', '品牌项目月度考核'][i],
    version: 2, status: 'published', updated: '2026-09-01',
    metrics: [
      { name: ['有效线索与签约', '系统稳定性', '内容交付完成率', '品牌项目交付'][i], max: 50, target: ['线索 20 条 / 签约 4 家', '可用率 ≥ 99.9%', '按计划交付 20 条', '完成当月项目计划'][i], source: ['CRM业务数据', '监控与工单', '内容任务台账', '项目验收记录'][i] },
      { name: ['客户跟进质量', '故障响应及时率', '内容质量', '传播效果'][i], max: 30, target: ['及时率 ≥ 95%', '及时率 ≥ 95%', '验收通过率 ≥ 95%', '达到项目约定目标'][i], source: ['跟进记录', '工单记录', '验收与修改记录', '项目传播报表'][i] },
      { name: '协作与工作规范', max: 20, target: '按时协作，执行工作规范', source: '主管评价' }
    ]
  }));
  const people = deptNames.flatMap((department, i) => names[i].map((name, j) => ({
    id: 'person-' + i + '-' + j, name, department, role: roles[i], manager: managers[i], templateId: templates[i].id, templateSnapshot: structuredClone(templates[i]),
    status: statusSeeds[i][j], score: ['done', 'review', 'confirm'].includes(statusSeeds[i][j]) ? 80 + (i * 3 + j * 2) % 17 : null,
    attention: i === 0 && j === 0 ? '材料已退回' : i === 2 && j === 0 ? '缺少成果附件' : '',
    log: [{ text: '考核已发起，模板及人员范围已确认', at: '2026-09-01 09:00' }]
  })));
  const cycles = {
    '2026-09': { people, dates: ['2026-10-03', '2026-10-05', '2026-10-06', '2026-10-08'], review: true },
    '2026-10': { people: [], dates: ['2026-11-03', '2026-11-05', '2026-11-06', '2026-11-08'], review: true }
  };
  const entry = new URLSearchParams(location.search);
  const requestedPage = entry.get('page') || 'overview';
  const requestedRole = ['admin', 'manager', 'employee'].includes(entry.get('role')) ? entry.get('role') : requestedPage === 'self' ? 'employee' : ['team', 'scoring'].includes(requestedPage) ? 'manager' : 'admin';
  const state = { role: requestedRole, page: requestedPage, cycle: '2026-09', history: '2026-08', status: 'all', department: '', query: '', tab: 'all', pageNumber: 1, pageSize: 10, templatePage: 1, employeeId: entry.get('person') || people[0].id, managerName: managers[0], managerQuery: '', teamTab: 'pending', selectedId: entry.get('person') || '' };
  const allowedPages = { admin: ['overview', 'history', 'templates'], manager: ['team', 'scoring'], employee: ['self'] };
  if (!allowedPages[state.role].includes(state.page)) state.page = allowedPages[state.role][0];
  let resizeObserver, frame, lastFocus, wizard, activePerson, activeTemplate;
  const cycleLabel = value => value.replace('-', '年') + '月';
  const current = () => cycles[state.cycle];
  const getEmployee = () => current().people.find(p => p.id === state.employeeId);
  let employee, manager;
  function rolePicker() {
    const employeeName = getEmployee()?.name || people.find(p => p.id === state.employeeId)?.name || '张明';
    return '<select class="kp-select kp-role-picker" id="kp-role" aria-label="原型体验身份">' + [['admin', '管理员 · 陈悦'], ['manager', '主管 · ' + state.managerName], ['employee', '员工 · ' + employeeName]].map(([role, label]) => '<option value="' + role + '"' + (state.role === role ? ' selected' : '') + '>' + label + '</option>').join('') + '</select>';
  }
  const button = (text, action, primary = false, extra = '') => '<button class="kb-btn' + (primary ? ' primary' : '') + '" data-kp-action="' + action + '" ' + extra + '>' + text + '</button>';
  const textButton = (text, action, extra = '') => '<button class="kp-text-btn" data-kp-action="' + action + '" ' + extra + '>' + text + '</button>';
  const statusTag = status => '<span class="kp-status ' + status + '">' + labels[status] + '</span>';
  const notify = message => {
    const notice = document.getElementById('notice');
    notice.textContent = message;
    notice.classList.add('show');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => notice.classList.remove('show'), 3500);
  };
  const departmentOptions = selected => '<option value="">全部部门</option>' + deptNames.map(d => '<option value="' + esc(d) + '"' + (selected === d ? ' selected' : '') + '>' + d + '</option>').join('');
  function historyRows() {
    return people.map((p, i) => ({ ...p, status: 'done', attention: '', score: 78 + (i * 7 + (state.history === '2026-07' ? 4 : 8)) % 20, previous: 78 + (i * 7 + 4) % 20 }));
  }
  const allRows = () => state.page === 'history' ? historyRows() : current().people;
  function filtered() {
    const query = state.query.trim().toLowerCase();
    return allRows().filter(p => (!state.department || p.department === state.department) &&
      (state.status === 'all' || (state.status === 'attention' ? Boolean(p.attention) : p.status === state.status)) &&
      (state.tab === 'all' || (state.tab === 'done' ? p.status === 'done' : p.status !== 'done')) &&
      (!query || [p.name, p.department, p.role, p.manager].join(' ').toLowerCase().includes(query)));
  }
  function counts(rows = current().people) {
    const result = { total: rows.length, submit: 0, scoring: 0, review: 0, confirm: 0, done: 0 };
    rows.forEach(p => result[p.status]++);
    return result;
  }
  function sidebar() {
    const menu = [['经营总览', 'chart'], ['我的待办', 'bell'], ['审批中心', 'check'], ['销售中心', 'users'], ['合同回款', 'doc'], ['项目管理', 'folder'], ['协作工单', 'doc'], ['排期会议', 'calendar']];
    return '<aside class="kb-sidebar"><div class="kb-brand"><span class="kb-brand-mark">鼎</span><div><small>经营管理平台</small><strong>中泰旭鼎 CRM</strong></div></div><nav class="kb-global-nav" aria-label="主导航">' +
      (state.role === 'admin' ? menu : menu.filter(([label]) => ['我的待办', '排期会议'].includes(label))).map(([label, name]) => '<button class="kb-nav-item" data-kp-action="outside">' + icon(name) + label + '</button>').join('') +
      '<div class="kb-nav-item group">' + icon('trophy') + 'KPI 考核</div>' +
      (state.role === 'admin' ? [['overview', '发起考核'], ['history', '往期考核'], ['templates', '考核模板管理']] : state.role === 'manager' ? [['team', '团队考核']] : [['self', '我的考核']]).map(([page, label]) => '<button class="kb-nav-item child ' + (state.page === page || page === 'team' && state.page === 'scoring' ? 'current' : '') + '" data-kp-action="page" data-value="' + page + '" aria-current="' + (state.page === page ? 'page' : 'false') + '">' + label + '</button>').join('') +
      (state.role === 'admin' ? '<button class="kb-nav-item" data-kp-action="outside">' + icon('folder') + '固定资产</button>' : '') + '<div class="kb-nav-item group">' + icon('book') + '知识库</div><a class="kb-nav-item child" href="frontend.html">企业知识库</a>' +
      (state.role === 'admin' ? '<button class="kb-nav-item" data-kp-action="outside">' + icon('users') + '员工管理</button><button class="kb-nav-item" data-kp-action="outside">' + icon('settings') + '系统设置</button>' : '') + '</nav>' +
      '<div class="kb-account"><span class="kb-avatar">' + (state.role === 'admin' ? '陈' : state.role === 'manager' ? state.managerName.slice(0, 1) : (getEmployee()?.name || '张明').slice(0, 1)) + '</span><div><strong>' + (state.role === 'admin' ? '陈悦' : state.role === 'manager' ? state.managerName : esc(getEmployee()?.name || '张明')) + '</strong><small>' + ({ admin: '人力资源管理员', manager: '直属团队主管', employee: '员工个人工作台' }[state.role]) + '</small></div></div></aside>';
  }
  function mobileNav() {
    return '<nav class="kp-mobile-nav" aria-label="KPI移动导航"><strong>中泰旭鼎 CRM</strong>' +
      (state.role === 'admin' ? [['overview', '本期考核'], ['history', '往期考核'], ['templates', '模板管理']] : state.role === 'manager' ? [['team', '团队考核']] : [['self', '我的考核']]).map(([page, text]) => '<button class="' + (state.page === page ? 'active' : '') + '" data-kp-action="page" data-value="' + page + '">' + text + '</button>').join('') +
      '<a href="frontend.html">企业知识库</a></nav>';
  }
  function header() {
    const title = state.page === 'history' ? '往期考核' : state.page === 'templates' ? '考核模板管理' : 'KPI 考核';
    const subtitle = state.page === 'history' ? '回顾每期考核结果，把成绩变化转化为后续沟通。' : state.page === 'templates' ? '统一评价标准，让每个部门用适合自己的考核规则。' : '看清团队进度，及时处理每一份考核。';
    let actions = state.page === 'templates' ? button(icon('plus') + '新建模板', 'new-template', true) :
      state.page === 'history' ? '<select class="kp-select" id="kp-history" aria-label="往期考核周期"><option value="2026-08"' + (state.history === '2026-08' ? ' selected' : '') + '>2026年8月</option><option value="2026-07"' + (state.history === '2026-07' ? ' selected' : '') + '>2026年7月</option></select>' + button(icon('download') + '导出结果', 'export') :
      '<select class="kp-select" id="kp-cycle" aria-label="本期考核周期"><option value="2026-09"' + (state.cycle === '2026-09' ? ' selected' : '') + '>2026年9月</option><option value="2026-10"' + (state.cycle === '2026-10' ? ' selected' : '') + '>2026年10月</option></select>' +
      button(icon('plus') + (current().people.length ? '发起下一期' : '配置新一期'), 'launch', true);
    return '<div class="kp-topline"><span>KPI 考核 ' + icon('chevron') + ' ' + (state.page === 'overview' ? '本期总览' : title) + '</span><small>交互原型 / 示例数据</small></div>' +
      '<header class="kp-heading"><div><div class="kp-title"><h1>' + title + '</h1><span class="kp-demo">管理员视角 / 示例数据</span></div><p>' + subtitle + '</p></div><div class="kp-actions">' + rolePicker() + actions + '</div></header>';
  }
  function cyclePanel() {
    const c = counts(), percent = c.total ? Math.round(c.done / c.total * 100) : 0;
    const stageKeys = current().review ? ['submit', 'scoring', 'review', 'confirm'] : ['submit', 'scoring', 'confirm'];
    return '<section class="kp-cycle" aria-label="考核阶段与截止时间"><div class="kp-cycle-label"><strong>' + cycleLabel(state.cycle) + '</strong><span><span class="kp-live">' + (c.total ? c.done === c.total ? '已完成' : '进行中' : '待发起') + '</span>月度考核</span></div><div class="kp-stages" style="grid-template-columns:repeat(' + stageKeys.length + ',minmax(0,1fr))">' +
      stageKeys.map((key, i) => '<button class="kp-stage ' + ((state.status === key || state.status === 'all' && i === 0) && c.total ? 'active' : '') + '" data-kp-action="status" data-value="' + key + '" aria-label="按' + labels[key] + '筛选"><b>' + ({ submit: '员工提交', scoring: '主管评分', review: 'HR 复核', confirm: '结果确认' }[key]) + '</b><small>' + current().dates[i].slice(5).replace('-', '/') + ' 截止</small></button>').join('') +
      '</div><div class="kp-completion"><strong>' + percent + '<small>%</small></strong><span>已完成 ' + c.done + ' / ' + c.total + ' 人</span></div></section>';
  }
  function stats() {
    if (state.page === 'history') {
      const rows = historyRows(), average = (rows.reduce((s, p) => s + p.score, 0) / rows.length).toFixed(1);
      return '<section class="kp-stats" style="grid-template-columns:repeat(4,minmax(0,1fr))">' +
        [['参评人数', rows.length, '人'], ['平均得分', average, '分'], ['90 分及以上', rows.filter(p => p.score >= 90).length, '人'], ['考核完成率', '100', '%']].map(([label, value, unit]) => '<div class="kp-stat"><small>' + label + '</small><strong>' + value + '<span>' + unit + '</span></strong></div>').join('') + '</section>';
    }
    const c = counts();
    return '<section class="kp-stats" aria-label="考核统计">' + [['all', '本期参评人数', c.total], ...Object.keys(labels).map(key => [key, labels[key], c[key]])].map(([key, label, number]) =>
      '<button class="kp-stat ' + (state.status === key ? 'active' : '') + '" data-kp-action="status" data-value="' + key + '" aria-label="筛选' + label + '" aria-pressed="' + (state.status === key) + '"><small><i></i>' + label + '</small><strong>' + number + '<span>人</span></strong></button>').join('') + '</section>';
  }
  function departments() {
    const rows = current().people;
    return '<aside class="kp-panel kp-departments"><div class="kp-panel-head"><h2>部门进度</h2>' + textButton('全部部门', 'clear-department') + '</div><div class="kp-dept-list">' + deptNames.map(department => {
      const members = rows.filter(p => p.department === department), c = counts(members), percent = c.total ? Math.round(c.done / c.total * 100) : 0;
      return '<button class="kp-dept ' + (state.department === department ? 'active' : '') + '" data-kp-action="department" data-value="' + department + '" aria-label="筛选' + department + '"><div class="kp-dept-top"><b>' + department + '</b><strong>' + percent + '%</strong></div><div class="kp-track">' + ['done', 'scoring', 'review', 'confirm', 'submit'].map(key => '<span class="' + key + '" style="width:' + (c.total ? c[key] / c.total * 100 : 0) + '%"></span>').join('') + '</div><div class="kp-dept-foot"><span>已完成 ' + c.done + ' / ' + c.total + ' 人</span><em>待处理 ' + (c.total - c.done) + ' 人</em></div></button>';
    }).join('') + '</div><div class="kp-legend">' + [['#4b9d87', '完成'], ['#809de5', '评分'], ['#b29bc5', '复核'], ['#dcaf6f', '提交']].map(([color, label]) => '<span><i style="background:' + color + '"></i>' + label + '</span>').join('') +
      '</div><section class="kp-attention"><h3>需要关注</h3><p>' + (rows.some(p => p.attention) ? '有 ' + rows.filter(p => p.attention).length + ' 位员工需补充材料，建议在提交截止前跟进。' : '当前没有材料异常，按阶段截止时间推进考核。') + '</p>' +
      (rows.some(p => p.attention) ? textButton('查看材料异常', 'status', 'data-value="attention"') : '') + '</section></aside>';
  }
  function filters() {
    return '<form class="kp-filter" id="kp-filter"><label class="kp-search">' + icon('search') + '<input type="search" id="kp-query" aria-label="搜索考核人员" placeholder="搜索员工、岗位或主管" value="' + esc(state.query) + '"></label>' +
      '<button class="kb-btn" type="submit">查询</button><select class="kp-select" id="kp-department" aria-label="筛选部门">' + departmentOptions(state.department) + '</select>' +
      (state.page === 'history' ? '' : '<select class="kp-select" id="kp-status" aria-label="考核状态"><option value="all">全部状态</option>' + Object.entries(labels).map(([key, label]) => '<option value="' + key + '"' + (state.status === key ? ' selected' : '') + '>' + label + '</option>').join('') + '<option value="attention"' + (state.status === 'attention' ? ' selected' : '') + '>材料异常</option></select>') +
      textButton('清空筛选', 'clear') + '</form>';
  }
  function peoplePanel(history = false) {
    const c = history ? null : counts();
    return '<section class="kp-panel kp-people ' + (history ? 'kp-wide' : '') + '" aria-label="考核人员列表"><div class="kp-panel-head kp-person-head"><h2>' + (history ? '考核结果' : '人员考核进度') + '<span class="kb-count" id="kp-result-count"></span></h2><span>' + (history ? '已归档结果，只读查看' : '点击详情查看材料与处理记录') + '</span></div>' + filters() +
      (history ? '' : '<nav class="kp-tabs" aria-label="人员状态分组">' + [['all', '全部人员', c.total], ['pending', '待处理', c.total - c.done], ['done', '已完成', c.done]].map(([key, text, number]) => '<button class="' + (state.tab === key ? 'active' : '') + '" data-kp-action="tab" data-value="' + key + '">' + text + ' <span>' + number + '</span></button>').join('') + '</nav>') +
      '<div class="kp-results"></div><div class="kp-pager"></div></section>';
  }
  function emptyCycle() {
    return '<section class="kp-panel kp-wide"><div class="kp-empty">' + icon('trophy') + '<h2>准备好开启新一期考核</h2><p>' + cycleLabel(state.cycle) + '还没有发起考核。选择已发布模板，核对参评人员和阶段截止时间，再统一发起。</p><div class="kp-empty-steps"><span><b>1</b>选择部门模板</span><span><b>2</b>核对人员与日期</span><span><b>3</b>确认并发起</span></div>' +
      button(icon('plus') + '发起本期考核', 'launch', true) + '</div><p class="kp-subnote">发起后，本页会按部门和人员展示处理进度；员工提交材料后进入主管评分。</p></section>';
  }
  function templatesPage() {
    const pages = Math.ceil(templates.length / 4);
    state.templatePage = Math.min(state.templatePage, pages);
    return '<section class="kp-panel kp-wide"><div class="kp-panel-head"><h2>部门考核模板</h2><span>' + templates.filter(t => t.status === 'published').length + ' 个已发布 / ' + templates.length + ' 个模板</span></div><div class="kp-template-list">' + templates.slice((state.templatePage - 1) * 4, state.templatePage * 4).map(t =>
      '<article class="kp-template"><div class="kp-template-head">' + icon('doc') + '<span class="kp-status ' + (t.status === 'published' ? 'done' : 'submit') + '">' + (t.status === 'published' ? '已发布' : '草稿') + '</span></div><h3>' + esc(t.name) + '</h3><p>' + esc(t.department) + ' / ' + esc(t.role) + '<br>' + t.metrics.length + ' 项指标，满分 ' + t.metrics.reduce((n, m) => n + m.max, 0) + ' 分；版本 V' + t.version + '</p><div class="kp-template-footer"><span>更新于 ' + t.updated + '</span>' + textButton(t.status === 'published' ? '查看模板' : '编辑模板', 'template', 'data-id="' + t.id + '"') + '</div></article>').join('') +
      '</div>' + (pages > 1 ? '<div class="kp-pager"><span>第 ' + state.templatePage + ' / ' + pages + ' 页，共 ' + templates.length + ' 个模板</span><nav aria-label="模板分页"><button data-kp-action="template-page" data-value="' + (state.templatePage - 1) + '"' + (state.templatePage === 1 ? ' disabled' : '') + ' aria-label="模板上一页">‹</button><button data-kp-action="template-page" data-value="' + (state.templatePage + 1) + '"' + (state.templatePage === pages ? ' disabled' : '') + ' aria-label="模板下一页">›</button></nav></div>' : '') +
      '<p class="kp-subnote">已发布模板用于发起考核。修改时先复制为草稿，新版本发布后用于后续考核，已发起记录保留原规则。</p></section>';
  }
  function render() {
    cancelAnimationFrame(frame);
    resizeObserver?.disconnect();
    if (state.role !== 'admin') {
      document.title = (state.role === 'employee' ? '我的考核' : state.page === 'scoring' ? '主管评分' : '团队考核') + ' · 交互原型';
      app.innerHTML = '<div class="kp-shell">' + sidebar() + '<main class="kp-workspace' + (state.role === 'employee' || state.page === 'scoring' ? ' ks-workspace' : '') + '">' + mobileNav() + (state.role === 'employee' ? employee.pageMarkup() : manager.pageMarkup()) + '</main></div>';
      if (state.role === 'manager' && state.page === 'team') manager.renderRows();
      return;
    }
    document.title = (state.page === 'history' ? '往期考核' : state.page === 'templates' ? '考核模板管理' : 'KPI考核') + ' · 交互原型';
    app.innerHTML = '<div class="kp-shell">' + sidebar() + '<main class="kp-workspace">' + mobileNav() + header() + (state.page === 'templates' ? '' : (state.page === 'overview' ? cyclePanel() : '') + stats()) +
      '<div class="kp-board">' + (state.page === 'templates' ? templatesPage() : state.page === 'history' ? peoplePanel(true) : current().people.length ? departments() + peoplePanel() : emptyCycle()) + '</div></main></div>';
    if (document.querySelector('.kp-results')) {
      renderRows();
      resizeObserver = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(renderRows); });
      resizeObserver.observe(document.querySelector('.kp-results'));
    }
  }
  function renderRows() {
    if (state.role === 'manager') { if (state.page === 'team') manager.renderRows(); return; }
    if (state.role !== 'admin') return;
    const results = document.querySelector('.kp-results');
    if (!results) return;
    const row = parseFloat(getComputedStyle(results).getPropertyValue('--kp-row')) || 46;
    const capacity = innerWidth <= 960 ? (innerWidth <= 600 ? 6 : 10) : Math.min(10, Math.max(1, Math.floor((results.clientHeight - 38) / row)));
    if (capacity !== state.pageSize) {
      const first = (state.pageNumber - 1) * state.pageSize;
      state.pageSize = capacity;
      state.pageNumber = Math.floor(first / capacity) + 1;
    }
    const data = filtered(), pages = Math.max(1, Math.ceil(data.length / state.pageSize));
    state.pageNumber = Math.min(state.pageNumber, pages);
    const rows = data.slice((state.pageNumber - 1) * state.pageSize, state.pageNumber * state.pageSize), history = state.page === 'history';
    document.getElementById('kp-result-count').textContent = data.length + ' 人';
    results.innerHTML = data.length ? '<table class="kp-table"><thead><tr><th>员工</th><th>部门 / 岗位</th><th>' + (history ? '最终得分' : '当前状态') + '</th><th>' + (history ? '较上期' : '当前处理人') + '</th><th>' + (history ? '考核主管' : '阶段截止') + '</th><th>操作</th></tr></thead><tbody>' +
      rows.map((p, i) => '<tr data-person-id="' + p.id + '"><td><div class="kp-person"><span class="kp-avatar ' + (i % 2 ? 'alt' : '') + '">' + esc(p.name.slice(-2)) + '</span><div><strong>' + esc(p.name) + '</strong><small>' + (history ? '已归档' : p.status === 'done' ? p.score + ' 分' : '月度考核') + '</small></div></div></td><td><div class="kp-cell-ellipsis">' + p.department + '</div><small class="kp-cell-ellipsis">' + p.role + '</small></td><td>' + (history ? '<strong class="kp-score">' + p.score + '<small>/ 100</small></strong>' : statusTag(p.status) + (p.attention ? '<small class="kp-warning">' + p.attention + '</small>' : '')) + '</td><td>' +
        (history ? '<span style="color:' + (p.score >= p.previous ? '#218167' : '#a87831') + '">' + (state.history === '2026-07' ? '—' : (p.score - p.previous > 0 ? '+' : '') + (p.score - p.previous) + ' 分') + '</span>' : p.status === 'done' ? '—' : p.status === 'review' ? '陈悦' : p.status === 'scoring' ? p.manager : p.name) + '</td><td>' +
        (history ? p.manager : p.status === 'done' ? '已完成' : current().dates[{ submit: 0, scoring: 1, review: 2, confirm: current().review ? 3 : 2 }[p.status]].slice(5).replace('-', '/') + '<small>18:00 前</small>') + '</td><td>' + textButton('查看详情', 'detail', 'data-id="' + p.id + '"') + '</td></tr>').join('') + '</tbody></table>' :
        '<div class="kp-empty">' + icon('search') + '<h2>没有匹配的考核记录</h2><p>试试其他姓名、部门或状态。</p>' + button('清空筛选', 'clear') + '</div>';
    document.querySelector('.kp-pager').innerHTML = '<span>' + (data.length ? '显示 ' + ((state.pageNumber - 1) * state.pageSize + 1) + '–' + Math.min(state.pageNumber * state.pageSize, data.length) + ' 人，共 ' + data.length + ' 人' : '共 0 人') + '</span><nav aria-label="考核分页"><button data-kp-action="pagination" data-value="' + (state.pageNumber - 1) + '" aria-label="上一页"' + (state.pageNumber === 1 ? ' disabled' : '') + '>‹</button>' +
      Array.from({ length: pages }, (_, i) => '<button class="' + (state.pageNumber === i + 1 ? 'active' : '') + '" data-kp-action="pagination" data-value="' + (i + 1) + '" aria-label="第 ' + (i + 1) + ' 页"' + (state.pageNumber === i + 1 ? ' aria-current="page"' : '') + '>' + (i + 1) + '</button>').join('') + '<button data-kp-action="pagination" data-value="' + (state.pageNumber + 1) + '" aria-label="下一页"' + (state.pageNumber === pages ? ' disabled' : '') + '>›</button></nav>';
  }
  function resetFilters() { Object.assign(state, { status: 'all', department: '', query: '', tab: 'all', pageNumber: 1 }); }
  function dialog(title, body, footer, drawer = false) {
    if (!overlay.innerHTML) lastFocus = document.activeElement;
    overlay.innerHTML = '<div class="kp-dialog-mask' + (drawer ? ' kp-drawer-mask' : '') + '"><section class="kp-dialog' + (drawer ? ' kp-drawer' : '') + '" role="dialog" aria-modal="true" aria-labelledby="kp-dialog-title"><div class="kp-dialog-head"><h2 id="kp-dialog-title">' + title + '</h2><button class="kb-icon-btn" data-kp-action="close" aria-label="关闭">' + icon('close') + '</button></div><div class="kp-dialog-body">' + body + '<p class="kp-error" role="alert" id="kp-error"></p></div><div class="kp-dialog-footer">' + footer + '</div></section></div>';
    overlay.querySelector('button')?.focus();
  }
  function close() { overlay.innerHTML = ''; wizard = null; activePerson = null; activeTemplate = null; if (lastFocus?.isConnected) lastFocus.focus(); else document.querySelector('.kp-heading button')?.focus(); }
  function error(message) { document.getElementById('kp-error').textContent = message; }
  function showDetail(id) {
    const p = allRows().find(row => row.id === id);
    if (!p) return;
    activePerson = id;
    const t = p.templateSnapshot, history = state.page === 'history', editable = false;
    let allocated = 0;
    const scores = !history && p.itemScores || t.metrics.map((m, i) => {
      const score = i === t.metrics.length - 1 ? (p.score ?? 88) - allocated : Math.round(m.max * (p.score ?? 88) / 100);
      allocated += score;
      return score;
    });
    const actionText = !history && p.status === 'review' ? '复核通过' : '';
    dialog((history ? '考核档案' : '人员考核详情'),
      '<div class="kp-detail-person"><span class="kp-avatar">' + p.name.slice(-2) + '</span><div><h3>' + p.name + '</h3><p>' + p.department + ' / ' + p.role + '</p></div><div class="kp-detail-status">' + statusTag(p.status) + '</div></div>' +
      '<dl class="kp-recap"><dt>考核周期</dt><dd>' + cycleLabel(history ? state.history : state.cycle) + '</dd><dt>考核模板</dt><dd>' + esc(t.name) + ' V' + t.version + '</dd><dt>考核主管</dt><dd>' + p.manager + '</dd><dt>' + (['confirm', 'done'].includes(p.status) ? '最终得分' : '主管拟评分') + '</dt><dd>' + (p.score == null ? '待评分完成' : p.score + ' / 100 分' + (['confirm', 'done'].includes(p.status) ? '' : '（待复核或修订）')) + '</dd></dl>' +
      (p.attention ? '<p class="kp-form-note">' + p.attention + '：请补充本月成果记录，再提交主管评分。</p>' : '') +
      '<section class="kp-detail-section"><h3>考核指标与材料</h3><table class="kp-detail-table"><thead><tr><th>指标 / 数据来源</th><th>目标 / 标准</th><th>满分</th><th>得分</th></tr></thead><tbody>' + t.metrics.map((m, i) => '<tr><td>' + esc(m.name) + '<br><small style="color:var(--muted)">' + esc(m.source) + '</small></td><td>' + esc(m.target) + '</td><td>' + m.max + '</td><td>' + (editable ? '<input aria-label="' + esc(m.name) + '得分" class="kp-item-score" type="number" min="0" max="' + m.max + '" step="0.1" value="' + scores[i] + '">' : p.score == null ? '—' : scores[i]) + '</td></tr>').join('') + '</tbody></table></section>' +
      '<section class="kp-detail-section"><h3>员工提交内容</h3>' + employee.submissionMarkup(p) + '</section>' +
      (!history && p.status === 'review' ? '<section class="kp-detail-section"><label class="kp-field"><span>HR 复核意见</span><textarea id="kp-process-note" aria-label="HR复核意见" placeholder="填写复核依据和处理意见"></textarea></label></section>' : '') +
      '<section class="kp-detail-section"><h3>处理记录</h3><ol class="kp-timeline">' + (history ? [{ text: '员工已确认结果，考核归档', at: (state.history === '2026-08' ? '2026-09-08' : '2026-08-08') + ' 16:30' }] : [...p.log].reverse()).map(item => '<li>' + esc(item.text) + '<small>' + esc(item.at) + '</small></li>').join('') + '</ol></section>',
      '<small>' + (history || p.status === 'done' ? '结果已归档，按本期规则保留。' : '管理员查看全局进度，HR 处理复核。') + '</small><div class="kp-actions">' + button('关闭', 'close') + (!history && p.status === 'review' ? button('退回主管', 'return-score') : '') + (actionText ? button(actionText, 'process', true) : '') + '</div>', true);
  }
  function processPerson() {
    const p = current().people.find(p => p.id === activePerson);
    if (state.role !== 'admin' || !p || p.status !== 'review') return;
    const note = document.getElementById('kp-process-note').value.trim();
    if (!note) return error('请填写工作说明或处理依据。');
    p.status = 'confirm';
    p.attention = '';
    p.log.push({ text: 'HR 复核通过：' + note, at: '刚刚（本地演示）' });
    render();
    showDetail(p.id);
    notify('处理完成，已进入' + labels[p.status] + '。');
  }
  function startLaunch() {
    if (current().people.length) {
      state.cycle = '2026-10';
      resetFilters();
      render();
      if (current().people.length) return notify('10月考核已经发起，请在人员列表中处理。');
    }
    wizard = { step: 1, departmentIds: [0, 1, 2, 3], personIds: people.map(p => p.id), templateIds: deptNames.map(d => [...templates].reverse().find(t => t.department === d && t.status === 'published').id), dates: [...current().dates], review: true };
    launchDialog();
  }
  function launchDialog() {
    const w = wizard, selected = w.departmentIds.map(i => deptNames[i]), chosen = people.filter(p => w.personIds.includes(p.id) && selected.includes(p.department));
    let body = '<div class="kp-wizard-steps">' + ['1 选择模板与人员', '2 配置截止时间', '3 核对并发起'].map((label, i) => '<span class="' + (w.step === i + 1 ? 'active' : '') + '">' + label + '</span>').join('') + '</div>';
    if (w.step === 1) {
      body += '<p class="kp-form-note">考核周期：' + cycleLabel(state.cycle) + '。按已发布模板匹配正式员工；可以展开部门核对和调整人员名单。</p><div class="kp-scope-pick">' +
        deptNames.map((d, i) => '<section class="kp-scope"><label class="kp-check"><input type="checkbox" class="kp-scope-check" value="' + i + '"' + (w.departmentIds.includes(i) ? ' checked' : '') + '><span><b>' + d + '</b><small>已发布模板 / 月度考核</small></span></label><select class="kp-select kp-launch-template" style="width:100%;margin-top:10px" aria-label="' + d + '考核模板">' + templates.filter(t => t.department === d && t.status === 'published').map(t => '<option value="' + t.id + '"' + (w.templateIds[i] === t.id ? ' selected' : '') + '>' + esc(t.name) + ' V' + t.version + '</option>').join('') + '</select><details style="margin-top:12px"><summary style="font-size:11px;color:var(--blue);cursor:pointer">核对 6 位参评人员</summary><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px">' +
          people.filter(p => p.department === d).map(p => '<label class="kp-check"><input type="checkbox" class="kp-person-check" value="' + p.id + '"' + (w.personIds.includes(p.id) ? ' checked' : '') + '>' + p.name + '</label>').join('') + '</div></details></section>').join('') + '</div>';
    } else if (w.step === 2) {
      body += '<p class="kp-form-note">已选择 ' + selected.length + ' 个部门、' + chosen.length + ' 位员工。截止时间须在考核月结束后，并按提交、评分、复核、确认依次排列。</p><div class="kp-form-grid">' +
        ['员工提交截止', '主管评分截止', 'HR 复核截止', '员工确认截止'].map((label, i) => '<label class="kp-field"><span>' + label + (i === 2 ? '（启用复核时必填）' : '') + '</span><input type="date" class="kp-date" aria-label="' + label + '" value="' + w.dates[i] + '"></label>').join('') + '</div><label class="kp-check" style="margin-top:18px"><input type="checkbox" id="kp-review"' + (w.review ? ' checked' : '') + '>主管评分后，由 HR 复核再交员工确认</label>';
    } else {
      body += '<dl class="kp-recap"><dt>考核周期</dt><dd>' + cycleLabel(state.cycle) + '</dd><dt>发起范围</dt><dd>' + selected.join('、') + '</dd><dt>参评人数</dt><dd><strong>' + chosen.length + ' 人</strong>，' + selected.length + ' 个部门</dd><dt>考核模板</dt><dd>' + w.departmentIds.map(i => { const t = templates.find(t => t.id === w.templateIds[i]); return esc(t.name) + ' V' + t.version; }).join('<br>') + '</dd><dt>阶段截止</dt><dd>提交 ' + w.dates[0] + '，评分 ' + w.dates[1] + '<br>' + (w.review ? '复核 ' + w.dates[2] + '，' : '') + '确认 ' + w.dates[3] + '，均为 18:00</dd><dt>审批流程</dt><dd>员工提交 → 主管评分 → ' + (w.review ? 'HR 复核 → ' : '') + '员工确认</dd></dl><p class="kp-form-note">发起后固定本期模板版本和人员范围。此原型只生成本地示例考核，不发送实际通知。</p><label class="kp-check"><input type="checkbox" id="kp-launch-confirm">我已核对人员、模板和截止时间</label>';
    }
    dialog('发起 ' + cycleLabel(state.cycle) + '考核', body, '<small>第 ' + w.step + ' 步，共 3 步</small><div class="kp-actions">' + button(w.step === 1 ? '取消' : '上一步', w.step === 1 ? 'close' : 'launch-back') + button(w.step === 3 ? '确认发起' : '下一步', w.step === 3 ? 'launch-confirm' : 'launch-next', true) + '</div>');
  }
  function launchNext() {
    if (wizard.step === 1) {
      wizard.departmentIds = [...overlay.querySelectorAll('.kp-scope-check:checked')].map(n => Number(n.value));
      wizard.personIds = [...overlay.querySelectorAll('.kp-person-check:checked')].map(n => n.value);
      wizard.templateIds = [...overlay.querySelectorAll('.kp-launch-template')].map(n => n.value);
      if (!wizard.departmentIds.length) return error('至少选择一个已发布的部门模板。');
      if (wizard.departmentIds.some(i => !people.some(p => p.department === deptNames[i] && wizard.personIds.includes(p.id)))) return error('每个选中部门至少选择一位参评员工。');
    } else {
      const dates = [...overlay.querySelectorAll('.kp-date')].map(n => n.value), review = document.getElementById('kp-review').checked;
      const ordered = review ? dates : [dates[0], dates[1], dates[3]];
      if (ordered.some(d => !/^\d{4}-\d{2}-\d{2}$/.test(d) || d <= state.cycle + '-31') || ordered.some((d, i) => i && d < ordered[i - 1])) return error('请填写考核月结束后的有效日期，并按阶段顺序排列。');
      wizard.dates = dates;
      wizard.review = review;
    }
    wizard.step++;
    launchDialog();
  }
  function confirmLaunch() {
    if (!document.getElementById('kp-launch-confirm').checked) return error('请先勾选核对确认，再发起考核。');
    if (current().people.length) return error('本周期已发起，请勿重复操作。');
    current().people = people.filter(p => wizard.personIds.includes(p.id) && wizard.departmentIds.includes(deptNames.indexOf(p.department))).map(p => {
      const t = templates.find(t => t.id === wizard.templateIds[deptNames.indexOf(p.department)]);
      return { ...p, templateId: t.id, templateSnapshot: structuredClone(t), status: 'submit', score: null, itemScores: null, submission: null, managerDraft: null, returnInfo: null, hrReturnInfo: null, attention: '', log: [{ text: '考核已发起，等待员工提交材料', at: '刚刚（本地演示）' }] };
    });
    current().dates = wizard.review ? [...wizard.dates] : [wizard.dates[0], wizard.dates[1], wizard.dates[3]];
    current().review = wizard.review;
    const count = current().people.length;
    close();
    resetFilters();
    render();
    notify('已发起 ' + cycleLabel(state.cycle) + '考核，覆盖 ' + count + ' 位员工（本地演示）。');
  }
  function templateDialog(id) {
    const t = templates.find(t => t.id === id);
    if (!t) return;
    activeTemplate = id;
    const editable = t.status === 'draft';
    dialog(editable ? '编辑考核模板' : '考核模板详情',
      '<div class="kp-template-preview"><span>' + esc(t.department) + ' / ' + esc(t.role) + '</span><span>月度考核</span><span>版本 V' + t.version + '</span><span>' + (editable ? '草稿' : '已发布') + '</span></div>' +
      (editable ? '<label class="kp-field"><span>模板名称</span><input id="kp-template-name" value="' + esc(t.name) + '" maxlength="60"></label>' : '<h3 style="font-size:17px;margin-bottom:16px">' + esc(t.name) + '</h3>') +
      '<section class="kp-detail-section"><h3>指标与权重</h3><table class="kp-detail-table"><thead><tr><th>考核指标</th><th>目标与标准</th><th>满分 / 权重</th></tr></thead><tbody>' + t.metrics.map(m => '<tr><td>' + esc(m.name) + '</td><td>' + esc(m.target) + '<br><small style="color:var(--muted)">' + esc(m.source) + '</small></td><td>' + (editable ? '<input class="kp-weight" type="number" min="1" max="100" value="' + m.max + '" aria-label="' + esc(m.name) + '权重">' : m.max + ' 分 / ' + m.max + '%') + '</td></tr>').join('') + '</tbody></table></section><p class="kp-form-note" style="margin-top:20px">各项满分合计须为 100 分。发布后用于后续发起的考核；本期记录保留已使用的模板版本。</p>',
      '<small>' + (editable ? '核对指标和权重后发布。' : '已发布模板通过复制草稿调整。') + '</small><div class="kp-actions">' + button('关闭', 'close') + (editable ? button('保存草稿', 'save-template') + button('发布模板', 'publish-template', true) : button('复制为草稿', 'copy-template', true)) + '</div>');
  }
  function newTemplate() {
    dialog('新建考核模板', '<p class="kp-form-note">先选择适用部门，以该部门当前指标作为初始规则，再调整权重。</p><div class="kp-form-grid"><label class="kp-field wide"><span>模板名称</span><input id="kp-new-template-name" maxlength="60" placeholder="例如：市场业务月度考核"></label><label class="kp-field wide"><span>适用部门</span><select id="kp-new-template-department">' + deptNames.map((d, i) => '<option value="' + i + '">' + d + ' / ' + roles[i] + '</option>').join('') + '</select></label></div>', '<small>新建模板先保存为草稿。</small><div class="kp-actions">' + button('取消', 'close') + button('创建并配置', 'create-template', true) + '</div>');
  }
  function saveTemplate(publish) {
    const t = templates.find(t => t.id === activeTemplate), name = document.getElementById('kp-template-name').value.trim();
    const inputs = [...overlay.querySelectorAll('.kp-weight')], weights = inputs.map(n => Number(n.value));
    if (!name) return error('请填写模板名称。');
    if (inputs.some(n => !n.value.trim()) || weights.some(n => !Number.isFinite(n) || n <= 0 || n > 100) || weights.reduce((a, b) => a + b, 0) !== 100) return error('每项权重需大于 0，全部权重合计须为 100。');
    t.name = name;
    t.metrics.forEach((m, i) => m.max = weights[i]);
    t.updated = '2026-09-30';
    if (publish) t.status = 'published';
    close();
    render();
    notify(publish ? '模板已发布，可用于后续考核。' : '模板草稿已保存。');
  }
  function exportResults() {
    const rows = filtered();
    const cell = value => '"' + String(value).replace(/"/g, '""') + '"';
    const csv = '\uFEFF' + [['考核周期', '员工', '部门', '岗位', '主管', '得分'], ...rows.map(p => [cycleLabel(state.history), p.name, p.department, p.role, p.manager, p.score])].map(row => row.map(cell).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = '考核结果-' + state.history + '.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify('已导出当前筛选范围，共 ' + rows.length + ' 人。');
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-kp-action]');
    if (!trigger || trigger.disabled) return;
    const action = trigger.dataset.kpAction, value = trigger.dataset.value;
    if (action === 'outside') return notify('此处展示 KPI 与知识库原型，可从左侧切换。');
    if (action === 'page') {
      if (!allowedPages[state.role].includes(value)) return notify('当前视角没有该页面入口，请通过原型体验身份切换。');
      state.page = value; resetFilters(); close(); render();
    }
    else if (action === 'admin-view') switchRole('admin');
    else if (action === 'return-score') {
      const p = current().people.find(p => p.id === activePerson);
      if (state.role !== 'admin' || p?.status !== 'review') return;
      dialog('退回主管修订评分', '<label class="kp-field"><span>退回评分原因</span><textarea id="kp-return-score" aria-label="退回评分原因" placeholder="具体指出评分依据或分值需要调整的地方"></textarea></label>', '<small>保留原评分，交主管重新核对。</small><div class="kp-actions">' + button('取消', 'close') + button('确认退回评分', 'confirm-return-score', true) + '</div>');
    }
    else if (action === 'confirm-return-score') {
      const p = current().people.find(p => p.id === activePerson), note = document.getElementById('kp-return-score')?.value.trim();
      if (state.role !== 'admin' || p?.status !== 'review') return;
      if (!note) return error('请填写具体退回评分原因。');
      p.status = 'scoring'; p.hrReturnInfo = note;
      p.managerDraft = { scores: p.itemScores?.map(String) || p.templateSnapshot.metrics.map(() => ''), note: p.scoreNote || '', checked: false };
      p.log.push({ text: 'HR 退回主管评分：' + note, at: '刚刚（本地演示）' });
      render(); showDetail(p.id); notify('已退回主管修订，原评分保留。');
    }
    else if (action === 'status') { state.status = value; state.tab = 'all'; state.pageNumber = 1; render(); }
    else if (action === 'department') { state.department = value; state.pageNumber = 1; render(); }
    else if (action === 'clear-department') { state.department = ''; state.pageNumber = 1; render(); }
    else if (action === 'clear') { resetFilters(); render(); }
    else if (action === 'tab') { state.tab = value; state.status = 'all'; state.pageNumber = 1; render(); }
    else if (action === 'pagination') { state.pageNumber = Number(value); renderRows(); }
    else if (action === 'detail') showDetail(trigger.dataset.id);
    else if (action === 'close') close();
    else if (action === 'process') processPerson();
    else if (action === 'launch') startLaunch();
    else if (action === 'launch-next') launchNext();
    else if (action === 'launch-back') { wizard.step--; launchDialog(); }
    else if (action === 'launch-confirm') confirmLaunch();
    else if (action === 'template') templateDialog(trigger.dataset.id);
    else if (action === 'template-page') { state.templatePage = Number(value); render(); }
    else if (action === 'new-template') newTemplate();
    else if (action === 'create-template') {
      const name = document.getElementById('kp-new-template-name').value.trim();
      if (!name) return error('请填写模板名称。');
      const base = templates[Number(document.getElementById('kp-new-template-department').value)];
      const t = { ...structuredClone(base), id: 'custom-' + templates.length, name, version: 1, status: 'draft', updated: '2026-09-30' };
      templates.push(t); state.templatePage = Math.ceil(templates.length / 4); render(); templateDialog(t.id);
    } else if (action === 'copy-template') {
      const base = templates.find(t => t.id === activeTemplate);
      const t = { ...structuredClone(base), id: 'custom-' + templates.length, name: base.name + '（修订）', version: base.version + 1, status: 'draft', updated: '2026-09-30' };
      templates.push(t); state.templatePage = Math.ceil(templates.length / 4); render(); templateDialog(t.id);
    } else if (action === 'save-template') saveTemplate(false);
    else if (action === 'publish-template') saveTemplate(true);
    else if (action === 'export') exportResults();
  });
  document.addEventListener('submit', event => {
    if (event.target.id !== 'kp-filter') return;
    event.preventDefault();
    state.query = document.getElementById('kp-query').value.trim();
    state.pageNumber = 1;
    renderRows();
  });
  document.addEventListener('change', event => {
    const id = event.target.id;
    if (id === 'kp-role') { switchRole(event.target.value); return; }
    if (id === 'kp-cycle') { state.cycle = event.target.value; resetFilters(); render(); }
    if (id === 'kp-history') { state.history = event.target.value; resetFilters(); render(); }
    if (id === 'kp-department') { state.department = event.target.value; state.pageNumber = 1; render(); }
    if (id === 'kp-status') { state.status = event.target.value; state.tab = 'all'; state.pageNumber = 1; render(); }
  });
  document.addEventListener('keydown', event => {
    const modal = overlay.querySelector('[role="dialog"]');
    if (!modal) return;
    if (event.key === 'Escape') return close();
    if (event.key !== 'Tab') return;
    const fields = [...modal.querySelectorAll('button,input,select,textarea,summary,a[href]')].filter(node => !node.disabled && node.getClientRects().length);
    const first = fields[0], last = fields[fields.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  function switchRole(role) {
    if (!allowedPages[role]) return;
    close();
    state.role = role; state.page = allowedPages[role][0];
    resetFilters(); render();
  }
  employee = globalThis.createKpiEmployee({
    state, current, getPerson: getEmployee, esc, icon, button, notify, render, dialog, close, showDetail, rolePicker,
    getActivePerson: () => state.role === 'manager' ? manager.selected() : current().people.find(p => p.id === activePerson),
    afterReturn: p => {
      if (state.role === 'manager') { close(); state.page = 'team'; state.teamTab = 'all'; render(); }
      else { render(); showDetail(p.id); }
    }
  });
  employee.seedSamples();
  manager = globalThis.createKpiManager({ state, current, esc, icon, button, notify, render, dialog, close, rolePicker, employee });
  render();
})();
