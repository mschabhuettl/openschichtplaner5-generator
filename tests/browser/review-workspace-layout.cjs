'use strict';
// S-UX02A-02: real synthetic solver + saved reopen; no production/network data.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}}
const inputs=['tests/browser/review-workspace-layout.cjs','tests/browser/server.py','tests/browser/navigation.cjs','sp5generator/static/design.css','sp5generator/static/app.js','sp5generator/static/workspace.js','sp5generator/static/index.html'];
const hashes=()=>Object.fromEntries(inputs.map(file=>[file,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
const cases=[
 {name:'standard',title:'Synthetisches Team Oktober',people:['Testperson A','Testperson B','Testperson C']},
 {name:'spaced-title',title:'Synthetisches Planungsteam mit einem langen Projektnamen für die gemeinsame Dienstplanung im Oktober',people:['Testperson A','Testperson B','Testperson C']},
 {name:'unbroken-title',title:'X'.repeat(120),people:['Testperson A','Testperson B','Testperson C']},
 {name:'long-people',title:'Synthetisches Team Oktober',people:['Synthetische Testperson Alexandra mit langem zusammengesetztem Familiennamen','Synthetische Testperson Benjamin mit ebenfalls langem Familiennamen','SynthetischeTestperson'.padEnd(120,'Z')]},
].filter(c=>!process.env.LAYOUT_TEXT_CASE||c.name===process.env.LAYOUT_TEXT_CASE);
assert(cases.length,'LAYOUT_TEXT_CASE must name a declared text fixture');
const viewports=[{width:320,height:1000},{width:390,height:1000},{width:768,height:1000},{width:1440,height:1000},{width:390,height:800}];
const csp="default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'";
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(90);}
async function top(page){await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);document.querySelectorAll('#calendar,#calendar *').forEach(e=>{e.scrollTop=0;e.scrollLeft=0;});});await settle(page);}
async function font(page,scale){
 return page.evaluate(scale=>{
  for(const [e,value,priority] of window.layoutFonts||[])if(e.isConnected){if(value)e.style.setProperty('font-size',value,priority);else e.style.removeProperty('font-size');}
  window.layoutFonts=[];
  const nodes=[...document.querySelectorAll('body,body *')].filter(e=>e instanceof HTMLElement);
  const baseline=nodes.map(e=>({e,size:parseFloat(getComputedStyle(e).fontSize),value:e.style.getPropertyValue('font-size'),priority:e.style.getPropertyPriority('font-size')}));
  if(scale!==1){window.layoutFonts=baseline.map(({e,value,priority})=>[e,value,priority]);for(const {e,size} of baseline)e.style.setProperty('font-size',size*scale+'px','important');}
  const proof=baseline.map(({e,size})=>({tag:e.tagName,id:e.id,before:size,after:parseFloat(getComputedStyle(e).fontSize)}));
  return {scale,dpr:devicePixelRatio,count:proof.length,mismatches:proof.filter(p=>Math.abs(p.after-p.before*scale)>.02),samples:proof.filter(p=>['solve','planTitle','projectName','planView'].includes(p.id))};
 },scale);
}
async function measure(page,selector){return page.locator(selector).first().evaluate(e=>{
 const r=e.getBoundingClientRect(),h=document.querySelector('.topbar').getBoundingClientRect();
 const rect={left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};
 const overlap=r.right>h.left&&r.left<h.right&&!e.closest('.topbar,.sidebar');
 const clip={left:0,right:innerWidth,top:overlap?Math.max(0,h.bottom):0,bottom:innerHeight};
 const ancestors=[];
 for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),q=p.getBoundingClientRect();
  if(/auto|scroll|hidden|clip/.test(s.overflowX)){clip.left=Math.max(clip.left,q.left+p.clientLeft);clip.right=Math.min(clip.right,q.left+p.clientLeft+p.clientWidth);}
  if(/auto|scroll|hidden|clip/.test(s.overflowY)){clip.top=Math.max(clip.top,q.top+p.clientTop);clip.bottom=Math.min(clip.bottom,q.top+p.clientTop+p.clientHeight);}
  if(p.scrollLeft||p.scrollTop)ancestors.push({tag:p.tagName,id:p.id,className:p.className,x:p.scrollLeft,y:p.scrollTop});
 }
 const uncovered=[[.1,.1],[.5,.5],[.9,.9]].every(([x,y])=>{const hit=document.elementFromPoint(r.left+r.width*x,r.top+r.height*y);return hit===e||e.contains(hit);});
 return {...rect,clip,uncovered,fullyVisible:r.width>0&&r.height>0&&r.left>=clip.left-.1&&r.right<=clip.right+.1&&r.top>=clip.top-.1&&r.bottom<=clip.bottom+.1,focused:document.activeElement===e,text:e.textContent,scrollX,scrollY,ancestors};
 });}
