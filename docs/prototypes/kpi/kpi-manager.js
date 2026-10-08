'use strict';
globalThis.createKpiManager = function (env) {
  const { state, current, esc, icon, button, notify, render, dialog, close, rolePicker, employee } = env;
  const records = () => current().people.filter(p => p.manager === state.managerName);
  const selected = () => records().find(p => p.id === state.selectedId);
  const names = { submit: '待员工提交', scoring: '待我评分', review: '待 HR 复核', confirm: '待员工确认', done: '已完成' };
  const draftKey = p => 'kpi-manager-draft-v1:' + state.cycle + ':' + state.managerName + ':' + p.id + ':v' + p.templateSnapshot.version;
  function draft(p) {
    if (!p.managerDraft) {
      p.managerDraft = { scores: p.itemScores ? p.itemScores.map(String) : p.templateSnapshot.metrics.map(() => ''), note: p.scoreNote || '', checked: false, dirty: false };
      try {
        const saved = JSON.parse(localStorage.getItem(draftKey(p)) || 'null');
        if (saved?.scores?.length === p.templateSnapshot.metrics.length && !p.hrReturnInfo) p.managerDraft = { scores: saved.scores.map(String), note: String(saved.note || ''), checked: false, dirty: false };
      } catch {}
    }
    return p.managerDraft;
  }
  function heading(title, subtitle, score = false) {
    return '<header class="kp-heading"><div><div class="kp-title"><h1>' + title + '</h1><span class="kp-demo">主管视角 / ' + esc(state.managerName) + '</span></div><p>' + subtitle + '</p></div><div class="kp-actions">' +
      rolePicker() + (score ? button('返回团队', 'page', false, 'data-value="team"') : '<select class="kp-select" id="kp-cycle" aria-label="本期考核周期"><option value="2026-09"' + (state.cycle === '2026-09' ? ' selected' : '') + '>2026年9月</option><option value="2026-10"' + (state.cycle === '2026-10' ? ' selected' : '') + '>2026年10月</option></select>') + '</div></header>';
  }
  function pageMarkup() {
    if (state.page === 'scoring') return scorePage();
    const rows = records(), done = rows.filter(p => p.status === 'done').length, pending = rows.filter(p => p.status === 'scoring').length;
    return heading('团队考核', '核对直属团队材料，按固定考核标准评分。') +
      '<section class="kp-stats km-overview-stats">' + [['团队参评', rows.length], ['待我评分', pending], ['员工待提交', rows.filter(p => p.status === 'submit').length], ['考核已完成', done]].map(([label, number]) =>
        '<div class="kp-stat"><small>' + label + '</small><strong>' + number + '<span>人</span></strong></div>').join('') + '</section>' +
      '<section class="kp-panel kp-people kp-wide" style="flex:1;min-height:0"><div class="kp-panel-head"><h2>我的团队 <span class="kb-count" id="kp-result-count"></span></h2><span>仅显示由 ' + esc(state.managerName) + ' 负责考核的员工</span></div>' +
      '<form class="kp-filter" id="km-filter"><label class="kp-search">' + icon('search') + '<input type="search" id="km-query" aria-label="搜索团队员工" placeholder="搜索员工或岗位" value="' + esc(state.managerQuery) + '"></label><button class="kb-btn" type="submit">查询</button><button type="button" class="kp-text-btn" data-km-action="clear">清空筛选</button></form>' +
      '<nav class="kp-tabs" aria-label="主管考核分组"><button class="' + (state.teamTab === 'pending' ? 'active' : '') + '" data-km-action="tab" data-value="pending">待我评分 ' + pending + '</button><button class="' + (state.teamTab === 'all' ? 'active' : '') + '" data-km-action="tab" data-value="all">全部团队 ' + rows.length + '</button></nav><div class="kp-results"></div><div class="kp-pager"></div></section>';
  }
  function renderRows() {
    const results = document.querySelector('.kp-results');
    if (!results) return;
    const data = records().filter(p => (state.teamTab === 'all' || p.status === 'scoring') && (!state.managerQuery.trim() || [p.name, p.role].join(' ').includes(state.managerQuery.trim())));
    document.getElementById('kp-result-count').textContent = data.length + ' 人';
    results.innerHTML = data.length ? '<table class="kp-table"><thead><tr><th>员工</th><th>岗位 / 模板</th><th>当前状态</th><th>材料</th><th>评分截止</th><th>操作</th></tr></thead><tbody>' +
      data.map(p => '<tr data-team-person="' + p.id + '"><td><div class="kp-person"><span class="kp-avatar">' + esc(p.name.slice(-2)) + '</span><strong>' + esc(p.name) + '</strong></div></td><td><div class="kp-cell-ellipsis">' + esc(p.role) + '</div><small class="kp-cell-ellipsis">' + esc(p.templateSnapshot.name) + ' V' + p.templateSnapshot.version + '</small></td><td><span class="kp-status ' + p.status + '">' + names[p.status] + '</span></td><td>' + (p.submission ? '已提交' : '待补充') + '</td><td>' + current().dates[1].slice(5).replace('-', '/') + '</td><td><button class="kp-text-btn" data-km-action="open" data-id="' + p.id + '">' + (p.status === 'scoring' ? '去评分' : '查看记录') + '</button></td></tr>').join('') + '</tbody></table>' :
      '<div class="kp-empty">' + icon('check') + '<h2>' + (state.managerQuery ? '没有匹配的团队员工' : '当前没有待评分考核') + '</h2><p>' + (state.managerQuery ? '调整搜索词或查看全部团队。' : '员工提交后，考核会进入你的评分列表。') + '</p><button class="kb-btn" data-km-action="tab" data-value="all">查看全部团队</button></div>';
    document.querySelector('.kp-pager').innerHTML = '<span>当前显示 ' + data.length + ' 人 / 负责 ' + records().length + ' 人</span><span>团队数据按主管归属展示</span>';
  }
  function total(d) { return Math.round(d.scores.reduce((n, score) => n + (Number(score) || 0), 0) * 10) / 10; }
  function scorePage() {
    const p = selected();
    if (!p) return heading('主管评分', '本页仅处理由你负责的团队员工。', true) + '<section class="kp-panel kp-wide"><div class="kp-empty"><h2>该考核不属于你的评分范围</h2><p>返回团队查看可处理的考核。</p></div></section>';
    const t = p.templateSnapshot, d = draft(p), editable = p.status === 'scoring';
    if (!editable) return heading('团队考核记录', '查看已提交材料和当前进度。', true) +
      '<div class="ks-body"><section class="ks-editor"><div class="ks-submitted-head"><div><h2>' + esc(p.name) + ' · ' + names[p.status] + '</h2><p>' + esc(t.name) + ' V' + t.version + (p.score != null ? '，主管得分 ' + p.score + ' / 100' : '') + '</p></div></div>' + employee.submissionMarkup(p) + '</section><aside class="ks-sidebar"><section class="ks-side-panel"><h2>处理记录</h2><ol class="kp-timeline">' + [...p.log].reverse().map(item => '<li>' + esc(item.text) + '<small>' + esc(item.at) + '</small></li>').join('') + '</ol></section></aside></div><footer class="ks-footer"><span>该阶段无法修改材料与评分。</span>' + button('返回团队', 'page', false, 'data-value="team"') + '</footer>';
    return heading('主管评分', '先核对员工成果，再填写指标得分和评分依据。', true) +
      '<section class="ks-assignment"><div class="ks-person"><span class="kp-avatar">' + esc(p.name.slice(-2)) + '</span><div><strong>' + esc(p.name) + '</strong><small>' + esc(p.department) + ' / ' + esc(p.role) + '</small></div></div><div><small>固定考核模板</small><strong>' + esc(t.name) + ' V' + t.version + '</strong></div><div><small>评分主管</small><strong>' + esc(p.manager) + '</strong></div><div><small>评分截止</small><strong>' + current().dates[1].slice(5).replace('-', '/') + ' 18:00</strong></div></section>' +
      '<div class="km-score-body"><section class="ks-editor">' +
      (p.hrReturnInfo ? '<section class="ks-return"><strong>HR 退回，请重新核对评分</strong><p>' + esc(p.hrReturnInfo) + '</p></section>' : '') +
      '<p class="ks-intro">评分规则与员工材料只读；材料不足时退回补充，不直接替员工修改。</p>' +
      t.metrics.map((m, i) => {
        const evidence = p.submission?.draft.metrics[i];
        return '<section class="km-metric"><h3>' + esc(m.name) + '<small>满分 ' + m.max + ' 分</small></h3><div class="ks-standard"><span>考核标准</span><p>' + esc(m.target) + '</p></div><div class="km-material"><strong>实际完成：</strong>' + esc(evidence?.actual || '尚无员工填报') + '<br><strong>成果说明：</strong>' + esc(evidence?.note || '待补充') +
          (evidence?.link ? '<br><strong>成果链接：</strong>' + esc(evidence.link) : '') +
          (evidence?.files.length ? '<br><strong>附件：</strong>' + evidence.files.map(f => esc(f.name)).join('、') : '') +
          '</div><label class="km-score-field"><span>本项得分</span><input type="number" min="0" max="' + m.max + '" step="0.1" data-km-score="' + i + '" aria-label="' + esc(m.name) + '主管得分" value="' + esc(d.scores[i]) + '"><span>/ ' + m.max + ' 分</span></label></section>';
      }).join('') + '<section class="km-feedback"><h3>工作总结与评分反馈</h3><p class="km-material">' + esc(p.submission?.draft.summary || '暂无员工总结') + '</p><label class="ks-field"><span>评分依据与改进建议</span><textarea id="km-note" aria-label="评分依据与改进建议" maxlength="2000" placeholder="说明评分依据、主要优势和后续改进建议">' + esc(d.note) + '</textarea></label></section>' +
      '<label class="ks-ack"><input type="checkbox" id="km-checked"' + (d.checked ? ' checked' : '') + '>我已核实员工材料，并按本期模板标准评分</label><p class="ks-error" id="ks-error" role="alert"></p></section>' +
      '<aside class="ks-sidebar"><section class="ks-side-panel"><h2>拟评总分</h2><strong class="km-total" id="km-total">' + total(d) + '<small> / 100 分</small></strong><p class="ks-source">三项指标得分自动汇总</p></section><section class="ks-side-panel ks-guide"><h3>下一步</h3><p>' + (current().review ? '提交后进入 HR 复核，复核通过再交员工确认。' : '本期未启用 HR 复核，提交后交员工确认。') + '</p><p>评分未提交时可以保存草稿；材料缺失则退回员工补充。</p></section></aside></div>' +
      '<footer class="ks-footer"><span id="km-save-state">拟评总分 ' + total(d) + ' / 100 分</span><div><button class="kb-btn" data-km-action="return">退回补充</button><button class="kb-btn" data-km-action="save">保存评分草稿</button><button class="kb-btn primary" data-km-action="submit">提交评分</button></div></footer>';
  }
  function error(text) {
    const node = document.getElementById('ks-error') || document.getElementById('kp-error');
    node.textContent = text; node.scrollIntoView({ block: 'nearest' });
  }
  function validate(p, complete) {
    const d = draft(p), metrics = p.templateSnapshot.metrics;
    if (d.scores.some((score, i) => score !== '' && (!Number.isFinite(Number(score)) || Number(score) < 0 || Number(score) > metrics[i].max))) return '单项得分不能超出该项满分，且须为有效数字。';
    if (d.scores.some(score => score !== '' && Math.abs(Number(score) * 10 - Math.round(Number(score) * 10)) > 1e-8)) return '得分最多保留一位小数。';
    if (complete && d.scores.some(score => score.trim() === '')) return '请完整填写各项得分。';
    if (complete && !d.note.trim()) return '请填写评分依据与改进建议。';
    if (complete && !d.checked) return '请先确认已核实员工材料。';
    if (complete && !p.submission) return '员工尚未提交材料，请退回补充或等待员工提交。';
    return '';
  }
  function submit() {
    const p = selected();
    if (!p || p.status !== 'scoring') return;
    const issue = validate(p, true);
    if (issue) return error(issue);
    dialog('提交主管评分', '<dl class="kp-recap"><dt>考核员工</dt><dd>' + esc(p.name) + '</dd><dt>拟评总分</dt><dd>' + total(draft(p)) + ' / 100 分</dd><dt>下一阶段</dt><dd>' + (current().review ? 'HR 复核' : '员工确认') + '</dd></dl><p class="kp-form-note">提交后评分锁定。若被 HR 退回，保留原评分供你修改。</p>', '<small>只处理本人负责的员工考核。</small><div class="kp-actions">' + button('继续修改', 'close') + '<button class="kb-btn primary" data-km-action="confirm">确认提交评分</button></div>');
  }
  document.addEventListener('input', event => {
    if (state.role !== 'manager' || state.page !== 'scoring') return;
    const p = selected();
    if (!p || p.status !== 'scoring') return;
    const d = draft(p), node = event.target;
    if (node.hasAttribute('data-km-score')) d.scores[Number(node.dataset.kmScore)] = node.value;
    if (node.id === 'km-note') d.note = node.value;
    if (node.id === 'km-checked') d.checked = node.checked;
    if (node.hasAttribute('data-km-score') || node.id === 'km-note') d.dirty = true;
    const element = document.getElementById('km-total');
    if (element) element.innerHTML = total(d) + '<small> / 100 分</small>';
    document.getElementById('km-save-state').textContent = '拟评总分 ' + total(d) + ' / 100 分，有未保存的修改';
  });
  document.addEventListener('submit', event => {
    if (event.target.id !== 'km-filter') return;
    event.preventDefault(); state.managerQuery = document.getElementById('km-query').value; renderRows();
  });
  document.addEventListener('click', event => {
    const node = event.target.closest('[data-km-action]');
    if (!node || state.role !== 'manager') return;
    const action = node.dataset.kmAction;
    if (action === 'tab') { state.teamTab = node.dataset.value; render(); }
    if (action === 'clear') { state.managerQuery = ''; state.teamTab = 'all'; render(); }
    if (action === 'open') { state.selectedId = node.dataset.id; state.page = 'scoring'; render(); }
    const p = selected();
    if (!p || p.status !== 'scoring') return;
    if (action === 'return') employee.returnDialog();
    if (action === 'save') {
      const issue = validate(p, false);
      if (issue) return error(issue);
      try { localStorage.setItem(draftKey(p), JSON.stringify(draft(p))); draft(p).dirty = false; document.getElementById('km-save-state').textContent = '评分草稿已保存'; notify('评分草稿已保存至当前浏览器。'); }
      catch { error('评分草稿未能保存，请保留页面后重试。'); }
    }
    if (action === 'submit') submit();
    if (action === 'confirm') {
      const issue = validate(p, true);
      if (issue) return error(issue);
      const d = draft(p);
      p.itemScores = d.scores.map(Number); p.score = total(d); p.scoreNote = d.note.trim();
      p.status = current().review ? 'review' : 'confirm'; p.hrReturnInfo = null;
      p.log.push({ text: p.manager + '提交评分 ' + p.score + ' 分：' + p.scoreNote, at: '刚刚（本地演示）' });
      try { localStorage.removeItem(draftKey(p)); } catch {}
      close(); state.page = 'team'; state.teamTab = 'all'; render();
      notify('评分已提交，进入' + (current().review ? 'HR 复核' : '员工确认') + '。');
    }
  });
  window.addEventListener('beforeunload', event => {
    const p = selected();
    if (state.role === 'manager' && state.page === 'scoring' && p?.status === 'scoring' && p.managerDraft?.dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  return { pageMarkup, renderRows, records, selected };
};
