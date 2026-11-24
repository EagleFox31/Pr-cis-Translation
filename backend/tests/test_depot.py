"""Envoi unique du fichier (docs/etude-test-gros-fichier.md, option C).

Le fichier est déposé une fois par `/api/upload`, puis relu par son
identifiant. On vérifie :
  • dépôt puis aperçu par identifiant, sans renvoyer le fichier ;
  • un dépôt n'est lisible que par le compte qui l'a envoyé ;
  • il expire après 24 heures et la purge l'efface du disque ;
  • une taille annoncée au-delà de 100 Mo est refusée avant la réception ;
  • un identifiant inconnu répond 410 (le navigateur renvoie alors le fichier) ;
  • un type refusé ou un corps vide ne crée rien ;
  • un Office tronqué (envoi coupé) est refusé au dépôt et ne crée rien.

Exécution :  cd backend && venv/Scripts/python.exe tests/test_depot.py
Ne touche pas à la base : la session est simulée.
"""
from __future__ import annotations
import os
import shutil
import tempfile
import time
import zipfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi.testclient import TestClient                # noqa: E402

from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.core.security import require_auth               # noqa: E402
from app.services import depots                          # noqa: E402

PDF = b"%PDF-1.4 contenu de test"


def _pptx() -> bytes:
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("ppt/presentation.xml", "<p:presentation/>")
        z.writestr("ppt/slides/slide1.xml", "x" * 4000)
    return tampon.getvalue()


PPTX = _pptx()
CLE = {"X-API-Key": cfg.FRONTEND_API_KEY}


def main():
    dossier = tempfile.mkdtemp(prefix="depots-")
    compte = {"user": SimpleNamespace(id=101)}
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: compte["user"]
    client = TestClient(app)  # sans `with` : pas de démarrage (base) nécessaire
    try:
        with patch.object(depots, "DOSSIER", dossier), \
             patch("app.api.translate.convert_to_pdf_bytes",
                   side_effect=lambda data, ext: b"PDF:" + data) as conv:
            # Dépôt : un identifiant, un dossier sur le disque.
            r = client.post("/api/upload?nom=rapport.pdf", content=PDF,
                            headers={**CLE, "Content-Type": "application/octet-stream"})
            assert r.status_code == 200, r.text
            depot_id = r.json()["upload_id"]
            assert r.json()["taille"] == len(PDF)
            assert os.path.isdir(os.path.join(dossier, depot_id))

            # Un PDF n'a pas de conversion préparée ; un PowerPoint, si.
            assert not conv.called
            r = client.post("/api/upload?nom=slides.pptx", content=PPTX,
                            headers={**CLE, "Content-Type": "application/octet-stream"})
            assert r.status_code == 200, r.text
            assert conv.call_args.args == (PPTX, "pptx"), conv.call_args

            # Aperçu par identifiant : seul `upload_id` part, le contenu est relu.
            r = client.post("/api/preview/pdf", data={"upload_id": depot_id}, headers=CLE)
            assert r.status_code == 200, r.text
            assert r.content in (PDF, b"PDF:" + PDF), r.content[:40]

            # Un autre compte ne lit pas ce dépôt (même réponse qu'un inconnu).
            compte["user"] = SimpleNamespace(id=202)
            r = client.post("/api/preview/pdf", data={"upload_id": depot_id}, headers=CLE)
            assert r.status_code == 410, r.text
            assert depots.lire(depot_id, 202) is None
            compte["user"] = SimpleNamespace(id=101)

            # Identifiant inconnu ou mal formé → 410, jamais de lecture hors dossier.
            for faux in ("0" * 32, "../../etc/passwd", "ABC"):
                r = client.post("/api/translate/analyse", data={"upload_id": faux}, headers=CLE)
                assert r.status_code == 410, (faux, r.status_code, r.text)

            # Ni fichier ni identifiant → 400.
            r = client.post("/api/preview/pdf", data={}, headers=CLE)
            assert r.status_code == 400, r.text

            # Taille annoncée trop grande : refus avant toute réception.
            r = client.post("/api/upload?nom=gros.pdf", content=PDF,
                            headers={**CLE, "Content-Length": str(cfg.MAX_FILE_SIZE + 1),
                                     "Content-Type": "application/octet-stream"})
            assert r.status_code == 413, r.text

            # Type refusé, corps vide : rien n'est créé.
            avant = set(os.listdir(dossier))
            r = client.post("/api/upload?nom=virus.exe", content=PDF, headers=CLE)
            assert r.status_code == 400, r.text
            r = client.post("/api/upload?nom=vide.pdf", content=b"", headers=CLE)
            assert r.status_code == 400, r.text
            # PPTX coupé en route (cas réel : 4,9 Mo reçus sur 19,7) : refusé
            # au dépôt avec un message clair, pas un job qui échoue plus loin.
            r = client.post("/api/upload?nom=coupe.pptx", content=PPTX[: len(PPTX) // 2],
                            headers=CLE)
            assert r.status_code == 400, r.text
            assert "incomplet" in r.json()["detail"], r.text
            assert set(os.listdir(dossier)) == avant

            # Expiration : illisible au-delà de 24 h, puis effacé par la purge.
            assert depots.lire(depot_id, 101) == ("rapport.pdf", PDF)
            plus_tard = time.time() + depots.CONSERVATION_S + 60
            with patch("app.services.depots.time.time", return_value=plus_tard):
                assert depots.lire(depot_id, 101) is None
            assert depots.purger(plus_tard) >= 1
            assert not os.path.exists(os.path.join(dossier, depot_id))
            r = client.post("/api/preview/pdf", data={"upload_id": depot_id}, headers=CLE)
            assert r.status_code == 410, r.text

            # Dépôt sans session : refusé.
            app.dependency_overrides.clear()
            r = client.post("/api/upload?nom=rapport.pdf", content=PDF, headers=CLE)
            assert r.status_code == 401, r.text
        print("OK test_depot")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    main()
