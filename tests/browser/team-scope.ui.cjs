'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function teamScopeUi({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));
  snapshot.employees.forEach((e,i)=>{e.team_ids=[i%2?'sp5:group:fremd':'sp5:group:eigen'];e.excluded=false;e.mentor_capacity=0;});
  snapshot.metadata.group_tree=[{id:'sp5:group:eigen',name:'Eigener Bereich',children:[]},
                                {id:'sp5:group:fremd',name:'Fremder Bereich',children:[]}];
  invalidateResult();navigate('team');renderActivePanel(true);
 });
 const scope=page.locator('#teamScopeFields');
 await scope.waitFor();
 const counts=await page.evaluate(()=>[snapshot.employees.filter(e=>e.team_ids[0]==='sp5:group:fremd').length,snapshot.employees.length]);
 // The chooser names the group and how many people it holds, so the consequence is visible first.
 assert.match(await scope.locator('select').first().textContent(),new RegExp(`Fremder Bereich · ${counts[0]} Personen`));

 await scope.locator('select').first().selectOption('sp5:group:fremd');
 await scope.getByRole('button',{name:'Gruppe ausnehmen'}).click();
 assert.deepEqual(await page.evaluate(()=>[snapshot.employees.filter(e=>e.excluded).length,snapshot.employees.filter(e=>!e.excluded).length]),
  [counts[0],counts[1]-counts[0]]);
 assert.match(await page.locator('#notice').textContent(),new RegExp(`${counts[0]} von ${counts[0]} Personen von der Planung ausgenommen`));

 const school=page.locator('#teachingFields');
 await school.locator('select').first().selectOption('sp5:group:eigen');
 await school.getByLabel('Begleitete Personen je Dienst').fill('2');
 await school.getByRole('button',{name:'Gruppe als Ausbilder kennzeichnen'}).click();
 assert.deepEqual(await page.evaluate(()=>[...new Set(snapshot.employees.filter(e=>e.team_ids[0]==='sp5:group:eigen').map(e=>e.mentor_capacity))]),[2]);

 await school.locator('select').nth(1).selectOption('sp5:group:fremd');
 await school.getByRole('button',{name:'Gruppe unter Begleitung stellen'}).click();
 const supervised=await page.evaluate(()=>snapshot.employees.filter(e=>e.team_ids[0]==='sp5:group:fremd')
  .flatMap(e=>e.approvals.map(a=>a.supervised)));
 assert.ok(supervised.length&&supervised.every(Boolean),'every approval of the group now needs company');
 await school.getByRole('button',{name:'Begleitung wieder aufheben'}).click();
 assert.ok((await page.evaluate(()=>snapshot.employees.flatMap(e=>e.approvals.map(a=>a.supervised)))).every(v=>!v),'and it can be taken back');
 console.log('Team scope: whole groups leave the plan, mentors and apprentices are marked in one step.');
};
