/* Execute the existing OSP5 error extractor against synthetic HTTP JSON.
 * Function-level consumer contract only: no browser/app/authentication claim. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const frontend = path.resolve(process.argv[2]);
const ts = createRequire(path.join(frontend, 'package.json'))('typescript');
const file = path.join(frontend, 'src/api/client.ts');
const source = fs.readFileSync(file, 'utf8');
const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
const functions = ast.statements.filter(node =>
  ts.isFunctionDeclaration(node) && node.name?.text === 'extractErrorMessage');
assert.equal(functions.length, 1);
const js = ts.transpileModule(functions[0].getText(ast), {
  compilerOptions: {target: ts.ScriptTarget.ES2022},
}).outputText;
const context = vm.createContext({Response});
vm.runInContext(js, context);
const body = fs.readFileSync(0, 'utf8');
context.extractErrorMessage(new Response(body, {status: 500})).then(message => {
  assert.notEqual(message, '[object Object]');
  process.stdout.write(JSON.stringify(message));
}).catch(error => { console.error(error); process.exitCode = 1; });
