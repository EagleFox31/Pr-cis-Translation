"""Orchestrateur de développement — démarre backend PUIS frontend, sortie
concise, et un SEUL Ctrl+C arrête TOUT proprement (zéro serveur zombie).

POURQUOI CE SCRIPT REMPLACE `concurrently`
------------------------------------------
Sur Windows, `concurrently` (comme la plupart des lanceurs Node) tue ses enfants
DIRECTS mais pas leurs descendants. Or nos deux serveurs en ont :

  • uvicorn --reload lance un PROCESSUS WORKER enfant qui hérite de la socket :
    c'est lui qui sert le port 8000. Tuer le reloader laissait le worker en vie.
  • vite lance esbuild / des workers node.

Résultat : après un Ctrl+C, des serveurs « zombies » continuaient d'écouter sur
8000 et 3000, et le lancement suivant tombait sur l'ancien code (backend servi
différé, cache trompeur).

Ici on maîtrise les ARBRES de processus : chaque serveur est lancé dans son
propre groupe, et à l'arrêt on tue l'arbre ENTIER (`taskkill /T` sur Windows,
`killpg` sur Unix), puis on balaie les ports par sécurité. Un seul Ctrl+C suffit.

ORDRE : backend d'abord (on attend qu'il écoute), puis frontend. Le frontend
proxifie `/api` vers le backend : le démarrer après garantit qu'il ne sert pas
une première page dont les appels API échouent.
"""
from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_WIN = sys.platform == "win32"

# La console Windows par défaut est en cp1252 : nos préfixes (│, →, ●) la font
# planter à l'écriture. On force l'UTF-8 sur la sortie — Windows Terminal les
# affiche correctement, et `errors="replace"` évite tout crash ailleurs.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# Codes couleur ANSI (Windows 10+ les gère). Préfixes courts et alignés.
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"
_GREY = "\033[90m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _log(prefix: str, color: str, line: str) -> None:
    sys.stdout.write(f"{color}{prefix}{_RESET} {line}\n")
    sys.stdout.flush()


def _port_pids(port: int) -> list[int]:
    """PID(s) à l'écoute sur `port` (Windows via netstat)."""
    pids: set[int] = set()
    if IS_WIN:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True,
                                 text=True, timeout=5, encoding="utf-8",
                                 errors="replace").stdout
            for ln in out.splitlines():
                if f":{port} " in ln and "LISTENING" in ln:
                    parts = ln.split()
                    if parts and parts[-1].isdigit():
                        pids.add(int(parts[-1]))
        except Exception:
            pass
    else:
        try:
            out = subprocess.run(["lsof", "-ti", f"tcp:{port}"],
                                 capture_output=True, text=True, timeout=5).stdout
            for ln in out.split():
                if ln.isdigit():
                    pids.add(int(ln))
        except Exception:
            pass
    return list(pids)


def _kill_tree(pid: int) -> None:
    """Tue le processus `pid` ET tous ses descendants."""
    if IS_WIN:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def _sweep_port(port: int) -> int:
    """Tue tout ce qui écoute sur `port`. Retourne le nombre de PID tués."""
    pids = _port_pids(port)
    for pid in pids:
        _kill_tree(pid)
    return len(pids)


