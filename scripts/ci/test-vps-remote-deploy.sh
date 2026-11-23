#!/usr/bin/env bash
# Non-régression de deploy/vps/remote-deploy.sh, sans Docker ni VPS : sudo, curl, df, flock et
# sleep sont remplacés par des doublures (PATH). Vérifie le garde-fou disque, l'idempotence et
# que l'échec d'un build n'annonce pas un faux retour arrière.
set -euo pipefail
SCRIPT="$(cd "$(dirname "$0")/../.." && pwd)/deploy/vps/remote-deploy.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
fails=0

mkdir -p "$WORK/bin"
cat > "$WORK/bin/sudo" <<'STUB'
#!/usr/bin/env bash
# sudo -n docker compose … <verbe> … : journalise, échoue sur demande, pilote la santé.
shift; echo "$*" >> "$STATE/calls"
case " $* " in
  *" build "*) [[ -z "${FAIL_BUILD:-}" ]] || exit 1 ;;
  *" up "*)    [[ -z "${FAIL_UP:-}" ]] || exit 1; [[ -n "${UP_UNHEALTHY:-}" ]] && rm -f "$STATE/healthy" || touch "$STATE/healthy" ;;
esac
STUB
cat > "$WORK/bin/curl" <<'STUB'
#!/usr/bin/env bash
[[ -e "$STATE/healthy" ]] && printf 200 || printf 000
STUB
cat > "$WORK/bin/df" <<'STUB'
#!/usr/bin/env bash
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/sda1 39000000 1 %s 99%% /\n' "$FREE_KB"
STUB
printf '#!/bin/sh\nexit 0\n' > "$WORK/bin/flock"
printf '#!/bin/sh\nexit 0\n' > "$WORK/bin/sleep"
chmod +x "$WORK/bin/"*

mkdir -p "$WORK/src/backend" && echo app > "$WORK/src/backend/main.py"
tar czf "$WORK/app.tgz" -C "$WORK/src" .

PREV=aaaaaaaaaaaa NEW=bbbbbbbbbbbb
# setup : BASE avec une version précédente en service et saine.
setup() {
  export STATE="$WORK/case-$1" PRECIS_BASE="$WORK/case-$1/base"
  mkdir -p "$PRECIS_BASE/app-$PREV/backend" "$PRECIS_BASE/shared"
  ln -sfn "app-$PREV" "$PRECIS_BASE/current"
  touch "$STATE/healthy" "$STATE/calls"
  export PRECIS_DISK_PATHS="$PRECIS_BASE" FREE_KB=$((20 * 1024 * 1024))
  unset FAIL_BUILD FAIL_UP UP_UNHEALTHY PRECIS_MIN_FREE_GB
}
run() { set +e; PATH="$WORK/bin:$PATH" SSH_ORIGINAL_COMMAND="deploy $1" bash "$SCRIPT" < "$WORK/app.tgz" > "$STATE/out" 2>&1; echo $? > "$STATE/rc"; set -e; }
check() { if eval "$2"; then echo "ok   - $1"; else echo "FAIL - $1"; sed 's/^/       /' "$STATE/out"; fails=$((fails + 1)); fi; }
rc() { cat "$STATE/rc"; }
out() { grep -q -- "$1" "$STATE/out"; }
current() { readlink "$PRECIS_BASE/current"; }

setup disk-low; FREE_KB=$((399 * 1024)); run $NEW
check "disque bas : refus (73)"                         '[[ $(rc) == 73 ]]'
check "disque bas : message avec espace libre"          'out "399 Mo libres, minimum 5 Go"'
check "disque bas : propose docker builder prune"       'out "docker builder prune"'
check "disque bas : aucun appel docker"                 '[[ ! -s $STATE/calls ]]'
check "disque bas : rien écrit, current inchangé"       '[[ $(current) == app-$PREV && ! -e $PRECIS_BASE/app-$NEW && ! -e $PRECIS_BASE/releases ]]'

setup disk-threshold; FREE_KB=$((8 * 1024 * 1024)); PRECIS_MIN_FREE_GB=10; export PRECIS_MIN_FREE_GB; run $NEW
check "seuil configurable : 8 Go < 10 Go refusé"        '[[ $(rc) == 73 ]] && out "minimum 10 Go"'

setup bad-threshold; PRECIS_MIN_FREE_GB=abc; export PRECIS_MIN_FREE_GB; run $NEW
check "seuil invalide : usage (64)"                     '[[ $(rc) == 64 ]] && [[ ! -s $STATE/calls ]]'

setup noop; ln -sfn "app-$PREV" "$PRECIS_BASE/current"; FREE_KB=1; run $PREV
check "déjà en service : no-op même disque plein"       '[[ $(rc) == 0 ]] && out "déjà en service"'
check "déjà en service : zéro écriture"                 '[[ ! -s $STATE/calls && ! -e $PRECIS_BASE/releases ]]'

setup build-fail; FAIL_BUILD=1; export FAIL_BUILD; run $NEW
check "build en échec : code 1"                         '[[ $(rc) == 1 ]]'
check "build en échec : pas de faux retour arrière"     '! out "intervention requise" && out "production inchangée"'
check "build en échec : ni up ni rebuild de l ancienne" '! grep -q " up " $STATE/calls && [[ $(grep -c build $STATE/calls) == 1 ]]'
check "build en échec : current restauré"               '[[ $(current) == app-$PREV ]]'

setup build-fail-down; FAIL_BUILD=1; export FAIL_BUILD; rm -f "$STATE/healthy"; run $NEW
check "build en échec, prod déjà KO : intervention"     '[[ $(rc) == 1 ]] && out "production indisponible"'

setup up-unhealthy; UP_UNHEALTHY=1; export UP_UNHEALTHY; run $NEW
check "santé KO après up : retour arrière avec rebuild" '[[ $(rc) == 1 ]] && grep -q "up -d --build" $STATE/calls && [[ $(current) == app-$PREV ]]'
check "retour arrière KO : intervention requise"        'out "retour arrière en échec : intervention requise"'

setup success; run $NEW
check "succès : déployé, current bascule"               '[[ $(rc) == 0 ]] && out "déployé : $NEW" && [[ $(current) == app-$NEW ]]'
check "succès : build backend, web puis up"             '[[ $(grep -c build $STATE/calls) == 2 ]] && grep -q "up -d --remove-orphans" $STATE/calls'

setup usage; run "not-a-sha"
check "commande invalide : usage (64)"                  '[[ $(rc) == 64 ]]'

(( fails == 0 )) && echo "tous les cas passent" || { echo "$fails cas en échec"; exit 1; }
