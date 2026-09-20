'use strict';
// Constructed synthetic data, served only by the local browser fixture.
const assert=require('node:assert/strict');

module.exports=async function planningControls({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 const days=Array.from({length:7},(_,i)=>`2026-01-${String(i+5).padStart(2,'0')}`);
 const fixture={
  schema_version:'1.0',id:'synthetic-planning-controls',revision:'0',created_at:'2026-01-01T00:00:00Z',
  timezone:'UTC',period_start:days[0],period_end:days[6],context_start:'2025-12-28',context_end:'2026-01-19',
  context_complete:true,rule_version:'synthetic-1',software_versions:{},source:'synthetic',
  employees:[6000,3600,1200].map((target,i)=>({
   id:`person-${i}`,name:`Gruppe ${i===1?'B':'A'} ${i+1}`,team_ids:['team-a'],employment_start:'2025-01-01',employment_end:'2027-12-31',
   approvals:[{function_id:'service-a',workplace_id:'*',valid_from:'2025-01-01',valid_until:'2027-12-31',supervised:false}],
   qualifications:[],availability:[],unavailable:[],allowed_kinds:['day','night'],preferred_kind:null,
   preferred_functions:[],allow_weekends:true,allow_holidays:true,profile_ids:['synthetic-profile'],target_minutes:target,
   contractual_weekly_minutes:1200,balance_minutes:120,credit_minutes:60,employment_fraction:50,
   historical_nights:2,historical_weekends:3,historical_holidays:1,mentor_capacity:0,
  })),
  profiles:[{id:'synthetic-profile',valid_from:'2025-12-28',valid_until:'2026-01-19',min_rest_minutes:660,weekly_rest_minutes:2160,confirmed:true,source:'synthetic'}],
  positions:[
   {id:'position-a',name:'Funktion A',function_id:'service-a',workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false},
   {id:'position-a-second',name:'Funktion A anderer Arbeitsplatz',function_id:'service-a',workplace_id:'workplace-b',qualification_ids:[],qualification_level:1,qualifications_required:false},
   {id:'position-b',name:'Funktion B',function_id:'service-b',workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false},
  ],
  shifts:[],demands:[],assignments:[],boundary_work:[],restrictions:[],wishes:[],objectives:{},unresolved:[],
  metadata:{history_matrix:[{employee_id:'person-0',observed_assignment_count:3,first_date:'2025-12-01',last_date:'2025-12-20',observed_shifts:[{name:'Dienst A',count:3}],suggested_approvals:[]}]},
 };
 function shift(id,name,day,start,end,paid,holiday=false){fixture.shifts.push({id,name,kind:'day',team_id:'team-a',segments:[{start:`${day}T${start}:00Z`,end:`${day}T${end}:00Z`}],paid_minutes:paid,holiday,source:'synthetic'});}
 function demand(id,shiftId,positionId,minimum=1){fixture.demands.push({id,shift_id:shiftId,position_id:positionId,minimum,maximum:2,team_ids:['team-a'],alternative_group:null,source:'synthetic'});}
 days.forEach((day,i)=>{
  shift(`a-${i}`,'Dienst A',day,'08:00','16:00',480,i===1);demand(`d-a-${i}`,`a-${i}`,'position-a');
  shift(`b-${i}`,'Dienst B',day,'08:00','12:00',240);demand(`d-b-${i}`,`b-${i}`,'position-b');
 });
 demand('d-a-second','a-0','position-a-second',2);
 shift('a-late','Dienst A spät',days[0],'16:00','22:00',360);demand('d-a-late','a-late','position-a',2);
 for(const [id,day] of [['before','2026-01-04'],['after','2026-01-12']]){
  shift(id,'Dienst A',day,'08:00','16:00',480);demand(`d-${id}`,id,'position-a');
 }
 async function navigate(panel){await page.locator(`.main-nav [data-navigate="${panel}"]`).click();await page.locator(`[data-panel="${panel}"]`).waitFor({state:'visible'});}
 async function open(value=fixture){await page.evaluate(value=>load(value,true),structuredClone(value));await navigate('team');}
 const employeeRow=id=>page.locator(`#people tbody tr[data-employee-id="${id}"]`);
 const planning=id=>employeeRow(id).locator('input[data-employee-planning]');
 const hours=id=>employeeRow(id).locator('input[data-employee-hours]');
 const employees=()=>page.evaluate(()=>structuredClone(snapshot.employees));
 const demands=()=>page.evaluate(()=>structuredClone(snapshot.demands));
 const functionRows=page.locator('#demandBoard tr[data-demand-function]');
 const functionRow=id=>page.locator(`#demandBoard tr[data-demand-function="${id}"]`);
 const functionInput=(id,type)=>functionRow(id).locator(`td[data-demand-type="${type}"] input.demand-value`);
 const number=async selector=>Number((await page.locator(selector).innerText()).replace(/\./g,'').replace(',','.').replace(/[^\d.-]/g,''));
 async function focused(input,message){assert(await input.evaluate(element=>document.activeElement===element),message);}
 async function edit(input,value){await input.fill(String(value));await input.blur();}
 async function save(){
  const panel=await page.evaluate(()=>activePanel);if(panel!=='team')await navigate('team');
  const response=page.waitForResponse(response=>response.url().endsWith('/api/snapshots')&&response.request().method()==='PUT');
  await page.click('#save');const saved=await response;assert.equal(saved.status(),200);
  const value=await saved.json();await page.waitForFunction(()=>document.querySelector('#save').dataset.busy!=='true');
  if(panel!=='team')await navigate(panel);return value;
 }

 // Legacy rows start enabled. Exclusion changes just the planning flag and style.
 await open();
 assert.equal(await planning('person-0').isChecked(),true);
 const ordinaryOpacity=await employeeRow('person-0').evaluate(row=>Number(getComputedStyle(row).opacity));
 await planning('person-0').uncheck();
 assert.deepEqual(await employees(),fixture.employees.map((employee,i)=>i===0?{...employee,excluded:true}:employee));
 assert(await employeeRow('person-0').evaluate(row=>Number(getComputedStyle(row).opacity))<ordinaryOpacity,'An excluded person is visibly dimmed');
 assert.equal(await page.locator('#people tbody tr').count(),3,'Exclusion retains the person in the list');
 assert.equal(await number('#metricPeople'),3,'Excluded people remain part of the imported count');
 assert.equal(await page.evaluate(()=>dirty),true);
 const stored=await save();
 assert.deepEqual(stored.employees[0],{...fixture.employees[0],excluded:true,max_period_minutes:null},'Saving retains targets, contracts, approvals and historical counters');
 assert.deepEqual(stored.metadata.history_matrix,fixture.metadata.history_matrix);
 await page.evaluate(async id=>load(await api('/api/snapshots/'+encodeURIComponent(id)),true),fixture.id);
 assert.equal(await planning('person-0').isChecked(),false,'The excluded flag survives the normal project roundtrip');
 assert(await employeeRow('person-0').evaluate(row=>Number(getComputedStyle(row).opacity))<ordinaryOpacity);
 await planning('person-0').check();
 assert.equal((await employees())[0].excluded,false);
 assert.equal(await employeeRow('person-0').evaluate(row=>Number(getComputedStyle(row).opacity)),ordinaryOpacity);

 // Numeric values commit before moving, and both boundaries keep the same field.
 await hours('person-0').fill('101.5');await hours('person-0').press('Enter');
 assert.equal((await employees())[0].target_minutes,6090);await focused(hours('person-1'),'Enter selects the next visible target-hours field');
 await hours('person-1').fill('61');await hours('person-1').press('ArrowDown');
 assert.equal((await employees())[1].target_minutes,3660);await focused(hours('person-2'));
 await hours('person-2').fill('21');await hours('person-2').press('ArrowDown');
 assert.equal((await employees())[2].target_minutes,1260);await focused(hours('person-2'),'ArrowDown at the final row keeps focus and commits');
 await hours('person-2').press('Enter');await focused(hours('person-2'),'Enter at the final row keeps focus');
 await hours('person-2').press('ArrowUp');await focused(hours('person-1'));
 await hours('person-1').press('ArrowUp');await focused(hours('person-0'));
 await hours('person-0').fill('102');await hours('person-0').press('ArrowUp');
 assert.equal((await employees())[0].target_minutes,6120);await focused(hours('person-0'),'ArrowUp at the first row keeps focus and commits');

 // Space changes a planning checkbox; Enter and arrows navigate that column.
 await planning('person-0').focus();await planning('person-0').press('Space');await planning('person-0').press('Enter');
 assert.equal((await employees())[0].excluded,true);await focused(planning('person-1'));
 await planning('person-1').press('ArrowDown');await focused(planning('person-2'));
 await planning('person-2').press('ArrowDown');await focused(planning('person-2'));
 await planning('person-2').press('Enter');await focused(planning('person-2'));
 await planning('person-2').press('ArrowUp');await focused(planning('person-1'));
 await planning('person-1').press('ArrowUp');await planning('person-0').press('ArrowUp');await focused(planning('person-0'));
 assert.deepEqual((await employees()).map(employee=>employee.excluded),[true,false,false],'Navigation never toggles a planning choice');
 await page.locator('#people input[data-collection-search="people"]').fill('Gruppe A');
 await page.waitForFunction(()=>document.querySelectorAll('#people tbody tr').length===2);
 await hours('person-0').press('Enter');await focused(hours('person-2'),'Navigation follows the filtered visible list');
 await hours('person-2').press('Enter');await focused(hours('person-2'));
 await planning('person-0').press('Enter');await focused(planning('person-2'));
 await planning('person-2').press('ArrowUp');await focused(planning('person-0'));

 // Use a separate project so the exclusion roundtrip's saved revision stays intact.
 // Functions combine different shift patterns and workplaces. Opening is read-only.
 await open({...fixture,id:fixture.id+'-functions'});await navigate('demand');
 const beforeView=await page.evaluate(()=>({dirty,version:changeVersion,snapshot:currentSnapshot()}));
 assert.equal((await page.locator('#demandViewDates').innerText()).trim(),'Nach Datum');
 assert.equal((await page.locator('#demandViewFunctions').innerText()).trim(),'Nach Funktion');
 await page.click('#demandViewFunctions');
 assert.deepEqual(await page.evaluate(()=>({dirty,version:changeVersion,snapshot:currentSnapshot()})),beforeView);
 assert.deepEqual((await functionRows.evaluateAll(rows=>rows.map(row=>row.dataset.demandFunction))).sort(),['service-a','service-b']);
 for(const id of ['service-a','service-b']){
  assert.equal(await functionRow(id).locator('input.demand-value').count(),4,'Each function has exactly four day-type fields');
  assert.deepEqual(await functionRow(id).locator('td[data-demand-type]').evaluateAll(cells=>cells.map(cell=>cell.dataset.demandType)),['weekday','saturday','sunday','holiday']);
 }
 for(const title of ['Werktag','Samstag','Sonntag','Feiertag'])assert((await page.locator('#demandBoard thead').innerText()).includes(title));
 assert.equal(await functionInput('service-a','weekday').inputValue(),'');
 assert.match(await functionInput('service-a','weekday').getAttribute('placeholder'),/uneinheitlich/i,'Different individual minima are explicitly marked');
 assert.equal(await functionInput('service-b','weekday').inputValue(),'1');
 assert.equal(await functionInput('service-a','holiday').inputValue(),'1');
 assert.equal(await functionInput('service-b','holiday').inputValue(),'1','A holiday marks the local date for every function, even if its own shift flag is false');
 assert.equal(await number('#demandMinimumHours'),112);assert.equal(await number('#demandContractHours'),180);
 await edit(functionInput('service-a','weekday'),3);
 const expected=structuredClone(fixture.demands);
 const weekdayIds=['d-a-0','d-a-2','d-a-3','d-a-4','d-a-second','d-a-late'];
 for(const item of expected)if(weekdayIds.includes(item.id))Object.assign(item,{minimum:3,maximum:3,source:'override'});
 assert.deepEqual(await demands(),expected,'Weekday input updates each matching demand only; holidays, weekends, other functions and context stay intact');
 assert.equal(await functionInput('service-a','weekday').inputValue(),'3','Entering a value resolves mixed staffing');
 assert.equal(await number('#demandMinimumHours'),190,'The shared hours balance updates after a function edit');
 assert.equal(await functionInput('service-a','saturday').inputValue(),'1');assert.equal(await functionInput('service-a','sunday').inputValue(),'1');
 const savedFunctions=await save();assert.deepEqual(savedFunctions.demands,expected,'Every function edit persists with source override');
 await page.click('#demandViewDates');
 assert(await page.locator('#demandBoard td[data-demand-day]').count()>0,'The existing date matrix remains available');
 assert.equal(await number('#demandMinimumHours'),190);
 await page.click('#demandViewFunctions');
 assert.equal(await functionInput('service-a','weekday').inputValue(),'3');
 for(const [type,id,value] of [['saturday','d-a-5',4],['sunday','d-a-6',5],['holiday','d-a-1',6]]){
  await edit(functionInput('service-a',type),value);
  Object.assign(expected.find(item=>item.id===id),{minimum:value,maximum:value,source:'override'});
  assert.deepEqual(await demands(),expected,`${type} edits only that day type within the selected function`);
 }

 // Function navigation commits the edited value and retains its day-type column.
 const visibleFunctions=await functionRows.evaluateAll(rows=>rows.map(row=>row.dataset.demandFunction));
 const first=functionInput(visibleFunctions[0],'weekday'),last=functionInput(visibleFunctions[1],'weekday');
 await first.fill('4');await first.press('Enter');await focused(last);
 assert.equal(await first.inputValue(),'4');
 assert((await demands()).filter(item=>weekdayIds.includes(item.id)).every(item=>item.minimum===4),'Enter commits each affected demand before changing rows');
 await last.fill('2');await last.press('ArrowUp');await focused(first);assert.equal(await last.inputValue(),'2');
 await first.press('ArrowUp');await focused(first);
 await first.press('ArrowDown');await focused(last);
 await last.fill('3');await last.press('ArrowDown');await focused(last);assert.equal(await last.inputValue(),'3');
 await last.press('Enter');await focused(last);

 // Date-view navigation follows visible service rows, preserving the date column.
 await page.click('#demandViewDates');
 const dateInputs=page.locator(`#demandBoard tr[data-demand-row] td[data-demand-day="${days[0]}"] input.demand-value:enabled`);
 assert(await dateInputs.count()>=2);
 const dateFirst=dateInputs.first(),dateLast=dateInputs.last();
 await dateFirst.fill('7');await dateFirst.press('Enter');await focused(dateInputs.nth(1));
 assert.equal(await dateFirst.inputValue(),'7');
 await page.click('#demandViewFunctions');await page.click('#demandViewDates');
 assert.equal(await dateFirst.inputValue(),'7','Enter in the date view commits staffing before rerendering');
 await dateInputs.nth(1).press('ArrowUp');await focused(dateFirst);
 await dateFirst.press('ArrowUp');await focused(dateFirst);
 await dateFirst.press('ArrowDown');await focused(dateInputs.nth(1));
 await dateLast.fill('8');await dateLast.press('ArrowDown');await focused(dateLast);assert.equal(await dateLast.inputValue(),'8');
 await dateLast.press('Enter');await focused(dateLast);

 // Without a holiday in the planning period, the holiday fields are empty/disabled.
 const ordinary=structuredClone(fixture);ordinary.id+='-ordinary';ordinary.shifts.forEach(item=>item.holiday=item.id==='before');
 await open(ordinary);await navigate('demand');await page.click('#demandViewFunctions');
 for(const id of ['service-a','service-b']){
  assert.equal(await functionInput(id,'holiday').inputValue(),'');
  assert.equal(await functionInput(id,'holiday').isDisabled(),true,'A context-only holiday cannot enable a planning-period holiday field');
 }

 // A holiday and its demands are assigned using the project's local start date.
 const zoned=structuredClone(fixture);zoned.id+='-zoned';zoned.timezone='Pacific/Auckland';zoned.shifts=[];zoned.demands=[];
 function zonedDuty(id,start,holiday=false){
  const end=new Date(new Date(start).getTime()+4*60*60*1000).toISOString();
  zoned.shifts.push({...fixture.shifts[0],id,segments:[{start,end}],paid_minutes:240,holiday});
  zoned.demands.push({id:`d-${id}`,shift_id:id,position_id:'position-a',minimum:1,maximum:2,team_ids:['team-a'],alternative_group:null,source:'synthetic'});
 }
 zonedDuty('local-monday','2026-01-04T11:30:00Z');
 zonedDuty('local-tuesday-holiday','2026-01-05T11:30:00Z',true);
 zonedDuty('local-tuesday-second','2026-01-05T16:00:00Z');
 zonedDuty('local-sunday-context','2026-01-04T01:00:00Z');
 await open(zoned);await navigate('demand');await page.click('#demandViewFunctions');
 await edit(functionInput('service-a','weekday'),4);
 let changed=await demands();
 assert.deepEqual(changed.map(item=>item.minimum),[4,1,1,1],'Local Monday is a weekday even though its UTC date is Sunday');
 await edit(functionInput('service-a','holiday'),5);changed=await demands();
 assert.deepEqual(changed.map(item=>item.minimum),[4,5,5,1],'Holiday grouping uses the local start date for all shifts on that date');
 assert.deepEqual(errors,[]);
 console.log('Planning controls: exclusion and preservation, function/day-type staffing, mixed values, local holidays, hours balance and keyboard navigation passed.');
};
