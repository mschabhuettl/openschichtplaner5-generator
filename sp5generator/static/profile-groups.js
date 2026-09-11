/* Explicit bulk assignment preserves individual rule profiles. */
(function(root){
 function apply(snapshot,profileId,teamId=''){
  const profile=snapshot.profiles.find(p=>p.id===profileId);
  if(!profile?.confirmed)throw new Error('Zuerst ein fachlich bestätigtes Profil wählen.');
  if(profile.valid_from>snapshot.context_start||profile.valid_until<snapshot.context_end)throw new Error('Das Profil muss den gesamten Planungs- und Randzeitraum abdecken.');
  const byId=new Map(snapshot.profiles.map(p=>[p.id,p]));let count=0;
  for(const person of snapshot.employees){
   if(teamId&&!person.team_ids.includes(teamId))continue;
   if(person.profile_ids.some(id=>{const p=byId.get(id);return !p||p.id!=='sp5:unconfirmed'||p.confirmed||p.source!=='unresolved';}))continue;
   person.profile_ids=[profileId];count++;
  }
  return count;
 }
 const api={apply};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ProfileGroups=api;
})(globalThis);