async function reach(page,selector,focus=false){
 await page.locator(selector).first().evaluate((e,focus)=>{e.scrollIntoView({block:'center',inline:'end',behavior:'instant'});if(focus)e.focus({preventScroll:true});},focus);
 await settle(page);return measure(page,selector);
}
async function shell(page){return page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollX,scrollY,documentWidth:document.documentElement.scrollWidth,navWidth:document.querySelector('.main-nav').clientWidth,navScroll:document.querySelector('.main-nav').scrollWidth,rootOverflow:getComputedStyle(document.documentElement).overflowX,bodyOverflow:getComputedStyle(document.body).overflowX,outside:[...document.querySelectorAll('#mainContent *,.topbar *')].filter(e=>e.getClientRects().length&&!e.closest('.scroll,.sr-only')&&![...document.querySelectorAll('details:not([open])')].some(d=>d.contains(e)&&!d.querySelector(':scope > summary')?.contains(e))).map(e=>{const r=e.getBoundingClientRect();return {id:e.id,tag:e.tagName,className:typeof e.className==='string'?e.className:'',left:r.left,right:r.right,width:r.width};}).filter(r=>r.left<0||r.right>innerWidth),localScrolls:[...document.querySelectorAll('#calendar,#calendar *')].filter(e=>e.scrollLeft||e.scrollTop).map(e=>({id:e.id,x:e.scrollLeft,y:e.scrollTop}))}));}
async function createAndSolve(page,data){
 await page.click('.main-nav [data-navigate="projects"]');await page.click('#newProject');await page.fill('#wizardName',data.title);
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople',data.people.join('\n'));await page.click('#wizardNext');
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
 const first=page.locator('#people tbody tr:first-child input[type="number"]');await first.fill('32');await first.press('Tab');
 await require('./navigation.cjs')(page,'demand');const demand=page.locator('td[data-demand-day="2026-10-05"] input.demand-value');await demand.fill('2');await demand.press('Tab');
 await require('./navigation.cjs')(page,'calculate');await page.fill('#limit','5');await page.click('#solve');
 await page.waitForFunction(()=>!PlannerApp.getState().solving&&!PlannerApp.getState().jobId&&document.getElementById('result').textContent.includes('Vollständig'),null,{timeout:40000});
 const reference=await page.evaluate(()=>{const s=currentSnapshot();return {snapshot:s,minutes:s.assignments.reduce((n,a)=>n+s.shifts.find(x=>x.id===s.demands.find(d=>d.id===a.demand_id).shift_id).paid_minutes,0)};});
 assert.equal(reference.snapshot.employees.length,3);assert.equal(reference.snapshot.assignments.length,6);assert.equal(reference.minutes,2880);
 assert.equal(await page.locator('#calendar td[data-date="2026-10-05"] .shift-badge').count(),2);
 return reference;
}

