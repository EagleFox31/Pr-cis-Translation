"""Ordonnanceur des traductions — file de PRIORITÉ bornée.

LE PROBLÈME QU'IL RÉSOUT
------------------------
Chaque `/api/translate` lançait AUSSITÔT son propre thread, sans aucune borne :
tout tournait en parallèle, à la merci de la machine. Rien ne distinguait un
compte payant d'un compte gratuit — la « vitesse » vendue sur la carte de tarifs
n'existait nulle part dans le code.

CE QU'IL FAIT
-------------
Un nombre FIXE de workers (`TRANSLATION_WORKERS`) mène les traductions de front.
Au-delà, les demandes attendent dans une `PriorityQueue` : le worker suivant
sert TOUJOURS la plus prioritaire (priorité du plan : admin > pro > starter >
gratuit), et à priorité égale la plus ancienne (FIFO). Payer, c'est passer
devant ceux qui attendent.

CE QU'IL NE FAIT PAS
--------------------
Pas de PRÉEMPTION : un job prioritaire ne coupe pas un job déjà en cours, il
passe seulement devant ceux qui n'ont pas encore démarré. Interrompre un rendu
à mi-course gâcherait le travail fait sans rien garantir de mieux. « Prioritaire »
veut donc dire « en tête de file », pas « instantané » — l'interface ne doit
promettre que ça.
"""
from __future__ import annotations

import itertools
import math
import queue
import statistics
import time
from collections import deque
import threading
from typing import Any, Callable

from app.config import (FILE_ATTENTE_DUREE_DEFAUT_S, FILE_ATTENTE_MAX,
                        FILE_ATTENTE_MAX_PAR_COMPTE, FILE_ATTENTE_SEUIL_MIN,
                        MEMOIRE_SOCLE_MO, MEMOIRE_TRAVAIL_MO, OCR_SCAN_WORKERS,
                        TRANSLATION_WORKERS, logger)
from app.services import memoire, ocr_file
from app.services.jobs import ArretDemande, jobs

# Places communes aux deux files (traductions et scans), fixées au démarrage.
budget = memoire.Budget(memoire.places_pour(
    memoire.limite(), MEMOIRE_SOCLE_MO,
    memoire.DETECTION_MO + memoire.LIBREOFFICE_MO, MEMOIRE_TRAVAIL_MO))
if budget.places:
    logger.info("Mémoire : %d travaux simultanés au plus", budget.places)

# ── File d'attente affichée ──────────────────────────────────────────────────
# Une seule vérité pour « N devant vous » : d'abord les travaux qui attendent
# une place mémoire (ordre d'arrivée), puis ceux qui attendent un worker, dans
# l'ordre où les files les serviront. Tout se calcule et s'émet sous
# `budget.verrou` : un travail ne démarre qu'après avoir franchi ce verrou, donc
# aucun « en file » ne peut lui parvenir après son démarrage.
_arrivee = itertools.count()          # ordre d'arrivée commun aux deux files
_durees: deque[float] = deque(maxlen=10)
_dernier_signal: dict[str, tuple[int, int]] = {}
_files: list["TranslationScheduler"] = []


def _actif(job_id: object) -> bool:
    """Travail qui sera vraiment traité (ni en pause ni annulé)."""
    if not isinstance(job_id, str):
        return False
    job = jobs.get(job_id)
    return job is not None and not job.get("arret")


def _ordre_d_attente() -> list[str]:
    en_file: list[tuple[int, int, str]] = []
    for f in _files:
        # Une file dont un worker est libre sera servie aussitôt : ses travaux
        # ne sont pas « en attente » (pas de bandeau qui clignote).
        if f._running < f._workers:
            continue
        with f._pq.mutex:
            en_file += [(e[0], e[1], e[2]) for e in f._pq.queue]
    en_file.sort()
    return ([j for j in budget.attente if _actif(j)]
            + [e[2] for e in en_file if _actif(e[2])])


