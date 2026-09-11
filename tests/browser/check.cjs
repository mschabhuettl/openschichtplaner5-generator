'use strict';
require('./service-groups.cjs');
require('./profile-groups.cjs');
require('./setup-assistant.cjs');
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
  let browser, failed=false;
  try {
    let ready = false;
    for (let i=0;i<100;i++) {
      if (server.exitCode !== null) throw Error('Synthetic web service failed: '+output);
      try { if ((await fetch(base)).ok) { ready=true; break; } } catch {}
      await delay(100);
    }
    assert(ready, 'Web service starts');
    browser = await chromium.launch({headless:true, args:['--no-sandbox'], ...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    async function screenshot(name){
      if(!process.env.WEB_TEST_SCREENSHOT_DIR)return;
      await page.evaluate(()=>{window.scrollTo(0,0);return new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
      await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,name),fullPage:true});
    }
    async function navigate(panel){
      await page.locator(`.main-nav [data-navigate="${panel}"]`).click();
      await page.locator(`[data-panel="${panel}"]`).waitFor({state:'visible'});
    }
    async function reveal(selector){
      const target=page.locator(selector);
      const panel=await target.evaluate(element=>element.closest('[data-panel]')?.dataset.panel);
      if(panel)await navigate(panel);
      // Open disclosure controls through their actual keyboard/click interface.
      for(let remaining=5;remaining>0;remaining--){
        const closed=target.locator('xpath=ancestor::details[not(@open)]').first();
        if(!await closed.count())break;
        await closed.locator(':scope > summary').click();
      }
    }
    async function saveProject(){await reveal('#save');await page.click('#save');}
    async function uploadProject(file){
      await reveal('#file');
      await page.waitForFunction(()=>!document.querySelector('#file').disabled);
      const checked=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
      await page.setInputFiles('#file',file);await checked;
      await page.waitForFunction(()=>document.querySelector('#file').dataset.busy!=='true');
    }
    const errors = [];
    let acceptDiscard=true;
    page.on('dialog', dialog => acceptDiscard ? dialog.accept() : dialog.dismiss());
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
    });
    await page.goto(base);
    await page.waitForFunction(()=>/^Version [0-9]+\.[0-9]+\.[0-9]+/.test(document.querySelector('#version').textContent));
    await reveal('#sourceType');
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
    await navigate('rules');
    await page.waitForSelector('#setupReview');
    const readiness=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));
    await page.getByRole('button',{name:'Planungsbereitschaft prüfen',exact:true}).click();
    assert.equal((await readiness).status(),200);
    await page.getByText('Vor der Berechnung noch bearbeiten:',{exact:true}).waitFor();
    // Opening Calculate runs the existing read-only check, never saves or starts jobs.
    const writes=[];
    const observeWrites=request=>{if(['POST','PUT'].includes(request.method())&&/\/api\/(snapshots|jobs)$/.test(new URL(request.url()).pathname))writes.push(request.url());};
    page.on('request',observeWrites);
    const automaticResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));
    await navigate('calculate');await automaticResponse;
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    assert(await page.locator('#automaticReadinessDetails').innerText());
    assert.deepEqual(writes,[]);page.off('request',observeWrites);
    const personHint=page.locator('#automaticReadinessDetails .diagnostic-item').filter({hasText:'Kein bestätigtes gültiges Regelprofil: Testperson 001'});
    assert.equal(await personHint.count(),1);
    assert(!(await personHint.innerText()).includes('sp5:employee:101'));
    await personHint.getByRole('button',{name:'Person bearbeiten',exact:true}).click();
    assert.equal(await page.locator('#details').getByLabel('Name',{exact:true}).inputValue(),'Testperson 001');
    await navigate('calculate');

    await screenshot('automatic-preflight.png');
    // A delayed old success must not replace a newer failed check after an edit.
    let releaseOld,oldSeenResolve;const oldSeen=new Promise(resolve=>oldSeenResolve=resolve);
    await page.route('**/api/readiness',async route=>{oldSeenResolve();await new Promise(resolve=>releaseOld=resolve);await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ready:true,diagnostics:[]})});},{times:1});
    await page.fill('#projectName','Vorprüfung alt');await page.locator('#projectName').blur();await oldSeen;
    await page.route('**/api/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetische Prüfunterbrechung'})}),{times:1});
    await page.fill('#projectName','Vorprüfung aktuell');await page.locator('#projectName').blur();
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='error');
    const oldResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness')&&r.status()===200);releaseOld();await oldResponse;
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await page.locator('#automaticReadinessStatus').getAttribute('data-state'),'error');
    assert(await page.locator('#retryReadiness').isVisible());
    await page.click('#retryReadiness');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    assert(await page.locator('#retryReadiness').isHidden());
    let repeatedChecks=0;const countChecks=request=>{if(request.url().endsWith('/api/readiness'))repeatedChecks++;};
    page.on('request',countChecks);await navigate('team');await navigate('calculate');
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(repeatedChecks,0,'Unchanged project reuses the current check');page.off('request',countChecks);
    await reveal('#json');await page.fill('#json',(await page.locator('#json').inputValue())+' ');
    await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='draft');
    assert.equal(await page.locator('#automaticReadinessDetails').innerText(),'');
    await reveal('#refreshJson');await page.click('#refreshJson');await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    // Ignore an in-flight reply during hidden JSON editing, then allow a fresh check.
    await page.route('**/api/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Fehler vor Wiederholung'})}),{times:1});
    await page.fill('#projectName','Prüfung während JSON-Bearbeitung');await page.locator('#projectName').blur();
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='error');
    let releaseHidden,hiddenSeenResolve;const hiddenSeen=new Promise(resolve=>hiddenSeenResolve=resolve);
    await page.route('**/api/readiness',async route=>{hiddenSeenResolve();await new Promise(resolve=>releaseHidden=resolve);await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ready:true,diagnostics:[]})});},{times:1});
    await page.click('#retryReadiness');await hiddenSeen;
    await reveal('#json');await page.fill('#json',(await page.locator('#json').inputValue())+' ');
    const hiddenResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));releaseHidden();await hiddenResponse;
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    await reveal('#refreshJson');await page.click('#refreshJson');await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues',null,{timeout:5000});
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await screenshot(`automatic-preflight-${width}.png`);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.setViewportSize({width:1440,height:1000});
    await navigate('rules');


    const patternRow=page.locator('#serviceGroups tbody tr').first();
    await patternRow.locator('select').selectOption('night');
    await patternRow.getByRole('button',{name:'Offene Vorkommen übernehmen'}).click();
    await navigate('team');

    assert(!snapshot.employees.some(e => e.id==='sp5:employee:102'));
    await page.waitForSelector('.matrix-cell');
    assert.equal(await page.locator('#matrix tbody tr').count(), 2);
    assert.equal(await page.locator('#matrix thead th').count(), 4, 'Two services at the same workplace plus unused catalog service');
    assert.match(await page.locator('#matrix thead').innerText(), /Dienst A/);
    assert.match(await page.locator('#matrix thead').innerText(), /Dienst B/);
    const selector = '.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:201"][data-workplace-id="*"]';
    assert.match(await page.locator(selector).innerText(), /Vorschlag/);
    assert.equal(snapshot.employees[0].approvals.length, 0);
    await reveal('#people');
    await page.locator('#people tbody tr').first().getByRole('button',{name:'Bearbeiten',exact:true}).click();
    const nominal=page.locator('#details').getByLabel('Sollstunden im Planungszeitraum',{exact:true});
    assert.equal(await nominal.inputValue(),'40');
    assert.match(await page.locator('#personHoursOrigin').innerText(),/Monatsbasis mit 156 Stunden je Monat/);
    assert.match(await page.locator('#personHoursOrigin').innerText(),/2026-02-02 bis 2026-02-08: 40 Stunden/);
    assert.match(await page.locator('#personHoursOrigin').innerText(),/Sollbuchungen sind im Importwert nicht enthalten/);
    assert.equal(await nominal.getAttribute('aria-describedby'),'personHoursHelp personHoursOrigin');
    await nominal.fill('48');await nominal.blur();
    assert.match(await page.locator('#personHoursOrigin').innerText(),/: 40 Stunden/,'Import provenance does not become the edited target');
    await nominal.fill('40');await nominal.blur();
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      await screenshot(`nominal-source-${width}.png`);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.setViewportSize({width:1440,height:1000});
    await screenshot('matrix.png');
    await page.click(selector);
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await page.click('#transpose');
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await saveProject();
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('dauerhaft'));
    await reveal('#restore');
    await page.click('#restore');
    await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('Daten geladen'));
    assert.equal(await page.locator(selector).getAttribute('aria-pressed'), 'true');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.setViewportSize({width:1440,height:1000});
    // Removing the visible period must retain approvals before and after it.
    const dated = structuredClone(snapshot); dated.id += ":dated";
    dated.employees[0].approvals = [{function_id:'sp5:service:201',workplace_id:'*',valid_from:'2026-01-01',valid_until:'2026-03-31',supervised:true}];
    await uploadProject( {name:'synthetic-dated.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(dated))});
    await page.waitForFunction(() => [...document.querySelectorAll('.matrix-cell')].some(b=>b.textContent.includes('Betreut')));
    await page.click(selector);
    const datedSave = page.waitForResponse(r=>r.url().endsWith('/api/snapshots') && r.request().method()==='PUT');
    await saveProject();
    const datedResult = await (await datedSave).json();
    assert.deepEqual(datedResult.employees[0].approvals.map(a=>[a.valid_from,a.valid_until,a.supervised]), [
      ['2026-01-01','2026-02-01',true], ['2026-02-09','2026-03-31',true]
    ]);
    // Extending a partial supervised grant must not turn it into unsupervised work.
    const partial = structuredClone(snapshot); partial.id += ":partial";
    partial.employees[0].approvals = [{function_id:'sp5:service:201',workplace_id:'sp5:workplace:301',valid_from:'2026-02-02',valid_until:'2026-02-03',supervised:true}];
    await uploadProject( {name:'synthetic-partial.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(partial))});
    await page.waitForFunction(() => document.querySelector('.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:201"]').getAttribute('aria-pressed')==='false');
    assert.match(await page.locator(selector).innerText(), /Einzelne Arbeitsplätze/);
    await page.click(selector);
    const partialSave = page.waitForResponse(r=>r.url().endsWith('/api/snapshots') && r.request().method()==='PUT');
    await saveProject();
    const partialResult = await (await partialSave).json();
    assert(partialResult.employees[0].approvals.every(a=>a.supervised));
    assert(partialResult.employees[0].approvals.some(a=>a.valid_until==='2026-02-08'&&a.workplace_id==='*'));
    assert.equal(await page.locator('.matrix-cell[data-employee-id="sp5:employee:101"][data-function-id="sp5:service:202"]').getAttribute('aria-pressed'),'false');
    // Imported calendar groups by native service, not shared physical workplace.
    const calendarSnapshot=structuredClone(snapshot);
    calendarSnapshot.assignments=calendarSnapshot.demands.map(d=>({employee_id:calendarSnapshot.employees[0].id,demand_id:d.id,fixed:false,segments:[]}));
    await uploadProject({name:'synthetic-services.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(calendarSnapshot))});
    await navigate('plan');
    await page.selectOption('#planView','positions');
    await page.waitForFunction(()=>document.querySelector('#calendar thead').textContent.includes('Dienst'));
    assert.equal(await page.locator('#calendar tbody tr').count(),3);
    assert.equal(await page.locator('#calendar tbody tr').nth(2).locator('.shift-badge').count(),0);
    assert(await page.locator('#calendar tbody tr').nth(0).locator('.shift-badge').count()>0);
    assert(await page.locator('#calendar tbody tr').nth(1).locator('.shift-badge').count()>0);
    await page.selectOption('#planView','employees');
    await reveal('#demo');
    await page.click('#demo');
    await page.waitForFunction(() => document.querySelector('#source').textContent.includes('SYNTHETISCHE DEMO'));
    await navigate('calculate');
    await page.fill('#limit', '5');
    await page.click('#solve');
    await page.waitForFunction(() => document.querySelector('#result').textContent.includes('Vollständig'), null, {timeout:30000});
    assert(await page.locator('#calendar .shift-badge').count() > 0);
    assert.match(await page.locator('#calendar thead').innerText(), /Person/);
    await page.selectOption('#planView', 'positions');
    assert.match(await page.locator('#calendar thead').innerText(), /Funktion/);
    assert.match(await page.locator('#calendar .shift-badge').first().innerText(), /Testperson/);
    await screenshot('monthly.png');
    await page.locator('#assignmentDetails summary').click();
    await page.locator('#plan tbody input[type="checkbox"]').first().check();
    // A failing history list must not prevent polling the newly submitted job.
    let failedHistoryCalls=0;
    await page.route('**/api/jobs',async route=>{
      if(route.request().method()==='GET'){failedHistoryCalls++;await route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Liste vorübergehend nicht verfügbar"}'});}
      else await route.continue();
    });
    const recomputeResponse = page.waitForResponse(r=>r.url().endsWith('/api/jobs') && r.request().method()==='POST');
    await page.click('#recompute');
    const newJob = await (await recomputeResponse).json();
    assert.equal(typeof newJob.id,'string');
    assert(await page.locator('#matrix').evaluate(e=>e.inert),'Editors locked while a calculation is active');
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
    assert(failedHistoryCalls>0);
    assert.equal(await page.locator('#matrix').evaluate(e=>e.inert),false);
    await page.unroute('**/api/jobs');
    assert.match(await page.locator('#validation').textContent(), /"valid": true/);
    // A completed draft survives reload through the persistent job history.
    const solvedAssignments=computed.result.assignments.length;
    await page.addInitScript(()=>{Object.defineProperty(crypto,'randomUUID',{value:undefined,configurable:true});});
    await page.reload();
    await reveal('#savedJobs');
    await page.waitForSelector(`#savedJobs option[value="${newJob.id}"]`,{state:'attached'});
    await page.selectOption('#savedJobs',newJob.id);
    await page.click('#restoreJob');
    await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('Vollständig'));
    await navigate('plan');
    await page.locator('#assignmentDetails summary').click();
    await page.locator('#plan tbody tr').first().waitFor({state:'visible'});
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    assert.match(await page.locator('#saveStatus').innerText(),/Ungespeicherte/);
    // Project backup includes all rules and the latest fixed assignments and reopens.
    const backupDownload=page.waitForEvent('download');
    await page.click('#backup');
    const backup=await backupDownload;
    const backupPath=await backup.path();
    const backedUp=JSON.parse(fs.readFileSync(backupPath,'utf8'));
    assert.equal(backedUp.assignments.length,solvedAssignments);
    assert(backedUp.assignments.some(a=>a.fixed));
    assert(backedUp.employees.length>0 && backedUp.profiles.length>0);
    // Loading a project excludes both user and programmatic solve submissions.
    let releaseUpload,signalUpload;
    const uploadStarted=new Promise(resolve=>{signalUpload=resolve;});
    const uploadReleased=new Promise(resolve=>{releaseUpload=resolve;});
    await page.route('**/api/snapshots/check',async route=>{signalUpload();await uploadReleased;await route.continue();});
    const loading=uploadProject({name:'project-backup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(backedUp))});
    await uploadStarted;
    assert(await page.locator('#solve').isDisabled());
    assert(await page.locator('#recompute').isDisabled());
    let overlappingJobs=0;const countJob=request=>{if(request.url().endsWith('/api/jobs')&&request.method()==='POST')overlappingJobs++;};
    page.on('request',countJob);
    await page.locator('#solve').evaluate(button=>button.onclick());
    assert.equal(overlappingJobs,0);
    releaseUpload();await loading;
    page.off('request',countJob);await page.unroute('**/api/snapshots/check');
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Daten geladen'));
    await navigate('plan');
    await reveal('#plan');
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    // Invalid projects never replace the in-memory draft or leave the UI broken.
    await uploadProject({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{"employees":[]}')});
    await page.waitForFunction(()=>document.querySelector('#notice').classList.contains('error'));
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    assert.match(await page.locator('#notice').innerText(),/Felder/);
    const invalidZone=structuredClone(backedUp);invalidZone.timezone='Invalid/Nowhere';
    const rejectedZone=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
    await uploadProject({name:'invalid-timezone.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalidZone))});
    assert.equal((await rejectedZone).status(),422);
    await page.waitForFunction(()=>document.querySelector('#file').disabled===false);
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    const invalidSetup=structuredClone(backedUp);invalidSetup.metadata.setup_review={};
    const rejectedSetup=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
    await uploadProject({name:'invalid-setup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalidSetup))});
    assert.equal((await rejectedSetup).status(),422);
    assert.match(await page.locator('#notice').textContent(),/Einrichtungsübersicht.*beschädigt/);
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    for(const [key,value] of [['history_matrix',{}],['history_automation',{}],['workplaces',{}],['group_tree',[null]],['services',{}]]){
      const invalidHistory=structuredClone(backedUp);invalidHistory.metadata[key]=value;
      const rejectedHistory=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
      await uploadProject({name:'invalid-history.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalidHistory))});
      assert.equal((await rejectedHistory).status(),422);
      assert.match(await page.locator('#notice').textContent(),new RegExp(key));
      assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    }
    // Older saved projects and job inputs must pass the same preflight as files.
    for(const [endpoint,method] of [['snapshots/legacy-broken','openSavedProject'],['jobs/legacy-broken/snapshot','openJob']]){
      const damaged=structuredClone(backedUp);damaged.metadata.workplaces={};
      const pattern='**/api/'+endpoint;
      await page.route(pattern,route=>route.fulfill({json:damaged}));
      const before=await page.evaluate(()=>JSON.stringify(window.PlannerApp.getState()));
      const failure=await page.evaluate(async method=>{try{await window.PlannerApp[method]('legacy-broken');return null;}catch(error){return error.message;}},method);
      assert.match(failure??'',/workplaces/);
      assert.equal(await page.evaluate(()=>JSON.stringify(window.PlannerApp.getState())),before);
      assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
      await page.unroute(pattern);
    }
    acceptDiscard=false;
    await reveal('#demo');
    await page.click('#demo');
    assert.equal(await page.locator('#plan tbody tr').count(),Math.min(40,solvedAssignments));
    acceptDiscard=true;
    // Saving advances the recovered project without overwriting the original job input.
    const recoveredSave=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');
    await saveProject();
    const recovered=await(await recoveredSave).json();
    assert.notEqual(recovered.id,newJob.snapshot_id);
    assert.equal(recovered.assignments.length,solvedAssignments);
    assert.equal(recovered.metadata.restored_from_job,newJob.id);
    const original=await(await fetch(base+'/api/jobs/'+newJob.id+'/snapshot')).json();
    assert.equal(original.id,newJob.snapshot_id);
    // Every profile field is editable without JSON, with persisted nullable caps.
    await navigate('rules');
    const profile = page.locator('#profiles details').first();
    await profile.locator('summary').click();
    const expected = {
      version:'browser-synthetic',source:'synthetic',valid_from:'2026-01-01',valid_until:'2026-01-31',
      min_rest_minutes:600,after_night_rest_minutes:720,after_night_block_rest_minutes:1440,
      night_block_gap_days:2,weekly_rest_minutes:1800,weekly_rest_window_days:9,
      max_consecutive_work_days:5,max_consecutive_nights:3,max_daily_minutes:720,
      max_weekly_minutes:2400,max_period_minutes:4800,max_work_days:8,max_nights:4,max_weekends:1
    };
    for(const [key,value] of Object.entries(expected)) {
      await profile.locator(`[data-profile-field="${key}"]`).fill(String(value));
      await profile.locator(`[data-profile-field="${key}"]`).blur();
    }
    await profile.locator('[data-profile-field="weekly_rest_frame"]').selectOption('rolling_local');
    await profile.locator('[data-profile-field="weekly_rest_add_daily"]').check();
    await profile.locator('[data-profile-field="confirmed"]').check();
    assert.match(await page.locator('#validation').textContent(), /nicht aktuell/);
    assert(!await page.locator('#result').innerText().then(t=>t.includes('Vollständig')));
    const profileSave=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');
    await saveProject();
    const profileResponse=await profileSave;
    assert.equal(profileResponse.status(),200);
    const storedProfile=(await profileResponse.json()).profiles[0];
    for(const [key,value] of Object.entries({...expected,weekly_rest_frame:'rolling_local',weekly_rest_add_daily:true,confirmed:true}))assert.equal(storedProfile[key],value,key);
    await reveal('#restore');
    await page.click('#restore');
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Daten geladen'));
    await navigate('rules');
    await profile.locator('summary').click();
    assert.equal(await profile.locator('[data-profile-field="max_period_minutes"]').inputValue(),'4800');
    await profile.locator('[data-profile-field="max_period_minutes"]').fill('');
    const clearedSave=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');
    await saveProject();
    assert.equal((await (await clearedSave).json()).profiles[0].max_period_minutes,null);
    // The calendar renders local dates and end-exclusive midnight, not UTC slices.
    const demo = await (await fetch(base+'/api/demo')).json();
    const demand = demo.demands[0];
    demo.timezone = 'Pacific/Auckland';
    demo.period_start = '2026-01-05'; demo.period_end = '2026-01-18';
    demo.shifts.find(s => s.id===demand.shift_id).segments = [
      {start:'2026-01-04T20:00:00Z',end:'2026-01-05T11:00:00Z'}
    ];
    demo.assignments = [{employee_id:demo.employees[0].id,demand_id:demand.id,fixed:true,segments:[]}];
    await uploadProject( {name:'synthetic-calendar.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(demo))});
    await page.waitForFunction(() => document.querySelector('#source').textContent.includes('Pacific/Auckland'));
    await navigate('plan');
    await page.selectOption('#planView','employees');
    assert.equal(await page.locator('#calendar td[data-date="2026-01-05"] .shift-badge').count(),1);
    assert.equal(await page.locator('#calendar td[data-date="2026-01-06"] .shift-badge').count(),0);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await screenshot('mobile.png');
    // Unsaved removal of an input fixation must fail independent validation and export.
    await page.locator('#assignmentDetails').evaluate(details=>{details.open=true;});
    assert(await page.locator('#plan tbody input[type="checkbox"]').first().isChecked());
    await page.locator('#plan tbody tr').first().getByRole('button',{name:'Entfernen',exact:true}).click();
    const missingFixed=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.request().method()==='POST');
    await page.click('#validate');
    const fixedReport=await(await missingFixed).json();
    assert.equal(fixedReport.valid,false);
    assert(fixedReport.diagnostics.some(d=>d.code==='fixed'&&d.demand_id===demand.id),'Original fixed assignment remains the validation baseline');
    const rejectedExport=page.waitForResponse(r=>r.url().endsWith('/api/export/json')&&r.request().method()==='POST');
    await page.click('[data-export="json"]');
    assert.equal((await rejectedExport).status(),422);
    await page.waitForFunction(()=>document.querySelector('[data-export="json"]').dataset.busy!=='true');
    // Explicit save establishes a new input baseline for subsequent checks.
    const savedBaseline=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');
    await page.click('#saveDraft');
    assert.equal((await savedBaseline).status(),200);
    const checkedBaseline=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.request().method()==='POST');
    await page.click('#validate');
    assert(!(await(await checkedBaseline).json()).diagnostics.some(d=>d.code==='fixed'));
    await page.waitForFunction(()=>document.querySelector('#validate').dataset.busy!=='true');
    // Failed non-JSON responses remain actionable and duplicate submits are ignored.
    let validationCalls=0;
    await page.route('**/api/validate',async route=>{validationCalls++;await delay(250);await route.fulfill({status:503,contentType:'text/html',body:'Temporarily unavailable'});});
    await page.locator('#validate').evaluate(b=>{b.click();b.click();});
    assert(await page.locator('#validate').isDisabled());
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('HTTP 503'));
    assert.equal(validationCalls,1);
    assert(await page.locator('#validate').isEnabled());
    await page.unroute('**/api/validate');
    // Explicit SP5 setup reuse retains active position gates through import and save.
    const qualifiedPrevious=structuredClone(snapshot);
    qualifiedPrevious.id+=':qualified-setup';
    Object.assign(qualifiedPrevious.positions[0],{qualifications_required:true,qualification_ids:['synthetic-training'],qualification_level:2});
    await uploadProject({name:'synthetic-qualified-setup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(qualifiedPrevious))});
    await reveal('#reuseSetup');
    await page.selectOption('#sourceType','api');
    await page.click('#inspect');
    await page.waitForSelector('[data-team-id="3"]');
    await page.check('[data-team-id="1"]');
    await page.uncheck('[data-team-id="3"]');
    await page.fill('#start','2026-02-02');
    await page.fill('#end','2026-02-08');
    await page.check('#reuseSetup');
    const reusedSetup=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
    await page.click('#import');
    const reusedSnapshot=await (await reusedSetup).json();
    const reusedPosition=reusedSnapshot.positions.find(p=>p.id===qualifiedPrevious.positions[0].id);
    assert.equal(reusedPosition.qualifications_required,true);
    assert.deepEqual(reusedPosition.qualification_ids,['synthetic-training']);
    assert.equal(reusedPosition.qualification_level,2);
    await page.waitForFunction(()=>document.querySelector('#import').dataset.busy!=='true');
    const persistedSetup=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');
    await saveProject();
    assert.deepEqual((await(await persistedSetup).json()).positions.find(p=>p.id===reusedPosition.id),reusedPosition);
    await reveal('#reuseSetup');
    await page.uncheck('#reuseSetup');
    // A valid partial plan must explain missing approvals and link to the actual demand.
    const shortage = await (await fetch(base+'/api/demo')).json();
    shortage.id += ':approval-shortage';
    shortage.assignments = [];
    shortage.employees.forEach(employee => { employee.approvals = []; });
    await uploadProject({name:'synthetic-shortage.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(shortage))});
    await navigate('calculate');
    await page.check('#partial');
    await page.fill('#limit','5');
    await page.click('#solve');
    await page.waitForFunction(()=>document.querySelector('#job').textContent.includes('Berechnung beendet'));
    await reveal('#validationSummary');
    assert.match(await page.locator('#validationSummary').textContent(),/Gültiger Teilplan mit offenen Stellen/);
    const shortageGroup=page.locator('.validation-group').filter({has:page.locator('summary', {hasText:'Zu wenige geeignete Personen'})});
    await shortageGroup.locator(':scope > summary').click();
    const shortageItem=shortageGroup.locator('.diagnostic-item').first();
    assert.match(await shortageItem.textContent(),/persönliche Dienstfreigabe fehlt oder ist nicht gültig/);
    assert.match(await shortageItem.textContent(),/Mehrfachzählung möglich/);
    const shortageReport=JSON.parse(await page.locator('#validation').textContent());
    assert(shortageReport.valid && !shortageReport.complete);
    const shortageDemand=shortageReport.diagnostics.find(d=>d.code==='candidate_shortage').demand_id;
    await shortageItem.getByRole('button',{name:'Bedarf öffnen'}).click();
    assert(await page.locator('[data-panel="rules"]').isVisible());
    assert.equal(await page.locator('#demands .collection-toolbar input').inputValue(),shortageDemand);
    await navigate('calculate');
    await page.uncheck('#partial');
    await require('./product-flows.cjs')({page,base,navigate,reveal,uploadProject,root,state,delay});
    assert.deepEqual(errors, []);
    console.log('Passed: exact team selection, history, matrix, solver, job recovery, project backup roundtrip, rejected invalid files, unsaved-work guard, profile persistence, calendar/timezones, fixed-input validation/export, desktop/mobile, actionable errors.');
  } catch(error) {
    failed=true;
    if(browser){const pages=browser.contexts().flatMap(context=>context.pages());if(pages[0]){
      console.error('Browser state:',await pages[0].locator('#notice, #job, #saveStatus').allTextContents());
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await pages[0].screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,'failure.png'),fullPage:true});
    }}
    throw error;
  } finally {
    if(browser) await browser.close();
    server.kill('SIGTERM');
    await Promise.race([new Promise(resolve=>server.once('exit',resolve)),delay(5000)]);
    if(server.exitCode===null) server.kill('SIGKILL');
    if(failed && process.env.WEB_TEST_KEEP_STATE)console.error('Preserved browser state:',state);
    else fs.rmSync(state,{recursive:true,force:true});
  }
})().catch(error => {console.error(error.stack??error.message);console.error(output);process.exitCode=1;});
