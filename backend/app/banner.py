"""La bannière affichée au démarrage.

CE QU'ELLE DOIT DIRE, ET RIEN DE PLUS
-------------------------------------
Qui tourne, en quelle version, et **où cliquer**. Un démarrage qui déroule
quarante lignes de journal ne dit rien : on n'y cherche plus l'adresse, on la
retape de mémoire.

L'adresse affichée est celle du FRONTEND — c'est là que va l'utilisateur.
L'API n'est pas une destination : elle est appelée par l'interface.

La ligne « réseau » n'apparaît que si une adresse locale existe vraiment.
Afficher une adresse injoignable est pire que n'en afficher aucune : on essaie,
ça échoue, et on doute de l'installation entière.
"""
from __future__ import annotations

import socket

# Tracé au trait, et non en blocs pleins : lisible sur fond clair comme sur
# fond sombre, et il ne déborde d'aucun terminal étroit. Chaque caractère de
# dessin de boîte occupe UNE colonne, donc le rembourrage du cadre reste juste.
TITRE = r"""
╔═╗╦═╗╔═╗╔═╗╦╔═╗
╠═╝╠╦╝║╣ ║  ║╚═╗   T R A N S L A T O R
╩  ╩╚═╚═╝╚═╝╩╚═╝
"""

LARGEUR = 66
DESCRIPTION = "Traduction de documents à mise en forme préservée"


def adresses_reseau() -> list[str]:
    """Adresses IPv4 locales joignables depuis le réseau, sans le loopback.

    La ruse de l'UDP : ouvrir un socket vers une adresse externe ne fait
    circuler AUCUN paquet (UDP n'établit rien) mais force le système à choisir
    l'interface qu'il utiliserait — donc la bonne, celle par laquelle un
    collègue arrivera. `gethostbyname` rend souvent 127.0.0.1 ou une interface
    virtuelle, et l'adresse affichée ne répondait alors à personne.
    """
    trouvees: list[str] = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(0.2)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            trouvees.append(ip)
    except Exception:
        pass
    finally:
        s.close()
    return trouvees


def _cadre(lignes: list[str]) -> str:
    """Encadre en traits fins. Le rembourrage compte les caractères AFFICHÉS."""
    haut = "┌" + "─" * (LARGEUR - 2) + "┐"
    bas = "└" + "─" * (LARGEUR - 2) + "┘"
    corps = []
    for l in lignes:
        corps.append("│ " + l.ljust(LARGEUR - 4) + " │")
    return "\n".join([haut, *corps, bas])


def construire(port_front: int, port_api: int, versions: dict,
               extras: list[str] | None = None) -> str:
    """La bannière complète, prête à imprimer."""
    v = versions
    moteurs = v.get("moteurs", {})
    ligne_moteurs = " · ".join(f"{k} {val}" for k, val in sorted(moteurs.items()))

    lignes: list[str] = []
    for l in TITRE.strip("\n").split("\n"):
        lignes.append(l)
    lignes.append("")
    lignes.append(DESCRIPTION)
    lignes.append("")
    lignes.append(f"Version    {v.get('projet', '?')}"
                  f"        backend {v.get('backend', '?')}"
                  f"   ·   frontend {v.get('frontend', '?')}")
    if ligne_moteurs:
        lignes.append(f"Moteurs    {ligne_moteurs}")
    lignes.append("")
    lignes.append(f"Local      http://localhost:{port_front}")
    for ip in adresses_reseau():
        lignes.append(f"Réseau     http://{ip}:{port_front}")
    lignes.append(f"API        http://localhost:{port_api}   ·   /docs")
    for e in (extras or []):
        lignes.append(e)
    return _cadre(lignes)
