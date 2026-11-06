"""
pdf_engine_v2.stream — Traduction PROGRESSIVE page par page.

Contrairement au pipeline « tout le document puis rendu », chaque page est
extraite, traduite puis rendue AVANT de passer à la suivante :

    pour chaque page :  extract_page_data → translate (+ retraduction compacte
                        de la page) → render_page_into → PDF PARTIEL réécrit

Le PDF partiel (`partial_path`) contient à tout instant les pages 1..k déjà
traitées — le client l'affiche au fil de l'eau (la page k+1 est « en cours »).
Les pages hors sélection sont COPIÉES de l'original (fidélité parfaite, aucune
traduction) pour que la pagination du partiel suive celle du document.

`on_event(event: dict)` reçoit :
    {"type": "start", "total": N}
    {"type": "page",  "page": i, "status": "extracting"|"translating"|
                       "rendering"|"done"|"copied", "done": k, "total": N}
    (les erreurs remontent en exception à l'appelant)
"""

import json
import os
import threading
import time

import fitz

from .engine import PDFObjectEngine
from .version import ENGINE_VERSION
from . import translate


def _emit(on_event, payload):
    if on_event:
        try:
            on_event(payload)
        except Exception:
            pass


# Mention posée sur une page illisible restée en langue d'origine sans choix de
# l'utilisateur : le fichier ne livre jamais l'original sans le dire. Écrite
# dans la langue cible ; anglais pour une langue absente (police Helvetica).
MENTION_NON_TRADUITE = {
    "fr": "Page non traduite : laissée en langue d'origine.",
    "en": "Page not translated: left in the original language.",
    "es": "Página no traducida: se mantiene en el idioma original.",
    "de": "Seite nicht übersetzt: in der Originalsprache belassen.",
    "it": "Pagina non tradotta: lasciata nella lingua originale.",
    "pt": "Página não traduzida: mantida no idioma original.",
    "nl": "Pagina niet vertaald: in de oorspronkelijke taal gelaten.",
}


def mention_non_traduite(target_lang) -> str:
    code = str(target_lang or "").lower()[:2]
    return MENTION_NON_TRADUITE.get(code, MENTION_NON_TRADUITE["en"])


# Mention posée sur une page laissée hors de la sélection, sans choix de
# l'utilisateur.
MENTION_NON_INCLUSE = {
    "fr": "Page non incluse dans la traduction.",
    "en": "Page not included in the translation.",
    "es": "Página no incluida en la traducción.",
    "de": "Seite nicht in der Übersetzung enthalten.",
    "it": "Pagina non inclusa nella traduzione.",
    "pt": "Página não incluída na tradução.",
    "nl": "Pagina niet opgenomen in de vertaling.",
}


def mention_non_incluse(target_lang) -> str:
    code = str(target_lang or "").lower()[:2]
    return MENTION_NON_INCLUSE.get(code, MENTION_NON_INCLUSE["en"])


def _poser_mention(page, texte):
    """Bandeau discret en haut de la page : fond blanc pour rester lisible sur
    un scan, texte gris foncé. Coordonnées de la page affichée (rotation prise
    en compte)."""
    vue = page.rect
    hauteur = 18
    bande = fitz.Rect(vue.x0, vue.y0, vue.x1, vue.y0 + hauteur)
    reelle = bande * page.derotation_matrix
    page.draw_rect(reelle, color=None, fill=(1, 1, 1), overlay=True)
    page.insert_textbox(fitz.Rect(bande.x0 + 8, bande.y0 + 4, bande.x1 - 8, bande.y1)
                        * page.derotation_matrix,
                        texte, fontsize=8, fontname="helv", color=(0.25, 0.25, 0.25),
                        align=fitz.TEXT_ALIGN_CENTER, rotate=page.rotation)


