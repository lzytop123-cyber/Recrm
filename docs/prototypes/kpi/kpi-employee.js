'use strict';
// Employee workflow shares the same synthetic assessment records as the admin workbench.
globalThis.createKpiEmployee = function (env) {
  const { state, current, getPerson, esc, icon, button, notify, render, dialog, close, showDetail, getActivePerson } = env;
  const drafts = new Map(), cachePrefix = 'kpi-employee-draft-v2:';
  const key = p => state.cycle + ':' + p.id + ':' + p.templateSnapshot.id + ':v' + p.templateSnapshot.version;
  const readonly = p => p.status !== 'submit';
  const dateLabel = () => state.cycle.replace('-', '年') + '月';
  const validLink = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) && Boolean(url.hostname); } catch { return false; } };
  function initialDraft(p) {
    return {
      metrics: p.templateSnapshot.metrics.map(() => ({ actual: '', note: '', link: '', files: [] })),
      summary: '', acknowledged: false, dirty: false, savedAt: ''
    };
  }
  function getDraft(p = getPerson()) {
    const id = key(p);
    if (!drafts.has(id)) {
      let value = p.submission ? structuredClone(p.submission.draft) : initialDraft(p);
      if (!p.submission) {
        try {
          const cached = JSON.parse(localStorage.getItem(cachePrefix + id) || 'null');
          if (cached?.metrics?.length === p.templateSnapshot.metrics.length && typeof cached.summary === 'string') {
            value = initialDraft(p);
            cached.metrics.forEach((m, i) => {
              value.metrics[i] = {
                actual: String(m.actual || ''),
                note: String(m.note || ''), link: String(m.link || ''),
                files: Array.isArray(m.files) ? m.files.slice(0, 5).map(f => ({ name: String(f.name || ''), size: Number(f.size) || 0, ready: false })) : []
              };
            });
            value.summary = cached.summary;
            value.savedAt = String(cached.savedAt || '');
          }
        } catch { /* A missing or unusable draft does not prevent filling the form. */ }
      }
      value.acknowledged = false;
      value.dirty = false;
      drafts.set(id, value);
    }
    return drafts.get(id);
  }
  function feedback(p) {
    return p.returnInfo || (p.attention === '材料已退回' ? { note: '签约证明不完整，请补充客户名称、签约日期及成果链接或附件。', by: p.manager, at: '本期示例反馈' } : null);
  }
  function readiness(draft) {
    return draft.metrics.map((m, i) => Boolean(m.actual.trim() && m.note.trim() && (!m.link.trim() || validLink(m.link.trim())) &&
      (i !== 0 || validLink(m.link.trim()) || m.files.some(f => f.ready))));
  }
  function completed(draft) { return readiness(draft).filter(Boolean).length + Number(Boolean(draft.summary.trim())); }
  function fileList(files, editable, index) {
    return files.map((file, i) => '<span class="ks-file">' + icon('doc') + '<span>' + esc(file.name) + '<small>' + (file.ready ? (file.size / 1024).toFixed(0) + ' KB' : '需重新选择文件') + '</small></span>' +
      (editable ? '<button type="button" data-ks-action="remove-file" data-index="' + index + '" data-file="' + i + '" aria-label="移除' + esc(file.name) + '">' + icon('close') + '</button>' : '') + '</span>').join('');
  }
  function field(label, index, fieldName, value, textarea = false, extra = '') {
    const input = textarea ? '<textarea' : '<input type="text"';
    return '<label class="ks-field"><span>' + label + '</span>' + input + ' data-ks-index="' + index + '" data-ks-field="' + fieldName + '" aria-label="' + label + '" ' + extra +
      (textarea ? ' maxlength="2000">' + esc(value) + '</textarea>' : ' maxlength="1000" value="' + esc(value) + '">') + '</label>';
  }
  function metric(p, m, i, draft) {
    const data = draft.metrics[i], ready = readiness(draft)[i];
    return '<details class="ks-metric" id="ks-metric-' + i + '" open><summary><span class="ks-metric-title"><b>' + esc(m.name) + '</b><span>' + m.max + ' 分 / ' + m.max + '%</span></span><span class="ks-ready" data-ks-ready="' + i + '">' + (ready ? '已完成' : '待补充') + '</span></summary>' +
      '<div class="ks-metric-body"><div class="ks-standard"><span>目标与标准</span><p>' + esc(m.target) + '</p></div>' +
      field(m.name + '实际完成情况', i, 'actual', data.actual, false, 'placeholder="对照目标填写本项实际完成情况"') +
      '<p class="ks-source">由员工填写，主管结合成果材料评分。</p>' +
      field(m.name + '成果说明', i, 'note', data.note, true, 'placeholder="说明完成情况、关键成果，以及未达成部分的原因"') +
      '<div class="ks-evidence"><label class="ks-field"><span>' + (i === 0 ? '成果证明 <em>链接或附件至少提供一项</em>' : '补充证明 <em>选填</em>') + '</span><input type="url" data-ks-index="' + i + '" data-ks-field="link" aria-label="' + esc(m.name) + '成果链接" placeholder="https://… 成果、客户或验收记录链接" value="' + esc(data.link) + '" maxlength="1000"></label>' +
      '<label class="ks-upload">' + icon('plus') + '<span>添加附件</span><input type="file" data-ks-upload="' + i + '" aria-label="' + esc(m.name) + '成果附件" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"></label></div>' +
      '<div class="ks-files" data-ks-files="' + i + '">' + fileList(data.files, true, i) + '</div><p class="ks-file-note">支持 PDF、Word、Excel、图片，单个不超过 10 MB，最多 5 个。</p></div></details>';
  }
  function steps(p) {
    const keys = current().review ? ['submit', 'scoring', 'review', 'confirm', 'done'] : ['submit', 'scoring', 'confirm', 'done'];
    const labels = { submit: '员工填报', scoring: '主管评分', review: 'HR 复核', confirm: '结果确认', done: '考核完成' };
    const active = keys.indexOf(p.status);
    return '<ol class="ks-flow" aria-label="我的考核进度">' + keys.map((k, i) => '<li class="' + (i === active ? 'active' : i < active ? 'done' : '') + '"><span>' + (i < active ? icon('check') : i + 1) + '</span><b>' + labels[k] + '</b></li>').join('') + '</ol>';
  }
  function heading(p) {
    return '<header class="kp-heading"><div><div class="kp-title"><h1>我的考核</h1><span class="kp-demo">员工视角 / 示例数据</span></div><p>' + dateLabel() + ' · 本期填报与处理进度</p></div><div class="kp-actions">' +
      env.rolePicker() + '<select class="kp-select" id="kp-cycle" aria-label="本期考核周期"><option value="2026-09"' + (state.cycle === '2026-09' ? ' selected' : '') + '>2026年9月</option><option value="2026-10"' + (state.cycle === '2026-10' ? ' selected' : '') + '>2026年10月</option></select>' +
      button('管理员视角', 'admin-view') + '</div></header>';
  }
  function assignment(p) {
    return '<section class="ks-assignment"><div class="ks-person"><span class="kp-avatar">' + esc(p.name.slice(-2)) + '</span><div><strong>' + esc(p.name) + '</strong><small>' + esc(p.department) + ' / ' + esc(p.role) + '</small></div></div>' +
      '<div><small>考核模板</small><strong>' + esc(p.templateSnapshot.name) + ' V' + p.templateSnapshot.version + '</strong></div><div><small>直属主管</small><strong>' + esc(p.manager) + '</strong></div><div><small>' + (p.status === 'submit' ? '员工提交截止' : '本期填报') + '</small><strong>' + (p.status === 'submit' ? current().dates[0].slice(5).replace('-', '/') + ' 18:00' : '已提交') + '</strong></div></section>';
  }
  function checklist(p, draft) {
    const ready = readiness(draft), total = p.templateSnapshot.metrics.length + 1, n = completed(draft);
    return '<aside class="ks-sidebar"><section class="ks-side-panel"><h2>材料完成情况</h2><div class="ks-completion"><strong data-ks-count>' + n + '<small> / ' + total + '</small></strong><span>项已完成</span></div><div class="ks-progress"><span data-ks-progress style="width:' + n / total * 100 + '%"></span></div><nav class="ks-checklist" aria-label="填报清单">' +
      p.templateSnapshot.metrics.map((m, i) => '<button type="button" data-ks-action="jump" data-index="' + i + '"><span>' + esc(m.name) + '</span><b data-ks-check="' + i + '" class="' + (ready[i] ? 'done' : '') + '">' + (ready[i] ? '完成' : '待补充') + '</b></button>').join('') +
      '<button type="button" data-ks-action="jump" data-index="summary"><span>本月工作总结</span><b data-ks-check="summary" class="' + (draft.summary.trim() ? 'done' : '') + '">' + (draft.summary.trim() ? '完成' : '待补充') + '</b></button></nav></section>' +
      '<section class="ks-side-panel ks-guide"><h3>填报提示</h3><p>考核规则已固定。请按目标自行填写实际完成情况、成果说明和证明材料。</p><p>提交后由 ' + esc(p.manager) + ' 评分。退回补充时，已填内容会保留。</p><small>附件仅用于本次原型演示；刷新后需要重新选择。</small></section></aside>';
  }
  function submissionMarkup(p) {
    const draft = p.submission?.draft;
    if (!draft) return '<p class="ks-read-empty">该示例记录尚未展示员工补充材料。</p>';
    return '<div class="ks-read-materials">' + p.templateSnapshot.metrics.map((m, i) => {
      const data = draft.metrics[i];
      return '<article class="ks-read-metric"><h3>' + esc(m.name) + '<small>满分 ' + m.max + ' 分</small>' + (p.itemScores && ['review', 'confirm', 'done'].includes(p.status) ? '<strong class="ks-item-result">得分 ' + p.itemScores[i] + '</strong>' : '') + '</h3><dl><dt>实际完成</dt><dd>' + esc(data.actual) + '</dd><dt>成果说明</dt><dd>' + esc(data.note) + '</dd>' + (data.link && validLink(data.link) ? '<dt>成果链接</dt><dd><a href="' + esc(data.link) + '" target="_blank" rel="noopener noreferrer">' + esc(data.link) + '</a></dd>' : '') + '</dl>' +
        (data.files.length ? '<div class="ks-files">' + fileList(data.files, false, i) + '</div>' : '') + '</article>';
    }).join('') + '<section class="ks-read-summary"><h3>本月工作总结</h3><p>' + esc(draft.summary) + '</p></section>' + (p.scoreNote ? '<section class="ks-read-summary"><h3>主管评分依据与改进建议</h3><p>' + esc(p.scoreNote) + '</p></section>' : '') + '</div>';
  }
  function submitted(p) {
    const titles = { scoring: '已提交，等待主管评分', review: '主管已评分，等待 HR 复核', confirm: '评分已完成，请确认考核结果', done: '本期考核已完成' };
    const owner = p.status === 'review' ? 'HR · 陈悦' : p.status === 'scoring' ? p.manager : p.name;
    return '<div class="ks-body"><section class="ks-editor ks-submitted"><div class="ks-submitted-head">' + icon('check') + '<div><h2>' + titles[p.status] + '</h2><p>' + (p.status === 'done' ? '考核已归档，材料与规则保留。' : '当前处理人：' + owner + '。提交内容已锁定，可在下方查看。') + '</p></div>' +
      (p.score != null ? '<strong class="ks-result-score"><span>' + (['confirm', 'done'].includes(p.status) ? '最终得分' : '主管拟评分') + '</span>' + p.score + '<small> / 100 分</small></strong>' : '') + '</div>' + submissionMarkup(p) + '</section><aside class="ks-sidebar"><section class="ks-side-panel"><h2>处理记录</h2><ol class="kp-timeline">' +
      [...p.log].reverse().map(item => '<li>' + esc(item.text) + '<small>' + esc(item.at) + '</small></li>').join('') + '</ol></section></aside></div><footer class="ks-footer"><span>提交记录只读，退回后可继续补充材料。</span><div>' +
      (p.status === 'confirm' ? '<button class="kb-btn primary" data-ks-action="confirm-result">确认考核结果</button>' : '<span class="ks-wait">' + (p.status === 'done' ? '已归档' : '等待下一阶段处理') + '</span>') + '</div></footer>';
  }
  function pageMarkup() {
    const p = getPerson();
    if (!p) return heading() + '<section class="kp-panel kp-wide"><div class="kp-empty">' + icon('calendar') + '<h2>本期还没有考核任务</h2><p>考核发起后，这里会展示你的考核指标与填报要求。</p></div></section>';
    if (readonly(p)) return heading(p) + assignment(p) + steps(p) + submitted(p);
    const draft = getDraft(p), returned = feedback(p);
    return heading(p) + assignment(p) + steps(p) +
      '<div class="ks-body"><section class="ks-editor" aria-label="本期考核填报">' +
      (returned ? '<section class="ks-return" role="status"><strong>主管退回，需补充材料</strong><p>' + esc(returned.note) + '</p><small>' + esc(returned.by) + ' · ' + esc(returned.at) + '，原内容已保留。</small></section>' :
        '<p class="ks-intro">逐项填写实际完成情况并补充成果说明。</p>') +
      p.templateSnapshot.metrics.map((m, i) => metric(p, m, i, draft)).join('') +
      '<section class="ks-summary" id="ks-summary"><h2>本月工作总结</h2><label class="ks-field"><span>关键成果、未达成原因与下月改进</span><textarea data-ks-field="summary" aria-label="本月工作总结" maxlength="3000" placeholder="简要说明本月的主要成果、遇到的问题和下一步改进">' + esc(draft.summary) + '</textarea></label></section>' +
      '<label class="ks-ack"><input type="checkbox" data-ks-field="acknowledged"' + (draft.acknowledged ? ' checked' : '') + '>我已核对填报内容和成果材料，确认真实完整</label><p class="ks-error" id="ks-error" role="alert"></p></section>' +
      checklist(p, draft) + '</div><footer class="ks-footer"><span><span data-ks-save-state>' + (draft.dirty ? '有未保存的修改' : draft.savedAt ? '草稿已保存 · ' + esc(draft.savedAt) : '草稿尚未保存') +
      '</span><small class="ks-mobile-count" data-ks-mobile-count>必填项 ' + completed(draft) + ' / ' + (draft.metrics.length + 1) + ' 完成</small></span><div><button class="kb-btn" data-ks-action="save">保存草稿</button><button class="kb-btn primary" data-ks-action="submit">提交主管</button></div></footer>';
  }
  function update() {
    const p = getPerson();
    if (!p || readonly(p) || state.page !== 'self') return;
    const draft = getDraft(p), ready = readiness(draft), n = completed(draft), total = draft.metrics.length + 1;
    const count = document.querySelector('[data-ks-count]');
    if (!count) return;
    count.innerHTML = n + '<small> / ' + total + '</small>';
    document.querySelector('[data-ks-progress]').style.width = n / total * 100 + '%';
    const mobileCount = document.querySelector('[data-ks-mobile-count]');
    if (mobileCount) mobileCount.textContent = '必填项 ' + n + ' / ' + total + ' 完成';
    ready.forEach((value, i) => {
      const check = document.querySelector('[data-ks-check="' + i + '"]');
      check.textContent = value ? '完成' : '待补充';
      check.classList.toggle('done', value);
      document.querySelector('[data-ks-ready="' + i + '"]').textContent = value ? '已完成' : '待补充';
    });
    const summary = document.querySelector('[data-ks-check="summary"]');
    summary.textContent = draft.summary.trim() ? '完成' : '待补充';
    summary.classList.toggle('done', Boolean(draft.summary.trim()));
    document.querySelector('[data-ks-save-state]').textContent = draft.dirty ? '有未保存的修改' : draft.savedAt ? '草稿已保存 · ' + draft.savedAt : '草稿尚未保存';
  }
  function formError(message) {
    const element = document.getElementById('ks-error');
    if (element) { element.textContent = message; element.scrollIntoView({ block: 'nearest', behavior: 'auto' }); }
    else if (document.getElementById('kp-error')) document.getElementById('kp-error').textContent = message;
  }
  function save(silent = false) {
    const p = getPerson();
    if (!p || readonly(p)) return false;
    const draft = getDraft(p), savedAt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit' }).format(new Date());
    try {
      localStorage.setItem(cachePrefix + key(p), JSON.stringify({ ...draft, savedAt, dirty: false, acknowledged: false }));
      draft.savedAt = savedAt;
      draft.dirty = false;
      update();
      if (!silent) notify('草稿已保存至当前浏览器。');
      return true;
    } catch { formError('草稿未能保存，请保留当前页面后重试。'); return false; }
  }
  function validate(p, draft) {
    const invalidLink = draft.metrics.findIndex(m => m.link.trim() && !validLink(m.link.trim()));
    if (invalidLink !== -1) return '成果链接须使用有效的 http:// 或 https:// 地址。';
    const missing = readiness(draft).flatMap((ready, i) => ready ? [] : [p.templateSnapshot.metrics[i].name]);
    if (!draft.summary.trim()) missing.push('本月工作总结');
    if (missing.length) return '请补齐：' + missing.join('、') + '。首项指标需提供成果链接或有效附件。';
    if (!draft.acknowledged) return '请先勾选数据与材料核对确认。';
    return '';
  }
  function prepareSubmit() {
    const p = getPerson();
    if (!p || readonly(p)) return;
    const draft = getDraft(p), issue = validate(p, draft);
    if (issue) return formError(issue);
    dialog('确认提交考核', '<p class="kp-form-note">提交后，填报内容锁定并交由主管评分。主管退回时可继续修改。</p><dl class="kp-recap"><dt>考核周期</dt><dd>' + dateLabel() + '</dd><dt>考核员工</dt><dd>' + esc(p.name) + '</dd><dt>考核主管</dt><dd>' + esc(p.manager) + '</dd><dt>材料完成</dt><dd>' + completed(draft) + ' / ' + (draft.metrics.length + 1) + ' 项已完成</dd></dl>',
      '<small>提交仅更新本地示例考核。</small><div class="kp-actions">' + button('继续修改', 'close') + '<button class="kb-btn primary" data-ks-action="confirm-submit">确认提交</button></div>');
  }
  function submit() {
    const p = getPerson();
    if (!p || readonly(p)) return;
    const draft = getDraft(p), issue = validate(p, draft);
    if (issue) return formError(issue);
    p.submission = { draft: structuredClone(draft), revision: (p.submission?.revision || 0) + 1, at: '刚刚（本地演示）' };
    p.status = 'scoring';
    p.attention = '';
    p.returnInfo = null;
    p.log.push({ text: p.name + '已提交考核材料，交 ' + p.manager + ' 评分', at: p.submission.at });
    draft.dirty = false;
    close();
    render();
    notify('已提交，等待 ' + p.manager + ' 评分。');
  }
  function returnDialog() {
    const p = getActivePerson();
    if (!p || p.status !== 'scoring') return;
    dialog('退回员工补充材料', '<p class="kp-form-note">退回后，' + esc(p.name) + '可在原填报内容上继续修改；原提交记录保留。</p><label class="kp-field"><span>退回原因</span><textarea id="ks-return-reason" aria-label="退回原因" placeholder="写明哪项材料缺少什么，以及需要如何补充" maxlength="2000"></textarea></label>',
      '<small>请给出员工可以执行的补充要求。</small><div class="kp-actions">' + button('取消', 'close') + '<button class="kb-btn primary" data-ks-action="return">确认退回</button></div>');
  }
  function returnMaterial() {
    const p = getActivePerson(), reason = document.getElementById('ks-return-reason')?.value.trim();
    if (!p || p.status !== 'scoring') return;
    if (!reason) return formError('请填写具体退回原因。');
    p.status = 'submit';
    p.attention = '材料已退回';
    p.score = null;
    p.itemScores = null;
    p.returnInfo = { note: reason, by: p.manager, at: '刚刚（本地演示）' };
    if (p.submission) {
      const draft = structuredClone(p.submission.draft);
      draft.acknowledged = false; draft.dirty = false;
      drafts.set(key(p), draft);
    }
    p.log.push({ text: p.manager + '退回材料：' + reason, at: '刚刚（本地演示）' });
    env.afterReturn(p);
    notify('已退回补充，员工填报内容已保留。');
  }
  function handleInput(event) {
    if (state.page !== 'self') return;
    const p = getPerson();
    if (!p || readonly(p)) return;
    const element = event.target, name = element.dataset.ksField;
    if (!name) return;
    const draft = getDraft(p);
    if (name === 'summary') draft.summary = element.value;
    else if (name === 'acknowledged') draft.acknowledged = element.checked;
    else {
      const i = Number(element.dataset.ksIndex);
      draft.metrics[i][name] = element.value;
    }
    if (name !== 'acknowledged') draft.dirty = true;
    update();
  }
  document.addEventListener('input', handleInput);
  document.addEventListener('change', event => {
    if (!event.target.hasAttribute('data-ks-upload') || state.page !== 'self') return;
    const p = getPerson();
    if (!p || readonly(p)) return;
    const i = Number(event.target.dataset.ksUpload), draft = getDraft(p), existing = draft.metrics[i].files;
    const files = [...event.target.files];
    const allowed = /\.(pdf|docx?|xlsx?|png|jpe?g)$/i;
    if (files.some(f => !allowed.test(f.name) || f.size > 10 * 1024 * 1024)) { formError('附件类型不支持或超过 10 MB，请重新选择。'); event.target.value = ''; return; }
    const additions = files.filter(f => !existing.some(old => old.ready && old.name === f.name && old.size === f.size));
    if (existing.filter(f => f.ready).length + additions.length > 5) { formError('每项指标最多添加 5 个附件。'); event.target.value = ''; return; }
    draft.metrics[i].files = [...existing.filter(f => f.ready), ...additions.map(f => ({ name: f.name, size: f.size, ready: true }))];
    draft.dirty = true;
    document.querySelector('[data-ks-files="' + i + '"]').innerHTML = fileList(draft.metrics[i].files, true, i);
    event.target.value = '';
    update();
  });
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-ks-action]');
    if (!trigger || trigger.disabled) return;
    const action = trigger.dataset.ksAction, p = getPerson();
    if (action === 'return') return returnMaterial();
    if (action === 'save') return save();
    if (action === 'submit') return prepareSubmit();
    if (action === 'confirm-submit') return submit();
    if (action === 'remove-file' && p && !readonly(p)) {
      const i = Number(trigger.dataset.index), draft = getDraft(p);
      draft.metrics[i].files.splice(Number(trigger.dataset.file), 1);
      draft.dirty = true;
      document.querySelector('[data-ks-files="' + i + '"]').innerHTML = fileList(draft.metrics[i].files, true, i);
      update();
    }
    if (action === 'jump') {
      const target = document.getElementById(trigger.dataset.index === 'summary' ? 'ks-summary' : 'ks-metric-' + trigger.dataset.index);
      if (target.tagName === 'DETAILS') target.open = true;
      target.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
    if (action === 'confirm-result' && p?.status === 'confirm') {
      dialog('确认考核结果', '<p class="kp-form-note">本期最终得分：' + p.score + ' / 100 分。确认后材料与结果归档。</p>', '<small>请核对评分与处理记录。</small><div class="kp-actions">' + button('继续查看', 'close') + '<button class="kb-btn primary" data-ks-action="finish">确认结果并归档</button></div>');
    }
    if (action === 'finish' && p?.status === 'confirm') {
      p.status = 'done';
      p.log.push({ text: p.name + '已确认结果，考核归档', at: '刚刚（本地演示）' });
      close(); render(); notify('结果已确认，本期考核已完成。');
    }
  });
  window.addEventListener('beforeunload', event => {
    const p = getPerson();
    if (state.page === 'self' && p && !readonly(p) && getDraft(p).dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  function seedSamples() {
    current().people.forEach(p => {
      if (p.status === 'submit' || p.submission) return;
      const d = initialDraft(p);
      d.metrics.forEach((m, i) => {
        m.actual = i === 0 ? '已按本期目标完成首项指标' : i === 1 ? '已按计划完成质量指标' : '按期完成跨部门协作任务';
        m.note = i === 0 ? '已按本期目标整理成果记录。' : i === 1 ? '已核对业务记录，按计划完成相关工作。' : '执行工作规范，按时完成协作任务。';
        if (i === 0) m.link = 'https://example.com/kpi/evidence/' + p.id;
      });
      d.summary = '本月按计划推进工作；未达成部分将继续跟进并形成改进清单。';
      p.submission = { draft: d, revision: 1, at: '本期示例提交' };
      if (p.score != null && !p.itemScores) {
        let allocated = 0;
        p.itemScores = p.templateSnapshot.metrics.map((m, i) => {
          const value = i === p.templateSnapshot.metrics.length - 1 ? p.score - allocated : Math.round(m.max * p.score / 100);
          allocated += value; return value;
        });
        p.scoreNote = '按本期模板及成果材料核对评分（示例）。';
      }
    });
  }
  return { pageMarkup, submissionMarkup, returnDialog, seedSamples };
};
