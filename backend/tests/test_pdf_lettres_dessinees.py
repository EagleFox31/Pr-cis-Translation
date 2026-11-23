"""
LETTRES DESSINÉES (moteur PDF 1.0.14) — preuve sur des PDF SYNTHÉTIQUES.

Un mot dont la première lettre est un DESSIN peint après le texte (initiale
colorée, lettrine) ne se traduit pas à moitié. Règles testées :

  A   dessin PLEIN d'une seule couleur, peint après le texte, qui masque la
      première lettre d'un mot : la lettre n'est plus retirée, le mot entier
      part au traducteur, la lettre reçoit son propre style (couleur du dessin,
      taille agrandie) qui passe à la PREMIÈRE lettre du mot traduit. Le dessin
      d'origine n'est pas repeint.
  3   (filet) dessin opaque non reconstituable (lettre ornée) : repeint APRÈS
      le texte, ligne ANCRÉE (même départ, même ligne de base), obstacle fixe
      du flux vertical.
  =   inchangés : contours, surligneurs multiply, pastilles couvrant des mots
      entiers, logos sans texte dessous.

Chaque cas : assertions automatiques ET image « original | traduit » (x2) dans
backend/tests/out_lettres_dessinees/Cn_<nom>.png, plus une planche.png.

Aucun appel API : la traduction est simulée (même schéma que
test_engine_v2_generic.py). La forme des lettres vient d'un glyphe de police
système (Arial gras), dessiné en chemin plein : aucune police n'est livrée.

    backend/venv/Scripts/python.exe backend/tests/test_pdf_lettres_dessinees.py
"""

import os
import sys

import fitz
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

import racine  # noqa: F401
from engines.pdf.engine import PDFObjectEngine        # noqa: E402
from engines.pdf import tagging                        # noqa: E402

DOSSIER = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(DOSSIER, "out_lettres_dessinees")
# Police grasse livrée avec le dépôt : même dessin de lettre sur tous les postes
# (Windows, CI Linux). Une police système change la forme des lettres.
POLICE_LETTRES = os.path.join(os.path.dirname(DOSSIER), "fonts",
                              "roboto-Bold.ttf")

LARG, HAUT = 300, 130
GRIS, ROUGE = (0.25, 0.25, 0.25), (0.93, 0.27, 0.18)
JAUNE, BLEU = (1.0, 0.85, 0.0), (0.1, 0.25, 0.7)


# ── Fabrication des PDF ──────────────────────────────────────────────────────
class _Chemin(BasePen):
    """Glyphe → liste de segments en points de page (courbes cubiques)."""

    def __init__(self, glyphes, x, base, k):
        super().__init__(glyphes)
        self.k, self.x, self.base = k, x, base
        self.contours, self._cur, self._p = [], None, None

    def _pt(self, p):
        return fitz.Point(self.x + p[0] * self.k, self.base - p[1] * self.k)

    def _moveTo(self, p):
        self._cur = []
        self.contours.append(self._cur)
        self._p = self._pt(p)
        self._start = self._p

    def _lineTo(self, p):
        q = self._pt(p)
        self._cur.append(("l", self._p, q))
        self._p = q

    def _curveToOne(self, a, b, c):
        q = self._pt(c)
        self._cur.append(("c", self._p, self._pt(a), self._pt(b), q))
        self._p = q

    def _closePath(self):
        if self._cur is not None and self._p != self._start:
            self._cur.append(("l", self._p, self._start))


_FONTE = {}


def glyphe(page, car, x, base, taille, couleur):
    """Dessine `car` (chemin plein, une seule couleur) : origine (x, base)."""
    if "tt" not in _FONTE:
        _FONTE["tt"] = TTFont(POLICE_LETTRES)
    tt = _FONTE["tt"]
    gs = tt.getGlyphSet()
    nom = tt.getBestCmap()[ord(car)]
    pen = _Chemin(gs, x, base, taille / tt["head"].unitsPerEm)
    gs[nom].draw(pen)
    sh = page.new_shape()
    for contour in pen.contours:
        for seg in contour:
            if seg[0] == "l":
                sh.draw_line(seg[1], seg[2])
            else:
                sh.draw_bezier(seg[1], seg[2], seg[3], seg[4])
    sh.finish(fill=couleur, color=None, even_odd=True, closePath=True)
    sh.commit()


