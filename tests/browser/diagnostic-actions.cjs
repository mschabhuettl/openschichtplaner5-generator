'use strict';
// Synthetic demo project and diagnostics only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function diagnosticActions({page,base}){
 await page.goto(base);
 const autoKind=page.locator('#autoKind');
 assert.equal(await autoKind.isChecked(),false,'Time-based day/night assignment requires an explicit decision');
 await page.click('#openImport');
 await page.locator('.import-options > summary').click();
 const importHelp=page.locator('#autoKindHelp');
 assert.equal(await importHelp.count(),1);
 assert(await importHelp.isVisible(),'The import consequence is visible alongside its checkbox');
 assert.equal(await importHelp.evaluate(e=>e.tagName),'SMALL');
 assert.equal(await autoKind.evaluate(e=>e.parentElement.nextElementSibling.id),'autoKindHelp','The explanation immediately follows the checkbox label');
 assert.equal(await autoKind.getAttribute('aria-describedby'),'autoKindHelp');
 assert.match(await importHelp.innerText(),/Regeln und Bedarf/);
 assert.equal(await autoKind.isChecked(),false,'Opening the import settings never enables the assignment');

 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  navigate('plan');
  document.querySelector('#validationDetails').open=true;
 });
 const boundaryAction='Unter Regeln und Bedarf gesammelt einstellen: Wiederkehrende Dienste gesammelt einstellen. Je Dienst und Zeitmuster einmal Tag oder Nacht.';
 const volumeHint='Viele gleichartige Befunde lassen sich meist gesammelt erledigen.';
 const boundary=page.locator('.validation-group').filter({has:page.locator('summary',{hasText:'Tag-/Nachtart der Randarbeit'})});
 const interval=page.locator('.validation-group').filter({has:page.locator('summary',{hasText:'Dienstzeiten'})});
 // The threshold applies to each code, independently of the report's total.
 for(const [boundaryCount,intervalCount] of [[21,20],[20,21]]){
  await page.evaluate(({boundaryCount,intervalCount})=>{
   renderValidation({valid:false,complete:false,diagnostics:[
    ...Array.from({length:boundaryCount},(_,i)=>({code:'boundary_kind',message:`Synthetische Randarbeit ${i+1}: Tag oder Nacht bestätigen.`})),
    ...Array.from({length:intervalCount},(_,i)=>({code:'interval',message:`Synthetischer Zeitfehler ${i+1}.`})),
   ]});
  },{boundaryCount,intervalCount});
  assert.equal(await page.locator('.validation-group').count(),2);
  assert.equal(await boundary.locator(':scope > summary').innerText(),`Tag-/Nachtart der Randarbeit · ${boundaryCount}`);
  await boundary.locator(':scope > summary').click();
  await boundary.locator('.diagnostic-item').first().waitFor();
  assert.equal(await boundary.locator('.diagnostic-item').count(),boundaryCount,'Every boundary diagnostic stays available');
  assert.equal(await boundary.locator(':scope > .diagnostic-action').count(),1,'One action belongs to the group');
  assert.equal(await boundary.getByText(boundaryAction,{exact:true}).count(),1,'The action is not repeated for individual diagnostics');
  assert(await boundary.locator('.diagnostic-action').isVisible());
  assert.equal(await boundary.locator('.diagnostic-item .diagnostic-action').count(),0);
  assert.equal(await boundary.locator('.diagnostic-volume-hint').count(),Number(boundaryCount>20));

  await interval.locator(':scope > summary').click();
  await interval.locator('.diagnostic-item').first().waitFor();
  assert.equal(await interval.locator('.diagnostic-item').count(),intervalCount);
  assert.equal(await interval.locator('.diagnostic-action').count(),0,'Codes without an action have no additional action hint');
  assert.equal(await interval.locator('.diagnostic-volume-hint').count(),Number(intervalCount>20));
  assert.equal(await page.locator('.validation-group .diagnostic-volume-hint').innerText(),volumeHint);
  assert.equal(await page.locator('.validation-group .diagnostic-action').count(),1);
 }
 console.log('Diagnostic actions: one hint per group, unmapped codes, 20/21 threshold and explicit import choice passed.');
};
