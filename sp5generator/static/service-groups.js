/* Group equal service/time patterns without changing individual confirmations. */
(function(root){
 function groups(snapshot){
  const positions=new Map(snapshot.positions.map(p=>[p.id,p]));
  const services=new Map();
  for(const d of snapshot.demands){const p=positions.get(d.position_id);if(!p)continue;if(!services.has(d.shift_id))services.set(d.shift_id,new Set());services.get(d.shift_id).add(p.function_id);}
  const format=new Intl.DateTimeFormat('sv-SE',{timeZone:snapshot.timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const parts=value=>{const p=Object.fromEntries(format.formatToParts(new Date(value)).map(x=>[x.type,x.value]));return {day:Date.UTC(+p.year,+p.month-1,+p.day)/86400000,time:p.hour+':'+p.minute};};
  const rows=new Map();
  for(const shift of snapshot.shifts){const ids=services.get(shift.id);if(!ids||ids.size!==1||!shift.segments.length)continue;
   const anchor=parts(shift.segments[0].start).day;
   const times=shift.segments.map(s=>{const a=parts(s.start),b=parts(s.end);return [a.day-anchor,a.time,b.day-anchor,b.time];});
   const key=JSON.stringify([[...ids][0],times,shift.paid_minutes]);
   if(!rows.has(key))rows.set(key,{key,name:shift.name,times,paidMinutes:shift.paid_minutes,shiftIds:[],pending:0});
   const row=rows.get(key);row.shiftIds.push(shift.id);if(shift.kind==='unconfirmed')row.pending++;
  }
  return [...rows.values()];
 }
 function apply(snapshot,key,kind){
  if(!['day','night'].includes(kind))throw Error('Dienstart auswählen.');
  const group=groups(snapshot).find(g=>g.key===key);if(!group)throw Error('Dienstmuster nicht mehr vorhanden.');
  const ids=new Set(group.shiftIds);let count=0;
  for(const shift of snapshot.shifts)if(ids.has(shift.id)&&shift.kind==='unconfirmed'){shift.kind=kind;count++;}
  return count;
 }
 function suggest(group,start='22:00',end='06:00',minimum=180){
  const minute=t=>{if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(t))throw Error('Gültige Nachtzeit eingeben.');return +t.slice(0,2)*60 + +t.slice(3);};
  const a=minute(start),b=minute(end);
  if(a===b||!Number.isInteger(minimum)||minimum<1||minimum>1440)throw Error('Nachtfenster und Mindestdauer prüfen.');
  let total=0,night=0,last=-Infinity;
  for(const [d1,t1,d2,t2] of group.times){
   const from=d1*1440+minute(t1),to=d2*1440+minute(t2);
   if(to<=from||from<last||to-from>10080)return null;
   last=to;total+=to-from;
   for(let day=Math.floor(from/1440)-1;day<=Math.floor(to/1440);day++){
    const lo=day*1440+a,hi=day*1440+b+(b<a?1440:0);
    night+=Math.max(0,Math.min(to,hi)-Math.max(from,lo));
   }
  }
  return total?{kind:night>=minimum?'night':'day',nightMinutes:night}:null;
 }
 function preview(snapshot,rule){
  suggest({times:[]},rule.start,rule.end,rule.minimum);
  const rows=groups(snapshot).filter(g=>g.pending).map(group=>({group,proposal:suggest(group,rule.start,rule.end,rule.minimum)}));
  const pending=snapshot.shifts.filter(s=>s.kind==='unconfirmed').length;
  let day=0,night=0;
  for(const {group,proposal} of rows)if(proposal?.kind==='day')day+=group.pending;else if(proposal?.kind==='night')night+=group.pending;
  return {rows,pending,day,night,skipped:pending-day-night};
 }
 const api={groups,apply,suggest,preview};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ServiceGroups=api;
})(globalThis);
