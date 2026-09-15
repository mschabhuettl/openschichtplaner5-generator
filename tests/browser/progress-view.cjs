'use strict';
// Newly constructed synthetic project only; the server is the local browser fixture.
const assert=require('node:assert/strict');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
module.exports=async function progressView({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 const demo=JSON.parse(execFileSync(process.env.WEB_TEST_PYTHON||'python3',
  ['-c','from sp5generator.demo import make_demo; print(make_demo(16,10).model_dump_json())'],
  {cwd:root,encoding:'utf8',maxBuffer:8*1024*1024}));
 await page.evaluate(value=>load(value,true),demo);

 // Der Fortschritt kommt vom Rechenprozess; für eine verlässliche Prüfung
 // wird ein fester Stand eingespielt, statt auf Laufzeit zu hoffen.
 const eingespielt=[
  {phase:'vacancies',search_seconds:0.4,native_status:'OPTIMAL',accepted:true},
  {phase:'quality',kind:'incumbent',solutions:9,search_seconds:2.5,elapsed_seconds:2.9,objective:28500,bound:2700},
 ];
 const muster=/\/api\/jobs\/[^/]+\/status$/;
 await page.route(muster,async route=>{
  const response=await route.fetch(),data=await response.json();
  if(data.state==='running'||data.state==='queued'){
   data.state='running';data.progress=eingespielt;data.elapsed_seconds=10;data.started_at=data.started_at??data.created_at;
  }
  await route.fulfill({response,json:data});
 });
 await page.locator('.main-nav [data-navigate="calculate"]').click();
 await page.locator('[data-panel="calculate"]').waitFor({state:'visible'});
 await page.fill('#limit','40');
 await page.check('#partial');
 await page.click('#solve');

 const steps=page.locator('#progressSteps .trace-step');
 await steps.first().waitFor({timeout:30000});
 assert.equal(await steps.count(),2,'Abgeschlossene Stufe und laufende Suche stehen untereinander');
 assert.match(await steps.nth(0).innerText(),/Besetzung maximieren/);
 assert.match(await steps.nth(0).innerText(),/bewiesenes Optimum · übernommen/);
 const laufend=await steps.nth(1).innerText();
 assert.match(laufend,/Qualität abwägen · sucht/,'Die laufende Stufe ist als solche erkennbar');
 assert.match(laufend,/9 Lösungen gefunden/,'Gefundene Zwischenlösungen werden gezählt');
 assert.match(laufend,/beste Bewertung 28\.500/,'Die beste Bewertung steht in deutscher Schreibweise');
 assert.match(laufend,/untere Schranke 2\.700/,'Die Schranke zeigt, wie weit es noch sein kann');
 assert.equal(await page.locator('#progressSteps .trace-step.running').count(),1);
 assert.match(await page.locator('#progressPhase').innerText(),/Qualität abwägen · 10 von höchstens 40 Sekunden/);
 assert.equal(await page.locator('#progressFill').evaluate(node=>node.style.width),'25%','Der Balken zeigt den Anteil der Rechenzeit');

 await page.click('#cancel');
 await page.unroute(muster);
 assert.deepEqual(errors,[]);
 console.log('Progress view: finished stage, running search with incumbents, bounds and time budget passed.');
};
