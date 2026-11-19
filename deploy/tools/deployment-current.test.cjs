const test = require('node:test');
const assert = require('node:assert/strict');

const isCurrent = require('./deployment-current.cjs');

const context = {
  sha: 'local-sha',
  repo: { owner: 'wahackr', repo: 'Credit-Cards-Spendings-Analyzer' },
};

// No default for `files`: passing undefined must reach the module as a missing array.
function client({ headSha, status = 'ahead', files }) {
  const calls = { refs: [], comparisons: [] };
  return {
    calls,
    rest: {
      git: {
        getRef: async ({ owner, repo, ref }) => {
          calls.refs.push({ owner, repo, ref });
          return { data: { object: { sha: headSha } } };
        },
      },
      repos: {
        compareCommitsWithBasehead: async ({ basehead }) => {
          calls.comparisons.push(basehead);
          return { data: { status, files } };
        },
      },
    },
  };
}

test('deploys the commit that is already the branch head', async () => {
  const github = client({ headSha: 'local-sha' });
  assert.equal(await isCurrent({ github, context }), true);
  assert.deepEqual(github.calls.comparisons, []);
});

test('compares the run against the configured branch head', async () => {
  const github = client({ headSha: 'newer-sha', files: [{ filename: 'README.md' }] });
  assert.equal(await isCurrent({ github, context }), true);
  assert.deepEqual(github.calls.refs, [
    { owner: 'wahackr', repo: 'Credit-Cards-Spendings-Analyzer', ref: 'heads/development' },
  ]);
  assert.deepEqual(github.calls.comparisons, ['local-sha...newer-sha']);
});

test('permits newer commits that only changed documentation', async () => {
  const files = [{ filename: 'README.md' }, { filename: 'deploy/README.md', previous_filename: 'deploy/README.md' }];
  const github = client({ headSha: 'newer-sha', files });
  assert.equal(await isCurrent({ github, context }), false, 'deploy/README.md is a deployment file');

  const docs = client({ headSha: 'newer-sha', files: [{ filename: 'README.md' }] });
  assert.equal(await isCurrent({ github: docs, context }), true);
});

test('skips when a newer commit changed application code', async () => {
  const github = client({ headSha: 'newer-sha', files: [{ filename: 'src/libs/tools/statement_reader.py' }] });
  assert.equal(await isCurrent({ github, context }), false);
});

test('skips when a newer commit changed dependencies or the image', async () => {
  for (const filename of ['pyproject.toml', 'uv.lock', 'deploy/docker/analyzer.Dockerfile', 'deploy/compose.yaml']) {
    const github = client({ headSha: 'newer-sha', files: [{ filename }] });
    assert.equal(await isCurrent({ github, context }), false, filename);
  }
});

test('skips when a relevant file was renamed away', async () => {
  const github = client({
    headSha: 'newer-sha',
    files: [{ filename: 'infra/compose.yaml', previous_filename: 'deploy/compose.yaml' }],
  });
  assert.equal(await isCurrent({ github, context }), false);
});

test('skips when the branch is not a simple fast-forward from the run', async () => {
  for (const status of ['diverged', 'behind', 'identical']) {
    const github = client({ headSha: 'newer-sha', status, files: [{ filename: 'README.md' }] });
    assert.equal(await isCurrent({ github, context }), false, status);
  }
});

test('skips when the comparison cannot be trusted', async () => {
  // A full first page means page 2 might hold relevant files, and the module only reads one.
  for (const length of [100, 300, 0]) {
    const full = client({
      headSha: 'newer-sha',
      files: Array.from({ length }, (_value, index) => ({ filename: `docs/page-${index}.md` })),
    });
    assert.equal(await isCurrent({ github: full, context }), false, `${length} files`);
  }

  const missing = client({ headSha: 'newer-sha', files: undefined });
  assert.equal(await isCurrent({ github: missing, context }), false);

  // Just under the page size is still a complete answer, so it must not be declined.
  const almost = client({
    headSha: 'newer-sha',
    files: Array.from({ length: 99 }, (_value, index) => ({ filename: `docs/page-${index}.md` })),
  });
  assert.equal(await isCurrent({ github: almost, context }), true);
});

test('honours an explicit branch override', async () => {
  const github = client({ headSha: 'newer-sha', files: [{ filename: 'README.md' }] });
  assert.equal(await isCurrent({ github, context, branch: 'release' }), true);
  assert.equal(github.calls.refs[0].ref, 'heads/release');
});
