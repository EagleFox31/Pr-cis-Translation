# Étude — Téléchargement des pages payées, aperçu partiel des formats Office, tremblement

Date : 23/11/2026. Origine : recette du 23/11, compte gratuit (5 pages offertes par mois).

## 1. Besoin

1. **Télécharger les pages payées.** Exemple : un PDF de 3 pages, dont 2 sont payées par l'offre gratuite. Aujourd'hui, « Télécharger » envoie vers les tarifs. Il faut plutôt prévenir le client que la page 3 ne sera pas dans le fichier, lui donner les pages 1 et 2, et lui proposer d'acheter le reste.
2. **Aperçu partiel pour Word, PowerPoint, Excel et texte.** Sans pages restantes, un PDF montre un aperçu filigrané. Les autres formats affichent seulement « Pages insuffisantes ».
3. **Compter les vraies pages d'un Word**, au lieu de les estimer par tranches de 500 mots.
4. **Livrer un Word qui ne contient que les pages payées**, si c'est faisable. Sinon, livrer un PDF de ces pages.
5. **Tremblement** d'un aperçu non payé.

## 2. État de l'existant

| Sujet | Où | Constat |
|---|---|---|
| Bouton « Télécharger » | `frontend/src/components/preview/ViewerToolbar.tsx:356` | Sur un forfait gratuit, le bouton ouvre les tarifs sans rien demander au serveur. |
| Fenêtre « Acheter / Continuer » | `frontend/src/components/library/TelechargementLibres.tsx` | Elle existe déjà. Le solde paie d'abord ce qu'il peut. S'il reste des pages non payées, la fenêtre propose « Acheter » ou « Continuer » (fichier limité aux pages payées). Elle sert à la bibliothèque et à l'accueil. Un compte gratuit n'y arrive jamais, à cause de la ligne ci-dessus. |
| Fichier limité aux pages payées | `backend/app/api/documents.py:428-432` | Le serveur sait déjà retirer les pages non payées (`sans_libres=1`), mais **seulement pour un PDF**. |
| Aperçu filigrané sans solde | `backend/app/api/translate.py:334` | Il ne s'applique qu'aux PDF. |
| Traduction partielle (ne traduire que les pages couvertes) | `backend/app/api/translate.py:566` | Possible pour PDF et PowerPoint seulement. |
| Comptage des pages | `backend/app/services/documents.py:144` | PDF : vraies pages. PowerPoint : diapositives. Word, Excel et texte : 1 page par tranche de 500 mots. |
| Outil de conversion en PDF | `backend/app/services/office.py` | L'outil qui fabrique déjà l'aperçu des fichiers Word donne le vrai nombre de pages. |

## 3. Options

### 3.1 Téléchargement des pages payées (point 1)

| Option | Pour | Contre |
|---|---|---|
| **A. Faire passer le compte gratuit par la fenêtre existante** | Peu de code, côté écran seulement. Comportement identique à celui d'un abonné. | Aucun. |
| B. Créer une fenêtre propre à l'essai | — | Deux écrans pour le même besoin (contraire à la règle du projet). |

**Choix : A.** Quand le document a au moins une page payée, le bouton passe par la fenêtre. Le texte de la fenêtre annonce clairement : « N page(s) verrouillée(s) ne seront pas dans le fichier ». Le bouton « Acheter » mène aux tarifs.

**Sans aucune page payée**, le client n'est jamais envoyé aux tarifs sans explication. La même fenêtre s'ouvre avec un autre texte : « Aucune page de ce document n'est encore payée. Le fichier sera disponible après l'achat de N page(s). » Deux boutons : « Voir les tarifs » (le seul qui mène aux tarifs) et « Fermer », qui le laisse sur son aperçu.

### 3.2 Comptage des pages Word (point 3)

| Option | Pour | Contre |
|---|---|---|
| **A. Vraies pages, obtenues en convertissant le fichier en PDF au dépôt** | Le nombre facturé est celui que le client voit dans l'aperçu. Word rejoint le PDF et le PowerPoint. | Quelques secondes de plus au dépôt (la conversion sert ensuite à l'aperçu, on la garde). Avec d'autres polices, le nombre peut différer d'une page de ce qu'affiche Word. |
| B. Garder le comptage par mots | Rien à changer. | Un Word de 2 pages avec de grandes images compte 1 page, alors que l'aperçu en montre 2. |

