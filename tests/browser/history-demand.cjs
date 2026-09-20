'use strict';
// Synthetic project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function historyDemand({page,base}){
 await page.goto(base);
 await page.click('#openImport');
 const note=page.locator('#demandSourceNote');
 await page.locator('#demandSource').waitFor();
 assert.equal(await note.isVisible(),false,'no note while the source is the requirements table');

 await page.fill('#start','2027-01-01');await page.fill('#end','2027-01-31');
 await page.selectOption('#demandSource','history');
 await note.waitFor({state:'visible'});
 assert.match(await note.textContent(),/Optionale Einrichtung/);
 // The window is no longer optional, so it has to be open and filled in.
 assert.equal(await page.locator('#importOptions').evaluate(node=>node.open),true);
 assert.equal(await page.inputValue('#historyEnd'),'2026-12-31');
 assert.equal(await page.inputValue('#historyStart'),'2026-10-01');

 // A window the planner already chose is never overwritten.
 await page.selectOption('#demandSource','requirements');
 await page.fill('#historyStart','2026-01-01');
 await page.selectOption('#demandSource','history');
 assert.equal(await page.inputValue('#historyStart'),'2026-01-01');
 await page.selectOption('#demandSource','observed');
 await note.waitFor({state:'hidden'});
 console.log('History demand: the source offers a typical-day derivation and insists on a comparable window.');
};
