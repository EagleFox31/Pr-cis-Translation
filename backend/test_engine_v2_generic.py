"""
GÉNÉRICITÉ du moteur v2 — preuve sur un document SYNTHÉTIQUE.

Les correctifs P10-P13 ont été trouvés sur mv21, le Handbook et la démo journal.
Rien ne prouve, à ce stade, qu'ils traitent la CLASSE du problème plutôt que ces
trois documents. Ce test fabrique donc de toutes pièces un PDF que le moteur n'a
jamais vu — autres polices, autres corps, autres couleurs, autres coordonnées —
mais qui rejoue les MÊMES STRUCTURES :

  P10  titre VERTICAL à lettres espacées (+ en-tête de tableau pivoté serré)
  P12  titre pleine colonne suivi d'un FILET DE SECTION (à ne pas confondre avec
       un soulignement) · et un VRAI soulignement (à ne pas perdre)
  P13  deux colonnes séparées par une gouttière PLUS ÉTROITE que les blancs de
       justification de leurs propres lignes · et une liste à PUCES (dont
       l'indentation ne doit pas passer pour une gouttière)

Aucun appel API : la traduction est simulée. Le test échoue si un correctif ne
tient que sur les documents d'origine.

    backend/venv/Scripts/python.exe backend/test_engine_v2_generic.py
"""

import os
import sys

import fitz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdf_engine_v2.engine import PDFObjectEngine        # noqa: E402
from pdf_engine_v2 import tagging                        # noqa: E402

# Volontairement DIFFÉRENT des documents de test : autre police, autres corps,
# autres couleurs, autres marges.
FONT = "tiro"                       # Times (mv21 = ProximaNova, hb = Avenir)
ENCRE_TITRE = (0.10, 0.20, 0.55)    # bleu nuit
ENCRE_FILET = (0.62, 0.62, 0.62)    # gris — DIFFÉRENT du titre (piège P12)
ENCRE_LIEN = (0.00, 0.45, 0.35)     # vert — le trait sera de la MÊME couleur
NOIR = (0.15, 0.15, 0.15)

W, H = 612, 792                     # Letter (les 3 docs sont en A4/A5)


def _w(txt, size, font=FONT):
    return fitz.get_text_length(txt, fontname=font, fontsize=size)


def build(path):
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    # ── P12 : titre PLEINE COLONNE + filet de section (couleur différente) ───
    titre = "Regional Output Exceeds Every Published Forecast This Quarter"
    pg.insert_text((45, 70), titre, fontname=FONT, fontsize=15.5,
                   color=ENCRE_TITRE)
    # Le filet court sur TOUTE la colonne — donc de largeur ~= celle du titre :
    # le seul critère de largeur est aveugle ici (c'est le piège).
    for y in (40, 78, 700, 726, 752):          # famille de filets identiques
        pg.draw_line(fitz.Point(45, y), fitz.Point(567, y),
                     color=ENCRE_FILET, width=0.6)

    # ── P12 : VRAI soulignement (trait de la MÊME encre que son texte) ───────
    lien = "reports.example.org/quarterly"
    pg.insert_text((45, 105), lien, fontname=FONT, fontsize=10, color=ENCRE_LIEN)
    pg.draw_line(fitz.Point(45, 107.2),
                 fitz.Point(45 + _w(lien, 10), 107.2),
                 color=ENCRE_LIEN, width=0.5)

    # ── P13 : deux colonnes, gouttière PLUS ÉTROITE que les blancs de mots ───
    # Corps 9 ; on place chaque mot À LA MAIN pour imposer la géométrie :
    #   • blancs de mots (justification lâche) : 1.9 × largeur de glyphe
    #   • gouttière entre colonnes             : 2.3 × largeur de glyphe
    # -> la gouttière est PLUS ÉTROITE que le seuil de coupe (2.5) ET plus
    #    étroite que certains blancs de mots : seul le corridor peut trancher.
    size = 9
    gw = _w("n", size)                       # largeur de glyphe de référence
    mot_gap = 1.9 * gw
    gouttiere = 2.3 * gw
    colA = [
        "Regional plants raised output", "again during the period as",
        "demand held firm across the", "network of supply partners",
        "and logistics operators who", "handle the bulk of transit",
        "volumes between the ports.",
    ]
    colB = [
        "Managers credited steady", "hiring and a wider base of",
        "contracts for the result and", "expect the trend to hold as",
        "new capacity arrives at the", "northern sites during the",
        "second half of the year.",
    ]
    x_a = 45
    largeur_a = max(_w(l.replace(" ", ""), size)
                    + mot_gap * l.count(" ") for l in colA)
    x_b = x_a + largeur_a + gouttiere
    for i, (la, lb) in enumerate(zip(colA, colB)):
        y = 150 + i * 13
        for x0, ligne in ((x_a, la), (x_b, lb)):
            x = x0
            for mot in ligne.split(" "):
                pg.insert_text((x, y), mot, fontname=FONT, fontsize=size,
                               color=NOIR)
                x += _w(mot, size) + mot_gap

    # ── P13 : liste à PUCES (l'indentation NE DOIT PAS passer pour une gouttière)
    for i, item in enumerate([
            "Capacity was added at three northern sites during the period",
            "Hiring continued across the logistics and transit divisions",
            "Contract renewals covered the majority of regional partners",
            "Inventory levels returned to their long term seasonal average",
            "Maintenance windows were shortened without affecting output",
            "Freight costs eased slightly after the new routes opened up"]):
        y = 275 + i * 15
        pg.insert_text((45, y), "•", fontname=FONT, fontsize=10, color=NOIR)
        pg.insert_text((63, y), item, fontname=FONT, fontsize=10, color=NOIR)

    # ── P10 : titre VERTICAL à lettres espacées (marge gauche) ───────────────
    mot = "APPENDIX SECTION"
    y = 640                                   # part du bas, monte (dir = 0,-1)
    pas = 13.0                                # lettres ESPACÉES
    for ch in mot:
        if ch != " ":
            pg.insert_text((30, y), ch, fontname=FONT, fontsize=11,
                           color=ENCRE_TITRE, rotate=90)
        y -= pas

    # ── P10 : en-tête de tableau PIVOTÉ, dans une boîte SERRÉE ───────────────
    for k, lab in enumerate(["Region", "Output", "Change"]):
        x = 330 + k * 60
        pg.draw_rect(fitz.Rect(x - 6, 560, x + 12, 650), color=ENCRE_FILET,
                     width=0.5)
        pg.insert_text((x, 646), lab, fontname=FONT, fontsize=9, color=NOIR,
                       rotate=90)

    doc.save(path)
    doc.close()
    return path


