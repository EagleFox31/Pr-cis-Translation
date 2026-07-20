import os
import zipfile
import json
import shutil
import tempfile
import re
import io
from lxml import etree
from pathlib import Path
from collections import defaultdict

NAMESPACES = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    's': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
}


def _is_numeric(val: str) -> bool:
    """Vérifie si une chaîne est une valeur numérique pure (pour ne pas extraire
    les chiffres bruts des axes ou données de graphiques)."""
    try:
        float(val.strip().replace(",", ".").replace(" ", "").replace("%", ""))
        return True
    except ValueError:
        return False


def _auto_refresh_powerpoint(pptx_path: str) -> bool:
    """Sur Windows, ouvre silencieusement le PPTX en arrière-plan via COM/PowerShell
    pour forcer la mise à jour automatique de tous les aperçus d'objets OLE (tableaux/graphiques Excel)."""
    if os.name != 'nt':
        return False
    import subprocess
    abs_path = os.path.abspath(pptx_path)
    if not os.path.exists(abs_path):
        return False

    ps_script = f"""
$ErrorActionPreference = 'Stop'
try {{
    $ppt = New-Object -ComObject PowerPoint.Application
    $pres = $ppt.Presentations.Open('{abs_path}', 0, 0, 0)
    foreach ($slide in $pres.Slides) {{
        foreach ($shape in $slide.Shapes) {{
            if ($shape.Type -eq 7 -or $shape.Type -eq 10 -or $shape.Type -eq 14) {{
                try {{ $shape.OLEFormat.Update() }} catch {{}}
            }}
        }}
    }}
    $pres.Save()
    $pres.Close()
    $ppt.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
    Write-Host "AUTO_REFRESH_SUCCESS"
}} catch {{
    Write-Host "AUTO_REFRESH_ERROR: $_"
    exit 1
}}
"""
    ps_file = os.path.join(os.path.dirname(abs_path), f"_temp_refresh_{os.getpid()}.ps1")
    try:
        with open(ps_file, "w", encoding="utf-8") as f:
            f.write(ps_script)

        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return "AUTO_REFRESH_SUCCESS" in res.stdout
    except Exception:
        return False
    finally:
        if os.path.exists(ps_file):
            try: os.remove(ps_file)
            except OSError: pass


