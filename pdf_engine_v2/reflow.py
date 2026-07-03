"""
pdf_engine_v2.reflow — Coulée du texte traduit dans le conteneur (Étape reflow).

Prend les SEGMENTS traduits d'un paragraphe (chacun : texte + style + police
`fitz.Font` déjà résolue) et les COULE dans le polygone `container_lines` (les
cadres orange de l'Étape D), en respectant STRICTEMENT, à chaque ligne, le bord
gauche et le bord droit de la bande à ce niveau — donc sans débordement ni
chevauchement.

Le conteneur a une HAUTEUR FIXE (il s'étend à droite, pas vers le bas). Si le
texte traduit ne tient pas, on applique une CASCADE d'ajustements bornés, du
moins au plus intrusif :

    tracking (resserrement inter-lettres) → taille de police → interligne

et, à chaque ligne, une CÉSURE syllabique (pyphen) pour limiter le crénelage.

Ce module ne peint rien : il renvoie des lignes de « runs placés »
(texte, x, baseline, police, taille, couleur, sx) que le moteur peindra.
"""

import re

try:
    import pyphen
except Exception:                       # pyphen absent : pas de césure (dégradé)
    pyphen = None


# ── Résolution glyphe-par-glyphe (police embarquée sinon repli complet) ──────
# `fonts` = liste de (police, couverture) où `couverture` est un ENSEMBLE de
# caractères que la police rend FIDÈLEMENT, ou None = couverture universelle
# (police de repli base-14). NB : on n'utilise PAS has_glyph()/valid_codepoints()
# — un sous-ensemble embarqué les renvoie « présents » pour des glyphes dont le
# contour a été RETIRÉ au subsetting (rendus vides). La seule couverture fiable
# est l'ensemble des caractères réellement DESSINÉS dans le PDF source.
def glyph_font(fonts, ch):
    """Première police dont la couverture contient `ch` (ou universelle) ; sinon
    la dernière (repli). Les espaces passent partout."""
    ws = ch.isspace()
    for f, cover in fonts:
        if cover is None or ws or ch in cover:
            return f
    return fonts[-1][0]


def text_width(text, fonts, size, sx=1.0):
    """Largeur de `text` mesurée caractère par caractère avec la police qui
    couvre chaque glyphe (× `sx`)."""
    w = 0.0
    for ch in text:
        f = glyph_font(fonts, ch)
        try:
            w += f.text_length(ch, fontsize=size)
        except Exception:
            pass
    return w * sx


# ── Tokenisation : segments -> mots porteurs de style ────────────────────────
def build_tokens(segments):
    """segments : liste de {text, fonts:[fitz.Font,…], size, color}.
    Retourne une liste de tokens-mots : {text, fonts, size, color, space_before}.
    Les espaces (internes/aux frontières) deviennent le drapeau `space_before`
    du mot suivant → la coulée décide où tombent les retours à la ligne."""
    tokens = []
    pending_space = False
    for seg in segments:
        fonts = seg.get("fonts") or ([seg["font"]] if seg.get("font") else [])
        size = seg.get("size", 0) or 0
        color = seg.get("color", (0, 0, 0))
        for part in re.split(r"(\s+)", seg.get("text", "")):
            if part == "":
                continue
            if part.isspace():
                pending_space = True
            else:
                tokens.append({"text": part, "fonts": fonts, "size": size,
                               "color": color, "space_before": pending_space})
                pending_space = False
    return tokens


# ── Géométrie du conteneur en escalier ───────────────────────────────────────
def _bounds_at(container_lines, y0, y1):
    """[gauche, droite] utilisables pour une ligne occupant [y0, y1].
    Intersection CONSERVATRICE (max des gauches, min des droites) des bandes qui
    chevauchent verticalement → la ligne reste à l'intérieur de toutes, ce qui
    gère l'enroulement en L autour d'un encart sans jamais déborder."""
    lefts, rights = [], []
    for b in container_lines:
        lx0, lty, tgt, lby = b[0], b[1], b[2], b[3]
        if lby <= y0 or lty >= y1:
            continue
        lefts.append(lx0)
        rights.append(tgt)
    if not lefts:                       # aucune bande : prend la plus proche
        c = 0.5 * (y0 + y1)
        best = min(container_lines, key=lambda b: abs(0.5 * (b[1] + b[3]) - c))
        return best[0], best[2]
    return max(lefts), min(rights)


# ── Césure syllabique ────────────────────────────────────────────────────────
_HYPH_CACHE = {}


def _hyphenator(lang):
    if pyphen is None:
        return None
    if lang not in _HYPH_CACHE:
        try:
            _HYPH_CACHE[lang] = pyphen.Pyphen(lang=lang)
        except Exception:
            _HYPH_CACHE[lang] = None
    return _HYPH_CACHE[lang]


def _hyphen_split(word, fonts, size, sx, avail, lang):
    """Tente de couper `word` pour que « préfixe- » tienne dans `avail`.
    Retourne (prefixe_avec_trait, reste) ou None si aucune coupe ne convient.
    On ne coupe pas les mots courts (< 5 lettres) ni les jetons non alphabétiques
    (nombres, symboles : ce sont des ancres immuables)."""
    dic = _hyphenator(lang)
    if dic is None or len(word) < 5 or not word.isalpha():
        return None
    positions = dic.positions(word)             # indices de coupe possibles
    best = None
    for p in positions:
        head = word[:p] + "-"
        if text_width(head, fonts, size, sx) <= avail:
            best = (head, word[p:])             # garde la plus longue qui tient
        else:
            break
    return best