**Choix : A pour Word.** Excel et texte gardent le comptage par mots, car ils n'ont pas de vraies pages : une feuille large sort sur 15 pages à l'impression. Si la conversion échoue, on revient au comptage par mots.

### 3.3 Word limité aux pages payées (point 4)

Méthode envisagée :
1. On convertit la traduction en PDF.
2. On repère où commence la première page non payée.
3. On retrouve le paragraphe correspondant dans le fichier Word.
4. On coupe le document juste avant ce paragraphe, en gardant sa mise en page.

| Cas difficile | Règle |
|---|---|
| Paragraphe à cheval sur deux pages | On coupe avant ce paragraphe : le client ne reçoit jamais plus que ce qu'il a payé. |
| Tableau à cheval sur deux pages | On coupe avant le tableau, sauf s'il fait plus d'une page. Dans ce cas, on coupe entre deux lignes du tableau. |
| Image flottante, en-tête, pied de page, notes | À vérifier sur le prototype. |

**Décision :** on fait d'abord un prototype sur les deux fichiers Word de test (texte, puis texte et images). Si la coupe est juste sur les deux, on livre un Word. Sinon, on livre un PDF des pages payées, comme vous l'avez validé.

### 3.4 Aperçu partiel des formats Office (point 2)

L'aperçu filigrané s'étend à **Word** quand ses pages sont comptées comme au point 3.2, et à **PowerPoint**, déjà compté par diapositive. Le moteur traduit tout le document. Les pages payées s'affichent en clair, les autres sous le voile, comme pour un PDF.

**Excel et texte** gardent « Pages insuffisantes ». Sans vraies pages, on ne peut pas dire quelle partie est payée.

## 4. Tremblement (point 5)

**Votre observation :** l'écran tremble au chargement, quand le voile gris apparaît, puis il se stabilise une fois la traduction terminée.

**Piste dans le code** (`frontend/src/components/preview/PdfViewer.tsx`, autour de la ligne 599) : pendant l'attente, le cadre de la page traduite reçoit une taille minimale (320 × 300). Il reprend la taille de la page dès qu'elle est dessinée. Si une barre de défilement apparaît ou disparaît à ce moment-là, la largeur change, la page est redessinée à une autre échelle, et la barre peut à nouveau changer : l'écran oscille jusqu'à ce que la page soit fixée.

**Méthode :** filmer le chargement d'une page non payée et relever la largeur du cadre à chaque image. Si la piste se confirme, on donne au cadre la taille de la page originale dès le départ, pour que rien ne bouge.

## 5. Impacts

- **Données :** aucune migration. Le nombre de pages Word est enregistré comme avant.
- **Facturation :** le nombre de pages d'un Word peut changer, à la hausse ou à la baisse. C'est le prix qui s'affiche avant de traduire, donc aucune surprise après coup.
- **Performance :** une conversion de plus au dépôt d'un Word, réutilisée ensuite par l'aperçu.
- **Traductions de l'interface :** une nouvelle phrase en français et en anglais pour la fenêtre (« N page(s) verrouillée(s) ne seront pas dans le fichier »).
- **Sécurité :** le serveur reste seul juge des pages livrées. L'écran ne fait que transmettre la demande.

## 6. Plan

1. Tremblement : le reproduire au chargement, le corriger, vérifier dans le navigateur.
2. Téléchargement des pages payées pour un compte gratuit : passer par la fenêtre existante et ajouter la note.
3. Comptage réel des pages Word, avec retour au comptage par mots en cas d'échec.
4. Prototype « Word limité aux pages payées » : on garde cette solution si la coupe est juste, sinon on livre un PDF des pages payées.
5. Aperçu filigrané et téléchargement partiel pour Word et PowerPoint.
6. Tests et recette dans le navigateur, avec le compte gratuit et le compte payé.
