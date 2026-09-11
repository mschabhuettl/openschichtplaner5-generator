'use strict';
const assert=require('node:assert/strict');
const {groups,apply}=require('../../sp5generator/static/service-groups.js');
const shift=(id,day,kind='unconfirmed',end='06:00',paid=480)=>({id,name:'Dienst A',kind,paid_minutes:paid,segments:[{start:`2026-01-${day}T22:00:00Z`,end:`2026-01-${String(+day+1).padStart(2,'0')}T${end}:00Z`}]});
const snapshot={timezone:'UTC',positions:[{id:'p',function_id:'service-a'}],shifts:[shift('s1','01'),shift('s2','02','day'),shift('s3','03'),shift('s4','04','unconfirmed','07:00'),shift('s5','05','unconfirmed','06:00',450)],demands:[1,2,3,4,5].map(i=>({shift_id:'s'+i,position_id:'p'}))};
const rows=groups(snapshot);assert.equal(rows.length,3);assert.equal(rows[0].pending,2);assert.equal(rows[0].times[0][2],1);assert.equal(apply(snapshot,rows[0].key,'night'),2);assert.equal(snapshot.shifts[1].kind,'day');assert.equal(snapshot.shifts[3].kind,'unconfirmed');assert.equal(apply(snapshot,rows[0].key,'night'),0);assert.throws(()=>apply(snapshot,rows[0].key,'other'));
snapshot.positions.push({id:'q',function_id:'service-b'});snapshot.demands.push({shift_id:'s4',position_id:'q'});assert(!groups(snapshot).some(g=>g.shiftIds.includes('s4')));
{
 const {suggest}=require('../../sp5generator/static/service-groups.js');
 const pattern=times=>({times});
 assert.equal(suggest(pattern([[0,'18:00',1,'06:00']])).kind,'night');
 assert.equal(suggest(pattern([[0,'08:00',0,'16:00']])).kind,'day');
 assert.equal(suggest(pattern([[0,'21:00',0,'23:00'],[1,'05:00',1,'07:00']])).kind,'day');
 assert.equal(suggest(pattern([[0,'21:00',1,'01:00']])).kind,'night');
 assert.equal(suggest(pattern([[0,'08:00',0,'12:00']]),'08:00','12:00',180).kind,'night');
 assert.equal(suggest(pattern([[0,'18:00',0,'06:00']])),null);
 assert.throws(()=>suggest(pattern([]),'22:00','22:00'));
}
{
 const {preview}=require('../../sp5generator/static/service-groups.js');
 const example={timezone:'UTC',positions:[{id:'p',function_id:'service-a'}],shifts:[shift('s1','01'),shift('s2','02','day'),shift('s3','03'),shift('orphan','04')],demands:[1,2,3].map(i=>({shift_id:'s'+i,position_id:'p'}))};
 const before=structuredClone(example),rule={start:'22:00',end:'06:00',minimum:180};
 assert.deepEqual(Object.fromEntries(Object.entries(preview(example,rule)).filter(([key])=>key!=='rows')),{pending:3,day:0,night:2,skipped:1});
 assert.deepEqual(example,before,'Preview never confirms shifts');
 assert.equal(preview(example,{...rule,start:'08:00',end:'16:00'}).day,2);
 assert.throws(()=>preview({...example,shifts:[]},{...rule,minimum:null}),'Invalid settings fail even with no pending rows');
 example.shifts[0].segments[0].end='2026-01-01T20:00:00Z';
 assert.equal(preview(example,rule).skipped,2);
}