# ── Coulée gloutonne d'une passe (paramètres fixés) ──────────────────────────
def _layout(tokens, container_lines, top, bottom, size_scale, pitch, sx, lang):
    """Une passe de coulée avec des paramètres FIXES. Retourne
    (lignes, hauteur_utilisée, déborde:bool). Chaque ligne :
    {"top", "baseline", "runs":[{text,x,font,size,color,sx}]}."""
    lines = []
    y = top

    def bounds():
        return _bounds_at(container_lines, y, y + pitch)

    left, right = bounds()
    x = left
    cur = []
    line_size = 0.0

    def close_line():
        nonlocal cur, line_size, y, left, right, x
        if cur:
            asc = line_size * 0.78          # baseline approx (ascender)
            lines.append({"top": y, "baseline": y + asc, "runs": cur})
        y += pitch
        left, right = bounds()
        x = left
        cur = []
        line_size = 0.0

    queue = list(tokens)
    while queue:
        t = queue.pop(0)
        size = (t["size"] or 0) * size_scale
        w = text_width(t["text"], t["fonts"], size, sx)
        sp = (text_width(" ", t["fonts"], size, sx)
              if (cur and t["space_before"]) else 0.0)

        if cur and x + sp + w > right + 0.5:
            # Ne tient pas : tenter une césure du mot pour finir la ligne.
            avail = right - (x + sp)
            piece = _hyphen_split(t["text"], t["fonts"], size, sx, avail, lang)
            if piece:
                head, tail = piece
                cur.append({"text": head, "x": x + sp, "fonts": t["fonts"],
                            "size": size, "color": t["color"], "sx": sx})
                line_size = max(line_size, size)
                queue.insert(0, {**t, "text": tail, "space_before": False})
                close_line()
                continue
            close_line()
            # replace le mot en début de nouvelle ligne (sans espace de tête)
            queue.insert(0, {**t, "space_before": False})
            continue

        x += sp
        cur.append({"text": t["text"], "x": x, "fonts": t["fonts"],
                    "size": size, "color": t["color"], "sx": sx})
        x += w
        line_size = max(line_size, size)

    close_line()
    height_used = len(lines) * pitch
    overflow = (top + height_used) > (bottom + 0.35 * pitch)
    return lines, height_used, overflow


# ── Cascade d'ajustement : première passe qui tient ──────────────────────────
# (pitch_scale, size_scale, sx) — du moins au plus intrusif. Marges infimes pour
# préserver la lisibilité (règle 3 : « toujours dans des marges infimes »).
_CASCADE = [
    (1.00, 1.00, 1.00),
    (1.00, 1.00, 0.98),                 # tracking léger
    (0.98, 1.00, 0.97),                 # + interligne
    (0.97, 0.98, 0.96),                 # + taille
    (0.95, 0.96, 0.96),
    (0.93, 0.94, 0.95),
    (0.90, 0.92, 0.95),
    (0.88, 0.90, 0.94),                 # plancher (lisibilité)
]


def reflow_paragraph(segments, container_lines, lang="fr_FR"):
    """Coule les `segments` traduits dans `container_lines`.

    Retourne un dict :
      { "lines":[…], "fitted":bool, "level":int, "pitch_scale","size_scale","sx",
        "n_lines":int }
    `lines` = lignes de runs placés (cf. `_layout`). `fitted` False = le texte
    déborde même au niveau le plus serré (à signaler / re-traduire plus court)."""
    if not container_lines:
        return {"lines": [], "fitted": False, "level": -1, "n_lines": 0,
                "pitch_scale": 1.0, "size_scale": 1.0, "sx": 1.0}
    tokens = build_tokens(segments)
    top = min(b[1] for b in container_lines)
    bottom = max(b[3] for b in container_lines)
    orig_pitch = _orig_pitch(container_lines, segments)

    best = None
    for lvl, (ps, ss, sx) in enumerate(_CASCADE):
        pitch = orig_pitch * ps
        lines, h, overflow = _layout(tokens, container_lines, top, bottom,
                                     ss, pitch, sx, lang)
        best = {"lines": lines, "fitted": not overflow, "level": lvl,
                "pitch_scale": ps, "size_scale": ss, "sx": sx,
                "n_lines": len(lines)}
        if not overflow:
            return best
    return best                          # rien ne tient : renvoie le plus serré


def _orig_pitch(container_lines, segments):
    """Interligne d'origine : pas vertical médian entre bandes successives,
    sinon repli sur la taille dominante des segments."""
    tops = sorted(b[1] for b in container_lines)
    gaps = [b - a for a, b in zip(tops, tops[1:]) if b - a > 0.5]
    if gaps:
        gaps.sort()
        return gaps[len(gaps) // 2]
    sizes = [s.get("size", 0) or 0 for s in segments]
    return (max(sizes) if sizes else 10.0) * 1.2
