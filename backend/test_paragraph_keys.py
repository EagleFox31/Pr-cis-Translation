# -*- coding: utf-8 -*-
"""Inspecte les paragraph_key attribuées par l'IA dans translated.json.
Usage : python test_paragraph_keys.py <translated.json> [max_pages]
"""
import sys
import json
from collections import OrderedDict

path = sys.argv[1]
max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

with open(path, encoding="utf-8") as f:
    data = json.load(f)

for page in data.get("pages", [])[:max_pages]:
    print(f"=== PAGE {page.get('page_num')} ===")
    groups = OrderedDict()
    solo = []
    for b in page.get("text_blocks", []):
        k = b.get("paragraph_key")
        if k:
            groups.setdefault(k, []).append(b)
        else:
            solo.append(b)
    for k, grp in groups.items():
        if len(grp) < 2:
            solo.extend(grp)
            continue
        print(f"  GROUPE {k}  ({len(grp)} blocs)")
        for b in grp:
            sz = b.get("size", 0)
            y = b.get("origin", b.get("bbox", [0, 0, 0, 0]))[1]
            t = (b.get("text") or "")[:55]
            tt = (b.get("translated_text") or "")[:55]
            print(f"     [{sz:>5.1f}pt y={y:>6.1f}] {t!r}")
            print(f"        -> {tt!r}")
    if solo:
        print(f"  SEULS ({len(solo)} blocs) :")
        for b in solo:
            sz = b.get("size", 0)
            y = b.get("origin", b.get("bbox", [0, 0, 0, 0]))[1]
            t = (b.get("text") or "")[:55]
            print(f"     [{sz:>5.1f}pt y={y:>6.1f}] {t!r}")
    print()
