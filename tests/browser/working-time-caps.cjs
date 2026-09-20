'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function workingTimeCaps({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  snapshot.profiles=[{...structuredClone(snapshot.profiles[0]),id:'sp5:unconfirmed',confirmed:false,
   max_daily_minutes:null,max_weekly_minutes:null}];
  snapshot.employees.forEach(e=>e.profile_ids=['sp5:unconfirmed']);
  invalidateResult();renderRules();navigate('rules');selectConfig('profile');
 });
 const card=page.locator('[data-profile-id="sp5:unconfirmed"]');
 await card.waitFor();await card.evaluate(node=>node.open=true);
 const warning=page.locator('[data-missing-caps="sp5:unconfirmed"]');
 await warning.waitFor({state:'visible'});
 assert.match(await warning.textContent(),/Keine Höchstarbeitszeit hinterlegt/);

 // Typing a daily cap is enough to settle the question; the hint must react at once.
 await card.locator('[data-profile-field="max_daily_minutes"]').fill('600');
 await assert.doesNotReject(warning.waitFor({state:'hidden'}));
 await card.locator('[data-profile-field="max_daily_minutes"]').fill('');
 await assert.doesNotReject(warning.waitFor({state:'visible'}));

 const before=await page.evaluate(()=>{const {max_daily_minutes,max_weekly_minutes,...rest}=snapshot.profiles[0];return rest;});
 await card.getByRole('button',{name:'12/48-Höchstgrenzen in dieses Profil übernehmen'}).click();
 assert.deepEqual(await page.evaluate(()=>[snapshot.profiles[0].max_daily_minutes,snapshot.profiles[0].max_weekly_minutes]),[720,2880]);
 // Adopting a cap is not a professional sign-off and must not touch anything else.
 assert.deepEqual(await page.evaluate(()=>{const {max_daily_minutes,max_weekly_minutes,...rest}=snapshot.profiles[0];return rest;}),before);
 await page.locator('[data-missing-caps="sp5:unconfirmed"]').waitFor({state:'hidden'});
 console.log('Working time caps: missing-cap warning reacts to the field and the 12/48 adoption leaves every other rule alone.');
};
