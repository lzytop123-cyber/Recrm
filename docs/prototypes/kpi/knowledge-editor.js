'use strict';
// Native, local-only editor for the prototype. Attachment processing is simulated.
(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const types = { note: '普通文档', guide: '操作指南', policy: '规章制度', case: '项目案例', faq: '常见问题' };
  const templates = {
    guide: '<h2>适用场景</h2><p>说明适用业务、人员和前置条件。</p><h2>办理步骤</h2><ol><li>准备资料并确认负责人。</li><li>按流程办理，记录处理结果。</li><li>完成核对与归档。</li></ol><h2>注意事项</h2><p>补充常见异常及处理方法。</p>',
    policy: '<h2>目的与适用范围</h2><p>说明制度目的和适用对象。</p><h2>职责分工</h2><p>明确负责人与协作人员。</p><h2>具体要求</h2><ol><li>填写办理要求。</li><li>填写审批及留存要求。</li></ol><h2>生效与维护</h2><p>说明生效时间、解释部门和修订周期。</p>',
    case: '<h2>项目背景</h2><p>记录业务目标、范围与关键约束。</p><h2>实施过程</h2><p>说明关键决策、方案和交付过程。</p><h2>结果与复盘</h2><p>记录实际结果、遇到的问题和改进措施。</p><h2>可复用经验</h2><ul><li>补充其他项目可以参考的做法。</li></ul>',
    faq: '<h2>问题一：填写常见问题</h2><p>回答：说明适用条件和处理方法。</p><h2>问题二：填写常见问题</h2><p>回答：提供操作步骤及注意事项。</p>',
    note: '<h2>文档说明</h2><p>记录文档主题、适用范围和主要内容。</p>',
  };
  let active = false, session = 0, config, model, changed = false, range, saveTimer, beforeFocus;
  const overlay = () => document.getElementById('overlay');
  const field = id => document.getElementById(id);
  const key = () => 'knowledge-editor-v2:' + (config.doc?.id ?? 'new');
  function sanitize(html) {
    const container = document.createElement('template');
    container.innerHTML = html || '';
    const allowed = new Set(['P', 'DIV', 'BR', 'H2', 'H3', 'STRONG', 'B', 'EM', 'I', 'U', 'UL', 'OL', 'LI', 'BLOCKQUOTE', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TD', 'TH', 'A', 'IMG']);
    [...container.content.querySelectorAll('*')].reverse().forEach(node => {
      if (['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'SVG'].includes(node.tagName)) { node.remove(); return; }
      if (!allowed.has(node.tagName)) { node.replaceWith(...node.childNodes); return; }
      const href = node.getAttribute('href'), src = node.getAttribute('src');
      [...node.attributes].forEach(attr => node.removeAttribute(attr.name));
      if (node.tagName === 'A') {
        if (/^https?:\/\//i.test(href || '')) { node.setAttribute('href', href); node.setAttribute('target', '_blank'); node.setAttribute('rel', 'noopener noreferrer'); }
      }
      if (node.tagName === 'IMG') {
        if (/^data:image\/(png|jpe?g|webp|gif);base64,/i.test(src || '')) { node.setAttribute('src', src); node.setAttribute('alt', '文档插图'); }
        else node.remove();
      }
    });
    return container.innerHTML;
  }
  function initial(doc, catalogs, preferredCatalog) {
    return {
      title: doc?.title || '', catalog: doc?.catalog || preferredCatalog || catalogs[0], type: doc?.type || 'note',
      summary: doc?.summary || '', tags: doc?.keywords || '',
      html: sanitize(doc?.richContent || (doc?.content ? esc(doc.content).replace(/\n/g, '<br>') : '')),
      visibility: doc?.visibility || 'inherit', department: doc?.department || '项目交付部', expires: doc?.expires || '',
      sourceNote: doc?.sourceNote || '', attachments: (doc?.attachments || []).map((attachment, index) => typeof attachment === 'string'
        ? { id: 'existing-' + index, name: attachment, size: 0, status: 'ready', existing: true } : { ...attachment, status: 'ready' }),
    };
  }
  function collect() {
    model = { ...model, title: field('ke-title').value, catalog: field('ke-catalog').value, type: field('ke-type').value,
      summary: field('ke-summary').value, tags: field('ke-tags').value, html: sanitize(field('ke-content').innerHTML),
      visibility: field('ke-visibility').value, department: field('ke-department').value,
      expires: field('ke-expires').value, sourceNote: field('ke-source').value };
    return model;
  }
  function plain(html) { const node = document.createElement('div'); node.innerHTML = sanitize(html); return node.innerText.trim(); }
  function error(message) { field('ke-error').textContent = message; }
  function count() { field('ke-word-count').textContent = plain(field('ke-content').innerHTML).length + ' 字'; }
  function autosave() {
    if (!active) return;
    collect();
    try {
      localStorage.setItem(key(), JSON.stringify({ model, at: Date.now() }));
      field('ke-save-status').textContent = '草稿已保存到本机';
      field('ke-save-status').classList.remove('pending');
      return true;
    } catch {
      field('ke-save-status').textContent = '自动保存失败，请手动保存草稿';
      field('ke-save-status').classList.add('pending');
      return false;
    }
  }
  function onEdit() {
    changed = true; error(''); count();
    field('ke-save-status').textContent = '正在保存草稿…';
    field('ke-save-status').classList.add('pending');
    clearTimeout(saveTimer); saveTimer = setTimeout(autosave, 650);
  }
  function attachments() {
    field('ke-attachments').innerHTML = model.attachments.map(file => `<div class="ke-file"><span class="ke-file-mark">${esc(file.name.split('.').at(-1).toUpperCase())}</span><div><strong>${esc(file.name)}</strong><small>${file.size ? (file.size / 1024 / 1024).toFixed(2) + ' MB / ' : ''}<span class="${file.status === 'processing' ? 'ke-processing' : ''}">${file.existing ? '已有附件' : file.status === 'processing' ? '解析中（演示）' : '就绪（演示）'}</span></small></div><button type="button" class="kb-icon-btn" data-ke-action="remove-file" data-id="${esc(file.id)}" aria-label="移除 ${esc(file.name)}">×</button></div>`).join('');
  }
  function attach(files) {
    error('');
    const token = session;
    for (const file of files) {
      const extension = file.name.split('.').at(-1).toLowerCase();
      if (!['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'png', 'jpg', 'jpeg', 'webp'].includes(extension)) { error('不支持该文件格式：' + file.name); continue; }
      if (file.size > 20 * 1024 * 1024) { error('单个附件不能超过 20 MB。'); continue; }
      if (model.attachments.length >= 8) { error('每篇文档最多选择 8 个附件。'); break; }
      if (model.attachments.some(item => item.name === file.name)) { error('已存在同名附件：' + file.name); continue; }
      const item = { id: crypto.randomUUID(), name: file.name, size: file.size, status: 'processing' };
      model.attachments.push(item);
      setTimeout(() => { if (active && token === session && model.attachments.includes(item)) { item.status = 'ready'; attachments(); autosave(); } }, 800);
    }
    attachments(); changed = true; collect(); autosave();
  }
  function finish() { active = false; session++; clearTimeout(saveTimer); overlay().querySelector('.ke-guard')?.remove(); }
  function discard() {
    try { localStorage.removeItem(key()); } catch { /* private mode */ }
    finish(); config.onClose(); beforeFocus?.isConnected && beforeFocus.focus();
  }
  function guard(title, description, buttons) {
    overlay().querySelector('.ke-guard')?.remove();
    const div = document.createElement('div'); div.className = 'ke-guard';
    div.innerHTML = `<section role="alertdialog" aria-modal="true" aria-labelledby="ke-guard-title"><h3 id="ke-guard-title">${esc(title)}</h3><p>${esc(description)}</p><div>${buttons}</div></section>`;
    overlay().appendChild(div); div.querySelector('button')?.focus();
  }
  function requestClose() {
    if (!active) return false;
    if (!changed) { finish(); config.onClose(); beforeFocus?.isConnected && beforeFocus.focus(); return true; }
    guard('保留这次编辑吗？', '修改尚未保存到文档列表。可以继续编辑，或保留本机草稿后关闭。', '<button class="kb-btn" data-ke-action="continue">继续编辑</button><button class="kb-btn danger" data-ke-action="discard">丢弃修改</button><button class="kb-btn primary" data-ke-action="keep">保留草稿并关闭</button>');
    return true;
  }
  function save(submit) {
    collect();
    if (submit) {
      if (!model.title.trim()) { error('请填写文档标题。'); field('ke-title').focus(); return; }
      if (!plain(model.html) && !model.html.includes('<img') && !model.attachments.length) { error('请填写正文或选择至少一个附件。'); field('ke-content').focus(); return; }
      if (model.attachments.some(file => file.status === 'processing')) { error('附件正在处理，请等待完成后提交。'); return; }
      if (model.visibility === 'department' && !model.department) { error('请选择可见部门。'); return; }
      if (model.expires && model.expires < new Date().toLocaleDateString('en-CA')) { error('有效期不能早于今天。'); return; }
    }
    const payload = { ...model, title: model.title.trim() || '未命名文档', content: plain(model.html), richContent: sanitize(model.html),
      keywords: model.tags.split(/[,，、\s]+/).filter(Boolean).slice(0, 8).join(','),
      summary: model.summary.trim() || plain(model.html).replace(/\s+/g, ' ').slice(0, 100), status: submit ? 'pending_review' : 'draft' };
    try { localStorage.removeItem(key()); } catch { /* private mode */ }
    finish(); config.onSave(payload, submit);
  }
  function command(name, value) {
    field('ke-content').focus();
    if (range) { const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range); }
    document.execCommand(name, false, value || null);
    onEdit();
  }
  function open(options) {
    config = options; beforeFocus = document.activeElement; active = true; session++; changed = false; range = null;
    document.getElementById('notice').classList.remove('show');
    model = initial(options.doc, options.catalogs, options.preferredCatalog);
    let recovered = false;
    try {
      const cached = JSON.parse(localStorage.getItem(key()));
      if (cached?.model && Date.now() - cached.at < 7 * 24 * 3600 * 1000) {
        model = { ...model, ...cached.model, html: sanitize(cached.model.html), attachments: (cached.model.attachments || []).map(file => ({ ...file, status: 'ready' })) };
        if (!options.catalogs.includes(model.catalog)) model.catalog = options.catalogs[0];
        recovered = true;
      }
    } catch { /* unavailable local cache */ }
    document.body.style.overflow = 'hidden';
    overlay().innerHTML = `<div class="kb-mask kb-dialog-mask ke-mask"><section class="ke-editor" role="dialog" aria-modal="true" aria-labelledby="ke-heading"><header class="ke-header"><div><h2 id="ke-heading">${options.doc ? '编辑文档' : '新建文档'}</h2><span class="ke-draft-label">草稿</span>${options.doc?.status === 'published' ? '<span class="ke-revision">修订后审核发布，当前版本继续可用</span>' : ''}</div><div><span id="ke-save-status">${recovered ? '已恢复本机草稿' : '尚未修改'}</span><button class="kb-icon-btn" data-ke-action="close" aria-label="关闭">×</button></div></header><div class="ke-scroll">${recovered ? '<div class="ke-recovery">已恢复上次未完成的草稿<span>仅保存在当前浏览器中</span></div>' : ''}<div class="ke-layout"><div class="ke-writing"><div class="kb-field ke-title"><label for="ke-title">文档标题</label><input id="ke-title" maxlength="100" placeholder="清楚描述主题，例如：项目交付验收检查清单" value="${esc(model.title)}"></div><div class="ke-basic"><div class="kb-field"><label for="ke-catalog">所属目录</label><select id="ke-catalog">${options.catalogs.map(name => `<option ${name === model.catalog ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></div><div class="kb-field"><label for="ke-type">文档类型</label><select id="ke-type">${Object.entries(types).map(([value, name]) => `<option value="${value}" ${value === model.type ? 'selected' : ''}>${name}</option>`).join('')}</select></div></div><section class="ke-content-section"><div class="ke-section-head"><label id="ke-content-label">文档内容</label><button class="ke-text-button" data-ke-action="template">插入模板</button></div><div class="ke-toolbar" role="toolbar" aria-label="正文编辑工具"><select id="ke-format" aria-label="段落格式"><option value="p">正文</option><option value="h2">一级标题</option><option value="h3">二级标题</option></select><button data-ke-command="bold" aria-label="加粗"><b>B</b></button><button data-ke-command="italic" aria-label="斜体"><i>I</i></button><span></span><button data-ke-command="insertUnorderedList" aria-label="项目列表">• 列表</button><button data-ke-command="insertOrderedList" aria-label="编号列表">1. 编号</button><button data-ke-action="checklist">☐ 清单</button><button data-ke-action="table">表格</button><button data-ke-action="link">链接</button><button data-ke-action="image">图片</button><span></span><button data-ke-command="undo" aria-label="撤销">↶</button><button data-ke-command="redo" aria-label="重做">↷</button></div><div class="ke-inline-prompt" hidden></div><div id="ke-content" class="ke-content" contenteditable="true" role="textbox" aria-labelledby="ke-content-label" aria-multiline="true" data-placeholder="记录适用场景、办理步骤和注意事项，也可以从模板开始。">${model.html}</div><div class="ke-content-foot"><span>支持表格、图片和链接</span><span id="ke-word-count"></span></div></section><section class="ke-attachment-section"><div class="ke-section-head"><h3>附件</h3><span>选填 / 最多 8 个</span></div><label class="ke-dropzone" tabindex="0" role="button" aria-label="选择附件">＋ 点击选择或拖拽文件<input id="ke-files" type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg,.webp" hidden><small>PDF、Word、Excel、图片等，单个不超过 20 MB</small></label><div id="ke-attachments"></div><p class="ke-local-note">原型仅保留附件信息，文件不会上传；解析状态为演示。</p></section></div><aside class="ke-information"><section><div class="ke-section-head"><h3>知识整理</h3><span>选填</span></div><div class="kb-field"><label for="ke-summary">文档摘要</label><textarea id="ke-summary" rows="3" maxlength="200" placeholder="用一两句话说明这篇文档能解决什么问题">${esc(model.summary)}</textarea><small>用于文档列表；不填时提取正文开头。</small></div><div class="kb-field"><label for="ke-tags">文档标签</label><input id="ke-tags" maxlength="100" placeholder="例如：项目、验收、操作指南" value="${esc(model.tags)}"><small>用逗号分隔，最多保留 8 个标签。</small></div></section><details class="ke-more-settings"><summary>更多设置</summary><div class="kb-field"><label for="ke-visibility">可见范围</label><select id="ke-visibility"><option value="inherit" ${model.visibility === 'inherit' ? 'selected' : ''}>继承目录权限（推荐）</option><option value="department" ${model.visibility === 'department' ? 'selected' : ''}>指定部门</option><option value="all" ${model.visibility === 'all' ? 'selected' : ''}>全体员工</option></select></div><div class="kb-field" id="ke-department-field" ${model.visibility !== 'department' ? 'hidden' : ''}><label for="ke-department">可见部门</label><select id="ke-department">${['项目交付部', '市场销售部', '人事行政部'].map(name => `<option ${name === model.department ? 'selected' : ''}>${name}</option>`).join('')}</select></div><div class="kb-field"><label for="ke-expires">有效期至</label><input id="ke-expires" type="date" value="${esc(model.expires)}"><small>留空表示不设期限。</small></div><div class="kb-field"><label for="ke-source">来源说明</label><input id="ke-source" maxlength="100" placeholder="例如：制度文件、项目复盘会议" value="${esc(model.sourceNote)}"></div><p class="ke-local-note">权限和有效期用于原型展示，真实访问控制需接入业务系统。</p></details><section class="ke-publish-guide"><h3>保存与发布</h3><ol><li>保存草稿，可稍后继续补充</li><li>提交审核，由目录管理员核对</li><li>审核通过，团队可阅读与检索</li></ol><p>作者：林嘉宁<br>来源：${esc(options.doc?.source || '手动创建')}</p></section></aside></div><input id="ke-image" type="file" accept="image/png,image/jpeg,image/webp" hidden></div><footer class="ke-footer"><div><span>草稿可暂不填写完整</span><p id="ke-error" role="alert"></p></div><div><button class="kb-btn" data-ke-action="close">取消</button><button class="kb-btn" data-ke-action="save">保存草稿</button><button class="kb-btn primary" data-ke-action="submit">提交审核</button></div></footer></section></div>`;
    attachments(); count(); field('ke-title').focus();
  }
  overlay()?.addEventListener('input', event => { if (active && event.target.closest('.ke-editor')) onEdit(); });
  overlay()?.addEventListener('change', event => {
    if (!active) return;
    if (event.target.id === 'ke-files') { attach(event.target.files); event.target.value = ''; return; }
    if (event.target.id === 'ke-image') {
      const file = event.target.files[0];
      if (!file) return;
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) { error('请选择不超过 2 MB 的 PNG、JPEG 或 WebP 图片。'); return; }
      const token = session, reader = new FileReader();
      reader.onload = () => { if (active && token === session) command('insertHTML', `<img src="${reader.result}" alt="文档插图"><p><br></p>`); };
      reader.readAsDataURL(file); return;
    }
    if (event.target.id === 'ke-format') { command('formatBlock', event.target.value); return; }
    if (event.target.id === 'ke-visibility') field('ke-department-field').hidden = event.target.value !== 'department';
    if (event.target.closest('.ke-editor')) onEdit();
  });
  document.addEventListener('selectionchange', () => {
    if (!active) return;
    const selection = getSelection();
    if (selection.rangeCount && field('ke-content')?.contains(selection.anchorNode)) range = selection.getRangeAt(0).cloneRange();
  });
  overlay()?.addEventListener('mousedown', event => { if (event.target.closest('[data-ke-command]')) event.preventDefault(); });
  overlay()?.addEventListener('paste', event => {
    if (active && event.target.closest('#ke-content')) { event.preventDefault(); command('insertText', event.clipboardData.getData('text/plain')); }
  });
  overlay()?.addEventListener('dragover', event => { if (active && event.target.closest('.ke-dropzone')) { event.preventDefault(); event.target.closest('.ke-dropzone').classList.add('dragging'); } });
  overlay()?.addEventListener('dragleave', event => event.target.closest('.ke-dropzone')?.classList.remove('dragging'));
  overlay()?.addEventListener('drop', event => { if (active && event.target.closest('.ke-dropzone')) { event.preventDefault(); event.target.closest('.ke-dropzone').classList.remove('dragging'); attach(event.dataTransfer.files); } });
  overlay()?.addEventListener('click', event => {
    if (!active) return;
    const target = event.target.closest('[data-ke-action], [data-ke-command]');
    if (!target) return;
    event.stopPropagation();
    if (target.dataset.keCommand) { command(target.dataset.keCommand); return; }
    switch (target.dataset.keAction) {
      case 'close': requestClose(); break;
      case 'continue': overlay().querySelector('.ke-guard').remove(); field('ke-content').focus(); break;
      case 'discard': discard(); break;
      case 'keep':
        if (!autosave()) { overlay().querySelector('.ke-guard').remove(); error('本机草稿保存失败，请使用保存草稿。'); break; }
        finish(); config.onClose(); break;
      case 'save': save(false); break;
      case 'submit': save(true); break;
      case 'remove-file': model.attachments = model.attachments.filter(file => file.id !== target.dataset.id); attachments(); onEdit(); break;
      case 'template':
        collect();
        if (plain(model.html) || model.html.includes('<img')) guard('替换当前正文？', '插入模板会替换现有正文，标题和其他信息会保留。', '<button class="kb-btn" data-ke-action="continue">保留正文</button><button class="kb-btn primary" data-ke-action="confirm-template">替换为模板</button>');
        else { field('ke-content').innerHTML = templates[model.type]; range = null; onEdit(); }
        break;
      case 'confirm-template': field('ke-content').innerHTML = templates[model.type]; range = null; overlay().querySelector('.ke-guard').remove(); onEdit(); break;
      case 'table': command('insertHTML', '<table><tbody><tr><th>项目</th><th>说明</th></tr><tr><td>填写项目</td><td>填写说明</td></tr><tr><td>填写项目</td><td>填写说明</td></tr></tbody></table><p><br></p>'); break;
      case 'checklist': command('insertHTML', '<ul><li>☐ 核对资料完整性</li><li>☐ 确认负责人和截止时间</li></ul>'); break;
      case 'image': field('ke-image').click(); break;
      case 'link':
        overlay().querySelector('.ke-inline-prompt').hidden = false;
        overlay().querySelector('.ke-inline-prompt').innerHTML = '<label>链接地址<input id="ke-link-url" placeholder="https://"></label><button class="kb-btn" data-ke-action="cancel-link">取消</button><button class="kb-btn primary" data-ke-action="insert-link">插入链接</button>';
        field('ke-link-url').focus(); break;
      case 'cancel-link': overlay().querySelector('.ke-inline-prompt').hidden = true; break;
      case 'insert-link': {
        const url = field('ke-link-url').value.trim();
        if (!/^https?:\/\//i.test(url)) { error('请填写以 http:// 或 https:// 开头的链接。'); break; }
        const text = range?.toString() || url;
        command('insertHTML', `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`);
        overlay().querySelector('.ke-inline-prompt').hidden = true; break;
      }
    }
  });
  overlay()?.addEventListener('keydown', event => {
    if (!active) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (overlay().querySelector('.ke-guard')) overlay().querySelector('.ke-guard').remove(); else requestClose(); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); autosave(); }
    if (event.target.matches('.ke-dropzone') && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); field('ke-files').click(); }
    if (event.key === 'Tab') {
      const root = overlay().querySelector('.ke-guard') || overlay().querySelector('.ke-editor');
      const items = [...root.querySelectorAll('button, input, select, textarea, summary, [contenteditable], [tabindex="0"]')].filter(node => !node.disabled && node.getClientRects().length);
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); event.stopPropagation(); items.at(-1)?.focus(); }
      else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); event.stopPropagation(); items[0]?.focus(); }
    }
  });
  window.addEventListener('beforeunload', event => { if (active && changed && !autosave()) { event.preventDefault(); event.returnValue = ''; } });
  globalThis.KnowledgeEditor = { open, requestClose, sanitize, get active() { return active; } };
})();
