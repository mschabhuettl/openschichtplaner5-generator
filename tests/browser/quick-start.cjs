'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function quickStart({page,base}){
 await page.goto(base);
 await page.click('#openImport');
 await page.locator('#quickStart').waitFor();

 // Ohne Teams sagt der Schnellstart, was fehlt, statt einen leeren Import zu starten.
 await page.fill('#quickMonth','2027-01');
 await page.click('#quickPrepare');
 assert.match(await page.locator('#notice').textContent(),/Teams/);

 // Mit Teams setzt ein Monat alle abgeleiteten Felder.
 await page.evaluate(()=>{checkedTeams.add('1');});
 await page.click('#quickPrepare');
 assert.deepEqual(await page.evaluate(()=>[$('start').value,$('end').value,
  $('demandSource').value,$('demandHistoryStart').value,$('demandHistoryEnd').value,
  $('historyStart').value,$('historyEnd').value,$('autoKind').checked]),
  ['2027-01-01','2027-01-31','history','2026-01-01','2026-01-31','2024-01-01','2026-12-31',true]);
 // Das historische Fenster ist damit nicht mehr optional und wird aufgeklappt.
 assert.equal(await page.locator('#importOptions').evaluate(node=>node.open),true);
 assert.match(await page.locator('#quickHint').textContent(),/2026-01-01 bis 2026-01-31/);

 // Was noch zu entscheiden ist, steht als Liste mit je einem Schritt.
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  snapshot.profiles.forEach(p=>{p.confirmed=false;});
  snapshot.employees.forEach(e=>{e.max_period_minutes=null;});
  navigate('calculate');renderActivePanel(true);
 });
 const liste=page.locator('#openDecisions');
 await liste.locator('[data-open-decision]').first().waitFor();
 assert.match(await liste.innerText(),/Regelprofile sind noch nicht fachlich bestätigt/);
 assert.match(await liste.innerText(),/Niemand hat eine persönliche Höchstarbeitszeit/);

 await liste.getByRole('button',{name:'Grenze bei 150 % des Solls setzen'}).click();
 const gesetzt=await page.evaluate(()=>snapshot.employees.filter(e=>!e.excluded&&e.target_minutes)
  .map(e=>[e.max_period_minutes,Math.round(e.target_minutes*1.5)]));
 assert.ok(gesetzt.length&&gesetzt.every(([a,b])=>a===b),'die Grenze folgt dem eigenen Soll');
 assert.doesNotMatch(await liste.innerText(),/Niemand hat eine persönliche Höchstarbeitszeit/);

 await page.evaluate(()=>{snapshot.profiles.forEach(p=>{p.confirmed=true;p.max_daily_minutes=720;p.max_weekly_minutes=2880;});
  snapshot.metadata.history_matrix=[];invalidateResult();renderActivePanel(true);});
 assert.match(await liste.innerText(),/Keine offenen Entscheidungen/);
 console.log('Quick start: one month sets every derived field, and what is left to decide is listed with its step.');
};
