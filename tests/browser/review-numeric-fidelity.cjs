'use strict';
// Real product HTTP + Chromium + independent Python JSON/SQLite oracle.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn,spawnSync}=require('node:child_process'),{chromium}=require('playwright');
const fixture=path.join(__dirname,'numeric_fixture.py');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function bounded(p,ms,label){let timer;try{return await Promise.race([p,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error(label+' timed out')),ms))]);}finally{clearTimeout(timer);}}
function python(mode,input,...args){const p=spawnSync(process.env.WEB_TEST_PYTHON||'python',[fixture,mode,...args],{env:{...process.env,TMPDIR:os.tmpdir()},input,encoding:'utf8',timeout:20000,maxBuffer:80*1024*1024});assert.equal(p.status,0,p.stderr);return p.stdout;}
function compare(source,output,keys=['metadata','opaque']){python('compare',JSON.stringify([{source,output,path:keys}]));}
async function withPage(run){
 const tmpdir=os.tmpdir(),state=fs.mkdtempSync(path.join(tmpdir,'numeric-fidelity-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',[fixture,'serve',state],{cwd:path.resolve(__dirname,'../..'),env:{...process.env,TMPDIR:tmpdir},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError,stopped=false;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',e=>{spawnError=e;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',d=>output=(output+d).slice(-16000));
 try{
  const base=await bounded((async()=>{while(!stopped){if(spawnError)throw spawnError;if(server.exitCode!==null||server.signalCode!==null)throw Error(output);const url=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];if(url){try{if((await fetch(url+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return url;}catch{}}await pause(50);}})(),15000,'startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run({page,base,state,db:()=>python('inspect',null,state)}),60000,'scenario');assert.deepEqual(errors,[]);
 }finally{
  stopped=true;
  try{if(browser)await bounded(browser.close(),5000,'browser shutdown');}
  finally{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'server shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'forced shutdown');}}
   fs.rmSync(state,{recursive:true,force:true});assert.equal(fs.existsSync(state),false);if(server.pid)assert.throws(()=>process.kill(server.pid,0),{code:'ESRCH'});
  }
 }
}


test('T09 real rejected file/editor/capability preserves drafts, durable bytes and queue',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 await page.evaluate(()=>openSavedProject('numeric-source'));const before=db();
 const initial=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 await page.evaluate(()=>{dirty=true;personDraft=true;jsonDirty=true;document.querySelector('#json').value='retained draft';});
 const invalid=(await source(page,base)).replace('9007199254740993','1e400');
 await page.locator('#file').setInputFiles({name:'unsupported.json',mimeType:'application/json',buffer:Buffer.from(invalid)});await idle(page);
 assert.equal(await page.locator('#file').evaluate(n=>n.files[0]?.name),'unsupported.json');
 await page.evaluate(text=>{document.querySelector('#json').value=text;document.querySelector('#applyJson').onclick();},invalid);await idle(page);
 assert.equal(await page.locator('#json').inputValue(),invalid);assert.equal(db(),before);
 assert.equal(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),initial);
 assert.deepEqual(await page.evaluate(()=>({dirty,jsonDirty,personDraft,revision:snapshot.revision})),{dirty:true,jsonDirty:true,personDraft:true,revision:'1'});
 const count=[];page.on('request',r=>{if(r.requestMethod==='PUT'||r.method()==='PUT')count.push(r);});
 await page.evaluate(async()=>{window.savedRaw=JSON.rawJSON;JSON.rawJSON=undefined;try{await api('/api/snapshots','PUT',currentSnapshot());}catch(e){notice(e.message,true);}finally{JSON.rawJSON=window.savedRaw;}});
 assert.equal(count.length,0);assert.match(await page.locator('#notice').textContent(),/Browser/);assert.equal(await page.locator('#notice').getAttribute('role'),'status');assert((await page.locator('#notice').textContent()).length<300);assert.equal(db(),before);
}));

test('T10 canonical 16MiB metadata boundary replays, first excess rejects, envelopes are not snapshots',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 const raw=python('boundary',null,'0'),over=python('boundary',null,'1');assert.equal(Buffer.byteLength(raw),16*1024*1024);assert.equal(Buffer.byteLength(over),16*1024*1024+1);
 const before=db(),accepted=await page.request.post(base+'/api/snapshots/check',{data:raw,headers:{'Content-Type':'application/json'}});assert.equal(accepted.status(),200);assert.equal(Buffer.byteLength(await accepted.text()),16*1024*1024);
 const compact=await page.evaluate(raw=>ProjectJSON.stringify(ProjectJSON.parse(raw)),raw);assert(Buffer.byteLength(compact)<=Buffer.byteLength(raw));compare(raw,compact);
 const replay=await page.request.post(base+'/api/snapshots/check',{data:compact,headers:{'Content-Type':'application/json'}});assert.equal(replay.status(),200);compare(raw,await replay.text());
 const rejected=await page.request.post(base+'/api/snapshots/check',{data:over,headers:{'Content-Type':'application/json'}});assert.equal(rejected.status(),413);assert.equal(db(),before);
 // Explicit synthetic response-envelope seam; no universal response-byte cap.
 await page.route('**/numeric-envelope',route=>route.fulfill({status:200,contentType:'application/json',body:'{"snapshot":'+raw+'}'}));
 const bytes=await page.evaluate(async()=>ProjectJSON.stringify((await api('/numeric-envelope')).snapshot).length);assert(bytes>1000000);
}));



