"""Tirage du banc public : 50 images de documents prises au hasard dans des jeux publics.

Voir docs/etude-banc-public.md. Graine fixe : relancer redonne les mêmes images.
Les images sont des données de tiers non fiables : elles vont dans un dossier hors
du dépôt, ce script vit ailleurs, et il se lance avec `python -I`.

    python -I backend/tests/banc_public_tirage.py [DOSSIER_PYARROW]
        télécharge, applique la règle d'admission (l'OCR lit au moins 2 textes avec
        une lettre), puis construit les cas dans backend/translations/_banc_public/.
"""
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # `-I` retire ce dossier
import racine  # noqa: E402,F401
if len(sys.argv) > 1:  # pyarrow installé à part (secours parquet), `-I` ignore PYTHONPATH
    sys.path.append(sys.argv[1])

from app.services import cache_images  # noqa: E402
from app.services.ocr_v2 import image as img  # noqa: E402

GRAINE = 20261110
MIN_TEXTES = 2
MAX_OCTETS = 10 * 1024 * 1024
ESSAIS_MAX = 60  # tirages au plus par source avant d'abandonner
BANC = os.path.join(os.path.dirname(cache_images.DOSSIER), "_banc_public")
AGENT = "precis-banc-public/1.0 (test interne)"
HF = "https://datasets-server.huggingface.co/rows"

# (nom, jeu HF ou None pour Wikimedia, config, split, taille du split, nombre, licence)
# Images de documents seulement (schémas, scans, graphiques, organigrammes), jamais de
# photos de rue : la cible du produit est le document traduit.
SOURCES = [
    ("ai2d", "lmms-lab-encoder/ai2d", "default", "test", 3088, 15, "AI2D, Apache 2.0"),
    ("funsd", "nielsr/funsd", "default", "test", 50, 7, "FUNSD, usage de recherche"),
    ("docvqa", "lmms-lab-encoder/DocVQA", "DocVQA", "validation", 5349, 8, "DocVQA (UCSF IDL), usage de recherche"),
    ("chartqa", "HuggingFaceM4/ChartQA", "default", "test", 2500, 10, "ChartQA, GPL-3.0"),
    ("organigrammes", None, None, "Category:Organizational charts", None, 5, "Wikimedia Commons, par fichier"),
    ("procedes", None, None, "Category:Process flow diagrams", None, 5, "Wikimedia Commons, par fichier"),
    # Ajout du 10/11/2026 (docs/etude-robustesse-ocr.md) : usages courants absents du banc.
    # Ajoutées à la fin : la graine de chaque source dépend de son rang, les 50 premiers
    # cas restent identiques.
    ("tickets", "naver-clova-ix/cord-v2", "default", "test", 100, 5, "CORD v2, CC-BY-4.0"),
    ("factures", "katanaml-org/invoices-donut-data-v1", "default", "test", 26, 5, "invoices-donut-data-v1, licence du jeu"),
    ("tableaux", "apoidea/pubtabnet-html", "default", "validation", 9115, 5, "PubTabNet, CDLA-Permissive"),
    ("infographies", "lmms-lab-encoder/DocVQA", "InfographicVQA", "validation", 2801, 5, "InfographicVQA, usage de recherche"),
    ("dessins", None, None, "Category:Technical drawings", None, 5, "Wikimedia Commons, par fichier"),
    ("diapositives", None, None, "Category:Presentation slides", None, 5, "Wikimedia Commons, par fichier"),
]


def _get(url, limite=MAX_OCTETS, essais=4):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for n in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(limite + 1)
            break
        except urllib.error.URLError:
            # Coupure réseau passagère : réessayer, sinon le tirage dépendrait du réseau.
            if n == essais - 1:
                raise
            time.sleep(10 * (n + 1))
    if len(data) > limite:
        raise ValueError("fichier trop gros")
    return data


def _json(url):
    return json.loads(_get(url).decode("utf-8"))


def _ligne_hf(jeu, config, split, indice):
    """URL de l'image de la ligne `indice` (API de lignes du visualiseur)."""
    q = urllib.parse.urlencode({"dataset": jeu, "config": config, "split": split,
                                "offset": indice, "length": 1})
    row = _json(f"{HF}?{q}")["rows"][0]["row"]
    return row["image"]["src"]


