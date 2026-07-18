"""
Tests des EXPRESSIONS PIÈGES (backend/glossary.py) — hors ligne, aucun appel API.

Deux niveaux :
  • RÉSOLUTION  — le bon rendu est-il choisi selon le support / l'urgence / le direct ?
  • FILET       — une sortie de modèle contenant un rendu INTERDIT est-elle corrigée ?

    backend/venv/Scripts/python.exe backend/test_glossary.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glossary


def entry(eid):
    e = next((x for x in glossary._entries("en", "fr") if x["id"] == eid), None)
    assert e, f"entrée absente du glossaire : {eid}"
    return e


# ── 1) RÉSOLUTION : (texte, support, contexte) -> rendu attendu ───────────────
RESOLVE = [
    # « breaking news » : le MÊME texte donne 3 rendus selon le contexte.
    ("breaking-news", "BREAKING NEWS", "titre", "",
     "FLASH INFO",          "bandeau d'affiche, urgence ordinaire"),
    ("breaking-news", "BREAKING NEWS", "titre", "Watch live coverage now",
     "EN DIRECT",           "diffusion en cours signalée par le contexte"),
    ("breaking-news", "BREAKING NEWS", "titre", "Emergency evacuation after attack",
     "ALERTE INFO",         "urgence maximale (evacuation + attack)"),
    ("breaking-news", "The breaking news was reported at 6pm.", "corps", "",
     "Dernières nouvelles", "dans une phrase : registre neutre, pas un bandeau"),

    ("actually", "Actually, the file is empty.", "corps", "",
     "en fait", "faux ami : jamais « actuellement »"),
    ("eventually", "The task eventually completed.", "corps", "",
     "finalement", "faux ami : jamais « éventuellement »"),
    ("youre-welcome", "You're welcome", "titre", "",
     "Je vous en prie", "formule isolée, registre soutenu"),
    ("youre-welcome", "You're welcome to try again.", "corps", "",
     "De rien", "registre courant"),
    ("library", "Install the library.", "corps", "",
     "bibliothèque", "jamais « librairie »"),
    ("coming-soon", "COMING SOON", "titre", "",
     "Prochainement", "affiche"),
    ("top-stories", "TOP STORIES", "titre", "",
     "À LA UNE", "rubrique de presse (casse alignée sur la source)"),
    ("issue", "ISSUE 42", "titre", "",
     "numéro", "presse : livraison d'un périodique"),
    ("issue", "We fixed the issue.", "corps", "",
     "problème", "technique : dysfonctionnement"),
]

# ── 2) FILET : sortie fautive du modèle -> sortie corrigée ────────────────────
ENFORCE = [
    ("[[0]]BREAKING NEWS[[/0]]", "[[0]]DERNIÈRES MINUTES[[/0]]", "titre", "",
     "[[0]]FLASH INFO[[/0]]",
     "le bug d'origine : le rendu interdit est remplacé, balises intactes"),
    ("[[0]]BREAKING NEWS[[/0]]", "[[0]]Dernières minutes[[/0]]", "titre",
     "Watch live now", "[[0]]EN DIRECT[[/0]]",
     "corrigé vers le rendu du contexte (direct)"),
    ("[[0]]Actually[[/0]], it works.", "[[0]]Actuellement[[/0]], ça marche.",
     "corps", "", "[[0]]en fait[[/0]], ça marche.",
     "faux ami corrigé au milieu d'une phrase balisée"),
    ("[[0]]BREAKING NEWS[[/0]]", "[[0]]FLASH INFO[[/0]]", "titre", "",
     "[[0]]FLASH INFO[[/0]]",
     "sortie DÉJÀ correcte : le filet ne doit RIEN changer"),
    ("[[0]]The library is open.[[/0]]", "[[0]]La bibliothèque est ouverte.[[/0]]",
     "corps", "", "[[0]]La bibliothèque est ouverte.[[/0]]",
     "sortie correcte : pas de faux positif"),
]


def main():
    ok = fail = 0

    print("=" * 78)
    print("1) RÉSOLUTION — le bon rendu selon support / urgence / direct")
    print("=" * 78)
    for eid, text, support, ctx, expected, why in RESOLVE:
        got = glossary.resolve(entry(eid), text, support=support, context=ctx)
        good = got == expected
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  [{'OK ' if good else 'ÉCHEC'}] {text!r} ({support})"
              f"{' + ctx' if ctx else ''}")
        print(f"          -> {got!r}" + ("" if good else f"  ATTENDU {expected!r}"))
        print(f"          urgence={glossary.urgency_score(text, ctx)}/10 "
              f"direct={glossary.is_live(text, ctx)} — {why}")

    print()
    print("=" * 78)
    print("2) FILET — un rendu INTERDIT sorti du modèle est corrigé")
    print("=" * 78)
    for src, model_out, support, ctx, expected, why in ENFORCE:
        got, fixed = glossary.enforce(src, model_out, support=support, context=ctx)
        good = got == expected
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  [{'OK ' if good else 'ÉCHEC'}] modèle: {model_out!r}")
        print(f"          -> {got!r}" + ("" if good else f"  ATTENDU {expected!r}"))
        print(f"          corrigé={fixed or '—'} — {why}")

    print()
    print("=" * 78)
    print("3) MÉMOIRE DE DOCUMENT — un titre répété garde SA première traduction")
    print("=" * 78)
    # Hors ligne : le traducteur est un FAUX qui change d'avis entre deux pages
    # — exactement le défaut mesuré (« PARTIE UN » p4, « DEUXIÈME PARTIE » plus
    # bas). La mémoire doit primer : même texte → même traduction, sans rappel.
    import types
    import fitz
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from pdf_engine_v2 import translate as _tr
    from pdf_engine_v2.engine import PDFObjectEngine

    class _Faux:
        version = 0        # incrémenté entre les « pages » : trahit un rappel
        appels = []

        def lang_name(self, lang):
            return "français"

        def _translate_batch(self, batch, lang_name, progress=None):
            for it in batch:
                plain = _tr._plain_key(it["text"])
                _Faux.appels.append(plain)
                it["translated_text"] = it["text"].replace(
                    plain, f"{plain}-fr{_Faux.version}")

    vrai = sys.modules.get("translator_ai")
    faux_mod = types.ModuleType("translator_ai")
    faux_mod.TranslatorAI = _Faux
    sys.modules["translator_ai"] = faux_mod
    try:
        doc = fitz.open()
        for _ in range(2):
            pg = doc.new_page(width=400, height=200)
            pg.insert_text((40, 60), "Quarterly Report", fontsize=14)
            pg.insert_text((40, 120), "Some longer body sentence appears here.",
                           fontsize=10)
        eng = PDFObjectEngine()
        mem = {}
        pd1 = eng.extract_page_data(doc, 0, doc[0])
        _tr.translate_extraction({"pages": [pd1], "fonts": {}},
                                 target_lang="fr", doc_memory=mem)
        _Faux.version = 1                      # le modèle « change d'avis »
        pd2 = eng.extract_page_data(doc, 1, doc[1])
        _tr.translate_extraction({"pages": [pd2], "fonts": {}},
                                 target_lang="fr", doc_memory=mem)

        def _tr_of(pd, frag):
            for el in pd.get("elements", []):
                if frag in (el.get("text") or ""):
                    return el.get("tr_tagged") or ""
            return ""
        t1, t2 = _tr_of(pd1, "Quarterly"), _tr_of(pd2, "Quarterly")
        good = ("fr0" in t1 and t2 == t1)
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  [{'OK ' if good else 'ÉCHEC'}] même titre, même traduction "
              f"(p1={t1[:40]!r} p2={t2[:40]!r})")
        rappels = _Faux.appels.count("Quarterly Report")
        good = rappels == 1
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  [{'OK ' if good else 'ÉCHEC'}] le titre répété n'est envoyé "
              f"qu'UNE fois au modèle ({rappels} appel(s))")
        # Le corps, lui, suit le modèle de sa page (pas de mémoire au long cours).
        c2 = _tr_of(pd2, "longer body")
        good = "fr1" in c2 or "fr0" in c2      # court : mémorisé aussi (≤ 120)
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  [{'OK ' if good else 'ÉCHEC'}] le corps est bien traduit "
              f"({c2[:40]!r})")
    finally:
        if vrai is not None:
            sys.modules["translator_ai"] = vrai
        else:
            sys.modules.pop("translator_ai", None)

    print()
    print(f"== {ok} réussite(s), {fail} échec(s) ==")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
