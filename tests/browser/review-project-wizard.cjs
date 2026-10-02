'use strict';
// UX-03B: real wizard controls and synthetic loopback persistence only.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function fixture(name,run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-project-wizard-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 const observations={consoleErrors:[],pageErrors:[],measurements:[]};
 const artifacts=process.env.WEB_TEST_SCREENSHOT_DIR;
 if(artifacts)fs.mkdirSync(artifacts,{recursive:true});
 try{
  const base=await bounded((async()=>{for(;;){
   if(spawnError)throw spawnError;
   if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
   const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
   if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
   await pause(100);
  }})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({baseURL:base,viewport:{width:1440,height:1000},timezoneId:'Europe/Vienna',locale:'de-AT'});page.setDefaultTimeout(7000);
  page.on('pageerror',error=>observations.pageErrors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')observations.consoleErrors.push(message.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run(page,{base,observations,artifacts}),60000,'Wizard scenario');
  assert.deepEqual(observations.pageErrors,[],'no JavaScript exceptions');
 }finally{
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{
    fs.rmSync(state,{recursive:true,force:true});
    if(artifacts)fs.writeFileSync(path.join(artifacts,name+'.json'),JSON.stringify(observations,null,2)+'\n');
   }
  }
 }
}
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(160);}
async function shifts(page){
 await page.click('#newProject');await page.fill('#wizardName','Synthetisches Team Oktober');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
}
async function measure(page,label,observations,artifacts){
 await settle(page);
 const m=await page.locator('#createProjectDialog').evaluate(d=>{
  const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
  const visible=e=>{
   if(e.closest('[hidden]')||!e.getClientRects().length||getComputedStyle(e).visibility==='hidden')return false;
   for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS'&&!p.open&&!p.querySelector(':scope > summary')?.contains(e))return false;
   const r=rect(e);return r.width>1&&r.height>1;
  };
  const geometry=e=>{
   const r=rect(e),clips=[];
   for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),b=p.getBoundingClientRect();clips.push({id:p.id,x:!(/auto|scroll|hidden|clip/.test(s.overflowX))||(r.left>=b.left+p.clientLeft&&r.right<=b.left+p.clientLeft+p.clientWidth),y:!(/auto|scroll|hidden|clip/.test(s.overflowY))||(r.top>=b.top+p.clientTop&&r.bottom<=b.top+p.clientTop+p.clientHeight)});}
   const hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);
   return {...r,fullyVisible:r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight&&clips.every(c=>c.x&&c.y),centerHit:hit===e||e.contains(hit),clips};
  };
  return {width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,dialog:{...rect(d),scrollHeight:d.scrollHeight,clientHeight:d.clientHeight,scrollTop:d.scrollTop,scrollWidth:d.scrollWidth,clientWidth:d.clientWidth},step:d.querySelector('[aria-current="step"]')?.textContent,controls:[...d.querySelectorAll('button,input,select,textarea,summary,a[href]')].filter(visible).map(e=>({id:e.id,tag:e.tagName,label:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.textContent.trim(),...geometry(e)}))};
 });m.label=label;observations.measurements.push(m);
 if(artifacts)await page.screenshot({path:path.join(artifacts,`wizard-${m.width}-${label}.png`)});
 return m;
}
for(const width of [1440,390])test(`UX03B-P01/P02 separate shifts and readable rules within control/scroll budgets at ${width}`,async()=>fixture('wizard-layout-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await shifts(page);
 const shift=await measure(page,'shifts-entry',observations,artifacts);
 assert(shift.controls.length<=18,'UX03B-P01 shift control budget: '+shift.controls.length);
 await page.click('#wizardNext');
 const rules=await measure(page,'rules-entry',observations,artifacts);
 assert.match(rules.step,/4.*Regeln/);assert(rules.controls.length<=7,'UX03B-P01 closed rules control budget: '+rules.controls.length);
 const summary=await page.locator('#wizardRuleValues').innerText();
 for(const text of ['11 Stunden','6 Tage','3 Nächte','12 Stunden','48 Stunden','36 Stunden'])assert(summary.includes(text),'visible rule value with unit: '+text);
 assert.equal(await page.locator('#wizardRuleValues > div').count(),7);
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])assert.equal(await page.locator('#'+id).isChecked(),false);
 await page.locator('#wizardRuleEditor > summary').click();
 const expanded=await measure(page,'rules-expanded',observations,artifacts);
 assert(expanded.controls.length<=14,'UX03B-P01 expanded rules control budget: '+expanded.controls.length);
 for(const id of ['wizardMinRest','wizardNightRest','wizardWorkDays','wizardNights','wizardDailyHours','wizardMaxWeeklyHours','wizardWeeklyRest'])assert(await page.locator('#'+id).isVisible());
 for(const [m,id,maximum] of [[shift,'wizardNext',width===390?1500:1000],[rules,'wizardCreate',width===390?1200:1000]]){
  assert.equal(m.dialog.scrollTop,0,'UX03B-P02 step entry starts at the top, not a native focus-scroll offset');
  assert(m.dialog.scrollHeight<=maximum,'UX03B-P02 scroll budget '+JSON.stringify(m.dialog));
  assert(m.documentWidth<=width&&m.dialog.scrollWidth<=m.dialog.clientWidth,'no horizontal overflow');
  const action=m.controls.find(c=>c.id===id);assert(action?.fullyVisible&&action.centerHit,'UX03B-P02 primary action visible at entry: '+JSON.stringify(action));
  assert(action.width>=44&&action.height>=44,'UX03B-P05 primary target size');
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03B-P04 returning through Team preserves unadmitted demand text and its node',async()=>fixture('wizard-invalid-demand',async(page,{observations,artifacts})=>{
 await shifts(page);const field=page.locator('#wizardTemplates [data-field="minimum"]').first();
 await field.fill('');await field.press('1');await field.press('e');
 await page.evaluate(()=>window.reviewDemandNode=document.querySelector('#wizardTemplates [data-field="minimum"]'));
 const before=await values(page);assert(before.some(v=>v.badInput));
 await page.click('#wizardBack');await page.click('#wizardNext');
 assert(await field.evaluate(e=>e===window.reviewDemandNode&&e.validity.badInput),'do not rebuild unchanged templates from their numeric model');
 assert.deepEqual(await values(page),before);
 await page.click('#wizardNext');const m=await measure(page,'invalid-demand',observations,artifacts);
 const target=m.controls.find(c=>c.label.startsWith('Funktion A Minimum'));
 assert(await field.evaluate(e=>e===document.activeElement));assert(target?.fullyVisible&&target.centerHit);
 assert.match(m.step,/3.*Schichten/);assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03B-P03/P04/P06 exact draft, explicit confirmations, 422, busy and save/reopen',async()=>fixture('wizard-data',async(page,{base,observations})=>{
 await page.setViewportSize({width:390,height:1000});await shifts(page);await page.click('#wizardBack');
 await page.fill('#wizardPeople','Synthetisch A; 32; 80\nSynthetisch B; 40; 100\nSynthetisch C; 20; 50');
 await page.fill('#wizardPositions','Funktion A\nFunktion B');await page.click('#wizardNext');
 await page.locator('#wizardTemplates [data-field="name"]').first().fill('Synthetischer Tag');
 await page.click('#wizardAddTemplate');const night=page.locator('.wizard-template').nth(1);
 await night.locator('[data-field="name"]').fill('Synthetische Nacht');await night.locator('[data-field="kind"]').selectOption('night');
 await night.locator('[data-field="start"]').fill('22:00');await night.locator('[data-field="end"]').fill('06:00');
 for(let day=0;day<7;day++)await night.locator('[data-weekday="'+day+'"]').setChecked([2,5].includes(day));
 await night.locator('[data-field="maximum"]').first().fill('2');await page.click('#wizardNext');
 await page.locator('#wizardRuleEditor > summary').click();await page.fill('#wizardMinRest','12.5');await page.locator('#wizardRuleEditor > summary').click();
 const unconfirmed=await values(page);
 for(let n=0;n<3;n++)await page.click('#wizardBack');for(let n=0;n<3;n++)await page.click('#wizardNext');
 assert.deepEqual(await values(page),unconfirmed);await page.click('#wizardCancel');await page.click('#newProject');assert.deepEqual(await values(page),unconfirmed);
 const posts=[];page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/projects/new'))posts.push(r.postDataJSON());});
 await page.click('#wizardCreate');await settle(page);assert.equal(posts.length,0);assert(await page.locator('#wizardRulesConfirmed').evaluate(e=>e===document.activeElement));
 await page.check('#wizardRulesConfirmed');const confirmed=await values(page);
 await page.route('**/api/projects/new',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Server-Prüffehler'})}),{times:1});
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectForm').hasAttribute('aria-busy')&&document.getElementById('wizardError').textContent.includes('Server-Prüffehler'));
 assert.deepEqual(await values(page),confirmed);assert.equal(posts.length,1);
 let release,arrived,finished,routeError;const hold=new Promise(r=>release=r),arrival=new Promise(r=>arrived=r),done=new Promise(r=>finished=r);
 await page.route('**/api/projects/new',async route=>{try{arrived();await bounded(hold,10000,'synthetic creation delay');await route.continue();}catch(error){routeError=error;try{await route.abort();}catch{}}finally{finished();}},{times:1});
 const response=page.waitForResponse(r=>r.url().endsWith('/api/projects/new')&&r.request().method()==='POST');
 try{
  await page.click('#wizardCreate');await bounded(arrival,10000,'creation arrival');
  assert(await page.locator('#createProjectForm').evaluate(f=>f.getAttribute('aria-busy')==='true'&&[...f.querySelectorAll('button,input,select,textarea')].every(e=>e.disabled)));
  await page.keyboard.press('Escape');assert(await page.locator('#createProjectDialog').evaluate(d=>d.open));
  for(const key of ['Tab','Tab','Shift+Tab']){
   await page.keyboard.press(key);
   assert(await page.locator('#createProjectDialog').evaluate(d=>d.contains(document.activeElement)),'busy keyboard focus remains in modal');
  }
  await page.evaluate(()=>document.getElementById('createProjectForm').requestSubmit());assert.equal(posts.length,2,'busy submit is ignored');
  assert.deepEqual(await values(page),confirmed);
 }finally{release();await bounded(done,10000,'owned callback drain');if(routeError)throw routeError;}
 const created=await response;assert.equal(created.status(),200);const result=(await created.json()).snapshot;
 await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&!projectSwitchBusy());
 assert.deepEqual(posts[0],posts[1]);const sent=posts[1];observations.request=sent;observations.result=result;
 assert.equal(sent.rules_confirmed,true);assert.equal(sent.approvals_confirmed,false);assert.equal(sent.context_duty_free_confirmed,false);
 assert.equal(sent.rules.min_rest_hours,12.5);assert.deepEqual(sent.people,[{name:'Synthetisch A',weekly_hours:32,employment_fraction:80},{name:'Synthetisch B',weekly_hours:40,employment_fraction:100},{name:'Synthetisch C',weekly_hours:20,employment_fraction:50}]);
 assert.deepEqual(sent.positions,[{name:'Funktion A'},{name:'Funktion B'}]);
 assert.deepEqual(sent.shift_templates[1],{name:'Synthetische Nacht',kind:'night',start_time:'22:00',end_time:'06:00',weekdays:[2,5],demands:[{position:0,minimum:1,maximum:2},{position:1,minimum:1,maximum:1}]});
 assert.equal(result.context_complete,false);assert.equal(result.metadata.setup_approvals_confirmed,false);assert.equal(result.metadata.context_duty_free_confirmed,false);assert(result.employees.every(e=>e.approvals.length===0));assert.equal(result.profiles[0].min_rest_minutes,sent.rules.min_rest_hours*60);
 await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());const saved=await page.evaluate(()=>currentSnapshot());
 assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+saved.id)).json(),saved);
 await page.reload();await page.locator('.project-card[data-project-id="'+saved.id+'"]').click();await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),saved.id);
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),saved);
 assert.equal(observations.consoleErrors.length,1);assert.match(observations.consoleErrors[0],/422/);
}));
for(const width of [1440,390])test(`UX03B-P05 native keyboard containment and error focus at ${width}`,async()=>fixture('wizard-keyboard-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await page.click('#newProject');await page.locator('#wizardNext').press('Enter');
 const m=await measure(page,'empty-error',observations,artifacts),input=m.controls.find(c=>c.id==='wizardName');
 assert(await page.locator('#wizardName').evaluate(e=>e===document.activeElement));assert(input.fullyVisible&&input.centerHit);assert.match(m.step,/1.*Zeitraum/);
 const tabStops=[];
 for(let n=0;n<12;n++){await page.keyboard.press('Tab');tabStops.push(await page.evaluate(()=>({id:document.activeElement.id,inside:document.getElementById('createProjectDialog').contains(document.activeElement)})));}
 assert(tabStops.every(s=>s.inside),'Tab must stay in the modal: '+JSON.stringify(tabStops));
 await page.keyboard.press('Escape');assert(await page.locator('#createProjectDialog').evaluate(d=>!d.open));assert(await page.locator('#newProject').evaluate(e=>e===document.activeElement));assert.deepEqual(observations.consoleErrors,[]);
}));
async function values(page){return page.locator('#createProjectDialog').evaluate(d=>[...d.querySelectorAll('input,select,textarea')].map(e=>({id:e.id,field:e.dataset.field||null,value:e.value,badInput:e.validity.badInput,checked:e.type==='checkbox'?e.checked:undefined})));}
for(const width of [1440,390])test(`UX03B-P04 hidden invalid rule preserves its original node and text and reveals settled focus at ${width}`,async()=>fixture('wizard-invalid-rule-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await shifts(page);await page.click('#wizardNext');
 await page.locator('#wizardRuleEditor > summary').click();await page.fill('#wizardMinRest','');await page.locator('#wizardMinRest').press('1');await page.locator('#wizardMinRest').press('e');
 assert.equal(await page.locator('#wizardMinRest').evaluate(e=>e.validity.badInput),true,'native unadmitted number text is present');
 await page.evaluate(()=>window.reviewRuleNode=document.getElementById('wizardMinRest'));
 await page.locator('#wizardRuleEditor > summary').click();const before=await values(page);
 await page.click('#wizardBack');await page.click('#wizardNext');assert.deepEqual(await values(page),before);
 await page.click('#wizardCancel');await page.click('#newProject');assert.deepEqual(await values(page),before);
 let posts=0;page.on('request',r=>{if(r.method()==='POST')posts++;});await page.click('#wizardCreate');await settle(page);
 const m=await measure(page,'invalid-rule',observations,artifacts),input=m.controls.find(c=>c.id==='wizardMinRest');
 assert(await page.locator('#wizardRuleEditor').evaluate(e=>e.open),'hidden invalid rule editor must open');
 assert(await page.locator('#wizardMinRest').evaluate(e=>e===window.reviewRuleNode&&e===document.activeElement&&e.validity.badInput),'original invalid node/text/focus');
 assert(input?.fullyVisible&&input.centerHit,'settled invalid field is visible and not behind actions');
 assert.deepEqual(await values(page),before);assert.equal(posts,0);assert.deepEqual(observations.consoleErrors,[]);
}));

