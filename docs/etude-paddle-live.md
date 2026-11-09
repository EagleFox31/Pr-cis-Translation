# Étude — passer le paiement par carte (Paddle) en réel

## Besoin
Encaisser de vrais paiements par carte sur https://precis-translator.trigenys.com.
La logique (devis, transaction, webhook, crédit) est faite et testée en sandbox
(`docs/paiement-carte-paddle.md`). Il reste à la faire tourner en production.

## État de l'existant (mesuré le 30/10/2026)
| Point | Constat |
|---|---|
| Backend | `PaddleClient` bascule sur `api.paddle.com` si `PADDLE_ENV=LIVE` ; rien à changer dans la logique. |
| Secrets prod | `backend/.env` est écrit depuis SSM (`/precis-translation/staging/env`), puis `scripts/staging/aws-ssm-compose.sh` construit les images avec `docker-compose.yml --env-file backend/.env`. |
| **Front, build** | `VITE_PADDLE_ENV` et `VITE_PADDLE_CLIENT_TOKEN` ne sont ni dans `frontend/Dockerfile` ni dans `docker-compose.yml`. En production, la page de paiement afficherait « Paiement par carte non configuré ». |
| **nginx, route** | `location /` sert `try_files $uri =404` : `/paiement/carte` (le lien de paiement déclaré chez Paddle) renvoie **404**. Seules `/home` et quelques routes servent l'application. |
| **nginx, cadre** | Toutes les pages portent `frame-ancestors 'none'` et `X-Frame-Options: DENY`. La fenêtre de paiement affiche `/paiement/carte` dans un cadre : le navigateur le **bloquerait**. |
| En local | Rien de cela ne se voit : Vite sert toutes les routes, sans ces en-têtes. |

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Front lit le même `PADDLE_ENV` que le backend (`SANDBOX`/`LIVE`), plus un `PADDLE_CLIENT_TOKEN` dans le même fichier | Une seule valeur : front et back ne peuvent pas viser deux environnements différents (même logique que `FRONTEND_API_KEY`) | La page accepte deux écritures (`sandbox`/`production` en local, `SANDBOX`/`LIVE` en prod) |
| B. Deux variables `VITE_PADDLE_*` séparées dans SSM | Aucun code front touché | Deux copies à garder d'accord ; un oubli = paiement d'un côté en sandbox, de l'autre en live |

Pour nginx : une `location = /paiement/carte` dédiée qui sert l'application,
autorise le cadre **de notre propre site seulement** (`frame-ancestors 'self'`,
`SAMEORIGIN`) et reste hors moteurs de recherche. Les autres pages gardent `DENY`.

## Choix
A + location dédiée. Ajout : le backend signale au démarrage une clé qui ne
correspond pas à l'environnement (`pdl_sdbx_` avec `LIVE`, ou l'inverse).

## Impacts
- Données / migrations : aucun.
- Sécurité : le cadre n'est ouvert qu'à notre domaine et sur cette seule page ;
  le jeton client Paddle est public par conception.
- Déploiement : nouvelles clés dans SSM, rebuild de l'image front (automatique au déploiement).
- Coût : tarif Paddle 5 % + 0,50 $ déjà répercuté (`CARD_FEE_*`) ; à confirmer sur le contrat.

## Ce que seul le propriétaire du compte peut faire
1. Compte Paddle live vérifié ; domaine `precis-translator.trigenys.com` approuvé.
2. Produit live sans prix → `PADDLE_PRODUCT_ID`.
3. *Checkout settings* → Default payment link `https://precis-translator.trigenys.com/paiement/carte`.
4. Notification `https://precis-translator.trigenys.com/api/payments/paddle/webhook`, événements `transaction.*`.
5. Dans SSM : `PADDLE_ENV=LIVE`, `PADDLE_API_KEY=pdl_live_…`, `PADDLE_PRODUCT_ID`, `PADDLE_WEBHOOK_SECRET`,
   `PADDLE_CLIENT_TOKEN=live_…`, `PAYMENT_METHODS` contenant `card=paddle` ; pas de `PADDLE_CHECKOUT_URL`.
6. Déployer (fusion sur `main`), puis un paiement réel de faible montant et son remboursement.

## Risques
- Domaine non approuvé : `checkout.url` nul → erreur « transaction sans checkout.url » (déjà gérée).
- Minimum live différent du sandbox : à relire dans `GET /currencies` après passage.
