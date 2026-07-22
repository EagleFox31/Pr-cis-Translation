"""
CLI de pdf_engine_v2.

Exemples :
  # Extraction -> JSON (images encodées en base64 dans le JSON)
  python -m pdf_engine_v2.cli extract mon.pdf

  # Extraction avec images en dossier annexe (JSON plus léger)
  python -m pdf_engine_v2.cli extract mon.pdf --assets

  # Réinjection : reconstruit le PDF depuis le JSON, avec bordures
  python -m pdf_engine_v2.cli reinject mon_objects.json sortie.pdf

  # Sans bordures
  python -m pdf_engine_v2.cli reinject mon_objects.json sortie.pdf --no-borders

  # Tout en un : extraire puis reconstruire (test de fidélité)
  python -m pdf_engine_v2.cli roundtrip mon.pdf sortie.pdf
"""

import argparse
import sys

try:
    from .engine import PDFObjectEngine
except ImportError:  # exécution directe : python cli.py ...
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engines.pdf.engine import PDFObjectEngine


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pdf_engine_v2",
                                     description="Extraction/réinjection objet par objet.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("extract", help="PDF -> JSON des objets")
    p_ex.add_argument("pdf")
    p_ex.add_argument("-o", "--output", help="JSON de sortie")
    p_ex.add_argument("--assets", action="store_true",
                      help="images en dossier annexe au lieu de base64")
    p_ex.add_argument("--no-remaining-space", action="store_true",
                      help="desactive la coupe paragraphe « espace restant »")
    p_ex.add_argument("--no-expand", action="store_true",
                      help="desactive l'expansion du conteneur de paragraphe")
    p_ex.add_argument("--no-tables", action="store_true",
                      help="desactive le cloisonnement des cellules de table")

    p_re = sub.add_parser("reinject", help="JSON -> PDF reconstruit")
    p_re.add_argument("json")
    p_re.add_argument("output_pdf")
    p_re.add_argument("--no-borders", action="store_true", help="sans bordures")
    p_re.add_argument("--assets-dir", help="dossier des images (mode --assets)")

    p_rt = sub.add_parser("roundtrip", help="PDF -> JSON -> PDF (test fidélité)")
    p_rt.add_argument("pdf")
    p_rt.add_argument("output_pdf")
    p_rt.add_argument("--no-borders", action="store_true", help="sans bordures")
    p_rt.add_argument("--no-remaining-space", action="store_true",
                      help="desactive la coupe paragraphe « espace restant »")
    p_rt.add_argument("--no-expand", action="store_true",
                      help="desactive l'expansion du conteneur de paragraphe")
    p_rt.add_argument("--no-tables", action="store_true",
                      help="desactive le cloisonnement des cellules de table")

    args = parser.parse_args(argv)
    engine = PDFObjectEngine()

    if args.cmd == "extract":
        if getattr(args, "no_remaining_space", False):
            engine.para_remaining_space = False
        if getattr(args, "no_expand", False):
            engine.expand_paragraphs = False
        if getattr(args, "no_tables", False):
            engine.detect_tables = False
        data, out = engine.extract(args.pdf, args.output,
                                   embed_images=not args.assets)
        n = sum(len(p["elements"]) for p in data["pages"])
        print(f"[OK] {len(data['pages'])} page(s), {n} objet(s) -> {out}")

    elif args.cmd == "reinject":
        out = engine.reinject(args.json, args.output_pdf,
                              draw_borders=not args.no_borders,
                              assets_dir=args.assets_dir)
        print(f"[OK] PDF reconstruit -> {out}")

    elif args.cmd == "roundtrip":
        if getattr(args, "no_remaining_space", False):
            engine.para_remaining_space = False
        if getattr(args, "no_expand", False):
            engine.expand_paragraphs = False
        if getattr(args, "no_tables", False):
            engine.detect_tables = False
        data, jpath = engine.extract(args.pdf, embed_images=True)
        out = engine.reinject(data, args.output_pdf,
                              draw_borders=not args.no_borders)
        n = sum(len(p["elements"]) for p in data["pages"])
        print(f"[OK] {len(data['pages'])} page(s), {n} objet(s)")
        print(f"  JSON : {jpath}")
        print(f"  PDF  : {out}")


if __name__ == "__main__":
    main()
