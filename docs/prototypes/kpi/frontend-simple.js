'use strict';
// Independent, synthetic prototype; no network, production data or payroll writes.
(function(){
const base=typeof module!=='undefined'&&module.exports?require('./frontend-flow.js'):{initialState,defaultPlan,totalScore,coefficient,validateScores,systemPoints,evidenceItems,METRICS,TEMPLATE_ROWS};
const templateApi=typeof module!=='undefined'&&module.exports?require('./template-workflow.js'):globalThis.TemplateWorkflow;
const personnelApi=typeof module!=='undefined'&&module.exports?require('./personnel-matching.js'):globalThis.PersonnelMatching;
const PEOPLE=['张明','王芳','李强'];
const PAST_PERIODS=[
  {id:'2026-08',label:'2026年8月',rows:[
    {id:'p8-1',name:'张明',department:'市场部',role:'市场业务',manager:'李岚',score:'91',status:'已完成'},
    {id:'p8-2',name:'王芳',department:'市场部',role:'市场业务',manager:'李岚',score:'86',status:'已完成'},
    {id:'p8-3',name:'李强',department:'市场部',role:'市场业务',manager:'李岚',score:'79',status:'已完成'},
    {id:'p8-4',name:'陈浩',department:'AI技术运维',role:'运维专员',manager:'周宁',score:'88',status:'已完成'},
    {id:'p8-5',name:'许航',department:'内容制作团队',role:'内容专员',manager:'陆可',score:'84',status:'已完成'}
  ]},
  {id:'2026-07',label:'2026年7月',rows:[
    {id:'p7-1',name:'张明',department:'市场部',role:'市场业务',manager:'李岚',score:'83',status:'已完成'},
    {id:'p7-2',name:'王芳',department:'市场部',role:'市场业务',manager:'李岚',score:'90',status:'已完成'},
    {id:'p7-3',name:'李强',department:'市场部',role:'市场业务',manager:'李岚',score:'76',status:'已完成'},
    {id:'p7-4',name:'陈浩',department:'AI技术运维',role:'运维专员',manager:'周宁',score:'92',status:'已完成'},
    {id:'p7-5',name:'许航',department:'内容制作团队',role:'内容专员',manager:'陆可',score:'81',status:'已完成'}
  ]}
];
const DEPARTMENT_ROLES={
  '市场部':['市场业务'],
  'AI技术运维':['运维专员'],
  '内容制作团队':['内容专员'],
  '品宣团队':['品宣专员'],
  '直播团队':['主播','投手'],
  '培训部':['业务新人','职能新人'],
  '讲师部':['讲师']
};
const SCORE_TYPES={quantity:'数量型',ratio:'比例型',tier:'分档型',subjective:'主观评分型',bonus:'加减分型',veto:'一票否决型'};
const INDICATOR_LIBRARY={
  '市场部':[
    {id:'market-leads',name:'有效线索',type:'quantity',target:'9',unit:'条',source:'CRM客户与线索',evidence:'客户画像、联系人及沟通记录',formula:'达到目标得满分；不足按完成比例计分，最高不超过满分'},
    {id:'market-sign',name:'签约客户',type:'quantity',target:'4',unit:'家',source:'CRM签约记录',evidence:'已确认签约单及客户台账',formula:'按有效签约数量分档计分，同一客户当月去重'},
    {id:'market-follow',name:'跟进及时率',type:'ratio',target:'95',unit:'%',source:'CRM跟进记录',evidence:'系统自动获取，无需员工重复提交',formula:'达到95%得满分；低于目标按比例计分'}
  ],
  'AI技术运维':[
    {id:'ops-availability',name:'系统可用率',type:'ratio',target:'99.9',unit:'%',source:'运维监控平台',evidence:'监控报表与异常记录',formula:'达到99.9%得满分；重大责任事故按制度扣分'},
    {id:'ops-response',name:'故障响应及时率',type:'ratio',target:'95',unit:'%',source:'工单系统',evidence:'工单受理及关闭时间',formula:'按及时关闭工单比例分档计分'}
  ],
  '内容制作团队':[
    {id:'content-output',name:'内容交付数量',type:'quantity',target:'20',unit:'条',source:'内容任务台账',evidence:'已验收内容链接或任务记录',formula:'达到目标得满分；仅统计验收通过内容'},
    {id:'content-quality',name:'内容质量评分',type:'subjective',target:'90',unit:'分',source:'主管评分',evidence:'质量评分表与修改记录',formula:'主管按准确性、表达和交付质量评分'}
  ],
  '品宣团队':[
    {id:'brand-plan',name:'品牌项目交付',type:'tier',target:'按计划完成',unit:'项',source:'项目台账',evidence:'方案、交付物及验收记录',formula:'按完成质量和时间分档计分'},
    {id:'brand-risk',name:'品牌风险事件',type:'veto',target:'0',unit:'次',source:'舆情与审批记录',evidence:'事件调查及处理结论',formula:'触发经确认的重大品牌风险时，本项为0分'}
  ],
  '直播团队':[
    {id:'live-sales',name:'直播成交额',type:'quantity',target:'100000',unit:'元',source:'直播平台数据',evidence:'平台结算与订单明细',formula:'按目标完成率计分，退款订单不计入'},
    {id:'live-compliance',name:'直播合规',type:'veto',target:'无重大违规',unit:'项',source:'直播巡检记录',evidence:'巡检记录与违规处理单',formula:'触发重大违规时按制度判定不合格'}
  ],
  '培训部':[
    {id:'training-stage',name:'阶段任务完成度',type:'tier',target:'完成本阶段任务',unit:'项',source:'培训任务台账',evidence:'任务成果及带教确认',formula:'按第5天、第1月或第3月阶段标准分档评分'}
  ],
  '讲师部':[
    {id:'lecturer-delivery',name:'课程交付完成率',type:'ratio',target:'100',unit:'%',source:'排课与交付记录',evidence:'排课、签到及课程交付记录',formula:'按已完成课程占计划课程比例计分'},
    {id:'lecturer-satisfaction',name:'学员满意度',type:'ratio',target:'90',unit:'%',source:'课后评价问卷',evidence:'有效问卷汇总，剔除无效评价',formula:'达到90%得满分；低于目标按分档计分'},
    {id:'lecturer-quality',name:'授课质量',type:'subjective',target:'优秀',unit:'等级',source:'教学负责人评分',evidence:'听课记录与改进反馈',formula:'按内容准确性、表达、互动和课堂管理评分'}
  ]
};
const need=(ok,text)=>{if(!ok)throw new Error(text);};
function createState(){return {version:5,role:'hr',page:'overview',selectedId:null,templateViewId:null,launched:false,periodEnded:false,records:[],batches:[],focusBatchId:null,historyPeriod:'2026-08',launchDraft:{templateIds:null},migrationNote:'',templateState:templateApi.createTemplateState()};}
function record(name,settings,template,personSnapshot=null,batchId=null){
  const r=base.initialState();
  const signed=template.metrics.find(x=>x.name.includes('签约客户')),signedTarget=Number((signed?.target.match(/\d+/)||[])[0])||4;
  Object.assign(r,{id:personSnapshot?.id||name,name,batchId,personSnapshot:personSnapshot||{id:name,name,department:template.department,role:template.role,manager:'李岚',adjustmentType:'automatic'},stage:1,standard:{id:template.id,name:template.name,signedTarget,version:template.version},standardApproved:true,plan:{...base.defaultPlan(),...settings,employee:name},reviewRequired:settings.reviewRequired===true,preflight:true,periodEnded:false});
  base.evidenceItems(r);return r;
}
function log(s,r,message){r.log.unshift({message,by:{hr:'HR · 陈悦',manager:'主管 · 李岚',employee:'员工 · '+r.name}[s.role]||'系统',at:new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})});}
function normalizeLaunchBatches(s,p){
  if(Array.isArray(p.batches)&&p.batches.length)return p.batches;
  const hasSnapshots=Array.isArray(p.personnel)&&p.personnel.length;
  if(!hasSnapshots)need(Array.isArray(p.employees)&&p.employees.every(name=>PEOPLE.includes(name)),'请选择模板范围内的有效考核员工。');
  const personnel=hasSnapshots?p.personnel:(p.employees||[]).map(name=>({id:name,name,department:'市场部',role:'市场业务',manager:'李岚',adjustmentType:'automatic'}));
  return [{templateId:p.templateId,personnel}];
}
function launch(s,p){
  need(s.role==='hr','仅HR可发起考核。');need(!s.launched,'本期已发起，不能重复发起。');
  const dates=[p.dataDue,p.scoreDue,...(p.reviewRequired?[p.reviewDue]:[]),p.resultDue];
  need(dates.every(v=>typeof v==='string'&&/^2026-10-(0[1-9]|[12][0-9]|3[01])$/.test(v)),'请设置9月考核结束后的有效10月截止日期。');
  need(dates.every((v,i)=>i===0||v>=dates[i-1]),'截止日应按员工提交、主管评分、可选HR复核、员工确认排序。');
  const available=templateApi.availableForLaunch(s.templateState);
  const batchInputs=normalizeLaunchBatches(s,p);
  need(batchInputs.length,'请至少选择1个已发布模板。');
  const records=[],batches=[],seen=new Set();
  batchInputs.forEach((batch,index)=>{
    const template=available.find(x=>x.id===(batch.templateId||available[0]?.id));
    need(template,'请选择已发布且有效的考核模板。');
    const personnel=batch.personnel||[];
    need(personnel.length&&personnel.every(x=>x?.id&&x?.name),'请为'+template.department+'选择有效考核员工。');
    personnel.forEach(person=>{need(!seen.has(person.id),person.name+'不能同时出现在多个考核批次中。');seen.add(person.id);});
    const batchId='batch-'+(index+1);
    batches.push({id:batchId,templateId:template.id,templateName:template.name,department:template.department,role:template.role,count:personnel.length});
    personnel.forEach(person=>records.push(record(person.name,{...p,selfDue:p.dataDue,reviewDue:p.reviewRequired?p.reviewDue:p.scoreDue},template,person,batchId)));
  });
  s.records=records;s.batches=batches;s.launched=true;s.selectedId=s.records[0].id;s.page='overview';s.launchDraft={templateIds:null};
  s.records.forEach(r=>log(s,r,'HR已发起考核；系统检查通过，目标与截止日期已在本地演示中通知员工（不代表员工已签收）。'));
}
function deriveBatches(records){
  const map=new Map();
  (records||[]).forEach(r=>{
    const key=r.standard?.id||r.personSnapshot?.department||'unknown';
    if(!map.has(key))map.set(key,{id:'batch-'+map.size+1,templateId:r.standard?.id||key,templateName:r.standard?.name||'历史模板',department:r.personSnapshot?.department||'未分组',role:r.personSnapshot?.role||'—',count:0});
    map.get(key).count+=1;r.batchId=r.batchId||map.get(key).id;
  });
  return [...map.values()];
}
function ensureDemoTemplates(templateState){
  const state=templateState||templateApi.createTemplateState();
  const fresh=templateApi.createTemplateState().templates;
  fresh.forEach(t=>{if(!state.templates.some(x=>x.id===t.id))state.templates.push(JSON.parse(JSON.stringify(t)));});
  return state;
}
function migrate(old){
  if(old?.version===5&&Array.isArray(old.records)){old.batches=old.batches||deriveBatches(old.records);old.launchDraft=old.launchDraft||{templateIds:null};old.focusBatchId=old.focusBatchId||null;old.templateState=ensureDemoTemplates(old.templateState);old.templateViewId=old.templateViewId||null;return old;}
  if(old?.version===4&&Array.isArray(old.records)){old.version=5;old.batches=deriveBatches(old.records);old.launchDraft={templateIds:null};old.focusBatchId=null;old.templateState=ensureDemoTemplates(old.templateState);old.templateViewId=old.templateViewId||null;return old;}
  const s=createState();if(!old||old.version!==3)return s;
  s.role=['hr','manager','employee'].includes(old.role)?old.role:'hr';
  if(old.stage<1){s.migrationNote='旧版尚未发起。本次可多选已发布模板，按部门批量发起；旧版缓存保留不删除。';return s;}
  const r={...base.initialState(),...JSON.parse(JSON.stringify(old)),id:'张明',name:'张明',plan:{...base.defaultPlan(),...old.plan},reviewRequired:true};
  base.evidenceItems(r);
  if(r.stage===1||r.stage===2){
    r.stage=1;r.evidence=false;
    r.evidenceItems.forEach(x=>{if(x.status==='pending')x.status='ready';});
  }
  if(r.stage===6){r.stage=7;r.resultConfirmed=true;}
  s.records=[r];s.batches=deriveBatches(s.records);s.launched=true;s.selectedId=r.id;s.periodEnded=old.periodEnded||old.stage>1;
  s.migrationNote='已接续旧版进度和材料。原有HR复核要求保留；未提交的材料与说明现在合并提交。';
  return s;
}
function act(s,id,action,p={}){
  const r=s.records.find(x=>x.id===id);need(r,'请选择考核员工。');
  const who=role=>need(s.role===role,'请切换到对应处理人的演示身份。');
  const at=stage=>need(r.stage===stage,'当前环节不支持该操作。');
  let message='';
  if(action==='period-end'){
    who('hr');need(!s.periodEnded,'已进入期末。');s.periodEnded=true;s.records.forEach(x=>x.periodEnded=true);
    s.records.forEach(x=>log(s,x,'演示时间推进至9月期末，带入合成记录。'));return;
  }
  if(action==='draft'||action==='submit'){
    who('employee');at(1);need(s.periodEnded,'尚未到期末，当前可查看目标。');
    const items=JSON.parse(JSON.stringify(base.evidenceItems(r)));
    for(const [itemId,value] of Object.entries(p.materials||{})){
      const item=items.find(x=>x.id===itemId);
      need(item&&['missing','ready','returned'].includes(item.status),'仅能补充缺失或退回的材料。');
      need(typeof value==='string','材料应为文字说明。');
      item.value=value.trim();item.status=item.value?'ready':'missing';
    }
    const note=typeof p.note==='string'?p.note.trim():r.selfNote;
    if(Array.isArray(p.actuals)){
      need(p.actuals.length===base.METRICS.length,'请按指标填写实际完成。');
      if(action==='submit')need(p.actuals.every(x=>String(x).trim()),'请填写每项指标的实际完成，没有完成可填 0。');
      r.actuals=p.actuals.map(x=>String(x??'').trim());
    }
    if(action==='submit'){
      need(items.every(x=>x.value.trim()&&x.status!=='returned'),'请补齐缺失或退回的材料。');
      need(note,'请填写本月工作说明。');need(p.checked===true,'请先确认已填写实际与材料。');
      items.forEach(x=>x.status='pending');r.stage=3;r.evidence=true;
    }
    r.evidenceItems=items;r.selfNote=note;r.verified=false;
    message=action==='submit'?'员工已提交各项实际完成和补充材料，待主管评分。':'员工草稿已保存，尚未提交。';
  }else if(action==='return-item'){
    who('manager');at(3);need(p.note?.trim(),'请写明该项目需要补充什么。');
    const item=base.evidenceItems(r).find(x=>x.id===p.itemId);need(item,'请选择具体材料。');
    item.status='returned';item.returnReason=p.note.trim();r.stage=1;r.evidence=false;r.verified=false;
    message='主管退回'+item.name+'：'+item.returnReason+'；其他材料与说明保留。';
  }else if(action==='score'||action==='score-draft'){
    who('manager');at(3);
    const scoredAll=Array.isArray(p.scores)&&p.scores.length===base.METRICS.length;
    if(scoredAll)need(p.scores.every((x,i)=>x!==''&&x!==null&&Number.isFinite(Number(x))&&Number(x)>=0&&Number(x)<=base.METRICS[i].max),'请为每项填写得分，且不超过该项满分。');
    else need(base.validateScores(p.scores),'请完整填写5项评分，且在对应满分范围内。');
    need(p.note?.trim(),'请填写评分依据。');
    if(Array.isArray(p.actuals)&&p.actuals.length===base.METRICS.length){
      need(p.actuals.every(x=>String(x).trim()),'实际完成还没填齐。请让员工补充，或由主管改填后再打分。');
      const prev=(r.actuals||[]).join('\n');
      r.actuals=p.actuals.map(x=>String(x).trim());
      if(prev&&prev!==r.actuals.join('\n'))r.actualCorrected=true;
    }
    if(action==='score'){
      need(p.checked===true,'请先确认已核对员工填写的实际。');
      need(r.evidence&&base.evidenceItems(r).every(x=>x.value.trim()&&x.status!=='returned'),'材料未齐，不能提交评分。');
      r.verified=true;r.evidenceItems.forEach(x=>x.status='approved');r.stage=r.reviewRequired?4:5;
    }
    if(scoredAll){r.itemScores=p.scores.map(Number);r.scores=r.itemScores.slice(-5);}
    else r.scores=p.scores.map(Number);
    r.scoreNote=p.note.trim();
    message=action==='score-draft'?'主管评分草稿已保存。':r.reviewRequired?'主管已核对实际并提交评分，待HR复核。':'主管已按满分评分，结果已告知员工。';
  }else if(action==='review'){
    who('hr');at(4);need(r.verified&&base.totalScore(r)!==null,'材料与评分未完整。');r.stage=5;message='HR复核通过，结果已告知员工。';
  }else if(action==='return-score'){
    who('hr');at(4);need(p.note?.trim(),'请填写退回理由。');r.stage=3;r.returnNote=p.note.trim();message='HR退回主管评分：'+r.returnNote;
  }else if(action==='confirm'){
    who('employee');at(5);need(r.appeal?.status!=='pending','申诉处理后才能确认。');need(r.verified&&base.totalScore(r)!==null,'结果尚未完整。');
    r.resultConfirmed=true;r.stage=7;message='员工已确认结果；系统自动锁定材料、分数与规则，考核完成。';
  }else if(action==='appeal'){
    who('employee');at(5);need(r.appeal?.status!=='pending','已有待处理申诉。');need(p.note?.trim(),'请填写争议指标与依据。');r.appeal={status:'pending',reason:p.note.trim()};message='员工提交申诉，交HR复核，不自动确认。';
  }else if(action==='resolve'){
    who('hr');at(5);need(r.appeal?.status==='pending','没有待处理申诉。');need(p.note?.trim(),'请填写复核依据。');r.appeal.status='resolved';r.appeal.resolution=p.note.trim();r.revision++;message='HR复核申诉并维持原评分，等待员工确认。';
  }else throw new Error('未知操作。');
  log(s,r,message);return message;
}
const api={createState,launch,migrate,act};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(typeof document==='undefined')return;
const KEY='kpi-flow-simple-v5';
let state=createState();
try{const cached=localStorage.getItem(KEY);state=cached?migrate(JSON.parse(cached)):migrate(JSON.parse(localStorage.getItem('kpi-flow-simple-v4')||localStorage.getItem('kpi-flow-v3')));}catch{}
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const el=id=>document.getElementById(id);
const button=(text,a,primary=false)=>'<button type="button" class="btn '+(primary?'primary':'')+'" data-simple-action="'+esc(a)+'">'+text+'</button>';
const tag=(text,color='blue')=>'<span class="tag '+color+'">'+esc(text)+'</span>';
const panel=(title,body)=>'<section class="panel"><div class="panelhead"><h2>'+title+'</h2></div>'+body+'</section>';
const notice=text=>'<div class="callout">'+text+'</div>';
const table=(headers,rows)=>'<div class="tablewrap"><table><thead><tr>'+headers.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
const active=()=>state.records.find(r=>r.id===state.selectedId)||state.records[0];
const phase=r=>r.stage===7?'已完成':r.stage===5?(r.appeal?.status==='pending'?'申诉处理中':'结果确认'):r.stage===4?'HR复核':r.stage===3?'主管评分':state.periodEnded?'员工提交':'考核进行中';
const owner=r=>r.stage===4||r.appeal?.status==='pending'?'hr':r.stage===3?'manager':'employee';
const roleName=role=>({hr:'HR · 陈悦',manager:'主管 · 李岚',employee:'员工'}[role]);
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state));}catch{toast('浏览器未能保存进度，请勿关闭页面。');}};
function toast(text){el('notice').textContent=text;el('notice').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>el('notice').classList.remove('show'),3500);}
function close(){el('overlay').innerHTML='';}
function dialog(title,body,footer){el('overlay').innerHTML='<div class="modal-mask"><section class="modal wide" role="dialog" aria-modal="true" aria-labelledby="simple-dialog-title"><div class="modalhead"><h2 id="simple-dialog-title">'+title+'</h2>'+button('关闭','close')+'</div>'+body+'<p class="error" id="simple-error" role="alert"></p><div class="modalfoot">'+footer+'</div></section></div>';document.querySelector('#overlay button')?.focus();}
function path(r){
  const steps=!state.launched
    ?['发起考核（可多部门）','员工各自提交','各部门主管并行评分',...(r?.reviewRequired?['HR复核']:[]),'结果确认','已完成']
    :['已发起','员工提交','主管评分',...(r?.reviewRequired?['HR复核']:[]),'结果确认','已完成'];
  const current=!state.launched?0:!state.periodEnded?0:r.stage===1?1:r.stage===3?2:r.stage===4?3:r.stage===5?steps.length-2:steps.length-1;
  return '<ol class="flow simple-flow">'+steps.map((name,i)=>'<li class="'+(i<current?'done':i===current?'active':'')+'" '+(i===current?'aria-current="step"':'')+'><span class="dot">'+(i<current?'✓':i+1)+'</span>'+name+'</li>').join('')+'</ol><p class="hintline">个人考核独立推进：各部门主管并行评分，不因其他人未提交而互相等待。</p>';
}
function summary(r){return table(['安排','内容'],[
  ['周期','2026年9月1日—9月30日'],['考核人员',esc(r.name)+' · '+esc(r.personSnapshot?.department||'市场部')+' / '+esc(r.personSnapshot?.role||'市场业务')+' · 主管'+esc(r.personSnapshot?.manager||'李岚')],['匹配方式',r.personSnapshot?.adjustmentType==='manual_include'?'HR手动纳入：'+esc(r.personSnapshot.adjustmentReason):'系统按模板范围自动匹配'],['考核模板',esc(r.standard?.name||'旧版演示模板')+' · V'+(r.standard?.version||1)],
  ['评分人 / 复核','李岚 / '+(r.reviewRequired?'陈悦（已启用）':'不启用常规HR复核；申诉由HR处理')],
  ['截止日期','员工提交 '+esc(r.plan.dataDue)+' → 主管评分 '+esc(r.plan.scoreDue)+(r.reviewRequired?' → HR复核 '+esc(r.plan.reviewDue):'')+' → 结果确认 '+esc(r.plan.resultDue)],
  ['目标通知','已在本地演示中通知，可随时查看；不要求每月重复签收']
]);}
function teamTable(filterBatchId){
  const rows=state.records.filter(r=>!filterBatchId||r.batchId===filterBatchId);
  return table(['员工','部门 / 批次','当前状态','当前处理人','操作'],rows.map(r=>[
    '<b>'+esc(r.name)+'</b><br><small class="muted">'+(r.personSnapshot?.adjustmentType==='manual_include'?'人工纳入':'自动匹配')+' · 主管'+esc(r.personSnapshot?.manager||'李岚')+'</small>',
    esc(r.personSnapshot?.department||'—')+' / '+esc(r.standard?.name||'—'),
    tag(phase(r),r.stage===7?'green':'blue'),
    r.stage===7?'无需处理':!state.periodEnded?'按期初目标工作':roleName(owner(r)),
    button(r.stage===7?'查看结果':'打开考核','record:'+r.id)
  ]));
}
function deptBoard(){
  const batches=state.batches.length?state.batches:deriveBatches(state.records);
  return table(['批次 / 部门','模板','人数','待员工提交','待主管评分','已完成','操作'],batches.map(b=>{
    const rows=state.records.filter(r=>r.batchId===b.id||(!r.batchId&&r.standard?.id===b.templateId));
    const pendingSelf=rows.filter(x=>x.stage===1).length,pendingMgr=rows.filter(x=>x.stage===3).length,done=rows.filter(x=>x.stage===7).length;
    return [
      '<b>'+esc(b.department)+'</b><br><small class="muted">'+esc(b.role)+'</small>',
      esc(b.templateName)+' · V'+(state.records.find(r=>r.standard?.id===b.templateId)?.standard?.version||1),
      String(rows.length||b.count),
      String(pendingSelf),
      String(pendingMgr),
      String(done),
      button('查看名单','batch:'+b.id)
    ];
  }));
}
function selectedLaunchTemplateIds(){
  const available=templateApi.availableForLaunch(state.templateState);
  if(Array.isArray(state.launchDraft?.templateIds))return state.launchDraft.templateIds.filter(id=>available.some(t=>t.id===id));
  return available.map(t=>t.id);
}
function launchMatch(templateId){
  const available=templateApi.availableForLaunch(state.templateState),template=available.find(x=>x.id===templateId)||available[0];
  if(!template)return {template:null,result:{all:[],matched:[],excluded:[],blocked:[]}};
  return {template,result:personnelApi.matchPersonnel(personnelApi.demoRoster(),template,{month:'2026-09'},{includeProbation:false,minDays:15},['u3|'+template.id+'|2026-09'])};
}
function personnelSection(template){
  const {result}=launchMatch(template.id);
  const statusText={matched:['自动匹配','green'],excluded:['规则排除','amber'],blocked:['不可选择','red']};
  const rows=result.all.map(person=>{
    const st=statusText[person.status],checked=person.status==='matched'?'checked':'',disabled=person.status==='blocked'?'disabled':'';
    const sid='s-select-'+template.id+'-'+person.id,rid='s-reason-'+template.id+'-'+person.id;
    return ['<label class="checkbox personnel-check"><input id="'+sid+'" type="checkbox" '+checked+' '+disabled+'><span><b>'+esc(person.name)+'</b><small>'+esc(person.department)+' · '+esc(person.role)+' · 主管'+esc(person.manager)+'</small></span></label>',
      esc(person.employmentType==='probation'?'试用期':person.employmentStatus==='long_leave'?'长期休假':'正式在职')+'<br><small class="muted">本月在岗'+person.daysInPeriod+'天</small>',
      tag(st[0],st[1])+'<br><small>'+esc(person.reason)+'</small>',
      person.status==='blocked'?'—':'<input class="reason-input" id="'+rid+'" placeholder="'+(person.status==='matched'?'取消选择时必填原因':'手动纳入时必填原因')+'">'
    ];
  });
  return '<article class="batch-card" id="batch-card-'+esc(template.id)+'" data-template-id="'+esc(template.id)+'"><div class="batch-card-head"><div><b>'+esc(template.department)+' / '+esc(template.role)+'</b><p class="subline">'+esc(template.name)+' · V'+template.version+' · 自动匹配'+result.matched.length+'人，排除'+result.excluded.length+'人，阻断'+result.blocked.length+'人</p></div>'+tag('独立批次','blue')+'</div>'+
    (rows.length?table(['人员','任职情况','匹配结果','人工调整原因'],rows):'<div class="empty"><b>没有匹配人员</b>请检查模板的适用部门和岗位。</div>')+
    '<p class="hintline">本批次人员独立推进；调整系统结果时必须填写原因。</p></article>';
}
function launchSummary(selectedTemplates,preview){
  const matchedCount=preview.reduce((n,x)=>n+x.result.matched.length,0);
  const excludedCount=preview.reduce((n,x)=>n+x.result.excluded.length,0);
  const blockedCount=preview.reduce((n,x)=>n+x.result.blocked.length,0);
  const deptCount=new Set(selectedTemplates.map(t=>t.department)).size;
  if(!selectedTemplates.length){
    return '<div class="launch-scope empty-scope"><div><b>尚未选择模板</b><p class="subline">请在上方勾选要发起的部门模板；选择后这里会汇总范围。</p></div>'+
      '<div class="actions">'+button('全选已发布模板','launch:select-all',true)+'</div></div>';
  }
  const deptLine=[...new Set(selectedTemplates.map(t=>t.department))].map(d=>esc(d)).join('、');
  return '<div class="launch-scope">'+
    '<div class="launch-scope-main">'+
      '<div class="launch-scope-title">发起范围</div>'+
      '<p class="launch-scope-line"><b>'+selectedTemplates.length+'</b> 个模板 · <b>'+deptCount+'</b> 个部门 · 预计自动匹配 <b>'+matchedCount+'</b> 人</p>'+
      '<p class="launch-scope-depts">'+deptLine+'</p>'+
      '<p class="hintline">规则排除 '+excludedCount+' 人 · 阻断 '+blockedCount+' 人。勾选/取消请用上方模板卡片；核对名单见步骤 02。</p>'+
    '</div>'+
    '<div class="launch-scope-actions">'+
      button('预览匹配人员','launch:people-preview')+
      button('去确认人员名单','launch:goto-people',true)+
      button('清空已选','launch:clear')+
    '</div>'+
  '</div>';
}
function launchWorkbench(){
  const p=base.defaultPlan(),available=templateApi.availableForLaunch(state.templateState),selected=selectedLaunchTemplateIds();
  const selectedTemplates=available.filter(t=>selected.includes(t.id));
  const preview=selectedTemplates.map(t=>({t,...launchMatch(t.id)}));
  if(!available.length)return panel('2026年9月 · 待发起',notice('暂无已发布模板。请先在「考核模板管理」中发布至少一个模板。')+button('去模板管理','templates',true));
  return '<div class="launch-progress"><b class="on">1 选择部门模板</b><b>2 确认各部门人员</b><b>3 设置时间并发起</b></div>'+
    panel('01 · 选择考核周期与已发布模板',
      notice('一个周期可同时勾选多个部门模板；每个模板生成独立批次，各部门主管并行评分，互不等待。')+
      '<label class="field launch-period"><span>考核周期</span><select style="max-width:280px"><option>2026年9月（合成演示）</option></select></label>'+
      '<div class="sectionlabel">勾选要发起的部门模板</div>'+
      '<div class="template-pick">'+available.map(t=>{
        const on=selected.includes(t.id),{result}=launchMatch(t.id);
        return '<label class="template-pick-item'+(on?' on':'')+'"><input type="checkbox" id="s-tpl-'+esc(t.id)+'" data-template-toggle="'+esc(t.id)+'" '+(on?'checked':'')+'><span><b>'+esc(t.name)+' · V'+t.version+'</b><small>'+esc(t.department)+' / '+esc(t.role)+' · 自动匹配 '+result.matched.length+' 人</small></span></label>';
      }).join('')+'</div>'+
      '<div class="actions template-pick-actions">'+button('全选已发布模板','launch:select-all')+button('仅保留市场部','launch:only-demo')+'</div>'+
      launchSummary(selectedTemplates,preview)
    )+
    '<div id="launch-step-02">'+panel('02 · 按部门确认考核人员',
      selectedTemplates.length
        ? selectedTemplates.map(personnelSection).join('')
        : '<div class="empty"><b>尚未选择模板</b>请先勾选至少一个已发布模板。</div>'
    )+'</div>'+
    panel('03 · 设置处理截止日期并批量发起',
      '<p class="subline">截止日对本期所有批次生效；每位员工仍独立推进，不会因其他部门或其他人未提交而阻塞。</p>'+
      '<div class="formgrid">'+[['dataDue','员工提交截止'],['scoreDue','主管评分截止'],['resultDue','结果确认截止']].map(([key,label])=>'<label class="field"><span>'+label+'</span><input type="date" id="s-'+key+'" value="'+p[key]+'"></label>').join('')+'</div>'+
      '<details><summary>可选：增加HR结果复核</summary><label class="checkbox"><input id="s-review-required" type="checkbox">主管评分后，由HR陈悦复核再告知员工</label><label class="field"><span>HR复核截止（启用时生效）</span><input type="date" id="s-reviewDue" value="'+p.reviewDue+'"></label></details>'+
      '<p class="error" id="simple-error" role="alert"></p><div class="actions">'+button('检查人员与日期并批量发起','do-launch',true)+'</div>'
    );
}
function dashboard(){
  if(!state.launched)return '<div class="pagehead"><div><h1>本期考核</h1><p class="subline">多选部门模板、核对人员、统一定时间，一次批量发起；各部门并行推进。</p></div>'+button('演示操作说明','guide')+'</div>'+
    (state.migrationNote?notice(esc(state.migrationNote)):'')+
    panel('日常流程',path(null))+
    (state.role==='hr'?launchWorkbench():panel('2026年9月 · 待发起',notice('请切换到 HR 身份后，在本页勾选多部门模板并批量发起。')+button('切换HR发起','role:hr',true)));
  const r=active();
  const title=state.role==='employee'?'我的本期待办':'本期考核总览';
  let text,action;
  if(r.stage===7){text='考核已完成，结果和材料已自动锁定。';action=button('查看结果','work',true);}
  else if(!state.periodEnded){text='考核已发起。员工按目标开展工作；期末再提交实际完成情况。各部门批次互不阻塞。';action=button('查看本期目标','targets',true)+(state.role==='hr'?button('演示快进到期末','period-end'):'');}
  else {text=r.stage===1?'按每项指标填写实际完成，补齐缺失说明后提交给主管。':r.stage===3?'核对员工填写的实际，不准则改，再按满分打分。':r.stage===4?'此考核启用了HR复核，请核实结果后发布。':r.appeal?.status==='pending'?'员工有异议，等待HR说明处理结论。':'查看成绩与评价，无异议确认后自动完成；有异议可申诉。';
    action=state.role===owner(r)?button(r.stage===1?'填写实际并提交':r.stage===3?'核对实际并评分':r.stage===4?'复核结果':'查看结果','work',true):button('切换'+roleName(owner(r))+'继续','role:'+owner(r));}
  const batchNote=state.batches.length?state.batches.map(b=>esc(b.department)+' '+b.count+'人').join(' · '):'';
  return '<div class="pagehead"><div><h1>'+title+'</h1><p class="subline">每个人独立推进，不因其他员工或其他部门未提交而等待。</p></div>'+button('演示操作说明','guide')+'</div>'+
    (state.migrationNote?'<p class="hintline">'+esc(state.migrationNote)+'</p>':'')+
    (state.role==='employee'?'':'<div class="stats">'+[['本期人数',state.records.length],['批次 / 部门',state.batches.length||new Set(state.records.map(x=>x.personSnapshot?.department)).size],['待员工提交',state.records.filter(x=>x.stage===1).length],['待主管评分',state.records.filter(x=>x.stage===3).length],['已完成',state.records.filter(x=>x.stage===7).length]].slice(0,4).map(x=>'<div class="stat"><label>'+x[0]+'</label><strong>'+x[1]+'</strong></div>').join('')+'</div>')+
    (state.role!=='employee'&&batchNote?'<p class="hintline">本期批次：'+batchNote+'</p>':'')+
    '<div class="nextbox"><div><b>'+esc(r.name)+' · '+phase(r)+'</b><p class="subline">'+text+'</p></div><div class="actions">'+action+'</div></div>'+
    (state.role!=='employee'?panel('按部门进度',deptBoard())+panel(state.focusBatchId?'全员进度 · 已按批次筛选':'全员进度',(state.focusBatchId?('<div class="actions" style="margin-bottom:12px">'+button('清除批次筛选','batch:clear')+'</div>'):'')+teamTable(state.focusBatchId||null)):'')+
    '<details class="panel"><summary>查看完整流程与本期安排</summary>'+path(r)+summary(r)+'</details>';
}
function metricTarget(r,m,i){return i===1?(r.standard?.signedTarget||4)+'家':m.target;}
function fullPoints(){return base.METRICS.reduce((n,m)=>n+Number(m.max),0);}
function shownTotal(r){
  if(Array.isArray(r.itemScores)&&r.itemScores.length===base.METRICS.length&&r.itemScores.every(x=>x!==null&&x!==''&&Number.isFinite(Number(x))))return Math.round(r.itemScores.reduce((a,b)=>a+Number(b),0)*100)/100;
  return base.totalScore(r);
}
function scoreCell(r,m,i){
  const raw=Array.isArray(r.itemScores)?r.itemScores[i]:(i>=6?r.scores?.[i-6]:null);
  if(raw===null||raw===undefined||raw==='')return '<span class="muted">待评分</span>';
  return esc(raw)+' / '+m.max;
}
function actualCell(r,i){const v=r.actuals?.[i];return v?esc(v):'<span class="muted">未填</span>';}
function goalTable(r){return table(['指标','目标','满分'],base.METRICS.map((m,i)=>[esc(m.name),esc(metricTarget(r,m,i)),m.max]));}
function resultTable(r){return table(['指标','目标','实际','满分','得分'],base.METRICS.map((m,i)=>[esc(m.name),esc(metricTarget(r,m,i)),actualCell(r,i),m.max,scoreCell(r,m,i)]));}
function itemCard(item,editing=false,reviewing=false){
  const editable=editing&&['missing','ready','returned'].includes(item.status);
  const labels={missing:'待补充',ready:'草稿已保存',returned:'退回待补充',source:'补充说明 · 待核实',pending:'已提交 · 待核实',approved:'已核实'};
  const contents='<p><b>已有资料：</b>'+esc(item.known)+'</p><p><b>补充要求：</b>'+esc(item.returnReason||item.requirement)+'</p>'+
    (editable?'<label class="field"><span>'+esc(item.reason)+'（请在此补充）</span><textarea id="s-material-'+item.id+'" placeholder="'+esc(item.example||'填写事实和依据')+'">'+esc(item.value)+'</textarea></label>':'<p class="material-value">'+esc(item.value||'尚未填写')+'</p>')+
    (reviewing?button('退回这一条','return:'+item.id):'');
  return editable?'<article class="material-card"><div class="material-title"><h3>'+esc(item.name)+'</h3>'+tag(labels[item.status],'amber')+'</div>'+contents+'</article>':
    '<details class="material-card"><summary>'+esc(item.name)+'　'+tag(labels[item.status])+'　查看资料</summary>'+contents+'</details>';
}
function employeeForm(r){
  const items=base.evidenceItems(r),editable=items.filter(x=>['missing','ready','returned'].includes(x.status));
  const rows=base.METRICS.map((m,i)=>[esc(m.name),esc(metricTarget(r,m,i)),m.max,'<input class="cell-input" id="s-actual-'+i+'" aria-label="'+esc(m.name)+'实际" value="'+esc(r.actuals?.[i]||'')+'" placeholder="做到多少">']);
  return panel('1. 填写实际完成','<p class="subline">按每项指标填写本期做到了多少。不从系统自动带出，没完成可填 0。</p>'+table(['指标','目标','满分','实际'],rows))+
    panel('2. 补充缺少的材料',notice('共'+items.length+'条材料；'+editable.length+'条可补充或修改。材料是说明，不代替上面的实际。')+
      '<div class="material-list">'+items.map(x=>itemCard(x,true)).join('')+'</div>'+
      '<p class="hintline">只保存演示文字，不上传真实附件。已齐材料折叠展示，仍需主管核对。</p>')+
    panel('3. 工作说明与提交','<label class="field"><span>本月完成情况、问题及下月计划</span><textarea id="s-self" placeholder="简要说明本月工作；数据有疑问请写明。">'+esc(r.selfNote)+'</textarea></label>'+
      '<label class="checkbox"><input id="s-confirm-data" type="checkbox">我已填写各项实际和材料，提交给主管评分。</label>'+
      '<p class="error" id="simple-error" role="alert"></p><div class="actions">'+button('填入演示示例','examples')+button('保存草稿','draft')+button('一次提交给主管','submit',true)+'</div><p class="hintline">未提交可先保存草稿；离开页面前请保存。</p>');
}
function scoringForm(r){
  const rows=base.METRICS.map((m,i)=>{
    const saved=Array.isArray(r.itemScores)?r.itemScores[i]:(i>=6?r.scores[i-6]:'');
    return [esc(m.name),esc(metricTarget(r,m,i)),'<input class="cell-input" id="s-actual-'+i+'" aria-label="'+esc(m.name)+'实际" value="'+esc(r.actuals?.[i]||'')+'">',m.max,'<input class="scoreinput" id="s-score-'+i+'" aria-label="'+esc(m.name)+'得分" type="number" min="0" max="'+m.max+'" step="0.1" value="'+(saved??'')+'">'];
  });
  return panel('核对实际并打分',(r.returnNote?notice('HR退回：'+esc(r.returnNote)):'')+'<p class="subline">实际默认是员工填的。不对可以改，再按该项满分打分。系统不自动计分。</p>'+table(['指标','目标','实际','满分','得分'],rows)+'<h3>员工工作说明</h3><p class="material-value">'+esc(r.selfNote||'（员工未填写工作说明）')+'</p><div class="material-list">'+base.evidenceItems(r).map(x=>itemCard(x,false,true)).join('')+'</div>'+
      '<label class="field"><span>评分依据与反馈</span><textarea id="s-score-note">'+esc(r.scoreNote)+'</textarea></label><label class="checkbox"><input id="s-checked" type="checkbox">已核对员工填写的实际，并确认以上评分。</label>'+
      '<p class="error" id="simple-error" role="alert"></p><div class="actions">'+button('填入演示评分','score-example')+button('保存评分草稿','score-draft')+button(r.reviewRequired?'提交HR复核':'发布结果给员工','score',true)+'</div>');
}
function resultPage(r){
  const score=shownTotal(r);
  const done=r.stage===7?'结果已锁定，无需再操作。':r.stage===5&&state.role==='employee'&&r.appeal?.status!=='pending'?'请确认结果。有异议可申诉。':'主管已评分。';
  let footer='';
  if(r.stage===4&&state.role==='hr')footer='<label class="field"><span>需要退回时填写理由</span><textarea id="s-review-note"></textarea></label>'+button('退回主管修改','return-score')+button('复核通过并告知员工','review',true);
  if(r.stage===5&&r.appeal?.status==='pending'&&state.role==='hr')footer=notice('本原型演示核实后维持原分；改分应重新评分及复核，此处不直接改分。')+'<label class="field"><span>申诉复核依据</span><textarea id="s-resolution"></textarea></label>'+button('反馈复核结论','resolve',true);
  if(r.stage===5&&r.appeal?.status!=='pending'&&state.role==='employee')footer=button('对结果有异议','appeal')+button('确认结果并完成','confirm',true);
  return panel(r.stage===7?'已完成 · 结果已锁定':'考核结果','<p class="subline">'+done+'</p><p class="metric">'+(score??'待评分')+' <small>/ '+fullPoints()+'分</small></p><p>主管：李岚</p><p class="material-value">主管评价：'+esc(r.scoreNote||'—')+'</p>'+(r.actualCorrected?notice('部分实际已由主管改过，表中显示的是改后的值。'):'')+
    (r.stage===7?notice('确认后已自动锁定，无需HR再次结束考核。本原型不执行发薪。'):'')+
    (r.appeal?notice('员工申诉：'+esc(r.appeal.reason)+'<br>处理状态：'+(r.appeal.status==='pending'?'待HR复核':esc(r.appeal.resolution))):'')+
    '<p class="error" id="simple-error" role="alert"></p><div class="actions">'+footer+'</div>'+resultTable(r))+
    '<details class="panel"><summary>补充材料</summary>'+base.evidenceItems(r).map(x=>itemCard(x)).join('')+'</details>';
}
function work(){
  const r=active();if(!r)return dashboard();
  let body;
  if(!state.periodEnded)body=panel('本期目标与安排',summary(r)+goalTable(r));
  else if(r.stage===7||r.stage>=4)body=resultPage(r);
  else if(state.role!==owner(r))body=notice('当前应由'+roleName(owner(r))+'处理。本原型切换身份用于体验，不代表正式系统权限。')+button('切换对应身份','role:'+owner(r));
  else body=r.stage===1?employeeForm(r):scoringForm(r);
  return '<div class="pagehead"><div><h1>'+esc(r.name)+' · '+phase(r)+'</h1><p class="subline">2026年9月 · 市场部月度考核</p></div>'+button('返回总览','overview')+'</div>'+body+
    '<details class="panel"><summary>完整流程与处理记录</summary>'+path(r)+'<ol class="timeline">'+r.log.map(x=>'<li>'+esc(x.message)+'<small>'+esc(x.by)+' · '+esc(x.at)+'</small></li>').join('')+'</ol></details>';
}
const templateStatus={draft:['草稿','amber'],returned:['已退回','red'],in_review:['审核中','blue'],approved:['审核通过 · 待发布','green'],published:['已发布','green'],disabled:['已停用','']};
function templateAction(t){
  if(state.role==='manager'&&t.status==='in_review')return button('审核模板','template:review:'+t.id,true);
  if(state.role!=='hr')return button('查看','template:open:'+t.id);
  if(['draft','returned'].includes(t.status))return button('继续配置','template:open:'+t.id,true);
  if(t.status==='approved')return button('发布V'+t.version,'template:publish:'+t.id,true)+button('查看','template:open:'+t.id);
  if(t.status==='published')return button('查看规则','template:open:'+t.id)+button('复制新版本','template:copy:'+t.id);
  return button('查看','template:open:'+t.id)+button('复制新版本','template:copy:'+t.id);
}
function templateCatalogue(){
  const ts=state.templateState.templates;
  return '<div class="pagehead"><div><h1>考核模板管理</h1><p class="subline">规则变更时配置和审核，日常发起直接复用已发布版本。</p></div>'+(state.role==='hr'?button('新建模板','template:new',true):'')+'</div>'+
    '<div class="stats">'+[['全部模板',ts.length],['待配置',ts.filter(x=>['draft','returned'].includes(x.status)).length],['待审核',ts.filter(x=>x.status==='in_review').length],['可用于发起',ts.filter(x=>x.status==='published').length]].map(x=>'<div class="stat"><label>'+x[0]+'</label><strong>'+x[1]+'</strong></div>').join('')+'</div>'+
    notice('模板状态会控制操作权限：草稿可编辑，审核中只读，审核通过后由HR发布；只有已发布模板能出现在发起考核页面。')+
    panel('模板目录',table(['模板 / 版本','适用范围','指标 / 满分','状态','更新时间','操作'],ts.map(t=>{
      const st=templateStatus[t.status]||[t.status,''];
      return ['<b>'+esc(t.name)+'</b><br><small class="muted">V'+t.version+' · '+(t.cycle==='monthly'?'月度':'自定义周期')+'</small>',esc(t.department)+' / '+esc(t.role),t.metrics.length+'项 / '+t.metrics.reduce((n,x)=>n+Number(x.max||0),0)+'分',tag(st[0],st[1]),esc(t.history[0]?.at||'—'),'<div class="actions">'+templateAction(t)+'</div>'];
    })))+
    '<p class="hintline">“市场部月度 · 演示版”是合成演示模板。其他部门原始表格的规则冲突仍需业务确认后再配置发布。</p>';
}
function templateDetail(t){
  const st=templateStatus[t.status]||[t.status,''],canEdit=state.role==='hr'&&['draft','returned'].includes(t.status),errors=templateApi.validateTemplate(t),sum=t.metrics.reduce((n,x)=>n+Number(x.max||0),0);
  const targetUnit=m=>{const t=String(m.target||'').trim(),u=String(m.unit||'').trim();if(!t&&!u)return '—';if(t&&u)return esc(t)+' / '+esc(u);return esc(t||u);};
  const metricRows=t.metrics.map((m,i)=>['<b>'+esc(m.name)+'</b> '+tag(SCORE_TYPES[m.type]||'数量型','blue')+'<br><small class="muted">'+esc(m.source||'未设置来源')+'</small>',esc(m.max),targetUnit(m),esc(m.formula),esc(m.evidence),canEdit?button('编辑','template:metric:'+m.id)+button('删除','template:remove-metric:'+m.id):'只读']);
  const footer=state.role==='hr'&&canEdit?button('保存基本信息','template:edit-info')+button('新增指标','template:add-metric')+(!t.metrics.length?button('载入本部门推荐指标','template:seed'):'')+button('提交审核','template:submit',true):
    state.role==='manager'&&t.status==='in_review'?button('审核模板','template:review:'+t.id,true):
    state.role==='hr'&&t.status==='approved'?button('发布V'+t.version,'template:publish:'+t.id,true):
    state.role==='hr'&&t.status==='published'?button('复制为V'+(t.version+1),'template:copy:'+t.id,true)+button('停用模板','template:disable:'+t.id):'';
  return '<div class="pagehead"><div><button class="textbutton" data-simple-action="template:back">← 返回模板目录</button><h1>'+esc(t.name)+' · V'+t.version+'</h1><p class="subline">'+esc(t.department)+' / '+esc(t.role)+'　'+tag(st[0],st[1])+'</p></div><div class="actions">'+footer+'</div></div>'+
    (t.reviewNote?notice('<b>最近审核意见：</b>'+esc(t.reviewNote)):'')+
    '<div class="template-tabs"><a href="#template-info">模板信息</a><a href="#template-metrics">指标配置</a><a href="#template-check">校验与试算</a><a href="#template-history">审核记录</a></div>'+
    panel('<span id="template-info">模板信息</span>',table(['字段','内容'],[['模板名称',esc(t.name)],['适用范围',esc(t.department)+' / '+esc(t.role)],['考核周期',t.cycle==='monthly'?'月度':'自定义'],['生效日期',esc(t.effectiveFrom||'未设置')],['模板说明',esc(t.description||'未填写')]]))+
    panel('<span id="template-metrics">指标配置</span>',(t.metrics.length?table(['指标 / 数据来源','满分','目标 / 单位','计分规则','材料要求','操作'],metricRows):'<div class="empty"><b>尚未配置指标</b>新增指标，或载入演示指标后调整。</div>')+'<div class="table-footer"><span>指标满分合计</span><b class="'+(sum===100?'':'error')+'">'+sum+' / 100分</b></div>')+
    panel('<span id="template-check">校验与试算</span>',errors.length?'<div class="validation-list">'+errors.map(x=>'<p>⚠ '+esc(x)+'</p>').join('')+'</div>':notice('✓ 校验通过：基本信息完整、总分为100、指标名称无重复，且目标、单位、来源、规则和材料要求均已配置。')+
      (t.metrics.length?'<label class="field"><span>选择指标试算</span><select id="s-sim-metric">'+t.metrics.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name)+'</option>').join('')+'</select></label><div class="formgrid"><label class="field"><span>实际完成值</span><input id="s-sim-actual" type="number" min="0" value="3"></label><div><span class="muted">试算结果</span><p id="s-sim-result" class="metric">—</p></div></div>'+button('运行试算','template:simulate'):'')+
      '<p class="hintline">复杂条件或主管评价可能无法自动试算，页面会明确提示人工核对，不猜测得分。</p>')+
    panel('<span id="template-history">审核记录</span>',t.history.length?'<ol class="timeline">'+t.history.map(x=>'<li>'+esc(x.action)+(x.note?'<br>'+esc(x.note):'')+'<small>'+esc(x.by)+' · '+esc(x.at)+'</small></li>').join('')+'</ol>':'<p class="muted">暂无记录</p>');
}
function historyRows(periodId=state.historyPeriod){
  const period=PAST_PERIODS.find(p=>p.id===periodId)||PAST_PERIODS[0];
  let rows=period.rows;
  if(state.role==='manager')rows=rows.filter(x=>x.manager==='李岚');
  else if(state.role==='employee')rows=rows.filter(x=>x.name===(active()?.name||'张明'));
  return {period,rows};
}
function previousHistory(row,period){
  const previous=PAST_PERIODS[PAST_PERIODS.indexOf(period)+1];
  return previous?historyRows(previous.id).rows.find(x=>x.name===row.name):null;
}
function historyDelta(row,period){
  const previous=previousHistory(row,period);
  if(!previous)return '<span class="muted">暂无上期</span>';
  const delta=Number(row.score)-Number(previous.score);
  return '<span class="history-delta '+(delta>0?'up':delta<0?'down':'')+'">'+(delta>0?'↑ +':delta<0?'↓ ':'持平 ')+delta+' 分</span>';
}
function historyPage(){
  const {period,rows}=historyRows();
  const scope=state.role==='hr'?'全部部门':state.role==='manager'?'主管李岚的下属':'本人';
  const departments=[...new Set(rows.map(x=>x.department))];
  if(!departments.includes(state.historyDepartment))state.historyDepartment='';
  const query=(state.historyQuery||'').trim().toLowerCase();
  let filtered=rows.filter(x=>(!state.historyDepartment||x.department===state.historyDepartment)&&(!query||[x.name,x.role,x.manager].some(v=>v.toLowerCase().includes(query))));
  if(state.historySort==='high')filtered.sort((a,b)=>Number(b.score)-Number(a.score));
  if(state.historySort==='low')filtered.sort((a,b)=>Number(a.score)-Number(b.score));
  const average=filtered.length?(filtered.reduce((sum,x)=>sum+Number(x.score),0)/filtered.length).toFixed(1):'—';
  const stats=[['考核记录',filtered.length,'当前筛选范围'],['平均得分',average,'满分 100 分'],['最高得分',filtered.length?Math.max(...filtered.map(x=>Number(x.score))):'—','当前筛选范围'],['覆盖部门',new Set(filtered.map(x=>x.department)).size,'按考核时组织快照']];
  const options=PAST_PERIODS.map(p=>'<option value="'+p.id+'" '+(p.id===period.id?'selected':'')+'>'+esc(p.label)+'</option>').join('');
  const list=filtered.length?table(['员工','部门 / 岗位','考核主管','最终得分','较上期','状态','操作'],filtered.map(x=>['<div class="history-person"><span class="history-avatar" aria-hidden="true">'+esc(x.name.slice(-2))+'</span><b>'+esc(x.name)+'</b></div>',esc(x.department)+'<br><small class="muted">'+esc(x.role)+'</small>',esc(x.manager),'<span class="history-score">'+esc(x.score)+'</span><small class="muted"> / 100</small>',historyDelta(x,period),tag(x.status,'green'),button('查看详情','history:open:'+x.id)])):'<div class="empty"><b>没有匹配的考核记录</b><p>试试其他关键词或部门，或切换考核周期。</p>'+button('清空筛选','history:reset')+'</div>';
  return '<div class="history-page"><div class="pagehead"><div><div class="history-eyebrow">绩效档案 / HISTORY</div><h1>往期考核</h1><p class="subline">回顾历史成绩，查看每一期已完成的考核结果。</p></div><span class="tag blue">历史结果 · 只读</span></div>'+
    '<section class="history-toolbar" aria-label="往期考核筛选"><label class="field"><span>考核周期</span><select id="s-history-period">'+options+'</select></label><label class="field"><span>部门</span><select id="s-history-department"><option value="">全部可见部门</option>'+departments.map(d=>'<option '+(state.historyDepartment===d?'selected ':'')+'value="'+esc(d)+'">'+esc(d)+'</option>').join('')+'</select></label><label class="field history-search"><span>搜索员工 / 岗位 / 主管</span><input id="s-history-query" type="search" placeholder="输入关键词，按回车搜索" value="'+esc(state.historyQuery||'')+'"></label><div class="actions">'+button('查询','history:search',true)+button('重置','history:reset')+'</div></section>'+
    '<div class="history-scope"><span>可见范围：<b>'+scope+'</b></span><span>部门与主管保留考核时快照 · 演示数据</span></div>'+
    '<div class="stats history-stats">'+stats.map(x=>'<div class="stat"><label>'+x[0]+'</label><strong>'+x[1]+'</strong><small>'+x[2]+'</small></div>').join('')+'</div>'+
    '<section class="panel history-results"><div class="panelhead"><div><h2>'+esc(period.label)+' · 考核记录</h2><p class="subline" aria-live="polite">共 '+filtered.length+' 条结果'+(filtered.length!==rows.length?' / 可见 '+rows.length+' 条':'')+'</p></div><label class="history-sort">排序 <select id="s-history-sort">'+[['default','默认排序'],['high','得分从高到低'],['low','得分从低到高']].map(x=>'<option value="'+x[0]+'" '+((state.historySort||'default')===x[0]?'selected':'')+'>'+x[1]+'</option>').join('')+'</select></label></div>'+list+'<div class="table-footer">成绩变化与上一可见周期的同一员工比较；无上期记录时不计算。</div></section></div>';
}
function templatesPage(){const t=state.templateViewId&&state.templateState.templates.find(x=>x.id===state.templateViewId);return t?templateDetail(t):templateCatalogue();}
function render(){
  if(!['hr','employee','manager'].includes(state.role))state.role='hr';
  const body=state.page==='templates'?templatesPage():state.page==='history'?historyPage():state.page==='work'?work():dashboard();
  el('app').innerHTML='<div class="layout"><aside class="sidebar"><div class="brand"><span class="brandmark">鼎</span><div><small>经营管理平台</small><b>中泰旭鼎 CRM</b></div></div><div class="nav-caption">绩效考核 · 日常简版</div><nav><button class="navbutton '+(state.page==='overview'?'on':'')+'" data-simple-action="overview">本期待办与进度</button><button class="navbutton '+(state.page==='history'?'on':'')+'" data-simple-action="history">往期考核</button>'+(['hr','manager'].includes(state.role)?'<button class="navbutton '+(state.page==='templates'?'on':'')+'" data-simple-action="templates">考核模板管理</button>':'')+'</nav><div class="sidebar-bottom">独立原型 · 合成数据<br>不连接系统，不执行发薪<br>'+button('重新演示','reset-modal')+'</div></aside><div class="workspace"><header class="topbar"><span class="crumb">绩效管理 / 日常简版</span><div class="role-control"><label>演示身份 <select id="s-role">'+['hr','employee','manager'].map(role=>'<option value="'+role+'" '+(state.role===role?'selected':'')+'>'+roleName(role)+'</option>').join('')+'</select></label>'+
    (state.records.length?'<label>当前演示员工 <select id="s-person">'+state.records.map(r=>'<option value="'+esc(r.id)+'" '+(active()?.id===r.id?'selected':'')+'>'+esc(r.name)+'</option>').join('')+'</select></label>':'')+'</div></header><main class="main"><div class="simple-mobile-nav">'+button('本期待办','overview')+button('往期考核','history')+(['hr','manager'].includes(state.role)?button('模板管理','templates'):'')+button('重新演示','reset-modal')+'</div>'+body+'</main></div></div>';
  document.title='绩效考核 · 日常简版';save();
}
function payload(r){return {note:el('s-self').value,checked:el('s-confirm-data').checked,actuals:base.METRICS.map((_,i)=>el('s-actual-'+i).value),materials:Object.fromEntries(base.evidenceItems(r).filter(x=>['missing','ready','returned'].includes(x.status)).map(x=>[x.id,el('s-material-'+x.id).value]))};}
function optionList(values,current){return values.map(x=>'<option value="'+esc(x)+'" '+(x===current?'selected':'')+'>'+esc(x)+'</option>').join('');}
function roleOptions(department,current){const roles=DEPARTMENT_ROLES[department]||[];return optionList(roles,roles.includes(current)?current:roles[0]);}
function templateInfoDialog(t){
  const department=t?.department&&DEPARTMENT_ROLES[t.department]?t.department:'市场部',role=t?.role||DEPARTMENT_ROLES[department][0];
  dialog('模板基本信息',notice('<b>第一步先确定适用范围。</b>部门和岗位决定可选指标、数据来源以及后续考核人员。模板名称不会被用来判断所属部门。')+'<div class="formgrid"><label class="field"><span>模板名称</span><input id="s-template-name" value="'+esc(t?.name||'')+'" placeholder="例如：讲师月度考核"></label><label class="field"><span>考核周期</span><select id="s-template-cycle"><option value="monthly">月度</option><option value="custom">自定义周期</option></select></label><label class="field"><span>适用部门</span><select id="s-template-department">'+optionList(Object.keys(DEPARTMENT_ROLES),department)+'</select></label><label class="field"><span>适用岗位</span><select id="s-template-role">'+roleOptions(department,role)+'</select></label><label class="field"><span>生效日期</span><input id="s-template-effective" type="date" value="'+esc(t?.effectiveFrom||'2026-10-01')+'"></label></div><label class="field"><span>模板说明</span><textarea id="s-template-description">'+esc(t?.description||'适用于对应部门和岗位的月度绩效考核。')+'</textarea></label>'+(t?.metrics?.length?'<div class="callout warn"><b>注意：</b>修改部门或岗位后，需要重新核对当前指标是否仍适用。</div>':'')+'<p class="hintline">新建后为草稿；发布前不会出现在发起考核页面。</p>',button('保存','template:'+(t?'save-info':'create'),true));
  el('s-template-cycle').value=t?.cycle||'monthly';
}
function sourceOptions(current){
  const values=['CRM客户与线索','CRM签约记录','CRM跟进记录','运维监控平台','工单系统','内容任务台账','项目台账','直播平台数据','培训任务台账','排课与交付记录','课后评价问卷','主管评分','教学负责人评分','员工提交材料'];
  if(current&&!values.includes(current))values.unshift(current);
  return optionList(values,current||values[0]);
}
function scoreTypeOptions(current){return Object.entries(SCORE_TYPES).map(([value,label])=>'<option value="'+value+'" '+(value===current?'selected':'')+'>'+label+'</option>').join('');}
function metricRuleFields(type){
  const fields={
    quantity:'<div class="formgrid"><label class="field"><span>完成值口径</span><select><option>按实际完成数量</option><option>按目标完成率</option></select></label><label class="field"><span>封顶方式</span><select><option>最高不超过本项满分</option><option>允许超额加分</option></select></label></div>',
    ratio:'<div class="formgrid"><label class="field"><span>比例计算口径</span><input placeholder="例如：及时完成数 ÷ 应完成数"></label><label class="field"><span>未达到目标时</span><select><option>按完成比例计分</option><option>按区间分档计分</option></select></label></div>',
    tier:'<label class="field"><span>分档条件</span><textarea placeholder="例如：优秀=满分；良好=80%；合格=60%；不合格=0分"></textarea></label>',
    subjective:'<div class="formgrid"><label class="field"><span>评分人</span><select><option>直属主管</option><option>业务负责人</option><option>多人平均</option></select></label><label class="field"><span>评分维度</span><input placeholder="例如：准确性、表达、协作"></label></div>',
    bonus:'<div class="formgrid"><label class="field"><span>触发条件</span><input placeholder="例如：获得客户书面表扬"></label><label class="field"><span>单次加减分</span><input type="number" placeholder="例如：2"></label></div>',
    veto:'<div class="formgrid"><label class="field"><span>否决触发条件</span><input placeholder="例如：经确认的重大违规"></label><label class="field"><span>触发结果</span><select><option>本指标计0分</option><option>考核结果不合格</option></select></label></div>'
  };
  return fields[type]||fields.quantity;
}
function metricDialog(t,m){
  const library=INDICATOR_LIBRARY[t.department]||[],preset=m?.libraryId?library.find(x=>x.id===m.libraryId):(!m&&library[0]),draft={...(preset||{}),...(m||{})},mode=m&&!m.libraryId?'custom':'library',type=draft.type||'quantity';
  dialog(m?'编辑指标':'新增指标','<input id="s-metric-id" type="hidden" value="'+esc(m?.id||'')+'">'+
    '<div class="metric-config-steps"><b>1 选择指标来源</b><b>2 配置计分方式</b><b>3 绑定数据和材料</b></div>'+notice('<b>当前模板范围：</b>'+esc(t.department)+' / '+esc(t.role)+'。指标库已按该范围过滤；不适用的部门指标不会显示。')+
    '<section class="metric-config-section"><h3>01　选择指标来源</h3><div class="formgrid"><label class="field"><span>建立方式</span><select id="s-metric-mode"><option value="library" '+(mode==='library'?'selected':'')+'>从'+esc(t.department)+'指标库选择</option><option value="custom" '+(mode==='custom'?'selected':'')+'>新建自定义指标</option></select></label><label class="field" id="s-metric-library-wrap"><span>部门指标</span><select id="s-metric-library">'+(library.length?library.map(x=>'<option value="'+esc(x.id)+'" '+(x.id===draft.libraryId?'selected':'')+'>'+esc(x.name)+' · '+SCORE_TYPES[x.type]+'</option>').join(''):'<option value="">本部门暂无预置指标</option>')+'</select></label></div></section>'+ 
    '<section class="metric-config-section"><h3>02　配置目标与计分方式</h3><div class="formgrid"><label class="field"><span>指标名称</span><input id="s-metric-name" value="'+esc(draft.name||'')+'"></label><label class="field"><span>指标类型</span><select id="s-metric-type">'+scoreTypeOptions(type)+'</select></label><label class="field"><span>满分</span><input id="s-metric-max" type="number" min="0.1" step="0.1" value="'+esc(draft.max||'')+'"></label><label class="field"><span>目标值</span><input id="s-metric-target" value="'+esc(draft.target||'')+'"></label><label class="field"><span>单位</span><input id="s-metric-unit" value="'+esc(draft.unit||'')+'"></label></div><div id="s-metric-rule-fields" class="metric-rule-box">'+metricRuleFields(type)+'</div><label class="field"><span>计分规则摘要</span><textarea id="s-metric-formula" placeholder="请写清计算口径、边界、封顶和去重方式">'+esc(draft.formula||'')+'</textarea></label></section>'+ 
    '<section class="metric-config-section"><h3>03　绑定数据与材料</h3><div class="formgrid"><label class="field"><span>数据来源</span><select id="s-metric-source">'+sourceOptions(draft.source)+'</select></label><label class="field"><span>员工处理方式</span><select><option>系统自动获取，员工核对</option><option>系统缺失时员工补充</option><option>员工主动提交</option><option>主管评分，无需员工提交</option></select></label></div><label class="field"><span>材料要求</span><textarea id="s-metric-evidence" placeholder="说明需要什么材料、什么情况下需要员工补充">'+esc(draft.evidence||'')+'</textarea></label></section>'+ 
    '<p class="hintline">保存后仍需通过总分、必填项和规则冲突校验；指标随模板版本保存，历史考核不会被新规则覆盖。</p>',button('保存指标','template:save-metric',true));
  if(mode==='custom')el('s-metric-library-wrap').style.display='none';
}
function applyLibraryMetric(id){
  const t=templateApi.find(state.templateState,state.templateViewId),item=(INDICATOR_LIBRARY[t.department]||[]).find(x=>x.id===id);if(!item)return;
  for(const [field,value] of [['name',item.name],['target',item.target],['unit',item.unit],['source',item.source],['evidence',item.evidence],['formula',item.formula]]){const input=el('s-metric-'+field);if(input)input.value=value;}
  el('s-metric-type').value=item.type;el('s-metric-rule-fields').innerHTML=metricRuleFields(item.type);
}
function reviewDialog(t){
  dialog('审核模板 · '+esc(t.name),notice('请重点核对指标定义、目标口径、数据来源、计分边界以及满分合计。审核中模板只读。')+
    table(['指标','满分','目标','数据来源','计分规则'],t.metrics.map(x=>[esc(x.name),esc(x.max),esc(x.target),esc(x.source),esc(x.formula)]))+
    '<label class="field"><span>审核意见（退回时必填）</span><textarea id="s-review-template-note"></textarea></label>',button('退回修改','template:review-return')+button('审核通过','template:review-approve',true));
}
function action(a){
  try{
    const r=active();
    if(a==='close'){close();return;}
    if(a==='overview'||a==='templates'||a==='history'){state.page=a;close();render();return;}
    if(a==='history:search'){state.historyQuery=el('s-history-query').value;render();return;}
    if(a==='history:reset'){state.historyQuery='';state.historyDepartment='';state.historySort='default';render();return;}
    if(a.startsWith('history:open:')){
      const {period,rows}=historyRows();
      const row=rows.find(x=>x.id===a.slice(13));
      need(row,'找不到该往期考核，或当前身份无权查看。');
      dialog(esc(row.name)+' · '+esc(period.label)+'考核结果',
        '<div class="history-detail-score"><div><span class="muted">最终得分</span><div><strong>'+esc(row.score)+'</strong> / 100</div></div><div>'+tag(row.status,'green')+'<p>较上期 '+historyDelta(row,period)+'</p></div></div>'+
        table(['档案信息','考核时快照'],[['考核周期',esc(period.label)],['员工',esc(row.name)],['部门 / 岗位',esc(row.department)+' / '+esc(row.role)],['考核主管',esc(row.manager)],['记录编号',esc(row.id)]])+
        '<div class="callout">历史结果只读，部门及主管信息不随当前组织调整变化。</div><p class="muted">本原型仅提供历史汇总分，暂未提供当期指标明细、评分依据及处理记录。</p>',button('关闭','close',true));
      return;
    }
    if(a==='template:new'){templateInfoDialog(null);return;}
    if(a==='template:create'){
      const t=templateApi.createTemplate(state.templateState,{name:el('s-template-name').value,department:el('s-template-department').value,role:el('s-template-role').value,cycle:el('s-template-cycle').value});
      templateApi.updateTemplate(state.templateState,t.id,{effectiveFrom:el('s-template-effective').value,description:el('s-template-description').value},'hr');state.templateViewId=null;close();render();toast('模板草稿已创建，请继续配置指标。');return;
    }
    if(a.startsWith('template:open:')){state.templateViewId=a.slice(14);render();return;}
    if(a==='template:back'){state.templateViewId=null;render();return;}
    if(a==='template:edit-info'){templateInfoDialog(templateApi.find(state.templateState,state.templateViewId));return;}
    if(a==='template:save-info'){
      templateApi.updateTemplate(state.templateState,state.templateViewId,{name:el('s-template-name').value,department:el('s-template-department').value,role:el('s-template-role').value,cycle:el('s-template-cycle').value,effectiveFrom:el('s-template-effective').value,description:el('s-template-description').value},'hr');close();render();toast('模板基本信息已保存。');return;
    }
    if(a==='template:add-metric'){metricDialog(templateApi.find(state.templateState,state.templateViewId),null);return;}
    if(a.startsWith('template:metric:')){const t=templateApi.find(state.templateState,state.templateViewId),m=t.metrics.find(x=>x.id===a.slice(16));metricDialog(t,m);return;}
    if(a==='template:save-metric'){
      const t=templateApi.find(state.templateState,state.templateViewId),id=el('s-metric-id').value;
      const metric={id:id||'metric-'+Date.now(),libraryId:el('s-metric-mode').value==='library'?el('s-metric-library').value:'',type:el('s-metric-type').value,name:el('s-metric-name').value,max:el('s-metric-max').value,target:el('s-metric-target').value,unit:el('s-metric-unit').value,source:el('s-metric-source').value,evidence:el('s-metric-evidence').value,formula:el('s-metric-formula').value};
      if(id)templateApi.updateMetric(state.templateState,t.id,id,metric,'hr');else templateApi.replaceMetrics(state.templateState,t.id,[...t.metrics,metric],'hr');
      close();render();toast('指标已保存，校验结果已更新。');return;
    }
    if(a.startsWith('template:remove-metric:')){
      const t=templateApi.find(state.templateState,state.templateViewId),id=a.slice(23);templateApi.replaceMetrics(state.templateState,t.id,t.metrics.filter(x=>x.id!==id),'hr');render();toast('指标已从草稿移除。');return;
    }
    if(a==='template:seed'){
      const t=templateApi.find(state.templateState,state.templateViewId),items=INDICATOR_LIBRARY[t.department]||[];need(items.length,'当前部门暂无推荐指标，请使用“新增指标”创建。');
      const average=Math.floor(100/items.length),metrics=items.map((x,i)=>({...x,id:'metric-'+Date.now()+'-'+i,libraryId:x.id,max:i===items.length-1?100-average*(items.length-1):average}));
      templateApi.replaceMetrics(state.templateState,t.id,metrics,'hr');render();toast('已载入'+items.length+'项'+t.department+'推荐指标，请按实际制度调整分值和规则。');return;
    }
    if(a==='template:simulate'){
      const t=templateApi.find(state.templateState,state.templateViewId);try{el('s-sim-result').innerHTML=templateApi.simulate(t,el('s-sim-metric').value,el('s-sim-actual').value)+' <small>分</small>';}catch(e){el('s-sim-result').innerHTML='<small class="error">'+esc(e.message)+'</small>';}return;
    }
    if(a==='template:submit'){templateApi.submitForReview(state.templateState,state.templateViewId,'hr');render();toast('模板已提交业务负责人审核，当前只读。');return;}
    if(a.startsWith('template:review:')){state.templateViewId=a.slice(16);reviewDialog(templateApi.find(state.templateState,state.templateViewId));return;}
    if(a==='template:review-return'||a==='template:review-approve'){templateApi.review(state.templateState,state.templateViewId,'manager',{decision:a.endsWith('return')?'return':'approve',note:el('s-review-template-note').value});close();render();toast(a.endsWith('return')?'模板已退回HR修改。':'模板审核通过，待HR发布。');return;}
    if(a.startsWith('template:publish:')){const id=a.slice(17);templateApi.publish(state.templateState,id,'hr');state.templateViewId=id;render();toast('模板已发布，可用于新考核。');return;}
    if(a.startsWith('template:copy:')){const t=templateApi.copyVersion(state.templateState,a.slice(14),'hr');state.templateViewId=t.id;render();toast('已复制为V'+t.version+'草稿，修改后重新审核发布。');return;}
    if(a.startsWith('template:disable:')){state.templateViewId=a.slice(17);dialog('停用模板','<p>停用后不能用于新考核，历史考核仍保留当时的模板快照和版本。</p>',button('取消','close')+button('确认停用','template:disable-confirm',true));return;}
    if(a==='template:disable-confirm'){templateApi.disable(state.templateState,state.templateViewId,'hr');close();render();toast('模板已停用，历史考核不受影响。');return;}
    if(a==='work'){state.page='work';render();return;}
    if(a.startsWith('record:')){state.selectedId=a.slice(7);state.page='work';render();return;}
    if(a.startsWith('batch:')){state.focusBatchId=a.slice(6);state.page='overview';render();toast('已按该部门批次筛选全员进度。');return;}
    if(a==='batch:clear'){state.focusBatchId=null;render();return;}
    if(a.startsWith('role:')){state.role=a.slice(5);close();render();return;}
    if(a==='launch'||a==='launch:focus'){state.page='overview';render();document.querySelector('.launch-progress')?.scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(a==='launch:select-all'){state.launchDraft={...state.launchDraft,templateIds:templateApi.availableForLaunch(state.templateState).map(t=>t.id)};render();return;}
    if(a==='launch:clear'){state.launchDraft={...state.launchDraft,templateIds:[]};render();toast('已清空模板选择。');return;}
    if(a==='launch:only-demo'){state.launchDraft={...state.launchDraft,templateIds:['demo']};render();toast('已仅保留市场部演示模板。');return;}
    if(a.startsWith('launch:remove:')){
      const id=a.slice(14),next=selectedLaunchTemplateIds().filter(x=>x!==id);
      state.launchDraft={...state.launchDraft,templateIds:next};render();toast('已取消该部门批次。');return;
    }
    if(a==='launch:goto-people'){close();document.getElementById('launch-step-02')?.scrollIntoView({behavior:'smooth',block:'start'});toast('请在下方核对各部门人员。');return;}
    if(a.startsWith('launch:goto-batch:')){
      const id=a.slice(18);close();document.getElementById('batch-card-'+id)?.scrollIntoView({behavior:'smooth',block:'center'});
      toast('已定位到该部门人员名单。');return;
    }
    if(a==='launch:summary-templates'){document.querySelector('.template-pick')?.scrollIntoView({behavior:'smooth',block:'center'});toast('可在下方勾选或取消模板。');return;}
    if(a==='launch:summary-depts'){document.getElementById('launch-step-02')?.scrollIntoView({behavior:'smooth',block:'start'});toast('各部门人员名单见步骤 02。');return;}
    if(a==='launch:people-preview'){
      const selected=selectedLaunchTemplateIds(),available=templateApi.availableForLaunch(state.templateState);
      const rows=available.filter(t=>selected.includes(t.id)).map(t=>{
        const {result}=launchMatch(t.id);
        return [esc(t.department),'自动匹配 '+result.matched.length+' 人',result.matched.map(x=>esc(x.name)).join('、')||'—',button('去核对','launch:goto-batch:'+t.id)];
      });
      if(!rows.length){toast('请先勾选模板。');return;}
      dialog('预计自动匹配人员',notice('以下为系统按模板范围自动匹配的人员；最终以步骤 02 勾选结果为准。')+table(['部门','匹配','姓名','操作'],rows),button('去确认名单','launch:goto-people',true)+button('关闭','close'));
      return;
    }
    if(a==='do-launch'){
      const selected=selectedLaunchTemplateIds();
      need(selected.length,'请至少勾选1个已发布模板。');
      const batches=[];
      for(const templateId of selected){
        const {result}=launchMatch(templateId);
        const selectedIds=result.all.filter(x=>el('s-select-'+templateId+'-'+x.id)?.checked).map(x=>x.id);
        const reasons=Object.fromEntries(result.all.filter(x=>x.status!=='blocked').map(x=>[x.id,el('s-reason-'+templateId+'-'+x.id)?.value||'']));
        const errors=personnelApi.validateSelection(result,selectedIds,reasons);if(errors.length)throw new Error(errors.join('；'));
        batches.push({templateId,personnel:personnelApi.buildSnapshots(result,selectedIds,reasons)});
      }
      const p={batches,reviewRequired:el('s-review-required')?.checked===true};
      for(const key of ['dataDue','scoreDue','reviewDue','resultDue'])p[key]=el('s-'+key).value;
      launch(state,p);state.focusBatchId=null;close();render();toast('已批量发起 '+state.batches.length+' 个部门批次、共 '+state.records.length+' 人；人员和规则快照已保存。');return;
    }
    if(a==='targets'){dialog('本期目标与时间安排',summary(r)+goalTable(r),button('知道了','close'));return;}
    if(a==='guide'){dialog('简版怎么跑', '<ol><li>HR：在本页勾选多个部门模板、核对各部门人员、设置截止日，一次批量发起。</li><li>每个模板生成独立批次；各部门主管并行评分，个人互不等待。</li><li>演示专用：HR点击“快进到期末”，真实业务中由周期自然推进。</li><li>员工：按每项指标填写实际完成，并补充材料，一次提交。</li><li>主管：核对实际，不对就改，再按满分打分。</li><li>员工：看总分和每项得分，确认后自动完成。启用HR复核时，评分后多一次HR处理。</li></ol><p>右上角选择演示身份和员工，可体验多人各自推进。得分由主管手填，系统不自动计分。</p>',button('继续体验','close',true));return;}
    if(a==='reset-modal'){dialog('重新演示','<p>将清除日常简版的本地进度、材料与评分，回到多部门发起工作台。旧版缓存和真实系统不受影响。</p>',button('取消','close')+button('确认重新开始','reset',true));return;}
    if(a==='reset'){state=createState();close();render();return;}
    if(a==='examples'){
      for(const x of base.evidenceItems(r))if(['missing','ready','returned'].includes(x.status))el('s-material-'+x.id).value=x.example||'合成补充说明：客户事实与依据已核对，记录DEMO-001。';
      base.METRICS.forEach((m,i)=>{const input=el('s-actual-'+i);if(input)input.value=m.actual;});
      el('s-self').value='演示说明：各项实际已按本期完成情况填写；签约未达标，下月推进在谈客户。';return;
    }
    if(a==='score-example'){[9,15,10,5,20,10,8,4,4,3,3].forEach((v,i)=>el('s-score-'+i).value=v);base.METRICS.forEach((m,i)=>{const input=el('s-actual-'+i);if(input&&!input.value)input.value=m.actual;});el('s-score-note').value='演示评价：已按员工填写的实际评分，需求方案落地较好。';return;}
    if(a.startsWith('return:')){dialog('退回指定材料','<input id="s-return-id" type="hidden" value="'+esc(a.slice(7))+'"><label class="field"><span>具体缺什么、如何补充</span><textarea id="s-return-note"></textarea></label>'+notice('其他材料与工作说明保留；未保存的评分请先保存草稿。'),button('退回员工补充','do-return',true));return;}
    if(a==='appeal'){dialog('提交结果异议','<label class="field"><span>争议指标与事实依据</span><textarea id="s-appeal-note"></textarea></label>',button('交HR复核','do-appeal',true));return;}
    let command=a,p={};
    if(a==='draft'||a==='submit')p=payload(r);
    if(a==='score'||a==='score-draft')p={scores:base.METRICS.map((_,i)=>el('s-score-'+i).value),actuals:base.METRICS.map((_,i)=>el('s-actual-'+i).value),note:el('s-score-note').value,checked:el('s-checked').checked};
    if(a==='do-return'){command='return-item';p={itemId:el('s-return-id').value,note:el('s-return-note').value};}
    if(a==='return-score')p={note:el('s-review-note').value};
    if(a==='do-appeal'){command='appeal';p={note:el('s-appeal-note').value};}
    if(a==='resolve')p={note:el('s-resolution').value};
    const message=act(state,r?.id,command,p);close();render();toast(message||'已推进到期末，可以提交材料。');
  }catch(e){const error=el('simple-error');if(error)error.textContent=e.message;else toast(e.message);}
}
document.addEventListener('click',e=>{const target=e.target.closest('[data-simple-action]');if(target)action(target.dataset.simpleAction);});
document.addEventListener('keydown',e=>{if(e.target.id==='s-history-query'&&e.key==='Enter'){e.preventDefault();action('history:search');}});
document.addEventListener('change',e=>{
  if(e.target.id==='s-role'){state.role=e.target.value;close();render();}
  if(e.target.id==='s-person'){state.selectedId=e.target.value;close();render();}
  if(e.target.id==='s-history-period'){state.historyPeriod=e.target.value;render();}
  if(e.target.id==='s-history-department'){state.historyDepartment=e.target.value;render();}
  if(e.target.id==='s-history-sort'){state.historySort=e.target.value;render();}
  if(e.target.id==='s-history-query'){state.historyQuery=e.target.value;}
  if(e.target.dataset.templateToggle){
    const id=e.target.dataset.templateToggle,selected=new Set(selectedLaunchTemplateIds());
    if(e.target.checked)selected.add(id);else selected.delete(id);
    state.launchDraft={templateIds:[...selected]};render();return;
  }
  if(e.target.id==='s-template-department'){el('s-template-role').innerHTML=roleOptions(e.target.value,'');}
  if(e.target.id==='s-metric-mode'){
    const wrap=el('s-metric-library-wrap');wrap.style.display=e.target.value==='library'?'block':'none';
    if(e.target.value==='library')applyLibraryMetric(el('s-metric-library').value);
  }
  if(e.target.id==='s-metric-library')applyLibraryMetric(e.target.value);
  if(e.target.id==='s-metric-type'){
    el('s-metric-rule-fields').innerHTML=metricRuleFields(e.target.value);
    if(!el('s-metric-formula').value.trim())el('s-metric-formula').placeholder={quantity:'例如：达到目标得满分，不足按完成比例计分，最高不超过满分',ratio:'例如：达到目标比例得满分，低于目标按比例或分档计分',tier:'请逐档写明条件和对应分数',subjective:'请写明评分人、评分维度和各维度分值',bonus:'请写明触发条件、单次分值和累计上限',veto:'请写明触发条件及触发后的考核结果'}[e.target.value]||'';
  }
});
document.addEventListener('keydown',e=>{
  const modal=document.querySelector('#overlay [role="dialog"]');if(!modal)return;
  if(e.key==='Escape')close();
  if(e.key==='Tab'){const fields=[...modal.querySelectorAll('button,input,select,textarea')].filter(x=>x.type!=='hidden');const first=fields[0],last=fields[fields.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
});
render();
})();
