"""L'adresse IP du client ne se choisit pas par un en-tête.

Toutes les limites par IP (bêta, connexion, inscription, Google) reposent sur
`request.client.host`. Cette suite verrouille la chaîne Caddy → nginx → uvicorn :
nginx écrase X-Forwarded-For, uvicorn ne le croit que venant du réseau Docker.
"""
import asyncio
import os
import re
import unittest

import racine  # noqa: F401
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NGINX = os.path.join(_RACINE, "frontend", "nginx.conf")
ENTREE = os.path.join(_RACINE, "backend", "docker-entrypoint.sh")


def lire(chemin):
    """Directives seules : les commentaires citent volontairement l'ancienne forme."""
    with open(chemin, encoding="utf-8") as f:
        return "\n".join(l for l in f.read().splitlines() if not l.lstrip().startswith("#"))


def ips_de_confiance():
    m = re.search(r'--forwarded-allow-ips "\$\{FORWARDED_ALLOW_IPS:-([^}]+)\}"', lire(ENTREE))
    assert m, "--forwarded-allow-ips introuvable dans docker-entrypoint.sh"
    return m.group(1)


def ip_vue(pair, xff):
    vu = {}

    async def app(scope, receive, send):
        vu["ip"] = scope["client"][0]

    mw = ProxyHeadersMiddleware(app, trusted_hosts=ips_de_confiance())
    scope = {"type": "http", "client": (pair, 1234), "scheme": "http",
             "headers": [(b"x-forwarded-for", xff.encode())] if xff else []}
    asyncio.run(mw(scope, None, None))
    return vu["ip"]


class ConfigNginx(unittest.TestCase):
    def test_x_forwarded_for_est_ecrase(self):
        conf = lire(NGINX)
        self.assertNotIn("$proxy_add_x_forwarded_for", conf)
        self.assertRegex(conf, r"proxy_set_header X-Forwarded-For\s+\$remote_addr;")

    def test_seul_le_reseau_prive_corrige_l_adresse(self):
        conf = lire(NGINX)
        sources = re.findall(r"set_real_ip_from\s+([^;]+);", conf)
        self.assertTrue(sources)
        self.assertNotIn("0.0.0.0/0", sources)
        self.assertRegex(conf, r"real_ip_header X-Forwarded-For;")


class ConfigUvicorn(unittest.TestCase):
    def test_pas_de_confiance_universelle(self):
        self.assertNotIn("'*'", lire(ENTREE))
        self.assertNotIn("*", ips_de_confiance())

    def test_nginx_relaie_l_adresse_du_client(self):
        self.assertEqual(ip_vue("172.18.0.5", "41.202.219.7"), "41.202.219.7")

    def test_emetteur_externe_ne_choisit_pas_son_adresse(self):
        self.assertEqual(ip_vue("41.202.219.7", "203.0.113.80"), "41.202.219.7")


if __name__ == "__main__":
    unittest.main()
