'use strict';
let snapshot=null, assignments=[], jobId=null, timer=null, previous=[];
let groups=[], checkedTeams=new Set(), transposed=false, planMonth="", solving=false;
let dirty=false, jsonDirty=false, changeVersion=0, activePanel='projects', projectBusy=false, personDraft=false;
let indexVersion=-1, indexes=null, matrixCache=null, stateFrame=null, jsonVersion=-1;
const renderedPanels=new Map(), collections=new Map();
let savedRequest=0,jobsRequest=0;
let readinessVersion=-1,readinessPending=-1,readinessRequest=0;
const fold=value=>String(value??'').toLocaleLowerCase('de-DE');
function dataIndex(){
 if(indexVersion===changeVersion&&indexes)return indexes;
 const keyed=rows=>new Map(rows.map(row=>[row.id,row]));
 indexes={demandLabels:new Map(),employees:keyed(snapshot.employees),shifts:keyed(snapshot.shifts),demands:keyed(snapshot.demands),positions:keyed(snapshot.positions),workplaces:keyed(snapshot.metadata.workplaces??[]),groups:new Map((snapshot.metadata.group_tree??[]).flatMap(g=>[[String(g.id),g],['sp5:group:'+g.id,g]])),history:new Map((snapshot.metadata.history_matrix??[]).map(row=>[row.employee_id,row]))};
 indexVersion=changeVersion;matrixCache=null;return indexes;
}
function plannerState(){return {snapshot,assignments,dirty,jsonDirty,jobId,solving,projectBusy};}
function publishState(){
 if(stateFrame!==null)return;
 stateFrame=requestAnimationFrame(()=>{stateFrame=null;window.dispatchEvent(new CustomEvent('planner:state',{detail:plannerState()}));refreshAutomaticReadiness();});
}
function navigate(panel){
 if(window.PlannerUI?.navigate){window.PlannerUI.refresh?.(plannerState());window.PlannerUI.navigate(panel);}
 else{activePanel=panel;renderActivePanel();}
}
function syncJson(force=false){
 if(!snapshot||jsonDirty||(!force&&!$('json').closest('details')?.open)||jsonVersion===changeVersion)return;
 $('json').value=JSON.stringify(currentSnapshot(),null,2);jsonVersion=changeVersion;
}
function pageState(key,size=30){if(!collections.has(key))collections.set(key,{page:0,size,query:''});return collections.get(key);}
function debounce(fn,delay=180){let pending;return (...args)=>{clearTimeout(pending);pending=setTimeout(()=>fn(...args),delay);};}
function pagination(parent,state,count,redraw,label='Einträge'){
 const pages=Math.max(1,Math.ceil(count/state.size));state.page=Math.max(0,Math.min(state.page,pages-1));
 const bar=el('div',undefined,parent);bar.className='pagination';bar.setAttribute('aria-label',label+' Seiten');
 if(pages===1){el('span',`${count} ${label}`,bar);return 0;}
 const start=count?state.page*state.size+1:0,end=Math.min(count,(state.page+1)*state.size);
 el('span',`${start}–${end} von ${count} ${label}`,bar);
 const prev=button(bar,'Zurück',()=>{state.page--;redraw();});prev.disabled=state.page===0;prev.setAttribute('aria-label',label+': vorherige Seite');
 el('span',`Seite ${state.page+1} / ${pages}`,bar);
 const next=button(bar,'Weiter',()=>{state.page++;redraw();});next.disabled=state.page>=pages-1;next.setAttribute('aria-label',label+': nächste Seite');
 return state.page*state.size;
}
function collection(parent,key,items,{label='Einträge',size=30,search=null,redraw}){
 const state=pageState(key,size);parent.replaceChildren();
 if(search){const bar=el('div',undefined,parent);bar.className='collection-toolbar';const l=el('label',`${label} suchen`,bar),input=el('input',undefined,l);input.type='search';input.placeholder='Name oder Suchbegriff';input.value=state.query;input.dataset.collectionSearch=key;
 input.oninput=debounce(()=>{const value=input.value,position=input.selectionStart;state.query=value;state.page=0;redraw();const replacement=document.querySelector(`[data-collection-search="${key}"]`);replacement?.focus({preventScroll:true});try{replacement?.setSelectionRange(position,position);}catch{};});
 if(state.query)items=items.filter(item=>fold(search(item)).includes(fold(state.query.trim())));
 }
 const offset=pagination(parent,state,items.length,redraw,label),content=el('div',undefined,parent);content.className='collection-content';
 return {items:items.slice(offset,offset+state.size),content,offset,total:items.length};
}
function detailsVisible(id){const details=$(id)?.closest('details');return !details||details.open;}
function renderActivePanel(force=false){
 if(!snapshot)return;
 if(!force&&renderedPanels.get(activePanel)===changeVersion)return;
 if(activePanel==='team'){renderMatrix();if(detailsVisible('people'))renderPeople();renderHistory();}
 if(activePanel==='rules')renderRules();
 if(activePanel==='plan')renderPlan();
 renderedPanels.set(activePanel,changeVersion);syncJson();updateJobButtons();
}

