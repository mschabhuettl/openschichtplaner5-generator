'use strict';
// Browser geometry, not a DOM mock: native scroll quantization must not be
// confused with inability to reach a control using the local scroll container.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require('playwright');
const geometryModule=process.env.LAYOUT_GEOMETRY_MODULE||path.join(__dirname,'workspace-layout-geometry.cjs');
const {measure,reach,settle}=require(geometryModule);
const moduleHash=()=>crypto.createHash('sha256').update(fs.readFileSync(geometryModule)).digest('hex');

test('UX02B-CI-LAYOUT-REVEAL fractional local scrolling and negative visibility controls',{timeout:30000},async t=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
 const report={browser:browser.version(),source:geometryModule,sourceBefore:moduleHash(),cases:[],pageErrors:[],consoleErrors:[]};
 try{
  const page=await browser.newPage({viewport:{width:390,height:800}});
  page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
  await page.route('**/*',r=>r.abort());
  const fixture=async({width=390,fraction=.140625,overflow='auto',rowWidth=1300,buttonWidth=140,overlay=false}={})=>{
   await page.setViewportSize({width,height:800});
   await page.setContent(`<style>body{margin:17px}.topbar{position:fixed;left:0;top:0;height:10px;width:100%}#scroller{width:${width-34}px;height:200px;overflow:${overflow}}#row{width:${rowWidth}px;height:100px;position:relative}#duty{position:absolute;left:${480+fraction}px;top:20px;width:${buttonWidth}px;height:60px}#cover{position:fixed;inset:15px;z-index:5}</style><div class="topbar"></div><div id="scroller"><div id="row"><button id="duty">Synthetic duty</button></div></div>${overlay?'<div id="cover"></div>':''}`);
   await page.evaluate(()=>{window.activations=0;document.getElementById('duty').addEventListener('click',()=>window.activations++);});
  };
  for(const width of [320,390])for(const fraction of [.140625,.484375])await t.test(`reachable fractional duty ${width}/${fraction}`,async()=>{
   await fixture({width,fraction});
   await page.locator('#duty').evaluate(e=>e.scrollIntoView({block:'center',inline:'end',behavior:'instant'}));await settle(page);
   const native=await measure(page,'#duty');
   assert.equal(native.fullyVisible,false,'original strict geometry still catches the native clipped edge');
   assert.equal(native.right-native.clip.right,fraction);
   await page.mouse.move(width-40,70);await page.mouse.wheel(1,0);await settle(page);
   const wheel=await measure(page,'#duty');assert.equal(wheel.fullyVisible&&wheel.uncovered,true,'real local wheel input reaches the whole control');
   const result=await reach(page,'#duty',true);report.cases.push({width,fraction,native,wheel,result});
   assert.equal(result.fullyVisible&&result.uncovered,true,'reach must reproduce complete local-scroll reachability without widening the geometry tolerance');
   assert.equal(result.focused,true);
   assert.equal(await page.locator('#duty').evaluate(e=>{const r=e.getBoundingClientRect();return document.elementFromPoint(r.right-.05,r.top+r.height/2)===e;}),true,'right-edge hit test, not only the centre');
   await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>window.activations),1,'original focused control activates by keyboard');
  });
  for(const [name,options] of [
   ['exact integer edge',{fraction:0}],
   ['non-scrollable clipping',{overflow:'clip'}],
   ['scroll range exhausted',{rowWidth:620.140625}],
   ['oversized control',{buttonWidth:400}],
   ['covered control',{overlay:true}],
  ])await t.test(name,async()=>{
   await fixture(options);const result=await reach(page,'#duty',true);report.cases.push({name,result});
   if(name==='exact integer edge')assert.equal(result.fullyVisible&&result.uncovered,true);
   else if(name==='covered control')assert.equal(result.uncovered,false,'occlusion remains a failing visibility oracle');
   else assert.equal(result.fullyVisible,false,'actual clipping remains a failing geometry oracle');
  });
  assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);
 }finally{
  report.sourceAfter=moduleHash();report.sourceStable=report.sourceBefore===report.sourceAfter;
  if(process.env.WEB_TEST_SCREENSHOT_DIR)fs.writeFileSync(path.join(process.env.WEB_TEST_SCREENSHOT_DIR,'layout-reach.json'),JSON.stringify(report,null,2)+'\n');
  await browser.close();
 }
 assert.equal(report.sourceStable,true);
});