def duree_type() -> float:
    """Médiane des derniers travaux terminés : un travail géant ne la fausse pas."""
    return statistics.median(_durees) if _durees else float(FILE_ATTENTE_DUREE_DEFAUT_S)


def estimer_attente(ahead: int) -> int:
    """Secondes avant le démarrage, légèrement surestimées : chaque travail en
    cours est compté comme s'il venait de commencer."""
    places = budget.places or TRANSLATION_WORKERS
    en_cours = min(budget.occupees, places)
    tours = max(1, math.ceil((ahead + en_cours) / places))
    return int(tours * duree_type())


def refus_admission(user_id: int) -> int | None:
    """Secondes à attendre avant de réessayer si la file est trop pleine pour
    accepter ce compte, sinon None.

    Compte les travaux EN ATTENTE (pas encore démarrés, ni en pause ni annulés)
    de toutes les files, y compris ceux qui attendent une place mémoire. Deux
    plafonds : le total, et le nombre de travaux en attente du compte. Un
    plafond à None est ignoré. Le contrôle est SOUPLE : il ne tient aucun verrou
    jusqu'à la mise en file, donc deux demandes simultanées peuvent le franchir
    ensemble."""
    en_attente: list[str] = []
    for f in _files:
        with f._pq.mutex:
            en_attente += [e[2] for e in f._pq.queue]
    with budget.verrou:
        en_attente += list(budget.attente)
    attendants = []
    for job_id in en_attente:
        if not _actif(job_id):
            continue
        job = jobs.get(job_id) or {}
        if not job.get("demarre"):
            attendants.append(job)
    total = len(attendants)
    du_compte = sum(1 for job in attendants if job.get("user_id") == user_id)
    trop_plein = ((FILE_ATTENTE_MAX is not None and total >= FILE_ATTENTE_MAX)
                  or (FILE_ATTENTE_MAX_PAR_COMPTE is not None
                      and du_compte >= FILE_ATTENTE_MAX_PAR_COMPTE))
    if not trop_plein:
        return None
    return max(30, min(600, estimer_attente(total)))


def etat_file(job_id: str | None) -> dict | None:
    """Dernière position annoncée à ce travail, s'il attend encore : l'écran
    rouvert depuis la bibliothèque n'a pas le flux qui l'a reçue."""
    etat = _dernier_signal.get(job_id) if job_id else None
    if etat is None:
        return None
    seuil_s = FILE_ATTENTE_SEUIL_MIN * 60 if FILE_ATTENTE_SEUIL_MIN else None
    return {"ahead": etat[0], "attente_s": etat[1], "seuil_s": seuil_s}


def signaler_file() -> None:
    """Renvoie à chaque travail en attente sa position et son attente, s'ils ont
    changé. À appeler sous `budget.verrou`."""
    ordre = _ordre_d_attente()
    seuil_s = FILE_ATTENTE_SEUIL_MIN * 60 if FILE_ATTENTE_SEUIL_MIN else None
    for ahead, job_id in enumerate(ordre):
        etat = (ahead, estimer_attente(ahead))
        if _dernier_signal.get(job_id) != etat:
            _dernier_signal[job_id] = etat
            jobs.emit(job_id, "queued",
                      {"ahead": ahead, "attente_s": etat[1], "seuil_s": seuil_s})
    for job_id in set(_dernier_signal) - set(ordre):
        del _dernier_signal[job_id]



