#!/usr/bin/env bash
# Generic AppFactory EC2/SSM deployment adapter for Précis.
# Closely follows Atelier Maître's working SSM -> Parameter Store -> Compose
# -> health verification pattern; never reads Atelier prod parameters.
set -Eeuo pipefail
umask 077

readonly PROJECT=precis-translation
readonly REPO_ROOT=/opt/appfactory/precis-translation/repo
readonly ENV_PARAMETER=/precis-translation/staging/env
readonly ENV_FILE="$REPO_ROOT/backend/.env"
readonly COMPOSE_PROJECT_NAME=precis-translation-staging

cd "$REPO_ROOT"
if ! docker compose version >/dev/null 2>&1; then
  # AL2023 Docker may install without the Compose v2 CLI plugin.
  dnf install -y docker-compose-plugin >/dev/null ||
    { echo 'Docker Compose v2 plugin absent on the reviewed staging AMI' >&2; exit 1; }
fi
docker compose version >/dev/null || exit 1

# A single SSM SecureString source, as in Atelier Maître. The host's instance
# profile must be allowed to GET only its dedicated parameter. Output never
# appears in GitHub Actions logs or SSM command parameters.
aws ssm get-parameter --name "$ENV_PARAMETER" --with-decryption \
  --query 'Parameter.Value' --output text > "$ENV_FILE.tmp"
chmod 600 "$ENV_FILE.tmp"
mv -f "$ENV_FILE.tmp" "$ENV_FILE"

# Prevent accidental production configuration, missing credentials, and
# external db references. The host stays deliberately private (SG: no ingress).
python3 - <<'PY'
from pathlib import Path
import os
keys = {}
for line in Path('backend/.env').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    keys[key] = value
required = ['DEEPSEEK_API_KEY','FRONTEND_API_KEY','POSTGRES_PASSWORD','JWT_SECRET']
missing=[k for k in required if not keys.get(k)]
if missing:
    raise SystemExit('Refusing staging startup: missing '+', '.join(missing))
if len(keys['JWT_SECRET']) < 32:
    raise SystemExit('JWT_SECRET below required minimum')
if keys.get('PRECIS_ENV') not in ('staging','production'):
    raise SystemExit('Expected an explicitly configured nondevelopment staging runtime')
if keys.get('CAMPAY_ENV') != 'DEMO':
    raise SystemExit('Only Campay DEMO may be enabled on disposable staging')
if keys.get('EMAIL_ENABLED','false').lower() != 'false':
    raise SystemExit('Real SMTP delivery disabled in disposable staging')
PY

# The already tested Compose stack contains Postgres, backend with system
# LibreOffice, and frontend Nginx. Named volumes must not be destroyed.
docker compose --project-name "$COMPOSE_PROJECT_NAME" \
  --env-file "$ENV_FILE" config --quiet

docker compose --project-name "$COMPOSE_PROJECT_NAME" \
  --env-file "$ENV_FILE" up -d --build --wait --wait-timeout 300

# Check the same internal /health route Atelier checks. No public success claim
# is allowed based on container state alone.
for attempt in $(seq 1 36); do
  if curl -fsS --max-time 5 http://127.0.0.1/health >/dev/null &&
     curl -fsS --max-time 5 http://127.0.0.1/ >/dev/null; then
    docker compose --project-name "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" ps
    echo "AppFactory Précis staging healthy (internal HTTP + API)."
    exit 0
  fi
  sleep 5
done
echo 'Précis staging failed internal frontend + API health checks' >&2
exit 1
