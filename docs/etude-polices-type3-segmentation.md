# Étude : polices Type3 sans nom et texte découpé lettre par lettre (moteur PDF)

## Besoin

Le CV exporté depuis Chrome (« Imprimer → PDF », producteur Skia) se traduit avec une structure juste, mais le contenu est faux :

- le sens est perdu : « Français · Courant » devient « Fluent · Pro » ;
- le gras et l'italique disparaissent ;
- les polices changent au milieu d'un mot ;
- les lettres sont espacées (« P r a c t i c e s ») ;
- certains mots sont coupés ou dupliqués.

Il faut consolider le moteur pour tous les PDF qui ont ce profil, sans retouche propre à ce document.

## Diagnostic de A à Z (rejoué en local)

| Étape | Ce qui se passe | Effet visible |
|---|---|---|
| 1. Extraction | Skia écrit des polices **Type3**. MuPDF les nomme « Type3 (12 0 R) » avec `flags=0`, alors que le vrai nom (Inter-Bold, Lora-Italic…) se trouve dans le `/FontDescriptor`. Skia répartit aussi **une seule police sur plusieurs objets** : dans « Frontend », les lettres alternent entre les objets 12, 16 et 17. | Le gras et l'italique sont perdus dès l'extraction. |
| 2. Balisage (`tagging.style_sig`) | La signature de style contient ce nom d'objet. Chaque changement d'objet ouvre donc un nouveau segment : `[[0]]F[[/0]][[1]] l[[/1]]…` | Le texte part au modèle en fragments de lettres. |
| 3. Traduction | Le modèle doit remplir des cases d'une ou deux lettres et recompose le sens au hasard. | Contresens, mots coupés ou dupliqués. Le résultat change d'un passage à l'autre. |
| 4. Rendu | Chaque objet reçoit une police de repli « proche » différente (Merriweather, Montserrat, Poppins…), toujours en Regular. | Polices mélangées, lettres espacées. |

**Preuve.** Un prototype restaure seulement le nom réel et le gras/italique depuis le descripteur, sans rien toucher d'autre. Le même CV ressort alors juste : « French · Fluent », gras et italique fidèles, police unique, plus d'espacement lettre par lettre.

**Défauts restants après le prototype (causes distinctes) :**

- les exposants (« 1re », « 2e ») se superposent au chiffre suivant. Ils sont déjà abîmés à l'aller-retour sans traduction : le défaut vient de l'extraction ou du rendu, pas de la traduction ;
- le bloc « Practices » est justifié et étiré alors que l'original est aligné à gauche (défaut de reflow).

## Existant concerné

- `engines/pdf/engine.py` `_span_dict` : reprend `font`, `flags`, `bold` et `italic` tels que MuPDF les donne ;
- `engines/pdf/tagging.py` `style_sig` : la signature inclut le nom de police ;
- `engines/pdf/polices.py` : le résolveur choisit la police par nom, avec Inter, Lora, etc. préchargées ;
- `tests/test_engine_v2_generic.py` : PDF synthétique, 77 contrôles, sans aucun cas Type3.

## Options

| Option | Pour | Contre |
|---|---|---|
| A. Lire le `/FontDescriptor` de toute police Type3 dans `_span_dict` (nom sans préfixe de sous-ensemble ; gras si `FontWeight` ≥ 600 ou si le nom l'indique ; italique si `ItalicAngle` ≠ 0, `Flags`&64 ou si le nom l'indique), avec un cache par objet | Corrige la cause à la source, pour toutes les étapes à la fois (balisage, traduction, rendu). Ne coûte rien. Validé par le prototype. | Une police Type3 sans descripteur (bitmap ancien) reste inchangée. |
| B. Garde-fou du balisage : ne jamais couper un mot sur la seule identité de police quand la taille, la couleur, le gras et l'italique sont identiques | Couvre aussi les Type3 sans descripteur et tout éclatement d'une police en sous-ensembles | À lui seul, il ne rend pas le gras et l'italique |
| C. Corriger dans le rendu seulement | — | Trop tard : la traduction est déjà faussée |

**Recommandation : A + B.** A répare la cause. B est le filet de sécurité générique. Il faut aussi :

- ajouter au PDF synthétique un cas « une police Type3 répartie sur plusieurs objets, avec descripteur » ;
- incrémenter `engines/pdf/version.py`, car des pixels changent (clé de cache).

Les exposants et la justification sont traités ensuite, un problème à la fois.

## Impacts et risques

- Pas de données, pas de migration. Coût nul : une lecture d'objet PDF par police et par document.
- Risque : une police Type3 dont le descripteur ment. Le garde-fou B limite alors les dégâts.
- Le rapport annuel est traité dans la section suivante.

