# PASSATION — 20/10/2026

## 1. Objectif en cours
Paiement par carte (dont Visa prépayée) via Paddle Billing sur la méthode `card` : page `/paiement/carte` (Paddle.js inline dans l'iframe de `PaymentModal`) + webhook signé qui crédite comme Fapshi. Sandbox validé ; prochaine étape : passage en LIVE (prod).

## 2. Fait (commit d0826c6, branche `feat/paiement-paddle`, non poussée)
- `backend/app/core/payment_gateway.py:461-620` : `paddle_amount`, `PaddleClient`, `verify_webhook_signature`.
- `backend/app/core/payment_methods.py:111` : `PaddleProvider` ; `PADDLE_CHECKOUT_URL` (dev local) remplace le lien Paddle dans `checkout_url`.
- `backend/app/api/payments.py` : webhook `POST /api/payments/paddle/webhook` ; garde « forfait en attente » (3 min) pour Mobile Money seulement ; carte : `_resume_card_plan` rouvre la transaction ouverte de la même offre (15 min), une autre offre crée un nouveau paiement.
- Minimum par moyen : `pricing.py` `MIN_CARD_AMOUNT` (427 F / 0,70 $ / 0,65 €, `minimum_payment_amount` Paddle) + `min_payment_amount(zone, method)` ; `billable_pages(..., method)` dans `collect` ; `/quote` renvoie un bloc `card` ; `PaymentModal` bascule sur ce bloc quand la carte est choisie (bouton désactivé + `payment.min_pages_card`). Frais 3 % déjà à la charge du client pour tous les moyens (`_with_fee`).
- Tests : test_paddle 21/21 ; test_fapshi 18/18 ; test_verrous_plan 17/17 ; test_paiement_minimum 15/15.
- Front : `CardPaymentPage.tsx` (`_ptxn` lu une fois via `useState`, retiré de l'URL, `Checkout.open` gardé par `useRef` contre le double effet du mode strict ; `checkout.error` laissé à Paddle) ; `App.tsx` rend la page carte HORS `AuthProvider` (wrapper `App` → `MainApp`) ; commentaire iframe corrigé `PaymentModal.tsx:230`. tsc + lint + build OK.
- Doc : bloc Paddle dans `backend/.env.example` (+ `PADDLE_CHECKOUT_URL` commenté), `frontend/.env.example`, `docs/deploiement.md`. CHANGELOG non édité (release-please).

## 3. Décisions
- Zone A en EUR (XAF / 655,957, arrondi sup.), B USD, C EUR ; base en XAF. Prix non-catalogue à chaque transaction, un seul produit Paddle sans prix.
- Crédit seulement après relecture API ; le polling `GET /payments/{id}` relit aussi Paddle → démo locale sans webhook/ngrok.
- Paddle refuse `localhost` comme Default payment link : lien de prod saisi chez Paddle, `PADDLE_CHECKOUT_URL=http://localhost:3000/paiement/carte` dans `backend/.env` local.
- Revue : rejetés double crédit (UPDATE atomique), tolérance 300 s signature, webhook txn inconnue → 200.

## 4. Plan
1. [x] `PaddleClient` + `PaddleProvider`.
2. [x] Webhook.
3. [x] Front `CardPaymentPage`.
4. [x] Tests backend.
5. [x] Doc.
6. [x] Écarts de revue a–e corrigés, tests/build verts.
7. [x] Test sandbox (4242, Pro 12 mois crédité, reprise checkout, minimum carte).
8. [x] Commit + doc `docs/paiement-carte-paddle.md`.
9. [ ] Frais carte (étude `docs/etude-frais-carte.md`, A+B, 5 % + 0,50 $, minimum pages 3 000 F / 5 € / 5 $) :
   9a. [x] Backend `pricing.py` (`card_fee`, `transaction_fee(..., method)`, `MIN_CARD_AMOUNT`) + `payments.py` (`_with_fee` par moyen, bloc `card` de `/plan/quote`, `/plan` et `/collect`) + `system.py`.
   9b. [x] Tests backend (minimum, abonnements, paddle) + nouveaux cas frais carte.
   9c. [x] Front : libellé frais carte sans %, bloc `card` du devis forfait, i18n fr/en ; tsc/lint/build.
   9d. [x] Doc `paiement-carte-paddle.md` ; revue du diff ; commit.
10. [ ] Passage en live : checklist « Passage en live » de `docs/paiement-carte-paddle.md` (MCP `paddle-live` sur demande explicite).
11. [ ] Push + PR vers main.

**Hors plan** : rattrapage serveur des paiements Fapshi `PENDING` (attend accord) ; secrets Paddle dans SSM au déploiement ; approbation du domaine en live ; test avec une vraie carte = mode live uniquement (sandbox : cartes de test seulement).

## 5. Pièges / contexte
- `backend/.env` en LIVE pour Fapshi : ne jamais valider d'invite réelle ; tester seulement la carte. Ne pas afficher les `.env` (vérifier par `grep -c`). Jamais de clé dans un fichier suivi.
- Tests : `cd backend && PYTHONUTF8=1 /c/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe tests/<suite>.py` (pas de pytest).
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- StatReload sous Windows ne recharge pas toujours : après un changement backend, `npm run stop` puis relancer.
- Démarrage : `npm run dev` échoue (pas de `backend/venv`) → en arrière-plan `PYTHONUTF8=1 <venv backup>/python.exe scripts/dev.py` à la racine ; arrêt `npm run stop`. Api :8000, front :3000.
- Produit sandbox `pro_01m5cza0wrhn34kss0tk9zxg4j`. MCP `paddle-live` seulement sur demande « live ». Remote `origin` = EagleFox31.
