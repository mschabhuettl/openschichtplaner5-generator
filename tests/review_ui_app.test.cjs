'use strict';
const {test} = require('node:test');

test('T08 native float provenance, service mode and progress are readable without mutation',async()=>{
 const h=await harness();h.run(`snapshot.metadata=ProjectJSON.parse('{"service_matrix_version":1.0,"provenance":{"e":{"nominal_hours":{"calcbase":0.0,"hours_day":0.0,"target_minutes":0.0,"period_start":"2026-10-01","period_end":"2026-10-31"}}}}')`);
 const wire=h.run('ProjectJSON.stringify(snapshot.metadata)');
 assert.equal(h.run('serviceMatrix()'),true);
 h.run('personDetails(snapshot.employees[0])');assert.match(h.get('personHoursOrigin')?.textContent??'',/Tagesbasis mit 0 Stunden/);
 h.run(`renderLiveProgress(ProjectJSON.parse('[{"kind":"incumbent","phase":"main","objective":1.0,"bound":0.0}]'),0,10)`);
 assert.match(h.get('progressSteps').textContent,/beste Bewertung 1/);assert.match(h.get('progressSteps').textContent,/untere Schranke 0/);
 assert.equal(h.run('ProjectJSON.stringify(snapshot.metadata)'),wire);
 h.run(`snapshot.metadata.provenance.e.nominal_hours.calcbase=BigInt('9007199254740993');personDetails(snapshot.employees[0])`);
 assert.equal(h.get('personHoursOrigin'),null,'unsafe BigInt is not a numeric display fallback');
});
test('T08 boxed integer diagnostic counts stay invalid',async()=>{
 const h=await harness();assert.throws(()=>h.run(`diagnosticCounts(ProjectJSON.parse('{"diagnostics":[],"diagnostics_total":0.0,"diagnostics_omitted":0}'))`),/Hinweiszahlen/);
});
test('T08 workspace whole-second float timestamps match primitive timestamps',async()=>{
 const h=await harness();vm.runInContext(fs.readFileSync(path.join(STATIC,'workspace.js'),'utf8'),h.c);
 h.run(`window.PlannerUI.setJobs([{id:'j',snapshot_id:'A',state:'succeeded',created_at:1700000000,started_at:0,finished_at:60}])`);
 const expected=h.get('jobCards').textContent;
 h.run(`window.PlannerUI.setJobs(ProjectJSON.parse('[{"id":"j","snapshot_id":"A","state":"succeeded","created_at":1700000000.0,"started_at":0.0,"finished_at":60.0}]'))`);
 assert.equal(h.get('jobCards').textContent,expected);
});

// Execute the complete, unmodified production scripts. Only browser/HTTP seams
// are synthetic; tests invoke the original handlers rather than copied logic.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const STATIC = path.join(__dirname, '../sp5generator/static');
const {spawnSync:numericSpawn}=require('node:child_process');
function numericOracle(source,output){const p=numericSpawn(process.env.WEB_TEST_PYTHON||'python',[path.join(__dirname,'json_numeric_oracle.py')],{input:JSON.stringify([{source,output}]),encoding:'utf8',timeout:15000});assert.equal(p.status,0,p.stderr);}

for(const failure of ['NaN','unsafe','clone'])test('T09 load stages '+failure+' before changing incumbent state',async()=>{
 const h=await harness();h.run("dirty=true;jsonDirty=true;personDraft=true;$('json').value='retained text';assignments=[{demand_id:'retained'}]");
 const before=h.state(),flags=h.run('[personDraft,changeVersion]');h.c.candidate=fixture('B');
 if(failure==='NaN')h.c.candidate.metadata.invalid=NaN;
 if(failure==='unsafe')h.c.candidate.metadata.invalid=9007199254740992;
 if(failure==='clone')h.c.candidate.assignments=[()=>{}];
 assert.throws(()=>h.run('load(candidate)'),/JSON|Zahl|Darstellung/);
 assert.deepEqual(h.state(),before);assert.deepEqual(h.run('[personDraft,changeVersion]'),flags);assert.equal(h.get('json').value,'retained text');
});
test('T09 encode errors are bounded numeric errors before fetch, not connectivity errors',async()=>{
 const h=await harness();h.run('snapshot.metadata.invalid=9007199254740992;dirty=true');const count=h.requests.length;
 await assert.rejects(h.run("api('/api/snapshots','PUT',currentSnapshot())"),error=>error.code==='PROJECT_JSON'&&!/erreichbar/.test(error.message));
 assert.equal(h.requests.length,count);assert.equal(h.state().snapshot.revision,'1');assert.equal(h.state().dirty,true);
});
test('T09 rejected file retains selection, JSON and person drafts',async()=>{
 const h=await harness();h.run("dirty=true;jsonDirty=true;personDraft=true;$('json').value='retained text'");
 const before=h.state();h.get('file').value='synthetic.json';h.get('file').files=[{size:10,text:async()=>'{"invalid":1e400}'}];
 await h.get('file').onchange();assert.equal(h.get('file').value,'synthetic.json');assert.deepEqual(h.state(),before);assert.equal(h.run('personDraft'),true);assert.equal(h.get('json').value,'retained text');
});
test('T09 refresh JSON stages serialization before clearing draft flags',async()=>{
 const h=await harness();h.run("snapshot.metadata.invalid=9007199254740992;jsonDirty=true;$('json').value='keep this draft'");
 await h.get('refreshJson').onclick();assert.equal(h.run('jsonDirty'),true);assert.equal(h.get('json').value,'keep this draft');
});


for(const route of ['saved','job','demo','file','editor','import'])test('T07 delayed '+route+' ingress cannot replace a newer edit',async()=>{
 const h=await harness(),pending=deferred();h.c.respond=()=>pending.promise;let opening;
 if(route==='saved')opening=h.run("openSavedProject('B')");
 if(route==='job')opening=h.run("openJob('j')");
 if(route==='demo')opening=h.get('demo').onclick();
 if(route==='file'){h.get('file').value='keep.json';h.get('file').files=[{size:10,text:async()=>JSON.stringify(fixture('B'))}];opening=h.get('file').onchange();}
 if(route==='editor'){h.get('json').value=JSON.stringify(fixture('B'));opening=h.get('applyJson').onclick();}
 if(route==='import'){h.run("checkedTeams.add('t');$('sourceType').value='directory'");opening=h.get('import').onclick();}
 await new Promise(r=>setImmediate(r));h.run("snapshot.employees[0].name='new local edit';invalidateResult();jsonDirty=true;personDraft=true;$('json').value='new draft text'");
 const before=h.state();h.c.respond=req=>req.url==='/api/snapshots/check'?req.data:{state:'failed',created_at:0,finished_at:0};pending.resolve(route==='import'?{snapshot:fixture('B')}:fixture('B'));
 await Promise.resolve(opening).catch(e=>assert.match(e.message,/geändert|erneut/));
 assert.deepEqual(h.state(),{...before,projectBusy:false});assert.equal(h.get('json').value,'new draft text');assert.equal(h.run('personDraft'),true);
 if(route==='file')assert.equal(h.get('file').value,'keep.json');
});
for(const change of ['json','person','unversioned'])test('T07 validation respects exact late '+change+' draft binding',async()=>{
 const h=await harness(),pending=deferred();h.c.respond=()=>pending.promise;const checking=h.get('validate').onclick();
 if(change==='json')h.run('jsonDirty=true');if(change==='person')h.run('personDraft=true');if(change==='unversioned')h.run("snapshot.metadata.numeric=BigInt('9007199254740993')");
 pending.resolve({valid:true,complete:true,diagnostics:[]});await checking;assert.equal(h.get('validation').textContent,'');
});
test('T09 capability loss during save response never advances revision or draft flags',async()=>{
 const h=await harness(),pending=deferred();h.run('dirty=true');h.c.respond=()=>pending.promise;const saving=h.run('save()');
 h.c.ProjectJSON={...h.c.ProjectJSON,stringify(){throw Object.assign(Error('JSON synthetic late error'),{code:'PROJECT_JSON'});}};
 pending.resolve({revision:'2'});await assert.rejects(saving,/JSON/);assert.equal(h.state().snapshot.revision,'1');assert.equal(h.state().dirty,true);
});


