'use strict';
// Scoped UX-02B contracts, not a whole-workspace accessibility certification.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}}
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(170);}
async function fixture(name,run){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'primary-controls-'));
 const out=process.env.WEB_TEST_SCREENSHOT_DIR||path.join(temp,'evidence');fs.mkdirSync(out,{recursive:true});
 const report={scope:name,pageErrors:[],consoleErrors:[],checks:[],failures:[]};
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:temp,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let log='',browser,spawnError;const exited=new Promise(r=>{server.once('exit',r);server.once('error',e=>{spawnError=e;r();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',b=>log+=b);
 try{
  const base=await bounded((async()=>{for(;;){if(spawnError)throw spawnError;if(server.exitCode!==null||server.signalCode!==null)throw Error(log);const url=log.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];if(url){try{if((await fetch(url+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return url;}catch{}}await pause(100);}})(),15000,'fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(8000);
  page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  const response=await page.goto(base);assert.equal(response.headers()['content-security-policy'],"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");await page.waitForFunction(()=>window.PlannerApp);
  await page.click('#newProject');await page.fill('#wizardName','Synthetische Bedienregression');await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
  await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
  for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
  await page.click('#wizardCreate');await page.waitForFunction(()=>snapshot&&!document.getElementById('createProjectDialog').open&&!projectSwitchBusy());
  // Load a declared synthetic unresolved item through the original client path;
  // the real backend readiness response, not a DOM double, populates the count.
  await page.evaluate(()=>{const data=currentSnapshot();data.unresolved.push('Synthetischer Prüfhinweis für die Kontrastregression');load(data);});
  await page.locator('.main-nav [data-navigate="plan"]').click();
  await page.waitForFunction(()=>!document.getElementById('navBlockers').hidden);
  const state=()=>page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,jsonDirty,changeVersion,id:snapshot.id,revision:snapshot.revision}));
  const backend=async()=>{const r={};for(const endpoint of ['snapshots','jobs']){const response=await page.request.get(base+'/api/'+endpoint);assert(response.ok());r[endpoint]=await response.json();}return r;};
  report.before=await state();report.backendBefore=await backend();
  await run(page,report,out);
  report.after=await state();report.backendAfter=await backend();
  assert.deepEqual(report.after,report.before,'style/navigation probes preserve exact client data and state');assert.deepEqual(report.backendAfter,report.backendBefore,'no backend mutations');
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);
  assert.deepEqual(report.failures,[],name+' failed: '+JSON.stringify(report.failures));
 }catch(e){report.error=e.stack;throw e;}
 finally{
  try{if(browser)await bounded(browser.close(),5000,'browser close');}finally{try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'server close');}catch{server.kill('SIGKILL');await bounded(exited,5000,'server force close');}}}finally{fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(report,null,2)+'\n');fs.writeFileSync(path.join(out,name+'-server.log'),log);fs.rmSync(temp,{recursive:true,force:true});}}
 }
}
async function keyboardFocus(page,selector){
 await page.locator('.skip-link').focus();
 for(let i=0;i<32;i++){await page.keyboard.press('Tab');if(await page.locator(selector).evaluate(e=>e===document.activeElement))return;}
 assert.fail('Tab did not reach '+selector);
}
async function contrast(page,selector){return page.locator(selector).evaluate(button=>{
 const rgba=value=>{const parts=value.match(/[\d.]+/g).map(Number);return [...parts.slice(0,3),parts[3]??1];};
 const over=(a,b)=>a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3])).concat(1);
 const luminance=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 function sample(e,part){
  const chain=[];for(let p=e;p;p=p.parentElement){const s=getComputedStyle(p);chain.push({tag:p.tagName,id:p.id,color:s.color,stroke:s.stroke,background:s.backgroundColor,opacity:Number(s.opacity),image:s.backgroundImage,filter:s.filter});}
  // Composite the target group's foreground/background, then each ancestor's
  // background and opacity separately. Compare solid glyph/stroke interiors,
  // not anti-aliased edge pixels. Fail closed on unmodelled images/filters.
  const target=chain[0],ink=rgba(part==='icon'?target.stroke:target.color);
  function render(glyph){let pixel=glyph?ink:[0,0,0,0];for(const layer of chain){const bg=rgba(layer.background),alpha=pixel[3]+bg[3]*(1-pixel[3]);pixel=[...pixel.slice(0,3).map((v,i)=>alpha?(v*pixel[3]+bg[i]*bg[3]*(1-pixel[3]))/alpha:0),alpha*layer.opacity];}return over(pixel,[255,255,255,1]);}
  const fg=render(true),bg=render(false),a=luminance(fg),b=luminance(bg);
  return {part,text:e.textContent,foreground:fg,background:bg,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),chain,supported:chain.every(s=>s.image==='none'&&s.filter==='none')};
 }
 const samples=[sample(button.querySelector('span:first-of-type'),'label'),sample(button.querySelector('.icon'),'icon')];
 for(const e of button.querySelectorAll('.nav-count'))if(!e.hidden&&e.getClientRects().length&&e.textContent.trim())samples.push(sample(e,'count'));
 return {active:button.getAttribute('aria-current')==='page',hover:button.matches(':hover'),focus:button===document.activeElement,focusVisible:button.matches(':focus-visible'),samples};
});}

