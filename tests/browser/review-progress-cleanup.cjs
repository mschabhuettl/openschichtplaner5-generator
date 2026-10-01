'use strict';
// CI lifecycle regression: real fixture and original progress callback.
// Only a declared route-fetch barrier and a synthetic assertion are injected.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function withWorkspace(run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-workspace-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;const releases=[];
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 try{
  const base=await bounded((async()=>{for(;;){
   if(spawnError)throw spawnError;
   if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
   const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
   if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
   await pause(100);
  }})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run(page,{base,releases}),60000,'Workspace scenario');assert.deepEqual(errors,[]);
 }finally{
  releases.forEach(release=>release());
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{fs.rmSync(state,{recursive:true,force:true});}
  }
 }
}

const progressView=require('./progress-view.cjs');
for(const failAtCancel of [false,true])test(`progress fixture drains active routes on ${failAtCancel?'assertion failure':'success'}`,async()=>withWorkspace(async(page,{base,releases})=>{
 let notify,release;const seen=new Promise(r=>notify=r),gate=new Promise(r=>release=r);releases.push(release);
 let armed=false,held=false,heldFinished=false,active=0,activeAtSettlement=null,trigger;
 const events=[],routeErrors=[];
 const proxy=new Proxy(page,{get(target,key){
  if(key==='route')return async(pattern,handler,...options)=>{
   if(!(pattern instanceof RegExp)||!pattern.test(base+'/api/jobs/probe/status'))return target.route(pattern,handler,...options);
   return target.route(pattern,async route=>{
    active++;let selected=false;
    const gated=new Proxy(route,{get(original,method){
     if(method==='fetch')return async(...args)=>{
      if(armed&&!held){selected=true;held=true;events.push('fetch-held');notify();await bounded(gate,10000,'Held status fetch');events.push('fetch-released');}
      return original.fetch(...args);
     };
     const member=Reflect.get(original,method,original);return typeof member==='function'?member.bind(original):member;
    }});
    try{await handler(gated);}catch(error){routeErrors.push(error.message);throw error;}
    finally{active--;if(selected){heldFinished=true;events.push('held-callback-finished');}}
   },...options);
  };
  if(key==='click')return async(selector,...options)=>{
   if(selector!=='#cancel')return target.click(selector,...options);
   const id=await target.evaluate(()=>jobId);assert(id,'Real calculation exists before cancellation');
   const cancelled=target.waitForResponse(r=>r.url()===base+'/api/jobs/'+encodeURIComponent(id)+'/cancel'&&r.request().method()==='POST');
   await target.click(selector,...options);
   const response=await cancelled;
   assert.equal(response.status(),200,'Real cancel endpoint accepted cancellation');
   let raw,reads=0;
   const deadline=Date.now()+10000;
   do{
    const status=await target.request.get(base+'/api/jobs/'+encodeURIComponent(id)+'/status');
    assert.equal(status.status(),200);raw=await status.json();reads++;
    if(raw.state==='cancelled')break;
    await pause(50);
   }while(Date.now()<deadline);
   assert.equal(raw.state,'cancelled','Unintercepted backend status confirms cancellation');
   console.log('Cancellation readback',JSON.stringify({failAtCancel,cancelHttpStatus:response.status(),state:raw.state,reads}));
   armed=true;
   // A real request to the real cancelled job enters the original progress
   // callback; only fetch timing is held. No fabricated backend response.
   trigger=target.evaluate(id=>fetch('/api/jobs/'+encodeURIComponent(id)+'/status').then(r=>r.json()),id);
   await bounded(seen,10000,'Pending status callback');
   events.push('cancel-action-return');
   if(failAtCancel)assert.fail('Injected assertion after real cancellation');
  };
  const member=Reflect.get(target,key,target);return typeof member==='function'?member.bind(target):member;
 }});
 const settled=progressView({page:proxy,base}).then(()=>{activeAtSettlement=active;events.push('fixture-resolved');return {ok:true};},error=>{activeAtSettlement=active;events.push('fixture-rejected');return {ok:false,error};});
 try{
  await bounded(Promise.race([seen,settled.then(result=>{if(!held)throw result.error||Error('No held route');})]),40000,'Reach cancellation');
  // This bounded negative assertion deliberately keeps the callback pending.
  // A wait-based teardown cannot return until the gate is explicitly released.
  const returnedEarly=await Promise.race([settled.then(()=>true),pause(150).then(()=>false)]);
  release();const result=await bounded(settled,10000,'Fixture completion');
  if(trigger)await bounded(trigger,10000,'Status response');
  await page.unrouteAll({behavior:'wait'});
  console.log('Progress teardown observations',JSON.stringify({failAtCancel,returnedEarly,activeAtSettlement,heldFinished,events,routeErrors}));
  assert.equal(returnedEarly,false,'Fixture must not finish while its original route callback is held');
  assert.equal(activeAtSettlement,0,'No callback may outlive the fixture');assert(heldFinished);
  assert.deepEqual(routeErrors,[]);
  if(failAtCancel){assert.equal(result.ok,false);assert.match(result.error.message,/Injected assertion after real cancellation/);}
  else assert.equal(result.ok,true,result.error?.stack);
  // Same owner action as check.cjs; no route is still using the closed page.
  await page.close();
 }finally{
  release();await bounded(settled,10000,'Final fixture cleanup');
  if(trigger)await bounded(trigger,10000,'Final request cleanup');
  if(!page.isClosed())await page.unrouteAll({behavior:'wait'});
 }
}));
