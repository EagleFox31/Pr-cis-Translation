# Étude préalable — Frais propres au paiement par carte (Paddle)

*20/10/2026 — branche `feat/paiement-paddle`*

## 1. Besoin et contraintes

Les frais de transaction sont à la charge du client (décision du 20/10/2026),
annoncés avant paiement, et le montant débité est exactement celui affiché.
Aujourd'hui un seul taux, `PSP_FEE_PERCENT = 3`, s'applique à tous les moyens.
Il correspond au mobile money (Fapshi / Campay), pas à la carte : Paddle
facture **5 % + 0,50 $ par transaction** (tarif public, à confirmer sur le
contrat du compte). Le 3 % actuel ne couvre donc pas le coût réel de la carte,
surtout sur les petits montants où la part fixe domine.

Contraintes :
- Calcul en unités mineures, entiers seulement, arrondi en faveur de Précis
  (convention de `transaction_fee`).
- Le devis (`/quote`, `/plan/quote`) et l'encaissement (`/collect`, `/plan`)
  doivent produire le même montant.
- Zone A facturée en euros par Paddle (XAF → EUR, `paddle_amount`), B en USD,
  C en EUR.
- `tax_mode: "internal"` : la TVA éventuelle est **comprise** dans le montant
  débité et retenue par Paddle (marchand officiel). Elle dépend du pays de la
  carte, connu seulement au checkout : elle ne peut pas entrer dans le devis.

## 2. Existant

| Élément | Rôle | Impact |
|---|---|---|
| `pricing.PSP_FEE_PERCENT`, `transaction_fee(amount)` | frais unique 3 % | à paramétrer par moyen |
| `payments._with_fee(subtotal)` | détail `subtotal / fee / amount` | prend le moyen en argument |
| `/quote` | bloc `card` (pages, frais, minimum) | frais carte dans ce bloc |
| `/plan/quote`, `_plan_offer` | prix d'abonnement, sans notion de moyen | ajouter un bloc `card` comme `/quote` |
| `/collect`, `/plan` | encaissement | frais du moyen choisi |
| `MIN_CARD_AMOUNT` (427 F / 0,70 $ / 0,65 €) | minimum Paddle, sur le **net** | à relever si le seuil technique n'est plus le bon |
| `system.py` → `fee_percent` | libellé « Frais de transaction (3 %) » | libellé carte distinct |
| `PaymentModal.tsx:372-377` | ligne frais du récapitulatif | lire le taux dans le devis |
| `test_abonnements.py:140` | `net + transaction_fee(net)` | signature à adapter |

## 3. Ordres de grandeur (part fixe 0,50 $ ≈ 0,47 € ≈ 309 F)

| Achat | Net | Coût Paddle réel | Frais client actuels (3 %) | Perte par vente |
|---|---|---|---|---|
| 6 pages zone A (minimum carte) | 450 F | ~332 F (74 %) | 14 F | ~318 F |
| 50 pages zone A | 3 750 F | ~502 F (13 %) | 113 F | ~389 F |
| Pro mensuel zone C | 19,90 € | ~1,50 € (8 %) | 0,60 € | ~0,90 € |

Hors TVA, qui réduit encore le net en zone C et partout où Paddle la collecte.

## 4. Options

| Option | Pour | Contre |
|---|---|---|
| **A. Frais carte = 5 % + part fixe, à la charge du client** (le client paie `net + ⌈(net + fixe) × 5 / 95⌉ + fixe`, pour que Précis touche son net) | Précis touche toujours son net, cohérent avec la décision « frais à la charge du client » | Petits achats chers par carte (6 pages : 792 F au lieu de 464 F) ; ligne de frais visible et dissuasive |
| **B. Frais carte = 5 % + fixe, et minimum carte relevé** (ex. 3 000 F / 5 € / 5 $ net) | Part fixe diluée (< 15 %) ; les petits achats restent sur mobile money | Un client sans mobile money doit acheter plus |
| **C. Taux carte unique en pourcentage** (ex. 8 %), part fixe absorbée | Affichage simple « 8 % » | Perte sur les petits montants, gain sur les gros : approximation |
| **D. Statu quo 3 %** | Rien à coder | Perte systématique, jusqu'à 70 % du net |

## 5. Choix recommandé : **A + B**

- Frais carte = taux + part fixe (`CARD_FEE_PERCENT = 5`,
  `CARD_FEE_FIXED = {"USD": 50, "EUR": 47, "XAF": 309}`), calculés « grossis »
  pour que le net reçu après commission Paddle égale le prix catalogue.
- Minimum carte relevé à un seuil économique où les frais restent sous ~15 %
  du net (proposé : 3 000 F / 5 € / 5 $), au-dessus du minimum technique Paddle
  qui reste vérifié.
- Mobile money inchangé (3 %).
- La fenêtre affiche « Frais de paiement par carte » avec le montant, sans
  pourcentage (la part fixe le rendrait faux).
- Le taux et la part fixe sont des constantes de `pricing.py`, ajustables
  quand le contrat Paddle sera confirmé ; la TVA reste hors calcul (cf. §7).

## 6. Impacts

- **Données** : aucune migration ; `Payment.amount` porte déjà le montant
  débité frais compris.
- **API** : `/quote` et `/plan/quote` gagnent un bloc `card` complet ;
  `/api/pricing` expose les frais carte pour la grille.
- **Front** : `PaymentModal` (ligne frais, bloc carte pour les forfaits),
  i18n fr/en (`payment.fee_card`).
- **Tests** : `test_paiement_minimum`, `test_abonnements`, `test_paddle` ;
  nouveaux cas : frais carte, arrondi, minimum relevé, cohérence devis /
  encaissement.
- **Sécurité / argent** : le serveur recalcule toujours le montant ; aucun
  chiffre du navigateur n'entre dans le prix.
- **Doc** : `docs/paiement-carte-paddle.md` (section *Frais*, checklist live).

## 7. Risques

- Tarif Paddle réel différent (contrat négocié, frais de change, paiements
  internationaux) : constantes à mettre à jour avant le live.
- TVA retenue par Paddle (`tax_mode: internal`) : le net réel est plus bas que
  le prix catalogue là où elle s'applique. Passer en `external` ferait afficher
  au client un montant majoré au checkout, contraire à « le montant débité
  reste celui affiché ». Laissé tel quel ; à revoir avec le comptable.
- Part fixe convertie en EUR / XAF à un taux figé : à réviser si le dollar
  bouge fortement.

## 8. Décisions (21/10/2026)

1. Modèle **A + B** retenu.
2. Minimum carte **3 000 F / 5 € / 5 $ net**, pour les **achats de pages**
   seulement (zone A : 40 pages, B : 42, C : 27 ; surplus crédité au compte).
   Un forfait ne s'arrondit pas : Starter mensuel (1 500 F, 4,90 $) serait
   bloqué par carte. Les forfaits gardent donc le seul minimum technique de
   Paddle (0,65 € / 0,70 $, sous tous les prix) et paient les frais réels.
   *Révisé le 22/10/2026* : le minimum des achats de pages est ramené au seul
   minimum Paddle (427 F / 0,65 € / 0,70 $, soit 6 / 6 / 4 pages) ; voir
   `docs/etude-normalisation-main.md`.
3. Tarif **5 % + 0,50 $** pris comme référence ; part fixe en EUR fixée à
   0,47 € (309 F) pour couvrir les variations du dollar.
