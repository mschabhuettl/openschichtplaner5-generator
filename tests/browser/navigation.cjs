'use strict';
// Exercise the four visible destinations and real local controls. The legacy
// scenario word "calculate" means Plan + its explicit optional tools, not a
// hidden navigation alias or a direct call into PlannerUI.
module.exports=async function navigate(page,target){
 const content=target==='calculate'?'plan':target;
 const area=['rules','demand'].includes(content)?'setup':content;
 await page.locator(`.main-nav [data-navigate="${area}"]`).click();
 if(area==='setup')await page.locator(`#setupNav [data-navigate="${content}"]`).click();
 await page.locator(`[data-panel="${content}"]`).waitFor({state:'visible'});
 if(target==='calculate'){
  await page.locator('#openCalculationOptions').click();
  if(!await page.locator('#inputReview').evaluate(e=>e.open))await page.locator('#inputReview > summary').click();
 }
};