const $=id=>document.getElementById(id);
const el=(tag,text,parent)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(parent)parent.append(n);return n;};
const notice=(text,error=false)=>{$('notice').textContent=text;$('notice').classList.toggle('error',error);};
async function responseError(response){
 let payload;
 try{payload=await response.json();}catch{payload=null;}
 const fields=payload?.fields?.map(f=>f.location.filter(x=>x!=='body').join('.')).filter(Boolean);
 const message=typeof payload?.detail==='string'?payload.detail:`Anfrage fehlgeschlagen (HTTP ${response.status}). Bitte erneut versuchen.`;
 const error=Error(message+(fields?.length?' Betroffene Felder: '+fields.join(', '):''));error.status=response.status;return error;
}
async function api(path,method='GET',data){
 let r;
 try{r=await fetch(path,{method,headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});}
 catch{throw Error('Server nicht erreichbar. Verbindung prüfen und erneut versuchen. Änderungen bleiben in dieser Ansicht erhalten.');}
 if(!r.ok)throw await responseError(r);
 if(!r.headers.get('content-type')?.includes('application/json'))throw Error('Keine gültige Serverantwort. Bei abgelaufener Anmeldung die Seite neu laden. Ungespeicherte Änderungen vorher als Projekt sichern.');
 return r.json();
}
async function runAction(b,fn){if(b.disabled||b.dataset.busy==='true')return;b.dataset.busy='true';const disabled=b.disabled;b.disabled=true;b.setAttribute('aria-busy','true');updateJobButtons();try{await fn();}catch(e){notice(e.message,true);}finally{delete b.dataset.busy;b.removeAttribute('aria-busy');b.disabled=disabled;updateJobButtons();}}
const lockedControls=new Map();
function updateJobButtons(){
 $('cancel').disabled=!jobId||$('cancel').dataset.busy==='true';
 const switchIds=['demo','import','restore','restoreJob','applyJson','file'];
 const busy=projectBusy||solving||!!jobId||['save','saveDraft'].some(id=>$(id).dataset.busy==='true')||switchIds.some(id=>$(id).dataset.busy==='true');
 for(const id of switchIds)$(id).disabled=busy||(id==='restore'&&!$('saved').value)||(id==='restoreJob'&&!$('savedJobs').value);
 $('save').disabled=busy;$('saveDraft').disabled=busy;if($('addPerson'))$('addPerson').disabled=busy;
 for(const id of ['solve','recompute'])$(id).disabled=busy||$(id).dataset.busy==='true';
 const editing='#setupReview, #serviceGroups, #matrix, #people, #details, #history, #shifts, #positions, #demands, #profiles, #unresolved, #weights, #contextConfirmation, #plan';
 const regions=[...document.querySelectorAll(editing)];for(const region of regions)region.inert=busy;
 $('json').readOnly=busy;
 const controls=[$('confirmHistory'),$('refreshJson')];
 if(busy){for(const input of controls){if(!lockedControls.has(input))lockedControls.set(input,input.disabled);input.disabled=true;}}
 else{for(const [input,disabled] of lockedControls)input.disabled=disabled;lockedControls.clear();}
 publishState();
}
function projectId(){
 if(typeof crypto.randomUUID==='function')return crypto.randomUUID();
 const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function currentSnapshot(){return {...snapshot,assignments:structuredClone(assignments)};}
function updateSaveStatus(){
 $('saveStatus').textContent=jsonDirty?'JSON-Änderungen noch nicht übernommen.':dirty?'Ungespeicherte Änderungen':`Gespeicherter Stand ${snapshot?.revision??''}`;
 $('saveStatus').classList.toggle('bad',dirty||jsonDirty);publishState();
}
function markChanged(){changeVersion++;dirty=true;updateSaveStatus();}
function canReplace(){return !(dirty||jsonDirty)||window.confirm('Ungespeicherte Änderungen verwerfen und einen anderen Stand öffnen? Mit Abbrechen können Sie den aktuellen Stand zuerst speichern oder als Projekt sichern.');}
window.addEventListener('beforeunload',event=>{if(dirty||jsonDirty){event.preventDefault();event.returnValue='';}});
function action(id,fn){$(id).onclick=()=>runAction($(id),fn);}
function field(parent,label,value,change,type='text'){const l=el('label',label,parent),i=el('input',undefined,l);i.type=type;if(type==='number')i.step='any';if(type==='checkbox')i.checked=!!value;else i.value=value??'';i.onchange=()=>{change(type==='checkbox'?i.checked:type==='number'?(i.value===''?null:Number(i.value)):i.value);invalidateResult();};return i;}
function select(parent,label,value,options,change){const l=el('label',label,parent),s=el('select',undefined,l);for(const [v,t] of options){const o=el('option',t,s);o.value=v;}s.value=value;s.onchange=()=>{change(s.value);invalidateResult();};return s;}
function button(parent,text,fn){const b=el('button',text,parent);b.type='button';b.onclick=()=>runAction(b,fn);return b;}
function table(parent,head){parent.replaceChildren();const t=el('table',undefined,parent),tr=el('tr',undefined,el('thead',undefined,t));head.forEach(x=>{const th=el('th',x,tr);th.scope='col';});return el('tbody',undefined,t);}
async function saved(){
 const request=++savedRequest,list=[];for(let offset=0;offset<=1000000;offset+=1000){const page=await api('/api/snapshots?limit=1000&offset='+offset);if(request!==savedRequest)return;list.push(...page);if(page.length<1000)break;}const selected=snapshot?.id??$('saved').value;$('saved').replaceChildren();
 if(!list.length)el('option','Keine gespeicherten Projekte',$('saved')).value='';
 list.forEach(x=>{const o=el('option',`${x.project_name??x.name??'Projekt'} · ${x.period_start??x.id} bis ${x.period_end??''} · ${x.employee_count??'?'} Personen · Stand ${x.revision} · ${x.id.slice(0,8)}`,$('saved'));o.value=x.id;});
 if(list.some(x=>x.id===selected))$('saved').value=selected;window.PlannerUI?.setProjects?.(list);updateJobButtons();
}
const jobStates={queued:'In Warteschlange',running:'Berechnung läuft',succeeded:'Berechnung beendet',failed:'Fehlgeschlagen',cancelled:'Abgebrochen'};
async function savedJobs(){
 const request=++jobsRequest,list=await api('/api/jobs');if(request!==jobsRequest)return;const selected=jobId??$('savedJobs').value;$('savedJobs').replaceChildren();
 if(!list.length)el('option','Keine Berechnungen vorhanden',$('savedJobs')).value='';
 list.forEach(j=>{const date=new Date(j.created_at*1000).toLocaleString('de-DE');const o=el('option',`${date} · ${jobStates[j.state]??j.state} · ${j.snapshot_id}`,$('savedJobs'));o.value=j.id;});
 if(list.some(j=>j.id===selected))$('savedJobs').value=selected;window.PlannerUI?.setJobs?.(list);updateJobButtons();
}
async function readProject(text){
 let candidate;try{candidate=JSON.parse(text);}catch{throw Error('Ungültige JSON-Datei. Syntax prüfen; der aktuelle Stand wurde beibehalten.');}
 if(candidate?.snapshot_id&&!candidate?.employees)throw Error('Diese Datei ist ein Prüfergebnis. Zum Weiterarbeiten die vollständige Datei aus „Projekt als JSON sichern“ laden oder eine gespeicherte Berechnung öffnen.');
 return api('/api/snapshots/check','POST',candidate);
}
function load(s,persisted=false){
 new Intl.DateTimeFormat('de-DE',{timeZone:s.timezone}).format();if(s.period_start>s.period_end)throw Error('Planungsbeginn muss vor dem Planungsende liegen.');
 clearTimeout(timer);timer=null;jobId=null;previous=[];$('cancel').disabled=true;$('job').textContent='';$('result').replaceChildren();$('validation').textContent='';$('validationSummary')?.remove();
 snapshot=s;personDraft=false;assignments=structuredClone(s.assignments);changeVersion++;dirty=!persisted;jsonDirty=false;jsonVersion=-1;indexes=null;matrixCache=null;renderedPanels.clear();collections.clear();
 for(const id of ['details','people','history','shifts','positions','demands','profiles','plan','calendar','matrix'])$(id).replaceChildren();
 $('json').value='';updateSaveStatus();updateJobButtons();$('planView').querySelector('[value=positions]').textContent=serviceMatrix()?'Einsatzplan · Dienste':'Einsatzplan · Funktionen / Arbeitsplätze';
 $('start').value=s.period_start;$('end').value=s.period_end;$('timezone').value=s.timezone;$('matrixSearch').value='';
 if(s.metadata.history_period){$('historyStart').value=s.metadata.history_period.start;$('historyEnd').value=s.metadata.history_period.end;}else historyDefaults();
 if(s.metadata.night_classification){$('setupNightStart').value=s.metadata.night_classification.start;$('setupNightEnd').value=s.metadata.night_classification.end;$('setupNightMin').value=s.metadata.night_classification.minimum;}
 planMonth=s.period_start.slice(0,7);$('workspace').hidden=false;activePanel='team';render();navigate('team');updateJobButtons();
 notice(`Daten geladen: ${s.employees.length} Personen${s.metadata.selected_group_ids?' aus '+s.metadata.selected_group_ids.length+' ausgewählten Teams':''}. Regeln und offene Angaben prüfen.`);
}
function render(){
 $('source').textContent=`Quelle: ${snapshot.source==='synthetic'?'SYNTHETISCHE DEMO':snapshot.source} · ${snapshot.period_start} bis ${snapshot.period_end} · ${snapshot.timezone} · Stand ${snapshot.revision}`;
 renderActivePanel(true);publishState();
}
function setTargetHours(person,value){person.target_minutes=value===null?null:Math.round(value*60);for(const input of document.querySelectorAll('[data-employee-hours]'))if(input.dataset.employeeHours===person.id&&input!==document.activeElement)input.value=value===null?'':String(value);}
function renderPeople(){
 const view=collection($('people'),'people',snapshot.employees,{label:'Personen',search:e=>e.name+' '+e.id,redraw:renderPeople});
 const body=table(view.content,['Person','Dienstart','Bevorzugt','Sollstunden','Teams','Profile','Details']),idx=dataIndex();
 view.items.forEach(e=>{const tr=el('tr',undefined,body);el('td',e.name||'Neue Person',tr);select(el('td',undefined,tr),'Erlaubt',e.allowed_kinds.join(','),[['day','Nur Tag'],['night','Nur Nacht'],['day,night','Tag und Nacht']],v=>e.allowed_kinds=v.split(','));select(el('td',undefined,tr),'Wunsch',e.preferred_kind??'',[['','Keine Präferenz'],['day','Bevorzugt Tag'],['night','Bevorzugt Nacht']],v=>e.preferred_kind=v||null);const hours=field(el('td',undefined,tr),'Stunden',e.target_minutes==null?'':e.target_minutes/60,v=>setTargetHours(e,v),'number');hours.dataset.employeeHours=e.id;hours.required=true;hours.min='0';el('td',e.team_ids.map(id=>idx.groups.get(id)?.name??id).join(', '),tr);el('td',e.profile_ids.join(', '),tr);button(el('td',undefined,tr),'Bearbeiten',()=>personDetails(e));});
}
function addPerson(){
 if(projectSwitchBusy())throw Error('Die laufende Aktion zuerst abschließen.');
 if(personDraft&&!window.confirm('Nicht übernommene Abwesenheit verwerfen?'))return;personDraft=false;
 const person={id:'person-'+projectId(),name:'',team_ids:[],employment_start:snapshot.period_start,employment_end:snapshot.period_end,approvals:[],qualifications:[],availability:[],unavailable:[],allowed_kinds:['day','night'],preferred_kind:null,preferred_functions:[],allow_weekends:true,allow_holidays:true,profile_ids:[],target_minutes:null,balance_minutes:0,credit_minutes:0,employment_fraction:100,historical_nights:0,historical_weekends:0,historical_holidays:0,mentor_capacity:0};
 snapshot.employees.push(person);invalidateResult();$('matrixSearch').value='';pageState('matrixPeople',30).page=Math.floor((snapshot.employees.length-1)/30);const people=pageState('people',30);people.query='';people.page=Math.floor((snapshot.employees.length-1)/30);renderActivePanel(true);personDetails(person);$('details').querySelector('input')?.focus();notice('Neue Person angelegt. Name, Sollstunden, Team und Regelprofile festlegen; Freigaben ausdrücklich erteilen.');
}
function removePerson(person){
 if(projectSwitchBusy())throw Error('Die laufende Aktion zuerst abschließen.');
 const current=assignments.filter(a=>a.employee_id===person.id),fixed=snapshot.assignments.filter(a=>a.employee_id===person.id&&a.fixed),references=snapshot.restrictions.filter(r=>r.employee_id===person.id).length+snapshot.wishes.filter(w=>w.employee_id===person.id).length;
 if(!window.confirm(`${person.name||'Diese Person'} aus dem Projekt entfernen? Dabei werden ${current.length} aktuelle Einteilungen, ${fixed.length} gespeicherte Fixierungen sowie ${references} Wünsche und Dienstsperren dieser Person entfernt. Auch persönliche Freigaben, Abwesenheiten und die historische Personenbasis werden entfernt. Die Änderung wird mit dem nächsten Speichern dauerhaft.`))return;
 personDraft=false;snapshot.employees=snapshot.employees.filter(e=>e.id!==person.id);assignments=assignments.filter(a=>a.employee_id!==person.id);snapshot.assignments=snapshot.assignments.filter(a=>a.employee_id!==person.id);snapshot.restrictions=snapshot.restrictions.filter(r=>r.employee_id!==person.id);snapshot.wishes=snapshot.wishes.filter(w=>w.employee_id!==person.id);previous=previous.filter(a=>a.employee_id!==person.id);
 const isPerson=row=>String(row.employee_id)===person.id||'sp5:employee:'+row.employee_id===person.id;
 for(const key of ['history_matrix','context_schedule','reference_schedule'])if(Array.isArray(snapshot.metadata[key]))snapshot.metadata[key]=snapshot.metadata[key].filter(row=>!isPerson(row));
 for(const key of ['direct_group_memberships','provenance'])if(snapshot.metadata[key])delete snapshot.metadata[key][person.id];
 if(Array.isArray(snapshot.metadata.unresolved_native?.reference_schedule))snapshot.metadata.unresolved_native.reference_schedule=snapshot.metadata.unresolved_native.reference_schedule.filter(row=>!isPerson(row));
 $('details').replaceChildren();invalidateResult();renderActivePanel(true);notice('Person und zugehörige Einteilungen entfernt. Den verbleibenden Bedarf prüfen und Projekt speichern.');
}
function localDateTime(value){
 const formatter=new Intl.DateTimeFormat('sv-SE',{timeZone:snapshot.timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const parts=Object.fromEntries(formatter.formatToParts(new Date(value)).map(part=>[part.type,part.value]));return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
function personDetails(e){
 if(personDraft&&!window.confirm('Nicht übernommene Abwesenheit verwerfen?'))return;personDraft=false;navigate('team');
 const box=$('details');box.replaceChildren();const title=el('h3',e.name,box);box.classList.add('person-editor');
 const grid=el('div',undefined,box);grid.className='grid';
 const name=field(grid,'Name',e.name,v=>{e.name=v.trim();title.textContent=e.name;});name.required=true;name.maxLength=160;
 const fraction=field(grid,'Beschäftigung in %',e.employment_fraction,v=>e.employment_fraction=v,'number');fraction.min='1';fraction.max='100';fraction.step='1';
 const hoursGroup=el('div',undefined,grid);
 const hours=field(hoursGroup,'Sollstunden im Planungszeitraum',e.target_minutes==null?'':e.target_minutes/60,v=>setTargetHours(e,v),'number');hours.dataset.employeeHours=e.id;hours.min='0';hours.required=true;hours.placeholder='Sollstunden festlegen';
 const hoursHelp=el('p','Das Soll gilt für den gesamten Planungszeitraum, nicht pro Woche. Maximale Wochenstunden sind eine separate verbindliche Regel.',hoursGroup);hoursHelp.id='personHoursHelp';hoursHelp.className='helper-text';hours.setAttribute('aria-describedby',hoursHelp.id);
 const origin=snapshot.metadata?.provenance?.[e.id]?.nominal_hours;
 const bases={0:['Tagesbasis','hours_day','Tag'],1:['Wochenbasis','hours_week','Woche'],2:['Monatsbasis','hours_month','Monat'],3:['Gesamtbasis','hours_total','Beschäftigungszeitraum']};
 if(origin&&Number.isInteger(origin.calcbase)&&Object.hasOwn(bases,origin.calcbase)){
  const [basis,key,unit]=bases[origin.calcbase];
  if(Number.isFinite(origin[key])&&Number.isFinite(origin.target_minutes)&&/^\d{4}-\d{2}-\d{2}$/.test(origin.period_start)&&/^\d{4}-\d{2}-\d{2}$/.test(origin.period_end)){
   const imported=el('p',`SP5-Importstand: ${basis} mit ${origin[key].toLocaleString('de-DE')} Stunden je ${unit}. Berechnetes Soll für ${origin.period_start} bis ${origin.period_end}: ${(origin.target_minutes/60).toLocaleString('de-DE')} Stunden. Teilzeiträume werden nach der SP5-Quellenformel berechnet, nicht pauschal umgerechnet. Das oben bearbeitbare Soll kann inzwischen abweichen.`,hoursGroup);imported.className='helper-text';imported.id='personHoursOrigin';hours.setAttribute('aria-describedby',`${hoursHelp.id} ${imported.id}`);
   if(origin.bookings_included===false)imported.append(document.createTextNode(' Sollbuchungen sind im Importwert nicht enthalten; separat prüfen.'));
  }
 }
 field(grid,'Beschäftigt ab',e.employment_start,v=>e.employment_start=v,'date');field(grid,'Beschäftigt bis',e.employment_end,v=>e.employment_end=v,'date');
 field(grid,'Saldo Minuten',e.balance_minutes,v=>e.balance_minutes=v,'number');
 select(grid,'Erlaubte Dienstart',e.allowed_kinds.join(','),[['day','Nur Tag'],['night','Nur Nacht'],['day,night','Tag und Nacht']],v=>e.allowed_kinds=v.split(','));
 select(grid,'Bevorzugte Dienstart',e.preferred_kind??'',[['','Keine Präferenz'],['day','Tag'],['night','Nacht']],v=>e.preferred_kind=v||null);
 field(grid,'Wochenenden erlaubt',e.allow_weekends,v=>e.allow_weekends=v,'checkbox');field(grid,'Feiertage erlaubt',e.allow_holidays,v=>e.allow_holidays=v,'checkbox');
 const teams=el('fieldset',undefined,box);el('legend','Teams',teams);const knownTeams=new Set([...snapshot.shifts.map(shift=>shift.team_id),...snapshot.employees.flatMap(person=>person.team_ids)]);for(const id of knownTeams)field(teams,dataIndex().groups.get(id)?.name??id,e.team_ids.includes(id),checked=>{e.team_ids=checked?[...new Set([...e.team_ids,id])]:e.team_ids.filter(value=>value!==id);},'checkbox');
 const profiles=el('fieldset',undefined,box);el('legend','Zugeordnete Regelprofile',profiles);const known=new Set(snapshot.profiles.map(p=>p.id));
 for(const profile of snapshot.profiles)field(profiles,`${profile.id} · ${profile.confirmed?'bestätigt':'noch unbestätigt'}`,e.profile_ids.includes(profile.id),checked=>{e.profile_ids=checked?[...new Set([...e.profile_ids,profile.id])]:e.profile_ids.filter(id=>id!==profile.id);},'checkbox');
 for(const id of e.profile_ids.filter(id=>!known.has(id)))field(profiles,`${id} · Profil fehlt im Projekt`,true,checked=>{if(!checked)e.profile_ids=e.profile_ids.filter(value=>value!==id);},'checkbox');
 if(!snapshot.profiles.length)el('p','Noch keine Regelprofile im Projekt vorhanden.',profiles);
 el('h3','Abwesenheiten',box);el('p',`Urlaub, Krankenstand und andere gesperrte Zeiträume. Alle Zeiten gelten in ${snapshot.timezone}; das Ende gehört nicht mehr zur Abwesenheit.`,box);
 const absences=el('div',undefined,box),absenceForm=el('div',undefined,box);
 const drawAbsences=()=>{absences.replaceChildren();if(!e.unavailable.length)el('p','Keine Abwesenheiten erfasst.',absences);e.unavailable.forEach((interval,index)=>{const row=el('div',undefined,absences);row.className='absence-row card';el('span',`${localDateTime(interval.start).replace('T',' ')} – ${localDateTime(interval.end).replace('T',' ')}`,row);button(row,'Abwesenheit bearbeiten',()=>editAbsence(interval,index));button(row,'Abwesenheit entfernen',()=>{if(personDraft)throw Error('Die offene Abwesenheit zuerst übernehmen oder verwerfen.');e.unavailable.splice(index,1);invalidateResult();drawAbsences();});});};
 const editAbsence=(interval=null,index=null)=>{
  if(personDraft&&!window.confirm('Nicht übernommene Abwesenheit verwerfen?'))return;personDraft=false;absenceForm.replaceChildren();
  const group=el('fieldset',undefined,absenceForm);el('legend',interval?'Abwesenheit bearbeiten':'Neue Abwesenheit',group);const row=el('div',undefined,group);row.className='grid';
  const input=(label,value)=>{const wrap=el('label',label,row),control=el('input',undefined,wrap);control.type='datetime-local';control.required=true;control.value=value;control.oninput=()=>{personDraft=true;invalidateResult();};return control;};
  const from=input('Abwesend ab',interval?localDateTime(interval.start):snapshot.period_start+'T00:00'),until=input('Abwesend bis',interval?localDateTime(interval.end):dayOffset(snapshot.period_start,1)+'T00:00');
  button(group,'Abwesenheit übernehmen',async()=>{
   if(!from.reportValidity()||!until.reportValidity())return;if(until.value<=from.value)throw Error('Das Ende der Abwesenheit muss nach dem Beginn liegen.');
   projectBusy=true;updateJobButtons();try{const resolved=await api('/api/intervals/resolve','POST',{timezone:snapshot.timezone,start:from.value,end:until.value});if(index===null)e.unavailable.push(resolved);else e.unavailable[index]=resolved;personDraft=false;absenceForm.replaceChildren();invalidateResult();drawAbsences();notice('Abwesenheit übernommen. Projekt speichern und Entwurf erneut prüfen.');}finally{projectBusy=false;updateJobButtons();}
  });
  button(group,'Abbrechen',()=>{personDraft=false;absenceForm.replaceChildren();});from.focus();
 };
 drawAbsences();button(box,'Abwesenheit hinzufügen',()=>editAbsence());
 el('h3','Freigaben',box);const approvals=el('div',undefined,box);
 const draw=()=>{approvals.replaceChildren();const positions=approvalPositions(),byId=new Map(positions.map(p=>[p.id,p]));e.approvals.forEach((a,i)=>{const row=el('div',undefined,approvals);row.className='grid card';select(row,'Dienst / Arbeitsplatz',positions.find(p=>samePosition(a,p))?.id??'', [['','Position auswählen'],...positions.map(p=>[p.id,p.name])],id=>{const p=byId.get(id);if(p){a.function_id=p.function_id;a.workplace_id=p.workplace_id;}});field(row,'Gültig ab',a.valid_from,v=>a.valid_from=v,'date');field(row,'Gültig bis',a.valid_until,v=>a.valid_until=v,'date');field(row,'Betreuung erforderlich',a.supervised,v=>a.supervised=v,'checkbox');button(row,'Entfernen',()=>{e.approvals.splice(i,1);invalidateResult();draw();});});};
 draw();button(box,'Freigabe hinzufügen',()=>{e.approvals.push({function_id:'',workplace_id:'',valid_from:snapshot.period_start,valid_until:snapshot.period_end,supervised:false});invalidateResult();draw();});
 el('h3','Verfügbarkeit',box);el('p','Ein Dienst muss vollständig in erlaubte Zeitfenster passen. Ohne Zeitfenster ist die Person zeitlich nicht eingeschränkt. Mehrere Fenster und wechselnde Wochen sind möglich.',box);
 const avail=el('div',undefined,box);
 const drawAvail=()=>{avail.replaceChildren();e.availability.forEach((a,i)=>{const row=el('div',undefined,avail);row.className='card';const dates=el('div',undefined,row);dates.className='grid';field(dates,'Gültig ab',a.valid_from,v=>a.valid_from=v,'date');field(dates,'Gültig bis',a.valid_until,v=>a.valid_until=v,'date');
 const weekdays=el('fieldset',undefined,row);weekdays.className='weekday-picker';el('legend','Erlaubte Wochentage',weekdays);['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag'].forEach((day,index)=>field(weekdays,day,a.weekdays.includes(index),enabled=>{a.weekdays=enabled?[...new Set([...a.weekdays,index])].sort((x,y)=>x-y):a.weekdays.filter(x=>x!==index);},'checkbox'));
 const times=el('div',undefined,row);times.className='grid';field(times,'Von',a.start_time,v=>a.start_time=v,'time');const end=field(times,'Bis (24:00 möglich)',a.end_time,v=>a.end_time=v);end.pattern='(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00';
 const cycle=field(times,'Alle wie viele Wochen?',a.cycle_weeks,v=>a.cycle_weeks=v,'number');cycle.min='1';cycle.step='1';const phase=field(times,'Woche im Zyklus (erste = 0)',a.cycle_phase,v=>a.cycle_phase=v,'number');phase.min='0';phase.step='1';field(times,'Zyklus beginnt am',a.cycle_anchor??'',v=>a.cycle_anchor=v||null,'date');button(row,'Zeitfenster entfernen',()=>{e.availability.splice(i,1);invalidateResult();drawAvail();});});};
 drawAvail();button(box,'Zeitfenster hinzufügen',()=>{e.availability.push({valid_from:snapshot.period_start,valid_until:snapshot.period_end,weekdays:[0,1,2,3,4],start_time:'08:00',end_time:'13:00',cycle_weeks:1,cycle_phase:0,cycle_anchor:null,source:'additional'});invalidateResult();drawAvail();});
 const remove=button(box,'Person entfernen',()=>removePerson(e));remove.id='removePerson';remove.className='danger';
 button(box,'Details schließen',()=>{if(personDraft&&!window.confirm('Nicht übernommene Abwesenheit verwerfen?'))return;personDraft=false;box.replaceChildren();render();});box.scrollIntoView({block:'start',behavior:'smooth'});
}
function renderHistory(){
 const box=$('history'),rows=snapshot.metadata.history_matrix??[],idx=dataIndex();
 if(!rows.length){box.replaceChildren();el('p','Keine historischen Vorschläge vorhanden.',box);return;}
 const view=collection(box,'history',rows,{label:'Historische Personen',size:20,search:row=>idx.employees.get(row.employee_id)?.name,redraw:renderHistory});
 el('p',snapshot.metadata.history_automation?`${snapshot.metadata.history_automation.applied.length} Dienstfreigaben automatisch aus mindestens ${snapshot.metadata.history_automation.minimum_days} verschiedenen Einsatztagen übernommen. Qualifikationen und Einschränkungen bleiben unverändert.`:snapshot.metadata.history_notice??'Historie ist kein Qualifikationsnachweis. Vorschläge werden erst durch ausdrückliche Freigabe nutzbar.',view.content);
 const positions=new Map(matrixPositions().map(p=>[JSON.stringify([p.function_id,p.workplace_id]),p]));
 view.items.forEach(row=>{const e=idx.employees.get(row.employee_id);if(!e)return;
 const card=el('details',undefined,view.content);el('summary',`${e.name}: ${row.observed_assignment_count} historische Einsätze · ${row.first_date??''} bis ${row.last_date??''}`,card);
 const content=el('div',undefined,card);card.ontoggle=()=>{if(!card.open||content.childNodes.length)return;
 el('p',(row.observed_shifts??[]).map(s=>`${s.name}: ${s.count}`).join(' · '),content);
 (row.suggested_approvals??[]).forEach(a=>{const p=positions.get(JSON.stringify([a.function_id,a.workplace_id]));if(!p)return;
 const line=el('p',`${p.name} · ${a.evidence_count} beobachtete Einsätze `,content);
 const exists=approved(e,p);const b=button(line,exists?'Im Planungszeitraum freigegeben':'Für Planungszeitraum ausdrücklich freigeben',()=>{setApproval(e,p,true);renderMatrix();renderHistory();});b.disabled=exists;});};});
}
function demandLabel(d){const idx=dataIndex();if(idx.demandLabels.has(d.id))return idx.demandLabels.get(d.id);const s=idx.shifts.get(d.shift_id),p=idx.positions.get(d.position_id);const label=`${s?.segments[0]?localDay(s.segments[0].start)+' · ':''}${s?.name??'Dienst'}${p?.name&&p.name!==s?.name?' / '+p.name:''} · ${(s?.segments??[]).map(x=>localTime(x.start)+'–'+localTime(x.end)+(localDay(x.end)!==localDay(x.start)?' (Folgetag)':'')).join(' / ')}`;idx.demandLabels.set(d.id,label);return label;}
function renderShifts(){
 const view=collection($('shifts'),'shifts',snapshot.shifts,{label:'Schichten',size:30,search:s=>s.name+' '+s.segments.map(x=>localDay(x.start)).join(' '),redraw:renderShifts});
 const body=table(view.content,['Schicht','Dienstart','Zeitfenster']);view.items.forEach(s=>{const tr=el('tr',undefined,body);el('td',s.name,tr);select(el('td',undefined,tr),'Art',s.kind,[['unconfirmed','Noch festzulegen'],['day','Tag'],['night','Nacht']],v=>s.kind=v);el('td',s.segments.map(x=>`${localDay(x.start)} · ${localTime(x.start)}–${localTime(x.end)}`).join(' / '),tr);});
}
function renderPositions(){
 const view=collection($('positions'),'positions',snapshot.positions,{label:'Positionen',size:30,search:p=>p.name+' '+workplaceName(p.workplace_id),redraw:renderPositions});
 const body=table(view.content,['Position','Funktion / Arbeitsplatz','Qualifikation']);view.items.forEach(p=>{const tr=el('tr',undefined,body);el('td',p.name,tr);el('td',`${p.name} / ${workplaceName(p.workplace_id)}`,tr);const cell=el('td',undefined,tr);field(cell,'Nachweis erforderlich',p.qualifications_required,v=>p.qualifications_required=v,'checkbox');field(cell,'Qualifikations-IDs (Komma)',p.qualification_ids.join(','),v=>p.qualification_ids=v.split(',').map(x=>x.trim()).filter(Boolean));});
}
function renderDemands(){
 const view=collection($('demands'),'demands',snapshot.demands,{label:'Bedarfe',size:40,search:d=>demandLabel(d)+' '+d.id,redraw:renderDemands});
 const body=table(view.content,['Dienst und Zeit','Mindestens Personen','Höchstens Personen','Details']);view.items.forEach(d=>{const tr=el('tr',undefined,body);el('td',demandLabel(d),tr);const min=field(el('td',undefined,tr),'Min',d.minimum,v=>d.minimum=v,'number');min.min='0';min.step='1';const maxInput=field(el('td',undefined,tr),'Max (leer = unbegrenzt)',d.maximum,v=>d.maximum=v,'number');maxInput.min='0';maxInput.step='1';maxInput.placeholder='Unbegrenzt';const details=el('details',undefined,el('td',undefined,tr));el('summary','Technische Details',details);el('p',d.id,details);el('p',d.source,details);el('p',workplaceName(dataIndex().positions.get(d.position_id)?.workplace_id??''),details);});
}
function renderServiceGroups(){
 let box=$('serviceGroups');if(!box){box=el('section');box.id='serviceGroups';box.className='surface padded';$('profiles').before(box);}box.replaceChildren();
 el('h3','Wiederkehrende Dienste gesammelt einstellen',box);
 el('p','Je Dienst und Zeitmuster einmal Tag oder Nacht wählen. Übernommen werden nur noch offene Vorkommen, einschließlich Randzeitraum. Bereits eingestellte Dienstarten, Freigaben, Bedarfe und Ruheprofile bleiben unverändert.',box);
 const settings=snapshot.metadata.night_classification??{start:'22:00',end:'06:00',minimum:180};
 const automatic=el('fieldset',undefined,box);el('legend','Tag/Nacht aus Uhrzeiten erkennen',automatic);
 el('p','Vorschlagsregel, keine gesetzliche Vorgabe: Nacht bei mindestens der eingestellten Minutenzahl im Nachtfenster, sonst Tag. Geteilte Dienste zählen nur ihre Arbeitsblöcke. Bereits festgelegte Dienstarten bleiben erhalten.',automatic);
 field(automatic,'Nacht ab',settings.start,v=>settings.start=v,'time');field(automatic,'Nacht bis',settings.end,v=>settings.end=v,'time');
 const threshold=field(automatic,'Mindestens Minuten im Nachtfenster',settings.minimum,v=>settings.minimum=v,'number');threshold.min='1';threshold.max='1440';
 button(automatic,'Zeitregel auf offene Dienste anwenden',()=>{const candidates=ServiceGroups.groups(snapshot).filter(g=>g.pending).map(g=>({g,proposal:ServiceGroups.suggest(g,settings.start,settings.end,settings.minimum)}));let count=0;for(const {g,proposal} of candidates)if(proposal)count+=ServiceGroups.apply(snapshot,g.key,proposal.kind);snapshot.metadata.night_classification={...settings};invalidateResult();renderRules();notice(`${count} offene Dienstvorkommen nach Zeitregel eingestellt. Projekt speichern.`);});
 const rows=ServiceGroups.groups(snapshot).filter(g=>g.pending);
 if(!rows.length){el('p','Keine offenen zuordenbaren Dienstmuster.',box);return;}
 const list=el('div',undefined,box);list.className='scroll';
 const view=collection(list,'serviceGroups',rows,{label:'Dienstmuster',size:20,search:g=>g.name,redraw:renderServiceGroups});
 const body=table(view.content,['Dienst','Zeitmuster','Offene Vorkommen','Dienstart','Übernehmen']);
 view.items.forEach(g=>{const tr=el('tr',undefined,body);el('td',g.name,tr);el('td',g.times.map(t=>`${t[1]}–${t[3]}${t[2]!==t[0]?' (Folgetag)':''}`).join(' / '),tr);el('td',String(g.pending),tr);let kind='';select(el('td',undefined,tr),'Dienstart für dieses Zeitmuster','',[['','Bitte wählen'],['day','Tag'],['night','Nacht']],v=>kind=v);button(el('td',undefined,tr),'Offene Vorkommen übernehmen',()=>{if(!kind){notice('Zuerst Tag oder Nacht auswählen.',true);return;}const count=ServiceGroups.apply(snapshot,g.key,kind);invalidateResult();renderRules();notice(`${count} offene Dienstvorkommen eingestellt.`);});});
}
function renderSetupReview(){
 let box=$('setupReview');if(!box){box=el('section');box.id='setupReview';box.className='surface padded';$('profiles').before(box);}box.replaceChildren();
 el('h3','Einrichtung prüfen',box);
 const report=snapshot.metadata.setup_review;
 if(report){el('p',`${report.reusedPeople} Personen mit übernommenen Einstellungen · ${report.newPeople.length} neue Personen · ${report.newServices.length} neue Dienste · ${report.classified} automatisch zugeordnete Dienstvorkommen`,box);
 const rows=[...report.newPeople.map(id=>({label:'Neue Person: '+(dataIndex().employees.get(id)?.name??id),id})),...report.newServices.map(id=>({label:'Neuer Dienst: '+(snapshot.positions.find(p=>p.function_id===id)?.name??id)})),...report.review.map(label=>({label}))];
 const list=el('div',undefined,box);const draw=()=>{const view=collection(list,'setupChanges',rows,{label:'Änderungen und Prüfhinweise',size:20,redraw:draw});for(const row of view.items){const line=el('p',row.label,view.content);if(row.id)button(line,'Person prüfen',()=>{navigate('team');personDetails(dataIndex().employees.get(row.id));});}};draw();
 }
 el('p','Die Eingabeprüfung zeigt offene Regeln. Sie garantiert noch keine vollständige Besetzung oder lösbare Planung.',box);
 const output=el('div',undefined,box);
 button(box,'Planungsbereitschaft prüfen',async()=>{const version=changeVersion,result=await api('/api/readiness','POST',currentSnapshot());if(version!==changeVersion){notice('Projekt geändert. Prüfung erneut starten.');return;}output.replaceChildren();el('strong',result.ready?'Eingaben geprüft – Berechnung kann gestartet werden.':'Vor der Berechnung noch bearbeiten:',output);const counts=new Map();for(const d of result.diagnostics)counts.set(d.code,(counts.get(d.code)??0)+1);for(const [code,n] of counts)el('p',`${diagnosticTitles[code]??code}: ${n}`,output);const details=el('details',undefined,output);el('summary','Konkrete Hinweise',details);const list=el('div',undefined,details);const draw=()=>{const view=collection(list,'setupReadiness',result.diagnostics,{label:'Hinweise',size:20,redraw:draw});for(const d of view.items)el('p',diagnosticMessage(d),view.content);};draw();});
}
function renderRules(){
 renderSetupReview();renderServiceGroups();
 if(detailsVisible('shifts'))renderShifts();if(detailsVisible('positions'))renderPositions();if(detailsVisible('demands'))renderDemands();
 renderProfiles();renderContext();$('unresolved').replaceChildren();snapshot.unresolved.forEach((u,i)=>{const row=el('div',undefined,$('unresolved'));row.className='card';el('span',u,row);button(row,'Nach fachlicher Korrektur als geklärt markieren',()=>{snapshot.unresolved.splice(i,1);invalidateResult();renderRules();});});
 if(!snapshot.unresolved.length)el('p','Keine offenen Importangaben.',$('unresolved'));$('weights').replaceChildren();Object.entries(snapshot.objectives).forEach(([k,v])=>field($('weights'),({hours:'Stunden',nights:'Nächte',weekends:'Wochenenden',holidays:'Feiertage',wishes:'Wünsche',changes:'Änderungen'})[k],v,n=>snapshot.objectives[k]=n,'number'));
}
function renderContext(){
 let box=$('contextConfirmation');if(!box){box=el('section');box.id='contextConfirmation';box.className='surface padded';$('profiles').before(box);}box.replaceChildren();
 el('h3','Dienste vor und nach dem Planungszeitraum',box);
 el('p',`Planung: ${snapshot.period_start} bis ${snapshot.period_end}. Für Ruhezeiten und Dienstserien wird auch der Randzeitraum ${snapshot.context_start} bis ${snapshot.context_end} berücksichtigt.`,box);
 if(snapshot.metadata.created_with==='project-setup'){
  field(box,'Außer den erfassten Diensten gibt es im angegebenen Randzeitraum vor und nach der Planung keine weiteren Dienste.',snapshot.context_complete&&snapshot.metadata.context_duty_free_confirmed,confirmed=>{snapshot.context_complete=confirmed;snapshot.metadata.context_duty_free_confirmed=confirmed;},'checkbox');
  el('p','Nur bestätigen, wenn die Aussage für alle Personen tatsächlich zutrifft. Zusätzliche Dienste zuerst im Projekt erfassen; ohne bestätigten Randkontext kann der Plan nicht abschließend geprüft werden.',box);
 }else el('p',snapshot.context_complete?'Der Import bestätigt einen vollständigen Randkontext.':'Der Randkontext ist noch nicht vollständig bestätigt. Die Datenquelle mit den angrenzenden Diensten und Zeiträumen erneut importieren.',box);
}
function invalidateResult(){
 if(!snapshot)return;
 markChanged();
 $('result').textContent='Daten oder Entwurf geändert. Erneut prüfen oder berechnen.';
 $('validation').textContent='Prüfbericht nicht aktuell. Entwurf erneut prüfen.';$('validationSummary')?.remove();
}
function renderProfiles(){
 const box=$('profiles');box.replaceChildren();
 el('h3','Verbindliche Regelprofile',box);
 const bulk=el('fieldset',undefined,box);el('legend','Regelprofil gesammelt zuordnen',bulk);
 el('p','Ein bestätigtes Profil allen Personen ohne individuelles Profil zuordnen. Unbestätigte Importplatzhalter werden ersetzt; individuelle Zuordnungen bleiben erhalten.',bulk);
 let chosen='',team='';
 select(bulk,'Bestätigtes Profil','',[['','Bitte wählen'],...snapshot.profiles.filter(p=>p.confirmed).map(p=>[p.id,p.id])],v=>chosen=v);
 select(bulk,'Team','',[['','Alle geladenen Personen'],...[...new Set(snapshot.employees.flatMap(e=>e.team_ids))].map(id=>[id,dataIndex().groups.get(id)?.name??id])],v=>team=v);
 button(bulk,'Offene Profilzuordnungen übernehmen',()=>{const n=ProfileGroups.apply(snapshot,chosen,team);invalidateResult();renderRules();notice(`${n} Profilzuordnungen übernommen. Individuelle Profile bleiben erhalten. Projekt speichern.`);});

 el('p','Alle Grenzen hier sind harte Regeln, keine Optimierungswünsche. Werte fachlich festlegen; es werden keine gesetzlichen Werte vorgeschlagen. Leere optionale Grenzen bedeuten: keine Grenze aus diesem Profil.',box);
 if(!snapshot.profiles.length)el('p','Keine Regelprofile vorhanden. Profile und Zuordnungen können im erweiterten Datenvertrag ergänzt werden.',box);
 snapshot.profiles.forEach(p=>{
  const card=el('details',undefined,box);card.dataset.profileId=p.id;
  const summary=el('summary',undefined,card);
  const title=()=>summary.textContent=`Regelprofil ${p.id} · ${p.confirmed?'bestätigt':'unbestätigt'}`;title();
  const content=el('div',undefined,card);card.ontoggle=()=>{if(!card.open||content.childNodes.length)return;
  const group=label=>{const g=el('fieldset',undefined,content);el('legend',label,g);const grid=el('div',undefined,g);grid.className='grid';return grid;};
  const edit=(g,key,label,type='number',optional=false,min=0)=>{
   const input=field(g,label,p[key],v=>{p[key]=v;title();invalidateResult();},type);input.dataset.profileField=key;
   if(type==='number'){input.min=String(min);input.step='1';input.required=!optional;if(optional)input.placeholder='Keine Grenze';}
   if(type==='date'||type==='text')input.required=true;
   return input;
  };
  let g=group('Identität und Gültigkeit');
  const id=field(g,'Profil-ID (Referenz)',p.id,()=>{});id.readOnly=true;
  edit(g,'version','Version','text');edit(g,'source','Herkunft','text');
  edit(g,'valid_from','Gültig ab','date');edit(g,'valid_until','Gültig bis','date');
  g=group('Tägliche Ruhe und Nachtblöcke');
  edit(g,'min_rest_minutes','Mindestruhe (Minuten)');edit(g,'after_night_rest_minutes','Ruhe nach Nachtdienst (Minuten)');
  edit(g,'after_night_block_rest_minutes','Ruhe nach Nachtblock (Minuten)');edit(g,'night_block_gap_days','Nachtblock-Abstand (Tage)','number',false,1);
  g=group('Wöchentliche Ruhe');
  edit(g,'weekly_rest_minutes','Wochenruhe (Minuten)');
  const mode=select(g,'Wochenruhe-Bezug',p.weekly_rest_frame,[['calendar_week','Kalenderwoche'],['rolling_elapsed','Rollierend verstrichene Zeit'],['rolling_local','Rollierend lokale Tage']],v=>{p.weekly_rest_frame=v;invalidateResult();});mode.dataset.profileField='weekly_rest_frame';
  edit(g,'weekly_rest_window_days','Rollierendes Fenster (Tage)','number',false,1);
  el('p','Die Fensterlänge gilt für rollierende Bezüge; Kalenderwochen bleiben kalendergebunden.',content);
  edit(g,'weekly_rest_add_daily','Tägliche Ruhe zusätzlich','checkbox');
  g=group('Optionale Höchstgrenzen');
  for(const [key,label,min] of [
   ['max_consecutive_work_days','Aufeinanderfolgende Arbeitstage',1],['max_consecutive_nights','Aufeinanderfolgende Nächte',1],
   ['max_daily_minutes','Tägliche Arbeitszeit (Minuten)',0],['max_weekly_minutes','Wöchentliche Arbeitszeit (Minuten)',0],
   ['max_period_minutes','Arbeitszeit im Planungszeitraum (Minuten)',0],['max_work_days','Arbeitstage im Planungszeitraum',0],
   ['max_nights','Nächte im Planungszeitraum',0],['max_weekends','Wochenenden im Planungszeitraum',0]
  ])edit(g,key,label,'number',true,min);
  g=group('Fachliche Prüfung');edit(g,'confirmed','Profil fachlich bestätigt','checkbox');
  el('p','Bestätigung ersetzt keine fachliche Prüfung. Änderungen dauerhaft speichern; offene Importangaben separat klären.',content);
  };
 });
}
function renderPlan(){renderCalendar();if($('assignmentDetails').open)renderAssignments();}
function assignmentRows(){return assignments.map((a,index)=>({a,index}));}
function renderAssignments(){
 $('plan').dataset.renderVersion=String(changeVersion);
 const idx=dataIndex(),view=collection($('plan'),'assignments',assignmentRows(),{label:'Einteilungen',size:40,search:({a})=>`${idx.employees.get(a.employee_id)?.name??a.employee_id} ${idx.demands.has(a.demand_id)?demandLabel(idx.demands.get(a.demand_id)):a.demand_id}`,redraw:renderAssignments});
 const body=table(view.content,['Person','Dienst / Position','Fixiert','Aktion']);
 view.items.forEach(({a,index})=>{const d=idx.demands.get(a.demand_id),tr=el('tr',undefined,body);tr.dataset.assignmentIndex=String(index);tr.tabIndex=-1;
 const person=el('td',undefined,tr);el('span',idx.employees.get(a.employee_id)?.name??'Unbekannte Person',person);
 button(person,'Person ändern',()=>{person.replaceChildren();const picker=select(person,'Person',a.employee_id,snapshot.employees.map(e=>[e.id,e.name]),v=>{a.employee_id=v;renderCalendar();notice('Entwurf geändert: erneut prüfen.');});picker.focus();});
 el('td',d?demandLabel(d):'Unbekannter Bedarf',tr);field(el('td',undefined,tr),'Fixieren',a.fixed,v=>{a.fixed=v;renderCalendar();},'checkbox');button(el('td',undefined,tr),'Entfernen',()=>{assignments.splice(index,1);invalidateResult();renderPlan();});});
 if(!assignments.length)el('p','Noch keine Einteilungen.',view.content);
 const add=el('details',undefined,$('plan'));el('summary','Einteilung hinzufügen',add);const box=el('div',undefined,add);box.className='assignment-composer';
 add.ontoggle=()=>{if(!add.open||box.childNodes.length)return;let employee=snapshot.employees[0]?.id,demand=snapshot.demands[0]?.id;
 select(box,'Person hinzufügen',employee,snapshot.employees.map(e=>[e.id,e.name]),v=>employee=v);
 // Only this explicit editor creates the potentially large demand picker.
 select(box,'Bedarfsposition',demand,snapshot.demands.map(d=>[d.id,demandLabel(d)]),v=>demand=v);
 button(box,'Einteilung hinzufügen',()=>{if(!employee||!demand)return;assignments.push({employee_id:employee,demand_id:demand,fixed:false,segments:[]});invalidateResult();const state=pageState('assignments',40);state.query='';state.page=Math.floor((assignments.length-1)/state.size);renderPlan();notice('Einteilung ergänzt. Vor Export oder Neuberechnung erneut prüfen.');});};
}
function focusAssignment(index){
 const state=pageState('assignments',40);state.query='';state.page=Math.floor(index/state.size);$('assignmentDetails').open=true;renderAssignments();
 const row=$('plan').querySelector(`[data-assignment-index="${index}"]`);row?.focus({preventScroll:true});row?.scrollIntoView({block:'center',behavior:'smooth'});
}
const diagnosticTitles={candidate_shortage:'Zu wenige geeignete Personen',shared_candidate_shortage:'Gemeinsamer Kandidatenengpass',vacancy:'Offene Stellen',maximum:'Höchstbesetzung',fixed:'Fixierte Einteilungen',duplicate:'Doppelte Einteilungen',reference:'Ungültige Verweise',context_assignment:'Planungszeitraum',interval_mismatch:'Dienstzeiten',unresolved:'Offene Angaben',profile:'Regelprofile',qualification:'Qualifikationen',approval:'Freigaben',rest:'Ruhezeiten',overlap:'Überlappende Dienste',interleaving:'Geteilte Dienste',availability:'Verfügbarkeit',kind:'Dienstart',weekend:'Wochenenden',holiday:'Feiertage',employment:'Beschäftigungszeitraum',team:'Teamzuordnung',restriction:'Dienstsperren',absence:'Abwesenheiten',night_block:'Ruhe nach Nachtblock',daily_limit:'Tägliche Höchstzeit',weekly_limit:'Wöchentliche Höchstzeit',period_limit:'Höchstzeit im Planungszeitraum',work_days:'Höchstens erlaubte Arbeitstage',nights:'Höchstens erlaubte Nächte',weekends:'Höchstens erlaubte Wochenenden',consecutive_work:'Aufeinanderfolgende Arbeitstage',consecutive_nights:'Aufeinanderfolgende Nächte',weekly_rest:'Zusammenhängende Wochenruhe',context:'Angrenzende Dienste und Zeiträume',mentoring:'Erforderliche Betreuung',size_limit:'Planungsgröße',numeric_range:'Zahlenbereich',date_range:'Datumsbereich',created_at:'Datenstand',empty_id:'Fehlende Kennungen',duplicate_id:'Doppelte Kennungen',interval:'Dienstzeiten',demand:'Besetzungsbedarf',validity:'Gültigkeitszeitraum',assignment_reference:'Einteilungen',input:'Eingabedaten'};
const eligibilityMessages={employment:'Der Dienst liegt außerhalb des Beschäftigungszeitraums.',team:'Die Person gehört nicht zum Team dieses Dienstes.',kind:'Diese Dienstart ist für die Person nicht erlaubt.',weekend:'Wochenenddienste sind für diese Person nicht erlaubt.',holiday:'Feiertagsdienste sind für diese Person nicht erlaubt.',approval:'Eine gültige Freigabe für diesen Dienst oder Arbeitsplatz fehlt.',qualification:'Ein gültiger Qualifikationsnachweis für diesen Dienst fehlt.',restriction:'Eine bestätigte Dienstsperre verhindert diese Einteilung.',absence:'Der Dienst überschneidet sich mit einer Abwesenheit.',availability:'Der vollständige Dienst liegt nicht innerhalb der erlaubten Zeitfenster.'};
function diagnosticMessage(d){
 if(d.message.startsWith('Einsatz nicht zulässig:'))return eligibilityMessages[d.code]??d.message;
 if(d.message.startsWith('Persönliche Obergrenze überschritten:'))return `${diagnosticTitles[d.code]??'Persönliche Obergrenze'} überschritten.`;
 if(d.message.startsWith('Unvereinbare Dienste'))return d.code==='rest'?'Zwischen dieser Einteilung und einem anderen Dienst bleibt zu wenig Ruhezeit.':'Diese Einteilung ist zeitlich nicht mit einem anderen Dienst der Person vereinbar.';
 return d.message;
}
function refreshAutomaticReadiness(force=false){
 if(!snapshot||activePanel!=='calculate')return;
 const status=$('automaticReadinessStatus'),details=$('automaticReadinessDetails'),retry=$('retryReadiness');
 const display=(state,message)=>{status.dataset.state=state;status.textContent=message;};
 if(jsonDirty||personDraft){
  readinessRequest++;readinessPending=-1;readinessVersion=-1;details.replaceChildren();retry.hidden=true;
  display('draft','Offene JSON- oder Abwesenheitsbearbeitung zuerst übernehmen oder verwerfen. Noch keine aktuelle Vorprüfung.');return;
 }
 if(!force&&(readinessVersion===changeVersion||readinessPending===changeVersion))return;
 const version=changeVersion,request=++readinessRequest;readinessVersion=-1;readinessPending=version;retry.hidden=true;details.replaceChildren();
 display('pending','Aktuelle Eingaben werden geprüft …');
 const current=()=>request===readinessRequest&&version===changeVersion&&!jsonDirty&&!personDraft;
 api('/api/readiness','POST',currentSnapshot()).then(result=>{
  if(!current())return;
  if(typeof result?.ready!=='boolean'||!Array.isArray(result.diagnostics)||result.diagnostics.some(d=>!d||typeof d.message!=='string'||typeof d.code!=='string')||result.ready!==(result.diagnostics.length===0))throw Error('Unvollständige Antwort der Vorprüfung.');
  readinessVersion=version;readinessPending=-1;
  display(result.ready?'ready':'issues',result.ready?'Keine offenen Eingabefehler gefunden. Die Berechnung und anschließende Ergebnisprüfung stehen noch aus.':`${result.diagnostics.length.toLocaleString('de-DE')} Hinweise vor der Berechnung prüfen.`);
  if(result.diagnostics.length){
   const disclosure=el('details',undefined,details);disclosure.open=true;el('summary','Konkrete Prüfhinweise',disclosure);
   const list=el('div',undefined,disclosure);const draw=()=>{const view=collection(list,'automaticReadiness',result.diagnostics,{label:'Hinweise',size:10,redraw:draw});for(const d of view.items)el('p',diagnosticMessage(d),view.content);};draw();
  }
 }).catch(error=>{
  if(!current())return;
  readinessVersion=version;readinessPending=-1;details.replaceChildren();retry.hidden=false;
  display('error','Vorprüfung nicht abgeschlossen. '+error.message);
 }).finally(()=>{if(request===readinessRequest)readinessPending=-1;});
}
function renderValidation(report){
 $('validation').textContent=JSON.stringify(report,null,2);$('validationSummary')?.remove();
 let raw=$('validationRaw');if(!raw){raw=el('details');raw.id='validationRaw';el('summary','Technischer Prüfbericht (JSON)',raw);$('validation').before(raw);raw.append($('validation'));}
 const box=el('div');box.id='validationSummary';box.className='validation-summary';raw.before(box);
 const heading=el('p',report.valid?(report.complete?'Vollständig und geprüft':'Gültiger Teilplan mit offenen Stellen'):'Regelverletzungen müssen korrigiert werden',box);heading.className=report.valid&&report.complete?'good':'bad';
 if(!report.diagnostics.length){el('p','Die unabhängige Prüfung hat keine Regelverletzungen oder unbesetzten Stellen gefunden.',box);return;}
 const grouped=new Map(),idx=dataIndex();for(const diagnostic of report.diagnostics){if(!grouped.has(diagnostic.code))grouped.set(diagnostic.code,[]);grouped.get(diagnostic.code).push(diagnostic);}
 for(const [code,entries] of grouped){const group=el('details',undefined,box);group.className='validation-group';group.open=grouped.size===1;el('summary',`${diagnosticTitles[code]??'Regel prüfen'} · ${entries.length}`,group);
 const content=el('div',undefined,group);const draw=()=>{const view=collection(content,'diagnostics-'+code,entries,{label:'Hinweise',size:20,redraw:draw});for(const d of view.items){const line=el('article',undefined,view.content);line.className='diagnostic-item';const employee=idx.employees.get(d.employee_id),demand=idx.demands.get(d.demand_id);el('strong',[employee?.name,d.date].filter(Boolean).join(' · ')||diagnosticTitles[code]||code,line);el('p',diagnosticMessage(d),line);if(demand)el('small',demandLabel(demand),line);if(employee)button(line,'Person bearbeiten',()=>personDetails(employee));if(demand)button(line,'Bedarf öffnen',()=>{const state=pageState('demands',40);state.query=demand.id;state.page=0;navigate('rules');const details=$('demands').closest('details');if(details)details.open=true;renderDemands();$('demands').scrollIntoView({block:'center',behavior:'smooth'});});}};
 group.ontoggle=()=>{if(group.open&&!content.childNodes.length)draw();};if(group.open)draw();}
}
function checkPeopleReady(){const unfinished=snapshot.employees.find(person=>!person.name.trim()||person.target_minutes==null);if(unfinished){personDetails(unfinished);throw Error('Name und Sollstunden der neuen Person zuerst festlegen.');}}
async function save(){
 checkPeopleReady();
 if(personDraft){navigate('team');$('details').scrollIntoView({block:'center',behavior:'smooth'});throw Error('Die bearbeitete Abwesenheit zuerst übernehmen oder abbrechen.');}
 if(jsonDirty)throw Error('JSON-Änderungen zuerst übernehmen oder mit „Aktuelle Daten anzeigen“ verwerfen.');
 const invalid=$('workspace').querySelector('input:invalid');
 if(invalid){const panel=invalid.closest('[data-panel]')?.dataset.panel;if(panel){renderedPanels.set(panel,changeVersion);navigate(panel);}let parent=invalid.parentElement;while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}invalid.scrollIntoView({block:'center',behavior:'smooth'});invalid.reportValidity();throw Error('Ungültige oder fehlende Eingabe korrigieren.');}
 const persisted=await api('/api/snapshots','PUT',currentSnapshot());
 snapshot.revision=persisted.revision;snapshot.assignments=structuredClone(assignments);dirty=false;jsonVersion=-1;updateSaveStatus();$('source').textContent=`Quelle: ${snapshot.source==='synthetic'?'SYNTHETISCHE DEMO':snapshot.source} · ${snapshot.period_start} bis ${snapshot.period_end} · ${snapshot.timezone} · Stand ${snapshot.revision}`;
 syncJson();
 await saved();notice('Regeln und Entwurf dauerhaft gespeichert.');
}
async function solve(){
 if(solving||jobId)throw Error('Eine Berechnung läuft bereits.');if(!snapshot)throw Error('Zuerst Daten laden');
 if(!$('limit').checkValidity()){$('limit').reportValidity();throw Error('Zeitlimit zwischen 1 und 600 Sekunden eingeben.');}
 solving=true;updateJobButtons();navigate('calculate');
 try{await save();const j=await api('/api/jobs','POST',{snapshot_id:snapshot.id,snapshot_revision:snapshot.revision,time_limit:Number($('limit').value),partial:$('partial').checked});jobId=j.id;updateJobButtons();clearTimeout(timer);await poll();await savedJobs().catch(e=>notice('Liste der Berechnungen konnte nicht aktualisiert werden. '+e.message,true));}
 finally{solving=false;updateJobButtons();}
}
async function poll(){
 const requestedJob=jobId;if(!requestedJob)return;
 try{
  let j=await api('/api/jobs/'+encodeURIComponent(requestedJob)+'/status');if(jobId!==requestedJob)return;
  if(!['queued','running'].includes(j.state)){j=await api('/api/jobs/'+encodeURIComponent(requestedJob));if(jobId!==requestedJob)return;}
  $('job').textContent=`${jobStates[j.state]??j.state} · ${Math.max(0,Math.round((j.finished_at??Date.now()/1000)-(j.started_at??j.created_at)))} Sekunden`;
  if(['queued','running'].includes(j.state)){timer=setTimeout(poll,1000);return;}
  jobId=null;updateJobButtons();
  if(j.error)notice(j.error,true);
  if(j.result){
   assignments=structuredClone(j.result.assignments);markChanged();$('result').replaceChildren();
   const valid=j.result.validation.valid,complete=j.result.validation.complete;
   const summary=el('p',`${valid?(complete?'Vollständig und geprüft':'Geprüfter Teilplan'):'Prüfung fehlgeschlagen'} · Berechnet in ${j.result.runtime_seconds.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} s`,$('result'));summary.className=valid&&complete?'good':'bad';
   const evaluation=el('details',undefined,$('result'));el('summary','Technische Auswertung',evaluation);evaluation.ontoggle=()=>{if(evaluation.open&&!evaluation.querySelector('pre'))el('pre',JSON.stringify({solver_status:j.result.solver_status,offene_Stellen:j.result.vacancies,auswertung:j.result.metrics},null,2),evaluation);};
   renderValidation(j.result.validation);$('validationDetails').open=!valid||!complete;
   if(previous.length){const old=new Set(previous.map(a=>a.employee_id+'|'+a.demand_id)),next=new Set(assignments.map(a=>a.employee_id+'|'+a.demand_id));el('p',`Vergleich: ${[...next].filter(x=>!old.has(x)).length} hinzugefügt, ${[...old].filter(x=>!next.has(x)).length} entfernt.`,$('result'));}
   navigate('plan');renderPlan();syncJson();publishState();notice(valid&&complete?'Berechnung abgeschlossen. Entwurf prüfen und dauerhaft speichern.':'Berechnung abgeschlossen. Prüfbericht und offene Stellen beachten.',!valid);
  }
  await savedJobs();
 }catch(e){
  if(jobId!==requestedJob)return;notice(e.message,true);
  if(e.status===404||e.status===401){jobId=null;updateJobButtons();return;}
  $('job').textContent='Verbindung zur Berechnung unterbrochen. Status wird erneut abgerufen …';timer=setTimeout(poll,2000);
 }
}
action('demo',async()=>{if(canReplace())load(await api('/api/demo'));});
action('inspect',async()=>{const key=JSON.stringify([$('sourceType').value,$('directory').value]);const source=await api($('sourceType').value==='api'?'/api/remote-source':'/api/source?directory='+encodeURIComponent($('directory').value));if(key!==JSON.stringify([$('sourceType').value,$('directory').value])){notice('Datenquelle geändert. Teams erneut laden.');return;}groups=source.groups;checkedTeams.clear();renderTeams();notice(`${groups.length} Teams gefunden. Gewünschte Teams auswählen.`);});
action('import',async()=>{if(!checkedTeams.size)throw Error('Mindestens ein Team auswählen.');if($('reuseSetup').checked&&!snapshot)throw Error('Zuerst das bisherige Projekt öffnen.');if(!canReplace())return;const setupPrevious=$('reuseSetup').checked?currentSnapshot():null;const setupOptions={sameSource:$('reuseSetup').checked,classify:$('autoKind').checked,rule:{start:$('setupNightStart').value,end:$('setupNightEnd').value,minimum:Number($('setupNightMin').value)}};notice('Import einschließlich historischer Basis läuft …');const r=await api($('sourceType').value==='api'?'/api/remote-import':'/api/import','POST',{...($('sourceType').value==='directory'?{directory:$('directory').value}:{}),period_start:$('start').value,period_end:$('end').value,team_ids:[...checkedTeams],timezone:$('timezone').value,history_plan:$('historyPlan').value,auto_history:$('autoHistory').checked,history_min_days:Number($('historyMinDays').value),existing_plan_mode:$('existingPlanMode').value,history_start:$('historyStart').value||null,history_end:$('historyEnd').value||null});const prepared=SetupAssistant.prepare(r.snapshot,setupPrevious,setupOptions);const checked=await api('/api/snapshots/check','POST',prepared);load(checked);navigate('rules');});
action('save',save);action('saveDraft',save);
function projectSwitchBusy(){return projectBusy||solving||!!jobId||['save','saveDraft','demo','import','applyJson','file'].some(id=>$(id).dataset.busy==='true');}
async function openSavedProject(id){
 if(projectSwitchBusy())throw Error('Die laufende Aktion zuerst abschließen.');if(!id||!canReplace())return false;
 projectBusy=true;updateJobButtons();try{const original=await api('/api/snapshots/'+encodeURIComponent(id));const checked=await api('/api/snapshots/check','POST',original);load(checked,true);return true;}finally{projectBusy=false;updateJobButtons();}
}
async function openJob(id){
 if(projectSwitchBusy())throw Error('Die laufende Aktion zuerst abschließen.');if(!id||!canReplace())return false;
 projectBusy=true;updateJobButtons();try{const stored=await api('/api/jobs/'+encodeURIComponent(id)+'/snapshot');const original=await api('/api/snapshots/check','POST',stored);original.id=projectId();original.revision='0';original.metadata={...original.metadata,restored_from_job:id};load(original);jobId=id;updateJobButtons();navigate('calculate');await poll();return true;}finally{projectBusy=false;updateJobButtons();}
}
action('restore',()=>openSavedProject($('saved').value));action('refreshJobs',savedJobs);action('restoreJob',()=>openJob($('savedJobs').value));
action('solve',solve);
action('cancel',async()=>{await api('/api/jobs/'+encodeURIComponent(jobId)+'/cancel','POST');await poll();});
action('retryReadiness',()=>refreshAutomaticReadiness(true));
action('validate',async()=>{
 const version=changeVersion;$('validationDetails').open=true;const report=await api('/api/validate','POST',{snapshot,assignments});
 if(version!==changeVersion){notice('Daten während der Prüfung geändert. Aktuellen Entwurf erneut prüfen.');return;}
 renderValidation(report);
 notice(report.valid?(report.complete?'Entwurf ist vollständig und geprüft.':'Teilplan geprüft. Offene Stellen im Prüfbericht beachten.'):'Entwurf enthält Regelverletzungen. Prüfbericht beachten.',!report.valid);
});
action('recompute',async()=>{previous=structuredClone(assignments);await solve();});
action('refreshJson',()=>{if(jsonDirty&&!window.confirm('Nicht übernommene JSON-Änderungen verwerfen?'))return;jsonDirty=false;jsonVersion=-1;syncJson(true);updateSaveStatus();});
action('applyJson',async()=>{const checked=await readProject($('json').value);load(checked);});
$('json').oninput=()=>{jsonDirty=true;updateSaveStatus();};
$('file').onchange=()=>runAction($('file'),async()=>{
 try{const file=$('file').files[0];if(!file)return;if(file.size>16*1024*1024)throw Error('Projektdatei überschreitet die Grenze von 16 MiB.');const checked=await readProject(await file.text());if(canReplace())load(checked);}
 finally{$('file').value='';}
});
function download(content,name){const url=URL.createObjectURL(content),a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
action('backup',()=>{
 checkPeopleReady();
 if(personDraft)throw Error('Die bearbeitete Abwesenheit zuerst übernehmen oder abbrechen.');
 if(jsonDirty)throw Error('JSON-Änderungen zuerst übernehmen oder verwerfen, damit die Projektsicherung den angezeigten Stand enthält.');
 download(new Blob([JSON.stringify(currentSnapshot(),null,2)],{type:'application/json'}),`projekt-${snapshot.period_start}-${snapshot.period_end}.json`);notice('Vollständiges Projekt mit Regeln und aktuellem Entwurf heruntergeladen.');
});
document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>runAction(b,async()=>{
 checkPeopleReady();
 if(personDraft)throw Error('Die bearbeitete Abwesenheit zuerst übernehmen oder abbrechen.');
 if(jsonDirty)throw Error('JSON-Änderungen zuerst übernehmen oder verwerfen.');
 const f=b.dataset.export,r=await fetch('/api/export/'+f,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({snapshot,assignments})});
 if(!r.ok)throw await responseError(r);if(r.redirected)throw Error('Anmeldung abgelaufen. Projekt sichern und erneut anmelden.');download(await r.blob(),'plan.'+f);
}));
$('saved').onchange=updateJobButtons;$('savedJobs').onchange=updateJobButtons;
saved().catch(e=>notice(e.message,true));savedJobs().catch(e=>notice(e.message,true));

$('directory').oninput=()=>{if(groups.length||checkedTeams.size){groups=[];checkedTeams.clear();renderTeams();notice('Verzeichnis geändert. Teams erneut laden.');}};
$('sourceType').onchange=()=>{$('directoryLabel').hidden=$('sourceType').value==='api';groups=[];checkedTeams.clear();renderTeams();notice('Datenquelle geändert. Teams erneut laden.');};

function renderTeams(){
 const box=$('teamTree');box.replaceChildren();
 const descendants=id=>{const found=new Set([String(id)]);let changed=true;while(changed){changed=false;groups.forEach(g=>{if(found.has(String(g.parent_id))&&!found.has(String(g.id))){found.add(String(g.id));changed=true;}});}return found;};
 groups.forEach(g=>{const row=el('label',undefined,box);row.className='team-row';row.style.paddingLeft=`${Math.min(g.depth??0,12)*18}px`;
 const input=el('input',undefined,row);input.type='checkbox';input.value=String(g.id);input.checked=checkedTeams.has(String(g.id));input.dataset.teamId=String(g.id);
 const children=[...descendants(g.id)].filter(id=>id!==String(g.id));input.indeterminate=children.length>0&&children.some(id=>checkedTeams.has(id))&&!(input.checked&&children.every(id=>checkedTeams.has(id)));
 el('span',g.name,row);input.onchange=()=>{descendants(g.id).forEach(id=>input.checked?checkedTeams.add(id):checkedTeams.delete(id));renderTeams();};
 });$('teamCount').textContent=`${checkedTeams.size} Teams ausgewählt · Nur angekreuzte Teams werden importiert`;
}
function historyDefaults(){
 const date=new Date($('start').value+'T12:00:00Z');if(Number.isNaN(+date))return;
 const before=new Date(date);before.setUTCDate(before.getUTCDate()-1);
 const from=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()-3,1,12));
 from.setUTCDate(Math.min(date.getUTCDate(),new Date(Date.UTC(from.getUTCFullYear(),from.getUTCMonth()+1,0)).getUTCDate()));
 $('historyStart').value=from.toISOString().slice(0,10);$('historyEnd').value=before.toISOString().slice(0,10);
}
function serviceMatrix(){return snapshot?.metadata?.service_matrix_version===1;}
function relatedApproval(a,p){return a.function_id===p.function_id&&(serviceMatrix()&&p.workplace_id==='*'||a.workplace_id===p.workplace_id);}
function samePosition(a,b){return a.function_id===b.function_id&&a.workplace_id===b.workplace_id;}
function approved(e,p){return e.approvals.some(a=>samePosition(a,p)&&a.valid_from<=snapshot.period_start&&a.valid_until>=snapshot.period_end);}
function suggested(e,p){return (dataIndex().history.get(e.id)?.suggested_approvals??[]).some(a=>samePosition(a,p));}
function dayOffset(day,delta){const date=new Date(day+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+delta);return date.toISOString().slice(0,10);}
function setApproval(e,p,enabled){
 invalidateResult();
 if(enabled){if(!approved(e,p))e.approvals.push({function_id:p.function_id,workplace_id:p.workplace_id,valid_from:snapshot.period_start,valid_until:snapshot.period_end,supervised:e.approvals.some(a=>relatedApproval(a,p)&&a.supervised&&a.valid_from<=snapshot.period_end&&a.valid_until>=snapshot.period_start)});}
 else {e.approvals=e.approvals.flatMap(a=>{if(!relatedApproval(a,p)||a.valid_until<snapshot.period_start||a.valid_from>snapshot.period_end)return[a];const remaining=[];if(a.valid_from<snapshot.period_start)remaining.push({...a,valid_until:dayOffset(snapshot.period_start,-1)});if(a.valid_until>snapshot.period_end)remaining.push({...a,valid_from:dayOffset(snapshot.period_end,1)});return remaining;});}
 notice('Freigabe im Planungszeitraum geändert. Qualifikationen und Freigaben außerhalb des Zeitraums bleiben erhalten. Änderungen speichern.');
}
function matrixPositions(){
 dataIndex();if(matrixCache)return matrixCache;
 if(serviceMatrix()){const services=new Map(),serviceNames=new Map((snapshot.metadata.services??[]).map(s=>[s.function_id??'sp5:service:'+s.id,s]));const add=p=>{if(!p.function_id)return;const existing=services.get(p.function_id);if(existing){existing.qualifications_required ||= p.qualifications_required;return;}const service=serviceNames.get(p.function_id);services.set(p.function_id,{...p,id:p.function_id,workplace_id:'*',name:service?.name??p.function_name??p.name??p.function_id});};(snapshot.metadata.services??[]).forEach(add);snapshot.positions.forEach(add);snapshot.employees.flatMap(e=>e.approvals).forEach(add);(snapshot.metadata.history_matrix??[]).flatMap(r=>r.suggested_approvals??[]).forEach(add);matrixCache=[...services.values()];return matrixCache;}
 const seen=new Set(),positions=[];const add=p=>{const key=JSON.stringify([p.function_id,p.workplace_id]);if(!seen.has(key)){seen.add(key);positions.push(p);}};
 snapshot.positions.forEach(add);
 const extra=[...snapshot.employees.flatMap(e=>e.approvals),...(snapshot.metadata.history_matrix??[]).flatMap(r=>r.suggested_approvals??[])];
 extra.forEach(a=>add({id:JSON.stringify([a.function_id,a.workplace_id]),function_id:a.function_id,workplace_id:a.workplace_id,name:a.function_name&&a.workplace_name?`${a.function_name} / ${a.workplace_name}`:a.name??'Weitere Funktion / Arbeitsplatz',qualifications_required:false}));matrixCache=positions;return matrixCache;
}
function workplaceName(id){return dataIndex().workplaces.get(id)?.name??id;}
function approvalPositions(){const positions=[...matrixPositions()];if(serviceMatrix())snapshot.positions.forEach(p=>positions.push({...p,name:`${p.name} · ${workplaceName(p.workplace_id)} (eingeschränkt)`}));return positions;}
function matrixFiltered(){const q=fold($('matrixSearch').value.trim()),positions=matrixPositions();if(!q)return {employees:snapshot.employees,positions};const matchingPeople=snapshot.employees.filter(e=>fold(e.name).includes(q));const matchingPositions=positions.filter(p=>fold(p.name).includes(q));return {employees:matchingPositions.length?snapshot.employees:matchingPeople,positions:matchingPeople.length?positions:matchingPositions};}
function matrixVisible(){
 const data=matrixFiltered(),people=pageState('matrixPeople',30),positions=pageState('matrixPositions',16);
 people.page=Math.min(people.page,Math.max(0,Math.ceil(data.employees.length/people.size)-1));positions.page=Math.min(positions.page,Math.max(0,Math.ceil(data.positions.length/positions.size)-1));
 return {employees:data.employees.slice(people.page*people.size,(people.page+1)*people.size),positions:data.positions.slice(positions.page*positions.size,(positions.page+1)*positions.size)};
}
function renderMatrix(){
 $('mappingWarning').hidden=serviceMatrix()||!snapshot.source.startsWith('sp5');
 const {employees,positions}=matrixVisible(),rows=transposed?positions:employees,cols=transposed?employees:positions;
 const box=$('matrix');box.replaceChildren();const filtered=matrixFiltered();pagination(box,pageState('matrixPeople',30),filtered.employees.length,renderMatrix,'Personen');if(filtered.positions.length>16)pagination(box,pageState('matrixPositions',16),filtered.positions.length,renderMatrix,'Dienste');const grid=el('div',undefined,box);grid.className='collection-content';
 const body=table(grid,[transposed?(serviceMatrix()?'Dienst':'Funktion / Arbeitsplatz'):'Person',...cols.map(x=>x.name)]);const t=body.parentElement;t.className='matrix-table';t.setAttribute('aria-label','Freigabematrix für den Planungszeitraum');
 rows.forEach((row,ri)=>{const tr=el('tr',undefined,body);const h=el('th',undefined,tr);h.scope='row';if(!transposed)button(h,row.name||'Neue Person',()=>personDetails(row));else h.textContent=row.name;
 cols.forEach((col,ci)=>{const e=transposed?col:row,p=transposed?row:col,allowed=approved(e,p),history=suggested(e,p);
 const supervised=allowed&&e.approvals.some(a=>relatedApproval(a,p)&&a.supervised&&a.valid_from<=snapshot.period_end&&a.valid_until>=snapshot.period_start);const partial=!allowed&&e.approvals.some(a=>relatedApproval(a,p)&&a.valid_from<=snapshot.period_end&&a.valid_until>=snapshot.period_start);
 const mixedSupervision=supervised&&e.approvals.some(a=>samePosition(a,p)&&!a.supervised&&a.valid_from<=snapshot.period_end&&a.valid_until>=snapshot.period_start);
 const workplacePartial=partial&&serviceMatrix()&&e.approvals.some(a=>relatedApproval(a,p)&&a.workplace_id!=='*'&&a.valid_from<=snapshot.period_end&&a.valid_until>=snapshot.period_start);
 const text=allowed?(mixedSupervision?'✓ Teils betreut':supervised?'✓ Betreut':'✓ Frei'):(workplacePartial?'◐ Einzelne Arbeitsplätze':partial?'◐ Teilzeitraum':history?'◇ Vorschlag':'− Keine Freigabe');const td=el('td',undefined,tr);
 const b=button(td,text,()=>{setApproval(e,p,!allowed);renderMatrix();renderHistory();$('matrix').querySelector(`[data-row="${ri}"][data-col="${ci}"]`)?.focus();});b.className='matrix-cell '+(allowed?'allowed':partial?'partial':history?'suggested':'prohibited');b.dataset.row=ri;b.dataset.col=ci;b.dataset.employeeId=e.id;b.dataset.functionId=p.function_id;b.dataset.workplaceId=p.workplace_id;b.setAttribute('aria-pressed',String(allowed));b.setAttribute('aria-label',`${e.name} · ${p.name}: ${text}. ${allowed?'Freigabe im Zeitraum entfernen':(serviceMatrix()?'Dienst an allen Arbeitsplätzen für ganzen Planungszeitraum freigeben':'Für ganzen Planungszeitraum freigeben')}`);b.title=`${snapshot.period_start} bis ${snapshot.period_end}. ${supervised?'Betreuung erforderlich. ':''}${p.qualifications_required?'Zusätzlicher Qualifikationsnachweis bleibt erforderlich.':''}`;
 b.onkeydown=event=>{const delta={ArrowRight:[0,1],ArrowLeft:[0,-1],ArrowDown:[1,0],ArrowUp:[-1,0]}[event.key];if(!delta)return;event.preventDefault();$('matrix').querySelector(`[data-row="${ri+delta[0]}"][data-col="${ci+delta[1]}"]`)?.focus();};});});
 if(!rows.length||!cols.length)el('p','Keine passenden Personen oder Dienste. Suche leeren oder Teams und Planungszeitraum beim Import prüfen.',$('matrix'));
}
let dateFormatter,timeFormatter,formatterZone;
function ensureFormatters(){if(formatterZone===snapshot.timezone)return;formatterZone=snapshot.timezone;dateFormatter=new Intl.DateTimeFormat('en-CA',{timeZone:formatterZone,year:'numeric',month:'2-digit',day:'2-digit'});timeFormatter=new Intl.DateTimeFormat('de-DE',{timeZone:formatterZone,hour:'2-digit',minute:'2-digit'});}
function localDay(value){ensureFormatters();return dateFormatter.format(new Date(value));}
function localTime(value){ensureFormatters();return timeFormatter.format(new Date(value));}
function renderCalendar(){
 if(!snapshot)return;const start=planMonth+'-01',next=new Date(start+'T12:00:00Z');next.setUTCMonth(next.getUTCMonth()+1);const last=dayOffset(next.toISOString().slice(0,10),-1),days=[];
 for(let day=start;day<=last;day=dayOffset(day,1))days.push(day);
 $('planMonth').textContent=new Intl.DateTimeFormat('de-DE',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(start+'T12:00:00Z'));
 $('prevMonth').disabled=planMonth<=snapshot.period_start.slice(0,7);$('nextMonth').disabled=planMonth>=snapshot.period_end.slice(0,7);
 const byPosition=$('planView').value==='positions',idx=dataIndex();
 const view=collection($('calendar'),'calendar-'+(byPosition?'positions':'employees'),byPosition?matrixPositions():snapshot.employees,{label:'Planzeilen',size:30,search:row=>row.name,redraw:renderCalendar});
 const weekdayFormat=new Intl.DateTimeFormat('de-DE',{weekday:'short',day:'2-digit',timeZone:'UTC'}),weekends=new Set(days.filter(day=>[0,6].includes(new Date(day+'T12:00:00Z').getUTCDay())));
 const body=table(view.content,[byPosition?(serviceMatrix()?'Dienst':'Funktion / Arbeitsplatz'):'Person',...days.map(day=>weekdayFormat.format(new Date(day+'T12:00:00Z')))]);body.parentElement.className='calendar-table';
 [...body.parentElement.querySelectorAll('thead th')].slice(1).forEach((th,i)=>{if(weekends.has(days[i]))th.classList.add('weekend');});
 const indexed=new Map(),rowKey=row=>byPosition?JSON.stringify([row.function_id,serviceMatrix()?'*':row.workplace_id]):row.id,visibleKeys=new Set(view.items.map(rowKey));
 const counts=new Map();for(const a of assignments){if(!idx.employees.has(a.employee_id))continue;if(!counts.has(a.demand_id))counts.set(a.demand_id,new Set());counts.get(a.demand_id).add(a.employee_id);}
 assignments.forEach((a,index)=>{const demand=idx.demands.get(a.demand_id),shift=idx.shifts.get(demand?.shift_id),position=idx.positions.get(demand?.position_id),employee=idx.employees.get(a.employee_id),segments=a.segments?.length?a.segments:shift?.segments??[],key=byPosition?(position?rowKey(position):null):a.employee_id;
 if(key===null||!visibleKeys.has(key))return;
 const touched=new Map();segments.forEach(segment=>{const first=localDay(segment.start),end=localDay(new Date(new Date(segment.end).getTime()-1)),time=`${localTime(segment.start)}–${localTime(segment.end)}${first!==end?' ↪':''}`;for(let day=first<start?start:first;day<=end&&day<=last;day=dayOffset(day,1)){if(!touched.has(day))touched.set(day,[]);touched.get(day).push(time);}});
 touched.forEach((times,day)=>{const cellKey=JSON.stringify([key,day]);if(!indexed.has(cellKey))indexed.set(cellKey,[]);indexed.get(cellKey).push({a,index,shift,position,employee,timeLabel:times.join(' / ')});});});
 const gaps=new Map();let required=0,filled=0;
 for(const demand of snapshot.demands){const shift=idx.shifts.get(demand.shift_id),position=idx.positions.get(demand.position_id),first=shift?.segments[0]?.start;if(!first)continue;const day=localDay(first);if(day<start||day>last||day<snapshot.period_start||day>snapshot.period_end)continue;
 const staffed=counts.get(demand.id)?.size??0;required+=demand.minimum;filled+=Math.min(demand.minimum,staffed);const gap=Math.max(0,demand.minimum-staffed);
 if(byPosition&&position&&gap){const cellKey=JSON.stringify([rowKey(position),day]);if(!gaps.has(cellKey))gaps.set(cellKey,[]);gaps.get(cellKey).push({demand,gap});}}
 const coverage=el('div');coverage.className='coverage-summary';coverage.setAttribute('role','status');el('strong',`${filled} / ${required} erforderliche Plätze besetzt`,coverage);el('span',required===filled?' · Keine offenen Mindestplätze':' · '+(required-filled)+' offene Plätze',coverage);el('small','Besetzung im angezeigten Monat. Die Regelprüfung erfolgt separat.',coverage);view.content.before(coverage);
 view.items.forEach(row=>{const tr=el('tr',undefined,body);const th=el('th',row.name,tr);th.scope='row';days.forEach(day=>{const td=el('td',undefined,tr);td.dataset.date=day;if(weekends.has(day))td.classList.add('weekend');if(day<snapshot.period_start||day>snapshot.period_end)td.classList.add('outside-period');
 const cellKey=JSON.stringify([rowKey(row),day]);(indexed.get(cellKey)??[]).forEach(x=>{
 const badge=button(td,`${x.a.fixed?'◆ ':''}${byPosition?(x.employee?.name??'Unbekannte Person'):(x.shift?.name??'Dienst')}\n${x.timeLabel}${!byPosition?'\n'+(x.position?.name??''):''}`,()=>focusAssignment(x.index));badge.className='shift-badge '+(x.shift?.kind==='night'?'night':'day');badge.title=`${x.employee?.name??''} · ${x.position?.name??''}${x.a.fixed?' · Fixiert':''}`;});
 (gaps.get(cellKey)??[]).forEach(({demand,gap})=>{const badge=button(td,`${gap} offen`,()=>{const state=pageState('demands',40);state.query=demand.id;state.page=0;navigate('rules');const details=$('demands').closest('details');if(details)details.open=true;renderDemands();$('demands').scrollIntoView({block:'center',behavior:'smooth'});});badge.className='vacancy-badge';badge.title=demandLabel(demand);});});});
 if(!view.total)el('p','Keine passenden Personen oder Dienste. Suche anpassen.',view.content);
 else if(!assignments.length)el('p','Noch keine Einteilungen. Berechnen oder Einteilungen im Detailbereich ergänzen.',view.content);
}
$('matrixSearch').oninput=debounce(()=>{if(!snapshot)return;pageState('matrixPeople',30).page=0;pageState('matrixPositions',16).page=0;renderMatrix();});
action('transpose',()=>{transposed=!transposed;$('transpose').setAttribute('aria-pressed',String(transposed));renderMatrix();});
action('confirmHistory',()=>{const {employees,positions}=matrixVisible();const pairs=employees.flatMap(e=>positions.filter(p=>suggested(e,p)&&!approved(e,p)).map(p=>[e,p]));if(!pairs.length){notice('Keine unbestätigten historischen Vorschläge in der aktuellen Ansicht.');return;}if(!window.confirm(`${pairs.length} sichtbare historische Vorschläge ausdrücklich für ${snapshot.period_start} bis ${snapshot.period_end} freigeben? ${serviceMatrix()?'Die Freigabe gilt für den Dienst an allen Arbeitsplätzen. ':''}Qualifikationen werden dadurch nicht bestätigt.`))return;pairs.forEach(([e,p])=>setApproval(e,p,true));renderMatrix();renderHistory();});
$('start').addEventListener('change',historyDefaults);
{
 const today=new Date(),year=today.getFullYear(),month=String(today.getMonth()+1).padStart(2,'0');
 $('start').value=`${year}-${month}-01`;$('end').value=`${year}-${month}-${new Date(year,today.getMonth()+1,0).getDate()}`;
 $('timezone').value=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';historyDefaults();
}
$('planView').onchange=renderCalendar;
for(const [id,delta] of [['prevMonth',-1],['nextMonth',1]])action(id,()=>{const date=new Date(planMonth+'-01T12:00:00Z');date.setUTCMonth(date.getUTCMonth()+delta);planMonth=date.toISOString().slice(0,7);renderCalendar();});

