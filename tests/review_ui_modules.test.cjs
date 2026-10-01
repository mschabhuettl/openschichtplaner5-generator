'use strict';
// Synthetic module regressions; run: node --test tests/review_ui_modules.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ProjectJSON=require('../sp5generator/static/project-json.js');
const NumericGroups=require('../sp5generator/static/service-groups.js');
test('T08 zero-valued float provenance does not create a boundary service',()=>{
 const s=fixture();s.boundary_work=[{id:'w',kind:'unknown',segments:[{start:'2026-10-01T22:00:00Z',end:'2026-10-02T06:00:00Z'}]}];
 s.metadata.provenance={w:{function_id:0}};assert.equal(NumericGroups.groups(s).length,0);
 s.metadata.provenance.w.function_id=ProjectJSON.parse('0.0');assert.equal(NumericGroups.groups(s).length,0);
});

test('T08 native float night minimum and opaque provenance service key',()=>{
 const group={times:[[0,'22:00',1,'06:00']]};
 assert.deepEqual(NumericGroups.suggest(group,'22:00','06:00',ProjectJSON.parse('180.0')),NumericGroups.suggest(group));
 assert.throws(()=>NumericGroups.suggest(group,'22:00','06:00',BigInt('180')),/Mindestdauer/);
 const s=fixture();s.boundary_work=[{id:'w',kind:'unknown',segments:[{start:'2026-10-01T22:00:00Z',end:'2026-10-02T06:00:00Z'}]}];
 s.metadata.provenance={w:{function_id:BigInt('9007199254740993')}};
 assert.match(NumericGroups.groups(s)[0].key,/9007199254740993/);
});
test('T05 setup reuse, next period and team CSV preserve clone carriers and current edits',()=>{
 const s=fixture(),old=fixture();s.metadata.opaque=ProjectJSON.parse('{"n":9007199254740993,"rows":[-0.0,1.0,1e20],"deleted":4}');
 const prior=ProjectJSON.stringify(s.metadata.opaque);old.metadata.opaque={stale:true};
 const prepared=SetupAssistant.prepare(s,old,{sameSource:true});
 assert.equal(ProjectJSON.stringify(prepared.metadata.opaque),prior);
 prepared.metadata.opaque.rows.reverse();delete prepared.metadata.opaque.deleted;
 prepared.metadata.opaque.n=BigInt('9007199254740995');
 const after=ProjectJSON.stringify(prepared.metadata.opaque);
 assert.equal(after,'{"n":9007199254740995,"rows":[1e20,1.0,-0.0]}');
 assert.equal(ProjectJSON.stringify(s.metadata.opaque),prior);
 SetupAssistant.followingPeriod(prepared);TeamTransfer.toCsv(prepared);
 assert.equal(ProjectJSON.stringify(prepared.metadata.opaque),after);
});

const SetupAssistant = require('../sp5generator/static/setup-assistant.js');
const TeamTransfer = require('../sp5generator/static/team-transfer.js');

function fixture() {
  return {
    id: 'review-only', timezone: 'UTC',
    period_start: '2026-10-01', period_end: '2026-10-31',
    context_start: '2026-09-23', context_end: '2026-11-08',
    employees: [{id: ' person:01 ', name: 'Synthetic person', team_ids: ['t'], profile_ids: ['p'],
      target_minutes: 600, contractual_weekly_minutes: null, max_period_minutes: null, excluded: false,
      approvals: [], qualifications: [], availability: [], unavailable: [], allowed_kinds: ['day', 'night']}],
    profiles: [{id: 'p', confirmed: true, valid_from: '2025-01-01', valid_until: '2028-12-31'}],
    positions: [], shifts: [], demands: [], boundary_work: [], restrictions: [], wishes: [], unresolved: [],
    metadata: {adapter: 'sp5-api'}
  };
}

test('UI-002: same-period carry-forward preserves exclusion and every explicit personal cap', () => {
  for (const cap of [720, 0, null]) {
    for (const excluded of [true, false]) {
      const imported = fixture(), previous = fixture();
      imported.employees[0].max_period_minutes = 123;
      imported.employees[0].excluded = !excluded;
      previous.employees[0].max_period_minutes = cap;
      previous.employees[0].excluded = excluded;
      const before = structuredClone({imported, previous});
      const result = SetupAssistant.prepare(imported, previous, {sameSource: true});
      assert.equal(result.employees[0].excluded, excluded, 'user exclusion is retained');
      assert.equal(result.employees[0].max_period_minutes, cap, 'zero and explicit no-cap are retained');
      assert.equal(result.employees[0].id, previous.employees[0].id);
      assert.equal(result.metadata.setup_review.reusedPeople, 1);
      assert.deepEqual(result.metadata.setup_review.review, []);
      assert.deepEqual(result.unresolved, []);
      assert.deepEqual({imported, previous}, before, 'neither source object is mutated');
    }
  }
});

