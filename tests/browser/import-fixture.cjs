'use strict';
// UX-03C: real import controls and synthetic loopback persistence only.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function fixture(name,run,{sourceRoot}={}){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-import-flow-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0',...(sourceRoot?{SP5_SOURCE_ROOT:sourceRoot}:{})},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 const observations={consoleErrors:[],pageErrors:[],measurements:[]};
 const artifacts=process.env.WEB_TEST_SCREENSHOT_DIR||path.join(state,'artifacts');
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
  await bounded(run(page,{base,observations,artifacts}),60000,'Import scenario');
  assert.deepEqual(observations.pageErrors,[],'no JavaScript exceptions');
 }finally{
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{
    try{if(artifacts)fs.writeFileSync(path.join(artifacts,name+'.json'),JSON.stringify(observations,null,2)+'\n');}
    finally{fs.rmSync(state,{recursive:true,force:true});}
   }
  }
 }
}
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(160);}
async function visibleFeedback(page,id,observations,artifacts,label){
 const m=await page.locator('#'+id).evaluate(e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);return {id:e.id,text:e.textContent,role:e.getAttribute('role'),label:e.getAttribute('aria-label'),focused:e===document.activeElement,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,hit:hit===e||e.contains(hit)};});
 observations.measurements.push(m);if(artifacts)await page.screenshot({path:path.join(artifacts,label+'-'+m.width+'.png')});
 assert(m.text&&m.label&&m.role==='status');assert(m.focused&&m.hit&&m.left>=0&&m.right<=m.width&&m.top>=0&&m.bottom<=m.height,'settled local status visible and focused '+JSON.stringify(m));
}
async function state(page){return page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),raw:document.getElementById('json').value,dirty,jsonDirty,changeVersion,personDraft}));}
async function teams(page){await page.click('#openImport');await page.selectOption('#sourceType','api');await page.click('#inspect');await page.waitForSelector('[data-team-id="2"]');await page.check('[data-team-id="2"]');}
async function persisted(page,base,id){return {list:await(await page.request.get(base+'/api/snapshots')).json(),detail:await(await page.request.get(base+'/api/snapshots/'+id)).json()};}

function assertTypedEqual(left,right){
 // Independent Python decoder preserves integer/float categories and signed zero.
 require('node:child_process').execFileSync(process.env.WEB_TEST_PYTHON||'python',[path.join(__dirname,'import-wire-oracle.py')],{input:JSON.stringify([left,right]),encoding:'utf8',env:{...process.env,TMPDIR:os.tmpdir()}});
}
module.exports={fixture,state,persisted,settle,visibleFeedback,bounded,teams,assertTypedEqual,pause};
