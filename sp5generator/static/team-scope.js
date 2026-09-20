/* Groups decide who is planned: take a whole group out of planning in one step. */
(function(root){
 function members(snapshot,teamId){return snapshot.employees.filter(e=>(e.team_ids||[]).includes(teamId));}
 function overview(snapshot){
  const counts=new Map();
  for(const person of snapshot.employees)
   for(const id of person.team_ids||[]){
    const row=counts.get(id)||{total:0,excluded:0};row.total++;if(person.excluded)row.excluded++;counts.set(id,row);
   }
  return counts;
 }
 function apply(snapshot,teamId,excluded){
  if(!teamId)throw new Error('Zuerst eine Gruppe wählen.');
  const rows=members(snapshot,teamId);
  if(!rows.length)throw new Error('Diese Gruppe hat im Projekt keine Mitglieder.');
  let changed=0,shared=0;
  for(const person of rows){
   if(!!person.excluded===excluded)continue;
   person.excluded=excluded;changed++;
   // Membership is not exclusive. Someone taken out here may be planned elsewhere.
   if((person.team_ids||[]).some(id=>id!==teamId))shared++;
  }
  return {changed,total:rows.length,shared};
 }
 const api={apply,overview,members};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TeamScope=api;
})(globalThis);