# ═════════════════════════════════════════════════════════════════════════════
def run():
    scratch = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_generic_tmp")
    os.makedirs(scratch, exist_ok=True)
    pdf = build(os.path.join(scratch, "synthetique.pdf"))

    eng = PDFObjectEngine()
    doc = fitz.open(pdf)
    pd = eng.extract_page_data(doc, 0, doc[0], embed_images=True)
    paras = [e for e in pd["elements"] if e.get("type") == "paragraph"]
    draws = [e for e in pd["elements"] if e.get("type") == "drawing"]

    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # ── P12 ─────────────────────────────────────────────────────────────────
    soulignes = [r for p in paras for ln in p.get("lines", [])
                 for r in ln.get("runs", []) if r.get("underline")]
    txt_soulignes = " ".join(r["text"] for r in soulignes)
    ok("P12  le FILET de section n'est pas pris pour un soulignement",
       "Regional Output Exceeds" not in txt_soulignes,
       f"runs soulignés = {txt_soulignes[:60]!r}")
    ok("P12  le VRAI soulignement (même encre) est conservé",
       "reports.example.org" in txt_soulignes,
       f"runs soulignés = {txt_soulignes[:60]!r}")
    consommes = [d for d in draws if d.get("_underline_consumed")]
    ok("P12  un seul trait consommé (celui du lien)",
       len(consommes) == 1, f"{len(consommes)} trait(s) consommé(s)")

    # ── P13 : les deux colonnes ─────────────────────────────────────────────
    def _txt(p):
        return (p.get("text") or "")
    melanges = [p for p in paras
                if "Regional plants" in _txt(p) and "Managers credited" in _txt(p)]
    ok("P13  les 2 colonnes ne sont PAS entrelacées",
       not melanges,
       "un paragraphe contient les deux colonnes" if melanges else "")
    colA = [p for p in paras if "Regional plants raised" in _txt(p)]
    colB = [p for p in paras if "Managers credited steady" in _txt(p)]
    ok("P13  colonne GAUCHE reconstituée d'un bloc",
       colA and "ports" in _txt(colA[0]),
       _txt(colA[0])[:70] if colA else "(absente)")
    ok("P13  colonne DROITE reconstituée d'un bloc",
       colB and "second half" in _txt(colB[0]),
       _txt(colB[0])[:70] if colB else "(absente)")

    # ── P13 : les puces ─────────────────────────────────────────────────────
    # Contrôle GÉOMÉTRIQUE (et non textuel : la base-14 Times rend « • » en
    # « · »). Un item de liste doit démarrer à l'abscisse de SA PUCE (45), pas à
    # celle de son texte (63) — sinon le corridor d'indentation l'a détachée.
    items = [p for p in paras if "Capacity was added" in _txt(p)
             or "Freight costs eased" in _txt(p)]
    orphelines = [p for p in paras
                  if len(_txt(p).strip()) <= 1 and _txt(p).strip()]
    ok("P13  la PUCE n'est pas détachée de son texte",
       items and all(p["bbox"][0] < 55 for p in items) and not orphelines,
       f"{len(orphelines)} marqueur(s) orphelin(s) ; "
       f"x0 des items = {[round(p['bbox'][0], 1) for p in items]} (attendu ≈ 45)")

    # ── P10 : le vertical est LU ────────────────────────────────────────────
    def _rot(p):
        return any(abs((r.get("dir") or [1, 0])[1]) > 0.01
                   for ln in p.get("lines", []) for r in ln.get("runs", []))
    verticaux = [p for p in paras if _rot(p)]
    titre_v = [p for p in verticaux if "APPENDIX" in _txt(p)]
    ok("P10  le titre vertical à lettres espacées est LU comme un mot",
       titre_v and "APPENDIX SECTION" in _txt(titre_v[0]),
       _txt(titre_v[0])[:40] if titre_v else "(absent)")
    if titre_v:
        _tag, meta = tagging.tag_paragraph(titre_v[0])
        ls = (meta[0] or {}).get("letter_spaced") or {}
        bb = titre_v[0]["bbox"]
        empan = bb[3] - bb[1]                 # empan VERTICAL (axe d'écriture)
        ok("P10  l'empan est mesuré LE LONG DE L'AXE (pas en x)",
           ls and abs(ls.get("width", 0) - empan) < 2.0,
           f"ls_width={ls.get('width')} vs empan d'axe={empan:.1f} "
           f"(largeur en x = {bb[2]-bb[0]:.1f})")

    # ── P10 : le vertical est TRADUIT et RENDU dans sa bande ────────────────
    FAUX = {"APPENDIX SECTION": "SECTION ANNEXE", "Region": "Région",
            "Output": "Production", "Change": "Variation"}
    for p in paras:
        tagged, meta = tagging.tag_paragraph(p)
        p["tr_segments"] = meta
        cle = (p.get("text") or "").strip()
        p["tr_tagged"] = (f"[[0]]{FAUX[cle]}[[/0]]" if cle in FAUX else tagged)

    out = fitz.open()
    eng.render_page_into(out, pd, draw_borders=False, translated=True)
    rendu = out[0].get_text("dict")["blocks"]
    lignes_rot = [(ln["dir"], ln["bbox"],
                   "".join(s["text"] for s in ln["spans"]))
                  for b in rendu for ln in b.get("lines", [])
                  if abs(ln["dir"][1]) > 0.01]
    txt_rot = " ".join(t for _d, _b, t in lignes_rot).replace(" ", "")
    ok("P10  le titre vertical est TRADUIT au rendu",
       "SECTIONANNEXE" in txt_rot, f"rendu = {txt_rot[:60]!r}")
    ok("P10  les en-têtes pivotés sont TRADUITS",
       "Région" in txt_rot and "Production" in txt_rot,
       f"rendu = {txt_rot[:80]!r}")
    if titre_v:
        src = titre_v[0]["bbox"]
        cibles = [b for _d, b, t in lignes_rot
                  if b[1] >= src[1] - 3 and b[3] <= src[3] + 3 and b[0] < 60]
        ok("P10  le titre traduit reste DANS SA BANDE (aucun débordement)",
           cibles, f"bande source y=[{src[1]:.0f}, {src[3]:.0f}]")
    # Les en-têtes pivotés, serrés dans leur boîte, ne doivent pas se replier.
    entetes = [t for _d, _b, t in lignes_rot
               if any(k in t for k in ("Région", "Production", "Variation"))]
    ok("P10  un en-tête pivoté serré ne se REPLIE pas sur 2 lignes",
       len(entetes) == 3, f"{len(entetes)} en-tête(s) rendu(s) : {entetes}")

    # ── Rapport ─────────────────────────────────────────────────────────────
    print("=" * 78)
    print("GÉNÉRICITÉ — document SYNTHÉTIQUE (jamais vu par le moteur)")
    print("=" * 78)
    n_ok = 0
    for nom, bon, detail in checks:
        print(f"  [{'OK ' if bon else 'ÉCHEC'}] {nom}")
        if detail and not bon:
            print(f"          {detail}")
        n_ok += bon
    print()
    print(f"== {n_ok}/{len(checks)} ==")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(run())
