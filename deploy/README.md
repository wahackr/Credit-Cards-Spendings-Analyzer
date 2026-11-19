# Deployment

Three pipelines, on purpose different machines and different Docker daemons:

| Workflow | Trigger | Docker context | Runs on | Does |
| --- | --- | --- | --- | --- |
| `.github/workflows/test.yml` | push to `development`, any PR | — | GitHub-hosted `ubuntu-latest` | `node --test` on the deploy tooling, `pytest`, `flake8`, image build |
| `.github/workflows/deploy-development.yml` | push to `development` (paths-filtered), `workflow_dispatch` | `dev` | your self-hosted runner | validate config → `compose build` → `compose up -d --wait` |
| `.github/workflows/deploy-production.yml` | push to `master` (paths-filtered), `workflow_dispatch` | `prod` | your self-hosted runner | the same three stages against the prod daemon |

CI never runs on the self-hosted runner: a PR from a fork would execute untrusted code on
the same machine that holds the LLM keys and the deployed stack.

Each deploy job pins its Docker context in the workflow file (`DOCKER_CONTEXT: dev` /
`prod`), so nothing selects a daemon by inference and no GitHub variable can retarget a
deploy from the dashboard. `deploy.sh` honours exactly what it is handed.

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

### 2. Create the `dev` and `prod` environments and fill in their settings

**Settings → Environments → New environment**, then add the variables and secrets. Each
environment carries its own copy: `dev` is read by the `development` job, `prod` by the
`master` job, and neither inherits the other's keys. (An environment is also created
implicitly on the first deploy run — but the values have to exist before that run can get
past validation.) For `prod`, also add a **required reviewer** under *Deployment
protection rules*: it is the only gate between a merge to `master` and a public deploy.

Defaults below are the workflow's fallbacks; a GitHub variable of the same name overrides it.

| Name | Kind | Default (dev / prod) | Notes |
| --- | --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | var | `credit-card-analyzer-dev` / `-prod` | Compose project, container names, image tag |
| `TZ` | var | `Asia/Hong_Kong` | |
| `APP_BIND_ADDRESS` | var | `127.0.0.1` / `0.0.0.0` | See the bind rules below |
| `APP_HOST_PORT` | var | `8010` / `8000` | `8000` is Portainer's on this host, hence dev's `8010` |
| `APP_ALLOW_LAN_BIND` | var | `false` / `true` | Pre-approved in prod so its `0.0.0.0` bind validates |
| `APP_MEM_LIMIT` | var | `2g` | Container memory ceiling |
| `LLM_PROVIDER` | var | `openai-compatible` | The only supported value; `gemini` fails validation |
| `OPENAI_BASE_URL` | var | — | Required |
| `OPENAI_MODEL` | var | — | Required |
| `OPENAI_API_KEY` | **secret** | `not-required` | Empty is rejected by the app; use `not-required` |
| `OPENAI_THINKING` | var | — | Set `false` for Qwen-on-Ollama style servers |
| `OPENAI_MAX_OUTPUT_TOKENS` | var | — | |
| `MAX_CONCURRENT_STATEMENTS` | var | `2` | Each statement buffers up to 25 MB |
| `LLM_DEBUG` | var | `false` | See the log warning below |

### 3. Make sure the runner's account can see the `dev` and `prod` contexts

The deploy jobs pass `--context dev` and `--context prod`, so those two names must exist for
the account that runs the runner. Contexts are per-user (`~/.docker/contexts/` and
`~/.docker/config.json`), so a runner running as a different user — or a rootless setup —
sees a different set than your login shell:

```bash
docker context ls                # as the user that runs run.sh / the runner service
docker --context prod info       # proves that endpoint is reachable and authorised
```

A missing or misspelled context fails at `validate` with `context "prod": context not
found`, before any image is built; `validate` also prints the context it selected, so every
run states which daemon it targeted. `APP_BIND_ADDRESS` and `APP_HOST_PORT` apply to the
**daemon** that context selects, not to the runner's machine — on a remote context, a
`127.0.0.1` bind means that host's loopback, reachable through a reverse proxy or an SSH
tunnel there.

### 4. Merge

Push to `development` for the `dev` stack, to `master` for the `prod` stack. Note that
`master` is currently far behind `development`, so the first `master` merge is a large one —
and the prod job only exists once this branch lands there, since a workflow must be present
on the branch that is pushed.