test('UX02B-NAV-HOVER-CONTRAST active/inactive labels, icons and counts survive mouse and keyboard states',{timeout:120000},async()=>fixture('nav-control-contrast',async(page,report,out)=>{
 const keys=['projects','plan','team','setup'];
 for(const width of [320,1440]){
  await page.setViewportSize({width,height:1000});await settle(page);
  for(const key of keys)for(const active of [false,true]){
   const selector=`.main-nav [data-navigate="${key}"]`,other=key==='projects'?'team':'projects';
   await page.locator(`.main-nav [data-navigate="${active?key:other}"]`).click();
   for(const phase of ['idle','hover','focus']){
    await page.mouse.move(width-2,2);await page.evaluate(()=>document.activeElement?.blur());
    if(phase==='hover')await page.locator(selector).hover();
    if(phase==='focus')await keyboardFocus(page,selector);
    await settle(page);const measured=await contrast(page,selector),record={width,key,active,phase,...measured};report.checks.push(record);
    assert.equal(measured.active,active);assert.equal(measured.hover,phase==='hover');if(phase==='focus')assert(measured.focus&&measured.focusVisible);
    for(const sample of measured.samples){assert(sample.supported,'unsupported color composition');if(sample.ratio<4.5)report.failures.push({width,key,active,phase,part:sample.part,ratio:sample.ratio});}
    if(phase==='hover'&&active&&key==='plan')await page.screenshot({path:path.join(out,`nav-control-hover-${width}.png`)});
   }
   await page.keyboard.press('Enter');await settle(page);assert.equal(await page.locator(selector).getAttribute('aria-current'),'page','keyboard activation uses the actual nav handler');
  }
 }
 assert.equal(report.checks.length,48);
 for(const key of ['team','setup'])assert(report.checks.filter(c=>c.key===key).every(c=>c.samples.some(s=>s.part==='count')),'actual '+key+' counts covered in all states');
}));

async function scaleFonts(page,scale){return page.evaluate(scale=>{
 for(const [e,value,priority] of window.primaryControlFonts||[])if(e.isConnected){if(value)e.style.setProperty('font-size',value,priority);else e.style.removeProperty('font-size');}
 const nodes=[...document.querySelectorAll('body,body *')].filter(e=>e instanceof HTMLElement);
 const baseline=nodes.map(e=>({e,size:parseFloat(getComputedStyle(e).fontSize),value:e.style.getPropertyValue('font-size'),priority:e.style.getPropertyPriority('font-size')}));
 window.primaryControlFonts=baseline.map(({e,value,priority})=>[e,value,priority]);
 if(scale!==1)for(const {e,size} of baseline)e.style.setProperty('font-size',size*scale+'px','important');
 return {scale,mismatches:baseline.filter(({e,size})=>Math.abs(parseFloat(getComputedStyle(e).fontSize)-size*scale)>.02).length};
},scale);}
async function geometry(page,selector){return page.locator(selector).evaluate(e=>{
 const r=e.getBoundingClientRect(),header=document.querySelector('.topbar').getBoundingClientRect();
 const clip={left:0,right:innerWidth,top:Math.max(0,header.bottom),bottom:innerHeight};
 for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),a=p.getBoundingClientRect();if(/auto|scroll|hidden|clip/.test(s.overflowX)){clip.left=Math.max(clip.left,a.left+p.clientLeft);clip.right=Math.min(clip.right,a.left+p.clientLeft+p.clientWidth);}if(/auto|scroll|hidden|clip/.test(s.overflowY)){clip.top=Math.max(clip.top,a.top+p.clientTop);clip.bottom=Math.min(clip.bottom,a.top+p.clientTop+p.clientHeight);}}
 return {id:e.id,disabled:e.disabled,focused:e===document.activeElement,height:r.height,left:r.left,right:r.right,top:r.top,bottom:r.bottom,clip,scrollX,scrollY,documentWidth:document.documentElement.scrollWidth,width:innerWidth,font:getComputedStyle(e).fontSize,fullyVisible:r.width>0&&r.height>0&&r.left>=clip.left-.1&&r.right<=clip.right+.1&&r.top>=clip.top-.1&&r.bottom<=clip.bottom+.1,uncovered:[[.1,.1],[.5,.5],[.9,.9]].every(([x,y])=>{const hit=document.elementFromPoint(r.left+r.width*x,r.top+r.height*y);return hit===e||e.contains(hit);})};
});}
test('UX02B-PRIMARY-CONTROL-44 actual plan action and view selector at 100% and 125% CSSOM text',{timeout:60000},async()=>fixture('primary-control-height',async(page,report,out)=>{
 await page.locator('.main-nav [data-navigate="plan"]').click();
 assert.equal(await page.getByRole('button',{name:'Speichern und berechnen',exact:true}).count(),1);
 assert.equal(await page.getByRole('combobox',{name:'Ansicht',exact:true}).count(),1);
 for(const width of [320,390,1440])for(const scale of [1,1.25]){
  await scaleFonts(page,1);await page.setViewportSize({width,height:1000});const fonts=await scaleFonts(page,scale);assert.equal(fonts.mismatches,0);
  for(const id of ['solve','planView']){
   await page.locator('#'+id).evaluate(e=>{e.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});e.focus({preventScroll:true});});await settle(page);
   const g=await geometry(page,'#'+id);report.checks.push({width,scale,fonts,...g});
   assert(!g.disabled&&g.focused&&g.fullyVisible&&g.uncovered,'settled control must be enabled, focused, visible and hit-testable: '+JSON.stringify(g));
   assert.equal(g.documentWidth,width,'no document clipping or horizontal overflow');
   if(g.height<44)report.failures.push({id,width,scale,height:g.height});
   await page.screenshot({path:path.join(out,`primary-${id}-${width}-${scale}.png`)});
  }
 }
 await scaleFonts(page,1);assert.equal(report.checks.length,12);
 // The actual native select handles keyboard selection without changing data.
 await page.locator('#planView').focus();await page.keyboard.press('End');assert.equal(await page.locator('#planView').inputValue(),'positions');await page.keyboard.press('Home');assert.equal(await page.locator('#planView').inputValue(),'employees');
}));
