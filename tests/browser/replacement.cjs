'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function replacement({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{load(await api('/api/demo'));window.__entwurf=assignments;assignments=[];navigate('plan');renderActivePanel(true);});
 await page.locator('#replacementPanel').evaluate(node=>node.open=true);
 // Without a draft the panel says so instead of offering an empty form.
 assert.match(await page.locator('#replacementForm').textContent(),/Erst planen/);

 await page.evaluate(()=>{assignments=window.__entwurf;renderActivePanel(true);});
 await page.locator('#replacementPanel').evaluate(node=>node.open=true);
 await page.locator('#findReplacement').waitFor();
 const sick=await page.inputValue('#replacementForm select');
 await page.fill('#replacementForm input[type="date"]','2026-01-05');
 await page.locator('#replacementForm input[type="date"]').nth(1).fill('2026-01-05');
 await page.click('#findReplacement');
 const result=page.locator('#replacementResult');
 await result.locator('table').waitFor();
 const text=await result.textContent();
 assert.match(text,/Dienste werden frei/);
 // The plan itself is untouched: a stand-in search answers a question, it does not replan.
 assert.equal(await page.evaluate(()=>assignments.filter(a=>a.employee_id===document.querySelector('#replacementForm select').value).length>0),true);
 assert.ok(sick);
 const rows=await result.locator('tbody tr').count();
 assert.ok(rows>0,'every freed duty gets its own row');
 assert.doesNotMatch(text,/undefined/);
 console.log('Replacement: a sick call lists free, approved stand-ins without touching the plan.');
};
