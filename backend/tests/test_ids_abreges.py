"""Le modèle abrège parfois les identifiants (« slide20_p1 » au lieu de
« slide20_p_p1 »). Le lot ne doit plus échouer pour autant : les résultats
orphelins sont appariés dans l'ordre aux blocs restés sans traduction.

    python tests/test_ids_abreges.py
"""
from __future__ import annotations
import json
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from engines import translation_ai                                     # noqa: E402
from test_deepseek_seul import _Client, _traducteur                    # noqa: E402


def _rep(paires):
    return json.dumps({"translations": [
        {"id": i, "translated_text": t} for i, t in paires]})


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    vrai_sleep = translation_ai.time.sleep
    translation_ai.time.sleep = lambda *_: None
    try:
        # Bloc unique, identifiant abrégé : un seul appel, traduit.
        c = _Client(_rep([("slide20_p1", "Hello")]))
        lot = [{"id": "slide20_p_p1", "text": "Bonjour"}]
        reussi = _traducteur(c)._translate_batch(lot, "English", None, passes=0)
        ok("bloc unique abrégé : traduit", reussi and lot[0].get("translated_text") == "Hello",
           str(lot))
        ok("bloc unique abrégé : sans relance", len(c.appels) == 1, str(len(c.appels)))

        # Mélange : un id exact, deux abrégés → appariés dans l'ordre.
        c = _Client(_rep([("a", "A"), ("s1_p1", "B"), ("s1_p2", "C")]))
        lot = [{"id": "a", "text": "a"}, {"id": "s1_p_p1", "text": "b"},
               {"id": "s1_p_p2", "text": "c"}]
        _traducteur(c)._translate_batch(lot, "English", None, passes=0)
        ok("mélange : ordre respecté",
           [b.get("translated_text") for b in lot] == ["A", "B", "C"], str(lot))

        # Nombres différents : pas d'appariement hasardeux, le lot est relancé.
        c = _Client(_rep([("x", "X")]), _rep([("p1", "U"), ("p2", "V")]))
        lot = [{"id": "p1", "text": "u"}, {"id": "p2", "text": "v"}]
        _traducteur(c)._translate_batch(lot, "English", None, passes=0)
        ok("comptes différents : relance, puis bons textes",
           len(c.appels) == 2 and [b.get("translated_text") for b in lot] == ["U", "V"],
           f"{len(c.appels)} {lot}")
    finally:
        translation_ai.time.sleep = vrai_sleep

    n_ok = sum(1 for _, c, _ in checks if c)
    for nom, cond, detail in checks:
        ligne = f"{'  OK  ' if cond else ' FAIL '}  {nom}"
        if not cond and detail:
            ligne += f"   [{detail}]"
        print(ligne)
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
