#!/bin/sh
# Raccourci de pilotage de la pile Docker.
#
# Il n'existe que pour une raison : `docker compose` DOIT être appelé avec
# `--env-file backend/.env`. Sans ce drapeau, Compose lit un `.env` à la racine
# — un deuxième fichier de secrets, qui divergerait du premier. Un raccourci
# qu'on tape sans réfléchir vaut mieux qu'une consigne qu'on oublie.
#
#   ./scripts/precis.sh up        construit et démarre (en arrière-plan)
#   ./scripts/precis.sh down      arrête (les données SURVIVENT)
#   ./scripts/precis.sh logs      suit les journaux
#   ./scripts/precis.sh ps        état des conteneurs
#   ./scripts/precis.sh rebuild   reconstruit tout et redémarre
#   ./scripts/precis.sh psql      ouvre un accès à la base
#   ./scripts/precis.sh shell     ouvre un terminal dans le service
set -e

RACINE=$(cd "$(dirname "$0")/.." && pwd)
cd "$RACINE"

if [ ! -f backend/.env ]; then
    echo "ERREUR : backend/.env est absent." >&2
    echo "Copier backend/.env.example en backend/.env et remplir les cases vides." >&2
    exit 1
fi

DC="docker compose --env-file backend/.env"

case "${1:-up}" in
    up)      $DC up -d --build ;;
    down)    $DC down ;;
    logs)    shift; $DC logs -f "$@" ;;
    ps)      $DC ps ;;
    rebuild) $DC build --no-cache && $DC up -d ;;
    psql)    $DC exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' ;;
    shell)   $DC exec backend bash ;;
    # Volontairement ABSENT : `down -v`, qui efface les volumes — donc la base
    # et tous les documents traduits. Un geste irréversible ne doit pas tenir
    # dans un raccourci de trois lettres. Il reste possible à la main, ce qui
    # laisse le temps d'y penser.
    *)
        echo "Usage : $0 {up|down|logs|ps|rebuild|psql|shell}" >&2
        exit 2 ;;
esac
