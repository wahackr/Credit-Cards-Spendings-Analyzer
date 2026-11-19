const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { mkdtempSync, rmSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const test = require('node:test');

function deployWithStub(t, stage, context, failRollout = false) {
  const bin = mkdtempSync(join(tmpdir(), 'deploy-docker-'));
  t.after(() => rmSync(bin, { recursive: true, force: true }));
  writeFileSync(join(bin, 'docker'), `#!/usr/bin/env bash
set -eu
if [[ -v DOCKER_HOST || -v DOCKER_TLS || -v DOCKER_TLS_VERIFY || -v DOCKER_CERT_PATH ]]; then
  echo 'Unexpected inherited Docker connection settings' >&2
  exit 1
fi
echo "$*" >&2
if [[ "$FAIL_ROLLOUT" == true && " $* " == *" up "* ]]; then
  exit 1
fi
`, { mode: 0o755 });

  const result = spawnSync('bash', [join(__dirname, 'deploy.sh'), stage], {
    encoding: 'utf8',
    env: {
      PATH: `${bin}:${process.env.PATH}`,
      COMPOSE_PROJECT_NAME: 'context-test',
      LLM_PROVIDER: 'openai-compatible',
      OPENAI_BASE_URL: 'http://stub.example:8080/v1',
      OPENAI_MODEL: 'test-model',
      DOCKER_CONTEXT: context,
      DOCKER_HOST: 'tcp://inherited.example:2376',
      DOCKER_TLS: '1',
      DOCKER_TLS_VERIFY: '1',
      DOCKER_CERT_PATH: '/inherited',
      FAIL_ROLLOUT: String(failRollout),
    },
  });
  assert.ifError(result.error);
  return result;
}

const compose = 'compose --env-file /dev/null -f deploy/compose.yaml';

test('validation and build use the configured context', (t) => {
  const validation = deployWithStub(t, 'validate', 'dev-engine');
  assert.equal(validation.status, 0, validation.stderr);
  assert.deepEqual(validation.stderr.trim().split('\n'), [
    '--context dev-engine info',
    '--context dev-engine compose version',
    `--context dev-engine ${compose} config --quiet`,
  ]);

  const build = deployWithStub(t, 'build', 'dev-engine');
  assert.equal(build.status, 0, build.stderr);
  assert.equal(build.stderr.trim(), `--context dev-engine ${compose} build --pull`);
});

test('rollout diagnostics use the same context after a failed rollout', (t) => {
  const rollout = deployWithStub(t, 'deploy', 'dev-engine', true);
  assert.equal(rollout.status, 1);
  assert.deepEqual(rollout.stderr.trim().split('\n'), [
    `--context dev-engine ${compose} up -d --no-build --wait --wait-timeout 180`,
    `--context dev-engine ${compose} logs --no-color --tail 40`,
    `--context dev-engine ${compose} ps -a`,
    'Deployment failed or application readiness timed out.',
  ]);
});

test('an empty context uses the local default', (t) => {
  const build = deployWithStub(t, 'build', '');
  assert.equal(build.status, 0, build.stderr);
  assert.equal(build.stderr.trim(), `--context default ${compose} build --pull`);
});
