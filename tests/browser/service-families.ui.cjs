'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function serviceFamilyMatrix({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  snapshot.metadata.service_matrix_version=1;
  snapshot.metadata.services=[
   {function_id:'f-nct-6',name:'N-CT 6-16'},
   {function_id:'f-nct-12',name:'N-CT 12-22'},
   {function_id:'f-ovd',name:'OvD TD 5:20-17:20'},
  ];
  snapshot.employees.forEach(e=>{e.approvals=[];});
  snapshot.metadata.history_matrix=[{employee_id:snapshot.employees[0].id,
   suggested_approvals:[{function_id:'f-nct-6',workplace_id:'*'}]}];
  invalidateResult();navigate('team');renderActivePanel(true);
 });
 const kopf=page.locator('#matrix thead th');
 await kopf.first().waitFor();
 const spalten=async()=>(await kopf.allInnerTexts()).slice(1).map(t=>t.trim());
 // Zwei Zeitlagen derselben Tätigkeit werden eine Spalte; auch der Einzeldienst
 // verliert seine Uhrzeit, denn freigegeben wird die Tätigkeit.
 const eigene=await spalten();
 assert.equal(eigene[0],'N-CT');
 assert.ok(eigene.includes('OvD TD'),`OvD TD fehlt in ${JSON.stringify(eigene)}`);
 assert.ok(!eigene.some(name=>/\d[:.]?\d*\s*[-–]/.test(name)),'keine Uhrzeit mehr in den Spalten');

 const zelle=page.locator('#matrix tbody tr').first().locator('button.matrix-cell').first();
 assert.match(await zelle.getAttribute('title'),/2 Zeitlagen/);

 // Eine einzelne freigegebene Zeitlage macht die Dienstart noch nicht frei.
 await page.evaluate(()=>{snapshot.employees[0].approvals=[{function_id:'f-nct-6',workplace_id:'*',
  valid_from:snapshot.period_start,valid_until:snapshot.period_end,supervised:false}];renderActivePanel(true);});
 assert.match(await zelle.getAttribute('title'),/Einzelne Zeitlagen/);
 assert.equal(await zelle.getAttribute('aria-pressed'),'false');
 await zelle.click();
 assert.deepEqual(await page.evaluate(()=>snapshot.employees[0].approvals.map(a=>a.function_id).sort()),
  ['f-nct-12','f-nct-6'],'der Klick vervollständigt die Dienstart, statt sie zu entziehen');
 await zelle.click();
 await page.evaluate(()=>{snapshot.employees[0].approvals=[];renderActivePanel(true);});
 await zelle.click();
 assert.deepEqual(await page.evaluate(()=>snapshot.employees[0].approvals.map(a=>a.function_id).sort()),
  ['f-nct-12','f-nct-6'],'ein Klick gibt beide Zeitlagen frei');
 assert.match(await page.locator('#notice').textContent(),/2 Zeitlagen/);
 await zelle.click();
 assert.deepEqual(await page.evaluate(()=>snapshot.employees[0].approvals),[],'und nimmt beide zurück');

 // Ohne Zusammenfassung steht jede Zeitlage wieder für sich.
 await page.uncheck('#groupFamilies');
 const einzeln=await spalten();
 assert.deepEqual(einzeln.slice(0,3),['N-CT 6-16','N-CT 12-22','OvD TD 5:20-17:20']);
 await page.locator('#matrix tbody tr').first().locator('button.matrix-cell').first().click();
 assert.deepEqual(await page.evaluate(()=>snapshot.employees[0].approvals.map(a=>a.function_id)),['f-nct-6']);

 // Der Nachweis für eine Zeitlage trägt die ganze Dienstart - aber nur im Familienmodus.
 await page.evaluate(()=>{snapshot.employees.forEach(e=>{e.approvals=[];});renderActivePanel(true);});
 const offen=async()=>page.evaluate(()=>pendingHistoryApprovals().length);
 assert.equal(await offen(),1,'ohne Zusammenfassung zählt nur die belegte Zeitlage');
 await page.check('#groupFamilies');
 assert.equal(await offen(),2,'zusammengefasst trägt der Nachweis beide Zeitlagen');
 console.log('Service families: one column per duty type, one click for every time of day.');
};
