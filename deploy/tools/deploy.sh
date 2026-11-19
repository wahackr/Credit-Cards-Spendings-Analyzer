#!/usr/bin/env bash
# Build and roll out the analyzer Compose stack using the configured Docker context.
# Configuration comes only from GitHub environment variables and secrets; local
# .env files are ignored so a persistent runner can never deploy a stale one.
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."

stage=${1:-}
case "$stage" in validate|build|deploy) ;; *) echo 'Usage: deploy.sh validate|build|deploy' >&2; exit 1 ;; esac

# GitHub accepts empty variables, so unfilled placeholders must fail before any image is built.
for key in COMPOSE_PROJECT_NAME TZ APP_BIND_ADDRESS APP_HOST_PORT APP_MEM_LIMIT \
  APP_ALLOW_LAN_BIND LLM_PROVIDER OPENAI_BASE_URL OPENAI_MODEL \
  OPENAI_API_KEY OPENAI_THINKING OPENAI_MAX_OUTPUT_TOKENS MAX_CONCURRENT_STATEMENTS LLM_DEBUG; do
  if [[ "${!key:-}" == CHANGE_ME ]]; then
    echo "Replace the GitHub deployment placeholder: $key" >&2
    exit 1
  fi
done

for key in COMPOSE_PROJECT_NAME LLM_PROVIDER; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing GitHub deployment configuration: $key" >&2
    exit 1
  fi
done

if ! [[ "$COMPOSE_PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  echo 'Invalid COMPOSE_PROJECT_NAME: use lowercase letters, digits, "_" or "-"' >&2
  exit 1
fi

# The provider decides which credentials must exist; a missing key surfaces here
# rather than as a readiness timeout after the image build.
case "$LLM_PROVIDER" in
  gemini)
    # Fail with the reason rather than the generic message below, so a stale GitHub
    # variable points at the fix instead of looking like a typo.
    echo 'LLM_PROVIDER=gemini is no longer supported: the Gemini provider was removed.' >&2
    echo 'Set LLM_PROVIDER=openai-compatible and provide OPENAI_BASE_URL and OPENAI_MODEL.' >&2
    exit 1
    ;;
  openai-compatible)
    for key in OPENAI_BASE_URL OPENAI_MODEL; do
      if [[ -z "${!key:-}" ]]; then
        echo "Missing GitHub deployment configuration: $key (required for LLM_PROVIDER=openai-compatible)" >&2
        exit 1
      fi
    done
    if ! [[ "$OPENAI_BASE_URL" =~ ^https?://[^[:space:]/]+ ]]; then
      echo "Invalid OPENAI_BASE_URL: expected an absolute http:// or https:// URL" >&2
      exit 1
    fi
    ;;
  *)
    echo 'LLM_PROVIDER must be openai-compatible' >&2
    exit 1
    ;;
esac

# Compose needs a numeric address: Docker rejects a hostname here, so fail with a reason
# instead of "invalid IP address: localhost" from the deploy stage. IPv6 is not supported.
bind_address=${APP_BIND_ADDRESS:-127.0.0.1}
if ! [[ "$bind_address" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "Invalid APP_BIND_ADDRESS: $bind_address (expected a numeric address such as 127.0.0.1)" >&2
  exit 1
fi
# One GitHub variable must not silently expose an unauthenticated upload endpoint to the
# whole network, so a routable bind needs an explicit opt-in.
if [[ "$bind_address" != 127.* ]] && [[ "${APP_ALLOW_LAN_BIND:-}" != true ]]; then
  echo "APP_BIND_ADDRESS=$bind_address would publish an unauthenticated app beyond this host." >&2
  echo "Set APP_ALLOW_LAN_BIND=true in the GitHub environment to accept that." >&2
  exit 1
fi
value=${APP_HOST_PORT:-8010}
if ! [[ "$value" =~ ^[0-9]{1,5}$ ]] || ! (( 10#$value >= 1 && 10#$value <= 65535 )); then
  echo "Invalid APP_HOST_PORT: $value" >&2
  exit 1
fi
for key in MAX_CONCURRENT_STATEMENTS OPENAI_MAX_OUTPUT_TOKENS; do
  if [[ -n "${!key:-}" ]] && ! [[ "${!key}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid $key: expected a positive integer" >&2
    exit 1
  fi
done

# Select the same context for validation, build, rollout, and diagnostics.
# Never use an untracked .env or an inherited profile on a persistent runner.
export COMPOSE_PROFILES=''
unset DOCKER_HOST DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker_context=${DOCKER_CONTEXT:-default}
docker_cli=(docker --context "$docker_context")
compose=("${docker_cli[@]}" compose --env-file /dev/null -f deploy/compose.yaml)

case "$stage" in
  validate)
    printf 'Validating Docker context %s\n' "$docker_context"
    "${docker_cli[@]}" info >/dev/null
    "${docker_cli[@]}" compose version
    "${compose[@]}" config --quiet
    ;;
  build)
    "${compose[@]}" build --pull
    ;;
  deploy)
    # Compose waits for the container healthcheck, so an unhealthy rollout fails the run.
    if ! "${compose[@]}" up -d --no-build --wait --wait-timeout 180; then
      # Detached up hides service output; dump logs so provider and startup errors show the
      # cause. Kept short because these logs land in the public Actions log, and a container
      # running with LLM_DEBUG=true prints the statement text it was given.
      "${compose[@]}" logs --no-color --tail 40 || true
      "${compose[@]}" ps -a
      echo 'Deployment failed or application readiness timed out.' >&2
      exit 1
    fi
    "${compose[@]}" ps -a
    ;;
esac
