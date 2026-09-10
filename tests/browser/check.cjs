'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..');
const state = fs.mkdtempSync(path.join(os.tmpdir(), 'generator-web-check-'));
const port = process.env.WEB_TEST_PORT || '8765';
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.env.WEB_TEST_PYTHON || 'python3', [path.join(__dirname, 'server.py')], {
  cwd: root, env: {...process.env, WEB_TEST_STATE: state, WEB_TEST_PORT: port}, stdio: ['ignore', 'pipe', 'pipe']
});
let output = '';
for (const stream of [server.stdout, server.stderr]) stream.on('data', data => { output = (output + data).slice(-8000); });
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  let browser;
  try {
    let ready = false;
    for (let i=0;i<100;i++) {
      if (server.exitCode !== null) throw Error('Synthetic web service failed: '+output);
      try { if ((await fetch(base)).ok) { ready=true; break; } } catch {}
      await delay(100);
    }
    assert(ready, 'Web service starts');
    browser = await chromium.launch({headless:true, args:['--no-sandbox']});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
    });
    await page.goto(base);
    await page.waitForFunction(()=>document.querySelector('#version').textContent==='Version 0.3.0');
    await page.selectOption('#sourceType', 'api');
    await page.click('#inspect');
    await page.waitForSelector('[data-team-id="3"]');
    await page.check('[data-team-id="1"]');
    await page.uncheck('[data-team-id="3"]');
    await page.fill('#start', '2026-02-02');
    await page.fill('#end', '2026-02-08');
    await page.fill('#historyStart', '2026-01-01');
    await page.fill('#historyEnd', '2026-01-31');
    const imported = page.waitForResponse(r => r.url().endsWith('/api/remote-import') && r.request().method()==='POST');
    await page.click('#import');
    const importedResponse = await imported;
    assert.equal(importedResponse.status(), 200);
    const snapshot = (await importedResponse.json()).snapshot;
    assert.deepEqual(snapshot.metadata.selected_group_ids, [1,2]);
    assert.equal(snapshot.employees.length, 2);
    assert.equal(snapshot.metadata.service_matrix_version,1);
    assert(!snapshot.employees.some(e => e.id==='sp5:employee:102'));
    await page.waitForSelector('.matrix-cell');
    assert.equal(await page.locator('#matrix tbody tr').count(), 2);
    assert.equal(await page.locator('#matrix thead th').count(), 4, 'Two services at the same workplace plus unused catalog service');
    assert.match(await page.locator('#matrix thead').innerText(), /Dienst A/);
    assert.match(await page.locator('#matrix thead').innerText(), /Dienst B/);
    const selector = '.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:201"][data-workplace-id="*"]';
    assert.match(await page.locator(selector).innerText(), /Vorschlag/);
    assert.equal(snapshot.employees[0].approvals.length, 0);
    if(process.env.WEB_TEST_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,'matrix.png'),fullPage:true});
    await page.click(selector);
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await page.click('#transpose');
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await page.click('#save');
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('dauerhaft'));
    await page.click('#restore');
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('Daten geladen'));
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.setViewportSize({width:1440,height:1000});
    // Removing the visible period must retain approvals before and after it.
    const dated = structuredClone(snapshot); dated.id += ":dated";
    dated.employees[0].approvals = [{function_id:'sp5:service:201',workplace_id:'*',valid_from:'2026-01-01',valid_until:'2026-03-31',supervised:true}];
    await page.setInputFiles('#file', {name:'synthetic-dated.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(dated))});
    await page.waitForFunction(() => [...document.querySelectorAll('.matrix-cell')].some(b=>b.textContent.includes('Betreut')));
    await page.click(selector);
    const datedSave = page.waitForResponse(r=>r.url().endsWith('/api/snapshots') && r.request().method()==='PUT');
    await page.click('#save');
    const datedResult = await (await datedSave).json();
    assert.deepEqual(datedResult.employees[0].approvals.map(a=>[a.valid_from,a.valid_until,a.supervised]), [
      ['2026-01-01','2026-02-01',true], ['2026-02-09','2026-03-31',true]
    ]);
    // Extending a partial supervised grant must not turn it into unsupervised work.
    const partial = structuredClone(snapshot); partial.id += ":partial";
    partial.employees[0].approvals = [{function_id:'sp5:service:201',workplace_id:'sp5:workplace:301',valid_from:'2026-02-02',valid_until:'2026-02-03',supervised:true}];
    await page.setInputFiles('#file', {name:'synthetic-partial.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(partial))});
    await page.waitForFunction(() => document.querySelector('.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:201"]').getAttribute('aria-pressed')==='false');
    assert.match(await page.locator(selector).innerText(), /Einzelne Arbeitsplätze/);
    await page.click(selector);
    const partialSave = page.waitForResponse(r=>r.url().endsWith('/api/snapshots') && r.request().method()==='PUT');
    await page.click('#save');
    const partialResult = await (await partialSave).json();
    assert(partialResult.employees[0].approvals.every(a=>a.supervised));
    assert(partialResult.employees[0].approvals.some(a=>a.valid_until==='2026-02-08'&&a.workplace_id==='*'));
    assert.equal(await page.locator('.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:202"]').getAttribute('aria-pressed'),'false');
    // Imported calendar groups by native service, not shared physical workplace.
    const calendarSnapshot=structuredClone(snapshot);
    calendarSnapshot.assignments=calendarSnapshot.demands.map(d=>({employee_id:calendarSnapshot.employees[0].id,demand_id:d.id,fixed:false,segments:[]}));
    await page.setInputFiles('#file',{name:'synthetic-services.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(calendarSnapshot))});
    await page.selectOption('#planView','positions');
    await page.waitForFunction(()=>document.querySelector('#calendar thead').textContent.includes('Dienst'));
    assert.equal(await page.locator('#calendar tbody tr').count(),3);
    assert.equal(await page.locator('#calendar tbody tr').nth(2).locator('.shift-badge').count(),0);
    assert(await page.locator('#calendar tbody tr').nth(0).locator('.shift-badge').count()>0);
    assert(await page.locator('#calendar tbody tr').nth(1).locator('.shift-badge').count()>0);
    await page.selectOption('#planView','employees');
    await page.click('#demo');
    await page.waitForFunction(() => document.querySelector('#source').textContent.includes('SYNTHETISCHE DEMO'));
    await page.fill('#limit', '5');
    await page.click('#solve');
    await page.waitForFunction(() => document.querySelector('#result').textContent.includes('Vollständig'), null, {timeout:30000});
    assert(await page.locator('#calendar .shift-badge').count() > 0);
    assert.match(await page.locator('#calendar thead').innerText(), /Person/);
    await page.selectOption('#planView', 'positions');
    assert.match(await page.locator('#calendar thead').innerText(), /Funktion/);
    assert.match(await page.locator('#calendar .shift-badge').first().innerText(), /Testperson/);
    if(process.env.WEB_TEST_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,'monthly.png'),fullPage:true});
    await page.locator('#assignmentDetails summary').click();
    await page.locator('#plan tbody input[type="checkbox"]').first().check();
    const recomputeResponse = page.waitForResponse(r=>r.url().endsWith('/api/jobs') && r.request().method()==='POST');
    await page.click('#recompute');
    const newJob = await (await recomputeResponse).json();
    let computed;
    for(let i=0;i<200;i++) {
      computed = await (await fetch(base+'/api/jobs/'+newJob.id)).json();
      if(!['queued','running'].includes(computed.state)) break;
      await delay(100);
    }
    assert.equal(computed.state,'succeeded');
    assert(computed.result.validation.valid && computed.result.assignments.some(a=>a.fixed));
    await page.waitForFunction(() => document.querySelector('#job').textContent.includes('Berechnung beendet'), null, {timeout:30000});
    assert(await page.locator('#plan tbody input[type="checkbox"]').first().isChecked());
    assert.match(await page.locator('#validation').textContent(), /"valid": true/);
    // The calendar renders local dates and end-exclusive midnight, not UTC slices.
    const demo = await (await fetch(base+'/api/demo')).json();
    const demand = demo.demands[0];
    demo.timezone = 'Pacific/Auckland';
    demo.period_start = '2026-01-05'; demo.period_end = '2026-01-18';
    demo.shifts.find(s => s.id===demand.shift_id).segments = [
      {start:'2026-01-04T20:00:00Z',end:'2026-01-05T11:00:00Z'}
    ];
    demo.assignments = [{employee_id:demo.employees[0].id,demand_id:demand.id,fixed:true,segments:[]}];
    await page.setInputFiles('#file', {name:'synthetic-calendar.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(demo))});
    await page.waitForFunction(() => document.querySelector('#source').textContent.includes('Pacific/Auckland'));
    await page.selectOption('#planView','employees');
    assert.equal(await page.locator('#calendar td[data-date="2026-01-05"] .shift-badge').count(),1);
    assert.equal(await page.locator('#calendar td[data-date="2026-01-06"] .shift-badge').count(),0);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    if(process.env.WEB_TEST_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,'mobile.png'),fullPage:true});
    // Failed non-JSON responses remain actionable and duplicate submits are ignored.
    let validationCalls=0;
    await page.route('**/api/validate',async route=>{validationCalls++;await delay(250);await route.fulfill({status:503,contentType:'text/html',body:'Temporarily unavailable'});});
    await page.locator('#validate').evaluate(b=>{b.click();b.click();});
    assert(await page.locator('#validate').isDisabled());
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('HTTP 503'));
    assert.equal(validationCalls,1);
    assert(await page.locator('#validate').isEnabled());
    assert.deepEqual(errors, []);
    console.log('Passed: exact team selection, automatic history, matrix edit/transpose/save, local solver, both monthly views, fix/recompute, local midnight, desktop/mobile.');
  } finally {
    if(browser) await browser.close();
    server.kill('SIGTERM');
    await Promise.race([new Promise(resolve=>server.once('exit',resolve)),delay(5000)]);
    if(server.exitCode===null) server.kill('SIGKILL');
    fs.rmSync(state,{recursive:true,force:true});
  }
})().catch(error => {console.error(error.message);console.error(output);process.exitCode=1;});
