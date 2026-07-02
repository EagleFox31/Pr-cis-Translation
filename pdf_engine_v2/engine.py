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
import base64
from pathlib import Path
from collections import defaultdict

import fitz  # PyMuPDF >= 1.23

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
                page_data["elements"].extend(self._extract_drawings(page))
                page_data["elements"].extend(self._extract_images(
                    doc, page, page_num, embed_images, assets_dir))
                text_lines = self._extract_text(page)
                if self.group_paragraphs:
                    page_data["elements"].extend(self._group_paragraphs(text_lines))
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
    _PARA_GAP_FACTOR     = 1.8     # saut vertical > facteur × taille → coupe DURE
    _PARA_MODERATE_FACTOR = 1.35   # gap au-delà duquel l'INDENTATION peut couper
    _PARA_PUNCT_FACTOR   = 1.6     # gap au-delà duquel la PONCTUATION peut couper
    _PARA_INDENT_FACTOR  = 1.2     # indentation > facteur × taille → coupe
    _PARA_SIZE_FACTOR    = 0.20    # écart de taille relatif → coupe (titre)

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
        """Regroupe des spans en lignes visuelles (clustering baseline + coupe
        aux séparateurs de colonne). Retourne une liste d'objets `text_line`."""
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
        runs = [{
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
        } for s in seg_spans]
        return {
            "type": "text_line",
            "bbox": [x0, y0, x1, y1],
            "text": "".join(parts),
            "runs": runs,
        }

    # ── Regroupement en PARAGRAPHES (étape 7 : géométrie + linguistique) ─────
    def _group_paragraphs(self, lines):
        """Regroupe des lignes (`text_line`) en paragraphes. Column-aware :
        deux lignes ne fusionnent que si elles se chevauchent horizontalement
        (même colonne). La priorité va à la GÉOMÉTRIE (interligne) ; les signaux
        faibles (indentation, ponctuation) n'agissent qu'en cas d'écart élevé.
        Retourne des objets `paragraph` { bbox, text, lines:[...] }."""
        if not lines:
            return []
        items = [self._line_metrics(ln) for ln in lines]
        items.sort(key=lambda it: (round(it["top"], 1), it["left"]))

        paras = []
        for it in items:
            # Candidats parents : paragraphes ouverts dont la dernière ligne est
            # AU-DESSUS et chevauche horizontalement (même colonne).
            cands = []
            for p in paras:
                last = p["items"][-1]
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
            if parent is not None and not self._para_break(parent, it):
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
        return out

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
            "bold": (bold_chars / total) >= 0.6,
        }

    def _para_break(self, parent, it):
        """True si `it` doit démarrer un NOUVEAU paragraphe (coupe).

        Hiérarchie stricte (la géométrie prime, cf. cas texte enroulé) :
          1. signaux DURS : liste, changement de style, gros saut vertical ;
          2. flot continu : sous le seuil « modéré », on FUSIONNE toujours —
             peu importe x0 (enroulement) ou une ponctuation faible ;
          3. zone modérée : indentation d'alinéa, puis (gap plus élevé)
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

        # ── 2. Flot continu : interligne normal → FUSION obligatoire ────────
        # (x0 ignoré : c'est ce qui permet au texte de s'enrouler autour d'une
        # image / d'un encart sans être scindé.)
        if g < self._PARA_MODERATE_FACTOR:
            return False
        # Ligne suivante en minuscule → continuation certaine → fusion.
        if _starts_lower(it["text"]):
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
    def reinject(self, data_or_json, output_pdf, draw_borders=True,
                 assets_dir=None):
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

    def _draw_text_line(self, page, el):
        for run in el.get("runs", []):
            self._draw_run(page, run)

    def _draw_run(self, page, run):
        origin = run.get("origin") or [run["bbox"][0], run["bbox"][3]]
        text = run.get("text", "")
        if not text.strip():
            return
        size = run.get("size", 12) or 12
        color = tuple(run.get("color", [0, 0, 0]))

        # 1) Police source embarquée (fidélité exacte de police + glyphes).
        font = self._pick_font(run.get("font", ""), text)
        if font is not None:
            try:
                tw = fitz.TextWriter(page.rect, color=color)
                tw.append(fitz.Point(origin), text, font=font, fontsize=size)
                tw.write_text(page)
                return
            except Exception:
                pass   # repli base-14 ci-dessous

        # 2) Repli base-14 (police non embarquée : Helvetica/Times/Courier).
        fontname = _base14_fontname(run.get("font", ""), run.get("bold"),
                                    run.get("italic"))
        try:
            page.insert_text(fitz.Point(origin), text, fontsize=size,
                             fontname=fontname, color=color)
        except Exception:
            page.insert_text(fitz.Point(origin), text, fontsize=size,
                             fontname="helv", color=color)

    # ── Bordures : une par objet (les lignes de texte sont déjà groupées) ────
    def _draw_borders(self, page, elements):
        for el in elements:
            self._draw_border(page, el)

    # ── Bordure autour d'un objet ────────────────────────────────────────────
    def _draw_border(self, page, el):
        color = BORDER_COLORS.get(el.get("type"), (0.5, 0.5, 0.5))

        # Paragraphe multi-lignes : contour EXACT en escalier épousant chaque
        # ligne (bords droits irréguliers, retraits, enroulement autour d'une
        # image/encart) plutôt qu'un rectangle englobant.
        if el.get("type") == "paragraph":
            bboxes = [ln.get("bbox") for ln in el.get("lines", [])]
            if len([b for b in bboxes if b and len(b) >= 4]) > 1:
                self._draw_stair_outline(page, bboxes, color)
                return

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

    def _draw_stair_outline(self, page, bboxes, color):
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
            try:
                page.draw_rect(fitz.Rect(r[0], r[1], r[2], r[3]),
                               color=color, width=BORDER_WIDTH)
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
            page.draw_polyline(pts, color=color, width=BORDER_WIDTH)
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


def _int_color_to_rgb(c):
    """Couleur span PyMuPDF (entier 0xRRGGBB) -> [r, g, b] en 0..1."""
    if isinstance(c, (list, tuple)):
        return [float(v) for v in c]
    c = int(c)
    return [((c >> 16) & 255) / 255.0,
            ((c >> 8) & 255) / 255.0,
            (c & 255) / 255.0]


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