`deploy.sh validate` checks that the selected Docker daemon is reachable before building.
It also checks for `CHANGE_ME` placeholders, a missing provider credential, a malformed port,
or a routable bind without `APP_ALLOW_LAN_BIND` (prod sets that to `true` in the workflow).
Then build, then `up -d --no-build --wait --wait-timeout 180`.

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
- **Prod is published on `0.0.0.0:8000` by default, with that gate already approved** in
  `deploy-production.yml`. Anyone who can route to the prod daemon's host can upload
  statements, spend the quota, and try to steer `base_url`. Put a reverse proxy with access
  control in front of it, or override `APP_BIND_ADDRESS` for that environment until there is
  authentication.
- **`LLM_DEBUG=true` prints raw card data** — every statement's extracted text and the model's
  reply — to the container log, and `deploy.sh` echoes recent container logs into the Actions
  log when a deploy fails. Turn it on only while debugging, and only on a private repo.
- The Actions log itself is only visible to people with repo access; still treat it as
  containing whatever the container printed.

## Manual deploy (same files, no GitHub)

```bash
cp deploy/.env.example deploy/.env     # then edit; deploy/.env is git-ignored
(
  set -a
  source deploy/.env
  set +a
  export DOCKER_CONTEXT=dev             # prod for the production stack; unset means "default"
  bash deploy/tools/deploy.sh validate &&
    bash deploy/tools/deploy.sh build &&
    bash deploy/tools/deploy.sh deploy
)
```

`deploy.sh` passes the chosen context to Docker and uses `--env-file /dev/null` for Compose.
For direct Compose commands, use the same context and project settings as the deployment.
For a GitHub deployment, set `COMPOSE_PROJECT_NAME` in `deploy/.env` to the environment's
project name if you changed it.

```bash
docker_context=dev                    # prod for the production stack
compose=(docker --context "$docker_context" compose --env-file deploy/.env -f deploy/compose.yaml)
"${compose[@]}" up --build
"${compose[@]}" logs -f
```

Escapes when a rollout misbehaves:

```bash
"${compose[@]}" ps -a          # health, restart count
"${compose[@]}" logs --tail 100
"${compose[@]}" down           # stop the stack
```

## Things that will surprise you

- **A green deploy does not mean the LLM works.** `/healthz` returns `{"status":"ok"}` with no
  provider configured, so the healthcheck can never catch a bad key. That is why `deploy.sh`
  checks the provider's credential before building anything. To confirm the app can actually
  analyze: `curl -s "http://127.0.0.1:<APP_HOST_PORT>/api/config"` — `8010` on dev, `8000` on
  prod, and run it where the selected daemon runs — `providers` should list the one you
  configured, `errors` should be empty.
- **Rolling the container clears in-flight jobs.** Job state and uploads are in memory only.
- **Superseded pushes are skipped, not stacked.** `deploy/tools/deployment-current.cjs` compares
  the run's SHA to its branch's head (`development` or `master` — each workflow passes
  `branch:` explicitly) and exits the job early if newer relevant code already landed
  (documentation-only commits still deploy). One runner, no five-build pile-up. If you change
  the `paths:` filter in a workflow, change the list in that file too — they must agree.
- **Python drift:** `.python-version` says 3.13, `deploy/docker/analyzer.Dockerfile` builds on
  `python:3.12-slim`, and CI tests 3.12 to match what ships. Reconcile them in one commit.
- **The first Compose run under the new `name:` is a new project.** A stack you started earlier
  from the repo root keeps its old auto-derived project name and still holds its port; stop it
  with `docker compose ls` to find the name, then `docker compose -p <name> down`.
- **This app writes nothing to disk** (no volumes, no database). Nothing to back up, nothing to
  migrate — and nothing survives a redeploy either.

## Follow-ups worth their own issues

- No auth on `/api/*` (everything above is mitigation, not the fix) — prod's `0.0.0.0` bind
  makes this the one worth filing first.
- Non-root user inside the image, kept separate from this move so the first deploy is a clean diff.
- No rollback target: every build is tagged `<project>-analyzer:latest`, so reverting a prod
  deploy means rebuilding the older commit rather than re-pointing a saved tag.
- `master` trails `development` by a wide margin, so the first push there is a large merge.
