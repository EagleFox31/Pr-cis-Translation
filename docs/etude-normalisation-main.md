# Étude : normalisation après fusion de main 1.6.2

Suite de la revue des apports de main (#45, #47, #49) : corrections retenues
pour les points 2, 3 et 4 (cf. `PASSATION.md`, section 4b).

## Besoin

1. **Comptage Office/TXT (point 2)** : un fichier sans texte ou un Office
   invalide doit renvoyer une erreur claire (422), aussi lors du paiement d'un
   document, et aucun message ne doit parler de « bêta » hors du programme bêta.
2. **Frais (point 3)** : les frais n'apparaissent **que** dans la fenêtre de
   paiement. Le minimum carte s'aligne sur le vrai minimum de Paddle.
3. **Mentions sous les cartes (point 4)** : en mode Annuel, dire que le
   montant est facturé à l'année ; rappeler la règle de comptage des pages.

## Existant

| Élément | État | Écart |
|---|---|---|
| `payments._document_pages` | appelle `count_pages` sans intercepter `ValueError` | un TXT vide → 500 au devis / à l'encaissement |
| `translate.py` | intercepte déjà `ValueError` → 422 | rien |
| `beta_meter.office_cost` | message « Unsupported beta Office format » (anglais, « beta ») | message neutre en français |
| `GET /system/pricing` | `monthly_total` / `annual_total` = prix **+ frais au taux Mobile Money** | faux pour la carte, et frais hors fenêtre de paiement |
| `PricingCards` | affiche `*_total` (frais compris) | afficher le prix net du forfait |
| `PaymentModal` | seul endroit qui détaille les frais | rien |
| `MIN_CARD_AMOUNT` | 3 000 F / 5 € / 5 $ (seuil économique, 21/10) | décision : minimum Paddle réel |

**Minimum Paddle** (`GET /currencies`, champ `minimum_payment_amount`,
developer.paddle.com, vérifié le 22/10/2026) : **0,65 €** et **0,70 $**, par
transaction, sur le solde à débiter ; au-dessous, erreur
`transaction_balance_less_than_charge_limit`. La zone A étant encaissée en EUR
(XAF ÷ 655,957), 0,65 € = **427 F** (arrondi supérieur). Le seuil s'applique
au net : le montant débité (net + frais) est toujours au-dessus.

## Options

| Option | Pour | Contre |
|---|---|---|
| A. Retirer `*_total` de l'API et afficher `monthly` / `annual` | une seule source de prix, aucun frais hors fenêtre | le prix affiché n'est plus le débit final (les frais s'ajoutent dans la fenêtre, annoncés avant paiement) |
| B. Garder `*_total` et ne plus l'afficher | aucun changement d'API | champ mort, frais Mobile Money appliqués à tort à la carte |

**Choix : A.** Décision produit du point 3 ; un champ inutilisé et faux pour la
carte n'a pas lieu d'être.

## Impacts

- Pas de migration, pas de donnée touchée.
- i18n : clés `pricing.billed_annually_total` (sans « frais inclus ») et
  `pricing.equivalence` rétablies en fr et en.
- Argent : minimum carte abaissé, donc les petits achats par carte redeviennent
  possibles. La part fixe des frais carte pèse plus sur eux (cf.
  `etude-frais-carte.md`), mais ces frais sont à la charge du client et
  annoncés dans la fenêtre.

## Risques

- Un achat carte proche du minimum dont le solde après remise passerait sous
  0,65 € : aucun code de remise n'est utilisé aujourd'hui.

## Hors périmètre

- **Mention du comptage dans les CGU/CGV** : il n'existe pas de page CGU (les
  liens du pied de page pointent sur `#`). À rédiger à part, c'est un texte
  juridique.
