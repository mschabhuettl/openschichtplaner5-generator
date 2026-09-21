/* Dienste derselben Art, nur zu anderen Uhrzeiten, gehören zusammen.

   Freigegeben wird eine Tätigkeit, keine Uhrzeit: wer "OvD TD" fahren darf,
   darf ihn um 5:20 wie um 6:00. Die Quelle führt jede Zeitlage als eigenen
   Dienst; diese Zusammenfassung wirkt nur auf die Bedienung, die Freigaben
   selbst bleiben je Dienst gespeichert. */
(function(root){
 // Eine Zeitangabe am Namensende: "5:20-17:20", "6-14", "18–06", "0520".
 // Bewusst eng gefasst - ein Name wie "N-10" ist ein eigener Dienst, keine
 // Zeitlage von "N".
 const ZEIT=/^(?<stamm>.*?)[\s_]*[-–]?[\s_]*(?<zeit>\d{1,2}(?:[:.]\d{2})?\s*[-–]\s*\d{1,2}(?:[:.]\d{2})?|\d{4})\s*$/;
 function stem(name){
  const text=String(name??'').trim();
  const treffer=ZEIT.exec(text);
  if(!treffer)return text;
  const stamm=treffer.groups.stamm.replace(/[\s_-]+$/,'').trim();
  // Ohne tragenden Namensteil bleibt der Dienst für sich: "12-20" ist kein Stamm.
  return stamm&&/[A-Za-zÄÖÜäöüß]/.test(stamm)?stamm:text;
 }
 function group(entries){
  const familien=new Map();
  for(const entry of entries){
   const name=stem(entry.name);
   const familie=familien.get(name)||{id:'familie:'+name,name,members:[]};
   familie.members.push(entry);
   familien.set(name,familie);
  }
  return [...familien.values()];
 }
 const api={stem,group};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ServiceFamilies=api;
})(globalThis);
