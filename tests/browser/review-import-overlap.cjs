'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {fixture,state:baseState,persisted,settle,visibleFeedback,bounded,teams,assertTypedEqual}=require('./import-fixture.cjs');
async function state(page){return {...await baseState(page),...await page.evaluate(()=>({draftVersion,nativeDraftCount:nativeDrafts.size}))};}
for(const owner of ['import','file','save'])for(const first of ['inspect','owner'])test(`A04 genuine inspect then ${owner}; ${first} response delivered first`,async()=>fixture(`overlap-${owner}-${first}`,async(page,{base,observations})=>{
 await page.click('#demo');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const id=await page.evaluate(()=>snapshot.id),candidate=JSON.parse(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())));candidate.id='synthetic-overlap-'+owner+'-'+first;candidate.revision='0';
 await page.click('.main-nav [data-navigate="projects"]');await teams(page);
 const before=await state(page),backend=await persisted(page,base,id),requests=[];page.on('request',r=>{if(['POST','PUT'].includes(r.method())&&!r.url().endsWith('/api/readiness'))requests.push({url:new URL(r.url()).pathname,method:r.method()});});
 const responseTasks=[];page.on('response',r=>{if(['POST','PUT'].includes(r.request().method())&&['/api/snapshots/check','/api/snapshots'].includes(new URL(r.url()).pathname))responseTasks.push(r.text().then(raw=>({path:new URL(r.url()).pathname,method:r.request().method(),status:r.status(),raw})));});
 const rawBackendBefore={list:await(await page.request.get('/api/snapshots')).text(),detail:await(await page.request.get('/api/snapshots/'+id)).text()};
 const holds={};const failures=[];
 async function hold(name,pattern,method){let release,arrive,finish;const ready=new Promise(r=>arrive=r),gate=new Promise(r=>release=r),done=new Promise(r=>finish=r);const h=async route=>{if(route.request().method()!==method)return route.fallback();try{const response=await route.fetch();assert.equal(response.status(),200);holds[name].responseText=await response.text();arrive();await bounded(gate,12000,'response release '+name);await route.fulfill({response});}catch(e){failures.push(e);try{await route.abort();}catch{}}finally{finish();}};holds[name]={ready,release,done,h,pattern};await page.route(pattern,h);}
 await hold('inspect','**/api/remote-source','GET');await hold('owner',owner==='import'?'**/api/remote-import':owner==='file'?'**/api/snapshots/check':'**/api/snapshots',owner==='save'?'PUT':'POST');
 try{
  await page.click('#inspect');await bounded(holds.inspect.ready,5000,'real inspect response');assert(await page.locator('#inspect').isDisabled());assert.equal(await page.evaluate(()=>projectSwitchBusy()),false);
  if(owner==='file')await page.locator('#file').setInputFiles({name:'synthetic-overlap.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(candidate))});else await page.click(owner==='save'?'#headerSave':'#import');
  await bounded(holds.owner.ready,5000,'real owner response');await page.waitForFunction(()=>$('file').disabled&&$('import').disabled&&$('save').disabled);await settle(page);
  assert.deepEqual(await state(page),before,'pending real responses do not mutate canonical state');
  // Both HTTP responses exist and are held; unlike rejected mutex activation this is genuine overlap.
  observations.bothResponsesHeld=true;observations.backendWhileHeld=await persisted(page,base,id);
  holds[first].release();await bounded(holds[first].done,5000,'first callback');
  if(first==='inspect'){
   await page.waitForFunction(()=>!$('inspect').dataset.busy);await settle(page);assert(await page.evaluate(()=>projectSwitchBusy()));for(const c of ['file','import','save'])assert(await page.locator('#'+c).isDisabled());assert.deepEqual(await state(page),before);
  }else{
   await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);assert(await page.locator('#inspect').isDisabled());for(const c of ['file','import','save'])assert.equal(await page.locator('#'+c).isDisabled(),false);
  }
  const other=first==='inspect'?'owner':'inspect';holds[other].release();await bounded(holds[other].done,5000,'second callback');await page.waitForFunction(()=>!projectSwitchBusy()&&!$('inspect').dataset.busy);await settle(page);
  for(const c of ['file','import','save','inspect'])assert.equal(await page.locator('#'+c).isDisabled(),false,'no stuck control '+c);
  const stored=await persisted(page,base,id),after=await state(page);observations.result={owner,first,before,after,backendBefore:backend,backendAfter:stored,requests,realResponses:Object.fromEntries(Object.entries(holds).map(([k,v])=>[k,v.responseText]))};
  if(owner==='save'){assert.equal(after.dirty,false);assert.equal(await page.evaluate(()=>snapshot.id),id);assert.deepEqual(JSON.parse(after.wire),stored.detail);assert.equal(requests.filter(x=>x.method==='PUT').length,1);}
  else{assert.deepEqual(stored,backend);assert.equal(requests.filter(x=>x.method==='PUT').length,0);if(owner==='file')assert.equal(await page.evaluate(()=>snapshot.id),candidate.id);else assert.match(await page.evaluate(()=>snapshot.id),/^sp5:api-import:/);}
  observations.typedAudit={responses:await Promise.all(responseTasks),rawBackendBefore,rawBackendAfter:{list:await(await page.request.get('/api/snapshots')).text(),detail:await(await page.request.get('/api/snapshots/'+id)).text()}};
  const admitted=observations.typedAudit.responses.find(r=>r.path===(owner==='save'?'/api/snapshots':'/api/snapshots/check'));
  assert(admitted&&admitted.status===200);assertTypedEqual(after.wire,admitted.raw);
  if(owner==='save')assertTypedEqual(after.wire,observations.typedAudit.rawBackendAfter.detail);
  else for(const part of ['list','detail'])assertTypedEqual(observations.typedAudit.rawBackendBefore[part],observations.typedAudit.rawBackendAfter[part]);
  assert.equal(after.changeVersion,before.changeVersion+(owner==='save'?0:1));assert.equal(after.draftVersion,before.draftVersion);assert.equal(after.nativeDraftCount,0);assert.equal(after.dirty,owner!=='save');assert.equal(after.jsonDirty,false);
  assert.deepEqual(observations.consoleErrors,[]);
 }finally{for(const h of Object.values(holds))h.release();await Promise.all(Object.values(holds).map(h=>bounded(h.done,15000,'owned callback drain')));for(const h of Object.values(holds))await page.unroute(h.pattern,h.h);if(failures.length)throw failures[0];}
}));
