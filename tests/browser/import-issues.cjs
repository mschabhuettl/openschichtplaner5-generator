'use strict';
// Synthetic import notes only; never a personal project or SP5 source.
const assert=require('node:assert/strict');
module.exports=async function importIssues({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  const person=snapshot.employees[0].id;
  snapshot.unresolved=[
   ...Array.from({length:40},(_,i)=>`Bestehender Dienst ${person} 2026-01-0${(i%9)+1}: Zuordnung zum Besetzungsbedarf und Freigaben bestätigen. Nr ${i}`),
   ...Array.from({length:12},(_,i)=>`Sonderdienst ${person} 2026-01-05: bezahlte Minuten prüfen. Nr ${i}`),
   'Importinterpretation bestätigen: MAX=-1 ohne Obergrenze.',
   'Zeitgutschriften und Anfangssalden für den gewählten Zeitraum ergänzen.'
  ];
  invalidateResult();renderRules();navigate('rules');
 });
 const bar=page.locator('#unresolvedBulk');
 await bar.waitFor();
 assert.equal(await page.locator('#unresolvedBulkTitle').textContent(),'54 offene Importangaben');
 assert.match(await page.locator('#unresolvedBulkBreakdown').textContent(),/40× Bestehender Dienst/);
 assert.match(await page.locator('#unresolvedBulkBreakdown').textContent(),/12× Sonderdienst/);
 assert.equal(await page.locator('#confirmUnresolved').textContent(),'Alle 54 angezeigten Angaben als geprüft markieren');
 assert.equal(await page.locator('#unresolved .card').count(),54,'Every note stays reachable without paging');

 // Narrowing the search confirms exactly one category and leaves the rest open.
 await page.fill('[data-collection-search="unresolved"]','Sonderdienst');
 await page.waitForFunction(()=>document.querySelectorAll('#unresolved .card').length===12);
 assert.equal(await page.locator('#unresolvedBulkTitle').textContent(),'12 von 54 offenen Importangaben angezeigt');
 page.once('dialog',dialog=>dialog.dismiss());
 await page.click('#confirmUnresolved');
 assert.equal(await page.evaluate(()=>snapshot.unresolved.length),54,'Cancel keeps every note');
 page.once('dialog',async dialog=>{assert.match(dialog.message(),/12 angezeigte Importangaben/);await dialog.accept();});
 await page.click('#confirmUnresolved');
 assert.equal(await page.evaluate(()=>snapshot.unresolved.length),42);
 assert.equal(await page.evaluate(()=>snapshot.unresolved.some(m=>m.startsWith('Sonderdienst'))),false);

 // Clearing the search then acknowledges the remainder in one step.
 await page.fill('[data-collection-search="unresolved"]','');
 await page.waitForFunction(()=>document.querySelectorAll('#unresolved .card').length===42);
 page.once('dialog',async dialog=>{await dialog.accept();});
 await page.click('#confirmUnresolved');
 assert.equal(await page.evaluate(()=>snapshot.unresolved.length),0);
 assert.equal(await page.locator('#unresolvedBulk').isVisible(),false);
 assert.match(await page.locator('#unresolved').innerText(),/Keine offenen Importangaben/);
 console.log('Import issues: category breakdown, filtered and full bulk acknowledgement passed.');
};
