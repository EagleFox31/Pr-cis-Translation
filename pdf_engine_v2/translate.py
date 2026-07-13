"""
pdf_engine_v2.translate — Orchestration de la traduction d'une extraction v2.

Chaîne : pour chaque paragraphe (des `max_pages` premières pages), on produit un
texte BALISÉ par style (`tagging.tag_paragraph`), on l'envoie par lots au
traducteur existant (`backend/translator_ai.py`, qui préserve les balises
`[[n]]`), puis on stocke sur le paragraphe :

    el["tr_tagged"]   = texte traduit balisé  (rendu par le reflow)
    el["tr_segments"] = styles des balises    (police/gras/italique/taille/couleur)

Aucune modification du reste de l'extraction : images, dessins, mise en page
restent identiques ; seule la source du TEXTE change à la réinjection
(`engine.reinject(..., translated=True)`).
"""

import os
import re
import sys

from . import tagging


def _tags_ok(src_tagged, out_tagged):
    """Les balises `[[n]]…[[/n]]` de la traduction correspondent-elles à celles
    de la source ? (mêmes numéros ouvrants/fermants — l'ordre peut varier)."""
    tags = lambda t: sorted(re.findall(r"\[\[/?\d+\]\]", t or ""))
    return tags(src_tagged) == tags(out_tagged)

# `translator_ai` vit dans backend/ : on l'ajoute au chemin d'import.
_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def translate_extraction(data, target_lang="fr", max_pages=None,
                         batch_size=40, progress=None):
    """Traduit les paragraphes des `max_pages` premières pages de `data` (dict
    d'extraction v2). Modifie `data` en place et le retourne.

    target_lang : code court ('fr', 'en', …) ou nom.
    max_pages   : limite le nombre de pages traitées (None = tout).
    """
    from translator_ai import TranslatorAI
    tr = TranslatorAI()
    lang_name = tr._LANG_NAMES.get(str(target_lang).lower(), target_lang)

    pages = data.get("pages", [])
    if max_pages is not None:
        pages = pages[:max_pages]

    # 1) Balisage + collecte des items à traduire (id unique -> paragraphe).
    items, refs = [], {}
    for page in pages:
        for el in page.get("elements", []):
            if el.get("type") != "paragraph":
                continue
            tagged, meta = tagging.tag_paragraph(el)
            el["tr_segments"] = meta
            if not tagged.strip():
                el["tr_tagged"] = tagged           # paragraphe vide : rien à faire
                continue
            _id = f"p{page['page_num']}_e{len(refs)}"
            items.append({"id": _id, "text": tagged})
            refs[_id] = el
            el["tr_tagged"] = tagged                # repli si la trad échoue

    if progress:
        progress(f"{len(items)} paragraphe(s) à traduire vers {lang_name}.")

    # 2) Traduction par lots (le traducteur préserve les balises [[n]]).
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        try:
            tr._translate_batch(batch, lang_name, progress)
        except Exception as e:
            if progress:
                progress(f"[!] lot {i // batch_size} échoué : {e}")
        for b in batch:
            el = refs[b["id"]]
            el["tr_tagged"] = b.get("translated_text") or b["text"]
        if progress:
            progress(f"  lot {i // batch_size + 1}/"
                     f"{(len(items) + batch_size - 1) // batch_size} traduit.")

    # 3) VÉRIFICATION PAR ITEM + relance individuelle : un id absent de la
    #    réponse ou des balises mutilées restaient silencieux (texte source
    #    conservé / styles perdus). On re-traduit ces items un à un (2 essais),
    #    et on JOURNALISE ce qui reste en repli au lieu de le taire.
    failed = [it for it in items
              if not it.get("translated_text")
              or not _tags_ok(it["text"], it["translated_text"])]
    for attempt in range(2):
        if not failed:
            break
        if progress:
            progress(f"{len(failed)} item(s) à re-traduire individuellement "
                     f"(id manquant ou balises mutilées), essai {attempt + 1}.")
        still = []
        for it in failed:
            one = {"id": it["id"], "text": it["text"]}
            try:
                tr._translate_batch([one], lang_name, None)
            except Exception:
                pass
            out = one.get("translated_text")
            if out and _tags_ok(it["text"], out):
                it["translated_text"] = out
                refs[it["id"]]["tr_tagged"] = out
            else:
                still.append(it)
        failed = still
    if failed and progress:
        for it in failed:
            progress(f"[!] non traduit (repli source) : {it['text'][:60]!r}")

    return data


