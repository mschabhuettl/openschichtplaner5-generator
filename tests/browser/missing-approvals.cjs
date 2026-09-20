'use strict';
// Newly constructed synthetic project only; the server is the local browser fixture.
const assert=require('node:assert/strict');
const fs=require('node:fs');
module.exports=async function missingApprovals({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 const fixture={
  schema_version:'1.0',id:'synthetic-missing-approvals',revision:'0',created_at:'2026-01-01T00:00:00Z',
  timezone:'UTC',period_start:'2026-01-05',period_end:'2026-01-11',
  context_start:'2025-12-28',context_end:'2026-01-19',context_complete:true,
  rule_version:'synthetic-1',software_versions:{},source:'synthetic',
  employees:[0,1].map(i=>({
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
  positions:[
   {id:'position-a',name:'Dienst A',function_id:'service-a',workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false},
   {id:'position-b',name:'Dienst B',function_id:'service-b',workplace_id:'workplace-a',qualification_ids:[],qualification_level:1,qualifications_required:false},
  ],
  shifts:[['first','2026-01-05'],['second','2026-01-07']].map(([shiftId,day])=>({
   id:shiftId,name:`Dienst ${shiftId}`,kind:'day',team_id:'team-a',
   segments:[{start:`${day}T08:00:00Z`,end:`${day}T16:00:00Z`}],paid_minutes:480,holiday:false,source:'synthetic',
  })),
  demands:[
   {id:'d-first',shift_id:'first',position_id:'position-a',minimum:1,maximum:1,team_ids:['team-a'],alternative_group:null,source:'synthetic'},
   {id:'d-second',shift_id:'second',position_id:'position-b',minimum:1,maximum:1,team_ids:['team-a'],alternative_group:null,source:'synthetic'},
  ],
  assignments:[],boundary_work:[],restrictions:[],wishes:[],
  objectives:{hours:0,nights:0,weekends:0,holidays:0,wishes:0,changes:0},
  unresolved:[],metadata:{services:[{function_id:'service-b',name:'Nachtdienst B'}]},
 };
 await page.evaluate(value=>load(value,true),fixture);
 await page.locator('.main-nav [data-navigate="calculate"]').click();
 await page.locator('[data-panel="calculate"]').waitFor({state:'visible'});
 await page.check('#partial');
 await page.click('#solve');
 await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('Fehlende Dienstfreigaben'),null,{timeout:30000});

 const box=page.locator('#result details',{hasText:'Fehlende Dienstfreigaben'}).first();
 assert.match(await box.locator('summary').innerText(),/Fehlende Dienstfreigaben: 2 · 2 Personen/,'Both people are named once for the blocked service');
 await box.locator('summary').click();
 const entries=box.locator('article.diagnostic-item');
 await entries.first().waitFor();
 assert.equal(await entries.count(),2);
 const text=await box.innerText();
 assert.match(text,/Testperson 1 · Nachtdienst B/,'The service catalogue name is used, not the raw id');
 assert.match(text,/1 Stelle bleibt ohne diese Freigabe unbesetzbar/,'A single blocked position is named in the singular');
 assert.doesNotMatch(text,/Dienst A/,'A staffable service needs no approval hint');

 const csvDownload=page.waitForEvent('download');
 await box.getByRole('button',{name:'Fehlende Freigaben als CSV',exact:true}).click();
 const csv=fs.readFileSync(await(await csvDownload).path(),'utf8');
 assert.equal(csv.split('\r\n')[0],'﻿Person;Dienst;Blockierte Stellen');
 assert.match(csv,/Testperson 1;Nachtdienst B;1/);
 assert.match(csv,/Testperson 2;Nachtdienst B;1/);

 // Granting the approval removes the entry again.
 await page.evaluate(()=>{for(const person of snapshot.employees)person.approvals.push({function_id:'service-b',workplace_id:'*',valid_from:'2025-01-01',valid_until:'2027-12-31',supervised:false});invalidateResult();});
 await page.locator('.main-nav [data-navigate="calculate"]').click();
 await page.locator('[data-panel="calculate"]').waitFor({state:'visible'});
 await page.click('#solve');
 await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('Vollständig und geprüft'),null,{timeout:30000});
 assert.equal(await page.locator('#result details',{hasText:'Fehlende Dienstfreigaben'}).count(),0,'A complete plan reports no missing approvals');

 assert.deepEqual(errors,[]);
 console.log('Missing approvals: blocked positions per person and service, catalogue names, CSV export and clearing passed.');
};