def _save_partial(out_doc, partial_path):
    """Réécrit le PDF partiel de façon ATOMIQUE (tmp + rename) : un client qui
    le télécharge pendant l'écriture ne voit jamais un fichier tronqué."""
    if not partial_path:
        return
    tmp = partial_path + ".tmp"
    out_doc.save(tmp, garbage=2, deflate=True)
    # Windows refuse de remplacer un fichier ouvert (lecture de l'aperçu,
    # antivirus qui inspecte le fichier neuf) : on réessaie, puis on renonce.
    # L'aperçu n'est qu'une vitrine : en retard d'une page, il se rattrape à
    # la suivante ; il ne doit JAMAIS faire échouer la traduction (mesuré :
    # blocage de plus de 3 s après plusieurs pauses/reprises, job en échec).
    for _ in range(50):
        try:
            os.replace(tmp, partial_path)
            return
        except PermissionError:
            time.sleep(0.1)


def _sans_attendre(travail, arret, pas=0.3):
    """Exécute `travail` (la traduction d'une page) sans bloquer un arrêt.

    Sans `arret`, appel direct. Sinon le travail tourne dans un fil à part et
    `arret()` est consulté pendant l'attente : s'il lève, la page en vol est
    ABANDONNÉE sur-le-champ — son résultat n'atteint ni le cache, ni le
    partiel, ni le décompte des pages faites (décision du 30/10 : on n'attend
    pas le retour du modèle). Le fil orphelin finit seul, sans effet."""
    if arret is None:
        return travail()
    issue = {}

    def _fil():
        try:
            issue["ok"] = travail()
        except BaseException as e:      # relancée dans le fil appelant
            issue["err"] = e

    fil = threading.Thread(target=_fil, name="page-pdf", daemon=True)
    fil.start()
    while fil.is_alive():
        fil.join(pas)
        if fil.is_alive():
            arret()
    if "err" in issue:
        raise issue["err"]
    return issue.get("ok")


def _alleger_images(pages) -> bool:
    """Retire les octets d'image recopiés dans des pages déjà extraites ; seul
    le `xref` reste. Vrai si quelque chose a été retiré."""
    allege = False
    for pg in pages:
        for el in pg.get("elements", []):
            if el.get("type") == "image" and el.get("xref") and (
                    el.get("asset_b64") or "asset_file" in el):
                for k in ("asset_b64", "asset_file", "ext"):
                    el.pop(k, None)
                allege = True
    return allege


def _images_par_xref(images) -> dict:
    """Clés "xref:<n>" (ou entières) -> {xref entier: octets} ; ignore le reste."""
    out = {}
    for cle, octets in (images or {}).items():
        try:
            xref = int(str(cle).split(":")[-1])
        except ValueError:
            continue
        out[xref] = octets
    return out


def _ajouter_polices(eng, data, doc):
    """Ajoute les polices de `doc` (une page lue par l'OCR) à celles du document.

    `_build_fonts` repart de zéro : on fusionne d'abord, et on ne reconstruit
    que si une police est vraiment nouvelle (les pages lues d'un même scan
    partagent les mêmes fichiers)."""
    nouvelle = False
    for nom, variantes in eng._extract_fonts(doc, data["font_profiles"]).items():
        connues = data["fonts"].setdefault(nom, [])
        deja = {v["b64"] for v in connues}
        for variante in variantes:
            if variante["b64"] not in deja:
                connues.append(variante)
                deja.add(variante["b64"])
                nouvelle = True
    if nouvelle:
        eng._build_fonts(data)


