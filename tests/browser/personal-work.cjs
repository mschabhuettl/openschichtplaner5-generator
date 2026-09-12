'use strict';
// Synthetic demo project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function personalWork({page,base}){
 await page.goto(base);
 const setup=await page.evaluate(async()=>{
  load(await api('/api/demo'));
  assignments=[];
  const person=snapshot.employees[0];
  const duty=snapshot.shifts[0];
  const day=duty.segments[0].start.slice(0,10);
  snapshot.boundary_work=[{
   id:'personal-1',employee_id:person.id,segments:structuredClone(duty.segments),
   kind:'day',in_period:true,paid_minutes:330,holiday:false,source:'sp5:existing',
  }];
  snapshot.metadata.provenance={...snapshot.metadata.provenance,'personal-1':{name:'Ausbildung'}};
  planMonth=day.slice(0,7);
  invalidateResult();navigate('plan');renderPlan();
  return {personId:person.id,day};
 });

 const badge=page.locator('.personal-badge').first();
 await badge.waitFor();
 assert.match(await badge.textContent(),/^◼ Ausbildung\n\d{2}:\d{2}–\d{2}:\d{2}/);
 assert.match(await badge.getAttribute('title'),/330 bezahlte Minuten/);
 assert.match(await badge.getAttribute('title'),/deckt keinen Bedarf/);
 // It is context, not an assignment: no plan row and no coverage is created.
 assert.equal(await page.evaluate(()=>assignments.length),0,'Personal work is context, never an assignment');
 assert.match(await page.locator('.coverage-summary').first().innerText(),/0 \/ \d+ erforderliche Plätze besetzt/);

 // Work the source states without times shows its day and says so, instead
 // of a time the source never gave.
 await page.evaluate(day=>{
  const work=snapshot.boundary_work[0];
  work.segments=[];work.day=day;work.kind='unknown';work.paid_minutes=480;
  renderPlan();
 },setup.day);
 const untimed=page.locator('.personal-badge').first();
 await untimed.waitFor();
 assert.equal(await untimed.textContent(),'\u25fc Ausbildung\nohne Zeitangabe');
 assert.match(await untimed.getAttribute('title'),/480 bezahlte Minuten/);
 assert.equal(await page.locator('.personal-badge').count(),1,'One day, one badge');

 // Context outside the period keeps its previous behaviour and stays hidden.
 await page.evaluate(()=>{snapshot.boundary_work[0].in_period=false;renderPlan();});
 assert.equal(await page.locator('.personal-badge').count(),0);
 console.log('Personal work: in-period duty is visible with its paid minutes and covers nothing, with or without source times.');
};
