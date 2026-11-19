# Étude — Qualité PowerPoint (contrôle du fichier Gerold, R7 + R6)

Fichier contrôlé : présentation Toyota de 75 diapositives, traduite en production.
Pour chaque défaut, l'étude donne : ce qu'on a observé, ce que font les traducteurs professionnels et leurs outils, ce qui existe déjà dans nos autres moteurs, et une règle qui ne casse rien.

---

## (a) Retours à la ligne forcés : le texte est traduit ligne par ligne

### Ce qu'on observe
- **Diapositive 1** : le titre « Toyota / Service Advisor Program / Deployment Guide » forme un seul paragraphe. L'auteur a seulement ajouté des retours à la ligne manuels pour équilibrer les lignes.
  Notre moteur envoie chaque ligne comme un morceau séparé. Le modèle les traduit donc chacune de son côté : « Toyota / Programme Service Advisor / Guide de déploiement ». Il ne traduit pas la phrase entière.
- **Bandeau des 6 étapes** (diapositives 5, 10, 12, 13, 14, 22) : « Appointment » et « Preparation » sont deux paragraphes séparés dans la même forme. Chacun est traduit seul, et les libellés finissent mélangés d'une diapositive à l'autre.
- Ampleur : 51 paragraphes sur 3 719 contiennent un retour à la ligne manuel.

### Ce que font les professionnels
- **memoQ** traite le retour à la ligne manuel comme une balise à l'intérieur de la phrase. L'option « Import soft breaks as inline tags » est activée par défaut. La phrase reste entière, et le traducteur place lui-même la coupure dans la traduction.
- **Trados** fait de même avec ses règles de segmentation, qui ne coupent pas sur un retour à la ligne manuel.
- Le principe commun : **une phrase est traduite en entier**, et la mise en lignes est refaite ensuite.

### Ce qui existe déjà chez nous
- `runtags.repartir` et `_concentrer` savent déjà répartir un texte traduit sur plusieurs morceaux.
- Le moteur OCR sait déjà recoller des lignes d'un même bloc avant de traduire, avec les règles `haut`, `champ` et RETOUR dans `blocs()`.
- Le moteur PDF supprime déjà le retour à la ligne manuel (`_CTRL_RE`) et traduit le paragraphe entier.

### Règle proposée (sans régression)
1. **Retour à la ligne manuel dans un paragraphe** : quand des morceaux ne sont séparés que par un retour à la ligne et ont la même mise en forme, on les envoie comme **une seule phrase**. On traduit, puis on redistribue le texte sur **le même nombre de lignes**, équilibrées, au plus près des espaces. C'est la méthode de memoQ, appliquée au format PowerPoint.
2. **Paragraphes séparés dans une même forme**, comme le bandeau : on les recolle seulement s'ils remplissent toutes ces conditions :
   - la même mise en forme ;
   - aucune ponctuation finale ;
   - une longueur courte, comme pour un libellé.

   C'est la règle de l'OCR. On les traduit ensemble, puis on les recoupe.
3. **Garde-fou** : si le découpage ne retrouve pas le bon nombre de lignes, on garde la traduction actuelle, ligne par ligne. Rien n'est jamais pire qu'aujourd'hui.
4. **Contrôle** : on rejoue les 75 diapositives. Seuls les paragraphes concernés doivent changer, et on compare les deux versions.

---

## (b) Coches « ✓ » perdues (7 cas : diapositive 12 ×1, 13 ×3, 14 ×3)

### Ce qu'on observe
La coche est un caractère d'une police de symboles (U+F0FC, Wingdings).
- **Quand elle est seule dans son morceau** : on l'envoie quand même au modèle, qui renvoie une espace vide.
- **Quand elle est suivie de « TSM-FIR as Kaizen »** : le modèle la supprime aussi.

Notre filtre `_is_numeric` n'écarte que les nombres, pas les symboles.

### Ce que font les professionnels
Les outils de traduction assistée **verrouillent** les segments qui ne contiennent rien à traduire, comme les nombres, les symboles ou les codes. Ils ne sont jamais envoyés au traducteur, ni à la traduction automatique.
Les contrôles qualité (Xbench, Verifika) signalent aussi tout symbole présent dans l'original et absent de la traduction.

### Ce qui existe déjà chez nous
- `_is_numeric` : un morceau composé seulement de chiffres n'est pas envoyé.
- `runtags.nombres` vérifie déjà que les nombres de l'original se retrouvent dans la traduction. Il suffit d'appliquer le même contrôle aux symboles.

### Règle proposée
1. **Un morceau sans aucune lettre** (symboles, police de symboles, espaces) est recopié tel quel et jamais envoyé.
2. **Un symbole de police de symboles placé en tête d'un morceau** est retiré avant l'envoi, puis remis à sa place après.
3. **Contrôle** : chaque symbole de l'original doit se retrouver dans la traduction. Ce contrôle est ajouté aux défauts déjà vérifiés par `runtags.defauts`.

Il n'y a pas de risque de régression : ces morceaux n'avaient de toute façon rien à traduire.

---

## (c) Texte qui déborde (diapositives 12, 23, 69)

### Ce qu'on observe
Le français est plus long que l'anglais, d'environ 15 à 25 %. Dans une forme de taille fixe, le texte sort du cadre.

