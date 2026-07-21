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


def _find_soffice_engine() -> str | None:
    """Localise l'exécutable LibreOffice (pour régénérer les aperçus OLE).
    Autonome — le moteur ne dépend pas d'`app` (évite un cycle d'import)."""
    import shutil
    candidates = (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "soffice", "libreoffice",
    )
    for c in candidates:
        if os.path.isfile(c):
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


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
                            self._process_excel_file(emb_path, slide_num,
                                                     slide_data["excel_elements"],
                                                     element_types_used)

            # 6. Masques principaux (slideMasters) — hors bloc rels_path
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
            for layout_item in slide.get("layout_elements", []):
                for elem in layout_item.get("text_elements", []):
                    translation_map[elem["id"]] = elem.get("translated_text", elem["text"])
            for master_item in slide.get("master_elements", []):
                for elem in master_item.get("text_elements", []):
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

                    # Excel incorporés (.xlsx) — injecter dans sharedStrings.xml
                    pkg_rels = rels_tree.xpath("//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/package']")
                    for rel in pkg_rels:
                        target = rel.get("Target")
                        emb_path = (slides_dir / target).resolve()
                        if emb_path.exists() and emb_path.suffix.lower() in ('.xlsx', '.xlsm'):
                            self._inject_excel_file(emb_path, slide_num, translation_map)

            # SlideMasters — injecter une fois pour chaque slide (les IDs sont
            # préfixés par slide_num, donc chaque slide a ses propres entrées)
            masters_dir = temp_path / "ppt" / "slideMasters"
            if masters_dir.exists():
                for master_path in sorted(masters_dir.glob("slideMaster*.xml")):
                    master_id = master_path.stem
                    for slide_path in slide_files:
                        slide_num = int(slide_path.stem.replace("slide", ""))
                        self._inject_in_xml(master_path, slide_num, f"master_{master_id}", translation_map)

            # Aperçus des objets OLE Excel : régénérés depuis les classeurs
            # traduits (best-effort — voir regenerate_ole_previews). Sans ça, les
            # tableaux/graphiques Excel restent affichés en langue source tant que
            # PowerPoint n'a pas activé l'objet.
            try:
                self.regenerate_ole_previews(progress_callback=progress_callback)
            except Exception:
                pass

            if progress_callback:
                progress_callback("Re-compression du fichier PPTX...")
            self._repack_zip(output_pptx)
            self._cleanup_temp()

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
        """Construit un PPTX partiel (slides 1..up_to_slide) depuis le dossier
        temporaire, SANS JAMAIS LE MODIFIER.

        Non-destructif À DESSEIN : cette méthode est appelée plusieurs fois
        pendant un même job (aperçu progressif, une fois par slide traitée) puis
        une dernière fois pour le fichier final. L'ancienne version réécrivait
        `presentation.xml`, ses rels et `[Content_Types].xml` DANS le dossier
        temporaire en retirant les slides > up_to_slide : au deuxième appel, les
        slides déjà retirées avaient disparu du temp dir et ne revenaient jamais
        — le PPTX final se serait retrouvé amputé de toutes ses slides sauf la
        première. On calcule donc les fichiers de contrôle trimmés EN MÉMOIRE et
        on les écrit directement dans le zip ; le temp dir reste intact pour la
        suite du traitement (et pour les appels suivants).

        Parcourt TOUS les fichiers réels du dossier temporaire (pas seulement
        ceux listés dans [Content_Types].xml : les .rels et certains médias n'y
        figurent pas). Écriture ATOMIQUE (tmp + rename) : un lecteur (conversion
        d'aperçu) ne voit jamais un zip à moitié écrit."""
        temp_path = self._get_temp_dir()

        # Parcourir TOUS les fichiers réels du dossier temporaire
        all_files: list[str] = []
        for root, _dirs, files in os.walk(temp_path):
            for fn in files:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, temp_path).replace("\\", "/")
                all_files.append(rel)
        all_set = set(all_files)

        # Déterminer les fichiers à EXCLURE (slides au-delà de up_to_slide)
        exclude_prefixes: set[str] = set()
        for n in range(up_to_slide + 1, 1000):
            if f"ppt/slides/slide{n}.xml" in all_set:
                exclude_prefixes.add(f"ppt/slides/slide{n}")
            else:
                break  # plus de slides au-delà

        def _excluded(rel: str) -> bool:
            return any(rel.startswith(p) for p in exclude_prefixes)

        include = [rel for rel in all_files if not _excluded(rel)]

        # ── Fichiers de CONTRÔLE recalculés EN MÉMOIRE (jamais réécrits sur disque) ──
        control_bytes: dict[str, bytes] = {}

        # 1. ppt/_rels/presentation.xml.rels — retirer les relations des slides exclues
        rels_rel = "ppt/_rels/presentation.xml.rels"
        rels_path = temp_path / "ppt" / "_rels" / "presentation.xml.rels"
        r_id_to_slide_num: dict[str, int] = {}
        if rels_path.exists():
            rels_tree = etree.parse(str(rels_path))
            rels_root = rels_tree.getroot()
            slide_rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
            for rel in list(rels_root):
                if rel.get("Type") == slide_rel_type:
                    m = re.search(r"slide(\d+)\.xml", rel.get("Target", ""))
                    if m:
                        slide_num = int(m.group(1))
                        if slide_num > up_to_slide:
                            rels_root.remove(rel)
                        else:
                            r_id_to_slide_num[rel.get("Id")] = slide_num
            control_bytes[rels_rel] = etree.tostring(
                rels_tree, encoding="utf-8", xml_declaration=True)

        # 2. ppt/presentation.xml — ne garder dans sldIdLst que les slides conservées
        pres_rel = "ppt/presentation.xml"
        pres_path = temp_path / "ppt" / "presentation.xml"
        if pres_path.exists():
            pres_tree = etree.parse(str(pres_path))
            sld_id_list = pres_tree.xpath("//p:sldIdLst", namespaces=NAMESPACES)
            if sld_id_list:
                sld_list = sld_id_list[0]
                for el in list(sld_list):
                    r_id = el.get(f"{{{NAMESPACES['r']}}}id")
                    if r_id not in r_id_to_slide_num:
                        sld_list.remove(el)
            control_bytes[pres_rel] = etree.tostring(
                pres_tree, encoding="utf-8", xml_declaration=True)

        # 3. [Content_Types].xml — retirer les Override des slides exclues
        ct_rel = "[Content_Types].xml"
        content_types_path = temp_path / "[Content_Types].xml"
        if content_types_path.exists():
            ct_tree = etree.parse(str(content_types_path))
            types_elem = ct_tree.getroot()
            for ov in list(types_elem):
                part_name = ov.get("PartName", "")
                if part_name.startswith("/ppt/slides/slide"):
                    m = re.match(r"/ppt/slides/slide(\d+)", part_name)
                    if m and int(m.group(1)) > up_to_slide:
                        types_elem.remove(ov)
            control_bytes[ct_rel] = etree.tostring(
                ct_tree, encoding="utf-8", xml_declaration=True)

        # ── Reconstruire le ZIP (atomique) : contrôle depuis la mémoire, le reste du disque ──
        tmp_out = output_path + ".tmp"
        with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(include):
                if rel in control_bytes:
                    zf.writestr(rel, control_bytes[rel])
                    continue
                part_path = temp_path / rel
                if part_path.exists():
                    zf.write(part_path, rel)
        os.replace(tmp_out, output_path)

    # ── Aperçus des objets OLE Excel ─────────────────────────────────────────
    #
    # PROBLÈME : un classeur Excel incorporé dans un PPTX est affiché via une
    # IMAGE de remplacement (.emf) générée par Office à la création. Cette image
    # n'est JAMAIS régénérée par une modification XML : on traduit bien les
    # cellules du xlsx incorporé, mais l'aperçu visuel reste en langue d'origine
    # tant que PowerPoint n'active pas l'objet. Mesuré : le xlsx dit « Theoretical
    # test during training », l'EMF montre encore « Test théorique durant
    # formation ». LibreOffice, à l'affichage comme à l'export PDF, rend cette
    # même EMF périmée — donc l'aperçu de l'app est touché autant que PowerPoint.
    #
    # SOLUTION (sans licence Windows, sans macro) : on rend le classeur TRADUIT
    # en image avec LibreOffice, on recadre au contenu, et on remplace le média
    # de remplacement. Un seul correctif rend l'aperçu ET le fichier téléchargé
    # cohérents. L'ancienne piste COM/VBA (`_auto_refresh_powerpoint`,
    # `generate_autorefresh_pptm`) est abandonnée : elle exigeait PowerPoint et
    # déclenchait l'avertissement de sécurité macro.

    def regenerate_ole_previews(self, soffice_path: str | None = None,
                                progress_callback=None) -> int:
        """Régénère l'image de remplacement de chaque objet OLE Excel depuis le
        classeur TRADUIT (déjà réinjecté dans le dossier temporaire). À appeler
        APRÈS l'injection, AVANT le repack. Retourne le nombre d'aperçus refaits.

        Best-effort : en cas d'échec (LibreOffice absent, classeur illisible),
        on laisse l'EMF d'origine plutôt que d'interrompre la traduction."""
        if soffice_path is None:
            soffice_path = _find_soffice_engine()
        if not soffice_path:
            return 0
        temp_path = self._get_temp_dir()
        slides_dir = temp_path / "ppt" / "slides"
        if not slides_dir.exists():
            return 0

        R = NAMESPACES['r']
        # 1. Collecte : pour chaque graphicFrame OLE Excel, le couple
        #    (classeur incorporé, image de remplacement) via le XML + les rels.
        tasks = []
        rels_cache = {}
        for slide_path in sorted(slides_dir.glob("slide*.xml")):
            rels_path = slides_dir / "_rels" / (slide_path.name + ".rels")
            if not rels_path.exists():
                continue
            try:
                rels_tree = etree.parse(str(rels_path))
                slide_tree = etree.parse(str(slide_path))
            except Exception:
                continue
            rid_to_target = {r.get("Id"): r.get("Target")
                             for r in rels_tree.getroot()}
            found = False
            for gf in slide_tree.iter("{%s}graphicFrame" % NAMESPACES['p']):
                ole = gf.find(".//p:oleObj", NAMESPACES)
                if ole is None or "Excel" not in (ole.get("progId") or ""):
                    continue
                blip = gf.find(".//a:blip", NAMESPACES)
                if blip is None:
                    continue
                xlsx_rel = rid_to_target.get(ole.get("{%s}id" % R))
                img_rid = blip.get("{%s}embed" % R)
                img_rel = rid_to_target.get(img_rid)
                if not xlsx_rel or not img_rel:
                    continue
                xlsx_path = (slides_dir / xlsx_rel).resolve()
                if (not xlsx_path.exists()
                        or xlsx_path.suffix.lower() not in (".xlsx", ".xlsm")):
                    continue
                tasks.append({"xlsx": xlsx_path, "img_rel": img_rel,
                              "img_rid": img_rid, "rels_path": str(rels_path)})
                found = True
            if found:
                rels_cache[str(rels_path)] = rels_tree
        if not tasks:
            return 0

        # 2. Rendu de TOUS les classeurs uniques en une SEULE invocation
        #    LibreOffice (le coût de démarrage est amorti sur tous les fichiers).
        import subprocess
        uniq = sorted({str(t["xlsx"]) for t in tasks})
        png_for = {}
        with tempfile.TemporaryDirectory() as td:
            prof = "file:///" + os.path.join(td, "prof").replace(os.sep, "/")
            cmd = [soffice_path, "--headless", "--norestore", "--nolockcheck",
                   f"-env:UserInstallation={prof}",
                   "--convert-to", "pdf", "--outdir", td] + uniq
            try:
                subprocess.run(cmd, capture_output=True, timeout=600)
            except Exception:
                return 0
            for x in uniq:
                pdf = os.path.join(td, Path(x).stem + ".pdf")
                if os.path.exists(pdf):
                    png_for[x] = self._crop_xlsx_pdf_to_png(pdf)

        # 3. Écrire les PNG et construire la carte {image_emf → image_png}.
        media_dir = slides_dir.parent / "media"
        media_dir.mkdir(exist_ok=True)
        emf_to_png = {}
        for t in tasks:
            png = png_for.get(str(t["xlsx"]))
            if not png:
                continue
            emf_name = t["img_rel"].rsplit("/", 1)[-1]        # image37.emf
            png_name = Path(emf_name).stem + ".png"           # image37.png
            with open(media_dir / png_name, "wb") as f:
                f.write(png)
            emf_to_png[emf_name] = png_name
        if not emf_to_png:
            return 0

        # 4. Repointer TOUTES les relations qui référencent ces EMF vers le PNG.
        #    CRUCIAL : un objet OLE est affiché via la branche `mc:Choice` (VML),
        #    dont l'image est référencée par les rels du `vmlDrawing`, PAS par le
        #    blip DrawingML du `mc:Fallback`. Ne repointer que le fallback (ce
        #    qu'on faisait) laissait PowerPoint ET LibreOffice afficher l'EMF
        #    d'origine, en langue source. On balaie donc TOUS les .rels du
        #    paquet et on repointe par nom de fichier — les deux branches suivent.
        IMG_TYPE = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                    "relationships/image")
        for rels_file in temp_path.rglob("*.rels"):
            try:
                tree = etree.parse(str(rels_file))
            except Exception:
                continue
            changed = False
            for rel in tree.getroot():
                tgt = rel.get("Target") or ""
                base = tgt.rsplit("/", 1)[-1]
                if base in emf_to_png:
                    rel.set("Target", tgt[:len(tgt) - len(base)] + emf_to_png[base])
                    rel.set("Type", IMG_TYPE)
                    changed = True
            if changed:
                tree.write(str(rels_file), xml_declaration=True, encoding="UTF-8")

        # 5. Supprimer les EMF devenus orphelins (plus aucune relation n'y
        #    pointe) : une part non référencée fait afficher à PowerPoint un
        #    avertissement de réparation.
        for emf_name in emf_to_png:
            old = media_dir / emf_name
            try:
                if old.exists():
                    old.unlink()
            except OSError:
                pass

        self._ensure_png_content_type(temp_path)
        if progress_callback:
            progress_callback(f"{len(emf_to_png)} aperçu(s) Excel régénéré(s)")
        return len(emf_to_png)

    def _crop_xlsx_pdf_to_png(self, pdf_path: str, dpi: int = 150,
                              margin: int = 8) -> bytes | None:
        """Rend la 1re page d'un PDF de classeur et la recadre à la boîte
        englobante du contenu (LibreOffice pose le contenu dans un coin d'une
        page A4 : sans recadrage, l'aperçu serait 90 % de blanc)."""
        try:
            import fitz
            import numpy as np
            from PIL import Image
            doc = fitz.open(pdf_path)
            if doc.page_count == 0:
                doc.close()
                return None
            pix = doc[0].get_pixmap(dpi=dpi, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            arr = np.asarray(im.convert("L"))
            mask = arr < 245
            if not mask.any():
                return None
            ys, xs = np.where(mask)
            x0 = max(0, int(xs.min()) - margin)
            y0 = max(0, int(ys.min()) - margin)
            x1 = min(im.width, int(xs.max()) + margin + 1)
            y1 = min(im.height, int(ys.max()) + margin + 1)
            buf = io.BytesIO()
            im.crop((x0, y0, x1, y1)).save(buf, "PNG")
            return buf.getvalue()
        except Exception:
            return None

    def _ensure_png_content_type(self, temp_path: Path) -> None:
        """Garantit que [Content_Types].xml déclare le type PNG (le média de
        remplacement passe de .emf à .png)."""
        ct_path = temp_path / "[Content_Types].xml"
        if not ct_path.exists():
            return
        CT = "http://schemas.openxmlformats.org/package/2006/content-types"
        try:
            tree = etree.parse(str(ct_path))
            root = tree.getroot()
            for d in root.findall("{%s}Default" % CT):
                if (d.get("Extension") or "").lower() == "png":
                    return
            el = etree.SubElement(root, "{%s}Default" % CT)
            el.set("Extension", "png")
            el.set("ContentType", "image/png")
            tree.write(str(ct_path), xml_declaration=True, encoding="UTF-8")
        except Exception:
            pass
