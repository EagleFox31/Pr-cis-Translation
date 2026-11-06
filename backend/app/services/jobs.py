"""Gestionnaire des travaux de traduction.

UN JOB, C'EST QUOI
------------------
Une traduction lancée par une requête, exécutée dans un THREAD worker, et
suivie par le client via SSE. Il porte :
  - une file thread-safe pour les messages de progression ;
  - un état (pending / running / done / error, ou paused / cancelled quand
    l'utilisateur l'arrête) ;
  - le chemin du rendu une fois terminé ;
  - le propriétaire, sans lequel un `job_id` deviné suffirait à récupérer le
    document d'autrui.

POURQUOI UNE CLASSE
-------------------
Ces données vivaient dans deux variables de module (`_jobs`, `_jobs_lock`) que
huit fonctions manipulaient. Rien n'empêchait un accès sans verrou, et rien ne
disait où était la frontière. Ici l'état est privé et le verrou est pris par
les méthodes : on ne peut plus lire la table sans passer par elles.

L'instance `jobs` en fin de module est le point d'accès unique du processus.
"""
from __future__ import annotations

import asyncio
import os
import queue
import re
import threading
import time
import uuid
from typing import Any, Callable

from app.config import (
    JOB_MAX_AGE_SECONDS,
    JOB_RETENTION_SECONDS,
    PROGRESS_EVERY_S,
    logger,
)


