'use strict';
// UX-03A: actual Chromium layout/resources against an isolated synthetic store.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function fixture(name,run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-team-first-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 const observations={consoleErrors:[],pageErrors:[]};
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
  const page=await browser.newPage({baseURL:base,viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);
  page.on('pageerror',error=>observations.pageErrors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')observations.consoleErrors.push(message.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  const response=await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  observations.csp=response.headers()['content-security-policy'];
  await bounded(run(page,{base,observations,artifacts}),60000,'Navigation scenario');
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
async function createTeam(page){
 await page.click('#newProject');await page.fill('#wizardName','Synthetisches Team Oktober');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 await page.click('#wizardNext'); // Separate rule review after shifts.
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
}
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(150);}
async function measureTeam(page){return page.evaluate(()=>{
 const modal=document.querySelector('dialog[open]');
 const visible=e=>{
  if(modal&&!modal.contains(e))return false;
  if(e.closest('[hidden]')||!e.getClientRects().length||getComputedStyle(e).visibility==='hidden')return false;
  for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS'&&!p.open&&!p.querySelector(':scope > summary')?.contains(e))return false;
  const r=e.getBoundingClientRect();return r.width>1&&r.height>1;
 };
 const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
 const viewport=r=>r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;
 const geometry=e=>{
  const r=rect(e),clips=[];
  for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),b=p.getBoundingClientRect();if(/auto|scroll|hidden|clip/.test(s.overflowX+s.overflowY))clips.push({id:p.id,className:p.className,x:!(/auto|scroll|hidden|clip/.test(s.overflowX))||(r.left>=b.left&&r.right<=b.left+p.clientWidth),y:!(/auto|scroll|hidden|clip/.test(s.overflowY))||(r.top>=b.top&&r.bottom<=b.top+p.clientHeight)});}
  const hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2),header=document.querySelector('.topbar').getBoundingClientRect();
  return {...r,visible:visible(e),inViewport:viewport(r),clips,belowHeader:r.top>=Math.max(0,header.bottom),uncovered:hit===e||e.contains(hit)};
 };
 const row=document.querySelector('#people tbody tr');
 return {width:innerWidth,height:innerHeight,scrollY,documentWidth:document.documentElement.scrollWidth,
  controls:[...document.querySelectorAll('button,input,select,textarea,summary,a[href]')].filter(visible).map(e=>({id:e.id,tag:e.tagName,label:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.textContent.trim(),...rect(e),inViewport:viewport(rect(e))})),
  first:row?{name:geometry(row.cells[0]),planning:geometry(row.querySelector('[data-employee-planning]')),hours:geometry(row.querySelector('[data-employee-hours]'))}:null};
 });}
test('UX03A first people task is visible without group or approval detours',async()=>fixture('team-first',async(page,{observations,artifacts})=>{
 await createTeam(page);observations.viewports=[];
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:1000});await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);});await settle(page);
  const m=await measureTeam(page);observations.viewports.push(m);
  if(artifacts)await page.screenshot({path:path.join(artifacts,'team-first-'+width+'.png')});
 }
 for(const m of observations.viewports){
  assert.equal(m.documentWidth,m.width,'no document overflow at '+m.width);
  assert(m.controls.length<=30,`initial layout-visible control budget 30, got ${m.controls.length} at ${m.width}`);
  if(m.width===320)continue;
  assert.equal(m.scrollY,0,'no scrolling before the first task');
  for(const [name,r] of Object.entries(m.first))assert(r.visible&&r.inViewport&&r.belowHeader&&r.uncovered&&r.clips.every(c=>c.x&&c.y),`${name} must be fully visible/hit-testable at ${m.width}: ${JSON.stringify(r)}`);
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));