class TranslationScheduler:
    """Pool de workers + file de priorité. Un seul exemplaire par processus."""

    def __init__(self, workers: int) -> None:
        self._workers = max(1, workers)
        self._pq: queue.PriorityQueue = queue.PriorityQueue()
        # Le compteur `_arrivee` départage deux jobs de MÊME priorité par ordre
        # d'arrivée (FIFO), et — tout aussi important — garantit que la file ne
        # compare JAMAIS les charges utiles entre elles (fonctions, tuples
        # d'arguments non ordonnables). La clé (-prio, seq) est toujours unique.
        self._lock = threading.Lock()
        self._running = 0                      # jobs occupant un worker
        self._threads: list[threading.Thread] = []
        _files.append(self)
        for i in range(self._workers):
            t = threading.Thread(target=self._worker, name=f"xl-worker-{i}",
                                 daemon=True)
            t.start()
            self._threads.append(t)

    # ── Soumission ───────────────────────────────────────────────────────────
    def submit(self, job_id: str, priority: int,
               target: Callable[..., Any], args: tuple) -> None:
        """Met un job en file. `priority` = niveau du plan (plus grand = plus
        prioritaire). Émet un événement `queued` SI aucun worker n'est libre —
        c'est ce qui permet à l'interface d'afficher « en file d'attente »."""
        seq = next(_arrivee)
        # -priority : PriorityQueue sert le plus PETIT en premier, or on veut le
        # plus prioritaire d'abord. Sous `budget.verrou` : le calcul de la file
        # affichée voit ce job dès qu'il y est.
        with budget.verrou:
            self._pq.put((-priority, seq, job_id, target, args))
            if self._running >= self._workers:
                signaler_file()
                logger.info("Job %s en file (priorité %s)", job_id, priority)

    # ── Boucle worker ────────────────────────────────────────────────────────
    def _worker(self) -> None:
        while True:
            _negprio, _seq, job_id, target, args = self._pq.get()
            with self._lock:
                self._running += 1
            a_une_place = False
            try:
                # Budget mémoire commun : au-delà des places, le conteneur
                # serait tué avec TOUS les travaux en cours. Sans place, le
                # travail attend ici, affiché « en file ».
                def en_attente(jid=job_id) -> None:
                    signaler_file()
                    logger.info("Mémoire : travail %s attend une place (%s places)",
                                jid, budget.places)

                budget.prendre(job_id, sur_attente=en_attente)
                a_une_place = True
                with budget.verrou:
                    signaler_file()     # les suivants avancent d'un rang
                # Un job mis en pause ou annulé pendant qu'il attendait ne
                # démarre pas : la route l'a déjà arrêté et consigné.
                if jobs.demarrer(job_id):
                    # Les lectures OCR de ce job se rangent à sa priorité.
                    ocr_file.definir_priorite(-_negprio)
                    debut = time.monotonic()
                    target(*args)
                    _durees.append(time.monotonic() - debut)
            except ArretDemande as arret:
                logger.info("Job %s arrêté à la demande (%s)", job_id, arret.mode)
                try:
                    jobs.arreter(job_id, arret.mode)
                except Exception as e:
                    logger.error("Arrêt du job %s non consigné : %s", job_id, e)
            except Exception as e:
                # Le job lui-même signale déjà ses propres erreurs (`jobs.error`).
                # Ce filet n'existe que pour qu'une exception inattendue ne TUE
                # pas le worker — sans quoi on perdrait une place de traitement à
                # chaque plantage, jusqu'à figer toute la file.
                logger.error("Worker : job %s a levé %s", job_id, e)
                try:
                    jobs.error(job_id, "Erreur interne pendant la traduction.")
                except Exception:
                    pass
            finally:
                memoire.rendre_au_systeme()
                if a_une_place:
                    budget.rendre()
                with self._lock:
                    self._running -= 1
                with budget.verrou:
                    signaler_file()     # nouvelle médiane, place rendue
                self._pq.task_done()
                # Une traduction vient de dépenser : relire le solde DeepSeek.
                from app.services.solde_ia import verifier_depuis_un_thread
                verifier_depuis_un_thread()


# Point d'accès unique du processus.
scheduler = TranslationScheduler(TRANSLATION_WORKERS)

# Documents scannés : file à part. Leurs workers passent l'essentiel du temps à
# attendre le guichet OCR (une lecture à la fois) ; sur la file commune ils
# bloqueraient les traductions de documents à texte.
scheduler_scans = TranslationScheduler(OCR_SCAN_WORKERS)
