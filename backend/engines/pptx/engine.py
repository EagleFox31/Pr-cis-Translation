import os
import zipfile
import json
import shutil
import tempfile
import re
from lxml import etree
from pathlib import Path
from collections import defaultdict

from engines import runtags        # contrat des balises de runs (et sa réparation)
from engines import incorpores     # objets incorporés (Excel, Word, PowerPoint)

NAMESPACES = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    's': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
}

_SLIDE_REL_TYPE = ("http://schemas.openxmlformats.org/officeDocument/"
                   "2006/relationships/slide")


def _ordre_diapositives(temp_path) -> list[int]:
    """Numéros de FICHIER des diapositives, dans l'ordre d'AFFICHAGE.

    La diapositive n°1 n'est pas forcément `slide1.xml` : un export Google
    Slides nomme `slide1000.xml`, `slide1001.xml`…, et réordonner dans
    PowerPoint ne renomme rien. Le seul ordre qui fait foi est `sldIdLst` de
    `presentation.xml` (rId → Target dans ses rels). Toute méthode « par
    diapositive » reçoit donc une POSITION (1..N) et passe par ici.

    Repli sur le tri numérique des fichiers si ces deux parties manquent ou
    sont illisibles ; une diapositive absente de `sldIdLst` n'est pas affichée
    par PowerPoint et n'est pas comptée."""
    temp_path = Path(temp_path)
    slides_dir = temp_path / "ppt" / "slides"
    presentes: set[int] = set()
    if slides_dir.exists():
        for p in slides_dir.glob("slide*.xml"):
            m = re.fullmatch(r"slide(\d+)\.xml", p.name)
            if m:
                presentes.add(int(m.group(1)))

    ordre: list[int] = []
    rels_path = temp_path / "ppt" / "_rels" / "presentation.xml.rels"
    pres_path = temp_path / "ppt" / "presentation.xml"
    if rels_path.exists() and pres_path.exists():
        try:
            rid_to_num: dict[str, int] = {}
            for rel in etree.parse(str(rels_path)).getroot():
                if rel.get("Type") == _SLIDE_REL_TYPE:
                    m = re.search(r"slide(\d+)\.xml$", rel.get("Target", ""))
                    if m:
                        rid_to_num[rel.get("Id")] = int(m.group(1))
            for el in etree.parse(str(pres_path)).getroot().xpath(
                    "//p:sldIdLst/p:sldId", namespaces=NAMESPACES):
                num = rid_to_num.get(el.get(f"{{{NAMESPACES['r']}}}id"))
                if num in presentes and num not in ordre:
                    ordre.append(num)
        except etree.XMLSyntaxError:
            ordre = []
    return ordre or sorted(presentes)


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
    """Moteur PPTX — UNE INSTANCE PAR OPÉRATION, JAMAIS PARTAGÉE.

    Tout l'état du moteur tient dans `self.temp_dir` : le PPTX y est décompressé,
    les XML y sont injectés sur place, et `_cleanup_temp()` l'efface. Cet état
    n'est PAS protégé — il ne peut pas l'être, puisque deux traductions
    différentes du même original y écriraient de toute façon dans les mêmes
    fichiers.

    Une instance unique partagée par le processus (ce qu'était `app.pptx_engine`)
    faisait donc collisionner tout ce qui tourne en même temps :

      • deux aperçus concurrents — cas COURANT, l'aperçu lançait lui-même une
        construction de cache en tâche de fond en plus de son propre rendu —
        partageaient le dossier : l'aperçu portugais injectait le portugais dans
        les XML que l'aperçu anglais était en train de re-zipper. On demandait
        l'anglais, on recevait le portugais. Intermittent, donc invisible en
        test manuel et bien réel en usage.
      • pire : le `_cleanup_temp()` d'un aperçu supprimait le dossier temporaire
        d'un JOB de traduction en cours.

    D'où la règle : `new_pptx_engine()` au début de chaque opération, et cette
    instance meurt avec elle.
    """

    # Numéro de « diapositive » des parties PARTAGÉES (slideLayout, slideMaster).
    #
    # Un layout est référencé par plusieurs diapositives, mais c'est UN SEUL
    # fichier. En faisant entrer le numéro de diapositive dans l'identité de ses
    # paragraphes, on en fabriquait autant de copies qu'il y avait de
    # diapositives : traduites une fois chacune (autant d'appels payés), puis
    # injectées tour à tour dans le même fichier — la dernière écrasait les
    # autres. Et en mode progressif, la diapositive 7 extrayait un layout DÉJÀ
    # injecté par la 2 : on traduisait une traduction, avec la dérive que ça
    # suppose.
    #
    # Une partie partagée n'appartient à aucune diapositive : elle porte donc ce
    # numéro fixe, et n'est extraite qu'une fois par document.
    PART_PARTAGEE = 0

    def __init__(self):
        self.temp_dir = None
        # Parties partagées déjà extraites pour CE document (chemins de
        # fichiers). Remis à zéro avec le dossier temporaire.
        self._parts_vues: set[str] = set()
        # PPTX d'origine du dossier temporaire : les objets incorporés se
        # relèvent et se réinjectent depuis lui (chemin progressif, diapo à diapo).
        self._source: str | None = None

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
        self._parts_vues.clear()

    def _extract_zip(self, pptx_path):
        """Décompresse le PPTX (archive ZIP) dans le dossier temporaire."""
        temp_path = self._get_temp_dir()
        with zipfile.ZipFile(pptx_path, 'r') as zf:
            zf.extractall(temp_path)
        self._source = str(pptx_path)
        # Nouveau document : les parties partagées sont à revoir.
        self._parts_vues.clear()

    def _part_deja_vue(self, chemin) -> bool:
        """Cette partie PARTAGÉE a-t-elle déjà été extraite ? (et la marque)"""
        cle = str(chemin)
        if cle in self._parts_vues:
            return True
        self._parts_vues.add(cle)
        return False

    def _repack_zip(self, output_path):
        """Re-compresse le dossier temporaire en un fichier PPTX valide."""
        temp_path = self._get_temp_dir()
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(temp_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_path)
                    zf.write(file_path, arcname)

    def extract_text(self, pptx_path, output_json="extraction_texte.json", filters=None, progress_callback=None, pages=None, niveau_objets=1):
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

        # Ordre d'AFFICHAGE ; `slide_num` = position (cf. _ordre_diapositives).
        slide_files = [slides_dir / f"slide{n}.xml" for n in _ordre_diapositives(temp_path)]

        extraction = {"slides": []}
        element_types_used = defaultdict(set)
        total_slides = len(slide_files)

        # Objets incorporés : relevés UNE fois pour tout le document, puis rangés
        # dans `excel_elements` de la diapositive qui les affiche. Ceux d'un
        # masque, d'une disposition ou d'une page de notes vont à la première
        # diapositive relevée.
        objets_par_diapo: dict[int, list] = {}
        if filters.get("tables"):
            retenues = {int(p.stem.replace("slide", ""))
                        for i, p in enumerate(slide_files)
                        if pages is None or (i + 1) in pages}
            if retenues:
                elements_objets, rapport_objets = incorpores.relever(
                    pptx_path, base=self._base_objets(retenues), niveau=niveau_objets)
                extraction["objets_rapport"] = rapport_objets
                for el in elements_objets:
                    m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml",
                                     el["context"].get("partie", ""))
                    num = int(m.group(1)) if m else min(retenues)
                    objets_par_diapo.setdefault(num, []).append(el)
                    element_types_used[num].add(el["context"]["shape_type"])

        for i, slide_path in enumerate(slide_files):
            slide_num = i + 1
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
                "excel_elements": objets_par_diapo.get(slide_num, [])
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
                    # UNE SEULE FOIS par document : un layout partagé par dix
                    # diapositives était sinon extrait et traduit dix fois.
                    if layout_path.exists() and not self._part_deja_vue(layout_path):
                        layout_tree = etree.parse(str(layout_path))
                        layout_root = layout_tree.getroot()
                        layout_id = layout_path.stem
                        layout_data = {"layout_id": layout_id, "text_elements": []}
                        self._process_xml_element(layout_root, self.PART_PARTAGEE, layout_data["text_elements"], element_types_used, f"layout_{layout_id}", filters)
                        if layout_data["text_elements"]:
                            slide_data["layout_elements"].append(layout_data)

            # (5. Objets incorporés : relevés plus haut, pour tout le document.)

            # 6. Masques principaux (slideMasters) — hors bloc rels_path
            masters_dir = temp_path / "ppt" / "slideMasters"
            if masters_dir.exists():
                for master_path in sorted(masters_dir.glob("slideMaster*.xml")):
                    # Partagé par TOUTES les diapositives : même règle.
                    if self._part_deja_vue(master_path):
                        continue
                    master_tree = etree.parse(str(master_path))
                    master_root = master_tree.getroot()
                    master_id = master_path.stem
                    master_data = {"master_id": master_id, "text_elements": []}
                    self._process_xml_element(master_root, self.PART_PARTAGEE, master_data["text_elements"], element_types_used, f"master_{master_id}", filters)
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

    # Objets incorporés (Excel, Word, PowerPoint, jusqu'à PROFONDEUR_MAX niveaux) :
    # relevés et réinjectés par le moteur de leur format, via `incorpores`. Les
    # ids sont préfixés par la diapositive (ou la partie) et le nom du fichier.
    @staticmethod
    def _base_objets(retenues):
        """Préfixe des ids d'un objet : `slide<N>_` pour une diapositive de
        `retenues` (None pour les autres, ignorées), `<partie>_` pour un masque,
        une disposition ou une page de notes."""
        def base(objet):
            m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", objet.partie)
            if m:
                n = int(m.group(1))
                return f"slide{n}_" if n in retenues else None
            return f"{Path(objet.partie).stem}_"
        return base

    @staticmethod
    def _base_diapo(slide_num: int):
        """Chemin progressif : seuls les objets affichés par CETTE diapositive."""
        partie = f"ppt/slides/slide{slide_num}.xml"
        return lambda objet: f"slide{slide_num}_" if objet.partie == partie else None

    def _a_des_objets(self, slide_num: int) -> bool:
        """La diapositive pointe-t-elle vers ppt/embeddings ou vers un graphique
        (son classeur caché, 6.11.5) ? Test bon marché qui évite de reparcourir
        tout le paquet pour chaque diapositive sans objet."""
        rels = Path(self._get_temp_dir()) / "ppt" / "slides" / "_rels" / f"slide{slide_num}.xml.rels"
        try:
            contenu = rels.read_bytes()
            return b"embeddings/" in contenu or b"charts/" in contenu
        except OSError:
            return False

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

            # Extraction par run <a:r> pour préserver la mise en forme (gras,
            # italique, taille…). Les sauts de ligne <a:br/> sont des siblings
            # des runs et restent intacts dans le XML.
            runs = p_elem.xpath("a:r", namespaces=NAMESPACES)
            tagged_parts = []
            valid_idx = 0

            for r_elem in runs:
                t_elems = r_elem.xpath("a:t", namespaces=NAMESPACES)
                r_text = "".join(t.text for t in t_elems if t.text)
                if r_text.strip():
                    tagged_parts.append(f"[[{valid_idx}]]{r_text}[[/{valid_idx}]]")
                    valid_idx += 1

            # Fallback : paragraphes sans <a:r> mais avec des <a:t> directs
            if not tagged_parts:
                text_nodes = p_elem.xpath(".//a:t", namespaces=NAMESPACES)
                full_text = "".join(t.text for t in text_nodes if t.text)
                if full_text.strip() and not _is_numeric(full_text):
                    tagged_parts.append(f"[[0]]{full_text}[[/0]]")

            if not tagged_parts:
                continue

            # Vérification numérique sur le texte combiné
            combined = re.sub(r"\[\[/?\d+\]\]", "", "".join(tagged_parts))
            if _is_numeric(combined):
                continue

            elem_id = f"slide{slide_num}_{id_prefix}_p{p_idx}"
            data_store.append({
                "id": elem_id,
                "text": "".join(tagged_parts),
                "context": {"shape_type": shape_type, "paragraph_index": p_idx, "run_count": valid_idx}
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

    def inject_translation(self, original_pptx, translated_json_path, output_pptx, progress_callback=None, format_options=None, niveau_objets=1):
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
            # Même numérotation que l'extraction : la POSITION d'affichage.
            slide_files = [slides_dir / f"slide{n}.xml" for n in _ordre_diapositives(temp_path)]
            total_slides = len(slide_files)

            for slide_num, slide_path in enumerate(slide_files, start=1):
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
                            # Identité PARTAGÉE ; `num_alt` retrouve les
                            # traductions produites avant ce changement.
                            self._inject_in_xml(layout_path, self.PART_PARTAGEE,
                                                f"layout_{layout_id}",
                                                translation_map,
                                                num_alt=(slide_num,))

            # SlideMasters — UNE injection par masque, pas une par diapositive.
            # La boucle imbriquée réécrivait le même fichier autant de fois
            # qu'il y avait de diapositives, chaque passe écrasant la
            # précédente : seule la dernière comptait, les autres n'étaient que
            # du travail perdu (et des traductions payées pour rien).
            masters_dir = temp_path / "ppt" / "slideMasters"
            if masters_dir.exists():
                nums_anciens = tuple(
                    int(p.stem.replace("slide", "")) for p in slide_files)
                for master_path in sorted(masters_dir.glob("slideMaster*.xml")):
                    master_id = master_path.stem
                    self._inject_in_xml(master_path, self.PART_PARTAGEE,
                                        f"master_{master_id}", translation_map,
                                        num_alt=nums_anciens)

            # Objets incorporés : traduits par le moteur de leur format, puis remis
            # dans le dossier avec leur aperçu redessiné (`engines/apercus.py`).
            # Au mieux : un objet en échec reste tel quel.
            try:
                retenues = {sl.get("slide_id") for sl in translation_data.get("slides", [])}
                incorpores.appliquer_dossier(temp_path, incorpores.reinjecter(
                    original_pptx, translation_map, self._base_objets(retenues),
                    niveau=niveau_objets))
            except Exception as exc:  # noqa: BLE001
                incorpores.logger.warning("Objets PPTX non réinjectés : %s", exc)

            if progress_callback:
                progress_callback("Re-compression du fichier PPTX...")
            self._repack_zip(output_pptx)
            self._cleanup_temp()

            return True, f"Fichier traduit généré : {output_pptx}"

        except Exception as e:
            self._cleanup_temp()
            return False, f"Erreur lors de la réinjection : {str(e)}"

    def _inject_in_xml(self, xml_path, slide_num, id_prefix, translation_map,
                       num_alt=()):
        """`num_alt` : autres numéros sous lesquels chercher le paragraphe.

        Sert aux parties PARTAGÉES, dont l'identité ne porte plus le numéro de
        diapositive. Les traductions produites avant ce changement les nomment
        encore `slide{N}_layout_…` : sans ce repli, elles ne seraient plus
        retrouvées et le layout resterait en langue source.
        """
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        modified = False

        paragraphs = root.xpath(".//a:p", namespaces=NAMESPACES)
        for p_idx, p_elem in enumerate(paragraphs):
            elem_id = f"slide{slide_num}_{id_prefix}_p{p_idx}"
            if elem_id not in translation_map:
                for n in num_alt:
                    candidat = f"slide{n}_{id_prefix}_p{p_idx}"
                    if candidat in translation_map:
                        elem_id = candidat
                        break
            if elem_id in translation_map:
                translated_text = translation_map[elem_id]

                # Réinjection par run <a:r> — même parcours que l'extraction
                runs = p_elem.xpath("a:r", namespaces=NAMESPACES)
                if runs:
                    # On relève d'abord les runs PORTEURS et leur texte source,
                    # dans l'ordre : c'est le contrat que la traduction doit
                    # honorer, et `runtags` le fait honorer coûte que coûte.
                    porteurs = []          # [(r_elem, t_elems, texte_source)]
                    for r_elem in runs:
                        t_elems = r_elem.xpath("a:t", namespaces=NAMESPACES)
                        r_text = "".join(t.text for t in t_elems if t.text)
                        if r_text.strip():
                            porteurs.append((r_elem, t_elems, r_text))

                    # Le code précédent ne remplaçait QUE les runs présents dans
                    # la réponse. Un run oublié par le modèle gardait donc son
                    # texte SOURCE, et la diapositive affichait la traduction
                    # collée à l'original (« DAY 2 OF TRAINING° JOUR DE
                    # FORMATION »). `repartir` rend toujours un texte PAR RUN.
                    textes = runtags.repartir([p[2] for p in porteurs],
                                              translated_text)
                    for (_r, t_elems, _src), nouveau in zip(porteurs, textes):
                        if t_elems:
                            t_elems[0].text = nouveau
                            for extra_t in t_elems[1:]:
                                extra_t.text = ""
                    modified = True
                else:
                    # Fallback : pas de runs, injection directe dans les <a:t>
                    text_nodes_direct = p_elem.xpath(".//a:t", namespaces=NAMESPACES)
                    if text_nodes_direct:
                        clean_text = runtags.sans_balises(translated_text)
                        text_nodes_direct[0].text = clean_text
                        for i in range(1, len(text_nodes_direct)):
                            text_nodes_direct[i].text = ""
                        modified = True

        if "chart" in id_prefix:
            c_nodes = root.xpath(".//c:v | .//c:t", namespaces=NAMESPACES)
            for v_idx, v_node in enumerate(c_nodes):
                elem_id = f"slide{slide_num}_{id_prefix}_cv{v_idx}"
                if elem_id in translation_map:
                    # `sans_balises` retire AUSSI les balises orphelines : une
                    # ouverture sans fermeture traversait l'ancienne regex et
                    # s'affichait telle quelle dans le graphique.
                    v_node.text = runtags.sans_balises(translation_map[elem_id])
                    modified = True

        if modified:
            with open(xml_path, "wb") as f:
                f.write(etree.tostring(tree, encoding="utf-8", xml_declaration=True))
        return modified

    # ── Méthodes pour le pipeline PROGRESSIF (slide par slide) ──────────────

    def _fichier_diapo(self, slide_num: int) -> int | None:
        """Numéro de FICHIER (`slideNNN.xml`) de la diapositive en position N."""
        ordre = _ordre_diapositives(self._get_temp_dir())
        return ordre[slide_num - 1] if 1 <= slide_num <= len(ordre) else None

    def _slide_path(self, slide_num: int):
        """Chemin du fichier XML de la diapositive en position N (None si absente)."""
        num = self._fichier_diapo(slide_num)
        if num is None:
            return None
        return self._get_temp_dir() / "ppt" / "slides" / f"slide{num}.xml"

    def _rels_path(self, slide_num: int):
        """Chemin du fichier .rels de la diapositive en position N (None si absente)."""
        num = self._fichier_diapo(slide_num)
        if num is None:
            return None
        return self._get_temp_dir() / "ppt" / "slides" / "_rels" / f"slide{num}.xml.rels"

    def slide_count(self) -> int:
        """Nombre de diapositives affichées du PPTX déjà décompressé."""
        return len(_ordre_diapositives(self._get_temp_dir()))

    def extract_slide(self, slide_num: int, filters: dict | None = None):
        """Extrait le texte d'une SEULE diapositive (position N) déjà décompressée.

        Une diapositive introuvable LÈVE : la confondre avec « rien à traduire »
        a déclaré terminé un deck dont aucune diapositive n'avait été lue."""
        if filters is None:
            filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}

        slide_path = self._slide_path(slide_num)
        if slide_path is None or not slide_path.exists():
            raise ValueError(f"Diapositive {slide_num} introuvable.")

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

            # SlideLayouts — extraits UNE FOIS par document.
            #
            # En progressif, c'était le pire des cas : la diapositive 2
            # extrayait le layout, le traduisait, l'injectait ; la 7 relisait ce
            # MÊME fichier, désormais traduit, et le renvoyait à la traduction.
            # On traduisait une traduction, et la dernière diapositive écrasait
            # le travail de toutes les autres.
            layout_rels = rels_tree.xpath(
                "//*[@Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout']")
            for rel in layout_rels:
                target = rel.get("Target")
                layout_path = (slides_dir / target).resolve()
                if layout_path.exists() and not self._part_deja_vue(layout_path):
                    layout_tree = etree.parse(str(layout_path))
                    layout_root = layout_tree.getroot()
                    layout_id = layout_path.stem
                    layout_data = {"layout_id": layout_id, "text_elements": []}
                    self._process_xml_element(layout_root, self.PART_PARTAGEE, layout_data["text_elements"],
                                              element_types_used, f"layout_{layout_id}", filters)
                    if layout_data["text_elements"]:
                        slide_data["layout_elements"].append(layout_data)
                # Masque du layout : même règle (une fois par document). Ses
                # formes hors espace réservé s'affichent sur la diapositive.
                master_path = self._master_du_layout(layout_path)
                if master_path is not None and not self._part_deja_vue(master_path):
                    master_data = {"master_id": master_path.stem, "text_elements": []}
                    self._process_xml_element(etree.parse(str(master_path)).getroot(),
                                              self.PART_PARTAGEE, master_data["text_elements"],
                                              element_types_used, f"master_{master_path.stem}", filters)
                    if master_data["text_elements"]:
                        slide_data.setdefault("master_elements", []).append(master_data)

        # Objets incorporés affichés par cette diapositive.
        if filters.get("tables") and self._source and self._a_des_objets(slide_num):
            elements_objets, _ = incorpores.relever(
                self._source, base=self._base_diapo(slide_num))
            for el in elements_objets:
                slide_data["excel_elements"].append(el)
                element_types_used[slide_num].add(el["context"]["shape_type"])

        if not any([slide_data["text_elements"], slide_data["diagram_elements"],
                    slide_data["chart_elements"], slide_data["layout_elements"],
                    slide_data.get("master_elements"), slide_data["excel_elements"]]):
            return None, "Aucun texte trouvé dans cette slide."
        return slide_data, element_types_used

    @staticmethod
    def _master_du_layout(layout_path: Path):
        """Le slideMaster d'un layout (via ses relations), ou None."""
        rels = layout_path.parent / "_rels" / (layout_path.name + ".rels")
        if not rels.exists():
            return None
        for rel in etree.parse(str(rels)).getroot():
            if (rel.get("Type") or "").endswith("/slideMaster"):
                chemin = (layout_path.parent / rel.get("Target")).resolve()
                return chemin if chemin.exists() else None
        return None

    def inject_slide(self, slide_num: int, translation_map: dict):
        """Injecte la traduction dans les XML d'une SEULE slide déjà décompressée."""
        slide_path = self._slide_path(slide_num)
        if slide_path is None or not slide_path.exists():
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
                    if self._inject_in_xml(layout_path, self.PART_PARTAGEE,
                                           f"layout_{layout_id}",
                                           translation_map,
                                           num_alt=(slide_num,)):
                        modified = True
                master_path = self._master_du_layout(layout_path)
                if master_path is not None and self._inject_in_xml(
                        master_path, self.PART_PARTAGEE,
                        f"master_{master_path.stem}", translation_map):
                    modified = True

        # Objets incorporés affichés par cette diapositive.
        if self._source and translation_map and self._a_des_objets(slide_num):
            try:
                modifs = incorpores.reinjecter(self._source, translation_map,
                                               self._base_diapo(slide_num))
                incorpores.appliquer_dossier(self._get_temp_dir(), modifs)
                if modifs.cibles:
                    modified = True
            except Exception as exc:  # noqa: BLE001
                incorpores.logger.warning("Objets diapo %s non réinjectés : %s", slide_num, exc)

        return bool(modified)

    def build_partial_pptx(self, output_path: str, up_to_slide: int,
                           only_slides: set[int] | None = None):
        """Construit un PPTX partiel depuis le dossier temporaire, SANS JAMAIS
        LE MODIFIER.

        `only_slides` : les seules slides à garder (positions 1..N). Par
        défaut, toutes celles jusqu'à la position `up_to_slide`. Sert à extraire UNE slide isolée pour la convertir
        seule en PDF — l'aperçu progressif ne peut pas se permettre de reconvertir
        tout le deck à chaque diapositive terminée (cf. app.py).

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

        # Numéros de TOUTES les slides réellement présentes. On ne s'arrête plus
        # au premier trou : `only_slides` peut ne garder qu'une slide isolée, et
        # tout ce qui n'est pas gardé doit être exclu, pas seulement la queue.
        toutes = set()
        for rel in all_set:
            m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", rel)
            if m:
                toutes.add(int(m.group(1)))

        # `only_slides` / `up_to_slide` sont des POSITIONS ; tout le reste de
        # la méthode raisonne en numéros de FICHIER.
        ordre = _ordre_diapositives(temp_path)
        positions = (set(only_slides) if only_slides is not None
                     else range(1, up_to_slide + 1))
        garder = {ordre[p - 1] for p in positions if 1 <= p <= len(ordre)}
        garder &= toutes

        exclus = toutes - garder

        def _excluded(rel: str) -> bool:
            """La slide est identifiée par son NUMÉRO, jamais par un préfixe.

            Un test `startswith("ppt/slides/slide1")` retire aussi slide12 et
            slide19. Invisible tant qu'on ne coupait qu'une queue contiguë
            (slide1 exclue ⇒ tout l'est) ; faux dès qu'on garde une slide isolée.
            """
            m = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", rel)
            if m is None:
                m = re.fullmatch(r"ppt/slides/_rels/slide(\d+)\.xml\.rels", rel)
            return m is not None and int(m.group(1)) in exclus

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
                        if slide_num in garder:
                            r_id_to_slide_num[rel.get("Id")] = slide_num
                        else:
                            rels_root.remove(rel)
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
                m = re.fullmatch(r"/ppt/slides/slide(\d+)\.xml", part_name)
                if m and int(m.group(1)) not in garder:
                    types_elem.remove(ov)
            control_bytes[ct_rel] = etree.tostring(
                ct_tree, encoding="utf-8", xml_declaration=True)

        # 4. Numéros de diapositive FIGÉS. Le champ `<a:fld type="slidenum">`
        # est recalculé au rendu d'après la position dans le deck PARTIEL : une
        # slide isolée (aperçu progressif) s'affichait « 1 » quelle que soit sa
        # place. On le remplace par un run portant son numéro dans le deck
        # COMPLET (ordre de sldIdLst + firstSlideNum), seulement quand des
        # slides sont exclues : le fichier final garde ses champs vivants.
        if exclus and rels_path.exists() and pres_path.exists():
            control_bytes.update(
                self._figer_numeros(temp_path, rels_path, pres_path, garder))

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

    @staticmethod
    def _figer_numeros(temp_path, rels_path, pres_path,
                       garder: set[int]) -> dict[str, bytes]:
        """XML des slides gardées dont les champs slidenum portent leur numéro
        dans le deck complet. Lit les fichiers d'ORIGINE (non trimmés)."""
        slide_rel_type = ("http://schemas.openxmlformats.org/officeDocument/"
                          "2006/relationships/slide")
        rid_to_num: dict[str, int] = {}
        for rel in etree.parse(str(rels_path)).getroot():
            if rel.get("Type") == slide_rel_type:
                m = re.search(r"slide(\d+)\.xml", rel.get("Target", ""))
                if m:
                    rid_to_num[rel.get("Id")] = int(m.group(1))
        pres_root = etree.parse(str(pres_path)).getroot()
        try:
            premier = int(pres_root.get("firstSlideNum", "1"))
        except ValueError:
            premier = 1
        affiche: dict[int, int] = {}
        for pos, el in enumerate(pres_root.xpath(
                "//p:sldIdLst/p:sldId", namespaces=NAMESPACES)):
            num = rid_to_num.get(el.get(f"{{{NAMESPACES['r']}}}id"))
            if num is not None:
                affiche[num] = premier + pos

        a = NAMESPACES["a"]
        out: dict[str, bytes] = {}
        for num in garder:
            if num not in affiche:
                continue
            path = temp_path / "ppt" / "slides" / f"slide{num}.xml"
            if not path.exists():
                continue
            tree = etree.parse(str(path))
            champs = tree.xpath('//a:fld[@type="slidenum"]',
                                namespaces=NAMESPACES)
            if not champs:
                continue
            for fld in champs:
                run = etree.Element(f"{{{a}}}r")
                rpr = fld.find(f"{{{a}}}rPr")
                if rpr is not None:
                    run.append(rpr)
                t = etree.SubElement(run, f"{{{a}}}t")
                t.text = str(affiche[num])
                fld.getparent().replace(fld, run)
            out[f"ppt/slides/slide{num}.xml"] = etree.tostring(
                tree, encoding="utf-8", xml_declaration=True, standalone=True)
        return out