def multiplier(doc, page):
    """Applique le mode de fusion Multiply au DERNIER flux de contenu."""
    xr = doc.get_new_xref()
    doc.update_object(xr, "<</Type/ExtGState/BM/Multiply>>")
    rx = int(doc.xref_get_key(page.xref, "Resources")[1].split()[0])
    doc.xref_set_key(rx, "ExtGState", f"<</GS1 {xr} 0 R>>")
    x = page.get_contents()[-1]
    s = doc.xref_stream(x).decode("latin1")
    doc.update_stream(x, ("/GS1 gs\n" + s).encode("latin1"))


def nouvelle_page(larg=LARG, haut=HAUT):
    doc = fitz.open()
    return doc, doc.new_page(width=larg, height=haut)


def cas_c1():
    doc, pg = nouvelle_page()
    pg.insert_text((20, 60), "Seiri", fontname="helv", fontsize=20, color=GRIS)
    glyphe(pg, "S", 19.5, 60, 22, ROUGE)
    return doc


def cas_c2():
    doc, pg = nouvelle_page()
    pg.insert_text((20, 50), "Seiton", fontname="helv", fontsize=20, color=GRIS)
    glyphe(pg, "S", 19.5, 50, 22, ROUGE)
    pg.insert_text((20, 100), "Seiso", fontname="helv", fontsize=20, color=GRIS)
    glyphe(pg, "S", 19.5, 100, 22, ROUGE)
    return doc


def _orne(pg, base, taille=22):
    """Lettre ornée : « S » rouge portant un second « S » jaune plus petit —
    deux couleurs visibles, donc impossible à refaire avec une police."""
    glyphe(pg, "S", 19.5, base, taille, ROUGE)
    glyphe(pg, "S", 19.5 + taille * 0.17, base - taille * 0.17, taille * 0.66,
           JAUNE)


def cas_c3():
    doc, pg = nouvelle_page()
    pg.insert_text((20, 60), "Seiri", fontname="helv", fontsize=20, color=GRIS)
    _orne(pg, 60)
    return doc


def cas_c4(avant=False):
    doc, pg = nouvelle_page()
    if avant:
        pg.draw_rect(fitz.Rect(14, 38, 150, 72), color=ROUGE, width=1.5)
    pg.insert_text((20, 60), "Seiri", fontname="helv", fontsize=20, color=GRIS)
    if not avant:
        pg.draw_rect(fitz.Rect(14, 38, 150, 72), color=ROUGE, width=1.5)
    return doc


def cas_c5(avant=False):
    doc, pg = nouvelle_page()

    def surligneur():
        sh = pg.new_shape()
        sh.draw_rect(fitz.Rect(18, 40, 140, 68))
        sh.finish(fill=JAUNE, color=None)
        sh.commit()
        multiplier(doc, pg)

    if avant:
        surligneur()
    pg.insert_text((20, 60), "Highlight me", fontname="helv", fontsize=16,
                   color=(0, 0, 0))
    if not avant:
        surligneur()
    return doc


def cas_c6():
    doc, pg = nouvelle_page()
    pg.insert_text((20, 60), "Hidden words", fontname="helv", fontsize=16,
                   color=GRIS)
    pg.draw_oval(fitz.Rect(10, 38, 135, 72), color=None, fill=ROUGE)
    pg.insert_text((20, 105), "Visible line stays", fontname="helv",
                   fontsize=12)
    return doc


def cas_c7():
    doc, pg = nouvelle_page()
    for i, c in enumerate("ABC"):
        glyphe(pg, c, 20 + 26 * i, 60, 30, BLEU)
    pg.insert_text((20, 105), "Plain caption", fontname="helv", fontsize=12)
    return doc


