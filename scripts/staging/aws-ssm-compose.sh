#!/usr/bin/env bash
# Generic AppFactory EC2/SSM deployment adapter for Précis.
# Closely follows Atelier Maître's working SSM -> Parameter Store -> Compose
# -> health verification pattern; never reads Atelier prod parameters.
set -Eeuo pipefail
umask 077

readonly LIFECYCLE="${APPFACTORY_HOST_LIFECYCLE:-ephemeral}"
[[ "$LIFECYCLE" == ephemeral || "$LIFECYCLE" == persistent ]] || exit 1
export APPFACTORY_HOST_LIFECYCLE="$LIFECYCLE"
readonly PROJECT=precis-translation
readonly REPO_ROOT=/opt/appfactory/precis-translation/repo
readonly ENV_PARAMETER=/precis-translation/staging/env
readonly ENV_FILE="$REPO_ROOT/backend/.env"
readonly COMPOSE_PROJECT_NAME=precis-translation-staging

cd "$REPO_ROOT"
if ! docker compose version >/dev/null 2>&1; then
  # AL2023 Docker may install without the Compose v2 CLI plugin.
  install -d -m 0755 /usr/local/lib/docker/cli-plugins
  # On AL2023 Docker v2 Compose is not reliably provided as a dnf package.
  # Fetch the explicitly pinned Linux AMD64 Compose binary over HTTPS.
  curl -fLsS --retry 3 --max-time 120 \
    https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose.tmp
  chmod 0755 /usr/local/lib/docker/cli-plugins/docker-compose.tmp
  mv -f /usr/local/lib/docker/cli-plugins/docker-compose.tmp /usr/local/lib/docker/cli-plugins/docker-compose
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
import os,json
if os.environ['APPFACTORY_HOST_LIFECYCLE'] == 'persistent':
    from urllib.parse import urlparse
    origin=json.loads(Path('deploy/public-site.json').read_text())['url'].rstrip('/')
    parsed=urlparse(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.hostname in ('localhost','127.0.0.1') or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise SystemExit('Invalid tracked public origin')
    changes={'FRONTEND_URL':origin,'ALLOWED_ORIGINS':origin,'PUBLIC_SITE':parsed.hostname}
    env=Path('backend/.env')
    rows=[]
    seen=set()
    for row in env.read_text().splitlines():
        name=row.partition('=')[0]
        if name in changes:
            rows.append(name+'='+changes[name])
            seen.add(name)
        else:
            rows.append(row)
    rows.extend(name+'='+value for name,value in changes.items() if name not in seen)
    env.write_text('\n'.join(rows)+'\n')
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
if os.environ['APPFACTORY_HOST_LIFECYCLE'] == 'ephemeral':
    if keys.get('CAMPAY_ENV') != 'DEMO':
        raise SystemExit('Only Campay DEMO may be enabled on disposable staging')
    if keys.get('EMAIL_ENABLED','false').lower() != 'false':
        raise SystemExit('Real SMTP delivery disabled in disposable staging')
else:
    from urllib.parse import urlparse
    origin=keys.get('FRONTEND_URL','')
    if urlparse(origin).scheme != 'https' or urlparse(origin).hostname in (None,'localhost','127.0.0.1'):
        raise SystemExit('Persistent deployment requires public HTTPS FRONTEND_URL')
    if keys.get('ALLOWED_ORIGINS') != origin:
        raise SystemExit('Persistent deployment requires matching public CORS origin')
    if keys.get('EMAIL_ENABLED','false').lower()=='true' and not (keys.get('SMTP_USER') and keys.get('SMTP_PASSWORD')):
        raise SystemExit('Enabled SMTP requires credentials')
    if keys.get('CAMPAY_ENV')=='PROD' and not all(keys.get(k) for k in ('CAMPAY_USERNAME','CAMPAY_PASSWORD','CAMPAY_WEBHOOK_KEY')):
        raise SystemExit('Campay PROD requires credentials and webhook key')
PY

COMPOSE_FILES=(-f docker-compose.yml)
if [[ "$LIFECYCLE" == persistent ]]; then
  python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlparse
import re
vals={}
for row in Path('backend/.env').read_text().splitlines():
    if '=' in row and not row.lstrip().startswith('#'):
        key,value=row.split('=',1)
        vals[key]=value.strip().strip("'").strip('"')
host=urlparse(vals['FRONTEND_URL']).hostname
if not host or not re.fullmatch(r'[A-Za-z0-9.-]+',host):
    raise SystemExit('Invalid public HTTPS hostname')
Path('deploy/Caddyfile.runtime').write_text(host+' {\n    reverse_proxy web:80 {\n        flush_interval -1\n    }\n}\n')
PY
  COMPOSE_FILES+=(-f docker-compose.https.yml)
  readonly HEALTH_ORIGIN=http://127.0.0.1:8080
else
  readonly HEALTH_ORIGIN=http://127.0.0.1
fi

# The already tested Compose stack contains Postgres, backend with system
# LibreOffice, and frontend Nginx. Named volumes must not be destroyed.
docker compose "${COMPOSE_FILES[@]}" --project-name "$COMPOSE_PROJECT_NAME" \
  --env-file "$ENV_FILE" config --quiet

docker compose "${COMPOSE_FILES[@]}" --project-name "$COMPOSE_PROJECT_NAME" \
  --env-file "$ENV_FILE" up -d --build --wait --wait-timeout 300

if [[ "$LIFECYCLE" == persistent ]]; then
  docker compose "${COMPOSE_FILES[@]}" --project-name "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" \
    exec -T edge caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
fi

# Check the same internal /health route Atelier checks. No public success claim
# is allowed based on container state alone.
for attempt in $(seq 1 36); do
  if curl -fsS --max-time 5 "$HEALTH_ORIGIN/health" >/dev/null &&
     curl -fsS --max-time 5 "$HEALTH_ORIGIN/" >/dev/null; then
    docker compose "${COMPOSE_FILES[@]}" --project-name "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" ps
    echo "AppFactory Précis $LIFECYCLE host healthy (internal HTTP + API only)."
    exit 0
  fi
  sleep 5
done
echo 'Précis staging failed internal frontend + API health checks' >&2
exit 1
