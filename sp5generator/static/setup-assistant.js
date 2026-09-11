/* Explicit reuse from a user-confirmed identical source; never extend validity. */
(function(root){
 function prepare(imported,previous,options={}){
  const next=structuredClone(imported),report={newPeople:[],newServices:[],review:[],reusedPeople:0,classified:0};
  if(previous){
   if(!options.sameSource)throw Error('Identische SP5-Datenquelle für die Übernahme bestätigen.');
   if(!['sp5-api','sp5lib'].includes(next.metadata.adapter)||previous.timezone!==next.timezone||previous.metadata.adapter!==next.metadata.adapter)throw Error('Datenquelle oder Zeitzone unterscheiden sich. Ohne Übernahme importieren.');
   const oldPeople=new Map(previous.employees.map(e=>[e.id,e])),functions=new Set(next.positions.map(p=>p.function_id));
   const oldFunctions=new Set(previous.positions.map(p=>p.function_id));report.newServices=[...functions].filter(id=>!oldFunctions.has(id));
   const oldPositions=new Map(previous.positions.map(p=>[p.id,p])),matchedPositions=new Set();
   for(const position of next.positions){const old=oldPositions.get(position.id);
    if(!old||old.function_id!==position.function_id||old.workplace_id!==position.workplace_id)continue;
    matchedPositions.add(old.id);
    if(position.qualifications_required){
     // Keep current source requirements; never resolve conflicting active gates implicitly.
     const ids=p=>JSON.stringify([...new Set(p.qualification_ids??[])].sort());
     if(old.qualifications_required&&(ids(old)!==ids(position)||old.qualification_level!==position.qualification_level))report.review.push('Qualifikationsanforderungen für '+(position.name??position.id)+' unterscheiden sich zwischen bisherigem Projekt und aktuellem Import. Aktuelle Anforderungen wurden beibehalten; vor der Berechnung fachlich abgleichen.');
    }else{
     for(const key of ['qualifications_required','qualification_ids','qualification_level'])if(old[key]!==undefined)position[key]=structuredClone(old[key]);
    }
   }
   for(const old of previous.positions)if(old.qualifications_required&&!matchedPositions.has(old.id))report.review.push('Die frühere zusätzliche Qualifikationspflicht für '+(old.name??old.id)+' konnte keinem aktuellen Dienst und Arbeitsplatz eindeutig zugeordnet werden. Anforderungen vor der Berechnung prüfen.');
   const profileMap=new Map();
   for(const p of previous.profiles){if(!p.confirmed)continue;let id='reused:'+p.id;while(next.profiles.some(x=>x.id===id))id='reused:'+id;
    next.profiles.push({...structuredClone(p),id});profileMap.set(p.id,id);
    if(p.valid_from>next.context_start||p.valid_until<next.context_end)report.review.push('Ein übernommenes Profil deckt den neuen Randzeitraum nicht vollständig ab. Gültigkeit prüfen.');
   }
   for(const person of next.employees){const old=oldPeople.get(person.id);if(!old){report.newPeople.push(person.id);continue;}
    for(const key of ['allowed_kinds','preferred_kind','preferred_functions','allow_weekends','allow_holidays','approvals','qualifications','availability','mentor_capacity'])if(old[key]!==undefined)person[key]=structuredClone(old[key]);
    person.approvals=person.approvals.filter(a=>{if(functions.has(a.function_id))return true;report.review.push('Eine frühere Dienstfreigabe gehört zu einem nicht mehr importierten Dienst.');return false;});
    if(person.approvals.some(a=>a.valid_from>next.period_start||a.valid_until<next.period_end))report.review.push('Frühere Dienstfreigaben gelten nicht für den gesamten neuen Planungszeitraum.');
    const mapped=old.profile_ids.map(id=>profileMap.get(id));
    if(mapped.length&&mapped.every(Boolean))person.profile_ids=mapped;else report.review.push('Eine frühere Profilzuordnung ist unbestätigt oder fehlt; neue Zuordnung prüfen.');
    // Source absences, employment, teams and nominal hours belong to the new import.
    if(old.unavailable?.length)report.review.push('Abwesenheiten aus dem bisherigen Projekt wurden nicht kopiert; aktuellen Import prüfen.');
    report.reusedPeople++;
   }
   if(next.metadata.history_automation?.applied){const freshIds=new Set(report.newPeople);next.metadata.history_automation.applied=next.metadata.history_automation.applied.filter(a=>freshIds.has(a.employee_id));}
   if(previous.restrictions?.length||previous.wishes?.length)report.review.push('Individuelle Dienstsperren und datierte Wünsche aus dem bisherigen Projekt separat prüfen; nicht automatisch kopiert.');
   const priorShifts=new Map(previous.shifts.map(s=>[s.id,s]));
   const kinds=new Map(root.ServiceGroups.groups(previous).map(g=>[g.key,new Set(g.shiftIds.map(id=>priorShifts.get(id).kind).filter(k=>['day','night'].includes(k)))]));
   for(const group of root.ServiceGroups.groups(next)){const found=kinds.get(group.key);if(found?.size===1)root.ServiceGroups.apply(next,group.key,[...found][0]);else if(found?.size>1)report.review.push('Ein bisheriges Zeitmuster hat widersprüchliche Dienstarten; Zuordnung prüfen.');}
   if(previous.metadata.night_classification)next.metadata.night_classification=structuredClone(previous.metadata.night_classification);
  }else{report.newPeople=next.employees.map(e=>e.id);report.newServices=[...new Set(next.positions.map(p=>p.function_id))];}
  if(options.classify){const rule=options.rule??next.metadata.night_classification??{start:'22:00',end:'06:00',minimum:180};
   const proposals=root.ServiceGroups.groups(next).filter(g=>g.pending).map(g=>({g,p:root.ServiceGroups.suggest(g,rule.start,rule.end,rule.minimum)}));
   for(const {g,p} of proposals)if(p)report.classified+=root.ServiceGroups.apply(next,g.key,p.kind);else report.review.push('Ein Dienstzeitmuster konnte nicht automatisch zugeordnet werden.');
   next.metadata.night_classification=structuredClone(rule);
  }
  report.review=[...new Set(report.review)];next.metadata.setup_review=report;next.unresolved.push(...report.review.map(text=>'Einstellungsübernahme: '+text));
  if(previous)next.metadata.history_notice='Einstellungen vorhandener Personen aus dem bisherigen Projekt übernommen. Historienautomatik gilt nur für neue Personen; Gültigkeiten wurden nicht verlängert.';
  return next;
 }
 const api={prepare};if(typeof module!=='undefined'&&module.exports){root.ServiceGroups=require('./service-groups.js');module.exports=api;}else root.SetupAssistant=api;
})(globalThis);
