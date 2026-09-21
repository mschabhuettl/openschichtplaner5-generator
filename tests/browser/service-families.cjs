const assert=require('node:assert/strict');
const {stem,group}=require('../../sp5generator/static/service-families.js');

// Dieselbe Tätigkeit zu verschiedenen Zeitlagen.
assert.equal(stem('OvD TD 5:20-17:20'),'OvD TD');
assert.equal(stem('OVD ND 17:20-5:20'),'OVD ND');
assert.equal(stem('N-CT 6-16'),'N-CT');
assert.equal(stem('AUSB 7-16:14'),'AUSB');
assert.equal(stem('DP-BM-Früh 6-14'),'DP-BM-Früh');
assert.equal(stem('OvD TD 0520'),'OvD TD');
assert.equal(stem('AUSB 18-06'),'AUSB');

// Kein Stamm ohne tragenden Namen, und keine Zahl im Namen verschlucken.
assert.equal(stem('N-10'),'N-10','eine Ziffer im Namen ist keine Zeitlage');
assert.equal(stem('12-20'),'12-20','ohne Namensteil bleibt der Dienst für sich');
assert.equal(stem('144 Trainer'),'144 Trainer');
assert.equal(stem('1450 Fortbildung- 8h'),'1450 Fortbildung- 8h');
assert.equal(stem('Spätdispo SÜD'),'Spätdispo SÜD');
assert.equal(stem(''),'');
assert.equal(stem(null),'');

const familien=group([{name:'N-CT 6-16'},{name:'N-CT 12-22'},{name:'OvD TD 5:20-17:20'},{name:'N-10'}]);
assert.deepEqual(familien.map(f=>[f.name,f.members.length]),[['N-CT',2],['OvD TD',1],['N-10',1]]);
assert.equal(familien[0].id,'familie:N-CT');
// Die Reihenfolge folgt dem ersten Auftreten, damit die Matrix stabil bleibt.
assert.deepEqual(group([{name:'B 6-14'},{name:'A 6-14'}]).map(f=>f.name),['B','A']);

// Ein Stamm ohne Buchstaben ist kein Name, sondern eine weitere Zahl.
assert.equal(stem('7 6-14'),'7 6-14');
assert.equal(stem('2 18-06'),'2 18-06');
