import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class TranslatorAI:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("La clé DEEPSEEK_API_KEY est manquante dans le fichier .env")
        
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = "deepseek-chat"
        self.max_retries = 3
        self.target_batch_size = 50
        
        self.system_instruction = """
        Tu es un traducteur technique expert spécialisé dans la localisation de documents structurés.

        On te fournit les éléments de texte d'une page de document, dans l'ordre de
        lecture, sous la forme [{"id": "...", "text": "..."}]. Beaucoup d'éléments ne
        sont que des FRAGMENTS d'une même phrase, coupée par des retours à la ligne
        automatiques ou des changements de style (italique, gras, formule, code).

        TA TÂCHE, EN DEUX TEMPS :

        1. REGROUPE les éléments en paragraphes. Deux éléments appartiennent au MÊME
        paragraphe UNIQUEMENT si l'un est la continuation grammaticale de l'autre —
        phrase coupée par un retour à la ligne AUTOMATIQUE ou par un changement de
        style en milieu de phrase (le premier se termine en plein milieu de phrase ou
        sur un mot coupé, le suivant la poursuit sans majuscule de début). TOUT RETOUR
        À LA LIGNE VOLONTAIRE = paragraphes différents. Forment donc chacun leur propre
        paragraphe : les titres et sous-titres (même empilés), les numéros de page, les
        en-têtes/pieds de page, les libellés (notamment se terminant par « : »), la
        ligne de noms/auteurs qui suit un libellé, les items de liste, les signatures,
        les éléments de tableau ou de sommaire. Dans le doute, préfère des paragraphes
        SÉPARÉS (une fusion à tort déplace le texte dans le document final ; une
        séparation à tort est sans gravité).

        2. TRADUIS chaque paragraphe EN ENTIER, d'un seul tenant : concatène le texte
        de ses éléments dans l'ordre fourni, reconstitue les mots coupés par une césure
        de fin de ligne (« mo- » puis « dèle » → « modèle »), puis traduis la phrase
        complète de façon naturelle. N'écris JAMAIS de césure de coupure de ligne dans
        la traduction — seuls les traits d'union lexicaux (« peut-être »,
        « c'est-à-dire ») sont permis.

        RÉPONDS UNIQUEMENT avec un objet JSON de la forme :
        {"paragraphs": [{"ids": ["id1", "id2"], "translated_text": "..."}, ...]}

        RÈGLES CRITIQUES :
        - CHAQUE id fourni apparaît dans EXACTEMENT UN paragraphe, dans l'ordre de
          lecture. Ne modifie JAMAIS les id, n'en invente pas, n'en oublie aucun.
        - "translated_text" est la traduction COMPLÈTE et UNIQUE du paragraphe entier.
          Ne la répartis PAS entre les éléments, ne répète aucun contenu.
        - Les fragments non traduisibles (formules, code, nombres, symboles : « 2n »,
          « O(k) », « 7 »…) sont recopiés TELS QUELS, à leur place, dans la traduction
          de leur paragraphe.
        - PRÉSERVE les balises structurelles comme [[n]] et [[/n]] exactement à leur place.
        - LONGUEUR : la traduction remplace le texte dans une mise en page figée,
        elle doit donc occuper un espace aussi proche que possible de l'original.
        Par ordre de préférence : (1) même longueur ; (2) légèrement plus courte ;
        (3) plus longue — à éviter si une formulation équivalente plus compacte existe.
        INTERDICTIONS ABSOLUES : ne JAMAIS abréger des mots, ne JAMAIS tronquer ou
        omettre une partie du contenu, ne JAMAIS utiliser d'abréviations absentes du
        texte original, ne JAMAIS remplacer des mots par des symboles ou caractères
        de substitution (« & » au lieu de « et », « + » au lieu de « plus », « / » au
        lieu de « ou », chiffres au lieu de nombres écrits en lettres, etc.) ni aucune
        astuce typographique de ce genre : le résultat doit rester irréprochable dans
        un document professionnel. La traduction doit toujours être COMPLÈTE, naturelle
        et fidèle : la concision s'obtient uniquement par le choix de tournures et de
        synonymes naturellement plus courts, jamais en sacrifiant du contenu ni la
        qualité rédactionnelle.
        """

    def _clean_json_text(self, text):
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    @staticmethod
    def _reading_order(members):
        """Ordre de lecture géométrique des fragments d'un paragraphe — le MÊME
        que celui du moteur d'injection (baseline puis x pour l'horizontal ;
        le long de l'axe X pour le texte pivoté), pour que la concaténation des
        morceaux distribués reconstitue exactement la phrase rendue. Les
        éléments sans géométrie (DOCX/PPTX) gardent leur ordre d'envoi."""
        def key(b):
            rot = b.get("rotation", 0.0) or 0.0
            o = b.get("origin") or []
            bb = b.get("bbox") or [0, 0, 0, 0]
            if abs(rot) <= 1.0:
                base = o[1] if len(o) >= 2 else bb[3]
                return (0, round(base, 1), bb[0])
            rn = int(round(rot / 90.0)) * 90 % 360
            x = o[0] if len(o) >= 1 else bb[0]
            return (1, -x if rn == 270 else x, bb[1])
        return sorted(members, key=key)

    @staticmethod
    def _distribute_paragraph(members, translated):
        """Répartit la traduction ENTIÈRE d'un paragraphe entre ses fragments
        d'origine. La répartition est purement matérielle — le moteur refond de
        toute façon le flux du groupe dans son conteneur englobant :
          • les fragments courts (≤ 3 tokens) retrouvés tels quels dans la
            traduction (formules, nombres, code : « 2n », « O(k) »…) sont
            ANCRÉS : ils reçoivent exactement leur token, ce qui préserve leur
            style inline (italique mathématique, fonte code…) ;
          • le reste des mots est réparti entre les autres fragments
            proportionnellement à la longueur de leur texte source.
        Chaque fragment d'un paragraphe multi-éléments est marqué
        « unit_member » : le moteur ne doit ni retomber sur le texte original
        pour un fragment resté vide (sa part vit chez un voisin), ni
        dé-dupliquer (la répartition est exacte par construction)."""
        text = (translated or "").strip()
        if len(members) == 1:
            members[0].pop("unit_member", None)   # purge d'un essai rejeté
            members[0]["translated_text"] = text
            return
        for b in members:
            b["unit_member"] = True
            b["translated_text"] = ""
        if not text:
            return
        words = text.split()

        _SUPSUB = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")

        def norm(w):
            return w.strip(".,;:!?()[]{}«»\"'’…").translate(_SUPSUB)

        # Ancres : recherche ordonnée (jamais de retour en arrière) des
        # fragments courts repris verbatim dans la traduction.
        anchors = []                              # (idx_membre, début, fin)
        anchored = set()
        cursor = 0
        for i, b in enumerate(members):
            src = (b.get("text") or "").split()
            if not 0 < len(src) <= 3:
                continue
            m = len(src)
            for j in range(cursor, len(words) - m + 1):
                if all(norm(words[j + k]) == norm(src[k]) and norm(src[k])
                       for k in range(m)):
                    anchors.append((i, j, j + m))
                    anchored.add(i)
                    cursor = j + m
                    break

        # Marqueurs inline minuscules (exposant « R² », indice, appel de
        # note : taille NETTEMENT plus petite que la dominante ET ≤ 3
        # caractères) restés sans ancre : leur contenu a été absorbé
        # typographiquement par la traduction (« R » + « 2 » → « R² ») —
        # leur donner des mots du flux afficherait un mot normal en corps
        # d'exposant. Ils restent vides (unit_member bloque le fallback).
        weight = {}
        for b in members:
            s = b.get("size")
            if s:
                weight[round(s, 1)] = (weight.get(round(s, 1), 0)
                                       + len((b.get("text") or "").strip()))
        dom = max(weight, key=weight.get) if weight else None
        excluded = set()
        for i, b in enumerate(members):
            s = b.get("size")
            if (i not in anchored and s and dom and s < 0.85 * dom
                    and len((b.get("text") or "").strip()) <= 3):
                excluded.add(i)

        result = [[] for _ in members]
        seg_start = 0
        prev = -1
        for mi, s, e in anchors + [(len(members), len(words), len(words))]:
            gap = words[seg_start:s]
            between = [k for k in range(prev + 1, mi) if k not in excluded]
            if between and gap:
                weights = [max(1, len(members[k].get("text") or ""))
                           for k in between]
                tot = sum(weights)
                counts, acc = [], 0
                for idx in range(len(between)):
                    c = (len(gap) - acc if idx == len(between) - 1
                         else min(int(round(len(gap) * weights[idx] / tot)),
                                  len(gap) - acc))
                    counts.append(c)
                    acc += c
                # Chaque fragment reçoit au moins un mot quand il y en a assez :
                # un fragment vide perd son obstacle visuel et tente le moteur
                # de retomber sur l'original (désormais bloqué par unit_member).
                while len(gap) >= len(between) and 0 in counts:
                    zi = counts.index(0)
                    mx = max(range(len(counts)), key=counts.__getitem__)
                    if counts[mx] <= 1:
                        break
                    counts[mx] -= 1
                    counts[zi] += 1
                pos = 0
                for c, k in zip(counts, between):
                    result[k] = gap[pos:pos + c]
                    pos += c
            elif gap:
                # Mots entre deux ancres sans fragment porteur : rattachés au
                # membre précédent (ou au suivant en tout début de paragraphe).
                if prev >= 0:
                    result[prev].extend(gap)
                elif mi < len(members):
                    result[mi].extend(gap)
            if mi < len(members):
                result[mi].extend(words[s:e])
                prev = mi
                seg_start = e
        for k, b in enumerate(members):
            b["translated_text"] = " ".join(result[k])

    @staticmethod
    def _unit_geometry_ok(members):
        """Validation géométrique d'un paragraphe proposé par l'IA — miroir de
        la propriété universelle qu'utilise le moteur (_split_group_runs) : un
        paragraphe réel a une taille de police homogène (±15 %) et une seule
        orientation. Un mélange (titre 48 pt + corps 13 pt, exposant + texte)
        révèle une fusion à tort : le moteur scinderait le groupe au rendu et
        les mots distribués fuiraient d'un morceau à l'autre (« PROGRAMMATION
        Les » en taille de titre). Exception légitime : les marqueurs inline
        (exposant « R² », indice, appel de note) — plus PETITS que la taille
        dominante ET très courts (≤ 3 caractères). Un titre fusionné à tort
        est au contraire plus GRAND que le texte porteur. Les écarts de
        baseline ne sont PAS rejetés : une phrase peut légitimement continuer
        dans la colonne suivante."""
        rots = {int(round((b.get("rotation") or 0.0) / 90.0)) * 90 % 360
                for b in members}
        if len(rots) > 1:
            return False
        # Taille dominante = celle qui porte le plus de caractères.
        weight = {}
        for b in members:
            s = b.get("size")
            if s:
                weight[round(s, 1)] = (weight.get(round(s, 1), 0)
                                       + len((b.get("text") or "").strip()))
        if not weight:
            return True
        dom = max(weight, key=weight.get)
        for b in members:
            s = b.get("size")
            if not s or min(s, dom) / max(s, dom) >= 0.85:
                continue
            if s < dom and len((b.get("text") or "").strip()) <= 3:
                continue                      # exposant / appel de note
            return False
        return True

    @staticmethod
    def _extract_paragraphs(data):
        """Repère le format de réponse par paragraphe ({"paragraphs": [...]})
        avec la même tolérance que le format historique : liste à la racine ou
        sous n'importe quelle clé, du moment que les entrées portent "ids"."""
        def looks_like(v):
            return (isinstance(v, list) and v
                    and all(isinstance(p, dict) and "ids" in p for p in v))
        if isinstance(data, dict):
            paras = data.get("paragraphs")
            if looks_like(paras):
                return paras
            return next((v for v in data.values() if looks_like(v)), None)
        if looks_like(data):
            return data
        return None

    def _apply_paragraphs(self, batch, paragraphs):
        """Applique une réponse par paragraphe : la clé de groupe est posée par
        le CODE (l'IA ne décide que l'appartenance), et la traduction entière
        est distribuée déterministiquement entre les fragments. Lève ValueError
        si la réponse ne couvre pas tous les ids ou contient une traduction
        vide — le mécanisme retry/scission existant prend alors le relais."""
        by_id = {b["id"]: b for b in batch}
        key_prefix = batch[0]["id"]
        seen = set()
        units = []
        for p in paragraphs:
            ids = [i for i in (p.get("ids") or []) if i in by_id and i not in seen]
            if not ids:
                continue
            text = (p.get("translated_text") or p.get("text") or "").strip()
            if not text:
                raise ValueError(f"Traduction vide pour le paragraphe {ids}.")
            seen.update(ids)
            units.append((ids, text))
        missing = [b["id"] for b in batch if b["id"] not in seen]
        if missing:
            shown = ", ".join(missing[:5])
            extra = f" (+{len(missing) - 5} autres)" if len(missing) > 5 else ""
            raise ValueError(f"Ids absents de la réponse : {shown}{extra}")
        bad = [ids for ids, _t in units
               if len(ids) > 1 and not self._unit_geometry_ok([by_id[i] for i in ids])]
        if bad:
            shown = " | ".join(", ".join(ids) for ids in bad[:3])
            raise ValueError(
                "Paragraphes invalides (tailles de police ou orientations "
                f"incompatibles, à séparer) : {shown}")
        for n, (ids, text) in enumerate(units):
            members = self._reading_order([by_id[i] for i in ids])
            for b in members:
                b["paragraph_key"] = f"{key_prefix}:u{n}"
            self._distribute_paragraph(members, text)

    def _translate_batch(self, batch, target_lang, progress_callback, retries=3):
        if not batch:
            return True
            
        items = [{"id": b["id"], "text": b["text"]} for b in batch]
        
        base_prompt = (
            f"Traduis ces éléments vers la langue : {target_lang}. "
            "Regroupe les fragments d'une même phrase en paragraphes et traduis "
            "chaque paragraphe ENTIER, au format {\"paragraphs\": [...]} demandé. "
            "Conserve les balises [[n]].\n\n"
            f"{json.dumps(items, ensure_ascii=False)}"
        )

        last_error = None
        for attempt in range(retries):
            # Retry informé : la cause du rejet précédent (id manquant,
            # paragraphe géométriquement impossible…) est signalée au modèle
            # plutôt que de rejouer le même prompt à l'aveugle.
            prompt = base_prompt if not last_error else (
                base_prompt
                + f"\n\nIMPORTANT — ta réponse précédente était invalide : "
                  f"{last_error} Corrige ce point précis."
            )
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=8192,
                    response_format={"type": "json_object"}
                )

                # Réponse coupée à max_tokens : le JSON est tronqué, inutile de
                # réessayer le même lot — on le scinde en deux directement.
                if response.choices[0].finish_reason == "length":
                    if len(batch) > 1:
                        if progress_callback:
                            progress_callback(f"Lot trop grand ({len(batch)} blocs), scission en deux.")
                        mid = len(batch) // 2
                        return (self._translate_batch(batch[:mid], target_lang, progress_callback, retries)
                                and self._translate_batch(batch[mid:], target_lang, progress_callback, retries))
                    raise ValueError("Réponse tronquée (max_tokens atteint) sur un bloc unique.")

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Réponse vide de DeepSeek.")

                translated_data = json.loads(content)

                # Format nominal : par PARAGRAPHE ({"paragraphs": [...]}) — le
                # modèle traduit chaque paragraphe d'un seul tenant, le code
                # distribue ensuite la traduction entre les fragments (jamais
                # de redistribution par l'IA : c'était la cause des décalages
                # id↔texte sur les pages très fragmentées).
                paragraphs = self._extract_paragraphs(translated_data)
                if paragraphs is not None:
                    self._apply_paragraphs(batch, paragraphs)
                    return True

                # Secours — format historique par élément. Le modèle ne
                # respecte pas toujours {"translations": [...]} : il renvoie
                # parfois une liste à la racine, ou un objet avec une autre
                # clé, ou un mapping direct {id: texte}. On accepte tout.
                if isinstance(translated_data, list):
                    translated_results = translated_data
                elif isinstance(translated_data, dict):
                    translated_results = translated_data.get("translations")
                    if translated_results is None:
                        # n'importe quelle clé contenant une liste de dicts
                        translated_results = next(
                            (v for v in translated_data.values() if isinstance(v, list)),
                            None
                        )
                    if translated_results is None:
                        # mapping direct {id: texte_traduit}
                        translated_results = [
                            {"id": k, "translated_text": v}
                            for k, v in translated_data.items() if isinstance(v, str)
                        ]
                else:
                    raise ValueError(f"Format de réponse inattendu : {type(translated_data).__name__}")

                res_dict = {}
                for res in translated_results:
                    if isinstance(res, dict) and "id" in res:
                        res_dict[res["id"]] = (
                            res.get("translated_text") or res.get("text", ""),
                            res.get("paragraph"),
                        )

                # Préfixe d'unicité : un lot scindé (troncature) régénère des
                # clés p1/p2… dans chaque moitié — on les préfixe par l'id du
                # premier bloc du lot pour éviter toute collision sur la page.
                key_prefix = batch[0]["id"]
                count = 0
                for b in batch:
                    if b["id"] in res_dict:
                        text, para_key = res_dict[b["id"]]
                        b["translated_text"] = text
                        if para_key:
                            b["paragraph_key"] = f"{key_prefix}:{para_key}"
                        count += 1
                
                if count == 0 and len(batch) > 0:
                    raise ValueError(f"Aucune correspondance d'ID trouvée dans la réponse. Début de la réponse : {content[:200]}")
                    
                return True
                
            except Exception as e:
                last_error = str(e)
                if progress_callback:
                    progress_callback(f"⚠️ Erreur lot (tentative {attempt+1}/{retries}) : {e}")
                time.sleep(2 ** attempt)

        # Dernier recours : scinder le lot (un JSON tronqué ou malformé sur un
        # gros lot passe souvent une fois divisé).
        if len(batch) > 1:
            if progress_callback:
                progress_callback(f"Échec du lot de {len(batch)} blocs, scission en deux.")
            mid = len(batch) // 2
            return (self._translate_batch(batch[:mid], target_lang, progress_callback, retries)
                    and self._translate_batch(batch[mid:], target_lang, progress_callback, retries))
        return False

    _LANG_NAMES = {
        "fr": "French", "en": "English", "es": "Spanish", "de": "German",
        "it": "Italian", "pt": "Portuguese", "ar": "Arabic", "zh": "Chinese",
        "ja": "Japanese", "ko": "Korean", "ru": "Russian", "nl": "Dutch",
    }

    def translate_json(self, json_path, target_lang="en", progress_callback=None, limit=None):
        target_lang = self._LANG_NAMES.get(target_lang.lower(), target_lang)
        if not os.path.exists(json_path):
            return False, "Fichier JSON introuvable."

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        batches = []
        
        if "pages" in data:
            if progress_callback: progress_callback("Mode PDF : Groupement par page détecté.")
            for page in data["pages"]:
                page_blocks = [b for b in page.get("text_blocks", []) if b.get("text", "").strip()]
                if page_blocks:
                    batches.append(page_blocks)
        
        elif "slides" in data:
            if progress_callback: progress_callback("Mode PPTX : Groupement par slide détecté.")
            for slide in data["slides"]:
                slide_blocks = []
                for block in slide.get("text_elements", []):
                    if block.get("text", "").strip(): slide_blocks.append(block)
                for diag in slide.get("diagram_elements", []):
                    for block in diag.get("text_elements", []):
                        if block.get("text", "").strip(): slide_blocks.append(block)
                
                if slide_blocks:
                    batches.append(slide_blocks)
        
        else:
            if progress_callback: progress_callback("Mode DOCX : Groupement par sections et éléments détecté.")
            doc_data = data.get("document", {})
            for section in ["elements", "headers", "footers", "textboxes", "smartarts"]:
                section_blocks = [b for b in doc_data.get(section, []) if b.get("text", "").strip()]
                if not section_blocks:
                    continue
                
                if section == "elements":
                    current_group = []
                    last_type = None
                    
                    for b in section_blocks:
                        b_type = b.get("context", {}).get("type", "paragraph")
                        
                        if last_type and b_type != last_type and len(current_group) >= self.target_batch_size:
                            batches.append(current_group)
                            current_group = []
                        
                        current_group.append(b)
                        last_type = b_type
                        
                        if len(current_group) >= self.target_batch_size:
                            batches.append(current_group)
                            current_group = []
                    
                    if current_group:
                        batches.append(current_group)
                else:
                    for i in range(0, len(section_blocks), self.target_batch_size):
                        batches.append(section_blocks[i:i+self.target_batch_size])

        if limit and isinstance(limit, int):
            flat_all = [b for batch in batches for b in batch]
            batches = [flat_all[:limit]]
            if progress_callback:
                progress_callback(f"Mode TEST : Traduction limitée aux {limit} premiers blocs.")

        total_batches = len(batches)
        if total_batches == 0:
            return False, "Aucun texte à traduire."

        if progress_callback:
            progress_callback(f"Début de la traduction ({total_batches} lots structurels)...")

        batches_processed = 0
        for batch in batches:
            success = self._translate_batch(batch, target_lang, progress_callback)
            if not success:
                return False, f"Échec lors de la traduction du lot {batches_processed+1}."
            
            batches_processed += 1
            if progress_callback:
                progress_callback(f"Progression : {batches_processed}/{total_batches} lots traités.")
            
            time.sleep(0.5)

        output_path = json_path.replace(".json", "_translated.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback("Traduction terminée avec succès !")

        return True, output_path
