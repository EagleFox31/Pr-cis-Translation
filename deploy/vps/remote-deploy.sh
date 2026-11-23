#!/usr/bin/env bash
# Commande forcée de la clé de déploiement Précis sur le VPS.
#   authorized_keys : restrict,command="<BASE>/bin/deploy.sh" ssh-ed25519 … precis-deploy-ci
#   côté CI         : git archive --format=tar.gz <sha> | ssh <cible> "deploy <sha>"
# La clé ne peut rien faire d'autre : pas de shell, pas de redirection, une seule commande validée.
# Idempotent : une version déjà en service et saine n'est ni reconstruite ni redémarrée (aucune écriture).
# Garde-fou de capacité : sous PRECIS_MIN_FREE_GB Go libres (défaut 5), refus avant toute écriture.
set -euo pipefail
BASE="${PRECIS_BASE:-$HOME/precis-translation}"
PROJECT="${PRECIS_COMPOSE_PROJECT:-precis-translation}"
PORT="${PRECIS_EDGE_PORT:-8090}"
MIN_FREE_GB="${PRECIS_MIN_FREE_GB:-5}"
# Systèmes de fichiers contrôlés : les versions et le data-root Docker (couches, cache de build).
DISK_PATHS="${PRECIS_DISK_PATHS:-$BASE /var/lib/docker}"
KEEP=3
MAX_BYTES=$((200 * 1024 * 1024))

cmd="${SSH_ORIGINAL_COMMAND:-$*}"
[[ "$cmd" =~ ^deploy\ ([0-9a-f]{7,40})$ ]] || { echo "usage : deploy <sha>" >&2; exit 64; }
sha="${BASH_REMATCH[1]:0:12}"
[[ "$MIN_FREE_GB" =~ ^[0-9]+$ ]] || { echo "PRECIS_MIN_FREE_GB invalide : '$MIN_FREE_GB' (entier en Go attendu)" >&2; exit 64; }

exec 9>"$BASE/.deploy.lock"
flock -w 900 9 || { echo "un déploiement est déjà en cours" >&2; exit 75; }

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
# Vide l'archive reçue sur stdin : le client (git archive | ssh) se termine proprement.
drain() { cat >/dev/null || true; }
# Échoue (et explique) si un des systèmes de fichiers de DISK_PATHS a moins de MIN_FREE_GB Go libres.
enough_disk() {
  local path line avail_kb mount ok=0 min_kb=$((MIN_FREE_GB * 1024 * 1024))
  for path in $DISK_PATHS; do
    [[ -e "$path" ]] || continue
    line="$(df -Pk -- "$path" | awk 'NR == 2 { print $4, $6 }')"
    avail_kb="${line%% *}" mount="${line#* }"
    [[ "$avail_kb" =~ ^[0-9]+$ ]] || continue
    if (( avail_kb < min_kb )); then
      echo "espace disque insuffisant sur $mount ($path) : $((avail_kb / 1024)) Mo libres, minimum ${MIN_FREE_GB} Go (PRECIS_MIN_FREE_GB)" >&2
      ok=1
    fi
  done
  return "$ok"
}

prev="$(readlink "$BASE/current" || true)"
if [[ "$prev" == "app-$sha" ]] && healthy; then drain; echo "déjà en service : $sha"; exit 0; fi

if ! enough_disk; then
  drain
  cat >&2 <<MSG
déploiement de $sha refusé avant toute modification : la version en service (${prev:-<aucune>}) et ses conteneurs restent en place.
Libérer de l'espace sur le VPS puis relancer le job, par exemple :
  sudo docker system df        # repérer ce qui occupe le disque
  sudo docker builder prune    # purger le cache de build (non lancé automatiquement : hôte partagé)
MSG
  exit 73
fi

mkdir -p "$BASE/releases"
tgz="$BASE/releases/app-$sha.tgz"
head -c $((MAX_BYTES + 1)) > "$tgz.part"
if (( $(stat -c %s "$tgz.part") > MAX_BYTES )); then rm -f "$tgz.part"; echo "archive trop volumineuse" >&2; exit 65; fi
mv "$tgz.part" "$tgz"

rel="$BASE/app-$sha"
rm -rf "$rel.tmp" && mkdir -p "$rel.tmp"
tar xzf "$tgz" -C "$rel.tmp"
ln -sfn ../../shared/backend.env "$rel.tmp/backend/.env"
rm -rf "$rel" && mv "$rel.tmp" "$rel"
ln -sfn "app-$sha" "$BASE/current"

restore_current() { [[ -n "$prev" && -d "$BASE/$prev" ]] && ln -sfn "$prev" "$BASE/current"; }

# Phase 1 : construction. Un échec ici ne touche pas aux conteneurs en service :
# on remet seulement le lien `current`, sans reconstruire l'ancienne version (disque plein = même échec).
if ! { compose build backend && compose build web; }; then
  echo "échec de la construction de $sha : conteneurs en service non modifiés" >&2
  if restore_current; then
    if healthy; then
      echo "production inchangée : ${prev} toujours en service" >&2
    else
      echo "production indisponible sur ${prev} (indépendamment de ce build) : intervention requise" >&2
    fi
  else
    echo "aucune version précédente : rien à restaurer" >&2
  fi
  enough_disk || echo "capacité disque probablement en cause : voir 'sudo docker system df' puis 'sudo docker builder prune'" >&2
  exit 1
fi

# Phase 2 : bascule. Ici les conteneurs ont pu être recréés : retour arrière réel.
if compose up -d --remove-orphans && healthy; then
  echo "déployé : $sha"
else
  echo "échec du déploiement de $sha, retour à ${prev:-<aucune>}" >&2
  if restore_current; then
    compose up -d --build --remove-orphans && healthy || echo "retour arrière en échec : intervention requise" >&2
  fi
  exit 1
fi

# Ménage : garder les KEEP versions les plus récentes (dont celle en service).
cd "$BASE"
ls -1dt app-*/ | sed 's#/$##' | grep -vx "app-$sha" | tail -n +"$KEEP" | xargs -r rm -rf --
ls -1t releases/app-*.tgz | tail -n +$((KEEP + 1)) | xargs -r rm -f --
