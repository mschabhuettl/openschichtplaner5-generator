const {test} = require('node:test');
const assert = require('node:assert/strict');
const resolve = require('../tools/release_source.cjs');
const repo = {owner: 'synthetic', repo: 'generator'};
const sha = 'a'.repeat(40);
const success = {id: 42, head_sha: sha, head_branch: 'main', event: 'push',
  status: 'completed', conclusion: 'success', head_repository: {full_name: 'synthetic/generator'}};
function api(runs, draft = false) {
  return {rest: {
    repos: {
      getReleaseByTag: async args => {assert.equal(args.tag, 'v1.2.3'); return {data: {draft}};},
      getCommit: async args => {assert.equal(args.ref, 'v1.2.3'); return {data: {sha}};}
    },
    actions: {listWorkflowRuns: async args => {
      assert.deepEqual(args, {...repo, workflow_id: 'container.yml', branch: 'main',
        event: 'push', head_sha: sha, status: 'success', per_page: 100});
      return {data: {workflow_runs: runs}};
    }}
  }};
}
test('selects exact successful release CI, not an unrelated latest result', async () => {
  const result = await resolve(api([{...success, head_sha: 'b'.repeat(40)}, success]), repo, 'v1.2.3');
  assert.deepEqual(result, {run: success, sha});
});
for (const [name, changes] of Object.entries({
  'wrong commit': {head_sha: 'b'.repeat(40)},
  'feature branch': {head_branch: 'feature/test'},
  'pull request': {event: 'pull_request'},
  'unfinished CI': {status: 'in_progress'},
  'failed CI': {conclusion: 'failure'},
  'foreign repository': {head_repository: {full_name: 'other/generator'}},
  'deleted repository': {head_repository: null}
})) {
  test(`rejects ${name}`, async () => {
    await assert.rejects(resolve(api([{...success, ...changes}]), repo, 'v1.2.3'), /No fully successful/);
  });
}
test('rejects absent successful CI', async () => {
  await assert.rejects(resolve(api([]), repo, 'v1.2.3'), /No fully successful/);
});
test('rejects unpublished releases', async () => {
  await assert.rejects(resolve(api([success], true), repo, 'v1.2.3'), /Draft/);
});
test('rejects invalid tags before contacting GitHub', async () => {
  await assert.rejects(resolve({}, repo, 'v1.2.3\nmain'), /Expected/);
});
test('rejects a trailing newline in a release tag', async () => {
  await assert.rejects(resolve({}, repo, 'v1.2.3\n'), /Expected/);
});
