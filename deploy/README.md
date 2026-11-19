# Deployment

Two pipelines, on purpose different machines:

| Workflow | Trigger | Runs on | Does |
| --- | --- | --- | --- |
| `.github/workflows/test.yml` | push to `development`, any PR | GitHub-hosted `ubuntu-latest` | `node --test` on the deploy tooling, `pytest`, `flake8`, image build |
| `.github/workflows/deploy-development.yml` | push to `development` (paths-filtered), `workflow_dispatch` | your self-hosted runner | validate config → `compose build` → `compose up -d --wait` |

CI never runs on the self-hosted runner: a PR from a fork would execute untrusted code on
the same machine that holds the LLM keys and the deployed stack.

## One-time setup

### 1. Register a runner for *this* repository

Self-hosted runners registered to one repository do not serve another. This machine already
has one (`~/GitHub-Runners/actions-runner` builds `Quickbook-Invoice-Status`); it will not
pick up jobs from this repo, and `gh api repos/wahackr/Credit-Cards-Spendings-Analyzer/actions/runners`
currently reports none here. A first run therefore sits at *"waiting for a runner"* until you
register one — that is expected, not a hang.

GitHub → this repo → **Settings → Actions → Runners → New self-hosted runner**, pick Linux,
and copy the download/expose commands it shows (they carry the current runner version). The
shape, using a directory per runner so the existing one is untouched:

```bash
mkdir -p ~/GitHub-Runners/credit-card-analyzer && cd ~/GitHub-Runners/credit-card-analyzer
# curl + tar the runner tarball from the version pinned on that Settings page
./config.sh --url https://github.com/wahackr/Credit-Cards-Spendings-Analyzer --unattended
./run.sh            # foreground; Ctrl-C stops taking jobs
```

Do not add custom labels — the deploy job asks for `runs-on: self-hosted`, and a runner that
only carries extra labels will not match it. `--unattended` without `--labels` registers the
default `self-hosted` label set.

A hand-run `./run.sh` dies on reboot, on logout, and when the runner self-updates. To keep it
up, use the bundled service wrapper (`./svc.sh install && ./svc.sh start`, systemd).

### 2. Create the `dev` environment and fill in its settings

**Settings → Environments → New environment → `dev`**, then add the variables and secrets.
(The environment is also created implicitly on the first deploy run — but the values have to
exist before that run can get past validation.)

| Name | Kind | Default if unset | Notes |
| --- | --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | var | `credit-card-analyzer-dev` | Compose project, container names, image tag |
| `TZ` | var | `Asia/Hong_Kong` | |
| `APP_BIND_ADDRESS` | var | `127.0.0.1` | See the bind rules below |
| `APP_HOST_PORT` | var | `8010` | `8000` is already taken on this host by Portainer |
| `APP_ALLOW_LAN_BIND` | var | `false` | Must be `true` for any non-loopback bind |
| `APP_MEM_LIMIT` | var | `2g` | Container memory ceiling |
| `LLM_PROVIDER` | var | `openai-compatible` | The only supported value; `gemini` fails validation |
| `OPENAI_BASE_URL` | var | — | Required |
| `OPENAI_MODEL` | var | — | Required |
| `OPENAI_API_KEY` | **secret** | `not-required` | Empty is rejected by the app; use `not-required` |
| `OPENAI_THINKING` | var | — | Set `false` for Qwen-on-Ollama style servers |
| `OPENAI_MAX_OUTPUT_TOKENS` | var | — | |
| `MAX_CONCURRENT_STATEMENTS` | var | `2` | Each statement buffers up to 25 MB |
| `LLM_DEBUG` | var | `false` | See the log warning below |

Only the names in that table reach the deploy step: an unset variable is invisible to
`deploy.sh`, so a typo in a GitHub variable name shows up as a missing key, not a wrong value.

### 3. Merge to `development`

`deploy.sh validate` fails fast on `CHANGE_ME` placeholders, a missing provider credential, a
malformed port, or a routable bind without `APP_ALLOW_LAN_BIND`. Then build, then
`up -d --no-build --wait --wait-timeout 180`.