## Rapport annuel (Word 2016, 19 pages)

Cas testé : `Rapport_annuel_test.pdf` traduit en anglais. Trois versions ont été comparées : l'original, un aller-retour sans traduction (même chaîne, texte recopié tel quel) et la version produite par l'app.

Polices de l'original : Calibri, Calibri gras, Calibri italique, Arial et Symbol, toutes intégrées au PDF en sous-ensembles. Il n'y a **aucune police Type3** : la cause trouvée pour le CV ne joue pas ici.

| # | Défaut constaté | Exemple | Étape responsable | Gravité |
|---|---|---|---|---|
| R1 | Sommaire : les numéros de page ne sont plus alignés à droite, et les entrées plus longues rétrécissent | « Open day » s'arrête au milieu de la ligne ; « 40th anniversary celebration » passe de 11 à 9,3 pt. Même sans traduction, la dernière entrée passe à 10,9 pt et son numéro se décale. | Reflow : la ligne de points de conduite est traitée comme du texte ordinaire et le nombre de points est recopié au lieu d'être recalculé. Seul le sommaire sans points est géré (`engine._split_trailing_numbers`). | Structure |
| R2 | Deux polices dans une même page (Calibri et Carlito) | Page 3 : 2 557 caractères en Carlito contre 127 en Calibri | Rendu : le sous-ensemble Calibri du PDF ne contient que les lettres du texte français. Il en manque pour l'anglais, donc `_pick_font` échoue et le serveur (sans Calibri installé) se rabat sur le clone Carlito. Ce choix se fait ligne par ligne. | Aspect |
| R3 | Tableaux : toute une colonne rétrécit à cause de son en-tête | « Variance % », plus long que « Écart % », fait passer toutes les valeurs de la colonne de 9,5 à 8 pt (6,5 pt page 14), alors qu'elles tiendraient | Reflow des tableaux : une taille commune est appliquée à la colonne | Aspect |
| R4 | Coupures de lignes différentes de l'original, même sans traduction | « tri-mestrielle » est coupé alors que Word ne coupait pas ; la citation est coupée un mot plus loin | Reflow : la césure est active même quand l'original n'en avait aucune, et la largeur d'un paragraphe centré est estimée à partir de ses lignes | Finition (le texte traduit change de toute façon les coupures) |
| R5 | Le trait d'union « - » devient le caractère « ‐ » (U+2010) | « -12,2% » ne se retrouve plus par recherche, et le copier-coller change | Rendu : correspondance glyphe → caractère lors de l'écriture | Finition (invisible à l'écran) |

Ce qui est conforme : aucun mot perdu, aucun texte hors de la page, justification conservée, même nombre d'images et de dessins sur chaque page.

### Options

| Défaut | Option recommandée | Autre option |
|---|---|---|
| R1 | Reconnaître la ligne « texte, points, numéro » et la recomposer : texte traduit à gauche, numéro calé sur le même bord droit que l'original, points recalculés pour remplir l'écart. Pas de réduction de taille tant que le texte tient en laissant au moins 3 points. | Garder la taille d'origine et couper sur deux lignes les entrées trop longues. Plus fidèle à Word, mais le sommaire s'allonge. |
| R2 | Une seule police par famille dans tout le document : si une partie de la traduction exige le clone, tout le texte de cette famille utilise le clone. Le document reste homogène. | Garder Calibri partout où il suffit (situation actuelle) : plus proche de l'original par endroits, mais le mélange se voit. |
| R3 | Réduire seulement la cellule qui déborde (ici l'en-tête), pas toute la colonne. | Passer l'en-tête sur deux lignes si la ligne d'en-tête a la hauteur nécessaire. |
| R4, R5 | Corriger après R1 à R3 : césure seulement si l'original en contient, et caractère « - » conservé. | — |

**Recommandation** : traiter dans cet ordre R1 (structure), puis R2 et R3 (aspect), puis R4 et R5 (finition), un défaut à la fois, chacun avec son test sur le PDF synthétique et un incrément de `engines/pdf/version.py`.

**Confirmation avec la version actuelle du code** (traduction locale réelle, `local.pdf`) :

- R1 est en grande partie corrigé : « Open day » est à 11 pt avec son numéro aligné à droite. Il reste « 40th anniversary celebration » à 10,9 pt, dont le numéro est décalé de 5 pt. La version de l'app était plus ancienne.
- R2 se reproduit aussi sur Windows, page 3 : 2 586 caractères en Carlito contre environ 70 en Calibri.
- R3 se reproduit : la colonne passe à 8,3 pt.
