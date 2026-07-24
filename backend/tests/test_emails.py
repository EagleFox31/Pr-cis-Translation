"""Les e-mails transactionnels : bonne langue, bonne identité, bien formés.

CE QUI EST VÉRIFIÉ
  1. LANGUE    — la langue de l'INTERFACE décide, pas celle du système ; toute
                 langue inconnue retombe sur le français, jamais sur du vide.
  2. CONTENU   — le code et le lien sont présents dans les DEUX versions (HTML
                 et texte brut). Un client qui refuse le HTML doit pouvoir se
                 connecter.
  3. IDENTITÉ  — le logo voyage DANS le message (`cid:`), jamais par une URL.
  4. STRUCTURE — `related` enveloppe `alternative`, sinon le logo apparaît en
                 pièce jointe séparée chez plusieurs clients.
  5. HYGIÈNE   — expéditeur affiché, en-têtes anti-réponse-automatique.
  6. BRIÈVETÉ  — un e-mail transactionnel a UN travail ; on le mesure.

Aucun réseau, aucun serveur SMTP : on compose le message et on le lit.

    backend/venv/Scripts/python.exe backend/tests/test_emails.py
"""
from __future__ import annotations

import re
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.core.email import (LOGO_CID, _message_verification,  # noqa: E402
                            _logo)
from app.core.email_content import LANGUES, normaliser_langue  # noqa: E402


def _partie(msg, sous_type):
    for p in msg.walk():
        if p.get_content_subtype() == sous_type and p.get_content_maintype() == "text":
            return p.get_payload(decode=True).decode("utf-8")
    return ""


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # ── 1. La langue ─────────────────────────────────────────────────────
    cas = [
        ("fr", "fr"), ("en", "en"),
        ("fr-CA", "fr"), ("en-GB,en;q=0.9", "en"),
        ("de", "fr"),            # langue non prise en charge -> defaut
        ("", "fr"), (None, "fr"),
        ("EN-us", "en"),         # casse indifferente
    ]
    for entree, attendu in cas:
        ok(f"LANGUE  « {entree!r} » -> {attendu}",
           normaliser_langue(entree) == attendu,
           normaliser_langue(entree))

    # Le sujet et le corps changent VRAIMENT d'une langue a l'autre : sans ce
    # controle, un dictionnaire ou les deux langues sont identiques passerait.
    sujets, titres = set(), set()
    for lg in LANGUES:
        m = _message_verification("a@b.c", "123456", "TOK", lg)
        sujets.add(str(m["Subject"]))
        titres.add(_partie(m, "plain"))
    ok("LANGUE  chaque langue a SON sujet", len(sujets) == len(LANGUES),
       str(sujets))
    ok("LANGUE  chaque langue a SON corps", len(titres) == len(LANGUES))

    # ── 2. Le contenu, dans les DEUX versions ────────────────────────────
    msg = _message_verification("client@exemple.fr", "482915", "JETON42", "fr")
    html, texte = _partie(msg, "html"), _partie(msg, "plain")
    for nom, corps in (("HTML", html), ("texte brut", texte)):
        ok(f"CONTENU  le code figure dans la version {nom}", "482915" in corps)
        ok(f"CONTENU  le lien figure dans la version {nom}", "JETON42" in corps)
    ok("CONTENU  une version TEXTE existe (client sans HTML)", bool(texte.strip()))

    # ── 3. L'identité voyage avec le message ─────────────────────────────
    logo = _logo()
    ok("IDENTITE  le logo est trouve sur le disque", logo is not None)
    cids = [p.get("Content-ID") for p in msg.walk() if p.get("Content-ID")]
    ok("IDENTITE  le logo est joint avec son Content-ID",
       f"<{LOGO_CID}>" in cids, str(cids))
    ok("IDENTITE  le HTML pointe le logo par cid:, pas par une URL",
       f"cid:{LOGO_CID}" in html)
    ok("IDENTITE  aucune image DISTANTE (bloquee par defaut, et mouchard)",
       not re.search(r'<img[^>]+src="https?://', html), html[:200])
    ok("IDENTITE  la marque apparait dans l'expediteur",
       "Précis" in str(msg["From"]), str(msg["From"]))

    # ── 4. La structure MIME ─────────────────────────────────────────────
    ok("STRUCTURE  le message est `related` (HTML + son image)",
       msg.get_content_subtype() == "related", msg.get_content_subtype())
    sous = [p.get_content_subtype() for p in msg.get_payload()
            if hasattr(p, "get_content_subtype")]
    ok("STRUCTURE  il contient un `alternative` (HTML + texte)",
       "alternative" in sous, str(sous))

    # ── 5. Hygiene ───────────────────────────────────────────────────────
    ok("HYGIENE  le sujet porte le code (visible sans ouvrir)",
       "482915" in str(msg["Subject"]), str(msg["Subject"]))
    ok("HYGIENE  aucune reponse automatique ne sera declenchee",
       msg["Auto-Submitted"] == "auto-generated"
       and msg["X-Auto-Response-Suppress"] == "All")
    ok("HYGIENE  un Reply-To est pose", bool(msg["Reply-To"]))

    # ── 6. Brievete ──────────────────────────────────────────────────────
    # L'ancienne version deroulait trois paragraphes pour expliquer ce que le
    # code affiche disait deja. On borne, sans quoi « plus court » ne veut rien
    # dire et le texte regrossira au premier ajout.
    mots = len(texte.split())
    ok("BRIEVETE  la version texte tient en moins de 40 mots",
       mots < 40, f"{mots} mots")
    phrases = [p for p in re.split(r"[.\n]", texte) if p.strip()]
    ok("BRIEVETE  pas plus de 6 phrases", len(phrases) <= 6, str(len(phrases)))

    print()
    n_ok = sum(1 for _, c, _ in checks if c)
    for nom, cond, detail in checks:
        ligne = ("  OK  " if cond else " FAIL ") + f"  {nom}"
        if not cond and detail:
            ligne += f"   [{detail}]"
        print(ligne)
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
