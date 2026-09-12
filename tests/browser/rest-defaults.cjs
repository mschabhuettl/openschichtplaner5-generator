'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function restDefaults({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  const standard={...structuredClone(snapshot.profiles[0]),id:'sp5:unconfirmed',confirmed:false,
   min_rest_minutes:660,weekly_rest_minutes:2160,weekly_rest_frame:'calendar_week',weekly_rest_add_daily:false};
  const deviating={...structuredClone(standard),id:'sp5:abweichend',min_rest_minutes:480};
  snapshot.profiles=[standard,deviating];
  snapshot.employees.forEach((e,i)=>e.profile_ids=[i?'sp5:unconfirmed':'sp5:abweichend']);
  invalidateResult();renderRules();navigate('rules');
 });
 const bar=page.locator('#restDefaults');
 await bar.waitFor();
 const people=await page.evaluate(()=>snapshot.employees.length);
 assert.equal(await page.locator('#restDefaultsTitle').textContent(),`${people} Personen ohne bestätigtes Regelprofil`);
 assert.match(await page.locator('#restDefaultsNote').textContent(),/660 Minuten/);
 assert.match(await page.locator('#restDefaultsNote').textContent(),/2160 Minuten/);
 assert.match(await page.locator('#restDefaultsNote').textContent(),/1 weitere Profile weichen davon ab/);
 assert.equal(await page.locator('#confirmRestDefaults').textContent(),'Vereinbarte 11/36-Ruhevorgaben für 1 Profile bestätigen');

 page.once('dialog',dialog=>dialog.dismiss());
 await page.click('#confirmRestDefaults');
 assert.deepEqual(await page.evaluate(()=>snapshot.profiles.map(p=>p.confirmed)),[false,false],'Cancel confirms nothing');

 page.once('dialog',async dialog=>{assert.match(dialog.message(),/1 Regelprofile/);await dialog.accept();});
 await page.click('#confirmRestDefaults');
 // Only the profile carrying the agreed values is confirmed; the deviating one stays open.
 assert.deepEqual(await page.evaluate(()=>snapshot.profiles.map(p=>[p.id,p.confirmed])),
  [['sp5:unconfirmed',true],['sp5:abweichend',false]]);
 assert.deepEqual(await page.evaluate(()=>snapshot.profiles.map(p=>p.min_rest_minutes)),[660,480],'No limits rewritten');
 assert.equal(await page.locator('#confirmRestDefaults').isDisabled(),true);
 assert.match(await page.locator('#restDefaultsNote').textContent(),/weichen von den vereinbarten/);
 console.log('Rest defaults: agreed 11/36 confirmed in one step, deviating profiles stay open.');
};
