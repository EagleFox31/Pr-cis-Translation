# Étude — Visionneuse, fidélité de la retraduction compacte, originaux côté admin

Date : 20/10/2026 — branche `feat/visionneuse`.

## 1. Besoins

| # | Demande | Constat |
|---|---|---|
| 1 | La visionneuse « bloque les redirections » : il faut cliquer sur Retour pour sortir. | La visionneuse est une surcouche `position: fixed` (`html.preview-active .story-band`, `index.css`). Les liens de la barre (`Accueil`, `Tarifs`…) appellent `handleNavClick` (`Home.tsx`) qui fait défiler la page **sous** la surcouche : rien ne bouge à l'écran. |
| 2 | La molette doit faire passer d'une page à l'autre. | La molette ne sert qu'au zoom (Ctrl + molette). Changer de page : flèches, clavier, vignettes. |
| 3 | Vignettes : remplacer la pastille verte par un signe lisible (bordure verte + coche). | Pastille de 8 px en haut à droite (`StorySection.tsx`, barre latérale) : peu lisible, sens non évident. |
| 4 | Analyse d'une traduction : « In this section we will learn about 4S. » → « Les 4S en bref ». | Voir §3. |
| 5 | Récupérer les documents originaux (admin) pour diagnostiquer un rendu cassé. | `GET /documents/{id}/original` existe mais exige `doc.user_id == user.id` : l'admin ne voit que ses propres fichiers. Aucune page admin ne liste les documents. |

## 2. Existant réutilisé

- `handleBack` (`Home.tsx`) ferme proprement l'aperçu ; `retourVers` choisit déjà la section où l'on revient (`story` / `pricing`).
- Le gestionnaire de molette existe déjà sur `#scroll` (zoom) : on y ajoute la navigation.
- `require_admin` (`core/security.py`), `AdminShell`, et le modèle `admin_users.py` / `AdminUsersPage.tsx` / `useAdminUsers.ts`.

## 3. Analyse de la traduction « Les 4S en bref »

Sur la même page, la légende **dans l'image** est traduite fidèlement (« Dans cette partie, nous allons découvrir les 4S. ») ; seule la ligne de texte sous l'image est résumée.

Cause la plus probable : la **retraduction compacte** (`engines/pdf/translate.py`, `retranslate_overflows`). La traduction fidèle (48 caractères) déborde de la case de la source (39). Le moteur redemande alors une version de *n* caractères au maximum, avec la consigne « ne rien omettre d'**essentiel** ». Le modèle a répondu par un titre de 14 caractères. Le résultat est **accepté sans contrôle** : seules les balises sont vérifiées (`_tags_ok`).

Correctif : un **plancher de fidélité**. Une retraduction compacte plus courte que 60 % de la source est rejetée, et l'on garde la traduction fidèle. Le léger débordement est absorbé par la compression du rendu, comme le prévoit déjà le plancher de budget à 0,92. La consigne passe de « rien d'essentiel » à « ne rien omettre ».

Limite : sans le fichier source, l'hypothèse n'est pas rejouée de bout en bout. Le garde-fou est testé unitairement. Pour confirmer, il faudra retraduire le document en prod après déploiement.

## 4. Options et choix

| Sujet | Options | Choix |
|---|---|---|
| Nav depuis l'aperçu | a) cacher la barre ; b) fermer l'aperçu puis défiler vers la section | **b** : même effet que Retour, puis défilement vers la cible. La traduction continue côté serveur et le document reste dans la bibliothèque. |
| Molette | a) défilement continu de toutes les pages ; b) bord atteint + nouvel élan → page suivante / précédente | **b** : on garde le rendu page par page actuel. Un seuil et une pause de 500 ms évitent de sauter plusieurs pages d'un coup sur un pavé tactile. |
| Vignettes | bordure verte + coche ronde ; bleu = page affichée (anneau) ; spinner = en cours ; grisé = en attente | retenu |
| Originaux admin | a) ouvrir `/documents/{id}/original` à l'admin ; b) routes dédiées `/api/admin/documents` + page `/admin/documents` | **b** : la route utilisateur garde sa règle de propriété. Chaque téléchargement admin est journalisé (qui, quel document). |

## 5. Impacts et risques

- Données : aucune migration.
- Sécurité / confidentialité : l'admin accède aux fichiers des clients. Protections : `require_admin` et une trace dans les logs. **À trancher** : en informer les clients dans la politique de confidentialité.
- i18n : nouvelles clés fr/en (page admin, infobulles des vignettes).
- Risque molette : un geste trop sensible. Mitigé par le seuil, la pause et la condition « bord atteint ».
