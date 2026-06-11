# -*- coding: utf-8 -*-
"""Mesure les débordements : largeur du texte traduit vs conteneur d'origine.
Usage : python test_overflow.py <translated.json> [max_pages]
"""
import sys
import json
import fitz

path = sys.argv[1]
max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

with open(path, encoding="utf-8") as f:
    data = json.load(f)

for page in data.get("pages", [])[:max_pages]:
    blocks = page.get("text_blocks", [])
    page_w = page.get("width", 612)
    n_over_box = n_over_page = 0
    worst = []
    for b in blocks:
        t = (b.get("translated_text") or "").strip()
        if not t:
            continue
        bbox = b.get("bbox")
        size = b.get("size", 12)
        fm = b.get("font_mapped", "helv")
        try:
            tw = fitz.get_text_length(t, fontname=fm, fontsize=size)
        except Exception:
            tw = 0.5 * size * len(t)
        box_w = bbox[2] - bbox[0]
        x0 = b.get("origin", bbox)[0]
        if tw > box_w + 1:
            n_over_box += 1
            ratio = tw / max(1.0, box_w)
            worst.append((ratio, t[:60], box_w, tw, x0 + tw > page_w))
        if x0 + tw > page_w + 1:
            n_over_page += 1
    worst.sort(reverse=True)
    print(f"=== PAGE {page.get('page_num')} : {len(blocks)} blocs | "
          f"{n_over_box} debordent de leur conteneur | "
          f"{n_over_page} depassent le bord de page ===")
    for ratio, txt, bw, tw, off in worst[:5]:
        flag = " [HORS PAGE]" if off else ""
        print(f"   x{ratio:.2f}  ({bw:.0f} -> {tw:.0f} pt){flag}  {txt}")
    print()
