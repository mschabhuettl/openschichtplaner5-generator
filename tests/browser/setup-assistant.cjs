const assert=require('node:assert/strict');
const {prepare}=require('../../sp5generator/static/setup-assistant.js');
const make=()=>({metadata:{adapter:'sp5-api'},timezone:'UTC',period_start:'2026-02-01',period_end:'2026-02-28',context_start:'2026-01-01',context_end:'2026-03-31',unresolved:[],positions:[{id:'position',function_id:'service'}],demands:[],shifts:[],profiles:[],restrictions:[],wishes:[],employees:[{id:'person',approvals:[],profile_ids:[],allowed_kinds:['day','night'],target_minutes:100}]});
let old=make();old.employees[0].allowed_kinds=['night'];old.employees[0].target_minutes=900;old.employees[0].approvals=[{function_id:'service',workplace_id:'*',supervised:true,valid_from:'2026-01-01',valid_until:'2026-01-31'}];old.profiles=[{id:'p',confirmed:true,valid_from:'2026-01-01',valid_until:'2026-12-31'}];old.employees[0].profile_ids=['p'];
const fresh=make(),copy=structuredClone(fresh);fresh.employees[0].approvals=[{function_id:'service',supervised:false}];
assert.throws(()=>prepare(fresh,old));
const result=prepare(fresh,old,{sameSource:true});assert.deepEqual(result.employees[0].allowed_kinds,['night']);assert.equal(result.employees[0].target_minutes,100);assert.equal(result.employees[0].approvals[0].supervised,true);assert.equal(result.employees[0].approvals[0].valid_until,'2026-01-31');assert.equal(result.profiles[0].id,'reused:p');assert.ok(result.unresolved.length);assert.equal(fresh.employees[0].approvals[0].supervised,false);
old.employees[0].approvals=[];assert.deepEqual(prepare(fresh,old,{sameSource:true}).employees[0].approvals,[]);
old.timezone='Europe/Vienna';assert.throws(()=>prepare(fresh,old,{sameSource:true}));
assert.equal(prepare(copy,null).metadata.setup_review.newPeople.length,1);

// Reusing personal qualifications must also retain the position's explicit gate.
const qualificationSource=make();
Object.assign(qualificationSource.positions[0],{workplace_id:'workplace',qualifications_required:true,qualification_ids:['training'],qualification_level:2});
const qualificationImport=make();
Object.assign(qualificationImport.positions[0],{workplace_id:'workplace',qualifications_required:false,qualification_ids:[],qualification_level:1});
const retained=prepare(qualificationImport,qualificationSource,{sameSource:true});
assert.equal(retained.positions[0].qualifications_required,true);
assert.deepEqual(retained.positions[0].qualification_ids,['training']);
assert.equal(retained.positions[0].qualification_level,2);
assert.equal(qualificationImport.positions[0].qualifications_required,false);
retained.positions[0].qualification_ids.push('another');
assert.deepEqual(qualificationSource.positions[0].qualification_ids,['training']);

// A new source gate is never silently disabled or replaced by older settings.
const sourceGate=structuredClone(qualificationImport);
Object.assign(sourceGate.positions[0],{qualifications_required:true,qualification_ids:['new-training'],qualification_level:3});
const conflict=prepare(sourceGate,qualificationSource,{sameSource:true});
assert.deepEqual(conflict.positions[0].qualification_ids,['new-training']);
assert.equal(conflict.positions[0].qualification_level,3);
assert(conflict.unresolved.some(text=>text.includes('Qualifikationsanforderungen')));
const disabledPrevious=structuredClone(qualificationSource);
disabledPrevious.positions[0].qualifications_required=false;
assert.equal(prepare(sourceGate,disabledPrevious,{sameSource:true}).positions[0].qualifications_required,true);

// Same ID with another workplace is not a safe identity match.
const changedWorkplace=structuredClone(qualificationImport);
changedWorkplace.positions[0].workplace_id='another-workplace';
const unmatched=prepare(changedWorkplace,qualificationSource,{sameSource:true});
assert.equal(unmatched.positions[0].qualifications_required,false);
assert(unmatched.unresolved.some(text=>text.includes('Qualifikationspflicht')));
const removedPosition=structuredClone(qualificationImport);removedPosition.positions=[];
assert(prepare(removedPosition,qualificationSource,{sameSource:true}).unresolved.some(text=>text.includes('Qualifikationspflicht')));

// An enabled but empty gate remains enabled; reuse is not an implicit repair.
const emptyGate=structuredClone(qualificationSource);emptyGate.positions[0].qualification_ids=[];
const stillEmpty=prepare(qualificationImport,emptyGate,{sameSource:true});
assert.equal(stillEmpty.positions[0].qualifications_required,true);
assert.deepEqual(stillEmpty.positions[0].qualification_ids,[]);

// Calendar preparation is continuous across month lengths, leap years and DST.
const {followingPeriod}=require('../../sp5generator/static/setup-assistant.js');
const monthly={period_start:'2026-01-01',period_end:'2026-01-31'};
assert.deepEqual(followingPeriod(monthly,'month'),{start:'2026-02-01',end:'2026-02-28',days:28});
assert.deepEqual(followingPeriod(monthly,'same'),{start:'2026-02-01',end:'2026-03-03',days:31});
assert.deepEqual(followingPeriod({period_start:'2028-01-01',period_end:'2028-01-31'},'month'),{start:'2028-02-01',end:'2028-02-29',days:29});
assert.deepEqual(followingPeriod({period_start:'2026-12-01',period_end:'2026-12-31'},'month'),{start:'2027-01-01',end:'2027-01-31',days:31});
assert.deepEqual(followingPeriod({period_start:'2026-03-23',period_end:'2026-03-29'},'same'),{start:'2026-03-30',end:'2026-04-05',days:7});
assert.deepEqual(followingPeriod({period_start:'2026-02-02',period_end:'2026-02-08'},'month'),{start:'2026-02-09',end:'2026-02-28',days:20});
const beforeNext=structuredClone(monthly);followingPeriod(monthly,'same');assert.deepEqual(monthly,beforeNext);
for(const previous of [null,{period_start:'2026-02-30',period_end:'2026-03-03'},{period_start:'2026-03-02',period_end:'2026-03-01'},{period_start:'2025-01-01',period_end:'2026-12-31'},{period_start:'9999-12-01',period_end:'9999-12-31'}])assert.throws(()=>followingPeriod(previous,'month'));
assert.throws(()=>followingPeriod(monthly,'unknown'));
