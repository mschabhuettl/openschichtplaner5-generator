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
      await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,name),fullPage:!name.startsWith('reference-overview-')&&!name.startsWith('automatic-preflight-')});
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
    assert(await page.locator('#prepareNextPeriod').isDisabled(),'A previous project is required');
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
    await page.waitForFunction(()=>document.querySelector('#import').dataset.busy!=='true');
    await reveal('#prepareNextPeriod');
    const followingBefore=await page.evaluate(()=>({snapshot:JSON.stringify(currentSnapshot()),version:changeVersion,dirty,teams:[...checkedTeams],options:['referencePlan','historyPlan','existingPlanMode','sourceType'].map(id=>document.getElementById(id).value),flags:['reuseSetup','autoHistory','autoKind'].map(id=>document.getElementById(id).checked)}));
    let unintendedImports=0;
    const countFollowingImports=request=>{if(request.url().endsWith('/api/remote-import'))unintendedImports++;};
    page.on('request',countFollowingImports);
    assert.match(await page.locator('#followPeriodPreview').innerText(),/2026-02-09 bis 2026-02-15.*7 Kalendertage/);
    await page.click('#prepareNextPeriod');
    assert.equal(await page.locator('#start').inputValue(),'2026-02-09');
    assert.equal(await page.locator('#end').inputValue(),'2026-02-15');
    assert.equal(await page.locator('#historyStart').inputValue(),'2025-11-09');
    assert.equal(await page.locator('#historyEnd').inputValue(),'2026-02-08');
    assert.equal(await page.locator('#timezone').inputValue(),snapshot.timezone);
    assert.equal(await page.locator('#start').evaluate(e=>document.activeElement===e),true);
    await page.selectOption('#followPeriodMode','month');
    assert.match(await page.locator('#followPeriodPreview').innerText(),/2026-02-09 bis 2026-02-28.*20 Kalendertage/);
    assert.equal(await page.locator('#end').inputValue(),'2026-02-15','Preview alone does not replace import dates');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await page.click('#prepareNextPeriod');
      assert.equal(await page.locator('#end').inputValue(),'2026-02-28');
      assert.equal(await page.locator('#start').inputValue(),'2026-02-09','Repeated preparation remains anchored to the opened project');
      await page.locator('#followPeriodPreparation').evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-100));
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await page.locator('#followPeriodPreparation').screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`follow-period-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    assert.equal(unintendedImports,0,'Date preparation never starts a source import');page.off('request',countFollowingImports);
    assert.deepEqual(await page.evaluate(()=>({snapshot:JSON.stringify(currentSnapshot()),version:changeVersion,dirty,teams:[...checkedTeams],options:['referencePlan','historyPlan','existingPlanMode','sourceType'].map(id=>document.getElementById(id).value),flags:['reuseSetup','autoHistory','autoKind'].map(id=>document.getElementById(id).checked)})),followingBefore);
    await page.fill('#start',snapshot.period_start);await page.fill('#end',snapshot.period_end);
    await page.fill('#historyStart','2026-01-01');await page.fill('#historyEnd','2026-01-31');
    await navigate('rules');
    await page.waitForSelector('#setupReview');
    assert.equal(snapshot.metadata.reference_plan,'ist');
    assert.match(await page.locator('#referenceImport').innerText(),/Istplan/);
    assert.match(await page.locator('#referenceImport').innerText(),/0 Vergleichsdienste/);
    const referenceFixture=structuredClone(snapshot);
    referenceFixture.metadata.reference_schedule=Array.from({length:13},(_,i)=>({employee_id:101,date:'2026-02-02',shift_id:201,...(i===0?{demand_id:snapshot.demands[0].id}:i===1?{resolution:'ambiguous',resolution_reason:'ambiguous'}:{resolution:'unmatched',...(i%3===0?{resolution_reason:'zero_capacity'}:i%3===2?{resolution_reason:'missing_demand'}:{})})}));
    const referencePath=path.join(state,'reference-overview.json');
    const originalPath=path.join(state,'reference-original.json');
    fs.writeFileSync(referencePath,JSON.stringify(referenceFixture));fs.writeFileSync(originalPath,JSON.stringify(snapshot));
    await uploadProject(referencePath);await navigate('rules');
    const referenceBox=page.locator('#referenceImport');
    assert.match(await referenceBox.innerText(),/Eindeutig zugeordnet: 1/);
    assert.match(await referenceBox.innerText(),/Ohne Zuordnung: 11/);
    assert.match(await referenceBox.innerText(),/Mehrdeutig: 1/);
    assert.match(await referenceBox.innerText(),/keine aktuelle Planprüfung/);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await screenshot(`reference-overview-${width}.png`);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await referenceBox.locator('summary').click();
    await referenceBox.locator('.card').first().waitFor();
    assert.equal(await referenceBox.locator('.card').count(),10);
    assert.match(await referenceBox.locator('.card').first().innerText(),/Testperson 001.*Dienst A/);
    await referenceBox.getByRole('button',{name:'Vergleichsdienste: nächste Seite',exact:true}).click();
    assert.equal(await referenceBox.locator('.card').count(),3);
    assert.equal(await referenceBox.locator('[data-page-status]').evaluate(e=>document.activeElement===e),true,'Last-page navigation focuses the new range instead of the removed button');
    const unfilteredState=await page.evaluate(()=>({version:changeVersion,dirty,snapshot:JSON.stringify(currentSnapshot())}));
    const referenceFilter=referenceBox.getByLabel('Zuordnung filtern',{exact:true});
    await referenceFilter.selectOption('unmatched');
    assert.equal(await referenceBox.locator('.card').count(),10,'Changing filters returns to page one');
    assert.match(await referenceBox.innerText(),/Kein Bedarf für dieses Datum und diesen Dienst/);
    assert.match(await referenceBox.innerText(),/Passender Bedarf hat überall Maximum 0/);
    assert.match(await referenceBox.innerText(),/Konkrete Ursache im Import nicht dokumentiert/);
    await referenceBox.getByRole('button',{name:'Vergleichsdienste: nächste Seite',exact:true}).click();
    assert.equal(await referenceBox.locator('.card').count(),1);
    await referenceFilter.selectOption('ambiguous');
    assert.equal(await referenceBox.locator('.card').count(),1);
    assert.match(await referenceBox.innerText(),/Mehrere passende Bedarfsgruppen/);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await referenceBox.locator('details').screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`reference-reason-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await referenceFilter.selectOption('unknown');
    assert.equal(await referenceBox.locator('.card').count(),0);
    await referenceFilter.selectOption('matched');
    assert.equal(await referenceBox.locator('.card').count(),1);
    assert.doesNotMatch(await referenceBox.locator('.card').innerText(),/Ursache/);
    await referenceFilter.selectOption('all');
    assert.deepEqual(await page.evaluate(()=>({version:changeVersion,dirty,snapshot:JSON.stringify(currentSnapshot())})),unfilteredState,'Read-only filtering never invalidates results or changes the project');

    const untouched=await page.evaluate(()=>JSON.stringify(currentSnapshot()));
    await referenceBox.getByRole('button',{name:'Team & Freigaben prüfen',exact:true}).click();
    assert.equal(await page.locator('#teamTitle').evaluate(e=>document.activeElement===e),true);
    await navigate('rules');await referenceBox.getByRole('button',{name:'Bedarf prüfen',exact:true}).click();
    assert.equal(await page.locator('#demands').evaluate(e=>document.activeElement===e&&e.closest('details').open),true);
    assert.equal(await page.evaluate(()=>JSON.stringify(currentSnapshot())),untouched,'Overview and navigation never change rules, approvals or assignments');
    await referenceFilter.selectOption('matched');
    await referenceBox.getByRole('button',{name:'Zugeordneten Bedarf prüfen',exact:true}).click();
    assert.equal(await page.locator('[data-collection-search="demands"]').inputValue(),snapshot.demands[0].id);
    assert.equal(await page.locator('[data-collection-search="demands"]').evaluate(e=>document.activeElement===e),true);
    assert.match(await page.locator('#demands').innerText(),/Dienst A/);
    await referenceBox.getByRole('button',{name:'Person prüfen',exact:true}).click();
    assert.equal(await page.locator('#details input').first().inputValue(),'Testperson 001');
    assert.equal(await page.locator('#details input').first().evaluate(e=>document.activeElement===e),true);
    await navigate('rules');await referenceFilter.selectOption('ambiguous');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      await referenceBox.locator('.card').first().waitFor();
      await referenceBox.locator('details').evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-100));
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await referenceBox.locator('details').screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`reference-navigation-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await referenceBox.getByRole('button',{name:'Bedarfe am Datum prüfen',exact:true}).click();
      assert.equal(await page.locator('[data-collection-search="demands"]').inputValue(),'2026-02-02');
      assert.equal(await page.locator('[data-collection-search="demands"]').evaluate(e=>document.activeElement===e),true);
      assert.match(await page.locator('#demands').innerText(),/2026-02-02/);
    }
    assert.deepEqual(await page.evaluate(()=>({version:changeVersion,dirty,snapshot:JSON.stringify(currentSnapshot())})),unfilteredState,'Reference review shortcuts do not change project data, approvals or validation state');
    const staleReference=structuredClone(referenceFixture);
    staleReference.metadata.reference_schedule=[{employee_id:999999,date:'2099-01-01',shift_id:201,demand_id:'missing-demand'}];
    fs.writeFileSync(referencePath,JSON.stringify(staleReference));
    await uploadProject(referencePath);await navigate('rules');await referenceBox.locator('summary').click();
    await referenceBox.locator('.card').first().waitFor();
    assert.equal(await referenceBox.getByRole('button',{name:'Person prüfen',exact:true}).count(),0);
    assert.equal(await referenceBox.getByRole('button',{name:'Zugeordneten Bedarf prüfen',exact:true}).count(),0);
    assert.match(await referenceBox.innerText(),/im aktuellen Projekt nicht mehr vorhanden/);
    const staleBefore=await page.evaluate(()=>JSON.stringify(currentSnapshot()));
    await referenceBox.getByRole('button',{name:'Bedarfe am Datum prüfen',exact:true}).click();
    assert.equal(await page.locator('#demands tbody tr').count(),0,'Unknown reference date does not invent demand');
    assert.equal(await page.evaluate(()=>JSON.stringify(currentSnapshot())),staleBefore);
    delete referenceFixture.metadata.reference_plan;
    fs.writeFileSync(referencePath,JSON.stringify(referenceFixture));
    await uploadProject(referencePath);await navigate('rules');
    assert.match(await referenceBox.innerText(),/Plansicht nicht dokumentiert/);
    await uploadProject(originalPath);await navigate('rules');
    await page.setViewportSize({width:1440,height:1000});

    // Large warning lists stay paged and searchable; resolving a filtered duplicate removes only that row.
    const issuesFixture=structuredClone(snapshot);
    issuesFixture.unresolved=Array.from({length:1001},(_,i)=>`Synthetische Prüfangabe ${String(i+1).padStart(4,'0')}`);
    issuesFixture.unresolved[17]=issuesFixture.unresolved[999]='Gezielter synthetischer Hinweis';
    const issuesPath=path.join(state,'import-issues.json');fs.writeFileSync(issuesPath,JSON.stringify(issuesFixture));
    await uploadProject(issuesPath);await navigate('rules');
    const issuesBox=page.locator('#unresolved'),issueSearch=issuesBox.getByRole('searchbox',{name:'Offene Angaben suchen',exact:true});
    assert.equal(await issuesBox.locator('.card').count(),10);
    assert.match(await issuesBox.innerText(),/von 1001 Offene Angaben/);
    const beforeIssueSearch=await page.evaluate(()=>({version:changeVersion,dirty,snapshot:JSON.stringify(currentSnapshot())}));
    await issuesBox.getByRole('button',{name:'Offene Angaben: nächste Seite',exact:true}).click();
    assert.equal(await issuesBox.getByRole('button',{name:'Offene Angaben: nächste Seite',exact:true}).evaluate(e=>document.activeElement===e),true);
    await page.keyboard.press('Enter');
    assert.match(await issuesBox.locator('.card').first().innerText(),/Prüfangabe 0021/);
    await issuesBox.getByRole('button',{name:'Offene Angaben: vorherige Seite',exact:true}).click();
    assert.match(await issuesBox.locator('.card').first().innerText(),/Prüfangabe 0011/);
    await issueSearch.fill('nicht vorhanden xxx');
    await page.waitForFunction(()=>document.querySelector('#unresolved').textContent.includes('Keine passenden Angaben'));
    assert.equal(await issuesBox.locator('.card').count(),0);
    await issueSearch.fill('Gezielter synthetischer Hinweis');
    await page.waitForFunction(()=>document.querySelectorAll('#unresolved .card').length===2);
    assert.deepEqual(await page.evaluate(()=>({version:changeVersion,dirty,snapshot:JSON.stringify(currentSnapshot())})),beforeIssueSearch);
    await issuesBox.locator('.card').nth(1).getByRole('button',{name:'Nach fachlicher Korrektur als geklärt markieren',exact:true}).click();
    const expectedIssues=[...issuesFixture.unresolved];expectedIssues.splice(999,1);
    assert.deepEqual(await page.evaluate(()=>currentSnapshot().unresolved),expectedIssues);
    assert.equal(await issuesBox.locator('.card').count(),1);
    assert.deepEqual(await page.evaluate(()=>currentSnapshot().employees),issuesFixture.employees);
    assert.deepEqual(await page.evaluate(()=>currentSnapshot().profiles),issuesFixture.profiles);
    await issueSearch.fill('');
    await page.waitForFunction(()=>document.querySelectorAll('#unresolved .card').length===10);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await page.locator('.unresolved-surface').screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`paged-import-issues-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await uploadProject(originalPath);await navigate('rules');await page.setViewportSize({width:1440,height:1000});
    // Select a distinct Soll baseline without changing history, availability or approvals.
    await reveal('#referencePlan');
    assert.equal(await page.locator('#referencePlan').inputValue(),'ist');
    await page.selectOption('#referencePlan','soll');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await page.locator('#referencePlan').scrollIntoViewIfNeeded();
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`reference-selection-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.setViewportSize({width:1440,height:1000});

    assert.equal(await page.locator('#historyPlan').inputValue(),'ist');
    assert.match(await page.locator('#referencePlanHelp').innerText(),/Abwesenheiten, Sonderdienste und Randkontext bleiben aus dem Istplan/);
    const sollImported=page.waitForResponse(r=>r.url().endsWith('/api/remote-import')&&r.request().method()==='POST');
    await page.click('#import');const sollResponse=await sollImported;
    assert.equal(sollResponse.status(),200);
    const sollSnapshot=(await sollResponse.json()).snapshot;
    assert.equal(sollSnapshot.metadata.reference_plan,'soll');
    assert.equal(sollSnapshot.metadata.history_plan,'ist');
    assert.equal(sollSnapshot.metadata.reference_schedule.length,1);
    assert.equal(sollSnapshot.metadata.reference_schedule[0].shift_id,201);
    assert(sollSnapshot.employees.every(person=>person.approvals.length===0&&person.unavailable.length===0));
    assert(sollSnapshot.profiles.every(profile=>!profile.confirmed));
    assert.equal(sollSnapshot.context_complete,false);
    assert(sollSnapshot.unresolved.length>0);
    await navigate('rules');
    assert.match(await referenceBox.innerText(),/Sollplan/);
    assert.match(await referenceBox.innerText(),/Eindeutig zugeordnet: 1/);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await screenshot(`reference-overview-soll-${width}.png`);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await reveal('#referencePlan');await page.selectOption('#referencePlan','ist');
    await uploadProject(originalPath);await navigate('rules');
    await page.setViewportSize({width:1440,height:1000});
    assert.equal(await page.locator('#metricBlockers').innerText(),'—');
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'noch nicht geprüft');
    const readiness=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));
    await page.getByRole('button',{name:'Planungsbereitschaft prüfen',exact:true}).click();
    const manualResponse=await readiness;assert.equal(manualResponse.status(),200);
    const expectedHints=(await manualResponse.json()).diagnostics.length;
    await page.getByText('Vor der Berechnung noch bearbeiten:',{exact:true}).waitFor();
    assert.equal(await page.locator('#metricBlockers').innerText(),String(expectedHints));
    // Opening Calculate runs the existing read-only check, never saves or starts jobs.
    const writes=[];
    const observeWrites=request=>{if(['POST','PUT'].includes(request.method())&&/\/api\/(snapshots|jobs)$/.test(new URL(request.url()).pathname))writes.push(request.url());};
    page.on('request',observeWrites);
    const automaticResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));
    await navigate('calculate');await automaticResponse;
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    assert(await page.locator('#automaticReadinessDetails').innerText());
    assert.equal(await page.locator('#metricBlockers').innerText(),String(expectedHints));
    assert.equal(await page.locator('#navBlockers').innerText(),String(expectedHints));
    assert.match(await page.locator('#calculationReadiness').innerText(),new RegExp(`^${expectedHints} Hinweise`));
    assert.deepEqual(writes,[]);page.off('request',observeWrites);
    const category=page.locator('#readinessCategory'),beforeCategory=await page.evaluate(()=>({snapshot:JSON.stringify(currentSnapshot()),version:changeVersion,dirty,readiness:currentReadiness()}));
    let categoryChecks=0;const countCategoryChecks=request=>{if(request.url().endsWith('/api/readiness'))categoryChecks++;};page.on('request',countCategoryChecks);
    await category.selectOption('profile');
    assert.equal(await page.locator('#automaticReadinessDetails .diagnostic-item').count(),2);
    assert.equal(await page.locator('#metricBlockers').innerText(),String(expectedHints),'Filtering does not shrink the total input issue count');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      const box=page.locator('#automaticReadinessTitle').locator('..');
      await box.evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-100));
      if(process.env.WEB_TEST_SCREENSHOT_DIR)await box.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`readiness-category-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.locator('#automaticReadinessDetails').getByRole('button',{name:'Regelprofile prüfen',exact:true}).click();
    assert.equal(await page.locator('#profiles h3').first().evaluate(e=>document.activeElement===e),true);
    await navigate('calculate');await category.selectOption('unresolved');
    await page.locator('#automaticReadinessDetails').getByRole('button',{name:'Offene Angaben prüfen',exact:true}).click();
    assert.equal(await page.locator('#unresolved').evaluate(e=>document.activeElement===e&&e.offsetParent!==null),true);
    await navigate('calculate');await category.selectOption('all');
    assert.deepEqual(await page.evaluate(()=>({snapshot:JSON.stringify(currentSnapshot()),version:changeVersion,dirty,readiness:currentReadiness()})),beforeCategory);
    assert.equal(categoryChecks,0,'Category changes and review navigation reuse the current check');page.off('request',countCategoryChecks);
    const personHint=page.locator('#automaticReadinessDetails .diagnostic-item').filter({hasText:'Kein bestätigtes gültiges Regelprofil: Testperson 001'});
    assert.equal(await personHint.count(),1);
    assert(!(await personHint.innerText()).includes('sp5:employee:101'));
    await personHint.getByRole('button',{name:'Person bearbeiten',exact:true}).click();
    assert.equal(await page.locator('#details').getByLabel('Name',{exact:true}).inputValue(),'Testperson 001');
    await navigate('calculate');

    await screenshot('automatic-preflight.png');
    const manyHints={ready:false,diagnostics:[...Array.from({length:1001},(_,i)=>({code:'unresolved',message:`Synthetische offene Angabe ${i}`})),{code:'context',message:'Synthetischer Randkontext'}]};
    await page.route('**/api/readiness',route=>route.fulfill({json:manyHints}),{times:1});
    await page.fill('#projectName','Viele synthetische Prüfhinweise');await page.locator('#projectName').blur();
    await page.waitForFunction(()=>document.querySelector('#metricBlockers').textContent==='1.002');
    await category.selectOption('unresolved');
    assert.equal(await page.locator('#automaticReadinessDetails .diagnostic-item').count(),10);
    await page.locator('#automaticReadinessDetails').getByRole('button',{name:'Hinweise: nächste Seite',exact:true}).click();
    await category.selectOption('context');
    assert.equal(await page.locator('#automaticReadinessDetails .diagnostic-item').count(),1,'Category switch returns to its first page');
    await page.locator('#automaticReadinessDetails').getByRole('button',{name:'Randkontext prüfen',exact:true}).click();
    assert.equal(await page.locator('#contextConfirmation h3').evaluate(e=>document.activeElement===e),true);
    await navigate('calculate');assert.equal(await page.locator('#metricBlockers').innerText(),'1.002');
    // A delayed old success must not replace a newer failed check after an edit.
    let releaseOld,oldSeenResolve;const oldSeen=new Promise(resolve=>oldSeenResolve=resolve);
    await page.route('**/api/readiness',async route=>{oldSeenResolve();await new Promise(resolve=>releaseOld=resolve);await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ready:true,diagnostics:[]})});},{times:1});
    await page.fill('#projectName','Vorprüfung alt');await page.locator('#projectName').blur();await oldSeen;
    assert.equal(await page.locator('#metricBlockers').innerText(),'…');
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'wird geprüft');
    await page.route('**/api/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetische Prüfunterbrechung'})}),{times:1});
    await page.fill('#projectName','Vorprüfung aktuell');await page.locator('#projectName').blur();
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='error');
    const oldResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness')&&r.status()===200);releaseOld();await oldResponse;
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await page.locator('#automaticReadinessStatus').getAttribute('data-state'),'error');
    assert.equal(await page.locator('#metricBlockers').innerText(),'—');
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'Prüfung fehlgeschlagen');
    assert(await page.locator('#retryReadiness').isVisible());
    await page.click('#retryReadiness');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    assert(await page.locator('#retryReadiness').isHidden());
    assert.equal(await category.inputValue(),'all','A category absent from the fresh result falls back to all hints');
    let repeatedChecks=0;const countChecks=request=>{if(request.url().endsWith('/api/readiness'))repeatedChecks++;};
    page.on('request',countChecks);await navigate('team');await navigate('calculate');
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(repeatedChecks,0,'Unchanged project reuses the current check');page.off('request',countChecks);
    await reveal('#json');await page.fill('#json',(await page.locator('#json').inputValue())+' ');
    await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='draft');
    assert(await page.locator('#prepareNextPeriod').isDisabled(),'Unapplied JSON cannot be used as period basis');
    assert.equal(await page.locator('#metricBlockers').innerText(),'—');
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'Bearbeitung offen');
    assert.equal(await page.locator('#automaticReadinessDetails').innerText(),'');
    await reveal('#refreshJson');await page.click('#refreshJson');await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues');
    assert(await page.locator('#prepareNextPeriod').isEnabled(),'Discarding JSON restores date preparation');
    // Ignore an in-flight reply during hidden JSON editing, then allow a fresh check.
    await page.route('**/api/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Fehler vor Wiederholung'})}),{times:1});
    await page.fill('#projectName','Prüfung während JSON-Bearbeitung');await page.locator('#projectName').blur();
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='error');
    let releaseHidden,hiddenSeenResolve;const hiddenSeen=new Promise(resolve=>hiddenSeenResolve=resolve);
    await page.route('**/api/readiness',async route=>{hiddenSeenResolve();await new Promise(resolve=>releaseHidden=resolve);await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ready:true,diagnostics:[]})});},{times:1});
    await page.click('#retryReadiness');await hiddenSeen;
    await reveal('#json');await page.fill('#json',(await page.locator('#json').inputValue())+' ');
    const hiddenResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness'));releaseHidden();await hiddenResponse;
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'Bearbeitung offen');
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    await reveal('#refreshJson');await page.click('#refreshJson');await navigate('calculate');
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='issues',null,{timeout:5000});
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});await screenshot(`automatic-preflight-${width}.png`);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.setViewportSize({width:1440,height:1000});
    await navigate('rules');


    assert.equal(await page.locator('#metricBlockers').innerText(),String(expectedHints));
    const patternRow=page.locator('#serviceGroups tbody tr').first();
    await patternRow.locator('select').selectOption('night');
    await patternRow.getByRole('button',{name:'Offene Vorkommen übernehmen'}).click();
    await page.waitForFunction(()=>document.querySelector('#metricBlockersLabel').textContent==='noch nicht geprüft');
    assert.equal(await page.locator('#metricBlockers').innerText(),'—');
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
    await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state==='ready');
    assert.equal(await page.locator('#metricBlockers').innerText(),'0');
    assert.equal(await page.locator('#metricBlockersLabel').innerText(),'Eingabehinweise');
    assert.match(await page.locator('#calculationReadiness').innerText(),/Ergebnisprüfung stehen noch aus/);
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
