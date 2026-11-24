# Étude — l'unité « page » partout

Date : 23/11/2026. Demande : l'application n'affiche plus jamais de « mots », seulement des pages. Là où c'est utile, une remarque explique la règle de calcul.

## 1. Ce qui existe aujourd'hui

Deux mondes coexistent.

**Les forfaits payants comptent déjà en pages.** Une page de PDF vaut une page, une diapositive vaut une page. Word, Excel et texte valent une page par tranche de 500 mots entamée (`WORDS_PER_PAGE = 500`, `backend/app/services/documents.py:44`). Depuis l'étape 3 de la mission « pages payées », Word compte ses vraies pages (conversion LibreOffice). Le compte en mots ne sert plus que de secours si la mise en page ne peut pas être lue.

**Le programme Bêta compte en mots pour Word et Excel.** Les quotas sont enregistrés tels quels en base (colonne `limits` des campagnes et des accès, `backend/app/models/beta.py`) :

| Format | Quota Bêta actuel | Unité enregistrée |
|---|---|---|
| PDF | 20 | pages |
| PowerPoint | 20 | diapositives |
| Word | 10 000 | **mots** |
| Excel | 10 feuilles et 5 000 | feuilles et **mots** |

Le calcul se trouve dans `backend/app/services/beta_meter.py` (`office_cost`, `word_count`).

### Où le mot « mots » apparaît à l'écran

- **Page Tarifs** (`PricingCards.tsx:292-296`) : « Une page tous les 500 mots entamés » et « un document Word de 1 200 mots compte pour 3 pages ». C'est déjà la remarque souhaitée, mais le texte cite Word, qui compte désormais ses vraies pages.
- **Panneau du compte et bibliothèque** (`AccountPanel.tsx:179`, `BetaAllowances.tsx:21,38`) : « Il vous reste 9 200 mots », « 9 200 mots restants sur 10 000 ».
- **Page Bêta, offre et fiche du programme** (`BetaPage.tsx:127`, `BetaOffer.tsx:16`, `BetaProgramDetails.tsx:34-36`) : « Word : 10 000 mots », « Excel : 10 feuilles · 5 000 mots », « Word est compté en mots ».
- **Administration Bêta** (`AdminBetaPage.tsx:90-92`) : champs « Word — mots » et « Excel — mots cumulés ».
- **Courriel d'invitation Bêta** (`backend/app/core/email.py:688-704`, `email_content.py:226-250`) : « Word : 10 000 mots », « Excel : 10 feuilles, 5 000 mots au plus ».
- **Textes de langue** : clés `account.balance_words_*`, `account.qty_words_*`, `beta.left.words_*`, `beta.units.words`, `beta.limit_labels.docx/xlsx_words`, `beta.public.excel`, `beta.quota_hint`, `pricing.units.*` (fr et en).

Les autres occurrences de « mots » relevées (mots de passe, textes de la page d'accueil comme « le sens avant le mot à mot », commentaires du code) ne parlent pas de quantité. Elles restent telles quelles.

## 2. Le vrai sujet : la Bêta

Côté forfaits payants, il suffit de reformuler la remarque. Côté Bêta, c'est plus délicat, parce que les quotas sont réellement enregistrés en mots.

Exemple concret. Un testeur Bêta dépose un rapport Word de 3 pages courtes, soit 1 200 mots.
- Aujourd'hui, son solde passe de « 10 000 mots » à « 8 800 mots ».
- La bibliothèque annonce pourtant le document comme faisant 3 pages.

## 3. Options

### Option A — Afficher en pages, garder les mots en coulisse

Le quota reste enregistré en mots. L'écran divise par 500 : « 10 000 mots » devient « 20 pages ».
- Effet visible : le testeur voit son solde passer de « 20 pages » à « 18 pages » (8 800 ÷ 500 = 17,6, arrondi à 18). Le document affiche pourtant « 3 pages ». Les chiffres ne tombent pas juste, et un utilisateur attentif le remarquera.
- Avantages : aucun changement en base, rapide.

### Option B — Passer vraiment la Bêta en pages (recommandée)

Le quota Word et Excel est enregistré en pages. Le décompte suit exactement la règle des forfaits payants : vraies pages pour Word, 500 mots par page pour Excel et texte.
- Effet visible : le testeur voit « 20 pages », dépose 3 pages, il lui reste « 17 pages ». Tout tombe juste et c'est la même règle partout.
- Travail : conversion des quotas existants en base (10 000 mots → 20 pages, 5 000 mots Excel → 10 pages, consommations déjà faites converties de la même façon, arrondi à la page supérieure), mise à jour du compteur Bêta, de l'administration et du courriel d'invitation. Cette option touche des données : revue par un auditeur avant de la déclarer terminée.

### Sous-question — les feuilles Excel et les diapositives

La demande vise les « mots ». Deux autres unités s'affichent encore :
- **Diapositives** : les tarifs disent déjà qu'une diapositive vaut une page. Afficher « 20 pages » au lieu de « 20 diapositives » unifie tout sans rien changer au calcul. *Recommandé.*
- **Feuilles Excel** : la Bêta limite aussi Excel à 10 feuilles. On peut garder cette limite en plus des pages (« 10 pages, 10 feuilles au plus »), ou la retirer pour n'avoir qu'une seule unité. *Recommandé : la retirer*, car les forfaits payants ne l'ont pas.

## 4. La remarque d'explication

Texte proposé, affiché sous les quotas (Tarifs, page Bêta, panneau du compte) :

> Pour les documents Excel et texte, le nombre de pages est calculé selon la règle 1 page = 500 mots. Cette règle s'applique aussi à un document Word dont la mise en page ne peut pas être lue.

L'exemple actuel de la page Tarifs (« un document Word de 1 200 mots ») devient : « Par exemple, un fichier Excel de 1 200 mots compte pour 3 pages. »

## 5. Ordre avec la mission « pages payées »

Les étapes 1 à 4 de la mission sont faites mais pas encore commitées. Il reste l'étape 5 (aperçu et téléchargement partiel Word/PowerPoint) et l'étape 6 (tests et recette).

**Recommandé : terminer d'abord les étapes 5 et 6, puis faire l'unité « page » à la suite, dans une PR séparée.** Les deux chantiers touchent les mêmes fichiers de langue. Les mélanger rendrait la recette plus difficile à suivre. En les séparant, chaque PR reste lisible.

## 6. Plan (option B)

1. Compteur Bêta en pages : `office_cost` renvoie des pages (Word : `pages_word`, sinon mots ÷ 500), unités `docx`/`xlsx` = pages.
2. Conversion des quotas et consommations Bêta existants (script de migration, essayé d'abord sur la base de test).
3. Écrans : panneau du compte, bibliothèque, page Bêta, offre, fiche programme, administration ; diapositives affichées en pages.
4. Courriel d'invitation Bêta (fr et en).
5. Remarque d'explication et exemple de la page Tarifs.
6. Tests (compteur, migration, courriel) et recette navigateur : aucun « mots » visible.
