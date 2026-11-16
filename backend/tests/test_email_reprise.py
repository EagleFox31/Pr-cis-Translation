"""Envoi SMTP avec reprise : les ratés passagers sont réessayés, pas les refus.

CE QUI EST VÉRIFIÉ
  1. PASSAGER  — connexion coupée puis rétablie : le message part, 3 essais.
  2. DÉFINITIF — refus 5xx : un seul essai, l'erreur remonte telle quelle.
  3. ÉPUISÉ    — panne qui dure : 3 essais puis l'erreur parlante.
  4. ALERTE    — `send_plain` ne lève pas et renvoie False en cas d'échec.

Aucun réseau : `aiosmtplib.send` et l'attente sont remplacés.

    backend/venv/Scripts/python.exe backend/tests/test_email_reprise.py
"""
from __future__ import annotations

import asyncio
import os
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

os.environ.setdefault("SMTP_FROM", "bonjour@example.com")

import aiosmtplib  # noqa: E402

import app.core.email as email_mod  # noqa: E402

checks: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    checks.append((bool(ok), label))


class FauxSMTP:
    """Échoue avec les erreurs données, dans l'ordre, puis réussit."""

    def __init__(self, erreurs: list[Exception]):
        self.erreurs = list(erreurs)
        self.appels = 0

    async def __call__(self, msg, **kw):  # noqa: ANN001
        self.appels += 1
        if self.erreurs:
            raise self.erreurs.pop(0)
        return ({}, "OK")


async def _scenarios() -> None:
    attentes: list[float] = []

    async def pas_d_attente(s):  # noqa: ANN001
        attentes.append(s)

    email_mod.EMAIL_ENABLED = True
    email_mod.SMTP_HOST = "smtp.example.com"
    orig_send, orig_sleep = aiosmtplib.send, asyncio.sleep
    asyncio.sleep = pas_d_attente
    try:
        # 1. Passager puis rétabli
        faux = FauxSMTP([aiosmtplib.SMTPServerDisconnected("coupé"),
                         aiosmtplib.SMTPResponseException(421, "plus tard")])
        aiosmtplib.send = faux
        await email_mod.send_verification_email("a@example.com", "123456", "tok")
        check(faux.appels == 3, f"passager : 3 essais (vu {faux.appels})")
        check(attentes == [2, 5], f"attentes 2 s puis 5 s (vu {attentes})")

        # 2. Refus définitif
        faux = FauxSMTP([aiosmtplib.SMTPResponseException(550, "inconnu")])
        aiosmtplib.send = faux
        try:
            await email_mod.send_verification_email("b@example.com", "123456", "tok")
            check(False, "définitif : l'erreur devait remonter")
        except email_mod.EmailIndisponible:
            check(faux.appels == 1, f"définitif : un seul essai (vu {faux.appels})")

        faux = FauxSMTP([aiosmtplib.SMTPRecipientsRefused(
            [aiosmtplib.SMTPRecipientRefused(550, "non", "c@example.com")])])
        aiosmtplib.send = faux
        try:
            await email_mod.send_verification_email("c@example.com", "123456", "tok")
        except email_mod.EmailIndisponible:
            pass
        check(faux.appels == 1, f"destinataire refusé : un seul essai (vu {faux.appels})")

        faux = FauxSMTP([aiosmtplib.SMTPAuthenticationError(535, "mauvais")])
        aiosmtplib.send = faux
        try:
            await email_mod.send_verification_email("d@example.com", "123456", "tok")
        except email_mod.EmailIndisponible:
            pass
        check(faux.appels == 1, f"identifiants faux : un seul essai (vu {faux.appels})")

        # 3. Panne qui dure
        faux = FauxSMTP([aiosmtplib.SMTPConnectError("refusé")] * 5)
        aiosmtplib.send = faux
        try:
            await email_mod.send_verification_email("e@example.com", "123456", "tok")
            check(False, "épuisé : l'erreur devait remonter")
        except email_mod.EmailIndisponible:
            check(faux.appels == 3, f"épuisé : 3 essais puis abandon (vu {faux.appels})")

        # 4. Alerte interne
        faux = FauxSMTP([aiosmtplib.SMTPConnectError("refusé")] * 5)
        aiosmtplib.send = faux
        ok = await email_mod.send_plain("admin@example.com", "Sujet", "Corps")
        check(ok is False, "alerte ratée : renvoie False sans lever")
        faux = FauxSMTP([])
        aiosmtplib.send = faux
        ok = await email_mod.send_plain("admin@example.com", "Sujet", "Corps")
        check(ok is True and faux.appels == 1, "alerte réussie : renvoie True")
    finally:
        aiosmtplib.send, asyncio.sleep = orig_send, orig_sleep


def main() -> int:
    asyncio.run(_scenarios())
    n_ok = sum(ok for ok, _ in checks)
    for ok, label in checks:
        print(f"{'OK ' if ok else 'KO '} {label}")
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
