'use strict';
(function(){
const clone=x=>JSON.parse(JSON.stringify(x));
const need=(ok,text)=>{if(!ok)throw new Error(text);};
const now=()=>new Date().toLocaleString('zh-CN',{hour12:false});
const demoMetrics=[
 ['有效线索',10,'10条','条','线索及客户画像','目标10条，每少1条扣1分，最低0分'],
 ['签约客户',20,'4家','家','已确认签约记录','每完成1家得5分，最高20分'],
 ['新增客户',10,'10家','家','客户档案','完成率×10，最高10分'],
 ['跟进时效',5,'无超时','次','跟进记录','每超时1次扣1分，最低0分'],
 ['客户拜访',20,'15家且新客≥5家','家','拜访记录','两个条件均达标得20分'],
 ['有效渠道拓展',10,'10家','家','渠道审核记录','完成率×10，最高10分'],
 ['需求分析落地',10,'主管评价','分','员工材料','主管在0—10分内评分'],
 ['销售标准动作',5,'主管评价','分','员工材料','主管在0—5分内评分'],
 ['内部协同',4,'主管评价','分','协作记录','主管在0—4分内评分'],
 ['客户信息同步',3,'主管评价','分','客户信息台账','主管在0—3分内评分'],
 ['复盘与计划',3,'主管评价','分','复盘记录','主管在0—3分内评分']
].map((x,i)=>({id:'demo-'+(i+1),name:x[0],max:x[1],target:x[2],unit:x[3],source:x[4],formula:x[5],evidence:i<6?'系统记录':'员工说明/主管评价'}));
function event(t,action,by,note=''){t.history.unshift({action,by,note,at:now()});}
const opsMetrics=[
  {id:'ops-1',name:'系统可用率',max:50,target:'99.9%',unit:'%',source:'运维监控平台',formula:'达到99.9%得满分；重大责任事故按制度扣分',evidence:'监控报表与异常记录'},
  {id:'ops-2',name:'故障响应及时率',max:50,target:'95%',unit:'%',source:'工单系统',formula:'按及时关闭工单比例分档计分',evidence:'工单受理及关闭时间'}
];
const contentMetrics=[
  {id:'content-1',name:'内容交付数量',max:50,target:'20条',unit:'条',source:'内容任务台账',formula:'达到目标得满分；仅统计验收通过内容',evidence:'已验收内容链接或任务记录'},
  {id:'content-2',name:'内容质量评分',max:50,target:'90分',unit:'分',source:'主管评分',formula:'主管按准确性、表达和交付质量评分',evidence:'质量评分表与修改记录'}
];
const brandMetrics=[
  {id:'brand-1',name:'品牌项目交付',max:60,target:'按计划完成',unit:'项',source:'项目台账',formula:'按完成质量和时间分档计分',evidence:'方案、交付物及验收记录'},
  {id:'brand-2',name:'品牌风险事件',max:40,target:'0次',unit:'次',source:'舆情与审批记录',formula:'无重大风险得满分；触发经确认重大风险本项为0分',evidence:'事件调查及处理结论'}
];
const liveHostMetrics=[
  {id:'live-host-1',name:'直播成交额',max:70,target:'100000元',unit:'元',source:'直播平台数据',formula:'按目标完成率计分，退款订单不计入',evidence:'平台结算与订单明细'},
  {id:'live-host-2',name:'直播合规',max:30,target:'无重大违规',unit:'项',source:'直播巡检记录',formula:'无重大违规得满分；触发重大违规按制度判定',evidence:'巡检记录与违规处理单'}
];
const liveAdsMetrics=[
  {id:'live-ads-1',name:'投放ROI',max:60,target:'1:3',unit:'倍',source:'投放后台',formula:'达到目标得满分；不足按完成比例计分',evidence:'投放报表与消耗明细'},
  {id:'live-ads-2',name:'素材验收通过率',max:40,target:'90%',unit:'%',source:'素材库',formula:'按验收通过素材占比计分',evidence:'素材验收记录'}
];
const trainingMetrics=[
  {id:'train-1',name:'阶段任务完成度',max:70,target:'完成本阶段任务',unit:'项',source:'培训任务台账',formula:'按第5天、第1月或第3月阶段标准分档评分',evidence:'任务成果及带教确认'},
  {id:'train-2',name:'带教评价',max:30,target:'合格',unit:'级',source:'主管评分',formula:'带教人对学习态度与产出评分',evidence:'带教评价表'}
];
const lecturerMetrics=[
  {id:'lecturer-1',name:'课程交付完成率',max:50,target:'100%',unit:'%',source:'排课与交付记录',formula:'按已完成课程占计划课程比例计分',evidence:'排课、签到及课程交付记录'},
  {id:'lecturer-2',name:'学员满意度',max:50,target:'90%',unit:'%',source:'课后评价问卷',formula:'达到90%得满分；低于目标按分档计分',evidence:'有效问卷汇总'}
];
const pubHistory=[{action:'发布V1',by:'HR · 陈悦',note:'仅合成演示',at:'2026/09/01 09:00'}];
function publishedTemplate(id,name,department,role,description,metrics){
  return {id,name,department,role,cycle:'monthly',description,effectiveFrom:'2026-09-01',status:'published',version:1,parentId:null,metrics:clone(metrics),history:clone(pubHistory)};
}
function createTemplateState(){return {nextId:1,templates:[
  publishedTemplate('demo','市场部月度 · 演示版','市场部','市场业务','已确认的合成演示模板，仅用于本地流程演示。',demoMetrics),
  publishedTemplate('demo-ops','运维月度 · 演示版','AI技术运维','运维专员','运维岗位合成演示模板，支持与其他部门一并发起。',opsMetrics),
  publishedTemplate('demo-content','内容月度 · 演示版','内容制作团队','内容专员','内容岗位合成演示模板，支持与其他部门一并发起。',contentMetrics),
  publishedTemplate('demo-brand','品宣月度 · 演示版','品宣团队','品宣专员','品宣岗位合成演示模板。',brandMetrics),
  publishedTemplate('demo-live-host','主播月度 · 演示版','直播团队','主播','直播主播岗位合成演示模板。',liveHostMetrics),
  publishedTemplate('demo-live-ads','投手月度 · 演示版','直播团队','投手','直播投手岗位合成演示模板。',liveAdsMetrics),
  publishedTemplate('demo-training-sales','培训·业务新人 · 演示版','培训部','业务新人','培训部业务新人阶段考核演示模板。',trainingMetrics),
  publishedTemplate('demo-training-func','培训·职能新人 · 演示版','培训部','职能新人','培训部职能新人阶段考核演示模板。',trainingMetrics),
  publishedTemplate('demo-lecturer','讲师月度 · 演示版','讲师部','讲师','讲师岗位合成演示模板。',lecturerMetrics)
]};}
function find(s,id){const t=s.templates.find(x=>x.id===id);need(t,'模板不存在。');return t;}
function editable(t){need(['draft','returned'].includes(t.status),'只有草稿或已退回模板可以修改。');}
function createTemplate(s,p){
  need(p?.name?.trim(),'请填写模板名称。');need(p.department?.trim()&&p.role?.trim(),'请选择适用部门和岗位。');
  const t={id:'custom-'+s.nextId++,name:p.name.trim(),department:p.department.trim(),role:p.role.trim(),cycle:p.cycle||'monthly',description:'',effectiveFrom:'',status:'draft',version:1,parentId:null,metrics:[],history:[]};
  event(t,'新建草稿','HR · 陈悦');s.templates.unshift(t);return t;
}
function updateTemplate(s,id,patch,actor){need(actor==='hr','仅HR可编辑模板。');const t=find(s,id);editable(t);for(const k of ['name','department','role','cycle','description','effectiveFrom'])if(k in patch)t[k]=String(patch[k]).trim();event(t,'保存基本信息','HR · 陈悦');return t;}
function normalizeMetric(m,i){return {id:m.id||'metric-'+(i+1),libraryId:String(m.libraryId||'').trim(),type:String(m.type||'quantity').trim(),name:String(m.name||'').trim(),max:Number(m.max),target:String(m.target||'').trim(),unit:String(m.unit||'').trim(),source:String(m.source||'').trim(),formula:String(m.formula||'').trim(),evidence:String(m.evidence||'').trim()};}
function replaceMetrics(s,id,metrics,actor){need(actor==='hr','仅HR可配置指标。');const t=find(s,id);editable(t);need(Array.isArray(metrics),'指标格式不正确。');t.metrics=metrics.map(normalizeMetric);event(t,'更新全部指标','HR · 陈悦');return t;}
function updateMetric(s,id,metricId,patch,actor){need(actor==='hr','仅HR可配置指标。');const t=find(s,id);editable(t);const index=t.metrics.findIndex(x=>x.id===metricId);need(index>=0,'指标不存在。');t.metrics[index]=normalizeMetric({...t.metrics[index],...patch},index);event(t,'修改指标：'+t.metrics[index].name,'HR · 陈悦');return t.metrics[index];}
function validateTemplate(t){
  const errors=[];
  if(!t.name?.trim())errors.push('模板名称不能为空');
  if(!t.department?.trim()||!t.role?.trim())errors.push('适用部门和岗位不能为空');
  if(!/^\d{4}-\d{2}-\d{2}$/.test(t.effectiveFrom||''))errors.push('请设置生效日期');
  if(!t.description?.trim())errors.push('请填写模板说明');
  if(!t.metrics?.length)errors.push('至少配置1项指标');
  const sum=(t.metrics||[]).reduce((n,x)=>n+(Number.isFinite(Number(x.max))?Number(x.max):0),0);
  if(Math.abs(sum-100)>0.001)errors.push('指标满分合计必须等于100，当前为'+sum);
  const names=new Set();
  (t.metrics||[]).forEach((m,i)=>{
    const pos='第'+(i+1)+'项';
    if(!m.name)errors.push(pos+'指标名称不能为空');else if(names.has(m.name))errors.push('指标名称重复：'+m.name);else names.add(m.name);
    if(!Number.isFinite(Number(m.max))||Number(m.max)<=0)errors.push(pos+'满分必须大于0');
    if(!m.target)errors.push(pos+'目标不能为空');
    if(!m.unit)errors.push(pos+'单位不能为空');
    if(!m.source)errors.push(pos+'数据来源不能为空');
    if(!m.formula)errors.push(pos+'计分规则不能为空');
    if(!m.evidence)errors.push(pos+'材料要求不能为空');
  });
  return errors;
}
function simulate(t,metricId,actual){
  const m=t.metrics.find(x=>x.id===metricId);need(m,'指标不存在。');need(Number.isFinite(Number(actual))&&Number(actual)>=0,'请输入非负实际完成值。');
  const step=m.formula.match(/每完成\s*1\s*[^得]*得\s*(\d+(?:\.\d+)?)\s*分/);
  if(step)return Math.min(m.max,Math.round(Number(actual)*Number(step[1])*100)/100);
  const target=Number((m.target.match(/\d+(?:\.\d+)?/)||[])[0]);
  const ratio=m.formula.includes('完成率')&&Number.isFinite(target)&&target>0;
  need(ratio,'该规则不能自动试算，请由业务负责人核对文字规则。');
  return Math.min(m.max,Math.round(Number(actual)/target*m.max*100)/100);
}
function submitForReview(s,id,actor){need(actor==='hr','仅HR可提交审核。');const t=find(s,id);editable(t);const errors=validateTemplate(t);need(!errors.length,'模板校验未通过：'+errors.join('；'));t.status='in_review';event(t,'提交业务审核','HR · 陈悦');return t;}
function review(s,id,actor,p){need(actor==='manager','仅业务负责人可审核模板。');const t=find(s,id);need(t.status==='in_review','只有审核中的模板可以处理。');need(['approve','return'].includes(p?.decision),'请选择审核结果。');need(p.decision!=='return'||p.note?.trim(),'退回时必须填写修改意见。');t.status=p.decision==='approve'?'approved':'returned';t.reviewNote=p.note?.trim()||'';event(t,p.decision==='approve'?'审核通过':'退回修改','业务负责人 · 李岚',t.reviewNote);return t;}
function publish(s,id,actor){need(actor==='hr','仅HR可发布模板。');const t=find(s,id);need(t.status==='approved','仅审核通过的模板可以发布。');t.status='published';t.publishedAt=now();event(t,'发布V'+t.version,'HR · 陈悦');return t;}
function copyVersion(s,id,actor){need(actor==='hr','仅HR可创建新版本。');const source=find(s,id);need(['published','disabled'].includes(source.status),'只能从已发布或已停用模板创建新版本。');const t=clone(source);t.id='custom-'+s.nextId++;t.parentId=source.id;t.version=source.version+1;t.status='draft';t.name=source.name.replace(/ · V\d+$/,'');t.publishedAt=null;t.history=[];event(t,'从'+source.name+' V'+source.version+'复制','HR · 陈悦');s.templates.unshift(t);return t;}
function disable(s,id,actor){need(actor==='hr','仅HR可停用模板。');const t=find(s,id);need(t.status==='published','只有已发布模板可以停用。');t.status='disabled';event(t,'停用模板','HR · 陈悦');return t;}
function availableForLaunch(s){return s.templates.filter(x=>x.status==='published').map(clone);}
const api={createTemplateState,createTemplate,updateTemplate,replaceMetrics,updateMetric,validateTemplate,simulate,submitForReview,review,publish,copyVersion,disable,availableForLaunch,find};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(typeof globalThis!=='undefined')globalThis.TemplateWorkflow=api;
})();
