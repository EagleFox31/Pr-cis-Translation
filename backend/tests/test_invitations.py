"""L'e-mail d'invitation : personnalisé, de marque, et SANS injection.

CE QUI EST VÉRIFIÉ
  1. SÉCURITÉ  — le nom et le mot saisis par l'inviteur sont échappés : pas de
                 balise, pas de lien glissé dans un e-mail qui part sous notre nom.
  2. EN-TÊTES  — sujet sur une ligne (pas d'injection d'en-tête), Reply-To vers
                 l'inviteur, expéditeur de marque.
  3. CONTENU   — lien vers l'app et nom de l'inviteur dans les DEUX versions ;
                 le mot personnel n'apparaît que s'il est fourni.
  4. IDENTITÉ  — logo embarqué (`cid:`), structure `related` > `alternative`.
  5. LANGUE    — français et anglais, repli sur le français.

    backend/venv/Scripts/python.exe backend/tests/test_invitations.py
"""
from __future__ import annotations

import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.core.email import FRONTEND_URL, LOGO_CID, _message_invitation  # noqa: E402
from app.core.email_content import MARQUE  # noqa: E402


def _partie(msg, sous_type):
    for p in msg.walk():
        if p.get_content_type() == f"text/{sous_type}":
            return p.get_payload(decode=True).decode("utf-8")
    return ""


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    hostile = 'Eve <script>alert(1)</script>\r\nBcc: x@y.z'
    mot = 'Regarde <a href="http://evil">ici</a>\nÀ plus'
    msg = _message_invitation("ami@exemple.com", hostile, "eve@exemple.com", mot, "fr")
    html, texte = _partie(msg, "html"), _partie(msg, "plain")

    # 1. Sécurité
    check("html : <script> échappé", "<script>" not in html and "&lt;script&gt;" in html)
    check("html : lien du mot échappé", 'href="http://evil"' not in html)
    check("html : saut de ligne du mot → <br>", "ici&lt;/a&gt;<br>À plus" in html)

    # 2. En-têtes
    check("sujet sur une seule ligne", "\n" not in msg["Subject"] and "\r" not in msg["Subject"],
          repr(msg["Subject"]))
    check("pas d'en-tête Bcc injecté", msg["Bcc"] is None)
    check("Reply-To = inviteur", msg["Reply-To"] == "eve@exemple.com")
    check("expéditeur de marque", str(msg["From"]).startswith(MARQUE["nom"]))
    check("destinataire", msg["To"] == "ami@exemple.com")

    # 3. Contenu
    check("html : lien vers l'app", f'href="{FRONTEND_URL}"' in html)
    check("texte : lien vers l'app", FRONTEND_URL in texte)
    check("texte : nom de l'inviteur", "Eve" in texte)
    check("texte : mot personnel", "À plus" in texte)
    sans = _message_invitation("ami@exemple.com", "Eve", "eve@exemple.com", None, "fr")
    check("sans mot : pas de bloc citation", "border-left:3px" not in _partie(sans, "html"))
    check("sans mot : pas de « » vides", "«" not in _partie(sans, "plain"))

    # 4. Identité / structure
    check("logo en cid:", f"cid:{LOGO_CID}" in html)
    check("structure related > alternative",
          msg.get_content_type() == "multipart/related"
          and msg.get_payload()[0].get_content_type() == "multipart/alternative")
    check("pas d'accolade non remplie", "{" not in html and "{" not in texte)

    # 5. Langue
    en = _message_invitation("a@b.c", "Eve", "eve@exemple.com", None, "en")
    check("anglais : html lang=en", 'lang="en"' in _partie(en, "html"))
    check("anglais ≠ français", en["Subject"] != sans["Subject"], en["Subject"])

    n_ok = sum(1 for _, c, _ in checks if c)
    for nom, cond, detail in checks:
        print(f"{'OK ' if cond else 'KO '} {nom}" + (f"  — {detail}" if detail and not cond else ""))
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
