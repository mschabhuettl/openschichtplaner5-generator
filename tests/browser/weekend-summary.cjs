'use strict';
// Newly constructed synthetic project only; the server is the local browser fixture.
const assert=require('node:assert/strict');
module.exports=async function weekendSummary({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 function project(id,saturdayMinimum){
  const fixture={
   schema_version:'1.0',id,revision:'0',created_at:'2026-01-01T00:00:00Z',
   timezone:'UTC',period_start:'2026-01-05',period_end:'2026-01-11',
   context_start:'2025-12-28',context_end:'2026-01-19',context_complete:true,
   rule_version:'synthetic-1',software_versions:{},source:'synthetic',
   employees:[0,1,2].map(i=>({
    id:`person-${i}`,name:`Testperson ${i+1}`,team_ids:['team-a'],
    employment_start:'2025-01-01',employment_end:'2027-12-31',
    approvals:[{function_id:'service-a',workplace_id:'workplace-a',valid_from:'2025-01-01',valid_until:'2027-12-31',supervised:false}],
    qualifications:[],availability:[],unavailable:[],allowed_kinds:['day','night'],
    preferred_kind:null,preferred_functions:[],allow_weekends:true,allow_holidays:true,
    profile_ids:['synthetic-profile'],target_minutes:0,contractual_weekly_minutes:null,
    balance_minutes:0,credit_minutes:0,employment_fraction:100,
    historical_nights:0,historical_weekends:0,historical_holidays:0,mentor_capacity:0,
   })),
   profiles:[{id:'synthetic-profile',valid_from:'2025-12-28',valid_until:'2026-01-19',min_rest_minutes:660,confirmed:true,source:'synthetic'}],
   positions:[{id:'position-a',name:'Dienst A',function_id:'service-a',workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false}],
   shifts:[['saturday','2026-01-10'],['sunday','2026-01-11']].map(([shiftId,day])=>({
    id:shiftId,name:`Dienst ${shiftId}`,kind:'day',team_id:'team-a',
    segments:[{start:`${day}T08:00:00Z`,end:`${day}T16:00:00Z`}],paid_minutes:480,holiday:false,source:'synthetic',
   })),
   demands:[
    {id:'d-saturday',shift_id:'saturday',position_id:'position-a',minimum:saturdayMinimum,maximum:saturdayMinimum,team_ids:['team-a'],source:'synthetic'},
    {id:'d-sunday',shift_id:'sunday',position_id:'position-a',minimum:1,maximum:1,team_ids:['team-a'],source:'synthetic'},
   ],
   assignments:[],boundary_work:[],restrictions:[],wishes:[],
   objectives:{split_weekends:1000,hours:0,nights:0,weekends:0,holidays:0,wishes:0,changes:0},
   unresolved:[],metadata:{},
  };
  return fixture;
 }
 async function solved(fixture){
  await page.evaluate(value=>load(value,true),fixture);
  await page.locator('.main-nav [data-navigate="calculate"]').click();
  await page.locator('[data-panel="calculate"]').waitFor({state:'visible'});
  await page.click('#solve');
  await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('geprüft'),null,{timeout:30000});
  return page.locator('#result').innerText();
 }

 // Saturday needs two people, Sunday one: one person can only work a single day.
 const forced=await solved(project('synthetic-weekend-forced',2));
 assert.match(forced,/1 geteiltes Wochenende/,'The plan reports its counted split weekends');
 assert.match(forced,/1 davon erzwingt der Bedarf selbst; so viele bleiben/,'Unequal weekend demand is named as the cause');
 assert.match(forced,/Zusammenhängende Freizeit: \d+ Blöcke/,'Free time is reported in plain words');

 // Der Suchverlauf erklärt in Klartext, wie der Plan zustande kam.
 const trace=page.locator('#result details.trace-box');
 assert.match(await trace.locator('summary').innerText(),/Wie der Plan entstanden ist/);
 const steps=trace.locator('.trace-step');
 assert((await steps.count())>=1,'At least one search stage is shown');
 const first=await steps.first().innerText();
 assert.match(first,/Gültige Besetzung finden|Besetzung maximieren/,'The first stage is named in plain words');
 assert.match(first,/\d+(,\d+)? s ·/,'Each stage reports how long it ran');
 assert.match(first,/übernommen|verworfen/,'Each stage says whether its result was kept');
 assert((await trace.locator('.trace-step.accepted').count())>=1,'A kept stage is marked');

 // Both days need one person: nothing forces a split any more.
 const balanced=await solved(project('synthetic-weekend-balanced',1));
 assert.doesNotMatch(balanced,/erzwingt der Bedarf selbst/,'Equal weekend demand forces no split');
 assert.match(balanced,/Zusammenhängende Freizeit: \d+ Blöcke/);

 assert.deepEqual(errors,[]);
 console.log('Weekend summary: counted splits, demand-forced share and free time are shown in plain words.');
};
