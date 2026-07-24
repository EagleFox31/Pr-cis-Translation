# Moteur PPTX — contexte

Version **1.0.0** · `engines/pptx/engine.py` · inscrit au registre sous `pptx`

Traduit une présentation PowerPoint **sans jamais la reconstruire** : le `.pptx`
est un ZIP d'XML, on le décompresse, on modifie les nœuds de texte **sur place**
avec lxml, on re-zippe. Aucun run n'est supprimé ni recréé — c'est ce qui
préserve intégralement la mise en forme.

> À lire d'abord : [`../CONTEXTE.md`](../CONTEXTE.md) — la règle d'indépendance,
> l'instance par opération, LibreOffice, les balises de runs.

## Le contrat

```python
eng = engines.new_engine("pptx")          # instance NEUVE, obligatoire
data, path = eng.extract_text(pptx, json_out, filters=…, pages=…)
ok, msg    = eng.inject_translation(original, json_traduit, sortie)
```

Et pour le mode progressif, diapositive par diapositive :

```python
eng.slide_count()                          # sans tout décompresser
eng.extract_slide(n)                       # une seule diapositive
eng.inject_slide(n, translation_map)
eng.build_partial_pptx(sortie, jusqu_a=n, only_slides={…})
eng.regenerate_ole_previews(only_slides={…})
```

## Trois pièges déjà payés

### 1. Les parties partagées n'appartiennent à aucune diapositive

Un `slideLayout` ou un `slideMaster` est référencé par plusieurs diapositives,
mais c'est **un seul fichier**.

En faisant entrer le numéro de diapositive dans l'identité de ses paragraphes,
on en fabriquait autant de copies qu'il y avait de diapositives : traduites une
fois chacune (**autant d'appels payés**), puis injectées tour à tour dans le
même fichier — la dernière écrasait les autres. Pire en mode progressif : la
diapositive 7 extrayait un layout **déjà injecté** par la 2, et on traduisait
une traduction, avec la dérive que ça suppose.

D'où `PART_PARTAGEE = 0` : un numéro fixe, hors de toute diapositive, et une
seule extraction par document.

### 2. L'aperçu d'un objet Excel est référencé deux fois

Un classeur incorporé est rendu par **une image**, pas par Excel. Cette image
est pointée à **deux endroits** : `mc:Choice` (VML) et le repli DrawingML.

Régénérer l'image depuis le classeur traduit sans repointer **toutes** les
relations laisse la moitié des clients afficher l'ancienne version — celle
d'avant traduction. Le symptôme est un tableau resté en français dans une
présentation anglaise, et il dépend du logiciel qui ouvre le fichier.

L'image régénérée est rendue en **RGBA**, alpha compris : un fond opaque
masquait une forme placée dessous. LibreOffice ne peint pas de fond (mesuré :
99,9 % des pixels à alpha 0) et la transparence survit à `--convert-to pdf`.

### 3. Un aperçu partiel qui échoue ne doit pas emporter le serveur

Le convertisseur d'aperçu remet en attente un lot qui a échoué. La première
version repartait **aussitôt** : la file n'était jamais vide, la boucle ne
dormait pas, et elle monopolisait le verrou LibreOffice — affamant toutes les
autres conversions. Un classeur illisible dans un document devenait une panne
globale.

Deux bornes, et les deux sont nécessaires : **3 essais** par diapositive, puis
abandon de son *aperçu* seulement (la conversion finale la reprendra) ; et une
**pause interruptible** entre essais, sans quoi le plafond est atteint en
quelques microsecondes et le mal est déjà fait.

Verrouillé par `tests/test_apercu_resilience.py`.

## Ce qui n'est pas traduit, volontairement

* les valeurs **numériques pures** des axes et séries de graphiques — les
  traduire les corromprait ;
* le contenu de `mc:Fallback` quand `mc:Choice` porte le même texte — sans ce
  filtrage, le texte est extrait et réinjecté **deux fois** (texte fantôme
  dédoublé à l'écran).

## Aperçu progressif

Le flux est identique à celui du PDF : on affiche d'abord **tout l'original**
converti en PDF, puis chaque diapositive traduite est greffée à sa place dès
qu'elle est prête (`app/services/progressive_preview.py`).

La greffe porte deux gardes, et la seconde seule ne suffisait pas : demander une
diapositive **inexistante** produit un deck vide que LibreOffice rend comme
**une page blanche** — le contrôle de nombre voyait `1 == 1` et enregistrait une
page fantôme. D'où une garde d'**existence** en plus du compte.

## Limites connues

* les objets OLE non-Excel ne sont pas régénérés — leur aperçu reste celui
  d'origine ;
* `_auto_refresh_powerpoint()` (COM/PowerShell) n'existe que sur Windows **avec
  PowerPoint installé** ; ce n'est pas un chemin de production ;
* les SmartArt sont traduits dans leur XML de données, mais leur rendu mis en
  cache par PowerPoint peut rester ancien jusqu'à réouverture.

## Vérifier

```bash
backend/venv/Scripts/python.exe backend/tests/test_pptx_preview.py
backend/venv/Scripts/python.exe backend/tests/test_ole_apercu.py
backend/venv/Scripts/python.exe backend/tests/test_runtags.py
backend/venv/Scripts/python.exe backend/tests/test_apercu_progressif.py
backend/venv/Scripts/python.exe backend/tests/test_apercu_resilience.py
```
