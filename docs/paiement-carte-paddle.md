# Paiement par carte — Paddle Billing

Moyen `card` (carte bancaire, dont Visa prépayée), encaissé par Paddle Billing.
Paiements uniques : achat de pages et forfaits payés d'avance (1 ou 12 mois).
Aucun abonnement Paddle : le renouvellement reste géré chez nous.

## Parcours

1. La fenêtre de paiement (`PaymentModal`) demande un devis (`POST /api/payments/quote`
   ou `/plan/quote`). Le devis porte un bloc `card` : pages facturées, frais,
   montant et minimum propres à la carte.
2. Au clic sur « Payer », le backend crée une transaction Paddle à prix
   non-catalogue (`POST /transactions`, rattachée à `PADDLE_PRODUCT_ID`) et
   enregistre un `Payment` `PENDING` (`provider_ref` = `txn_…`).
3. Il renvoie `checkout_url` : le *Default payment link* déclaré chez Paddle,
   suivi de `?_ptxn=txn_…`. La fenêtre l'affiche dans un cadre.
4. `/paiement/carte` (`CardPaymentPage.tsx`, hors `AuthProvider`) charge
   Paddle.js v2 et ouvre le formulaire en mode `inline`. Elle annonce sa hauteur
   au cadre parent (`CARD_HEIGHT_MSG`).
5. La confirmation arrive par deux chemins, qui relisent tous deux la
   transaction par l'API avant de créditer :
   - le webhook signé `POST /api/payments/paddle/webhook` (`transaction.*`) ;
   - le polling `GET /api/payments/{id}` de la fenêtre.
   Le crédit est atomique (UPDATE conditionnel sur `PENDING`) : jamais de double crédit.

Un checkout de forfait fermé avant paiement se rouvre : même offre dans les
15 minutes → même transaction (`_resume_card_plan`) ; autre offre → nouveau
paiement. La garde « forfait en attente » (3 min, 409) ne vise que le Mobile Money.

## Montants

| Zone | Devise Paddle | Conversion |
|------|---------------|------------|
| A (Afrique, XAF) | EUR | XAF ÷ 655,957, arrondi supérieur au centime |
| B | USD | aucune |
| C | EUR | aucune |

La base garde le montant dans la devise de la zone (XAF en zone A).

**Minimum.** Paddle refuse une transaction sous `minimum_payment_amount`
(`GET /currencies`) : 0,65 € et 0,70 $. Pour les **achats de pages**, Précis
applique ce minimum, `MIN_CARD_AMOUNT` (`backend/app/core/pricing.py`) :
427 F, 0,65 €, 0,70 $ net (6 / 6 / 4 pages en zones A / B / C ; la zone A est
encaissée en EUR). Sous ce seuil,
la fenêtre grise le bouton et indique le nombre de pages minimum
(`payment.min_pages_card`), sans modifier la quantité. Le serveur applique la
même règle (`billable_pages(zone, pages, method)`) ; un document payé au-delà
de sa taille crédite le surplus au compte. Les forfaits ne s'arrondissent pas :
ils gardent le seul minimum technique de Paddle, sous tous les prix.

**Frais.** À la charge du client, détaillés dans la fenêtre avant paiement.
Mobile money : `PSP_FEE_PERCENT` (3 %). Carte : tarif Paddle 5 % + 0,50 $
(`CARD_FEE_PERCENT`, `CARD_FEE_FIXED` : 50 c$, 47 c€, 309 F), calculé « grossi »
par `card_fee` pour que le net reçu après commission égale le prix catalogue :
`total = ⌈(net + fixe) × 100 / 95⌉`. Libellé « Frais de paiement par carte »,
sans pourcentage. La TVA éventuelle (`tax_mode: internal`) reste hors calcul ;
voir `docs/etude-frais-carte.md`.

## Configuration

Backend (`backend/.env`) :

| Variable | Rôle |
|----------|------|
| `PAYMENT_METHODS` | contient `card=paddle` |
| `PADDLE_ENV` | `SANDBOX` ou `LIVE` |
| `PADDLE_API_KEY` | clé API serveur (`pdl_sdbx_…` / `pdl_live_…`) |
| `PADDLE_PRODUCT_ID` | produit sans prix (`pro_…`) |
| `PADDLE_WEBHOOK_SECRET` | secret de la destination de notification (`pdl_ntfset_…`) |
| `PADDLE_CHECKOUT_URL` | dev local seulement : `http://localhost:3000/paiement/carte` (Paddle refuse `localhost` comme lien par défaut) |

Front (`frontend/.env`, rebuild nécessaire) : `VITE_PADDLE_ENV`
(`sandbox` / `production`) et `VITE_PADDLE_CLIENT_TOKEN` (jeton public `test_…` / `live_…`).
Les deux côtés doivent viser le même environnement.

En production, les secrets vont dans SSM, jamais dans un fichier suivi.

## Tester en sandbox

- Carte `4242 4242 4242 4242`, date future, CVC quelconque. Refus :
  `4000 0000 0000 0002`. Une vraie carte est refusée en sandbox.
- Sans webhook public, le polling suffit à créditer en local.
- Tests : `backend/tests/test_paddle.py`, `test_paiement_minimum.py`
  (lancés avec le Python du venv, sans pytest).

## Passage en live

1. Compte Paddle live vérifié ; domaine de production approuvé par Paddle.
2. Créer le produit live sans prix → `PADDLE_PRODUCT_ID`.
3. *Checkout settings* : Default payment link `https://<domaine>/paiement/carte`.
4. Notification : `https://<domaine>/api/payments/paddle/webhook`, événements
   `transaction.*` → secret dans `PADDLE_WEBHOOK_SECRET`.
5. Clé API live et jeton client live ; `PADDLE_ENV=LIVE`,
   `VITE_PADDLE_ENV=production` ; retirer `PADDLE_CHECKOUT_URL`.
6. Secrets dans SSM, redémarrage du backend, rebuild du front.
7. Confirmer le tarif du contrat Paddle (`CARD_FEE_PERCENT`, `CARD_FEE_FIXED`)
   et vérifier que le minimum de `GET /currencies` en live reste sous les prix.
8. Paiement réel de faible montant avec une vraie carte, puis remboursement
   depuis le tableau de bord Paddle.
