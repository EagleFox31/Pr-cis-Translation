"""Wrapper autour d'uvicorn qui garantit le nettoyage des processus enfants
(notamment le worker --reload) quand le processus parent est tué (Ctrl+C)."""
import os
import sys
import signal
import subprocess
import atexit

CHILD_PIDS: set[int] = set()


def _kill_children():
    """Tue tous les processus enfants connus, puis force le nettoyage du port.
    Silencieuse : appelée depuis atexit et les handlers de signal, ne doit
    jamais produire de traceback."""
    import time
    try:
        # Passe 1 : arrêt propre (SIGTERM fonctionne sur Windows et Unix)
        for pid in list(CHILD_PIDS):
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        time.sleep(0.4)
        # Passe 2 : force-kill — taskkill /F sur Windows, SIGKILL sur Unix
        for pid in list(CHILD_PIDS):
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                    )
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        CHILD_PIDS.clear()
    except Exception:
        pass


def _cleanup_port(port: int):
    """Tue tout processus à l'écoute sur le port donné (Windows uniquement)."""
    if sys.platform != "win32":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid_str = parts[-1]
                if pid_str.isdigit():
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid_str],
                        capture_output=True,
                    )
    except Exception:
        pass


atexit.register(_kill_children)

# ── Gestion des signaux ───────────────────────────────────────────────────
def _on_signal(signum, frame):
    try:
        _kill_children()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # Nettoyage préalable du port
    _cleanup_port(port)

    # Lancement d'uvicorn en tant que sous-processus.
    # --reload-dir : sans ça le reloader scrute toute la racine du dépôt, donc
    # node_modules/ et backend/venv/ — des milliers de fichiers relus en boucle.
    # --log-level warning : supprime les messages INFO (watched dirs, reloader,
    #   process startup). On affiche notre propre ligne de confirmation plus bas.
    uvicorn_args = [
        sys.executable, "-m", "uvicorn",
        "app:app",
        "--app-dir", "backend",
        "--host", "0.0.0.0",
        "--reload",
        "--reload-dir", "backend",
        "--reload-dir", "pdf_engine_v2",
        "--log-level", "warning",
        "--port", str(port),
    ]

    # Forcer l'encodage UTF-8 pour le sous-processus (corrige les logs
    # accentués rendus en 'd�tect�' sur Windows via concurrently).
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen(
        uvicorn_args,
        # Hériter des flux stdout/stderr du parent — évite les pipes
        # et les erreurs d'encodage cp1252/utf-8 sur Windows.
        stdout=sys.stdout,
        stderr=sys.stderr,
        stdin=subprocess.DEVNULL,
        env=env,
    )
    CHILD_PIDS.add(proc.pid)

    # Ligne de confirmation concise (uvicorn tourne en --log-level warning,
    # donc ses propres messages INFO sont masqués).
    print(f"\n  API  ~  http://0.0.0.0:{port}    (localhost + réseau local)", flush=True)

    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        # Tuer l'arbre de processus uvicorn
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        _kill_children()
        _cleanup_port(port)
