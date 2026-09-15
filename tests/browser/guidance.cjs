'use strict';
// Newly constructed synthetic project only; the server is the local browser fixture.
const assert=require('node:assert/strict');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
module.exports=async function guidance({page,base}){
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
 await page.goto(base);
 const demo=size=>JSON.parse(execFileSync(process.env.WEB_TEST_PYTHON||'python3',
  ['-c',`from sp5generator.demo import make_demo; print(make_demo(${size[0]},${size[1]}).model_dump_json())`],
  {cwd:root,encoding:'utf8',maxBuffer:8*1024*1024}));
 const small=demo([6,7]),large=demo([120,31]);
 large.id+=':gross';
 async function open(project){
  await page.evaluate(value=>load(value,true),project);
  await page.locator('.main-nav [data-navigate="calculate"]').click();
  await page.locator('[data-panel="calculate"]').waitFor({state:'visible'});
 }

 // Die vorgeschlagene Rechenzeit richtet sich nach dem Zuschnitt.
 await open(small);
 const smallLimit=Number(await page.locator('#limit').inputValue());
 assert.match(await page.locator('#limitSuggestion').innerText(),/Vorschlag für diesen Zuschnitt: \d+ Sekunden/);
 assert.match(await page.locator('#limitSuggestion').innerText(),/6 Personen, 28 Bedarfe/);
 await open(large);
 const largeLimit=Number(await page.locator('#limit').inputValue());
 assert(largeLimit>smallLimit,`Der größere Zuschnitt bekommt mehr Zeit (${largeLimit} > ${smallLimit})`);
 assert(largeLimit<=600&&smallLimit>=30,'Der Vorschlag bleibt im erlaubten Bereich');

 // Eine eigene Eingabe wird nicht überschrieben.
 await page.fill('#limit','7');
 await page.evaluate(()=>{const s=window.PlannerApp.getState().snapshot;s.employees[0].name='Testperson geändert';invalidateResult();});
 await page.locator('.main-nav [data-navigate="team"]').click();
 await page.locator('.main-nav [data-navigate="calculate"]').click();
 assert.equal(await page.locator('#limit').inputValue(),'7','Die eigene Rechenzeit bleibt stehen');

 // Von der Berechnung zu den Gewichten, die dort erwähnt werden.
 await page.getByRole('button',{name:'Optimierungswünsche',exact:true}).click();
 await page.locator('[data-panel="rules"]').waitFor({state:'visible'});
 assert.equal(await page.locator('#weightsSection').evaluate(node=>node.open),true,'Die Gewichte sind aufgeklappt');
 assert(await page.locator('#weights').isVisible());

 // Von den einzelnen Bedarfen zur Tabelle über alle Tage.
 await page.evaluate(()=>selectConfig('bedarf'));
 await page.getByRole('button',{name:'Zur Bedarfstabelle',exact:true}).click();
 await page.locator('[data-panel="demand"]').waitFor({state:'visible'});

 // Einstellungen: ein Bereich zur Zeit, über eine Unternavigation erreichbar.
 await page.locator('.main-nav [data-navigate="rules"]').click();
 await page.locator('[data-panel="rules"]').waitFor({state:'visible'});
 const bereiche=page.locator('#rulesNav button');
 assert.equal(await bereiche.count(),6,'Sechs Einstellungsbereiche');
 for(const [name,sichtbar] of [['Regelprofile','#profiles'],['Ziele','#weights'],['Bedarf','#demands']]){
  await bereiche.filter({hasText:name}).click();
  assert.equal(await page.locator(sichtbar).isVisible(),true,`${name} ist sichtbar`);
  assert.equal(await page.locator('#rulesNav button.active').innerText(),name);
  assert.equal(await page.locator('[data-config]:not([hidden])').count(),1,'Genau ein Bereich ist offen');
 }

 // Ohne offene Vorschläge wird kein Übernehmen angeboten.
 await page.locator('.main-nav [data-navigate="team"]').click();
 await page.locator('[data-panel="team"]').waitFor({state:'visible'});
 assert.equal(await page.locator('#historyBulk').isVisible(),false,'Kein Streifen ohne historische Vorschläge');

 assert.deepEqual(errors,[]);
 console.log('Guidance: computation-time suggestion, kept manual entry, weights shortcut, demand cross-link and hidden empty bulk bar passed.');
};
