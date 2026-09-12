/* Edit existing people in a spreadsheet. Never creates or deletes a person. */
(function(root){
 const COLUMNS=['id','name','team_ids','profile_ids','target_minutes','contractual_weekly_minutes'];
 const LIST=new Set(['team_ids','profile_ids']);
 const NUMBER=new Set(['target_minutes','contractual_weekly_minutes']);
 const cell=value=>{const text=String(value??'');return /[";\r\n]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text;};
 const read=person=>COLUMNS.map(key=>LIST.has(key)?person[key].join(','):person[key]??'');

 function toCsv(snapshot){
  const rows=[COLUMNS,...snapshot.employees.map(read)];
  // BOM and semicolons so Excel opens the file in the user's locale.
  return '﻿'+rows.map(row=>row.map(cell).join(';')).join('\r\n')+'\r\n';
 }

 function parse(text){
  const rows=[];let row=[],field='',quoted=false;
  const body=text.replace(/^﻿/,'');
  for(let i=0;i<body.length;i++){
   const c=body[i];
   if(quoted){
    if(c!=='"'){field+=c;continue;}
    if(body[i+1]==='"'){field+='"';i++;continue;}
    quoted=false;continue;
   }
   if(c==='"'&&!field){quoted=true;continue;}
   if(c===';'){row.push(field);field='';continue;}
   if(c==='\r')continue;
   if(c==='\n'){row.push(field);rows.push(row);row=[];field='';continue;}
   field+=c;
  }
  if(field||row.length)  {row.push(field);rows.push(row);}
  return rows.filter(r=>r.some(value=>value.trim()!==''));
 }

 function preview(snapshot,text){
  const rows=parse(text),errors=[],changes=[];
  if(!rows.length)throw new Error('Die Datei enthält keine Zeilen.');
  const header=rows[0].map(value=>value.trim());
  if(header.join(';')!==COLUMNS.join(';'))
   throw new Error('Kopfzeile muss genau lauten: '+COLUMNS.join(';'));
  const people=new Map(snapshot.employees.map(e=>[e.id,e]));
  const teams=new Set(snapshot.employees.flatMap(e=>e.team_ids));
  const profiles=new Set(snapshot.profiles.map(p=>p.id));
  const seen=new Set();
  for(const [index,row] of rows.slice(1).entries()){
   const line=index+2,record=Object.fromEntries(COLUMNS.map((key,i)=>[key,(row[i]??'').trim()]));
   const person=people.get(record.id);
   if(!person){errors.push(`Zeile ${line}: Unbekannte Personenkennung. Es wird niemand angelegt.`);continue;}
   if(seen.has(record.id)){errors.push(`Zeile ${line}: Personenkennung mehrfach in der Datei.`);continue;}
   seen.add(record.id);
   const update={};
   for(const key of COLUMNS.slice(1)){
    const raw=record[key];
    if(LIST.has(key)){
     const values=raw?raw.split(',').map(v=>v.trim()).filter(Boolean):[];
     const known=key==='team_ids'?teams:profiles;
     const missing=values.filter(v=>!known.has(v));
     if(missing.length){errors.push(`Zeile ${line}: ${missing.length} unbekannte Kennung(en) in ${key}.`);continue;}
     if(!values.length){errors.push(`Zeile ${line}: ${key} darf nicht leer sein.`);continue;}
     if(values.join(',')!==person[key].join(','))update[key]=values;
     continue;
    }
    if(NUMBER.has(key)){
     if(raw===''){
      if(key==='target_minutes'){errors.push(`Zeile ${line}: target_minutes ist erforderlich.`);continue;}
      if(person[key]!=null)update[key]=null;
      continue;
     }
     if(!/^\d+$/.test(raw)){errors.push(`Zeile ${line}: ${key} muss eine ganze Minutenzahl sein.`);continue;}
     const value=Number(raw);
     if(person[key]!==value)update[key]=value;
     continue;
    }
    if(!raw){errors.push(`Zeile ${line}: name darf nicht leer sein.`);continue;}
    if(person[key]!==raw)update[key]=raw;
   }
   if(Object.keys(update).length)changes.push({id:record.id,name:person.name,update});
  }
  const missing=snapshot.employees.filter(e=>!seen.has(e.id));
  return {changes,errors,missing:missing.length,rows:rows.length-1,
          unchanged:seen.size-changes.length};
 }

 function apply(snapshot,report){
  if(report.errors.length)throw new Error('Zuerst alle gemeldeten Zeilen korrigieren.');
  const people=new Map(snapshot.employees.map(e=>[e.id,e]));
  let count=0;
  for(const change of report.changes){
   const person=people.get(change.id);
   if(!person)throw new Error('Das Projekt hat sich seit der Vorschau geändert. Vorschau erneut erzeugen.');
   // Approvals, qualifications, availability and assignments are untouched.
   Object.assign(person,change.update);
   count++;
  }
  return count;
 }

 const api={COLUMNS,toCsv,parse,preview,apply};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TeamTransfer=api;
})(globalThis);
