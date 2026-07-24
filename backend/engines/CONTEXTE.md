# Les moteurs — contexte commun

Un moteur prend un document, en relève le texte **avec sa géométrie et ses
styles**, et sait réinjecter une traduction dans l'original. Il ne reconstruit
jamais le document : c'est toute la promesse du produit.

## La seule règle non négociable

**Un moteur n'importe jamais `app`.** Ni la base, ni les comptes, ni les
forfaits, ni FastAPI. Il reçoit des chemins, il rend des octets ou du JSON.

```bash
cd backend && venv/Scripts/python.exe -c "import engines, sys; \
  print([m for m in sys.modules if m.startswith('app')])"
# => []   ← doit rester vrai
```

Ce n'est pas du purisme. Le moteur PPTX faisait `from app import _preview_lock`
en import tardif, avec un commentaire qui s'excusait du cycle. Un moteur qui
importe son application ne peut plus en sortir : ni pour un banc d'essai, ni
pour un autre projet, ni pour être remplacé.

## Une instance par opération — jamais un singleton

Un moteur porte un `self.temp_dir`. C'est un objet **à état**, et cet état n'est
pas protégeable : deux traductions du même original écriraient de toute façon
dans les mêmes fichiers.

Ce qu'une instance partagée a réellement produit :

* deux aperçus concurrents partageaient le dossier — l'aperçu portugais
  injectait le portugais dans les XML que l'aperçu anglais re-zippait. **On
  demandait l'anglais, on recevait le portugais.** Intermittent, donc invisible
  en test manuel et bien réel en usage ;
* le `_cleanup_temp()` d'un aperçu supprimait le dossier temporaire d'un **job
  de traduction en cours**.

D'où `engines.new_engine("pptx")` au début de chaque opération, et le registre
qui ne rend **jamais autre chose qu'une classe**.

## Le registre, et l'exception PDF

`engines/__init__.py` est le seul endroit du projet qui nomme un format.
L'application demande « qui traite le `.pptx` ? » — elle n'importe pas de moteur
directement.

**Le PDF n'y figure pas**, et c'est délibéré : il n'a pas le contrat
`extract_text` / `inject_translation` en deux temps. Sa traduction est
progressive par construction (`engines/pdf/stream.py`), page extraite → traduite
→ rendue avant de passer à la suivante. L'exécuteur l'appelle nommément. Si
cette asymétrie surprend, elle est réelle : ne pas la maquiller derrière une
fausse conformité au registre.

## Ce que les moteurs partagent

| Module | Rôle |
|---|---|
| `engines/base.py` | Le contrat `TranslationEngine` (Office : DOCX, PPTX). |
| `engines/office.py` | La **seule** porte vers LibreOffice : verrou global, profil partagé, pré-chauffage. |
| `engines/runtags.py` | Le contrat des balises `[[n]]…[[/n]]` et sa réparation. |
| `engines/translation_ai.py` | Le client DeepSeek : lots, réessais, invariants. |

### LibreOffice : un verrou, un profil

`soffice` ne supporte pas deux invocations concurrentes. Tout passe par
`engines/office.py` et son `preview_lock`.

Le coût dominant n'est pas la conversion, c'est le **profil utilisateur**.
Mesuré : profil neuf **6,99 s**, profil réutilisé **2,66 s**, une seule
diapositive à chaud **1,58 s**. D'où un profil partagé pour tout le processus.

Deux mesures qui évitent de refaire le chemin :

* **élaguer les médias avant conversion ne gagne rien** — 0,00 s. L'hypothèse
  était plausible, elle est fausse. Ne pas la réécrire ;
* LibreOffice garde son profil ouvert un instant après avoir rendu la main.
  Sous Windows, le nettoyage du dossier temporaire lève alors `PermissionError`
  et une conversion **réussie** remonte comme un échec. D'où
  `ignore_cleanup_errors=True` partout où un profil est créé.

### Les balises de runs : un contrat, pas une politesse

Un paragraphe est découpé en runs, un par changement de mise en forme.
L'extraction les balise ; le modèle est censé les rendre. **Il ne le fait pas
toujours.**

Quand l'injection ne remplaçait que les runs qu'elle retrouvait, les autres
gardaient leur **texte source** et le document affichait la traduction collée à
l'original — « DAY 2 OF TRAINING° JOUR DE FORMATION », mesuré. Le modèle avait
pourtant bien traduit : c'était un défaut de **contrat**, pas de traduction.

La règle : aucun run ne conserve jamais son texte source. Si la réponse ne
couvre pas tous les runs, on répartit ce qu'on a reçu — quitte à en vider
certains. **Un run vide est invisible ; un run resté en français ne l'est pas.**

### Les invariants sont sans seuil

Balises, recopie, nombres : quand un invariant est rompu, on **redemande au
modèle**. On ne rafistole pas en aval.

Un seuil calé sur un document donné efface des noms propres sur le suivant —
c'est arrivé. Un invariant qui a besoin d'un nombre magique pour tenir n'est pas
un invariant.

## Ajouter un moteur

1. `engines/<format>/engine.py`, classe héritant de `TranslationEngine`.
2. L'inscrire dans `_REGISTRE`.
3. `engines/<format>/version.py` avec `__version__ = "1.0.0"`.
4. Un `CONTEXTE.md` — celui-ci, pour ce format.

Aucune route, aucun exécuteur à modifier.

## Prouver un correctif

Sur un document **synthétique**, jamais sur celui qui a révélé le défaut. Un
correctif prouvé sur le seul document qui l'a fait apparaître est une
heuristique déguisée : il tiendra jusqu'au document suivant.

Et tout test doit passer le **test de mutation** — casser exprès le correctif et
vérifier que la suite rougit. Un test vert sur du code cassé ne teste rien.
