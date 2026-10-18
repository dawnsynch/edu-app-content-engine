#!/usr/bin/env bash
set -Eeuo pipefail

: "${API_IMAGE:?API_IMAGE is required}"
: "${WEB_IMAGE:?WEB_IMAGE is required}"
: "${RELEASE_SHA:?RELEASE_SHA is required}"

deploy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$deploy_dir"

if [[ ! -f .env ]]; then
  echo "Deployment aborted: $deploy_dir/.env does not exist." >&2
  exit 1
fi

compose=(
  docker compose
  --env-file .env
  -f docker-compose.yml
  -f docker-compose.deploy.yml
)
release_file="$deploy_dir/.release.env"
previous_release=""

if [[ -f "$release_file" ]]; then
  previous_release="$(mktemp)"
  cp "$release_file" "$previous_release"
fi

wait_for_api() {
  local attempts="${DEPLOY_HEALTH_ATTEMPTS:-30}"
  local delay="${DEPLOY_HEALTH_DELAY_SECONDS:-2}"
  local health_url="${DEPLOY_HEALTH_URL:-http://127.0.0.1:8010/health/ready}"

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error "$health_url" >/dev/null; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

rollback() {
  if [[ -z "$previous_release" ]]; then
    echo "No previous application image references are available for rollback." >&2
    return 0
  fi

  echo "Restoring the previous application images." >&2
  # The release file contains only registry image references written by this script.
  source "$previous_release"
  export API_IMAGE WEB_IMAGE
  "${compose[@]}" up -d --no-build --remove-orphans
  wait_for_api || echo "Previous application images did not become ready." >&2
}

echo "Pulling release $RELEASE_SHA."
"${compose[@]}" pull api worker scheduler web

echo "Applying database migrations."
"${compose[@]}" run --rm --no-deps api alembic upgrade head

echo "Starting application processes."
"${compose[@]}" up -d --no-build --remove-orphans

if ! wait_for_api; then
  echo "Deployment failed its readiness check." >&2
  "${compose[@]}" logs --tail=100 api worker scheduler web >&2 || true
  rollback
  exit 1
fi

release_tmp="$(mktemp "$deploy_dir/.release.env.XXXXXX")"
printf 'API_IMAGE=%q\nWEB_IMAGE=%q\nRELEASE_SHA=%q\n' \
  "$API_IMAGE" "$WEB_IMAGE" "$RELEASE_SHA" > "$release_tmp"
chmod 600 "$release_tmp"
mv "$release_tmp" "$release_file"
[[ -n "$previous_release" ]] && rm -f "$previous_release"

echo "Release $RELEASE_SHA is ready."
