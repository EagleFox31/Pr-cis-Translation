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
    # Titre et texte (hauteurs 82 et 64, essai Edge) : deux blocs.
    assert len(blocs([("冷却水ポンプ", (45, 40, 390, 82)), ("毎日点検", (45, 130, 390, 64))])) == 2
    # Une puce ouvre un bloc, même à hauteur égale.
    liste = [("1. 電源を切る", (40, 10, 300, 36)), ("2. 弁を閉じる", (40, 50, 300, 39)),
             ("・圧力を確認", (40, 92, 300, 39))]
    assert len(blocs(liste)) == 3, [b.texte for b in blocs(liste)]
    # Couleurs différentes (titre rouge, corps noir) : deux blocs.
    deux = [("a b", (10, 10, 90, 24)), ("c d", (10, 38, 80, 24))]
    assert len(blocs(deux, [ROUGE, (20, 20, 20)])) == 2
    assert len(blocs(deux, [(20, 20, 20), (30, 25, 25)])) == 1
    print("  blocs : lignes empilées réunies, confiance < 70 ignorée, japonais sans espace, "
          "hauteur, puce et couleur séparent")


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
    # Étiquette trop longue : le bloc grandit dans le vide autour.
    b = blocs([("Storage tank", (100, 50, 120, 24))])[0]
    b.traduction = "Réservoir de stockage principal du circuit de refroidissement"
    assert placer(b, 640) is None
    p = placer(b, 640, libre=(20, 160))
    assert p is not None and len(p["lignes"]) > 1, p
    assert 20 <= p["y"] and p["y"] + (len(p["lignes"]) - 1) * p["pas"] + p["haut_glyphe"] <= 160, p
    assert placer(b, 640, libre=(48, 76)) is None
    # Étiquette serrée entre deux traits (cadre = sa largeur) : sur deux lignes,
    # elle n'entre qu'en dessous du seuil de croissance ; elle grandit quand même.
    b = blocs([("Outlet pipe", (189, 140, 173, 42))])[0]
    b.traduction = "Tuyau de refoulement"
    q = placer(b, 640, libre=(78, 359), cadre=(189, 362, True))
    assert q is not None and len(q["lignes"]) == 2 and q["larg"] <= 173, q
    assert 78 <= q["y"] and q["y"] + q["haut"] <= 359, q
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
    # Hors de la bande des blocs (la traduction s'étend à droite, §7.4), l'image n'a pas bougé.
    hors = np.ones(a.shape[:2], bool)
    for b in res.blocs:
        x, y, w, h = b.boite
        hors[max(y - 12, 0):y + h + 12, max(x - int(w * 0.25), 0):] = False
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


def cas_bords():
    """Boîtes plus étroites que l'encre (sortie CTC sur du japonais) : bords effacés aussi."""
    im, mots = dessiner([("Cooling water", (60, 60), 40, ROUGE)])
    serres = []
    for m in mots:
        x, y, w, h = m.boite
        d = int(0.15 * h)
        serres.append(Mot(m.texte, (x + d, y, w - 2 * d, h), m.conf, m.ligne))
    res = traduire_image(octets(im), lambda ts: ["Eau"] * len(ts), Simule(serres))
    assert res.remplacee
    a, s = np.asarray(im).astype(int), np.asarray(Image.open(io.BytesIO(res.data)).convert("RGB")).astype(int)
    rouge_a, rouge_s = (np.abs(a - ROUGE).sum(axis=2) < 90), (np.abs(s - ROUGE).sum(axis=2) < 90)
    x0 = int(min(m.boite[0] for m in serres))
    x1 = int(np.ceil(max(m.boite[0] + m.boite[2] for m in serres)))
    bords = np.zeros(a.shape[:2], bool)
    bords[:, :x0] = bords[:, x1:] = True
    assert rouge_a[bords].sum() > 20, rouge_a[bords].sum()  # le cas reproduit bien le défaut
    assert rouge_s[bords].sum() == 0, rouge_s[bords].sum()
    # Étiquette trop longue pour sa boîte, vide autour : remplacée sur plusieurs lignes.
    im, mots = dessiner([("Tank", (280, 150), 24, (20, 20, 20))])
    res = traduire_image(octets(im), lambda ts: ["Réservoir de stockage principal du circuit"] * len(ts),
                         Simule(mots))
    assert res.remplacee, res.blocs
    print(f"  bords : {rouge_a[bords].sum()} px de glyphe hors boîte effacés ; étiquette longue placée dans le vide")