test('UX03A frequent labels stay on one readable line',async()=>fixture('team-labels',async(page,{observations,artifacts})=>{
 await createTeam(page);observations.labels=[];
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});await settle(page);
  const labels=await page.locator('#people th:nth-child(2),#people tbody tr:first-child button').evaluateAll(nodes=>nodes.map(e=>{const range=document.createRange();range.selectNodeContents(e);return {text:e.textContent,lines:[...new Set([...range.getClientRects()].map(r=>r.top))].length};}));
  observations.labels.push({width,labels});if(artifacts)await page.screenshot({path:path.join(artifacts,'team-labels-'+width+'.png')});
  for(const label of labels)assert.equal(label.lines,1,'do not wrap one trailing character: '+JSON.stringify({width,label}));
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));
async function assertFocused(page,selector){
 await settle(page);const m=await page.locator(selector).evaluate(e=>{
  const r=e.getBoundingClientRect(),h=document.querySelector('.topbar').getBoundingClientRect(),hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);
  return {focused:document.activeElement===e,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,headerBottom:h.bottom,hit:hit===e||e.contains(hit)};
 });assert(m.focused&&m.hit&&m.left>=0&&m.right<=m.width&&m.top>=Math.max(0,m.headerBottom)&&m.bottom<=m.height,JSON.stringify(m));return m;
}
for(const width of [1440,390])test(`UX03A correction links reveal the intended team view with settled focus at ${width}`,async()=>fixture('team-corrections-'+width,async(page,{observations})=>{
 await page.setViewportSize({width,height:1000});await createTeam(page);await saveTeam(page);
 await page.locator('[data-team-to="approvals"]').click();
 await page.evaluate(()=>{navigate('plan');renderValidation({valid:false,complete:false,diagnostics:[{code:'approval',message:'Synthetische Freigabenprüfung',employee_id:snapshot.employees[0].id}]});document.getElementById('validationDetails').open=true;});
 const before=await wireState(page);
 await page.getByRole('button',{name:'Person bearbeiten',exact:true}).press('Enter');
 assert(await page.locator('#details input').first().isVisible(),'person correction reveals people instead of remaining in approvals');
 observations.person=await assertFocused(page,'#details > .grid > label:first-child input');
 await page.locator('#details input').first().press('Escape');
 assert.equal(await page.locator('#details input').count(),0,'Escape closes the personal editor');
 observations.returnFocus=await assertFocused(page,'#people tbody tr:first-child button');
 assert.deepEqual(await wireState(page),before);
 await page.evaluate(()=>{navigate('plan');renderValidation({valid:false,complete:false,diagnostics:[{code:'candidate_shortage',message:'Synthetischer Engpass',demand_id:snapshot.demands[0].id}]});document.getElementById('validationDetails').open=true;});
 await page.getByRole('button',{name:'Freigaben öffnen',exact:true}).first().press('Enter');
 assert(await page.locator('#matrix').isVisible(),'shortage correction reveals approval matrix');
 observations.approvals=await assertFocused(page,'#matrixSearch');
 assert.deepEqual(await wireState(page),before);assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03A another opened project resets the local view to people',async()=>fixture('team-project-reset',async(page)=>{
 await createTeam(page);await page.locator('[data-team-to="approvals"]').click();
 await page.evaluate(async()=>load(await api('/api/demo')));
 assert(await page.locator('#people').isVisible(),'new project starts at people, not the previous matrix');
}));

