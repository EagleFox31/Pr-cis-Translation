"""Image traduite pour l'extension (OCR v2, étude §7.2).

Images générées (dégradé, étiquettes colorées) lues par un lecteur simulé :
contrôles d'entrée, blocs, mise en place, effacement et dessin. Puis, si les
poids PP-OCRv6 sont là, lecture réelle et relecture de la traduction
(anglais, et japonais si une police japonaise est installée).

    backend/venv/Scripts/python.exe backend/tests/test_ocr_v2_image.py
"""
import io
import os
import time

import racine  # noqa: F401
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from app.services.ocr_v2 import image as module
from app.services.ocr_v2.detect import Mot
from app.services.ocr_v2.image import ImageRefusee, blocs, lignes, placer, traduire_image, verifier

POLICE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts",
                      "montserrat-Regular.ttf")
JAPONAISES = ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "C:/Windows/Fonts/YuGothM.ttc")
ROUGE = (200, 30, 30)
TRADUCTIONS = {"Cooling water": "Eau de refroidissement", "Main pump": "Pompe principale",
               "Tank": "Réservoir", "Valve": "Vanne " * 40, "冷却水": "Eau de refroidissement",
               "冷却水ポンプ": "Pompe à eau"}


def traduire(textes):
    return [TRADUCTIONS.get(t, t) for t in textes]


class Simule:
    """Lecteur qui renvoie les mots dessinés, avec leur boîte exacte."""

    def __init__(self, mots):
        self.mots = mots

    def manquant(self):
        return None

    def lire(self, chemin, delai):
        return self.mots


def fond(w=640, h=360):
    x = np.linspace(0, 1, w)[None, :, None]
    y = np.linspace(0, 1, h)[:, None, None]
    return (np.array([235, 240, 250]) * (1 - 0.25 * x) - 30 * y).clip(0, 255).astype(np.uint8) \
        * np.ones((h, w, 3), np.uint8)


def dessiner(etiquettes, police=POLICE, conf=95):
    """Image + mots simulés pour `[(texte, (x, y), taille, couleur), …]`."""
    im = Image.fromarray(fond())
    d = ImageDraw.Draw(im)
    mots = []
    for n, (texte, (x, y), taille, couleur) in enumerate(etiquettes):
        f = ImageFont.truetype(police, taille)
        cx = x
        for mot in texte.split():
            l, t, r, b = d.textbbox((cx, y), mot, font=f)
            d.text((cx, y), mot, font=f, fill=couleur)
            mots.append(Mot(mot, (l, t, r - l, b - t), conf, (n,)))
            cx += f.getlength(mot + " ")
    return im, mots


def octets(im, fmt="PNG"):
    b = io.BytesIO()
    im.save(b, fmt, **({"save_all": True} if fmt == "GIF" else {}))
    return b.getvalue()


def cas_controles():
    for data, code in ((b"x" * (module.OCTETS_MAX + 1), "taille"), (b"pas une image", "type"),
                       (octets(Image.new("RGB", (8, 8)), "BMP"), "type"),
                       (octets(Image.new("L", (6000, 5000))), "pixels")):
        try:
            verifier(data)
        except ImageRefusee as e:
            assert e.code == code, (e.code, code)
        else:
            raise AssertionError(f"accepté : {code}")
    b = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(b, "GIF", save_all=True,
                                         append_images=[Image.new("RGB", (8, 8), "blue")])
    try:
        verifier(b.getvalue())
    except ImageRefusee as e:
        assert e.code == "animee", e.code
    else:
        raise AssertionError("GIF animé accepté")
    # JPEG de smartphone (MPO, deux images) : accepté comme un JPEG.
    b = io.BytesIO()
    Image.new("RGB", (8, 8)).save(b, "MPO", save_all=True, append_images=[Image.new("RGB", (8, 8))])
    assert verifier(b.getvalue()).format == "MPO"
    tronque = octets(Image.fromarray(fond()), "JPEG")[:2000]
    try:
        traduire_image(tronque, traduire, Simule([]))
    except ImageRefusee as e:
        assert e.code == "type", e.code
    else:
        raise AssertionError("JPEG tronqué accepté")
    print("  contrôles : taille, type, pixels, animée, tronqué ; MPO accepté")


def cas_blocs():
    mots = [Mot("Main", (10, 10, 40, 20), 95, (0,)), Mot("pump", (55, 10, 45, 20), 95, (0,)),
            Mot("is", (10, 38, 15, 20), 95, (1,)), Mot("on", (30, 38, 20, 20), 90, (1,)),
            Mot("Tank", (300, 200, 50, 20), 95, (2,)),
            Mot("flou", (10, 300, 50, 20), 40, (3,)),
            Mot("冷却", (400, 10, 40, 20), 95, (4,)), Mot("水", (442, 10, 20, 20), 95, (4,))]
    ls = lignes(mots)
    assert [t for t, _ in ls] == ["Main pump", "is on", "Tank", "冷却水"], ls
    bs = blocs(ls)
    assert [b.texte for b in bs] == ["Main pump is on", "Tank", "冷却水"], [b.texte for b in bs]
    assert bs[0].boite == (10, 10, 90, 48), bs[0].boite
    # Boîtes qui débordent sur la ligne du dessus (PP-OCR) : même paragraphe.
    assert len(blocs([("a b", (10, 10, 90, 24)), ("c d", (10, 30, 80, 24))])) == 1
    print("  blocs : lignes empilées réunies, confiance < 70 ignorée, japonais sans espace")


