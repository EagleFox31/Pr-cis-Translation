"""Grille tarifaire — la baisse zone A, l'échelle de vitesse, et l'ACCORD entre
la source (`pricing`/`plans`) et ce que l'endpoint `/api/pricing` publie.

Ce qui est MESURÉ :
  • les prix zone A sont bien les valeurs BASSES décidées le 24/07 (garde la
    décision : une remontée accidentelle à 2500/6900 échoue ici) ;
  • la priorité est une ÉCHELLE strictement croissante free < starter < pro —
    sinon « payer = aller plus vite » ne veut rien dire ;
  • l'endpoint publie, pour chaque plan, la MÊME priorité que `get_plan_priority`
    (accord source ↔ API ; tester la valeur des deux côtés serait aveugle, on
    teste qu'ils CONCORDENT) ;
  • un pays inconnu retombe en zone plein tarif (invariant conservé).

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_pricing.py
N'ouvre aucune connexion réseau ni base — pur calcul.
"""
from __future__ import annotations
import asyncio
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import Request                                  # noqa: E402

from app.core.pricing import (DEFAULT_ZONE, ZONE_AFRICA,     # noqa: E402
                              ZONE_GLOBAL, page_price, plan_price,
                              zone_for_country)
from app.models import get_plan_priority                     # noqa: E402
from app.api.system import pricing as pricing_route          # noqa: E402

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


def _fake_request() -> Request:
    """Requête minimale sans en-tête géo : force le repli plein tarif, qu'on
    contourne ensuite via le paramètre `country`."""
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/api/pricing"}
    return Request(scope)


async def main() -> None:
    # ── 1. Baisse zone A (valeurs littérales, garde-décision) ──────────────────
    check(plan_price("starter", ZONE_AFRICA) == 1500, "Starter zone A = 1500 F/mois")
    check(plan_price("starter", ZONE_AFRICA, annual=True) == 1200, "Starter zone A = 1200 F/an")
    check(plan_price("pro", ZONE_AFRICA) == 4500, "Pro zone A = 4500 F/mois")
    check(plan_price("pro", ZONE_AFRICA, annual=True) == 3500, "Pro zone A = 3500 F/an")
    check(page_price(ZONE_AFRICA) == 75, "Page à l'unité zone A = 75 F")

    # ── 2. Vitesse : échelle strictement croissante ───────────────────────────
    pf, ps, pp = (get_plan_priority(p) for p in ("free", "starter", "pro"))
    check(pf < ps < pp, f"priorité croissante free<starter<pro ({pf}<{ps}<{pp})")
    check(get_plan_priority("free") == 0, "le gratuit est en file standard (priorité 0)")

    # ── 3. Accord source ↔ endpoint ───────────────────────────────────────────
    #    On demande explicitement la zone A ; l'endpoint doit republier, pour
    #    chaque plan, exactement la priorité que la source calcule.
    payload = await pricing_route(_fake_request(), country="CM")
    check(payload["zone"] == ZONE_AFRICA, "CM -> zone A")
    by_key = {p["key"]: p for p in payload["plans"]}
    accord = all(by_key[k]["priority"] == get_plan_priority(k)
                 for k in ("free", "starter", "pro", "enterprise"))
    check(accord, "l'endpoint publie la priorité de get_plan_priority (accord)")
    check(by_key["starter"]["monthly"] == 1500 and payload["page_price"] == 75,
          "l'endpoint sert bien les prix zone A baissés")

    # ── 4. Invariant conservé : pays inconnu -> plein tarif ─────────────────────
    check(zone_for_country("ZZ") == DEFAULT_ZONE == ZONE_GLOBAL,
          "pays inconnu -> zone plein tarif (on ne brade pas)")

    # ── Verdict ───────────────────────────────────────────────────────────────
    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} contrôles")
    if passed != total:
        print("ÉCHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK — grille tarifaire conforme")


if __name__ == "__main__":
    asyncio.run(main())
