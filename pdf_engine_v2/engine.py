"""
pdf_engine_v2 — Moteur PDF minimaliste et « from scratch ».

Une seule responsabilité, en deux temps :

  1. EXTRACTION  : lit chaque page et sérialise CHAQUE objet détectable
                   (texte, image, dessin vectoriel) sous forme de JSON,
                   dans l'ordre de rendu, sans AUCUNE fusion ni détection
                   de paragraphe. Tout est basique : un span = un objet,
                   un tracé = un objet, une image = un objet.

  2. RÉINJECTION : reconstruit chaque page sur une feuille VIERGE (même
                   dimensions) en redessinant chaque objet exactement à sa
                   position d'origine, avec sa mise en forme d'origine, puis
                   trace une BORDURE autour de chaque objet.

Aucune dépendance au moteur historique (backend/pdf_translator_engine.py).
Seul PyMuPDF (fitz) est requis.
"""

import os
import io
import re
import json
import math
import base64
from pathlib import Path
from collections import defaultdict

import fitz  # PyMuPDF >= 1.23

from . import reflow

# Ligne commençant par une puce ou un numéro d'item de liste.
_LIST_RE = re.compile(
    r'^\s*([•◦▪‣·●○∙\-–—*]\s+|\(?\d{1,3}[.)]\s+|\(?[a-zA-Z][.)]\s+)')

# Conjonctions de coordination : une ligne qui commence par l'une d'elles
# CONTINUE le paragraphe précédent même après un point (pas de coupe).
_COORD_CONJ = {
    "But", "And", "So", "Yet", "Or", "Nor", "For", "However", "Because",
    "Although", "Though", "While", "Thus", "Therefore", "Also", "Then",
    "Still", "Besides", "Moreover", "Furthermore", "Hence",
}


# ── Couleurs des bordures de debug par type d'objet ─────────────────────────
BORDER_COLORS = {
    "paragraph": (0.00, 0.55, 0.00),   # vert
    "text_line": (0.00, 0.55, 0.00),   # vert
    "image":     (1.00, 0.00, 0.00),   # rouge
    "drawing":   (0.00, 0.30, 1.00),   # bleu
}
BORDER_WIDTH = 0.6

# Cadre du CONTENEUR élargi d'un paragraphe (Étape D : expansion vers la
# droite). Orange pointillé, pour le distinguer du contour de texte (vert).
EXPAND_COLOR = (1.00, 0.50, 0.00)
EXPAND_WIDTH = 0.8


# ════════════════════════════════════════════════════════════════════════════
# Helpers de sérialisation (fitz -> JSON natif)
# ════════════════════════════════════════════════════════════════════════════
def _pt(p):
    """fitz.Point / (x, y) -> [x, y]."""
    if p is None:
        return None
    if hasattr(p, "x"):
        return [p.x, p.y]
    return [p[0], p[1]]


def _rect(r):
    """fitz.Rect / (x0, y0, x1, y1) -> [x0, y0, x1, y1]."""
    if r is None:
        return None
    if hasattr(r, "x0"):
        return [r.x0, r.y0, r.x1, r.y1]
    return [r[0], r[1], r[2], r[3]]


def _color(c):
    """Couleur fitz (tuple de floats) -> liste de floats, ou None."""
    if c is None:
        return None
    return [float(v) for v in c]


def _serialize_drawing_item(item):
    """Sérialise un item de tracé get_drawings() en structure JSON.

    Formes possibles (PyMuPDF) :
      ('l',  p1, p2)              segment
      ('c',  p1, p2, p3, p4)      courbe de Bézier
      ('re', rect, orientation)   rectangle
      ('qu', quad)                quadrilatère
    """
    op = item[0]
    if op == "l":
        return {"op": "l", "p1": _pt(item[1]), "p2": _pt(item[2])}
    if op == "c":
        return {"op": "c", "p1": _pt(item[1]), "p2": _pt(item[2]),
                "p3": _pt(item[3]), "p4": _pt(item[4])}
    if op == "re":
        d = {"op": "re", "rect": _rect(item[1])}
        if len(item) > 2:
            d["orientation"] = item[2]
        return d
    if op == "qu":
        q = item[1]
        # Quad -> 4 points
        return {"op": "qu", "quad": [_pt(q.ul), _pt(q.ur), _pt(q.lr), _pt(q.ll)]}
    # Type inconnu : on garde une trace brute (ignoré à la réinjection).
    return {"op": op, "raw": str(item)}


def _serialize_drawing(d):
    """Sérialise un dessin vectoriel complet (une entrée get_drawings())."""
    return {
        "type": "drawing",
        "draw_type": d.get("type"),                 # 's', 'f', 'fs', 'clip', 'group'
        "bbox": _rect(d.get("rect")),
        "items": [_serialize_drawing_item(it) for it in d.get("items", [])],
        "stroke_color": _color(d.get("color")),
        "fill_color": _color(d.get("fill")),
        "width": d.get("width"),
        "dashes": d.get("dashes"),
        "close_path": d.get("closePath"),
        "even_odd": d.get("even_odd"),
        "line_cap": d.get("lineCap"),
        "line_join": d.get("lineJoin"),
        "stroke_opacity": d.get("stroke_opacity"),
        "fill_opacity": d.get("fill_opacity"),
        "seqno": d.get("seqno"),
    }


