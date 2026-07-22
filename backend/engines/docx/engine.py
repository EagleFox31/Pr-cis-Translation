"""
DOCXTranslatorEngine – réécrit pour suivre exactement la même logique que
PPTXTranslatorEngine :
  • Extraction via lxml directement sur le XML interne du DOCX
  • Réinjection via lxml en modifiant les nœuds <w:t> en place (aucune
    suppression/recréation de run → toute la mise en forme est préservée)
  • Gestion cohérente des textboxes, headers et footers
"""

import os
import json
import zipfile
import shutil
import re
import tempfile
from pathlib import Path
from collections import defaultdict
from lxml import etree

# ── Namespace WordprocessingML ────────────────────────────────────────────────
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
# Markup Compatibility : encapsule deux représentations du MÊME contenu —
# mc:Choice (moderne, rendu par Word/LibreOffice) et mc:Fallback (VML legacy,
# jamais rendu). Les deux portent un w:txbxContent → sans filtrage on extrait et
# on réinjecte le texte deux fois (texte « fantôme » dédoublé à l'écran).
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'

def _w(tag):
    return f'{{{W}}}{tag}'

def _a(tag):
    return f'{{{A}}}{tag}'

def _mc(tag):
    return f'{{{MC}}}{tag}'


class DOCXTranslatorEngine:
    def __init__(self):
        self.temp_dir = None

    def _get_temp_dir(self):
        if self.temp_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="docx_trad_"))
        return self.temp_dir

    def _cleanup_temp(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

    # ── ZIP helpers ───────────────────────────────────────────────────────────

    def _extract_zip(self, docx_path):
        self._cleanup_temp()
        temp_path = self._get_temp_dir()
        temp_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(docx_path, 'r') as z:
            z.extractall(temp_path)

    def _repack_zip(self, output_path):
        temp_path = self._get_temp_dir()
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for root_dir, dirs, files in os.walk(temp_path):
                for file in files:
                    fp = os.path.join(root_dir, file)
                    arcname = os.path.relpath(fp, temp_path)
                    z.write(fp, arcname)

    def _parse_xml(self, path):
        return etree.parse(str(path))

    def _strip_fallbacks(self, root):
        """Retire les blocs mc:Fallback de l'arbre en mémoire. Ce sont des copies
        non rendues du mc:Choice : les conserver provoque une double
        extraction/réinjection du même texte. Appelé À L'IDENTIQUE en extraction
        et en injection pour garder l'alignement des id (même parcours)."""
        for fb in root.findall(f'.//{_mc("Fallback")}'):
            parent = fb.getparent()
            if parent is not None:
                parent.remove(fb)

    def _save_xml(self, tree, path):
        with open(path, 'wb') as f:
            f.write(etree.tostring(tree, encoding='utf-8', xml_declaration=True))

    # ── Collecte des runs d'un <w:p> (Word) ──────────────────────────────────

    def _process_paragraph(self, p_elem, elem_id, data_store, types_set, source_label):
        runs = p_elem.findall(f'{_w("r")}')
        tagged_parts = []
        valid_idx = 0

        for r_elem in runs:
            t_elems = r_elem.findall(f'{_w("t")}')
            r_text = ''.join((t.text or '') for t in t_elems)
            
            if r_text.strip():
                tagged_parts.append(f'[[{valid_idx}]]{r_text}[[/{valid_idx}]]')
                valid_idx += 1

        data_store.append({
            'id': elem_id,
            'text': ''.join(tagged_parts),
            'context': {
                'type': source_label,
                'run_count': valid_idx,
            }
        })
        types_set.add(source_label)

    # ── Collecte des runs d'un <a:p> (DrawingML / SmartArt) ──────────────────

    def _process_drawing_paragraph(self, p_elem, elem_id, data_store, types_set, source_label):
        runs = p_elem.findall(f'.//{_a("r")}')
        tagged_parts = []
        valid_idx = 0

        for r_elem in runs:
            t_elems = r_elem.findall(f'.//{_a("t")}')
            r_text = ''.join((t.text or '') for t in t_elems)
            if r_text:
                tagged_parts.append(f'[[{valid_idx}]]{r_text}[[/{valid_idx}]]')
                valid_idx += 1

        if not tagged_parts:
            t_nodes = p_elem.findall(f'.//{_a("t")}')
            if not runs and t_nodes:
                full_text = ''.join((t.text or '') for t in t_nodes)
                if full_text.strip():
                    tagged_parts.append(f'[[0]]{full_text}[[/0]]')
                    valid_idx = 1

        if not tagged_parts:
            return

        data_store.append({
            'id': elem_id,
            'text': ''.join(tagged_parts),
            'context': {
                'type': source_label,
                'run_count': valid_idx,
            }
        })
        types_set.add(source_label)

    # ── Réinjection dans les runs d'un <w:p> (Word) ──────────────────────────

    def _inject_paragraph(self, p_elem, translated_text):
        matches = re.findall(r'\[\[(\d+)\]\](.*?)\[\[/\1\]\]', translated_text, re.DOTALL)
        if not matches: return
        match_dict = {int(idx): txt for idx, txt in matches}

        runs = p_elem.findall(f'{_w("r")}')
        valid_idx = 0
        for r_elem in runs:
            t_elems = r_elem.findall(f'{_w("t")}')
            r_text = ''.join((t.text or '') for t in t_elems)
            
            if r_text.strip():
                if valid_idx in match_dict:
                    new_text = match_dict[valid_idx]
                    if t_elems:
                        t_elems[0].text = new_text
                        if new_text and (new_text.startswith(' ') or new_text.endswith(' ')):
                            t_elems[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                        for extra_t in t_elems[1:]:
                            extra_t.text = ''
                valid_idx += 1

    # ── Réinjection dans les runs d'un <a:p> (DrawingML / SmartArt) ──────────

    def _inject_drawing_paragraph(self, p_elem, translated_text):
        matches = re.findall(r'\[\[(\d+)\]\](.*?)\[\[/\1\]\]', translated_text, re.DOTALL)
        if not matches: return
        match_dict = {int(idx): txt for idx, txt in matches}

        runs = p_elem.findall(f'.//{_a("r")}')
        if runs:
            valid_idx = 0
            for r_elem in runs:
                t_elems = r_elem.findall(f'.//{_a("t")}')
                r_text = ''.join((t.text or '') for t in t_elems)
                if not r_text: continue
                if t_elems:
                    t_elems[0].text = match_dict.get(valid_idx, '')
                    for extra_t in t_elems[1:]: extra_t.text = ''
                valid_idx += 1
        else:
            t_nodes = p_elem.findall(f'.//{_a("t")}')
            for idx, t_node in enumerate(t_nodes):
                t_node.text = match_dict.get(idx, '')

    # ══════════════════════════════════════════════════════════════════════════
    # 1. EXTRACTION
    # ══════════════════════════════════════════════════════════════════════════

    def extract_text(self, docx_path, output_json='extraction_docx.json',
                     filters=None, progress_callback=None):
        if filters is None:
            filters = {
                'paragraphs': True, 'tables': True,
                'headers_footers': True, 'text_boxes': True,
                'smartarts': True
            }

        self._extract_zip(docx_path)

        extraction = {
            'document': {
                'elements': [], 'headers': [], 'footers': [],
                'textboxes': [], 'smartarts': []
            }
        }
        types_used = {'document': set()}
        counters = defaultdict(int)

        def next_id(prefix='para'):
            idx = counters[prefix]; counters[prefix] += 1
            return f'{prefix}_{idx}'

        temp_path = self._get_temp_dir()
        doc_xml = temp_path / 'word' / 'document.xml'
        tree = self._parse_xml(doc_xml)
        root = tree.getroot()
        self._strip_fallbacks(root)

        body = root.find(f'.//{_w("body")}')
        if body is None: body = root

        for child in body:
            tag = etree.QName(child.tag).localname
            if tag == 'p' and filters.get('paragraphs', True):
                self._process_paragraph(child, next_id('body_para'), extraction['document']['elements'], types_used['document'], 'paragraph')
            elif tag == 'tbl' and filters.get('tables', True):
                for row in child.findall(f'.//{_w("tr")}'):
                    for cell in row.findall(f'.//{_w("tc")}'):
                        for p in cell.findall(f'{_w("p")}'):
                            self._process_paragraph(p, next_id('tbl_para'), extraction['document']['elements'], types_used['document'], 'table_cell')
                types_used['document'].add('table')

        if filters.get('text_boxes', True):
            for txbx in root.findall(f'.//{_w("txbxContent")}'):
                for p in txbx.findall(f'.//{_w("p")}'):
                    self._process_paragraph(p, next_id('txbx_para'), extraction['document']['textboxes'], types_used['document'], 'textbox')

        if filters.get('headers_footers', True):
            word_dir = self._get_temp_dir() / 'word'
            for xml_file in sorted(word_dir.glob('header*.xml')):
                hroot = self._parse_xml(xml_file).getroot()
                self._strip_fallbacks(hroot)
                for p in hroot.findall(f'.//{_w("p")}'):
                    self._process_paragraph(p, f'hdr_{xml_file.stem}_{next_id("h")}', extraction['document']['headers'], types_used['document'], 'header')
            for xml_file in sorted(word_dir.glob('footer*.xml')):
                froot = self._parse_xml(xml_file).getroot()
                self._strip_fallbacks(froot)
                for p in froot.findall(f'.//{_w("p")}'):
                    self._process_paragraph(p, f'ftr_{xml_file.stem}_{next_id("f")}', extraction['document']['footers'], types_used['document'], 'footer')

        if filters.get('smartarts', True):
            diag_dir = self._get_temp_dir() / 'word' / 'diagrams'
            if diag_dir.exists():
                for diag_file in sorted(diag_dir.glob('data*.xml')):
                    droot = self._parse_xml(diag_file).getroot()
                    d_ctr = 0
                    for p in droot.xpath('.//a:p', namespaces={'a': A}):
                        self._process_drawing_paragraph(p, f'dgm_{diag_file.stem}_{d_ctr}', extraction['document']['smartarts'], types_used['document'], 'smartart')
                        d_ctr += 1

        self._cleanup_temp()
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback(f'✓ Extraction DOCX terminée → {output_json}')
        return extraction, types_used

    # ══════════════════════════════════════════════════════════════════════════
    # 2. RÉINJECTION
    # ══════════════════════════════════════════════════════════════════════════

    def inject_translation(self, original_docx, translated_json_path,
                           output_docx, progress_callback=None,
                           format_options=None):
        if not os.path.exists(translated_json_path):
            return False, 'Fichier JSON de traduction introuvable.'

        with open(translated_json_path, 'r', encoding='utf-8') as f:
            translation_data = json.load(f)

        translation_map = {}
        doc_data = translation_data.get('document', {})
        for section in ('elements', 'headers', 'footers', 'textboxes', 'smartarts'):
            for elem in doc_data.get(section, []):
                translation_map[elem['id']] = elem.get('translated_text', elem['text'])

        if not translation_map: return False, 'Aucun élément traduit dans le JSON.'

        self._extract_zip(original_docx)
        temp_path = self._get_temp_dir()
        
        doc_xml = temp_path / 'word' / 'document.xml'
        tree = self._parse_xml(doc_xml)
        root = tree.getroot()
        self._strip_fallbacks(root)
        body = root.find(f'.//{_w("body")}')
        if body is None:
            body = root
        
        counters = defaultdict(int)
        def next_id(prefix='para'):
            idx = counters[prefix]; counters[prefix] += 1
            return f'{prefix}_{idx}'

        for child in body:
            tag = etree.QName(child.tag).localname
            if tag == 'p':
                eid = next_id('body_para')
                if eid in translation_map: self._inject_paragraph(child, translation_map[eid])
            elif tag == 'tbl':
                for row in child.findall(f'.//{_w("tr")}'):
                    for cell in row.findall(f'.//{_w("tc")}'):
                        for p in cell.findall(f'{_w("p")}'):
                            eid = next_id('tbl_para')
                            if eid in translation_map: self._inject_paragraph(p, translation_map[eid])

        for txbx in root.findall(f'.//{_w("txbxContent")}'):
            for p in txbx.findall(f'.//{_w("p")}'):
                eid = next_id('txbx_para')
                if eid in translation_map: self._inject_paragraph(p, translation_map[eid])

        self._save_xml(tree, doc_xml)

        word_dir = self._get_temp_dir() / 'word'
        for xml_file in sorted(word_dir.glob('header*.xml')):
            htree = self._parse_xml(xml_file)
            self._strip_fallbacks(htree.getroot())
            h_mod = False; counters['h'] = 0
            for p in htree.getroot().findall(f'.//{_w("p")}'):
                eid = f'hdr_{xml_file.stem}_{next_id("h")}'
                if eid in translation_map: self._inject_paragraph(p, translation_map[eid]); h_mod = True
            if h_mod: self._save_xml(htree, xml_file)

        for xml_file in sorted(word_dir.glob('footer*.xml')):
            ftree = self._parse_xml(xml_file)
            self._strip_fallbacks(ftree.getroot())
            f_mod = False; counters['f'] = 0
            for p in ftree.getroot().findall(f'.//{_w("p")}'):
                eid = f'ftr_{xml_file.stem}_{next_id("f")}'
                if eid in translation_map: self._inject_paragraph(p, translation_map[eid]); f_mod = True
            if f_mod: self._save_xml(ftree, xml_file)

        diag_dir = word_dir / 'diagrams'
        if diag_dir.exists():
            for diag_file in sorted(diag_dir.glob('data*.xml')):
                dtree = self._parse_xml(diag_file)
                d_mod = False; d_ctr = 0
                for p in dtree.getroot().xpath('.//a:p', namespaces={'a': A}):
                    eid = f'dgm_{diag_file.stem}_{d_ctr}'
                    if eid in translation_map: self._inject_drawing_paragraph(p, translation_map[eid]); d_mod = True
                    d_ctr += 1
                if d_mod: self._save_xml(dtree, diag_file)

        self._repack_zip(output_docx)
        self._cleanup_temp()
        return True, f'Fichier DOCX traduit généré : {output_docx}'