test('T07 real readiness, validation, replacement, approval and export send exact snapshots',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 const raw=await source(page,base);await page.evaluate(()=>openSavedProject('numeric-source'));const before=db(),requests=[];
 page.on('request',r=>{if(r.method()==='POST')requests.push({path:new URL(r.url()).pathname,body:r.postData()});});
 await page.evaluate(async()=>{
  assignments=[{employee_id:'p',demand_id:'d',segments:[]}];invalidateResult();
  renderSetupReview();await [...document.querySelectorAll('#setupReview button')].find(b=>b.textContent==='Planungsbereitschaft prüfen').onclick();
  activePanel='plan';refreshAutomaticReadiness(true);
  await document.querySelector('#validate').onclick();
  renderReplacementForm();await document.querySelector('#findReplacement').onclick();
  renderApprovalLeverage();await [...document.querySelectorAll('#approvalLeverage button')].find(b=>b.textContent==='Vorschau berechnen').onclick();
 });
 const download=page.waitForEvent('download');await page.evaluate(()=>document.querySelector('[data-export="csv"]').onclick());const file=await download;assert(fs.statSync(await file.path()).size>0);
 for(const endpoint of ['/api/readiness','/api/validate','/api/replacement','/api/approval-leverage','/api/export/csv']){
  const sent=requests.find(r=>r.path===endpoint);assert(sent,'missing original handler request '+endpoint);
  python('compare',JSON.stringify([{source:endpoint==='/api/readiness'?raw:'{"snapshot":'+raw+'}',output:sent.body,path:endpoint==='/api/readiness'?['metadata','opaque']:['snapshot','metadata','opaque']}]));
 }
 assert.equal(db(),before,'analysis/export never writes or queues');
}));