class PPTXTranslatorEngine:
    def __init__(self):
        self.temp_dir = None

    def generate_autorefresh_pptm(self, pptx_path: str, pptm_output_path: str = None) -> str:
        """Génère une version .pptm (PowerPoint Macro-Enabled) contenant la macro VBA
        Presentation_Open qui rafraîchit automatiquement tous les objets OLE Excel
        dès l'ouverture dans Microsoft PowerPoint."""
        if pptm_output_path is None:
            if pptx_path.lower().endswith(".pptx"):
                pptm_output_path = pptx_path[:-5] + "_autorefresh.pptm"
            else:
                pptm_output_path = pptx_path + "_autorefresh.pptm"

        template_pptm_path = os.path.join(os.path.dirname(__file__), "templates", "template_autorefresh.pptm")

        if not os.path.exists(pptx_path) or not os.path.exists(template_pptm_path):
            return None

        try:
            with zipfile.ZipFile(template_pptm_path, "r") as ztemplate:
                if "ppt/vbaProject.bin" not in ztemplate.namelist():
                    return None
                vba_bin_bytes = ztemplate.read("ppt/vbaProject.bin")

            with zipfile.ZipFile(pptx_path, "r") as xin, zipfile.ZipFile(pptm_output_path, "w", zipfile.ZIP_DEFLATED) as xout:
                for item in xin.infolist():
                    content = xin.read(item.filename)

                    if item.filename == "[Content_Types].xml":
                        tree = etree.fromstring(content)
                        for elem in tree.xpath(".//*[@PartName='/ppt/presentation.xml']"):
                            elem.attrib["ContentType"] = "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
                        bin_exists = False
                        for elem in tree.xpath(".//*[@Extension='bin']"):
                            bin_exists = True
                        if not bin_exists:
                            default_bin = etree.Element("{http://schemas.openxmlformats.org/package/2006/content-types}Default", Extension="bin", ContentType="application/vnd.ms-office.vbaProject")
                            tree.append(default_bin)
                        content = etree.tostring(tree, encoding="utf-8", xml_declaration=True)

                    if item.filename == "ppt/_rels/presentation.xml.rels":
                        tree = etree.fromstring(content)
                        rel_vba_exists = False
                        for elem in tree.xpath(".//*[@Target='vbaProject.bin']"):
                            rel_vba_exists = True
                        if not rel_vba_exists:
                            rel_elem = etree.Element("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship", Id="rIdVbaProjectAuto", Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject", Target="vbaProject.bin")
                            tree.append(rel_elem)
                        content = etree.tostring(tree, encoding="utf-8", xml_declaration=True)

                    xout.writestr(item, content)

                xout.writestr("ppt/vbaProject.bin", vba_bin_bytes)

            if os.path.exists(pptm_output_path) and os.path.getsize(pptm_output_path) > 0:
                return pptm_output_path
            return None
        except Exception as e:
            print(f"Erreur génération PPTM AutoRefresh: {e}")
            return None

    def _get_temp_dir(self):
        if self.temp_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="pptx_trad_"))
        return self.temp_dir

    def _cleanup_temp(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

    def _extract_zip(self, pptx_path):
        """Décompresse le PPTX (archive ZIP) dans le dossier temporaire."""
        temp_path = self._get_temp_dir()
        with zipfile.ZipFile(pptx_path, 'r') as zf:
            zf.extractall(temp_path)

    def _repack_zip(self, output_path):
        """Re-compresse le dossier temporaire en un fichier PPTX valide."""
        temp_path = self._get_temp_dir()
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(temp_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_path)
                    zf.write(file_path, arcname)

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
            if pages is not None and (i + 1) not in pages:
                continue
            if progress_callback:
                progress_callback(f"Extraction slide {i+1}/{total_slides}...")
                
            tree = etree.parse(str(slide_path))
            root = tree.getroot()

            slide_data = {
                "slide_id": slide_num,
                "text_elements": [],
                "diagram_elements": [],
                "chart_elements": [],
                "layout_elements": [],
                "excel_elements": []
            }

            # 1. Extraction du texte de la slide
            self._process_xml_element(root, slide_num, slide_data["text_elements"], element_types_used, "p", filters)

            rels_path = slides_dir / "_rels" / f"{slide_path.name}.rels"
            if rels_path.exists():
                rels_tree = etree.parse(str(rels_path))

                # 2. SmartArts (Diagrams)
                if filters.get("smartarts"):
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

                # 3. Graphiques XML (Charts)
                if filters.get("tables"):
                    chart_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart']")
                    for rel in chart_rels:
                        target = rel.get("Target")
                        chart_path = (slides_dir / target).resolve()
                        if chart_path.exists():
                            chart_tree = etree.parse(str(chart_path))
                            chart_root = chart_tree.getroot()
                            chart_id = chart_path.stem
                            chart_data = {"chart_id": chart_id, "text_elements": []}
                            self._process_xml_element(chart_root, slide_num, chart_data["text_elements"], element_types_used, f"chart_{chart_id}", filters)
                            if chart_data["text_elements"]:
                                slide_data["chart_elements"].append(chart_data)

                # 4. Modèles de disposition (slideLayouts - pour les sous-titres et masques)
                layout_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout']")
                for rel in layout_rels:
                    target = rel.get("Target")
                    layout_path = (slides_dir / target).resolve()
                    if layout_path.exists():
                        layout_tree = etree.parse(str(layout_path))
                        layout_root = layout_tree.getroot()
                        layout_id = layout_path.stem
                        layout_data = {"layout_id": layout_id, "text_elements": []}
                        self._process_xml_element(layout_root, slide_num, layout_data["text_elements"], element_types_used, f"layout_{layout_id}", filters)
                        if layout_data["text_elements"]:
                            slide_data["layout_elements"].append(layout_data)

                # 5. Tableaux & Graphiques Excel incorporés (ppt/embeddings/*.xlsx)
                if filters.get("tables"):
                    pkg_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/package']")
                    for rel in pkg_rels:
                        target = rel.get("Target")
                        emb_path = (slides_dir / target).resolve()
                        if emb_path.exists() and emb_path.suffix.lower() in ('.xlsx', '.xlsm'):
                # 6. Masques principaux (slideMasters)
                masters_dir = temp_path / "ppt" / "slideMasters"
                if masters_dir.exists():
                    for master_path in sorted(masters_dir.glob("slideMaster*.xml")):
                        master_tree = etree.parse(str(master_path))
                        master_root = master_tree.getroot()
                        master_id = master_path.stem
                        master_data = {"master_id": master_id, "text_elements": []}
                        self._process_xml_element(master_root, slide_num, master_data["text_elements"], element_types_used, f"master_{master_id}", filters)
                        if master_data["text_elements"]:
                            if "master_elements" not in slide_data:
                                slide_data["master_elements"] = []
                            slide_data["master_elements"].append(master_data)

            if any([slide_data.get("text_elements"), slide_data.get("diagram_elements"),
                    slide_data.get("chart_elements"), slide_data.get("layout_elements"),
                    slide_data.get("master_elements"), slide_data.get("excel_elements")]):
                extraction["slides"].append(slide_data)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        self._cleanup_temp()
        return extraction, element_types_used

    def _process_excel_file(self, emb_path: Path, slide_num: int, excel_store: list, element_types_used: dict):
        """Extrait les chaînes de texte partagées (xl/sharedStrings.xml) d'un fichier Excel incorporé."""
        try:
            with open(emb_path, "rb") as f:
                excel_bytes = f.read()
            with zipfile.ZipFile(io.BytesIO(excel_bytes), "r") as xzf:
                if "xl/sharedStrings.xml" in xzf.namelist():
                    ss_xml = xzf.read("xl/sharedStrings.xml")
                    tree = etree.fromstring(ss_xml)
                    t_nodes = tree.xpath(".//s:t", namespaces=NAMESPACES)
                    for t_idx, t_node in enumerate(t_nodes):
                        val = t_node.text or ""
                        if val.strip() and not _is_numeric(val):
                            elem_id = f"slide{slide_num}_excel_{emb_path.stem}_ss{t_idx}"
                            excel_store.append({
                                "id": elem_id,
                                "text": f"[[0]]{val}[[/0]]",
                                "context": {"shape_type": "Excel Cell", "paragraph_index": t_idx}
                            })
                            element_types_used[slide_num].add("Excel Cell")
        except Exception:
            pass

    def _process_xml_element(self, root, slide_num, data_store, element_types_used, id_prefix, filters):
        paragraphs = root.xpath(".//a:p", namespaces=NAMESPACES)
        for p_idx, p_elem in enumerate(paragraphs):
            shape_type = "SmartArt (Diagram)" if "diag" in id_prefix else ("Chart" if "chart" in id_prefix else ("Slide Layout" if "layout" in id_prefix else "unknown"))
            if "diag" not in id_prefix and "chart" not in id_prefix and "layout" not in id_prefix:
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
            if shape_type == "Chart" and not filters.get("tables"): continue

            # Unifier l'extraction au niveau du paragraphe <a:p> pour éviter le morcellement des mots (ex: Sous- + titre -> Subtitletitre)
            text_nodes = p_elem.xpath(".//a:t", namespaces=NAMESPACES)
            if not text_nodes:
                continue

            full_text = "".join([t.text for t in text_nodes if t.text])
            if not full_text.strip() or _is_numeric(full_text):
                continue

            elem_id = f"slide{slide_num}_{id_prefix}_p{p_idx}"
            data_store.append({
                "id": elem_id,
                "text": f"[[0]]{full_text}[[/0]]",
                "context": {"shape_type": shape_type, "paragraph_index": p_idx}
            })
            element_types_used[slide_num].add(shape_type)

        # Pour les graphiques XML (charts), extraire aussi les étiquettes autonomes (<c:v> / <c:t>)
        if "chart" in id_prefix:
            c_nodes = root.xpath(".//c:v | .//c:t", namespaces=NAMESPACES)
            for v_idx, v_node in enumerate(c_nodes):
                v_text = v_node.text or ""
                if v_text.strip() and not _is_numeric(v_text):
                    elem_id = f"slide{slide_num}_{id_prefix}_cv{v_idx}"
                    data_store.append({
                        "id": elem_id,
                        "text": f"[[0]]{v_text}[[/0]]",
                        "context": {"shape_type": "Chart Label", "paragraph_index": v_idx}
                    })
                    element_types_used[slide_num].add("Chart Label")

    def inject_translation(self, original_pptx, translated_json_path, output_pptx, progress_callback=None, format_options=None):
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
            for chart in slide.get("chart_elements", []):
                for elem in chart.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])
            for layout in slide.get("layout_elements", []):
                for elem in layout.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])
            for elem in slide.get("excel_elements", []):
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
                    
                    # SmartArts
                    diag_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData']")
                    for rel in diag_rels:
                        target = rel.get("Target")
                        diag_path = (slides_dir / target).resolve()
                        if diag_path.exists():
                            diag_id = diag_path.stem
                            self._inject_in_xml(diag_path, slide_num, f"diag_{diag_id}", translation_map)

                    # Charts
                    chart_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart']")
                    for rel in chart_rels:
                        target = rel.get("Target")
                        chart_path = (slides_dir / target).resolve()
                        if chart_path.exists():
                            chart_id = chart_path.stem
                            self._inject_in_xml(chart_path, slide_num, f"chart_{chart_id}", translation_map)

                    # SlideLayouts (sous-titres / masques)
                    layout_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout']")
                    for rel in layout_rels:
                        target = rel.get("Target")
                        layout_path = (slides_dir / target).resolve()
                        if layout_path.exists():
                            layout_id = layout_path.stem
                            self._inject_in_xml(layout_path, slide_num, f"layout_{layout_id}", translation_map)

            for master in slide.get("master_elements", []):
                for elem in master.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])

                    # Excel incorporés (.xlsx)
                    pkg_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/package']")
                    for rel in pkg_rels:
                        target = rel.get("Target")
                        emb_path = (slides_dir / target).resolve()
                        if emb_path.exists() and emb_path.suffix.lower() in ('.xlsx', '.xlsm'):
                            self._inject_excel_file(emb_path, slide_num, translation_map)

                # SlideMasters (masques racine)
                masters_dir = temp_path / "ppt" / "slideMasters"
                if masters_dir.exists():
                    for master_path in sorted(masters_dir.glob("slideMaster*.xml")):
                        master_id = master_path.stem
                        self._inject_in_xml(master_path, slide_num, f"master_{master_id}", translation_map)

            if progress_callback:
                progress_callback("Re-compression du fichier PPTX...")
            self._repack_zip(output_pptx)
            self._cleanup_temp()

            # Actualisation 100% automatique en arrière-plan des aperçus d'objets OLE sous Windows
            _auto_refresh_powerpoint(output_pptx)

            return True, f"Fichier traduit généré : {output_pptx}"

        except Exception as e:
            self._cleanup_temp()
            return False, f"Erreur lors de la réinjection : {str(e)}"

    def _inject_excel_file(self, emb_path: Path, slide_num: int, translation_map: dict) -> bool:
        """Réinjecte la traduction dans le fichier Excel incorporé (xl/sharedStrings.xml) en mémoire."""
        if not emb_path.exists():
            return False
        try:
            with open(emb_path, "rb") as f:
                excel_bytes = f.read()
            
            in_mem = io.BytesIO(excel_bytes)
            out_mem = io.BytesIO()
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            modified = False

            with zipfile.ZipFile(in_mem, "r") as xin, zipfile.ZipFile(out_mem, "w", zipfile.ZIP_DEFLATED) as xout:
                for item in xin.infolist():
                    content = xin.read(item.filename)
                    if item.filename == "xl/sharedStrings.xml":
                        tree = etree.fromstring(content)
                        t_nodes = tree.xpath(".//s:t", namespaces=ns)
                        for t_idx, t_node in enumerate(t_nodes):
                            elem_id = f"slide{slide_num}_excel_{emb_path.stem}_ss{t_idx}"
                            if elem_id in translation_map:
                                tr_text = translation_map[elem_id]
                                clean_text = re.sub(r"\[\[\d+\]\](.*?)\[\[/\d+\]\]", r"\1", tr_text)
                                t_node.text = clean_text
                                modified = True
                        content = etree.tostring(tree, encoding="utf-8", xml_declaration=True)
                    xout.writestr(item, content)

            if modified:
                with open(emb_path, "wb") as f:
                    f.write(out_mem.getvalue())
            return modified
        except Exception:
            return False

    def _inject_in_xml(self, xml_path, slide_num, id_prefix, translation_map):
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
                
                text_nodes_direct = p_elem.xpath(".//a:t", namespaces=NAMESPACES)
                if text_nodes_direct:
                    clean_text = match_dict.get(0, re.sub(r"\[\[\d+\]\](.*?)\[\[/\d+\]\]", r"\1", translated_text))
                    text_nodes_direct[0].text = clean_text
                    for i in range(1, len(text_nodes_direct)):
                        text_nodes_direct[i].text = ""
                    modified = True

        if "chart" in id_prefix:
            c_nodes = root.xpath(".//c:v | .//c:t", namespaces=NAMESPACES)
            for v_idx, v_node in enumerate(c_nodes):
                elem_id = f"slide{slide_num}_{id_prefix}_cv{v_idx}"
                if elem_id in translation_map:
                    tr_text = translation_map[elem_id]
                    clean_text = re.sub(r"\[\[\d+\]\](.*?)\[\[/\d+\]\]", r"\1", tr_text)
                    v_node.text = clean_text
                    modified = True

        if modified:
            with open(xml_path, "wb") as f:
                f.write(etree.tostring(tree, encoding="utf-8", xml_declaration=True))
        return modified

    # ── Méthodes pour le pipeline PROGRESSIF (slide par slide) ──────────────

    def _slide_path(self, slide_num: int):
        """Chemin du fichier XML de la slide N dans le dossier temporaire."""
        return self._get_temp_dir() / "ppt" / "slides" / f"slide{slide_num}.xml"

    def _rels_path(self, slide_num: int):
        """Chemin du fichier .rels de la slide N."""
        return self._get_temp_dir() / "ppt" / "slides" / "_rels" / f"slide{slide_num}.xml.rels"

    def slide_count(self) -> int:
        """Nombre de slides dans le PPTX déjà décompressé."""
        slides_dir = self._get_temp_dir() / "ppt" / "slides"
        if not slides_dir.exists():
            return 0
        return len(list(slides_dir.glob("slide*.xml")))

    def extract_slide(self, slide_num: int, filters: dict | None = None):
        """Extrait le texte d'une SEULE slide déjà décompressée."""
        if filters is None:
            filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}

        slide_path = self._slide_path(slide_num)
        if not slide_path.exists():
            return None, f"Slide {slide_num} introuvable."

        tree = etree.parse(str(slide_path))
        root = tree.getroot()

        slide_data = {
            "slide_id": slide_num,
            "text_elements": [],
            "diagram_elements": [],
            "chart_elements": [],
            "layout_elements": [],
            "excel_elements": []
        }
        element_types_used = defaultdict(set)

        self._process_xml_element(root, slide_num, slide_data["text_elements"],
                                  element_types_used, "p", filters)

        rels_path = self._rels_path(slide_num)
        if rels_path.exists():
            rels_tree = etree.parse(str(rels_path))
            slides_dir = self._get_temp_dir() / "ppt" / "slides"

            if filters.get("smartarts"):
                diag_rels = rels_tree.xpath(
                    "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData']")
                for rel in diag_rels:
                    target = rel.get("Target")
                    diag_path = (slides_dir / target).resolve()
                    if diag_path.exists():
                        diag_tree = etree.parse(str(diag_path))
                        diag_root = diag_tree.getroot()
                        diag_id = diag_path.stem
                        diag_data = {"diag_id": diag_id, "text_elements": []}
                        self._process_xml_element(diag_root, slide_num, diag_data["text_elements"],
                                                  element_types_used, f"diag_{diag_id}", filters)
                        if diag_data["text_elements"]:
                            slide_data["diagram_elements"].append(diag_data)

            if filters.get("tables"):
                chart_rels = rels_tree.xpath(
                    "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart']")
                for rel in chart_rels:
                    target = rel.get("Target")
                    chart_path = (slides_dir / target).resolve()
                    if chart_path.exists():
                        chart_tree = etree.parse(str(chart_path))
                        chart_root = chart_tree.getroot()
                        chart_id = chart_path.stem
                        chart_data = {"chart_id": chart_id, "text_elements": []}
                        self._process_xml_element(chart_root, slide_num, chart_data["text_elements"],
                                                  element_types_used, f"chart_{chart_id}", filters)
                        if chart_data["text_elements"]:
                            slide_data["chart_elements"].append(chart_data)

            # SlideLayouts
            layout_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout']")
            for rel in layout_rels:
                target = rel.get("Target")
                layout_path = (slides_dir / target).resolve()
                if layout_path.exists():
                    layout_tree = etree.parse(str(layout_path))
                    layout_root = layout_tree.getroot()
                    layout_id = layout_path.stem
                    layout_data = {"layout_id": layout_id, "text_elements": []}
                    self._process_xml_element(layout_root, slide_num, layout_data["text_elements"],
                                              element_types_used, f"layout_{layout_id}", filters)
                    if layout_data["text_elements"]:
                        slide_data["layout_elements"].append(layout_data)

            # Excel incorporés
            if filters.get("tables"):
                pkg_rels = rels_tree.xpath(
                    "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/package']")
                for rel in pkg_rels:
                    target = rel.get("Target")
                    emb_path = (slides_dir / target).resolve()
                    if emb_path.exists() and emb_path.suffix.lower() in ('.xlsx', '.xlsm'):
                        self._process_excel_file(emb_path, slide_num, slide_data["excel_elements"], element_types_used)

        if not any([slide_data["text_elements"], slide_data["diagram_elements"],
                    slide_data["chart_elements"], slide_data["layout_elements"],
                    slide_data["excel_elements"]]):
            return None, "Aucun texte trouvé dans cette slide."
        return slide_data, element_types_used

    def inject_slide(self, slide_num: int, translation_map: dict):
        """Injecte la traduction dans les XML d'une SEULE slide déjà décompressée."""
        slide_path = self._slide_path(slide_num)
        if not slide_path.exists():
            return False
        modified = self._inject_in_xml(slide_path, slide_num, "p", translation_map)

        rels_path = self._rels_path(slide_num)
        if rels_path.exists():
            rels_tree = etree.parse(str(rels_path))
            slides_dir = self._get_temp_dir() / "ppt" / "slides"

            diag_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData']")
            for rel in diag_rels:
                target = rel.get("Target")
                diag_path = (slides_dir / target).resolve()
                if diag_path.exists():
                    diag_id = diag_path.stem
                    if self._inject_in_xml(diag_path, slide_num, f"diag_{diag_id}", translation_map):
                        modified = True
            
            chart_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart']")
            for rel in chart_rels:
                target = rel.get("Target")
                chart_path = (slides_dir / target).resolve()
                if chart_path.exists():
                    chart_id = chart_path.stem
                    if self._inject_in_xml(chart_path, slide_num, f"chart_{chart_id}", translation_map):
                        modified = True

            layout_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout']")
            for rel in layout_rels:
                target = rel.get("Target")
                layout_path = (slides_dir / target).resolve()
                if layout_path.exists():
                    layout_id = layout_path.stem
                    if self._inject_in_xml(layout_path, slide_num, f"layout_{layout_id}", translation_map):
                        modified = True

            pkg_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/package']")
            for rel in pkg_rels:
                target = rel.get("Target")
                emb_path = (slides_dir / target).resolve()
                if emb_path.exists() and emb_path.suffix.lower() in ('.xlsx', '.xlsm'):
                    if self._inject_excel_file(emb_path, slide_num, translation_map):
                        modified = True

        return bool(modified)

    def build_partial_pptx(self, output_path: str, up_to_slide: int):
        """Construit un PPTX partiel contenant les slides 1..up_to_slide depuis le
        dossier temporaire (déjà décompressé et modifié)."""
        temp_path = self._get_temp_dir()

        content_types_path = temp_path / "[Content_Types].xml"
        all_parts: set[str] = set()
        if content_types_path.exists():
            ct_tree = etree.parse(str(content_types_path))
            for ov in ct_tree.xpath("//*[@PartName]"):
                part = ov.get("PartName", "")
                if part.startswith("/"):
                    part = part[1:]
                all_parts.add(part)

        include: set[str] = set()
        for part in all_parts:
            if not part.startswith("ppt/slides/"):
                include.add(part)
        for n in range(1, up_to_slide + 1):
            prefix = f"ppt/slides/slide{n}"
            for part in all_parts:
                if part.startswith(prefix):
                    include.add(part)
        include.add("[Content_Types].xml")

        pres_path = temp_path / "ppt" / "presentation.xml"
        if pres_path.exists():
            pres_tree = etree.parse(str(pres_path))
            sld_id_list = pres_tree.xpath("//p:sldIdLst", namespaces=NAMESPACES)
            if sld_id_list:
                sld_list = sld_id_list[0]
                existing = list(sld_list)
                for el in existing:
                    sld_list.remove(el)
                for n in range(1, up_to_slide + 1):
                    r_id = f"rId{n}"
                    el = etree.SubElement(sld_list, f"{{{NAMESPACES['p']}}}sldId")
                    el.set("id", str(256 + n))
                    el.set(f"{{{NAMESPACES['r']}}}id", r_id)
                with open(pres_path, "wb") as f:
                    f.write(etree.tostring(pres_tree, encoding="utf-8", xml_declaration=True))

        if content_types_path.exists():
            ct_tree = etree.parse(str(content_types_path))
            types_elem = ct_tree.getroot()
            for ov in list(types_elem):
                part_name = ov.get("PartName", "")
                if part_name.startswith("/ppt/slides/slide"):
                    m = re.match(r"/ppt/slides/slide(\d+)", part_name)
                    if m and int(m.group(1)) > up_to_slide:
                        types_elem.remove(ov)
            with open(content_types_path, "wb") as f:
                f.write(etree.tostring(ct_tree, encoding="utf-8", xml_declaration=True))

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for part in sorted(include):
                part_path = temp_path / part
                if part_path.exists():
                    zf.write(part_path, part)
                elif part.endswith(".xml.rels"):
                    rels_file = temp_path / part
                    if rels_file.exists():
                        zf.write(rels_file, part)