def cas_placer():
    b = blocs([("Tank", (100, 50, 60, 24))])[0]
    b.traduction = "Cuve"
    p = placer(b, 640)
    assert len(p["lignes"]) == 1 and p["taille"] >= 20, p
    b.traduction = "Réservoir"
    p = placer(b, 640)
    assert p is not None and p["taille"] < 20, p
    assert p["x"] >= 0 and all(module._police(module._fichier_police(), p["taille"]).getlength(t)
                               <= 60 * module.ELARGIR for t in p["lignes"]), p
    b.traduction = "Vanne " * 40
    assert placer(b, 640) is None
    print(f"  mise en place : élargie et réduite ({p['taille']} px, {len(p['lignes'])} ligne(s)), "
          "trop longue refusée")


def cas_rendu():
    etiquettes = [("Cooling water", (40, 40), 30, ROUGE), ("Main pump", (40, 160), 26, (20, 20, 20)),
                  ("Valve", (420, 260), 24, (20, 20, 20))]
    im, mots = dessiner(etiquettes)
    mots.append(Mot("Tank", (420, 160, 50, 24), 30, (9,)))  # confiance basse : non touché
    data = octets(im)
    t0 = time.monotonic()
    res = traduire_image(data, traduire, Simule(mots))
    sortie = Image.open(io.BytesIO(res.data))
    assert res.mime == "image/png" and sortie.size == im.size and res.remplacee
    par = {b.texte: b for b in res.blocs}
    assert set(par) == {"Cooling water", "Main pump", "Valve"}, set(par)
    assert par["Cooling water"].remplace and par["Main pump"].remplace
    assert not par["Valve"].remplace and par["Valve"].traduction.startswith("Vanne")
    a, s = np.asarray(im).astype(int), np.asarray(sortie.convert("RGB")).astype(int)
    # Bloc trop long : pixels d'origine intacts.
    x, y, w, h = par["Valve"].boite
    assert (a[y:y + h, x:x + w] == s[y:y + h, x:x + w]).all()
    # Traduction dessinée en rouge à l'endroit de « Cooling water ».
    x, y, w, h = par["Cooling water"].boite
    zone = s[y - 4:y + h + 4, max(x - 40, 0):x + int(w * 1.4)]
    rouge = (np.abs(zone - ROUGE).sum(axis=2) < 60).sum()
    assert rouge > 150, rouge
    # Hors des blocs, l'image n'a pas bougé.
    hors = np.ones(a.shape[:2], bool)
    for b in res.blocs:
        x, y, w, h = b.boite
        hors[max(y - 12, 0):y + h + 12, max(x - int(w * 0.25), 0):x + int(w * 1.25)] = False
    assert (np.abs(a - s).max(axis=2)[hors] <= 2).all()
    # JPEG reste JPEG ; l'alpha est conservé.
    assert traduire_image(octets(im, "JPEG"), traduire, Simule(mots)).mime == "image/jpeg"
    rgba = im.convert("RGBA")
    rgba.putpixel((5, 5), (0, 0, 0, 0))
    sortie = Image.open(io.BytesIO(traduire_image(octets(rgba), traduire, Simule(mots)).data))
    assert sortie.mode == "RGBA" and sortie.getpixel((5, 5))[3] == 0
    # Rien à remplacer : l'original revient tel quel (pas de ré-encodage).
    assert traduire_image(data, lambda ts: ts, Simule(mots)).data == data
    # Retours à la ligne du traducteur : ramenés à des espaces.
    res = traduire_image(data, lambda ts: [t.replace(" ", "\n") for t in traduire(ts)], Simule(mots))
    assert all("\n" not in b.traduction for b in res.blocs) and res.remplacee
    # Profil couleur conservé.
    b = io.BytesIO()
    im.save(b, "PNG", icc_profile=b"profil-test")
    assert Image.open(io.BytesIO(traduire_image(b.getvalue(), traduire, Simule(mots)).data)).info.get(
        "icc_profile") == b"profil-test"
    print(f"  rendu : 2 blocs remplacés, 1 gardé, 1 ignoré, reste intact, original rendu si rien à faire ({time.monotonic() - t0:.1f} s)")


def cas_ppocr():
    from app.services.ocr_v2.ppocr import PPOCR
    lecteur = PPOCR()
    if lecteur.manquant():
        print("  SAUTÉ PP-OCRv6 : onnxruntime ou poids absents (scripts/telecharger_ppocr.py)")
        return
    jp = next((p for p in JAPONAISES if os.path.isfile(p)), None)
    cas = [("anglais", POLICE, "refroidissement",
            [("Cooling water", (60, 80), 34, ROUGE), ("Main pump", (60, 220), 30, (20, 20, 20))])]
    if jp:
        cas.append(("japonais", jp, "pompe", [("冷却水ポンプ", (60, 80), 40, ROUGE)]))
    else:
        print("  SAUTÉ japonais : aucune police japonaise installée")
    for nom, police, attendu, etiquettes in cas:
        im, _ = dessiner(etiquettes, police)
        res = traduire_image(octets(im), traduire, lecteur)
        assert all(b.remplace for b in res.blocs) and res.blocs, (nom, res.blocs)
        relu = " ".join(m.texte for m in lecteur.lire(_png(res.data), 30))
        assert attendu in relu.lower(), (nom, relu)
        source = [t for t, *_ in etiquettes]
        assert not any(w in relu for t in source for w in t.split()) and not any(
            "぀" <= c <= "鿿" for c in relu), (nom, relu)
        print(f"  PP-OCRv6 {nom} : relu « {relu} »")


def _png(data):
    chemin = os.path.join(os.environ.get("TEMP", "/tmp"), "test-ocr-v2-image.png")
    with open(chemin, "wb") as f:
        f.write(data)
    return chemin


def main():
    debut = time.monotonic()
    cas_controles()
    cas_blocs()
    cas_placer()
    cas_rendu()
    cas_ppocr()
    print(f"OK image traduite ({time.monotonic() - debut:.1f} s)")


if __name__ == "__main__":
    main()
