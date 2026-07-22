"""LibreOffice : la seule porte du projet vers `soffice`.

CE MODULE EST DANS `engines/` ET PAS DANS `app/`, ET C'EST VOULU
----------------------------------------------------------------
Le verrou qui sérialise les appels à LibreOffice vivait dans le module
applicatif. Le moteur PPTX en avait besoin, et faisait donc
`from app import _preview_lock` — un import TARDIF, commenté d'une excuse, pour
que le cycle ne casse pas au chargement. Un moteur qui importe son application
ne peut plus en sortir : ni pour un banc d'essai, ni pour un autre projet.

Le sens autorisé des dépendances est `app -> engines`. Placer la ressource ici
la rend accessible aux deux sans qu'aucune flèche ne remonte : l'application
l'utilise (c'est le sens normal), les moteurs aussi (ce sont des voisins).

CE QUE CE MODULE NE FAIT PAS
----------------------------
Il ne met rien en cache. Décider qu'un résultat mérite d'être conservé, et où,
est une politique de l'application — pas une propriété de la conversion. C'est
`app.services.office` qui en décide, en s'appuyant sur celui-ci.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading

# LibreOffice supporte mal les invocations concurrentes : tout appel passe par
# ce verrou. Public : c'est l'interface du module, et le moteur PPTX s'en sert
# pour envelopper ses propres conversions (régénération des aperçus OLE).
#
# NOTE — une file PRIORITAIRE a été écrite ici, puis retirée.
#
# L'idée : faire passer les conversions qu'un écran attend devant celles du
# travail de fond, en soupçonnant que le panneau source restait blanc parce
# qu'il était affamé derrière le convertisseur de partiel. Le test de mutation a
# tranché : en NEUTRALISANT la priorité, aucun contrôle ne tombait. `Lock` de
# CPython réveille déjà le thread en attente au premier relâchement — le
# mécanisme ne changeait donc rien, et la vraie cause était ailleurs (le partiel
# n'était jamais écrit, cf. `_write_pptx_pdf_partial`).
#
# Un mécanisme dont on ne peut pas prouver qu'il agit ne se garde pas : il ne
# se lit plus comme du code, mais comme une intention.
preview_lock = threading.Lock()


def find_soffice() -> str | None:
    """Chemin de l'exécutable LibreOffice, ou None s'il est introuvable."""
    candidates = [
        os.getenv("SOFFICE_PATH"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "soffice",
        "libreoffice",
    ]
    for c in candidates:
        if not c:
            continue
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


SOFFICE_PATH = find_soffice()


def convert_to_pdf(file_bytes: bytes, ext: str) -> bytes:
    """Convertit un document en PDF. Lève si la conversion échoue.

    Aucun cache ici — voir la docstring du module.
    """
    if not SOFFICE_PATH:
        raise RuntimeError("LibreOffice est requis pour convertir ce format en PDF.")

    # `ignore_cleanup_errors` — LibreOffice garde son profil (`profile/user/…`)
    # ouvert quelques instants APRÈS avoir rendu la main. Sous Windows, effacer
    # un fichier encore ouvert lève `PermissionError` : sans ce drapeau, une
    # conversion RÉUSSIE échouait au nettoyage, et l'erreur remontait comme si
    # la conversion elle-même avait échoué. Ce qui reste est du temporaire, que
    # le système récupère.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src_path = os.path.join(tmp, f"input.{ext}")
        with open(src_path, "wb") as f:
            f.write(file_bytes)
        profile_uri = "file:///" + os.path.join(tmp, "profile").replace(os.sep, "/")
        cmd = [
            SOFFICE_PATH, "--headless", "--norestore", "--nolockcheck",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", "pdf", "--outdir", tmp, src_path,
        ]
        with preview_lock:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
        out_path = os.path.join(tmp, "input.pdf")
        if proc.returncode != 0 or not os.path.exists(out_path):
            err = proc.stderr.decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"Conversion LibreOffice échouée : {err}")
        with open(out_path, "rb") as f:
            return f.read()


def _prewarm() -> None:
    """Le premier appel à LibreOffice prend 3-5 s (démarrage à froid). Un appel
    factice met le processus au chaud pour la première conversion réelle."""
    if not SOFFICE_PATH:
        return
    try:
        # Même verrouillage de profil que dans `convert_to_pdf`. Ici le
        # nettoyage a lieu dans un thread démon, et son échec était signalé au
        # tout dernier moment — d'où le `PermissionError` affiché APRÈS le
        # score vert d'une suite de tests.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            src = os.path.join(td, "warm.docx")
            # Fichier DOCX minimal pour que LibreOffice ait quelque chose à ouvrir
            with open(src, "wb") as f:
                f.write(b"PK\x03\x04" + b"\x00" * 22)  # en-tête ZIP minimal
            profile = "file:///" + os.path.join(td, "prof").replace(os.sep, "/")
            subprocess.run(
                [SOFFICE_PATH, "--headless", "--norestore", "--nolockcheck",
                 f"-env:UserInstallation={profile}",
                 "--convert-to", "pdf", "--outdir", td, src],
                capture_output=True, timeout=30)
    except Exception:
        pass  # échec silencieux : la première conversion sera juste plus lente


def prewarm() -> None:
    """Lance le pré-chauffage dans un thread démon.

    Appelé par le lifespan de l'application, PAS à l'import du module : un effet
    de bord au chargement partirait aussi dans le process parent d'uvicorn
    `--reload`, dans les tests et dans les scripts d'administration, qui n'ont
    aucun aperçu à produire.
    """
    threading.Thread(target=_prewarm, daemon=True).start()
