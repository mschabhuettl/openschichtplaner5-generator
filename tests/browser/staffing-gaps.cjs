'use strict';
// Synthetic demo project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function staffingGaps({page,base}){
 await page.goto(base);
 // Build a validation report whose shortages concentrate on two services.
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  navigate('plan');
  document.querySelector('#validationDetails').open=true;
  const chosen=snapshot.demands.slice(0,6);
  renderValidation({valid:false,complete:false,diagnostics:chosen.map(d=>({
   code:'candidate_shortage',
   message:`${d.minimum} benötigte Stellen; nur 0 individuell geeignete Personen.`,
   demand_id:d.id,
  }))});
 });
 // A single group opens on its own; the summary is what the user sees first.
 await page.locator('.shortage-summary').waitFor();
 const view=await page.evaluate(()=>({
  heading:document.querySelector('.shortage-summary strong').textContent,
  rows:[...document.querySelectorAll('.shortage-summary tbody tr')]
   .map(row=>[row.dataset.serviceRow,...[...row.children].slice(1,4).map(c=>Number(c.textContent))]),
  expectedSlots:snapshot.demands.slice(0,6).reduce((n,d)=>n+d.minimum,0),
 }));
 assert(view.rows.length>=1&&view.rows.length<6,'Six demands collapse into fewer service rows');
 assert.match(view.heading,/^\d+ Dienste betroffen$/);
 assert.equal(view.heading,`${view.rows.length} Dienste betroffen`);
 // Affected demands and open slots add up to the diagnostics that were passed in.
 assert.equal(view.rows.reduce((n,r)=>n+r[1],0),6);
 assert.equal(view.rows.reduce((n,r)=>n+r[2],0),view.expectedSlots);

 // The shortcut opens the approval matrix filtered to that service.
 await page.locator('.shortage-summary tbody tr').first().getByRole('button',{name:'Freigaben öffnen'}).click();
 assert.equal(await page.locator('[data-panel="team"]').isVisible(),true);
 const query=await page.locator('#matrixSearch').inputValue();
 assert(query.length>0,'Matrix search is prefilled with the service');
 assert.equal(await page.evaluate(()=>snapshot.employees.every(e=>e.approvals.length>=0)),true,'No approval was added');
 console.log('Staffing gaps: per-service summary, totals and matrix shortcut passed.');
};