async function fillNumericWizard(page){
 await page.evaluate(()=>navigate('projects'));
 await page.click('#newProject');await page.fill('#wizardName','Synthetic retained wizard');await page.fill('#wizardStart','2026-01-05');await page.fill('#wizardEnd','2026-01-05');await page.fill('#wizardTimezone','UTC');await page.click('#wizardNext');await page.fill('#wizardPeople','Synthetic Ada; 40; 100');await page.click('#wizardNext');await page.check('#wizardRulesConfirmed');
}
for(const failure of ['capability','decode','changed'])test('T09 wizard '+failure+' keeps dialog, input, incumbent and durable state',{timeout:90000},async()=>withPage(async({page,db})=>{
 await page.evaluate(()=>openSavedProject('numeric-source'));await fillNumericWizard(page);const before=db();
 let release,notify;const arrival=new Promise(r=>notify=r),hold=new Promise(r=>release=r);let writes=0;
 page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/projects/new'))writes++;});
 if(failure!=='capability')await page.route('**/api/projects/new',async route=>{const response=await route.fetch();notify();await bounded(hold,10000,'wizard gate');await route.fulfill({response,body:failure==='decode'?'{"snapshot":{"invalid":1e400}}':await response.text()});});
 if(failure==='capability')await page.evaluate(()=>{window.originalRaw=JSON.rawJSON;JSON.rawJSON=undefined;});
 try{
  await page.click('#wizardCreate');
  if(failure!=='capability'){await bounded(arrival,10000,'wizard request');if(failure==='changed')await page.evaluate(()=>{snapshot.employees[0].name='Later local edit';dirty=true;personDraft=true;jsonDirty=true;document.querySelector('#json').value='later text';});release();}
  await page.waitForFunction(()=>!document.querySelector('#createProjectForm').hasAttribute('aria-busy'));
  assert(await page.locator('#createProjectDialog').evaluate(n=>n.open));assert.equal(await page.locator('#wizardName').inputValue(),'Synthetic retained wizard');assert.equal(await page.locator('#wizardPeople').inputValue(),'Synthetic Ada; 40; 100');
  assert.match(await page.locator('#wizardError').textContent(),failure==='changed'?/geändert/:/JSON|Browser/);assert.equal(await page.locator('#wizardError').getAttribute('role'),'alert');
  assert.equal(await page.evaluate(()=>snapshot.id),'numeric-source');assert.equal(db(),before);
  if(failure==='capability')assert.equal(writes,0);
  if(failure==='changed')assert.deepEqual(await page.evaluate(()=>({dirty,jsonDirty,personDraft,name:snapshot.employees[0].name,text:document.querySelector('#json').value})),{dirty:true,jsonDirty:true,personDraft:true,name:'Later local edit',text:'later text'});
 }finally{release();if(failure==='capability')await page.evaluate(()=>JSON.rawJSON=window.originalRaw);}
}));
for(const order of ['edit-before-response','edit-after-response'])test('T05 T07 numeric Save '+order+' preserves edits, deletes, reordering and reopen',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 const raw=await source(page,base),expected=python('edit',raw);await page.evaluate(()=>openSavedProject('numeric-source'));
 let release,notify,captured;const arrival=new Promise(r=>notify=r),hold=new Promise(r=>release=r);
 await page.route('**/api/snapshots',async route=>{if(route.request().method()!=='PUT')return route.continue();captured=route.request().postData();const response=await route.fetch();notify();await bounded(hold,10000,'save gate');await route.fulfill({response});});
 const edit=()=>page.evaluate(()=>{snapshot.metadata.opaque.integer=BigInt('9007199254740995');snapshot.metadata.opaque.rows.reverse();delete snapshot.metadata.opaque.numeric_string;snapshot.employees[0].name='Synthetic edited';invalidateResult();});
 try{
  await page.click('#headerSave');await bounded(arrival,10000,'save arrival');compare(raw,captured);
  if(order==='edit-before-response')await edit();release();await idle(page);if(order==='edit-after-response')await edit();
  assert.equal(await page.evaluate(()=>dirty),true);assert.equal(await page.evaluate(()=>snapshot.revision),'2');
  compare(expected,await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())));
  await page.unroute('**/api/snapshots');await page.click('#headerSave');await idle(page);
  const row=JSON.parse(db()).snapshots.find(row=>row.id==='numeric-source');assert.equal(row.revision,3);compare(expected,row.payload);assert.equal(JSON.parse(row.payload).employees[0].name,'Synthetic edited');
  await page.evaluate(()=>openSavedProject('numeric-source'));compare(expected,await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())));assert.equal(await page.evaluate(()=>dirty),false);
 }finally{release();}
}));

async function source(page,base){const r=await page.request.get(base+'/api/snapshots/numeric-source');assert.equal(r.status(),200);return r.text();}
async function idle(page){await page.waitForFunction(()=>!projectSwitchBusy());}

test('T01 real copy Open/check/Save SQLite preserves numeric type/value and float sign',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 const raw=await source(page,base);assert.match(raw,/"integer":9007199254740993/);
 const copied=await page.request.post(base+'/api/snapshots/numeric-source/copy',{data:{revision:'1'}});assert.equal(copied.status(),200);
 const copyText=await copied.text(),id=JSON.parse(copyText).id;compare(raw,copyText);const before=db();
 await page.evaluate(()=>saved());
 const checkWait=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check'));
 await page.locator('[data-project-id="'+id+'"]').click();const checked=await checkWait;assert.equal(checked.status(),200);await idle(page);
 compare(raw,checked.request().postData());compare(raw,await checked.text());assert.equal(db(),before,'Open must not write');
 const saving=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');await page.click('#headerSave');const saved=await saving;assert.equal(saved.status(),200);await idle(page);
 const read=await page.request.get(base+'/api/snapshots/'+id);compare(raw,await read.text());
 const row=JSON.parse(db()).snapshots.find(row=>row.id===id);assert.equal(row.revision,2);compare(raw,row.payload);
 assert.deepEqual(await page.evaluate(()=>({dirty,jsonDirty,revision:snapshot.revision})),{dirty:false,jsonDirty:false,revision:'2'});
}));

