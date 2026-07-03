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
import sys

from . import tagging

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
                progress(f"⚠️ lot {i // batch_size} échoué : {e}")
        for b in batch:
            el = refs[b["id"]]
            el["tr_tagged"] = b.get("translated_text") or b["text"]
        if progress:
            progress(f"  lot {i // batch_size + 1}/"
                     f"{(len(items) + batch_size - 1) // batch_size} traduit.")

    return data
