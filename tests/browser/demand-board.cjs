'use strict';
// Newly constructed synthetic project only; the server is the local browser fixture.
const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async function demandBoard({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 const days=Array.from({length:7},(_,i)=>`2026-01-${String(i+5).padStart(2,'0')}`);
 const fixture={
  schema_version:'1.0',id:'synthetic-demand-board',revision:'0',created_at:'2026-01-01T00:00:00Z',
  timezone:'UTC',period_start:days[0],period_end:days[6],context_start:'2025-12-28',context_end:'2026-01-19',
  context_complete:true,rule_version:'synthetic-1',software_versions:{},source:'synthetic',
  employees:[6000,3600,0].map((target,i)=>({
   id:`person-${i}`,name:`Testperson ${i+1}`,team_ids:['team-a'],employment_start:'2025-01-01',employment_end:'2027-12-31',
   approvals:[],qualifications:[],availability:[],unavailable:[],allowed_kinds:['day','night'],preferred_kind:null,
   preferred_functions:[],allow_weekends:true,allow_holidays:true,profile_ids:['synthetic-profile'],target_minutes:target,
   contractual_weekly_minutes:null,balance_minutes:0,credit_minutes:0,employment_fraction:100,
   historical_nights:0,historical_weekends:0,historical_holidays:0,mentor_capacity:0,
  })),
  profiles:[{id:'synthetic-profile',valid_from:'2025-12-28',valid_until:'2026-01-19',min_rest_minutes:660,weekly_rest_minutes:2160,confirmed:true,source:'synthetic'}],
  positions:['a','b'].map(name=>({id:`position-${name}`,name:`Dienst ${name.toUpperCase()}`,function_id:`service-${name}`,workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false})),
  shifts:[],demands:[],assignments:[],boundary_work:[],restrictions:[],wishes:[],objectives:{},unresolved:[],metadata:{},
 };
 function addShift(id,name,day,start,end,paid){fixture.shifts.push({id,name,kind:'day',team_id:'team-a',segments:[{start:`${day}T${start}:00Z`,end:`${day}T${end}:00Z`}],paid_minutes:paid,holiday:false,source:'synthetic'});}
 function addDemand(id,shift,position,minimum,maximum){fixture.demands.push({id,shift_id:shift,position_id:position,minimum,maximum,team_ids:['team-a'],alternative_group:null,source:'synthetic'});}
 days.forEach((day,i)=>{
  addShift(`a-day-${i}`,'Dienst A',day,'08:00','16:00',480);
  if(i!==2)addDemand(`d-a-${i}`,`a-day-${i}`,'position-a',1,2);
 });
 addShift('a-late','Dienst A',days[0],'16:00','22:00',360);addDemand('d-a-late','a-late','position-a',2,2);
 for(let i=0;i<2;i++)addShift(`b-day-${i}`,'Dienst B',days[i],'08:00','12:00',240);
 addDemand('d-b-0','b-day-0','position-b',1,1);
 await page.evaluate(value=>load(value,true),fixture);
 async function navigate(panel){await page.locator(`.main-nav [data-navigate="${panel}"]`).click();await page.locator(`[data-panel="${panel}"]`).waitFor({state:'visible'});}
 await navigate('demand');
 const table=page.locator('#demandBoard table.demand-table');
 const rows=table.locator('tbody tr[data-demand-row]');
 const dayRow=rows.filter({has:page.locator('th.demand-row',{hasText:'Dienst A'})}).filter({has:page.locator('th.demand-row',{hasText:'08:00'})});
 const lateRow=rows.filter({has:page.locator('th.demand-row',{hasText:'Dienst A'})}).filter({has:page.locator('th.demand-row',{hasText:'16:00'})}).filter({hasNot:page.locator('th.demand-row',{hasText:'08:00'})});
 const otherRow=rows.filter({has:page.locator('th.demand-row',{hasText:'Dienst B'})});
 const cell=(row,day)=>row.locator(`td[data-demand-day="${day}"]`);
 const value=(row,day)=>cell(row,day).locator('input.demand-value');
 async function edit(row,day,minimum){await value(row,day).fill(String(minimum));await value(row,day).blur();}
 const demands=()=>page.evaluate(()=>structuredClone(snapshot.demands));
 const number=async selector=>Number((await page.locator(selector).innerText()).replace(/\./g,'').replace(',','.').replace(/[^\d.-]/g,''));
 // Die Sammelbearbeitung ist eingeklappt; für die Prüfung zuerst öffnen.
 async function openBulk(row){await row.evaluate(node=>{const box=node.querySelector('details.demand-row-bulk');if(box)box.open=true;});}
 async function reset(row){await openBulk(row);await row.getByRole('button',{name:'Zeile zurücksetzen',exact:true}).click();}
 async function bulk(row,minimum,label){await openBulk(row);await row.locator('input.demand-bulk-value').fill(String(minimum));await row.getByRole('button',{name:label,exact:true}).click();}

 // One row per service/time pattern, with the inclusive planning period as columns.
 assert.equal(await rows.count(),3,'Repeated daily shifts form one row; different names or times remain separate');
 assert.equal(await dayRow.count(),1);assert.equal(await lateRow.count(),1);assert.equal(await otherRow.count(),1);
 assert.equal(await table.locator('thead tr th').count(),days.length+1,'A pattern column plus every calendar day');
 for(const row of [dayRow,lateRow,otherRow])assert.deepEqual(await row.locator('td[data-demand-day]').evaluateAll(cells=>cells.map(cell=>cell.dataset.demandDay)),days);
 const headings=await table.locator('thead tr th').allTextContents();
 for(let i=0;i<days.length;i++){
  assert.match(headings[i+1],new RegExp(['Mo','Di','Mi','Do','Fr','Sa','So'][i]),'Headers include weekdays');
  assert.match(headings[i+1],new RegExp(`${String(i+5).padStart(2,'0')}\\.01\\.`),'Headers include calendar dates');
 }
 assert.deepEqual(await table.locator('thead th.weekend').evaluateAll(cells=>cells.map(cell=>cell.dataset.demandDay)),days.slice(5),'Weekend headers are visibly distinguished');
 for(const row of [dayRow,lateRow,otherRow])assert.deepEqual(await row.locator('td.weekend').evaluateAll(cells=>cells.map(cell=>cell.dataset.demandDay)),days.slice(5),'Weekend columns remain marked through the entire matrix');
 assert.deepEqual(await page.locator('.main-nav [data-navigate]').evaluateAll(buttons=>buttons.map(button=>button.dataset.navigate)).then(panels=>panels.slice(panels.indexOf('rules'),panels.indexOf('calculate')+1)),['rules','demand','calculate']);
 const initialState=await page.evaluate(()=>({dirty,version:changeVersion,snapshot:currentSnapshot()}));
 await navigate('team');await navigate('demand');
 assert.deepEqual(await page.evaluate(()=>({dirty,version:changeVersion,snapshot:currentSnapshot()})),initialState,'Opening the board is read-only');
 assert.equal(await value(dayRow,days[2]).inputValue(),'','An existing shift without demand starts empty');
 assert.equal(await value(dayRow,days[2]).isEnabled(),true,'An existing matching shift permits creating demand');

 // Paid shift minutes times minimum staffing are compared with every period target.
 assert.equal(await number('#demandMinimumHours'),64);assert.equal(await number('#demandContractHours'),160);assert.equal(await number('#demandRatio'),40);
 // Somebody taken out of the plan brings no contract hours to this comparison.
 const wieder=await page.evaluate(()=>{const e=snapshot.employees.find(e=>e.target_minutes);e.excluded=true;renderDemandSummary();return e.target_minutes/60;});
 assert.equal(await number('#demandContractHours'),160-wieder);
 await page.evaluate(()=>{snapshot.employees.find(e=>e.excluded).excluded=false;renderDemandSummary();});
 assert.equal(await number('#demandContractHours'),160);
 assert.equal(await page.locator('#demandSummary').getAttribute('data-balance'),'low');
 assert.equal(await page.locator('#demandSummary').evaluate(element=>element.classList.contains('warning')),true);
 assert.match(await page.locator('#demandBalanceNote').innerText(),/unbeschäftigt/i);

 const beforeEdit=await demands();
 await edit(dayRow,days[0],3);
 const expectedEdit=structuredClone(beforeEdit);Object.assign(expectedEdit.find(demand=>demand.id==='d-a-0'),{minimum:3,maximum:3,source:'override'});
 assert.deepEqual(await demands(),expectedEdit,'Only the selected demand changes; a finite maximum permits the new minimum');
 assert.equal(await cell(dayRow,days[0]).getAttribute('data-source'),'override');
 assert.equal(await cell(dayRow,days[0]).evaluate(element=>element.classList.contains('overridden')),true);
 assert.equal(await page.evaluate(()=>dirty),true);
 assert(await page.evaluate(version=>changeVersion>version,initialState.version));
 assert.match(await page.locator('#result').textContent(),/Erneut prüfen oder berechnen/);
 assert.match(await page.locator('#validation').textContent(),/nicht aktuell/);
 assert.equal(await number('#demandMinimumHours'),80);assert.equal(await number('#demandRatio'),50,'The balance recalculates immediately after editing');
 for(const invalid of [-1,1.5]){
  await edit(dayRow,days[0],invalid);
  assert.deepEqual(await demands(),expectedEdit,'Negative and fractional staffing never enter the snapshot');
 }
 await edit(dayRow,days[0],3);

 const beforeWeekend=await demands();
 await bulk(dayRow,4,'Nur Wochenenden');
 const expectedWeekend=structuredClone(beforeWeekend);
 for(const demand of expectedWeekend)if(['d-a-5','d-a-6'].includes(demand.id))Object.assign(demand,{minimum:4,maximum:4,source:'override'});
 assert.deepEqual(await demands(),expectedWeekend,'The weekend action changes only Saturday and Sunday in the chosen pattern');
 assert.equal(await value(dayRow,days[2]).inputValue(),'','Weekend editing never fills a weekday gap');
 assert.equal(await number('#demandRatio'),80);
 assert.equal(await page.locator('#demandSummary').getAttribute('data-balance'),'balanced','Exactly 80 percent is within the stated range');
 await reset(dayRow);
 assert.deepEqual(await demands(),fixture.demands,'Reset restores imported minimum, maximum and source');
 assert.equal(await dayRow.locator('td.overridden').count(),0);
 assert.equal(await number('#demandMinimumHours'),64);

 await edit(dayRow,days[2],2);
 const created=(await demands()).filter(demand=>!fixture.demands.some(original=>original.id===demand.id));
 assert.equal(created.length,1);
 assert.equal(created[0].shift_id,'a-day-2');assert.equal(created[0].position_id,'position-a');
 assert.equal(created[0].minimum,2);assert.equal(created[0].source,'override');
 assert(created[0].maximum===null||created[0].maximum>=2);
 assert.equal(await cell(dayRow,days[2]).getAttribute('data-source'),'override');
 await reset(dayRow);
 assert.deepEqual(await demands(),fixture.demands,'Reset removes newly created demands and restores the empty cell');
 assert.equal(await value(dayRow,days[2]).inputValue(),'');

 await bulk(dayRow,2,'Nur Werktage');
 const weekdays=await demands();
 for(let i=0;i<days.length;i++)assert.equal(weekdays.find(demand=>demand.shift_id===`a-day-${i}`).minimum,i<5?2:1,'Weekday editing excludes Saturday and Sunday');
 await reset(dayRow);
 assert.deepEqual(await demands(),fixture.demands);

 // A day without a matching shift is disabled, explains why, and is skipped in bulk.
 assert.equal(await value(otherRow,days[2]).isDisabled(),true);
 const unavailable=await cell(otherRow,days[2]).evaluate(element=>[element.textContent,element.title,...[...element.querySelectorAll('[title],[aria-label]')].flatMap(child=>[child.title,child.getAttribute('aria-label')])].join(' '));
 assert.match(unavailable,/kein(?:e[nrms]?)?\s+(?:passender?\s+)?Dienst/i);
 await bulk(otherRow,2,'Alle Tage');
 const allDays=await demands();
 assert.deepEqual(allDays.filter(demand=>demand.position_id==='position-a'),fixture.demands.filter(demand=>demand.position_id==='position-a'),'A row action leaves every other pattern untouched');
 assert.deepEqual(allDays.filter(demand=>demand.position_id==='position-b').map(demand=>[demand.shift_id,demand.minimum]).sort(),[['b-day-0',2],['b-day-1',2]]);
 assert.equal(await value(otherRow,days[2]).isDisabled(),true);assert.equal(await value(otherRow,days[2]).inputValue(),'');
 await reset(otherRow);
 assert.deepEqual(await demands(),fixture.demands);

 await bulk(dayRow,10,'Alle Tage');
 assert.equal(await number('#demandMinimumHours'),576);assert.equal(await number('#demandRatio'),360);
 assert.equal(await page.locator('#demandSummary').getAttribute('data-balance'),'high');
 assert.equal(await page.locator('#demandSummary').evaluate(element=>element.classList.contains('warning')),true);
 assert.match(await page.locator('#demandBalanceNote').innerText(),/Stellen.*offen/i);
 await reset(dayRow);

 // The normal save and load path persists overrides without extra demand fields.
 await edit(dayRow,days[0],3);
 const changed=await demands();
 await navigate('team');
 const savedResponse=page.waitForResponse(response=>response.url().endsWith('/api/snapshots')&&response.request().method()==='PUT');
 await page.click('#save');
 const saved=await savedResponse;assert.equal(saved.status(),200);
 assert.deepEqual((await saved.json()).demands,changed,'The existing project save stores the board edits');
 await page.waitForFunction(()=>document.querySelector('#save').dataset.busy!=='true');
 assert.equal(await page.evaluate(()=>dirty),false);
 await page.evaluate(async id=>load(await api('/api/snapshots/'+encodeURIComponent(id)),true),fixture.id);
 await navigate('demand');
 assert.deepEqual(await demands(),changed);
 assert.equal(await value(dayRow,days[0]).inputValue(),'3');
 assert.equal(await cell(dayRow,days[0]).getAttribute('data-source'),'override');
 assert.equal(await cell(dayRow,days[0]).evaluate(element=>element.classList.contains('overridden')),true);
 assert.equal(await number('#demandMinimumHours'),80);assert.equal(await number('#demandRatio'),50);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'The matrix scrolls within the page at '+width);
  if(process.env.WEB_TEST_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.WEB_TEST_SCREENSHOT_DIR,`demand-board-${width}.png`),fullPage:true});
 }

 // One service/time cell can contain several workplace demands. Redistribution
 // retains the source proportions even after a smaller total has rounded down.
 const aggregate=structuredClone(fixture);aggregate.id+='-aggregate';
 aggregate.positions.push({...aggregate.positions[0],id:'position-a-second',workplace_id:'workplace-b'});
 aggregate.demands.push({id:'d-a-second',shift_id:'a-day-0',position_id:'position-a-second',minimum:1,maximum:null,team_ids:['team-a'],alternative_group:null,source:'synthetic'});
 await page.evaluate(value=>load(value,true),aggregate);await navigate('demand');
 assert.equal(await rows.count(),3,'Several workplace demands still form one service/time row');
 assert.equal(await value(dayRow,days[0]).inputValue(),'2','The cell displays the sum of workplace minima');
 await edit(dayRow,days[0],1);
 let shares=(await demands()).filter(demand=>demand.shift_id==='a-day-0');
 assert.deepEqual(shares.map(demand=>demand.minimum),[1,0],'Integer distribution follows a stable order');
 assert(shares.every(demand=>demand.source==='override'));
 await edit(dayRow,days[0],2);
 shares=(await demands()).filter(demand=>demand.shift_id==='a-day-0');
 assert.deepEqual(shares.map(demand=>demand.minimum),[1,1],'Raising the total restores the original proportions instead of retaining the rounded split');
 assert.deepEqual(shares.map(demand=>demand.maximum),[2,null],'Existing finite and unbounded maxima are retained');
 await edit(dayRow,days[0],0);await edit(dayRow,days[0],2);
 assert.deepEqual((await demands()).filter(demand=>demand.shift_id==='a-day-0').map(demand=>demand.minimum),[1,1],'Original weights also survive an intermediate zero');
 await reset(dayRow);assert.deepEqual(await demands(),aggregate.demands);

 // Calendar grouping uses the project's local start day, including UTC dates
 // on the preceding day and duties that end on the following local day.
 const zoned=structuredClone(fixture);zoned.id+='-timezone';zoned.timezone='Pacific/Auckland';
 zoned.positions=zoned.positions.slice(0,1);zoned.shifts=[];zoned.demands=[];
 function zonedShift(id,name,start,end){
  zoned.shifts.push({...fixture.shifts[0],id,name,segments:[{start,end}]});
  zoned.demands.push({id:`d-${id}`,shift_id:id,position_id:'position-a',minimum:1,maximum:2,team_ids:['team-a'],alternative_group:null,source:'synthetic'});
 }
 zonedShift('night-0','Nachtdienst','2026-01-05T10:00:00Z','2026-01-05T18:00:00Z');
 zonedShift('night-1','Nachtdienst','2026-01-06T10:00:00Z','2026-01-06T18:00:00Z');
 zonedShift('early','Frühdienst','2026-01-04T11:30:00Z','2026-01-04T19:30:00Z');
 zonedShift('context','Nachtdienst','2026-01-04T10:00:00Z','2026-01-04T18:00:00Z');
 await page.evaluate(value=>load(value,true),zoned);await navigate('demand');
 assert.equal(await rows.count(),2);
 const nightRow=rows.filter({has:page.locator('th.demand-row',{hasText:'Nachtdienst'})});
 const earlyRow=rows.filter({has:page.locator('th.demand-row',{hasText:'Frühdienst'})});
 assert.match(await nightRow.locator('th.demand-row').innerText(),/23:00–07:00.*Folgetag/);
 assert.equal(await value(nightRow,days[0]).inputValue(),'1');assert.equal(await value(nightRow,days[1]).inputValue(),'1');
 assert.equal(await value(nightRow,days[2]).isDisabled(),true,'A night shift belongs to its local start day only');
 assert.equal(await value(earlyRow,days[0]).inputValue(),'1','A previous UTC date is still the correct local planning date');
 assert.equal(await number('#demandMinimumHours'),24,'Demand starting before the planning period is excluded');
 await edit(nightRow,days[0],2);
 assert.equal((await demands()).find(demand=>demand.id==='d-night-0').minimum,2);
 assert.equal((await demands()).find(demand=>demand.id==='d-context').minimum,1);
 assert.equal(await number('#demandMinimumHours'),32);

 const noTarget=structuredClone(fixture);noTarget.id+='-no-target';noTarget.employees.forEach(person=>person.target_minutes=0);
 await page.evaluate(value=>load(value,true),noTarget);await navigate('demand');
 assert.equal(await number('#demandContractHours'),0);
 assert.equal(await page.locator('#demandSummary').getAttribute('data-balance'),'no-target');
 assert.equal(await page.locator('#demandSummary').evaluate(element=>element.classList.contains('warning')),false);
 assert.equal((await page.locator('#demandRatio').innerText()).trim(),'—');
 assert.match(await page.locator('#demandBalanceNote').innerText(),/Kein Vertragssoll/);
 // An unfinished target cannot manufacture a ratio from missing hours.
 noTarget.employees[0].target_minutes=null;
 await page.evaluate(value=>load(value,true),noTarget);await navigate('demand');
 assert.equal(await number('#demandContractHours'),0);
 assert.equal(await page.locator('#demandSummary').getAttribute('data-balance'),'no-target');
 assert.doesNotMatch(await page.locator('#demandSummary').innerText(),/NaN|Infinity/);
 assert.deepEqual(errors,[]);
 console.log('Demand board: service/time rows, calendar columns, direct and bulk overrides, reset, hours balance, missing shifts and project persistence passed.');
};
