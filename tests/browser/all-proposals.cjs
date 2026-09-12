'use strict';
// Synthetic end-to-end check; never opens a personal project or SP5 source.
const assert=require('node:assert/strict');
module.exports=async function allProposals({page,base}){
  await page.goto(base);
  await page.evaluate(async()=>{
   snapshot=await(await fetch('/api/demo')).json();assignments=[];
   snapshot.metadata={service_matrix_version:1,services:[],history_matrix:[]};
   const model=snapshot.employees[0];snapshot.employees=[];
   for(let i=0;i<35;i++){
    const e={...structuredClone(model),id:`person-${i}`,name:`Synthetic person ${i}`,approvals:[]};snapshot.employees.push(e);
    const proposals=Array.from({length:20},(_,j)=>({function_id:`service-${j}`,workplace_id:'*'}));
    snapshot.metadata.history_matrix.push({employee_id:e.id,suggested_approvals:proposals});
   }
   snapshot.metadata.services=Array.from({length:20},(_,j)=>({function_id:`service-${j}`,name:`Synthetic service ${j}`}));
   const e=snapshot.employees[34];
   e.approvals=[{function_id:'service-19',workplace_id:'*',valid_from:snapshot.period_start,valid_until:snapshot.period_end,supervised:true},
    {function_id:'service-18',workplace_id:'*',valid_from:snapshot.period_start,valid_until:snapshot.period_start,supervised:true}];
   snapshot.metadata.history_matrix[34].suggested_approvals.push({function_id:'service-17',workplace_id:'restricted-workplace'});
   snapshot.metadata.history_matrix[34].suggested_approvals.push({function_id:'service-19',workplace_id:'*'});
   matrixCache=null;indexes=null;indexVersion=-1;planMonth=snapshot.period_start.slice(0,7);document.querySelector("#workspace").hidden=false;activePanel="team";
   render();navigate('team');
  });
  // Prominent and above the matrix, not hidden in the footer below long lists.
  const placement=await page.evaluate(()=>{const b=document.querySelector('#confirmHistory');
   return {inBanner:!!b.closest('#historyBulk'),beforeMatrix:!!(b.compareDocumentPosition(document.querySelector('#matrix'))&Node.DOCUMENT_POSITION_FOLLOWING),
    inFooter:!!b.closest('.surface-footer'),primary:b.classList.contains('primary'),
    top:b.getBoundingClientRect().top,matrixTop:document.querySelector('#matrix').getBoundingClientRect().top,viewport:innerHeight};});
  assert.deepEqual({inBanner:placement.inBanner,beforeMatrix:placement.beforeMatrix,inFooter:placement.inFooter,primary:placement.primary},
   {inBanner:true,beforeMatrix:true,inFooter:false,primary:true},'Bulk approval stays prominent above the matrix');
  assert(placement.top<placement.viewport&&placement.top<placement.matrixTop,
   'Bulk approval is visible without scrolling and sits above the matrix');
  assert.match(await page.locator('#historyBulkTitle').textContent(),/^700 historische Vorschläge offen$/);
  await page.fill('#matrixSearch','Synthetic person 0');
  assert.equal(await page.locator('#confirmHistory').textContent(),'Alle 700 historischen Vorschläge übernehmen');
  const before=await page.evaluate(()=>structuredClone(snapshot.employees[34].approvals));
  page.once('dialog',dialog=>dialog.dismiss());await page.click('#confirmHistory');
  assert.deepEqual(await page.evaluate(()=>snapshot.employees[34].approvals),before,'Cancel leaves offscreen proposals unchanged');
  page.once('dialog',async dialog=>{assert.match(dialog.message(),/Alle 700/);await dialog.accept();});
  await page.click('#confirmHistory');
  const result=await page.evaluate(()=>structuredClone(snapshot.employees));
  assert.equal(result[0].approvals.length,20);assert.equal(result[33].approvals.length,20);
  assert.deepEqual(result[34].approvals.slice(0,2),before,'Existing approvals retained exactly');
  assert(result[34].approvals.some(a=>a.function_id==='service-18'&&a.valid_until>before[1].valid_until&&a.supervised),'Partial supervision preserved');
  assert(result[34].approvals.some(a=>a.workplace_id==='restricted-workplace'),'Restricted suggestion keeps exact workplace');
  assert.equal(await page.locator('#confirmHistory').textContent(),'Alle 0 historischen Vorschläge übernehmen');
  assert.match(await page.locator('#historyBulkTitle').textContent(),/^Keine offenen historischen Vorschläge$/);
  page.once('dialog',()=>{throw Error('No duplicate approval confirmation expected');});await page.click('#confirmHistory');
  assert.deepEqual(await page.evaluate(()=>snapshot.employees),result,'Repeated apply is idempotent');
  console.log('All historical proposals: >30 people, >16 services, search, cancellation, scope, supervision and repeat passed.');
};