for(const mode of ['manual','automatic'])test('T07 '+mode+' readiness cannot acknowledge an unversioned numeric edit',async()=>{
 const h=await harness(),pending=deferred();h.c.respond=()=>pending.promise;let checking;
 if(mode==='manual'){h.run('renderSetupReview()');checking=h.button('setupReview','Planungsbereitschaft prüfen').onclick();}
 else h.run("activePanel='calculate';refreshAutomaticReadiness(true)");
 h.run("snapshot.metadata.n=BigInt('9007199254740993')");pending.resolve({ready:true,diagnostics:[]});await checking;await new Promise(r=>setImmediate(r));
 assert.notEqual(h.state().readiness.state,'ready');assert.doesNotMatch(h.get('setupReview')?.textContent??'',/Berechnung kann gestartet werden/);
});
test('T09 assignment clone failure stays a bounded JSON error before transmission',async()=>{
 const h=await harness();h.run('assignments=[()=>{}];dirty=true');const count=h.requests.length;
 await assert.rejects(h.run('save()'),e=>e.code==='PROJECT_JSON');assert.equal(h.requests.length,count);assert.equal(h.run('snapshot.revision'),'1');
});


test('T08 float-zero metric predicates retain primitive presentation without mutation',async()=>{
 const h=await harness();const metrics={split_weekends_in_plan:0,split_weekends_forced_by_demand:0,split_weekends_blocked_by_approval:0,hours_attainment:{people:1,on_target:1,none:0,under_50:0,over_110:0,median:100},approval_reach:{services:1,people:1,approvals:1,approval_share_percent:100,median_per_service:1,lowest_per_service:0,without_any_approval:0,target_out_of_reach:0},free_time:{blocks:0}};
 h.c.metrics=metrics;h.run('renderPlanMetrics(metrics)');const before=h.get('result').textContent;
 h.get('result').replaceChildren();h.c.raw=JSON.stringify(metrics).replace(/(:)(-?\d+)([,}])/g,'$1$2.0$3');h.run('metrics=ProjectJSON.parse(raw)');const stored=h.run('ProjectJSON.stringify(metrics)');h.run('renderPlanMetrics(metrics)');
 assert.equal(h.get('result').textContent,before);assert.equal(h.run('ProjectJSON.stringify(metrics)'),stored);
});

const opaqueText='{"n":9007199254740993,"f":1.0000000000000001e18,"zero":-0.0}';
for(const route of ['editor','backup','export','technical-report'])test('T07 full numeric egress '+route,async()=>{
 const h=await harness();h.c.raw=opaqueText;h.run('snapshot.metadata.opaque=ProjectJSON.parse(raw);invalidateResult()');let blob,wire;
 h.c.download=content=>blob=content;
 if(route==='editor'){h.run('syncJson(true)');wire=h.get('json').value;}
 if(route==='backup'){await h.get('backup').onclick();assert(blob,h.get('notice').textContent);wire=await blob.text();}
 if(route==='export'){
  h.c.fetch=async(url,options)=>{wire=options.body;return {ok:true,blob:async()=>new Blob(['export'])};};
  await h.document.querySelector('[data-export]').onclick();assert(wire,h.get('notice').textContent);wire=h.c.ProjectJSON.stringify(h.c.ProjectJSON.parse(wire).snapshot);
 }
 if(route==='technical-report'){h.run('renderValidation({valid:true,complete:true,diagnostics:[],opaque:snapshot.metadata.opaque})');wire=h.get('validation').textContent;numericOracle(opaqueText,wire.slice(wire.indexOf('"opaque":')+9,-2));return;}
 const value=h.c.ProjectJSON.parse(wire);numericOracle(opaqueText,h.c.ProjectJSON.stringify(value.metadata.opaque));
});
for(const route of ['saved','job','demo','directory-import','api-import'])test('T06 faithful shared transport through '+route+' and setup reuse',async()=>{
 const h=await harness(),raw=JSON.stringify(fixture('incoming')).replace('"metadata":{}','"metadata":{"adapter":"sp5-api","opaque":'+opaqueText+'}');
 h.run("snapshot.metadata={adapter:'sp5-api',opaque:{stale:true}};$('reuseSetup').checked=true;checkedTeams.add('t')");
 const checks=[];
 h.c.fetch=async(url,options={})=>{
  let text;
  if(url==='/api/snapshots/check'){checks.push(options.body);text=options.body;}
  else if(url==='/api/import'||url==='/api/remote-import')text='{"snapshot":'+raw+'}';
  else if(url.endsWith('/status'))text='{"state":"failed","created_at":0.0,"finished_at":1.0}';
  else if(url==='/api/snapshots/incoming'||url==='/api/jobs/j/snapshot'||url==='/api/demo')text=raw;
  else throw Error('unexpected numeric seam '+url);
  return {ok:true,headers:{get:()=> 'application/json'},text:async()=>text};
 };
 if(route==='saved')await h.run("openSavedProject('incoming')");
 if(route==='job')await h.run("openJob('j')");
 if(route==='demo')await h.get('demo').onclick();
 if(route.endsWith('-import')){h.get('sourceType').value=route==='directory-import'?'directory':'api';await h.get('import').onclick();}
 numericOracle(opaqueText,h.run('ProjectJSON.stringify(snapshot.metadata.opaque)'));
 for(const text of checks)numericOracle(opaqueText,h.c.ProjectJSON.stringify(h.c.ProjectJSON.parse(text).metadata.opaque));
 assert.equal(checks.length,route==='demo'?0:1);
 if(route==='job'){assert.equal(h.run('snapshot.revision'),'0');assert.equal(h.run('snapshot.metadata.restored_from_job'),'j');}
 if(route.endsWith('-import'))assert.equal(h.run('snapshot.metadata.setup_review.reusedPeople'),1);
});
test('T07 job binding distinguishes later exact integer and float-kind edits',async()=>{
 const h=await harness();h.c.raw=opaqueText;h.run('snapshot.metadata.opaque=ProjectJSON.parse(raw);jobInput=inputBinding()');
 assert.equal(h.run('inputUnchanged(jobInput)'),true);
 h.run("snapshot.metadata.opaque.n=BigInt('9007199254740995')");assert.equal(h.run('inputUnchanged(jobInput)'),false);
 h.run("snapshot.metadata.opaque=ProjectJSON.parse(raw);jobInput=inputBinding();snapshot.metadata.opaque.zero=0");assert.equal(h.run('inputUnchanged(jobInput)'),false);
});
test('T06 raw editor ingress preserves numerical tokens before check',async()=>{
 const h=await harness(),raw=JSON.stringify(fixture()).replace('"metadata":{}','"metadata":{"opaque":'+opaqueText+'}');h.c.text=raw;
 h.c.respond=()=>fixture();await h.run('readProject(text)');numericOracle(raw,h.requests.at(-1).raw);
});

