/* Explicit bulk assignment preserves individual rule profiles. */
(function(root){
 const caps=['max_daily_minutes','max_weekly_minutes','max_period_minutes',
             'max_work_days','max_nights','max_weekends',
             'max_consecutive_work_days','max_consecutive_nights'];
 function protectedRules(previous,replacement){
  // A still-unconfirmed import ID does not mean that its rules are untouched.
  // Keep explicit caps (including zero) assigned until individually reviewed.
  if(caps.some(key=>previous[key]!=null))return true;
  if(['min_rest_minutes','after_night_rest_minutes','after_night_block_rest_minutes','weekly_rest_minutes']
     .some(key=>(previous[key]??0)>(replacement[key]??0)))return true;
  if((previous.weekly_rest_minutes??0)>0){
   const defaults={weekly_rest_frame:'calendar_week',weekly_rest_window_days:7,weekly_rest_add_daily:false};
   if(Object.keys(defaults).some(key=>(previous[key]??defaults[key])!==(replacement[key]??defaults[key])))return true;
  }
  return (previous.after_night_block_rest_minutes??0)>0&&
         (previous.night_block_gap_days??1)!==(replacement.night_block_gap_days??1);
 }
 function apply(snapshot,profileId,teamId=''){
  const profile=snapshot.profiles.find(p=>p.id===profileId);
  if(!profile?.confirmed)throw new Error('Zuerst ein fachlich bestätigtes Profil wählen.');
  if(profile.valid_from>snapshot.context_start||profile.valid_until<snapshot.context_end)throw new Error('Das Profil muss den gesamten Planungs- und Randzeitraum abdecken.');
  const byId=new Map(snapshot.profiles.map(p=>[p.id,p]));let count=0;
  for(const person of snapshot.employees){
   if(teamId&&!person.team_ids.includes(teamId))continue;
   if(person.profile_ids.some(id=>{const p=byId.get(id);return !p||p.id!=='sp5:unconfirmed'||p.confirmed||p.source!=='unresolved'||protectedRules(p,profile);}))continue;
   person.profile_ids=[profileId];count++;
  }
  return count;
 }
 const api={apply};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ProfileGroups=api;
})(globalThis);