for(const width of [1440,390])test(`UX03B-IR01 semantic template errors focus the concrete correction field at ${width}`,async()=>fixture('wizard-semantic-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});
 for(const scenario of ['blank-name','no-weekday','equal-times','minimum-over-maximum','zero-maximum']){
  await page.reload();await page.waitForFunction(()=>window.PlannerApp);await shifts(page);
  let target;
  if(scenario==='blank-name'){await page.locator('[data-field="name"]').fill('   ');target='[data-field="name"]';}
  if(scenario==='no-weekday'){for(let n=0;n<7;n++)await page.locator('[data-weekday="'+n+'"]').setChecked(false);target='[data-weekday="0"]';}
  if(scenario==='equal-times'){await page.locator('[data-field="end"]').fill('08:00');target='[data-field="end"]';}
  if(scenario==='minimum-over-maximum'){await page.locator('[data-field="minimum"]').fill('2');target='[data-field="maximum"]';}
  if(scenario==='zero-maximum'){await page.locator('[data-field="minimum"]').fill('0');await page.locator('[data-field="maximum"]').fill('0');target='[data-field="maximum"]';}
  const before=await values(page);let posts=0;const listener=r=>{if(r.method()==='POST')posts++;};page.on('request',listener);
  await page.click('#wizardNext');const m=await measure(page,'semantic-'+scenario,observations,artifacts);
  assert.match(m.step,/3.*Schichten/);assert.equal(posts,0);assert.deepEqual(await values(page),before);
  assert(await page.locator(target).evaluate(e=>e===document.activeElement),'semantic error must focus '+scenario+' field');
  const focused=await page.locator(target).getAttribute('aria-label');
  const control=m.controls.find(c=>focused?c.label===focused:c.label===(scenario==='blank-name'?'Bezeichnung':'Ende'));
  assert(control?.fullyVisible&&control.centerHit,'semantic correction field is settled, reachable and unoccluded: '+scenario);
  assert.equal(await page.locator(target).getAttribute('aria-invalid'),'true');page.off('request',listener);
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));

for(const width of [1440,390])test(`UX03B-IR02 function and template edits preserve existing native invalid demand at ${width}`,async()=>fixture('wizard-structural-draft-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await shifts(page);
 const minimum=()=>page.locator('[aria-label="Funktion A Minimum, Schichtvorlage 1"]');
 await minimum().fill('');await minimum().press('1');await minimum().press('e');
 await minimum().evaluate(e=>window.originalDemand=e);
 for(const positions of ['Funktion A\nFunktion B','Funktion B\nFunktion A','Funktion C\nFunktion A','Funktion A']){
  await page.click('#wizardBack');await page.fill('#wizardPositions',positions);await page.click('#wizardNext');
  assert(await minimum().evaluate(e=>e===window.originalDemand&&e.validity.badInput),'original native draft survives function edit: '+positions);
  assert.equal(await minimum().inputValue(),'');
 }
 await page.click('#wizardAddTemplate');
 assert(await minimum().evaluate(e=>e===window.originalDemand&&e.validity.badInput),'adding template preserves first draft');
 await page.getByRole('button',{name:'Schichtvorlage 2 entfernen',exact:true}).click();
 assert(await minimum().evaluate(e=>e===window.originalDemand&&e.validity.badInput),'removing another template preserves first draft');
 let posts=0;page.on('request',r=>{if(r.method()==='POST')posts++;});
 await page.click('#wizardNext');const m=await measure(page,'structural-invalid-demand',observations,artifacts);
 assert(await minimum().evaluate(e=>e===document.activeElement&&e.validity.badInput));
 const control=m.controls.find(c=>c.label==='Funktion A Minimum, Schichtvorlage 1');assert(control?.fullyVisible&&control.centerHit);assert.equal(posts,0);
 await minimum().press('End');await minimum().press('Backspace');assert.equal(await minimum().inputValue(),'1','recover the original native 1e, not a reconstructed empty value');
 assert.deepEqual(observations.consoleErrors,[]);
}));

