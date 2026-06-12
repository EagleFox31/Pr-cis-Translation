"""Registre de jobs de traduction en mémoire + progression temps réel.

Chaque job exécute le pipeline de traduction dans un thread et publie des
événements de progression dans une queue, consommée par l'endpoint SSE.
Les pourcentages sont dérivés des messages `progress_callback` existants des
moteurs (« Extraction page 2/5... », « Progression : 1/5 lots traités. »,
« Injection page 3/5... ») — aucun moteur n'est modifié.

Bornes par étape (cf. SRS RF-4.2) :
  upload      0 →   5 %   (acquis avant la création du job)
  extraction  5 →  20 %
  traduction 20 →  85 %
  génération 85 →  98 %
  terminé         100 %
"""
import re
import json
import queue
import threading
import time
import uuid

_JOBS = {}
_JOBS_LOCK = threading.Lock()
_JOB_TTL = 30 * 60          # purge des jobs terminés après 30 min

_STAGES = {
    "extraction":  (5.0, 20.0),
    "translation": (20.0, 85.0),
    "injection":   (85.0, 98.0),
}

_RX_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")


class TranslationJob:
    def __init__(self):
        self.id = uuid.uuid4().hex[:16]
        self.events = queue.Queue()
        self.done = threading.Event()
        self.error = None            # message d'erreur si échec
        self.status_code = 500       # code HTTP en cas d'échec
        self.result_path = None
        self.result_filename = None
        self.created = time.time()
        self._stage = "extraction"
        self._percent = 5.0

    # ── publication d'événements ───────────────────────────────────────────
    def set_stage(self, stage, message=""):
        self._stage = stage
        lo, _hi = _STAGES.get(stage, (self._percent, self._percent))
        self._percent = max(self._percent, lo)
        self.emit(message or stage)

    def progress_callback(self, message):
        """Branché sur les progress_callback des moteurs : déduit l'étape et
        le pourcentage du message texte."""
        msg = str(message)
        low = msg.lower()
        if "extraction page" in low:
            self._stage = "extraction"
        elif "injection page" in low:
            self._stage = "injection"
        elif "lot" in low or "traduction" in low or "progression" in low:
            # messages du traducteur IA (lots, tentatives, scissions)
            if self._stage == "extraction":
                self._stage = "translation"
        lo, hi = _STAGES.get(self._stage, (self._percent, self._percent))
        m = _RX_RATIO.search(msg)
        if m and int(m.group(2)) > 0:
            cur, tot = int(m.group(1)), int(m.group(2))
            pct = lo + (hi - lo) * min(1.0, cur / tot)
            self._percent = max(self._percent, pct)
        self.emit(msg)

    def emit(self, message):
        self.events.put({
            "stage": self._stage,
            "percent": round(min(self._percent, 98.0), 1),
            "message": str(message)[:300],
        })

    def finish(self, result_path, result_filename):
        self.result_path = result_path
        self.result_filename = result_filename
        self._percent = 100.0
        self.events.put({"stage": "done", "percent": 100.0,
                         "message": "Traduction terminée."})
        self.done.set()

    def fail(self, message, status_code=500):
        self.error = str(message)
        self.status_code = status_code
        self.events.put({"stage": "error", "percent": round(self._percent, 1),
                         "message": self.error[:300]})
        self.done.set()

    # ── flux SSE ───────────────────────────────────────────────────────────
    def sse_stream(self):
        """Générateur d'événements SSE. Se termine sur 'done' ou 'error'."""
        last_beat = time.time()
        while True:
            try:
                ev = self.events.get(timeout=2.0)
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev["stage"] in ("done", "error"):
                    return
            except queue.Empty:
                if self.done.is_set() and self.events.empty():
                    return
                if time.time() - last_beat > 10:
                    last_beat = time.time()
                    yield ": keep-alive\n\n"


def create_job():
    job = TranslationJob()
    with _JOBS_LOCK:
        # purge des jobs expirés
        now = time.time()
        for jid in [j for j, jb in _JOBS.items()
                    if jb.done.is_set() and now - jb.created > _JOB_TTL]:
            del _JOBS[jid]
        _JOBS[job.id] = job
    return job


def get_job(job_id):
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def run_in_thread(job, target, *args, **kwargs):
    """Exécute `target(*args, progress=job, **kwargs)` dans un thread démon."""
    def _worker():
        try:
            target(*args, job=job, **kwargs)
        except Exception as e:
            if not job.done.is_set():
                job.fail(str(e))
    threading.Thread(target=_worker, daemon=True).start()