def retranslate_overflows(data, engine, target_lang="fr", max_pages=None,
                          progress=None, max_rounds=2):
    """RETRADUCTION COMPACTE (décision produit : compression par REFORMULATION,
    jamais une mise en forme dégradée). Pour chaque paragraphe dont la
    traduction ne tient pas dans son conteneur sans compression visible
    (`engine.translated_fit`), on re-demande une traduction avec un BUDGET DE
    CARACTÈRES strict. Deux tours max ; en dernier recours le rendu garde sa
    garantie force-fit (jamais de chevauchement)."""
    from translator_ai import TranslatorAI
    tr = TranslatorAI()
    lang_name = tr._LANG_NAMES.get(str(target_lang).lower(), target_lang)

    pages = data.get("pages", [])
    if max_pages is not None:
        pages = pages[:max_pages]

    for rnd in range(max_rounds):
        # Prépare la page (grow/_vscale recalculés sur l'état courant) puis
        # mesure la tenue de chaque paragraphe traduit.
        offenders = []
        for page in pages:
            try:
                engine._prepare_translated_page(page)
            except Exception:
                pass
            for el in page.get("elements", []):
                if el.get("type") != "paragraph" or not el.get("_needs_shorter"):
                    continue
                fit = engine.translated_fit(el)
                if fit is None:
                    continue
                offenders.append((el, fit))
        if not offenders:
            break
        if progress:
            progress(f"{len(offenders)} paragraphe(s) trop longs -> "
                     f"retraduction compacte (tour {rnd + 1}).")
        shrink = 1.0 - 0.08 * rnd               # budgets resserrés au 2e tour
        batch = []
        refs = {}
        for k, (el, fit) in enumerate(offenders):
            src_tagged, _meta = tagging.tag_paragraph(el)
            if not src_tagged.strip():
                continue
            src_len = len(re.sub(r"\[\[/?\d+\]\]", "", src_tagged))
            # PLANCHER : ne jamais demander moins de ~0,92 × la longueur
            # SOURCE — en dessous, le modèle n'a d'autre issue que d'abréger
            # (« Ch7 », sigles), ce que la règle produit interdit. Le petit
            # dépassement restant est absorbé par la compression du rendu
            # (préférable à une abréviation).
            budget = max(int(0.92 * src_len), int(fit["budget"] * shrink))
            cur_len = len(re.sub(r"\[\[/?\d+\]\]", "", el.get("tr_tagged") or ""))
            if cur_len <= budget:
                continue                        # rien à gagner : garder tel quel
            _id = f"c{rnd}_{k}"
            batch.append({"id": _id, "text": src_tagged,
                          "consigne": (f"MAXIMUM {budget} caractères (hors "
                                       "balises), par REFORMULATION uniquement :"
                                       " AUCUNE abréviation, AUCUN sigle absent"
                                       " du texte source, ne rien omettre "
                                       "d'essentiel.")})
            refs[_id] = el
        for i in range(0, len(batch), 20):
            sub = batch[i:i + 20]
            try:
                tr._translate_batch(sub, lang_name, progress)
            except Exception as e:
                if progress:
                    progress(f"[!] retraduction : lot échoué : {e}")
            for b in sub:
                el = refs[b["id"]]
                out = b.get("translated_text")
                if out and _tags_ok(b["text"], out):
                    el["tr_tagged"] = out
    return data
