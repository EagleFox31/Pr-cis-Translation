import os
import json
import re
import zipfile
import shutil
import tempfile
from pathlib import Path
from collections import defaultdict
from lxml import etree
import fitz

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NAMESPACES = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

def _w(tag):
    return f'{{{W}}}{tag}'

def _a(tag):
    return f'{{{A}}}{tag}'


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

    def _save_xml(self, tree, path):
        with open(path, 'wb') as f:
            f.write(etree.tostring(tree, encoding='utf-8', xml_declaration=True))

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

    def extract_text(self, docx_path, output_json='extraction_docx.json', filters=None, progress_callback=None):
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
                for p in hroot.findall(f'.//{_w("p")}'):
                    self._process_paragraph(p, f'hdr_{xml_file.stem}_{next_id("h")}', extraction['document']['headers'], types_used['document'], 'header')
            for xml_file in sorted(word_dir.glob('footer*.xml')):
                froot = self._parse_xml(xml_file).getroot()
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
            progress_callback(f'Extraction DOCX complete: {output_json}')
        return extraction, types_used

    def inject_translation(self, original_docx, translated_json_path, output_docx, progress_callback=None, format_options=None):
        if not os.path.exists(translated_json_path):
            return False, 'Translated JSON not found.'

        format_opts = format_options or {}

        with open(translated_json_path, 'r', encoding='utf-8') as f:
            translation_data = json.load(f)

        translation_map = {}
        doc_data = translation_data.get('document', {})
        for section in ('elements', 'headers', 'footers', 'textboxes', 'smartarts'):
            for elem in doc_data.get(section, []):
                translation_map[elem['id']] = elem.get('translated_text', elem['text'])

        if not translation_map: return False, 'No translated elements in JSON.'

        self._extract_zip(original_docx)
        temp_path = self._get_temp_dir()

        doc_xml = temp_path / 'word' / 'document.xml'
        tree = self._parse_xml(doc_xml)
        root = tree.getroot()
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
            h_mod = False; counters['h'] = 0
            for p in htree.getroot().findall(f'.//{_w("p")}'):
                eid = f'hdr_{xml_file.stem}_{next_id("h")}'
                if eid in translation_map: self._inject_paragraph(p, translation_map[eid]); h_mod = True
            if h_mod: self._save_xml(htree, xml_file)

        for xml_file in sorted(word_dir.glob('footer*.xml')):
            ftree = self._parse_xml(xml_file)
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
        return True, f'Translated DOCX generated: {output_docx}'


