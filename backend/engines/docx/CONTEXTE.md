# Moteur DOCX — contexte

Version **1.0.0** · `engines/docx/engine.py` · inscrit au registre sous `docx`

Même principe que le moteur PPTX, et volontairement la même forme : un `.docx`
est un ZIP d'XML, on le décompresse, on modifie les nœuds `<w:t>` **en place**
avec lxml, on re-zippe. Aucun run n'est supprimé ni recréé — toute la mise en
forme est donc préservée par construction.

> À lire d'abord : [`../CONTEXTE.md`](../CONTEXTE.md) — la règle d'indépendance,
> l'instance par opération, les balises de runs.

## Le contrat

```python
eng = engines.new_engine("docx")          # instance NEUVE, obligatoire
data, path = eng.extract_text(docx, json_out, filters=…)
ok, msg    = eng.inject_translation(original, json_traduit, sortie)
```

C'est le moteur le plus simple des trois, et le seul qui n'ait ni mode
progressif ni dépendance à LibreOffice pour traduire. Son aperçu, lui, passe
bien par LibreOffice comme tout format non-PDF.

## Ce qui est parcouru

Au-delà du corps du document : les **en-têtes**, les **pieds de page** et les
**zones de texte** (`w:txbxContent`). Les oublier laissait des pages
partiellement traduites, et l'oubli ne se voit qu'à l'impression.

## Le piège de la compatibilité de balisage

`mc:AlternateContent` encapsule **deux représentations du même contenu** :

* `mc:Choice` — la moderne, celle que Word et LibreOffice rendent ;
* `mc:Fallback` — un VML historique, jamais rendu.

Les deux portent un `w:txbxContent`. Sans filtrage, on extrait **et on
réinjecte** le texte deux fois : on paie deux traductions du même paragraphe, et
selon le lecteur, du texte fantôme dédoublé apparaît à l'écran.

`_strip_fallbacks()` élimine la branche `mc:Fallback` avant tout parcours.

## Une instance par opération

La règle vaut ici aussi, et elle a été violée plus longtemps qu'ailleurs : un
`docx_engine = DOCXTranslatorEngine()` **au niveau du module** a survécu jusqu'à
la réorganisation en couches. Un moteur partagé écrit dans le `temp_dir` d'un
autre travail. Voir [`../CONTEXTE.md`](../CONTEXTE.md).

## Limites connues

* pas de traduction progressive : le document est traité d'un bloc, l'aperçu
  n'apparaît qu'à la fin ;
* les **champs calculés** (sommaire, numéros de page, renvois) portent un texte
  mis en cache par Word ; il est traduit, mais Word peut le recalculer et
  revenir à la langue d'origine des styles ;
* le **suivi des modifications** (`w:ins` / `w:del`) n'est pas traité
  spécifiquement : le texte des révisions est traduit comme le reste ;
* les **notes de bas de page** et **commentaires** ne sont pas parcourus.

## Vérifier

```bash
backend/venv/Scripts/python.exe backend/tests/test_runtags.py
backend/venv/Scripts/python.exe backend/tests/test_download_format_integrity.py
```

Le second garde une règle qui déborde le moteur : le cache de rendu ne contient
**que des PDF**. Servir son contenu au téléchargement d'un DOCX rend un fichier
que Word refuse d'ouvrir.
