'use strict';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(90);}
async function measure(page,selector){return page.locator(selector).first().evaluate(e=>{
 const r=e.getBoundingClientRect(),h=document.querySelector('.topbar').getBoundingClientRect();
 const rect={left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};
 const overlap=r.right>h.left&&r.left<h.right&&!e.closest('.topbar,.sidebar');
 const clip={left:0,right:innerWidth,top:overlap?Math.max(0,h.bottom):0,bottom:innerHeight};
 const ancestors=[];
 for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),q=p.getBoundingClientRect();
  if(/auto|scroll|hidden|clip/.test(s.overflowX)){clip.left=Math.max(clip.left,q.left+p.clientLeft);clip.right=Math.min(clip.right,q.left+p.clientLeft+p.clientWidth);}
  if(/auto|scroll|hidden|clip/.test(s.overflowY)){clip.top=Math.max(clip.top,q.top+p.clientTop);clip.bottom=Math.min(clip.bottom,q.top+p.clientTop+p.clientHeight);}
  if(p.scrollLeft||p.scrollTop)ancestors.push({tag:p.tagName,id:p.id,className:p.className,x:p.scrollLeft,y:p.scrollTop});
 }
 const uncovered=[[.1,.1],[.5,.5],[.9,.9]].every(([x,y])=>{const hit=document.elementFromPoint(r.left+r.width*x,r.top+r.height*y);return hit===e||e.contains(hit);});
 return {...rect,clip,uncovered,fullyVisible:r.width>0&&r.height>0&&r.left>=clip.left-.1&&r.right<=clip.right+.1&&r.top>=clip.top-.1&&r.bottom<=clip.bottom+.1,focused:document.activeElement===e,text:e.textContent,scrollX,scrollY,ancestors};
 });}
async function reach(page,selector,focus=false){
 await page.locator(selector).first().evaluate((e,focus)=>{e.scrollIntoView({block:'center',inline:'end',behavior:'instant'});if(focus)e.focus({preventScroll:true});},focus);
 await settle(page);
 const nativeAlignment=await measure(page,selector);
 // Native end alignment rounds a scroll offset to a CSS pixel in Chromium.
 // A fractional target edge can remain <1px outside even when a user wheel
 // step reaches it. Perform that local step, NOT a wider visibility tolerance.
 // Only a fitting target and an actually scrollable ancestor may be adjusted;
 // hidden/clip, exhausted ranges, oversize and occlusion still fail measure().
 const scrollCorrections=await page.locator(selector).first().evaluate(e=>{
  const changes=[];
  for(let p=e.parentElement;p;p=p.parentElement){
   const style=getComputedStyle(p),r=e.getBoundingClientRect(),q=p.getBoundingClientRect();
   if(!/auto|scroll/.test(style.overflowX)||p.scrollWidth<=p.clientWidth||r.width>p.clientWidth)continue;
   const right=q.left+p.clientLeft+p.clientWidth,excess=r.right-right;
   if(excess>0&&excess<1){const before=p.scrollLeft;p.scrollLeft+=1;changes.push({tag:p.tagName,id:p.id,className:p.className,before,after:p.scrollLeft,excess});}
  }
  return changes;
 });
 if(scrollCorrections.length)await settle(page);
 return {...await measure(page,selector),nativeAlignment,scrollCorrections};
}
module.exports={settle,measure,reach};
