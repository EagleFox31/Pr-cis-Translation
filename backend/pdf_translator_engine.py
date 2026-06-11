import os
import json
import math
import shutil
import tempfile
import threading
from pathlib import Path
import fitz  # PyMuPDF >= 1.23

# Téléchargements de polices en cours (dédupe inter-threads/instances)
_FONT_DL_INFLIGHT = set()
_FONT_DL_LOCK = threading.Lock()

# ── Constantes flags de span PyMuPDF ─────────────────────────────────────────
FLAG_BOLD       = 16   # bit 4
FLAG_ITALIC     = 2    # bit 1
FLAG_MONOSPACE  = 8    # bit 3
FLAG_SUPERSCRIPT = 1   # bit 0

# ── Constantes char_flags de span PyMuPDF (v1.25.2+) ────────────────────────
CHAR_UNDERLINE = 2    # bit 1
CHAR_STRIKEOUT = 1    # bit 0

# ── Caractères de puce / liste ───────────────────────────────────────────────
BULLET_CHARS = {
    '•', '●', '▪', '‣', '⁃', '→', '➢', '▸', '▹', '◆', '◦', '⦿', '⁌', '⁍',
    '◉', '◎', '◌', '○', '⦾', '⦿', '⬤', '✽', '⁖',
    # Losanges / diamants (Word, Segoe UI Symbol…)
    '❖', '◇', '♦', '⧫', '⬥', '⬦', '✦', '✧', '❅', '❉',
}

# Polices symbole couramment utilisées pour les puces : un span court dans l'une
# d'elles (ex. « O » en ZapfDingbats) est un marqueur de puce, pas du texte.
BULLET_FONT_NAMES = {
    "zapfdingbats", "wingdings", "wingdings2", "wingdings3",
    "webdings", "symbol", "dingbats",
}
# Police PDF de base à utiliser pour rendre fidèlement ces marqueurs.
SYMBOL_BUILTIN_FONT = {"zapfdingbats": "zadb", "dingbats": "zadb", "symbol": "symb"}

