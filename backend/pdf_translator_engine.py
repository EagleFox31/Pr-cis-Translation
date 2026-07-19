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
        self._doc_font_class = {}         # clé police normalisée -> 'serif'/'sans'/'mono'
        self._llm_client = None           # client OpenAI-compatible (optionnel)
        self._llm_model  = "deepseek-v4-flash"

        # ── Stratégie d'identification des paragraphes ──────────────────────
        # MODE ACTIF par défaut : regroupement délégué à l'IA (DeepSeek), écrit
        # dans block['paragraph_key']. Le regroupement GÉOMÉTRIQUE historique
        # (para_id) reste calculé et sert de REPLI (LLM absent/erreur), mais
        # n'est plus le mode principal. Pour repasser en géométrique pur :
        #   engine.use_llm_paragraph_grouping = False
        self.use_llm_paragraph_grouping = False
        # Attribut groupant les contours du mode debug : 'paragraph_key' (IA,
        # vue canonique) ou 'para_id' (géométrie).
        self.debug_para_attr = "paragraph_key"

    def configure_llm(self, api_key: str,
                      base_url: str = "https://api.deepseek.com",
                      model: str = "deepseek-v4-flash") -> None:
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
                     progress_callback=None,
                     pages=None):
        """
        Extrait chaque span de texte avec la totalité de ses métadonnées :
          - texte, bbox, origin (baseline exacte)
          - police, taille, couleur RGB, flags (gras/italique)
          - direction (horizontal ou rotation)
          - page_num
        """
        if output_json is None:
            output_json = str(Path(pdf_path).with_suffix("")) + "_extraction.json"

        extraction = {"pages": [], "vis_origin": True}
        element_types_used = {}

        try:
            doc = fitz.open(pdf_path)
            total = len(doc)

            # Collecte des polices embarquées du document source (xref → nom).
            # Chaque police sera extraite et sauvegardée pour être réutilisée
            # à l'injection, garantissant une fidélité parfaite de rendu.
            # Les noms PyMuPDF incluent un préfixe de sous-ensemble (ex.
            # "GUDYVK+AvenirLTStd-Book") ; on indexe SANS le préfixe pour
            # matcher le `font_raw` des spans (qui n'a pas le préfixe).
            # Une même police peut être embarquée en PLUSIEURS sous-ensembles
            # (un par jeu de glyphes / par groupe de pages) partageant le même
            # nom propre. On garde TOUS les sous-ensembles (un par xref) :
            # n'en retenir qu'un faisait échouer la couverture des glyphes des
            # autres pages → bascule sur un substitut (souvent plus léger).
            font_xrefs = {}
            for pg_num in range(total):
                try:
                    for xref, ext, ftype, base_name, *_ in doc.get_page_fonts(pg_num):
                        if ext == "n/a":
                            continue
                        # Retire le préfixe de sous-ensemble "XXXXXX+"
                        clean = base_name.split("+")[-1] if "+" in base_name else base_name
                        variants = font_xrefs.setdefault(clean, [])
                        if not any(v["xref"] == xref for v in variants):
                            variants.append({"xref": xref, "ext": ext,
                                             "base_name": base_name})
                except Exception:
                    pass
            extraction["font_xrefs"] = font_xrefs

            for page_num, page in enumerate(doc):
                page_data = {
                    "page_num": page_num + 1,
                    "width":    page.rect.width,
                    "height":   page.rect.height,
                    "text_blocks": []
                }

                # Hors plage sélectionnée : on conserve la page (l'injection la
                # recopiera à l'identique) mais on n'extrait AUCUN texte → elle
                # reste dans sa langue d'origine. `pages` est None = tout traduire.
                if pages is not None and (page_num + 1) not in pages:
                    extraction["pages"].append(page_data)
                    continue

                if progress_callback:
                    progress_callback(f"Extraction page {page_num + 1}/{total}...")

                raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

                # Origine x du PREMIER GLYPHE VISIBLE de chaque span (via
                # rawdict, niveau caractère). Le bbox/origine d'un span inclut
                # ses espaces de tête, dont l'avance varie (parfois nulle) :
                # cette table fournit la vraie position du 1er caractère non
                # blanc pour rendre le texte trimmé à la bonne place. Indexée
                # par bbox de span (identique entre dict et rawdict).
                vis_x0_map = {}
                try:
                    rawc = page.get_text("rawdict",
                                         flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    for rb in rawc.get("blocks", []):
                        for rl in rb.get("lines", []):
                            for rs in rl.get("spans", []):
                                for ch in rs.get("chars", []):
                                    if ch.get("c", " ").strip():
                                        bb = rs["bbox"]
                                        vis_x0_map[(round(bb[0], 1), round(bb[1], 1),
                                                    round(bb[2], 1))] = ch["origin"][0]
                                        break
                except Exception:
                    pass

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
                            bb = span["bbox"]
                            vx = vis_x0_map.get(
                                (round(bb[0], 1), round(bb[1], 1), round(bb[2], 1)))
                            if vx is not None:
                                span["_vis_x0"] = vx
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

                # Chaque groupe du regroupement intra-bloc (_group_paragraphs)
                # devient une entrée telle quelle : pas de fusion inter-blocs
                # (seul le regroupement des lignes wrap d'un même bloc PyMuPDF
                # est actif).
                for p_idx, group in enumerate(page_groups):
                    page_data["text_blocks"].append(
                        self._make_para_entry(group, page_num, 0, p_idx)
                    )

                # Paragraphes pivotés (titres verticaux de tableau) : regroupés
                # dans leur repère (colonnes = x, sens de lecture = y).
                for r_idx, group in enumerate(self._group_rotated_paragraphs(rotated_spans)):
                    page_data["text_blocks"].append(
                        self._make_para_entry(group, page_num, 9000, r_idx, rotated=True)
                    )

                # Annotation des PARAGRAPHES (cadres, écarts, ancres) — métadonnée
                # pour le futur reflux ; n'affecte PAS le rendu (identité intacte).
                try:
                    img_rects = [list(r) for info in page.get_images(full=True)
                                 for r in page.get_image_rects(info[0])]
                except Exception:
                    img_rects = []
                # Filets décoratifs : segments HORIZONTAUX longs (traits 'l' ou
                # fins rectangles 're') — délimitent souvent les encarts.
                rules = []
                try:
                    for d in page.get_drawings():
                        for it in d.get("items", []):
                            if it[0] == "l":
                                p1, p2 = it[1], it[2]
                                if abs(p1.y - p2.y) < 1.0 and abs(p2.x - p1.x) > 40:
                                    rules.append([min(p1.x, p2.x), p1.y,
                                                  max(p1.x, p2.x), p2.y])
                            elif it[0] == "re":
                                r = it[1]
                                if r.height < 3.0 and r.width > 40:
                                    rules.append([r.x0, r.y0, r.x1, r.y1])
                except Exception:
                    pass
                self._annotate_paragraphs(page_data, img_rects, rules)

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

                # Identification des paragraphes DÉLÉGUÉE au LLM (DeepSeek) :
                # on lui envoie id + texte + position de chaque bloc, il
                # attribue un identifiant de paragraphe partagé aux blocs d'un
                # même paragraphe → stocké dans block['paragraph_key'].
                # Métadonnée pure : n'affecte PAS le rendu (toujours bloc/bloc).
                self._llm_assign_paragraph_ids(page_data, progress_callback)

                # Groupement de référence = GÉOMÉTRIQUE (`para_id`) : il gère la
                # FUSION (paragraphe enroulé en L) ET la SÉPARATION (en-tête vs
                # n° de page, puces voisines) mieux que l'IA, qui se trompe dans
                # les deux sens. `paragraph_key` est aligné sur `para_id`.
                self._regroup_by_para_id(page_data)

                # Identification de l'alignement par paragraphe (Étape 0) :
                # signature multi-ligne + étirement intrinsèque (justifié) +
                # cadre de colonne (mono-ligne). Métadonnée pure.
                self._assign_paragraph_alignment(page_data)

                extraction["pages"].append(page_data)
                element_types_used[page_num + 1] = ["text_block"]

            # Inventaire des polices (le document est encore ouvert).
            try:
                fonts = self._font_inventory(doc, progress_callback)
                extraction["fonts"] = fonts
                # Les polices embarquées dans le PDF source (présentes dans
                # font_xrefs) sont extraites et réinjectées à l'identique :
                # elles ne sont PAS substituées, on les exclut de l'alerte.
                embedded_src = set(extraction.get("font_xrefs", {}))
                substituted = [f["name"] for f in fonts
                               if not f["exact"] and f["name"] not in embedded_src]
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

        # Carte police→classe (serif/sans/mono) déduite des drapeaux PyMuPDF
        # captés à l'extraction : alimente le repli général de substitution par
        # classe (_resolve_family_font). Tolérant aux JSON anciens sans le champ.
        self._doc_font_class = {}
        for pg in data.get("pages", []):
            for b in pg.get("text_blocks", []):
                fr = b.get("font")
                if not fr or "serif" not in b:
                    continue
                key = self._norm_font(fr)
                if key not in self._doc_font_class:
                    self._doc_font_class[key] = (
                        "mono" if b.get("mono") else
                        "serif" if b.get("serif") else "sans")

        # Garantit la disponibilité des polices AVANT rendu : pré-chargement
        # SYNCHRONE (borné par un budget) des familles manquantes, pour qu'elles
        # servent à CETTE sortie. Au-delà du budget, repli arrière-plan (substitut
        # ce coup-ci, police exacte au prochain rendu). Les familles déjà fidèles
        # (bundled/système/base-14) sont ignorées sans coût.
        try:
            import time as _time
            deadline = _time.time() + 25.0
            for fr in {b.get("font") for pg in data.get("pages", [])
                       for b in pg.get("text_blocks", []) if b.get("font")}:
                self._ensure_font(fr, progress_callback,
                                  synchronous=_time.time() < deadline)
            self._bundled = None  # ré-indexe backend/fonts/ avec les nouvelles polices
        except Exception:
            pass

        try:
            original_doc = fitz.open(original_pdf)
            new_doc      = fitz.open()
            pages        = data.get("pages", [])

            # Charge les polices embarquées du document source (collectées
            # à l'extraction) et les écrit sur disque. PyMuPDF n'accepte PAS
            # un buffer de police via insert_text(fontfile=...) (« bad
            # fontfile »), mais accepte un CHEMIN de fichier — y compris pour
            # les polices CFF/Type1. On extrait donc chaque police dans un
            # fichier temp : fidélité parfaite, TrueType comme CFF, sans
            # aucune substitution.
            self._source_fonts = {}
            font_xrefs = data.get("font_xrefs", {})
            if font_xrefs:
                fdir = os.path.join(str(self.temp_dir), "_srcfonts")
                os.makedirs(fdir, exist_ok=True)
                nfonts = 0
                for clean, info in font_xrefs.items():
                    # Compat : ancien JSON = 1 dict ; nouveau = liste de variantes
                    # (plusieurs sous-ensembles du même nom). On les écrit TOUS
                    # dans des fichiers distincts → la sélection à l'injection
                    # choisira celui qui couvre réellement le texte du bloc.
                    variants = info if isinstance(info, list) else [info]
                    for i, var in enumerate(variants):
                        try:
                            xref = var["xref"]
                            ext  = var["ext"]
                            buf = original_doc.extract_font(xref)[3]
                            if not buf:
                                continue
                            suffix = ".ttf" if ext == "ttf" else ".otf"
                            tag = "".join(ch for ch in clean if ch.isalnum())
                            fp = os.path.join(fdir, f"{tag}_{i}{suffix}")
                            with open(fp, "wb") as fh:
                                fh.write(buf)
                            self._source_fonts.setdefault(clean, []).append((fp, ext))
                            nfonts += 1
                        except Exception:
                            pass
                if progress_callback and self._source_fonts:
                    progress_callback(
                        f"✓ {nfonts} police(s) source embarquée(s) "
                        f"pour fidélité de rendu."
                    )
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
                    # Efface le texte d'origine à sa position (rectangle élargi).
                    bbox = block.get("bbox")
                    if not bbox or len(bbox) < 4:
                        continue
                    rect = fitz.Rect(bbox) + fitz.Rect(-1.5, -2, 1.5, 2)
                    new_page.add_redact_annot(rect, fill=None)

                new_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # Espace inter-blocs : un changement de style (mot souligné,
                # lien, gras…) coupe une ligne en plusieurs blocs ; l'espace qui
                # les séparait est retiré au .strip() de l'extraction mais reste
                # INCLUS dans la bbox du bloc de gauche (son x1 englobe l'espace
                # final). Sans le restituer, la condensation étire le texte
                # jusqu'au bord de la boîte et COLLE le bloc suivant
                # (« theInsight »). On rend donc un espace FINAL au bloc de
                # gauche d'une paire collée : sa boîte l'absorbe → aucun décalage
                # du bloc voisin, aucun débordement.
                _ATTACH = ",.;:!?)]}»’'%…"
                def _blk_base(b):
                    o = b.get("origin"); bb = b.get("bbox") or [0, 0, 0, 0]
                    return o[1] if o and len(o) >= 2 else bb[3]
                trail_space_ids = set()
                _ls = sorted(
                    [b for b in blocks
                     if abs(b.get("rotation", 0.0)) <= 1.0 and b.get("bbox")
                     and (b.get("translated_text") or b.get("text") or "").strip()],
                    key=lambda b: (round(_blk_base(b), 1), b["bbox"][0]))
                for _i in range(len(_ls) - 1):
                    _cur, _nxt = _ls[_i], _ls[_i + 1]
                    _sz = _cur.get("size", 12) or 12
                    if abs(_blk_base(_nxt) - _blk_base(_cur)) > 0.4 * _sz:
                        continue                       # pas la même ligne
                    _gap = _nxt["bbox"][0] - _cur["bbox"][2]
                    if not (-0.6 * _sz <= _gap <= 0.18 * _sz):
                        continue                       # collés uniquement
                    _ct = (_cur.get("translated_text") or _cur.get("text") or "").strip()
                    _nt = (_nxt.get("translated_text") or _nxt.get("text") or "").strip()
                    # pas d'espace après une césure (« mo- ») ni avant une
                    # ponctuation attachante (« , » « . » …).
                    if _ct and _nt and _ct[-1] != "-" and _nt[0] not in _ATTACH:
                        trail_space_ids.add(id(_cur))

                # Rendu BLOC PAR BLOC à la position d'origine. La fusion par
                # paragraphe et le reflux sont abandonnés (fidélité de mise en
                # page d'abord) : chaque bloc — horizontal ou pivoté — est rendu
                # seul dans sa boîte ; seuls la TAILLE (anti-débordement) et
                # l'ALIGNEMENT (Étape 1) sont ajustés.
                for block in blocks:
                    translated = ((block.get("translated_text") or "").strip()
                                  or (block.get("text") or "").strip())
                    if translated and id(block) in trail_space_ids:
                        translated = translated + " "

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
                    if block.get("multiline") and translated and abs(rotation) <= 1.0:
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

                    # Bloc mono-ligne PIVOTÉ (90°/270°) : l'ajustement de
                    # taille doit suivre l'axe de LECTURE — la hauteur de la
                    # bbox — et non sa largeur horizontale (épaisseur d'une
                    # ligne), sinon une traduction plus longue déborde de la
                    # cellule. L'insertion reste à la baseline d'origine.
                    if translated and abs(rotation) > 1.0:
                        rot_norm = int(round(rotation / 90.0)) * 90 % 360
                        if rot_norm in (90, 270):
                            self._insert_text_smart(
                                new_page, (x, y), translated, orig_size,
                                font_name, font_raw, color, rotation)
                            continue

                    # Réinjection identité : texte inchangé → taille d'origine,
                    # aucune réduction (la « réduction de police » servait à la
                    # traduction, écartée ici). Largeur = bbox d'origine stricte.
                    fontsize = orig_size
                    max_width = abs(bbox[2] - bbox[0])

                    text_x   = x
                    align_fit_w = None

                    # ── Rendu ALIGNÉ (Étape 1) — uniquement pour un bloc SEUL
                    # sur sa ligne (les lignes multi-fragments gardent leurs
                    # positions d'origine, déjà ≈ alignées). Le gauche (0) reste
                    # le comportement par défaut.
                    _al  = block.get("align", 0)
                    _ref = block.get("align_ref")
                    _solo = block.get("_align_line_solo", False)
                    if (_al and _ref and _solo and len(_ref) >= 2
                            and not (is_list and bullet_char)):
                        _L, _R = _ref
                        _tw = self._text_length(translated, fontsize,
                                                font_name, font_raw)
                        if _al == 3 and not block.get("_align_last_line") \
                                and " " in translated:
                            # Justifié : étire les blancs jusqu'à la marge R.
                            _target = _R - x
                            if 0 < _tw < _target <= 1.5 * _tw:
                                if self._insert_justified_line(
                                        new_page, (x, y), translated, fontsize,
                                        font_name, font_raw, color, _target):
                                    if is_underline:
                                        self._draw_underline(
                                            new_page, (x, y), translated,
                                            font_name, fontsize, color, rotation)
                                    continue
                        elif _al in (1, 2) and 0 < _tw <= (_R - _L):
                            # Centre : centre le texte dans le cadre ; droite :
                            # aligne sa fin sur R. Re-ancrage du point de départ.
                            text_x = (_L + ((_R - _L) - _tw) / 2.0) if _al == 1 \
                                else (_R - _tw)
                            align_fit_w = _R - text_x

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

                    # Couche 2 — largeur d'origine disponible : du début du
                    # texte jusqu'au bord droit de la bbox d'origine. Le texte
                    # est condensé horizontalement s'il la dépasse (substitut
                    # plus large / traduction plus longue), sinon inchangé.
                    # Largeur disponible : cadre d'alignement (centre/droite)
                    # si re-ancré, sinon bord droit de la bbox d'origine.
                    fit_w = align_fit_w if align_fit_w is not None \
                        else bbox[2] - text_x
                    text_inserted = self._insert_text_smart(
                        new_page, (text_x, y), translated, fontsize,
                        font_name, font_raw, color, rotation,
                        fit_width=fit_w
                    )

                    if text_inserted and is_underline and translated:
                        self._draw_underline(
                            new_page, (text_x, y), translated,
                            font_name, fontsize, color, rotation
                        )

                # DEBUG — bordures (toggle `self.debug_draw_borders`, n'affecte
                # pas le rendu normal) : un CONTOUR par paragraphe (VERT) =
                # UNION des bbox de ses blocs (regroupés par `para_id`). Le
                # contour épouse l'étendue RÉELLE de chaque ligne (bords droits
                # irréguliers, retraits, enroulement autour d'une image) : ce
                # n'est pas un rectangle englobant mais un tracé en escalier qui
                # cadre exactement les blocs du paragraphe. + images (ROUGE) +
                # filets (BLEU).
                if getattr(self, "debug_draw_borders", False):
                    # 1) regroupe les blocs horizontaux par clé de paragraphe.
                    #    Attribut configurable : 'para_id' (regroupement
                    #    GÉOMÉTRIQUE historique, défaut) ou 'paragraph_key'
                    #    (regroupement IA délégué à DeepSeek) — permet de
                    #    comparer visuellement les deux stratégies.
                    _para_attr = getattr(self, "debug_para_attr", "para_id")
                    _align_mode = getattr(self, "debug_draw_alignment", False)
                    _by_para = {}
                    _align_by_key = {}     # key -> (align, conf)
                    _ref_by_key = {}       # key -> [L, R] (cadre inféré)
                    for _b in blocks:
                        if abs(_b.get("rotation", 0.0)) > 1.0:
                            continue
                        _bb = _b.get("bbox")
                        if not _bb or len(_bb) < 4 or _bb[2] <= _bb[0] or _bb[3] <= _bb[1]:
                            continue
                        _pid = _b.get(_para_attr)
                        _key = _pid if _pid is not None else f"solo{id(_b)}"
                        _o = _b.get("origin")
                        _base = _o[1] if _o and len(_o) >= 2 else _bb[3]
                        _by_para.setdefault(_key, []).append(
                            (_base, max(6.0, _b.get("size", 10)), list(_bb[:4])))
                        _align_by_key[_key] = (_b.get("align", 0), _b.get("align_conf"))
                        _ref_by_key[_key] = _b.get("align_ref")

                    # Couleurs par alignement : gauche=vert, centre=bleu,
                    # droite=orange, justifié=violet.
                    _ALIGN_COL = {0: (0, 0.6, 0), 1: (0, 0.3, 1),
                                  2: (1, 0.55, 0), 3: (0.6, 0, 0.8)}

                    for _key, _members in _by_para.items():
                        # 2) lignes du paragraphe = blocs partageant une baseline ;
                        #    chaque ligne = étendue réelle [left, y0, right, y1].
                        _members.sort(key=lambda m: (round(m[0], 1), m[2][0]))
                        _rows = []
                        for _base, _sz, _bb in _members:
                            if _rows and abs(_base - _rows[-1]["base"]) <= 0.3 * _sz:
                                _r = _rows[-1]
                                _r["l"] = min(_r["l"], _bb[0]); _r["t"] = min(_r["t"], _bb[1])
                                _r["r"] = max(_r["r"], _bb[2]); _r["b"] = max(_r["b"], _bb[3])
                            else:
                                _rows.append({"base": _base, "l": _bb[0], "t": _bb[1],
                                              "r": _bb[2], "b": _bb[3]})
                        if not _rows:
                            continue
                        # 3) frontière nette entre lignes voisines (milieu du
                        #    chevauchement vertical) → escalier propre, sans
                        #    auto-intersection.
                        for _i in range(len(_rows) - 1):
                            _mid = (_rows[_i]["b"] + _rows[_i + 1]["t"]) / 2
                            _rows[_i]["b"] = _mid
                            _rows[_i + 1]["t"] = _mid
                        # 4) contour rectilinéaire : côté droit haut→bas, côté
                        #    gauche bas→haut, fermé.
                        _pts = []
                        for _r in _rows:
                            _pts.append((_r["r"], _r["t"])); _pts.append((_r["r"], _r["b"]))
                        for _r in reversed(_rows):
                            _pts.append((_r["l"], _r["b"])); _pts.append((_r["l"], _r["t"]))
                        _pts.append(_pts[0])
                        if _align_mode:
                            _al, _cf = _align_by_key.get(_key, (0, None))
                            _col = _ALIGN_COL.get(_al, (0, 0.6, 0))
                            new_page.draw_polyline(_pts, color=_col, width=1.0)
                            # Cadre de colonne inféré [L, R] : tirets gris sur
                            # la hauteur du paragraphe (référence du mono-ligne).
                            _ref = _ref_by_key.get(_key)
                            if _ref and len(_ref) >= 2:
                                _yt = min(_r["t"] for _r in _rows)
                                _yb = max(_r["b"] for _r in _rows)
                                for _vx in (_ref[0], _ref[1]):
                                    new_page.draw_line((_vx, _yt), (_vx, _yb),
                                                       color=(0.6, 0.6, 0.6),
                                                       width=0.4, dashes="[2 2] 0")
                        else:
                            new_page.draw_polyline(_pts, color=(0, 0.55, 0), width=0.8)

                    # ── Objets NON-TEXTUELS → cadre ROUGE (images, filets/
                    # lignes, formes, fonds…). Lus sur la page ORIGINALE pour ne
                    # pas encadrer les contours verts de cet overlay. On EXCLUT
                    # les soulignements (segment fin horizontal collé sous une
                    # baseline de texte — ils appartiennent au texte).
                    _op = original_doc[page_idx]
                    _bls = []        # baselines de texte : (y, x0, x1)
                    for _tb in blocks:
                        if abs(_tb.get("rotation", 0.0)) > 1.0:
                            continue
                        _ob = _tb.get("bbox"); _oo = _tb.get("origin")
                        if not _ob or len(_ob) < 4:
                            continue
                        _by = _oo[1] if _oo and len(_oo) >= 2 else _ob[3]
                        _bls.append((_by, _ob[0], _ob[2]))

                    def _is_underline(r):
                        if (r.y1 - r.y0) > 3.0 or (r.x1 - r.x0) < 5.0:
                            return False          # trop épais ou trop court
                        for _by, _x0, _x1 in _bls:
                            if not (-2.0 <= r.y0 - _by <= 5.0):
                                continue
                            ov = min(r.x1, _x1) - max(r.x0, _x0)
                            if ov > 0.3 * min(r.x1 - r.x0, max(1.0, _x1 - _x0)):
                                return True
                        return False

                    _seen_obj = set()

                    def _red_frame(r):
                        if r.x1 < r.x0 or r.y1 < r.y0:
                            return
                        # rect dégénéré (ligne) → épaissi pour rester visible
                        if (r.x1 - r.x0) < 1 or (r.y1 - r.y0) < 1:
                            r = fitz.Rect(r.x0 - 0.8, r.y0 - 0.8,
                                          r.x1 + 0.8, r.y1 + 0.8)
                        _k = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
                        if _k in _seen_obj:
                            return
                        _seen_obj.add(_k)
                        new_page.draw_rect(r, color=(1, 0, 0), width=0.8)

                    for _img in _op.get_images(full=True):       # images
                        try:
                            for _r in _op.get_image_rects(_img[0]):
                                _red_frame(fitz.Rect(_r))
                        except Exception:
                            pass
                    for _d in _op.get_drawings():                 # objets vectoriels
                        _r = _d.get("rect")
                        if _r is None:
                            continue
                        _r = fitz.Rect(_r)
                        if (_r.x1 - _r.x0) < 1 and (_r.y1 - _r.y0) < 1:
                            continue
                        if _is_underline(_r):
                            continue
                        _red_frame(_r)

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
        "sourcesanspro": "segoeui", "sourcesans": "segoeui",
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
        # — Polices éditeur (Avenir, Minion…) → substituts Google Fonts —
        # Avenir est une police commerciale. Montserrat est le meilleur
        # substitut gratuit (géométrique, mêmes proportions).
        "avenir": "montserrat", "avenirltstd": "montserrat",
        "minionpro": "georgia",
        # — Mono → Consolas —
        "robotomono": "consolas", "sourcecodepro": "consolas", "firacode": "consolas",
        "firamono": "consolas", "jetbrainsmono": "consolas", "inconsolata": "consolas",
        "spacemono": "consolas", "ibmplexmono": "consolas", "ubuntumono": "consolas",
        "courierprime": "consolas", "cousine": "consolas", "anonymouspro": "consolas",
        "overpassmono": "consolas",
    }
    # Repli GÉNÉRAL de classe : toute police introuvable (ni base-14, ni
    # bundled, ni système, ni _FONT_SIMILAR) est routée vers un substitut LOCAL
    # de MÊME CLASSE (serif→PT Serif, sans→Open Sans) au lieu de tomber sur
    # Helvetica base-14 — qui transformait une serif en sans et élargissait le
    # texte (espaces inter-mots mangés). La classe vient d'abord du DRAPEAU
    # serif/mono de PyMuPDF (fiable, capté à l'extraction), sinon de tokens de
    # NOM ci-dessous. Aucune police n'est énumérée : vaut pour tout document.
    _SERIF_NAME_TOKENS = (
        "serif", "times", "georgia", "garamond", "minion", "caslon",
        "baskerville", "palatino", "cambria", "century", "bodoni", "didot",
        "sabon", "antiqua", "slab", "plantin", "sylfaen", "constantia",
        "merriweather", "lora", "playfair", "spectral", "cormorant",
        "freight", "chronicle", "miller", "utopia", "scala",
    )
    _MONO_NAME_TOKENS = (
        "mono", "consol", "courier", "typewriter", "menlo", "monaco",
        "inconsolata", "jetbrains", "fira code", "firacode",
    )
    _CLASS_FALLBACK_FAMILY = {"serif": "ptserif", "sans": "opensans"}
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
        # 3. substitut de même classe (serif/sans/mono) — d'abord dans
        #    backend/fonts/ (police téléchargée), puis système, puis bundled.
        sim = self._FONT_SIMILAR.get(key)
        if sim:
            r = self._bundled_lookup(sim, bold, italic) \
                or self._family_variant_file(sim, bold, italic)
            if r:
                return r
        # 4. REPLI GÉNÉRAL : police inconnue → substitut LOCAL de même classe
        #    (serif→PT Serif, sans→Open Sans). Évite Helvetica base-14 qui
        #    rend une serif en sans. Mono → None (Courier base-14 via _map_font).
        fam_key = self._CLASS_FALLBACK_FAMILY.get(self._font_class(font_raw))
        if fam_key:
            r = self._bundled_lookup(fam_key, bold, italic)
            if r:
                return r
        return None

    def _font_class(self, font_raw):
        """Classe d'une police : 'serif' | 'sans' | 'mono'. Source FIABLE = le
        drapeau serif/mono PyMuPDF capté à l'extraction (self._doc_font_class) ;
        à défaut (JSON ancien, appel hors document), heuristique sur le nom.
        Règle générale, aucune police énumérée."""
        c = self._doc_font_class.get(self._norm_font(font_raw or ""))
        if c:
            return c
        n = (font_raw or "").lower()
        if any(t in n for t in self._MONO_NAME_TOKENS):
            return "mono"
        if any(t in n for t in self._SERIF_NAME_TOKENS):
            return "serif"
        return "sans"

    # ── Téléchargement automatique des polices manquantes (Google Fonts) ──────
    _GOOGLE_SLUG = {  # corrections clé normalisée → dossier du dépôt google/fonts
        "sourcesanspro": "sourcesans3", "sourceserifpro": "sourceserif4",
        "ptsans": "ptsans", "ptserif": "ptserif",
        # Avenir (commercial) → Montserrat (meilleur substitut open-source)
        "avenir": "montserrat", "avenirltstd": "montserrat",
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

    def _ensure_font(self, font_raw, progress_callback=None, synchronous=False):
        """Si la famille `font_raw` n'est PAS déjà reproductible fidèlement
        (bundled / système / base-14 / symbole), télécharge la vraie police
        depuis Google Fonts vers backend/fonts/. Best-effort : toute erreur
        (hors-ligne, police absente du dépôt, fonttools absent…) est silencieuse.

        `synchronous` : si True, télécharge EN BLOQUANT pour que la police serve
        à CETTE sortie (pré-chargement à l'injection) ; sinon en arrière-plan
        (la sortie courante utilise le substitut, la suivante la police exacte)."""
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
                                f"✓ Police téléchargée : {font_raw} → backend/fonts/")
                        except Exception:
                            pass
                else:
                    self._dl_tried().add(key)
                    self._mark_dl_failed(key)
                with _FONT_DL_LOCK:
                    _FONT_DL_INFLIGHT.discard(key)

        if synchronous:
            _worker()
            return
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
            _have_ft = True
        except Exception:
            _have_ft = False  # pas d'instanciation de variable → voie statique seule

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

        # ── Voie A — fichiers STATIQUES (Regular/Bold/Italic/BoldItalic) ──────
        # Beaucoup de familles (PT Serif, Roboto, Open Sans…) sont livrées en
        # fichiers statiques tels quels dans le dépôt : on les enregistre
        # DIRECTEMENT, SANS fonttools (leur table de noms distingue déjà les
        # variantes). Couvre le cas où fonttools est absent.
        static = [i for i in ttfs if "[" not in i.get("name", "")]

        def _has(nm, words):
            n = nm.lower()
            return any(w in n for w in words)

        if static:
            for suffix, bold, italic in (("Regular", False, False),
                                         ("Bold", True, False),
                                         ("Italic", False, True),
                                         ("BoldItalic", True, True)):
                it = next((i for i in static
                           if _has(i["name"], ("bold", "black", "heavy")) == bold
                           and _has(i["name"], ("italic", "oblique")) == italic), None)
                if not it:
                    continue
                try:
                    with open(os.path.join(self._BUNDLED_FONT_DIR,
                                           f"{fam}-{suffix}.ttf"), "wb") as fh:
                        fh.write(fetch(it["download_url"]))
                    saved = True
                except Exception:
                    pass
            if saved:
                return True

        # ── Voie B — police VARIABLE → instances de graisse via fonttools ─────
        if _have_ft:
            gen(pick(False), [(400, "Regular", False, False), (700, "Bold", True, False)])
            gen(pick(True), [(400, "Italic", False, True), (700, "BoldItalic", True, True)])
        elif ttfs:
            # Sans fonttools : enregistre la variable comme Regular (best-effort
            # — famille correcte, graisse par défaut ; gras/italique par substitut).
            v = next((i for i in ttfs if "italic" not in i["name"].lower()), ttfs[0])
            try:
                with open(os.path.join(self._BUNDLED_FONT_DIR,
                                       f"{fam}-Regular.ttf"), "wb") as fh:
                    fh.write(fetch(v["download_url"]))
                saved = True
            except Exception:
                pass
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

    def _glyph_renders(self, fpath, cp):
        """True si le codepoint `cp` produit RÉELLEMENT de l'encre avec la
        police `fpath`. `has_glyph` (présence dans la cmap) ne suffit PAS :
        certains sous-ensembles CFF extraits d'un PDF passent `has_glyph` mais
        rendent un glyphe VIDE (contour absent / encodage CID non reconstituable
        depuis l'unicode). Seul un rendu réel le détecte. Mis en cache par
        (fichier, codepoint) → coût payé une seule fois par glyphe."""
        if not hasattr(self, "_glyph_render_cache"):
            self._glyph_render_cache = {}
        cache = self._glyph_render_cache.setdefault(fpath, {})
        if cp in cache:
            return cache[cp]
        ok = False
        try:
            d = fitz.open()
            pg = d.new_page(width=40, height=40)
            pg.insert_text((6, 30), chr(cp), fontsize=24,
                           fontname="probe", fontfile=fpath, color=(0, 0, 0))
            pm = pg.get_pixmap(colorspace=fitz.csGRAY, alpha=False)
            ok = sum(1 for b in pm.samples if b < 200) >= 3
            d.close()
        except Exception:
            ok = False
        cache[cp] = ok
        return ok

    def _embed_font_for(self, text, font_raw):
        """Retourne (fontkey, fontfile) de la police à embarquer pour rendre
        `text` fidèlement, ou None si une police de base suffit.

        Priorité :
        0. Police extraite du PDF source (fidélité parfaite).
        1. Police de la famille d'origine (bundled > système > similar > fallback).
        2. Polices de secours Unicode pour les glyphes hors base-14."""
        needed = {ord(c) for c in text if ord(c) > 0xFF}

        # Étape 0 — police extraite du document source (fidélité parfaite).
        # Le buffer a été écrit dans un fichier temp : PyMuPDF le charge via
        # fontfile=<chemin>, TrueType comme CFF/Type1. La police d'origine est
        # souvent un SOUS-ENSEMBLE (seuls les glyphes du doc source) : on ne
        # l'utilise que si elle couvre TOUT le texte à rendre, sinon un
        # caractère traduit absent (ex. « é », « ç ») produirait un glyphe
        # manquant → on bascule alors sur la chaîne de secours normale.
        source_fonts = getattr(self, "_source_fonts", None) or {}
        clean = font_raw.split("+")[-1] if "+" in font_raw else font_raw
        variants = source_fonts.get(font_raw) or source_fonts.get(clean)
        if variants:
            # Compat ancien format (tuple unique) vs nouveau (liste de variantes).
            if isinstance(variants, tuple):
                variants = [variants]
            need = [ord(c) for c in set(text) if not c.isspace()]
            for fpath, _ext in variants:
                # fontkey UNIQUE par fichier : deux sous-ensembles du même nom
                # ne doivent pas être enregistrés sous le même fontname dans la
                # page (PyMuPDF réutiliserait le premier buffer → mauvais glyphes).
                stem = os.path.splitext(os.path.basename(fpath))[0]
                fontkey = "".join(ch for ch in stem if ch.isalnum()) or "srcfont"
                try:
                    fnt = fitz.Font(fontfile=fpath)
                except Exception:
                    continue
                # `has_glyph` = pré-filtre rapide mais NON FIABLE (un sous-
                # ensemble peut le passer puis rendre un glyphe vide). On confirme
                # par un RENDU RÉEL de chaque glyphe : sinon on rejette cette
                # variante et on bascule sur le substitut complet (texte visible
                # plutôt que des lettres manquantes).
                if not all(fnt.has_glyph(cp) for cp in need):
                    continue
                if all(self._glyph_renders(fpath, cp) for cp in need):
                    return fontkey, fpath

        fam = self._resolve_family_font(font_raw)
        if not needed:
            return fam

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

    def _write_line(self, page, point, text, fontsize, color,
                    fontname=None, fontfile=None, hscale=1.0):
        """Écrit une ligne de texte, éventuellement CONDENSÉE horizontalement
        (`hscale` < 1) autour de son origine. La condensation passe par un
        TextWriter + `morph=(origine, Matrix(hscale, 1))` : le texte garde sa
        baseline et son point de départ, seule sa largeur est réduite."""
        if hscale >= 0.999:
            page.insert_text(point, text, fontsize=fontsize,
                             fontname=fontname, fontfile=fontfile, color=color)
            return
        tw = fitz.TextWriter(page.rect)
        font = self._get_font(fontfile) if fontfile else fitz.Font(fontname)
        tw.append(fitz.Point(point), text, fontsize=fontsize, font=font)
        tw.write_text(page, color=color,
                      morph=(fitz.Point(point), fitz.Matrix(hscale, 1)))

    def _insert_text_smart(self, page, point, text, fontsize,
                           font_mapped, font_raw, color, rotation, fit_width=None):
        """Insère du texte en embarquant une police Unicode si la police de base
        ne peut pas représenter certains glyphes. Retourne True si écrit.

        `fit_width` (couche 2) : largeur d'origine disponible. Si la largeur
        NATURELLE du texte la dépasse, le texte est condensé horizontalement
        pour l'occuper exactement — supprime la dérive d'un substitut un peu
        plus large et borne le débordement d'une traduction plus longue. On ne
        fait que CONDENSER (jamais étirer) : no-op si la police rend déjà à la
        bonne largeur (sous-ensemble source exact)."""
        # Couche 2 — facteur de condensation horizontale (texte non pivoté).
        hscale = 1.0
        if fit_width and fit_width > 1 and abs(rotation) <= 1.0:
            nat = self._text_length(text, fontsize, font_mapped, font_raw)
            if nat > fit_width:
                hscale = max(0.60, fit_width / nat)

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
                    self._write_line(page, point, text, fontsize, color,
                                     fontname=fontkey, fontfile=fontfile,
                                     hscale=hscale)
                return True
            except Exception:
                pass  # bascule sur le chemin base-14 ci-dessous

        try:
            if abs(rotation) > 1.0:
                self._insert_rotated_text(page, point, text, fontsize,
                                          font_mapped, color, rotation)
            else:
                self._write_line(page, point, text, fontsize, color,
                                 fontname=font_mapped, hscale=hscale)
            return True
        except Exception:
            try:
                page.insert_text(point, text, fontsize=max(fontsize, 6),
                                 fontname="helv", color=(0, 0, 0))
                return True
            except Exception:
                return False

    def _insert_justified_line(self, page, point, text, fontsize,
                               font_mapped, font_raw, color, target_w):
        """Rend une ligne JUSTIFIÉE : répartit l'excédent (target_w − largeur
        naturelle des mots) dans les blancs inter-mots, mot par mot. Repli sur
        un rendu simple si l'étirement requis est aberrant. Retourne True si
        rendu."""
        words = text.split()
        if len(words) < 2:
            return self._insert_text_smart(page, point, text, fontsize,
                                           font_mapped, font_raw, color, 0.0)
        ws = [self._text_length(w, fontsize, font_mapped, font_raw) for w in words]
        space_w = self._text_length(" ", fontsize, font_mapped, font_raw) \
            or 0.3 * fontsize
        gap = (target_w - sum(ws)) / (len(words) - 1)
        # Garde-fou : ne pas fabriquer de blancs absurdes (< espace normal ou
        # > 3,5×) — sinon rendu simple, mieux vaut un bord droit légèrement
        # irrégulier qu'une ligne aérée.
        if gap < space_w or gap > 3.5 * space_w:
            return self._insert_text_smart(page, point, text, fontsize,
                                           font_mapped, font_raw, color, 0.0)
        x, y = point
        ok = True
        for i, w in enumerate(words):
            ok = self._insert_text_smart(page, (x, y), w, fontsize, font_mapped,
                                         font_raw, color, 0.0) and ok
            x += ws[i] + gap
        return ok

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




    def _llm_assign_paragraph_ids(self, page_data, progress_callback=None):
        """Délègue ENTIÈREMENT au LLM (DeepSeek) l'identification des blocs
        appartenant au MÊME paragraphe sur une page.

        On lui transmet, pour chaque bloc, son `id`, son `texte` et sa
        position (`bbox`). Il renvoie un identifiant de paragraphe par bloc :
        les blocs d'un même paragraphe partagent le même identifiant. Le
        résultat est écrit dans block['paragraph_key'] — MÉTADONNÉE PURE,
        sans aucun effet sur le rendu (qui reste bloc par bloc, fidélité
        intacte).

        Repli (LLM absent, page triviale, ou erreur) : on RETOMBE sur le
        regroupement GÉOMÉTRIQUE (`para_id`, posé par _annotate_paragraphs)
        quand il existe — sinon chaque bloc reste seul. Ainsi le champ
        `paragraph_key` porte toujours le meilleur regroupement disponible :
        l'IA en priorité, la géométrie en secours (jamais des blocs tous
        isolés tant qu'une structure géométrique a été détectée)."""
        blocks = [b for b in page_data.get("text_blocks", [])
                  if (b.get("text") or "").strip()]
        if not blocks:
            return

        page_num = page_data.get("page_num", "?")

        # Défaut / repli : reprend le regroupement géométrique (`para_id`).
        # Garanti même si le LLM échoue → `paragraph_key` existe toujours et
        # vaut au moins la géométrie.
        for b in blocks:
            pid = b.get("para_id")
            b["paragraph_key"] = (f"p{page_num}_geom{pid}"
                                  if pid is not None else b["id"])

        # Option géométrique (désactivée par défaut) : on s'arrête au repli
        # ci-dessus → paragraph_key = regroupement géométrique, sans DeepSeek.
        if (self._llm_client is None or len(blocks) < 2
                or not getattr(self, "use_llm_paragraph_grouping", True)):
            return

        items = [{
            "id":    b["id"],
            "texte": (b.get("text") or "").strip()[:200],
            "bbox":  [round(v, 1) for v in (b.get("bbox") or [])[:4]],
        } for b in blocks]

        prompt = (
            "Tu analyses les blocs de texte d'UNE page de PDF. Chaque bloc a "
            "un id, son texte et sa position [x0, y0, x1, y1] (origine en haut "
            "à gauche, y croît vers le bas).\n"
            "Regroupe les blocs qui appartiennent au MÊME paragraphe logique "
            "(même phrase coupée par un retour à la ligne, suite d'un même "
            "alinéa). Des blocs distincts — titre, puce d'une autre entrée, "
            "colonne voisine, en-tête/pied de page — NE doivent PAS être "
            "regroupés.\n"
            "Attribue à chaque bloc un numéro de paragraphe (entier ≥ 1). Les "
            "blocs d'un même paragraphe partagent le même numéro ; un bloc seul "
            "a son propre numéro.\n"
            "Réponds UNIQUEMENT en JSON : "
            "{\"blocs\": [{\"id\": \"...\", \"paragraphe\": 1}, ...]} — un objet "
            "par bloc reçu, sans rien omettre.\n\n"
            f"Blocs :\n{json.dumps(items, ensure_ascii=False)}"
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
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            mapping = {}
            for d in data.get("blocs", []):
                bid, para = d.get("id"), d.get("paragraphe")
                if bid is not None and para is not None:
                    mapping[bid] = para
            for b in blocks:
                para = mapping.get(b["id"])
                if para is not None:
                    b["paragraph_key"] = f"p{page_num}_para{para}"
            if progress_callback:
                n_para = len({b["paragraph_key"] for b in blocks})
                progress_callback(
                    f"  ↳ Page {page_num} : {len(blocks)} blocs → "
                    f"{n_para} paragraphe(s) (DeepSeek)."
                )
        except Exception as e:
            if progress_callback:
                progress_callback(
                    f"  ↳ Page {page_num} : regroupement LLM indisponible "
                    f"({type(e).__name__}) — repli sur la géométrie (para_id)."
                )


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
        """Déduit l'alignement d'un paragraphe à partir de ses lignes :
        0=gauche, 1=centre, 2=droite, 3=JUSTIFIÉ.
        - justifié : débuts ET fins alignés sur les marges, SAUF la dernière
          ligne (laissée courte) → nécessite ≥2 lignes pleines ;
        - gauche : seuls les débuts alignés ; droite : seules les fins ;
          centre : centres alignés.
        Texte pivoté 90° (lecture bas→haut) : axe vertical, début=bas (y1),
        fin=haut (y0). Les lignes sont triées en ordre de lecture pour isoler
        de façon fiable la DERNIÈRE ligne (exclue du test de marge droite)."""
        if len(spans) < 2:
            return 0
        if rotated:
            order   = sorted(spans, key=lambda s: -s["bbox"][3])     # bas→haut
            starts  = [s["bbox"][3] for s in order]                  # bas (y1)
            ends    = [s["bbox"][1] for s in order]                  # haut (y0)
            centers = [(s["bbox"][1] + s["bbox"][3]) / 2 for s in order]
            extent  = max(s["bbox"][3] for s in spans) - min(s["bbox"][1] for s in spans)
        else:
            order   = sorted(spans, key=lambda s: s["bbox"][1])      # haut→bas
            starts  = [s["bbox"][0] for s in order]                  # gauche (x0)
            ends    = [s["bbox"][2] for s in order]                  # droite (x1)
            centers = [(s["bbox"][0] + s["bbox"][2]) / 2 for s in order]
            extent  = max(s["bbox"][2] for s in spans) - min(s["bbox"][0] for s in spans)
        tol    = max(2.5, 0.03 * extent)
        spread = lambda v: max(v) - min(v)
        starts_aligned = spread(starts) <= tol
        # Justifié : débuts alignés ET fins des lignes PLEINES (toutes sauf la
        # dernière) alignées sur la marge droite, AVEC une dernière ligne plus
        # courte. ≥2 lignes pleines. Pas de faux positif sur du gauche-ragueux
        # (ses fins ne sont pas alignées).
        if (starts_aligned and len(ends) >= 3
                and spread(ends[:-1]) <= tol and spread(ends) > tol):
            return 3
        if starts_aligned:
            return 0
        if spread(ends) <= tol:
            return 2
        if spread(centers) <= tol:
            return 1
        return 0

    # ══════════════════════════════════════════════════════════════════════════
    # IDENTIFICATION DE L'ALIGNEMENT — métadonnée par paragraphe
    # ══════════════════════════════════════════════════════════════════════════
    # PRINCIPE CLÉ : tout alignement (détection ET rendu) est jugé RELATIVEMENT
    # AU BLOC DU PARAGRAPHE — sa propre boîte [min x0, max x1] de ses lignes —
    # jamais la page ni la colonne. Un n° de page « à droite de la PAGE » n'est
    # pas « à droite de son BLOC » ; un encart justifié se justifie sur SA boîte.
    #   • justifié → fins des lignes PLEINES alignées + dernière ligne courte
    #                (mesuré sur les fins, indépendant des débuts → robuste à un
    #                encart qui indente certaines lignes) ;
    #   • centré/droite → centres / fins alignés ;
    #   • mono-ligne → remplit sa propre boîte → neutre (gauche).
    # Sortie par bloc : align (0=g,1=c,2=d,3=just), align_conf, align_ref=[L,R].

    def _compute_alignment(self, lines, frame, page_w, col_right=None):
        """Retourne (align, confiance) pour un paragraphe, jugé PAR GÉOMÉTRIE
        (aucune estimation de largeur de police, peu fiable sur serif/italique).
        Le JUSTIFIÉ repose sur le bord droit COMMUN des lignes pleines : elles
        finissent toutes au même x (variance ~0), là où un paragraphe en drapeau
        a un bord droit irrégulier. Quand une SEULE ligne est pleine (parag. de
        2 lignes), justifié et drapeau sont indiscernables par la seule boîte du
        bloc → on regarde si cette ligne atteint la marge de COLONNE `col_right`
        (déduite de la page).  align : 0=gauche 1=centre 2=droite 3=justifié."""
        L, R = frame
        W = max(1.0, R - L)
        starts  = [ln["x0"] for ln in lines]
        ends    = [ln["x1"] for ln in lines]
        centers = [(ln["x0"] + ln["x1"]) / 2 for ln in lines]
        tol     = max(2.5, 0.03 * W)      # tolérance générale (débuts, centres)
        tol_end = max(2.0, 0.012 * W)     # fins d'un justifié : quasi exactes
        sp = lambda v: max(v) - min(v)
        n = len(lines)

        if n >= 2:
            last_short = ends[-1] < R - tol
            sa = sp(starts) <= tol
            ca = sp(centers) <= tol
            # Lignes PLEINES = toutes sauf une éventuelle dernière plus courte.
            full = ends[:-1] if last_short else ends
            nfull = len(full)
            ends_tight  = nfull >= 1 and sp(full) <= tol_end   # 1 seule marge
            reaches_col = (col_right is not None
                           and ends[0] >= col_right - tol_end)
            # Bord droit « régulier » d'un justifié : ses lignes pleines se
            # calent sur 1-2 MARGES DISCRÈTES (la colonne, et la pleine largeur
            # quand le texte s'enroule autour d'un encart) — chaque marge est
            # partagée par ≥2 lignes. Un drapeau a des fins TOUTES différentes.
            ends_grouped = nfull >= 2 and (
                ends_tight or
                sum(1 for v in full
                    if sum(1 for w in full if abs(w - v) <= tol_end) >= 2)
                >= 0.75 * nfull)

            # JUSTIFIÉ — bord droit régulier AVEC (dernière ligne courte OU
            # débuts alignés), MÊME si débuts/fins sont irréguliers à cause d'un
            # encart (lignes étroites puis pleine largeur). 1 seule ligne pleine
            # (parag. de 2 lignes) : exiger la marge de COLONNE.
            if (ends_grouped and (last_short or sa)) \
                    or (ends_tight and sa and reaches_col):
                return 3, (0.9 if nfull >= 2 else 0.8)
            # DROITE : une seule marge, débuts NON alignés, dernière ligne AUSSI
            # à droite (pas de ligne courte → ce n'est pas un justifié).
            if ends_tight and not sa and not last_short:
                return 2, 0.78
            # CENTRÉ : centres alignés, ni débuts ni fins alignés.
            if ca and not sa and not ends_tight:
                return 1, 0.8
            # GAUCHE par défaut (débuts alignés, bord droit en drapeau).
            return 0, (0.85 if sa and n >= 3 else 0.5)

        # ── mono-ligne : indéterminable par sa seule boîte. On n'autorise que
        # le CENTRÉ, et UNIQUEMENT par symétrie vs la PAGE (titre centré : centre
        # de la ligne ≈ centre de page, marges gauche/droite LARGES et ~égales).
        # Un n° de page (collé à droite) ou une ligne à gauche → marges
        # asymétriques → neutre (gauche), position d'origine préservée.
        x0, x1 = starts[0], ends[0]
        cl = (x0 + x1) / 2.0
        gl, gr = x0, page_w - x1
        if (abs(cl - page_w / 2.0) <= 0.035 * page_w
                and gl > 0.03 * page_w and gr > 0.03 * page_w
                and abs(gl - gr) <= 0.06 * page_w):
            return 1, 0.6
        return 0, 0.3

    @staticmethod
    def _regroup_by_para_id(page_data):
        """Aligne `paragraph_key` sur le groupement GÉOMÉTRIQUE `para_id`
        (_annotate_paragraphs) quand il existe. La géométrie gère mieux que l'IA
        à la fois la FUSION (paragraphe enroulé en L autour d'un encart) ET la
        SÉPARATION (l'IA groupe parfois un en-tête avec son numéro de page, ou
        deux puces voisines — la géométrie les distingue par colonne / item).
        Les blocs sans `para_id` (marqueurs de puce, texte pivoté) gardent la
        clé IA déjà posée. Déterministe, sans coût API."""
        page_num = page_data.get("page_num", "?")
        for b in page_data.get("text_blocks", []):
            pid = b.get("para_id")
            if pid is not None:
                b["paragraph_key"] = f"p{page_num}_pid{pid}"

    def _assign_paragraph_alignment(self, page_data):
        """Calcule l'alignement de CHAQUE paragraphe (regroupé par
        `paragraph_key`) et l'écrit sur ses blocs : `align`, `align_conf`,
        `align_ref`. MÉTADONNÉE — n'affecte pas le rendu."""
        blocks = [b for b in page_data.get("text_blocks", [])
                  if (b.get("text") or "").strip()
                  and abs(b.get("rotation", 0.0)) <= 1.0 and b.get("bbox")]
        if not blocks:
            return
        page_w = page_data.get("width", 595)

        groups = {}
        for b in blocks:
            groups.setdefault(b.get("paragraph_key", b["id"]), []).append(b)

        def _base(b):
            o = b.get("origin")
            return o[1] if o and len(o) >= 2 else b["bbox"][3]

        # 1re passe : découper chaque paragraphe en LIGNES (par baseline).
        built = []
        for members in groups.values():
            ordered = sorted(members, key=lambda b: (round(_base(b), 1),
                                                     b["bbox"][0]))
            lines = []
            for b in ordered:
                bs = _base(b)
                sz = max(6.0, b.get("size", 10))
                bb = b["bbox"]
                txt = (b.get("text") or "").strip()
                if lines and abs(bs - lines[-1]["base"]) <= 0.3 * sz:
                    ln = lines[-1]
                    ln["x0"] = min(ln["x0"], bb[0])
                    ln["x1"] = max(ln["x1"], bb[2])
                    ln["text"] = (ln["text"] + " " + txt).strip()
                    ln["blocks"].append(b)
                else:
                    lines.append({"base": bs, "size": sz, "x0": bb[0], "x1": bb[2],
                                  "text": txt, "blocks": [b],
                                  "font_mapped": b.get("font_mapped", "helv"),
                                  "font": b.get("font", "")})
            if lines:
                built.append((members, lines))

        # 2e passe — PRÉ-CLASSEMENT sans marge de colonne : ne retient comme
        # justifiés que les paragraphes PROUVÉS géométriquement (≥2 lignes
        # pleines au même bord droit, conf 0.9). Aucune estimation de police.
        prelim = []
        for members, lines in built:
            px0 = min(ln["x0"] for ln in lines)
            px1 = max(ln["x1"] for ln in lines)
            a, c = self._compute_alignment(lines, (px0, px1), page_w, None)
            prelim.append((members, lines, px0, px1, a, c))

        # Marge de COLONNE justifiée = bord droit d'un paragraphe PROUVÉ justifié
        # (≥2 lignes pleines au même bord). Preuve qu'on est dans une colonne
        # réellement justifiée → on peut alors trancher un paragraphe ambigu de
        # 2 lignes. On la retient si elle est PARTAGÉE par ≥2 paragraphes, OU
        # portée par ≥1 paragraphe LARGE (≥ 50 % de la page) : une justification
        # sur toute la largeur est une preuve forte, là où un alignement
        # fortuit en colonne étroite (ex. sidebar du CV) ne l'est pas.
        pe = {}
        wide = set()
        for _, _, px0, px1, a, c in prelim:
            if a == 3 and c >= 0.9:
                e = round(px1)
                pe[e] = pe.get(e, 0) + 1
                if (px1 - px0) >= 0.5 * page_w:
                    wide.add(e)
        cands = [e for e, n in pe.items() if n >= 2] + list(wide)
        col_right = max(cands) if cands else None

        # 3e passe — AFFECTATION : ré-évalue avec la marge SEULEMENT les
        # paragraphes encore ambigus (non déjà justifiés).
        for members, lines, px0, px1, align, conf in prelim:
            if align != 3 and col_right is not None:
                align, conf = self._compute_alignment(lines, (px0, px1),
                                                      page_w, col_right)
            ref = [round(px0, 1), round(px1, 1)]
            for b in members:
                b["align"] = align
                b["align_conf"] = round(conf, 2)
                b["align_ref"] = ref
            # Marqueurs pour le RENDU aligné (Étape 1) : un bloc SEUL sur sa
            # ligne peut être re-ancré (centre/droite) ou étiré (justifié) ;
            # la DERNIÈRE ligne d'un justifié ne s'étire jamais.
            for ln in lines:
                solo = len(ln["blocks"]) == 1
                last = ln is lines[-1]
                for blk in ln["blocks"]:
                    blk["_align_line_solo"] = solo
                    blk["_align_last_line"] = last

    @staticmethod
    def _annotate_paragraphs(page_data, img_rects=None, rules=None):
        """Passe d'ANNOTATION (N'AFFECTE PAS LE RENDU). DEUX niveaux :
          1) span-blocs → LIGNES (même baseline + adjacence horizontale) : une
             ligne peut mélanger des styles inline (mot gras, LIEN souligné) sans
             casser le paragraphe ;
          2) lignes → PARAGRAPHES (style DOMINANT de la ligne, interligne ≈
             hauteur, bord aligné, chevauchement = même colonne) + fusion L-shape.
        Stocke page_data['paragraphs'] (frame, bands=zones utilisables, gap_before)
        et page_data['anchors'] (images) ; annote chaque bloc d'un 'para_id'.
        Aucune fusion appliquée aux blocs → réinjection ligne-par-ligne → identité
        intacte."""
        blocks = page_data.get("text_blocks", [])
        anchors = [{"type": "image", "bbox": [round(v, 1) for v in r]}
                   for r in (img_rects or [])]
        # Un MARQUEUR de puce est un bloc autonome (pas du texte de paragraphe) :
        #  • soit `is_list_item` + `bullet_char` (souvent un bloc à texte VIDE,
        #    ex. « • » du Handbook) ;
        #  • soit un court span (≤2 car.) en police symbole/dingbat (ex. « O » en
        #    ZapfDingbats = ❖ du CV) — la détection par police vit dans
        #    `_group_paragraphs` (désactivé), donc `is_list_item` n'est pas posé.
        # On l'EXCLUT des lignes/paragraphes (sinon il est fusionné dans la ligne
        # de l'item et absorbé par le paragraphe) : il reste un marqueur défini à
        # part, rendu seul — comportement identique dans tous les documents.
        def _is_marker(b):
            # Un marqueur est COURT (le seul glyphe de puce, ≤2 car.). Un item à
            # « puce collée » dont le texte est le CONTENU réel n'en est pas un :
            # il doit rester dans les paragraphes.
            if len((b.get("text") or "").strip()) > 2:
                return False
            if b.get("is_list_item") and b.get("bullet_char"):
                return True
            fr = "".join(ch for ch in (b.get("font") or "").split("+")[-1].lower()
                         if ch.isalnum())
            return (fr in BULLET_FONT_NAMES
                    and 0 < len((b.get("text") or "").strip()) <= 2)

        idx = [i for i, b in enumerate(blocks)
               if abs(b.get("rotation", 0)) <= 1.0 and (b.get("text") or "").strip()
               and not _is_marker(b)]
        if not idx:
            page_data["paragraphs"] = []
            page_data["anchors"] = anchors
            return

        cx0 = min(blocks[i]["bbox"][0] for i in idx)   # marges de contenu RÉELLES
        cx1 = max(blocks[i]["bbox"][2] for i in idx)

        def baseline(i):
            o = blocks[i].get("origin")
            return o[1] if o and len(o) >= 2 else blocks[i]["bbox"][3]

        # Chaque marqueur de puce → SÉPARATEUR d'item : (baseline, x gauche). Une
        # ligne démarre un nouvel item si une puce est sur SA baseline ET juste à
        # SA gauche (même item) — la contrainte horizontale évite qu'une puce
        # d'une AUTRE colonne, à la même hauteur, scinde une ligne sans rapport.
        bullet_bases = []
        for b in blocks:
            if _is_marker(b):
                bo = b.get("bullet_origin") or b.get("origin")
                by = bo[1] if bo and len(bo) >= 2 else b["bbox"][3]
                bullet_bases.append((by, b["bbox"][0]))

        # ── 1) span-blocs → LIGNES ────────────────────────────────────────────
        # Même baseline (à 0,3·taille) ET adjacence horizontale (le saut de
        # colonne, lui, est large) → une seule ligne, styles inline confondus.
        lines = []
        for i in sorted(idx, key=lambda i: (round(baseline(i), 1), blocks[i]["bbox"][0])):
            bb = blocks[i]["bbox"]; bs = baseline(i); sz = max(6.0, blocks[i].get("size", 10))
            merge = False
            if lines and abs(bs - lines[-1]["base"]) <= 0.3 * sz:
                gap = bb[0] - lines[-1]["x1"]
                pb = blocks[lines[-1]["blocks"][-1]]; cb = blocks[i]
                same_style = (bool(cb.get("bold")) == bool(pb.get("bold"))
                              and bool(cb.get("italic")) == bool(pb.get("italic"))
                              and abs(cb.get("size", 0) - pb.get("size", 0)) <= 1.0)
                # Même baseline EXACTE (≤0.8 pt) = même flux typographique → run
                # inline, même si style/gros écart (titre en capitales espacées
                # « FOREWORD BY JAKE KLAMKA » dont un mot est gras).
                same_flow = abs(bs - lines[-1]["base"]) <= 0.8
                # Jointif/petit écart → même ligne (variation inline : mot gras,
                # lien…). Au-delà, on n'agrège QUE si style identique (contenu
                # tabulé) OU même flux. Un changement de style à travers une vraie
                # gouttière AVEC baseline décalée = frontière de COLONNE (corps
                # romain | encart italique, p.18 décalé de 2.7 pt) → on coupe.
                if (-0.5 * sz <= gap <= 2.0 * sz
                        and (gap <= 0.6 * sz or same_style or same_flow)):
                    merge = True
            if merge:
                L = lines[-1]; L["blocks"].append(i)
                L["x0"] = min(L["x0"], bb[0]); L["y0"] = min(L["y0"], bb[1])
                L["x1"] = max(L["x1"], bb[2]); L["y1"] = max(L["y1"], bb[3])
            else:
                lines.append({"blocks": [i], "base": bs,
                              "x0": bb[0], "y0": bb[1], "x1": bb[2], "y1": bb[3]})

        # Zone utilisable d'une LIGNE : bornée par les AUTRES lignes + images.
        lboxes = [[L["x0"], L["y0"], L["x1"], L["y1"]] for L in lines]
        obst = lboxes + [a["bbox"] for a in anchors]

        def avail(box):
            y0, y1, bh = box[1], box[3], max(1.0, box[3] - box[1])
            left, right = cx0, cx1
            for ob in obst:
                if ob is box or min(y1, ob[3]) - max(y0, ob[1]) <= 0.3 * bh:
                    continue
                if ob[0] >= box[2] - 1.0:
                    right = min(right, ob[0])
                elif ob[2] <= box[0] + 1.0:
                    left = max(left, ob[2])
            return [round(left, 1), round(right, 1)]

        for L, lb in zip(lines, lboxes):
            L["avail"] = avail(lb)
            # Style de paragraphe d'une ligne : la TAILLE vient du span le plus
            # large ; mais GRAS/ITALIQUE ne valent que si TOUS les spans de la
            # ligne le sont. Un libellé gras en tête (« Label : valeur ») est une
            # emphase inline, pas l'identité du paragraphe → la ligne compte comme
            # romaine et rejoint ses lignes de continuation romaines (sinon le
            # libellé gras isolait la 1re ligne dans son propre paragraphe).
            bi = max(L["blocks"], key=lambda i: blocks[i]["bbox"][2] - blocks[i]["bbox"][0])
            L["style"] = (round(blocks[bi].get("size", 0)),
                          all(blocks[i].get("bold") for i in L["blocks"]),
                          all(blocks[i].get("italic") for i in L["blocks"]))
            # Début d'item de liste : une puce sur CETTE baseline ET juste à
            # gauche de cette ligne (même item). La contrainte horizontale évite
            # qu'une puce d'une autre colonne, à la même hauteur, scinde la ligne.
            _sz = max(6.0, L["style"][0])
            L["item_start"] = any(abs(L["base"] - bby) <= 0.4 * _sz
                                  and -0.5 * _sz <= L["x0"] - bx <= 4.0 * _sz
                                  for bby, bx in bullet_bases)

        # ── 2) LIGNES → PARAGRAPHES ───────────────────────────────────────────
        # Comparaison à TOUS les paragraphes ouverts (pas seulement le dernier) :
        # colonne et encart s'entrelacent en y → une ligne doit rejoindre SON
        # paragraphe (même colonne = chevauchement horizontal, juste en dessous
        # de sa dernière ligne) même si une ligne d'une autre colonne s'est
        # intercalée. Sinon : sur-segmentation (1 paragraphe par ligne).
        paras = []
        for L in sorted(lines, key=lambda L: (round(L["y0"], 1), L["x0"])):
            best, best_dy = None, 1e9
            # Une ligne qui DÉMARRE un item de liste (puce alignée) ouvre
            # toujours un nouveau paragraphe : on ne la rattache à aucun item
            # précédent, même si style/marge/interligne coïncident.
            cands = [] if L.get("item_start") else paras
            for p in cands:
                if p["style"] != L["style"]:
                    continue
                last = p["lines"][-1]
                ov = min(L["x1"], p["x1"]) - max(L["x0"], p["x0"])  # même colonne ?
                if ov <= 0:
                    continue
                size = max(6.0, (L["style"][0] + last["style"][0]) / 2)
                tol = max(3.0, 0.35 * size)
                # Adjacence verticale mesurée BASELINE-À-BASELINE (et non entre
                # bords de boîtes) : la hauteur de boîte varie (gras, asc./desc.)
                # et peut chevaucher la ligne voisine → l'écart entre bords
                # devenait négatif et une ligne consécutive valide était rejetée
                # (la suivante la « sautait » alors, scindant un paragraphe gras).
                # L'interligne, lui, est un ratio typographique stable.
                dy = L["base"] - last["base"]                       # juste dessous ?
                if not (0.5 * size <= dy <= 1.7 * size):
                    continue
                # Bord aligné : x0 (début) ou x1 (fin). La tolérance sur x0 est
                # relative à la taille (~1 caractère) pour absorber le léger
                # retrait de puce — une continuation revenant à la marge sous une
                # 1re ligne indentée après « ❖ » reste le même paragraphe.
                edge = (abs(L["x0"] - last["x0"]) <= max(tol, min(0.9 * size, 12.0))
                        or abs(L["x1"] - last["x1"]) <= tol)
                # L-shape : la dernière ligne du para était bornée à gauche par un
                # obstacle (image/encart), la courante revient pleine largeur.
                lshape = abs(L["x0"] - cx0) <= tol and last["avail"][0] > cx0 + tol
                if (edge or lshape) and dy < best_dy:
                    best, best_dy = p, dy
            if best is not None:
                best["lines"].append(L)
                best["x0"] = min(best["x0"], L["x0"]); best["y0"] = min(best["y0"], L["y0"])
                best["x1"] = max(best["x1"], L["x1"]); best["y1"] = max(best["y1"], L["y1"])
            else:
                paras.append({"lines": [L], "style": L["style"],
                              "x0": L["x0"], "y0": L["y0"], "x1": L["x1"], "y1": L["y1"]})

        out = []
        for k, p in enumerate(paras):
            gap = None
            for q in reversed(paras[:k]):
                if min(p["x1"], q["x1"]) - max(p["x0"], q["x0"]) > 0:
                    gap = round(p["y0"] - q["y1"], 1)
                    break
            block_ids, bands = [], []
            for L in p["lines"]:
                for i in L["blocks"]:
                    blocks[i]["para_id"] = k
                    block_ids.append(i)
                bands.append([round(L["y0"], 1), round(L["y1"], 1),
                              L["avail"][0], L["avail"][1]])
            out.append({"id": k, "lines": block_ids, "n_lines": len(p["lines"]),
                        "frame": [round(p["x0"], 1), round(p["y0"], 1),
                                  round(p["x1"], 1), round(p["y1"], 1)],
                        "bands": bands, "gap_before": gap})
        page_data["paragraphs"] = out
        page_data["anchors"] = anchors
        page_data["rules"] = [[round(v, 1) for v in r] for r in (rules or [])]

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
        # Origine x = PREMIER GLYPHE VISIBLE (et non le début du span, qui peut
        # inclure un espace de tête dont l'avance varie — parfois nulle). Sans
        # ça, un mot suivant un espace de tête se rendrait collé ou décalé.
        vis_x0 = first.get("_vis_x0")
        if vis_x0 is not None and abs(rot) <= 1.0:
            origin[0] = vis_x0

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
            # Classe de police (drapeaux PyMuPDF : bit 2 = serif, bit 3 = mono) :
            # sert au repli GÉNÉRAL de substitution par classe à l'injection.
            "serif":           bool(flags & 4),
            "mono":            bool(flags & FLAG_MONOSPACE),
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
