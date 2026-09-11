const assert=require('node:assert/strict');
const {apply}=require('../../sp5generator/static/profile-groups.js');
const make=()=>({context_start:'2026-01-01',context_end:'2026-03-01',profiles:[{id:'p',confirmed:true,valid_from:'2026-01-01',valid_until:'2026-03-01'},{id:'sp5:unconfirmed',confirmed:false,source:'unresolved'}],employees:[{team_ids:['a'],profile_ids:[]},{team_ids:['a'],profile_ids:['sp5:unconfirmed']},{team_ids:['a'],profile_ids:['individual']},{team_ids:['b'],profile_ids:[]}]});
let s=make();assert.equal(apply(s,'p','a'),2);assert.deepEqual(s.employees.map(e=>e.profile_ids),[['p'],['p'],['individual'],[]]);assert.equal(apply(s,'p','a'),0);
s=make();s.profiles[0].confirmed=false;assert.throws(()=>apply(s,'p'));assert.deepEqual(s,(()=>{const x=make();x.profiles[0].confirmed=false;return x;})());
s=make();s.profiles[0].valid_until='2026-02-01';assert.throws(()=>apply(s,'p'));
// An edited import profile is not a disposable placeholder. Zero is a hard
// cap too; do not detach it merely because its confirmation is still pending.
for(const key of ['max_daily_minutes','max_weekly_minutes','max_period_minutes',
                 'max_work_days','max_nights','max_weekends',
                 'max_consecutive_work_days','max_consecutive_nights']) {
 for(const value of [0,1,2400]) {
  s=make();s.profiles[1][key]=value;
  assert.equal(apply(s,'p','a'),1,key+' '+value);
  assert.deepEqual(s.employees[1].profile_ids,['sp5:unconfirmed'],key+' '+value);
  assert.equal(s.profiles[1][key],value);
 }
}
for(const [key,value] of [['min_rest_minutes',720],['after_night_rest_minutes',720],
                         ['after_night_block_rest_minutes',1440],['weekly_rest_minutes',2160]]) {
 s=make();s.profiles[1][key]=value;s.profiles[0][key]=value-1;
 assert.equal(apply(s,'p','a'),1,key+' must not weaken');
 assert.deepEqual(s.employees[1].profile_ids,['sp5:unconfirmed']);
 s=make();s.profiles[1][key]=value;s.profiles[0][key]=value;
 assert.equal(apply(s,'p','a'),2,key+' equal constraint is preserved');
}
for(const key of ['weekly_rest_frame','weekly_rest_window_days','weekly_rest_add_daily']) {
 s=make();s.profiles[1].weekly_rest_minutes=s.profiles[0].weekly_rest_minutes=2160;
 s.profiles[1][key]=({weekly_rest_frame:'rolling_local',weekly_rest_window_days:8,weekly_rest_add_daily:true})[key];
 assert.equal(apply(s,'p','a'),1,key+' incomparable semantics');
}
s=make();s.profiles[1].after_night_block_rest_minutes=s.profiles[0].after_night_block_rest_minutes=1440;
s.profiles[1].night_block_gap_days=2;assert.equal(apply(s,'p','a'),1,'night block semantics preserved');
