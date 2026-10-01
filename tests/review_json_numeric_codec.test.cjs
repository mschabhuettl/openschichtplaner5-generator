'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const modulePath=path.join(__dirname,'../sp5generator/static/project-json.js');
// Before the module exists, exercise the actual pre-repair JSON representation,
// so RED is a semantic assertion failure, never a missing-import failure.
const codec=fs.existsSync(modulePath)?require(modulePath):JSON;
for(const token of ['1.0000000000000001e18','-1.0000000000000001e18','0.0','-0.0','1.0','1e20','1e30','0.1','1.5','1e-6','1e-5','5e-324','-5e-324','1.7976931348623157e308','1e-999','-1e-999','1.00000000000000001','9007199254740993.0'])test('T03 float '+token,()=>{
 const value=codec.parse(token);
 oracle([{source:token,output:codec.stringify(value)},{source:token,output:codec.stringify(structuredClone(value))}]);
});
test('T04 strict-int request fields retain their float category',()=>{
 const source='{"employees":[{"contractual_weekly_minutes":60.0}],"metadata":{"history_approvals":{"minimum_days":2.0}}}';
 oracle([{source,output:codec.stringify(codec.parse(source))}]);
});

const vm=require('node:vm');
for(const [name,value] of [
 ['unsafe primitive',9007199254740992],['nonfinite',Infinity],['NaN',NaN],['undefined',undefined],['function',()=>0],['symbol',Symbol('x')],['date',new Date(0)],['map',new Map()],['set',new Set()],['boxed string',new String('x')],['sparse',Array(1)],['raw wrapper',JSON.rawJSON('1')],['custom toJSON',{toJSON(){return 1;}}],['number properties',Object.assign(new Number(1),{custom:2})],['symbol key',{[Symbol('x')]:1}],['hidden',Object.defineProperty({},'hidden',{value:1})],['getter',Object.defineProperty({},'x',{enumerable:true,get(){throw Error('do not execute');}})]
])test('T09 rejects unsupported '+name,()=>{
 assert.throws(()=>codec.stringify({value}),error=>error.code==='PROJECT_JSON'&&error.message.length<300);
});
for(const token of ['1e400','-1e400','NaN','Infinity'])test('T09 rejects token '+token,()=>{
 assert.throws(()=>codec.parse(token),error=>error.code==='PROJECT_JSON'&&error.message.length<300);
});
for(const capability of ['source','rawJSON','BigInt','clone','box-clone'])test('T09 capability '+capability+' fails closed',()=>{
 const context=vm.createContext({structuredClone});
 if(capability==='source')vm.runInContext('const original=JSON.parse;JSON.parse=(text,reviver)=>original(text,reviver&&((k,v)=>reviver(k,v)));',context);
 if(capability==='rawJSON')vm.runInContext('JSON.rawJSON=undefined',context);
 if(capability==='BigInt')vm.runInContext('BigInt=undefined',context);
 if(capability==='clone')context.structuredClone=undefined;
 if(capability==='box-clone')context.structuredClone=()=>[0,0];
 vm.runInContext(fs.readFileSync(modulePath,'utf8'),context);
 for(const operation of ['ProjectJSON.parse("1")','ProjectJSON.stringify({a:1})'])assert.throws(()=>vm.runInContext(operation,context),error=>error.code==='PROJECT_JSON'&&/Browser/.test(error.message));
});
test('T09 cycles reject; repeated acyclic references are not cycles',()=>{
 const same={n:codec.parse('1.0')};const graph={a:same,b:same};oracle([{source:'{"a":{"n":1.0},"b":{"n":1.0}}',output:codec.stringify(graph)}]);
 same.self=same;assert.throws(()=>codec.stringify(graph),error=>error.code==='PROJECT_JSON');
});
test('T05 marker shapes, escaped keys and clone edits have no hidden source reinjection',()=>{
 const raw='{"__proto__":{"constructor":1.0},"rawJSON":"1e400","$number":[9007199254740993,-0.0],"a/~\\u0022":2.0}';
 const value=structuredClone(codec.parse(raw));value.renamed=value.$number.reverse();delete value.$number;delete value.__proto__;value.renamed.push(codec.parse('1e20'));
 oracle([{source:'{"rawJSON":"1e400","a/~\\u0022":2.0,"renamed":[-0.0,9007199254740993,1e20]}',output:codec.stringify(value)}]);
 assert(Number.isNaN(codec.number({valueOf:()=>1})));assert(Number.isNaN(codec.number('1')));assert(Number.isNaN(codec.number(BigInt('1'))));
});


test('T10 depth/resource failure is bounded; ordinary depth and 4000-digit integers remain supported',()=>{
 const shallow='['.repeat(100)+'1.0'+']'.repeat(100);oracle([{source:shallow,output:codec.stringify(codec.parse(shallow))}]);
 const deep='['.repeat(30000)+'0'+']'.repeat(30000);assert.throws(()=>codec.parse(deep),error=>error.code==='PROJECT_JSON'&&error.message.length<300);
 const integer='9'.repeat(4000);assert.equal(codec.stringify(codec.parse(integer)),integer);
});
test('T10 Python-generated binary64 corpus keeps type/value and does not expand canonical numeric tokens',()=>{
 const p=spawnSync(process.env.WEB_TEST_PYTHON||'python',['-c',
  'import json,random,struct,math; r=random.Random(6); values=[1.0,-0.0,1e20,1e-6,1e-5]; values += [struct.unpack(">d",r.getrandbits(64).to_bytes(8,"big"))[0] for _ in range(2000)]; print(json.dumps([json.dumps(n) for n in values if math.isfinite(n)]))'
 ],{encoding:'utf8',timeout:15000});assert.equal(p.status,0,p.stderr);
 const cases=JSON.parse(p.stdout).map(source=>({source,output:codec.stringify(codec.parse(source))}));oracle(cases);
 for(const item of cases)assert(item.output.length<=item.source.length,JSON.stringify(item));
});

function oracle(cases){
 const p=spawnSync(process.env.WEB_TEST_PYTHON||'python',[path.join(__dirname,'json_numeric_oracle.py')],{input:JSON.stringify(cases),encoding:'utf8',timeout:15000});
 assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout);
}
for(const token of ['0','-1','9007199254740991','9007199254740992','9007199254740993','9007199254740994','-9007199254740993','1000000000000000128','1'+'0'.repeat(400),'-0'])test('T02 integer '+token.slice(0,35),()=>{
 const value=codec.parse(token);
 oracle([{source:token,output:codec.stringify(value)},{source:token,output:codec.stringify(structuredClone(value))}]);
 if(token==='0'||token==='-1'||token==='9007199254740991')assert.equal(typeof value,'number');
});
