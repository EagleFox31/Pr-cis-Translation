"""
pdf_engine_v2.tagging — Balisage par SEGMENT DE STYLE (méthode Word).

But : produire, pour chaque paragraphe extrait, un texte balisé
`[[0]]…[[/0]][[1]]…[[/1]]…` où chaque balise regroupe des runs CONSÉCUTIFS de
MÊME mise en forme (police, gras, italique, taille, couleur). C'est la même
sémantique que la traduction DOCX (`backend/docx_translator_engine.py`), sauf
qu'ici un « run Word » = un groupe de runs PDF de style identique — car un mot à
lettres espacées est éclaté en un run PAR LETTRE (voir « FOREWORD ») : les tagger
séparément serait absurde.

Le texte à l'intérieur des balises est reconstruit EXACTEMENT comme le champ
`paragraph["text"]` de l'extraction (mêmes espaces, même dé-césure) → en retirant
les balises on retrouve le texte du paragraphe. La seule chose que le balisage
ajoute, ce sont les FRONTIÈRES de style.

Ce module ne fait AUCUN rendu ni traduction : il prépare seulement le texte à
envoyer au traducteur et la table `segments` (style de chaque balise) qui servira
à la réinjection (reflow) une fois la traduction revenue.
"""

import re


# ── Signature de style d'un run (ce qui définit une frontière de balise) ──────
def style_sig(run):
    """Signature comparable du style visible d'un run.

    On normalise le nom de police (sans préfixe de sous-ensemble 'ABCDEF+'),
    et on arrondit taille/couleur pour éviter des frontières parasites dues à
    des écarts infimes. `bold`/`italic` viennent des flags de span PyMuPDF.
    NB : le soulignement n'est PAS un flag de police en PDF (c'est un trait
    dessiné à part) → non capté ici.
    """
    font = run.get("font") or ""
    clean = font.split("+")[-1] if "+" in font else font
    color = run.get("color") or [0, 0, 0]
    try:
        col = tuple(round(float(c), 3) for c in color)
    except Exception:
        col = (0.0, 0.0, 0.0)
    return (clean, bool(run.get("bold")), bool(run.get("italic")),
            round(float(run.get("size", 0) or 0), 1), col,
            bool(run.get("underline")))


def _sig_to_meta(sig):
    """Signature -> dict de style lisible (pour la table `segments`)."""
    font, bold, italic, size, color, underline = sig
    return {"font": font, "bold": bold, "italic": italic,
            "size": size, "color": list(color), "underline": underline}


# ── Reconstruction du texte balisé d'un paragraphe ────────────────────────────
# On réplique la logique de composition du texte de l'extraction :
#   • au sein d'une ligne : espace insérée si l'écart dépasse 0.30×gw
#     (cf. engine `_make_text_line` / `_SPACE_FACTOR`) ;
#   • entre lignes : dé-césure d'un mot coupé, sinon espace
#     (cf. engine `_join_para_text`) ;
# tout en suivant le style de chaque fragment pour poser les frontières.
_SPACE_FACTOR = 0.30


def _line_segments(line):
    """Liste de {sig, text} pour UNE ligne, espaces internes replaçées comme à
    l'extraction, puis rognée en tête/queue."""
    runs = line.get("runs", [])
    if not runs:
        return []
    gw = line.get("gw") or 1.0
    space_gap = _SPACE_FACTOR * gw
    segs = []

    def emit(sig, s):
        if not s:
            return
        if segs and segs[-1]["sig"] == sig:
            segs[-1]["text"] += s
        else:
            segs.append({"sig": sig, "text": s})

    last_char = ""
    for i, r in enumerate(runs):
        sig = style_sig(r)
        txt = r.get("text", "")
        if i > 0:
            gap = r["bbox"][0] - runs[i - 1]["bbox"][2]
            if (gap > space_gap and last_char and last_char != " "
                    and not txt.startswith(" ")):
                emit(style_sig(runs[i - 1]), " ")
                last_char = " "
        emit(sig, txt)
        if txt:
            last_char = txt[-1]
    _strip_edges(segs)
    return segs


