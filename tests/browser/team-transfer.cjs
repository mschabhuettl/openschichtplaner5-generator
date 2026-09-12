'use strict';
// Synthetic demo project only; no SP5 source and no personal data.
const assert=require('node:assert/strict');
module.exports=async function teamTransfer({page,base}){
 await page.goto(base);
 await page.evaluate(async()=>{load(await api('/api/demo'));navigate('team');
  document.querySelector('#teamTransfer').open=true;});

 const csv=await page.evaluate(()=>TeamTransfer.toCsv(currentSnapshot()));
 assert(csv.startsWith('﻿id;name;team_ids;profile_ids;target_minutes;contractual_weekly_minutes'),
  'Header is the documented semicolon layout with a BOM');
 const before=await page.evaluate(()=>structuredClone(snapshot.employees));
 assert(before.length>=2);

 // Edit the first person, drop the last row entirely, add an unknown id.
 const edited=await page.evaluate(([text,id])=>{
  const lines=text.replace(/^﻿/,'').trim().split('\r\n');
  const columns=lines[1].split(';');columns[1]='Geänderter Name';columns[4]='777';
  lines[1]=columns.join(';');
  lines.pop();
  return '﻿'+lines.join('\r\n')+'\r\nsp5:employee:unbekannt;X;;;;\r\n';
 },[csv,before[0].id]);

 let report=await page.evaluate(text=>TeamTransfer.preview(currentSnapshot(),text),edited);
 assert.equal(report.changes.length,1);
 assert.deepEqual(report.changes[0].update,{name:'Geänderter Name',target_minutes:777});
 assert.equal(report.missing,1,'A dropped row deletes nobody');
 assert.equal(report.errors.length,1);
 assert.match(report.errors[0],/Unbekannte Personenkennung/);

 // Errors block the apply; the project stays untouched.
 await assert.rejects(
  page.evaluate(text=>TeamTransfer.apply(snapshot,TeamTransfer.preview(currentSnapshot(),text)),edited),
  /korrigieren/);
 assert.deepEqual(await page.evaluate(()=>structuredClone(snapshot.employees)),before);

 // Without the unknown row the change applies and keeps everything else.
 const clean=edited.split('\r\n').filter(line=>!line.startsWith('sp5:employee:unbekannt')).join('\r\n');
 const applied=await page.evaluate(text=>{
  const r=TeamTransfer.preview(currentSnapshot(),text);
  return [TeamTransfer.apply(snapshot,r),structuredClone(snapshot.employees)];
 },clean);
 assert.equal(applied[0],1);
 const after=applied[1];
 assert.equal(after.length,before.length,'Nobody is created or removed');
 assert.equal(after[0].name,'Geänderter Name');
 assert.equal(after[0].target_minutes,777);
 for(const key of ['approvals','qualifications','availability','unavailable','id','team_ids','profile_ids'])
  assert.deepEqual(after[0][key],before[0][key],`${key} is preserved`);
 assert.deepEqual(after.slice(1),before.slice(1),'Rows left out stay exactly as they were');

 // A header that does not match is rejected before anything is read.
 await assert.rejects(page.evaluate(()=>TeamTransfer.preview(currentSnapshot(),'id;name\r\ne;f\r\n')),/Kopfzeile/);
 console.log('Team transfer: export layout, unknown ids, dropped rows, error gate and preserved fields passed.');
};