test('UI-002: a different period retains the hard cap pending explicit person-specific review', () => {
  for (const changedDate of ['period_start', 'period_end']) {
    for (const cap of [0, 720]) {
      const previous = fixture(), imported = fixture();
      previous.employees[0].excluded = true;
      previous.employees[0].max_period_minutes = cap;
      imported[changedDate] = changedDate === 'period_start' ? '2026-10-02' : '2026-11-30';
      imported.employees[0].target_minutes = 9000;
      const before = structuredClone({previous, imported});
      const result = SetupAssistant.prepare(imported, previous, {sameSource: true});
      assert.equal(result.employees[0].excluded, true);
      assert.equal(result.employees[0].max_period_minutes, cap, 'do not drop or automatically scale a hard cap');
      assert.equal(result.employees[0].target_minutes, 9000, 'fresh source target is not overwritten');
      const review = result.metadata.setup_review.review;
      assert.equal(review.length, 1, 'requires an explicit period review, not silent reuse');
      for (const detail of [previous.employees[0].id, `${cap}`, previous.period_start,
        previous.period_end, imported.period_start, imported.period_end]) {
        assert(review[0].includes(detail), 'review identifies person, cap and both periods: ' + detail);
      }
      assert.match(review[0], /prüfen/);
      assert.match(review[0], /unverändert/);
      assert.deepEqual(result.unresolved, review.map(text => 'Einstellungsübernahme: ' + text),
        'review enters the existing unresolved workflow');
      assert.deepEqual({previous, imported}, before);
    }
  }
});

test('UI-002: reuse stays source-checked and identity-exact; absent settings keep fresh values', () => {
  const previous = fixture(), imported = fixture();
  previous.employees[0].excluded = true;
  previous.employees[0].max_period_minutes = 720;
  assert.throws(() => SetupAssistant.prepare(imported, previous), /Datenquelle/);
  imported.employees[0].id = imported.employees[0].id.trim();
  let result = SetupAssistant.prepare(imported, previous, {sameSource: true});
  assert.equal(result.employees[0].excluded, false);
  assert.equal(result.employees[0].max_period_minutes, null);
  assert.equal(result.metadata.setup_review.reusedPeople, 0);
  assert.deepEqual(result.metadata.setup_review.newPeople, [imported.employees[0].id]);
  delete previous.employees[0].excluded;
  delete previous.employees[0].max_period_minutes;
  imported.employees[0].id = previous.employees[0].id;
  imported.employees[0].excluded = true;
  imported.employees[0].max_period_minutes = 123;
  result = SetupAssistant.prepare(imported, previous, {sameSource: true});
  assert.equal(result.employees[0].excluded, true);
  assert.equal(result.employees[0].max_period_minutes, 123);
});

const guardedText = ['=1+1', '+1+1', '-1+1', '@SUM(1)', '\ttext', '\rtext', '\ntext',
  ' =1+1', '\t\r\n+1', '\u00a0@sum(1)', '  ordinary text ', "'literal", "'=1+1", "''=1+1",
  '＝1+1', '＋1+1', '－1+1', '＠SUM(1)', '=value;"quoted"\r\nnext'];

test('UI-008: shared csvCell neutralizes text before delimiter quoting in both APIs', () => {
  const browserGlobal = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../sp5generator/static/team-transfer.js'), 'utf8'), browserGlobal);
  for (const api of [TeamTransfer, browserGlobal.TeamTransfer]) {
    assert.equal(typeof api.csvCell, 'function', 'export the common text-cell helper');
    for (const value of guardedText) {
      const rawCell = api.parse(api.csvCell(value) + ';sentinel\r\n')[0][0];
      assert.equal(rawCell, "'" + value, 'guard precedes even original whitespace and apostrophes');
    }
    assert.equal(api.csvCell('semi;colon'), '"semi;colon"');
    assert.equal(api.csvCell('a"b'), '"a""b"');
    assert.equal(api.csvCell(null), '');
    assert.equal(api.csvCell(0), '0');
    assert.equal(api.csvCell('ordinary'), 'ordinary');
  }
  const snapshot = fixture();
  Object.assign(snapshot.employees[0], {id: '=id', name: '=1+1', team_ids: ['+team'], profile_ids: ['@profile']});
  const fields = TeamTransfer.parse(TeamTransfer.toCsv(snapshot))[1];
  assert.deepEqual(fields.slice(0, 6), ["'=id", "'=1+1", "'+team", "'@profile", '600', '']);
});