class PDFTranslatorEngine:
    """
    Moteur de traduction PDF production-ready.
    Pipeline : extraction JSON → traduction externe → réinjection fidèle.
    """

    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self._font_cache = {}   # fontfile -> fitz.Font (réutilisé entre spans)
        self._bundled = None    # index lazy du dossier backend/fonts/
        self.auto_download_fonts = True   # télécharge les polices manquantes
        self._font_dl_tried = None        # familles déjà tentées (lazy)
        self._llm_client = None           # client OpenAI-compatible (optionnel)
        self._llm_model  = "deepseek-chat"

    def configure_llm(self, api_key: str,
                      base_url: str = "https://api.deepseek.com",
                      model: str = "deepseek-chat") -> None:
        """Configure le client LLM utilisé pour valider les fusions inter-blocs
        ambiguës. Optionnel : sans configuration, seule la géométrie est utilisée."""
        from openai import OpenAI
        self._llm_client = OpenAI(api_key=api_key, base_url=base_url)
        self._llm_model  = model

    def _cleanup_temp(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. EXTRACTION — capture TOUS les attributs de style
    # ══════════════════════════════════════════════════════════════════════════
    def extract_text(self, pdf_path: str,
                     output_json: str = None,
                     filters: dict = None,
                     progress_callback=None):
        """
        Extrait chaque span de texte avec la totalité de ses métadonnées :
          - texte, bbox, origin (baseline exacte)
          - police, taille, couleur RGB, flags (gras/italique)
          - direction (horizontal ou rotation)
          - page_num
        """
        if output_json is None:
            output_json = str(Path(pdf_path).with_suffix("")) + "_extraction.json"

        extraction = {"pages": []}
        element_types_used = {}

        try:
            doc = fitz.open(pdf_path)
            total = len(doc)

            for page_num, page in enumerate(doc):
                if page_num >= 5:
                    break
                if progress_callback:
                    progress_callback(f"Extraction page {page_num + 1}/{total}...")

                page_data = {
                    "page_num": page_num + 1,
                    "width":    page.rect.width,
                    "height":   page.rect.height,
                    "text_blocks": []
                }

                raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

                rotated_spans = []    # spans pivotés, regroupés au niveau page
                page_groups = []      # groupes horizontaux de TOUS les blocs (fusion inter-blocs ensuite)
                all_gap_ratios = []   # gap/size intra-paragraphe observés sur cette page
                for b_idx, block in enumerate(raw.get("blocks", [])):
                    if block.get("type") != 0:   # 0 = texte, 1 = image
                        continue

                    # Aplatir les spans visibles du bloc (avec la rotation de
                    # leur ligne). Les spans pivotés (cellules verticales) sont
                    # collectés à part : PyMuPDF les éclate souvent en plusieurs
                    # blocs, on les regroupera au niveau page.
                    items = []
                    for line in block.get("lines", []):
                        rot = self._dir_to_angle(line.get("dir", (1, 0)))
                        for span in line.get("spans", []):
                            if not span.get("text", "").strip():
                                continue
                            if abs(rot) > 1.0:
                                rotated_spans.append((span, rot))
                            else:
                                items.append((span, rot))
                    if not items:
                        continue

                    block_w = block["bbox"][2] - block["bbox"][0]
                    grps, gap_ratios = self._group_paragraphs(items, block_w)
                    page_groups.extend(grps)
                    all_gap_ratios.extend(gap_ratios)

                # Fusion inter-blocs (_merge_cross_block + validation LLM)
                # DÉSACTIVÉE : elle créait des fusions erronées. Chaque groupe
                # issu du regroupement intra-bloc (_group_paragraphs) est
                # conservé tel quel. Seul le regroupement des lignes wrap d'un
                # même bloc PyMuPDF reste actif.
                merged_groups = page_groups

                for p_idx, group in enumerate(merged_groups):
                    page_data["text_blocks"].append(
                        self._make_para_entry(group, page_num, 0, p_idx)
                    )

                # Paragraphes pivotés (titres verticaux de tableau) : regroupés
                # dans leur repère (colonnes = x, sens de lecture = y).
                for r_idx, group in enumerate(self._group_rotated_paragraphs(rotated_spans)):
                    page_data["text_blocks"].append(
                        self._make_para_entry(group, page_num, 9000, r_idx, rotated=True)
                    )

                # ── Détection du soulignement via les dessins vectoriels ────
                # Un underline peut être tracé soit comme un trait (type 's',
                # item 'l'), soit comme un fin rectangle plein (type 'f',
                # item 're') — fréquent dans les PDF issus de Word. On collecte
                # tous les segments horizontaux fins, puis on les rattache aux
                # spans par proximité verticale (juste sous la baseline) et
                # recouvrement horizontal.
                try:
                    underline_segs = []   # (x0, x1, y)
                    for d in page.get_cdrawings():
                        for item in d.get("items", []):
                            op = item[0]
                            if op == "l":                       # trait
                                p1, p2 = item[1], item[2]
                                if abs(p1[1] - p2[1]) > 1.0:    # non horizontal
                                    continue
                                x0, x1 = sorted((p1[0], p2[0]))
                                if x1 - x0 < 5.0:
                                    continue
                                underline_segs.append((x0, x1, (p1[1] + p2[1]) / 2))
                            elif op == "re":                    # rectangle plein
                                r = item[1]
                                rx0, ry0, rx1, ry1 = r[0], r[1], r[2], r[3]
                                if abs(ry1 - ry0) > 3.0:        # trop épais → pas un underline
                                    continue
                                if abs(rx1 - rx0) < 5.0:
                                    continue
                                underline_segs.append((min(rx0, rx1), max(rx0, rx1),
                                                       (ry0 + ry1) / 2))

                    for block in page_data["text_blocks"]:
                        if block.get("underline"):
                            continue
                        origin_y = block["origin"][1]
                        bbox_x0, bbox_x1 = block["bbox"][0], block["bbox"][2]
                        text_width = bbox_x1 - bbox_x0
                        if text_width < 1:
                            continue
                        # tolérance d'alignement horizontal : un vrai underline
                        # épouse l'étendue du texte ; une bordure de cellule de
                        # tableau déborde largement jusqu'au bord de colonne.
                        tol = max(12.0, 0.3 * text_width)
                        for sx0, sx1, sy in underline_segs:
                            # le segment doit être juste sous la baseline
                            if not (-2.0 <= sy - origin_y <= 5.0):
                                continue
                            overlap = min(sx1, bbox_x1) - max(sx0, bbox_x0)
                            if overlap <= text_width * 0.3:
                                continue
                            # rejette les lignes de grille (débordent du texte)
                            if (sx1 - bbox_x1) > tol or (bbox_x0 - sx0) > tol:
                                continue
                            block["underline"] = True
                            break
                except Exception:
                    pass

                # Calcule l'espace libre à droite de chaque bloc (jusqu'au
                # prochain bloc voisin sur la même bande verticale, ou la marge
                # droite). Utilisé à l'injection comme largeur disponible pour
                # l'ajustement de taille : un bloc d'origine étroit peut recevoir
                # un texte traduit plus long tant que rien ne le borde à droite.
                self._compute_avail_widths(page_data, page_data["width"])

                extraction["pages"].append(page_data)
                element_types_used[page_num + 1] = ["text_block"]

            # Inventaire des polices (le document est encore ouvert).
            try:
                fonts = self._font_inventory(doc, progress_callback)
                extraction["fonts"] = fonts
                substituted = [f["name"] for f in fonts if not f["exact"]]
                if progress_callback and substituted:
                    progress_callback(
                        "⚠ Polices non disponibles (rendu en substitut) : "
                        + ", ".join(substituted)
                        + " — déposez le .ttf dans backend/fonts/ pour la fidélité exacte."
                    )
            except Exception:
                extraction["fonts"] = []

            doc.close()

        except Exception as e:
            return None, f"Erreur extraction : {str(e)}"

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback(f"✓ Extraction terminée → {output_json}")

        return extraction, element_types_used

    # ══════════════════════════════════════════════════════════════════════════
    # 2. RÉINJECTION — reconstruit chaque page avec style complet
    # ══════════════════════════════════════════════════════════════════════════
    def inject_translation(self, original_pdf: str,
                           translated_json_path: str,
                           output_pdf: str,
                           progress_callback=None,
                           format_options=None):
        """
        Réinjection en 3 étapes par page :
          1. insert_pdf  → copie page originale (images, formes, fonds)
          2. redact      → efface le texte original (rectangles blancs)
          3. insert_text → écrit le texte traduit avec style complet
        """
        if not os.path.exists(translated_json_path):
            return False, "Fichier JSON introuvable."

        try:
            with open(translated_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Erreur lecture JSON : {str(e)}"

        # Garantit la disponibilité des polices avant rendu (télécharge les
        # manquantes une fois ; couvre aussi le cas d'un extraction.json en cache
        # qui n'aurait pas déclenché le téléchargement à l'extraction).
        try:
            for fr in {b.get("font") for pg in data.get("pages", [])
                       for b in pg.get("text_blocks", []) if b.get("font")}:
                self._ensure_font(fr, progress_callback)
        except Exception:
            pass

        try:
            original_doc = fitz.open(original_pdf)
            new_doc      = fitz.open()
            pages        = data.get("pages", [])
            total        = len(pages)

            for page_idx, page_data in enumerate(pages):
                if page_idx >= len(original_doc):
                    break
                if progress_callback:
                    progress_callback(f"Injection page {page_idx + 1}/{total}...")

                new_doc.insert_pdf(original_doc, from_page=page_idx, to_page=page_idx)
                new_page = new_doc[-1]

                blocks = page_data.get("text_blocks", [])

                # Taille de police minimale présente sur cette page : plancher
                # adaptatif pour la réduction de police à l'injection — on ne
                # réduit jamais en-dessous du plus petit texte déjà visible.
                min_font_size = min(
                    (b.get("size", 12) for b in blocks if b.get("size")),
                    default=5.0
                )

                # Reflow (élargissement horizontal + déplacement vertical +
                # inline) DÉSACTIVÉ : chaque bloc est rendu à sa position et
                # dans sa boîte d'origine. La gestion de l'espace repose sur
                # (1) la fusion des blocs d'un même paragraphe à l'extraction
                # (géométrie + validation IA) et (2) la contrainte de longueur
                # imposée à la traduction (≈ même taille, sinon plus court).

                for block in blocks:
                    # On efface le texte à son ANCIENNE position (avant reflow).
                    bbox = block.get("_old_bbox") or block.get("bbox")
                    if not bbox or len(bbox) < 4:
                        continue
                    rect = fitz.Rect(bbox) + fitz.Rect(-1.5, -2, 1.5, 2)
                    new_page.add_redact_annot(rect, fill=None)

                new_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # ── Fusion par clés de paragraphe (attribuées par l'IA) ─────
                # Les blocs partageant une même paragraph_key sont rendus
                # ensemble dans un conteneur unique : le rectangle englobant de
                # leurs bbox d'ORIGINE (tangent aux bords extrêmes haut/bas/
                # gauche/droite). Chaque fragment conserve sa mise en forme
                # extraite (police, taille, couleur, soulignement) ; seul le
                # flux du texte (retours à la ligne) est recalculé dans le
                # conteneur. Les blocs pivotés ne sont jamais fusionnés.
                by_key = {}
                for block in blocks:
                    k = block.get("paragraph_key")
                    if k:
                        by_key.setdefault(k, []).append(block)

                # Passe 1 — déterminer les groupes à fusionner (validation
                # géométrique des clés IA : un paragraphe réel a une taille
                # homogène et des baselines consécutives ; les éléments
                # regroupés à tort — numéro de page, titre… — sont détachés).
                runs_to_render = []
                merged_ids = set()
                for grp in by_key.values():
                    if len(grp) < 2:
                        continue
                    if any(abs(b.get("rotation", 0.0)) > 1.0 for b in grp):
                        continue   # texte pivoté → rendu individuel
                    for run in self._split_group_runs(grp):
                        if len(run) >= 2:
                            runs_to_render.append(run)
                            merged_ids.update(id(b) for b in run)

                # Passe 2 — géométries d'origine des unités de rendu.
                run_geoms = []
                for run in runs_to_render:
                    def _rb(b):
                        o = b.get("origin")
                        return o[1] if o and len(o) >= 2 else b["bbox"][3]
                    run_geoms.append([
                        min(b["bbox"][0] for b in run),
                        min(b["bbox"][1] for b in run),
                        max(b["bbox"][2] for b in run),
                        max(b["bbox"][3] for b in run),
                        len({round(_rb(b), 1) for b in run}),   # nb de lignes
                    ])

                solos = []
                for b in blocks:
                    if id(b) in merged_ids or abs(b.get("rotation", 0.0)) > 1.0:
                        continue
                    t = (b.get("translated_text") or "").strip() \
                        or (b.get("text") or "").strip()
                    bb = b.get("bbox")
                    if not t or not bb or len(bb) < 4:
                        continue
                    solos.append((b, t))

                # Toutes les boîtes d'ORIGINE (groupes + individuels) : servent
                # de références d'alignement et d'obstacles.
                all_geoms = [(g[0], g[1], g[2], g[3]) for g in run_geoms]
                all_geoms += [tuple(b["bbox"][:4]) for b, _t in solos]

                # Garde-fou de légitimité : un alignement gauche ne définit une
                # « colonne » (et n'autorise l'étirement) que s'il est porté
                # par au moins MIN_ALIGNED unités de rendu de la page. Deux
                # blocs alignés peuvent être une coïncidence ; trois ou plus
                # révèlent une structure voulue par le maquettiste. En dessous
                # du seuil, comportement antérieur inchangé (bbox stricte).
                MIN_ALIGNED = 3

                def _aligned_count(v):
                    return sum(1 for ox0, _oy0, _ox1, _oy1 in all_geoms
                               if abs(ox0 - v) <= 3.0)

                # Passe 2a — largeur étendue des blocs INDIVIDUELS (même règle
                # de colonne que les groupes) : un bloc mono-ligne aligné à
                # gauche avec d'autres (entrées de sommaire, titres de même
                # niveau…) peut s'étendre jusqu'au bord droit max observé
                # parmi les blocs de même x0 (±3 pt), borné par le premier
                # bloc d'origine à sa droite dans sa bande verticale. La
                # réduction de police ne s'applique qu'APRÈS cet étirement.
                ext_widths = {}
                for b, _t in solos:
                    bx0, by0, bx1, by1 = b["bbox"][:4]
                    if _aligned_count(bx0) < MIN_ALIGNED:
                        ext_widths[id(b)] = bx1 - bx0   # alignement non prouvé
                        continue
                    col_x1 = bx1
                    for ox0, _oy0, ox1, _oy1 in all_geoms:
                        if abs(ox0 - bx0) <= 3.0:
                            col_x1 = max(col_x1, ox1)
                    limit = col_x1
                    for ox0, oy0, _ox1, oy1 in all_geoms:
                        if oy0 >= by1 or oy1 <= by0:
                            continue          # hors de la bande verticale
                        if (ox0, oy0) == (bx0, by0):
                            continue          # lui-même
                        if bx1 - 1.0 <= ox0 < limit:
                            limit = ox0 - 4.0
                    ext_widths[id(b)] = max(bx1, limit) - bx0

                # Passe 2b — étendue horizontale RÉELLEMENT rendue des blocs
                # individuels (avec leur largeur étendue) : sert aux groupes
                # pour l'anti-chevauchement de 1re ligne.
                solo_extents = []
                for b, t in solos:
                    bb = b["bbox"]
                    o = b.get("origin")
                    sx = o[0] if o and len(o) >= 2 else bb[0]
                    sy = o[1] if o and len(o) >= 2 else bb[3]
                    fm = b.get("font_mapped", "helv")
                    sz = b.get("size", 12)
                    fitted = self._fit_fontsize(
                        t, fm, max(2.0, ext_widths.get(id(b), bb[2] - bb[0])),
                        sz, min_size=min_font_size)
                    tw = self._text_length(t, fitted, fm, b.get("font", ""))
                    solo_extents.append((sx, sx + tw, sy, sz))

                # Passe 2c — largeur réelle de colonne des GROUPES. Les
                # paragraphes alignés sur la même verticale gauche (±3 pt)
                # appartiennent au même flux de colonne : le bord droit MAXIMAL
                # observé parmi les paragraphes multi-lignes de même x0 révèle
                # la vraie largeur de colonne. Un conteneur étroit (paragraphe
                # court) peut s'y étendre — borné par le premier élément
                # rendu à sa droite (encart, autre colonne, libellé…).

                ext_x1s = []
                for i, (rx0, ry0, rx1, ry1, _nl) in enumerate(run_geoms):
                    if _aligned_count(rx0) < MIN_ALIGNED:
                        ext_x1s.append(rx1)             # alignement non prouvé
                        continue
                    # Bord droit max des paragraphes multi-lignes de même x0
                    # (leurs lignes pleines épousent la marge de colonne ; les
                    # mono-lignes, titres…, ne sont pas une référence fiable).
                    col_x1 = rx1
                    for ox0, _oy0, ox1, _oy1, onl in run_geoms:
                        if onl >= 2 and abs(ox0 - rx0) <= 3.0:
                            col_x1 = max(col_x1, ox1)
                    # Borne : premier élément rendu à droite dans la bande
                    # verticale du paragraphe (jamais d'empiètement).
                    limit = col_x1
                    for sx0, _sx1, sy, ssize in solo_extents:
                        if sy - ssize >= ry1 or sy <= ry0:
                            continue          # hors de la bande verticale
                        if rx1 - 1.0 <= sx0 < limit:
                            limit = sx0 - 4.0
                    for j, (ox0, oy0, _ox1, oy1, _onl) in enumerate(run_geoms):
                        if j == i or oy0 >= ry1 or oy1 <= ry0:
                            continue
                        if rx1 - 1.0 <= ox0 < limit:
                            limit = ox0 - 4.0
                    ext_x1s.append(max(rx1, limit))

                # Passe 3 — rendu des groupes, informés des voisins rendus
                # et de la largeur de colonne disponible.
                for run, ext_x1 in zip(runs_to_render, ext_x1s):
                    self._render_paragraph_group(new_page, run, solo_extents,
                                                 ext_x1=ext_x1)

                for block in blocks:
                    if id(block) in merged_ids:
                        continue   # déjà rendu via son groupe de paragraphe
                    translated = block.get("translated_text", "").strip()
                    if not translated:
                        translated = block.get("text", "").strip()

                    is_list    = block.get("is_list_item", False)
                    bullet_char = block.get("bullet_char", None)
                    # Un bloc « puce seule » (texte propre vide) doit malgré tout
                    # dessiner sa puce — sinon le marqueur de liste disparaît.
                    if not translated and not (is_list and bullet_char):
                        continue

                    bbox       = block.get("bbox")
                    origin     = block.get("origin")
                    font_name  = block.get("font_mapped", "helv")
                    orig_size  = block.get("size", 12)
                    color      = tuple(block.get("color", [0, 0, 0]))
                    rotation   = block.get("rotation", 0.0)
                    bullet_font = block.get("bullet_font", None)
                    bullet_origin = block.get("bullet_origin", None)
                    font_raw    = block.get("font", font_name)
                    is_underline = block.get("underline", False)

                    if not bbox or len(bbox) < 4:
                        continue

                    if origin and len(origin) >= 2:
                        x, y = origin[0], origin[1]
                    else:
                        x, y = bbox[0], bbox[3]

                    # Paragraphe multi-lignes : rendu via boîte à retour à la
                    # ligne automatique, avec ajustement de taille au paragraphe.
                    if block.get("multiline") and translated:
                        if abs(rotation) <= 1.0:
                            self._insert_paragraph(
                                new_page, bbox, origin, translated, font_name,
                                font_raw, orig_size, color, is_list,
                                bullet_char, bullet_font or font_raw,
                                align=block.get("align", 0),
                                first_x=block.get("first_x"),
                                bullet_origin=bullet_origin,
                                min_size=min_font_size
                            )
                            continue
                        # Cellule verticale (texte pivoté ≈ 90°/270°)
                        rot_norm = int(round(rotation / 90.0)) * 90 % 360
                        if rot_norm in (90, 270):
                            self._insert_rotated_paragraph(
                                new_page, bbox, translated, font_name,
                                font_raw, orig_size, color,
                                block.get("align", 0), rot_norm,
                                min_size=min_font_size
                            )
                            continue

                    # Largeur du conteneur : bbox d'origine, étendue à la
                    # largeur de colonne si des blocs alignés (même x0) plus
                    # larges existent — bornée par le premier bloc à droite
                    # (passe 2a). La réduction de police ne s'applique
                    # qu'ensuite, si même cette largeur ne suffit pas.
                    max_width = ext_widths.get(id(block), abs(bbox[2] - bbox[0]))
                    if max_width < 2:
                        max_width = block.get("avail_width",
                                              page_data.get("width", 595) - x)

                    fontsize = self._fit_fontsize(translated, font_name, max_width, orig_size,
                                                  min_size=min_font_size)

                    text_x   = x
                    if is_list and bullet_char:
                        bullet_raw = bullet_font or font_raw
                        # Position de la puce : son marqueur séparé si connu
                        # (ex. « O » ZapfDingbats à gauche), sinon le début du
                        # texte (puce collée extraite du texte).
                        if bullet_origin and len(bullet_origin) >= 2:
                            bx, by, separate = bullet_origin[0], bullet_origin[1], True
                        else:
                            bx, by, separate = x, y, False

                        bullet_w = self._text_length(
                            bullet_char, fontsize, font_name, bullet_raw
                        )
                        if bullet_w < 2:
                            bullet_w = fontsize * 0.6

                        # Rend la puce avec sa police d'origine (losange ❖, etc.).
                        bullet_ok = self._insert_text_smart(
                            new_page, (bx, by), bullet_char, fontsize,
                            font_name, bullet_raw, color, rotation
                        )
                        if not bullet_ok:
                            try:
                                new_page.insert_text(
                                    (bx, by), "•", fontsize=fontsize,
                                    fontname=font_name, color=color
                                )
                                bullet_w = fitz.get_text_length(
                                    "•", fontname=font_name, fontsize=fontsize
                                )
                            except Exception:
                                bullet_w = fontsize * 0.6

                        if not separate:
                            # Puce collée : on décale le texte après la puce.
                            text_x = x + bullet_w + fontsize * 0.3
                            max_width = max_width - bullet_w - fontsize * 0.3
                        # Marqueur séparé : le texte garde sa position d'origine.

                    text_inserted = self._insert_text_smart(
                        new_page, (text_x, y), translated, fontsize,
                        font_name, font_raw, color, rotation
                    )

                    if text_inserted and is_underline and translated:
                        self._draw_underline(
                            new_page, (text_x, y), translated,
                            font_name, fontsize, color, rotation
                        )

            original_doc.close()
            new_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
            new_doc.close()
            self._cleanup_temp()

            if progress_callback:
                progress_callback(f"✓ PDF généré → {output_pdf}")

            return True, f"PDF traduit généré : {output_pdf}"

        except Exception as e:
            return False, f"Erreur réinjection : {str(e)}"

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES PRIVÉS
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _split_group_runs(grp):
        """Valide une clé de paragraphe IA par deux propriétés UNIVERSELLES
        d'un paragraphe wrappé (valables pour tout document, aucune règle
        spécifique) :
          • taille de police homogène entre fragments (tolérance 15 %) —
            un paragraphe ne mélange jamais 80 pt et 12 pt ;
          • baselines consécutives — l'écart entre deux fragments successifs
            ne dépasse pas ~2.5 × la taille (un numéro de page à 300 pt du
            texte n'est jamais sa continuation).
        Découpe le groupe en sous-suites respectant ces propriétés ; les
        fragments isolés résultants sont rendus individuellement à leur
        position d'origine."""
        def base(b):
            o = b.get("origin")
            return o[1] if o and len(o) >= 2 else b["bbox"][3]
        ordered = sorted(grp, key=lambda b: (round(base(b), 1), b["bbox"][0]))
        runs = [[ordered[0]]]
        for b in ordered[1:]:
            prev = runs[-1][-1]
            s1, s2 = prev.get("size", 12), b.get("size", 12)
            same_size = min(s1, s2) / max(1e-6, max(s1, s2)) >= 0.85
            gap = base(b) - base(prev)
            near = gap <= 2.5 * max(s1, s2) + 0.5
            if same_size and near:
                runs[-1].append(b)
            else:
                runs.append([b])
        return runs

    def _render_paragraph_group(self, page, grp, solo_extents=None, ext_x1=None):
        """Rend un groupe de blocs partageant la même paragraph_key (clé
        attribuée par l'IA à la traduction) dans un conteneur UNIQUE :

          • conteneur = rectangle englobant des bbox d'ORIGINE des membres
            (min x0, min y0, max x1, max y1 — tangent aux bords extrêmes) ;
          • le texte traduit de chaque fragment est réinjecté dans ce conteneur
            AVEC SA PROPRE mise en forme extraite (police, taille, couleur,
            soulignement) — aucune fusion de styles ;
          • le flux est recalculé mot à mot : retour à la ligne au bord droit
            du conteneur, interligne dérivé des baselines d'origine du groupe ;
          • le paragraphe ne sort JAMAIS de l'empreinte d'origine : si le texte
            traduit dépasse le bas du conteneur, la police de TOUS les fragments
            est réduite du même facteur (recherche binaire, plancher 60 %) —
            jamais de débordement ni de superposition avec les blocs voisins ;
          • les césures de fin de ligne sont recollées entre fragments
            (« mo- » + « dèle » → « modèle » — règle typographique générale).
        """
        # Ordre de lecture des fragments : baseline puis x.
        def _base(b):
            o = b.get("origin")
            return o[1] if o and len(o) >= 2 else b["bbox"][3]
        grp = sorted(grp, key=lambda b: (round(_base(b), 1), b["bbox"][0]))

        x0 = min(b["bbox"][0] for b in grp)
        y0 = min(b["bbox"][1] for b in grp)
        x1 = max(b["bbox"][2] for b in grp)
        y1 = max(b["bbox"][3] for b in grp)
        # Largeur de colonne : le conteneur peut s'étendre à droite jusqu'au
        # bord max observé parmi les paragraphes alignés sur le même x0
        # (calculé par l'appelant, déjà borné par les obstacles à droite).
        if ext_x1 is not None and ext_x1 > x1:
            x1 = ext_x1

        # Interligne d'origine : écart médian entre baselines distinctes du
        # groupe ; à défaut (fragments sur une seule ligne), 1.2 × la plus
        # grande taille du groupe.
        max_size = max(b.get("size", 12) for b in grp)
        baselines = sorted({round(_base(b), 1) for b in grp})
        gaps = [b2 - b1 for b1, b2 in zip(baselines, baselines[1:]) if b2 - b1 > 1.0]
        line_h = sorted(gaps)[len(gaps) // 2] if gaps else 1.2 * max_size

        # Mots stylés, dans l'ordre de lecture. Chaque mot porte le style de
        # SON fragment d'origine. Les césures de fin de ligne sont recollées
        # à la frontière entre fragments : un fragment finissant par « xxx- »
        # suivi d'un fragment commençant par une minuscule = mot coupé par la
        # justification d'origine, reconstitué (« mo- » + « dèle » → « modèle »).
        words = []
        for b in grp:
            t = (b.get("translated_text") or "").strip() or (b.get("text") or "").strip()
            if not t:
                continue
            style = (b.get("font_mapped", "helv"), b.get("font", ""),
                     b.get("size", 12), tuple(b.get("color", [0, 0, 0])),
                     bool(b.get("underline", False)))
            if b.get("is_list_item") and b.get("bullet_char"):
                words.append((b["bullet_char"],
                              (b.get("font_mapped", "helv"),
                               b.get("bullet_font") or b.get("font", ""),
                               b.get("size", 12), style[3], False)))
            frag_words = t.split()
            if (words and frag_words
                    and len(words[-1][0]) > 1 and words[-1][0].endswith("-")
                    and frag_words[0][:1].islower()):
                prev_w, prev_st = words[-1]
                words[-1] = (prev_w[:-1] + frag_words[0], prev_st)
                frag_words = frag_words[1:]
            for w in frag_words:
                words.append((w, style))
        if not words:
            return

        # Décalage de la 1re baseline par rapport au haut du conteneur.
        first_off = max(0.0, _base(grp[0]) - y0)
        # Retrait de 1re ligne : le paragraphe peut être en « L » (1re ligne
        # commençant APRÈS un libellé en ligne — ex. « (À partir d'un jeu de
        # données) » en italique). Le flux démarre au x d'origine du premier
        # fragment ; les lignes suivantes reviennent au bord du conteneur.
        # Sans ça, le texte du groupe s'écrivait PAR-DESSUS le libellé.
        first_indent = max(0.0, grp[0]["bbox"][0] - x0)

        # Anti-chevauchement : si un bloc individuel sur la MÊME baseline
        # (libellé, numéro…) se termine, une fois RENDU, au-delà du début
        # prévu de la 1re ligne (traduction plus large que sa boîte malgré la
        # réduction), le flux démarre après sa fin réelle. Règle générale :
        # vaut pour tout voisin de gauche, quel que soit le document.
        if solo_extents:
            fb = _base(grp[0])
            fsize = grp[0].get("size", 12)
            start_x = x0 + first_indent
            for sx0, sx1, sy, ssize in solo_extents:
                if abs(sy - fb) > 0.5 * max(fsize, ssize):
                    continue          # pas sur la 1re ligne du groupe
                if sx0 <= start_x and sx1 > start_x - 1.0:
                    first_indent = max(first_indent,
                                       sx1 + 0.3 * fsize - x0)

        def layout(scale):
            """Positionne les mots à l'échelle donnée (tailles et interligne
            multipliés par `scale`). Retourne (placements, dernière_baseline)."""
            placements = []
            cx = x0 + first_indent
            cy = y0 + first_off * scale
            lh = line_h * scale
            for w, (fm, fraw, size, color, underline) in words:
                s = size * scale
                ww = self._text_length(w, s, fm, fraw)
                sw = self._text_length(" ", s, fm, fraw) or 0.25 * s
                if cx > x0 and cx + ww > x1 + 0.5:
                    cx = x0
                    cy += lh
                placements.append((w, cx, cy, s, fm, fraw, color, underline))
                cx += ww + sw
            return placements, cy

        # Le paragraphe doit tenir dans son empreinte d'ORIGINE (le conteneur
        # englobant) : à l'échelle 1 d'abord ; s'il déborde en bas, recherche
        # binaire de la plus grande échelle qui tient. Plancher 0.6 (lisibilité) :
        # au-delà, on accepte le résidu plutôt que de rendre le texte illisible.
        placements, last_base = layout(1.0)
        if last_base > y1 + 0.5:
            lo, hi, best = 0.6, 1.0, None
            for _ in range(8):
                mid = (lo + hi) / 2
                pl, lb = layout(mid)
                if lb <= y1 + 0.5:
                    best, lo = pl, mid
                else:
                    hi = mid
            placements = best if best is not None else layout(0.6)[0]

        for w, cx, cy, s, fm, fraw, color, underline in placements:
            if self._insert_text_smart(page, (cx, cy), w, s, fm, fraw, color, 0.0) \
                    and underline:
                self._draw_underline(page, (cx, cy), w, fm, s, color, 0.0)

    def _insert_rotated_text(self, page, point, text, fontsize,
                              font_name, color, angle_deg, fontfile=None):
        try:
            tw = fitz.TextWriter(page.rect)
            font = self._get_font(fontfile) if fontfile else fitz.Font(font_name)
            tw.append(fitz.Point(point), text, fontsize=fontsize, font=font)
            pivot  = fitz.Point(point)
            matrix = fitz.Matrix(angle_deg)
            tw.write_text(page, color=color, morph=(pivot, matrix))
        except Exception:
            page.insert_text(point, text, fontsize=fontsize,
                             fontname=font_name, color=color)

    # ══════════════════════════════════════════════════════════════════════════
    # EMBARQUEMENT DE POLICES UNICODE (symboles, puces, glyphes hors base-14)
    # ══════════════════════════════════════════════════════════════════════════
    # Les 14 polices PDF de base (helv/times/cour) ne couvrent que le Latin-1
    # (≤ U+00FF). Tout glyphe au-delà (puces losange ❖, flèches, symboles…) doit
    # être rendu via une police TrueType embarquée qui contient réellement le
    # glyphe, sinon PyMuPDF le remplace par un caractère de substitution (·).
    _FONT_FILE_MAP = {
        "segoeuisymbol": "seguisym.ttf",
        "seguisym":      "seguisym.ttf",
        "segoeui":       "segoeui.ttf",
        "segoeuiemoji":  "seguiemj.ttf",
        "arial":         "arial.ttf",
        "arialmt":       "arial.ttf",
        "calibri":       "calibri.ttf",
        "cambria":       "cambria.ttc",
        "wingdings":     "wingding.ttf",
        "wingdings2":    "wingdng2.ttf",
        "wingdings3":    "wingdng3.ttf",
        "webdings":      "webdings.ttf",
        "symbol":        "symbol.ttf",
        "timesnewroman": "times.ttf",
        "times":         "times.ttf",
    }
    # Polices de secours Unicode, par ordre de préférence (couvrent les symboles)
    _FALLBACK_FONTS = ["seguisym.ttf", "arial.ttf", "segoeui.ttf", "calibri.ttf"]

    # Familles rendues fidèlement par les 14 polices PDF de base (helv/times/
    # cour) : inutile d'embarquer un fichier — on laisse `_map_font` les gérer.
    _BASE14_FAMILIES = {
        "helvetica", "arial", "helv", "times", "timesnewroman", "timesroman",
        "courier", "couriernew",
    }
    # Familles NON base-14 → fichiers système (regular, bold, italic, bold-italic)
    # pour préserver la police d'origine du document (sa « famille de style »).
    _FONT_FAMILY_FILES = {
        "calibri":     ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
        "carlito":     ("Carlito-Regular.ttf", "Carlito-Bold.ttf",
                        "Carlito-Italic.ttf", "Carlito-BoldItalic.ttf"),
        "cambria":     ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
        "segoeui":     ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
        "georgia":     ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
        "verdana":     ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
        "tahoma":      ("tahoma.ttf", "tahomabd.ttf", "tahoma.ttf", "tahomabd.ttf"),
        "consolas":    ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
        "trebuchetms": ("trebuc.ttf", "trebucbd.ttf", "trebucit.ttf", "trebucbi.ttf"),
        "comicsansms": ("comic.ttf", "comicbd.ttf", "comici.ttf", "comicz.ttf"),
        "couriernew":  ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
        "arialnova":   ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
        "candara":     ("Candara.ttf", "Candarab.ttf", "Candarai.ttf", "Candaraz.ttf"),
        "constantia":  ("constan.ttf", "constanb.ttf", "constani.ttf", "constanz.ttf"),
        "corbel":      ("corbel.ttf", "corbelb.ttf", "corbeli.ttf", "corbelz.ttf"),
        "franklingothicbook": ("frabk.ttf", "frabkit.ttf", "frabkit.ttf", "frabkit.ttf"),
        "century":     ("CENTURY.TTF", "CENTURY.TTF", "CENTURY.TTF", "CENTURY.TTF"),
        "garamond":    ("GARA.TTF", "GARABD.TTF", "GARAIT.TTF", "GARABD.TTF"),
        "bookantiqua": ("BKANT.TTF", "BKANT.TTF", "BKANT.TTF", "BKANT.TTF"),
    }
    # Polices web/Google/Office absentes de Windows → substitut système de la
    # MÊME CLASSE (serif/sans/mono) pour préserver l'aspect (à défaut d'avoir
    # le fichier exact ; déposer le vrai .ttf dans backend/fonts/ pour l'exact).
    _FONT_SIMILAR = {
        # — Serif → Georgia —
        "merriweather": "georgia", "lora": "georgia", "ptserif": "georgia",
        "robotoslab": "georgia", "playfairdisplay": "georgia", "playfair": "georgia",
        "notoserif": "georgia", "sourceserifpro": "georgia", "sourceserif": "georgia",
        "sourceserif4": "georgia", "librebaskerville": "georgia", "crimsontext": "georgia",
        "crimsonpro": "georgia", "ebgaramond": "garamond", "vollkorn": "georgia",
        "bitter": "georgia", "domine": "georgia", "cardo": "georgia", "alegreya": "georgia",
        "frankruhllibre": "georgia", "spectral": "georgia", "cormorant": "georgia",
        "cormorantgaramond": "garamond", "gelasio": "georgia", "zillaslab": "georgia",
        "rokkitt": "georgia", "slabo": "georgia", "slabo27px": "georgia",
        "notoserifdisplay": "georgia", "lustria": "georgia", "martel": "georgia",
        "neuton": "georgia", "faustina": "georgia",
        # — Sans → Segoe UI —
        "opensans": "segoeui", "roboto": "segoeui", "lato": "segoeui",
        "montserrat": "segoeui", "sourcesanspro": "segoeui", "sourcesans": "segoeui",
        "sourcesans3": "segoeui", "notosans": "segoeui", "notosansdisplay": "segoeui",
        "nunito": "segoeui", "nunitosans": "segoeui", "poppins": "segoeui",
        "raleway": "segoeui", "inter": "segoeui", "worksans": "segoeui",
        "ubuntu": "segoeui", "rubik": "segoeui", "karla": "segoeui", "dmsans": "segoeui",
        "manrope": "segoeui", "firasans": "segoeui", "ptsans": "segoeui", "hind": "segoeui",
        "oxygen": "segoeui", "cabin": "segoeui", "quicksand": "segoeui",
        "josefinsans": "segoeui", "barlow": "segoeui", "heebo": "segoeui",
        "arimo": "segoeui", "archivo": "segoeui", "mulish": "segoeui", "muli": "segoeui",
        "assistant": "segoeui", "catamaran": "segoeui", "exo": "segoeui", "exo2": "segoeui",
        "titilliumweb": "segoeui", "titillium": "segoeui", "kanit": "segoeui",
        "prompt": "segoeui", "sarabun": "segoeui", "signika": "segoeui",
        "overpass": "segoeui", "jost": "segoeui", "urbanist": "segoeui",
        "figtree": "segoeui", "plusjakartasans": "segoeui", "publicsans": "segoeui",
        "sora": "segoeui", "spacegrotesk": "segoeui", "leaguespartan": "segoeui",
        "librefranklin": "segoeui", "mukta": "segoeui", "helveticaneue": "segoeui",
        # — Mono → Consolas —
        "robotomono": "consolas", "sourcecodepro": "consolas", "firacode": "consolas",
        "firamono": "consolas", "jetbrainsmono": "consolas", "inconsolata": "consolas",
        "spacemono": "consolas", "ibmplexmono": "consolas", "ubuntumono": "consolas",
        "courierprime": "consolas", "cousine": "consolas", "anonymouspro": "consolas",
        "overpassmono": "consolas",
    }
    _BUNDLED_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    @staticmethod
    def _system_font_dir():
        return os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")

    @classmethod
    def _norm_font(cls, font_raw):
        """Normalise un nom de police : retire le préfixe de sous-ensemble
        (« ABCDEE+ »), les suffixes de style et la ponctuation.

        L'ordre des tokens importe : les graisses composées (« semibold »,
        « semilight », « extrabold »…) doivent être retirées AVANT leurs
        composants (« bold », « light »), sinon « SegoeUI-Semilight » devient
        « segoeuisemi » au lieu de « segoeui » et la famille n'est plus
        reconnue (repli erroné sur Helvetica)."""
        name = font_raw.split("+")[-1] if "+" in font_raw else font_raw
        name = name.lower()
        for token in ("bolditalic", "extrabold", "ultrabold", "semibold",
                      "demibold", "extralight", "ultralight", "semilight",
                      "bold", "italic", "regular", "oblique", "light",
                      "black", "heavy", "medium", "thin", "condensed",
                      "narrow", "mt", "ps"):
            name = name.replace(token, "")
        return "".join(ch for ch in name if ch.isalnum())

    def _get_font(self, fontfile):
        font = self._font_cache.get(fontfile)
        if font is None:
            font = fitz.Font(fontfile=fontfile)
            self._font_cache[fontfile] = font
        return font

    def _bundled_index(self):
        """Indexe (paresseusement) le dossier backend/fonts/ : permet à
        l'utilisateur de déposer les VRAIES polices du document (Merriweather,
        Open Sans…) pour une fidélité exacte. Clé = famille normalisée →
        {(bold, italic): chemin}."""
        if self._bundled is not None:
            return self._bundled
        idx = {}
        d = self._BUNDLED_FONT_DIR
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if not fn.lower().endswith((".ttf", ".otf", ".ttc")):
                    continue
                stem = os.path.splitext(fn)[0]
                low = stem.lower()
                bold = any(k in low for k in ("bold", "black", "heavy", "semibold"))
                italic = any(k in low for k in ("italic", "oblique"))
                idx.setdefault(self._norm_font(stem), {})[(bold, italic)] = \
                    os.path.join(d, fn)
        self._bundled = idx
        return idx

    def _bundled_lookup(self, key, bold, italic):
        variants = self._bundled_index().get(key)
        if not variants:
            return None
        for want in ((bold, italic), (bold, False), (False, italic), (False, False)):
            path = variants.get(want)
            if path and os.path.exists(path):
                try:
                    self._get_font(path)
                except Exception:
                    continue
                return os.path.splitext(os.path.basename(path))[0], path
        # n'importe quelle variante disponible
        for path in variants.values():
            if os.path.exists(path):
                return os.path.splitext(os.path.basename(path))[0], path
        return None

    # Graisses intermédiaires (Semilight, Light, Semibold, Black…) : fichiers
    # système exacts par famille. La résolution standard ne connaît que
    # regular/bold/italic/bold-italic, ce qui rendait Semilight en Regular
    # (plus épais) et Semibold en Bold (plus gras) → texte d'aspect « plus
    # gras » que l'original. Clé = (fichier regular, fichier italique).
    _FONT_WEIGHT_FILES = {
        "segoeui": {
            "semilight": ("segoeuisl.ttf", "seguisli.ttf"),
            "light":     ("segoeuil.ttf",  "seguili.ttf"),
            "semibold":  ("seguisb.ttf",   "seguisbi.ttf"),
            "black":     ("seguibl.ttf",   "seguibli.ttf"),
        },
        "calibri": {
            "light":     ("calibril.ttf",  "calibrili.ttf"),
        },
    }
    # Détection de graisse dans le nom brut : composées AVANT simples.
    _WEIGHT_TOKENS = ("semilight", "extralight", "ultralight", "demibold",
                      "semibold", "extrabold", "ultrabold", "light", "black",
                      "heavy", "thin", "medium")
    # Graisse absente de la famille → graisse la plus proche disponible.
    _WEIGHT_ALIASES = {"demibold": "semibold", "extralight": "light",
                       "ultralight": "light", "thin": "light",
                       "heavy": "black", "extrabold": "black",
                       "ultrabold": "black"}

    def _weight_variant_file(self, key, font_raw, italic):
        """Fichier système de la graisse intermédiaire EXACTE (Semilight,
        Semibold…) si la famille en dispose — None sinon (la résolution
        standard regular/bold prend alors le relais)."""
        weights = self._FONT_WEIGHT_FILES.get(key)
        if not weights:
            return None
        low = (font_raw or "").lower()
        token = next((t for t in self._WEIGHT_TOKENS if t in low), None)
        if not token:
            return None
        pair = weights.get(token) or weights.get(self._WEIGHT_ALIASES.get(token, ""))
        if not pair:
            return None
        fdir = self._system_font_dir()
        for cand in ((pair[1] if italic else pair[0]), pair[0]):
            path = os.path.join(fdir, cand)
            if not os.path.exists(path):
                continue
            try:
                self._get_font(path)
            except Exception:
                continue
            return os.path.splitext(cand)[0], path
        return None

    def _family_variant_file(self, key, bold, italic):
        """Fichier système pour une famille connue de `_FONT_FAMILY_FILES`,
        variante demandée puis repli sur le regular."""
        variants = self._FONT_FAMILY_FILES.get(key)
        if not variants:
            return None
        idx = (2 if italic else 0) + (1 if bold else 0)
        fdir = self._system_font_dir()
        for cand in (variants[idx], variants[0]):
            path = os.path.join(fdir, cand)
            if not os.path.exists(path):
                continue
            try:
                self._get_font(path)
            except Exception:
                continue
            return os.path.splitext(cand)[0], path
        return None

    def _resolve_family_font(self, font_raw):
        """Retourne (fontkey, fontfile) reproduisant la FAMILLE d'origine
        (`font_raw`), variante gras/italique comprise — ou None si base-14
        suffit (Helvetica/Times/Courier) ou si rien n'est trouvé.

        Ordre de préférence :
          1. backend/fonts/ — vraie police du document déposée par l'utilisateur
             (fidélité exacte, même pour Merriweather/Open Sans/Roboto…) ;
          2. fichier système de MÊME nom (Calibri, Segoe UI, Verdana…) ;
          3. substitut système de même CLASSE serif/sans/mono (`_FONT_SIMILAR`)
             pour les polices web absentes du système.
        Sans ça, toute police non base-14 était écrasée en Helvetica."""
        if not font_raw:
            return None
        low = font_raw.lower()
        bold = any(k in low for k in ("bold", "black", "heavy", "semibold"))
        italic = any(k in low for k in ("italic", "oblique"))
        key = self._norm_font(font_raw)

        # 1. police exacte déposée dans backend/fonts/ (prioritaire)
        r = self._bundled_lookup(key, bold, italic)
        if r:
            return r
        # 1bis. graisse intermédiaire exacte (Semilight, Semibold, Light…)
        r = self._weight_variant_file(key, font_raw, italic)
        if r:
            return r
        if key in self._BASE14_FAMILIES:
            return None  # base-14 fidèle, inutile d'embarquer
        # 2. police système de même nom
        r = self._family_variant_file(key, bold, italic)
        if r:
            return r
        # 3. substitut système de même classe (serif/sans/mono)
        sim = self._FONT_SIMILAR.get(key)
        if sim:
            r = self._family_variant_file(sim, bold, italic)
            if r:
                return r
        return None

    # ── Téléchargement automatique des polices manquantes (Google Fonts) ──────
    _GOOGLE_SLUG = {  # corrections clé normalisée → dossier du dépôt google/fonts
        "sourcesanspro": "sourcesans3", "sourceserifpro": "sourceserif4",
        "ptsans": "ptsans", "ptserif": "ptserif",
    }

    def _dl_state_path(self):
        return os.path.join(self._BUNDLED_FONT_DIR, ".dl_failed.json")

    def _dl_tried(self):
        if self._font_dl_tried is None:
            self._font_dl_tried = set()
            try:
                with open(self._dl_state_path(), encoding="utf-8") as f:
                    self._font_dl_tried = set(json.load(f))
            except Exception:
                pass
        return self._font_dl_tried

    def _mark_dl_failed(self, key):
        tried = self._dl_tried()
        tried.add(key)
        try:
            os.makedirs(self._BUNDLED_FONT_DIR, exist_ok=True)
            with open(self._dl_state_path(), "w", encoding="utf-8") as f:
                json.dump(sorted(tried), f)
        except Exception:
            pass

    def _ensure_font(self, font_raw, progress_callback=None):
        """Si la famille `font_raw` n'est PAS déjà reproductible fidèlement
        (bundled / système / base-14 / symbole), lance EN ARRIÈRE-PLAN le
        téléchargement de la vraie police depuis Google Fonts vers
        backend/fonts/ — **sans bloquer** : la sortie courante utilise le
        substitut de même classe (serif/sans), les traductions suivantes
        utiliseront la police exacte une fois téléchargée. Best-effort : toute
        erreur (hors-ligne, police absente du dépôt, fonttools absent…) est
        silencieuse."""
        if not self.auto_download_fonts:
            return
        if self._font_resolution_info(font_raw)["exact"]:
            return  # déjà fidèle, rien à faire
        key = self._norm_font(font_raw or "")
        if not key or key in self._dl_tried():
            return
        # dédupe inter-threads : un seul téléchargement par famille à la fois
        with _FONT_DL_LOCK:
            if key in _FONT_DL_INFLIGHT:
                return
            _FONT_DL_INFLIGHT.add(key)

        def _worker():
            ok = False
            try:
                ok = self._download_google_font(key)
            except Exception:
                ok = False
            finally:
                if ok:
                    self._bundled = None  # ré-indexe backend/fonts/
                    if progress_callback:
                        try:
                            progress_callback(
                                f"✓ Police téléchargée : {font_raw} → backend/fonts/ "
                                "(appliquée à la prochaine traduction)")
                        except Exception:
                            pass
                else:
                    self._dl_tried().add(key)
                    self._mark_dl_failed(key)
                with _FONT_DL_LOCK:
                    _FONT_DL_INFLIGHT.discard(key)

        if progress_callback:
            try:
                progress_callback(
                    f"⏳ Téléchargement de « {font_raw} » en arrière-plan "
                    "(substitut utilisé en attendant)…")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _download_google_font(self, key):
        """Télécharge la police variable depuis le dépôt google/fonts et en
        extrait des instances statiques Regular/Bold (+ Italic/BoldItalic) via
        fonttools, enregistrées dans backend/fonts/. Renvoie True si au moins
        un fichier a été produit."""
        import urllib.request
        import urllib.parse
        import io
        try:
            from fontTools.ttLib import TTFont
            from fontTools.varLib.instancer import instantiateVariableFont
        except Exception:
            return False  # fonttools absent → pas de téléchargement (substitut)

        slug = self._GOOGLE_SLUG.get(key, key)
        ua = {"User-Agent": "Mozilla/5.0"}

        def fetch(url, as_json=False):
            headers = dict(ua)
            if as_json:
                headers["Accept"] = "application/vnd.github+json"
            req = urllib.request.Request(url, headers=headers)
            data = urllib.request.urlopen(req, timeout=25).read()
            return json.loads(data) if as_json else data

        items = None
        for lic in ("ofl", "apache", "ufl"):
            try:
                items = fetch(
                    f"https://api.github.com/repos/google/fonts/contents/{lic}/{slug}",
                    as_json=True)
                break
            except Exception:
                continue
        if not items or not isinstance(items, list):
            return False

        ttfs = [i for i in items if i.get("name", "").lower().endswith(".ttf")]
        if not ttfs:
            return False

        def pick(italic):
            cands = [i for i in ttfs
                     if ("italic" in i["name"].lower()) == italic]
            if not cands:
                return None
            var = [i for i in cands if "[" in i["name"]]      # police variable
            if var:
                return var[0]
            reg = [i for i in cands if "regular" in i["name"].lower()]
            return (reg or cands)[0]

        os.makedirs(self._BUNDLED_FONT_DIR, exist_ok=True)
        fam = "".join(ch for ch in key if ch.isalnum())
        saved = False

        _WEIGHT_WORDS = ("thin", "extralight", "ultralight", "light", "regular",
                         "medium", "semibold", "demibold", "extrabold", "ultrabold",
                         "bold", "black", "heavy", "italic", "oblique")

        def finalize(f, bold, italic):
            """Régénère la table de noms + bits de style de l'instance pour que
            chaque variante soit une police autonome correctement identifiée
            (sinon Regular et Bold partagent le même nom interne → risque de
            déduplication à l'enregistrement = gras rendu en regular)."""
            try:
                nm = f["name"]
                base = nm.getDebugName(16) or nm.getDebugName(1) or fam
                toks = [w for w in base.replace("-", " ").split()
                        if w.lower() not in _WEIGHT_WORDS]
                base = " ".join(toks).strip() or fam
                sub = ("Bold Italic" if bold and italic else "Bold" if bold
                       else "Italic" if italic else "Regular")
                full = base if sub == "Regular" else f"{base} {sub}"
                ps = base.replace(" ", "") + "-" + sub.replace(" ", "")
                for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
                    nm.setName(base, 1, pid, eid, lid)
                    nm.setName(sub, 2, pid, eid, lid)
                    nm.setName(full, 4, pid, eid, lid)
                    nm.setName(ps, 6, pid, eid, lid)
                    nm.setName(base, 16, pid, eid, lid)
                    nm.setName(sub, 17, pid, eid, lid)
                if "OS/2" in f:
                    sel = f["OS/2"].fsSelection & ~((1 << 0) | (1 << 5) | (1 << 6))
                    if bold:
                        sel |= (1 << 5)
                    if italic:
                        sel |= (1 << 0)
                    if not bold and not italic:
                        sel |= (1 << 6)
                    f["OS/2"].fsSelection = sel
                if "head" in f:
                    mac = f["head"].macStyle & ~0b11
                    if bold:
                        mac |= 0b01
                    if italic:
                        mac |= 0b10
                    f["head"].macStyle = mac
            except Exception:
                pass

        def gen(item, variants):
            nonlocal saved
            if not item:
                return
            try:
                raw = fetch(item["download_url"])
            except Exception:
                return
            for wght, suffix, bold, italic in variants:
                try:
                    f = TTFont(io.BytesIO(raw))
                    if "fvar" in f:
                        axes = {a.axisTag: a.defaultValue for a in f["fvar"].axes}
                        if "wght" in axes:
                            axes["wght"] = wght
                        instantiateVariableFont(f, axes, inplace=True)
                    finalize(f, bold, italic)
                    out = io.BytesIO()
                    f.save(out)
                    with open(os.path.join(self._BUNDLED_FONT_DIR,
                                           f"{fam}-{suffix}.ttf"), "wb") as fh:
                        fh.write(out.getvalue())
                    saved = True
                except Exception:
                    pass

        gen(pick(False), [(400, "Regular", False, False), (700, "Bold", True, False)])
        gen(pick(True), [(400, "Italic", False, True), (700, "BoldItalic", True, True)])
        return saved

    def _font_resolution_info(self, font_raw):
        """Décrit COMMENT le moteur rendra `font_raw` (sans rien installer) :
        - method : bundled | base14 | system | similar | fallback
        - substitute : famille de remplacement (si non exact), sinon None
        - exact : True si la famille d'origine est reproduite fidèlement."""
        low = (font_raw or "").lower()
        bold = any(k in low for k in ("bold", "black", "heavy", "semibold"))
        italic = any(k in low for k in ("italic", "oblique"))
        key = self._norm_font(font_raw or "")
        # Polices symbole (puces ❖, Wingdings…) : rendues fidèlement via la
        # police builtin (zadb/symb) ou Segoe UI Symbol embarquée — pas un
        # substitut de texte, donc pas de fausse alerte « Helvetica ».
        if (key in BULLET_FONT_NAMES or key in SYMBOL_BUILTIN_FONT
                or key in ("segoeuisymbol", "seguisym")):
            return {"method": "symbol", "substitute": None, "exact": True}
        if self._bundled_lookup(key, bold, italic):
            return {"method": "bundled", "substitute": None, "exact": True}
        if self._weight_variant_file(key, font_raw, italic):
            return {"method": "system", "substitute": None, "exact": True}
        if key in self._BASE14_FAMILIES:
            return {"method": "base14", "substitute": None, "exact": True}
        if self._family_variant_file(key, bold, italic):
            return {"method": "system", "substitute": None, "exact": True}
        sim = self._FONT_SIMILAR.get(key)
        if sim and self._family_variant_file(sim, bold, italic):
            return {"method": "similar", "substitute": sim, "exact": False}
        return {"method": "fallback", "substitute": "helvetica", "exact": False}

    def _font_inventory(self, doc, progress_callback=None):
        """Inventaire des polices du PDF, calculé À L'EXTRACTION (le document est
        ouvert). Pour chaque police : embarquée ? sous-ensemble ? son sous-
        ensemble couvre-t-il l'ASCII (sinon glyphes manquants à la traduction) ?
        et comment le moteur la rendra (exacte / substitut / base-14). Tente au
        passage de TÉLÉCHARGER automatiquement les polices manquantes (Google
        Fonts → backend/fonts/) pour que le rendu soit ensuite fidèle."""
        STD = list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)) + list(range(0x30, 0x3A))
        seen = {}
        for pno in range(len(doc)):
            try:
                flist = doc[pno].get_fonts(full=True)
            except Exception:
                continue
            for f in flist:
                xref, ext, ftype, basefont = f[0], f[1], f[2], f[3]
                name = basefont.split("+")[-1] if "+" in basefont else basefont
                if name in seen:
                    continue
                embedded = bool(xref) and ext not in ("", "n/a")
                subset = "+" in basefont
                complete = None
                if embedded and xref:
                    try:
                        buf = doc.extract_font(xref)[3]
                        if buf:
                            fnt = fitz.Font(fontbuffer=buf)
                            complete = all(fnt.has_glyph(cp) for cp in STD)
                    except Exception:
                        complete = None
                # Tente le téléchargement de la vraie police si non fidèle.
                self._ensure_font(name, progress_callback)
                info = self._font_resolution_info(name)
                seen[name] = {
                    "name": name,
                    "embedded": embedded,
                    "subset": subset,
                    "embedded_covers_ascii": complete,
                    "type": ftype,
                    "render_as": info["substitute"] or name,
                    "match": info["method"],
                    "exact": info["exact"],
                }
        return list(seen.values())

    def _embed_font_for(self, text, font_raw):
        """Retourne (fontkey, fontfile) de la police à embarquer pour rendre
        `text` fidèlement, ou None si une police de base suffit.

        1. Texte purement latin (≤ U+00FF) → on embarque la police de la FAMILLE
           d'origine si elle n'est pas base-14 (préservation de la police) ;
           sinon None (base-14 fidèle).
        2. Texte contenant des glyphes hors base-14 (puces ❖, symboles…) → on
           choisit une police qui couvre réellement ces glyphes (famille
           d'origine si elle les contient, sinon police de secours Unicode)."""
        fam = self._resolve_family_font(font_raw)
        needed = {ord(c) for c in text if ord(c) > 0xFF}
        if not needed:
            return fam  # latin pur : famille d'origine (ou None → base-14)

        fdir = self._system_font_dir()
        candidates = []
        if fam is not None:
            candidates.append(fam[1])
        mapped = self._FONT_FILE_MAP.get(self._norm_font(font_raw or ""))
        if mapped:
            candidates.append(os.path.join(fdir, mapped))
        candidates += [os.path.join(fdir, f) for f in self._FALLBACK_FONTS]

        seen, ordered = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)

        first_valid = None
        for path in ordered:
            if not os.path.exists(path):
                continue
            try:
                font = self._get_font(path)
            except Exception:
                continue
            if first_valid is None:
                first_valid = path
            try:
                if all(font.has_glyph(cp) for cp in needed):
                    return os.path.splitext(os.path.basename(path))[0], path
            except Exception:
                continue
        # Aucune police ne couvre tous les glyphes : on prend la première valide
        if first_valid is not None:
            return os.path.splitext(os.path.basename(first_valid))[0], first_valid
        return None

    def _insert_text_smart(self, page, point, text, fontsize,
                           font_mapped, font_raw, color, rotation):
        """Insère du texte en embarquant une police Unicode si la police de base
        ne peut pas représenter certains glyphes. Retourne True si écrit."""
        # Police symbole (ZapfDingbats/Symbol…) : rendue via la police PDF de
        # base correspondante (zadb/symb) pour préserver le glyphe (ex. puce ❖).
        sym = SYMBOL_BUILTIN_FONT.get(self._norm_font(font_raw or ""))
        if sym is not None:
            try:
                if abs(rotation) > 1.0:
                    self._insert_rotated_text(page, point, text, fontsize,
                                              sym, color, rotation)
                else:
                    page.insert_text(point, text, fontsize=fontsize,
                                     fontname=sym, color=color)
                return True
            except Exception:
                pass

        embed = self._embed_font_for(text, font_raw)
        if embed is not None:
            fontkey, fontfile = embed
            try:
                if abs(rotation) > 1.0:
                    self._insert_rotated_text(page, point, text, fontsize,
                                              font_mapped, color, rotation,
                                              fontfile=fontfile)
                else:
                    page.insert_text(point, text, fontsize=fontsize,
                                     fontname=fontkey, fontfile=fontfile,
                                     color=color)
                return True
            except Exception:
                pass  # bascule sur le chemin base-14 ci-dessous

        try:
            if abs(rotation) > 1.0:
                self._insert_rotated_text(page, point, text, fontsize,
                                          font_mapped, color, rotation)
            else:
                page.insert_text(point, text, fontsize=fontsize,
                                 fontname=font_mapped, color=color)
            return True
        except Exception:
            try:
                page.insert_text(point, text, fontsize=max(fontsize, 6),
                                 fontname="helv", color=(0, 0, 0))
                return True
            except Exception:
                return False

    def _text_length(self, text, fontsize, font_mapped, font_raw):
        """Largeur du texte, en tenant compte d'une éventuelle police embarquée."""
        sym = SYMBOL_BUILTIN_FONT.get(self._norm_font(font_raw or ""))
        if sym is not None:
            try:
                return fitz.get_text_length(text, fontname=sym, fontsize=fontsize)
            except Exception:
                pass
        embed = self._embed_font_for(text, font_raw)
        if embed is not None:
            try:
                return self._get_font(embed[1]).text_length(text, fontsize=fontsize)
            except Exception:
                pass
        try:
            return fitz.get_text_length(text, fontname=font_mapped, fontsize=fontsize)
        except Exception:
            return fontsize * 0.5 * len(text)

    @staticmethod
    def _draw_underline(page, point, text, font_name, fontsize, color, rotation):
        try:
            x0, y0 = point[0], point[1]
            text_w = fitz.get_text_length(text, fontname=font_name, fontsize=fontsize)
            if text_w < 1:
                return
            underline_y = y0 + 1.5
            line_width = max(0.4, fontsize * 0.04)

            if abs(rotation) <= 1.0:
                page.draw_line(
                    (x0, underline_y), (x0 + text_w, underline_y),
                    color=color, width=line_width
                )
            else:
                rad = math.radians(rotation)
                dx = text_w * math.cos(rad)
                dy = text_w * math.sin(rad)
                page.draw_line(
                    (x0, underline_y), (x0 + dx, underline_y + dy),
                    color=color, width=line_width
                )
        except Exception:
            pass

    @staticmethod
    def _dir_to_angle(dir_vec: tuple) -> float:
        dx, dy = dir_vec[0], dir_vec[1]
        angle = math.degrees(math.atan2(-dy, dx))
        return round(angle, 1)

    @staticmethod
    def _int_to_rgb(color_int: int) -> list:
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8)  & 0xFF) / 255.0
        b = ( color_int        & 0xFF) / 255.0
        return [round(r, 4), round(g, 4), round(b, 4)]

    @staticmethod
    def _map_font(font_name: str, bold: bool, italic: bool) -> str:
        fn = font_name.lower()
        is_times   = any(k in fn for k in ("times", "serif", "georgia", "garamond"))
        is_courier = any(k in fn for k in ("courier", "mono", "consol", "fixedsys", "terminal"))

        if is_courier:
            if bold and italic: return "coit"
            if bold:            return "cobo"
            if italic:          return "coit"
            return "cour"
        if is_times:
            if bold and italic: return "tibo"
            if bold:            return "tibo"
            if italic:          return "tiit"
            return "tiro"
        if bold and italic: return "heit"
        if bold:            return "hebo"
        if italic:          return "heit"
        return "helv"

    @staticmethod
    def _detect_bullet(text: str) -> bool:
        if not text:
            return False
        stripped = text.lstrip()
        if stripped and stripped[0] in BULLET_CHARS:
            return True
        if stripped.startswith("- ") or stripped.startswith("* "):
            return True
        return False

    @staticmethod
    def _extract_bullet(text: str) -> tuple:
        if not text:
            return None, text
        stripped = text.lstrip()
        lead = text[:len(text) - len(stripped)]
        if stripped and stripped[0] in BULLET_CHARS:
            return stripped[0], lead + stripped[1:].lstrip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            return stripped[0], lead + stripped[2:].lstrip()
        return None, text

    # ══════════════════════════════════════════════════════════════════════════
    # GROUPEMENT EN PARAGRAPHES (fusion des lignes wrap d'une même phrase)
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _span_style_sig(span, font_mapped):
        fl = span.get("flags", 0)
        return (font_mapped, round(span.get("size", 12), 1),
                span.get("color", 0),
                bool(fl & FLAG_BOLD), bool(fl & FLAG_ITALIC))

    def _is_marker_span(self, span):
        """Vrai si le span est un marqueur de puce isolé : soit un glyphe puce
        connu, soit un span court dans une police symbole (ex. « O » en
        ZapfDingbats, rendu comme ❖). À ne pas confondre avec « ❖ texte… »
        collé dans un même span (géré par _extract_bullet)."""
        t = span.get("text", "").strip()
        if not t or len(t) > 3:
            return False
        if self._norm_font(span.get("font", "")) in BULLET_FONT_NAMES:
            return True
        return t[0] in BULLET_CHARS

    def _group_paragraphs(self, items, block_w):
        """REGROUPEMENT DÉSACTIVÉ : chaque span est traité comme un bloc
        indépendant, rendu tel quel à sa position d'origine. Aucune fusion de
        lignes, aucun rattachement de puce, aucun calcul intelligent — fidélité
        maximale à la géométrie d'origine du document."""
        groups = []
        for span, rot in sorted(items, key=lambda it: (round(it[0]["origin"][1], 1),
                                                       it[0]["bbox"][0])):
            fl = span.get("flags", 0)
            fm = self._map_font(span.get("font", "Helvetica"),
                                bool(fl & FLAG_BOLD), bool(fl & FLAG_ITALIC))
            groups.append({"members": [(span, rot, fm)],
                           "sig": None, "rot": rot, "bullet": None})
        return groups, []

    @staticmethod
    def _group_geom(group):
        """Géométrie de lecture d'un groupe : 1er/dernier span (baseline puis x),
        étendue x, taille. Sert à décider la fusion inter-blocs."""
        sp = [m[0] for m in group["members"]]
        ordered = sorted(sp, key=lambda s: (round(s["origin"][1], 1), s["bbox"][0]))
        first, last = ordered[0], ordered[-1]
        return {
            "x0":         min(s["bbox"][0] for s in sp),
            "x1":         max(s["bbox"][2] for s in sp),
            "first_base": first["origin"][1],
            "last_base":  last["origin"][1],
            "first_x0":   first["bbox"][0],
            "last_x1":    last["bbox"][2],
            "size":       first.get("size", 12),
        }

    @staticmethod
    def _group_text(group) -> str:
        """Concatène le texte de tous les spans d'un groupe, triés visuellement."""
        members = group["members"]
        ordered = sorted(members,
                         key=lambda m: (round(m[0]["origin"][1], 1), m[0]["bbox"][0]))
        return " ".join(
            m[0].get("text", "").strip()
            for m in ordered if m[0].get("text", "").strip()
        )

    def _llm_validate_merges(self, pairs: list) -> list:
        """Envoie au LLM les paires de groupes géométriquement ambiguës et retourne
        la liste des indices (dans `pairs`) que le LLM juge appartenir au même
        paragraphe. Retourne [] si le LLM est absent ou en cas d'erreur."""
        if not pairs or self._llm_client is None:
            return []

        items = []
        for i, (ga, gb) in enumerate(pairs):
            items.append({
                "id": i,
                "fin_a":    self._group_text(ga)[-150:],
                "debut_b":  self._group_text(gb)[:150],
            })

        prompt = (
            "Tu analyses des fragments de texte extraits d'un PDF.\n"
            "Pour chaque paire, détermine si les deux fragments font partie du MÊME "
            "paragraphe logique (continuation de la même phrase ou du même bloc).\n"
            "Réponds UNIQUEMENT avec JSON : "
            "{\"decisions\": [{\"id\": 0, \"merge\": true}, ...]}\n\n"
            f"Paires :\n{json.dumps(items, ensure_ascii=False)}"
        )
        try:
            resp = self._llm_client.chat.completions.create(
                model=self._llm_model,
                messages=[
                    {"role": "system",
                     "content": "Tu es un expert en analyse de structure de documents PDF."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            return [d["id"] for d in data.get("decisions", []) if d.get("merge")]
        except Exception:
            return []

    def _merge_cross_block(self, groups, line_gap_threshold=1.65):
        """Fusionne les groupes (issus de blocs PyMuPDF distincts) qui forment
        une MÊME phrase / titre / libellé. PyMuPDF éclate souvent une seule
        phrase en plusieurs blocs (espacement, tabulation, retour wrap) ; sans
        cette passe, les fragments restent séparés et espacés, et l'espace libre
        entre eux n'est pas exploité par l'ajustement de taille. Deux cas, avec
        les mêmes garde-fous que le regroupement intra-bloc (#3) et le reflow
        (#6/#7) :
          • même ligne  : même style, même baseline, petit écart horizontal
                          (gros écart = colonnes → jamais fusionné) ;
          • multi-ligne : même style, baselines consécutives, bord régulier
                          commun + recouvrement horizontal (côte-à-côte =
                          colonnes → non fusionné).
        `line_gap_threshold` est calculé par l'appelant à partir des espacements
        intra-paragraphe observés sur la page — aucune constante fixe.
        Conservateur : puces/listes, marqueurs et texte pivoté restent intacts
        (ils passent tels quels)."""
        cand, passthrough = [], []
        for g in groups:
            first_txt = g["members"][0][0].get("text", "").strip()
            if (abs(g.get("rot", 0.0)) <= 1.0 and g.get("bullet") is None
                    and g.get("sig") is not None
                    and not self._detect_bullet(first_txt)):
                cand.append(g)
            else:
                passthrough.append(g)

        # Instantané des positions de tous les groupes (avant fusion) : sert à
        # détecter un bloc intercalé entre deux candidats multi-ligne.
        snapshot = [self._group_geom(g) for g in groups]

        def _has_intervening(ga, gb, size):
            """Vrai si un autre bloc se trouve verticalement entre la dernière
            ligne de a et la première de b, dans leur bande horizontale. Empêche
            d'enchaîner deux paragraphes distincts séparés par un libellé/titre
            (ex. colonne « COMPÉTENCES » : chaque entrée a son intitulé en gras)."""
            lo, hi = ga["last_base"], gb["first_base"]
            bx0 = min(ga["x0"], gb["x0"])
            bx1 = max(ga["x1"], gb["x1"])
            for s in snapshot:
                if not (lo + 0.3 * size < s["first_base"] < hi - 0.3 * size):
                    continue
                if min(bx1, s["x1"]) - max(bx0, s["x0"]) > 2.0:
                    return True
            return False

        # Facteur de la zone floue : au-delà du seuil × AMBIGUOUS_FACTOR,
        # le rejet est certain. Entre threshold et threshold × factor,
        # le LLM tranche si disponible.
        AMBIGUOUS_FACTOR = 1.30

        def _mergeable_degree(a, b):
            """Retourne 'merge', 'ambiguous' ou 'reject'."""
            if a["sig"] != b["sig"]:
                return "reject"
            ga, gb = self._group_geom(a), self._group_geom(b)
            size  = max(6.0, (ga["size"] + gb["size"]) / 2)
            tol_x = max(8.0, 2.0 * size)
            # — même ligne : confiance totale —
            if abs(gb["first_base"] - ga["last_base"]) <= 0.4 * size:
                gap = gb["first_x0"] - ga["last_x1"]
                if -0.3 * size <= gap <= 0.6 * size:
                    return "merge"
            # — multi-ligne —
            dy = gb["first_base"] - ga["last_base"]
            edge = (abs(gb["x0"] - ga["x0"]) <= tol_x
                    or abs(gb["x1"] - ga["x1"]) <= tol_x
                    or abs((gb["x0"] + gb["x1"]) / 2
                           - (ga["x0"] + ga["x1"]) / 2) <= tol_x)
            overlap = min(ga["x1"], gb["x1"]) - max(ga["x0"], gb["x0"])
            if not (edge and overlap > 0):
                return "reject"
            if _has_intervening(ga, gb, size):
                return "reject"
            if 0.5 * size < dy <= line_gap_threshold * size:
                return "merge"
            if line_gap_threshold * size < dy <= line_gap_threshold * size * AMBIGUOUS_FACTOR:
                return "ambiguous"
            return "reject"

        # Ordre de lecture : baseline du 1er span puis x.
        cand.sort(key=lambda g: (round(self._group_geom(g)["first_base"], 1),
                                 self._group_geom(g)["x0"]))

        out            = []
        ambiguous_pairs = []   # [(target_group, candidate_group)] — à valider par LLM

        for g in cand:
            target, target_deg = None, "reject"
            for h in out:
                deg = _mergeable_degree(h, g)
                if deg in ("merge", "ambiguous"):
                    target, target_deg = h, deg

            if target is not None and target_deg == "merge":
                target["members"].extend(g["members"])
                target["members"].sort(
                    key=lambda m: (round(m[0]["origin"][1], 1), m[0]["bbox"][0]))
            elif target is not None and target_deg == "ambiguous":
                # Ajouté comme standalone pour l'instant ; le LLM décidera
                ambiguous_pairs.append((target, g))
                out.append(g)
            else:
                out.append(g)

        return out + passthrough, ambiguous_pairs

    def _group_rotated_paragraphs(self, rotated_spans):
        """REGROUPEMENT DÉSACTIVÉ : chaque span pivoté est traité comme un bloc
        indépendant, rendu tel quel à sa position d'origine (aucune fusion)."""
        groups = []
        for span, rot in rotated_spans:
            fl = span.get("flags", 0)
            fm = self._map_font(span.get("font", "Helvetica"),
                                bool(fl & FLAG_BOLD), bool(fl & FLAG_ITALIC))
            groups.append({"members": [(span, rot, fm)], "sig": None,
                           "rot": rot, "bullet": None})
        return groups

    @staticmethod
    def _detect_alignment(spans, rotated=False):
        """Déduit l'alignement (0=gauche/début, 1=centre, 2=droite/fin) d'un
        paragraphe à partir de ses lignes : on regarde quel bord est le plus
        régulier (début aligné → gauche, qui couvre aussi le justifié ; fin
        alignée → droite ; centres alignés → centre). Pour du texte pivoté 90°
        (lecture bas→haut), l'axe de lecture est vertical : le « début » est le
        bas (y1), la « fin » est le haut (y0)."""
        if len(spans) < 2:
            return 0
        if rotated:
            starts  = [s["bbox"][3] for s in spans]                  # bas (y1)
            ends    = [s["bbox"][1] for s in spans]                  # haut (y0)
            centers = [(s["bbox"][1] + s["bbox"][3]) / 2 for s in spans]
            extent  = max(s["bbox"][3] for s in spans) - min(s["bbox"][1] for s in spans)
        else:
            starts  = [s["bbox"][0] for s in spans]                  # gauche (x0)
            ends    = [s["bbox"][2] for s in spans]                  # droite (x1)
            centers = [(s["bbox"][0] + s["bbox"][2]) / 2 for s in spans]
            extent  = max(s["bbox"][2] for s in spans) - min(s["bbox"][0] for s in spans)
        tol    = max(2.5, 0.03 * extent)
        spread = lambda v: max(v) - min(v)
        if spread(starts) <= tol:
            return 0
        if spread(ends) <= tol:
            return 2
        if spread(centers) <= tol:
            return 1
        return 0

    def _make_para_entry(self, group, page_num, b_idx, p_idx, rotated=False):
        """Construit un bloc de texte à partir d'un groupe (1+ lignes), avec
        éventuellement un marqueur de puce rattaché (`group["bullet"]`)."""
        members = group["members"]
        spans = [m[0] for m in members]
        first = spans[0]
        rot   = members[0][1]
        fm    = members[0][2]

        first_text = first.get("text", "").strip()
        # Puce : soit un marqueur isolé rattaché, soit une puce collée au texte.
        bullet = group.get("bullet")
        if bullet is not None:
            mspan = bullet[0]
            bullet_char = mspan.get("text", "").strip()
            bullet_font = mspan.get("font", "Helvetica")
            is_list = True
            first_clean = first_text
        else:
            is_list = self._detect_bullet(first_text)
            bullet_char, first_clean = self._extract_bullet(first_text)
            bullet_font = first.get("font", "Helvetica") if bullet_char else None

        parts = [first_clean.strip()] + [s.get("text", "").strip() for s in spans[1:]]
        full_text = " ".join(p for p in parts if p)

        xs0 = min(s["bbox"][0] for s in spans)
        ys0 = min(s["bbox"][1] for s in spans)
        xs1 = max(s["bbox"][2] for s in spans)
        ys1 = max(s["bbox"][3] for s in spans)
        origin = list(first.get("origin", [xs0, ys1]))

        # bbox/point de la puce rattachée (pour la dessiner au bon endroit)
        if bullet is not None:
            mbb = bullet[0].get("bbox", [xs0, ys0, xs0, ys1])
            xs0 = min(xs0, mbb[0])
            bullet_origin = list(bullet[0].get("origin", [mbb[0], mbb[3]]))
        else:
            bullet_origin = None

        flags      = first.get("flags", 0)
        char_flags = first.get("char_flags", 0)
        font_raw   = first.get("font", "Helvetica")

        return {
            "id":              f"p{page_num + 1}_b{b_idx}_g{p_idx}",
            "text":            full_text,
            "translated_text": "",
            "bullet_char":     bullet_char or None,
            "bullet_font":     bullet_font,
            "bullet_origin":   bullet_origin,
            "bbox":            [xs0, ys0, xs1, ys1],
            "origin":          origin,
            "font":            font_raw,
            "font_mapped":     fm,
            "size":            round(first.get("size", 12), 2),
            "color":           self._int_to_rgb(first.get("color", 0)),
            "bold":            bool(flags & FLAG_BOLD),
            "italic":          bool(flags & FLAG_ITALIC),
            "underline":       bool(char_flags & CHAR_UNDERLINE),
            "strikeout":       bool(char_flags & CHAR_STRIKEOUT),
            "rotation":        rot,
            "page":            page_num + 1,
            "is_list_item":    is_list,
            "multiline":       len(spans) > 1,
            "align":           self._detect_alignment(spans, rotated=rotated),
            "first_x":         first.get("bbox", [xs0])[0],
        }

    # ══════════════════════════════════════════════════════════════════════════
    # RENDU D'UN PARAGRAPHE (texte multi-lignes avec retour à la ligne auto)
    # ══════════════════════════════════════════════════════════════════════════
    def _insert_paragraph(self, page, bbox, origin, text, font_mapped,
                          font_raw, orig_size, color, is_list,
                          bullet_char, bullet_raw, align=0, first_x=None,
                          bullet_origin=None, min_size=None):
        """Insère un paragraphe multi-lignes via insert_textbox, avec ajustement
        de la taille à l'échelle du paragraphe (et non ligne par ligne).

        `insert_textbox` ne dessine RIEN s'il déborde (retour < 0) ; on essaie
        donc les tailles de la plus grande à la plus petite et on garde la
        première qui tient — ce qui reproduit fidèlement le calcul interne de
        PyMuPDF sans estimation approximative."""
        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
        oy = origin[1] if origin and len(origin) >= 2 else y1
        text_x0 = x0

        # Cas « libellé en ligne » : la 1re ligne démarre nettement plus à droite
        # que les suivantes (ex. « Base de données : » suivi de « MySQL, » puis
        # la valeur qui continue à la marge). Un rectangle unique écraserait le
        # libellé → on rend avec un retrait de 1re ligne (conteneur en « L »).
        if min_size is None:
            min_size = orig_size * 0.7
        if (first_x is not None and not (is_list and bullet_char)
                and align == 0 and first_x - x0 > max(10.0, 1.5 * orig_size)):
            return self._insert_indented_paragraph(
                page, text, first_x, x0, x1, oy, y1,
                font_mapped, font_raw, orig_size, color, min_size=min_size
            )

        if is_list and bullet_char:
            if bullet_origin and len(bullet_origin) >= 2:
                # Marqueur séparé : puce à SA position, texte à la sienne.
                self._insert_text_smart(page, (bullet_origin[0], bullet_origin[1]),
                                        bullet_char, orig_size, font_mapped,
                                        bullet_raw, color, 0.0)
                text_x0 = first_x if first_x is not None else x0
            else:
                # Puce collée : la dessiner puis décaler le texte après elle.
                self._insert_text_smart(page, (x0, oy), bullet_char, orig_size,
                                        font_mapped, bullet_raw, color, 0.0)
                bw = self._text_length(bullet_char, orig_size, font_mapped, bullet_raw)
                if bw < 2:
                    bw = orig_size * 0.6
                text_x0 = x0 + bw + orig_size * 0.3

        embed = self._embed_font_for(text, font_raw)
        if embed is not None:
            fontkey, fontfile = embed
        else:
            fontkey, fontfile = font_mapped, None

        if (x1 - text_x0) <= 1:
            return self._insert_text_smart(page, (text_x0, oy), text, orig_size,
                                           font_mapped, font_raw, color, 0.0)

        def _try(rect, size):
            try:
                if fontfile:
                    return page.insert_textbox(rect, text, fontsize=size,
                                               fontname=fontkey, fontfile=fontfile,
                                               color=color, align=align)
                return page.insert_textbox(rect, text, fontsize=size,
                                           fontname=fontkey, color=color, align=align)
            except Exception:
                return None

        # Priorité 1 : taille d'origine dans la boîte telle quelle.
        tight = fitz.Rect(text_x0, y0, x1, y1 + 2.0)
        rv = _try(tight, orig_size)
        if rv is not None and rv >= 0:
            return True

        # Priorité 2 : réduction de taille via estimation de hauteur word-wrap.
        # On MESURE sans insérer (Font.text_length mot à mot), puis on insère
        # une seule fois avec la meilleure taille trouvée. Évite les insertions
        # multiples que produirait une recherche binaire avec insert_textbox.
        if orig_size > min_size:
            try:
                _fobj = self._get_font(fontfile) if fontfile else fitz.Font(font_mapped)
            except Exception:
                _fobj = None
            if _fobj is not None:
                _bw   = max(1.0, x1 - text_x0)
                _bh   = max(1.0, y1 - y0)
                _words = text.split()

                def _fits_at(sz):
                    if sz <= 0 or not _words:
                        return False
                    try:
                        sp = _fobj.text_length(" ", fontsize=sz)
                        n_lines, cur = 1, 0.0
                        for w in _words:
                            ww = _fobj.text_length(w, fontsize=sz)
                            if cur == 0.0:
                                cur = ww
                            elif cur + sp + ww > _bw:
                                n_lines += 1
                                cur = ww
                            else:
                                cur += sp + ww
                        return n_lines * sz * 1.25 <= _bh
                    except Exception:
                        return False

                lo2, hi2, best_size = min_size, orig_size, None
                for _ in range(12):
                    mid = (lo2 + hi2) * 0.5
                    if _fits_at(mid):
                        best_size, lo2 = mid, mid
                    else:
                        hi2 = mid

                if best_size is not None:
                    rv2 = _try(tight, best_size)
                    if rv2 is not None and rv2 >= 0:
                        return True

        # Priorité 3 : boîte étendue vers le bas (jamais de texte tronqué).
        rv = _try(fitz.Rect(text_x0, y0, x1, y0 + 2000), orig_size)
        if rv is not None and rv >= 0:
            return True
        return self._insert_text_smart(page, (text_x0, oy), text, orig_size,
                                       font_mapped, font_raw, color, 0.0)

    def _insert_indented_paragraph(self, page, text, x_first, x_rest, x_right,
                                   y_baseline0, bottom, font_mapped, font_raw,
                                   orig_size, color, min_size=None):
        """Rend un paragraphe dont la 1re ligne est indentée (démarre à
        `x_first`, ex. juste après un libellé en ligne) et dont les lignes
        suivantes reviennent à la marge `x_rest`. Reproduit un conteneur en
        « L » que `insert_textbox` (rectangulaire) ne sait pas faire : on
        effectue nous-mêmes le retour à la ligne, mot à mot."""
        embed = self._embed_font_for(text, font_raw)
        fontfile = embed[1] if embed is not None else None
        try:
            font = self._get_font(fontfile) if fontfile else fitz.Font(font_mapped)
        except Exception:
            font = fitz.Font("helv")

        words = text.split()

        def wrap(size):
            """Découpe en lignes (left, mots) ; 1re ligne à x_first, puis x_rest.
            Renvoie aussi True si un mot seul dépasse la largeur disponible."""
            space = font.text_length(" ", fontsize=size)
            lines, left, cur, curw, toowide = [], x_first, [], 0.0, False
            for w in words:
                ww = font.text_length(w, fontsize=size)
                if ww > (x_right - x_rest):
                    toowide = True
                if cur and curw + space + ww > (x_right - left):
                    lines.append((left, cur))
                    left, cur, curw = x_rest, [w], ww
                else:
                    curw = curw + space + ww if cur else ww
                    cur.append(w)
            if cur:
                lines.append((left, cur))
            return lines, toowide

        # Priorité 1 : taille d'origine.  Si le texte ne tient pas dans la
        # hauteur disponible (bottom - y_baseline0), on réduit jusqu'au plancher
        # adaptatif (min_size = plus petite police présente sur la page).
        if min_size is None:
            min_size = orig_size * 0.7
        orig_h = max(1.0, bottom - y_baseline0)
        size = orig_size
        lines, _ = wrap(size)
        if len(lines) * size * 1.3 > orig_h and orig_size > min_size:
            lo, hi = min_size, orig_size
            for _ in range(10):
                mid = (lo + hi) * 0.5
                ls, _ = wrap(mid)
                if len(ls) * mid * 1.3 <= orig_h:
                    lo, size, lines = mid, mid, ls
                else:
                    hi = mid
        y = y_baseline0
        for left, ws in lines:
            self._insert_text_smart(page, (left, y), " ".join(ws), size,
                                    font_mapped, font_raw, color, 0.0)
            y += size * 1.3
        return True

    def _insert_rotated_paragraph(self, page, bbox, text, font_mapped,
                                  font_raw, orig_size, color, align, rotate,
                                  min_size=None):
        """Insère un paragraphe pivoté (cellule verticale) via insert_textbox
        avec `rotate` (90/270) et retour à la ligne automatique. Même logique
        de réduction de taille que le cas horizontal."""
        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
        embed = self._embed_font_for(text, font_raw)
        if embed is not None:
            fontkey, fontfile = embed
        else:
            fontkey, fontfile = font_mapped, None

        def _try(rect, size):
            try:
                if fontfile:
                    return page.insert_textbox(rect, text, fontsize=size,
                                               fontname=fontkey, fontfile=fontfile,
                                               color=color, align=align, rotate=rotate)
                return page.insert_textbox(rect, text, fontsize=size,
                                           fontname=fontkey, color=color,
                                           align=align, rotate=rotate)
            except Exception:
                return None

        # Priorité 1 : taille d'origine dans la cellule telle quelle.
        base_rect = fitz.Rect(x0, y0, x1, y1)
        rv = _try(base_rect, orig_size)
        if rv is not None and rv >= 0:
            return True

        # Priorité 2 : réduction via estimation de hauteur (mesure pure, sans
        # insertion). Pour du texte pivoté 90°/270°, la largeur de wrap = hauteur
        # de cellule (y1-y0) et la hauteur disponible = largeur (x1-x0).
        if min_size is None:
            min_size = orig_size * 0.7
        if orig_size > min_size:
            try:
                _fobj = self._get_font(fontfile) if fontfile else fitz.Font(font_mapped)
            except Exception:
                _fobj = None
            if _fobj is not None:
                _bw = max(1.0, y1 - y0)   # largeur de wrap dans le repère pivoté
                _bh = max(1.0, x1 - x0)   # hauteur disponible
                _words = text.split()

                def _fits_rot(sz):
                    if sz <= 0 or not _words:
                        return False
                    try:
                        sp = _fobj.text_length(" ", fontsize=sz)
                        n, cur = 1, 0.0
                        for w in _words:
                            ww = _fobj.text_length(w, fontsize=sz)
                            if cur == 0.0:
                                cur = ww
                            elif cur + sp + ww > _bw:
                                n += 1
                                cur = ww
                            else:
                                cur += sp + ww
                        return n * sz * 1.25 <= _bh
                    except Exception:
                        return False

                lo2, hi2, best_size = min_size, orig_size, None
                for _ in range(12):
                    mid = (lo2 + hi2) * 0.5
                    if _fits_rot(mid):
                        best_size, lo2 = mid, mid
                    else:
                        hi2 = mid

                if best_size is not None:
                    r = _try(base_rect, best_size)
                    if r is not None and r >= 0:
                        return True

        # Priorité 3 : cellule élargie dans le sens du wrap.
        wide = fitz.Rect(x0, y0, x1 + max(orig_size * 12, 80), y1)
        rv = _try(wide, orig_size)
        if rv is not None and rv >= 0:
            return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # PASSE DE MISE EN PAGE — reflow vertical conservateur
    # ══════════════════════════════════════════════════════════════════════════
    # Recalcule la position verticale des blocs de texte « libres » selon la
    # longueur réelle de leur traduction : un paragraphe plus court rétrécit et
    # les blocs suivants de la MÊME colonne remontent (écarts d'origine
    # préservés) ; plus long, ils descendent dans l'espace libre. Périmètre
    # conservateur : on NE touche PAS aux tableaux, fonds colorés, images,
    # texte pivoté, ni à plusieurs colonnes à la fois. Au moindre risque de
    # collision/débordement, on revient à un comportement sans croissance
    # (déplacement vers le haut uniquement), puis à la position d'origine.

    LINE_PITCH = 1.32   # interligne approximatif (× taille de police)

    def _wrap_line_count(self, text, fontsize, width, font_mapped, font_raw):
        """Nombre de lignes après retour à la ligne de `text` dans `width`."""
        if width <= 1 or not text.strip():
            return 1
        sym = SYMBOL_BUILTIN_FONT.get(self._norm_font(font_raw or ""))
        try:
            if sym:
                font = fitz.Font(sym)
            else:
                embed = self._embed_font_for(text, font_raw)
                font = self._get_font(embed[1]) if embed else fitz.Font(font_mapped)
        except Exception:
            font = fitz.Font("helv")
        space = font.text_length(" ", fontsize=fontsize)
        lines, cur = 1, 0.0
        for w in text.split():
            ww = font.text_length(w, fontsize=fontsize)
            if cur <= 0:
                cur = ww
            elif cur + space + ww <= width:
                cur += space + ww
            else:
                lines += 1
                cur = ww
        return lines

    def _table_regions(self, src_page):
        """Régions quadrillées (tableaux), détectées par une vraie GRILLE :
        plusieurs lignes fines horizontales ET verticales. De simples filets
        horizontaux (soulignements de section) ne suffisent pas — sinon on
        exclurait à tort des paragraphes ordinaires du reflow."""
        hs, vs = [], []
        for d in src_page.get_cdrawings():
            for it in d.get("items", []):
                if it[0] == "re":
                    r = it[1]
                    w, h = abs(r[2] - r[0]), abs(r[3] - r[1])
                    if h < 3 and w >= 20:
                        hs.append((min(r[0], r[2]), min(r[1], r[3]),
                                   max(r[0], r[2]), max(r[1], r[3])))
                    elif w < 3 and h >= 20:
                        vs.append((min(r[0], r[2]), min(r[1], r[3]),
                                   max(r[0], r[2]), max(r[1], r[3])))
                elif it[0] == "l":
                    p1, p2 = it[1], it[2]
                    if abs(p1[1] - p2[1]) < 1 and abs(p2[0] - p1[0]) >= 20:
                        hs.append((min(p1[0], p2[0]), p1[1],
                                   max(p1[0], p2[0]), p1[1]))
                    elif abs(p1[0] - p2[0]) < 1 and abs(p2[1] - p1[1]) >= 20:
                        vs.append((p1[0], min(p1[1], p2[1]),
                                   p1[0], max(p1[1], p2[1])))
        # Une grille requiert des lignes dans les DEUX directions.
        if len(hs) < 4 or len(vs) < 2:
            return []
        allseg = hs + vs
        x0 = min(s[0] for s in allseg); y0 = min(s[1] for s in allseg)
        x1 = max(s[2] for s in allseg); y1 = max(s[3] for s in allseg)
        return [(x0, y0, x1, y1)]

    def _bg_fills(self, src_page, page_w, page_h):
        """Rectangles pleins significatifs (fonds colorés). Ignore le fond de
        page entier (≥ 70 % de la surface) qui n'ancre aucun bloc précis."""
        fills = []
        page_area = max(1.0, page_w * page_h)
        for d in src_page.get_cdrawings():
            for it in d.get("items", []):
                if it[0] != "re":
                    continue
                r = it[1]
                w, h = abs(r[2] - r[0]), abs(r[3] - r[1])
                if h >= 4 and w >= 8 and (w * h) < 0.70 * page_area:
                    fills.append((min(r[0], r[2]), min(r[1], r[3]),
                                  max(r[0], r[2]), max(r[1], r[3])))
        return fills

    @staticmethod
    def _cluster_columns(blocks):
        """Regroupe les blocs en colonnes par recouvrement horizontal (union-
        find transitif sur l'intervalle x). Deux blocs dont les x se recouvrent
        sont dans la même colonne."""
        n = len(blocks)
        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            parent[find(i)] = find(j)

        for i in range(n):
            ax0, ax1 = blocks[i]["bbox"][0], blocks[i]["bbox"][2]
            for j in range(i + 1, n):
                bx0, bx1 = blocks[j]["bbox"][0], blocks[j]["bbox"][2]
                if min(ax1, bx1) - max(ax0, bx0) > 1.0:   # recouvrement x
                    union(i, j)
        cols = {}
        for i in range(n):
            cols.setdefault(find(i), []).append(blocks[i])
        return list(cols.values())

    def _reflow_page(self, page_data, src_page):
        blocks = page_data.get("text_blocks", [])
        if not blocks:
            return
        W = page_data.get("width", src_page.rect.width)
        H = page_data.get("height", src_page.rect.height)
        top_margin, bot_margin = 0.05 * H, 0.95 * H
        tables = self._table_regions(src_page)
        fills = self._bg_fills(src_page, W, H)

        def overlaps(a, b):
            return not (a[2] <= b[0] or a[0] >= b[2]
                        or a[3] <= b[1] or a[1] >= b[3])

        def covered(bb, region, frac):
            ox = max(0.0, min(bb[2], region[2]) - max(bb[0], region[0]))
            oy = max(0.0, min(bb[3], region[3]) - max(bb[1], region[1]))
            area = max(1.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
            return (ox * oy) / area >= frac

        # 1. Classification : quels blocs sont reflowables ?
        reflowable = []
        for b in blocks:
            bb = b.get("bbox")
            ok = (bb and len(bb) >= 4
                  and abs(b.get("rotation", 0)) <= 1.0
                  and bb[1] >= top_margin and bb[3] <= bot_margin
                  and not any(covered(bb, t, 0.2) for t in tables)
                  and not any(covered(bb, f, 0.5) for f in fills))
            b["_reflow"] = bool(ok)
            if ok:
                reflowable.append(b)
        if not reflowable:
            return

        # Colonnes calculées sur la géométrie d'ORIGINE (avant tout élargissement,
        # sinon un bloc élargi pourrait fusionner à tort deux colonnes voisines).
        cols = self._cluster_columns(reflowable)

        # Règle 2b — reflow inline (chaînes « même ligne »). Quand un bloc
        # mono-ligne rétrécit (traduction plus courte), ses voisins directement
        # adjacents sur la même ligne se décalent pour refermer le trou ; s'il
        # s'allonge, ils se décalent à droite (borné anti-collision).
        self._reflow_inline(blocks, tables)

        # Règle 1 — élargissement horizontal dans l'espace libre à droite.
        # Doit s'exécuter AVANT le reflow vertical : si la traduction plus longue
        # retrouve sa hauteur d'origine en s'élargissant, le vertical ne bouge rien.
        self._expand_widths(reflowable, blocks, tables, fills, W)

        # 2. Obstacles fixes (à ne pas chevaucher quand on déplace du texte)
        obstacles = [b["bbox"] for b in blocks if not b.get("_reflow")]
        obstacles += list(tables)

        # 3. Reflow colonne par colonne
        for col in cols:
            col.sort(key=lambda b: b["bbox"][1])
            self._reflow_column(col, obstacles, bot_margin)

    def _expand_widths(self, reflowable, all_blocks, tables, fills, W):
        """Règle 1 — élargissement horizontal.

        Pour un paragraphe multi-lignes dont la traduction est PLUS LONGUE que
        l'original (donc occuperait plus de lignes à largeur égale), on agrandit
        sa boîte vers la DROITE dans l'espace libre — juste assez pour que le
        texte retrouve son nombre de lignes d'origine (donc sa hauteur). On
        préserve un écart minimal avec tout voisin de droite et on n'empiète
        jamais sur un autre bloc, un tableau ou un fond coloré. Si l'espace ne
        suffit pas, on élargit au maximum disponible et le reflow vertical
        absorbe le reste (règle 2). Si aucun espace à droite : on ne touche à
        rien (la réduction de police — règle 3 — sera traitée ultérieurement).
        """
        if not reflowable:
            return
        GAP = 6.0  # écart minimal préservé avec un voisin de droite
        # Marge droite du contenu : symétrique à la marge gauche du texte.
        left_margin = min(b["bbox"][0] for b in reflowable)
        right_bound = W - max(6.0, left_margin)
        extra = [list(r) for r in list(tables) + list(fills)]

        def yov(a, b):
            return min(a[3], b[3]) - max(a[1], b[1]) > 2.0

        for b in reflowable:
            # Règle 1 : gauche uniquement (élargir un bloc centré/droite
            # déplacerait son ancrage), horizontal, multi-lignes.
            if (abs(b.get("rotation", 0)) > 1.0
                    or b.get("align", 0) != 0
                    or not b.get("multiline")):
                continue
            bb = b["bbox"]
            size = b.get("size", 12)
            fm, fr = b.get("font_mapped", "helv"), b.get("font", "helv")
            src = (b.get("text") or "").strip()
            tr = (b.get("translated_text") or src).strip()
            if not tr:
                continue
            first_x = b.get("first_x", bb[0])
            cur_w = bb[2] - first_x
            if cur_w <= 1:
                continue
            nl_src = max(1, self._wrap_line_count(src, size, cur_w, fm, fr))
            nl_tr = max(1, self._wrap_line_count(tr, size, cur_w, fm, fr))
            if nl_tr <= nl_src:
                continue  # tient déjà : la règle 1 ne traite que le « plus long »

            # Limite droite : le plus proche obstacle à droite chevauchant en y.
            limit = right_bound
            for o in all_blocks:
                if o is b:
                    continue
                ob = o.get("bbox")
                if ob and len(ob) >= 4 and ob[0] >= bb[2] - 1.0 and yov(bb, ob):
                    limit = min(limit, ob[0] - GAP)
            for ob in extra:
                if ob[0] >= bb[2] - 1.0 and yov(bb, ob):
                    limit = min(limit, ob[0] - GAP)
            if limit <= bb[2] + 2.0:
                continue  # pas d'espace à droite → réduction (règle 3) plus tard

            new_x1 = self._min_width_x1(tr, size, fm, fr, first_x,
                                        bb[2], limit, nl_src)
            if new_x1 > bb[2] + 1.0:
                b.setdefault("_old_bbox", list(bb))  # redaction = aire d'origine
                b["bbox"] = [bb[0], bb[1], new_x1, bb[3]]

    def _min_width_x1(self, text, size, fm, fr, first_x,
                      cur_x1, max_x1, target_lines):
        """Plus petit `x1` dans ]cur_x1, max_x1] tel que `text` tienne en
        `target_lines` lignes (nombre de lignes décroissant avec la largeur →
        recherche dichotomique). Si même `max_x1` ne suffit pas, renvoie
        `max_x1` (élargissement maximal, le vertical absorbera le reste)."""
        if self._wrap_line_count(text, size, max_x1 - first_x, fm, fr) > target_lines:
            return max_x1
        lo, hi = cur_x1, max_x1
        for _ in range(20):
            mid = (lo + hi) / 2.0
            if self._wrap_line_count(text, size, mid - first_x, fm, fr) <= target_lines:
                hi = mid
            else:
                lo = mid
        return hi

    def _reflow_inline(self, blocks, tables):
        """Reflow horizontal des CHAÎNES INLINE (blocs mono-ligne partageant la
        même ligne de base et directement adjacents, écart ≈ 0). Quand la
        traduction d'un maillon change de largeur, les maillons suivants sont
        repositionnés pour préserver l'écart d'origine : décalage à GAUCHE si le
        texte rétrécit (on referme le trou « espace blanc sans texte »), à droite
        s'il s'allonge (borné pour ne jamais chevaucher un autre bloc/colonne).
        Les voisins à grand écart (vraies colonnes) ne sont JAMAIS déplacés."""
        INLINE_FACTOR = 0.6  # écart max d'une chaîne ≈ une espace (× taille)

        def covered(bb, region, frac=0.2):
            ox = max(0.0, min(bb[2], region[2]) - max(bb[0], region[0]))
            oy_ = max(0.0, min(bb[3], region[3]) - max(bb[1], region[1]))
            area = max(1.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
            return (ox * oy_) / area >= frac

        def oy(b):
            o = b.get("origin")
            return o[1] if o and len(o) >= 2 else b["bbox"][3]

        def line_start(b):
            # Bord gauche du bloc SUR LA LIGNE DE BASE. Pour un bloc multi-ligne
            # à 1re ligne indentée (libellé en ligne : « label : valeur… »), la
            # 1re ligne démarre à first_x (les lignes de retour, elles, à bbox[0]).
            if b.get("multiline") and b.get("first_x") is not None:
                return b["first_x"]
            return b["bbox"][0]

        cand = []
        for b in blocks:
            bb = b.get("bbox")
            if (not bb or len(bb) < 4 or abs(b.get("rotation", 0)) > 1.0
                    or b.get("bullet_char")):
                continue
            if b.get("multiline"):
                # Multi-ligne accepté UNIQUEMENT comme maillon terminal à 1re
                # ligne indentée (sa 1re ligne suit un libellé). Les autres
                # paragraphes multi-lignes ne sont pas des chaînes inline.
                fx = b.get("first_x")
                if fx is None or fx <= bb[0] + 1.0:
                    continue
            if any(covered(bb, t) for t in tables):
                continue
            cand.append(b)
        if len(cand) < 2:
            return

        cand.sort(key=lambda b: (round(oy(b), 1), line_start(b)))

        # Regroupement par ligne de base (origin y proche, tolérance ∝ taille).
        lines, cur = [], [cand[0]]
        for b in cand[1:]:
            ref = cur[0]
            tol = 0.4 * max(ref.get("size", 10), b.get("size", 10))
            if abs(oy(b) - oy(ref)) <= tol:
                cur.append(b)
            else:
                lines.append(cur)
                cur = [b]
        lines.append(cur)

        def overlaps(a, b):
            return not (a[2] <= b[0] or a[0] >= b[2]
                        or a[3] <= b[1] or a[1] >= b[3])

        for line in lines:
            line.sort(key=line_start)
            i = 0
            while i < len(line):
                chain, j = [line[i]], i
                while j + 1 < len(line):
                    a, nb = line[j], line[j + 1]
                    if a.get("multiline"):
                        break          # un multi-ligne ne peut être que terminal
                    gap = line_start(nb) - a["bbox"][2]
                    lim = max(2.0, INLINE_FACTOR * max(a.get("size", 10),
                                                       nb.get("size", 10)))
                    if -1.0 <= gap <= lim:
                        chain.append(nb)
                        j += 1
                        if nb.get("multiline"):
                            break       # maillon terminal atteint
                    else:
                        break
                if len(chain) >= 2:
                    self._apply_inline_chain(chain, blocks, tables, overlaps)
                i = j + 1

    def _apply_inline_chain(self, chain, all_blocks, tables, overlaps):
        """Repositionne les maillons (sauf l'ancre, fixe) d'une chaîne inline
        selon la largeur réelle de leur traduction, en préservant les écarts
        d'origine. Tout-ou-rien : si un décalage vers la droite crée une
        NOUVELLE collision avec un bloc/tableau externe, la chaîne est laissée
        intacte."""
        def scaled_width(b):
            # Largeur rendue estimée de la traduction = largeur RÉELLE d'origine
            # (bbox, vérité terrain) × ratio (longueur traduite / source) en
            # métriques de police. Le ratio annule le biais systématique des
            # métriques (gras, police embarquée…) ; si traduction = source, le
            # ratio vaut 1 → largeur inchangée → no-op rigoureusement nul.
            bb = b["bbox"]
            ow = max(0.0, bb[2] - bb[0])
            size = b.get("size", 10)
            fm, fr = b.get("font_mapped", "helv"), b.get("font", "helv")
            src = (b.get("text") or "").strip()
            tr = (b.get("translated_text") or src).strip()
            wsrc = self._text_length(src, size, fm, fr)
            if wsrc <= 1.0:
                return ow
            return ow * (self._text_length(tr, size, fm, fr) / wsrc)

        def line_start(b):
            if b.get("multiline") and b.get("first_x") is not None:
                return b["first_x"]
            return b["bbox"][0]

        cur_right = chain[0]["bbox"][0] + scaled_width(chain[0])
        proposals = []
        for k in range(1, len(chain)):
            b, prev = chain[k], chain[k - 1]
            ls = line_start(b)
            orig_gap = ls - prev["bbox"][2]
            new_ls = cur_right + orig_gap
            delta = new_ls - ls
            proposals.append((b, delta))
            if b.get("multiline"):
                break               # maillon terminal : pas de suite à propager
            cur_right = new_ls + scaled_width(b)

        if not proposals:
            return

        # Garde anti-collision pour les décalages à DROITE (allongement) des
        # maillons MONO-ligne (un maillon multi-ligne ne décale que sa 1re ligne
        # à l'intérieur de sa propre boîte → aucune collision externe possible).
        chain_ids = {id(c) for c in chain}
        obst = [o["bbox"] for o in all_blocks
                if id(o) not in chain_ids and o.get("bbox") and len(o["bbox"]) >= 4]
        obst += list(tables)
        for b, delta in proposals:
            if b.get("multiline") or delta <= 0.1:
                continue
            bb = b["bbox"]
            new_bb = [bb[0] + delta, bb[1], bb[2] + delta, bb[3]]
            for o in obst:
                if overlaps(new_bb, o) and not overlaps(bb, o):
                    return          # collision nouvelle → on abandonne la chaîne

        for b, delta in proposals:
            if abs(delta) < 0.3:
                continue
            if b.get("multiline"):
                # Décale uniquement la 1re ligne (first_x) ; les lignes de retour
                # restent à la marge (bbox inchangée → redaction d'origine OK).
                fx = b["first_x"]
                bb = b["bbox"]
                new_fx = min(max(fx + delta, bb[0]), bb[2] - b.get("size", 10))
                shift = new_fx - fx
                b["first_x"] = new_fx
                o = b.get("origin")
                if o and len(o) >= 2:
                    b["origin"] = [o[0] + shift, o[1]]
            else:
                b.setdefault("_old_bbox", list(b["bbox"]))
                bb = b["bbox"]
                b["bbox"] = [bb[0] + delta, bb[1], bb[2] + delta, bb[3]]
                o = b.get("origin")
                if o and len(o) >= 2:
                    b["origin"] = [o[0] + delta, o[1]]
                bo = b.get("bullet_origin")
                if bo and len(bo) >= 2:
                    b["bullet_origin"] = [bo[0] + delta, bo[1]]

    def _reflow_column(self, col, obstacles, bottom_limit):
        """Empile verticalement une colonne en préservant les écarts d'origine.
        Essaie d'abord en autorisant la croissance ; si ça déborde/chevauche,
        recommence en bornant chaque hauteur à sa valeur d'origine (déplacement
        vers le haut uniquement, sans risque)."""
        def needed_height(b):
            bb = b["bbox"]
            orig_h = bb[3] - bb[1]
            if not b.get("multiline"):
                return orig_h
            left = b.get("first_x", bb[0])
            width = bb[2] - left
            size = b.get("size", 12)
            fm, fr = b.get("font_mapped", "helv"), b.get("font", "helv")
            src = (b.get("text") or "").strip()
            tr = (b.get("translated_text") or src).strip()
            if not tr:
                return orig_h
            # On met à l'échelle la hauteur d'origine par le ratio de lignes
            # (traduction / source) : si le nombre de lignes ne change pas, la
            # hauteur est rigoureusement inchangée → reflow sans dérive.
            nl_src = max(1, self._wrap_line_count(src, size, width, fm, fr))
            nl_tr = max(1, self._wrap_line_count(tr, size, width, fm, fr))
            return orig_h * nl_tr / nl_src

        def overlaps_(a, b):
            return not (a[2] <= b[0] or a[0] >= b[2]
                        or a[3] <= b[1] or a[1] >= b[3])

        def layout(cap_to_original):
            """Renvoie la liste des nouveaux (top, height) ou None si collision."""
            placements = []
            prev_new_bottom = prev_orig_bottom = None
            for b in col:
                bb = b["bbox"]
                h = needed_height(b)
                if cap_to_original:
                    h = min(h, bb[3] - bb[1])
                if prev_new_bottom is None:
                    new_top = bb[1]                       # 1er bloc ancré
                else:
                    new_top = prev_new_bottom + (bb[1] - prev_orig_bottom)
                new_bb = (bb[0], new_top, bb[2], new_top + h)
                if new_bb[3] > bottom_limit:
                    return None
                # collision rejetée seulement si NOUVELLE (un chevauchement déjà
                # présent à l'origine dans le PDF source ne doit pas tout bloquer)
                for o in obstacles:
                    if overlaps_(new_bb, o) and not overlaps_(bb, o):
                        return None
                placements.append((new_top, h))
                prev_new_bottom, prev_orig_bottom = new_top + h, bb[3]
            return placements

        placements = layout(cap_to_original=False)
        if placements is None:
            placements = layout(cap_to_original=True)
        if placements is None:
            return  # impossible sans risque → on garde les positions d'origine

        for b, (new_top, h) in zip(col, placements):
            bb = b["bbox"]
            dy = new_top - bb[1]
            if abs(dy) < 0.5 and abs((new_top + h) - bb[3]) < 0.5:
                continue                                  # rien à déplacer
            # Conserve l'aire d'origine à effacer : si la passe horizontale a
            # déjà posé _old_bbox (bbox élargie), ne pas l'écraser.
            b.setdefault("_old_bbox", list(bb))
            b["bbox"] = [bb[0], new_top, bb[2], new_top + h]
            if b.get("origin") and len(b["origin"]) >= 2:
                b["origin"] = [b["origin"][0], b["origin"][1] + dy]
            if b.get("bullet_origin") and len(b["bullet_origin"]) >= 2:
                b["bullet_origin"] = [b["bullet_origin"][0], b["bullet_origin"][1] + dy]

    @staticmethod
    def _compute_avail_widths(page_data: dict, page_width: float) -> None:
        """Pour chaque bloc de la page, stocke `avail_width` = espace exploitable
        à droite : du bord gauche du bloc jusqu'au bord gauche du premier voisin
        qui le borde à droite sur la même bande verticale. Si personne ne borde,
        on s'étend jusqu'au bord droit réel du contenu (max x1 des blocs de la
        page) — aucune marge fixe, valeur entièrement dérivée du document.

        N'est calculé que pour les blocs horizontaux non-rotatifs ; les blocs
        pivotés gardent leur bbox width (ils sont dans des cellules de tableau)."""
        blocks = page_data.get("text_blocks", [])
        # Limite droite = bord droit réel du contenu sur cette page.
        horiz = [b for b in blocks if b.get("rotation", 0.0) == 0.0 and b.get("bbox")]
        content_right = max((b["bbox"][2] for b in horiz), default=page_width)
        content_right = min(content_right, page_width)   # jamais au-delà de la page
        max_x = content_right

        for b in blocks:
            if b.get("rotation", 0.0) != 0.0:
                b["avail_width"] = abs(b["bbox"][2] - b["bbox"][0])
                continue

            bx0, by0, bx1, by1 = b["bbox"]
            # Cherche le voisin le plus proche à droite (x0 > bx1) dont la bande
            # verticale [by0, by1] recouvre celle de b d'au moins 30 % de la
            # hauteur de b. Ignore les blocs à gauche ou quasi-alignés.
            h = max(1.0, by1 - by0)
            nearest = max_x
            for nb in blocks:
                if nb is b:
                    continue
                nx0, ny0, nx1, ny1 = nb["bbox"]
                if nx0 <= bx1 + 1.0:       # pas à droite
                    continue
                ov = min(by1, ny1) - max(by0, ny0)
                if ov < 0.3 * h:            # bande verticale sans recouvrement suffisant
                    continue
                if nx0 < nearest:
                    nearest = nx0
            avail = max(nearest - bx0, bx1 - bx0)
            b["avail_width"] = avail

    @staticmethod
    def _fit_fontsize(text: str, font_name: str, max_width: float,
                      original_size: float, min_size: float = 5.0) -> float:
        """Renvoie la plus grande taille qui permet à `text` de tenir sur une
        ligne dans `max_width`. Si la taille d'origine tient déjà, elle est
        conservée (no-op). Sinon : recherche binaire entre min_size et
        original_size. C'est le 3ᵉ recours (après fusion inter-blocs et
        élargissement horizontal) : s'applique seulement aux blocs mono-ligne
        (les multi-lignes sont gérés par _insert_paragraph)."""
        try:
            w = fitz.get_text_length(text, fontname=font_name, fontsize=original_size)
        except Exception:
            return original_size
        if w <= max_width or original_size <= min_size:
            return original_size
        lo, hi = min_size, original_size
        for _ in range(14):                  # 14 iter ≈ 0.003 pt de précision
            mid = (lo + hi) * 0.5
            try:
                if fitz.get_text_length(text, fontname=font_name, fontsize=mid) <= max_width:
                    lo = mid
                else:
                    hi = mid
            except Exception:
                break
        return max(lo, min_size)