def cas_c8():
    doc, pg = nouvelle_page(LARG, 230)
    pg.insert_text((20, 60), "Seiri is step one", fontname="helv",
                   fontsize=20, color=GRIS)
    _orne(pg, 60, 22)
    pg.insert_textbox(fitz.Rect(20, 150, 190, 200),
                      "A second paragraph follows below",
                      fontname="helv", fontsize=12)
    return doc


# ── Extraction + traduction factice + rendu ──────────────────────────────────
def traduire(doc, faux):
    """Extrait la page 0, injecte la traduction factice, rend. Renvoie
    (moteur, données de page, document traduit)."""
    eng = PDFObjectEngine()
    pd = eng.extract_page_data(doc, 0, doc[0], embed_images=True)
    eng._build_fonts({"fonts": eng._extract_fonts(doc)})
    envoyes = []
    for p in pd["elements"]:
        if p.get("type") != "paragraph":
            continue
        tagged, meta = tagging.tag_paragraph(p)
        p["tr_segments"] = meta
        cle = (p.get("text") or "").strip()
        envoyes.append(cle)
        p["tr_tagged"] = (f"[[0]]{faux[cle]}[[/0]]" if cle in faux else tagged)
    pd["_envoyes"] = envoyes
    out = fitz.open()
    eng.render_page_into(out, pd, draw_borders=False, translated=True)
    return eng, pd, out


def paras(pd):
    return [e for e in pd["elements"] if e.get("type") == "paragraph"]


def dessins(pd):
    return [e for e in pd["elements"] if e.get("type") == "drawing"]


def caracteres(page):
    """[(car, (r,g,b) 0..1, taille, origine, bbox)] du rendu."""
    res = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", ()):
            for s in ln["spans"]:
                c = s["color"]
                rgb = ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255,
                       (c & 255) / 255)
                for ch in s["chars"]:
                    res.append((ch["c"], rgb, s["size"], ch["origin"],
                                ch["bbox"]))
    return res


def proche(a, b, tol=0.06):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def rouges(page):
    """Dessins pleins rouges de la page."""
    return [d for d in page.get_drawings()
            if d.get("fill") and proche(d["fill"], ROUGE, 0.02)]


def pixels(page, zoom=2, clip=None):
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip,
                           alpha=False)


def quasi_egaux(pa, pb, tol=24, part=0.002):
    """Deux pixmaps de même taille : au plus `part` de pixels qui diffèrent."""
    if (pa.width, pa.height) != (pb.width, pb.height):
        return False
    a, b = pa.samples, pb.samples
    n = pa.n
    diff = 0
    for i in range(0, len(a), n):
        if max(abs(a[i + k] - b[i + k]) for k in range(3)) > tol:
            diff += 1
    return diff <= part * pa.width * pa.height


# ── Images ───────────────────────────────────────────────────────────────────
def cote_a_cote(src, out, chemin, titre=None):
    """Original | traduit, x2 : un fichier PNG."""
    w, h = src[0].rect.width, src[0].rect.height
    d = fitz.open()
    pg = d.new_page(width=2 * w + 6, height=h)
    pg.draw_rect(pg.rect, color=None, fill=(0.8, 0.8, 0.8))
    for x0 in (0, w + 6):                       # pages sur fond blanc
        pg.draw_rect(fitz.Rect(x0, 0, x0 + w, h), color=None, fill=(1, 1, 1))
    pg.show_pdf_page(fitz.Rect(0, 0, w, h), src, 0)
    pg.show_pdf_page(fitz.Rect(w + 6, 0, 2 * w + 6, h), out, 0)
    pixels(pg).save(chemin)


