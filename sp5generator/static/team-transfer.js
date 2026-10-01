/* Edit existing people in a spreadsheet. Never creates or deletes a person. */
(function(root){
 const COLUMNS=['id','name','team_ids','profile_ids','target_minutes','contractual_weekly_minutes'];
 const LIST=new Set(['team_ids','profile_ids']);
 const NUMBER=new Set(['target_minutes','contractual_weekly_minutes']);
 const ENCODING_COLUMN='text_encoding',ENCODING='apostrophe-v1';
 // Versioned, reversible text encoding, applied BEFORE CSV delimiter quoting:
 // prepend one apostrophe to formula prefixes, whitespace, or an apostrophe.
 // Decode exactly one guard only in marked exports; legacy CSV stays literal.
 // Never trim names/identifiers. Spreadsheet re-saves may rewrite text: review
 // the preview, preserve the encoding column, and import these columns as text.
 const needsTextGuard=text=>/^[\s'=+\-@＝＋－＠]/u.test(text);
 function csvCell(value){
  let text=String(value??'');
  if(needsTextGuard(text))text="'"+text;
  return /[";\r\n]/.test(text)?'"'+text.replace(/"/g,'""')+'"':text;
 }
 const unguard=text=>text.startsWith("'")&&needsTextGuard(text.slice(1))?text.slice(1):text;
 // Keep the usual comma-separated list editable; JSON disambiguates IDs that
 // themselves contain commas or look like the JSON-list syntax.
 const listText=values=>values.some(value=>value.includes(',')||value.startsWith('['))?JSON.stringify(values):values.join(',');
 const read=person=>COLUMNS.map(key=>LIST.has(key)?listText(person[key]):person[key]??'');

 function toCsv(snapshot){
  const rows=[[...COLUMNS,ENCODING_COLUMN],...snapshot.employees.map(person=>[...read(person),ENCODING])];
  // BOM and semicolons so Excel opens the file in the user's locale.
  return '﻿'+rows.map(row=>row.map(csvCell).join(';')).join('\r\n')+'\r\n';
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
  const encoded=header.join(';')===[...COLUMNS,ENCODING_COLUMN].join(';');
  if(!encoded&&header.join(';')!==COLUMNS.join(';'))
   throw new Error('Kopfzeile muss genau lauten: '+[...COLUMNS,ENCODING_COLUMN].join(';')+' (ältere Dateien auch ohne text_encoding).');
  const people=new Map(snapshot.employees.map(e=>[e.id,e]));
  const teams=new Set(snapshot.employees.flatMap(e=>e.team_ids));
  const profiles=new Set(snapshot.profiles.map(p=>p.id));
  const seen=new Set();
  for(const [index,row] of rows.slice(1).entries()){
   const line=index+2,record=Object.fromEntries(COLUMNS.map((key,i)=>[key,encoded?unguard(row[i]??''):row[i]??'']));
   const person=people.get(record.id);
   if(!person){errors.push(`Zeile ${line}: Unbekannte Personenkennung. Es wird niemand angelegt.`);continue;}
   if(encoded&&row[COLUMNS.length]!==ENCODING){errors.push(`Zeile ${line}: Unbekannte oder fehlende Text-Kodierung; text_encoding muss ${ENCODING} bleiben.`);continue;}
   if(seen.has(record.id)){errors.push(`Zeile ${line}: Personenkennung mehrfach in der Datei.`);continue;}
   seen.add(record.id);
   const update={};
   for(const key of COLUMNS.slice(1)){
    const raw=NUMBER.has(key)?record[key].trim():record[key];
    if(LIST.has(key)){
     let values;
     try{
      values=encoded&&raw.startsWith('[')?JSON.parse(raw):raw?raw.split(','):[];
      if(!Array.isArray(values)||values.some(value=>typeof value!=='string'||!value.length))throw Error();
     }catch{errors.push(`Zeile ${line}: ${key} muss eine Liste von Kennungen sein (Kommaliste oder JSON-Textliste).`);continue;}
     const known=key==='team_ids'?teams:profiles;
     const missing=values.filter(v=>!known.has(v));
     if(missing.length){errors.push(`Zeile ${line}: ${missing.length} unbekannte Kennung(en) in ${key}.`);continue;}
     if(!values.length){errors.push(`Zeile ${line}: ${key} darf nicht leer sein.`);continue;}
     if(JSON.stringify(values)!==JSON.stringify(person[key]))update[key]=values;
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
    if(!raw.trim()){errors.push(`Zeile ${line}: name darf nicht leer sein.`);continue;}
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

 const api={COLUMNS,csvCell,toCsv,parse,preview,apply};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TeamTransfer=api;
})(globalThis);
