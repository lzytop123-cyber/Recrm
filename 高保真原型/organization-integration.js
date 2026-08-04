Object.assign(state,{ticketDepartmentFilter:'全部部门'});

function organizationDepartmentOptions(includeAll=true){
  const names=orgDepartments.map(d=>d.name);
  return `${includeAll?'<option value="全部部门">全部部门</option>':''}${names.map(name=>`<option value="${esc(name)}" ${state.ticketDepartmentFilter===name?'selected':''}>${esc(name)}</option>`).join('')}`;
}
function normalizeOrganizationDepartment(name){
  const aliases={'技术支持':'技术交付中心','项目部':'技术交付中心','新媒体部':'新媒体中心','品宣组':'新媒体中心','培训部':'讲师部','教研组':'讲师部','业务部':'市场销售中心'};
  return aliases[name]||name;
}

// 历史演示数据按当前组织口径展示；新工单直接保存组织架构中的正式部门名称。
tickets.forEach(ticket=>{ticket[2]=normalizeOrganizationDepartment(ticket[2]);ticket[3]=normalizeOrganizationDepartment(ticket[3])});

function pageTicketsFromOrganization(){
  const cols=['待接收','处理中','待确认','已关闭'],selected=state.ticketDepartmentFilter;
  const visible=tickets.map((t,i)=>({t,i})).filter(({t})=>selected==='全部部门'||t[3]===selected);
  return head('协作工单','项目任务跨部门协作统一形成工单，由时限规则、处理结果和发起人验收推动闭环。','<button class="button" data-action="sla-rules">工单时限规则</button><button class="button primary" data-action="new-ticket">＋ 发起工单</button>')+
  `<section class="ticket-kpis"><div><small>接近时限</small><b>2</b></div><div><small>已逾期</small><b style="color:var(--down)">1</b></div><div><small>待发起人确认</small><b>${state.ticketStatus.filter(x=>x==='待确认').length}</b></div><div><small>本月满意度</small><b>4.7 / 5</b></div></section><div class="toolbar"><div class="filters"><select class="select"><option>全部项目</option><option>星河制造数据平台</option><option>北辰账号矩阵</option></select><select class="select" id="ticketDepartmentFilter" aria-label="按承接部门筛选">${organizationDepartmentOptions(true)}</select></div><span class="demo-chip">部门来自组织架构 · 调整后自动同步</span></div><section class="ticket-board">${cols.map((c,ci)=>{const rows=visible.filter(({i})=>state.ticketStatus[i]===c).sort((a,b)=>b.i-a.i);return `<div class="ticket-column reveal"><div class="column-head"><b><i style="background:${['var(--ink-3)','var(--accent)','var(--warn)','var(--up)'][ci]}"></i>${c}</b><span>${rows.length}张</span></div>${rows.map(({t,i})=>`<article class="ticket-card" data-ticket="${i}"><div class="ticket-id"><span>${t[0]}</span>${status(t[4],t[4]==='高'?'bad':t[4]==='中'?'warn':'')}</div><h3>${t[1]}</h3><div class="ticket-tags"><span class="status">${t[2]}</span><span class="status info">${t[3]}</span></div><div class="ticket-link">${t[6]||['RW-072301','SCH-072298','PJ-260721','RW-072286','RW-072268','HT-260724'][i]||'未关联'}</div><div class="ticket-footer"><span class="mini-avatar">${t[7]||['许','周','财','林','教','综'][i]||'我'}</span><span style="color:${t[5].includes('逾期')?'var(--down)':''}">${c==='已关闭'?'已关闭 · 可重开':t[5]}</span></div></article>`).join('')}</div>`}).join('')}</section>`;
}
pages.tickets=pageTicketsFromOrganization;

function ticketModal(taskIndex=null){
  const task=taskIndex===null?null:projectTasks[taskIndex],departments=orgDepartments.filter(d=>d.name!=='经营管理层');
  showModal('发起协作','创建跨部门工单',section(1,'业务关联',`<div class="form-grid"><div class="field"><label>关联项目</label><select id="ticketProject"><option>${task?task[2]:'星河制造数据平台'}</option><option>不关联项目</option></select></div><div class="field"><label>关联项目任务</label><select id="ticketTask"><option>${task?task[0]+' · '+task[1]:'RW-072301 · 完成数据接口联调'}</option><option>不关联任务</option></select></div></div>`)+section(2,'请求内容',`<div class="form-grid"><div class="field full"><label>工单标题 <em>*</em></label><input id="ticketTitle" value="${task?'协作支持：'+task[1]:'客户方案需要技术评估'}"></div><div class="field"><label>承接部门 <em>*</em></label><select id="ticketDepartment">${departments.map(d=>`<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('')}</select><small>部门来自组织架构，组织调整后自动同步。</small></div><div class="field"><label>工单分类 <em>*</em></label><select><option>项目交付工单</option><option>普通跨部门协作</option><option>紧急客户或生产问题</option></select><small>分类决定响应、完成和升级规则。</small></div><div class="field"><label>优先级 <em>*</em></label><select id="ticketPriority"><option>中</option><option>高</option><option>低</option></select></div><div class="field"><label>期望完成时间 <em>*</em></label><input type="datetime-local" value="2026-07-24T18:00"></div><div class="field full"><label>期望结果与验收标准 <em>*</em></label><textarea id="ticketExpectation">请提供可验收的处理结果，并说明差异和风险。</textarea></div></div>`)+section(3,'责任与时限',`<div class="form-grid"><div class="field"><label>验收人 <em>*</em></label><select><option>王洋 · 发起部门</option></select></div><div class="field"><label>当前时限规则</label><input value="2个工作小时内响应 · 完成时间按项目计划" disabled></div></div>`),'<button class="button" value="cancel">保存草稿</button><button class="button primary" id="confirmTicket">提交工单</button>');
  $('#confirmTicket').onclick=e=>{e.preventDefault();const title=$('#ticketTitle').value.trim(),expectation=$('#ticketExpectation').value.trim();if(!title||!expectation)return toast('工单信息未完整','标题和期望结果与验收标准均为必填项。');const taskValue=$('#ticketTask').value,projectValue=$('#ticketProject').value,link=taskValue==='不关联任务'?(projectValue==='不关联项目'?'未关联':projectValue):taskValue.split(' · ')[0],id=`TK-0723${String(tickets.length+1).padStart(2,'0')}`;tickets.push([id,title,'市场销售中心',$('#ticketDepartment').value,$('#ticketPriority').value,'等待接单',link,'王']);state.ticketStatus.push('待接收');$('#modal').close();render('tickets');toast('工单已提交',`${id} 已显示在“待接收”列，并已通知承接部门。`)};
}

const organizationBindBase=bindPage;
bindPage=function(){organizationBindBase();$('#ticketDepartmentFilter')?.addEventListener('change',e=>{state.ticketDepartmentFilter=e.target.value;render('tickets')})};
if(state.view==='tickets')render('tickets');