const clone = value => structuredClone(value);
function deferred() { let resolve, reject; const promise = new Promise((r,j)=>{resolve=r;reject=j;}); return {promise,resolve,reject}; }
class Element {
 constructor(tag, doc) { Object.assign(this,{tagName:tag.toUpperCase(),doc,children:[],parentElement:null,dataset:{},attrs:{},className:'',_text:'',id:'',hidden:false,inert:false,disabled:false,value:'',checked:false,open:false,scrollLeft:0,scrollTop:0,listeners:{},style:{setProperty(){}}});
 this.classList={add:(...n)=>this.classes(n,true),remove:(...n)=>this.classes(n,false),toggle:(n,v)=>this.classes([n],v??!this.className.split(/\s+/).includes(n))}; }
 classes(names, add) { const s=new Set(this.className.split(/\s+/).filter(Boolean)); for(const n of names)add?s.add(n):s.delete(n);this.className=[...s].join(' ');return add; }
 set textContent(v){this._text=String(v??'');this.children.forEach(c=>c.parentElement=null);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 get childNodes(){return this.children;}
 get isConnected(){return this===this.doc.body||!!this.parentElement?.isConnected;}
 append(...nodes){for(let n of nodes){if(typeof n!=='object'){const t=new Element('#text',this.doc);t._text=String(n);n=t;}n.remove();n.parentElement=this;this.children.push(n);}}
 replaceChildren(...nodes){this.textContent='';this.append(...nodes);}
 before(n){if(!this.parentElement)return;const p=this.parentElement;n.remove();n.parentElement=p;p.children.splice(p.children.indexOf(this),0,n);}
 remove(){if(!this.parentElement)return;const p=this.parentElement;p.children=p.children.filter(n=>n!==this);this.parentElement=null;}
 setAttribute(k,v){v=String(v);this.attrs[k]=v;if(k==='id')this.id=v;if(k==='class')this.className=v;if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;}
 getAttribute(k){if(k==='id')return this.id;if(k==='class')return this.className;if(k.startsWith('data-'))return this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]??null;return this.attrs[k]??null;}
 removeAttribute(k){delete this.attrs[k];}
 matches(s){if(s.includes(':invalid'))return false;if(s.startsWith('#'))return this.id===s.slice(1);if(s.startsWith('.'))return this.className.split(/\s+/).includes(s.slice(1));const a=/^(\w+)?\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]$/.exec(s);if(a)return (!a[1]||this.tagName===a[1].toUpperCase())&&(a[3]===undefined?this.getAttribute(a[2])!==null:this.getAttribute(a[2])===a[3]);return this.tagName===s.toUpperCase();}
 querySelectorAll(s){const sels=s.split(',').map(s=>s.trim()),r=[];const visit=n=>{for(const c of n.children){if(sels.some(s=>c.matches(s)))r.push(c);visit(c);}};visit(this);return r;}
 querySelector(s){return this.querySelectorAll(s)[0]??null;}
 closest(s){for(let n=this;n;n=n.parentElement)if(n.matches(s))return n;return null;}
 addEventListener(k,f){(this.listeners[k]??=[]).push(f);}
 focus(){this.doc.activeElement=this;}
 scrollTo(){} scrollIntoView(){} reportValidity(){return true;} checkValidity(){return true;} setCustomValidity(){}
 click(){if(this.disabled)return;for(let n=this;n;n=n.parentElement)if(n.inert)return;return this.onclick?.({target:this});}
}
function makeDOM(){
 const doc={activeElement:null,createElement(tag){return new Element(tag,this);},addEventListener(){}};
 doc.body=doc.createElement('body');doc.createElementNS=(_,tag)=>doc.createElement(tag);doc.createDocumentFragment=()=>doc.createElement('fragment');
 doc.querySelectorAll=s=>doc.body.querySelectorAll(s);doc.querySelector=s=>doc.body.querySelector(s);doc.getElementById=id=>doc.querySelector('#'+id);doc.createTextNode=t=>{const n=doc.createElement('#text');n.textContent=t;return n;};
 const stack=[doc.body],voids=new Set(['input','meta','link','br','hr','img','use','path','rect','circle']);
 for(const m of fs.readFileSync(path.join(STATIC,'index.html'),'utf8').matchAll(/<\/?[a-zA-Z][^>]*>/g)){
  const tag=/^<\/?([\w-]+)/.exec(m[0])[1].toLowerCase();if(['html','head','body','script','title','meta','link'].includes(tag))continue;
  if(m[0].startsWith('</')){const i=stack.findLastIndex(n=>n.tagName===tag.toUpperCase());if(i>0)stack.length=i;continue;}
  const n=doc.createElement(tag);for(const a of m[0].matchAll(/\s([\w-]+)(?:="([^"]*)"|='([^']*)')?/g)){n.setAttribute(a[1],a[2]??a[3]??'');if(a[1]==='value')n.value=a[2]??a[3]??'';if(['open','hidden','checked','disabled'].includes(a[1]))n[a[1]]=true;}
  stack.at(-1).append(n);if(!voids.has(tag)&&!m[0].endsWith('/>'))stack.push(n);
 }
 return doc;
}
function person(id='e',name='Synthetische Person'){return {id,name,team_ids:['t'],profile_ids:[],target_minutes:600,max_period_minutes:null,excluded:false,employment_start:'2025-01-01',employment_end:'2027-12-31',approvals:[],qualifications:[],availability:[],unavailable:[],allowed_kinds:['day','night'],mentor_capacity:0};}
function fixture(id='A'){return {id,revision:'1',source:'synthetic',timezone:'UTC',period_start:'2026-10-01',period_end:'2026-10-31',context_start:'2026-09-23',context_end:'2026-11-08',employees:[person()],assignments:[],shifts:[],positions:[],demands:[],profiles:[],restrictions:[],wishes:[],boundary_work:[],unresolved:[],objectives:{},metadata:{}};}
async function harness(s=fixture()){
 const document=makeDOM(),listeners={},requests=[];
 const c=vm.createContext({console,structuredClone,Intl,Date,Math,Map,Set,Number,String,JSON,Blob,Uint8Array,document,crypto:crypto.webcrypto,URL,
 window:{confirm:()=>true,addEventListener(k,f){(listeners[k]??=[]).push(f);},dispatchEvent(){},scrollTo(){}},CustomEvent:class{},MutationObserver:class{observe(){}},requestAnimationFrame:()=>1,setTimeout:()=>1,clearTimeout(){},
 fetch:async(url,options={})=>{const req={url,method:options.method??'GET',raw:options.body,data:options.body?JSON.parse(options.body):undefined};requests.push(req);let data;if(req.method==='GET'&&url.startsWith('/api/snapshots?'))data=[];else if(url==='/api/jobs'&&req.method==='GET')data=[];else if(url==='/api/version')data={version:'test',auth_enabled:false};else data=await c.respond(req);return {ok:true,headers:{get:()=> 'application/json'},json:async()=>data,text:async()=>JSON.stringify(data)};}
 });
 for(const [name,file] of Object.entries({TeamScope:'team-scope',ServiceFamilies:'service-families',SetupAssistant:'setup-assistant',TeamTransfer:'team-transfer',ServiceGroups:'service-groups',ProfileGroups:'profile-groups'}))c[name]=require(path.join(STATIC,file+'.js'));
 c.respond=()=>{throw Error('Unexpected synthetic request');};
 c.ProjectJSON=require(path.join(STATIC,'project-json.js'));
 const run=text=>vm.runInContext(text,c);
 vm.runInContext(fs.readFileSync(path.join(STATIC,'app.js'),'utf8'),c,{filename:'app.js'});
 await new Promise(r=>setImmediate(r));c.input=clone(s);run('load(input,true)');
 return {c,run,document,requests,listeners,get:id=>document.getElementById(id),state:()=>clone(run('plannerState()')),button:(id,text)=>{const b=document.getElementById(id).querySelectorAll('button').find(b=>b.textContent===text);assert(b,`button ${id}: ${text}`);return b;}};
}

for(const change of ['other-project','same-id-reloaded','revision','unversioned-edit','json-draft'])test(`UI-001 save is bound to its exact input: ${change}`,async()=>{
 const h=await harness(),pending=deferred();h.c.respond=()=>pending.promise;
 const saving=h.run('save()');
 if(change==='other-project'||change==='same-id-reloaded'){h.c.other=fixture(change==='other-project'?'B':'A');h.c.other.revision='9';h.run('load(other,true)');}
 if(change==='revision')h.run("snapshot.revision='9'");
 if(change==='unversioned-edit')h.run('snapshot.employees[0].target_minutes=42');
 if(change==='json-draft'){h.get('json').value='draft';h.get('json').oninput();}
 const before=h.state();pending.resolve({revision:'2'});await saving;
 const after=h.state();
 if(['other-project','same-id-reloaded','revision'].includes(change)){assert.deepEqual(after.snapshot,before.snapshot);assert.equal(after.dirty,before.dirty);}
 else {assert.equal(after.dirty,true);assert.doesNotMatch(h.get('saveStatus').textContent,/^Gespeicherter/);}
});

test('UI-001 solve does not enqueue a changed input after saving',async()=>{
 const h=await harness(),pending=deferred();let jobs=0;
 h.c.respond=req=>{if(req.url==='/api/snapshots')return pending.promise;if(req.url==='/api/jobs'){jobs++;return {id:'j'};}return {state:'running'};};
 const solving=h.run('solve()');h.run('snapshot.employees[0].target_minutes=42; invalidateResult()');pending.resolve({revision:'2'});
 await assert.rejects(solving,/geändert|erneut/i);assert.equal(jobs,0);assert.equal(h.state().dirty,true);
});
function jobResult(){return {state:'succeeded',created_at:0,finished_at:1,result:{validation:{valid:true,complete:true,diagnostics:[]},solver_status:'OPTIMAL',assignments:[{employee_id:'e',demand_id:'new',segments:[]}],runtime_seconds:0.1,metrics:{},parameters:{},vacancies:{}}};}
for(const stage of ['enqueue','status','result'])test(`UI-001 solve refuses a stale ${stage} response`,async()=>{
 const h=await harness(),pending=deferred(),reached=deferred();
 h.c.respond=req=>{
  if(req.url==='/api/snapshots')return {revision:'2'};
  const at=req.url==='/api/jobs'?'enqueue':req.url.endsWith('/status')?'status':'result';
  if(at===stage){reached.resolve();return pending.promise;}
  return at==='enqueue'?{id:'j'}:jobResult();
 };
 const solving=h.run('solve()');await reached.promise;
 h.run("assignments=[{employee_id:'e',demand_id:'local',segments:[]}]; invalidateResult()");const before=h.state();
 pending.resolve(stage==='enqueue'?{id:'j'}:jobResult());await solving;
 assert.deepEqual(h.state().assignments,before.assignments);
 assert.doesNotMatch(h.get('result').textContent,/Vollständig und geprüft/);
 assert.equal(h.state().jobId,null);
});
test('UI-001 an unchanged solve still accepts the validated result',async()=>{
 const h=await harness();h.c.respond=req=>req.url==='/api/snapshots'?{revision:'2'}:req.url==='/api/jobs'?{id:'j'}:jobResult();
 await h.run('solve()');assert.deepEqual(h.state().assignments,jobResult().result.assignments);assert.equal(h.state().dirty,true);
});

const mutationButtons=[
 ['openDecisions','Grenze bei 150 % des Solls setzen','renderOpenDecisions()'],
 ...['Gruppe ausnehmen','Gruppe wieder einplanen','Gruppe als Ausbilder kennzeichnen','Gruppe unter Begleitung stellen','Begleitung wieder aufheben','Grenze aus dem Soll ableiten','Alle Grenzen aufheben'].map(label=>['teamScope',label,'renderTeamScope()']),
 ['teamTransferPreview','1 Personen aus der Tabelle übernehmen',"teamTransferReport={rows:1,changes:[{id:'e',name:'Person',update:{name:'CSV edit'}}],unchanged:0,errors:[]};teamTransferVersion=changeVersion;renderTeamTransfer()"],
 ['unresolved','Nach fachlicher Korrektur als geklärt markieren','renderUnresolved()'],
 ['unresolvedBulk','Alle 1 angezeigten Angaben als geprüft markieren','renderUnresolved()']
];
for(const busy of ['save','solve','import','restore'])for(const [box,label,draw] of mutationButtons)test(`UI-001 ${busy} guards original handler: ${label}`,async()=>{
 const s=fixture();s.unresolved=['Offene Angabe'];if(label==='Gruppe wieder einplanen')s.employees[0].excluded=true;if(label==='Alle Grenzen aufheben')s.employees[0].max_period_minutes=900;s.employees[0].approvals=[{function_id:'f',workplace_id:'*',supervised:true,valid_from:s.period_start,valid_until:s.period_end}];
 const h=await harness(s);h.run("Object.assign(teamScopeChoice,{gruppe:'t',ausbilder:'t',lernende:'t'})");h.run(draw);const b=h.button(box,label),before=h.state();
 h.run(busy==='solve'?"jobId='running'":busy==='restore'?'projectBusy=true':`$('${busy}').dataset.busy='true'`);h.run('updateJobButtons()');
 await b.onclick(); // Invoke original event even if browser inert would stop it.
 assert.deepEqual(h.state().snapshot,before.snapshot);assert.deepEqual(h.state().assignments,before.assignments);assert.equal(h.state().dirty,before.dirty);
});
for(const kind of ['field','select','date-demand','function-demand','absence','json'])test(`UI-001 locked ${kind} input cannot mutate the project`,async()=>{
 const s=fixture();s.positions=[{id:'p',name:'Day',function_id:'f',workplace_id:'*'}];s.shifts=[{id:'s',name:'Day',kind:'day',team_id:'t',paid_minutes:480,segments:[{start:'2026-10-01T08:00:00Z',end:'2026-10-01T16:00:00Z'}]}];s.demands=[{id:'d',shift_id:'s',position_id:'p',minimum:1,maximum:2}];
 const h=await harness(s);let input;
 if(kind==='field'){h.run('renderPeople()');input=h.document.querySelector('[data-employee-hours]');input.value='20';}
 if(kind==='select'){h.run('renderPeople()');input=h.get('people').querySelector('select');input.value='night';}
 if(kind==='date-demand'||kind==='function-demand'){h.run(kind==='date-demand'?'renderDemandBoard()':"switchDemandView('functions')");input=h.get('demandBoard').querySelector('.demand-value');input.value='3';}
 if(kind==='absence'){h.run('personDetails(snapshot.employees[0])');await h.button('details','Abwesenheit hinzufügen').onclick();input=h.get('details').querySelectorAll('input').find(i=>i.type==='datetime-local');input.value='2026-10-03T10:00';}
 if(kind==='json'){input=h.get('json');input.value='unapplied draft';}
 const before=h.state();h.run('projectBusy=true; updateJobButtons()');(input.oninput??input.onchange)();
 assert.deepEqual(h.state().snapshot,before.snapshot);assert.equal(h.state().jsonDirty,false);assert.equal(h.state().dirty,false);
});

function familyFixture(){const s=fixture();s.metadata.service_matrix_version=1;s.positions=[{id:'p1',function_id:'f1',workplace_id:'*',name:'Rufdienst 06-14'},{id:'p2',function_id:'f2',workplace_id:'*',name:'Rufdienst 14-22'}];s.employees[0].approvals=[{function_id:'f1',workplace_id:'restricted',valid_from:'2026-10-05',valid_until:'2026-10-20',supervised:true}];return s;}
for(const route of ['matrix','history'])test(`UI-003 ${route} expansion keeps supervision across all new family members`,async()=>{
 const s=familyFixture();s.metadata.history_matrix=[{employee_id:'e',suggested_approvals:[{function_id:'f2',workplace_id:'*'}]}];
 const h=await harness(s);if(route==='matrix')await h.get('matrix').querySelector('.matrix-cell').onclick();else await h.get('confirmHistory').onclick();
 const approvals=h.state().snapshot.employees[0].approvals;assert(approvals.some(a=>a.function_id==='f2'&&a.workplace_id==='*'));
 assert(approvals.every(a=>a.supervised),'no new unsupervised service or workplace-wide grant');assert.deepEqual(approvals[0],s.employees[0].approvals[0]);
});
for(const route of ['matrix','history'])test(`UI-003 ungrouped ${route} still inherits family supervision`,async()=>{
 const s=familyFixture();s.metadata.history_matrix=[{employee_id:'e',suggested_approvals:[{function_id:'f2',workplace_id:'*'}]}];
 const h=await harness(s),toggle=h.get('groupFamilies');toggle.checked=false;for(const handler of toggle.listeners.change)handler({target:toggle});
 if(route==='matrix')await h.get('matrix').querySelectorAll('.matrix-cell').find(b=>b.dataset.functionId==='f2').onclick();else await h.get('confirmHistory').onclick();
 const approvals=h.state().snapshot.employees[0].approvals;assert.deepEqual(approvals[0],s.employees[0].approvals[0]);
 assert.equal(approvals.find(a=>a.function_id==='f2')?.supervised,true,'display grouping is not an independent-work decision');
 assert.equal(approvals.length,2,'ungrouped action grants only the requested member');
});
for(const active of [true,false])test(`UI-003 specific workplace inherits only active covering supervision: ${active}`,async()=>{
 const s=fixture();s.positions=[{id:'p',name:'Duty',function_id:'f',workplace_id:'w'}];
 s.employees[0].approvals=[{function_id:'f',workplace_id:'*',supervised:true,valid_from:'2026-09-01',valid_until:active?s.period_end:'2026-09-30'}];
 const h=await harness(s);const cell=h.get('matrix').querySelectorAll('.matrix-cell').find(b=>b.dataset.functionId==='f'&&b.dataset.workplaceId==='w');assert(cell);await cell.onclick();
 const approvals=h.state().snapshot.employees[0].approvals;assert.deepEqual(approvals[0],s.employees[0].approvals[0]);
 assert.equal(approvals.find(a=>a.workplace_id==='w').supervised,active,'covering wildcard cannot be bypassed by a specific grant');
});
test('UI-003 family expansion preserves existing independent approval and ignores expired supervision',async()=>{
 const s=familyFixture();s.employees[0].approvals[0].valid_until='2026-09-30';s.employees[0].approvals.push({function_id:'f1',workplace_id:'*',valid_from:s.period_start,valid_until:s.period_end,supervised:false});
 const h=await harness(s);await h.get('matrix').querySelector('.matrix-cell').onclick();
 const approvals=h.state().snapshot.employees[0].approvals;assert.deepEqual(approvals.slice(0,2),s.employees[0].approvals);assert.equal(approvals[2].supervised,false);
});

for(const grouped of [true,false])test(`UI-R2-003 concrete history keeps family supervision and scope: grouped=${grouped}`,async()=>{
 const s=familyFixture();s.positions[0].workplace_id='w0';s.positions[1].workplace_id='w1';
 s.employees[0].approvals[0].workplace_id='*';
 s.metadata.history_matrix=[{employee_id:'e',suggested_approvals:[{function_id:'f2',workplace_id:'w1'}]}];
 const h=await harness(s),toggle=h.get('groupFamilies');toggle.checked=grouped;for(const handler of toggle.listeners.change)handler({target:toggle});
 await h.get('confirmHistory').onclick();
 const approvals=h.state().snapshot.employees[0].approvals,newGrants=approvals.slice(1);
 assert.equal(newGrants.find(a=>a.function_id==='f2')?.supervised,true,'a concrete history proposal still belongs to the supervised service family');
 assert.deepEqual(approvals[0],s.employees[0].approvals[0]);
 assert.deepEqual(newGrants.map(a=>[a.function_id,a.workplace_id,a.supervised]),grouped?[['f1','w1',true],['f2','w1',true]]:[['f2','w1',true]],'family expansion must retain the proposed workplace, not the matrix wildcard');
});

function scopedFamilyFixture(workplace,siblingWorkplace){
 const s=familyFixture();s.positions[0].workplace_id='w0';s.positions[1].workplace_id='w1';
 s.positions.push({id:'other',function_id:'other',workplace_id:'w1',name:'Unrelated activity'});
 s.employees[0].approvals=[{function_id:'f1',workplace_id:siblingWorkplace,valid_from:s.context_start,valid_until:s.context_end,supervised:true}];
 s.metadata.history_matrix=[{employee_id:'e',suggested_approvals:[{function_id:'f2',workplace_id:workplace}]}];return s;
}
async function toggleFamilies(h,grouped){const toggle=h.get('groupFamilies');toggle.checked=grouped;for(const handler of toggle.listeners.change)handler({target:toggle});}
for(const route of ['history','direct','matrix'])for(const grouped of [true,false])for(const workplace of route==='matrix'?['*']:['*','w1'])for(const siblingWorkplace of ['*','w1','w2'])test(`UI-R2-003 scope cross-product ${route} grouped=${grouped} grant=${workplace} sibling=${siblingWorkplace}`,async()=>{
 const s=scopedFamilyFixture(workplace,siblingWorkplace),h=await harness(s);await toggleFamilies(h,grouped);
 const before=h.state().snapshot.employees[0].approvals;
 if(route==='history')await h.get('confirmHistory').onclick();
 else if(route==='matrix')await h.get('matrix').querySelectorAll('.matrix-cell').find(b=>grouped?b.dataset.family==='Rufdienst':b.dataset.functionId==='f2').onclick();
 else h.run(`setApproval(snapshot.employees[0],{function_id:'f2',workplace_id:${JSON.stringify(workplace)}},true)`);
 const approvals=h.state().snapshot.employees[0].approvals,expectedSupervision=workplace==='*'||siblingWorkplace==='*'||workplace===siblingWorkplace;
 const expectedFunctions=grouped&&route!=='direct'?['f1','f2']:['f2'];
 const expectedNew=expectedFunctions.filter(id=>!before.some(a=>a.function_id===id&&a.workplace_id===workplace))
  .map(function_id=>({function_id,workplace_id:workplace,valid_from:s.period_start,valid_until:s.period_end,supervised:expectedSupervision}));
 assert.deepEqual(approvals,[...before,...expectedNew]);
});
for(const grouped of [true,false])for(const workplace of ['*','w1'])for(const control of ['past','future','period-start','period-end','unrelated-family','independent','existing-independent'])test(`UI-R2-003 history supervision control ${control} grouped=${grouped} grant=${workplace}`,async()=>{
 const s=scopedFamilyFixture(workplace,'*'),sibling=s.employees[0].approvals[0];
 if(control==='past')sibling.valid_until='2026-09-30';
 if(control==='future')sibling.valid_from='2026-11-01';
 if(control==='period-start')sibling.valid_until=s.period_start;
 if(control==='period-end')sibling.valid_from=s.period_end;
 if(control==='unrelated-family')sibling.function_id='other';
 if(control==='independent')sibling.supervised=false;
 if(control==='existing-independent')s.employees[0].approvals.push({function_id:'f2',workplace_id:workplace,valid_from:s.period_start,valid_until:s.period_end,supervised:false});
 const h=await harness(s);await toggleFamilies(h,grouped);await h.get('confirmHistory').onclick();
 const approvals=h.state().snapshot.employees[0].approvals;assert.deepEqual(approvals.slice(0,s.employees[0].approvals.length),s.employees[0].approvals);
 assert.equal(approvals.find(a=>a.function_id==='f2')?.supervised,['period-start','period-end'].includes(control),'inherit only overlapping supervision; preserve explicit independent grants');
 assert(approvals.slice(s.employees[0].approvals.length).every(a=>a.workplace_id===workplace),'history cannot widen the grant');
});
for(const serviceMode of [true,false])for(const workplace of ['*','w1'])test(`UI-R2-003 removal stays directional and period-sliced: service=${serviceMode} scope=${workplace}`,async()=>{
 const s=scopedFamilyFixture(workplace,'*');if(!serviceMode)delete s.metadata.service_matrix_version;
 s.employees[0].approvals=['*','w1','w2'].map(workplace_id=>({function_id:'f2',workplace_id,valid_from:'2026-09-01',valid_until:'2026-11-30',supervised:true}));
 s.employees[0].approvals.push({function_id:'f1',workplace_id:workplace,valid_from:'2026-09-01',valid_until:'2026-11-30',supervised:true});
 const h=await harness(s);h.run(`setApproval(snapshot.employees[0],{function_id:'f2',workplace_id:${JSON.stringify(workplace)}},false)`);
 const expected=s.employees[0].approvals.flatMap(a=>a.function_id==='f2'&&(a.workplace_id===workplace||(serviceMode&&workplace==='*'))
  ?[{...a,valid_until:'2026-09-30'},{...a,valid_from:'2026-11-01'}]:[a]);
 assert.deepEqual(h.state().snapshot.employees[0].approvals,expected,'removal must not use symmetric supervision overlap or expand the family');
});
for(const grouped of [true,false])test(`UI-R2-003 grouped history deduplicates only identical target scopes: grouped=${grouped}`,async()=>{
 const s=scopedFamilyFixture('w1','*');s.metadata.history_matrix[0].suggested_approvals.push({function_id:'f2',workplace_id:'w1'},{function_id:'f2',workplace_id:'w2'});
 const h=await harness(s);await toggleFamilies(h,grouped);await h.get('confirmHistory').onclick();
 const expected=grouped?[['f1','w1'],['f2','w1'],['f1','w2'],['f2','w2']]:[['f2','w1'],['f2','w2']];
 const approvals=h.state().snapshot.employees[0].approvals;assert.deepEqual(approvals.slice(1).map(a=>[a.function_id,a.workplace_id]),expected);assert(approvals.every(a=>a.supervised));
});

for(const grouped of [true,false])test(`UI-R2-003 position-mode families keep their original member scopes: grouped=${grouped}`,async()=>{
 const s=scopedFamilyFixture('w1','w0');delete s.metadata.service_matrix_version;
 const h=await harness(s);await toggleFamilies(h,grouped);await h.get('confirmHistory').onclick();
 const approvals=h.state().snapshot.employees[0].approvals;
 assert.deepEqual(approvals,[...s.employees[0].approvals,{function_id:'f2',workplace_id:'w1',valid_from:s.period_start,valid_until:s.period_end,supervised:true}],'without service normalization the existing position-family policy is unchanged');
});

function replacementFixture(){const s=fixture();s.employees.push(person('standby','Replacement'));s.assignments=[{employee_id:'e',demand_id:'d',segments:[]}];return s;}
const replacementReport=()=>({employee_id:'e',covers_whole_absence:['standby'],duties:[{demand_id:'d',date:'2026-10-10',shift_name:'Old shift',candidates:[{employee_id:'standby',days_since_last_duty:10}],blocked:{}}]});
for(const change of ['project','edit','person','dates'])test(`UI-004 replacement response is discarded after ${change}`,async()=>{
 const h=await harness(replacementFixture()),pending=deferred();h.run('renderReplacementForm()');h.c.respond=()=>pending.promise;const search=h.get('findReplacement').onclick();
 if(change==='project'){h.c.other=replacementFixture();h.c.other.id='B';h.c.other.period_start='2026-11-01';h.c.other.period_end='2026-11-30';h.run('load(other,true);renderReplacementForm()');}
 if(change==='edit')h.run('invalidateResult()');
 if(change==='person'){const input=h.get('replacementForm').querySelector('select');input.value='standby';input.onchange();}
 if(change==='dates'){const input=h.get('replacementForm').querySelector('input');input.value='2026-10-12';input.onchange();}
 pending.resolve(replacementReport());await search;assert.equal(h.get('replacementResult').textContent,'');
 if(change==='project'){assert.equal(h.run('replacementChoice.from'),'2026-11-01');assert.equal(h.run('replacementChoice.bis'),'2026-11-01');}
});
for(const change of ['edit','project','person','dates'])test(`UI-004 displayed replacement clears after ${change}`,async()=>{
 const h=await harness(replacementFixture());h.run('renderReplacementForm()');h.c.respond=()=>replacementReport();await h.get('findReplacement').onclick();assert.match(h.get('replacementResult').textContent,/Replacement/);
 if(change==='edit')h.run('invalidateResult()');
 if(change==='project'){h.c.other=fixture('B');h.run('load(other,true)');}
 if(change==='person'){const input=h.get('replacementForm').querySelector('select');input.value='standby';input.onchange();}
 if(change==='dates'){const input=h.get('replacementForm').querySelector('input');input.value='2026-10-12';input.onchange();assert.equal(h.state().dirty,false,'search dates are not project edits');}
 assert.equal(h.get('replacementResult').textContent,'');
});
for(const change of ['project','edit','rerender'])test(`UI-004 leverage response cannot fill a different ${change} target`,async()=>{
 const h=await harness(),pending=deferred();h.run('renderApprovalLeverage()');h.c.respond=()=>pending.promise;const search=h.button('approvalLeverage','Vorschau berechnen').onclick();
 if(change==='project'){h.c.other=fixture('B');h.run('load(other,true)');}else if(change==='edit')h.run('invalidateResult()');else h.get('result').replaceChildren();
 h.run('renderApprovalLeverage()');pending.resolve({rows:[]});await search;
 assert.equal(h.get('approvalLeverageResult').textContent,'');
});

function coverageFixture(){const s=fixture();s.employees.push(person('other'));s.positions=[{id:'p1',function_id:'f1',workplace_id:'*',name:'Short'},{id:'p2',function_id:'f2',workplace_id:'*',name:'Long'}];s.shifts=[480,720].map((paid_minutes,i)=>({id:'s'+i,name:'Service '+i,kind:'day',team_id:'t',paid_minutes,segments:[{start:'2026-10-01T08:00:00Z',end:'2026-10-01T16:00:00Z'}]}));s.demands=[{id:'d1',shift_id:'s0',position_id:'p1',minimum:1,maximum:1,alternative_group:'a'},{id:'d2',shift_id:'s1',position_id:'p2',minimum:1,maximum:1,alternative_group:'a'}];s.assignments=[{employee_id:'e',demand_id:'d2',segments:[]}];return s;}
test('UI-005 header counts one fully covered alternative post',async()=>{
 const h=await harness(coverageFixture());vm.runInContext(fs.readFileSync(path.join(STATIC,'workspace.js'),'utf8'),h.c,{filename:'workspace.js'});h.run('window.PlannerUI.refresh(plannerState())');
 assert.equal(h.get('metricCoverage').textContent,'100 %');assert.equal(h.get('metricAssignments').textContent,'1 / 1 Stellen');assert.equal(h.get('calcDemand').textContent,'1');
});
test('UI-005 calendar does not show an unchosen covered alternative as vacant',async()=>{
 const h=await harness(coverageFixture());h.get('planView').value='positions';h.run('renderCalendar()');assert.match(h.get('calendar').textContent,/1 \/ 1 erforderliche/);assert.equal(h.get('calendar').querySelectorAll('.vacancy-badge').length,0);
});
test('UI-005 empty alternative IDs are independent and duplicates do not fill extra slots',async()=>{
 const s=coverageFixture();s.demands[0].alternative_group='';s.demands[1].alternative_group=null;s.assignments.push(clone(s.assignments[0]),{employee_id:'missing',demand_id:'d1'});
 const h=await harness(s);h.get('planView').value='positions';h.run('renderCalendar()');assert.match(h.get('calendar').textContent,/1 \/ 2 erforderliche/);assert.equal(h.get('calendar').querySelectorAll('.vacancy-badge').length,1);
});
test('UI-005 minimum hours count the cheapest available alternative, respecting capacity',async()=>{
 const s=coverageFixture();s.demands[1].minimum=2;s.demands[1].maximum=2;
 const h=await harness(s);h.run('renderDemandSummary()');assert.equal(h.get('demandMinimumHours').dataset.value,'20');assert.match(h.get('demandSummary').textContent,/Alternativen.*Untergrenze/);
});

for(const query of ['Rufdienst 06-14','f1'])test(`UI-006 family search includes member name or ID: ${query}`,async()=>{
 const h=await harness(familyFixture());h.get('matrixSearch').value=query;h.run('renderMatrix()');const filtered=clone(h.run('matrixFiltered()'));assert.equal(filtered.positions.length,1);assert.equal(filtered.employees.length,1);assert.equal(filtered.positions[0].members.length,2);
});
test('UI-006 shortage shortcut finds the full service name in family mode',async()=>{
 const s=familyFixture();s.demands=[{id:'d',position_id:'p1',minimum:1}];const h=await harness(s);h.run("renderShortageSummary($('result'),[{demand_id:'d'}])");await h.button('result','Freigaben öffnen').onclick();assert.equal(h.run('matrixFiltered().positions.length'),1);assert.equal(h.run('matrixFiltered().employees.length'),1);
});

test('UI-007 person removal also deletes personal/boundary work and its provenance',async()=>{
 const s=replacementFixture();s.boundary_work=[{id:'personal',employee_id:'e',in_period:true,day:'2026-10-01',segments:[]},{id:'boundary',employee_id:'e',in_period:false,segments:[]},{id:'kept',employee_id:'standby',in_period:true,day:'2026-10-02',segments:[]}];s.metadata.provenance={e:{name:'person'},personal:{name:'personal'},boundary:{name:'context'},kept:{name:'keep'},other:{name:'unrelated'}};s.metadata.context_schedule=[{employee_id:'e'},{employee_id:'standby'}];s.wishes=[{employee_id:'e'},{employee_id:'standby'}];s.restrictions=clone(s.wishes);
 const h=await harness(s);let confirmation;h.c.window.confirm=text=>{confirmation=text;return true;};h.run('personDetails(snapshot.employees[0])');await h.get('removePerson').onclick();
 const after=h.state().snapshot;assert.deepEqual(after.boundary_work,[s.boundary_work[2]]);assert.deepEqual(after.metadata.provenance,{kept:s.metadata.provenance.kept,other:s.metadata.provenance.other});assert.match(confirmation,/2.*persönliche.*Rand/);assert.deepEqual(after.metadata.context_schedule,[{employee_id:'standby'}]);assert.deepEqual(after.wishes,[{employee_id:'standby'}]);assert.deepEqual(after.restrictions,[{employee_id:'standby'}]);assert.deepEqual(h.state().assignments,[]);
});
test('UI-007 cancelling removal preserves all references',async()=>{const s=replacementFixture();s.boundary_work=[{id:'work',employee_id:'e'}];const h=await harness(s);h.c.window.confirm=()=>false;const before=h.state();h.run('removePerson(snapshot.employees[0])');assert.deepEqual(h.state(),before);});

for(const name of ['=1+1','+1','-1','@sum(A1)','\t=1+1',' =1+1','＝1+1','Normal; "quoted"\nname'])test(`UI-008 missing-approvals CSV protects text: ${JSON.stringify(name)}`,async()=>{
 const s=fixture();s.employees[0].name=name;s.metadata.services=[{function_id:'f',name}];const h=await harness(s);let blob;h.c.download=content=>blob=content;
 h.run("renderPlanMetrics({missing_approvals:[{employee_id:'e',function_id:'f',blocked_demands:1,blocked_minutes:90},{employee_id:'=missing',function_id:'@fallback',blocked_demands:2,blocked_minutes:120}]})");await h.button('result','Fehlende Freigaben als CSV').onclick();
 const rows=h.c.TeamTransfer.parse(await blob.text());const expected=name.startsWith('Normal')?name:"'"+name;
 assert.deepEqual(rows[1],[expected,expected,'1','1,5']);assert.deepEqual(rows[2],["'=missing","'@fallback",'2','2']);
});

test('UI-001 team CSV preview is bound before its asynchronous file read',async()=>{
 const s=fixture();s.profiles=[{id:'p'}];s.employees[0].profile_ids=['p'];const h=await harness(s),pending=deferred();
 const csv=h.c.TeamTransfer.toCsv({...s,employees:[{...s.employees[0],name:'CSV changed'}]});h.get('teamImport').files=[{size:csv.length,text:()=>pending.promise}];
 const importing=h.get('teamImport').onchange();h.c.other=clone(s);h.c.other.id='B';h.run('load(other,true)');pending.resolve(csv);await importing;
 assert.equal(h.run('teamTransferReport'),null);assert.equal(h.get('teamTransferPreview').textContent,'');assert.equal(h.state().dirty,false);
});
for(const first of ['file','save'])test(`UI-001 overlapping CSV read/save releases locks: ${first} first`,async()=>{
 const s=fixture();s.profiles=[{id:'p'}];s.employees[0].profile_ids=['p'];const h=await harness(s),file=deferred(),put=deferred();
 const csv=h.c.TeamTransfer.toCsv(s);h.get('teamImport').files=[{size:csv.length,text:()=>file.promise}];
 const importing=h.get('teamImport').onchange();h.c.respond=()=>put.promise;const saving=h.get('save').onclick();
 assert.equal(h.get('teamImport').disabled,true);
 if(first==='file'){file.resolve(csv);await importing;}else{put.resolve({revision:'2'});await saving;}
 assert.equal(h.get('teamImport').disabled,true,'the remaining operation still holds its lock');
 if(first==='file'){put.resolve({revision:'2'});await saving;}else{file.resolve(csv);await importing;}
 assert.equal(h.get('teamImport').dataset.busy,undefined);assert.equal(h.get('teamImport').disabled,false,'CSV chooser is usable after both completions');
 assert.equal(h.get('save').disabled,false);assert.equal(h.run('projectSwitchBusy()'),false);assert.equal(h.state().dirty,false);
});
test('UI-001 failed save releases controls and preserves dirty input',async()=>{
 const h=await harness();h.run('invalidateResult();renderOpenDecisions()');h.c.respond=()=>{throw Error('synthetic failure');};await h.get('save').onclick();
 assert.equal(h.state().dirty,true);assert.equal(h.get('openDecisions').inert,false);assert.equal(h.get('save').disabled,false);assert.equal(h.state().snapshot.revision,'1');
});
test('UI-001 restored job binds the cloned input and applies its own valid result',async()=>{
 const h=await harness();h.c.respond=req=>req.url.endsWith('/snapshot')?fixture('stored'):req.url==='/api/snapshots/check'?req.data:jobResult();
 await h.run("openJob('restored')");assert.equal(h.state().snapshot.metadata.restored_from_job,'restored');assert.notEqual(h.state().snapshot.id,'stored');assert.deepEqual(h.state().assignments,jobResult().result.assignments);
});

for(const change of ['same-id-reload','revision','unversioned','json-draft','person-draft'])test(`UI-001 pending result rejects changed basis: ${change}`,async()=>{
 const h=await harness(),pending=deferred(),reached=deferred();h.c.respond=req=>{if(req.url==='/api/snapshots')return {revision:'2'};if(req.url==='/api/jobs')return {id:'j'};if(req.url.endsWith('/status'))return jobResult();reached.resolve();return pending.promise;};
 const solving=h.run('solve()');await reached.promise;
 if(change==='same-id-reload'){h.c.other=fixture();h.run('load(other,true)');}
 if(change==='revision')h.run("snapshot.revision='99'");
 if(change==='unversioned')h.run('snapshot.employees[0].target_minutes=43');
 if(change==='json-draft')h.run('jsonDirty=true');
 if(change==='person-draft')h.run('personDraft=true');
 const before=h.state();pending.resolve(jobResult());await solving;assert.deepEqual(h.state().snapshot,before.snapshot);assert.deepEqual(h.state().assignments,before.assignments);assert.equal(h.state().jobId,null);
});
test('UI-004 older replacement request cannot replace a newer report',async()=>{
 const h=await harness(replacementFixture()),old=deferred();h.run('renderReplacementForm()');h.c.respond=()=>old.promise;const first=h.get('findReplacement').onclick();
 h.run('renderReplacementForm()');h.c.respond=()=>({...replacementReport(),duties:[]});await h.get('findReplacement').onclick();const text=h.get('replacementResult').textContent;
 old.resolve(replacementReport());await first;assert.match(text,/keinen Dienst/);assert.equal(h.get('replacementResult').textContent,text);
});
for(const count of [0,1,3])test(`UI-005 alternative coverage caps at group minimum: ${count} staffed`,async()=>{
 const s=coverageFixture();s.demands[1].minimum=2;s.demands[1].maximum=3;s.employees.push(person('third'));s.assignments=s.employees.slice(0,count).map((p,i)=>({employee_id:p.id,demand_id:i%2?'d1':'d2',segments:[]}));
 const h=await harness(s);h.get('planView').value='positions';h.run('renderCalendar()');assert.match(h.get('calendar').textContent,new RegExp(`${Math.min(count,2)} / 2 erforderliche`));const badges=h.get('calendar').querySelectorAll('.vacancy-badge');assert.equal(badges.length,count<2?1:0);if(count<2)assert.equal(badges[0].textContent,`${2-count} offen`);
});
for(const [capacity,hours] of [[0,24],[1,20],[null,16]])test(`UI-005 minimum-hour bound respects short-variant capacity ${capacity}`,async()=>{
 const s=coverageFixture();s.demands[0].minimum=0;s.demands[0].maximum=capacity;s.demands[1].minimum=2;s.demands[1].maximum=2;const h=await harness(s);h.run('renderDemandSummary()');assert.equal(Number(h.get('demandMinimumHours').dataset.value),hours);
});
test('UI-005 literal group IDs never collide with independent demands',async()=>{
 const h=await harness();const actual=clone(h.run(`staffingGroups([{id:'x',minimum:1},{id:'y',minimum:2,alternative_group:'x'},{id:'z',minimum:3,alternative_group:' x'}]).map(g=>g.minimum)`));assert.deepEqual(actual,[1,2,3]);
});

function boundedReport(shown){return {diagnostics:Array.from({length:shown},(_,i)=>({code:'unresolved',message:'Synthetic issue '+i})),diagnostics_total:3,diagnostics_omitted:3-shown,diagnostics_by_code:{unresolved:3}};}
for(const shown of [0,1])test(`SEC-04 automatic readiness respects bounded diagnostics: ${shown} shown`,async()=>{
 const h=await harness();h.c.respond=()=>({ready:false,...boundedReport(shown)});h.run("activePanel='calculate';refreshAutomaticReadiness(true)");await new Promise(r=>setImmediate(r));
 assert.equal(h.get('automaticReadinessStatus').dataset.state,'issues','a truncated report is not a failed request');assert.equal(h.state().readiness.count,3);
 assert.match(h.get('automaticReadinessStatus').textContent,/3 Hinweise/);assert.match(h.get('automaticReadinessDetails').textContent,new RegExp(`${shown}.*angezeigt.*${3-shown}.*ausgelassen`));
 assert.equal(h.get('retryReadiness').hidden,true);
});
for(const report of [
 {ready:true,diagnostics:[],diagnostics_total:1,diagnostics_omitted:1},
 {ready:false,...boundedReport(1),diagnostics_total:0},
 {ready:false,...boundedReport(1),diagnostics_omitted:0},
 {ready:false,...boundedReport(1),diagnostics_total:'3'},
])test(`SEC-04 inconsistent readiness counts fail closed: ${JSON.stringify(report)}`,async()=>{
 const h=await harness();h.c.respond=()=>report;h.run("activePanel='calculate';refreshAutomaticReadiness(true)");await new Promise(r=>setImmediate(r));
 assert.equal(h.get('automaticReadinessStatus').dataset.state,'error');assert.equal(h.get('retryReadiness').hidden,false);
});
for(const shown of [0,1])test(`SEC-04 manual readiness reports omitted diagnostics: ${shown} shown`,async()=>{
 const h=await harness();h.c.respond=()=>({ready:false,...boundedReport(shown)});h.run('renderSetupReview()');await h.button('setupReview','Planungsbereitschaft prüfen').onclick();
 assert.equal(h.state().readiness.state,'issues');assert.equal(h.state().readiness.count,3);
 assert.match(h.get('setupReview').textContent,new RegExp(`${shown}.*angezeigt.*${3-shown}.*ausgelassen`));
});
for(const valid of [false,true])for(const shown of [0,1])test(`SEC-04 validation never calls a bounded sample clean: valid=${valid}, shown=${shown}`,async()=>{
 const h=await harness();h.c.report={valid,complete:false,...boundedReport(shown)};h.run('renderValidation(report)');const text=h.get('validationSummary').textContent;
 assert.match(text,valid?/Gültiger Teilplan/:/Regelverletzungen müssen korrigiert/);
 assert.doesNotMatch(text,/keine Regelverletzungen oder unbesetzten Stellen/);
 assert.match(text,new RegExp(`${shown}.*angezeigt.*${3-shown}.*ausgelassen`));
});
test('SEC-04 validation flags reject a clean label even without legacy detail counts',async()=>{
 const h=await harness();h.c.report={valid:false,complete:false,diagnostics:[]};h.run('renderValidation(report)');assert.doesNotMatch(h.get('validationSummary').textContent,/keine Regelverletzungen oder unbesetzten Stellen/);
});
test('SEC-04 complete clean legacy validation still has its clean label',async()=>{
 const h=await harness();h.c.report={valid:true,complete:true,diagnostics:[]};h.run('renderValidation(report)');assert.match(h.get('validationSummary').textContent,/keine Regelverletzungen oder unbesetzten Stellen/);
});

test('UI-001 save acknowledges only the transmitted version and keeps newer edits dirty',async()=>{
 const h=await harness(),pending=deferred();let sent;
 h.c.respond=req=>{assert.equal(req.url,'/api/snapshots');sent=req.data;return pending.promise;};
 const saving=h.run('save()');assert(sent);
 // A late editor/event must not be acknowledged by a response to an older PUT.
 h.run('snapshot.employees[0].max_period_minutes=900; invalidateResult()');
 pending.resolve({revision:'2'});await saving;
 assert.equal(sent.employees[0].max_period_minutes,null);
 assert.equal(h.state().snapshot.employees[0].max_period_minutes,900);
 assert.equal(h.state().dirty,true);
 assert.match(h.get('saveStatus').textContent,/Ungespeicherte/);
 assert.equal(h.state().snapshot.revision,'2');
});