test('T04 T06 file/editor retain floats for real strict backend rejection and exact backup',{timeout:90000},async()=>withPage(async({page,base,db})=>{
 const raw=await source(page,base);const before=db();
 await page.locator('#file').setInputFiles({name:'numeric.json',mimeType:'application/json',buffer:Buffer.from(raw)});await idle(page);
 assert.equal(await page.evaluate(()=>snapshot?.id),'numeric-source');
 await page.evaluate(()=>syncJson(true));compare(raw,await page.locator('#json').inputValue());
 const download=page.waitForEvent('download');await page.click('#backup');const backup=await download;compare(raw,fs.readFileSync(await backup.path(),'utf8'));
 for(const kind of ['weekly','minimum'])for(const ingress of ['file','editor']){
  const text=python('strict',raw,kind),direct=await page.request.post(base+'/api/snapshots/check',{data:text,headers:{'Content-Type':'application/json'}});assert.equal(direct.status(),422,'direct API negative control');
  const valid=text.replace(kind==='weekly'?'\"contractual_weekly_minutes\": 60.0':'\"minimum_days\": 2.0',kind==='weekly'?'\"contractual_weekly_minutes\": 60':'\"minimum_days\": 2');
  assert.equal((await page.request.post(base+'/api/snapshots/check',{data:valid,headers:{'Content-Type':'application/json'}})).status(),200,'the corresponding strict integer is accepted');
  const checked=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check'));
  if(ingress==='file')await page.locator('#file').setInputFiles({name:'invalid-'+kind+'.json',mimeType:'application/json',buffer:Buffer.from(text)});
  else await page.evaluate(text=>{document.querySelector('#json').value=text;document.querySelector('#json').oninput();document.querySelector('#applyJson').onclick();},text);
  const response=await checked;assert.equal(response.status(),422,'UI may not normalize strict floats to integers');await idle(page);
  compare(text,response.request().postData(),[]);assert.equal(db(),before);assert.equal(await page.evaluate(()=>snapshot.revision),'1');
  if(ingress==='editor')assert.equal(await page.locator('#json').inputValue(),text);
 }
}));

test('T06 T11 real wizard direct response and demo retain canonical numeric semantics',{timeout:90000},async()=>withPage(async({page,base})=>{
 const asset=await page.request.get(base+'/static/project-json.js');assert.equal(asset.status(),200);assert.match(await asset.text(),/ProjectJSON/);
 let delivered;
 // Explicit response-injection seam for the wizard's otherwise numeric-small output.
 await page.route('**/api/projects/new',async route=>{const r=await route.fetch();delivered=(await r.text()).replace('\"metadata\":{','\"metadata\":{\"numeric_probe\":9007199254740993,\"float_probe\":-0.0,');await route.fulfill({response:r,body:delivered});});
 await page.click('#newProject');await page.fill('#wizardName','Synthetic numeric wizard');await page.fill('#wizardStart','2026-01-05');await page.fill('#wizardEnd','2026-01-05');await page.fill('#wizardTimezone','UTC');await page.click('#wizardNext');await page.fill('#wizardPeople','Synthetic Ada; 40; 100');await page.click('#wizardNext');await page.check('#wizardRulesConfirmed');
 const created=page.waitForResponse(r=>r.url().endsWith('/api/projects/new')),checked=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check'));await page.click('#wizardCreate');
 const response=await created;assert.equal(response.status(),200);const wire=await response.text(),check=await checked;assert.equal(check.status(),200);
 python('compare',JSON.stringify([{source:wire,output:'{"snapshot":'+check.request().postData()+'}',path:['snapshot']}]));
 await page.waitForFunction(()=>!document.querySelector('#createProjectDialog').open);
 const demo=await page.request.get(base+'/api/demo');assert.equal(demo.status(),200);const demoWire=await demo.text();
 await page.evaluate(async()=>{load(await api('/api/demo'));syncJson(true);});
 // IDs/timestamps are produced on each request; compare the stable numeric metadata.
 compare(demoWire,await page.locator('#json').inputValue(),['metadata']);
}));

