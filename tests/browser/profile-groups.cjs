const assert=require('node:assert/strict');
const {apply}=require('../../sp5generator/static/profile-groups.js');
const make=()=>({context_start:'2026-01-01',context_end:'2026-03-01',profiles:[{id:'p',confirmed:true,valid_from:'2026-01-01',valid_until:'2026-03-01'},{id:'sp5:unconfirmed',confirmed:false,source:'unresolved'}],employees:[{team_ids:['a'],profile_ids:[]},{team_ids:['a'],profile_ids:['sp5:unconfirmed']},{team_ids:['a'],profile_ids:['individual']},{team_ids:['b'],profile_ids:[]}]});
let s=make();assert.equal(apply(s,'p','a'),2);assert.deepEqual(s.employees.map(e=>e.profile_ids),[['p'],['p'],['individual'],[]]);assert.equal(apply(s,'p','a'),0);
s=make();s.profiles[0].confirmed=false;assert.throws(()=>apply(s,'p'));assert.deepEqual(s,(()=>{const x=make();x.profiles[0].confirmed=false;return x;})());
s=make();s.profiles[0].valid_until='2026-02-01';assert.throws(()=>apply(s,'p'));
