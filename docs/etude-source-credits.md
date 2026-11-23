# Étude : source des crédits, téléchargement et filigrane

## Besoin
Les conditions d'utilisation (pages légales, commit e169e8b) annoncent :

| Source des pages | Aperçu | Téléchargement |
|---|---|---|
| Pages gratuites du forfait Gratuit | filigrané | non |
| Crédits bêta (même sur un compte payant) | filigrané (mention promotionnelle) | oui |
| Forfait payant, pages achetées à l'unité | en clair | oui |

## Existant
- Droit au clair et au téléchargement : `_may_read_clear(user, doc) = is_paid_plan(plan) or doc.paid` (`backend/app/api/documents.py`).
- `translate.py` pose `doc.paid = True` pour **toute** traduction couverte, pages gratuites comprises (choix du commit #45, `docs/free-document-trial.md`) et bêta comprise.
- Exemple concret de l'écart : un compte gratuit traduit 3 pages avec ses pages offertes → aujourd'hui il télécharge le fichier sans filigrane. Un abonné Pro qui utilise ses crédits bêta → aperçu en clair, sans mention.
- Le filigrane est intégré aux pixels (`rasterize_for_trial`), côté serveur ; le frontend verrouille la carte si `trial && !doc.paid`.
- Chaque document bêta porte déjà `reglages["beta"] = true` (depuis 64f5ffb).

## Options pour reconnaître un document bêta
| Option | Pour | Contre |
|---|---|---|
| A. `reglages["beta"]` | déjà écrit, aucune requête, aucune migration | absent des documents bêta plus anciens que 64f5ffb |
| B. ligne `BetaUsage` non remboursée | source comptable | une requête de plus à chaque aperçu |
| C. nouvelle colonne (migration 0019) | explicite | migration + reprise des données pour un gain nul |

**Choix : A.** Les anciens documents gardent leur état (pas de changement rétroactif, comme pour les anciens aperçus verrouillés).

## Règles retenues
- `doc.paid` = « téléchargeable ». Branche quota : `paid = not gratuit or achetees > 0`. Bêta : `paid = True` (inchangé). Paiement ciblé : inchangé.
- Nouveau critère d'aperçu : filigrané si pas de droit au clair **ou** document bêta. Appliqué à `/documents/{id}/preview` (partiel et complet) et `/api/translate/partial`. Le téléchargement (`/download`, `/api/translate/result`) reste sur `_may_read_clear`.
- Format non-PDF : le refus 402 de l'aperçu ne vise que les documents non téléchargeables ; un document bêta non-PDF est rendu en PDF puis filigrané.

## Point à trancher (défaut appliqué)
Document **mixte** (ex. 2 pages gratuites + 3 pages achetées) : **téléchargeable**, car l'utilisateur a payé une partie ; sinon il devrait repayer tout le document pour le débloquer. Inconvénient : les 2 pages gratuites sortent en clair.

## Impacts
- Aucune migration. Sécurité : la règle reste appliquée par le serveur.
- `docs/free-document-trial.md` et les tests du #45 sont mis à jour.
- Risque : le cache de rendu en clair n'est jamais servi à un aperçu filigrané (même garde `clear` qu'avant).