// Plain CSV serialization deliberately does not apply the application's text encoding.
const plainCell = value => /[";\r\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
const plainCsv = rows => rows.map(row => row.map(plainCell).join(';')).join('\r\n') + '\r\n';

test('UI-008: safe team CSV round-trips literal apostrophes, whitespace and exact IDs without accumulating escapes', () => {
  for (const value of [...guardedText, 'trailing  ', 't,one', '[literal-id]', 'line\r\nend']) {
    const snapshot = fixture();
    Object.assign(snapshot.employees[0], {id: value, name: value, team_ids: [value, ' other team '],
      profile_ids: [value, "'profile"]});
    snapshot.profiles = [{id: value}, {id: "'profile"}];
    const before = structuredClone(snapshot);
    for (let round = 0; round < 3; round++) {
      const report = TeamTransfer.preview(snapshot, TeamTransfer.toCsv(snapshot));
      assert.deepEqual(report.errors, [], 'exact identifiers resolve: ' + JSON.stringify(value));
      assert.deepEqual(report.changes, [], 'the CSV does not propose silent text/ID edits');
      assert.equal(report.unchanged, 1);
      assert.equal(report.missing, 0);
      assert.equal(TeamTransfer.apply(snapshot, report), 0);
      assert.deepEqual(snapshot, before);
    }
  }
});

test('UI-008: versioned text editing is reversible while legacy six-column CSV stays literal', () => {
  const snapshot = fixture();
  Object.assign(snapshot.employees[0], {id: "'=id", name: "'=literal", team_ids: [' team '], profile_ids: ["'p"]});
  snapshot.profiles = [{id: "'p"}];
  const before = structuredClone(snapshot);
  const legacy = plainCsv([TeamTransfer.COLUMNS, ["'=id", "'=literal", ' team ', "'p", '600', '']]);
  const report = TeamTransfer.preview(snapshot, legacy);
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.changes, [], 'legacy leading apostrophes are text, not an implicit encoding');
  const edited = structuredClone(snapshot);
  edited.employees[0].name = "  '=new;\"name\"\r\n";
  edited.employees[0].target_minutes = 0;
  const change = TeamTransfer.preview(snapshot, TeamTransfer.toCsv(edited));
  assert.deepEqual(change.errors, []);
  assert.deepEqual(change.changes[0].update, {name: edited.employees[0].name, target_minutes: 0});
  assert.deepEqual(snapshot, before, 'preview is non-mutating');
  assert.equal(TeamTransfer.apply(snapshot, change), 1);
  assert.deepEqual(snapshot, edited, 'all unrelated fields remain untouched');
});

test('UI-008: malformed encoding and near-match identifiers cannot silently change people', () => {
  const snapshot = fixture(), before = structuredClone(snapshot);
  const encoded = TeamTransfer.parse(TeamTransfer.toCsv(snapshot));
  assert.equal(encoded[0].at(-1), 'text_encoding', 'exports declare reversible text semantics');
  encoded[1][encoded[0].indexOf('text_encoding')] = 'unsupported-encoding';
  const bad = TeamTransfer.preview(snapshot, plainCsv(encoded));
  assert(bad.errors.some(error => /Kodierung/.test(error)));
  assert.throws(() => TeamTransfer.apply(snapshot, bad), /korrigieren/);
  const nearMatch = plainCsv([TeamTransfer.COLUMNS, [snapshot.employees[0].id.trim(), 'Changed', 't', 'p', '600', '']]);
  const rejected = TeamTransfer.preview(snapshot, nearMatch);
  assert(rejected.errors.some(error => /Unbekannte Personenkennung/.test(error)), 'IDs are not trimmed into a match');
  assert.deepEqual(snapshot, before);
});
