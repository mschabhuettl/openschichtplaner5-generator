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
