# -*- coding: utf-8 -*-
"""Test : détection des retours à la ligne ENTRE paragraphes.

Règle générique (aucune règle spécifique à un document) :
  - on extrait les lignes de texte de chaque page (PyMuPDF, mode dict) ;
  - on mesure l'écart vertical entre lignes consécutives (baseline à baseline) ;
  - l'interligne « normal » de la page = médiane des écarts positifs ;
  - un écart nettement supérieur (> 1.5 × interligne médian) = saut de
    paragraphe ; un écart proche de l'interligne = même paragraphe (wrap).
"""
import sys
import statistics
import fitz

PDF = sys.argv[1] if len(sys.argv) > 1 else None
MAX_PAGES = 5

def lines_of_page(page):
    """Liste des lignes : (baseline_y, x0, taille, texte)."""
    out = []
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            text = " ".join(s["text"].strip() for s in spans)
            y = spans[0]["origin"][1]
            x0 = min(s["bbox"][0] for s in spans)
            size = max(s.get("size", 12) for s in spans)
            out.append((y, x0, size, text))
    out.sort(key=lambda l: (round(l[0], 1), l[1]))
    # fusionne les fragments d'une même ligne visuelle (même baseline)
    merged = []
    for y, x0, size, text in out:
        if merged and abs(merged[-1][0] - y) <= 0.4 * size:
            py, px0, psize, ptext = merged[-1]
            merged[-1] = (py, min(px0, x0), max(psize, size), ptext + "  |  " + text)
        else:
            merged.append((y, x0, size, text))
    return merged

def split_paragraphs(lines):
    """Coupe la liste de lignes en paragraphes selon les écarts verticaux."""
    if not lines:
        return []
    gaps = [lines[i + 1][0] - lines[i][0] for i in range(len(lines) - 1)]
    pos_gaps = [g for g in gaps if 0 < g]
    # interligne normal = médiane des petits écarts (≤ 2.5 × taille médiane)
    med_size = statistics.median(l[2] for l in lines)
    intra = [g for g in pos_gaps if g <= 2.5 * med_size]
    normal = statistics.median(intra) if intra else 1.3 * med_size

    paras = [[lines[0]]]
    for i in range(1, len(lines)):
        gap = lines[i][0] - lines[i - 1][0]
        if gap > 1.5 * normal:
            paras.append([lines[i]])      # saut de paragraphe
        else:
            paras[-1].append(lines[i])    # wrap / même paragraphe
    return paras, normal

def main():
    doc = fitz.open(PDF)
    print(f"Document : {PDF}")
    print(f"Pages analysées : {min(MAX_PAGES, len(doc))}/{len(doc)}\n")
    for pno in range(min(MAX_PAGES, len(doc))):
        page = doc[pno]
        lines = lines_of_page(page)
        if not lines:
            print(f"=== PAGE {pno + 1} : (aucun texte) ===\n")
            continue
        paras, normal = split_paragraphs(lines)
        print(f"=== PAGE {pno + 1} : {len(paras)} paragraphes "
              f"(interligne normal ≈ {normal:.1f} pt) ===")
        for n, p in enumerate(paras, 1):
            first = p[0][3]
            preview = first[:90] + ("…" if len(first) > 90 else "")
            print(f"  P{n:02d} [{len(p)} ligne(s)]  {preview}")
            if len(p) > 1:
                last = p[-1][3]
                preview2 = last[:90] + ("…" if len(last) > 90 else "")
                print(f"        └─ dernière ligne : {preview2}")
        print()
    doc.close()

if __name__ == "__main__":
    main()
