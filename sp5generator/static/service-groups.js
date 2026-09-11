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
 const api={groups,apply};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ServiceGroups=api;
})(globalThis);
