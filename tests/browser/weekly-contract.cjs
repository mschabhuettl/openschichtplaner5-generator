'use strict';
// Isolated synthetic server; never customer data.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage();
  await page.goto(process.env.WEB_TEST_BASE||'http://127.0.0.1:8765');
  await page.evaluate(async()=>{
   load(await api('/api/demo'));
   const e=snapshot.employees[0];
   e.target_minutes=4800;e.contractual_weekly_minutes=1200;
   personDetails(e);
  });
  assert.equal(await page.getByLabel('Vertragliche Wochenstunden',{exact:true}).inputValue(),'20');
  assert.equal(await page.getByLabel('Sollstunden im Planungszeitraum',{exact:true}).inputValue(),'80');
  assert.match(await page.locator('#personWeeklyHoursHelp').innerText(),/Keine harte Höchstgrenze/);
  await page.getByLabel('Vertragliche Wochenstunden',{exact:true}).fill('24');
  await page.getByLabel('Vertragliche Wochenstunden',{exact:true}).press('Tab');
  assert.deepEqual(await page.evaluate(()=>[snapshot.employees[0].contractual_weekly_minutes,snapshot.employees[0].target_minutes]),[1440,4800]);
  const checked=await page.evaluate(async()=>{
   const response=await fetch('/api/snapshots/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(snapshot)});
   return response.status;
  });
  assert.equal(checked,200);
  await page.getByLabel('Vertragliche Wochenstunden',{exact:true}).fill('');
  await page.getByLabel('Vertragliche Wochenstunden',{exact:true}).press('Tab');
  assert.equal(await page.evaluate(()=>snapshot.employees[0].contractual_weekly_minutes),null);
  console.log('Weekly contract UI: distinct values, editing, clearing and API roundtrip passed');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
