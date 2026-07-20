"""Diagnostic complet de l'extraction et réinjection sur original.pptx pour identifier la cause exacte des erreurs PowerPoint."""
import zipfile, io, os, sys, json
from lxml import etree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pptx_translator_engine import PPTXTranslatorEngine

pptx_in = r"C:\Users\IBRAH\Documents\Projets\original.pptx"
json_out = os.path.join(os.path.dirname(__file__), "debug_extract.json")

print("1. Test d'extraction de tous les masques, layouts et slides...")
engine = PPTXTranslatorEngine()
extraction, types = engine.extract_text(pptx_in, json_out)

print(f"   - Nombre de slides extraites: {len(extraction.get('slides', []))}")

# Vérifier si des slideMasters existent
with zipfile.ZipFile(pptx_in, "r") as zf:
    masters = [f for f in zf.namelist() if f.startswith("ppt/slideMasters/") and f.endswith(".xml")]
    print(f"   - Slide Masters trouvés dans le PPTX : {masters}")
    for m in masters:
        tree = etree.fromstring(zf.read(m))
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        txts = [t.text for t in tree.xpath(".//a:t", namespaces=ns) if t.text]
        print(f"     Textes dans {m}: {txts}")

try: os.remove(json_out)
except OSError: pass
