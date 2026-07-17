# Audit indépendant — branche `feat/comptes-utilisateurs`

> Document de passation pour une relecture critique par un autre modèle.
> Rédigé le 17/07/2026 par l'assistant ayant écrit le code. **Il est donc juge et
> partie : tout ce qui suit doit être re-mesuré, pas cru.**

---

## 1. Mission

Vérifier, avant fusion, une branche qui touche à **trois choses sensibles** :

1. **De l'argent** — un plan gratuit ne doit pas pouvoir obtenir la traduction en
   clair (c'est le produit).
2. **Des fichiers d'autrui** — le magasin est partagé entre comptes ; une purge
   erronée détruit les données d'un autre utilisateur, sans retour possible.
3. **Le rendu** — une clé de cache fausse ressert un rendu périmé *en silence*.

Ces trois-là méritent l'essentiel de l'effort. Le reste est cosmétique.

## 2. Méthode attendue

Ces règles ont été posées par l'utilisateur et **ont déjà été enfreintes** dans
cette session (voir §6). Les appliquer à la lettre :

- **Aucune solution spécifique à un document.** Tout correctif du moteur vise une
  *classe* de problème et se prouve sur un PDF **synthétique**
  (`backend/test_engine_v2_generic.py`), jamais sur le seul document qui l'a
  révélé.
- **Un test qui ne peut pas échouer ne teste rien.** Casser le code
  volontairement ; la vérification correspondante *doit* tomber. Une mutation
  non détectée = test vacant.
- **Le vide n'est pas une preuve.** Un espace blanc, une absence de trait, une
  console silencieuse ne démontrent rien.
- **Une structure ne s'établit que par répétition congruente** de ses membres.
- **La géométrie prime sur l'orthographe** : ne pas demander à l'orthographe de
  prouver une structure.

## 3. Contexte technique

| | |
|---|---|
| Stack | FastAPI + SQLAlchemy async + PostgreSQL (Alembic), React/TS/Vite |
| Moteur PDF | `pdf_engine_v2` — PyMuPDF 1.27.2.3, Python 3.14 |
| Pipeline | extract → tag → traduire (DeepSeek) → reflow → rendu, **page par page** (SSE) |
| Venv | `backend/venv/Scripts/python.exe` |
| Base | `postgresql+asyncpg://…@127.0.0.1:5432/precis` |
| Remote git | **aucun** — tout est local, rien n'est poussé |

**Lancer les tests** (le projet n'utilise pas pytest ; convention = script `run()`) :

```bash
backend/venv/Scripts/python.exe backend/test_engine_v2_generic.py   # attendu 38/38
backend/venv/Scripts/python.exe backend/test_documents_purge.py     # attendu 16/16 (requiert PostgreSQL)
```

**Docs existantes** : `PROBLEMES_PDF_ENGINE_V2.md` (catalogue P1-P20),
`CONTEXTE.md`, `CONTEXTE_COMPTES_UTILISATEURS.md`.

**Comptes de test en base** :
`mbowouibrah@gmail.com` / `PrecisTest2026!` (admin) ·
`free@example.com` / `NouveauMdpLong2026` (free)

## 4. Ce qui a été livré

La branche compte ~55 commits depuis `main` (`git log --oneline main..HEAD`, 51
fichiers, +5747/−660). Voici les **plus récents**, ceux de cette session :

| Commit | Objet |
|---|---|
| `02b2dd2` | Lot 2 : `ENGINE_VERSION` dans la clé + purge par comptage de références + réconciliation des jobs zombies |
| `220f361` | Viewer : annulation ≠ panne ; la démo n'est plus un substitut de source |
| `66e99e3` | Route `/original` — l'aperçu bibliothèque affichait le PDF de **démo** en source |
| `db4878f` | La bibliothèque contournait entièrement le verrou d'essai (3ᵉ porte) |
| `53be6ad` | Un 402 (refus de forfait) était traité comme une panne |
| `885def7` | Auth par mot de passe + parcours « mot de passe oublié » |
| `893a995` | Aperçu d'essai **rastérisé + filigrané** (option B choisie par l'utilisateur) |
| `657f3b4` | Verrous serveur : connexion pour traduire, plan payant pour télécharger |
| `3346b57` | Bibliothèque vide, aperçu bridé pour les abonnés, `getBlob` mort |
| `b260440`→`d65b265` | Moteur : P15-P20 + régénération de la démo |

**Règle produit à faire respecter partout** (mots de l'utilisateur) :
> « un utilisateur qui n'a pas de compte ou qui est en fremium ne dois pas
> telecharger ni voir en claire la traduction ; un non connecté ne peux meem pas
> lancer une traduction »

---

## 5. À vérifier — par ordre de risque décroissant

### 5.1 🔴 La règle de plan est dispersée dans les endpoints

**Trois portes successives ont été trouvées sur la même règle** : `/result`, puis
`/partial`, puis `/download` + `/preview`. Chacune a été bouchée séparément.
Aucune dépendance FastAPI unique ne la porte.

**À faire** : recenser **toute** route rendant des octets dérivés d'une
traduction et vérifier le verrou de plan sur chacune. En chercher une quatrième.
Vérifier aussi `/api/translate/events/{job_id}` (SSE) et l'appartenance du job
(`_job_of`) — un `job_id` deviné donne-t-il quoi que ce soit ?

**Attendu** : plan `free` → 402 sur le téléchargement ; aperçu rastérisé
uniquement. Mesure de référence : *0 mot du document extractible* d'un aperçu
d'essai (avant correctif : 782 mots sur 454 882 octets).

### 5.2 🔴 La purge peut détruire les fichiers d'un autre compte

`backend/routes/documents.py` — `_purge_if_orphan`, `_inside_store`,
`_prune_empty_dirs`.

Le magasin est **partagé** : `translations/{nom}_{hash}/{langue}/`. Deux comptes
ayant déposé le même fichier pointent sur **les mêmes octets**.

**À vérifier** :
- Le comptage de références est fait **après** `commit` de la suppression (sinon
  la ligne se compte elle-même et rien n'est jamais orphelin). Que se passe-t-il
  si le commit réussit et que la purge échoue ?
- **Concurrence** : A supprime pendant que B traduit le même hash. Le refcount
  est-il atteignable entre le `os.path.exists(output_path)` (dédup) et
  l'insertion du `Document` de B ? *Piste non explorée — probablement une
  fenêtre réelle.*
- `_inside_store` refuse-t-il vraiment tout chemin hors magasin (liens
  symboliques, `..`, autre volume) ?

### 5.3 🔴 Secrets exposés dans l'historique git

**Attention : j'avais d'abord écrit ici que `.env` était committé. C'est FAUX**
(mesuré : `git ls-files backend/.env` → 0, jamais suivi dans tout l'historique,
et le `.gitignore` le couvre). J'ai reproduit dans ce document même l'erreur n°1
du §6. **Preuve que rien ici ne doit être cru sans re-mesure.**

La fuite est réelle, mais par une **autre porte** : `CONTEXTE_COMPTES_UTILISATEURS.md`
— lui **suivi par git** — recopiait les valeurs en clair (lignes 291, 299). Le
`.gitignore` a fait son travail ; une documentation l'a contourné. *Même forme
que les « trois portes » du §5.1 : la règle est bonne, c'est le nombre d'entrées
qui est faux.*

Exposés : le **mot de passe applicatif Gmail**, le **mot de passe PostgreSQL**,
le `JWT_SECRET` (celui-ci de type « placeholder »).
Non secrets : `GOOGLE_CLIENT_ID` (public par nature), `VITE_API_KEY` (livrée au
navigateur de toute façon — **à vérifier : sert-elle de contrôle d'accès quelque
part ? Ce serait un faux verrou**).

**Fait** : valeurs masquées dans le document (commit à venir).
**Reste à faire — par l'utilisateur** : **l'historique git conserve les anciennes
versions**. Le masquage empêche la diffusion future, *pas* la lecture du passé.
⇒ **Rotation obligatoire** du mot de passe Gmail et du mot de passe PostgreSQL.
Vérifier qu'il n'existe aucune autre occurrence dans les fichiers suivis.

### 5.4 🟠 `ENGINE_VERSION` : une discipline humaine, donc fragile

`pdf_engine_v2/version.py`. La clé de cache inclut désormais la version du
moteur — mais **rien ne force à l'incrémenter**. L'oublier ressert un rendu
périmé *sans aucun signal*.

**À évaluer** : peut-on la dériver automatiquement (hash du source d'`engine.py`)
plutôt que de compter sur la mémoire d'un humain ? Contre-argument : un
commentaire modifié invaliderait tous les caches. Y a-t-il mieux ?

### 5.5 🟠 `storage_used` peut dériver (défaut connu, non corrigé)

`_save_document_for_user` facture `charge = 0` quand le quota est plein ou que le
plan est gratuit — mais `delete_document` rembourse `size` **inconditionnellement**.
Un compte payant au quota plein voit donc son compteur **descendre sous la
réalité** à chaque suppression.

Correctif proposé, non appliqué : colonne `Document.storage_charged` (**une vraie
migration Alembic serait justifiée ici**). Vérifier le raisonnement, et si le cas
`free` (charge 0, `storage_used` déjà 0) est bien inoffensif.

### 5.6 🟠 Énumération de comptes

`backend/routes/auth.py` — `forgot_password`. Les messages et statuts ont été
uniformisés, **mais l'erreur elle-même fuyait** : n'envoyer que si l'utilisateur
existe → SMTP en panne = 500 pour un compte existant, 201 pour un inconnu.
Enveloppé dans un `try/except`. **Vérifier qu'il n'y a pas de canal résiduel** :
temps de réponse (bcrypt n'est calculé que si le compte existe ?),
`/register-password` sur un email déjà pris, `/login-password`.

### 5.7 🟡 Réconciliation des jobs zombies — écart non élucidé

`app.py` — `_reconcilier_jobs_orphelins()` (dans le `lifespan`).

Principe : `_jobs` vit en mémoire, donc vide au démarrage ⇒ tout `Document` en
`translating` à cet instant est orphelin *par construction*.

**Anomalie honnête** : lors d'un essai, le journal a annoncé **1** ligne close
alors que **2** étaient en vol. Recompté juste en conditions contrôlées (3→3,
2→2) et les deux lignes ont bien fini `error`. **Je n'explique pas cet écart.**
À reproduire ou à réfuter.

Limite assumée (commentée dans le code) : un second processus démarrant pendant
qu'un premier traduit marquera un job vivant en erreur — dégât jugé transitoire
car `_job_done` repasse la ligne à `done`. **Vérifier ce raisonnement.**

### 5.8 🟡 Fuites de disque connues

- Les `partial_*.pdf` ne sont référencés par aucun `Document` : ils s'accumulent
  et maintiennent leur dossier en vie (`_prune_empty_dirs` s'arrête sur non-vide).
- Deux dossiers `demo_journal_avant_*` (≈ 2,9 Mo) sont orphelins sur le disque.
- Les anciens rendus pré-`v21` sont désormais inatteignables mais présents.

### 5.9 🟡 Moteur — limites documentées, non corrigées

- **Césure « routiè-re »** : *irréproductible*. `routière` n'a que la position
  [3] dans fr_FR/en_US/en_GB ; aucun chemin de code ne peut produire cette
  coupure. `com-mandes` est légitime. **Nécessite le PDF réel de l'utilisateur.**
- **Justification sur-étirée** : colonne 1 de la démo, blancs à 4,8 pt contre
  2,4 pt de médiane ; l'original anglais n'en a aucun. Mesuré, non traité.
- **Colonne justifiée de ≤ 5 lignes non recollée** — suspendu par l'utilisateur.

### 5.10 🟢 Invariants de non-régression

Toute modification du moteur doit les laisser intacts :

| Document | Paragraphes attendus |
|---|---|
| mv21 | 621 |
| Handbook | 309 |
| démo | 38 |

⚠️ Les **comptes de mots** de `PROBLEMES_PDF_ENGINE_V2.md` ont été trouvés
périmés (10 671/8 615 documentés contre 10 937/8 448 mesurés) — identiques avant
*et* après P20, donc antérieurs à cette session. Corrigés avec une note. **À
re-mesurer.**

---

## 6. Mes erreurs avérées dans cette session — creuser ici en priorité

Elles sont listées parce qu'un correcteur qui connaît les modes de défaillance de
l'auteur trouve plus vite. Chacune est une faute **constatée**, pas une
hypothèse.

1. **J'ai affirmé trois fois qu'un fichier contenait une chaîne qui n'y était
   pas.** (`demo_journal_apres.pdf` / « com activités des entreprise entreprises
   s »). Vérification : la chaîne **n'y est pas**. L'affirmation venait d'une note
   de session périmée jamais recontrôlée. ⇒ **Ne croire aucune de mes citations
   de fichier sans la re-mesurer.**

2. **Deux de mes trois vérifications P19 étaient vacantes** : elles passaient sous
   *toutes* les mutations, y compris la suppression des deux garde-fous. Réécrites
   en boîte blanche. ⇒ **Passer les tests au test de mutation.**

3. **Trois diagnostics faux d'affilée sur un « serveur zombie »**, jusqu'à ce que
   l'utilisateur impose de vérifier *tous* les processus : un PID mort tenait le
   port 8000, son enfant servait du code d'avant les correctifs. **Je n'avais
   jamais regardé qui écoutait.** ⇒ **Vérifier l'état réel du système avant de
   théoriser.**

4. **J'ai documenté un garde-fou avec la mauvaise raison.** J'avais écrit que la
   suppression « protégeait le cache partagé » ; en réalité `STORAGE_BASE`
   pointait sur `backend/routes/translations` (dirname de son propre fichier),
   dossier **vide**, pendant que tout s'écrivait dans `backend/translations`.
   La protection fonctionnait *en pointant à côté*. ⇒ **Un commentaire n'est pas
   une preuve.**

5. **Un test de mutation a révélé un trou dans mes propres tests** : remettre
   `STORAGE_BASE` sur le mauvais dossier ne faisait échouer **aucun** des 15
   tests — tous bâtissaient leurs fixtures à partir de ce même `STORAGE_BASE`.
   Ils *suivaient* le bug. ⇒ **Un test qui partage une constante avec le code ne
   peut pas voir cette constante fausse. Chercher d'autres occurrences de ce
   motif.**

6. **J'ai promis une migration Alembic, puis conclu qu'elle était inutile** — le
   magasin adressé par contenu existait déjà sur le disque. ⇒ **Vérifier que
   cette conclusion est juste** et que rien dans la demande initiale n'a été
   abandonné au passage (dédup entre comptes, suppression par utilisateur sans
   effet sur les autres).

7. **Régression que j'ai moi-même introduite** : le 402 tout neuf était traité
   comme une panne côté front (aperçu bloqué sur « page en attente »). ⇒ **Tout
   nouveau code de refus doit être suivi jusqu'à son affichage.**

8. **Une couche de texte survivait sous le pixmap** de l'aperçu d'essai :
   visuellement protégée, **intacte au copier-coller**. Corrigé par
   `clean_contents()` + recréation de page. ⇒ **Re-vérifier par extraction
   réelle, pas à l'œil.**

---

## 7. Questions ouvertes, sans réponse à ce jour

1. La fenêtre de concurrence entre la dédup (`os.path.exists`) et l'insertion du
   `Document` est-elle exploitable ? (§5.2)
2. `ENGINE_VERSION` peut-elle être dérivée automatiquement sans invalider le
   cache à chaque commentaire modifié ? (§5.4)
3. D'où vient le « 1 » au lieu de « 2 » de la réconciliation ? (§5.7)
4. Existe-t-il une **quatrième porte** sur la règle de plan ? (§5.1)
5. La césure « routiè-re » est-elle reproductible avec le PDF réel ? (§5.9)
