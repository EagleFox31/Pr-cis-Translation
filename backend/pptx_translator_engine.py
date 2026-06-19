import os
import zipfile
import json
import shutil
import tempfile
from lxml import etree
from pathlib import Path
from collections import defaultdict

NAMESPACES = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

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

    def extract_text(self, pptx_path, output_json="extraction_texte.json", filters=None, progress_callback=None, pages=None):
        if filters is None:
            filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}

        self._cleanup_temp()
        temp_path = self._get_temp_dir()
        temp_path.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback("Décompression du fichier PPTX...")
        try:
            self._extract_zip(pptx_path)
        except Exception as e:
            return None, f"Erreur lors de la décompression : {str(e)}"

        slides_dir = temp_path / "ppt" / "slides"
        if not slides_dir.exists():
            self._cleanup_temp()
            return None, "Le fichier n'est pas un PowerPoint valide."

        slide_files = sorted(slides_dir.glob("slide*.xml"), key=lambda x: int(x.stem.replace("slide", "")))
        
        extraction = {"slides": []}
        element_types_used = defaultdict(set)
        total_slides = len(slide_files)

        for i, slide_path in enumerate(slide_files):
            slide_num = int(slide_path.stem.replace("slide", ""))
            # Hors plage sélectionnée : on n'extrait pas le texte de cette diapo.
            # L'injection itère sur les fichiers de diapos (pas sur le JSON), donc
            # la diapo reste intacte dans sa langue d'origine. `pages` 1-basé sur
            # la position visuelle ; None = tout traduire.
            if pages is not None and (i + 1) not in pages:
                continue
            if progress_callback:
                progress_callback(f"Extraction slide {i+1}/{total_slides}...")
                
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
                    elif tag.endswith("}tbl"): shape_type = "tableau (tbl)"; break
                    elif tag.endswith("}cxnSp"): shape_type = "connecteur"; break
                    parent = parent.getparent()

            if shape_type == "shape (sp)" and not filters.get("shapes"): continue
            if shape_type == "tableau (tbl)" and not filters.get("tables"): continue
            if shape_type == "graphicFrame" and not filters.get("tables"): continue
            if shape_type == "connecteur" and not filters.get("connectors"): continue
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

    def inject_translation(self, original_pptx, translated_json_path, output_pptx, progress_callback=None, format_options=None):
        import re
        if not os.path.exists(translated_json_path):
            return False, "Fichier JSON de traduction introuvable."
        
        if progress_callback:
            progress_callback("Décompression du fichier PPTX...")
        self._extract_zip(original_pptx)
        temp_path = self._get_temp_dir()
        
        with open(translated_json_path, "r", encoding="utf-8") as f:
            translation_data = json.load(f)

        translation_map = {}
        for slide in translation_data.get("slides", []):
            for elem in slide.get("text_elements", []):
                translation_map[elem["id"]] = elem.get("translated_text", elem["text"])
            for diag in slide.get("diagram_elements", []):
                for elem in diag.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])

        try:
            slides_dir = temp_path / "ppt" / "slides"
            slide_files = sorted(slides_dir.glob("slide*.xml"), key=lambda x: int(x.stem.replace("slide", "")))
            total_slides = len(slide_files)

            for slide_path in slide_files:
                slide_num = int(slide_path.stem.replace("slide", ""))
                if progress_callback:
                    progress_callback(f"Réinjection slide {slide_num}/{total_slides}...")
                
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

            if progress_callback:
                progress_callback("Re-compression du fichier PPTX...")
            self._repack_zip(output_pptx)
            self._cleanup_temp()
            return True, f"Fichier traduit généré : {output_pptx}"

        except Exception as e:
            self._cleanup_temp()
            return False, f"Erreur lors de la réinjection : {str(e)}"

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
