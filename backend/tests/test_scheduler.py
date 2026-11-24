"""Ordonnanceur de traduction — la file de PRIORITE fait bien passer les
prioritaires devant, et departage a egalite par ordre d'arrivee (FIFO).

Principe du test (deterministe, sans DB ni reseau) :
  • un seul worker, occupe par une premiere tache qu'on BLOQUE volontairement ;
  • pendant ce blocage, on met en file B (prio 1), C (prio 5), D (prio 1) ;
  • on libere : le worker doit servir C (le plus prioritaire), puis B avant D
    (meme priorite -> le plus ancien d'abord).
Ordre attendu : A, C, B, D.

Execution :  backend/venv/Scripts/python.exe backend/tests/test_scheduler.py
"""
from __future__ import annotations
import sys
import threading
import time

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.services.scheduler import TranslationScheduler  # noqa: E402

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


def _wait_until(pred, timeout=5.0) -> bool:
    fin = time.time() + timeout
    while time.time() < fin:
        if pred():
            return True
        time.sleep(0.01)
    return False


def main() -> None:
    sched = TranslationScheduler(workers=1)

    order: list[str] = []
    order_lock = threading.Lock()
    started = threading.Event()   # A a saisi le worker
    release = threading.Event()   # autorise A a rendre le worker

    def record(name: str) -> None:
        with order_lock:
            order.append(name)

    def task_A(name: str) -> None:
        record(name)
        started.set()
        release.wait(timeout=5.0)   # bloque l'unique worker

    def task(name: str) -> None:
        record(name)

    # A occupe le worker. Priorite quelconque : il n'a personne devant.
    sched.submit("job-A", 0, task_A, ("A",))
    check(_wait_until(started.is_set), "la 1re tache demarre et saisit le worker")

    # Worker occupe : B, C, D s'empilent dans la file.
    sched.submit("job-B", 1, task, ("B",))
    sched.submit("job-C", 5, task, ("C",))
    sched.submit("job-D", 1, task, ("D",))
    # Rien d'autre n'a pu tourner tant que A tient le worker.
    time.sleep(0.05)
    with order_lock:
        check(order == ["A"], f"aucune tache ne double A pendant qu'il tient le worker (vu {order})")

    # On libere A : la file se vide dans l'ordre de PRIORITE puis FIFO.
    release.set()
    ok_len = _wait_until(lambda: len(order) == 4)
    check(ok_len, "les 4 taches se sont executees")
    check(order == ["A", "C", "B", "D"],
          f"ordre priorite puis FIFO : A, C, B, D (vu {order})")

    # Sanity : a egalite (B avant D), le plus ancien passe d'abord.
    check(order.index("B") < order.index("D"),
          "a priorite egale, le plus ancien (B) passe avant le plus recent (D)")

    attente_sans_les_arretes()

    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} controles")
    if passed != total:
        print("ECHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK - ordonnanceur conforme")


def attente_sans_les_arretes() -> None:
    """« N devant vous » ne compte pas les jobs annulés ou en pause en file."""
    from app.services import scheduler as mod
    jobs = mod.jobs
    sched = TranslationScheduler(workers=1)
    started, release = threading.Event(), threading.Event()
    vus: dict[str, int] = {}
    emit_orig = jobs.emit

    def espion(job_id, event_type, payload):
        if event_type == "queued":
            vus[job_id] = payload["ahead"]
        return emit_orig(job_id, event_type, payload)

    jobs.emit = espion
    try:
        a, b, c, d = (jobs.create() for _ in range(4))
        sched.submit(a, 0, lambda: (started.set(), release.wait(5.0)), ())
        _wait_until(started.is_set)
        sched.submit(b, 0, lambda: None, ())
        sched.submit(c, 0, lambda: None, ())
        check(vus.get(c) == 1, f"un job en file devant : 1 (vu {vus.get(c)})")
        check(jobs.demander_arret(b, "cancelled") == "en_file", "B annulé en file")
        sched.submit(d, 0, lambda: None, ())
        check(vus.get(d) == 1, f"B annulé ne compte plus : 1 devant D (vu {vus.get(d)})")
        release.set()
    finally:
        jobs.emit = emit_orig


if __name__ == "__main__":
    main()