class PDFTranslatorEngine:
    FLAG_BOLD = 16
    FLAG_ITALIC = 2
    FLAG_MONOSPACE = 8
    FLAG_SUPERSCRIPT = 1

    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def _cleanup_temp(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _int_to_rgb(self, color_int: int) -> list:
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return [round(r, 4), round(g, 4), round(b, 4)]

    def _map_font(self, font_name: str, bold: bool, italic: bool) -> str:
        fn = font_name.lower()
        is_times = any(k in fn for k in ("times", "serif", "georgia", "garamond"))
        is_courier = any(k in fn for k in ("courier", "mono", "consol", "fixedsys", "terminal"))

        if is_courier:
            if bold and italic: return "coit"
            if bold: return "cobo"
            if italic: return "coit"
            return "cour"
        if is_times:
            if bold and italic: return "tibo"
            if bold: return "tibo"
            if italic: return "tiit"
            return "tiro"
        if bold and italic: return "heit"
        if bold: return "hebo"
        if italic: return "heit"
        return "helv"

    def _fit_fontsize(self, text: str, font_name: str, max_width: float, original_size: float, min_size: float = 5.0) -> float:
        size = original_size
        step = 0.5
        while size > min_size:
            try:
                w = fitz.get_text_length(text, fontname=font_name, fontsize=size)
                if w <= max_width:
                    break
            except Exception:
                break
            size -= step
        return max(round(size, 1), min_size)

    def extract_text(self, pdf_path: str, output_json: str = None, filters: dict = None, progress_callback=None):
        if output_json is None:
            output_json = str(Path(pdf_path).with_suffix("")) + "_extraction.json"

        extraction = {"pages": []}

        try:
            doc = fitz.open(pdf_path)
            total = len(doc)

            for page_num, page in enumerate(doc):
                if progress_callback:
                    progress_callback(f"Extracting page {page_num + 1}/{total}...")

                page_data = {
                    "page_num": page_num + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "text_blocks": []
                }

                raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

                for b_idx, block in enumerate(raw.get("blocks", [])):
                    if block.get("type") != 0:
                        continue

                    for l_idx, line in enumerate(block.get("lines", [])):
                        for s_idx, span in enumerate(line.get("spans", [])):
                            text = span.get("text", "")
                            if not text or not re.search(r'[a-zA-Z0-9]', text):
                                continue

                            text_to_translate = text.strip()
                            if not text_to_translate:
                                continue

                            color_int = span.get("color", 0)
                            color_rgb = self._int_to_rgb(color_int)
                            flags = span.get("flags", 0)
                            is_bold = bool(flags & self.FLAG_BOLD)
                            is_italic = bool(flags & self.FLAG_ITALIC)
                            font_raw = span.get("font", "Helvetica")
                            font_mapped = self._map_font(font_raw, is_bold, is_italic)

                            bbox = list(span.get("bbox", [0, 0, 0, 0]))
                            origin = list(span.get("origin", [bbox[0], bbox[3]]))

                            block_id = f"p{page_num + 1}_b{b_idx}_l{l_idx}_s{s_idx}"

                            page_data["text_blocks"].append({
                                "id": block_id,
                                "text": text,
                                "translated_text": "",
                                "bbox": bbox,
                                "origin": origin,
                                "font": font_raw,
                                "font_mapped": font_mapped,
                                "size": round(span.get("size", 12), 2),
                                "color": color_rgb,
                                "bold": is_bold,
                                "italic": is_italic,
                                "rotation": 0,
                                "page": page_num + 1,
                            })

                extraction["pages"].append(page_data)

            doc.close()

        except Exception as e:
            return None, f"Extraction error: {str(e)}"

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback(f"PDF extraction complete: {output_json}")
        return extraction, {}

    def inject_translation(self, original_pdf: str, translated_json_path: str, output_pdf: str, progress_callback=None, format_options=None):
        if not os.path.exists(translated_json_path):
            return False, "JSON file not found."

        format_opts = format_options or {}

        try:
            with open(translated_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return False, f"JSON read error: {str(e)}"

        try:
            original_doc = fitz.open(original_pdf)
            new_doc = fitz.open()
            pages = data.get("pages", [])
            total = len(pages)

            for page_idx, page_data in enumerate(pages):
                if page_idx >= len(original_doc):
                    break
                if progress_callback:
                    progress_callback(f"Injecting page {page_idx + 1}/{total}...")

                new_doc.insert_pdf(original_doc, from_page=page_idx, to_page=page_idx)
                new_page = new_doc[-1]

                blocks = page_data.get("text_blocks", [])

                for block in blocks:
                    bbox = block.get("bbox")
                    if not bbox or len(bbox) < 4:
                        continue
                    rect = fitz.Rect(bbox) + fitz.Rect(-1.5, -2, 1.5, 2)
                    new_page.add_redact_annot(rect, fill=(1, 1, 1))

                new_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                for block in blocks:
                    translated = block.get("translated_text", "").strip()
                    if not translated:
                        translated = block.get("text", "").strip()
                    if not translated:
                        continue

                    bbox = block.get("bbox")
                    origin = block.get("origin")
                    font_name = block.get("font_mapped", "helv")
                    orig_size = block.get("size", 12)
                    color = tuple(block.get("color", [0, 0, 0]))

                    if not bbox or len(bbox) < 4:
                        continue

                    if origin is not None and len(origin) >= 2:
                        x, y = origin[0], origin[1]
                    else:
                        x, y = bbox[0], bbox[3]

                    max_width = abs(bbox[2] - bbox[0])
                    if max_width < 2:
                        max_width = page_data.get("width", 595) - x

                    fontsize = self._fit_fontsize(translated, font_name, max_width, orig_size)

                    if progress_callback:
                        progress_callback(f"Inserting text at ({x:.1f}, {y:.1f}): {translated[:50]}...")

                    try:
                        new_page.insert_text(
                            (x, y), translated,
                            fontsize=fontsize,
                            fontname=font_name,
                            color=color
                        )
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Font fallback for text: {str(e)[:50]}")
                        new_page.insert_text(
                            (x, y), translated,
                            fontsize=max(fontsize, 6),
                            fontname="helv",
                            color=(0, 0, 0)
                        )

            original_doc.close()
            new_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
            new_doc.close()

            if not os.path.exists(output_pdf):
                return False, "PDF file was not created after save operation."

            if progress_callback:
                progress_callback(f"Translated PDF generated: {output_pdf}")
            return True, f"Translated PDF generated: {output_pdf}"
        except Exception as e:
            return False, f"Injection error: {str(e)}"


class PPTXTranslatorEngine:
    def __init__(self):
        self.temp_dir = None

    def _get_temp_dir(self):
        if self.temp_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="pptx_trad_"))
        return self.temp_dir

    def _cleanup_temp(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

    def _extract_zip(self, pptx_path):
        self._cleanup_temp()
        temp_path = self._get_temp_dir()
        temp_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pptx_path, 'r') as z:
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

    def _save_xml(self, tree, path):
        with open(path, 'wb') as f:
            f.write(etree.tostring(tree, encoding='utf-8', xml_declaration=True))

    def _process_xml_element(self, root, slide_num, data_store, element_types_used, id_prefix, filters):
        paragraphs = root.xpath(".//a:p", namespaces=NAMESPACES)
        for p_idx, p_elem in enumerate(paragraphs):
            shape_type = "SmartArt (Diagram)" if "diag" in id_prefix else "unknown"
            if "diag" not in id_prefix:
                parent = p_elem.getparent()
                while parent is not None:
                    tag = parent.tag
                    if tag.endswith("}sp"): shape_type = "shape (sp)"; break
                    elif tag.endswith("}graphicFrame"): shape_type = "graphicFrame"; break
                    elif tag.endswith("}tbl"): shape_type = "table (tbl)"; break
                    elif tag.endswith("}cxnSp"): shape_type = "connector"; break
                    parent = parent.getparent()

            if shape_type == "shape (sp)" and not filters.get("shapes"): continue
            if shape_type == "table (tbl)" and not filters.get("tables"): continue
            if shape_type == "graphicFrame" and not filters.get("tables"): continue
            if shape_type == "connector" and not filters.get("connectors"): continue
            if shape_type == "SmartArt (Diagram)" and not filters.get("smartarts"): continue

            runs = p_elem.xpath(".//a:r", namespaces=NAMESPACES)
            if not runs:
                text_nodes = p_elem.xpath(".//a:t", namespaces=NAMESPACES)
                if not text_nodes:
                    tagged_text = ""
                else:
                    full_text = "".join([t.text for t in text_nodes if t.text])
                    tagged_text = f"[[0]]{full_text}[[/0]]"
            else:
                tagged_parts = []
                valid_run_count = 0
                for r_idx, r_elem in enumerate(runs):
                    t_nodes = r_elem.xpath(".//a:t", namespaces=NAMESPACES)
                    r_text = "".join([t.text for t in t_nodes if t.text])
                    if r_text.strip():
                        tagged_parts.append(f"[[{valid_run_count}]]{r_text}[[/{valid_run_count}]]")
                        valid_run_count += 1
                tagged_text = "".join(tagged_parts)

            elem_id = f"slide{slide_num}_{id_prefix}_p{p_idx}"
            data_store.append({
                "id": elem_id,
                "text": tagged_text,
                "context": {"shape_type": shape_type, "paragraph_index": p_idx}
            })
            element_types_used[slide_num].add(shape_type)

    def extract_text(self, pptx_path, output_json="extraction.json", filters=None, progress_callback=None):
        if filters is None:
            filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}

        self._extract_zip(pptx_path)

        slides_dir = self._get_temp_dir() / "ppt" / "slides"
        if not slides_dir.exists():
            self._cleanup_temp()
            return None, "Invalid PowerPoint file."

        slide_files = sorted(slides_dir.glob("slide*.xml"), key=lambda x: int(x.stem.replace("slide", "")))

        extraction = {"slides": []}
        element_types_used = defaultdict(set)
        total_slides = len(slide_files)

        for i, slide_path in enumerate(slide_files):
            slide_num = int(slide_path.stem.replace("slide", ""))
            if progress_callback:
                progress_callback(f"Extracting slide {i+1}/{total_slides}...")

            tree = etree.parse(str(slide_path))
            root = tree.getroot()

            slide_data = {
                "slide_id": slide_num,
                "text_elements": [],
                "diagram_elements": []
            }

            self._process_xml_element(root, slide_num, slide_data["text_elements"], element_types_used, "p", filters)

            if filters.get("smartarts"):
                rels_path = slides_dir / "_rels" / f"{slide_path.name}.rels"
                if rels_path.exists():
                    rels_tree = etree.parse(str(rels_path))
                    diag_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData']")
                    for rel in diag_rels:
                        target = rel.get("Target")
                        diag_path = (slides_dir / target).resolve()
                        if diag_path.exists():
                            diag_tree = etree.parse(str(diag_path))
                            diag_root = diag_tree.getroot()
                            diag_id = diag_path.stem
                            diag_data = {"diag_id": diag_id, "text_elements": []}
                            self._process_xml_element(diag_root, slide_num, diag_data["text_elements"], element_types_used, f"diag_{diag_id}", filters)
                            if diag_data["text_elements"]:
                                slide_data["diagram_elements"].append(diag_data)

            if slide_data["text_elements"] or slide_data["diagram_elements"]:
                extraction["slides"].append(slide_data)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        self._cleanup_temp()
        return extraction, element_types_used

    def _inject_in_xml(self, xml_path, slide_num, id_prefix, translation_map):
        import re
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        modified = False

        paragraphs = root.xpath(".//a:p", namespaces=NAMESPACES)
        for p_idx, p_elem in enumerate(paragraphs):
            elem_id = f"slide{slide_num}_{id_prefix}_p{p_idx}"
            if elem_id in translation_map:
                translated_text = translation_map[elem_id]
                matches = re.findall(r"\[\[(\d+)\]\](.*?)\[\[/\1\]\]", translated_text, re.DOTALL)
                match_dict = {int(idx): txt for idx, txt in matches}

                runs = p_elem.xpath(".//a:r", namespaces=NAMESPACES)
                text_nodes_direct = p_elem.xpath(".//a:t", namespaces=NAMESPACES)

                if runs:
                    valid_idx = 0
                    for r_elem in runs:
                        t_nodes = r_elem.xpath(".//a:t", namespaces=NAMESPACES)
                        r_text = "".join([t.text for t in t_nodes if t.text])

                        if r_text.strip():
                            if valid_idx in match_dict:
                                if t_nodes:
                                    t_nodes[0].text = match_dict[valid_idx]
                                    for i in range(1, len(t_nodes)): t_nodes[i].text = ""
                            valid_idx += 1
                    modified = True
                elif text_nodes_direct:
                    for t_idx, t_node in enumerate(text_nodes_direct):
                        t_node.text = match_dict.get(t_idx, "")
                    modified = True

        if modified:
            with open(xml_path, "wb") as f:
                f.write(etree.tostring(tree, encoding="utf-8", xml_declaration=True))

    def inject_translation(self, original_pptx, translated_json_path, output_pptx, progress_callback=None, format_options=None):
        import re
        if not os.path.exists(translated_json_path):
            return False, "Translated JSON not found."

        format_opts = format_options or {}

        with open(translated_json_path, "r", encoding="utf-8") as f:
            translation_data = json.load(f)

        translation_map = {}
        for slide in translation_data.get("slides", []):
            for elem in slide.get("text_elements", []):
                translation_map[elem["id"]] = elem.get("translated_text", elem["text"])
            for diag in slide.get("diagram_elements", []):
                for elem in diag.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])

        if not translation_map:
            return False, "No translated elements in JSON."

        self._extract_zip(original_pptx)
        temp_path = self._get_temp_dir()

        slides_dir = temp_path / "ppt" / "slides"
        slide_files = sorted(slides_dir.glob("slide*.xml"), key=lambda x: int(x.stem.replace("slide", "")))
        total_slides = len(slide_files)

        for slide_path in slide_files:
            slide_num = int(slide_path.stem.replace("slide", ""))
            if progress_callback:
                progress_callback(f"Injecting slide {slide_num}/{total_slides}...")

            self._inject_in_xml(slide_path, slide_num, "p", translation_map)

            rels_path = slides_dir / "_rels" / f"{slide_path.name}.rels"
            if rels_path.exists():
                rels_tree = etree.parse(str(rels_path))
                diag_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData']")
                for rel in diag_rels:
                    target = rel.get("Target")
                    diag_path = (slides_dir / target).resolve()
                    if diag_path.exists():
                        diag_id = diag_path.stem
                        self._inject_in_xml(diag_path, slide_num, f"diag_{diag_id}", translation_map)

        self._repack_zip(output_pptx)
        self._cleanup_temp()
        return True, f"Translated PPTX generated: {output_pptx}"