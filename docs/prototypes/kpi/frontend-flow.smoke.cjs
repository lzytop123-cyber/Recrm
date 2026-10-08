// Source-level generated markup checks. This is not a browser or visual test.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',checked:false,classList:{add(){},remove(){}},focus(){}});return nodes.get(id);}
const document={getElementById:node,querySelector(){return null;},addEventListener(){},activeElement:null,title:''};
const saved=new Map();
const context={document,localStorage:{getItem(key){return saved.get(key)||null;},setItem(key,value){saved.set(key,value);}},window:{scrollTo(){}},setTimeout(){return 1;},clearTimeout(){},console};
vm.createContext(context);
const source=fs.readFileSync(__dirname+'/frontend-flow.js','utf8');
assert.ok(source.endsWith('render();\n}\n'));
const instrumented=source.replace(/render\(\);\n}\n$/,`globalThis.probe={render,action,setState(s){state=s;},initialState,getState(){return state;},defaultPlan,setTemplate(id){templateId=id;},rulesFor};render();\n}\n`);
vm.runInContext(instrumented,context);
const p=context.probe;
let count=0;
for(const role of ['hr','employee','manager','training'])for(const stage of [-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7])for(const page of ['overview','mine','team','detail','cycles','templates','template','facts','archive','onboard','lecturer']){
  const s=p.initialState();Object.assign(s,{role,stage,page});if(stage>-5)s.standard={name:'演示标准',signedTarget:4};if(stage>=-3)s.standardApproved=true;if(stage>=-2)s.plan=p.defaultPlan();if(stage>1)s.periodEnded=true;if(stage>=3)s.verified=true;if(stage>=5)s.scores=[8,4,4,3,3];if(stage===7)s.resultConfirmed=true;p.setState(s);p.render();const html=node('app').innerHTML;
  assert.ok(html.includes('<h1>'),`${role}/${stage}/${page}`);assert.ok(!html.includes('undefined'),`${page} undefined`);assert.ok(!html.includes('NaN'),`${page} NaN`);count++;
}
for(const [id,expected] of [['ops',6],['content',4],['brand',20],['host',8],['ads',7],['sales-D5',4],['function-M1',5],['sales-M3',4]])assert.equal(p.rulesFor(id).length,expected,id);
for(const id of ['demo','market','ops','content','brand','host','ads','lecturer','sales-D5','function-M3']){p.setTemplate(id);const s=p.initialState();s.page='template';p.setState(s);p.render();assert.ok(node('app').innerHTML.includes('指标规则'));}
const s=p.initialState();p.setState(s);
p.action('standard-modal');node('standard-name').value='完整流程样例';node('standard-target').value='4';node('standard-accepted').checked=true;p.action('do-standard');assert.equal(p.getState().stage,-4);
p.action('role-manager');p.action('do-approve-standard');assert.equal(p.getState().stage,-3);
p.action('role-hr');p.action('plan-modal');for(const [key,val] of Object.entries(p.defaultPlan()))node('plan-'+key).value=val;p.action('do-plan');assert.equal(p.getState().stage,-2);
p.action('role-employee');p.action('ack-plan-modal');node('plan-accepted').checked=true;p.action('do-ack-plan');assert.equal(p.getState().stage,-1);
p.action('role-hr');p.action('preflight-modal');p.action('do-preflight');assert.equal(p.getState().stage,0);
p.action('launch');assert.ok(node('overlay').innerHTML.includes('检查并发起9月考核'));p.action('do-launch');assert.equal(p.getState().stage,1);assert.equal(p.getState().periodEnded,false);p.action('period-end-modal');p.action('do-period-end');assert.equal(p.getState().periodEnded,true);p.action('role-employee');p.action('evidence-modal');assert.ok(node('overlay').innerHTML.includes('客户行业'));
assert.ok(node('overlay').innerHTML.includes('具体需求'));
assert.ok(node('overlay').innerHTML.includes('沟通依据'));
p.action('do-evidence');assert.equal(p.getState().evidence,false);
for(const id of ['lead-1','lead-2','lead-3']){
 p.action('material-edit-'+id);node('material-id').value=id;p.action('material-example');
 assert.ok(node('material-value').value.length>10);p.action('material-save');
}
assert.ok(node('overlay').innerHTML.includes('提交材料给HR'));
const reload={...context};vm.createContext(reload);vm.runInContext(instrumented,reload);
assert.equal(reload.probe.getState().stage,1);
assert.ok(reload.probe.getState().evidenceItems.find(x=>x.id==='lead-2').value.includes('10月'));
assert.equal(reload.probe.getState().evidence,false);
p.action('do-evidence');assert.equal(p.getState().evidence,true);p.action('role-hr');p.action('verify-modal');assert.ok(node('overlay').innerHTML.includes('退回此条'));
p.action('material-return-lead-2');node('material-id').value='lead-2';node('note').value='补充具体采购日期';p.action('do-reject-evidence');
p.action('role-employee');p.action('evidence-modal');assert.ok(node('overlay').innerHTML.includes('补充具体采购日期'));
p.action('material-edit-lead-2');node('material-id').value='lead-2';node('material-value').value='10月采购；记录DEMO-002';p.action('material-save');p.action('do-evidence');
p.action('role-hr');p.action('do-verify');assert.equal(p.getState().stage,2);
p.action('role-employee');p.action('self-modal');node('checked').checked=true;node('note').value='已核对';p.action('do-self');p.action('role-manager');p.action('score-modal');p.action('sample-score');p.action('submit-score');assert.equal(p.getState().stage,4);p.action('role-hr');p.action('do-review');p.action('role-employee');p.action('do-confirm');p.action('role-hr');p.action('do-archive');p.action('do-payroll');assert.equal(p.getState().payroll,true);
p.setState(p.initialState());p.setTemplate('ops');p.action('edit-rule-0');node('rule-index').value='0';node('rule-max').value='15';node('rule-target').value='讨论中的目标';node('rule-text').value='待确认计分规则';p.action('save-rule');assert.equal(p.getState().drafts.ops.rules[0][1],15);node('template-note').value='讨论意见';p.action('save-template');assert.equal(p.getState().drafts.ops.rules[0][1],15);
console.log(`${count} role/stage/page markup checks passed`);
console.log('Template contents, event-handler flow and draft persistence checks passed');