test('T12 numeric fixture propagates Node temp root without parent TMPDIR',{timeout:90000},async()=>{
 const keys=['TMPDIR','TMP','TEMP'],values=()=>keys.map(key=>process.env[key]),original=values();
 // Allocate under the original configured root before changing any temp hint.
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'numeric-temp-contract-'));
 const tmp=path.join(root,'tmp-choice'),temp=path.join(root,'temp-choice'),outside=path.join(root,'tmp-choice-sibling');
 let fixtureState;
 try{
  for(const dir of [tmp,temp,outside])fs.mkdirSync(dir);
  const sentinel=path.join(outside,'planning.sqlite3'),bytes=Buffer.from('synthetic sentinel: never open as SQLite\n');
  fs.writeFileSync(sentinel,bytes,{flag:'wx'});
  const stamp=()=>{const s=fs.statSync(sentinel);return [s.dev,s.ino,s.size,s.mtimeMs,s.ctimeMs];},before=stamp();
  const escape=path.join(tmp,'escape');fs.symlinkSync(outside,escape,'dir');
  delete process.env.TMPDIR;process.env.TMP=tmp;process.env.TEMP=temp;
  const missing=[undefined,tmp,temp];assert.deepEqual(values(),missing);
  assert.equal(os.tmpdir(),tmp,'Node selects TMP before the conflicting TEMP on this POSIX fixture');
  await withPage(async({page,base,state,db})=>{
   fixtureState=state;assert.equal(fs.realpathSync(path.dirname(state)),fs.realpathSync(tmp));
   assert.deepEqual(values(),missing,'serve must not mutate the parent environment');
   const raw=await source(page,base);assert.match(raw,/"integer":9007199254740993/);
   assert(fs.statSync(path.join(state,'planning.sqlite3')).isFile());
   const stored=db(),rows=JSON.parse(stored).snapshots;assert.equal(rows.length,1);assert.equal(rows[0].id,'numeric-source');assert.equal(rows[0].revision,1);
   compare(raw,rows[0].payload);
   compare(raw,await page.evaluate(raw=>ProjectJSON.stringify(ProjectJSON.parse(raw)),raw));
   assert.equal(db(),stored);assert.deepEqual(values(),missing,'inspect/oracle must not mutate the parent environment');
   // Both entry points must reject a real sibling and a symlink escape at the
   // unchanged confinement assertion, before opening any synthetic DB sentinel.
   for(const candidate of [outside,escape])for(const mode of ['serve','inspect']){
    const rejected=spawnSync(process.env.WEB_TEST_PYTHON||'python',[fixture,mode,candidate],{env:{...process.env,TMPDIR:os.tmpdir()},encoding:'utf8',timeout:10000});
    assert.equal(rejected.error,undefined);assert.equal(rejected.signal,null);assert.equal(rejected.status,1,rejected.stderr);
    assert.match(rejected.stderr,/assert state\.is_relative_to\(Path\(os\.environ\['TMPDIR'\]\)\.resolve\(\)\)/);
    assert.match(rejected.stderr,/AssertionError/);assert.equal(rejected.stdout,'');
    assert.deepEqual(fs.readFileSync(sentinel),bytes);assert.deepEqual(stamp(),before);
    assert.deepEqual(fs.readdirSync(outside),['planning.sqlite3']);
   }
   assert.equal(db(),stored);assert.deepEqual(values(),missing);
  });
  assert.equal(fs.existsSync(fixtureState),false);assert.deepEqual(fs.readdirSync(temp),[]);
  assert.deepEqual(values(),missing);
 }finally{
  for(let i=0;i<keys.length;i++){if(original[i]===undefined)delete process.env[keys[i]];else process.env[keys[i]]=original[i];}
  fs.rmSync(root,{recursive:true,force:true});assert.equal(fs.existsSync(root),false);assert.deepEqual(values(),original);
 }
});
