# -*- coding: utf-8 -*-
"""Compare polices/tailles entre le PDF original et le PDF traduit.
Usage : python test_compare_fonts.py <original.pdf> <traduit.pdf> [max_pages]
"""
import sys
from collections import Counter
import fitz

FLAG_BOLD = 16
FLAG_ITALIC = 2

def page_stats(page):
    """Counter {(police, taille_arrondie, gras, italique): nb_caractères}."""
    stats = Counter()
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = span.get("text", "").strip()
                if not t:
                    continue
                font = span.get("font", "?")
                size = round(span.get("size", 0), 1)
                fl = span.get("flags", 0)
                stats[(font, size, bool(fl & FLAG_BOLD), bool(fl & FLAG_ITALIC))] += len(t)
    return stats

def fmt(key, n):
    font, size, b, i = key
    style = ("gras " if b else "") + ("italique" if i else "")
    return f"      {font:<28} {size:>6} pt  {style:<14} ({n} car.)"

def main():
    orig_path, trad_path = sys.argv[1], sys.argv[2]
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    d1, d2 = fitz.open(orig_path), fitz.open(trad_path)
    n = min(len(d1), len(d2), max_pages)
    print(f"Comparaison sur {n} page(s)\n")
    for p in range(n):
        s1, s2 = page_stats(d1[p]), page_stats(d2[p])
        print(f"=== PAGE {p + 1} ===")
        print("   ORIGINAL :")
        for k, v in s1.most_common(8):
            print(fmt(k, v))
        print("   TRADUIT :")
        for k, v in s2.most_common(8):
            print(fmt(k, v))
        # tailles moyennes pondérées par nb de caractères
        m1 = sum(k[1] * v for k, v in s1.items()) / max(1, sum(s1.values()))
        m2 = sum(k[1] * v for k, v in s2.items()) / max(1, sum(s2.values()))
        pb1 = 100 * sum(v for k, v in s1.items() if k[2]) / max(1, sum(s1.values()))
        pb2 = 100 * sum(v for k, v in s2.items() if k[2]) / max(1, sum(s2.values()))
        print(f"   Taille moyenne : {m1:.2f} pt -> {m2:.2f} pt | "
              f"part de gras : {pb1:.0f}% -> {pb2:.0f}%\n")
    d1.close(); d2.close()

if __name__ == "__main__":
    main()
