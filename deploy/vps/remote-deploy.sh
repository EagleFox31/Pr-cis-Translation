#!/usr/bin/env bash
# Commande forcée de la clé de déploiement Précis sur le VPS.
#   authorized_keys : restrict,command="<BASE>/bin/deploy.sh" ssh-ed25519 … precis-deploy-ci
#   côté CI         : git archive --format=tar.gz <sha> | ssh <cible> "deploy <sha>"
# La clé ne peut rien faire d'autre : pas de shell, pas de redirection, une seule commande validée.
# Idempotent : une version déjà en service et saine n'est ni reconstruite ni redémarrée.
set -euo pipefail
BASE="${PRECIS_BASE:-$HOME/precis-translation}"
PROJECT="${PRECIS_COMPOSE_PROJECT:-precis-translation}"
PORT="${PRECIS_EDGE_PORT:-8090}"
KEEP=3
MAX_BYTES=$((200 * 1024 * 1024))

cmd="${SSH_ORIGINAL_COMMAND:-$*}"
[[ "$cmd" =~ ^deploy\ ([0-9a-f]{7,40})$ ]] || { echo "usage : deploy <sha>" >&2; exit 64; }
sha="${BASH_REMATCH[1]:0:12}"

exec 9>"$BASE/.deploy.lock"
flock -w 900 9 || { echo "un déploiement est déjà en cours" >&2; exit 75; }

mkdir -p "$BASE/releases"
tgz="$BASE/releases/app-$sha.tgz"
head -c $((MAX_BYTES + 1)) > "$tgz.part"
if (( $(stat -c %s "$tgz.part") > MAX_BYTES )); then rm -f "$tgz.part"; echo "archive trop volumineuse" >&2; exit 65; fi
mv "$tgz.part" "$tgz"

compose() {
  (cd "$BASE/current" && sudo -n docker compose -p "$PROJECT" --env-file backend/.env \
    -f docker-compose.yml -f docker-compose.https.yml -f deploy/vps/docker-compose.vps.yml "$@")
}
healthy() {
  for _ in $(seq 1 40); do
    [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health")" == 200 ]] && return 0
    sleep 3
  done
  return 1
}

prev="$(readlink "$BASE/current" || true)"
if [[ "$prev" == "app-$sha" ]] && healthy; then echo "déjà en service : $sha"; exit 0; fi

rel="$BASE/app-$sha"
rm -rf "$rel.tmp" && mkdir -p "$rel.tmp"
tar xzf "$tgz" -C "$rel.tmp"
ln -sfn ../../shared/backend.env "$rel.tmp/backend/.env"
rm -rf "$rel" && mv "$rel.tmp" "$rel"
ln -sfn "app-$sha" "$BASE/current"

if compose build backend && compose build web && compose up -d --remove-orphans && healthy; then
  echo "déployé : $sha"
else
  echo "échec du déploiement de $sha, retour à ${prev:-<aucune>}" >&2
  if [[ -n "$prev" && -d "$BASE/$prev" ]]; then
    ln -sfn "$prev" "$BASE/current"
    compose up -d --build --remove-orphans && healthy || echo "retour arrière en échec : intervention requise" >&2
  fi
  exit 1
fi

# Ménage : garder les KEEP versions les plus récentes (dont celle en service).
cd "$BASE"
ls -1dt app-*/ | sed 's#/$##' | grep -vx "app-$sha" | tail -n +"$KEEP" | xargs -r rm -rf --
ls -1t releases/app-*.tgz | tail -n +$((KEEP + 1)) | xargs -r rm -f --
