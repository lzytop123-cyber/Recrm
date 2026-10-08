'use strict';
// Local interaction prototype. Synthetic documents; no API or external service calls.
(() => {
  const icons = {
    folder: '<path d="M3 7h7l2-3h8a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/>',
    doc: '<path d="M7 3h7l4 4v14H7Z"/><path d="M14 3v5h4M10 12h5M10 16h5"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    sync: '<path d="M20 9a8 8 0 0 0-14-3L3 9m0-5v5h5M4 15a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    chevron: '<path d="m9 6 6 6-6 6"/>',
    book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15"/>',
    building: '<path d="M5 21V5h14v16M3 21h18M9 8h1M14 8h1M9 12h1M14 12h1M10 21v-5h4v5"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    bell: '<path d="M6 16V9a6 6 0 0 1 12 0v7l2 2H4Zm4 5h4"/>',
    chart: '<path d="M4 20h16M6 16V9M12 16V4M18 16v-5"/>',
    paperclip: '<path d="m8 12 6-6a3 3 0 0 1 4 4L9 19a5 5 0 0 1-7-7l9-9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-5 5-5 13 0 18 5-5 5-13 0-18Z"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 4v2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="m10 3-1 3-3 1-3-1-1 4 2 2-1 3 3 3 3-1 3 1 2-2 4-1 1-4-3-2 1-3-3-3-3 1Z"/>',
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.doc}</svg>`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const catalogs = ['合规知识', '销售方法与产品', '项目交付规范', '新媒体运营', '制度与流程'];
  const examples = [
    ['审批流程与权限确认清单', 0, '发起审批前，确认申请内容、审批人员与适用权限。按清单逐项检查，减少反复退回。', '审批,权限,流程'],
    ['客户需求访谈：从问题到方案', 1, '通过业务目标、现有流程与关键约束三个维度识别客户需求，记录问题优先级和下一步行动。', '销售,需求,访谈'],
    ['项目交付前的验收检查清单', 2, '核对交付范围、质量标准、资料完整性和客户确认。交付前完成责任人签字与异常处理。', '项目,验收,清单'],
    ['合同签署与资料归档规范', 0, '签署前核实主体、金额和履约条款，签署后按项目编号归档，确保资料可查、版本可追溯。', '合同,归档,合规'],
    ['产品演示中的常见问题与回答', 1, '围绕功能边界、数据权限和实施周期准备演示。结合客户场景说明能力，避免过度承诺。', '产品,演示,答疑'],
    ['新媒体内容发布审核流程', 3, '明确内容负责人、审核范围和发布时间。涉及客户信息、产品承诺的内容须完成发布前审核。', '内容,发布,审核'],
    ['员工入职与账号开通指南', 4, '完成入职资料核对后，按岗位配置账号和权限。首日确认设备、系统访问与培训安排。', '入职,账号,权限'],
    ['制造业数字化项目交付复盘', 2, '记录需求确认、资源协调、上线验收中的关键决策，沉淀可复用的交付方法和改进项。', '案例,制造业,复盘'],
    ['客户数据处理与保密要求', 0, '按最小必要原则采集与使用客户数据，明确访问范围、保存期限和信息共享要求。', '数据,保密,合规'],
    ['销售跟进记录填写示例', 1, '记录客户反馈、需求变化、推进障碍和下一步计划。使用事实与明确日期，便于团队协作。', '销售,跟进,记录'],
    ['项目变更申请与评估方法', 2, '变更前评估范围、成本、周期与风险，取得相关人员确认后更新项目基线与交付计划。', '项目,变更,评估'],
    ['短视频选题与脚本撰写规范', 3, '从受众问题和内容目标确定选题，用场景、信息和行动引导组织脚本。拍摄前检查事实与措辞。', '视频,脚本,选题'],
    ['差旅申请与费用报销指引', 4, '出差前提交行程、预算和事由，报销时核对票据、审批记录与费用归属。', '差旅,报销,制度'],
    ['采购供应商准入检查表', 0, '核查供应商资质、服务能力和履约记录，完成利益冲突申报后进入采购评估。', '采购,供应商,准入'],
    ['客户异议处理与沟通建议', 1, '先确认客户顾虑，再补充事实与适用条件。对不能确认的问题记录并安排后续答复。', '异议,沟通,客户'],
    ['项目上线准备与回滚检查', 2, '上线前确认数据备份、权限配置、监控和回滚方案，按职责完成检查并安排上线值守。', '上线,回滚,检查'],
    ['企业账号内容发布规范', 3, '统一品牌表达、素材授权与发布节奏，发布后及时处理评论、咨询与内容纠错。', '账号,发布,品牌'],
    ['考勤异常与请假办理说明', 4, '出现考勤异常时说明原因并补充凭证，请假按时提交并完成工作交接。', '考勤,请假,人事'],
    ['对外合作中的信息披露边界', 0, '对外共享资料前确认披露范围与审批要求。未获授权的信息不得向合作方提供。', '合作,披露,合规'],
    ['售前方案编写与评审要点', 1, '明确项目目标、实施范围、交付成果和验收标准，评审时核对技术与商务边界。', '售前,方案,评审'],
    ['项目周报与风险升级规则', 2, '周报呈现进展、风险和需要协调的事项。高风险问题明确负责人、处置期限与升级路径。', '周报,风险,项目'],
    ['会议纪要与行动项模板', 4, '会议结束后记录决定、行动项、负责人和截止日期，定期回顾执行进展。', '会议,行动项,模板'],
  ];
  let documents = examples.map(([title, catalog, summary, keywords], i) => ({
    id: i + 1, title, catalog: catalogs[catalog], summary, keywords,
    status: i % 2 === 0 ? 'published' : 'pending_review', source: i % 3 === 0 ? '飞书文档' : '手动创建',
    author: ['人事行政部', '销售团队', '项目交付组'][i % 3],
    updated: `2026-09-${String(30 - Math.floor(i / 3)).padStart(2, '0')} ${String(17 - i % 3).padStart(2, '0')}:30`,
    attachments: i === 0 ? ['审批权限确认清单.pdf'] : i === 2 ? ['项目验收清单.xlsx', '交付说明.pdf'] : [],
    content: `${summary}\n\n适用范围\n供相关业务团队在日常办理与协作中参考。涉及特殊情况时，请与对应负责人确认后再执行。\n\n办理步骤\n1. 核对当前事项及适用条件，准备相关资料。\n2. 按制度要求确认负责人、处理顺序与完成时间。\n3. 对异常情况记录原因，及时协调并保留处理依据。\n4. 完成后核对结果，将资料归档到对应项目或事项。\n\n常见问题\n资料不完整时，应先补齐并重新核对；流程或权限发生变化时，以最新发布版本为准。`,
  }));
  const state = { tab: 'documents', catalog: '全部文档', query: '', status: 'all', sort: 'recent', view: 'list', page: 1, pageSize: 8, dirQuery: '', dirPage: 1, dirPageSize: 8, lastSync: '今天 11:28' };
  const app = document.getElementById('app');
  const overlay = document.getElementById('overlay');
  const mobile = matchMedia('(max-width: 700px)');
  let returnFocus;
  let modalDocumentId = null;
  let noticeTimer;
  let layoutObserver;
  let layoutFrame;
  const pendingCount = () => documents.filter(doc => doc.status === 'pending_review').length;
  const statusNames = { published: '已发布', pending_review: '待审核', draft: '草稿' };
  const statusTag = doc => `<span class="kb-status ${doc.status}">${doc.status === 'published' ? '<span class="kb-dot"></span>' : ''}${statusNames[doc.status]}</span>`;
  function filtered() {
    const query = state.query.trim().toLowerCase();
    return documents.filter(doc => (state.catalog === '全部文档' || doc.catalog === state.catalog)
      && (state.tab !== 'audit' || doc.status === 'pending_review')
      && (state.status === 'all' || doc.status === state.status)
      && (!query || [doc.title, doc.keywords, doc.content].some(value => value.toLowerCase().includes(query))))
      .sort((a, b) => state.sort === 'title' ? a.title.localeCompare(b.title, 'zh-CN') : b.updated.localeCompare(a.updated) || b.id - a.id);
  }
  function showNotice(message) {
    const notice = document.getElementById('notice');
    notice.textContent = message;
    notice.classList.add('show');
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => notice.classList.remove('show'), 3400);
  }
  function catalogButtons() {
    const filteredCatalogs = ['全部文档', ...catalogs].filter(name => name === '全部文档' || name.includes(state.dirQuery.trim()));
    return filteredCatalogs.slice((state.dirPage - 1) * state.dirPageSize, state.dirPage * state.dirPageSize).map(name => `<button class="kb-dir ${state.catalog === name ? 'active' : ''}" title="${esc(name)}" data-kb-action="catalog" data-value="${esc(name)}" aria-pressed="${state.catalog === name}">${icon(name === '全部文档' ? 'doc' : 'folder')}<span>${esc(name)}</span><span class="kb-count">${documents.filter(doc => name === '全部文档' || doc.catalog === name).length}</span></button>`).join('');
  }
  function renderDirectory(ensureActive = false) {
    const list = document.querySelector('.kb-dir-list');
    if (!list) return;
    const names = ['全部文档', ...catalogs].filter(name => name === '全部文档' || name.includes(state.dirQuery.trim()));
    if (!mobile.matches) state.dirPageSize = Math.max(1, Math.floor((list.clientHeight + 4) / 42));
    if (ensureActive && names.includes(state.catalog)) state.dirPage = Math.floor(names.indexOf(state.catalog) / state.dirPageSize) + 1;
    const pages = Math.max(1, Math.ceil(names.length / state.dirPageSize));
    state.dirPage = Math.min(state.dirPage, pages);
    list.innerHTML = catalogButtons();
    document.querySelector('.kb-directory-pager').innerHTML = pages > 1 ? `<button class="kb-icon-btn" data-kb-action="dir-page" data-value="${state.dirPage - 1}" aria-label="上一组目录" ${state.dirPage === 1 ? 'disabled' : ''}>‹</button><span>${state.dirPage} / ${pages}</span><button class="kb-icon-btn" data-kb-action="dir-page" data-value="${state.dirPage + 1}" aria-label="下一组目录" ${state.dirPage === pages ? 'disabled' : ''}>›</button>` : '';
  }
  function setupDirectory() {
    const directory = document.querySelector('.kb-directory');
    directory.querySelector('.kb-dir-list').insertAdjacentHTML('afterend', '<div class="kb-directory-pager"></div>');
    directory.insertAdjacentHTML('afterbegin', `<div class="kb-directory-mobile"><select aria-label="选择知识目录">${['全部文档', ...catalogs].map(name => `<option value="${esc(name)}" ${name === state.catalog ? 'selected' : ''}>${esc(name)}（${documents.filter(doc => name === '全部文档' || doc.catalog === name).length}）</option>`).join('')}</select><button class="kb-icon-btn" data-kb-action="add-catalog" aria-label="新建目录">${icon('plus')}</button></div>`);
    renderDirectory(true);
  }
  function fitPageSize() {
    const results = document.querySelector('.kb-results');
    const style = getComputedStyle(results);
    const cards = state.view === 'cards' || mobile.matches;
    const row = parseFloat(style.getPropertyValue(cards ? '--kb-card-row' : '--kb-list-row')) || (cards ? 176 : 44);
    const gap = cards && !mobile.matches ? 12 : 0;
    const columns = cards ? Number(style.getPropertyValue('--kb-card-columns')) || 2 : 1;
    const height = results.clientHeight - (cards ? 0 : 38) - 2;
    const availableRows = Math.max(1, Math.floor((height + gap) / (row + gap))) * columns;
    const capacity = cards ? availableRows : Math.min(10, availableRows);
    if (capacity !== state.pageSize) {
      const firstIndex = (state.page - 1) * state.pageSize;
      state.pageSize = capacity;
      state.page = Math.floor(firstIndex / capacity) + 1;
    }
  }
  function pageNumbers(total) {
    const visible = new Set([1, total, state.page - 1, state.page, state.page + 1]);
    if (state.page === 1) visible.add(2);
    return [...visible].filter(page => page >= 1 && page <= total).sort((a, b) => a - b).map((page, index, pages) =>
      `${index && page - pages[index - 1] > 1 ? '<span class="kb-page-gap">…</span>' : ''}<button class="${state.page === page ? 'current' : ''}" data-kb-action="page" data-value="${page}" ${state.page === page ? 'aria-current="page"' : ''} aria-label="第 ${page} 页">${page}</button>`).join('');
  }
  function rowActions(doc) {
    if (state.tab === 'audit') return `<div class="kb-row-actions"><button class="kb-read" data-kb-action="read" data-id="${doc.id}">审核</button></div>`;
    return `<div class="kb-row-actions"><button class="kb-read" data-kb-action="read" data-id="${doc.id}">阅读</button>${doc.status === 'pending_review' ? '' : `<details class="kb-more"><summary aria-label="${esc(doc.title)}的更多操作">⋯</summary><div class="kb-menu"><button data-kb-action="edit" data-id="${doc.id}">编辑文档</button>${doc.status === 'draft' ? `<button data-kb-action="submit" data-id="${doc.id}">提交审核</button>` : ''}<button class="danger" data-kb-action="delete" data-id="${doc.id}">删除文档</button></div></details>`}</div>`;
  }
  function docMeta(doc) {
    return `<div class="kb-doc-meta"><span class="kb-source">${icon(doc.source === '飞书文档' ? 'globe' : 'doc')}${doc.source}</span><span>${esc(doc.author)}</span>${doc.attachments.length ? `<span class="kb-source">${icon('paperclip')}${doc.attachments.length} 个附件</span>` : ''}</div>`;
  }
  function renderResults() {
    const results = filtered();
    const activeFilters = state.query.trim() || state.status !== 'all';
    document.querySelector('.kb-filter-summary').innerHTML = `<span>${activeFilters ? `筛选结果：${results.length} 篇文档` : state.tab === 'audit' ? '审核通过后，文档将对团队发布' : '点击标题阅读文档，查看来源和附件'}</span>${activeFilters ? '<button data-kb-action="reset">清除筛选</button>' : ''}`;
    document.querySelector('[data-kb-result-count]').textContent = results.length + ' 篇';
    fitPageSize();
    return renderPage(results, activeFilters);
  }
  function renderPage(results, activeFilters) {
    const pages = Math.max(1, Math.ceil(results.length / state.pageSize));
    state.page = Math.min(state.page, pages);
    const rows = results.slice((state.page - 1) * state.pageSize, state.page * state.pageSize);
    let html;
    if (!rows.length) {
      html = `<div class="kb-empty">${icon('search')}<h3>${activeFilters ? '没有找到匹配的文档' : state.tab === 'audit' ? '待审核文档已全部处理' : '这个目录还没有文档'}</h3><p>${activeFilters ? '尝试其他关键词，或清除筛选条件。' : '新建文档或同步飞书，将团队经验整理在这里。'}</p><button class="kb-btn" data-kb-action="${activeFilters ? 'reset' : 'create'}">${activeFilters ? '清除筛选' : '新建文档'}</button></div>`;
    } else if (state.view === 'cards' || mobile.matches) {
      html = `<div class="kb-cards">${rows.map(doc => `<article class="kb-card" data-document-id="${doc.id}"><div class="kb-card-top">${statusTag(doc)}<span>${esc(doc.catalog)}</span></div><button class="kb-doc-title" data-kb-action="read" data-id="${doc.id}">${esc(doc.title)}</button><p class="kb-excerpt">${esc(doc.summary)}</p>${docMeta(doc)}<div class="kb-card-foot"><span>${doc.updated.slice(0, 10)}</span>${rowActions(doc)}</div></article>`).join('')}</div>`;
    } else {
      html = `<div class="kb-table-wrap"><table class="kb-table"><thead><tr><th class="kb-title-col">文档</th><th class="kb-catalog-col">所属目录</th><th>状态</th><th class="kb-time-col">更新时间</th><th>操作</th></tr></thead><tbody>${rows.map(doc => `<tr data-document-id="${doc.id}"><td><div class="kb-doc-main"><span class="kb-doc-icon">${icon('doc')}</span><div class="kb-doc-content"><button class="kb-doc-title" data-kb-action="read" data-id="${doc.id}">${esc(doc.title)}</button><p class="kb-excerpt">${esc(doc.summary)}</p>${docMeta(doc)}</div></div></td><td class="kb-catalog-col">${esc(doc.catalog)}</td><td>${statusTag(doc)}</td><td class="kb-updated">${doc.updated.slice(0, 10)}<small>${doc.updated.slice(11)}</small></td><td>${rowActions(doc)}</td></tr>`).join('')}</tbody></table></div>`;
    }
    document.querySelector('.kb-results').innerHTML = html;
    document.querySelector('.kb-pagination').innerHTML = `<div class="kb-pager"><span>${results.length ? `显示 ${(state.page - 1) * state.pageSize + 1}–${Math.min(state.page * state.pageSize, results.length)} 篇，共 ${results.length} 篇` : '共 0 篇文档'}</span><nav class="kb-pages" aria-label="文档分页"><button data-kb-action="page" data-value="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''} aria-label="上一页">‹</button>${pageNumbers(pages)}<button data-kb-action="page" data-value="${state.page + 1}" ${state.page === pages ? 'disabled' : ''} aria-label="下一页">›</button></nav></div>`;
  }
  function render() {
    const menu = [['经营总览', 'chart'], ['我的待办', 'bell'], ['审批中心', 'check'], ['销售中心', 'users'], ['合同回款', 'doc'], ['项目管理', 'folder'], ['协作工单', 'doc'], ['排期会议', 'calendar']];
    app.innerHTML = `<div class="kb-shell"><aside class="kb-sidebar"><div class="kb-brand"><span class="kb-brand-mark">鼎</span><div><small>经营管理平台</small><strong>中泰旭鼎 CRM</strong></div></div><nav class="kb-global-nav" aria-label="主导航">${menu.map(([label, name]) => `<button class="kb-nav-item" data-kb-action="unavailable">${icon(name)}${label}</button>`).join('')}<a class="kb-nav-item" href="frontend.html?view=kpi">${icon('chart')}KPI 考核</a><button class="kb-nav-item group" data-kb-action="tab" data-value="documents">${icon('book')}知识库</button><button class="kb-nav-item child ${state.tab === 'documents' ? 'current' : ''}" data-kb-action="tab" data-value="documents">企业知识库</button><button class="kb-nav-item child ${state.tab === 'audit' ? 'current' : ''}" data-kb-action="tab" data-value="audit">知识库审核<span class="kb-count pending">${pendingCount()}</span></button><button class="kb-nav-item" data-kb-action="unavailable">${icon('users')}员工管理</button><button class="kb-nav-item" data-kb-action="unavailable">${icon('settings')}系统设置</button></nav><div class="kb-account"><span class="kb-avatar">林</span><div><strong>林嘉宁</strong><small>知识库管理员</small></div></div></aside><main class="kb-workspace"><div class="kb-mobile-bar"><span>中泰旭鼎 CRM</span><a href="frontend.html?view=kpi">KPI 原型</a></div><div class="kb-topline"><span>知识库 ${icon('chevron')} ${state.tab === 'audit' ? '审核管理' : '文档中心'}</span><span class="kb-demo">交互原型 / 示例数据</span></div><header class="kb-heading"><div><h1>企业知识库</h1><p>让经验可查，让协作有据。集中管理团队文档、业务规范与项目经验。</p></div><div class="kb-head-actions"><button class="kb-btn" data-kb-action="sync">${icon('sync')}同步飞书</button><button class="kb-btn primary" data-kb-action="create">${icon('plus')}新建文档</button></div></header><nav class="kb-tabs" aria-label="知识库页面"><button class="${state.tab === 'documents' ? 'active' : ''}" aria-current="${state.tab === 'documents' ? 'page' : 'false'}" data-kb-action="tab" data-value="documents">文档中心</button><button class="${state.tab === 'audit' ? 'active' : ''}" aria-current="${state.tab === 'audit' ? 'page' : 'false'}" data-kb-action="tab" data-value="audit">审核管理<span class="kb-count pending">${pendingCount()}</span></button></nav><div class="kb-content"><aside class="kb-directory"><div class="kb-directory-head"><h2>${icon('folder')}知识库目录</h2><button class="kb-icon-btn" data-kb-action="add-catalog" aria-label="新建目录">${icon('plus')}</button></div><input class="kb-dir-search" aria-label="查找目录" placeholder="查找目录" value="${esc(state.dirQuery)}"><nav class="kb-dir-list" aria-label="文档目录">${catalogButtons()}</nav><div class="kb-sync-state"><b><span class="kb-dot"></span>飞书同步正常</b>最近同步 ${esc(state.lastSync)}<br>同步文档需审核后发布</div></aside><section class="kb-library" aria-label="文档列表"><div class="kb-library-head"><div><h2>${state.tab === 'audit' ? '待审核文档' : esc(state.catalog)}<span class="kb-count" data-kb-result-count></span></h2><p>${state.tab === 'audit' ? '核对内容与来源，确认后发布给团队' : '团队文档集中整理，按目录快速查找'}</p></div><div class="kb-view-switch" aria-label="显示方式"><button class="${state.view === 'list' ? 'active' : ''}" aria-label="列表视图" aria-pressed="${state.view === 'list'}" data-kb-action="view" data-value="list">${icon('list')}</button><button class="${state.view === 'cards' ? 'active' : ''}" aria-label="卡片视图" aria-pressed="${state.view === 'cards'}" data-kb-action="view" data-value="cards">${icon('grid')}</button></div></div>${state.tab === 'audit' ? '<p class="kb-audit-note">飞书同步和人工提交的文档进入待审核列表。请核对内容、所属目录与来源；通过后才能被团队阅读和检索。</p>' : ''}<div class="kb-toolbar"><label class="kb-search">${icon('search')}<input id="kb-query" type="search" aria-label="搜索文档" placeholder="搜索标题、关键词或正文" value="${esc(state.query)}"></label><button class="kb-btn" data-kb-action="search">搜索</button>${state.tab === 'documents' ? `<select id="kb-status" aria-label="文档状态"><option value="all">全部状态</option>${Object.entries(statusNames).map(([value, name]) => `<option value="${value}" ${state.status === value ? 'selected' : ''}>${name}</option>`).join('')}</select>` : ''}<select id="kb-sort" class="kb-sort" aria-label="文档排序"><option value="recent" ${state.sort === 'recent' ? 'selected' : ''}>最近更新</option><option value="title" ${state.sort === 'title' ? 'selected' : ''}>标题排序</option></select></div><div class="kb-filter-summary" role="status" aria-live="polite"></div><div class="kb-results"></div><div class="kb-pagination"></div></section></div><p class="kb-prototype-footer">交互原型：修改仅用于本次演示，刷新后恢复示例文档。</p></main></div>`;
    setupDirectory();
    renderResults();
    layoutObserver?.disconnect();
    layoutObserver = new ResizeObserver(() => {
      cancelAnimationFrame(layoutFrame);
      layoutFrame = requestAnimationFrame(() => { renderDirectory(); renderResults(); });
    });
    layoutObserver.observe(document.querySelector('.kb-results'));
    layoutObserver.observe(document.querySelector('.kb-dir-list'));
  }
  function closeModal() {
    if (KnowledgeEditor.active) { KnowledgeEditor.requestClose(); return; }
    overlay.innerHTML = '';
    document.body.style.overflow = '';
    returnFocus?.focus();
  }
  function openModal(title, body, footer, drawer = false) {
    returnFocus = document.activeElement;
    document.body.style.overflow = 'hidden';
    overlay.innerHTML = `<div class="kb-mask ${drawer ? '' : 'kb-dialog-mask'}"><section class="${drawer ? 'kb-drawer' : 'kb-dialog'}" role="dialog" aria-modal="true" aria-labelledby="kb-modal-title"><header class="kb-modal-head"><h2 id="kb-modal-title">${esc(title)}</h2><button class="kb-icon-btn" data-kb-action="close" aria-label="关闭">${icon('close')}</button></header><div class="kb-modal-body">${body}<p class="kb-error" role="alert"></p></div><footer class="kb-modal-foot">${footer}</footer></section></div>`;
    overlay.querySelector('input, textarea, select, button')?.focus();
  }
  const closeButton = '<button class="kb-btn" data-kb-action="close">关闭</button>';
  function readDocument(doc) {
    modalDocumentId = doc.id;
    const footer = state.tab === 'audit'
      ? `<button class="kb-btn" data-kb-action="reject" data-id="${doc.id}">退回修改</button><button class="kb-btn primary" data-kb-action="approve" data-id="${doc.id}">确认发布</button>`
      : `${closeButton}${doc.status !== 'pending_review' ? `<button class="kb-btn primary" data-kb-action="edit" data-id="${doc.id}">编辑文档</button>` : ''}`;
    const attachmentNames = doc.attachments.map(file => typeof file === 'string' ? file : file.name);
    const content = doc.richContent ? KnowledgeEditor.sanitize(doc.richContent) : esc(doc.content);
    openModal(state.tab === 'audit' ? '审核文档' : '阅读文档', `${statusTag(doc)}<h2 class="kb-reading-title">${esc(doc.title)}</h2><p class="kb-reading-meta">${esc(doc.catalog)} / ${esc(doc.author)} / V${doc.version || 1}<br>更新于 ${doc.updated}${doc.keywords ? '<br>标签：' + esc(doc.keywords) : ''}</p><div class="kb-reading-content ${doc.richContent ? 'ke-rich-reading' : ''}">${content}</div><section class="kb-reading-source"><h3>来源与附件</h3><p>来源：${esc(doc.source)}${doc.source === '飞书文档' ? ' / 团队知识空间' : ' / 管理员上传'}${doc.sourceNote ? '<br>' + esc(doc.sourceNote) : ''}</p>${attachmentNames.length ? '<ul>' + attachmentNames.map(name => '<li>' + esc(name) + '</li>').join('') + '</ul>' : '<p>这篇文档没有附件</p>'}</section>`, footer, true);
  }
  function editDocument(doc) {
    if (doc?.status === 'published') {
      const revision = documents.find(item => item.basePublishedId === doc.id);
      if (revision?.status === 'pending_review') { showNotice('这个文档已有修订版待审核，请先处理审核。'); return; }
      if (revision) doc = revision;
    }
    const editing = doc;
    KnowledgeEditor.open({ doc, catalogs, preferredCatalog: state.catalog === '全部文档' ? catalogs[0] : state.catalog,
      onClose: closeModal,
      onSave(payload, submit) {
        if (editing && editing.status !== 'published') Object.assign(editing, payload, { updated: now() });
        else documents.unshift({ ...(editing || {}), ...payload, id: Math.max(...documents.map(item => item.id), 0) + 1,
          basePublishedId: editing?.status === 'published' ? editing.id : undefined,
          version: editing?.status === 'published' ? (editing.version || 1) + 1 : 1,
          source: editing?.source || '手动创建', author: '林嘉宁', updated: now() });
        state.tab = submit ? 'audit' : 'documents'; state.catalog = payload.catalog; state.query = ''; state.status = submit ? 'all' : 'draft'; state.sort = 'recent'; state.page = 1;
        mutateAndRefresh(submit ? '文档已提交审核，审核通过后发布。' : '草稿已保存，可稍后继续编辑。');
      },
    });
  }
  function now() {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }
  function mutateAndRefresh(message) { closeModal(); render(); showNotice(message); }
  function action(name, target) {
    const id = Number(target.dataset.id);
    const doc = documents.find(item => item.id === id);
    if (name === 'unavailable') { showNotice('本次原型展示知识库；可从 KPI 考核入口查看已有演示。'); return; }
    if (name === 'close') { closeModal(); return; }
    if (name === 'catalog') { state.catalog = target.dataset.value; state.page = 1; render(); return; }
    if (name === 'dir-page') { state.dirPage = Number(target.dataset.value); renderDirectory(); return; }
    if (name === 'tab') { state.tab = target.dataset.value; state.status = 'all'; state.page = 1; render(); return; }
    if (name === 'view') { state.view = target.dataset.value; render(); return; }
    if (name === 'page') { state.page = Number(target.dataset.value); renderResults(); return; }
    if (name === 'search') { state.page = 1; renderResults(); return; }
    if (name === 'reset') { state.query = ''; state.status = 'all'; state.page = 1; render(); return; }
    if (name === 'read' && doc) { readDocument(doc); return; }
    if (name === 'create') { editDocument(); return; }
    if (name === 'edit' && doc && doc.status !== 'pending_review') { editDocument(doc); return; }
    if (name === 'submit' && doc?.status === 'draft') {
      if (doc.title === '未命名文档' || (!doc.content?.trim() && !doc.richContent?.includes('<img') && !doc.attachments.length)
        || (doc.expires && doc.expires < now().slice(0, 10))) {
        editDocument(doc); showNotice('请补全文档信息，检查有效期后提交审核。'); return;
      }
      doc.status = 'pending_review'; doc.updated = now(); mutateAndRefresh('文档已提交审核。'); return;
    }
    if (name === 'delete' && doc && doc.status !== 'pending_review') {
      openModal('删除文档', `<p class="kb-help">确认删除“${esc(doc.title)}”？文档将从本次原型的列表中移除。</p>`, `<button class="kb-btn" data-kb-action="close">取消</button><button class="kb-btn danger" data-kb-action="confirm-delete" data-id="${id}">确认删除</button>`); return;
    }
    if (name === 'confirm-delete' && doc && doc.status !== 'pending_review') { documents = documents.filter(item => item.id !== id); mutateAndRefresh('文档已删除。'); return; }
    if (name === 'approve' && doc?.status === 'pending_review') {
      const previous = documents.find(item => item.id === doc.basePublishedId);
      if (previous) {
        doc.versionHistory = [...(previous.versionHistory || []), { title: previous.title, content: previous.content, version: previous.version || 1, updated: previous.updated }];
        documents = documents.filter(item => item.id !== previous.id);
      }
      delete doc.basePublishedId; doc.status = 'published'; doc.updated = now(); mutateAndRefresh('文档已发布，团队可阅读和检索。'); return;
    }
    if (name === 'reject' && doc?.status === 'pending_review') {
      openModal('退回修改', `<p class="kb-help">${esc(doc.title)}</p><div class="kb-field" style="margin-top:18px"><label for="kb-reject-reason">修改意见</label><textarea id="kb-reject-reason" placeholder="说明需要补充或修正的内容"></textarea></div>`, `<button class="kb-btn" data-kb-action="close">取消</button><button class="kb-btn primary" data-kb-action="confirm-reject" data-id="${id}">退回修改</button>`); return;
    }
    if (name === 'confirm-reject' && doc?.status === 'pending_review') {
      const reason = document.getElementById('kb-reject-reason').value.trim();
      if (!reason) { overlay.querySelector('.kb-error').textContent = '请填写修改意见，便于作者处理。'; return; }
      doc.status = 'draft'; doc.updated = now(); doc.content += '\n\n审核修改意见\n' + reason;
      if (doc.richContent) doc.richContent += '<h3>审核修改意见</h3><p>' + esc(reason) + '</p>';
      mutateAndRefresh('文档已退回草稿，修改意见已记录。'); return;
    }
    if (name === 'add-catalog') {
      openModal('新建目录', '<div class="kb-field"><label for="kb-catalog-name">目录名称</label><input id="kb-catalog-name" maxlength="30" placeholder="例如：客户案例、产品指南"></div>', '<button class="kb-btn" data-kb-action="close">取消</button><button class="kb-btn primary" data-kb-action="save-catalog">新建目录</button>'); return;
    }
    if (name === 'save-catalog') {
      const catalog = document.getElementById('kb-catalog-name').value.trim();
      if (!catalog || catalogs.includes(catalog) || catalog === '全部文档') { overlay.querySelector('.kb-error').textContent = '请输入不重复的目录名称。'; return; }
      catalogs.push(catalog); state.catalog = catalog; state.tab = 'documents'; state.query = ''; state.status = 'all'; state.dirQuery = ''; state.page = 1;
      mutateAndRefresh('目录已新建，可以添加第一篇文档。'); return;
    }
    if (name === 'sync') {
      openModal('同步飞书文档', `<div class="kb-field"><label for="kb-sync-catalog">保存到目录</label><select id="kb-sync-catalog">${catalogs.map(catalog => `<option>${esc(catalog)}</option>`).join('')}</select></div><p class="kb-help">从已授权的团队知识空间采集最新文档。同步结果进入待审核列表，通过审核后再发布。<br><br>本次演示将生成一篇示例待审核文档。</p>`, '<button class="kb-btn" data-kb-action="close">取消</button><button class="kb-btn primary" data-kb-action="confirm-sync">开始同步</button>'); return;
    }
    if (name === 'confirm-sync') {
      const catalog = document.getElementById('kb-sync-catalog').value;
      documents.unshift({ ...documents[0], id: Math.max(...documents.map(item => item.id), 0) + 1, title: '飞书同步：团队协作与交接指南', catalog, source: '飞书文档', status: 'pending_review', attachments: [], updated: now() });
      state.lastSync = '刚刚'; state.tab = 'audit'; state.catalog = '全部文档'; state.status = 'all'; state.query = ''; state.page = 1; state.sort = 'recent';
      mutateAndRefresh('已同步 1 篇示例文档，请审核内容后发布。');
    }
  }
  document.addEventListener('click', event => {
    const target = event.target.closest('[data-kb-action]');
    if (target && !target.disabled) action(target.dataset.kbAction, target);
    else if (event.target.classList.contains('kb-mask')) closeModal();
    document.querySelectorAll('.kb-more[open]').forEach(menu => { if (!menu.contains(event.target)) menu.removeAttribute('open'); });
    document.querySelectorAll('.kb-more[open] .kb-menu').forEach(menu => {
      menu.style.top = ''; menu.style.bottom = '';
      if (menu.getBoundingClientRect().bottom > document.querySelector('.kb-library').getBoundingClientRect().bottom - 8) { menu.style.top = 'auto'; menu.style.bottom = '26px'; }
    });
  });
  document.addEventListener('input', event => {
    if (event.target.id === 'kb-query') { state.query = event.target.value; state.page = 1; renderResults(); }
    if (event.target.matches('.kb-dir-search')) { state.dirQuery = event.target.value; state.dirPage = 1; renderDirectory(); }
  });
  document.addEventListener('change', event => {
    if (event.target.matches('.kb-directory-mobile select')) { state.catalog = event.target.value; state.page = 1; render(); return; }
    if (event.target.id === 'kb-status') { state.status = event.target.value; state.page = 1; renderResults(); }
    if (event.target.id === 'kb-sort') { state.sort = event.target.value; state.page = 1; renderResults(); }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { closeModal(); document.querySelectorAll('.kb-more[open]').forEach(menu => menu.removeAttribute('open')); }
    if (event.key === 'Enter' && event.target.id === 'kb-query') { event.preventDefault(); state.page = 1; renderResults(); }
    if (event.key === 'Tab' && overlay.firstElementChild) {
      const focusable = [...overlay.querySelectorAll('button, input, textarea, select, a[href]')].filter(node => !node.disabled && node.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });
  mobile.addEventListener('change', renderResults);
  render();
  if (new URLSearchParams(location.search).get('editor') === 'new') editDocument();
})();
