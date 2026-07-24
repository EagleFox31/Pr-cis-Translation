"""Une panne d'aperçu ne doit pas devenir une panne de serveur.

LE DÉFAUT QUE CETTE SUITE VERROUILLE
------------------------------------
Le convertisseur d'aperçu remet en attente un lot qui a échoué. La première
version repartait AUSSITÔT : la file n'était jamais vide, la boucle ne dormait
pas, et elle monopolisait le verrou LibreOffice — affamant toutes les autres
conversions du serveur. Un classeur illisible dans un document devenait une
panne globale.

Deux bornes doivent tenir :
  1. un nombre d'essais par page, après quoi on abandonne l'aperçu de cette
     page (jamais le document : la conversion finale la reprendra) ;
  2. une PAUSE entre deux tentatives, sans quoi la borne 1 est atteinte en
     quelques millisecondes et le mal est déjà fait.

On rejoue ici la boucle du convertisseur, à l'identique mais sans LibreOffice :
c'est sa MÉCANIQUE d'échec qu'on vérifie, pas la conversion.

    backend/venv/Scripts/python.exe backend/tests/test_apercu_resilience.py
"""
from __future__ import annotations

import sys
import threading
import time

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.services.progressive_preview import ProgressivePreview  # noqa: E402

MAX_TENTATIVES = 3
PAUSE = 0.20            # court, pour que la suite reste rapide


def _boucle(greffer, attente: set[int], stop: list[bool],
            cv: threading.Condition, echecs: dict[int, int],
            abandons: list[int]) -> None:
    """La boucle du convertisseur, réduite à sa mécanique d'échec.

    Copie FIDÈLE de `_partial_worker` (translation_runner) : mêmes bornes, même
    ordre. Ce que ce test prouve, c'est que cette forme-là tient.
    """
    while True:
        with cv:
            while not attente and not stop[0]:
                cv.wait()
            if stop[0] and not attente:
                return
            lot = sorted(attente)
            attente.clear()
        try:
            greffer(lot)
        except Exception:
            with cv:
                for n in lot:
                    echecs[n] = echecs.get(n, 0) + 1
                reprendre = [n for n in lot if echecs[n] < MAX_TENTATIVES]
                abandons.extend(n for n in lot if n not in reprendre)
                attente.update(reprendre)
                if stop[0]:
                    return
                if reprendre:
                    cv.wait(timeout=PAUSE)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # ── 1. Une greffe qui échoue TOUJOURS ────────────────────────────────
    appels = []
    cv = threading.Condition()
    attente = {1}
    stop = [False]
    echecs: dict[int, int] = {}
    abandons: list[int] = []

    def greffe_qui_echoue(lot):
        appels.append(time.time())
        raise RuntimeError("classeur illisible")

    th = threading.Thread(target=_boucle,
                          args=(greffe_qui_echoue, attente, stop, cv,
                                echecs, abandons), daemon=True)
    depart = time.time()
    th.start()

    # Le convertisseur ne DOIT PAS se terminer : le job continue, d'autres
    # pages vont arriver. Ce qu'on exige, c'est qu'il cesse de CONSOMMER --
    # qu'il se gare sur son verrou au lieu de tourner. On le mesure en
    # laissant passer largement le temps de plusieurs tentatives, puis en
    # verifiant que plus aucun appel n'a lieu.
    time.sleep(PAUSE * (MAX_TENTATIVES + 3))
    duree = time.time() - depart
    apres_bornes = len(appels)
    time.sleep(PAUSE * 3)

    ok("BORNE  le nombre d'essais est plafonné",
       len(appels) == MAX_TENTATIVES, f"{len(appels)} essais")
    ok("BORNE  passé le plafond, plus AUCUN appel (la boucle se gare)",
       len(appels) == apres_bornes, f"{apres_bornes} -> {len(appels)}")
    ok("BORNE  le thread reste disponible pour les pages suivantes",
       th.is_alive())
    # ... et il s'arrete des qu'on le lui demande.
    with cv:
        stop[0] = True
        cv.notify()
    th.join(timeout=2)
    ok("BORNE  il se termine à la demande d'arrêt", not th.is_alive())
    ok("BORNE  la page est abandonnée pour l'APERÇU, et signalée",
       abandons == [1], str(abandons))

    # LA borne qui manquait : sans pause, les 3 essais partaient en quelques
    # microsecondes et le verrou LibreOffice était pris trois fois d'affilée.
    if len(appels) >= 2:
        ecarts = [b - a for a, b in zip(appels, appels[1:])]
        ok("PAUSE  chaque nouvel essai attend vraiment",
           all(e >= PAUSE * 0.8 for e in ecarts),
           f"écarts = {[f'{e:.3f}s' for e in ecarts]}")
        ok("PAUSE  la boucle ne tourne pas à vide",
           duree >= PAUSE * (MAX_TENTATIVES - 1) * 0.8, f"{duree:.3f}s")

    # ── 2. Un échec PASSAGER se rattrape ─────────────────────────────────
    # La borne ne doit pas condamner une page pour un incident unique.
    n_appels = [0]
    cv2 = threading.Condition()
    attente2 = {7}
    stop2 = [False]
    echecs2: dict[int, int] = {}
    abandons2: list[int] = []
    reussites: list[int] = []

    def greffe_capricieuse(lot):
        n_appels[0] += 1
        if n_appels[0] == 1:
            raise RuntimeError("LibreOffice occupé")
        reussites.extend(lot)
        with cv2:
            stop2[0] = True         # travail fait : on demande l'arrêt
            cv2.notify()

    th2 = threading.Thread(target=_boucle,
                           args=(greffe_capricieuse, attente2, stop2, cv2,
                                 echecs2, abandons2), daemon=True)
    th2.start()
    th2.join(timeout=5)
    ok("REPRISE  un échec passager n'abandonne pas la page",
       reussites == [7] and abandons2 == [], f"{reussites} / {abandons2}")
    ok("REPRISE  le thread se termine proprement", not th2.is_alive())

    # ── 3. L'arrêt du job interrompt l'attente ───────────────────────────
    # Une pause de 5 s en production ne doit pas retarder la fin d'un job.
    cv3 = threading.Condition()
    attente3 = {2}
    stop3 = [False]

    def greffe_lente(lot):
        raise RuntimeError("échec")

    th3 = threading.Thread(target=_boucle,
                           args=(greffe_lente, attente3, stop3, cv3, {}, []),
                           daemon=True)
    th3.start()
    time.sleep(PAUSE / 4)
    t0 = time.time()
    with cv3:
        stop3[0] = True
        cv3.notify()
    th3.join(timeout=3)
    reaction = time.time() - t0
    ok("ARRÊT  la demande d'arrêt interrompt la pause",
       not th3.is_alive() and reaction < PAUSE * 3,
       f"{reaction:.3f}s")

    # ── 4. L'objet d'aperçu refuse de greffer sans socle ─────────────────
    # C'est ce qui déclenche l'échec en cascade quand la conversion initiale a
    # rate : il doit LEVER, pas produire un document muet.
    vide = ProgressivePreview(extraire=lambda c, p: None,
                              convertir=lambda o: b"")
    leve = False
    try:
        vide.greffer([1])
    except Exception:
        leve = True
    ok("SOCLE  greffer sans socle lève au lieu de produire du vide", leve)
    ok("SOCLE  l'objet se déclare non prêt", not vide.pret)

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