test('UX03A pending save locks original people and group handlers and preserves the sent wire',async()=>fixture('team-save-race',async(page,{base,observations})=>{
 await createTeam(page);await saveTeam(page);
 const original=await page.evaluate(()=>currentSnapshot()),hours=page.locator('#people [data-employee-hours]').first();
 await hours.fill('32');await hours.press('Tab');const before=await wireState(page),sent=await page.evaluate(()=>currentSnapshot());
 let release,seen,finished;const held=new Promise(r=>release=r),arrival=new Promise(r=>seen=r),done=new Promise(r=>finished=r);let failure,payload;
 await page.route('**/api/snapshots',async route=>{
  if(route.request().method()!=='PUT')return route.fallback();
  try{payload=route.request().postDataJSON();seen();await bounded(held,10000,'Synthetic team save delay');await route.continue();}catch(e){failure=e;try{await route.abort();}catch{}}finally{finished();}
 },{times:1});
 try{
  await page.click('#headerSave');await bounded(arrival,10000,'Save arrival');
  await page.waitForFunction(()=>document.getElementById('headerSave').disabled&&document.getElementById('people').inert&&document.getElementById('teamScope').inert);
  await page.locator('[data-team-to="approvals"]').press('Enter');await page.locator('[data-team-to="people"]').press('Enter');
  await page.evaluate(async()=>{
   const input=document.querySelector('#people [data-employee-hours]'),text=input.value;input.value='999';input.onchange();input.value=text;
   const planning=document.querySelector('#people [data-employee-planning]'),checked=planning.checked;planning.checked=!checked;planning.onchange();planning.checked=checked;
   await document.getElementById('addPerson').onclick();
   await [...document.querySelectorAll('#teamScope button')].find(b=>b.textContent==='Alle Grenzen aufheben').onclick();
  });
  assert.deepEqual(await wireState(page),before,'whole original handlers reject overlapping mutations');assert.deepEqual(payload,sent);
  assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+sent.id)).json(),original,'write remains held');
 }finally{release();await bounded(done,10000,'Owned route drain');if(failure)throw failure;}
 await page.waitForFunction(()=>!projectSwitchBusy()&&!dirty);
 const stored=await(await page.request.get(base+'/api/snapshots/'+sent.id)).json();sent.revision=stored.revision;assert.deepEqual(stored,sent);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored);
 observations.delay='synthetic pre-write PUT delay';observations.sent=payload;observations.stored=stored;assert.deepEqual(observations.consoleErrors,[]);
}));
for(const width of [1440,390])for(const action of ['save','solve'])test(`UX03A hidden absence draft is revealed unchanged by ${action} at ${width}`,async()=>fixture(`team-hidden-draft-${action}-${width}`,async(page,{base,observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await createTeam(page);await saveTeam(page);
 const baseline=await page.evaluate(()=>currentSnapshot()),writes=[];
 page.on('request',r=>{if(r.method()==='PUT'||(r.method()==='POST'&&r.url().endsWith('/api/jobs')))writes.push(r.url());});
 await page.locator('#people tbody tr:first-child button').click();await page.getByRole('button',{name:'Abwesenheit hinzufügen',exact:true}).click();
 const draft=page.getByLabel('Abwesend ab',{exact:true});await draft.fill('2026-10-06T01:23');
 await page.evaluate(()=>window.reviewDraft=document.querySelector('#details input[type=datetime-local]'));
 const before=await wireState(page);await page.locator('[data-team-to="approvals"]').click();
 if(action==='save')await page.click('#headerSave');else{await page.locator('.main-nav [data-navigate="plan"]').click();await page.click('#solve');}
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 observations.result=await page.evaluate(()=>({hidden:document.getElementById('teamPeople').hidden,sameNode:window.reviewDraft===document.querySelector('#details input[type=datetime-local]'),raw:window.reviewDraft.value,notice:document.getElementById('notice').textContent,personDraft}));
 if(artifacts)await page.screenshot({path:path.join(artifacts,`hidden-draft-${action}-${width}.png`)});
 assert.equal(observations.result.hidden,false,'save/solve error reveals the existing absence draft');
 assert(observations.result.sameNode);assert.equal(observations.result.raw,'2026-10-06T01:23');assert(observations.result.personDraft);
 observations.focus=await assertFocused(page,'#details input[type=datetime-local] >> nth=0');
 assert.deepEqual(await wireState(page),before);assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+baseline.id)).json(),baseline);
 assert.deepEqual(writes,[]);assert.deepEqual(observations.consoleErrors,[]);
}));
async function wireState(page){return page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,jsonDirty,changeVersion,personDraft}));}
async function saveTeam(page){
 await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
}
test('UX03A local views and groups preserve exact data and raw nodes; Soll saves and reopens',async()=>fixture('team-data',async(page,{base,observations})=>{
 await createTeam(page);await saveTeam(page);
 const baseline=await page.evaluate(()=>currentSnapshot());
 const backend=await(await page.request.get(base+'/api/snapshots/'+baseline.id)).json();assert.deepEqual(backend,baseline);
 const list=await(await page.request.get(base+'/api/snapshots')).json(),before=await wireState(page),writes=[];
 page.on('request',r=>{if(['PUT','DELETE'].includes(r.method())||r.url().endsWith('/api/jobs'))writes.push(r.url());});
 const hours=page.locator('#people [data-employee-hours]').first();
 // Detached from model by design: this is an actual unadmitted search draft.
 await page.locator('#people input[type=search]').fill('Test');
 await page.waitForFunction(()=>pageState('people').query==='Test');
 await hours.fill('-1');await hours.press('Tab');
 const edited=await wireState(page);
 await page.evaluate(()=>window.teamRawNode=document.querySelector('#people [data-employee-hours]'));
 for(const key of ['approvals','people'])await page.locator(`[data-team-to="${key}"]`).press('Enter');
 assert(await hours.evaluate(e=>e===window.teamRawNode));assert.equal(await hours.inputValue(),'-1');
 await page.locator('#teamTools > summary').press('Enter');
 await page.locator('#teamTools select').first().selectOption({index:1});
 await page.locator('#teamTools > summary').press('Enter');
 assert.deepEqual(await wireState(page),edited,'disclosures and group choice do not admit project changes');
 assert.equal(await page.locator('#teamTools').evaluate(e=>e.open),false);
 assert.deepEqual(writes,[]);assert.deepEqual(await(await page.request.get(base+'/api/snapshots')).json(),list);assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+baseline.id)).json(),baseline);
 await page.locator('[data-team-to="approvals"]').press('Enter');await page.click('#headerSave');
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 assert(await hours.isVisible(),'save reveals the actual invalid person field from Freigaben');
 assert(await hours.evaluate(e=>e===document.activeElement&&e===window.teamRawNode),'focus original node after unlock');
 assert.deepEqual(writes,[],'invalid input never writes');
 await hours.fill('32');await hours.press('Tab');
 const expected=structuredClone(baseline);expected.employees[0].target_minutes=1920;
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),expected,'only first Soll changes');
 await saveTeam(page);
 const stored=await(await page.request.get(base+'/api/snapshots/'+baseline.id)).json();expected.revision=stored.revision;assert.deepEqual(stored,expected);
 await page.locator('[data-team-to="approvals"]').press('Enter');await page.reload();
 await page.locator(`.project-card[data-project-id="${baseline.id}"]`).click();await page.waitForFunction(id=>snapshot?.id===id,baseline.id);
 await page.locator('.main-nav [data-navigate="team"]').click();
 assert.equal(await page.locator('[data-team-to="people"]').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#people [data-employee-hours]').first().inputValue(),'32');
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored);assert.equal(await page.evaluate(()=>dirty),false);
 observations.exactPersisted=stored;observations.initial=before;assert.deepEqual(observations.consoleErrors,[]);
}));