api('/api/version').then(v=>{$('version').textContent='Version '+v.version;$('logout').hidden=!v.auth_enabled;}).catch(()=>{$('version').textContent='Version nicht verfügbar';});

// The application shell and project wizard use this API instead of mutating editor state.
window.PlannerApp={
 getState:plannerState,
 async openProject(candidate){
  if(projectSwitchBusy())throw Error('Die laufende Aktion zuerst abschließen.');
  projectBusy=true;updateJobButtons();
  try{const checked=await api('/api/snapshots/check','POST',candidate);if(!canReplace())return false;load(checked);return true;}
  finally{projectBusy=false;updateJobButtons();}
 },
 openSavedProject,openJob,
 refreshProjects:saved,refreshJobs:savedJobs
};
window.addEventListener('planner:navigate',event=>{const panel=event.detail?.panel;if(!['projects','team','rules','calculate','plan'].includes(panel))return;activePanel=panel;renderActivePanel();refreshAutomaticReadiness();});
window.addEventListener('planner:open-project',event=>openSavedProject(event.detail?.id).catch(error=>notice(error.message,true)));
window.addEventListener('planner:open-job',event=>openJob(event.detail?.id).catch(error=>notice(error.message,true)));
window.addEventListener('planner:rename',event=>{
 if(!snapshot||projectSwitchBusy())return;const name=String(event.detail?.name??'').trim();
 if(!name||name.length>120){notice('Projektname muss 1 bis 120 Zeichen enthalten.',true);publishState();return;}
 if(snapshot.metadata.project_name===name)return;snapshot.metadata={...snapshot.metadata,project_name:name};markChanged();notice('Projektname geändert. Mit dem nächsten Speichern wird er dauerhaft übernommen.');
});
for(const [id,draw] of [['people',renderPeople],['shifts',renderShifts],['positions',renderPositions],['demands',renderDemands],['plan',renderAssignments]]){
 const details=$(id).closest('details');details?.addEventListener('toggle',()=>{if(snapshot&&details.open&&(id!=='plan'||$(id).dataset.renderVersion!==String(changeVersion)))draw();});
}
$('json').closest('details')?.addEventListener('toggle',()=>syncJson());
publishState();

const addPersonButton=button($('matrixSearch').closest('.surface-toolbar')??$('matrixSearch').parentElement.parentElement,'Person hinzufügen',addPerson);addPersonButton.id='addPerson';addPersonButton.className='primary';updateJobButtons();