# ════════════════════════════════════════════════════════════════════════════
# Moteur
# ════════════════════════════════════════════════════════════════════════════
class PDFObjectEngine:
    """Extraction/réinjection objet par objet, sans fusion ni interprétation."""

    # ─────────────────────────────────────────────────────────────────────────
    # 1. EXTRACTION
    # ─────────────────────────────────────────────────────────────────────────
    def extract(self, pdf_path, output_json=None, embed_images=True):
        """Extrait tous les objets de chaque page vers un JSON.

        Args:
            pdf_path:    chemin du PDF source.
            output_json: chemin du JSON de sortie (défaut : <pdf>_objects.json).
            embed_images: True = octets d'image encodés en base64 DANS le JSON
                          (fichier autonome). False = images écrites dans un
                          dossier <json>_assets/ et référencées par nom.

        Returns:
            (data:dict, output_json:str)
        """
        pdf_path = str(pdf_path)
        if output_json is None:
            output_json = str(Path(pdf_path).with_suffix("")) + "_objects.json"

        assets_dir = None
        if not embed_images:
            assets_dir = str(Path(output_json).with_suffix("")) + "_assets"
            os.makedirs(assets_dir, exist_ok=True)

        data = {
            "source": os.path.basename(pdf_path),
            "embed_images": embed_images,
            "fonts": {},
            "pages": [],
        }

        doc = fitz.open(pdf_path)
        try:
            # Polices embarquées du PDF source (pour un rendu fidèle des glyphes
            # et de la vraie police à la réinjection). Encodées en base64 dans
            # le JSON → fichier autonome.
            data["fonts"] = self._extract_fonts(doc)
            for page_num, page in enumerate(doc):
                page_data = {
                    "page_num": page_num + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "elements": [],
                }
                # Ordre de peinture (du fond vers l'avant), pour que les
                # objets se recouvrent comme dans l'original : dessins
                # vectoriels / fonds d'abord, puis images, puis texte au-dessus.
                draw_els = self._extract_drawings(page)
                img_els = self._extract_images(
                    doc, page, page_num, embed_images, assets_dir)
                page_data["elements"].extend(draw_els)
                page_data["elements"].extend(img_els)
                text_lines = self._extract_text(page)
                if self.group_paragraphs:
                    ctx = self._build_page_ctx(page, text_lines,
                                               draw_els, img_els)
                    page_data["elements"].extend(
                        self._group_paragraphs(text_lines, ctx))
                else:
                    page_data["elements"].extend(text_lines)
                data["pages"].append(page_data)
        finally:
            doc.close()

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data, output_json

    # ── Polices embarquées : nom propre -> liste de sous-ensembles (b64) ─────
    def _extract_fonts(self, doc):
        """Collecte les octets de chaque police embarquée du PDF.

        Une même police (ex. 'PTSerif-Regular') peut être embarquée en
        PLUSIEURS sous-ensembles (un par xref, chacun couvrant un jeu de
        glyphes partiel). On les garde TOUS : à la réinjection, on choisira
        pour chaque texte le sous-ensemble qui couvre réellement ses glyphes.
        Clé = nom SANS préfixe de sous-ensemble ('ABCDEF+') pour matcher le
        champ 'font' des spans.
        """
        # 1) Mapping Unicode -> glyph-id PAR XREF (sous-ensemble). Les polices
        #    CID/Type0 (Identity-H) sont embarquées sans cmap Unicode : on la
        #    reconstruit à partir de get_texttrace() qui expose, pour chaque
        #    caractère, son code Unicode ET son glyph-id dans le sous-ensemble.
        u2g_by_xref = defaultdict(dict)     # xref -> {unicode: gid}
        name_xrefs = defaultdict(set)       # nom propre -> {xref, ...}
        name_ext = {}                       # xref -> ext
        for pno in range(len(doc)):
            page = doc[pno]
            page_name2xref = defaultdict(list)   # nom propre -> [xref] (cette page)
            try:
                for entry in doc.get_page_fonts(pno):
                    xref, ext, _ftype, basefont = entry[0], entry[1], entry[2], entry[3]
                    if ext == "n/a":
                        continue
                    clean = basefont.split("+")[-1] if "+" in basefont else basefont
                    page_name2xref[clean].append(xref)
                    name_xrefs[clean].add(xref)
                    name_ext[xref] = ext
            except Exception:
                pass
            try:
                trace = page.get_texttrace()
            except Exception:
                trace = []
            for span in trace:
                nm = span.get("font", "")
                nm = nm.split("+")[-1] if "+" in nm else nm
                xrefs = page_name2xref.get(nm)
                if not xrefs:
                    continue
                for ch in span.get("chars", []):
                    u, g = ch[0], ch[1]
                    for xr in xrefs:     # ambiguïté (rare) : on renseigne tous
                        u2g_by_xref[xr][u] = g

        # 2) Extraction des octets de chaque sous-ensemble + patch de cmap si
        #    nécessaire. On garde TOUS les sous-ensembles d'un même nom : à la
        #    réinjection, on choisira celui qui couvre les glyphes du texte.
        fonts = {}
        for clean, xrefs in name_xrefs.items():
            for xr in sorted(xrefs):
                try:
                    buf = doc.extract_font(xr)[3]
                except Exception:
                    buf = None
                if not buf:
                    continue
                buf = self._maybe_patch_cmap(buf, u2g_by_xref.get(xr))
                fonts.setdefault(clean, []).append({
                    "ext": name_ext.get(xr, "ttf"),
                    "b64": base64.b64encode(buf).decode("ascii"),
                })
        return fonts

    @staticmethod
    def _maybe_patch_cmap(buf, u2g):
        """Ajoute une cmap Unicode au sous-ensemble s'il n'en a pas (police
        CID/Identity-H). Sans effet si la police a déjà une cmap utilisable ou
        si aucun mapping n'est disponible."""
        # Police avec cmap Unicode déjà utilisable → inchangée.
        try:
            if len(fitz.Font(fontbuffer=buf).valid_codepoints()) > 0:
                return buf
        except Exception:
            pass
        if not u2g:
            return buf
        try:
            from fontTools.ttLib import TTFont, newTable
            from fontTools.ttLib.tables._c_m_a_p import cmap_format_4
            ft = TTFont(io.BytesIO(buf))
            order = ft.getGlyphOrder()
            bmp = {u: order[g] for u, g in u2g.items()
                   if u <= 0xFFFF and 0 <= g < len(order)}
            if not bmp:
                return buf
            sub = cmap_format_4(4)
            sub.platformID, sub.platEncID, sub.language = 3, 1, 0
            sub.cmap = bmp
            cmap = newTable("cmap")
            cmap.tableVersion = 0
            cmap.tables = [sub]
            ft["cmap"] = cmap
            out = io.BytesIO()
            ft.save(out)
            return out.getvalue()
        except Exception:
            return buf

    # ── Texte : détection de LIGNES VISUELLES (façon sélection PDF) ───────────
    # Chaque span est d'abord capté tel quel (rendu fidèle : sa position, sa
    # police, son style), puis les spans sont regroupés en LIGNES par analyse
    # de disposition — sans OCR, sans détection de paragraphe :
    #   1. regroupement par ligne de base (clustering vertical) ;
    #   2. au sein d'une ligne, coupe aux GRANDS écarts horizontaux
    #      (séparateurs de colonne), mesurés RELATIVEMENT à la largeur de
    #      glyphe de la ligne. Un letter-spacing (~1–2× la largeur d'un glyphe)
    #      reste soudé ; un saut de colonne (≥ ~2.5×) coupe.
    # Une ligne détectée = un objet `text_line` { bbox, runs:[spans] }.
    _COL_SPLIT_FACTOR = 2.5    # écart de coupe = facteur × largeur de glyphe
    _SPACE_FACTOR     = 0.30   # écart au-delà duquel on insère une espace

    # ── Regroupement en paragraphes (étape 7) ───────────────────────────────
    group_paragraphs     = True    # False → objets = lignes (pas de paragraphes)
    para_remaining_space = True    # Étape A : coupe « espace restant » (togglable)
    expand_paragraphs    = True    # Étape D : conteneur élargi vers la droite
    detect_tables        = True    # Étape B : cloisonnement des cellules de table
    _EXPAND_GAP          = 6.0     # espace « raisonnable » laissé vers un objet/bord
    _PARA_GAP_FACTOR     = 1.8     # saut vertical > facteur × taille → coupe DURE
    _PARA_MODERATE_FACTOR = 1.35   # gap au-delà duquel l'INDENTATION peut couper
    _PARA_PUNCT_FACTOR   = 1.6     # gap au-delà duquel la PONCTUATION peut couper
    _PARA_INDENT_FACTOR  = 1.2     # indentation > facteur × taille → coupe
    _PARA_SIZE_FACTOR    = 0.20    # écart de taille relatif → coupe (titre)
    _RS_SPACE_FACTOR     = 1.0     # marge (en largeurs de glyphe) exigée en plus
                                   # du 1er mot pour parler de coupe volontaire
    _RS_WINDOW_FACTOR    = 2.5     # fenêtre verticale (× taille) pour estimer la
                                   # marge droite de COLONNE d'une ligne

    # ── Contexte de page : géométrie + BLOQUEURS (fondation partagée) ────────
    # Sert aux étapes qui raisonnent sur l'espace horizontal (règle « espace
    # restant », future expansion). Un « bloqueur » est tout objet qui empêche
    # une ligne de s'étendre vers la droite : image, dessin significatif, et
    # toute AUTRE ligne de texte (colonne voisine). Le bord droit utilisable de
    # la page est déduit de la disposition réelle (plus grande abscisse de fin
    # de texte) → aucune constante calée sur un document donné.
    def _build_page_ctx(self, page, text_lines, draw_els, img_els):
        # `obstacles` : objets non-texte (image / dessin) qui bornent DUR une
        # extension horizontale. `line_rects` : rectangles des autres lignes,
        # servant à retrouver la MARGE DROITE DE LA COLONNE d'une ligne (le bord
        # où le texte s'aligne réellement) — à ne pas confondre avec la colonne
        # voisine de l'autre côté d'une gouttière.
        obstacles = []
        for el in img_els:
            bb = el.get("bbox")
            if bb and len(bb) >= 4:
                obstacles.append((bb[0], bb[1], bb[2], bb[3]))
        for el in draw_els:
            bb = el.get("bbox")
            if bb and len(bb) >= 4 and (bb[2] - bb[0] > 0.5 or bb[3] - bb[1] > 0.5):
                obstacles.append((bb[0], bb[1], bb[2], bb[3]))
        xs = [bb[2] for ln in text_lines
              if (bb := ln.get("bbox")) and len(bb) >= 4]
        # Étape B : cellules de tableau (tables BORDÉES uniquement — stratégie
        # « lines » : faible faux-positif). Chaque cellule borne le texte qu'elle
        # contient : ajoutée aux obstacles (murs de cellule) ET conservée pour
        # taguer les lignes (empêche la fusion de paragraphes entre cellules).
        cells = []
        if self.detect_tables:
            try:
                tf = page.find_tables(vertical_strategy="lines",
                                      horizontal_strategy="lines")
                for t in (tf.tables if tf else []):
                    for c in t.cells:
                        if c and len(c) >= 4:
                            cells.append((c[0], c[1], c[2], c[3]))
            except Exception:
                pass
        obstacles.extend(cells)
        return {
            "width": page.rect.width,
            "height": page.rect.height,
            "obstacles": obstacles,
            "text_right": max(xs) if xs else page.rect.width,
            "cells": cells,
        }

    def _extract_text(self, page):
        raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        spans = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:      # 0 = texte
                continue
            for line in block.get("lines", []):
                direction = line.get("dir", (1, 0))
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    bb = span["bbox"]
                    o = span.get("origin", (bb[0], bb[3]))
                    flags = span.get("flags", 0)
                    nchar = max(1, len(text.strip()))
                    spans.append({
                        "bbox": [bb[0], bb[1], bb[2], bb[3]],
                        "origin": [o[0], o[1]],
                        "text": text,
                        "font": span.get("font"),
                        "size": span.get("size", 0) or 0,
                        "color": _int_color_to_rgb(span.get("color", 0)),
                        "flags": flags,
                        "bold": bool(flags & 16),
                        "italic": bool(flags & 2),
                        "dir": list(direction),
                        "_gw": (bb[2] - bb[0]) / nchar,   # largeur de glyphe approx.
                        "_base": o[1],
                    })
        return self._group_text_lines(spans)

    def _group_text_lines(self, spans):
        """Regroupe des spans en lignes visuelles. Le texte HORIZONTAL suit le
        clustering baseline + coupe colonne (inchangé) ; le texte INCLINÉ/VERTICAL
        (Étape C) est regroupé le long de son axe d'écriture par
        `_group_rotated_lines`."""
        if not spans:
            return []
        horiz, other = [], []
        for s in spans:
            if abs(s["dir"][1]) <= 0.01 and s["dir"][0] >= 0:
                horiz.append(s)
            else:
                other.append(s)
        elements = self._group_horizontal_lines(horiz)
        if other:
            elements.extend(self._group_rotated_lines(other))
        return elements

    def _group_horizontal_lines(self, spans):
        """Clustering baseline + coupe aux séparateurs de colonne (texte
        horizontal). Retourne une liste d'objets `text_line`."""
        if not spans:
            return []
        # 1) Lignes de base : tri par (baseline, x) puis clustering vertical.
        spans.sort(key=lambda s: (round(s["_base"], 1), s["bbox"][0]))
        rows = []
        for s in spans:
            if rows and abs(s["_base"] - rows[-1]["_base"]) <= 0.45 * max(
                    s["size"], rows[-1]["_size_ref"], 1.0):
                rows[-1]["spans"].append(s)
                rows[-1]["_base"] = s["_base"]
            else:
                rows.append({"spans": [s], "_base": s["_base"],
                             "_size_ref": s["size"]})

        # 2) Coupe de chaque ligne aux grands écarts (colonnes).
        elements = []
        for row in rows:
            row_spans = sorted(row["spans"], key=lambda s: s["bbox"][0])
            gws = sorted(s["_gw"] for s in row_spans if s["_gw"] > 0)
            med_gw = gws[len(gws) // 2] if gws else 1.0
            split_gap = self._COL_SPLIT_FACTOR * med_gw
            segment = [row_spans[0]]
            for prev, cur in zip(row_spans, row_spans[1:]):
                gap = cur["bbox"][0] - prev["bbox"][2]
                if gap > split_gap:
                    elements.append(self._make_text_line(segment, med_gw))
                    segment = [cur]
                else:
                    segment.append(cur)
            elements.append(self._make_text_line(segment, med_gw))
        return elements

    def _make_text_line(self, seg_spans, med_gw):
        """Construit un objet `text_line` depuis les spans d'un segment."""
        x0 = min(s["bbox"][0] for s in seg_spans)
        y0 = min(s["bbox"][1] for s in seg_spans)
        x1 = max(s["bbox"][2] for s in seg_spans)
        y1 = max(s["bbox"][3] for s in seg_spans)
        # Texte lisible : concatène les runs en insérant une espace là où
        # l'écart le justifie (pratique pour l'inspection / futur usage).
        parts = []
        space_gap = self._SPACE_FACTOR * med_gw
        for i, s in enumerate(seg_spans):
            if i > 0:
                gap = s["bbox"][0] - seg_spans[i - 1]["bbox"][2]
                prev_t = parts[-1] if parts else ""
                if gap > space_gap and prev_t and not prev_t.endswith(" ") \
                        and not s["text"].startswith(" "):
                    parts.append(" ")
            parts.append(s["text"])
        runs = [self._run_from_span(s) for s in seg_spans]
        return {
            "type": "text_line",
            "bbox": [x0, y0, x1, y1],
            "text": "".join(parts),
            "gw": med_gw,          # largeur de glyphe médiane (estimation de mot)
            "runs": runs,
        }

    @staticmethod
    def _run_from_span(s):
        return {
            "text": s["text"],
            "origin": s["origin"],
            "bbox": s["bbox"],
            "font": s["font"],
            "size": s["size"],
            "color": s["color"],
            "flags": s["flags"],
            "bold": s["bold"],
            "italic": s["italic"],
            "dir": s["dir"],
        }

    # ── Texte INCLINÉ / VERTICAL (Étape C) : regroupement le long de l'axe ────
    def _group_rotated_lines(self, spans):
        """Regroupe les spans non horizontaux en lignes le long de leur axe
        d'écriture. Pour chaque direction, on projette l'origine sur l'axe
        d'avancée `a = o·dir` et l'axe transverse `c = o·perp` : les spans de même
        `c` (même « ligne ») sont ordonnés par `a`. bbox axis-aligned ; le texte
        conserve son `dir` pour un rendu pivoté fidèle."""
        if not spans:
            return []
        out = []
        groups = defaultdict(list)
        for s in spans:
            dx, dy = s["dir"]
            groups[(round(dx, 2), round(dy, 2))].append(s)
        for (dx, dy), gspans in groups.items():
            def adv(s):
                return s["origin"][0] * dx + s["origin"][1] * dy

            def cross(s):
                return -s["origin"][0] * dy + s["origin"][1] * dx

            gspans.sort(key=lambda s: (round(cross(s), 1), adv(s)))
            rows = []
            for s in gspans:
                if rows and abs(cross(s) - rows[-1]["_c"]) <= 0.6 * max(
                        s["size"], 1.0):
                    rows[-1]["spans"].append(s)
                    rows[-1]["_c"] = cross(s)
                else:
                    rows.append({"spans": [s], "_c": cross(s)})
            for row in rows:
                seg = sorted(row["spans"], key=adv)
                out.append(self._make_rotated_line(seg, dx, dy))
        return out

    def _make_rotated_line(self, seg, dx, dy):
        x0 = min(s["bbox"][0] for s in seg); y0 = min(s["bbox"][1] for s in seg)
        x1 = max(s["bbox"][2] for s in seg); y1 = max(s["bbox"][3] for s in seg)
        return {
            "type": "text_line",
            "bbox": [x0, y0, x1, y1],
            "text": "".join(s["text"] for s in seg),
            "gw": 0,
            "runs": [self._run_from_span(s) for s in seg],
            "dir": [dx, dy],
        }

    # ── Regroupement en PARAGRAPHES (étape 7 : géométrie + linguistique) ─────
    def _group_paragraphs(self, lines, ctx=None):
        """Regroupe des lignes (`text_line`) en paragraphes. Column-aware :
        deux lignes ne fusionnent que si elles se chevauchent horizontalement
        (même colonne). La priorité va à la GÉOMÉTRIE (interligne) ; les signaux
        faibles (indentation, ponctuation) n'agissent qu'en cas d'écart élevé.
        Retourne des objets `paragraph` { bbox, text, lines:[...] }."""
        if not lines:
            return []
        items = [self._line_metrics(ln) for ln in lines]
        self._assign_column_margins(items, ctx)
        self._tag_cells(items, ctx)
        items.sort(key=lambda it: (round(it["top"], 1), it["left"]))

        paras = []
        for it in items:
            # Candidats parents : paragraphes ouverts dont la dernière ligne est
            # AU-DESSUS et chevauche horizontalement (même colonne).
            cands = []
            for p in paras:
                last = p["items"][-1]
                if last.get("cell") != it.get("cell"):    # cloisonnement table
                    continue
                if last["bottom"] > it["top"] + 0.5 * it["size"]:
                    continue
                ov = min(last["right"], it["right"]) - max(last["left"], it["left"])
                minw = max(1.0, min(last["right"] - last["left"],
                                    it["right"] - it["left"]))
                if ov <= 0.3 * minw:
                    continue
                cands.append(p)
            # Parent = la ligne au-dessus la PLUS PROCHE verticalement (flot de
            # lecture). Choisir « le plus aligné à gauche » cassait le texte qui
            # s'enroule autour d'une image/encart : une ligne revenue à gauche
            # était rattachée à l'encart voisin (gauche proche) au lieu du
            # paragraphe qu'elle continue, puis coupée (grand écart à l'encart).
            parent = None
            if cands:
                parent = min(cands,
                             key=lambda p: it["base"] - p["items"][-1]["base"])
            if parent is not None and not self._para_break(parent, it, ctx):
                parent["items"].append(it)
                parent["left_min"] = min(parent["left_min"], it["left"])
                parent["right_max"] = max(parent["right_max"], it["right"])
            else:
                paras.append({"items": [it], "left_min": it["left"],
                              "right_max": it["right"]})

        out = []
        for p in paras:
            its = p["items"]
            x0 = min(i["left"] for i in its); y0 = min(i["top"] for i in its)
            x1 = max(i["right"] for i in its); y1 = max(i["bottom"] for i in its)
            out.append({
                "type": "paragraph",
                "bbox": [x0, y0, x1, y1],
                "text": self._join_para_text([i["text"] for i in its]),
                "lines": [i["line"] for i in its],
            })
        out.sort(key=lambda e: (round(e["bbox"][1], 1), e["bbox"][0]))
        if self.expand_paragraphs and ctx is not None:
            self._expand_paragraphs(out, ctx)
        return out

    # ── Étape D : expansion du CONTENEUR vers la droite ──────────────────────
    def _expand_paragraphs(self, paras, ctx):
        """Calcule la zone utilisable élargie **vers la droite uniquement**
        (bord gauche de chaque ligne figé), pour absorber des traductions plus
        longues. Expansion LIGNE PAR LIGNE (`container_lines`), car un paragraphe
        peut s'enrouler autour d'un encart : le conteneur est alors un contour en
        escalier (un L) qui contourne l'objet, pas un rectangle qui le chevauche.

        Règle UNIQUE, appliquée à chaque ligne : on étend la ligne **seulement
        jusqu'à la plus grande ligne du paragraphe** (`right_max`) — ce qui
        aligne toutes les fins de ligne sur la ligne la plus longue (« équilibre
        vers la fin la plus éloignée »). JAMAIS jusqu'à la marge de page : une
        colonne reste donc dans sa largeur, sans déborder sur le bloc de droite.
        On n'étend que si `right_max` est atteignable en gardant l'espace de
        sécurité vis-à-vis du 1er objet/colonne à droite (sinon on laisse la
        ligne telle quelle — cas de l'enroulement autour d'un encart).

        Ne modifie jamais le texte ni sa position : seul le cadre conteneur
        change (visible à la réinjection en orange pointillé)."""
        obstacles = ctx.get("obstacles", ())
        boxed = [p for p in paras if p.get("bbox") and len(p["bbox"]) >= 4]

        for p in boxed:
            pleft, ptop, right_max, pbottom = p["bbox"]
            clines = []
            for ln in p.get("lines", []):
                bb = ln.get("bbox")
                if not bb or len(bb) < 4:
                    continue
                lx0, lty, lx1, lby = bb
                # 1er objet à droite de CETTE ligne (autre paragraphe OU objet
                # non-texte), dans SA bande verticale.
                obj = float("inf")
                for q in boxed:
                    if q is p:
                        continue
                    qb = q["bbox"]
                    if qb[3] <= lty or qb[1] >= lby:
                        continue
                    if lx1 < qb[0] < obj:
                        obj = qb[0]
                for ox0, oy0, ox1, oy1 in obstacles:
                    if oy1 <= lty or oy0 >= lby:
                        continue
                    if lx1 < ox0 < obj:
                        obj = ox0

                # Extension jusqu'à la plus grande ligne, uniquement si on peut
                # l'atteindre en gardant l'espace de sécurité ; sinon inchangée.
                if obj - self._EXPAND_GAP < right_max:
                    tgt = lx1
                else:
                    tgt = right_max
                tgt = max(tgt, lx1)          # jamais vers la gauche / rétrécir
                clines.append([lx0, lty, tgt, lby])

            if clines:
                p["container_lines"] = clines
                p["container_bbox"] = [pleft, ptop,
                                       max(c[2] for c in clines), pbottom]

    @staticmethod
    def _line_metrics(ln):
        bb = ln["bbox"]
        runs = ln.get("runs", [])
        sizes = [r.get("size", 0) or 0 for r in runs]
        size = max(sizes) if sizes else 0
        base = max((r["origin"][1] for r in runs
                    if r.get("origin")), default=bb[3])
        total = sum(len(r.get("text", "")) for r in runs) or 1
        bold_chars = sum(len(r.get("text", "")) for r in runs if r.get("bold"))
        return {
            "line": ln, "text": ln.get("text", ""),
            "left": bb[0], "right": bb[2], "top": bb[1], "bottom": bb[3],
            "base": base, "size": size or 1.0,
            "gw": ln.get("gw") or ((size or 1.0) * 0.5),
            "bold": (bold_chars / total) >= 0.6,
        }

    def _para_break(self, parent, it, ctx=None):
        """True si `it` doit démarrer un NOUVEAU paragraphe (coupe).

        Hiérarchie stricte (la géométrie prime, cf. cas texte enroulé) :
          1. signaux DURS : liste, changement de style, gros saut vertical ;
          2. continuation certaine (minuscule) → fusion, prioritaire sur A ;
          3. règle « espace restant » (Étape A, togglable) : si le 1er mot de la
             ligne suivante AURAIT PU tenir dans l'espace libre à droite de la
             ligne précédente (jusqu'au 1er bloqueur : marge, colonne, image,
             dessin), c'est un retour à la ligne VOLONTAIRE → coupe ;
          4. flot continu : sous le seuil « modéré », on FUSIONNE toujours —
             peu importe x0 (enroulement) ou une ponctuation faible ;
          5. zone modérée : indentation d'alinéa, puis (gap plus élevé)
             ponctuation forte + majuscule — sauf conjonction / minuscule.
        """
        last = parent["items"][-1]
        size_ref = max(last["size"], it["size"], 1.0)
        g = (it["base"] - last["base"]) / size_ref

        # ── 1. Signaux DURS ─────────────────────────────────────────────────
        if _LIST_RE.match(it["text"]):                 # puce / numéro
            return True
        if last["bold"] != it["bold"]:                 # titre gras vs corps
            return True
        if abs(last["size"] - it["size"]) > self._PARA_SIZE_FACTOR * size_ref:
            return True                                # changement de taille
        if g > self._PARA_GAP_FACTOR:                  # gros saut vertical
            return True

        # Ligne suivante en minuscule → continuation certaine → fusion.
        # (Prioritaire : un mot en minuscule n'ouvre quasi jamais un paragraphe,
        # même si l'espace restant aurait pu l'accueillir.)
        lower_next = _starts_lower(it["text"])

        # ── A. Coupe « espace restant » (tie-breaker géométrique, togglable) ─
        # Appliquée AVANT le flot continu : elle discrimine un vrai saut de
        # paragraphe d'un simple retour à la ligne, y compris à interligne
        # normal. En texte justifié/ferré, le mot suivant ne rentre jamais dans
        # le reliquat (c'est pourquoi il a wrappé) → fusion ; seul un mot qui
        # « aurait pu tenir » trahit une coupe voulue.
        if (self.para_remaining_space and ctx is not None and not lower_next
                and self._remaining_space_break(parent, it, ctx)):
            return True

        # ── 2. Flot continu : interligne normal → FUSION obligatoire ────────
        # (x0 ignoré : c'est ce qui permet au texte de s'enrouler autour d'une
        # image / d'un encart sans être scindé.)
        if g < self._PARA_MODERATE_FACTOR:
            return False
        if lower_next:
            return False

        # ── 3. Zone modérée : signaux faibles ───────────────────────────────
        # Indentation d'alinéa — mais pas un bloc CENTRÉ. On distingue les deux
        # par l'AXE CENTRAL : un alinéa décale la ligne vers la droite (centre
        # déplacé) ; un bloc centré garde le même axe central que la ligne
        # précédente. Comparer au bord droit du titre précédent était instable
        # (les titres ont des longueurs variables → coupe incohérente).
        left_shift = it["left"] - parent["left_min"]
        indent = self._PARA_INDENT_FACTOR * size_ref
        if left_shift > indent:
            c_it = (it["left"] + it["right"]) / 2.0
            c_last = (last["left"] + last["right"]) / 2.0
            if abs(c_it - c_last) > 0.5 * size_ref:
                return True
        # Ponctuation forte + majuscule, uniquement si l'interligne est déjà
        # nettement élevé, et hors conjonction de coordination.
        if (g > self._PARA_PUNCT_FACTOR and _ends_sentence(last["text"])
                and _starts_capital(it["text"])
                and _first_word(it["text"]) not in _COORD_CONJ):
            return True
        return False

    @staticmethod
    def _tag_cells(items, ctx=None):
        """Étape B : tague chaque ligne avec l'indice de la cellule de tableau
        qui contient son centre (`cell`), ou None hors tableau. Deux lignes de
        cellules différentes ne fusionneront jamais en un même paragraphe."""
        cells = (ctx or {}).get("cells", ())
        for it in items:
            it["cell"] = None
            if not cells:
                continue
            cx = 0.5 * (it["left"] + it["right"])
            cy = 0.5 * (it["top"] + it["bottom"])
            for i, (x0, y0, x1, y1) in enumerate(cells):
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    it["cell"] = i
                    break

    def _assign_column_margins(self, items, ctx=None):
        """Attribue à chaque ligne sa `col_margin` = bord droit de référence pour
        juger un retour à la ligne volontaire, selon la nature de sa colonne :

          • Colonne JUSTIFIÉE (≥ 2 lignes proches atteignent le MÊME bord droit
            max) → `col_margin` = ce bord. Les lignes internes l'atteignent → le
            mot suivant n'y rentre pas → pas de fausse coupe (texte qui coule).
          • Sinon (bords droits DISPERSÉS = sommaire / liste / titres) →
            `col_margin` = ESPACE OUVERT à droite (1er obstacle non-texte ou
            colonne de texte voisine, sinon bord droit du texte de la page). Une
            entrée courte y laisse largement la place au mot suivant → coupe du
            retour volontaire.

        Les voisines sont prises dans une fenêtre verticale (`_RS_WINDOW_FACTOR ×
        taille`) et doivent chevaucher horizontalement la ligne (même colonne) :
        la fenêtre isole la colonne d'un autre bloc pleine largeur séparé
        verticalement mais de même marge gauche."""
        page_w = (ctx or {}).get("width")
        obstacles = (ctx or {}).get("obstacles", ())
        for it in items:
            cy = 0.5 * (it["top"] + it["bottom"])
            win = self._RS_WINDOW_FACTOR * it["size"]
            left, right = it["left"], it["right"]
            # Voisines de colonne (chevauchement horizontal + proximité verticale).
            neigh = [it["right"]]
            for jt in items:
                if jt is it:
                    continue
                if jt["right"] <= left or jt["left"] >= right:
                    continue
                if abs(0.5 * (jt["top"] + jt["bottom"]) - cy) > win:
                    continue
                neigh.append(jt["right"])
            max_x1 = max(neigh)
            tol = 0.5 * it["size"]
            at_max = sum(1 for x in neigh if max_x1 - x <= tol)
            if page_w is None:
                it["col_margin"] = max_x1
                continue
            # Espace OUVERT à droite (jusqu'au 1er obstacle/colonne, sinon bord de
            # page) et largeur de contenu de la ligne.
            openr = self._open_right(it, items, page_w, obstacles)
            content_w = right - left
            remaining_open = openr - right
            # « Texte qui coule » (à protéger) = plusieurs lignes alignées au même
            # bord droit ET ligne dont le CONTENU est plus large que l'espace
            # restant (ce reliquat n'est qu'une gouttière). Sinon = item court
            # dans un espace ouvert (sommaire, liste, numéros) → référence =
            # espace ouvert, pour couper le retour à la ligne volontaire.
            if at_max >= 2 and content_w >= remaining_open:
                it["col_margin"] = max_x1
            else:
                it["col_margin"] = openr

    @staticmethod
    def _open_right(it, items, page_w, obstacles):
        """Bord droit UTILISABLE à droite d'une ligne : 1er obstacle non-texte ou
        1re ligne d'une AUTRE colonne à droite dans sa bande ; sinon bord droit
        de la PAGE (une colonne seule a donc bien tout l'espace ouvert à sa
        droite, et non son propre bord)."""
        top, bottom, right = it["top"], it["bottom"], it["right"]
        bound = page_w
        for jt in items:
            if jt is it:
                continue
            if jt["left"] <= right:                      # pas à droite
                continue
            if jt["bottom"] <= top or jt["top"] >= bottom:
                continue
            if jt["left"] < bound:
                bound = jt["left"]
        for ox0, oy0, ox1, oy1 in obstacles:
            if ox0 <= right:
                continue
            if oy1 <= top or oy0 >= bottom:
                continue
            if ox0 < bound:
                bound = ox0
        return bound

    def _remaining_space_break(self, parent, it, ctx):
        """Vrai si le PREMIER MOT de `it` aurait tenu dans l'espace libre à
        droite de la dernière ligne du paragraphe → retour à la ligne volontaire.

        Espace libre = (marge droite de la COLONNE) − (fin de la dernière ligne).
        La marge de colonne (`col_margin`) est le bord droit où le texte de la
        colonne s'aligne réellement, estimé à partir des lignes verticalement
        proches qui chevauchent horizontalement la ligne (cf.
        `_assign_column_margins`). Elle vaut la marge d'une colonne justifiée
        (→ pas de fausse coupe : le mot suivant n'y rentre pas) tout en restant
        bien à droite pour un sommaire/liste (→ coupe des retours volontaires).
        Plafonnée par le 1er obstacle non-texte (image/dessin) intercalé."""
        last = parent["items"][-1]
        col_right = self._cap_by_obstacles(last.get("col_margin", last["right"]),
                                           last, ctx)
        remaining = col_right - last["right"]
        if remaining <= 0:
            return False
        word = _first_word(it["text"])
        if not word:
            return False
        gw = it.get("gw") or (it["size"] * 0.5)
        if gw <= 0:
            return False
        # Largeur estimée du 1er mot + une espace de séparation ; on exige une
        # petite marge (_RS_SPACE_FACTOR) pour éviter les faux positifs quand le
        # mot tient tout juste (cas limite d'un wrap serré).
        needed = (len(word) + self._RS_SPACE_FACTOR) * gw
        return remaining >= needed

    @staticmethod
    def _cap_by_obstacles(col_right, m, ctx):
        """Réduit la marge droite `col_right` au 1er obstacle non-texte
        (image/dessin) intercalé à droite de la ligne `m`, dans sa bande
        verticale."""
        top, bottom, right = m["top"], m["bottom"], m["right"]
        bound = col_right
        for bx0, by0, bx1, by1 in ctx.get("obstacles", ()):
            if bx0 <= right:
                continue
            if by1 <= top or by0 >= bottom:
                continue
            if bx0 < bound:
                bound = bx0
        return bound

    @staticmethod
    def _join_para_text(texts):
        """Concatène les lignes d'un paragraphe (étape 8) : dé-césure des mots
        coupés en fin de ligne, insertion d'espaces, écrasement des doublons."""
        res = ""
        for i, t in enumerate(texts):
            t = t.strip()
            if not t:
                continue
            if not res:
                res = t
                continue
            # Césure : « trans-\nport » → « transport » (mot suivant en minuscule).
            if (res.endswith("-") and len(res) >= 2 and res[-2].isalpha()
                    and t[:1].islower()):
                res = res[:-1] + t
            else:
                res = res + " " + t
        return re.sub(r"\s{2,}", " ", res)

    # ── Images : une occurrence = un objet ───────────────────────────────────
    def _extract_images(self, doc, page, page_num, embed_images, assets_dir):
        elements = []
        try:
            infos = page.get_images(full=True)
        except Exception:
            infos = []
        for img_index, info in enumerate(infos):
            xref = info[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            if not rects:
                continue
            # Octets de l'image (extraits une fois par xref). Si l'image a un
            # masque de transparence (SMask), on la compose avec son alpha en
            # PNG — sinon les zones transparentes deviennent noires à la
            # réinjection (insert_image ne connaît pas le masque séparé).
            img_bytes, ext = None, "png"
            try:
                extracted = doc.extract_image(xref)
                smask_xref = extracted.get("smask", 0)
                if smask_xref:
                    base = fitz.Pixmap(doc, xref)
                    if base.alpha:
                        base = fitz.Pixmap(base, 0)          # retire alpha existant
                    if base.colorspace and base.colorspace.n > 3:
                        base = fitz.Pixmap(fitz.csRGB, base)  # CMYK -> RGB
                    mask = fitz.Pixmap(doc, smask_xref)
                    pix = fitz.Pixmap(base, mask)             # applique l'alpha
                    img_bytes = pix.tobytes("png")
                    ext = "png"
                else:
                    img_bytes = extracted["image"]
                    ext = extracted.get("ext", "png")
            except Exception:
                # Repli : pixmap composite direct.
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.colorspace and pix.colorspace.n > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_bytes = pix.tobytes("png")
                    ext = "png"
                except Exception:
                    img_bytes, ext = None, "png"

            asset_ref = None
            asset_b64 = None
            if img_bytes is not None:
                if embed_images:
                    asset_b64 = base64.b64encode(img_bytes).decode("ascii")
                else:
                    fname = f"p{page_num + 1}_img{xref}.{ext}"
                    with open(os.path.join(assets_dir, fname), "wb") as fh:
                        fh.write(img_bytes)
                    asset_ref = fname

            for rect in rects:
                elements.append({
                    "type": "image",
                    "bbox": _rect(rect),
                    "xref": xref,
                    "ext": ext,
                    "asset_file": asset_ref,   # si embed_images=False
                    "asset_b64": asset_b64,    # si embed_images=True
                })
        return elements

    # ── Dessins vectoriels : un tracé = un objet ─────────────────────────────
    def _extract_drawings(self, page):
        elements = []
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        for d in drawings:
            elements.append(_serialize_drawing(d))
        return elements

    # ─────────────────────────────────────────────────────────────────────────
    # 2. RÉINJECTION (reconstruction sur page vierge + bordures)
    # ─────────────────────────────────────────────────────────────────────────
    reflow_lang = "fr_FR"          # langue de césure pour le rendu traduit

    def reinject(self, data_or_json, output_pdf, draw_borders=True,
                 assets_dir=None, translated=False):
        """Reconstruit un PDF depuis le JSON d'extraction.

        Chaque objet est redessiné à sa position d'origine sur une page
        vierge de mêmes dimensions ; une bordure est tracée autour de chaque
        objet si draw_borders=True.

        Args:
            data_or_json: dict d'extraction, ou chemin vers le JSON.
            output_pdf:   chemin du PDF de sortie.
            draw_borders: trace un cadre autour de chaque objet.
            assets_dir:   dossier des images (si extraction embed_images=False).
                          Déduit du chemin JSON si non fourni.
        """
        if isinstance(data_or_json, (str, os.PathLike)):
            json_path = str(data_or_json)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if assets_dir is None:
                assets_dir = str(Path(json_path).with_suffix("")) + "_assets"
        else:
            data = data_or_json

        # Reconstruit les objets fitz.Font depuis les polices embarquées du JSON.
        self._build_fonts(data)

        doc = fitz.open()
        try:
            for page_data in data.get("pages", []):
                page = doc.new_page(width=page_data["width"],
                                    height=page_data["height"])
                for el in page_data.get("elements", []):
                    kind = el.get("type")
                    try:
                        if kind == "image":
                            self._draw_image(page, el, assets_dir)
                        elif kind == "drawing":
                            self._draw_drawing(page, el)
                        elif kind == "paragraph":
                            if translated and el.get("tr_tagged") is not None:
                                self._draw_paragraph_translated(page, el)
                            else:
                                self._draw_paragraph(page, el)
                        elif kind == "text_line":
                            self._draw_text_line(page, el)
                    except Exception:
                        # Un objet fautif ne doit pas casser toute la page.
                        pass
                # Bordures en dernier : toujours visibles, jamais recouvertes.
                if draw_borders:
                    self._draw_borders(page, page_data.get("elements", []))
            doc.save(output_pdf, garbage=4, deflate=True, clean=True)
        finally:
            doc.close()
        return output_pdf

    # ── Polices : b64 -> objets fitz.Font (regroupés par nom propre) ─────────
    def _build_fonts(self, data):
        self._fonts = {}   # clean -> [fitz.Font, ...]
        for clean, variants in data.get("fonts", {}).items():
            objs = []
            for v in variants:
                try:
                    buf = base64.b64decode(v["b64"])
                    objs.append(fitz.Font(fontbuffer=buf))
                except Exception:
                    pass
            if objs:
                self._fonts[clean] = objs

    def _pick_font(self, font_raw, text):
        """Choisit le sous-ensemble embarqué qui couvre les glyphes du texte."""
        fonts = getattr(self, "_fonts", {})
        clean = font_raw.split("+")[-1] if "+" in (font_raw or "") else (font_raw or "")
        variants = fonts.get(clean)
        if not variants:
            return None
        chars = [c for c in text if not c.isspace()]
        for f in variants:
            try:
                if all(f.has_glyph(ord(c)) for c in chars):
                    return f
            except Exception:
                continue
        return variants[0]   # meilleur effort : couverture partielle

    # ── Rendu image ──────────────────────────────────────────────────────────
    def _draw_image(self, page, el, assets_dir):
        rect = fitz.Rect(el["bbox"])
        if rect.is_empty or rect.is_infinite:
            return
        stream = None
        if el.get("asset_b64"):
            stream = base64.b64decode(el["asset_b64"])
        elif el.get("asset_file") and assets_dir:
            path = os.path.join(assets_dir, el["asset_file"])
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    stream = fh.read()
        if stream is None:
            return
        page.insert_image(rect, stream=stream)

    # ── Rendu dessin vectoriel ───────────────────────────────────────────────
    def _draw_drawing(self, page, el):
        draw_type = el.get("draw_type")
        if draw_type in ("clip", "group"):
            return   # basique : on ignore les clips/groupes
        shape = page.new_shape()
        drew = False
        for it in el.get("items", []):
            op = it.get("op")
            try:
                if op == "l":
                    shape.draw_line(fitz.Point(it["p1"]), fitz.Point(it["p2"]))
                    drew = True
                elif op == "c":
                    shape.draw_bezier(fitz.Point(it["p1"]), fitz.Point(it["p2"]),
                                      fitz.Point(it["p3"]), fitz.Point(it["p4"]))
                    drew = True
                elif op == "re":
                    shape.draw_rect(fitz.Rect(it["rect"]))
                    drew = True
                elif op == "qu":
                    pts = it["quad"]
                    quad = fitz.Quad(fitz.Point(pts[0]), fitz.Point(pts[1]),
                                     fitz.Point(pts[2]), fitz.Point(pts[3]))
                    shape.draw_quad(quad)
                    drew = True
            except Exception:
                pass
        if not drew:
            return

        # draw_type : 's'=trait, 'f'=remplissage, 'fs'=les deux.
        stroke = el.get("stroke_color")
        fill = el.get("fill_color")
        if draw_type == "f":
            stroke = None
        elif draw_type == "s":
            fill = None

        finish_kwargs = {
            "color": tuple(stroke) if stroke else None,
            "fill": tuple(fill) if fill else None,
            "width": el.get("width") or 1.0,
            "closePath": bool(el.get("close_path")),
        }
        if el.get("even_odd") is not None:
            finish_kwargs["even_odd"] = bool(el.get("even_odd"))
        if el.get("dashes"):
            finish_kwargs["dashes"] = el.get("dashes")
        if el.get("line_cap") is not None:
            lc = el["line_cap"]
            finish_kwargs["lineCap"] = max(lc) if isinstance(lc, (list, tuple)) else lc
        if el.get("line_join") is not None:
            finish_kwargs["lineJoin"] = el["line_join"]
        if el.get("stroke_opacity") is not None:
            finish_kwargs["stroke_opacity"] = el["stroke_opacity"]
        if el.get("fill_opacity") is not None:
            finish_kwargs["fill_opacity"] = el["fill_opacity"]

        try:
            shape.finish(**finish_kwargs)
        except Exception:
            # Repli minimal si un paramètre n'est pas accepté par cette version.
            shape.finish(color=finish_kwargs["color"], fill=finish_kwargs["fill"],
                         width=finish_kwargs["width"])
        shape.commit()

    # ── Rendu texte : paragraphe = lignes, ligne = runs (positions exactes) ──
    def _draw_paragraph(self, page, el):
        for line in el.get("lines", []):
            self._draw_text_line(page, line)

    # ── Rendu TRADUIT : coulée du texte traduit dans le conteneur (reflow) ────
    def _draw_paragraph_translated(self, page, el):
        """Peint la version traduite d'un paragraphe : les segments traduits
        (balises `[[n]]` + styles `tr_segments`) sont coulés dans le polygone
        `container_lines` par `reflow`, puis peints. Replis : texte incliné /
        vertical ou parsing vide → rendu original run-par-run (inchangé)."""
        lines = el.get("lines", [])
        horiz = all(_is_horizontal(r) for ln in lines
                    for r in ln.get("runs", []))
        if not horiz:
            self._draw_paragraph(page, el)     # incliné/vertical : pas de reflow
            return
        segs = self._parse_translated_segments(el)
        if not segs:
            self._draw_paragraph(page, el)     # rien de traduit : repli
            return
        clines = el.get("container_lines")
        if not clines:
            cbb = el.get("container_bbox") or el.get("bbox")
            clines = [cbb] if cbb else None
        if not clines:
            return
        res = reflow.reflow_paragraph(segs, clines, lang=self.reflow_lang)
        self._paint_reflow(page, res)

    def _parse_translated_segments(self, el):
        """Reconstruit les segments {text, font, size, color} depuis le texte
        traduit balisé (`tr_tagged`) et la table de styles (`tr_segments`)."""
        tagged = el.get("tr_tagged") or ""
        meta = el.get("tr_segments") or []
        segs = []
        for idx, txt in re.findall(r"\[\[(\d+)\]\](.*?)\[\[/\1\]\]",
                                   tagged, re.DOTALL):
            if not txt:
                continue
            i = int(idx)
            m = meta[i] if 0 <= i < len(meta) else (meta[-1] if meta else {})
            segs.append(self._seg_from_meta(m, txt))
        if not segs and tagged.strip():
            # Traduction renvoyée SANS balises → un seul segment, style dominant.
            clean = re.sub(r"\[\[/?\d+\]\]", "", tagged).strip()
            if clean:
                segs.append(self._seg_from_meta(meta[0] if meta else {}, clean))
        return segs

    def _seg_from_meta(self, m, txt):
        """Segment de reflow : police embarquée (typeface fidèle) + police de
        REPLI complète (accents/ponctuation absents du sous-ensemble anglais).
        Chaque police est associée à sa COUVERTURE fiable (caractères réellement
        dessinés dans le source pour l'embarquée ; None = universel pour le
        repli). Le reflow choisit, glyphe par glyphe, la 1re qui couvre."""
        font_raw = m.get("font", "")
        fonts = []
        primary = self._pick_font(font_raw, txt)
        if primary is not None:
            # Couverture RÉELLE de la police embarquée pour les caractères de ce
            # segment, déterminée par test de rendu (has_glyph/valid_codepoints/
            # glyph_bbox sur-déclarent tous la couverture d'un sous-ensemble).
            cover = frozenset(ch for ch in set(txt)
                              if self._renders_glyph(primary, ch))
            if cover:
                fonts.append((primary, cover))
        fonts.append((self._full_fallback_font(font_raw, m.get("bold"),
                                               m.get("italic")), None))
        return {"text": txt, "fonts": fonts,
                "size": m.get("size", 10) or 10,
                "color": tuple(m.get("color", (0, 0, 0)))}

    def _renders_glyph(self, font, ch):
        """True si `font` produit RÉELLEMENT de l'encre pour `ch` (test de rendu
        sur un petit pixmap, mis en cache). Seule mesure fiable de couverture
        d'un sous-ensemble embarqué, dont les tables cmap/glyf mentent après
        subsetting. Les espaces sont toujours « couverts »."""
        if ch.isspace():
            return True
        cache = getattr(self, "_render_cache", None)
        if cache is None:
            cache = self._render_cache = {}
        key = (id(font), ch)
        if key in cache:
            return cache[key]
        ok = False
        try:
            doc = fitz.open()
            pg = doc.new_page(width=48, height=48)
            tw = fitz.TextWriter(pg.rect, color=(0, 0, 0))
            tw.append(fitz.Point(4, 34), ch, font=font, fontsize=28)
            tw.write_text(pg)
            pix = pg.get_pixmap(alpha=False)
            ok = min(pix.samples) < 250          # un pixel non blanc = de l'encre
            doc.close()
        except Exception:
            ok = False
        cache[key] = ok
        return ok

    def _full_fallback_font(self, font_raw, bold, italic):
        """Police base-14 COMPLÈTE (Latin-1 : é à ç … et ponctuation) assortie à
        la famille et au style de la source, mise en cache."""
        cache = getattr(self, "_fallback_cache", None)
        if cache is None:
            cache = self._fallback_cache = {}
        key = (bool(bold), bool(italic), _base14_family(font_raw))
        f = cache.get(key)
        if f is None:
            try:
                f = fitz.Font(_base14_full_name(font_raw, bold, italic))
            except Exception:
                f = fitz.Font("Helvetica")
            cache[key] = f
        return f

    def _paint_reflow(self, page, res):
        """Peint les lignes de runs placés produites par `reflow`. Chaque run est
        redécoupé en sous-runs par police de glyphe (embarquée / repli) pour que
        les accents s'affichent sans perdre le typeface embarqué ailleurs."""
        for ln in res.get("lines", []):
            base = ln["baseline"]
            for r in ln["runs"]:
                self._paint_run_glyphs(page, r, base)

    def _paint_run_glyphs(self, page, r, base):
        fonts = r.get("fonts") or []
        if not fonts:
            return
        size, color, sx = r["size"], r["color"], r.get("sx", 1.0)
        x = r["x"]
        # Regroupe les caractères consécutifs partageant la même police.
        chunk, chunk_font = "", None
        def flush(cx):
            if not chunk:
                return cx
            pt = fitz.Point(cx, base)
            try:
                tw = fitz.TextWriter(page.rect, color=color)
                tw.append(pt, chunk, font=chunk_font, fontsize=size)
                if abs(sx - 1.0) > 0.001:
                    tw.write_text(page, morph=(pt, fitz.Matrix(sx, 1)))
                else:
                    tw.write_text(page)
            except Exception:
                pass
            return cx + reflow.text_width(chunk, [(chunk_font, None)], size, sx)
        for ch in r["text"]:
            gf = reflow.glyph_font(fonts, ch)
            if chunk and gf is not chunk_font:
                x = flush(x)
                chunk = ""
            chunk_font = gf
            chunk += ch
        flush(x)

    def _draw_text_line(self, page, el):
        for run in el.get("runs", []):
            self._draw_run(page, run)

    def _draw_run(self, page, run):
        bb = run.get("bbox")
        origin = run.get("origin") or [bb[0], bb[3]]
        text = run.get("text", "")
        if not text.strip():
            return
        size = run.get("size", 12) or 12
        color = tuple(run.get("color", [0, 0, 0]))
        # Largeur d'origine du run : on rend le texte MIS À L'ÉCHELLE
        # horizontalement pour l'occuper exactement. Les avances de glyphe du
        # sous-ensemble embarqué diffèrent légèrement (~2 %) du placement réel
        # du PDF ; sans correction, la dérive cumulée fait déborder un run sur
        # le suivant (texte qui se colle / se superpose).
        # La cible est la longueur du run LE LONG DE SON AXE D'ÉCRITURE : extent
        # horizontal (largeur) pour le texte horizontal, extent vertical
        # (hauteur) pour le texte vertical/incliné — la bbox est axis-aligned.
        d = run.get("dir") or (1, 0)
        if bb and len(bb) >= 4:
            target_w = (bb[3] - bb[1]) if abs(d[1]) > abs(d[0]) \
                else (bb[2] - bb[0])
        else:
            target_w = None

        # 1) Police source embarquée (fidélité exacte de police + glyphes).
        font = self._pick_font(run.get("font", ""), text)
        # 2) Sinon police base-14 (Helvetica/Times/Courier), comme objet Font
        #    pour bénéficier du même rendu mis à l'échelle.
        if font is None:
            fontname = _base14_fontname(run.get("font", ""), run.get("bold"),
                                        run.get("italic"))
            try:
                font = fitz.Font(fontname)
            except Exception:
                font = None

        if font is not None:
            try:
                self._write_scaled(page, origin, text, font, size, color,
                                   target_w, run.get("dir"))
                return
            except Exception:
                pass

        # 3) Ultime repli.
        try:
            page.insert_text(fitz.Point(origin), text, fontsize=size,
                             fontname="helv", color=color)
        except Exception:
            pass

    def _write_scaled(self, page, origin, text, font, size, color, target_w,
                      direction=None):
        """Écrit `text` à `origin` avec `font`. Texte horizontal : mis à
        l'échelle en x pour occuper exactement `target_w` (anti-dérive). Texte
        incliné/vertical (Étape C, `direction` ≠ (1,0)) : tourné par la matrice
        de rotation d'angle atan2(dy, dx) autour de l'origine."""
        dx, dy = (direction or (1, 0))
        if abs(dy) > 0.01 or dx < 0:            # direction non horizontale
            self._write_rotated(page, origin, text, font, size, color,
                                 target_w, dx, dy)
            return

        core = text.strip()
        if not core:
            return                              # espace pure : rien de visible
        n_lead = len(text) - len(text.lstrip())
        if n_lead:
            # Espace(s) DE TÊTE : dans l'original ce gap peut être large (mot
            # séparé, ou espace « tracké » d'un titre à lettres espacées). La
            # chasse d'espace de la police embarquée est bien plus étroite → si
            # on laisse la police avancer l'espace, le glyphe suivant se colle
            # trop à gauche (gaps de mots écrasés). On positionne donc le core
            # explicitement : slack (largeur d'origine − chasse du core) réparti
            # sur les espaces de tête/queue (même principe que `_write_rotated`).
            try:
                core_w = font.text_length(core, fontsize=size) if target_w else 0.0
            except Exception:
                core_w = 0.0
            slack = max(0.0, (target_w or core_w) - core_w)
            n_trail = len(text) - len(text.rstrip())
            lead_off = slack * n_lead / (n_lead + n_trail) if (n_lead + n_trail) else 0.0
            pt = fitz.Point(origin[0] + lead_off, origin[1])
            tw = fitz.TextWriter(page.rect, color=color)
            tw.append(pt, core, font=font, fontsize=size)
            tw.write_text(page)                 # rendu naturel (pas de distorsion)
            return

        pt = fitz.Point(origin)
        tw = fitz.TextWriter(page.rect, color=color)
        tw.append(pt, text, font=font, fontsize=size)
        sx = self._hscale(font, text, size, target_w)   # anti-dérive (ou None)
        if sx is not None:
            tw.write_text(page, morph=(pt, fitz.Matrix(sx, 1)))
        else:
            tw.write_text(page)

    def _write_rotated(self, page, origin, text, font, size, color,
                       target_w, dx, dy):
        """Rendu du texte INCLINÉ / VERTICAL (Étape C).

        Rotation : `dir` de PyMuPDF est en espace page (y vers le BAS) alors que
        fitz.Matrix(deg) attend un angle au sens mathématique (y vers le HAUT) —
        on nie dy pour convertir le sens (cf. moteur stable `_dir_to_angle`),
        sinon la rotation est inversée (texte à l'envers).

        Espaces de mot : le texte vertical est éclaté en glyphes, souvent avec une
        espace de tête (ex. run ' O'). Dans l'original ce gap est large, mais la
        chasse d'espace de la police embarquée est étroite → au naturel les mots
        se colleraient ; à l'échelle (bbox entière) le glyphe se déformerait. On
        NE rend donc PAS l'espace : on décale le glyphe visible de la largeur du
        gap d'origine (`target_w − chasse(core)`) et on le rend au NATUREL."""
        core = text.strip()
        if not core:
            return                              # espace pure : rien de visible
        deg = math.degrees(math.atan2(-dy, dx))

        lead_off = 0.0
        sx = None
        if core == text:                        # pas d'espace : anti-dérive normal
            sx = self._hscale(font, core, size, target_w)
        elif target_w and target_w > 0:         # espace(s) autour du glyphe
            try:
                core_w = font.text_length(core, fontsize=size)
            except Exception:
                core_w = 0.0
            n_lead = len(text) - len(text.lstrip())
            n_trail = len(text) - len(text.rstrip())
            slack = max(0.0, target_w - core_w)
            if n_lead + n_trail:
                lead_off = slack * n_lead / (n_lead + n_trail)

        pt = fitz.Point(origin[0] + dx * lead_off, origin[1] + dy * lead_off)
        tw = fitz.TextWriter(page.rect, color=color)
        tw.append(pt, core, font=font, fontsize=size)
        mat = fitz.Matrix(deg)
        if sx is not None:
            mat = fitz.Matrix(sx, 1) * mat      # scale (le long de l'axe) puis rotation
        tw.write_text(page, morph=(pt, mat))

    @staticmethod
    def _hscale(font, text, size, target_w):
        """Facteur d'échelle horizontal anti-dérive : ramène la chasse du run à sa
        largeur d'origine `target_w`. Retourne None (pas de correction) si :
        - pas de cible ; ou
        - **run d'un seul glyphe** : sa bbox reflète l'INK (approches latérales),
          pas la chasse — le mettre à l'échelle déformerait le glyphe alors que
          sa position vient déjà de son origine (cas du texte vertical éclaté en
          lettres) ; ou
        - écart aberrant (données incohérentes) ou négligeable.
        Sinon un `sx` borné à [0.5, 2.0]."""
        if not target_w or target_w <= 0:
            return None
        if len(text.strip()) < 2:            # glyphe isolé : positionné par origine
            return None
        try:
            rw = font.text_length(text, fontsize=size)
        except Exception:
            return None
        if rw <= 0:
            return None
        sx = target_w / rw
        if 0.5 <= sx <= 2.0 and abs(sx - 1.0) > 0.005:
            return sx
        return None

    # ── Bordures : une par objet (les lignes de texte sont déjà groupées) ────
    def _draw_borders(self, page, elements):
        for el in elements:
            self._draw_border(page, el)

    # ── Bordure autour d'un objet ────────────────────────────────────────────
    def _draw_border(self, page, el):
        color = BORDER_COLORS.get(el.get("type"), (0.5, 0.5, 0.5))

        # Paragraphe multi-lignes : contour EXACT en escalier épousant chaque
        # ligne (bords droits irréguliers, retraits, enroulement autour d'une
        # image/encart) plutôt qu'un rectangle englobant. Puis, si présent, le
        # CONTENEUR élargi (Étape D) en orange pointillé.
        if el.get("type") == "paragraph":
            bboxes = [ln.get("bbox") for ln in el.get("lines", [])]
            if len([b for b in bboxes if b and len(b) >= 4]) > 1:
                self._draw_stair_outline(page, bboxes, color)
                self._draw_expansion_frame(page, el)
                return
            self._draw_expansion_frame(page, el)

        bbox = el.get("bbox")
        if not bbox or len(bbox) < 4:
            return
        rect = fitz.Rect(bbox)
        if rect.x1 < rect.x0 or rect.y1 < rect.y0:
            return
        # Objet dégénéré (ligne fine) : on l'épaissit un peu pour rester visible.
        if (rect.x1 - rect.x0) < 1 or (rect.y1 - rect.y0) < 1:
            rect = fitz.Rect(rect.x0 - 0.8, rect.y0 - 0.8,
                             rect.x1 + 0.8, rect.y1 + 0.8)
        try:
            page.draw_rect(rect, color=color, width=BORDER_WIDTH)
        except Exception:
            pass

    def _draw_expansion_frame(self, page, el):
        """Trace le cadre du CONTENEUR élargi d'un paragraphe (Étape D) en orange
        pointillé : contour en escalier des lignes élargies (`container_lines`),
        qui épouse un L autour d'un encart. No-op si absent."""
        clines = el.get("container_lines")
        if clines:
            self._draw_stair_outline(page, clines, EXPAND_COLOR,
                                     width=EXPAND_WIDTH, dashes="[3 2] 0")
            return
        cbb = el.get("container_bbox")
        if cbb and len(cbb) >= 4:
            self._draw_stair_outline(page, [cbb], EXPAND_COLOR,
                                     width=EXPAND_WIDTH, dashes="[3 2] 0")

    def _draw_stair_outline(self, page, bboxes, color,
                            width=BORDER_WIDTH, dashes=None):
        """Trace un contour rectilinéaire (en escalier) qui passe par les
        sommets de chaque ligne du paragraphe : côté droit haut→bas, côté
        gauche bas→haut, fermé. Épouse exactement l'étendue réelle des lignes."""
        rows = []
        for bb in bboxes:
            if not bb or len(bb) < 4 or bb[2] <= bb[0] or bb[3] <= bb[1]:
                continue
            rows.append([bb[0], bb[1], bb[2], bb[3]])   # [l, t, r, b]
        if not rows:
            return
        if len(rows) == 1:
            r = rows[0]
            rect = fitz.Rect(r[0], r[1], r[2], r[3])
            try:
                page.draw_rect(rect, color=color, width=width, dashes=dashes)
            except Exception:
                try:
                    page.draw_rect(rect, color=color, width=width)
                except Exception:
                    pass
            return
        rows.sort(key=lambda r: (r[1], r[0]))
        # Frontière verticale nette entre deux lignes voisines (milieu de
        # l'écart) → escalier propre, sans recouvrement ni auto-intersection.
        for i in range(len(rows) - 1):
            mid = (rows[i][3] + rows[i + 1][1]) / 2.0
            rows[i][3] = mid
            rows[i + 1][1] = mid
        pts = []
        for r in rows:                       # côté droit, haut → bas
            pts.append(fitz.Point(r[2], r[1]))
            pts.append(fitz.Point(r[2], r[3]))
        for r in reversed(rows):             # côté gauche, bas → haut
            pts.append(fitz.Point(r[0], r[3]))
            pts.append(fitz.Point(r[0], r[1]))
        pts.append(pts[0])
        try:
            page.draw_polyline(pts, color=color, width=width, dashes=dashes)
        except Exception:
            try:
                page.draw_polyline(pts, color=color, width=width)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ════════════════════════════════════════════════════════════════════════════
def _ends_sentence(text):
    """La ligne se termine-t-elle par une ponctuation forte (hors guillemets) ?"""
    t = text.rstrip().rstrip('"”’\')')
    return bool(t) and t[-1] in ".!?…"


def _starts_capital(text):
    """La ligne commence-t-elle par une majuscule ? (False si chiffre/rien)."""
    for ch in text.lstrip():
        if ch.isalpha():
            return ch.isupper()
        if ch.isdigit():
            return False
    return False


def _starts_lower(text):
    """La ligne commence-t-elle par une minuscule ? (→ continuation certaine)."""
    for ch in text.lstrip():
        if ch.isalpha():
            return ch.islower()
        if ch.isdigit():
            return False
    return False


def _first_word(text):
    t = text.strip()
    return t.split(" ", 1)[0].strip(".,;:!?)]}»”\"'") if t else ""


def _is_horizontal(run):
    """Un run est horizontal si sa direction d'écriture est (≈1, 0)."""
    d = run.get("dir") or [1, 0]
    return abs(d[1]) <= 0.01 and d[0] >= 0


def _int_color_to_rgb(c):
    """Couleur span PyMuPDF (entier 0xRRGGBB) -> [r, g, b] en 0..1."""
    if isinstance(c, (list, tuple)):
        return [float(v) for v in c]
    c = int(c)
    return [((c >> 16) & 255) / 255.0,
            ((c >> 8) & 255) / 255.0,
            (c & 255) / 255.0]


def _base14_family(font_raw):
    """Famille base-14 déduite du nom : 'times' (serif), 'cour' (mono) ou
    'helv' (sans, défaut)."""
    name = (font_raw or "").lower()
    if any(t in name for t in ("mono", "courier", "consol", "typewriter")):
        return "cour"
    if any(t in name for t in ("times", "serif", "georgia", "garamond", "roman",
                               "minion", "cambria", "book")):
        return "times"
    return "helv"


def _base14_full_name(font_raw, bold, italic):
    """Nom base-14 COMPLET accepté par `fitz.Font` (ex. 'Times-BoldItalic',
    'Helvetica-Oblique', 'Courier-Bold') — polices à couverture Latin-1 complète,
    utilisées comme repli pour les glyphes absents du sous-ensemble embarqué."""
    fam = _base14_family(font_raw)
    bold, italic = bool(bold), bool(italic)
    if fam == "times":
        if bold and italic:
            return "Times-BoldItalic"
        if bold:
            return "Times-Bold"
        if italic:
            return "Times-Italic"
        return "Times-Roman"
    base = "Courier" if fam == "cour" else "Helvetica"
    slant = "Oblique"
    if bold and italic:
        return f"{base}-Bold{slant}"
    if bold:
        return f"{base}-Bold"
    if italic:
        return f"{base}-{slant}"
    return base


def _base14_fontname(font_raw, bold, italic):
    """Mappe un nom de police vers l'une des 14 polices PDF de base.

    Volontairement BASIQUE : on préserve la famille (serif/sans/mono) et le
    style (gras/italique) sans embarquer de police. Pour une fidélité de
    glyphes exacte, un embarquement de police serait nécessaire (hors scope
    de ce moteur minimal)."""
    name = (font_raw or "").lower()
    is_serif = any(t in name for t in
                   ("times", "serif", "georgia", "garamond", "roman",
                    "minion", "cambria", "book"))
    is_mono = any(t in name for t in
                  ("mono", "courier", "consol", "typewriter"))
    if is_mono:
        base = "cour"
    elif is_serif:
        base = "times"
    else:
        base = "helv"

    if base == "times":
        if bold and italic:
            return "tibi"
        if bold:
            return "tibo"
        if italic:
            return "tiit"
        return "times"
    # helv / cour partagent le schéma de suffixes b / o / bo
    suffix = ("bo" if bold and italic else
              "b" if bold else
              "o" if italic else "")
    return base + suffix
