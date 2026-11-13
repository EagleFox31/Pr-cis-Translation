# Étude : ergonomie de la visionneuse avant / après

## Existant (lu dans le code)
- **Barre d'outils** (`ViewerToolbar.tsx`), de gauche à droite :
  - retour ;
  - zoom −, % et + (de 50 à 300 %, par pas de 25 %) ;
  - nom du fichier source → nom du fichier traduit, avec une pastille de langue ;
  - progression, pause et annulation ;
  - agrandir ;
  - signaler un problème ;
  - télécharger l'original ;
  - télécharger la traduction ;
  - flèches de page avec « n / N ».
- **Colonne de vignettes** (`StorySection.tsx`) : l'état de chaque page est lisible (prête, en cours, illisible, hors sélection).
- **Deux panneaux** (`PdfViewer.tsx`) : original et traduction côte à côte, empilés pour un format paysage. Une bascule « original / traduction » existe (`cv-bascule`).
- **Lecture page par page** : la molette sert à défiler, puis à changer de page (correctif 8521d22).

## Comparaison aux meilleurs outils
Outils pris comme référence : traduction de documents DeepL et Google, comparaison de fichiers Acrobat, éditeurs Smartcat et Phrase.

| Point | Référence | Précis aujourd'hui | Écart |
|---|---|---|---|
| Zoom « ajusté » | « Pleine page » et « Largeur » à un clic, et c'est le réglage par défaut | Pourcentage seulement | **Fort** : on tâtonne pour faire tenir deux pages |
| Lecture | Défilement continu de toutes les pages | Page par page | Moyen : c'est la cause du saut de page ressenti à la molette |
| Lien source ↔ traduction | Survoler un paragraphe éclaire son pendant de l'autre côté (Smartcat, Phrase) | Aucun | **Fort** : c'est le moyen le plus rapide de vérifier une traduction |
| Contrôle de mise en page | Rideau ou superposition (Acrobat) | Côte à côte seulement | Moyen : c'est pourtant l'argument « PAO » de Précis |
| Aller à une page | Champ « page » où l'on tape un numéro | Flèches seulement | Faible, mais pénible sur 100 pages |
| Raccourcis | Aide « ? » visible | Raccourcis présents mais cachés | Faible |
| Recherche | Ctrl+F dans la traduction | Aucune | Moyen |
| Libellés des panneaux | Restent visibles au défilement | À vérifier sur écran | — |

## Améliorations proposées (par effet visible, de la plus rentable à la moins rentable)
1. **Boutons « Pleine page » et « Largeur »**, avec « Pleine page » par défaut. À l'ouverture, les deux pages tiennent entières à l'écran, sans réglage. *Petit chantier, front seul.*
2. **Champ de page** : on clique sur « 3 / 42 », on tape 17 et on y est. *Petit chantier.*
3. **Défilement continu**, en option : les pages s'enchaînent comme dans un lecteur PDF. Les deux colonnes défilent ensemble, et la vignette suit. *Chantier moyen.* Il rend le geste de molette naturel.
4. **Rideau de comparaison** : un curseur qu'on glisse fait apparaître la traduction par-dessus l'original, au pixel près. On voit immédiatement si un texte a bougé ou débordé. *Chantier moyen, front seul.* Il met en valeur la fidélité PAO.
5. **Survol lié** : on passe la souris sur un paragraphe traduit et le paragraphe source s'éclaire. *Gros chantier* : le serveur doit renvoyer les positions des blocs.
6. **Aide raccourcis** (« ? ») et **recherche** dans la traduction. *Petits chantiers.*

## Recommandation
Faire d'abord les points 1 et 2 (petits chantiers, gain immédiat), puis le 4 (rideau), qui différencie Précis. Le 3 et le 5 se décident après essai.

## Limite de cette analyse
Elle est faite à partir du code, sans capture de l'écran réel. Une capture recadrée de la visionneuse, avec un document ouvert, permettrait de juger aussi l'équilibre visuel : espacements, contrastes, densité de la barre.
