const assert=require('node:assert/strict');
const api=require('./frontend-simple.js');
assert.equal(typeof api.createState,'function','Simplified workflow must be available');
const s=api.createState();
api.launch(s,{employees:['张明','王芳'],reviewRequired:false,dataDue:'2026-10-02',scoreDue:'2026-10-05',reviewDue:'2026-10-06',resultDue:'2026-10-08'});
assert.equal(s.records.length,2);
assert.throws(()=>api.launch(s,{}));
const a=s.records[0],b=s.records[1];
assert.throws(()=>api.act(s,a.id,'submit',{note:'已核对',checked:true,materials:{}}));
api.act(s,a.id,'period-end');
s.role='employee';
assert.throws(()=>api.act(s,a.id,'submit',{note:'已核对',checked:true,materials:{}}));
const materials={'lead-1':'餐饮行业','lead-2':'10月启动门店推广','lead-3':'9月20日电话沟通，记录DEMO-003'};
api.act(s,a.id,'draft',{note:'工作说明',materials});
assert.equal(a.stage,1);assert.equal(a.verified,false);
const reload=JSON.parse(JSON.stringify(s));
assert.equal(reload.records[0].selfNote,'工作说明');
api.act(s,a.id,'submit',{note:'工作说明',checked:true,materials});
assert.equal(a.stage,3);assert.equal(b.stage,1);assert.equal(b.selfNote,'');
assert.throws(()=>api.act(s,a.id,'score',{scores:[8,4,4,3,3],note:'评分',checked:true}));
s.role='manager';
assert.throws(()=>api.act(s,a.id,'score',{scores:[8,4,4,3,3],note:'评分',checked:false}));
api.act(s,a.id,'return-item',{itemId:'lead-2',note:'说明采购时间'});
assert.equal(a.stage,1);
assert.equal(a.evidenceItems.find(x=>x.id==='lead-1').value,'餐饮行业');
s.role='employee';
assert.throws(()=>api.act(s,a.id,'submit',{note:'工作说明',checked:true,materials:{}}));
api.act(s,a.id,'submit',{note:'工作说明',checked:true,materials:{'lead-2':'计划10月采购，记录DEMO-002'}});
s.role='manager';api.act(s,a.id,'score',{scores:[8,4,4,3,3],note:'核实材料后评分',checked:true});
assert.equal(a.stage,5);assert.equal(a.verified,true);
s.role='employee';api.act(s,a.id,'appeal',{note:'请核实需求评分'});
assert.throws(()=>api.act(s,a.id,'confirm'));
s.role='hr';api.act(s,a.id,'resolve',{note:'已核实，维持原分'});
s.role='employee';api.act(s,a.id,'confirm');
assert.equal(a.stage,7);assert.equal(a.resultConfirmed,true);assert.equal(b.stage,1);
assert.throws(()=>api.act(s,a.id,'draft',{note:'改'}));
const t=api.createState();api.launch(t,{employees:['张明'],reviewRequired:true,dataDue:'2026-10-02',scoreDue:'2026-10-05',reviewDue:'2026-10-06',resultDue:'2026-10-08'});
const r=t.records[0];api.act(t,r.id,'period-end');t.role='employee';api.act(t,r.id,'submit',{materials,note:'说明',checked:true});t.role='manager';api.act(t,r.id,'score',{scores:[8,4,4,3,3],note:'说明',checked:true});assert.equal(r.stage,4);
t.role='employee';assert.throws(()=>api.act(t,r.id,'confirm'));t.role='hr';api.act(t,r.id,'review');assert.equal(r.stage,5);
const old={version:3,stage:4,role:'hr',periodEnded:true,standard:{name:'旧规则',signedTarget:5},plan:{dataDue:'2026-10-02'},selfNote:'旧说明',scores:[8,4,4,3,3],verified:true,log:[],evidenceNote:'旧材料'};
const migrated=api.migrate(old);assert.equal(migrated.records[0].stage,4);assert.equal(migrated.records[0].reviewRequired,true);assert.equal(migrated.records[0].standard.signedTarget,5);assert.equal(migrated.records[0].selfNote,'旧说明');
assert.equal(api.migrate({...old,stage:6,resultConfirmed:true}).records[0].stage,7);
assert.throws(()=>api.launch(api.createState(),{employees:['张明'],dataDue:'2026-10-09',scoreDue:'2026-10-05',resultDue:'2026-10-08'}));
console.log('Simplified flow: batch isolation, draft, returns, optional review, appeal, automatic completion and migration passed');
// Multi-department batches stay independent after one launch.
const multi=api.createState();
api.launch(multi,{
  batches:[
    {templateId:'demo',personnel:[{id:'u1',name:'张明',department:'市场部',role:'市场业务',manager:'李岚',adjustmentType:'automatic'}]},
    {templateId:'demo-ops',personnel:[{id:'u8',name:'陈浩',department:'AI技术运维',role:'运维专员',manager:'周宁',adjustmentType:'automatic'}]}
  ],
  reviewRequired:false,dataDue:'2026-10-02',scoreDue:'2026-10-05',reviewDue:'2026-10-06',resultDue:'2026-10-08'
});
assert.equal(multi.batches.length,2);
assert.equal(multi.records.length,2);
assert.equal(multi.records[0].batchId,'batch-1');
assert.equal(multi.records[1].personSnapshot.department,'AI技术运维');
assert.throws(()=>api.launch(multi,{batches:[{templateId:'demo',personnel:[{id:'u2',name:'王芳',department:'市场部',role:'市场业务',manager:'李岚',adjustmentType:'automatic'}]}],dataDue:'2026-10-02',scoreDue:'2026-10-05',resultDue:'2026-10-08'}));
console.log('Multi-department launch batches passed');
// HR return must require re-submission by the manager, not publish stale scores.
const reviewCase=api.migrate(old),rr=reviewCase.records[0];
api.act(reviewCase,rr.id,'return-score',{note:'补充评分依据'});
assert.equal(rr.stage,3);
assert.throws(()=>api.act(reviewCase,rr.id,'review'));
reviewCase.role='manager';
assert.throws(()=>api.act(reviewCase,rr.id,'score',{scores:[11,4,4,3,3],note:'依据',checked:true}));
// Fresh starts preserve failed form input outside the model; no partial batch mutation.
const invalid=api.createState();
assert.throws(()=>api.launch(invalid,{employees:['张明','未知'],dataDue:'2026-10-02',scoreDue:'2026-10-05',resultDue:'2026-10-08'}));
assert.equal(invalid.launched,false);assert.equal(invalid.records.length,0);
console.log('HR return and atomic launch validation passed');
