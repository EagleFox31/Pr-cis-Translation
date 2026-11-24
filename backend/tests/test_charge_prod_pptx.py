"""Échec PPTX en production (2026-11-24) : les trois garde-fous.

Ce qui est MESURÉ :
  • `office_illisible` : un Office complet passe, un Office tronqué, une
    archive sans sa partie principale ou un faux fichier sont refusés ; les
    autres formats ne sont jamais concernés ;
  • `log_error_threadsafe` depuis un thread : confié à la boucle principale
    quand elle est connue (jamais de boucle jetable sur le pool global, cause
    du « attached to a different loop ») ; sinon moteur dédié sans pool ;
  • `rendre_memoire` ne lève jamais et rend la main ;
  • `PPTX_SLIDE_WORKERS` se règle par l'environnement, minimum 1.

Exécution :  cd backend && venv/Scripts/python.exe tests/test_charge_prod_pptx.py
Ne touche pas à la base.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import threading
import zipfile
from io import BytesIO
from unittest.mock import patch

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.services import error_log                         # noqa: E402
from app.services.memoire import rendre_memoire            # noqa: E402
from app.services.office import office_illisible           # noqa: E402


def _office(partie: str) -> bytes:
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(partie, "<racine/>" + "x" * 2000)
    return tampon.getvalue()


def test_integrite_office() -> None:
    for ext, partie in (("pptx", "ppt/presentation.xml"),
                        ("docx", "word/document.xml"),
                        ("xlsx", "xl/workbook.xml")):
        complet = _office(partie)
        assert not office_illisible(complet, ext), ext
        assert office_illisible(complet[: len(complet) // 2], ext), ext
        assert office_illisible(b"PK pas une archive", ext), ext
        assert office_illisible(_office("autre/chose.xml"), ext), ext
    # Un .docx déposé sous l'extension .pptx n'est pas une présentation.
    assert office_illisible(_office("word/document.xml"), "pptx")
    for ext in ("pdf", "txt", ""):
        assert not office_illisible(b"%PDF tronque", ext), ext


def test_journal_depuis_un_thread() -> None:
    appels: list[tuple[str, int]] = []

    async def faux_log_error(source, message, **kw):
        appels.append(("principale", id(asyncio.get_running_loop())))

    async def faux_hors_pool(source, message, **kw):
        appels.append(("jetable", id(asyncio.get_running_loop())))

    async def scenario() -> None:
        boucle = asyncio.get_running_loop()
        error_log.install_db_log_handler()
        assert error_log._boucle is boucle
        fil = threading.Thread(
            target=error_log.log_error_threadsafe, args=("backend", "panne"))
        fil.start()
        await asyncio.to_thread(fil.join)
        for _ in range(50):
            if appels:
                break
            await asyncio.sleep(0.01)
        assert appels == [("principale", id(boucle))], appels

    with patch.object(error_log, "log_error", faux_log_error), \
         patch.object(error_log, "_log_error_hors_pool", faux_hors_pool):
        asyncio.run(scenario())
        # Boucle principale terminée : repli sur le moteur dédié, sans lever.
        appels.clear()
        error_log.log_error_threadsafe("backend", "apres arret")
        assert [a[0] for a in appels] == ["jetable"], appels
        error_log._boucle = None
        appels.clear()
        error_log.log_error_threadsafe("backend", "sans boucle")
        assert [a[0] for a in appels] == ["jetable"], appels


def test_memoire_et_reglage() -> None:
    assert rendre_memoire() in (True, False)
    from app import config
    with patch.dict(os.environ, {"PPTX_SLIDE_WORKERS": "2"}):
        assert importlib.reload(config).PPTX_SLIDE_WORKERS == 2
    with patch.dict(os.environ, {"PPTX_SLIDE_WORKERS": "0"}):
        assert importlib.reload(config).PPTX_SLIDE_WORKERS == 1
    os.environ.pop("PPTX_SLIDE_WORKERS", None)
    assert importlib.reload(config).PPTX_SLIDE_WORKERS == 4


def main() -> None:
    test_integrite_office()
    test_journal_depuis_un_thread()
    test_memoire_et_reglage()
    print("OK test_charge_prod_pptx")


if __name__ == "__main__":
    main()
