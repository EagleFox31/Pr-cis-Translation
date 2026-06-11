# -*- coding: utf-8 -*-
"""Géométrie des blocs du haut de la page 4 (diagnostic superposition)."""
import json

path = (r"translations\Carl_Shan__Max_Song__Henry_Wang__And_William_Chen__"
        r"6d9f3e4e4962\fr\translated.json")
d = json.load(open(path, encoding="utf-8"))
p = d["pages"][3]
for b in p["text_blocks"]:
    if b["origin"][1] < 140:
        print(f"x0={b['bbox'][0]:6.1f} x1={b['bbox'][2]:6.1f} "
              f"y={b['origin'][1]:6.1f} ital={b.get('italic')} "
              f"key={b.get('paragraph_key')} {b['text'][:45]!r}")