def _dans_une_boucle_jetable(faire: Callable[[Any], Any]) -> None:
    """Exécute une coroutine de base de données depuis un THREAD worker.

    Moteur DÉDIÉ à connexion NON poolée : on tourne dans une boucle jetable, or
    le pool du moteur global est lié à la boucle principale d'uvicorn — y
    réutiliser une connexion lèverait « Event loop is closed ». NullPool ouvre
    une connexion neuve sur CETTE boucle et la ferme avec le moteur.

    `faire` reçoit une session ouverte et fait son travail ; le commit et la
    fermeture sont pris en charge ici.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.database import DATABASE_URL

    async def _run():
        eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(eng) as db:
                await faire(db)
                await db.commit()
        finally:
            await eng.dispose()

    asyncio.run(_run())


# Statuts d'un Document arrêté avant la fin dont le travail fait est GARDÉ :
# pages traduites débitées, reste rendu, reprise possible sur le cache.
# Statuts d'un arrêt DEMANDÉ par le client (pause / annulation) : états
# finaux du job, comme `done` et `error`.
STATUTS_ARRET = ("paused", "cancelled")
STATUTS_REPRENABLES = ("interrupted", *STATUTS_ARRET)


class ArretDemande(BaseException):
    """Levée à un point de contrôle quand le client a demandé pause ou annulation.

    `BaseException` et non `Exception` : les jobs attrapent `Exception` pour
    passer en ERREUR (remboursement complet) ; un arrêt demandé doit traverser
    ces filets jusqu'à l'ordonnanceur, qui le consigne (`jobs.arreter`)."""

    def __init__(self, mode: str):
        super().__init__(mode)
        self.mode = mode


class JobManager:
    """Table des travaux en cours, et leur report en base."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── Cycle de vie ─────────────────────────────────────────────────────
    def create(self) -> str:
        """Ouvre un job et retourne son identifiant."""
        self.collect()
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "state": "pending",
                "created_at": time.time(),
                "q": queue.Queue(),
                "result_path": None,
                "result_filename": None,
                "partial_path": None,   # PDF v2 : fichier partiel (pages prêtes)
                "error": None,
                # PROPRIÉTAIRE du job. Sans lui, un job_id deviné suffisait à
                # récupérer le document d'autrui : /partial et /result ne
                # vérifiaient que la clé d'API, laquelle est publique (elle est
                # dans le bundle du frontend).
                "user_id": None,
            }
        return job_id

    def collect(self) -> None:
        """Oublie les jobs finis depuis > 30 min et efface leurs fichiers
        TRANSITOIRES (PDF partiel + rendu). La traduction persistante
        (pages.json) n'est jamais touchée ici : elle vit dans le magasin,
        protégée par la purge par références."""
        now = time.time()
        with self._lock:
            morts = [
                (jid, j) for jid, j in self._jobs.items()
                if (j.get("finished_at")
                    and now - j["finished_at"] > JOB_RETENTION_SECONDS)
                or (now - j.get("created_at", now) > JOB_MAX_AGE_SECONDS)
            ]
            for jid, _ in morts:
                del self._jobs[jid]
        for _, j in morts:
            for f in (j.get("partial_path"), j.get("result_path")):
                if f and os.path.isfile(f):
                    try:
                        os.remove(f)
                    except OSError:
                        pass

    # ── Accès ────────────────────────────────────────────────────────────
    def get(self, job_id: str) -> dict | None:
        """Le job, ou None. Lecture sous verrou."""
        with self._lock:
            return self._jobs.get(job_id)

    def for_document(self, doc_id: str) -> dict | None:
        """Le job VIVANT qui produit ce Document, ou None.

        Le Document ne connaît pas son job (rien en base) : c'est le job qui
        porte `document_id`. Sert à l'aperçu d'un document rouvert depuis la
        bibliothèque pendant sa traduction — sans lui, on n'avait que l'original.
        """
        with self._lock:
            for job in self._jobs.values():
                if job.get("document_id") == doc_id:
                    return job
        return None

    def id_for_document(self, doc_id: str) -> str | None:
        """L'identifiant du job vivant de ce Document : la bibliothèque s'en
        sert pour mettre en pause ou annuler une traduction qu'elle n'a pas
        lancée (autre onglet, après rechargement)."""
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.get("document_id") == doc_id:
                    return job_id
        return None

    def set(self, job_id: str, **champs) -> None:
        """Pose des champs sur un job existant. Écriture sous verrou."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(champs)

    def forget(self, job_id: str) -> None:
        """Oublie un job sans attendre le ménage.

        Le ménage automatique ne prend que les jobs FINIS depuis assez
        longtemps ; celui-ci retire un job à la demande — un abandon, ou un
        contexte de test qui range derrière lui. Ne touche à aucun fichier :
        seul `collect()` en efface, et seulement ceux qu'il a laissés mûrir.
        """
        with self._lock:
            self._jobs.pop(job_id, None)

    # ── Progression ──────────────────────────────────────────────────────
    def emit(self, job_id: str, event_type: str, payload: dict) -> None:
        """Publie un événement vers le flux SSE du job."""
        job = self.get(job_id)
        if job:
            if event_type == "page" and payload.get("page") and payload.get("status"):
                # Dernier état de chaque page, GARDÉ : le flux SSE ne vit que
                # pour l'onglet qui a lancé la traduction. Un aperçu rouvert
                # depuis la bibliothèque le relit pour savoir où en est chaque page.
                with self._lock:
                    job.setdefault("page_states", {})[int(payload["page"])] = payload["status"]
            job["q"].put({"type": event_type, **payload})

    def pages_etat(self, job: dict) -> tuple[list[int], dict[int, str]]:
        """(pages réellement traduites dans le partiel, état de chaque page).

        PPTX : la liste du greffage (`partial_pages`) fait foi, plus les
        diapositives sans texte (`copied`), identiques à l'original. Ailleurs,
        une page `done` est dans le partiel."""
        with self._lock:
            etats = dict(job.get("page_states") or {})
            greffees = job.get("partial_pages")
        if greffees is not None:
            pretes = set(greffees) | {p for p, s in etats.items() if s == "copied"}
        else:
            pretes = {p for p, s in etats.items() if s in ("done", "copied")}
        return sorted(pretes), etats

    def progress_callback(self, job_id: str, step: str,
                          total: int | None = None) -> Callable[[str], None]:
        """Retourne un progress_callback lié à un job et à une étape."""
        counter = [0]

        def cb(msg: str) -> None:
            # Détecter le pattern "page X/N" pour afficher la progression fine
            page, tot = None, total
            m = re.search(r'(\d+)/(\d+)', msg)
            if m:
                page, tot = int(m.group(1)), int(m.group(2))
                counter[0] = page
            self.emit(job_id, "progress", {
                "step": step,
                "message": msg,
                "page": page or counter[0],
                "total": tot,
            })
            logger.info(msg)

        return cb

    # ── Fin de vie ───────────────────────────────────────────────────────
    def done(self, job_id: str, result_path: str, filename: str,
             translation_path: str | None = None) -> None:
        """`result_path` = le rendu (transitoire) que /result sert tout de
        suite. `translation_path` = la traduction PERSISTANTE
        (pages.json/translated.json) consignée en base : c'est elle qui permet
        de recalculer le rendu plus tard, pas le fichier transitoire. Faute de
        quoi `Document.translated_path` pointerait sur un rendu que le ménage
        efface au bout de 30 min."""
        job = self.get(job_id)
        if job:
            job["result_path"] = result_path
            job["result_filename"] = filename
            job["state"] = "done"
            job["finished_at"] = time.time()
            job["q"].put({"type": "done", "filename": filename})
        self.sync_status(job_id, "done",
                         translated_path=translation_path or result_path)

    def error(self, job_id: str, message: str) -> None:
        job = self.get(job_id)
        if job:
            job["error"] = message
            job["state"] = "error"
            job["finished_at"] = time.time()
            job["q"].put({"type": "error", "message": message})
        self.sync_status(job_id, "error")

    # ── Arrêt demandé (pause / annulation) ───────────────────────────────
    def demander_arret(self, job_id: str, mode: str) -> str | None:
        """Pose le drapeau d'arrêt (`paused` ou `cancelled`).

        Renvoie `"en_cours"` si un worker traite déjà le job : il s'arrête au
        prochain contrôle (PDF/PPTX : la page en vol est abandonnée, sans
        attendre le modèle ; DOCX/XLSX : le lot en cours finit) ;
        `"en_file"` s'il attend encore : l'appelant l'arrête tout de suite
        (`arreter`), le worker ne le démarrera pas (`demarrer`). None si le
        job est inconnu, déjà fini ou déjà arrêté. Les deux décisions se
        prennent sous le même verrou : un job ne peut être à la fois démarré
        et arrêté en file."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.get("finished_at") or job.get("arret"):
                return None
            job["arret"] = mode
            return "en_cours" if job.get("demarre") else "en_file"

    def demarrer(self, job_id: str) -> bool:
        """Le worker prend le job : True s'il doit le traiter, False si une
        pause ou une annulation l'a devancé pendant qu'il attendait en file
        (la route l'a déjà consigné)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None and job.get("arret"):
                return False
            if job is not None:
                job["demarre"] = True
            return True

    def arret_demande(self, job_id: str) -> str | None:
        job = self.get(job_id)
        return job.get("arret") if job else None

    def verifier_arret(self, job_id: str) -> None:
        """Point de contrôle : lève `ArretDemande` si un arrêt est demandé."""
        mode = self.arret_demande(job_id)
        if mode:
            raise ArretDemande(mode)

    def arreter(self, job_id: str, mode: str) -> None:
        """Fin d'un job arrêté à la demande : pages faites débitées, reste rendu."""
        # Base d'abord : sur « stopped », le client recharge sa bibliothèque
        # et doit y lire le statut final, pas « translating ».
        self.sync_status(job_id, mode)
        job = self.get(job_id)
        if job:
            job["state"] = mode
            job["finished_at"] = time.time()
            job["q"].put({"type": "stopped", "mode": mode})

    # ── Report en base ───────────────────────────────────────────────────
    def _document_id(self, job_id: str) -> str | None:
        job = self.get(job_id)
        return job.get("document_id") if job else None

    def sync_progress(self, job_id: str, done: int,
                      total: int | None = None) -> None:
        """Consigne l'avancement en base, pour qu'il survive à la session.

        ÉCRITURE LIMITÉE. Un document de 285 pages ferait 285 transactions,
        chacune ouvrant sa propre connexion (voir `_dans_une_boucle_jetable`).
        On n'écrit donc que toutes les `PROGRESS_EVERY_S` secondes — sauf la
        DERNIÈRE page, qu'on écrit toujours : c'est celle qui fait passer la
        barre à 100 %, et la sauter laisserait un document terminé affiché à
        97 %.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            doc_id = job.get("document_id") if job else None
            if not doc_id:
                return
            derniere = total is not None and done >= total
            if not derniere:
                precedent = job.get("_progress_at", 0.0)
                if time.time() - precedent < PROGRESS_EVERY_S:
                    return
            job["_progress_at"] = time.time()

        async def _maj(db):
            from app.models import Document
            doc = await db.get(Document, doc_id)
            if doc is None:
                return
            doc.pages_done = done
            if total and not doc.page_count:
                doc.page_count = total

        try:
            _dans_une_boucle_jetable(_maj)
        except Exception as e:
            # L'avancement est un CONFORT : son échec ne doit jamais
            # interrompre une traduction en cours, qui elle a de la valeur.
            # Mais il doit se VOIR — un `except: pass` muet a déjà coûté une
            # heure de recherche ici même : la barre restait à zéro sans que
            # rien ne le signale. `asyncio.run` échoue notamment si on
            # l'appelle depuis une boucle déjà en cours ; ce chemin n'est
            # légitime que depuis un thread worker.
            logger.warning("Avancement non consigné (doc %s, %s pages) : %s",
                           doc_id, done, e)

    def sync_status(self, job_id: str, status: str,
                    translated_path: str | None = None) -> None:
        """Reporte l'état d'un job sur le Document en base (si l'utilisateur
        était connecté). Sans ce report, le Document restait éternellement
        `translating` et `translated_path` NULL : le téléchargement servait
        alors l'ORIGINAL au lieu de la traduction."""
        doc_id = self._document_id(job_id)
        if not doc_id:
            return

        async def _maj(db):
            from app.models import Document
            doc = await db.get(Document, doc_id, with_for_update=True)
            # Disparu ou déjà REPRIS par un autre job (worker d'un processus
            # précédent qui finit tard) : sa facturation appartient désormais
            # à la reprise ; rembourser ou refacturer ici compterait deux fois.
            if doc is None or doc.status == "resumed":
                return
            from app.services.documents import pages_faites_du_document, reglages_de
            deja = int(reglages_de(doc).get("deja") or 0)
            if status in STATUTS_ARRET or (status == "error" and deja > 0):
                # Pause, annulation, ou échec d'une REPRISE (« Interrompue » et
                # non « Échec », sinon les pages payées par le document repris
                # seraient perdues — il est `resumed` — et repayées à la
                # relance). Même règle qu'à l'arrêt du serveur : pages
                # traduites débitées, le reste rendu.
                from app.services.usage import refund_unfinished
                doc.status = "interrupted" if status == "error" else status
                # L'avancement n'est consigné que toutes les quelques secondes
                # (`sync_progress`) : on le recale sur le disque, qui fait foi
                # pour la facture, sinon la carte affiche une page de moins
                # que ce qui a été débité.
                faites = pages_faites_du_document(doc)
                doc.pages_done = faites
                await refund_unfinished(db, doc_id, max(0, faites - deja))
                return
            doc.status = status
            if translated_path:
                doc.translated_path = translated_path
            if status == "error":
                # On ne facture pas ce qu'on n'a pas livré : l'offre du mois
                # redevient libre, les pages achetées reviennent au solde.
                from app.services.usage import refund_for_document
                await refund_for_document(db, doc_id)
            elif status == "done":
                # Livré : si un redémarrage concurrent l'avait remboursé
                # (`reconcilier_jobs_orphelins`), la consommation revient.
                from app.services.usage import rebill_for_document
                await rebill_for_document(db, doc_id)

        try:
            _dans_une_boucle_jetable(_maj)
        except Exception as e:
            # Silence INTERDIT : sans ce report le Document reste
            # `translating` et le téléchargement sert l'original. Pas de
            # relance (on ne fait pas échouer un job terminé), mais la cause
            # doit se voir dans le journal.
            logger.warning("État non reporté sur le document (job %s → %s) : %s",
                           job_id, status, e)


# Point d'accès unique du processus.
jobs = JobManager()