class _FichierDistant:
    """Fichier HTTP lu par plages (Range) : pyarrow n'en lit que le pied et un groupe."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.taille = int(r.headers["Content-Length"])

    def seek(self, pos, whence=0):
        self.pos = {0: pos, 1: self.pos + pos, 2: self.taille + pos}[whence]
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        fin = self.taille if n is None or n < 0 else min(self.taille, self.pos + n)
        if fin <= self.pos:
            return b""
        req = urllib.request.Request(self.url, headers={
            "User-Agent": AGENT, "Range": f"bytes={self.pos}-{fin - 1}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def seekable(self):
        return True

    def readable(self):
        return True

    closed = False

    def close(self):
        pass


def _image_parquet(jeu, config, split, indice):
    """Octets de l'image de la ligne `indice`, lus dans la copie parquet du jeu.

    Secours quand l'API de lignes ne répond pas : même ordre de lignes (l'API lit ce
    même parquet), donc le même tirage. Seul le groupe de lignes utile est téléchargé.
    """
    import pyarrow.parquet as pq  # facultatif : seulement pour ce secours
    urls = _json(f"https://huggingface.co/api/datasets/{jeu}/parquet/{config}/{split}")
    reste = indice
    for url in urls:
        f = pq.ParquetFile(_FichierDistant(url))
        for g in range(f.metadata.num_row_groups):
            n = f.metadata.row_group(g).num_rows
            if reste < n:
                cell = f.read_row_group(g, columns=["image"]).column("image")[reste].as_py()
                if len(cell["bytes"]) > MAX_OCTETS:
                    raise ValueError("fichier trop gros")
                return cell["bytes"]
            reste -= n
    raise IndexError(indice)


def _fichiers_commons(categorie):
    """Fichiers bitmap ou SVG de la catégorie, triés par titre (ordre stable)."""
    titres, suite = [], {}
    while True:
        q = {"action": "query", "list": "categorymembers", "cmtitle": categorie,
             "cmtype": "file", "cmlimit": 500, "format": "json", **suite}
        j = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
        titres += [m["title"] for m in j["query"]["categorymembers"]
                   if m["title"].lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".gif"))]
        if "continue" not in j:
            return sorted(titres)
        suite = j["continue"]


def _image_commons(titre):
    q = {"action": "query", "titles": titre, "prop": "imageinfo", "iiprop": "url|extmetadata",
         "iiurlwidth": 1200, "format": "json"}
    j = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
    info = next(iter(j["query"]["pages"].values()))["imageinfo"][0]
    lic = info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "?")
    return info.get("thumburl") or info["url"], info["descriptionurl"], lic


def _admise(data):
    lus = img.lire_image(data, delai_s=600)
    textes = [t for t, _ in lus if any(c.isalpha() for c in t)]
    return lus if len(textes) >= MIN_TEXTES else None


def main():
    os.makedirs(os.path.join(BANC, "cas"), exist_ok=True)
    chemin_prov = os.path.join(BANC, "provenance.json")
    prov = json.load(open(chemin_prov, encoding="utf-8")) if os.path.exists(chemin_prov) else {}
    refus = []
    for rang, (nom, jeu, config, split, taille, nombre, licence) in enumerate(SOURCES):
        alea = random.Random(GRAINE + rang)
        deja = sum(1 for c in prov.values() if c["source"] == nom)
        if deja >= nombre:
            # Source complète : ne rien retélécharger (une autre voie d'accès peut
            # renvoyer un encodage différent, donc une autre empreinte : faux nouveau cas).
            print(f"{nom} : {deja}/{nombre} (déjà tirée)", flush=True)
            continue
        if jeu is None:
            titres = _fichiers_commons(split)
            ordre = alea.sample(range(len(titres)), min(ESSAIS_MAX, len(titres)))
        else:
            ordre = alea.sample(range(taille), min(ESSAIS_MAX, taille))
        gardes = 0
        for indice in ordre:
            if gardes >= nombre:
                break
            try:
                if jeu is None:
                    url, page, lic = _image_commons(titres[indice])
                    ident, lic_cas = titres[indice], lic
                    data = _get(url)
                else:
                    ident, page, lic_cas = f"{jeu}:{config}:{split}:{indice}", f"https://huggingface.co/datasets/{jeu}", licence
                    try:
                        data = _get(_ligne_hf(jeu, config, split, indice), essais=1)
                    except urllib.error.HTTPError:
                        data = _image_parquet(jeu, config, split, indice)
            except Exception as e:  # noqa: BLE001 — une image injoignable est refusée et notée
                refus.append((nom, indice, f"téléchargement : {e}"))
                continue
            sha = hashlib.sha256(data).hexdigest()[:10]
            cas = os.path.join(BANC, "cas", sha)
            if sha in prov:
                gardes += 1
                continue
            try:
                lus = _admise(data)
            except Exception as e:  # noqa: BLE001 — image illisible (format) : refusée
                refus.append((nom, indice, f"lecture : {e}"))
                continue
            if lus is None:
                refus.append((nom, indice, f"moins de {MIN_TEXTES} textes lus"))
                continue
            os.makedirs(cas, exist_ok=True)
            with open(os.path.join(cas, "source.img"), "wb") as f:
                f.write(data)
            with open(os.path.join(cas, "lus.json"), "w", encoding="utf-8") as f:
                json.dump([[t, list(map(int, b))] for t, b in lus], f, ensure_ascii=False, indent=1)
            prov[sha] = {"source": nom, "id": ident, "page": page, "licence": lic_cas,
                         "graine": GRAINE + rang, "textes": len(lus)}
            with open(chemin_prov, "w", encoding="utf-8") as f:
                json.dump(prov, f, ensure_ascii=False, indent=1)
            gardes += 1
            print(f"{nom:<14} {indice:>6} → {sha} ({len(lus)} textes)", flush=True)
        print(f"{nom} : {gardes}/{nombre}", flush=True)
    with open(os.path.join(BANC, "refus.json"), "w", encoding="utf-8") as f:
        json.dump(refus, f, ensure_ascii=False, indent=1)
    print(f"{len(prov)} cas, {len(refus)} refus. Dossier : {BANC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
