# syntax=docker/dockerfile:1
# check=skip=SecretsUsedInArgOrEnv
#
# POURQUOI CE CONTRÔLE EST DÉSACTIVÉ, ET SEULEMENT CELUI-LÀ
# ---------------------------------------------------------
# BuildKit avertit dès qu'une variable nommée *KEY* passe par ARG ou ENV. La
# règle est bonne — sauf ici, où elle décrit précisément ce qu'il FAUT faire.
#
# `VITE_API_KEY` n'est pas un secret : Vite la cuit dans le JavaScript envoyé au
# navigateur, où n'importe quel visiteur la lit avec F12. Elle ne peut pas être
# fournie autrement, et un `--mount=type=secret` ne changerait rien à ce fait —
# il déplacerait le message d'avertissement, pas l'exposition.
#
# Elle ne subsiste PAS dans l'image livrée : la construction est en deux étapes,
# et l'étape finale (nginx) n'hérite d'aucune variable de l'étape Node.
#
# Un avertissement qu'on sait faux et qu'on laisse s'afficher à chaque
# construction apprend à ignorer les avertissements. C'est ce qui rend le
# suivant — le vrai — invisible. D'où ce `skip` ciblé, sur cette règle seule.

# ══════════════════════════════════════════════════════════════════════════════
#  Précis Translator — image de l'interface
#
#  Construction depuis la RACINE du dépôt :
#      docker build -f frontend/Dockerfile -t precis-web .
#
#  Deux étapes : Node compile, nginx sert. L'image finale ne contient ni Node,
#  ni les node_modules — seulement des fichiers statiques et un serveur web.
#  Environ 50 Mo au lieu de 1,5 Go.
# ══════════════════════════════════════════════════════════════════════════════

# ── Étape 1 : compilation ────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# `npm ci` et non `npm install` : il installe EXACTEMENT le contenu du
# package-lock.json. `install` peut résoudre une version plus récente et
# produire une interface différente de celle testée en local.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vite CUIT ces valeurs dans les fichiers produits : elles sont nécessaires
# ICI, à la construction, et non au démarrage. Une variable posée au lancement
# du conteneur n'aurait aucun effet — le JavaScript est déjà écrit.
ARG VITE_API_KEY
ARG VITE_API_BASE=""
ARG VITE_GOOGLE_CLIENT_ID=""

ENV VITE_API_KEY=$VITE_API_KEY \
    VITE_API_BASE=$VITE_API_BASE \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

# Échec IMMÉDIAT si la clé manque. Le code n'a plus de valeur de repli (elle
# masquait l'oubli en faisant marcher l'interface avec la clé publique du
# dépôt) : sans ce contrôle, on obtiendrait une image qui se construit très
# bien et qu'aucune requête ne traverse — un 401 sur chaque envoi, et rien
# dans les journaux qui explique pourquoi.
#
# Le contrôle passe par Node et NON par `test -n "$VITE_API_KEY"` en shell :
# BuildKit substitue les variables dans le texte d'une instruction RUN avant de
# l'afficher, si bien que la clé s'écrivait EN CLAIR dans le journal de
# construction et y restait, consultable dans l'historique des builds. Node lit
# `process.env` à l'exécution — la valeur ne traverse jamais le texte de la
# commande, donc jamais le journal.
RUN node -e "if (!process.env.VITE_API_KEY) { \
        console.error('ERREUR : VITE_API_KEY est vide.'); \
        console.error('Elle doit valoir la meme chose que FRONTEND_API_KEY cote service.'); \
        console.error('docker compose la passe automatiquement depuis backend/.env.'); \
        process.exit(1); \
    }"

RUN npm run build

# ── Étape 2 : service des fichiers ───────────────────────────────────────────
FROM nginx:1.27-alpine

# La configuration est montée ici et non dans `docker-compose.yml` : elle décrit
# comment SERVIR l'application, ce qui appartient à l'image, pas au déploiement.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
