"""Test d'intégrité de la réinjection OpenXML sur original.pptx pour valider l'ouverture sans erreur PowerPoint."""
import sys, os, json, zipfile
from lxml import etree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pptx_translator_engine import PPTXTranslatorEngine

pptx_in = r"C:\Users\IBRAH\Documents\Projets\original.pptx"
json_out = os.path.join(os.path.dirname(__file__), "temp_integrity.json")
pptx_out = r"C:\Users\IBRAH\Documents\Projets\TEST_REINJECT_INTEGRITY.pptx"

print("1. Extraction complète...")
engine = PPTXTranslatorEngine()
extraction, types = engine.extract_text(pptx_in, json_out)

print("2. Réinjection sans aucune modification...")
ok, msg = engine.inject_translation(pptx_in, json_out, pptx_out)
print(f"   - Injection ok: {ok}, message: {msg}")

if os.path.exists(pptx_out):
    print(f"   - Fichier test généré : {pptx_out} ({os.path.getsize(pptx_out)} octets)")

try: os.remove(json_out)
except OSError: pass
