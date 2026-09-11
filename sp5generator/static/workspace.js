'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const names = {projects:'Projekte',team:'Team & Freigaben',rules:'Regeln & Bedarf',calculate:'Berechnen',plan:'Dienstplan'};
  const states = {queued:'In Warteschlange',running:'Wird berechnet',succeeded:'Berechnung beendet',failed:'Fehlgeschlagen',cancelled:'Abgebrochen'};
  let activePanel = 'projects';
  let current = {snapshot:null,assignments:[],dirty:false,jsonDirty:false,jobId:null,solving:false};
  let projects = [], jobs = [], searchableProjects = [];
  let projectPage=0, lastUiBusy=false;
  const projectPageSize=24;
  const dateFormatters=new Map();
  const node = (tag, text, className) => {
    const item = document.createElement(tag);
    if(text !== undefined) item.textContent = text;
    if(className) item.className = className;
    return item;
  };
  const icon = name => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.classList.add('icon');svg.setAttribute('aria-hidden','true');
    const use = document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#icon-'+name);svg.append(use);return svg;
  };
  const dispatch = (name,detail) => window.dispatchEvent(new CustomEvent('planner:'+name,{detail}));
  const date = (value, options={day:'2-digit',month:'short',year:'numeric'}) => {
    if(!value)return '—';
    const parsed = new Date(typeof value==='number'?value*1000:/^\d{4}-\d\d-\d\d$/.test(value)?value+'T12:00:00Z':value);
    if(Number.isNaN(+parsed))return '—';
    const key=JSON.stringify(options);
    if(!dateFormatters.has(key))dateFormatters.set(key,new Intl.DateTimeFormat('de-DE',options));
    return dateFormatters.get(key).format(parsed);
  };
  const period = project => `${date(project.period_start,{day:'2-digit',month:'short'})} – ${date(project.period_end)}`;
  const projectName = project => project.project_name || project.metadata?.project_name || project.name || project.metadata?.name || `Planung ${date(project.period_start,{month:'long',year:'numeric'})}`;
  const number = value => Number(value||0).toLocaleString('de-DE');
  const busy = () => !!(current.solving || current.jobId || current.projectBusy || ['save','saveDraft'].some(id=>byId(id)?.dataset.busy==='true'));
  const show = (id, visible) => {byId(id).hidden = !visible;};
  const text = (id, value) => {byId(id).textContent = value;};
  function navigate(panel,options={}) {
    if(!Object.hasOwn(names,panel))return false;
    if(panel!=='projects'&&!current.snapshot)return false;
    const changed=activePanel!==panel;
    activePanel=panel;
    document.body.dataset.activePanel=panel;
    document.querySelectorAll('[data-panel]').forEach(section => section.hidden=section.dataset.panel!==panel);
    byId('workspace').hidden=panel==='projects'||!current.snapshot;
    document.querySelectorAll('.main-nav [data-navigate]').forEach(button => {
      const selected=button.dataset.navigate===panel;
      button.classList.toggle('active',selected);
      if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
    });
    text('breadcrumbCurrent',names[panel]);
    document.title=`${names[panel]} · OpenSchichtplaner5 Generator`;
    dispatch('navigate',{panel});
    if(options.focus){const heading=document.querySelector(`[data-panel="${panel}"] h1, [data-panel="${panel}"] h2`);if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}}
    if(options.scroll||changed)window.scrollTo({top:0,behavior:'instant'});
    return true;
  }
  function emptyProjects(searching) {
    const box=node('div',undefined,'empty-state');
    const symbol=node('div',undefined,'empty-icon');symbol.append(icon('folder'));box.append(symbol);
    box.append(node('h3',searching?'Kein passendes Projekt gefunden.':'Platz für Ihren ersten Dienstplan.'));
    box.append(node('p',searching?'Versuchen Sie einen anderen Projektnamen oder Zeitraum.':'Starten Sie mit Ihrem Team und Ihren Schichten. Oder lernen Sie den Arbeitsbereich mit einem Demoprojekt kennen.'));
    if(!searching){const actions=node('div',undefined,'empty-actions');
      const create=node('button','Neues Projekt erstellen','primary');create.type='button';create.onclick=()=>byId('newProject').click();
      const demo=node('button','Demo ausprobieren');demo.type='button';demo.disabled=busy();demo.onclick=()=>{byId('importDetails').open=true;byId('demo').click();};
      actions.append(create,demo);box.append(actions);
    }
    return box;
  }
  function renderProjects() {
    const query=byId('projectSearch').value.trim().toLocaleLowerCase('de');
    const filtered=searchableProjects.filter(entry=>!query||entry.search.includes(query)).map(entry=>entry.project);
    const pages=Math.max(1,Math.ceil(filtered.length/projectPageSize));
    projectPage=Math.max(0,Math.min(projectPage,pages-1));
    const offset=projectPage*projectPageSize;
    const visible=filtered.slice(offset,offset+projectPageSize);
    const cards=byId('projectCards');cards.replaceChildren();
    text('projectTotal',number(projects.length));text('projectCount',number(filtered.length));
    show('projectPagination',filtered.length>projectPageSize);
    text('projectPageStatus',`${number(filtered.length?offset+1:0)}–${number(offset+visible.length)} von ${number(filtered.length)} Projekten · Seite ${number(projectPage+1)} / ${number(pages)}`);
    byId('projectPagePrevious').disabled=projectPage===0;
    byId('projectPageNext').disabled=projectPage>=pages-1;
    if(!filtered.length){cards.append(emptyProjects(!!query));return;}
    const fragment=document.createDocumentFragment();
    visible.forEach(project=>{
      const card=node('button',undefined,'project-card');card.type='button';card.disabled=busy();card.dataset.projectId=project.id;card.setAttribute('aria-label',`${projectName(project)} öffnen`);
      const head=node('div',undefined,'project-card-head');const symbol=node('span',undefined,'project-card-icon');symbol.append(icon('calendar'));head.append(symbol);
      if(project.id===current.snapshot?.id)head.append(node('span','Geöffnet','subtle-badge'));else if(project.source==='synthetic')head.append(node('span','Demoprojekt','subtle-badge'));else head.append(node('span','Projekt','subtle-badge'));
      card.append(head,node('h3',projectName(project)),node('span',period(project),'project-card-period'));
      const footer=node('div',undefined,'project-card-footer');const people=node('span');people.append(icon('people'),document.createTextNode(`${number(project.employee_count)} Personen`));footer.append(people,node('span',`Stand ${project.revision??'1'}`),icon('arrow'));card.append(footer);
      card.addEventListener('click',()=>dispatch('open-project',{id:project.id}));fragment.append(card);
    });
    cards.append(fragment);
  }
  function setProjects(list) {
    projects=Array.isArray(list)?list:[];
    searchableProjects=projects.map(project=>({project,search:`${projectName(project)} ${period(project)} ${project.period_start} ${project.period_end}`.toLocaleLowerCase('de')}));
    renderProjects();renderJobs();
  }
  function renderJobs() {
    text('jobTotal',number(jobs.length));text('activeJobTotal',number(jobs.filter(job=>['queued','running'].includes(job.state)).length));
    const list=byId('jobCards');list.replaceChildren();
    if(!jobs.length){list.append(node('div','Noch keine Berechnung. Sobald Sie einen Plan berechnen, finden Sie das Ergebnis hier wieder.','list-empty'));return;}
    jobs.slice(0,8).forEach(job=>{
      const project=projects.find(project=>project.id===job.snapshot_id);
      const row=node('button',undefined,'job-row');row.type='button';row.disabled=busy();row.dataset.jobId=job.id;
      const symbol=node('span',undefined,'job-row-icon');symbol.append(icon('clock'));row.append(symbol);
      const info=node('span');info.append(node('span',job.project_name||(project?projectName(project):'Dienstplan-Berechnung'),'job-row-name'));
      const created=typeof job.created_at==='number'?new Date(job.created_at*1000):new Date(job.created_at);
      info.append(node('span',Number.isNaN(+created)?'Gespeicherte Berechnung':created.toLocaleString('de-DE',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}),'job-row-date'));
      row.append(info,node('span',states[job.state]||job.state,'job-badge '+(['queued','running','succeeded','failed','cancelled'].includes(job.state)?job.state:'')));
      const elapsed=job.finished_at&&job.started_at?Math.max(0,Math.round(job.finished_at-job.started_at)):null;
      row.append(node('span',elapsed===null?'':`${number(elapsed)} Sekunden`,'job-row-duration'),icon('arrow'));
      row.setAttribute('aria-label',`${project?projectName(project):'Berechnung'}: ${states[job.state]||job.state} öffnen`);
      row.addEventListener('click',()=>dispatch('open-job',{id:job.id}));list.append(row);
    });
  }
  function setJobs(list) {jobs=Array.isArray(list)?list:[];renderJobs();}
  function refresh(detail) {
    if(!detail)return;
    const previousId=current.snapshot?.id;
    const previousBusy=lastUiBusy;
    current={...current,...detail};
    const project=current.snapshot;
    document.querySelectorAll('[data-requires-project]').forEach(button=>button.disabled=!project);
    ['topSaveIndicator','headerSave','headerBackup','sidebarProject'].forEach(id=>show(id,!!project));
    byId('newProject').disabled=busy();
    if(previousBusy!==busy()) {renderProjects();renderJobs();}
    lastUiBusy=busy();
    if(!project){navigate('projects');return;}
    if(activePanel!=='projects')byId('workspace').hidden=false;
    const employees=project.employees||[],demands=project.demands||[],shifts=project.shifts||[],profiles=project.profiles||[];
    const assignments=current.assignments||[];
    const minimum=demands.reduce((sum,demand)=>sum+Math.max(0,Number(demand.minimum)||0),0);
    const peopleIds=new Set(employees.map(person=>person.id));
    const byDemand=new Map();
    assignments.forEach(assignment=>{if(!peopleIds.has(assignment.employee_id))return;if(!byDemand.has(assignment.demand_id))byDemand.set(assignment.demand_id,new Set());byDemand.get(assignment.demand_id).add(assignment.employee_id);});
    const filled=demands.reduce((sum,demand)=>sum+Math.min(Math.max(0,Number(demand.minimum)||0),byDemand.get(demand.id)?.size||0),0);
    const coverage=minimum?Math.round(filled/minimum*100):0;
    const days=Math.max(0,Math.round((Date.parse(project.period_end)-Date.parse(project.period_start))/86400000)+1);
    const readiness=current.readiness||{state:'unchecked',count:null};
    const checked=['ready','issues'].includes(readiness.state);
    const hints=checked?readiness.count:0;
    const readinessLabels={unchecked:'noch nicht geprüft',pending:'wird geprüft',draft:'Bearbeitung offen',error:'Prüfung fehlgeschlagen',ready:'Eingabehinweise',issues:'Eingabehinweise'};
    const readinessMessages={unchecked:'Noch keine aktuelle Eingabeprüfung. Beim Öffnen von Berechnen wird automatisch geprüft.',pending:'Aktuelle Eingaben werden geprüft …',draft:'Offene Bearbeitung zuerst übernehmen oder verwerfen. Noch keine aktuelle Eingabeprüfung.',error:'Vorprüfung nicht abgeschlossen. Bitte den angezeigten Fehler prüfen und erneut versuchen.',ready:'Keine offenen Eingabehinweise. Berechnung und unabhängige Ergebnisprüfung stehen noch aus.',issues:`${number(hints)} Hinweise aus der aktuellen Eingabeprüfung. Die konkreten Hinweise unten fachlich bearbeiten.`};
    const title=projectName(project);
    if(document.activeElement!==byId('projectName'))byId('projectName').value=title;
    byId('projectName').readOnly=busy();
    text('projectPeriod',period(project));text('projectTimezone',project.timezone||'');text('projectKind',project.source==='synthetic'?'Demoprojekt':project.metadata?.created_with==='project-setup'?'Eigenes Projekt':'Importiertes Projekt');
    text('sidebarProjectName',title);text('sidebarPeriod',period(project));byId('sidebarCoverage').style.width=coverage+'%';text('sidebarCoverageText',`${number(filled)} von ${number(minimum)} Stellen belegt`);
    text('metricPeople',number(employees.length));text('navPeople',number(employees.length));
    const teamCount=new Set(employees.flatMap(person=>person.team_ids||[])).size;text('metricTeams',teamCount?`${number(teamCount)} ${teamCount===1?'Team':'Teams'}`:'im Projekt');
    text('metricDays',number(days));text('metricCoverage',`${coverage} %`);text('metricAssignments',`${number(filled)} / ${number(minimum)} Stellen`);
    text('metricBlockers',checked?number(hints):readiness.state==='pending'?'…':'—');text('metricBlockersLabel',readinessLabels[readiness.state]||readinessLabels.unchecked);byId('metricBlockers').classList.toggle('bad',readiness.state==='issues'||readiness.state==='error');
    text('navBlockers',number(hints));byId('navBlockers').title='Hinweise aus der aktuellen Eingabeprüfung';show('navBlockers',checked&&hints>0);show('navRunning',!!(current.solving||current.jobId));
    byId('topSaveIndicator').classList.toggle('dirty',!!(current.dirty||current.jsonDirty));
    byId('headerSave').disabled=busy()||byId('save').disabled;
    byId('headerBackup').disabled=byId('backup').disabled;
    text('calcPeriod',`${date(project.period_start)} – ${date(project.period_end)}`);text('calcDays',number(days));text('calcTimezone',project.timezone||'—');
    text('calcPeople',number(employees.length));text('calcShifts',number(shifts.length));text('calcDemand',number(minimum));text('calcFixed',number(assignments.filter(assignment=>assignment.fixed).length));text('calcProfiles',number(profiles.length));
    text('calculationReadiness',readinessMessages[readiness.state]||readinessMessages.unchecked);
    byId('calculationReadiness').classList.toggle('warning',['issues','error','draft'].includes(readiness.state));show('calculationProgress',!!(current.solving||current.jobId));show('planEmpty',!assignments.length);
    if(previousId!==project.id)renderProjects();
  }
  document.querySelectorAll('[data-navigate]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.navigate,{focus:true,scroll:true})));
  document.querySelector('.brand').addEventListener('click',event=>{event.preventDefault();navigate('projects',{focus:true,scroll:true});});
  byId('projectSearch').addEventListener('input',()=>{projectPage=0;renderProjects();});
  byId('projectPagePrevious').addEventListener('click',()=>{projectPage--;renderProjects();byId('projectCards').scrollIntoView({block:'start'});});
  byId('projectPageNext').addEventListener('click',()=>{projectPage++;renderProjects();byId('projectCards').scrollIntoView({block:'start'});});
  byId('projectName').addEventListener('change',()=>{const name=byId('projectName').value.trim();if(name)dispatch('rename',{name});else if(current.snapshot)byId('projectName').value=projectName(current.snapshot);});
  byId('projectName').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();byId('projectName').blur();}if(event.key==='Escape'&&current.snapshot){byId('projectName').value=projectName(current.snapshot);byId('projectName').blur();}});
  byId('headerSave').addEventListener('click',()=>byId('save').click());
  byId('headerBackup').addEventListener('click',()=>byId('backup').click());
  const saveObserver=new MutationObserver(()=>{byId('headerSave').disabled=busy()||byId('save').disabled;byId('headerBackup').disabled=byId('backup').disabled;});
  saveObserver.observe(byId('save'),{attributes:true,attributeFilter:['disabled']});saveObserver.observe(byId('backup'),{attributes:true,attributeFilter:['disabled']});
  window.addEventListener('planner:state',event=>refresh(event.detail));
  document.addEventListener('planner:state',event=>{if(!event.bubbles)refresh(event.detail);});
  document.body.dataset.activePanel=activePanel;
  window.PlannerUI={navigate,refresh,setProjects,setJobs,get panel(){return activePanel;}};
})();
