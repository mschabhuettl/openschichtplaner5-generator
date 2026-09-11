// Resolve provenance using GitHub's API; never infer a release from latest/main.
module.exports = async function releaseSource(github, repo, tag) {
  if (typeof tag !== 'string' || tag.trim() !== tag || !/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(tag)) {
    throw new Error('Expected an existing vX.Y.Z release');
  }
  const {data: release} = await github.rest.repos.getReleaseByTag({...repo, tag});
  if (release.draft) throw new Error('Draft releases are not eligible');
  const {data: commit} = await github.rest.repos.getCommit({...repo, ref: tag});
  const {data} = await github.rest.actions.listWorkflowRuns({
    ...repo, workflow_id: 'container.yml', branch: 'main', event: 'push',
    head_sha: commit.sha, status: 'success', per_page: 100
  });
  const run = data.workflow_runs.find(run =>
    run.head_sha === commit.sha && run.head_branch === 'main' &&
    run.event === 'push' && run.status === 'completed' && run.conclusion === 'success' &&
    run.head_repository?.full_name === `${repo.owner}/${repo.repo}`);
  if (!run) throw new Error('No fully successful main CI for this release commit');
  return {run, sha: commit.sha};
};