What that catches is a *missing* key, not a *wrong* one: the app starts and passes its
healthcheck regardless of the credential's validity, so a typo'd key still deploys green and
only shows up when an analysis fails. Check it with the `/api/config` call below, then upload a
real statement once. If a container genuinely fails to start, the readiness wait fails and the
run shows its last 40 log lines.

## Security notes — read these before changing a default

- **The app has no authentication at all.** `/api/jobs` accepts an unauthenticated 25 MB PDF
  upload and burns provider quota; the job API also takes a caller-supplied `base_url`, so an
  attacker can point your server at their own LLM endpoint. Binding the loopback address keeps
  that to your machine. A non-loopback `APP_BIND_ADDRESS` fails validation until
  `APP_ALLOW_LAN_BIND=true` says you meant it.
- **`LLM_DEBUG=true` prints raw card data** — every statement's extracted text and the model's
  reply — to the container log, and `deploy.sh` echoes recent container logs into the Actions
  log when a deploy fails. Turn it on only while debugging, and only on a private repo.
- The Actions log itself is only visible to people with repo access; still treat it as
  containing whatever the container printed.

## Manual deploy (same files, no GitHub)

```bash
cp deploy/.env.example deploy/.env     # then edit; deploy/.env is git-ignored
bash deploy/tools/deploy.sh validate
bash deploy/tools/deploy.sh build
env $(grep -v '^#' deploy/.env | xargs) bash deploy/tools/deploy.sh deploy
```

`deploy.sh` always calls Compose as `docker compose --env-file /dev/null -f deploy/compose.yaml`
with `DOCKER_HOST` pinned to the local socket and any inherited `DOCKER_CONTEXT`/TLS variables
cleared — so a stale `.env` or a stray Docker context on the runner can never change what gets
deployed. For an interactive run, be explicit instead:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build
docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f
```

Escapes when a rollout misbehaves:

```bash
docker compose -f deploy/compose.yaml ps -a          # health, restart count
docker compose -f deploy/compose.yaml logs --tail 100
docker compose -f deploy/compose.yaml down           # stop the stack
```

Those resolve the project name from the compose file's default; export
`COMPOSE_PROJECT_NAME` first if the deployment runs under a different one.

## Things that will surprise you

- **A green deploy does not mean the LLM works.** `/healthz` returns `{"status":"ok"}` with no
  provider configured, so the healthcheck can never catch a bad key. That is why `deploy.sh`
  checks the provider's credential before building anything. To confirm the app can actually
  analyze: `curl -s "http://127.0.0.1:${APP_HOST_PORT:-8010}/api/config"` — `providers` should
  list the one you configured, `errors` should be empty.
- **Rolling the container clears in-flight jobs.** Job state and uploads are in memory only.
- **Superseded pushes are skipped, not stacked.** `deploy/tools/deployment-current.cjs` compares
  the run's SHA to `development`'s head and exits the job early if newer relevant code already
  landed (documentation-only commits still deploy). One runner, no five-build pile-up. If you
  change the `paths:` filter in the workflow, change the list in that file too — they must agree.
- **Python drift:** `.python-version` says 3.13, `deploy/docker/analyzer.Dockerfile` builds on
  `python:3.12-slim`, and CI tests 3.12 to match what ships. Reconcile them in one commit.
- **The first Compose run under the new `name:` is a new project.** A stack you started earlier
  from the repo root keeps its old auto-derived project name and still holds its port; stop it
  with `docker compose ls` to find the name, then `docker compose -p <name> down`.
- **This app writes nothing to disk** (no volumes, no database). Nothing to back up, nothing to
  migrate — and nothing survives a redeploy either.

## Follow-ups worth their own issues

- No auth on `/api/*` (`deploy/README.md` above is the mitigation, not the fix).
- Non-root user inside the image, kept separate from this move so the first deploy is a clean diff.
- A `master`/production twin of the deploy job once this repo has one.