def _strip_edges(segs):
    """Rogne l'espace de tête du 1er segment et de queue du dernier (comme le
    `.strip()` appliqué à chaque ligne dans `_join_para_text`)."""
    while segs and not segs[0]["text"].lstrip():
        segs.pop(0)
    if segs:
        segs[0]["text"] = segs[0]["text"].lstrip()
    while segs and not segs[-1]["text"].rstrip():
        segs.pop()
    if segs:
        segs[-1]["text"] = segs[-1]["text"].rstrip()


def paragraph_segments(para):
    """Retourne la liste des segments {sig, text} d'un paragraphe, fusionnés par
    style sur l'ENSEMBLE du paragraphe (lignes jointes, dé-césure comprise)."""
    lines = para.get("lines")
    # Un `text_line` isolé (paragraphe mono-ligne non groupé) : on l'enveloppe.
    if lines is None:
        lines = [para]
    segs = []
    for line in lines:
        ls = _line_segments(line)
        if not ls:
            continue
        if not segs:
            segs = ls
            continue
        # Jointure inter-lignes : dé-césure ou espace (cf. `_join_para_text`).
        prev = segs[-1]
        pt = prev["text"]
        first_char = ls[0]["text"][:1]
        if (pt.endswith("-") and len(pt) >= 2 and pt[-2].isalpha()
                and first_char.islower()):
            prev["text"] = pt[:-1]                 # dé-césure : retire le trait
        else:
            prev["text"] = pt + " "                # sinon espace de jointure
        for s in ls:
            if segs and segs[-1]["sig"] == s["sig"]:
                segs[-1]["text"] += s["text"]
            else:
                segs.append(dict(s))
    # Écrasement des espaces multiples À L'INTÉRIEUR d'un segment (le global
    # `\s{2,}->  ` de l'extraction ; on ne touche pas aux frontières).
    for s in segs:
        s["text"] = re.sub(r"\s{2,}", " ", s["text"])
    return segs


def tag_paragraph(para):
    """Produit (tagged_text, segments_meta) pour un paragraphe.

    tagged_text : « [[0]]…[[/0]][[1]]…[[/1]]… » — prêt pour le traducteur.
    segments_meta : liste de dicts de style (index = numéro de balise), pour la
    réinjection.
    """
    segs = paragraph_segments(para)
    parts = []
    meta = []
    for i, s in enumerate(segs):
        parts.append(f"[[{i}]]{s['text']}[[/{i}]]")
        meta.append(_sig_to_meta(s["sig"]))
    return "".join(parts), meta


# ── Diagnostic : dump du balisage d'un JSON d'extraction ──────────────────────
def _diagnose(json_path, show=8):
    import json
    data = json.load(open(json_path, encoding="utf-8"))
    total = multi = 0
    examples = []
    mismatches = []
    for page in data.get("pages", []):
        for el in page.get("elements", []):
            if el.get("type") != "paragraph":
                continue
            total += 1
            tagged, meta = tag_paragraph(el)
            if len(meta) > 1:
                multi += 1
                if len(examples) < show:
                    examples.append((page["page_num"], len(meta), tagged, meta))
            # Contrôle de cohérence : texte sans balises ≈ texte d'extraction.
            stripped = re.sub(r"\[\[/?\d+\]\]", "", tagged)
            norm = lambda t: re.sub(r"\s+", " ", (t or "")).strip()
            if norm(stripped) != norm(el.get("text", "")):
                if len(mismatches) < 6:
                    mismatches.append((page["page_num"],
                                       norm(el.get("text", ""))[:120],
                                       norm(stripped)[:120]))
    print(f"== {json_path}")
    print(f"   paragraphes: {total} | multi-styles: {multi} "
          f"({100*multi/total:.1f}%)" if total else "   (aucun paragraphe)")
    print(f"   incohérences texte: {len(mismatches)}")
    for pn, a, b in mismatches:
        print(f"     p{pn} EXTRACT: {a!r}")
        print(f"         TAGGED : {b!r}")
    print("   — exemples multi-styles —")
    for pn, n, tagged, meta in examples:
        print(f"   p{pn} ({n} segments): {tagged[:200]}")
        for j, m in enumerate(meta):
            print(f"       [[{j}]] {m['font']} b={int(m['bold'])} i={int(m['italic'])} "
                  f"sz={m['size']} col={m['color']}")


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        _diagnose(p)
