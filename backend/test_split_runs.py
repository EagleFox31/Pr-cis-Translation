# -*- coding: utf-8 -*-
"""Vérifie _split_group_runs sur les groupes IA du translated.json courant."""
import sys
import json
from collections import OrderedDict
from pdf_translator_engine import PDFTranslatorEngine

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

for page in data.get("pages", [])[:2]:
    print(f"=== PAGE {page.get('page_num')} ===")
    groups = OrderedDict()
    for b in page.get("text_blocks", []):
        k = b.get("paragraph_key")
        if k:
            groups.setdefault(k, []).append(b)
    for k, grp in groups.items():
        if len(grp) < 2:
            continue
        runs = PDFTranslatorEngine._split_group_runs(grp)
        merged = [r for r in runs if len(r) >= 2]
        solo = [r[0] for r in runs if len(r) == 1]
        print(f"  {k} ({len(grp)} blocs) -> {len(merged)} fusion(s), {len(solo)} detache(s)")
        for r in merged:
            print(f"     FUSION  : " + " / ".join((b.get('text') or '')[:30] for b in r))
        for b in solo:
            print(f"     DETACHE : {(b.get('text') or '')[:40]!r} ({b.get('size')}pt)")
    print()
