'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function approvalLeverage({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{
  load(await api('/api/demo'));navigate('plan');$('result').replaceChildren();
  // Niemand ist für den zweiten Dienst freigegeben: dort ist die Freigabe die Hürde.
  const zweite={...structuredClone(snapshot.positions[0]),id:'p-zweite',function_id:'f-zweite',name:'Funktion B'};
  snapshot.positions.push(zweite);
  snapshot.demands[0].position_id='p-zweite';
  snapshot.metadata.services=[{function_id:'f-zweite',name:'Funktion B'}];
  assignments=[];
  renderPlanMetrics({});
 });
 const box=page.locator('#approvalLeverage');
 await box.waitFor();
 await box.evaluate(node=>node.open=true);
 assert.match(await box.innerText(),/erteilt keine Freigabe und schlägt keine vor/);

 await box.getByRole('button',{name:'Vorschau berechnen'}).click();
 const dienste=box.locator('#approvalLeverageServices tbody tr');
 await dienste.first().waitFor();
 assert.match(await box.locator('#approvalLeverageResult p').first().textContent(),
  /Freigaben kämen in Frage/);
 // Zuerst je Dienstart: dieselbe Lücke trifft dutzende Personen auf einmal.
 const kopf=await dienste.first().innerText();
 assert.match(kopf,/Funktion B/);
 assert.match(kopf,/Personen kämen in Frage/);
 // Die Personenzeilen bleiben als Detail erreichbar.
 const einzeln=box.locator('#approvalLeverageRows');
 await einzeln.evaluate(node=>node.open=true);
 assert.ok(await einzeln.locator('tbody tr').count()>0);

 // Die Vorschau lässt Projekt und Entwurf unangetastet.
 assert.deepEqual(await page.evaluate(()=>[assignments.length,
  snapshot.employees.flatMap(e=>e.approvals.map(a=>a.function_id)).includes('f-zweite')]),[0,false]);
 assert.match(await page.locator('#notice').textContent(),/fachliche Entscheidung/);
 console.log('Approval leverage: the preview shows what one more approval would open, and grants none.');
};