test('S-UX02A-02 extended text/viewport real-browser matrix', {timeout:300000},async t=>{
 const state=fs.mkdtempSync(path.join(os.tmpdir(),'layout-matrix-'));
 const out=process.env.WEB_TEST_SCREENSHOT_DIR||path.join(state,'evidence');fs.mkdirSync(out,{recursive:true});
 const report={started:new Date().toISOString(),sourcesBefore:hashes(),expected:cases.length*2*viewports.length*2,pageErrors:[],consoleErrors:[],fixtures:[],cases:[]};
 const save=()=>fs.writeFileSync(path.join(out,'layout-matrix.json'),JSON.stringify(report,null,2)+'\n');
 fs.writeFileSync(path.join(out,'harness.cjs'),fs.readFileSync(__filename));fs.writeFileSync(path.join(out,'design.css'),fs.readFileSync(path.join(root,'sp5generator/static/design.css')));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;const exited=new Promise(r=>{server.once('exit',r);server.once('error',e=>{spawnError=e;r();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>{output+=data;});
 try{
  const base=await bounded((async()=>{for(;;){if(spawnError)throw spawnError;if(server.exitCode!==null||server.signalCode!==null)throw Error(output);const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}await pause(100);}})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(8000);
  page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  const response=await page.goto(base);report.csp=response.headers()['content-security-policy'];assert.equal(report.csp,csp);await page.waitForFunction(()=>window.PlannerApp);
  for(const data of cases){
   await font(page,1);await page.setViewportSize({width:1440,height:1000});
   const reference=await createAndSolve(page,data);report.fixtures.push({name:data.name,...reference});
   for(const mode of ['solved','reopened']){
    if(mode==='reopened'){
     await font(page,1);await page.click('#saveDraft');await page.waitForFunction(()=>!PlannerApp.getState().dirty&&!projectSwitchBusy());
     const saved=await page.evaluate(()=>currentSnapshot());assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+saved.id)).json(),saved);
     await page.reload();await page.locator(`.project-card[data-project-id="${saved.id}"]`).press('Enter');await page.waitForFunction(()=>!projectSwitchBusy()&&snapshot!==null);
     assert.deepEqual(await page.evaluate(()=>currentSnapshot()),saved);assert.equal(await page.evaluate(()=>document.body.dataset.activePanel),'plan');
    }
    for(const viewport of viewports)for(const scale of [1,1.25]){
     const id=`${data.name}-${mode}-${viewport.width}x${viewport.height}-${scale}`;
     await t.test(id,async()=>{
      const record={id,...viewport,scale,mode,fixture:data.name,failures:[]};report.cases.push(record);
      const check=(ok,label,detail)=>{if(!ok)record.failures.push({label,detail});};
      const visible=(geometry,label)=>check(geometry.fullyVisible&&geometry.uncovered,label,geometry);
      try{
       await font(page,1);await page.setViewportSize(viewport);await page.click('.main-nav [data-navigate="plan"]');await settle(page);record.font=await font(page,scale);check(record.font.mismatches.length===0,'computed font enlargement',record.font);
       await top(page);record.initial=await shell(page);
       check(record.initial.documentWidth===viewport.width,'plan document overflow',record.initial);check(record.initial.navWidth===record.initial.navScroll,'main nav overflow',record.initial);
       check(!/hidden|clip/.test(record.initial.rootOverflow+' '+record.initial.bodyOverflow),'no root clipping',record.initial);
       record.nav=[];
       for(const [key,label] of [['projects','Projekte'],['plan','Plan'],['team','Team'],['setup','Einrichtung']]){
        const button=await measure(page,`.main-nav [data-navigate="${key}"]`),text=await measure(page,`.main-nav [data-navigate="${key}"] span:first-of-type`);record.nav.push({key,button,text});visible(button,'main button '+key);visible(text,'main label '+key);check(text.text===label,'exact label '+key,text);check(button.height>=44,'44px main control '+key,button);
       }
       record.person=await measure(page,'#calendar tbody tr:first-child th');record.row=await measure(page,'#calendar tbody tr:first-child');
       record.duties=[];const duties=page.locator('#calendar td[data-date="2026-10-05"] .shift-badge');
       for(let i=0;i<await duties.count();i++){await duties.nth(i).evaluate((e,i)=>e.dataset.layoutDuty=i,i);record.duties.push(await measure(page,`[data-layout-duty="${i}"]`));}
       check(record.duties.length===2,'two real first-day duties',record.duties);
       if(data.name==='standard'&&scale===1&&viewport.height===1000){
        check(record.initial.scrollX===0&&record.initial.scrollY===0&&record.initial.localScrolls.length===0,'reference starts unscrolled',record.initial);
        if(viewport.width===1440)record.duties.forEach(d=>visible(d,'desktop BOTH first-day duties'));
        if(viewport.width===390){visible(record.person,'mobile whole first person');check(record.row.bottom<=viewport.height-32,'mobile first row +32px reserve',record.row);}
       }
       await page.screenshot({path:path.join(out,id+'-top.png')});
       record.reachable={};for(const [key,selector] of [['primary','#solve'],['status','#result'],['calendar','#planView']]){const r=await reach(page,selector,key!=='status');record.reachable[key]=r;visible(r,'reachable '+key);}
       record.reachable.duty=await reach(page,'[data-layout-duty="0"]',true);visible(record.reachable.duty,'real duty reachable with local scroll');
       await page.screenshot({path:path.join(out,id+'-calendar.png')});
       if(viewport.height===800)check(await page.locator('.plan-panel .page-section-heading p').isVisible()===false,'no long plan intro at 800px');
       // Fixture has auth disabled: layout-only representation, not session test.
       await page.evaluate(()=>document.getElementById('logout').hidden=false);record.logout=await reach(page,'#logout button',true);visible(record.logout,'logout reachable');check(record.logout.focused,'logout keyboard focus',record.logout);check(record.logout.height>=44,'44px logout control',record.logout);await page.screenshot({path:path.join(out,id+'-logout.png')});await page.evaluate(()=>document.getElementById('logout').hidden=true);
       await font(page,1);await page.click('.main-nav [data-navigate="projects"]');await page.waitForSelector('.job-row');await settle(page);record.projectFont=await font(page,scale);check(record.projectFont.mismatches.length===0,'projects computed font enlargement',record.projectFont);await top(page);
       record.projects=await shell(page);check(record.projects.documentWidth===viewport.width,'populated projects document overflow',record.projects);
       record.jobs=await page.locator('.job-row').allTextContents();check(record.jobs.some(text=>text.includes('Beendet · Ergebnis prüfen')),'real completed job retained',record.jobs);
       const card=page.locator(`.project-card[data-project-id="${reference.snapshot.id}"]`);
       record.title=await card.evaluate(e=>{const p=e.getBoundingClientRect(),r=e.querySelector('h3').getBoundingClientRect();return {text:e.querySelector('h3').textContent,left:r.left,right:r.right,top:r.top,bottom:r.bottom,card:{left:p.left,right:p.right,top:p.top,bottom:p.bottom}};});
       check(record.title.text===data.title,'project title preserved',record.title);check(record.title.left>=record.title.card.left&&record.title.right<=record.title.card.right&&record.title.bottom<=record.title.card.bottom,'full title contained in project card',record.title);
       await page.screenshot({path:path.join(out,id+'-projects.png')});
       check(report.pageErrors.length===0,'pageerror channel',report.pageErrors);check(report.consoleErrors.length===0,'console.error channel',report.consoleErrors);
      }catch(error){record.harnessError=error.stack;throw error;}finally{save();}
      assert.deepEqual(record.failures,[],id+' layout failures: '+JSON.stringify(record.failures));
     });
    }
    await font(page,1);await page.click('.main-nav [data-navigate="plan"]');
   }
  }
  assert.equal(report.cases.length,report.expected,'full declared matrix executed');
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);
 }finally{
  report.finished=new Date().toISOString();report.sourcesAfter=hashes();report.sourceStable=JSON.stringify(report.sourcesBefore)===JSON.stringify(report.sourcesAfter);report.tested=report.cases.length;report.passed=report.cases.filter(c=>!c.harnessError&&!c.failures.length).length;save();fs.writeFileSync(path.join(out,'server.log'),output);
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}finally{try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}finally{fs.rmSync(state,{recursive:true,force:true});}}
 }
 assert.equal(report.sourceStable,true,'directly measured sources stable during run');
});
