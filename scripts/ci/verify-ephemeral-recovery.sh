#!/usr/bin/env bash
# Execute ONLY inside the disposable GitHub Actions Compose environment.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true || "${COMPOSE_PROJECT_NAME:-}" != precis-ci-* ]]; then
  echo "::error::Refusing recovery drill outside ephemeral CI" >&2
  exit 1
fi
[[ -f backend/.env && -n "${RUNNER_TEMP:-}" ]]
compose() { docker compose --env-file backend/.env "$@"; }

# Create a probe, dump the migrated DB and restore into a *different* empty DB.
compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE TABLE public.appfactory_ci_restore_probe (id integer PRIMARY KEY, marker text NOT NULL);
INSERT INTO public.appfactory_ci_restore_probe VALUES (1, 'before-backup');
SQL
backup="$RUNNER_TEMP/precis-ci-postgres.dump"
compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' > "$backup"
test -s "$backup"
sha256sum "$backup" > "$backup.sha256"
sha256sum -c "$backup.sha256"
compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM public.appfactory_ci_restore_probe WHERE id=1"'
compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" precis_ci_restore'
compose exec -T db sh -c 'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d precis_ci_restore' < "$backup"
restored="$(compose exec -T db sh -c 'psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d precis_ci_restore -c "SELECT marker FROM public.appfactory_ci_restore_probe WHERE id=1"')"
[[ "$restored" == before-backup ]] || { echo "::error::Database restore probe mismatch" >&2; exit 1; }
echo "PostgreSQL backup and isolated restore: PASS" >> "$GITHUB_STEP_SUMMARY"

# Rehearse translation file recovery using only the synthetic CI marker.
document="$RUNNER_TEMP/precis-ci-translation.backup"
compose exec -T backend sh -c 'cat /app/backend/translations/appfactory-ci-probe' > "$document"
[[ "$(cat "$document")" == persisted ]]
sha256sum "$document" > "$document.sha256"
compose exec -T backend sh -c ': > /app/backend/translations/appfactory-ci-probe'
sha256sum -c "$document.sha256"
compose exec -T backend sh -c 'cat > /app/backend/translations/appfactory-ci-probe' < "$document"
compose exec -T backend sh -c 'test "$(cat /app/backend/translations/appfactory-ci-probe)" = persisted'
echo "Synthetic translation document recovery: PASS" >> "$GITHUB_STEP_SUMMARY"

# Build a broken derivative of the known-good backend image locally.
baseline_container="$(compose ps -q backend)"
[[ -n "$baseline_container" ]]
baseline_id="$(docker inspect --format '{{.Image}}' "$baseline_container")"
docker image tag "$baseline_id" precis-ci-baseline:local
docker build --pull=false --tag precis-ci-failed:local - <<'DOCKERFILE'
FROM precis-ci-baseline:local
ENTRYPOINT ["/bin/sh", "-c", "exit 42"]
DOCKERFILE
failed_id="$(docker image inspect --format '{{.Id}}' precis-ci-failed:local)"
[[ "$failed_id" != "$baseline_id" ]]
override="$RUNNER_TEMP/precis-ci-rollback.yml"
cat > "$override" <<'YAML'
services:
  backend:
    image: precis-ci-failed:local
    pull_policy: never
YAML
docker compose -f docker-compose.yml -f "$override" --env-file backend/.env config --quiet
# A detached Compose launch may return success although the process immediately dies.
docker compose -f docker-compose.yml -f "$override" --env-file backend/.env up -d --no-deps --no-build --force-recreate backend || true
failed_container="$(docker compose -f docker-compose.yml -f "$override" --env-file backend/.env ps -a -q backend)"
[[ -n "$failed_container" ]]
[[ "$(docker inspect --format '{{.Image}}' "$failed_container")" == "$failed_id" ]]
if docker compose -f docker-compose.yml -f "$override" --env-file backend/.env exec -T backend curl -fsS --max-time 5 http://127.0.0.1:8000/health -o /dev/null; then
  echo "::error::Broken image unexpectedly passed health check" >&2
  exit 1
fi

cat > "$override" <<'YAML'
services:
  backend:
    image: precis-ci-baseline:local
    pull_policy: never
YAML
docker compose -f docker-compose.yml -f "$override" --env-file backend/.env up -d --no-deps --no-build --force-recreate backend
healthy=false
for _ in $(seq 1 30); do
  if docker compose -f docker-compose.yml -f "$override" --env-file backend/.env exec -T backend curl -fsS --max-time 5 http://127.0.0.1:8000/health -o /dev/null 2>/dev/null; then
    healthy=true
    break
  fi
  sleep 5
done
[[ "$healthy" == true ]] || { echo "::error::Rollback failed to restore backend health" >&2; exit 1; }
recovered="$(docker compose -f docker-compose.yml -f "$override" --env-file backend/.env ps -q backend)"
[[ -n "$recovered" ]]
[[ "$(docker inspect --format '{{.Image}}' "$recovered")" == "$baseline_id" ]]
compose exec -T backend sh -c 'test "$(cat /app/backend/translations/appfactory-ci-probe)" = persisted'
echo "Failed-image rollback to exact previous local image: PASS" >> "$GITHUB_STEP_SUMMARY"
echo "Scope: no SSM, no real host rollout, no database migration rollback." >> "$GITHUB_STEP_SUMMARY"
