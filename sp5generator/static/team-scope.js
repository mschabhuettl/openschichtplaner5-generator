/* Groups decide who is planned: take a whole group out of planning in one step. */
(function(root){
 // team_ids also carries the groups a person inherits from a parent node. Taking a
 // group out of the plan must follow actual membership, or a parent node would sweep
 // out everyone below it.
 function groupsOf(snapshot,person){
  const direct=snapshot.metadata?.direct_group_memberships?.[person.id];
  return direct?direct.map(id=>`sp5:group:${id}`):(person.team_ids||[]);
 }
 function members(snapshot,teamId){return snapshot.employees.filter(e=>groupsOf(snapshot,e).includes(teamId));}
 function overview(snapshot){
  const counts=new Map();
  for(const person of snapshot.employees)
   for(const id of groupsOf(snapshot,person)){
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
   if(groupsOf(snapshot,person).some(id=>id!==teamId))shared++;
  }
  return {changed,total:rows.length,shared};
 }
 function teaching(snapshot,teamId,capacity){
  if(!teamId)throw new Error('Zuerst eine Gruppe wählen.');
  if(!Number.isInteger(capacity)||capacity<0)throw new Error('Begleitkapazität muss eine ganze Zahl ab 0 sein.');
  const rows=members(snapshot,teamId);
  if(!rows.length)throw new Error('Diese Gruppe hat im Projekt keine Mitglieder.');
  let changed=0;
  for(const person of rows){if(person.mentor_capacity===capacity)continue;person.mentor_capacity=capacity;changed++;}
  return {changed,total:rows.length};
 }
 function learning(snapshot,teamId,supervised){
  if(!teamId)throw new Error('Zuerst eine Gruppe wählen.');
  const rows=members(snapshot,teamId);
  if(!rows.length)throw new Error('Diese Gruppe hat im Projekt keine Mitglieder.');
  let changed=0,people=0,without=0;
  for(const person of rows){
   const before=changed;
   for(const approval of person.approvals||[]){
    if(approval.supervised===supervised)continue;approval.supervised=supervised;changed++;
   }
   if(!(person.approvals||[]).length)without++;
   if(changed>before)people++;
  }
  return {changed,people,total:rows.length,without};
 }
 const api={apply,overview,members,teaching,learning,groupsOf};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TeamScope=api;
})(globalThis);
