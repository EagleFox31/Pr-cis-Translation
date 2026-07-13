import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv

try:
    from . import glossary                      # importé en paquet
except ImportError:                             # ... ou à plat (sys.path backend)
    import glossary

load_dotenv()

class TranslatorAI:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("La clé DEEPSEEK_API_KEY est manquante dans le fichier .env")

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        # Modèle de REPLI (fallback). Le vrai choix se fait PAR REQUÊTE via le
        # paramètre `quality` du formulaire (rapide vs précis) : app.py sélectionne
        # le modèle et le passe à translate_json(). Ici, défaut = rapide/stable.
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.max_retries = 3
        self.target_batch_size = 50

        self.system_instruction = """
        Tu es un traducteur expert spécialisé dans la localisation de documents structurés.

        RÈGLE DE REGISTRE — TRÈS IMPORTANTE :
        Adapte le registre au SUPPORT du fragment, pas seulement à son sens. Un
        bandeau de presse, un titre d'affiche, un libellé de bouton ou une
        notification obéissent à des formules CONSACRÉES : rends l'USAGE, pas le
        mot à mot (« BREAKING NEWS » en bandeau = « FLASH INFO » / « EN DIRECT »,
        jamais « dernières minutes » ; « Read more » = « Lire la suite »). Une
        traduction sémantiquement juste mais qui ne se dirait pas dans ce support
        est une FAUTE. Si un fragment porte un champ "consigne" de TERMINOLOGIE,
        elle prime sur ton choix spontané.

        RÈGLES CRITIQUES :
        1. PRÉSERVE les balises structurelles comme [[n]] et [[/n]] exactement à leur place.
        2. Traduis uniquement le contenu textuel à l'intérieur ou autour des balises.
        3. Ne modifie JAMAIS les identifiants "id".
        4. RÉPONDS UNIQUEMENT avec un objet JSON contenant une liste "translations".
        Chaque élément de la liste doit être un objet :
        {"id": "...", "translated_text": "..."}.

        RÈGLE D'ANCRAGE (nombres & symboles) — TRÈS IMPORTANTE :
        Si le texte ENTIER d'un fragment est uniquement un nombre, un seul symbole
        ou un jeton mathématique (ex. « 2 », « 11 », « n », « 2n », « O(k) », « k »),
        recopie-le À L'IDENTIQUE dans "translated_text". Ne lui attribue JAMAIS de
        mots ni de phrase. Ces fragments sont des points fixes immuables : ils
        servent d'ancres et empêchent le texte de glisser d'un fragment à l'autre.

        RÈGLE ANTI-EMPRUNT (anti-décalage) — TRÈS IMPORTANTE :
        Chaque fragment est une case FIGÉE : son "translated_text" est la traduction
        de SON PROPRE texte, jamais celle du fragment voisin. Si une phrase est
        coupée sur plusieurs fragments, répartis la traduction entre eux dans les
        mêmes proportions — n'entasse JAMAIS toute la phrase dans un seul fragment
        en laissant les suivants « emprunter » le contenu du fragment d'après. La
        sortie doit avoir EXACTEMENT le même nombre d'éléments que l'entrée, les
        mêmes "id", dans le même ordre, et AUCUN id ne doit être inventé ou omis.

        7. CÉSURES : un fragment peut se terminer par un mot coupé avec un trait
        d'union de fin de ligne (ex. « mo- » puis « dèle » au début du fragment
        suivant). Dans la traduction, reconstitue TOUJOURS les mots entiers : le
        fragment contenant le début du mot reçoit le mot complet (« modèle »), et
        le fragment suivant ne répète pas la fin du mot. N'écris JAMAIS de césure
        (trait d'union de coupure de ligne) dans "translated_text" — seuls les
        traits d'union lexicaux (« peut-être », « c'est-à-dire ») sont permis.
        5. LONGUEUR : la traduction remplace le texte dans une mise en page figée,
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

    def _translate_batch(self, batch, target_lang, progress_callback, retries=3,
                         model=None, max_tokens=8192):
        if not batch:
            return True

        tgt = self._tgt_code(target_lang)
        items = []
        for b in batch:
            it = {"id": b["id"], "text": b["text"]}
            # SUPPORT joint à TOUT fragment (pas seulement à ceux du glossaire) :
            # c'est la couche GÉNÉRALE. Savoir qu'un fragment est un titre / un
            # bandeau / un libellé suffit au modèle pour choisir la formule
            # consacrée, y compris pour une expression que le glossaire ne
            # connaît pas. Coût : quelques jetons par item.
            if b.get("support"):
                it["support"] = b["support"]
            consignes = []
            if b.get("consigne"):
                # Consigne PAR ITEM (ex. budget de caractères pour une
                # retraduction compacte) — voir translate.retranslate_overflows.
                consignes.append(b["consigne"])
            # Expressions PIÈGES : consigne de terminologie jointe UNIQUEMENT aux
            # fragments concernés (les autres ne paient rien). `support` et
            # `contexte` viennent de la mise en page — c'est ce que le modèle
            # n'avait pas et qui lui manquait pour choisir le bon usage.
            gl = glossary.consigne_for(b["text"], support=b.get("support", "corps"),
                                       context=b.get("contexte", ""), tgt=tgt)
            if gl:
                consignes.append(gl)
            if consignes:
                it["consigne"] = "\n".join(consignes)
            items.append(it)

        prompt = (f"Traduis ces éléments vers la langue : {target_lang}. "
                  "Conserve la structure JSON et les balises [[n]]. "
                  "Le champ \"support\" dit CE QU'EST le fragment dans la page : "
                  "\"titre\" = titre, bandeau, affiche, libellé ou notification "
                  "(texte court au grand corps) → emploie la formule CONSACRÉE de "
                  "ce support, pas la traduction mot à mot ; \"corps\" = phrase "
                  "courante → registre normal. "
                  "Si un élément comporte un champ \"consigne\", applique-la "
                  "STRICTEMENT (par exemple une longueur maximale à respecter "
                  "en reformulant, jamais en abrégeant ni en omettant du sens)."
                  f"\n\n{json.dumps(items, ensure_ascii=False)}")

        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=model or self.model,
                    messages=[
                        {"role": "system", "content": self.system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    # max_tokens dépend du mode (passé par translate_json) :
                    #  • rapide (non-raisonnant)  → 8192 suffit ;
                    #  • précis (raisonnement)    → 65536, car le modèle consomme
                    #    d'abord ~12-14k tokens de "réflexion" AVANT d'écrire la
                    #    réponse ; un budget trop bas tronque tout avant la sortie.
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )

                # Réponse coupée à max_tokens : le JSON est tronqué, inutile de
                # réessayer le même lot — on le scinde en deux directement.
                if response.choices[0].finish_reason == "length":
                    if len(batch) > 1:
                        if progress_callback:
                            progress_callback(f"Lot trop grand ({len(batch)} blocs), scission en deux.")
                        mid = len(batch) // 2
                        return (self._translate_batch(batch[:mid], target_lang, progress_callback, retries, model, max_tokens)
                                and self._translate_batch(batch[mid:], target_lang, progress_callback, retries, model, max_tokens))
                    if max_tokens < 32768:
                        # Bloc unique tronqué : doubler le budget de SORTIE
                        # avant d'abandonner (le modèle divague parfois avant de
                        # fermer le JSON ; un budget plus large le laisse finir).
                        max_tokens = min(32768, max_tokens * 2)
                        if progress_callback:
                            progress_callback(
                                f"Bloc unique tronqué : budget de sortie porté à {max_tokens}.")
                        continue
                    raise ValueError("Réponse tronquée (max_tokens atteint) sur un bloc unique.")

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Réponse vide de DeepSeek.")

                translated_data = json.loads(content)

                # Le modèle ne respecte pas toujours {"translations": [...]} :
                # il renvoie parfois une liste à la racine, ou un objet avec une
                # autre clé, ou un mapping direct {id: texte}. On accepte tout.
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
                    if translated_results is None and "id" in translated_data:
                        # objet NU d'un résultat unique (fréquent sur un lot
                        # d'un seul item) : {"id": "...", "translated_text": "..."}
                        translated_results = [translated_data]
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
                        res_dict[res["id"]] = res.get("translated_text") or res.get("text", "")

                # Moteur stable bloc par bloc : chaque bloc reçoit SA traduction,
                # aucune notion de paragraphe ni de regroupement.
                count = 0
                for b in batch:
                    if b["id"] in res_dict:
                        out = res_dict[b["id"]]
                        # FILET DE SÉCURITÉ des expressions pièges : un rendu
                        # INTERDIT (« dernières minutes ») est corrigé ici, quoi
                        # qu'ait produit le modèle. C'est cette passe — pas le
                        # prompt — qui rend l'erreur impossible.
                        out, fixed = glossary.enforce(
                            b["text"], out, support=b.get("support", "corps"),
                            context=b.get("contexte", ""), tgt=tgt)
                        if fixed and progress_callback:
                            progress_callback(
                                f"glossaire : rendu interdit corrigé "
                                f"({', '.join(fixed)}) sur {b['id']}.")
                        b["translated_text"] = out
                        count += 1

                if count == 0 and len(batch) > 0:
                    raise ValueError(f"Aucune correspondance d'ID trouvée dans la réponse. Début de la réponse : {content[:200]}")

                return True

            except Exception as e:
                if progress_callback:
                    progress_callback(f"⚠️ Erreur lot (tentative {attempt+1}/{retries}) : {e}")
                time.sleep(2 ** attempt)

        # Dernier recours : scinder le lot (un JSON tronqué ou malformé sur un
        # gros lot passe souvent une fois divisé).
        if len(batch) > 1:
            if progress_callback:
                progress_callback(f"Échec du lot de {len(batch)} blocs, scission en deux.")
            mid = len(batch) // 2
            return (self._translate_batch(batch[:mid], target_lang, progress_callback, retries, model, max_tokens)
                    and self._translate_batch(batch[mid:], target_lang, progress_callback, retries, model, max_tokens))
        return False

    # Nom ANGLAIS de la langue cible, injecté dans le prompt. Un code absent de
    # cette table y partirait tel quel (« Translate to sv-SE »), ce qui est une
    # consigne bien plus faible qu'un nom de langue explicite.
    #
    # Les VARIANTES régionales sont nommées une par une : « British English »
    # est une consigne que le modèle sait suivre (colour, whilst, 12/03/2026),
    # là où « en-GB » n'en est pas vraiment une. C'est ce nommage qui rend le
    # choix de variante réellement effectif — sans lui, en-GB et en-US
    # produisent le même texte. Clés en minuscules (cf. lang_name).
    _LANG_NAMES = {
        # Bases
        "fr": "French", "en": "English", "es": "Spanish", "de": "German",
        "it": "Italian", "pt": "Portuguese", "ar": "Arabic", "zh": "Chinese",
        "ja": "Japanese", "ko": "Korean", "ru": "Russian", "nl": "Dutch",
        "pl": "Polish", "ro": "Romanian", "cs": "Czech", "hu": "Hungarian",
        "tr": "Turkish", "sv": "Swedish", "da": "Danish", "nb": "Norwegian",
        "fi": "Finnish", "uk": "Ukrainian", "el": "Greek",
        # Variantes régionales
        "en-us": "American English (US spelling and conventions)",
        "en-gb": "British English (UK spelling and conventions)",
        "en-ca": "Canadian English",
        "en-au": "Australian English",
        "fr-fr": "French (France)",
        "fr-ca": "Canadian French (Québec usage)",
        "fr-be": "French (Belgium)",
        "fr-ch": "French (Switzerland)",
        "es-es": "European Spanish (Castilian, Spain)",
        "es-mx": "Mexican Spanish",
        "es-ar": "Argentine Spanish (rioplatense, voseo)",
        "de-de": "German (Germany)",
        "de-at": "Austrian German",
        "de-ch": "Swiss German (Swiss standard German, no ß)",
        "pt-pt": "European Portuguese (Portugal)",
        "pt-br": "Brazilian Portuguese",
        "nl-nl": "Dutch (Netherlands)",
        "nl-be": "Flemish (Dutch, Belgium)",
        "zh-cn": "Simplified Chinese",
        "zh-tw": "Traditional Chinese",
    }

    # Le glossaire est indexé par CODE de langue ('en->fr'), alors que les lots
    # circulent avec le NOM injecté dans le prompt (« French (Belgium) »). On
    # revient au code de base : toutes les variantes d'une langue partagent ses
    # pièges (« dernières minutes » est faux en fr-CA comme en fr-FR).
    _NAME_TO_CODE = {name.lower(): code.split("-")[0]
                     for code, name in {
                         "fr": "French", "en": "English", "es": "Spanish",
                         "de": "German", "it": "Italian", "pt": "Portuguese",
                     }.items()}

    @classmethod
    def _tgt_code(cls, target_lang):
        """Code de langue cible ('fr') depuis le nom injecté dans le prompt."""
        t = str(target_lang).strip().lower()
        for name, code in cls._NAME_TO_CODE.items():
            if name in t:                       # « Canadian French (Québec…) »
                return code
        return t.split("-")[0][:2]

    @classmethod
    def lang_name(cls, code):
        """Nom de langue à injecter dans le prompt. Reconnaît la variante
        ('en-GB' → British English) et, à défaut, retombe sur la langue de base
        ('en-NZ' → English) plutôt que de laisser passer un code brut."""
        c = str(code).strip().lower()
        if c in cls._LANG_NAMES:
            return cls._LANG_NAMES[c]
        base = c.split("-")[0]
        return cls._LANG_NAMES.get(base, code)

    def translate_json(self, json_path, target_lang="en", progress_callback=None, limit=None,
                       model=None, max_tokens=8192):
        target_lang = self.lang_name(target_lang)
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

        # Parallélisation des lots : plusieurs pages traduits simultanément.
        # MAX_WORKERS limité à 4 pour respecter les rate-limits DeepSeek et
        # éviter les collisions mémoire sur les gros documents. Le progress_callback
        # est thread-safe (GIL + appel simple sans état partagé).
        MAX_WORKERS = min(4, total_batches)
        failed_batch = [None]
        failed_lock = threading.Lock()
        batches_done = [0]
        done_lock = threading.Lock()

        def _run(idx_batch):
            idx, batch = idx_batch
            with failed_lock:
                if failed_batch[0] is not None:
                    return idx, False
            success = self._translate_batch(batch, target_lang, progress_callback,
                                            model=model, max_tokens=max_tokens)
            with done_lock:
                batches_done[0] += 1
                n = batches_done[0]
            if progress_callback:
                progress_callback(f"Progression : {n}/{total_batches} lots traités.")
            return idx, success

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_run, (i, b)): i for i, b in enumerate(batches)}
            for future in as_completed(futures):
                idx, success = future.result()
                if not success:
                    with failed_lock:
                        if failed_batch[0] is None:
                            failed_batch[0] = idx + 1

        if failed_batch[0] is not None:
            return False, f"Échec lors de la traduction du lot {failed_batch[0]}."

        output_path = json_path.replace(".json", "_translated.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if progress_callback:
            progress_callback("Traduction terminée avec succès !")

        return True, output_path