def _wait_listening(port: int, timeout: float) -> bool:
    """Attend qu'un service accepte les connexions sur `port`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


class Server:
    def __init__(self, name, prefix, color, args, cwd, env=None):
        self.name = name
        self.prefix = prefix
        self.color = color
        self.args = args
        self.cwd = cwd
        self.env = env
        self.proc: subprocess.Popen | None = None

    def start(self):
        creationflags = 0
        preexec = None
        if IS_WIN:
            # Nouveau groupe : le Ctrl+C de NOTRE console ne leur est pas
            # propagé sauvagement — on orchestre l'arrêt nous-mêmes.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            preexec = os.setsid  # groupe de processus dédié pour killpg
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["FORCE_COLOR"] = "1"
        if self.env:
            env.update(self.env)
        self.proc = subprocess.Popen(
            self.args, cwd=self.cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=1, text=True, encoding="utf-8", errors="replace",
            creationflags=creationflags, preexec_fn=preexec,
        )
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            if _noise(line):
                continue
            _log(self.prefix, self.color, line)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            _kill_tree(self.proc.pid)


# Lignes de bruit qu'on n'affiche pas (démarrage verbeux des deux serveurs).
# On les reconnaît APRÈS avoir retiré les codes couleur ANSI que vite y injecte.
_NOISE = (
    "Could not find platform independent libraries",
    "VITE v", "Local:", "Network:", "press h", "press h + enter",
    "ready in", "watching for file changes", "Re-optimizing dependencies",
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _noise(line: str) -> bool:
    s = _ANSI_RE.sub("", line).strip()
    if not s:
        return True
    return any(n in s for n in _NOISE)


def main() -> int:
    py = os.path.join(ROOT, "backend", "venv", "Scripts",
                      "python.exe" if IS_WIN else "python")
    if not os.path.exists(py):
        py = sys.executable
    node = "node"
    vite = os.path.join(ROOT, "frontend", "node_modules", "vite", "bin", "vite.js")

    backend = Server(
        "backend", "  api │", _CYAN,
        [py, "-m", "uvicorn", "main:app",
         "--app-dir", "backend",
         "--host", "0.0.0.0", "--port", str(BACKEND_PORT),
         "--reload", "--reload-dir", "backend",
         "--log-level", "warning"],
        cwd=ROOT,
    )
    frontend = Server(
        "frontend", "  web │", _MAGENTA,
        [node, vite, "--port", str(FRONTEND_PORT), "--strictPort"],
        cwd=os.path.join(ROOT, "frontend"),
    )
    servers = [backend, frontend]

    stopping = threading.Event()

    def shutdown(*_a):
        if stopping.is_set():
            return
        stopping.set()
        sys.stdout.write(f"\n{_GREY}  Arrêt…{_RESET}\n")
        sys.stdout.flush()
        for s in reversed(servers):        # frontend d'abord, puis backend
            s.stop()
        # Filet de sécurité : plus AUCUN écouteur ne doit rester sur les ports.
        for port in (FRONTEND_PORT, BACKEND_PORT):
            n = _sweep_port(port)
            if n:
                _log("  sys │", _GREY, f"port {port} libéré ({n} process)")
        _log("  sys │", _GREEN, "tous les services sont arrêtés.")

    # Ctrl+C / Ctrl+Break / fermeture → arrêt propre.
    _handler = lambda *_: (shutdown(), sys.exit(0))
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, "SIGBREAK"):        # Windows : Ctrl+Break
        signal.signal(signal.SIGBREAK, _handler)

    print(f"{_GREY}  Précis — démarrage (Ctrl+C pour tout arrêter){_RESET}")

    # Nettoyage préalable : d'anciens zombies squattent peut-être les ports.
    for port in (BACKEND_PORT, FRONTEND_PORT):
        if _sweep_port(port):
            _log("  sys │", _GREY, f"ancien process sur {port} nettoyé")

    # 1) Backend d'abord, on attend qu'il écoute.
    backend.start()
    if _wait_listening(BACKEND_PORT, timeout=40):
        _log("  api │", _GREEN, f"prêt  →  http://localhost:{BACKEND_PORT}")
    else:
        _log("  api │", _RED, "n'a pas démarré dans le délai imparti.")

    # 2) Frontend ensuite.
    frontend.start()
    if _wait_listening(FRONTEND_PORT, timeout=40):
        _log("  web │", _GREEN, f"prêt  →  http://localhost:{FRONTEND_PORT}")
    else:
        _log("  web │", _RED, "n'a pas démarré dans le délai imparti.")

    print(f"{_GREEN}  ● Application prête  →  http://localhost:{FRONTEND_PORT}{_RESET}")
    print(f"{_GREY}    (le hot-reload est actif — modifiez le code, l'app se met à jour){_RESET}")

    # Surveille : si un serveur meurt tout seul, on arrête l'autre.
    try:
        while not stopping.is_set():
            for s in servers:
                if s.proc and s.proc.poll() is not None:
                    _log("  sys │", _RED,
                         f"{s.name} s'est arrêté (code {s.proc.returncode}) — arrêt global.")
                    shutdown()
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