test('UX03B-P03 every existing confirmation invalidation survives the four-step flow',async()=>fixture('wizard-invalidation',async(page,{observations})=>{
 await shifts(page);await page.click('#wizardNext');
 const flags=()=>page.evaluate(()=>['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'].map(id=>document.getElementById(id).checked));
 const confirm=async()=>{for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);};
 for(const [id,value] of [['wizardMinRest','12.5'],['wizardNightRest','13'],['wizardWorkDays','5'],['wizardNights','2'],['wizardDailyHours','10'],['wizardMaxWeeklyHours','40'],['wizardWeeklyRest','35']]){
  await confirm();await page.locator('#wizardRuleEditor > summary').click();await page.fill('#'+id,value);await page.locator('#wizardRuleEditor > summary').click();
  assert.deepEqual(await flags(),[false,true,false],id+' invalidates only rules and context');
 }
 for(const [id,value,back,approvals] of [['wizardPeople','Testperson A\nTestperson B\nTestperson C\nTestperson D',2,false],['wizardPositions','Funktion A\nFunktion B',2,false],['wizardStart','2026-10-04',3,true],['wizardEnd','2026-10-10',3,true],['wizardTimezone','Europe/Berlin',3,true]]){
  await confirm();for(let n=0;n<back;n++)await page.click('#wizardBack');await page.fill('#'+id,value);for(let n=0;n<back;n++)await page.click('#wizardNext');
  assert.deepEqual(await flags(),[true,approvals,false],id+' invalidation is preserved');
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));
for(const width of [1440,390])test(`UX03B-P05 Tab and Shift+Tab remain in every step at ${width}`,async()=>fixture('wizard-all-step-keyboard-'+width,async(page,{observations})=>{
 await page.setViewportSize({width,height:1000});await shifts(page);await page.click('#wizardBack');await page.click('#wizardBack');
 for(let step=0;step<4;step++){
  for(const key of ['Tab','Shift+Tab'])for(let n=0;n<25;n++){
   await page.keyboard.press(key);
   assert(await page.locator('#createProjectDialog').evaluate(d=>d.contains(document.activeElement)),key+' stays in step '+step);
  }
  if(step<3)await page.locator('#wizardNext').press('Enter');
 }
 await page.keyboard.press('Escape');assert(await page.locator('#newProject').evaluate(e=>e===document.activeElement));assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03B-P04 reordered demands and reindexed template removal keep their exact payload',async()=>fixture('wizard-reindex-payload',async(page,{observations})=>{
 await shifts(page);await page.click('#wizardBack');await page.fill('#wizardPositions','Funktion A\nFunktion B');await page.click('#wizardNext');
 await page.click('#wizardAddTemplate');const second=page.locator('.wizard-template').nth(1);await second.locator('[data-field="name"]').fill('Verbleibende Vorlage');
 for(const [name,min,max] of [['Funktion A','2','4'],['Funktion B','3','5']]){
  await page.getByRole('spinbutton',{name:name+' Maximum, Schichtvorlage 2',exact:true}).fill(max);
  await page.getByRole('spinbutton',{name:name+' Minimum, Schichtvorlage 2',exact:true}).fill(min);
 }
 await page.click('#wizardBack');await page.fill('#wizardPositions','Funktion B\nFunktion A');await page.click('#wizardNext');
 await page.getByRole('button',{name:'Schichtvorlage 1 entfernen',exact:true}).click();await page.click('#wizardAddTemplate');
 await page.getByRole('button',{name:'Schichtvorlage 2 entfernen',exact:true}).click();
 assert.equal(await page.locator('.wizard-template').count(),1);assert.equal(await page.locator('[data-field="name"]').inputValue(),'Verbleibende Vorlage');
 await page.click('#wizardNext');await page.check('#wizardRulesConfirmed');
 const request=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/api/projects/new'));
 const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/projects/new'));
 await page.click('#wizardCreate');const sent=(await request).postDataJSON();assert.equal((await response).status(),200);
 assert.deepEqual(sent.positions,[{name:'Funktion B'},{name:'Funktion A'}]);assert.deepEqual(sent.shift_templates[0].demands,[{position:0,minimum:3,maximum:5},{position:1,minimum:2,maximum:4}]);
 assert.equal(sent.shift_templates[0].name,'Verbleibende Vorlage');observations.request=sent;assert.deepEqual(observations.consoleErrors,[]);
}));
