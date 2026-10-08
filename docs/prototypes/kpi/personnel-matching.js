'use strict';
(function(){
function demoRoster(){return [
  {id:'u1',name:'张明',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u2',name:'王芳',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'regular',daysInPeriod:22},
  {id:'u3',name:'李强',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u4',name:'赵敏',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'probation',daysInPeriod:25},
  {id:'u5',name:'孙悦',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'regular',daysInPeriod:10},
  {id:'u6',name:'刘川',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'long_leave',employmentType:'regular',daysInPeriod:30},
  {id:'u12',name:'何杰',department:'市场部',role:'市场业务',manager:'李岚',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u7',name:'李梅',department:'品宣团队',role:'品宣专员',manager:'周宁',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u13',name:'白露',department:'品宣团队',role:'品宣专员',manager:'周宁',employmentStatus:'active',employmentType:'regular',daysInPeriod:27},
  {id:'u14',name:'唐果',department:'品宣团队',role:'品宣专员',manager:'周宁',employmentStatus:'active',employmentType:'probation',daysInPeriod:20},
  {id:'u8',name:'陈浩',department:'AI技术运维',role:'运维专员',manager:'周宁',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u9',name:'韩雪',department:'AI技术运维',role:'运维专员',manager:'周宁',employmentStatus:'active',employmentType:'regular',daysInPeriod:28},
  {id:'u15',name:'罗斌',department:'AI技术运维',role:'运维专员',manager:'周宁',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u10',name:'许航',department:'内容制作团队',role:'内容专员',manager:'陆可',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u11',name:'邓蕾',department:'内容制作团队',role:'内容专员',manager:'陆可',employmentStatus:'active',employmentType:'regular',daysInPeriod:26},
  {id:'u16',name:'沈琪',department:'内容制作团队',role:'内容专员',manager:'陆可',employmentStatus:'active',employmentType:'regular',daysInPeriod:29},
  {id:'u17',name:'林悦',department:'直播团队',role:'主播',manager:'高远',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u18',name:'江夏',department:'直播团队',role:'主播',manager:'高远',employmentStatus:'active',employmentType:'regular',daysInPeriod:24},
  {id:'u19',name:'曹阳',department:'直播团队',role:'投手',manager:'高远',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u20',name:'温莎',department:'直播团队',role:'投手',manager:'高远',employmentStatus:'active',employmentType:'regular',daysInPeriod:18},
  {id:'u21',name:'俞晨',department:'培训部',role:'业务新人',manager:'苏晚',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u22',name:'方宁',department:'培训部',role:'职能新人',manager:'苏晚',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u23',name:'顾琛',department:'讲师部',role:'讲师',manager:'叶川',employmentStatus:'active',employmentType:'regular',daysInPeriod:30},
  {id:'u24',name:'莫言',department:'讲师部',role:'讲师',manager:'叶川',employmentStatus:'active',employmentType:'regular',daysInPeriod:28},
  {id:'u25',name:'安然',department:'讲师部',role:'讲师',manager:'叶川',employmentStatus:'active',employmentType:'regular',daysInPeriod:12}
];}
function matchPersonnel(roster,template,period,policy={},existingKeys=[]){
  const includeProbation=policy.includeProbation===true,minDays=Number(policy.minDays||0),existing=new Set(existingKeys);
  const pool=roster.filter(x=>x.department===template.department&&x.role===template.role);
  const all=pool.map(person=>{
    let status='matched',reason='部门、岗位及在岗条件均符合';
    const key=person.id+'|'+template.id+'|'+period.month;
    if(existing.has(key)){status='blocked';reason='本周期已存在该模板考核';}
    else if(person.employmentStatus==='long_leave'){status='excluded';reason='长期休假';}
    else if(person.employmentStatus!=='active'){status='excluded';reason='非在职状态';}
    else if(person.employmentType==='probation'&&!includeProbation){status='excluded';reason='试用期不参加月度考核';}
    else if(person.daysInPeriod<minDays){status='excluded';reason='本月在岗'+person.daysInPeriod+'天，少于'+minDays+'天';}
    return {...person,status,reason};
  });
  return {all,matched:all.filter(x=>x.status==='matched'),excluded:all.filter(x=>x.status==='excluded'),blocked:all.filter(x=>x.status==='blocked'),template:{id:template.id,department:template.department,role:template.role},period:{...period},policy:{includeProbation,minDays}};
}
function validateSelection(result,selectedIds,reasons={}){
  const selected=new Set(selectedIds||[]),errors=[];
  if(!selected.size)errors.push('至少选择1名考核人员');
  for(const person of result.all){
    if(person.status==='blocked'&&selected.has(person.id))errors.push(person.name+'存在重复考核，不能再次选择');
    if(person.status==='excluded'&&selected.has(person.id)&&!reasons[person.id]?.trim())errors.push('手动纳入'+person.name+'时必须填写原因');
    if(person.status==='matched'&&!selected.has(person.id)&&!reasons[person.id]?.trim())errors.push('排除自动匹配人员'+person.name+'时必须填写原因');
  }
  for(const id of selected)if(!result.all.some(x=>x.id===id))errors.push('选择了不属于模板范围的人员');
  return errors;
}
function buildSnapshots(result,selectedIds,reasons={}){
  const selected=new Set(selectedIds||[]);
  return result.all.filter(x=>selected.has(x.id)&&x.status!=='blocked').map(x=>({
    id:x.id,name:x.name,department:x.department,role:x.role,manager:x.manager,
    employmentStatus:x.employmentStatus,employmentType:x.employmentType,daysInPeriod:x.daysInPeriod,
    matchReason:x.reason,adjustmentType:x.status==='excluded'?'manual_include':'automatic',
    adjustmentReason:x.status==='excluded'?(reasons[x.id]||'').trim():''
  }));
}
const api={demoRoster,matchPersonnel,validateSelection,buildSnapshots};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(typeof globalThis!=='undefined')globalThis.PersonnelMatching=api;
})();
