const assert=require('node:assert/strict');
const {apply,overview,members}=require('../../sp5generator/static/team-scope.js');
const make=()=>({employees:[
 {id:'a',team_ids:['ct','1450'],excluded:false},
 {id:'b',team_ids:['1450'],excluded:false},
 {id:'c',team_ids:['ct'],excluded:false},
 {id:'d',team_ids:[],excluded:false},
 {id:'e',team_ids:['1450'],excluded:true}]});

let s=make();
// Someone in two groups is taken out here as well - that has to be reported, not hidden.
assert.deepEqual(apply(s,'1450',true),{changed:2,total:3,shared:1});
assert.deepEqual(s.employees.map(e=>e.excluded),[true,true,false,false,true]);
assert.deepEqual(apply(s,'1450',true),{changed:0,total:3,shared:0},'idempotent');

// Taking a group back in must not silently revive people excluded for other reasons.
assert.deepEqual(apply(s,'1450',false),{changed:3,total:3,shared:1});
assert.deepEqual(s.employees.map(e=>e.excluded),[false,false,false,false,false]);

s=make();assert.throws(()=>apply(s,'',true),/Gruppe wählen/);
assert.throws(()=>apply(s,'unbekannt',true),/keine Mitglieder/);
assert.deepEqual(s.employees.map(e=>e.excluded),[false,false,false,false,true],'failed calls change nothing');

assert.deepEqual(members(s,'ct').map(e=>e.id),['a','c']);
const counts=overview(make());
assert.deepEqual([...counts.entries()].sort(),[['1450',{total:3,excluded:1}],['ct',{total:2,excluded:0}]]);
assert.equal(overview({employees:[]}).size,0,'no groups, no control');

const {teaching,learning}=require('../../sp5generator/static/team-scope.js');
const school=()=>({employees:[
 {id:'m1',team_ids:['ausbilder'],mentor_capacity:0,approvals:[{supervised:false}]},
 {id:'m2',team_ids:['ausbilder'],mentor_capacity:2,approvals:[]},
 {id:'l1',team_ids:['lehre'],mentor_capacity:0,approvals:[{supervised:false},{supervised:false}]},
 {id:'l2',team_ids:['lehre'],mentor_capacity:0,approvals:[]}]});

let t=school();
// A deliberate bulk assignment sets the group, and reports how many it really moved.
assert.deepEqual(teaching(t,'ausbilder',1),{changed:2,total:2});
assert.deepEqual(t.employees.map(e=>e.mentor_capacity),[1,1,0,0]);
assert.deepEqual(teaching(t,'ausbilder',1),{changed:0,total:2},'idempotent');
assert.deepEqual(teaching(t,'ausbilder',0),{changed:2,total:2},'the mark can be taken back');
for(const bad of [1.5,-1,'1',null,true])assert.throws(()=>teaching(t,'ausbilder',bad),/ganze Zahl/);

t=school();
// Someone without a single approval cannot be put under supervision - say so, do not pretend.
assert.deepEqual(learning(t,'lehre',true),{changed:2,people:1,total:2,without:1});
assert.deepEqual(t.employees.map(e=>(e.approvals||[]).map(a=>a.supervised)),[[false],[],[true,true],[]]);
assert.deepEqual(learning(t,'lehre',true),{changed:0,people:0,total:2,without:1},'idempotent');
assert.deepEqual(learning(t,'lehre',false),{changed:2,people:1,total:2,without:1});
assert.throws(()=>learning(t,'unbekannt',true),/keine Mitglieder/);
for(const call of [()=>teaching(t,'',1),()=>learning(t,'',true)])assert.throws(call,/Gruppe wählen/);

// A parent node inherited into team_ids must not sweep out everyone below it.
const geerbt=()=>({metadata:{direct_group_memberships:{a:[12],b:[38],c:[12]}},employees:[
 {id:'a',team_ids:['sp5:group:12','sp5:group:38'],excluded:false},
 {id:'b',team_ids:['sp5:group:38'],excluded:false},
 {id:'c',team_ids:['sp5:group:12','sp5:group:38'],excluded:false}]});
let g=geerbt();
assert.deepEqual(apply(g,'sp5:group:38',true),{changed:1,total:1,shared:0});
assert.deepEqual(g.employees.map(e=>e.excluded),[false,true,false]);
assert.deepEqual([...overview(geerbt()).entries()].sort(),
 [['sp5:group:12',{total:2,excluded:0}],['sp5:group:38',{total:1,excluded:0}]]);
// Without the source's own membership list the inherited ids remain the only answer.
const ohne=geerbt();delete ohne.metadata;
assert.deepEqual(apply(ohne,'sp5:group:38',true),{changed:3,total:3,shared:2});