### Ce que font les professionnels
- La règle du métier : on **reformule plus court d'abord**, et on ne réduit la police qu'en dernier recours, avec un minimum.
- PowerPoint fait cette réduction lui-même : l'option « Ajuster le texte en cas de dépassement » (`normAutofit`) réduit la police et l'interligne. Mais elle n'agit qu'à l'ouverture dans PowerPoint, pas dans les autres lecteurs.

### Ce qui existe déjà chez nous
Le moteur PDF a `translated_fit`. Il mesure si la traduction tient dans son cadre. Si elle ne tient pas, il demande une **traduction plus courte**. Il ne déforme jamais la mise en page.

### Règle proposée
1. **Mesurer** : on estime la place prise par le texte traduit, à partir de la taille de la forme, de la police et du nombre de lignes. On la compare à celle de l'original.
2. **Si ça déborde** : on demande une traduction plus courte, comme dans le moteur PDF.
3. **Si ça déborde encore** : on réduit la police, sans descendre sous 80 % de la taille d'origine. On l'écrit dans le fichier avec `normAutofit fontScale`, la valeur que PowerPoint utilise lui-même.
4. Une forme qui ne déborde pas n'est **jamais modifiée**.

---

## (d) Termes traduits de plusieurs façons (23 cas)

### Ce qu'on observe
Le même terme anglais est traduit de deux ou trois façons dans le document. Par exemple, une même étape du processus porte des noms différents selon la diapositive.
Notre passe de cohérence (`termes_incoherents`) ne détecte qu'un cas : un mot traduit à un endroit et laissé en anglais ailleurs.

### Ce que font les professionnels
C'est le contrôle standard « même original, traductions différentes ». Xbench l'appelle « Inconsistency in target », et Gridly et Verifika ont le même. Les professionnels le complètent par un **glossaire** fixé au début du projet.

### Ce qui existe déjà chez nous
- `fiche_document` construit déjà, avant de traduire, une fiche du document. C'est un texte libre, pas une liste de termes avec leur traduction : on ne peut donc pas s'en servir comme glossaire.
- `_coherence_document` relit déjà tout le document à la fin et corrige les écarts.

### Règle retenue (mise en œuvre)
1. Quand **le même texte d'origine** (au moins deux mots) apparaît plusieurs fois avec des traductions différentes, on garde la traduction **majoritaire** et on l'applique partout. Par exemple, « Toyota customer service philosophy » est traduit 8 fois d'une façon et 1 fois d'une autre : les 9 deviennent identiques.
2. On ne touche à rien en cas d'égalité (2 contre 2), ni pour un mot seul : « Customer » peut légitimement donner « Accueil » ou « Client » selon l'endroit.
3. Aucun appel au modèle : on recopie une traduction déjà produite. Seules les diapositives modifiées sont réécrites.
4. Sur le PowerPoint de Gerold, cela corrige les écarts nets (« Job control » 6 contre 1, « Introduction to parts operation » 7 contre 3, etc.).

### Piste écartée
Imposer la traduction d'un libellé court partout où il apparaît dans une phrase. Testé sur Gerold, cela dégrade le texte : « HRD policy » forcerait « Politique HRD » au lieu de « politique RH », qui est meilleur. De même, « daily job » imposerait « Travail quotidien » là où « tâches quotidiennes » est juste. Sans glossaire validé, on ne force donc rien à l'intérieur des phrases.

---

## (e) Doubles espaces

### Ce qu'on observe
Des espaces doublées apparaissent dans la traduction alors qu'elles n'étaient pas dans l'original. Elles viennent surtout de la jonction entre deux morceaux.

### Ce que font les professionnels
C'est un contrôle de base, présent dans tous les outils qualité.
Ils vérifient seulement que l'espacement de la traduction **suit celui de l'original**.

### Règle proposée
- On réduit à une seule espace celles **ajoutées par la traduction**.
- Une double espace déjà présente dans l'original est conservée. Certains auteurs s'en servent pour aligner du texte, comme avec la coche suivie de « Leadership » sur la diapositive 13.

---

## R6 — Titre sur plusieurs lignes (Toyota)
C'est le même problème que (a), dans sa forme la plus visible. La règle (a)1 le corrige. Il n'y a pas besoin d'une étude séparée.

---

## Ordre proposé (du plus grave au plus léger)
1. **(a) + R6** : le sens est faux.
2. **(b)** : un contenu est perdu. Le correctif est simple et sans risque.
3. **(d)** : les termes sont incohérents.
4. **(c)** : la mise en page est abîmée.
5. **(e)** : la finition.

Chaque étape sera rejouée sur le fichier Gerold et sur le banc PowerPoint existant. Seules les diapositives qui changent seront montrées.

## Sources
- memoQ, format PPTX : https://docs-memoq-com.azurewebsites.net/current/en/Workspace/microsoft-powerpoint-2007-pptx.html
- Trados, segmentation sur retour manuel : https://community.rws.com/product-groups/trados-portfolio/trados-studio/f/studio/13299/stubborn-segmentation-rule-for-soft-breaks/46833
- Ajustement automatique PowerPoint : https://python-pptx.readthedocs.io/en/latest/dev/analysis/txt-autofit-text.html
- Xbench « Inconsistency in target » : https://wiki.proz.com/forum/xtm_cloud_support/317708-xtm_cloud_qa_vs_xbench_qa.html
- Gridly, contrôles qualité : https://help.gridly.com/auto-qa-errors-reference-guide
- Makoushina, contrôle qualité en traduction (Aslib 2007) : https://aclanthology.org/www.mt-archive.info/Aslib-2007-Makoushina.pdf
