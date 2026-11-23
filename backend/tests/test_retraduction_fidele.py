"""Retraduction compacte : raccourcir, jamais résumer.

Cas réel (4S_EN.pdf) : « In this section we will learn about 4S. » (39 car.)
traduit fidèlement « Dans cette partie, nous allons découvrir les 4S. » (48)
déborde ; la retraduction compacte a renvoyé « Les 4S en bref » (14) et le
moteur l'a ACCEPTÉE — seules les balises étaient contrôlées.

Plancher de fidélité : une version compacte plus courte que 60 % de la source
est rejetée, la traduction fidèle est gardée (le léger débordement est absorbé
par la compression du rendu).

IA, moteur et découpe SIMULÉS : aucun appel réseau.

Exécution :  cd backend && venv/Scripts/python.exe tests/test_retraduction_fidele.py
"""
from __future__ import annotations
import sys
import types

import racine  # noqa: F401  -- met backend/ sur le chemin

from engines.pdf import translate                              # noqa: E402

SOURCE = "In this section we will learn about 4S."
FIDELE = "Dans cette partie, nous allons découvrir les 4S."


def _rejouer(reponse):
    """Fait tourner `retranslate_overflows` sur un paragraphe qui déborde ;
    l'IA simulée répond `reponse`. Renvoie (tr_tagged final, consignes vues)."""
    consignes = []

    class FakeAI:
        def lang_name(self, code):
            return "français"

        def _translate_batch(self, items, lang_name, progress, cadre=None):
            for it in items:
                consignes.append(it["consigne"])
                it["translated_text"] = reponse

    class FakeEngine:
        def _prepare_translated_page(self, page):
            pass

        def translated_fit(self, el):
            return {"budget": 39}

    fake_mod = types.ModuleType("engines.translation_ai")
    fake_mod.TranslatorAI = FakeAI
    gardes = {k: getattr(translate, k) for k in
              ("_page_support", "_cadre_page", "_cadre_lot")}
    tag_garde = translate.tagging.tag_paragraph
    mod_garde = sys.modules.get("engines.translation_ai")
    try:
        sys.modules["engines.translation_ai"] = fake_mod
        translate._page_support = lambda page: {}
        translate._cadre_page = lambda page, support, fiche: {"rang": {}, "n_page": 1}
        translate._cadre_lot = lambda cadre, rangs, n: cadre
        translate.tagging.tag_paragraph = lambda el: (el["_src"], None)
        el = {"type": "paragraph", "_needs_shorter": True,
              "_src": SOURCE, "tr_tagged": FIDELE}
        translate.retranslate_overflows({"pages": [{"elements": [el]}]},
                                        FakeEngine())
        return el["tr_tagged"], consignes
    finally:
        for k, v in gardes.items():
            setattr(translate, k, v)
        translate.tagging.tag_paragraph = tag_garde
        if mod_garde is not None:
            sys.modules["engines.translation_ai"] = mod_garde
        else:
            sys.modules.pop("engines.translation_ai", None)


def run():
    checks = []

    final, consignes = _rejouer("Les 4S en bref")
    checks.append(("résumé (14/39 car.) rejeté : traduction fidèle gardée",
                   final == FIDELE, final))

    compacte = "Ici, nous découvrirons les 4S."     # 30 car. >= 60 % de 39
    final, _ = _rejouer(compacte)
    checks.append(("reformulation compacte fidèle acceptée",
                   final == compacte, final))

    checks.append(("consigne : ne rien omettre (plus « d'essentiel »)",
                   bool(consignes) and all("ne rien omettre" in c
                                           and "essentiel" not in c
                                           for c in consignes),
                   consignes[:1]))

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if detail and not cond else ""))
    passe = sum(1 for _, c, _ in checks if c)
    print(f"\n  {passe}/{len(checks)}\n")
    return 0 if passe == len(checks) else 1


if __name__ == "__main__":
    sys.exit(run())
