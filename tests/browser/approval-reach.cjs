'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function approvalReach({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));navigate('plan');$('result').replaceChildren();
  renderPlanMetrics({approval_reach:{services:10,people:20,approvals:40,
   approval_share_percent:20,lowest_per_service:0,median_per_service:2,
   without_any_approval:3,target_out_of_reach:5,people_with_target:18,
   target_out_of_reach_minutes:60000}});
 });
 const zeile=page.locator('#approvalReach');
 await zeile.waitFor();
 const text=await zeile.textContent();
 assert.match(text,/40 von 200 möglichen Freigaben \(20 %\)/);
 assert.match(text,/im Median 2 freigegebene Personen je Dienstart/);
 assert.match(text,/mindestens keine/,'a service nobody may staff has to be said plainly');
 const warnung=page.locator('#approvalReachWarning');
 assert.match(await warnung.textContent(),/3 Personen haben für keinen verlangten Dienst eine Freigabe/);
 assert.match(await warnung.textContent(),/5 von 18 Personen können ihr Soll/);
 assert.match(await warnung.textContent(),/1\.000 Stunden/);
 assert.match(await warnung.textContent(),/steckt im Zuschnitt, nicht in der Planung/);

 // Eine vollständige Freigabedecke meldet keinen Rückstand.
 await page.evaluate(()=>{$('result').replaceChildren();renderPlanMetrics({approval_reach:{services:2,people:4,
  approvals:8,approval_share_percent:100,lowest_per_service:4,median_per_service:4,
  without_any_approval:0,target_out_of_reach:0,people_with_target:4,
  target_out_of_reach_minutes:0}});});
 assert.match(await page.locator('#approvalReach').textContent(),/mindestens 4\./);
 assert.equal(await page.locator('#approvalReachWarning').count(),0);
 console.log('Approval reach: the plan says how far the granted approvals carry, and what that costs.');
};