def planche(entrees, chemin):
    """Planche contact : une ligne par cas, avec son titre."""
    marge, titre_h = 6, 16
    imgs = [(t, fitz.Pixmap(p)) for t, p in entrees]
    larg = max(i.width for _t, i in imgs) / 2 + 2 * marge
    haut = sum(i.height / 2 + titre_h + marge for _t, i in imgs) + marge
    d = fitz.open()
    pg = d.new_page(width=larg, height=haut)
    y = marge
    for t, i in imgs:
        pg.insert_text((marge, y + 11), t, fontname="helv", fontsize=9,
                       color=(0, 0, 0))
        y += titre_h
        r = fitz.Rect(marge, y, marge + i.width / 2, y + i.height / 2)
        pg.insert_image(r, pixmap=i)
        y += i.height / 2 + marge
    pixels(pg, 1.5).save(chemin)


# ── Exécution ────────────────────────────────────────────────────────────────
def run():
    os.makedirs(SORTIE, exist_ok=True)
    checks, images = [], []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    def image(cle, titre, src, out):
        chemin = os.path.join(SORTIE, f"{cle}.png")
        cote_a_cote(src, out, chemin)
        images.append((titre, chemin))

    # ── C1 : la lettre dessinée devient du style ────────────────────────────
    src = cas_c1()
    eng, pd, out = traduire(src, {"Seiri": "Trier"})
    pg = out[0]
    ch = caracteres(pg)
    ts = [c for c in ch if c[0] == "T"]
    reste = [c for c in ch if c[0] in "rier"]
    ok("C1  piège armé (le S rouge masque bien le S gris)",
       any(d.get("fill") and proche(d["fill"], ROUGE, 0.02)
           for d in src[0].get_drawings()) and "Seiri" in src[0].get_text(), "")
    ok("C1  le mot ENTIER part au traducteur", pd["_envoyes"] == ["Seiri"],
       str(pd["_envoyes"]))
    ok("C1  un seul T, aucun S", len(ts) == 1
       and not any(c[0] == "S" for c in ch),
       "".join(c[0] for c in ch))
    ok("C1  le T porte la couleur du dessin",
       ts and proche(ts[0][1], ROUGE), str(ts[0][1] if ts else None))
    ok("C1  le T est plus grand que le reste du mot",
       ts and reste and ts[0][2] > max(c[2] for c in reste) + 0.5,
       f"T={ts[0][2] if ts else None} reste={[c[2] for c in reste]}")
    ok("C1  le reste du mot garde la couleur du texte",
       reste and all(proche(c[1], GRIS) for c in reste),
       str([c[1] for c in reste]))
    ok("C1  le dessin d'origine n'est PAS repeint", not rouges(pg),
       f"{len(rouges(pg))} dessin(s) rouge(s)")
    ok("C1  la lettre est du vrai texte et le mot se lit « Trier »",
       "Trier" in pg.get_text().replace("\n", ""), repr(pg.get_text()))
    image("C1_lettre_dessinee_style", "C1  S rouge dessiné -> T rouge agrandi",
          src, out)

    # ── C2 : deux autres mots, même règle ───────────────────────────────────
    src = cas_c2()
    eng, pd, out = traduire(src, {"Seiton": "Ranger", "Seiso": "Système"})
    pg = out[0]
    ch = caracteres(pg)
    rg = [c for c in ch if c[0] == "R"]
    sy = [c for c in ch if c[0] == "S"]
    ok("C2  les deux mots entiers sont envoyés",
       sorted(pd["_envoyes"]) == ["Seiso", "Seiton"], str(pd["_envoyes"]))
    ok("C2  « Ranger » : un seul R rouge agrandi",
       len(rg) == 1 and proche(rg[0][1], ROUGE)
       and rg[0][2] > max(c[2] for c in ch if c[0] in "anger") + 0.5,
       str([(c[1], c[2]) for c in rg]))
    ok("C2  « Système » : un seul S rouge, pas de doublon",
       len(sy) == 1 and proche(sy[0][1], ROUGE), str([c[1] for c in sy]))
    ok("C2  aucune lettre d'origine ni dessin rouge résiduel",
       not rouges(pg) and "Seiton" not in pg.get_text()
       and "Seiso" not in pg.get_text(), "")
    ok("C2  mots complets",
       "Ranger" in pg.get_text().replace("\n", "")
       and "Système" in pg.get_text(), repr(pg.get_text()))
    bases = {round(c[3][1], 1) for c in ch
             if c[0] in "Ranger" and c[3][1] < 75}
    ok("C2  « Ranger » tient sur une seule ligne (rétréci, pas coupé)",
       len(bases) == 1, str(bases))
    image("C2_deux_mots", "C2  Seiton -> Ranger, Seiso -> Système", src, out)

    # ── C3 : lettre ornée = filet (avant-plan ancré) ────────────────────────
    src = cas_c3()
    eng, pd, out = traduire(src, {"Seiri": "Trier"})
    pg = out[0]
    ch = caracteres(pg)
    orig = [c for c in caracteres(src[0]) if c[0] == "e"]
    mot = [c for c in ch if c[0] == "T"]
    ap = [d for d in dessins(pd) if d.get("_avant_plan")]
    ok("C3  mot entier envoyé, lettre non retirée", pd["_envoyes"] == ["Seiri"],
       str(pd["_envoyes"]))
    ok("C3  le dessin orné est marqué avant-plan", len(ap) >= 1, str(len(ap)))
    ok("C3  aucune lettre refaite (pas de run initiale)",
       not any(r.get("initiale") or r.get("initiale_suite")
               for p in paras(pd) for ln in p["lines"] for r in ln["runs"]), "")
    ok("C3  le dessin est repeint (rouge et jaune présents)",
       len(rouges(pg)) >= 1 and any(
           d.get("fill") and proche(d["fill"], JAUNE, 0.02)
           for d in pg.get_drawings()), f"{len(rouges(pg))} rouge(s)")
    texte_seq = [t["seqno"] for t in pg.get_texttrace()]
    dessin_seq = [d["seqno"] for d in rouges(pg)]
    ok("C3  repeint APRÈS le texte (au-dessus)",
       texte_seq and dessin_seq and min(dessin_seq) > max(texte_seq),
       f"texte={texte_seq} dessin={dessin_seq}")
    src_s = [c for c in caracteres(src[0])]
    x0_src = min(c[3][0] for c in src_s if proche(c[1], GRIS, 0.01))
    base_src = orig[0][3][1]
    ok("C3  ligne ancrée : même x de départ (0,5 pt)",
       mot and abs(mot[0][3][0] - x0_src) <= 0.5,
       f"{mot[0][3][0] if mot else None} vs {x0_src}")
    ok("C3  ligne ancrée : même ligne de base (0,5 pt)",
       mot and abs(mot[0][3][1] - base_src) <= 0.5,
       f"{mot[0][3][1] if mot else None} vs {base_src}")
    ok("C3  le mot traduit est là", "Trier" in pg.get_text().replace("\n", ""),
       repr(pg.get_text()))
    image("C3_lettre_ornee", "C3  lettre ornée : dessin repeint, ligne ancrée",
          src, out)

    # ── C4 : un contour peint après le texte reste derrière ─────────────────
    src = cas_c4()
    eng, pd, out = traduire(src, {"Seiri": "Trier"})
    _e, _p, ref = traduire(cas_c4(avant=True), {"Seiri": "Trier"})
    ok("C4  contour : aucun avant-plan, aucune lettre refaite",
       not any(d.get("_avant_plan") or d.get("_initiale_consommee")
               for d in dessins(pd))
       and not any(r.get("initiale") for p in paras(pd)
                   for ln in p["lines"] for r in ln["runs"]), "")
    ok("C4  contour : mot entier envoyé", pd["_envoyes"] == ["Seiri"],
       str(pd["_envoyes"]))
    sq = [t["seqno"] for t in out[0].get_texttrace()]
    dq = [d["seqno"] for d in out[0].get_drawings()]
    ok("C4  contour : peint DERRIÈRE le texte",
       sq and dq and max(dq) < min(sq), f"dessins={dq} texte={sq}")
    ok("C4  rendu identique à celui d'un contour peint avant",
       quasi_egaux(pixels(out[0]), pixels(ref[0])), "")
    image("C4_contour", "C4  contour (stroke) : inchangé", src, out)

    # ── C5 : surligneur multiply ────────────────────────────────────────────
    src = cas_c5()
    eng, pd, out = traduire(src, {"Highlight me": "Surligne-moi"})
    _e, _p, ref = traduire(cas_c5(avant=True), {"Highlight me": "Surligne-moi"})
    ok("C5  surligneur : aucun avant-plan, texte conservé",
       not any(d.get("_avant_plan") or d.get("_initiale_consommee")
               for d in dessins(pd))
       and pd["_envoyes"] == ["Highlight me"], str(pd["_envoyes"]))
    ok("C5  surligneur : texte traduit lisible",
       "Surligne-moi" in out[0].get_text(), repr(out[0].get_text()))
    pix = pixels(out[0])
    zone = fitz.IRect(36, 80, 280, 136)
    foncés = sum(1 for x in range(zone.x0, zone.x1)
                 for y in range(zone.y0, zone.y1)
                 if max(pix.pixel(x, y)) < 70)
    jaunes = sum(1 for x in range(zone.x0, zone.x1)
                 for y in range(zone.y0, zone.y1)
                 if pix.pixel(x, y)[0] > 200 and pix.pixel(x, y)[2] < 80)
    ok("C5  surligneur : encre sombre sur fond jaune (texte non effacé)",
       foncés > 150 and jaunes > 1500, f"sombres={foncés} jaunes={jaunes}")
    ok("C5  rendu identique à celui d'un surligneur peint avant",
       quasi_egaux(pixels(out[0]), pixels(ref[0])), "")
    image("C5_surligneur_multiply", "C5  surligneur multiply : reste derrière",
          src, out)

    # ── C6 : pastille opaque sur des mots entiers = comportement actuel ─────
    src = cas_c6()
    eng, pd, out = traduire(src, {"Visible line stays": "Ligne visible"})
    textes = [p.get("text") for p in paras(pd)]
    ok("C6  piège armé (le texte caché reste lisible par fitz)",
       "Hidden words" in src[0].get_text(), "")
    ok("C6  pastille : les mots entiers cachés ne sont pas extraits",
       not any("Hidden" in (t or "") for t in textes), str(textes))
    ok("C6  pastille : jamais traitée comme une initiale",
       not any(d.get("_initiale_consommee") or d.get("_avant_plan")
               for d in dessins(pd)), "")
    ok("C6  pastille : texte caché absent du rendu, autre ligne traduite",
       "Hidden" not in out[0].get_text()
       and "Ligne visible" in out[0].get_text(), repr(out[0].get_text()))
    ok("C6  pastille : toujours peinte", len(rouges(out[0])) == 1,
       f"{len(rouges(out[0]))}")
    image("C6_pastille_mots_entiers", "C6  pastille sur mots entiers : inchangé",
          src, out)

    # ── C7 : logo dessiné sans texte dessous ────────────────────────────────
    src = cas_c7()
    eng, pd, out = traduire(src, {"Plain caption": "Légende simple"})
    bleus = lambda page: [d for d in page.get_drawings() if d.get("fill")
                          and proche(d["fill"], BLEU, 0.02)]
    ok("C7  logo : aucun dessin retiré ni marqué",
       not any(d.get("_initiale_consommee") or d.get("_avant_plan")
               for d in dessins(pd)), "")
    ok("C7  logo : aucune lettre ajoutée au texte",
       not any(c in out[0].get_text() for c in "ABC")
       and "Légende simple" in out[0].get_text(), repr(out[0].get_text()))
    ok("C7  logo : tous les dessins repeints à l'identique",
       len(bleus(out[0])) == len(bleus(src[0])) >= 3,
       f"{len(bleus(out[0]))} vs {len(bleus(src[0]))}")
    zone7 = fitz.Rect(10, 20, 110, 70)
    ok("C7  logo : rendu des lettres dessinées identique",
       quasi_egaux(pixels(out[0], clip=zone7), pixels(src[0], clip=zone7)), "")
    image("C7_logo_dessine", "C7  logo ABC sans texte dessous : intouché",
          src, out)

    # ── C8 : traduction longue à côté d'un avant-plan ───────────────────────
    src = cas_c8()
    longue = ("Seiri est la première des quatre étapes de la méthode et "
              "consiste à trier ce qui est utile de ce qui ne l'est pas")
    eng, pd, out = traduire(src, {
        "Seiri is step one": longue,
        "A second paragraph follows below":
            "Un second paragraphe suit plus bas dans la page"})
    pg = out[0]
    ap = [d for d in dessins(pd) if d.get("_avant_plan")]
    zones = [fitz.Rect(d["bbox"]) for d in ap]
    # Bloc du plus grand dessin (le « S » orné) : rien d'autre ne doit y tomber
    # que la ligne ancrée elle-même (celle de sa ligne de base d'origine).
    base0 = [c for c in caracteres(src[0]) if c[0] == "e"][0][3][1]
    intrus = []
    for c in caracteres(pg):
        if abs(c[3][1] - base0) <= 0.8:
            continue
        r = fitz.Rect(c[4])
        if c[0].strip() and any(r.intersects(z) for z in zones):
            intrus.append((c[0], [round(v, 1) for v in c[4]]))
    ok("C8  avant-plan reconnu", len(ap) >= 1, str(len(ap)))
    ok("C8  aucun texte poussé sous l'avant-plan", not intrus, str(intrus[:6]))
    ok("C8  la traduction longue est entière",
       "quatre étapes" in pg.get_text().replace("\n", " ")
       and "plus bas" in pg.get_text().replace("\n", " "), repr(pg.get_text()))
    suivant = [c for c in caracteres(pg) if c[0] == "U"]
    ok("C8  le second paragraphe reste sous le premier",
       suivant and suivant[0][3][1] > base0 + 20,
       str(suivant[0][3] if suivant else None))
    image("C8_traduction_longue", "C8  traduction longue près d'un avant-plan",
          src, out)

    # ── C9 : parent dominant — grand dessin, aucun plafond ×2 ──────────────
    src, pg0 = nouvelle_page()
    pg0.insert_text((20, 60), "Seiri", fontname="helv", fontsize=12,
                    color=GRIS)
    w_s = fitz.get_text_length("S", fontname="helv", fontsize=12)
    # Dessin uni, étroit (sur la seule 1re lettre) et haut : ~2,6 × l'encre.
    # Tracé (pas un simple rectangle : celui-là est un cache classique).
    x0, x1, y0, y1 = 19.6, 20 + w_s - 0.3, 60 - 23, 60.2
    pg0.draw_polyline([(x0, y1), (x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                      color=None, fill=ROUGE, closePath=True)
    eng, pd, out = traduire(src, {"Seiri": "Trier"})
    ts = [c for c in caracteres(out[0]) if c[0] == "T"]
    ok("C9  le T prend la taille entière du dessin (> 2 × le corps)",
       ts and ts[0][2] > 2.0 * 12 + 1.0,
       f"T={ts[0][2] if ts else None} corps=12")
    image("C9_parent_dominant", "C9  grand dessin : taille du dessin",
          src, out)

    planche(images, os.path.join(SORTIE, "planche.png"))

    # ── Rapport ─────────────────────────────────────────────────────────────
    print("=" * 78)
    print("LETTRES DESSINÉES — documents SYNTHÉTIQUES")
    print("=" * 78)
    n_ok = 0
    for nom, bon, detail in checks:
        print(f"  [{'OK ' if bon else 'ÉCHEC'}] {nom}")
        if detail and not bon:
            print(f"          {detail}")
        n_ok += bon
    print()
    print(f"Images : {SORTIE}")
    print(f"== {n_ok}/{len(checks)} ==")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(run())