def cas_mise_en_page():
    """Comme le PDF (étude OCR v2 §7.4) : gras gardé, bord gauche, place à droite, liste d'une taille."""
    gras = POLICE.replace("Regular", "Bold")
    noir = (20, 20, 20)
    for police, attendu in [(POLICE, False), (gras, True)] + [
            (f"C:/Windows/Fonts/YuGoth{s}.ttc", s == "B") for s in "RB"
            if os.path.isfile(f"C:/Windows/Fonts/YuGoth{s}.ttc")]:
        im, mots = dessiner([("冷却水ポンプ" if "YuGoth" in police else "Cooling water", (40, 60), 40, noir)], police)
        bgr = np.asarray(im)[:, :, ::-1].copy()
        zones = [module._elargie(m.boite, bgr) for m in mots]
        assert module._gras(module.masque_couleur(bgr, zones, dilatation=0), zones,
                            "YuGoth" in police) == attendu, police
    # Titre gras seul, puis une liste de trois lignes alignées à gauche.
    etiquettes = [("Cooling water", (40, 30), 40, ROUGE)] + [
        (t, (40, 140 + 60 * i), 30, noir) for i, t in enumerate(("Stop", "Close", "Check"))]
    im = Image.fromarray(fond())
    mots = []
    for n, (texte, (x, y), taille, couleur) in enumerate(etiquettes):
        f = ImageFont.truetype(gras if n == 0 else POLICE, taille)
        ImageDraw.Draw(im).text((x, y), texte, font=f, fill=couleur)
        l, t, r, b = ImageDraw.Draw(im).textbbox((x, y), texte, font=f)
        mots.append(Mot(texte, (l, t, r - l, b - t), 95, (n,)))
    sorties = {"Cooling water": "Pompe à eau", "Stop": "Arrêter le moteur",
               "Close": "Fermer la vanne principale d'alimentation en eau du circuit",
               "Check": "Contrôler le manomètre"}
    vus = []
    origine = module._freres
    module._freres = lambda *a: vus.extend(origine(*a)) or vus
    try:
        res = traduire_image(octets(im), lambda ts: [sorties[t] for t in ts], Simule(mots))
    finally:
        module._freres = origine
    assert res.remplacee and all(b.remplace for b in res.blocs), res.blocs
    p = {b.texte: q for b, q in vus}
    assert "bold" in os.path.basename(p["Cooling water"]["fichier"]).lower(), p["Cooling water"]["fichier"]
    assert all("bold" not in os.path.basename(p[t]["fichier"]).lower() for t in ("Stop", "Close", "Check"))
    # Titre court : taille d'origine, une ligne ; bords gauches gardés (± 3 px).
    assert len(p["Cooling water"]["lignes"]) == 1
    for b in res.blocs:
        assert abs(p[b.texte]["x"] - b.boite[0]) <= 3, (b.texte, p[b.texte]["x"], b.boite)
    # La ligne longue s'étend à droite au-delà de sa boîte, et la liste garde une seule taille.
    boite = next(b.boite for b in res.blocs if b.texte == "Close")
    assert p["Close"]["larg"] > boite[2] * 2, (p["Close"]["larg"], boite)
    tailles = {p[t]["taille"] for t in ("Stop", "Close", "Check")}
    assert len(tailles) == 1, tailles
    # Aucun chevauchement entre traductions posées.
    rects = [(q["x"], q["y"], q["x"] + q["larg"], q["y"] + q["haut"]) for q in p.values()]
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert min(a[2], b[2]) <= max(a[0], b[0]) or min(a[3], b[3]) <= max(a[1], b[1]), (a, b)
    # Grand titre dont la traduction est bien plus longue, texte juste
    # dessous : il rétrécit plutôt que de rester en japonais (essai Edge 01/11).
    im = Image.fromarray(fond())
    mots = []
    for n, (texte, y, taille, f) in enumerate([("Cooling", 20, 70, gras), ("Check", 110, 40, POLICE)]):
        f = ImageFont.truetype(f, taille)
        ImageDraw.Draw(im).text((48, y), texte, font=f, fill=ROUGE if n == 0 else noir)
        l, t, r, b = ImageDraw.Draw(im).textbbox((48, y), texte, font=f)
        mots.append(Mot(texte, (l, t, r - l, b - t), 95, (n,)))
    sorties = {"Cooling": "Pompe à eau de refroidissement", "Check": "Vérifier"}
    titre = traduire_image(octets(im), lambda ts: [sorties[t] for t in ts], Simule(mots))
    assert all(b.remplace for b in titre.blocs), titre.blocs
    print(f"  mise en page : gras détecté, bords gauches gardés, liste en {tailles.pop()} px, sans chevauchement")


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


def cas_ponctuation():
    p = module._ponctuation_latine
    assert p("Freins・Pneus") == "Freins • Pneus", p("Freins・Pneus")
    assert p("Contrôle、puis essai。") == "Contrôle, puis essai.", p("Contrôle、puis essai。")
    assert p("「Résultat」（étape１）") == "“Résultat” (étape1)", p("「Résultat」（étape１）")
    assert p("冷却水・ポンプ") == "冷却水・ポンプ"  # cible CJK : intacte
    assert module._couvre(module._ROBOTO[False], p("A・B"))


def cas_mots_entiers():
    police = ImageFont.truetype(POLICE, 40)
    assert module._couper("Débutant", police, 60) == ["Débutant"]  # jamais « Déb/utant »
    assert len(module._couper("Débutant", police, 60, casser=True)) > 1
    assert len(module._couper("冷却水ポンプ", police, 60)) > 1
    b = blocs([("Base", (10, 10, 40, 20))])[0]
    b.traduction = "Fondamentaux"
    p = placer(b, 400, POLICE, cadre=(10, 60, False))
    assert p is None or p["lignes"] == ["Fondamentaux"] or p["taille"] <= module.PLANCHER_PX + 1, p


def main():
    debut = time.monotonic()
    cas_ponctuation()
    cas_mots_entiers()
    cas_controles()
    cas_blocs()
    cas_placer()
    cas_rendu()
    cas_bords()
    cas_mise_en_page()
    cas_ppocr()
    print(f"OK image traduite ({time.monotonic() - debut:.1f} s)")


if __name__ == "__main__":
    main()
