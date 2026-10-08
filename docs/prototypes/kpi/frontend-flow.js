/* Standalone prototype. Synthetic data only; no network or production integration. */
'use strict';
const FLOW = ['检查并发起','准备考核资料','员工核对','主管评分','结果复核','确认结果','结束考核','考核已完成'];
Object.assign(FLOW,{'-5':'制定考核标准','-4':'确认考核标准','-3':'设置本期考核','-2':'员工知晓目标','-1':'启动前检查'});
const ROLES = {hr:'HR · 陈悦',employee:'员工 · 张明',manager:'主管 · 李岚',training:'培训负责人 · 周宁'};
const METRICS = [
  {name:'有效线索',max:10,target:'10条',actual:'9条',score:9,source:'线索记录及客户画像',rule:'目标10条，少1条扣1分；不足4条不得分'},
  {name:'签约客户数',max:20,target:'4家',actual:'3家',score:15,source:'已确认的客户签约记录',rule:'20 − (4 − 3) × 5 = 15分；同一客户去重'},
  {name:'新增客户',max:10,target:'10家',actual:'10家',score:10,source:'客户档案',rule:'达到目标，得10分'},
  {name:'线索跟进时效',max:5,target:'无超时',actual:'0次超时',score:5,source:'已审核跟进记录',rule:'每次超时扣1分；演示用时限已在样例模板确认'},
  {name:'客户／渠道拜访',max:20,target:'15家，其中新客≥5家',actual:'16家，其中新客6家',score:20,source:'去重后的拜访记录',rule:'总拜访及新客均达标，得20分'},
  {name:'有效客户／渠道拓展',max:10,target:'10家',actual:'10家',score:10,source:'有效客户／渠道审核记录',rule:'达到目标，得10分'},
  {name:'需求分析落地',max:10,target:'主管评价',actual:'方案及交付说明',source:'员工提交材料'},
  {name:'销售标准动作',max:5,target:'主管评价',actual:'销售资料清单',source:'员工提交材料'},
  {name:'内部协同',max:4,target:'主管评价',actual:'协作记录',source:'经核实的协作情况'},
  {name:'客户信息同步',max:3,target:'主管评价',actual:'客户信息更新记录',source:'信息同步台账'},
  {name:'复盘与计划',max:3,target:'主管评价',actual:'本月复盘及计划',source:'复盘提交记录'}
];
const TEMPLATE_ROWS = [
  ['demo','市场部月度 · 演示版','市场业务','已生效','green','11项 · 100分','仅用于本地演示，正式业务须另行批准'],
  ['market','市场部月度','市场业务','草稿待确认','amber','11项 · 100分','跟进时限、新客不足的扣分规则待确认'],
  ['ops','AI运维月度','运营专员','草稿待确认','amber','6项 · 合计110分','总分与100分标称不一致；两组目标冲突'],
  ['content','内容制作月度','内容专员','草稿待确认','amber','4项 · 100分','两项满分30，但评分档位最高20'],
  ['brand','品宣月度','品宣专员','草稿待确认','amber','20项＋专项加分','引流、到店目标存在两种口径'],
  ['host','主播月度','主播','草稿待确认','amber','8项 · 100分','完成率边界、时长目标待确认'],
  ['ads','投手月度','投手','草稿待确认','amber','7项 · 100分','费用控制方向和分档边界待确认'],
  ['lecturer','讲师积分月度','讲师','来源待核对','amber','基础100分＋事件','新增主制度的来源、版本和批准记录待核对'],
  ...['sales','function'].flatMap(role=>['D5','M1','M3'].map((stage,i)=>[`${role}-${stage}`,`${role==='sales'?'业务岗':'职能岗'} · ${['入职第5天','入职第1个月','入职第3个月'][i]}`,role==='sales'?'业务新人':'职能新人','草稿待确认','amber','100分','双评合并与评分量表待确认']))
];
const DEPARTMENT_METRICS={
  ops:[['视频发布',20,'25条×项目数','按完成率分档；80%至不足90%得15分'],['播放量',20,'30万×项目数','按完成率分档'],['客资',25,'40条×项目数','达标后发布及播放记满分'],['客诉',15,'每项目≤1次','排除软件原因；多项目汇总规则待确认'],['998续约',15,'续约率≥80%','无998项目记15；应续约为0的规则待确认'],['客户服务',15,'工作时间12小时内回复','每超时1次扣1分']],
  content:[['文案／视频产出',30,'个人全项目合计120条','分档最高20与满分30冲突'],['播放量',30,'个人全项目合计30万','分档最高20与满分30冲突'],['客资',25,'个人全项目合计40条','达标覆盖前两项'],['客诉',15,'每项目≤1次','仅计制作重大失误造成的有效客诉']],
  brand:[['视频质量',5,'全月质量合格','质量问题每条扣0.5；重复加倍'],['拍摄数量',8,'每天3条','每日与月度扣分叠加口径待确认'],['视频文案',3,'一视频一文案','每缺1篇扣0.2'],['播放量',4,'月10万／周单条1万／月单条5万','总量和单条分别考核'],['点赞量',2,'月3000','比例计分；不足50%不得分'],['转发量',3,'月1000','比例计分；不足50%不得分'],['朋友圈海报',8,'工作日每日1—2条','节气假日当日必发'],['朋友圈文案',4,'月≥20篇','每天配套文案'],['员工转发率',3,'≥80%','参与人数与统计口径待确认'],['私域引流',8,'表体50／备注20人','目标冲突；超额加分另计'],['到店转化',4,'表体10／备注2人','目标冲突；超额加分另计'],['沙龙邀约',5,'20人','有效邀约，专项分另计'],['私域沉淀',5,'50人','回复时限1.5小时'],['御酒到店',3,'5组','组与人不同，不混算'],['协会拓展',10,'2家','跟进记录佐证'],['协会转化',8,'20家','合作／意向的有效性待确认'],['协会到访',7,'5人','促成合作加分规则待确认'],['工作态度',4,'主管评价','核实事件后扣分'],['合规保密',4,'主管评价','严重情况本项清零'],['工作台账',2,'完整记录','扣分下限待确认']],
  host:[['GMV完成率',20,'实际／目标','≥100%等分档端点待补齐'],['直播转化率',20,'下单人数／观众数','0和≥5%未定义'],['直播时长',10,'原文2—3小时','需明确数值与统计窗口'],['直播复盘',10,'完成应参加复盘','按缺席次数扣分'],['直播违规',10,'0次','0／1／2／3次得10／8／5／0'],['主观能动性',10,'主管评价','提供实际案例'],['工作优化',10,'主管评价','提供改善记录'],['学习性',10,'主管评价','提供学习记录']],
  ads:[['GMV完成率',20,'实际／目标','分档端点待确认'],['转化率',20,'下单人数／观众数','0和≥5%未定义'],['推广费用控制',20,'支出／预算','方向与端点待确认；75%原档位得15'],['直播复盘',10,'完成应参加复盘','按缺席次数扣分'],['主观能动性',10,'主管评价','提供实际案例'],['工作优化',10,'主管评价','提供改善记录'],['学习性',10,'主管评价','提供学习记录']]
};
function initialState(){return {version:3,role:'hr',page:'overview',stage:-5,standard:null,standardApproved:false,plan:null,planAcknowledged:false,preflight:false,periodEnded:false,evidence:false,verified:false,selfNote:'',scores:[null,null,null,null,null],scoreNote:'',resultConfirmed:false,appeal:null,payroll:false,revision:1,log:[],drafts:{},imported:false,importStatus:'none',trainingStage:'D5',trainingRole:'sales',trainingScores:{},trainingSaved:false,feedback:[]};}
function signedPoints(s){const target=Number(s.standard?.signedTarget||4);return Math.max(0,20-Math.max(0,target-3)*5);}
function systemPoints(s){return 54+signedPoints(s);}
function totalScore(s){if(!s.verified||s.scores.some(x=>x===null))return null;return Math.round((systemPoints(s)+s.scores.reduce((a,b)=>a+Number(b),0))*100)/100;}
function validatePlan(p){
  if(!p||p.employee!=='张明'||p.manager!=='李岚'||p.reviewer!=='陈悦')return '请完整设置考核对象、直属主管和复核人。';
  const dates=['dataDue','selfDue','scoreDue','reviewDue','resultDue'].map(k=>p[k]);
  if(dates.some(v=>!/^2026-10-\d{2}$/.test(v)||Number(v.slice(-2))<1||Number(v.slice(-2))>31))return '演示截止日应为2026年10月的有效日期，确保9月考核期结束后再评分。';
  if(dates.some((v,i)=>i>0&&v<dates[i-1]))return '时间顺序应为：资料提交 → 员工核对 → 主管评分 → 复核 → 结果确认。';
  return '';
}
function defaultPlan(){return {employee:'张明',manager:'李岚',reviewer:'陈悦',dataDue:'2026-10-02',selfDue:'2026-10-03',scoreDue:'2026-10-05',reviewDue:'2026-10-06',resultDue:'2026-10-08'};}
function coefficient(score){return score===null?null:score>=90?1:score>=80?.8:score>=60?.6:0;}
function validateScores(values){return values.length===5&&values.every((x,i)=>x!==''&&x!==null&&Number.isFinite(Number(x))&&Number(x)>=0&&Number(x)<=METRICS[i+6].max);}
function evidenceItems(s){
  if(s.evidenceItems)return s.evidenceItems;
  // Preserve older in-progress submissions without inventing individual evidence.
  if(s.evidence||s.verified){
    s.evidenceItems=[{id:'legacy',name:'旧版汇总材料',known:'更新前提交的汇总说明，未记录逐客户明细',requirement:'如需补充，请按HR意见列明客户与依据。',reason:'旧版材料保留',value:s.evidenceNote||'旧版已审核记录（未留存明细）',status:s.verified?'approved':'pending'}];
  }else{
    const gaps=[
      ['演示客户A','已有联系人和沟通记录；行业为空','客户行业','填写客户所属行业，并说明是否符合本期目标画像。','例如：餐饮连锁，计划在本市拓店，符合样例目标客户范围。'],
      ['演示客户B','已有行业和联系人；需求描述为空','具体需求','写明客户想解决的问题、意向产品及预计时间。','例如：需要门店短视频获客服务，计划10月启动，见9月20日沟通记录。'],
      ['演示客户C','已有行业及需求；缺少可核对的沟通依据','沟通依据','补充沟通日期、方式和记录位置，便于HR核对。','例如：9月22日电话沟通，联系人王经理；依据为演示跟进记录DEMO-003。']
    ];
    s.evidenceItems=gaps.map((x,i)=>({id:'lead-'+(i+1),name:x[0],known:x[1],reason:'系统检查：缺少'+x[2],requirement:x[3],example:x[4],value:'',status:'missing'}));
    for(let i=4;i<=9;i++)s.evidenceItems.push({id:'lead-'+i,name:'演示客户'+String.fromCharCode(64+i),known:'行业、需求、联系人及跟进说明已带入',reason:'系统字段完整',requirement:'无需重复填写；由HR核实真实性及是否有效。',value:'合成来源摘要：餐饮行业；门店推广需求；已记录联系人及9月跟进说明。',status:'source'});
  }
  return s.evidenceItems;
}
function missingEvidence(s){return evidenceItems(s).filter(x=>!x.value.trim()||x.status==='returned');}
function changeState(s,action,payload={}){
  const need=(ok,message)=>{if(!ok)throw new Error(message);};
  const who=(role)=>need(s.role===role,'请切换到对应处理人的演示身份。');
  const at=(stage)=>need(s.stage===stage,'当前环节不支持这个操作，请返回考核详情查看下一步。');
  let message='';
  if(action==='standard'){who('hr');at(-5);need(payload.name?.trim(),'请填写模板名称。');need(Number.isInteger(Number(payload.signedTarget))&&Number(payload.signedTarget)>=1&&Number(payload.signedTarget)<=20,'签约目标须为1—20家的整数。');need(payload.accepted===true,'请确认已查看11项指标及演示计分口径。');s.standard={name:payload.name.trim(),signedTarget:Number(payload.signedTarget),scope:'市场业务',version:1};s.standardApproved=false;s.stage=-4;message='HR已制定演示标准，待主管确认指标与口径。';}
  if(action==='return-standard'){who('manager');at(-4);need(payload.note?.trim(),'请填写需要修改的规则。');s.standardReturn=payload.note;s.stage=-5;message='主管退回考核标准：'+payload.note;}
  if(action==='approve-standard'){who('manager');at(-4);need(s.standard,'尚未制定考核标准。');s.standardApproved=true;s.stage=-3;message='主管已确认演示标准，版本V1锁定；HR可设置本期考核。';}
  if(action==='plan'){who('hr');at(-3);need(s.standardApproved,'模板尚未确认。');need(!validatePlan(payload),validatePlan(payload));s.plan={...payload,periodStart:'2026-09-01',periodEnd:'2026-09-30',templateVersion:1,signedTarget:s.standard.signedTarget};s.planAcknowledged=false;s.preflight=false;s.stage=-2;message='HR已设置人员、目标、处理人及截止日，待员工知晓目标。';}
  if(action==='return-plan'){who('employee');at(-2);need(payload.note?.trim(),'请填写目标或时间方面的疑问。');s.planReturn=payload.note;s.planAcknowledged=false;s.stage=-3;message='员工提出设置疑问，HR需调整或说明后重新告知：'+payload.note;}
  if(action==='ack-plan'){who('employee');at(-2);need(s.plan&&s.standardApproved,'计划不完整。');need(payload.accepted===true,'请勾选已知晓本期目标和时间安排。');s.planAcknowledged=true;s.stage=-1;message='员工已在考核期开始前知晓目标与规则，待HR启动前检查。';}
  if(action==='preflight'){who('hr');at(-1);need(s.standardApproved&&s.planAcknowledged&&s.plan&&!validatePlan(s.plan),'请先完成模板确认、人员设置和员工知晓。');s.preflight=true;s.stage=0;message='启动前检查通过，HR可以正式发起这次演示考核。';}
  if(action==='launch'){who('hr');at(0);need(s.standardApproved&&s.planAcknowledged&&s.preflight&&s.plan&&!validatePlan(s.plan),'尚未完成发起前准备。');s.stage=1;s.periodEnded=false;message='HR已发起9月考核，进入考核期；期末再汇总实际完成情况。';}
  if(action==='period-end'){who('hr');at(1);need(!s.periodEnded,'已进入期末资料准备。');s.periodEnded=true;message='演示时间推进至9月30日期末，系统已带入已有记录，待员工补充线索证据。';}
  if(action==='save-evidence-item'){
    who('employee');at(1);need(s.periodEnded&&!s.evidence,'仅在期末待补充时可以修改材料。');
    const item=evidenceItems(s).find(x=>x.id===payload.id);
    need(item&&['missing','ready','returned'].includes(item.status),'该材料不可修改。');
    need(typeof payload.value==='string','请填写材料说明。');
    item.value=payload.value.trim();item.status=item.value?'ready':'missing';
    message=item.name+'材料草稿已保存，尚未提交审核。';
  }
  if(action==='evidence'){
    who('employee');at(1);need(s.periodEnded,'当前仍在考核期内，请先推进到期末。');need(!s.evidence,'材料已提交，请等待HR审核。');
    need(!missingEvidence(s).length,'请先补齐清单中的缺失材料或HR退回项，再提交审核。');
    evidenceItems(s).forEach(x=>x.status='pending');s.evidence=true;s.verified=false;
    s.evidenceNote=evidenceItems(s).map(x=>x.name+'：'+x.value).join('\n');message='员工已提交逐客户材料，待HR核实；材料齐全不等于审核通过。';
  }
  if(action==='verify'){who('hr');at(1);need(s.periodEnded&&s.evidence,'尚未收到期末员工证据。');need(!missingEvidence(s).length,'仍有未补齐材料。');evidenceItems(s).forEach(x=>x.status='approved');s.verified=true;s.stage=2;message='HR已审核数据，待员工核对并提交自评。';}
  if(action==='reject-evidence'){
    who('hr');at(1);need(s.evidence,'尚未收到员工证据。');need(payload.note?.trim(),'请填写该客户具体缺少什么以及补充要求。');
    const item=evidenceItems(s).find(x=>x.id===payload.id);need(item,'请选择要退回的客户材料。');
    item.status='returned';item.returnReason=payload.note.trim();s.evidence=false;s.evidenceReturn=item.name+'：'+item.returnReason;
    message='HR退回'+item.name+'：'+item.returnReason+'；其他材料保留，未视为审核通过。';
  }
  if(action==='self'){who('employee');at(2);need(payload.note?.trim(),'请填写本月工作说明。');s.selfNote=payload.note;s.stage=3;message='员工已提交数据核对和自评，待主管评分。';}
  if(action==='save-score'||action==='score'){who('manager');at(3);need(validateScores(payload.scores),'请完整填写5项评分，且不超过各项满分。');need(payload.note?.trim(),'请填写评分依据或反馈。');s.scores=payload.scores.map(Number);s.scoreNote=payload.note;if(action==='score')s.stage=4;message=action==='score'?'主管已提交评分，待HR复核。':'主管评分已暂存，尚未提交复核。';}
  if(action==='return-score'){who('hr');at(4);need(payload.note?.trim(),'请填写退回原因。');s.stage=3;s.returnNote=payload.note;message='HR退回主管评分：'+payload.note;}
  if(action==='review'){who('hr');at(4);need(totalScore(s)!==null,'数据或评分未完整，不能复核。');s.stage=5;s.announcedAt=s.plan.reviewDue;message='HR复核通过，结果已告知员工。';}
  if(action==='confirm'){who('employee');at(5);need(!s.appeal||s.appeal.status==='resolved','申诉处理完成后才能确认结果。');s.resultConfirmed=true;s.stage=6;message='员工已确认本次结果，待HR结束考核并锁定结果。';}
  if(action==='appeal'){who('employee');at(5);need(!s.appeal||s.appeal.status==='resolved','已有待处理申诉。');need(payload.note?.trim(),'请填写异议项目与依据。');s.appeal={reason:payload.note,status:'pending'};message='员工已提交结果申诉，待HR复核。';}
  if(action==='resolve-appeal'){who('hr');at(5);need(s.appeal?.status==='pending','没有待处理申诉。');need(payload.note?.trim(),'请填写复核说明。');s.appeal.status='resolved';s.appeal.resolution=payload.note;s.revision++;s.resultConfirmed=false;message='申诉已复核并维持原评分，员工需确认第'+s.revision+'版结果。';}
  if(action==='archive'){who('hr');at(6);need(s.resultConfirmed,'员工尚未确认结果。');s.stage=7;message='考核已完成：分数、证据、规则和处理记录已锁定保存。';}
  if(action==='payroll'){who('hr');at(7);need(!s.payroll,'本期工资依据已生成。');s.payroll=true;message='已生成模拟绩效工资依据，不涉及实际发薪。';}
  need(Boolean(message),'未知操作。');s.log.unshift({message,by:ROLES[s.role],at:new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})});return message;
}
if(typeof module!=='undefined'&&module.exports)module.exports={initialState,defaultPlan,totalScore,coefficient,validateScores,validatePlan,signedPoints,systemPoints,changeState,METRICS,TEMPLATE_ROWS,evidenceItems};
if(typeof document!=='undefined'&&document.documentElement?.dataset.kpiMode!=='simple'){
let state=initialState();
try{const cached=JSON.parse(localStorage.getItem('kpi-flow-v3'));if(cached?.version===3)state={...state,...cached};}catch{}
let templateId='demo',modalReturn=null;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tag=(text,color='blue')=>`<span class="tag ${color}">${esc(text)}</span>`;
const btn=(text,action,primary=false,disabled=false)=>`<button type="button" class="btn ${primary?'primary':''}" data-action="${action}" ${disabled?'disabled':''}>${text}</button>`;
const goto=(page,text)=>`<button type="button" class="textbutton" data-page="${page}">${text} →</button>`;
const money=x=>Number(x).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});
const save=()=>{try{localStorage.setItem('kpi-flow-v3',JSON.stringify(state));}catch{}};
const head=(title,subtitle,actions='')=>`<div class="pagehead"><div><p class="eyebrow">2026年9月 · 绩效管理</p><h1>${title}</h1><p class="subline">${subtitle}</p></div><div class="actions">${actions}</div></div>`;
const panel=(title,body,extra='')=>`<section class="panel"><div class="panelhead"><h2>${title}</h2>${extra}</div>${body}</section>`;
const table=(headers,rows)=>`<div class="tablewrap"><table><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const callout=(text,kind='')=>`<div class="callout ${kind}">${text}</div>`;
const stats=items=>`<div class="stats">${items.map((x,i)=>`<div class="stat ${i===0?'featured':''}"><label>${x[0]}</label><strong>${x[1]}</strong><small>${x[2]}</small></div>`).join('')}</div>`;
function task(){
  const prep={
    '-5':{role:'hr',title:'第一步：制定考核标准',detail:'明确考什么、目标是多少、怎么算分。本演示预填11项市场指标，可调整签约目标。',action:'standard-modal',label:'制定考核标准',due:'考核期开始前'},
    '-4':{role:'manager',title:'确认指标与评分口径',detail:'主管审核HR拟定的演示标准。确认后锁定版本；有问题可退回修改。',action:'approve-standard-modal',label:'查看并确认标准',due:'考核期开始前'},
    '-3':{role:'hr',title:'设置本期考核安排',detail:'选择员工和已确认模板，设置评分人、复核人及期末各环节截止日。',action:'plan-modal',label:'设置人员、目标和时间',due:'考核期开始前'},
    '-2':{role:'employee',title:'提前知晓本期目标',detail:'员工在考核开始前查看指标、目标、计分方式和时间安排。有疑问可反馈HR。',action:'ack-plan-modal',label:'查看本期目标与安排',due:'考核期开始前'},
    '-1':{role:'hr',title:'检查发起条件',detail:'逐项检查：模板已确认、人员已匹配、时间合理、员工已知晓。通过后才能发起。',action:'preflight-modal',label:'运行启动前检查',due:'考核期开始前'}
  };
  if(state.stage<0)return prep[state.stage];
  return [
  {role:'hr',title:'发起本期考核',detail:'准备工作全部完成，确认后进入9月考核期。开始时不会提前出现期末得分。',action:'launch',label:'确认发起9月考核',due:'演示时间：9月1日'},
  !state.periodEnded?{role:'hr',title:'考核已开始，按目标开展工作',detail:'真实业务需要经过整个考核期。本原型可把演示时间推进到9月30日，体验期末准备资料。',action:'period-end-modal',label:'模拟推进到9月期末',due:'考核区间：9月1日—9月30日'}:state.evidence?{role:'hr',title:'审核员工补充的证据',detail:'张明已提交逐客户材料，请逐条核实；有问题可指定客户退回，并写明具体补充要求。',action:'verify-modal',label:'审核线索证据',due:state.plan?.dataDue||'待设置'}:{role:'employee',title:'补充缺少的考核材料',detail:'系统已列出每位客户缺少的内容、原因和补充要求。打开清单逐条完善，保存草稿后统一提交。',action:'evidence-modal',label:'补充缺少的材料',due:state.plan?.dataDue||'待设置'},
  {role:'employee',title:'核对数据并提交自评',detail:'11项指标材料已齐，请核对数据并填写本月工作说明。',action:'self-modal',label:'核对并提交自评',due:state.plan?.selfDue||'待设置'},
  {role:'manager',title:'完成5项主管评价',detail:'6项系统指标已经确认。请对需求落地、标准动作及协作等评分。',action:'score-modal',label:'填写主管评分',due:state.plan?.scoreDue||'待设置'},
  {role:'hr',title:'复核评分及依据',detail:'核对分数、评分理由与证据，批准后告知员工结果。',action:'review-modal',label:'复核考核结果',due:state.plan?.reviewDue||'待设置'},
  state.appeal?.status==='pending'?{role:'hr',title:'处理员工结果申诉',detail:'结果确认已暂停，先核对申诉依据并反馈处理结论。',action:'resolve-modal',label:'处理申诉',due:'按批准的申诉时限'}:{role:'employee',title:'查看并确认结果',detail:'如有异议可提交申诉。确认后，HR将结束考核并保存最终结果。',action:'confirm-modal',label:'确认考核结果',due:state.plan?.resultDue||'待设置'},
  {role:'hr',title:'结束考核并锁定结果',detail:'员工已确认。此操作将保存最终分数、规则、材料和处理记录，以后可查看，不能直接改分。',action:'archive-modal',label:'结束考核并锁定结果',due:'结果确认后'},
  {role:'hr',title:state.payroll?'本期处理完成':'生成绩效工资依据',detail:state.payroll?'模拟工资依据已生成。考核记录与原始证据均可追溯。':'考核已锁定。使用已确认的绩效基数计算本期金额。',action:'payroll-modal',label:state.payroll?'已完成':'查看并生成依据',due:'已归档'}
][state.stage];}
function taskBox(){const t=task();return `<div class="nextbox"><div><b>${esc(t.title)}</b><p class="subline">${esc(t.detail)}</p><p class="tiny muted">当前处理人：${ROLES[t.role]}　·　截止：${esc(t.due)}</p></div><div class="actions">${state.role===t.role?btn(t.label,t.action,true,state.stage===7&&state.payroll):btn('切换为'+ROLES[t.role].split(' · ')[0]+'继续','role-'+t.role,false)}</div></div>`;}
function flow(){return `<div class="journey" aria-label="完整考核流程">${[
  ['01','开始前：先定标准和安排',[-5,-4,-3,-2,-1]],
  ['02','执行中：按目标工作、准备资料',[0,1,2,3]],
  ['03','期末：复核、确认、结束',[4,5,6,7]]
].map(([no,title,steps])=>`<section class="journey-group"><div class="journey-title"><span>${no}</span><b>${title}</b></div><ol class="flow">${steps.map(i=>`<li class="${i<state.stage?'done':i===state.stage?'active':''}" ${i===state.stage?'aria-current="step"':''}><span class="dot">${i<state.stage?'✓':i+6}</span>${FLOW[i]}</li>`).join('')}</ol></section>`).join('')}</div>`;}
function menu(){const base=[['overview','本期待办'],['mine','我的绩效']];if(['hr','manager'].includes(state.role))base.push(['team','团队考核']);if(state.role==='hr')base.push(['cycles','考核管理'],['templates','考核模板'],['facts','数据台账'],['archive','结果与薪酬']);if(['hr','manager','training'].includes(state.role))base.push(['onboard','入职考核'],['lecturer','讲师反馈']);return base;}
function history(){return state.log.length?`<ol class="timeline audit">${state.log.map(x=>`<li>${esc(x.message)}<small>${esc(x.by)} · ${esc(x.at)}</small></li>`).join('')}</ol>`:'<p class="muted">发起考核后，每一步处理都会记录在这里。</p>';}
function overview(){const t=task(),score=totalScore(state);return head('完整考核流程','从制定标准开始，按当前主按钮逐步操作；需要换人时可直接切换演示身份。',btn('查看演示指引','guide')+btn('从第一步重跑','reset-modal'))
  +stats([['当前环节',FLOW[state.stage],state.stage<0?'发起前准备，尚未产生考核成绩':'张明 · 市场部月度考核'],['待我处理',state.role===t.role&&!(state.stage===7&&state.payroll)?'1':'0',ROLES[state.role]],['发起前准备',[state.standardApproved,Boolean(state.plan),state.planAcknowledged,state.preflight].filter(Boolean).length+' / 4','标准、安排、知晓、检查'],[state.stage<5?'评分进度':'考核结果',score===null?(state.stage<=1?'尚未评分':'待评分'):score+'分',score===null?'期末资料核实后再评价':'演示模板 · 满分100']])
  +taskBox()+panel('全流程 · 当前环节已高亮',flow())+`<div class="split">${panel('本次演示安排',planSummary())}${panel('处理记录',history())}</div>`;}
function planSummary(){return table(['项目','当前安排'],[
  ['考核标准',state.standard?esc(state.standard.name)+' · '+tag(state.standardApproved?'已确认锁定':'待主管确认',state.standardApproved?'green':'amber'):'尚未制定'],
  ['对象与岗位',state.plan?'张明 · 市场部业务人员':'待设置本期人员'],
  ['签约目标',state.standard?state.standard.signedTarget+'家；满分20，少1家扣5分':'制定标准时设置'],
  ['考核区间','2026年9月1日—9月30日'],
  ['评分／复核',state.plan?'李岚 / 陈悦':'待指定'],
  ['资料／自评截止',state.plan?esc(state.plan.dataDue)+' / '+esc(state.plan.selfDue):'待设置'],
  ['评分／复核截止',state.plan?esc(state.plan.scoreDue)+' / '+esc(state.plan.reviewDue):'待设置'],
  ['员工知晓',state.planAcknowledged?tag('已提前知晓','green'):tag('待告知','amber')]
]);}
function effectiveMetrics(){return METRICS.map((m,i)=>i===1?{...m,target:(state.standard?.signedTarget||4)+'家',score:signedPoints(state),rule:'满分20 − 未完成客户数 × 5，最低0；本期目标'+(state.standard?.signedTarget||4)+'家，实际3家，得'+signedPoints(state)+'分'}:m);}
function preflightRows(){return [
  ['考核标准已确认',state.standardApproved,'先制定标准，再由主管确认。'],
  ['人员和处理人已设置',Boolean(state.plan),'HR设置员工、主管与复核人。'],
  ['截止日顺序合理',Boolean(state.plan)&&!validatePlan(state.plan),'截止日在考核期结束后，并按流程顺序设置。'],
  ['员工已提前知晓目标',state.planAcknowledged,'员工查看并确认已知晓目标和规则。']
];}
function cycles(){return head('考核准备与发起','每一步都需要完成后才能进入下一步。人员、目标和时间确认后，再启动考核。')+taskBox()+panel('完整流程',flow())+`<div class="split">${panel('本期设置',planSummary())}${panel('发起条件',table(['检查项','状态'],preflightRows().map(([name,ok,why])=>[name+'<br><small class="muted">'+why+'</small>',tag(ok?'已完成':'待完成',ok?'green':'amber')]))+`<div class="actions" style="margin-top:18px">${btn(state.stage>0?'考核已发起':'确认发起考核','launch',true,state.stage!==0)}</div>`)}</div>`;}
function templates(){return head('考核模板','先完成样例标准的制定与确认，再把它用于本期考核。13套正式草稿仍保持待业务确认。')
  +stats([['样例标准',state.standardApproved?'已确认':state.standard?'待确认':'待制定','本次从制定标准开始演示'],['正式模板草稿','13','与演示标准分开'],['正式已批准','0','本地确认不代表正式制度批准'],['版本控制','V1','确认后锁定，不改历史考核']])
  +taskBox()+panel('模板目录',table(['模板名称','适用岗位','计分范围','状态','操作'],TEMPLATE_ROWS.map(r=>[r[0]==='demo'?esc(state.standard?.name||'市场部月度 · 演示标准待制定'):r[1],r[2],r[5],r[0]==='demo'?tag(state.standardApproved?'已确认':state.standard?'待主管确认':'未制定',state.standardApproved?'green':'amber'):tag(r[3],r[4]),`<button class="textbutton" data-action="template-${r[0]}">查看规则</button>`])));}
function fullGuide(){modal('完整跑一次 · 从标准到考核结束',`<p>本次从零开始准备。按首页蓝色主按钮处理，遇到不同处理人时点击“切换为…继续”。</p><ol class="guide-list"><li><b>HR制定标准</b>：查看11项指标，设置签约目标并提交。</li><li><b>主管确认标准</b>：审核后锁定演示版本，有问题可以退回。</li><li><b>HR设置本期考核</b>：指定员工、评分人、复核人及时间。</li><li><b>员工知晓目标</b>：在期初看清考什么、怎么算，可反馈疑问。</li><li><b>HR启动检查并发起</b>：准备条件全部满足后，发起9月考核。</li><li><b>模拟推进到期末</b>：在真实业务中先经历考核期，此处可快进到9月30日。</li><li><b>员工补材料，HR审核</b>：已有系统数据自动带入，只补缺少的证据。</li><li><b>员工核对，主管评分</b>：提交自评后，由主管评价5项工作表现。</li><li><b>HR复核，员工确认</b>：有异议可申诉，经处理后再确认。</li><li><b>HR结束考核</b>：锁定结果，再生成模拟绩效工资依据。</li></ol><p class="subline">角色切换不改变业务进度。刷新可继续；从首页“从第一步重跑”可重置这份原型。</p>`,btn('开始操作','close',true),true);}
function launchModal(){modal('检查并发起9月考核',planSummary()+callout(state.stage===0?'准备条件已满足。发起后进入9月1日至9月30日的考核期，期末再汇总实际完成情况。':'请先按首页流程完成标准、安排、员工知晓和启动前检查。',state.stage===0?'ok':'warn'),btn('返回','close')+btn('确认发起','do-launch',true,state.stage!==0),true);}
function handlePreparation(a){
  switch(a){
    case 'standard-modal':{
      const s=state.standard||{name:'市场部月度 · 全流程演示版',signedTarget:4};
      modal('第一步 · 制定考核标准',callout('以下仅为全流程演示标准，不会批准或覆盖13套正式部门草稿。期末实际数据尚未产生。')+(state.standardReturn?callout('主管意见：'+esc(state.standardReturn),'warn'):'')+`<div class="formgrid"><label class="field"><span>模板名称</span><input id="standard-name" value="${esc(s.name)}"></label><label class="field"><span>本期签约目标（家）</span><input id="standard-target" type="number" min="1" max="20" value="${s.signedTarget}"></label></div>`+table(['指标','满分','目标／评价方式'],METRICS.map((m,i)=>[m.name,m.max,i===1?'以上方设置的签约目标为准':m.target]))+callout('演示口径：有效线索须符合画像；客户去重；拜访总量与新客均达标才满分；人工项由主管写依据评分。市场薪酬系数按≥90/≥80/≥60/不足60分，分别为1.00/0.80/0.60/0。')+'<label class="checkbox"><input id="standard-accepted" type="checkbox">我已查看11项指标、目标与演示计分口径，提交给主管确认。</label>',btn('提交标准确认','do-standard',true),true);return true;
    }
    case 'do-standard':transact('standard',{name:document.getElementById('standard-name').value,signedTarget:document.getElementById('standard-target').value,accepted:document.getElementById('standard-accepted').checked});return true;
    case 'approve-standard-modal':modal('第二步 · 主管确认标准',`<h3>${esc(state.standard?.name)}</h3><p>11项指标，满分100。本期签约目标：<b>${state.standard?.signedTarget}家</b>；满分20，每少1家扣5，最低0分。</p>`+table(['指标','满分','目标'],effectiveMetrics().map(m=>[m.name,m.max,m.target]))+noteField('如需退回，请说明要修改的规则')+callout('确认后锁定演示版本V1，再由HR配置本期人员和时间。'),btn('退回修改','do-return-standard')+btn('确认标准并锁定V1','do-approve-standard',true),true);return true;
    case 'do-return-standard':transact('return-standard',{note:document.getElementById('note').value});return true;
    case 'do-approve-standard':transact('approve-standard');return true;
    case 'plan-modal':{
      const p=state.plan||defaultPlan();
      modal('第三步 · 设置本期考核',(state.planReturn?callout('员工反馈：'+esc(state.planReturn),'warn'):'')+`<p>已确认模板：<b>${esc(state.standard?.name)}</b> · V1</p><div class="formgrid"><label class="field"><span>考核对象</span><select id="plan-employee"><option>张明</option></select></label><label class="field"><span>考核周期</span><input value="2026年9月1日—9月30日" readonly></label><label class="field"><span>主管评分人</span><select id="plan-manager"><option>李岚</option></select></label><label class="field"><span>HR复核人</span><select id="plan-reviewer"><option>陈悦</option></select></label>${[['dataDue','资料提交截止'],['selfDue','员工核对截止'],['scoreDue','主管评分截止'],['reviewDue','结果复核截止'],['resultDue','结果确认截止']].map(([k,n])=>`<label class="field"><span>${n}</span><input id="plan-${k}" type="date" min="2026-10-01" max="2026-10-31" value="${p[k]}"></label>`).join('')}</div>`+callout(`本次签约目标为${state.standard?.signedTarget}家，随已确认模板锁定。样例固定为1名员工，以便完整体验；可调整期末各环节截止日。`),btn('保存安排并告知员工','do-plan',true),true);return true;
    }
    case 'do-plan':{const p={employee:document.getElementById('plan-employee').value,manager:document.getElementById('plan-manager').value,reviewer:document.getElementById('plan-reviewer').value};for(const k of ['dataDue','selfDue','scoreDue','reviewDue','resultDue'])p[k]=document.getElementById('plan-'+k).value;transact('plan',p);return true;}
    case 'ack-plan-modal':modal('第四步 · 员工提前知晓目标',callout('这次确认的是“期初目标与安排”，不是确认最终成绩。期末还会另外确认考核结果。')+planSummary()+table(['考核指标','满分','目标'],effectiveMetrics().map(m=>[m.name,m.max,m.target]))+'<label class="checkbox"><input id="plan-accepted" type="checkbox">我已知晓本期目标、计分方式和各环节截止时间。</label>'+noteField('如有疑问，可填写后反馈HR'),btn('反馈疑问给HR','do-return-plan')+btn('确认已知晓本期目标','do-ack-plan',true),true);return true;
    case 'do-return-plan':transact('return-plan',{note:document.getElementById('note').value});return true;
    case 'do-ack-plan':transact('ack-plan',{accepted:document.getElementById('plan-accepted').checked});return true;
    case 'preflight-modal':modal('第五步 · 启动前检查',table(['检查项','状态','说明'],preflightRows().map(([name,ok,why])=>[name,tag(ok?'通过':'待完成',ok?'green':'amber'),why]))+callout('全部检查通过后进入最终发起确认。没有实际考核分数，期末数据不会提前计入。'),btn('检查通过，进入发起确认','do-preflight',true,!preflightRows().every(x=>x[1])),true);return true;
    case 'do-preflight':transact('preflight');return true;
    case 'period-end-modal':modal('模拟推进到期末','<p>考核已经发起。真实业务中，员工会在整个9月按目标开展工作，系统持续记录签约、拜访和跟进情况。</p><p>为了让你一次体验完整流程，点击下方按钮后，演示时间将推进到9月30日期末，并带入合成业务记录。</p>'+callout('只快进这个本地原型，不修改系统日期、真实业务数据或截止日。'),btn('推进到期末，准备考核资料','do-period-end',true));return true;
    case 'do-period-end':transact('period-end');return true;
  }
  return false;
}
function mine(){return head('我的绩效',state.role==='employee'?'张明的考核与待办。点击考核单查看资料、评分及处理进度。':'这里展示张明的员工视角；切换为员工后可处理本人待办。')+taskBox()+`<div class="split equal">${panel('2026年9月 · 市场部月度',tag(FLOW[state.stage])+`<p class="metric">${totalScore(state)??'待评分'} <small>${totalScore(state)!==null?'／100分':''}</small></p><p class="subline">计入月度绩效工资 · 市场部月度演示版</p><div class="progress"><i style="width:${state.stage/7*100}%"></i></div>`+goto('detail','查看本人考核'))}${panel('入职阶段考核',tag('独立场景','amber')+'<p>入职第5天、第1个月、第3个月分别评估，使用对应岗位维度。</p><p class="subline">不重复计入月度绩效工资。正式模板规则待确认，此处仅演示阶段表单。</p>'+btn('查看阶段示例','stage-example'))}</div>`;}
function team(){return head('团队考核','每份考核单都有明确的员工、模板、处理人和截止时间。')+panel('2026年9月 · 市场部',table(['员工','模板','当前环节','处理人／截止','操作'],[['张明<br><span class="tiny muted">业务人员</span>','市场部月度 · 演示版',tag(FLOW[state.stage]),`${ROLES[task().role]}<br><small class="muted">${esc(task().due)}</small>`,goto('detail',state.stage===3&&state.role==='manager'?'去评分':'查看详情')]]))+callout('此演示使用1名员工贯穿完整流程。入职阶段和讲师反馈有独立场景，避免不同员工点击后进入同一份考核。');}
function detail(){const score=totalScore(state);return head('张明 · 9月考核','市场部 / 业务人员　·　市场部月度演示版　·　结果第'+state.revision+'版',goto(state.role==='employee'?'mine':'team','返回列表'))+flow()+taskBox()+(state.appeal?callout(`申诉${state.appeal.status==='pending'?'处理中':'已复核'}：${esc(state.appeal.reason)}${state.appeal.resolution?'<br>处理结论：'+esc(state.appeal.resolution):''}`,'warn'):'')+`<div class="split">${panel('指标与得分',table(['指标','目标／实际','满分','得分','依据'],effectiveMetrics().map((m,i)=>[m.name,`${m.target}<br><small class="muted">${i===0&&!state.verified?'待证据审核':m.actual}</small>`,m.max,i===0&&!state.verified?tag('待核实','amber'):i<6?`<b>${m.score}</b>`:state.scores[i-6]??tag('待主管评分','amber'),`<button class="textbutton" data-action="metric-${i}">查看依据</button>`]))+`<div class="table-footer"><span>基础分与专项加减分分别记录；本样例无专项加分</span><b>${score===null?'总分待计算':'总分 '+score+' / 100'}</b></div>`)}<div>${panel('考核信息',`<ul class="checklist"><li><span>考核区间</span><b>9月1日—9月30日</b></li><li><span>资料状态</span>${tag(state.verified?'已审核':'待补／待审核',state.verified?'green':'amber')}</li><li><span>结果状态</span>${tag(state.stage===7?'已锁定':state.stage>=5?'已告知':'预估',state.stage===7?'green':'blue')}</li><li><span>员工结果确认</span><span>${state.resultConfirmed?'已确认':'尚未确认'}</span></li></ul>`)}${panel('员工工作说明',`<p>${esc(state.selfNote||'员工核对环节填写。')}</p>`)}${panel('主管评价',`<p>${esc(state.scoreNote||'主管评分环节填写。')}</p>`)}${state.stage===5&&state.role==='employee'?panel('对结果有异议？','<p class="subline">明确指出争议指标与依据，提交后由HR复核。本演示不设定尚未批准的月度申诉截止日。</p>'+btn('提交结果申诉','appeal-modal',false,state.appeal?.status==='pending')):''}</div></div>`+panel('处理记录',history());}
function rulesFor(id){
  if(id==='demo'||id==='market')return METRICS.map((m,i)=>[m.name,m.max,id==='demo'&&i===1?(state.standard?.signedTarget||4)+'家':m.target,i===1?'满分20，每少1家扣5，最低0分':m.rule||'主管在指标满分内评价，填写评分依据']);
  if(DEPARTMENT_METRICS[id])return DEPARTMENT_METRICS[id];
  if(id.includes('-')){const oldRole=state.trainingRole,oldStage=state.trainingStage;[state.trainingRole,state.trainingStage]=id.split('-');const rows=trainingRows().map(r=>[r[0],r[1],'对应岗位阶段标准','评分量表及双评合并方式待确认']);state.trainingRole=oldRole;state.trainingStage=oldStage;return rows;}
  return [['月度基础分',100,'起始100','加减分必须关联已核实活动及批准制度']];
}
function template(){
  const r=[...(TEMPLATE_ROWS.find(x=>x[0]===templateId)||TEMPLATE_ROWS[0])],d=state.drafts[templateId]||{},editable=templateId!=='demo';
  if(templateId==='demo'){r[1]=state.standard?.name||'演示标准 · 待制定';r[3]=state.standardApproved?'已确认':state.standard?'待主管确认':'尚未制定';r[4]=state.standardApproved?'green':'amber';r[6]=state.standardApproved?'演示标准已确认锁定，本期目标与计分口径保持一致。':'下方为拟用的指标参考，请按首页主按钮完成制定与确认。';}
  const rows=rulesFor(templateId),draftRows=rows.map((row,i)=>d.rules?.[i]||row),sum=draftRows.reduce((n,row)=>n+Number(row[1]),0);
  const ruleTable=table(['指标','满分','目标／计分依据','操作'],draftRows.map((row,i)=>[esc(row[0]),esc(row[1]),`${esc(row[2])}<br><small class="muted">${esc(row[3])}</small>`,editable?btn('编辑草稿','edit-rule-'+i):i===1?btn('试算','preview'):'只读']));
  return head(r[1],r[2]+'　·　'+(editable?'草稿版本，可保存讨论方案':state.standardApproved?'演示版V1，已确认只读':'演示标准准备中'),goto('templates','返回模板列表'))
    +callout(esc(r[6]),editable?'warn':'ok')
    +`<div class="split">${panel('指标规则',ruleTable+`<div class="table-footer"><span>基础满分合计</span><b>${sum}分${sum!==100?' · 与100分标称不一致':''}</b></div>`)}${panel('适用与生效',`<ul class="checklist"><li><span>适用岗位</span><b>${r[2]}</b></li><li><span>状态</span>${tag(r[3],r[4])}</li><li><span>计入工资</span><b>${templateId.includes('-')?'不参与':'按批准政策'}</b></li></ul><p class="hintline">编辑草稿不改变原始来源和已生效的演示模板。正式制度尚未确认的参数不会自动补成推荐值。</p>`)}</div>`
    +(editable?panel('处理意见 · 保存为草稿',`<label class="field"><span>拟定方案／待确认人／讨论说明</span><textarea id="template-note" placeholder="例如：请部门负责人确认总分调整方案及生效月份。">${esc(d.note||'')}</textarea></label><div class="actions">${btn('保存讨论草稿','save-template',true)}${btn('提交正式审批','blocked-template',false,true)}</div><p class="hintline">本原型可编辑讨论草稿。发布仍需业务负责人确认所有冲突；保存草稿不会自动消除待确认事项。</p>`):panel('试算一项指标','<p class="subline">签约客户数：目标以当前演示标准为准，满分20分，每少1家扣5分，最低0分。</p>'+btn('打开计分试算','preview',true)))
    +panel('版本与来源','<p class="subline">演示版与正式草稿隔离。正式版本生效前需保留原始文件、规则确认人和批准记录。原始Cursor原型已另存，可对照查看。</p>');
}
function facts(){return head('数据台账','按业务名称查看数据及证据。未审核材料只供核对，不进入正式结果。',btn('体验导入预览','import'))+taskBox()+panel('9月 · 张明 · 市场部',table(['指标','实际数据','来源','审核状态','操作'],[['有效线索','9条','客户画像说明',tag(state.verified?'已审核':state.evidence?'待审核':'待补证据',state.verified?'green':'amber'),state.role==='hr'&&state.stage===1&&state.evidence?btn('审核证据','verify-modal'):btn('查看来源','metric-0')],['签约客户数','3家','合同签约记录',tag('已确认','green'),btn('查看来源','metric-1')],['客户／渠道拜访','16家，新客6家','拜访记录',tag('已确认','green'),btn('查看来源','metric-4')]]))+(state.imported?callout('模拟导入批次已登记，仍为“待审核”，未改变张明的正式考核数据。','ok'):'')+panel('台账与考核的关系','<p>补充或更正业务事实 → 审核 → 员工核对 → 使用确认后的数据评分。</p><p class="subline">归档后更正事实不会直接覆盖历史考核。本原型的导入用于演示核对过程，不自动修改主案例。</p>');}
function archive(){const score=totalScore(state),coeff=coefficient(score);return head('结果与薪酬','先结束考核并锁定结果，再生成绩效工资依据。锁定保存也叫归档。')+taskBox()+panel('考核结果',table(['员工／模板','得分','结果状态','员工确认','操作'],[['张明 · 市场部月度',score??'待评分',tag(FLOW[state.stage]),state.resultConfirmed?'已确认':'尚未确认',goto('detail','查看记录')]]))+panel('绩效工资依据',table(['绩效基数','模板系数','绩效金额','处理状态'],[['¥2,000.00<br><small class="muted">已确认的演示基数</small>',state.stage>=5?coeff.toFixed(2):'结果复核后确定',state.stage>=5?'¥'+money(2000*coeff):'暂不计算',tag(state.payroll?'模拟依据已生成':state.stage===7?'待生成':'待考核归档',state.payroll?'green':'amber')]])+'<p class="hintline">本页面不发放工资，也不调整基本工资。</p>')+panel('特殊结果 · 独立示例',table(['场景','分数如何形成','处理说明'],[['品宣专项加分','基础95＋专项10＝105分','保留105分与加分证据，按批准的品宣政策计算'],['品宣数据造假','基础100－26＝74分；强制不合格','不合格不自动等于零工资；造假专项薪酬规定未确认前暂停生成'],['缺少绩效基数','考核92分，基数未确认','考核可按完整流程归档，工资金额待补基数后计算'],['入职阶段','80分，达到75分合格线','仅供阶段评估，不重复计入月度绩效工资']])) ;}
const STAGES={D5:'入职第5天',M1:'入职第1个月',M3:'入职第3个月'};
function trainingRows(){const sales=state.trainingRole==='sales';return state.trainingStage==='D5'?[['公司认知',25],['产品认知',25],['团队融入',10],['岗位适配',40]]:state.trainingStage==='M1'?(sales?[['述职汇报',30],['产品知识',20],['基础业务实操',25],['团队协作',15],['学习任务',10]]:[['述职汇报',30],['职能工作完成度',25],['专业技能应用',20],['团队协作',15],['学习任务',10]]):(sales?[['成交额／业绩',50],['客户开发',20],['流程熟练度',15],['工作态度与成长',15]]:[['业务数据',50],['工作成果',20],['流程优化',10],['技能提升',10],['工作态度与协作',10]]);}
function onboard(){const key=state.trainingRole+state.trainingStage,values=state.trainingScores[key]||[];return head('入职阶段考核','独立表单场景：切换岗位和阶段后，评分维度随之变化。')+callout('正式模板的双评合并规则尚未确认。可演示填写与暂存，不能发布正式结果或自动办理转正、离职。','warn')+`<div class="actions" style="margin-bottom:18px"><label>岗位 <select id="training-role"><option value="sales" ${state.trainingRole==='sales'?'selected':''}>业务岗</option><option value="function" ${state.trainingRole==='function'?'selected':''}>职能岗</option></select></label></div><div class="tabs">${Object.entries(STAGES).map(([k,v])=>`<button data-action="stage-${k}" class="${state.trainingStage===k?'on':''}">${v}</button>`).join('')}</div><div class="split">${panel(STAGES[state.trainingStage]+' · 评分草稿',table(['维度','满分','评估得分'],trainingRows().map((x,i)=>[x[0],x[1],`<input aria-label="${x[0]}得分" class="scoreinput" id="training-${i}" type="number" min="0" max="${x[1]}" step="0.1" value="${values[i]??''}" ${state.role==='employee'?'disabled':''}>`]))+`<div class="actions" style="margin-top:18px">${btn('暂存阶段评分','save-training',true,state.role==='employee')}${btn('发布阶段结果','blocked-stage',false,true)}</div>`)}${panel('阶段材料与确认',`<ul class="checklist"><li><span>合格线</span><b>75分</b></li><li><span>业务数据</span><span>${state.trainingStage==='M3'?'由业务部门确认':'对应阶段材料'}</span></li><li><span>评价人</span><span>主管＋培训负责人</span></li><li><span>结果确认</span><span>本人、主管、培训负责人</span></li></ul><p class="hintline">申诉：公布后2个工作日内；复核：3个工作日内。正式截止日期需结合业务日历。</p>`)}</div>`;}
function lecturer(){return head('讲师反馈','先记录活动反馈，经核实后按批准制度计入月度考核。',btn('登记活动反馈','feedback',true))+callout('新增讲师主制度的版本与批准记录待核对，本原型不把未确认的加减分直接计入工资。','warn')+panel('日常反馈记录',state.feedback.length?table(['活动','评价','状态'],state.feedback.map(x=>[esc(x.activity),esc(x.note),tag('待核实','amber')])):'<div class="empty"><b>暂无反馈</b>可登记宣讲、试讲或内部分享反馈；保存后进入待核实列表。</div>')+`<div class="split equal">${panel('月度积分','<p class="metric">100 <small>起始分</small></p><p class="subline">正式加减分规则确认后，按已核实事件计算。未核实反馈不计分。</p>')}${panel('观察期 · 业务示例','<p>月内有效评差或投诉超过3次时，触发不胜任评估；3次不触发，4次触发。</p><p class="subline">触发评估 → HR审批 → 观察期 → 到期复评。结果与基本工资处理由人事流程决定。</p>'+btn('查看观察期示例','observation'))}</div>`;}
function render(){
  FLOW[1]=state.periodEnded?'准备考核资料':'考核进行中';
  const pages={overview,mine,team,detail,cycles,templates,template,facts,archive,onboard,lecturer};
  const nav=menu();if(!pages[state.page])state.page='overview';
  const beforeResults=(state.stage<1||!state.periodEnded)&&['mine','team','detail','facts','archive'].includes(state.page);
  const content=beforeResults?head('本期考核安排','当前还未到期末评分环节。先明确目标和时间安排，再按流程开展考核。')+taskBox()+panel('完整流程',flow())+panel('本期安排',planSummary()):pages[state.page]();
  document.getElementById('app').innerHTML=`<div class="layout"><aside class="sidebar"><div class="brand"><span class="brandmark">鼎</span><div><small>经营管理平台</small><b>中泰旭鼎 CRM</b></div></div><div class="nav-caption">绩效与成长</div><nav>${nav.map(([p,n])=>`<button class="navbutton ${state.page===p?'on':''}" data-page="${p}">${p==='overview'?'完整流程与待办':n}${p==='overview'&&state.role===task().role&&!(state.stage===7&&state.payroll)?'<span>1</span>':''}</button>`).join('')}</nav><div class="sidebar-bottom">独立原型 · 合成数据<br>不连接系统，不执行发薪<br><button class="textbutton" style="color:#c6dce8" data-action="reset-modal">从第一步重新演示</button></div></aside><div class="workspace"><header class="topbar"><span class="crumb">经营台 / 绩效管理</span><div class="role-control"><span class="demo-label">全流程演示</span><label for="role">当前身份</label><select id="role">${Object.entries(ROLES).map(([v,n])=>`<option value="${v}" ${state.role===v?'selected':''}>${n}</option>`).join('')}</select></div></header><main class="main"><select aria-label="页面导航" class="mobile-nav" id="mobile-page">${nav.map(([p,n])=>`<option value="${p}" ${state.page===p?'selected':''}>${n}</option>`).join('')}</select>${content}</main></div></div>`;
  document.title='绩效管理 · '+FLOW[state.stage];save();
}
function notify(text){const n=document.getElementById('notice');n.textContent=text;n.classList.add('show');clearTimeout(notify.timer);notify.timer=setTimeout(()=>n.classList.remove('show'),3200);}
function modal(title,body,footer='',wide=false){modalReturn=document.activeElement;document.getElementById('overlay').innerHTML=`<div class="modal-mask"><section role="dialog" aria-modal="true" aria-labelledby="modal-title" class="modal ${wide?'wide':''}"><div class="modalhead"><div><p class="eyebrow">本地交互演示</p><h2 id="modal-title">${title}</h2></div><button class="btn" data-action="close" aria-label="关闭弹窗">关闭</button></div>${body}<p id="form-error" class="error" role="alert"></p>${footer?`<div class="modalfoot">${footer}</div>`:''}</section></div>`;document.querySelector('#overlay input,#overlay textarea,#overlay select,#overlay button')?.focus();}
function close(){document.getElementById('overlay').innerHTML='';modalReturn?.focus();}
const noteField=(label='说明',value='')=>`<label class="field"><span>${label}</span><textarea id="note">${esc(value)}</textarea></label>`;
function transact(action,payload){try{const message=changeState(state,action,payload);close();render();notify(message);}catch(e){const error=document.getElementById('form-error');if(error)error.textContent=e.message;else notify(e.message);}}
function openScoring(){modal('主管评分 · 张明',callout(state.returnNote?'HR退回说明：'+esc(state.returnNote):'6项系统指标合计'+systemPoints(state)+'分。请评价以下5项，完整填写后才能提交复核。')+table(['评价项','满分','得分'],METRICS.slice(6).map((m,i)=>[m.name,m.max,`<input class="scoreinput" type="number" min="0" max="${m.max}" step="0.1" id="score-${i}" aria-label="${m.name}得分" value="${state.scores[i]??''}">`]))+noteField('评分依据与工作反馈（必填）',state.scoreNote),btn('填入演示评分','sample-score')+btn('暂存评分','save-score')+btn('提交复核','submit-score',true),true);}
function importModal(){modal('导入数据 · 核对预览',callout('这里使用内置CSV样例演示。不会读取本机文件，不会更改主案例数据。')+table(['行','员工／指标','数值','核对结果'],[['2','演示员工 · 视频发布','7条',tag('可导入','green')],['3','未识别员工 · 播放量','30000',state.importStatus==='fixed'?tag('已排除本批','amber'):tag('员工不存在','red')]])+`<p class="hintline">${state.importStatus==='fixed'?'已排除错误行：本批导入1行，排除1行。':'请先处理错误行；有错误时不能直接提交整批。'}</p>`,btn('明确排除错误行','fix-import',false,state.importStatus==='fixed')+btn(state.imported?'此样例已导入':'确认导入1行','confirm-import',true,state.importStatus!=='fixed'||state.imported),true);}
const materialLabels={missing:'待补充',ready:'已填写 · 待提交',source:'系统已带入 · 待核实',pending:'已提交 · 待审核',returned:'HR退回 · 待补充',approved:'审核通过'};
function openEvidenceChecklist(review=false){
  const items=evidenceItems(state),missing=missingEvidence(state).length;
  const canEdit=state.role==='employee'&&state.stage===1&&state.periodEnded&&!state.evidence;
  const canReview=review&&state.role==='hr'&&state.stage===1&&state.evidence;
  const rows=items.slice().sort((a,b)=>Number(['missing','returned'].includes(b.status))-Number(['missing','returned'].includes(a.status)));
  const body=callout('张明 · 2026年9月 · 有效线索｜提交截止：'+esc(state.plan?.dataDue||'待设置')+'<br>只需补充清单指出的内容，无需重填全部数据。以下客户和资料均为合成演示数据。')+
    '<div class="material-summary"><div><b>'+items.length+'</b><span>材料记录</span></div><div><b>'+missing+'</b><span>需补充或修改</span></div><div><b>'+items.filter(x=>x.status==='ready').length+'</b><span>草稿待提交</span></div><div><b>'+items.filter(x=>['source','pending'].includes(x.status)).length+'</b><span>材料已齐待核实</span></div></div>'+
    (state.verified?callout('材料已审核，当前仅供查看。'):callout(missing?'请先处理标注“待补充”的客户。填写后保存草稿，全部补齐再统一提交。':'当前没有缺失项。'+(state.evidence?'请等待HR核实；有材料不代表已认定为有效线索。':'点击底部“提交材料给HR”进入审核。'),'warn'))+
    '<div class="material-list">'+rows.map(x=>'<article class="material-card"><div class="material-title"><h3>'+esc(x.name)+'</h3>'+tag(materialLabels[x.status],['missing','returned'].includes(x.status)?'amber':x.status==='approved'?'green':'blue')+'</div><p><b>已有资料：</b>'+esc(x.known)+'</p><p><b>检查结果：</b>'+esc(x.reason)+'</p>'+
      (x.returnReason?callout('<b>HR具体补充要求：</b>'+esc(x.returnReason),'warn'):'')+
      '<p><b>你需要做什么：</b>'+esc(x.requirement)+'</p>'+
      (x.value?'<details><summary>查看'+(x.status==='source'?'系统带入':'已保存')+'的材料</summary><p class="material-value">'+esc(x.value)+'</p></details>':'')+
      '<div class="actions">'+(canEdit&&['missing','ready','returned'].includes(x.status)?btn(x.status==='ready'?'修改草稿':'去补充','material-edit-'+x.id,true):'')+(canReview?btn('退回此条','material-return-'+x.id):'')+'</div></article>').join('')+'</div>'+
    '<p class="hintline">本原型只保存文字说明，不上传附件、不修改真实客户档案；正式系统应关联原始记录和附件。</p>';
  modal(review?'审核逐客户材料':'我缺哪些材料？',body,
    canReview?btn('已逐条核实，全部通过','do-verify',true):
    canEdit?btn(missing?'还有'+missing+'条待补充':'提交材料给HR','do-evidence',true,missing>0):btn('关闭','close'),true);
}
function handleEvidence(a){
  if(a==='evidence-modal'||a==='verify-modal'){openEvidenceChecklist(a==='verify-modal');return true;}
  if(a.startsWith('material-edit-')){
    const item=evidenceItems(state).find(x=>x.id===a.slice(14));
    if(!item||state.role!=='employee'||state.stage!==1||!state.periodEnded||state.evidence||!['missing','ready','returned'].includes(item.status)){notify('当前材料不可编辑。');return true;}
    modal('补充材料 · '+esc(item.name),'<input type="hidden" id="material-id" value="'+item.id+'">'+
      '<p><b>已有资料：</b>'+esc(item.known)+'</p>'+callout('<b>补充要求：</b>'+esc(item.returnReason||item.requirement),'warn')+
      '<label class="field"><span>补充内容（按上方要求填写）</span><textarea id="material-value" placeholder="'+esc(item.example||'请写明客户、事实及可核对的依据')+'">'+esc(item.value)+'</textarea></label>'+
      '<p class="hintline">可先保存未完成的草稿；保存不等于提交审核。关闭前请先保存。</p>',
      btn('返回清单（不保存）','evidence-modal')+(item.example?btn('填入演示示例','material-example'):'')+btn('保存草稿并返回','material-save',true));return true;
  }
  if(a==='material-example'){
    const item=evidenceItems(state).find(x=>x.id===document.getElementById('material-id').value);
    if(item)document.getElementById('material-value').value=item.example||'';return true;
  }
  if(a==='material-save'){
    try{const message=changeState(state,'save-evidence-item',{id:document.getElementById('material-id').value,value:document.getElementById('material-value').value});save();render();openEvidenceChecklist();notify(message);}catch(e){document.getElementById('form-error').textContent=e.message;}return true;
  }
  if(a.startsWith('material-return-')){
    const item=evidenceItems(state).find(x=>x.id===a.slice(16));
    if(!item||state.role!=='hr'||!state.evidence||state.stage!==1){notify('当前不能退回材料。');return true;}
    modal('退回补充 · '+esc(item.name),'<input type="hidden" id="material-id" value="'+item.id+'"><p class="material-value">'+esc(item.value)+'</p>'+noteField('具体缺什么、需要怎样补充（必填）')+callout('仅退回这一条，其他已提交材料保留待核实。员工修改并重新提交后，再继续审核。'),btn('返回审核清单','verify-modal')+btn('退回此条给员工','do-reject-evidence',true));return true;
  }
  return false;
}
function action(a){
  if(handleEvidence(a))return;
  if(handlePreparation(a))return;
  if(a.startsWith('role-')){state.role=a.slice(5);state.page='overview';render();return;}
  if(a.startsWith('edit-rule-')){
    const i=Number(a.slice(10)),row=state.drafts[templateId]?.rules?.[i]||rulesFor(templateId)[i];
    modal('编辑指标草稿',`<input id="rule-index" type="hidden" value="${i}"><p><b>${esc(row[0])}</b></p><div class="formgrid"><label class="field"><span>满分</span><input id="rule-max" type="number" min="0" step="0.1" value="${row[1]}"></label><label class="field"><span>目标与单位</span><input id="rule-target" value="${esc(row[2])}"></label></div><label class="field"><span>计分方式／待确认口径</span><textarea id="rule-text">${esc(row[3])}</textarea></label>`+callout('仅保存为讨论草稿，不影响演示考核。满分调整后会重新展示合计，但业务冲突仍需确认。'),btn('保存指标草稿','save-rule',true));return;
  }
  if(a.startsWith('template-')){templateId=a.slice(9);state.page='template';render();return;}
  if(a.startsWith('stage-')&&a!=='stage-example'){state.trainingStage=a.slice(6);render();return;}
  if(a==='metric-0'){openEvidenceChecklist(state.role==='hr'&&state.evidence);return;}
  if(a.startsWith('metric-')){const i=Number(a.slice(7)),m=effectiveMetrics()[i];modal(m.name+' · 计分依据',`<p>来源：${m.source}</p><p>目标：${m.target}</p><p>实际：${m.actual}</p>`+callout(m.rule||'由主管在满分内评分，结合材料填写评价理由。')+(i===0?`<p>证据：${esc(state.evidenceNote||'尚未补充客户画像说明')}</p><p>审核：${state.verified?'已审核':'待核实'}</p>`:'')+'<p class="hintline">此处为合成来源摘要。正式系统应展示原记录与附件入口。</p>');return;}
  switch(a){
    case 'close':close();break;
    case 'guide':fullGuide();break;
    case 'launch':launchModal();break;
    case 'do-launch':transact('launch');break;
    case 'do-evidence':transact('evidence');break;
    case 'do-verify':transact('verify');break;
    case 'do-reject-evidence':transact('reject-evidence',{id:document.getElementById('material-id').value,note:document.getElementById('note').value});break;
    case 'self-modal':modal('核对数据与提交自评',callout('有效线索9条、签约3家、拜访16家（新客6家）。系统计分数据已审核。')+noteField('本月工作说明',state.selfNote||'演示说明：已核对业务数据。完成客户方案交付，签约数量未达目标，下月重点推进在谈客户。')+'<label class="checkbox"><input id="checked" type="checkbox">我已核对本次数据及提交材料。</label>',btn('提交自评','do-self',true));break;
    case 'do-self':if(!document.getElementById('checked').checked){document.getElementById('form-error').textContent='请先确认已核对数据。';break;}transact('self',{note:document.getElementById('note').value});break;
    case 'score-modal':openScoring();break;
    case 'sample-score':[8,4,4,3,3].forEach((v,i)=>document.getElementById('score-'+i).value=v);document.getElementById('note').value='演示评价：需求方案落地较好，销售资料仍可补充，协作及复盘按要求完成。';break;
    case 'save-score':case 'submit-score':transact(a==='save-score'?'save-score':'score',{scores:METRICS.slice(6).map((_,i)=>document.getElementById('score-'+i).value),note:document.getElementById('note').value});break;
    case 'review-modal':modal('复核考核结果',`<p class="metric">${totalScore(state)} <small>／100分</small></p><p>主管反馈：${esc(state.scoreNote)}</p>`+noteField('需要退回修改时，填写原因'),btn('退回主管','do-return')+btn('复核通过并告知员工','do-review',true));break;
    case 'do-return':transact('return-score',{note:document.getElementById('note').value});break;
    case 'do-review':transact('review');break;
    case 'confirm-modal':modal('确认考核结果',`<p>张明 · 2026年9月 · 第${state.revision}版</p><p class="metric">${totalScore(state)} <small>／100分</small></p><p>确认后由HR结束考核并锁定结果。若对指标或分数有异议，请先提交申诉。</p>`,btn('返回查看','close')+btn('我已查看，确认结果','do-confirm',true));break;
    case 'do-confirm':transact('confirm');break;
    case 'appeal-modal':modal('提交结果申诉',noteField('争议指标、原因与补充依据'),btn('提交申诉','do-appeal',true));break;
    case 'do-appeal':transact('appeal',{note:document.getElementById('note').value});break;
    case 'resolve-modal':modal('申诉复核',`<p>员工意见：${esc(state.appeal?.reason)}</p>`+callout('本原型演示“核实后维持原评分”分支。修改评分需要重新评分及复核，未在此弹窗模拟。')+noteField('复核依据及对员工的说明'),btn('维持原评分并反馈','do-resolve',true));break;
    case 'do-resolve':transact('resolve-appeal',{note:document.getElementById('note').value});break;
    case 'archive-modal':modal('结束考核并锁定结果','<p>员工已确认，数据与评分复核已完成。结束后保存最终分数、规则、材料和处理记录，仍可查询，但不能直接修改。</p><p class="subline">这一步也叫归档，不等于发工资。发现错误需要另走更正流程。</p>',btn('结束考核并锁定结果','do-archive',true));break;
    case 'do-archive':transact('archive');break;
    case 'payroll-modal':modal('生成模拟绩效工资依据',`<p>已确认绩效基数：¥2,000.00</p><p>考核分数：${totalScore(state)}；市场模板系数：${coefficient(totalScore(state))}</p><p class="metric">¥${money(2000*coefficient(totalScore(state)))} <small>绩效金额</small></p>`+callout('仅生成本地演示依据，不涉及实际发放、基本工资或银行操作。'),btn('生成模拟依据','do-payroll',true));break;
    case 'do-payroll':transact('payroll');break;
    case 'save-template':state.drafts[templateId]={...state.drafts[templateId],note:document.getElementById('template-note').value};save();notify('讨论草稿已保存在本地，正式规则仍待确认。');break;
    case 'save-rule':{const i=Number(document.getElementById('rule-index').value),raw=document.getElementById('rule-max').value,max=Number(raw),target=document.getElementById('rule-target').value.trim(),text=document.getElementById('rule-text').value.trim();if(raw===''||!Number.isFinite(max)||max<0||max>100||!target||!text){document.getElementById('form-error').textContent='请填写0—100以内满分、目标与计分说明。';break;}const d=state.drafts[templateId]||{},rules={...d.rules,[i]:[rulesFor(templateId)[i][0],max,target,text]};state.drafts[templateId]={...d,rules};close();render();notify('指标草稿已保存；业务规则仍待确认。');break;}
    case 'preview':modal('签约客户数 · 计分试算',`<div class="formgrid"><label class="field"><span>完成客户数（家）</span><input id="preview-value" type="number" value="3" min="0" step="1"></label><div><span class="muted">试算得分</span><p id="preview-result" class="metric">${signedPoints(state)} <small>／20分</small></p></div></div><p>本期目标${state.standard?.signedTarget||4}家，满分20，每少1家扣5分；最低0，最高20。</p><p class="hintline">试算不保存实际业绩、不改变考核结果。独立运维示例：42/50＝84%，原表对应15分。</p>`);break;
    case 'import':importModal();break;
    case 'fix-import':state.importStatus='fixed';save();importModal();break;
    case 'confirm-import':if(state.role!=='hr'){notify('仅HR可确认本演示导入。');break;}if(state.importStatus!=='fixed'||state.imported)break;state.imported=true;close();render();notify('模拟批次已导入1行，待审核；主案例未改变。');break;
    case 'stage-example':state.page='onboard';render();break;
    case 'save-training':{if(!['hr','manager','training'].includes(state.role)){notify('员工不能修改阶段评分。');break;}const rows=trainingRows(),vals=rows.map((r,i)=>document.getElementById('training-'+i).value);if(vals.some((v,i)=>v!==''&&(!Number.isFinite(Number(v))||Number(v)<0||Number(v)>rows[i][1]))){notify('得分必须在对应维度满分以内。');break;}state.trainingScores[state.trainingRole+state.trainingStage]=vals;save();notify('已暂存当前岗位、阶段的评分草稿；尚未发布。');break;}
    case 'feedback':modal('登记活动反馈','<label class="field"><span>活动名称</span><input id="activity" placeholder="例如：9月客户宣讲"></label>'+noteField('反馈内容与事实依据')+callout('保存后为待核实反馈，不直接加分、扣分或触发工资调整。'),btn('保存待核实反馈','save-feedback',true));break;
    case 'save-feedback':{const activity=document.getElementById('activity').value.trim(),note=document.getElementById('note').value.trim();if(!activity||!note){document.getElementById('form-error').textContent='请填写活动和反馈内容。';break;}state.feedback.push({activity,note});close();render();notify('活动反馈已保存，等待核实。');break;}
    case 'observation':modal('观察期 · 流程示例','<ol><li>4次已核实有效评差：触发评估，不能只凭未核实反馈。</li><li>HR审批后确定观察期起止日期。</li><li>到期复评：≥75分且无再次触发条件，才可提出解除建议。</li><li>再次触发或低于75分，提交HR处理。</li></ol><p class="subline">观察期工资安排需依据批准制度通过人事处理，绩效页不直接改薪。本例未针对真实员工启动流程。</p>');break;
    case 'reset-modal':modal('重新开始本地演示','<p>将清除这份原型的演示进度、暂存评分、讨论意见和反馈记录。不会影响真实系统或其他文件。</p>',btn('取消','close')+btn('重置本地演示','reset',true));break;
    case 'reset':state=initialState();close();render();notify('已回到第一步：HR制定考核标准。');break;
  }
}
document.addEventListener('click',e=>{const a=e.target.closest('[data-action]'),p=e.target.closest('[data-page]');if(a&&!a.disabled)action(a.dataset.action);else if(p){state.page=p.dataset.page;render();window.scrollTo(0,0);}});
document.addEventListener('change',e=>{if(e.target.id==='role'){state.role=e.target.value;state.page='overview';close();render();}if(e.target.id==='mobile-page'){state.page=e.target.value;render();}if(e.target.id==='training-role'){state.trainingRole=e.target.value;render();}});
document.addEventListener('input',e=>{if(e.target.id==='preview-value'){const v=e.target.value,n=Number(v);document.getElementById('preview-result').innerHTML=v===''||!Number.isInteger(n)||n<0?'<small>请输入非负整数</small>':`${Math.max(0,Math.min(20,20-Math.max(0,(state.standard?.signedTarget||4)-n)*5))} <small>／20分</small>`;}});
document.addEventListener('keydown',e=>{const dialog=document.querySelector('[role="dialog"]');if(!dialog)return;if(e.key==='Escape')close();if(e.key==='Tab'){const els=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),textarea,select')];if(!els.length)return;const first=els[0],last=els[els.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
render();
}