def translate_pdf_progressive(pdf_path, output_path, target_lang="fr",
                              pages=None, partial_path=None, on_event=None,
                              debug=False, cache_path=None, engine=None,
                              arret=None, images=None, lecteur_ocr=None,
                              pages_vides=None, pages_originales=None,
                              signaler_illisibles=False,
                              pages_non_incluses=None):
    """Traduit `pdf_path` page par page vers `output_path`.

    pages        : ensemble de numéros 1-basés à traduire (None = toutes) ; les
                   autres pages sont copiées telles quelles de l'original.
    partial_path : PDF partiel réécrit après CHAQUE page (affichage progressif).
    debug        : mode structure — aucune traduction, bordures de debug.
    cache_path   : JSON de reprise — les pages déjà traduites (tr_tagged) y sont
                   relues au lieu d'être re-payées, et chaque page traduite y est
                   ajoutée aussitôt (un job interrompu reprend où il en était).
    images       : images traduites, {"xref:<n>" ou n: octets}, posées à la
                   place des images d'origine.
    lecteur_ocr  : appelé `(numéro 1-basé, src, index)` avant la relecture du
                   cache, même pour une page déjà traduite. Rend None (page non
                   concernée) ou un objet `statut`/`pdf` : `ok` fait extraire et
                   rendre la page depuis ce `pdf` d'une page ; tout autre statut
                   recopie l'original, sans la compter comme traduite
                   (`hors_budget` : mention « page non incluse »).
    pages_vides  : pages rendues blanches, au format d'origine.
    signaler_illisibles : une page lue `illisible` reçoit une mention « page non
                   traduite » dans la langue cible, sauf si elle figure dans
                   `pages_originales` (original choisi par l'utilisateur).
    pages_non_incluses : pages hors sélection qui reçoivent la mention « page
                   non incluse », sauf celles de `pages_originales`.
    """
    eng = engine or PDFObjectEngine()
    images = _images_par_xref(images)
    lang = "fr_FR" if str(target_lang).lower().startswith("fr") else \
        f"{str(target_lang).lower()[:2]}_{str(target_lang).upper()[:2]}"
    eng.reflow_lang = lang

    # Cache de reprise : pages déjà traduites lors d'un job précédent.
    cached_pages = {}
    # FICHE DE DOCUMENT par langue cible : écrite une fois, gardée avec la
    # reprise pour qu'un job repris garde le même vocabulaire.
    fiches = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                prev = json.load(f)
            for pg in prev.get("pages", []):
                cached_pages[pg.get("page_num")] = pg
            fiches = dict(prev.get("fiches") or {})
        except Exception:
            cached_pages = {}

    def _ecrire_cache():
        try:
            tmp = cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"pages": [cached_pages[k] for k in
                                     sorted(cached_pages)],
                           "fiches": {k: v for k, v in fiches.items() if v}},
                          f, ensure_ascii=False)
            os.replace(tmp, cache_path)
        except Exception:
            pass

    # Images PAR RÉFÉRENCE : le rendu les relit dans l'original (`src_doc`).
    # Un cache écrit avant ce choix embarquait leurs octets en base64 (94 %
    # du fichier) : on les retire une fois, le rendu reste identique puisque
    # l'original est le même (le dossier est adressé par son empreinte).
    if _alleger_images(cached_pages.values()) and cache_path:
        _ecrire_cache()

    # MÉMOIRE DE DOCUMENT (cohérence inter-pages) : un texte court déjà traduit
    # dans CE document est resservi tel quel par les pages suivantes. Semée
    # depuis le cache de reprise pour qu'un job repris garde les choix du
    # premier passage.
    doc_memory = {}
    from . import tagging as _tagging
    for pg in cached_pages.values():
        for el in pg.get("elements", []):
            if el.get("type") != "paragraph":
                continue
            tr = el.get("tr_tagged")
            if not tr:
                continue
            try:
                tagged, _m = _tagging.tag_paragraph(el)
            except Exception:
                continue
            cle = translate._plain_key(tagged)
            if (cle and tr != tagged
                    and len(cle) <= translate._MEMO_MAX_LEN
                    and cle not in doc_memory):
                doc_memory[cle] = (tagged, tr)

    src = fitz.open(pdf_path)
    out = fitz.open()
    done_pages = []
    traduites = {}          # page -> page_data : matière de la cohérence
    nouvelles = 0           # pages traduites PAR CE passage (hors reprise)
    # Page lue par l'OCR -> son document d'une page. Ouverts jusqu'à la fin : le
    # rendu y relit le fond du scan, et la cohérence peut rendre la page à nouveau.
    docs_lus = {}
    try:
        total = len(src)
        _emit(on_event, {"type": "start", "total": total})

        # Polices embarquées : extraites UNE fois (dictionnaire de document).
        # Les largeurs mesurées de chaque police choisissent la police la plus
        # proche quand l'originale est introuvable (voir `engines.pdf.polices`).
        profils = {}
        data = {"pages": [], "fonts": eng._extract_fonts(src, profils),
                "font_profiles": profils}
        eng._build_fonts(data)

        for page_num in range(total):
            human = page_num + 1
            if pages_vides and human in pages_vides:
                # Choix de l'utilisateur : testé avant la sélection, la page
                # reste vide même quand un rendu n'en reconstruit que quelques-unes.
                rect = src[page_num].rect
                out.new_page(width=rect.width, height=rect.height)
                _save_partial(out, partial_path)
                _emit(on_event, {"type": "page", "page": human,
                                 "status": "vide",
                                 "done": human, "total": total})
                continue
            if pages is not None and human not in pages:
                # Hors sélection : copie fidèle de la page d'origine.
                out.insert_pdf(src, from_page=page_num, to_page=page_num)
                if (pages_non_incluses and human in pages_non_incluses
                        and human not in (pages_originales or ())):
                    _poser_mention(out[-1], mention_non_incluse(target_lang))
                _save_partial(out, partial_path)
                _emit(on_event, {"type": "page", "page": human,
                                 "status": "copied",
                                 "done": human, "total": total})
                continue

            page_src, page_idx = src, page_num
            lecture = lecteur_ocr(human, src, page_num) if lecteur_ocr else None
            if lecture is not None:
                if lecture.statut != "ok":
                    out.insert_pdf(src, from_page=page_num, to_page=page_num)
                    hors_budget = lecture.statut == "hors_budget"
                    if human not in (pages_originales or ()):
                        if hors_budget:
                            # Solde épuisé : la page n'a pas été lue, comme
                            # une page laissée hors de la sélection.
                            _poser_mention(out[-1], mention_non_incluse(target_lang))
                        elif signaler_illisibles and lecture.statut == "illisible":
                            _poser_mention(out[-1], mention_non_traduite(target_lang))
                    _save_partial(out, partial_path)
                    _emit(on_event, {"type": "page", "page": human,
                                     "status": "copied" if hors_budget else lecture.statut,
                                     "done": human, "total": total})
                    continue
                page_src, page_idx = fitz.open(stream=lecture.pdf, filetype="pdf"), 0
                docs_lus[human] = page_src
                _ajouter_polices(eng, data, page_src)

            page_data = cached_pages.get(human)
            # En mode structure, l'EXTRACTION sauvegardée suffit : elle n'a pas
            # de `tr_tagged` à attendre. Sans ce cas, chaque réouverture
            # ré-extrayait toutes les pages et réécrivait le cache.
            has_translation = bool(page_data) and (debug or any(
                e.get("tr_tagged") for e in page_data.get("elements", [])
                if e.get("type") == "paragraph"))
            if (has_translation and page_data.get("moteur") != ENGINE_VERSION
                    and page_data.get("amelioration") != ENGINE_VERSION):
                # Page découpée par une AUTRE version du moteur : elle rejouerait
                # les décisions d'avant le correctif. On la redécoupe ; la
                # traduction suit si le texte est retrouvé à l'identique, sinon
                # la page ancienne reste (aucun texte changé sans accord).
                _emit(on_event, {"type": "page", "page": human,
                                 "status": "extracting",
                                 "done": human - 1, "total": total})
                neuve = eng.extract_page_data(
                    page_src, page_idx, page_src[page_idx], images_par_reference=True)
                neuve["page_num"] = human
                if debug or translate.reattacher_traductions(neuve, page_data):
                    page_data = neuve
                else:
                    # Le texte changerait : la page garde sa version, et la
                    # mise à jour reste PROPOSÉE (pas retentée à chaque visite).
                    page_data["amelioration"] = ENGINE_VERSION
                if cache_path:
                    cached_pages[human] = page_data
                    _ecrire_cache()
            if not has_translation:
                # Pause/annulation : contrôlée seulement avant une page À
                # TRADUIRE. Les pages hors sélection ou déjà au cache se
                # recopient sans frais ; s'arrêter dessus perdrait un travail
                # fini (la page précédente, elle, est déjà au cache).
                if arret is not None:
                    arret()
                _emit(on_event, {"type": "page", "page": human,
                                 "status": "extracting",
                                 "done": human - 1, "total": total})
                page_data = eng.extract_page_data(
                    page_src, page_idx, page_src[page_idx], images_par_reference=True)
                page_data["page_num"] = human

                if not debug:
                    _emit(on_event, {"type": "page", "page": human,
                                     "status": "translating",
                                     "done": human - 1, "total": total})
                    one = {"pages": [page_data], "fonts": {}}
                    cle_fiche = str(target_lang).lower()
                    # Lue ici, pas dans le fil : `src` est fermé dès l'arrêt,
                    # et un fil abandonné ne doit plus y toucher.
                    matiere = None
                    if cle_fiche not in fiches:
                        try:
                            matiere = translate.matiere_fiche_pdf(src)
                            # Scan pur : l'original n'a aucun texte, seule la
                            # page lue peut nourrir la fiche.
                            if page_src is not src and not any(map(any, matiere)):
                                matiere = translate.matiere_fiche_pdf(page_src)
                        except Exception:       # page illisible : sans fiche
                            matiere = ([], [])

                    def _traduire_page():
                        if matiere is not None:
                            from engines.translation_ai import TranslatorAI
                            fiches[cle_fiche] = TranslatorAI().fiche_document(
                                *matiere, target_lang)
                        translate.translate_extraction(
                            one, target_lang=target_lang,
                            doc_memory=doc_memory, fiche=fiches[cle_fiche])
                        # Recalcule l'expansion puis retraduction compacte de
                        # la page (paragraphes qui ne tiendraient pas sans
                        # compression visible).
                        try:
                            translate.retranslate_overflows(
                                one, eng, target_lang=target_lang,
                                fiche=fiches[cle_fiche])
                        except Exception:
                            pass

                    _sans_attendre(_traduire_page, arret)
                    nouvelles += 1
                # Reprise : la page traduite rejoint le cache immédiatement.
                if cache_path:
                    cached_pages[human] = page_data
                    _ecrire_cache()

            if not debug:
                traduites[human] = page_data
            _emit(on_event, {"type": "page", "page": human,
                             "status": "rendering",
                             "done": human - 1, "total": total})
            eng.render_page_into(out, page_data, draw_borders=debug,
                                 translated=not debug, src_doc=page_src,
                                 images=None if page_src is not src else images)
            _save_partial(out, partial_path)
            done_pages.append(human)
            _emit(on_event, {"type": "page", "page": human, "status": "done",
                             "done": human, "total": total})

        # COHÉRENCE DE DOCUMENT : chaque page est traduite sans voir les
        # suivantes ; un terme laissé en langue source ici, traduit ailleurs,
        # ne se voit qu'une fois tout le document lu. Seules les pages
        # touchées sont reconstruites (et ré-annoncées : l'aperçu se recharge).
        # Jamais sur une pure reprise : rien de neuf à confronter, et les
        # cognats légitimes seraient redemandés à chaque ouverture.
        if nouvelles and not debug:
            fiche = fiches.get(str(target_lang).lower(), "")
            try:
                touchees = translate.coherence_document(
                    [traduites[h] for h in sorted(traduites)],
                    target_lang=target_lang, fiche=fiche)
            except Exception:
                touchees = set()
            for human in sorted(touchees):
                page_data = traduites[human]
                try:
                    translate.retranslate_overflows(
                        {"pages": [page_data], "fonts": {}}, eng,
                        target_lang=target_lang, fiche=fiche)
                except Exception:
                    pass
                neuve = fitz.open()
                try:
                    lu = docs_lus.get(human)
                    eng.render_page_into(neuve, page_data, translated=True,
                                         src_doc=lu or src,
                                         images=None if lu else images)
                    out.delete_page(human - 1)
                    out.insert_pdf(neuve, start_at=human - 1)
                finally:
                    neuve.close()
            if touchees:
                if cache_path:
                    _ecrire_cache()
                _save_partial(out, partial_path)
                for human in sorted(touchees):
                    _emit(on_event, {"type": "page", "page": human,
                                     "status": "done",
                                     "done": total, "total": total})

        # Document sans aucune page traduite (tout illisible) : la table existe
        # quand même, la réouverture et la copie d'un document partagé en ont besoin.
        if cache_path and not os.path.exists(cache_path):
            _ecrire_cache()

        out.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        out.close()
        src.close()
        for lu in docs_lus.values():
            lu.close()
    return output_path
