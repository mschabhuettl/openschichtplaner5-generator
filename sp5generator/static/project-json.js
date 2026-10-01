/* Faithful project JSON, shared by transport, editor and native clones.
 * No tagged application objects, source sidecars or prototype modifications.
 * Number boxes carry only the native float brand, not original source spelling.
 */
(function(root){
 'use strict';
 const failure=message=>Object.assign(Error(message),{code:'PROJECT_JSON'});
 const invalid=()=>failure('JSON-Zahlen oder Daten können nicht sicher dargestellt werden. Der aktuelle Stand und Ihre Eingaben bleiben erhalten.');
 function assertSupported(){
  try{
   if(typeof BigInt!=='function'||typeof JSON.rawJSON!=='function'||typeof structuredClone!=='function')throw Error();
   let source;
   JSON.parse('9007199254740993',(_key,value,context)=>{source=context?.source;return value;});
   if(source!=='9007199254740993'||JSON.stringify(JSON.rawJSON(source))!==source)throw Error();
   const exact=BigInt(source),copy=structuredClone([exact,new Number(-0),new Number(1)]);
   if(copy[0]!==exact||typeof copy[1]!=='object'||typeof copy[2]!=='object'
     ||!Object.is(Number.prototype.valueOf.call(copy[1]),-0)||Number.prototype.valueOf.call(copy[2])!==1)throw Error();
  }catch{throw failure('Dieser Browser unterstützt keine sichere JSON-Zahlendarstellung. Bitte einen geeigneten Browser verwenden. Der aktuelle Stand und Ihre Eingaben bleiben erhalten.');}
 }
 function guarded(operation){
  assertSupported();
  try{return operation();}catch(error){if(error?.code==='PROJECT_JSON')throw error;throw invalid();}
 }
 function parse(text){
  return guarded(()=>{
   if(typeof text!=='string')throw invalid();
   return JSON.parse(text,(_key,value,context)=>{
    if(typeof value!=='number')return value;
    // A lexical integer may initially be Infinity in the native parser.
    if(/^-?\d+$/.test(context.source)){
     const exact=BigInt(context.source);
     return exact>=BigInt(Number.MIN_SAFE_INTEGER)&&exact<=BigInt(Number.MAX_SAFE_INTEGER)?Number(exact):exact;
    }
    if(!Number.isFinite(value))throw invalid();
    return Number.isInteger(value)?new Number(value):value;
   });
  });
 }
 // Non-mutating native brand read view; never coerce opaque strings or BigInt.
 function number(value){
  if(typeof value==='number')return value;
  if(value!==null&&typeof value==='object'){try{return Number.prototype.valueOf.call(value);}catch{}}
  return NaN;
 }
 function floatToken(value){
  if(Object.is(value,-0))return '-0.0';
  const decimal=String(value),plain=/[.e]/.test(decimal)?decimal:decimal+'.0';
  const exponent=value.toExponential().replace('e+','e');
  return exponent.length<plain.length?exponent:plain;
 }
 // Build a transient wire tree instead of invoking user toJSON/getters. Only
 // ancestors count as cycles: repeated acyclic references are ordinary JSON.
 function wire(value,ancestors){
  if(value===null||typeof value==='string'||typeof value==='boolean')return value;
  if(typeof value==='bigint')return JSON.rawJSON(value.toString());
  if(typeof value==='number'){
   if(!Number.isFinite(value)||Number.isInteger(value)&&!Number.isSafeInteger(value))throw invalid();
   return !Number.isInteger(value)||Object.is(value,-0)?JSON.rawJSON(floatToken(value)):value;
  }
  if(typeof value!=='object'||ancestors.has(value)||JSON.isRawJSON(value))throw invalid();
  const n=number(value),keys=Reflect.ownKeys(value);
  if(!Number.isNaN(n)){
   if(!Number.isFinite(n)||keys.length)throw invalid();
   return JSON.rawJSON(floatToken(n));
  }
  const array=Array.isArray(value),proto=Object.getPrototypeOf(value);
  // Permit plain records from another realm too (e.g. browser test harnesses),
  // but never class instances whose clone/JSON contracts would lose information.
  if(!array&&proto!==null){
   const constructor=Object.getOwnPropertyDescriptor(proto,'constructor');
   if(Object.getPrototypeOf(proto)!==null||typeof constructor?.value!=='function'
     ||Function.prototype.toString.call(constructor.value)!==Function.prototype.toString.call(Object))throw invalid();
  }
  if(array&&keys.length!==value.length+1)throw invalid(); // holes and extra keys
  const output=array?[]:Object.create(null);
  ancestors.add(value);
  try{
   for(const key of keys){
    if(array&&key==='length')continue;
    const descriptor=Object.getOwnPropertyDescriptor(value,key);
    if(typeof key!=='string'||!descriptor.enumerable||!Object.hasOwn(descriptor,'value'))throw invalid();
    if(array&&(!/^(0|[1-9]\d*)$/.test(key)||Number(key)>=value.length))throw invalid();
    output[key]=wire(descriptor.value,ancestors);
   }
  }finally{ancestors.delete(value);}
  return output;
 }
 function stringify(value,replacer=null,space){
  return guarded(()=>{
   if(replacer!==null||space!==undefined&&space!==2)throw invalid();
   return JSON.stringify(wire(value,new Set()),null,space);
  });
 }
 function clone(value){
  // Admission precedes structuredClone: it otherwise silently drops properties
  // of wrappers/classes. The returned state contains no rawJSON wire wrappers.
  stringify(value);
  return guarded(()=>structuredClone(value));
 }
 const api={parse,stringify,number,clone,assertSupported};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ProjectJSON=api;
})(globalThis);
