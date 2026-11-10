"""Catalogue des fonctionnalités, améliorations et correctifs de Précis.

UNE source pour la page /fonctionnalites, les fenêtres « Nouveautés » et
l'e-mail de version. Publier un élément = l'ajouter ici et déployer.

Champs d'un élément :
    id          slug stable (sert d'ancre et de clé « vu »)
    date        ISO AAAA-MM-JJ ; la fenêtre « depuis » compare cette date
    type        nouveaute | amelioration | correctif
    domaine     documents | visionneuse | extension | compte
    importance  1 (fort) à 3 ; trie les éléments phares
    phare       affiché dans la fenêtre d'accueil (4 au plus)
    icone       nom d'icône lucide (éléments phares), sinon icône du domaine
    lien        chemin interne facultatif
    fr / en     titre, resume, detail ; titre_court / resume_court pour
                les éléments phares (textes de la fenêtre d'accueil)

VERSION doit rester égale au champ "version" du package.json racine
(vérifié par le test du catalogue).
"""

VERSION = "1.7.0"
DATE_VERSION = "2026-11-09"

TYPES = ("nouveaute", "amelioration", "correctif")
DOMAINES = ("documents", "visionneuse", "extension", "compte")
LANGUES = ("fr", "en")

FONCTIONNALITES: list[dict] = [
    # ── Fonctionnalités ─────────────────────────────────────────────────
    {
        "id": "excel-traduit-en-entier",
        "date": "2026-10-09",
        "type": "nouveaute",
        "domaine": "documents",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "Excel traduit en entier",
            "resume": "Le texte est traduit partout où Excel le range ; nombres et formules restent intacts.",
            "detail": "Une traduction plus longue que sa source peut déborder de sa colonne : ce cas n'est pas encore traité.",
        },
        "en": {
            "titre": "Excel translated in full",
            "resume": "Text is translated wherever Excel stores it; numbers and formulas stay intact.",
            "detail": "A translation longer than its source can overflow its column: this case is not handled yet.",
        },
    },
    {
        "id": "mise-en-page-en-place",
        "date": "2026-07-24",
        "type": "nouveaute",
        "domaine": "documents",
        "importance": 1,
        "phare": True,
        "icone": "layout-template",
        "fr": {
            "titre": "La mise en page reste en place",
            "resume": "PDF, Word et PowerPoint : le texte est remis à sa place, pas reconstruit.",
            "detail": "Le texte est relevé avec sa position et son style, traduit, puis réinjecté dans le document d'origine. Le résultat reste un fichier modifiable, sans garantie d'identité au pixel près.",
            "titre_court": "Vos documents gardent leur mise en page",
            "resume_court": "PDF, Word, PowerPoint, Excel et texte : polices, colonnes, tableaux et images restent en place.",
        },
        "en": {
            "titre": "The layout stays in place",
            "resume": "PDF, Word and PowerPoint: text is put back where it was, not rebuilt.",
            "detail": "Text is read with its position and style, translated, then written back into the original document. The result is still an editable file, with no pixel-perfect guarantee.",
            "titre_court": "Your documents keep their layout",
            "resume_court": "PDF, Word, PowerPoint, Excel and text: fonts, columns, tables and images stay in place.",
        },
    },
    {
        "id": "apercu-page-par-page",
        "date": "2026-07-24",
        "type": "nouveaute",
        "domaine": "documents",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "Aperçu page par page",
            "resume": "L'original s'affiche d'abord, puis chaque page traduite le remplace.",
            "detail": "Une traduction interrompue reprend là où elle s'était arrêtée, sans repayer les pages déjà faites.",
        },
        "en": {
            "titre": "Page-by-page preview",
            "resume": "The original shows first, then each translated page replaces it.",
            "detail": "An interrupted translation resumes where it stopped, without paying again for pages already done.",
        },
    },
    {
        "id": "original-et-traduction",
        "date": "2026-07-24",
        "type": "nouveaute",
        "domaine": "visionneuse",
        "importance": 1,
        "phare": True,
        "icone": "columns-2",
        "fr": {
            "titre": "Original et traduction côte à côte",
            "resume": "Comparez les deux versions, avec un mode agrandi.",
            "detail": "Le mode agrandi affiche les deux pages sur toute la largeur de l'écran.",
            "titre_court": "Original et traduction côte à côte",
            "resume_court": "Page par page, avec vignettes et zoom à la molette.",
        },
        "en": {
            "titre": "Original and translation side by side",
            "resume": "Compare both versions, with an enlarged view.",
            "detail": "The enlarged view shows both pages across the full width of the screen.",
            "titre_court": "Original and translation side by side",
            "resume_court": "Page by page, with thumbnails and scroll-wheel zoom.",
        },
    },
    {
        "id": "extension-navigateur",
        "date": "2026-11-09",
        "type": "nouveaute",
        "domaine": "extension",
        "importance": 1,
        "phare": True,
        "icone": "puzzle",
        "lien": "/extension",
        "fr": {
            "titre": "Traduire depuis le navigateur",
            "resume": "Une extension, avec sa page d'installation sur le site.",
            "detail": "Les limites d'usage de l'extension sont précisées sur sa page.",
            "titre_court": "Une extension pour votre navigateur",
            "resume_court": "Traduisez aussi les pages web que vous lisez.",
        },
        "en": {
            "titre": "Translate from your browser",
            "resume": "An extension, with its installation page on the site.",
            "detail": "The extension's usage limits are stated on its page.",
            "titre_court": "An extension for your browser",
            "resume_court": "Translate the web pages you read, too.",
        },
    },
    {
        "id": "inviter-un-proche",
        "date": "2026-11-09",
        "type": "nouveaute",
        "domaine": "compte",
        "importance": 2,
        "phare": True,
        "icone": "user-plus",
        "fr": {
            "titre": "Inviter un proche",
            "resume": "Envoyez une invitation par e-mail depuis votre compte.",
            "detail": "Votre proche reçoit un e-mail avec un lien pour créer son compte.",
            "titre_court": "Invitez vos proches",
            "resume_court": "Une invitation par e-mail, depuis votre compte.",
        },
        "en": {
            "titre": "Invite someone",
            "resume": "Send an invitation by email from your account.",
            "detail": "They receive an email with a link to create their account.",
            "titre_court": "Invite the people you know",
            "resume_court": "An email invitation, sent from your account.",
        },
    },
    {
        "id": "essai-cinq-pages",
        "date": "2026-10-21",
        "type": "nouveaute",
        "domaine": "compte",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "Essai : cinq pages par mois",
            "resume": "Cinq pages de document offertes chaque mois pendant l'essai.",
            "detail": "Le compteur de pages est visible dans le panneau du compte.",
        },
        "en": {
            "titre": "Trial: five pages a month",
            "resume": "Five free document pages every month during the trial.",
            "detail": "The page counter is shown in the account panel.",
        },
    },
    {
        "id": "programme-beta",
        "date": "2026-10-20",
        "type": "nouveaute",
        "domaine": "compte",
        "importance": 3,
        "phare": False,
        "lien": "/beta",
        "fr": {
            "titre": "Programme bêta",
            "resume": "Des testeurs invités, avec un quota par format.",
            "detail": "L'accès se fait par un lien d'activation reçu par e-mail.",
        },
        "en": {
            "titre": "Beta programme",
            "resume": "Invited testers, with a quota per format.",
            "detail": "Access is granted through an activation link sent by email.",
        },
    },
    {
        "id": "connexion-sans-mot-de-passe",
        "date": "2026-07-24",
        "type": "nouveaute",
        "domaine": "compte",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "Connexion sans mot de passe",
            "resume": "Un code reçu par e-mail, ou votre compte Google.",
            "detail": "Aucun mot de passe à retenir ni à protéger.",
        },
        "en": {
            "titre": "Sign in without a password",
            "resume": "A code sent by email, or your Google account.",
            "detail": "No password to remember or protect.",
        },
    },
    # ── Améliorations ───────────────────────────────────────────────────
    {
        "id": "powerpoint-pause-reprise",
        "date": "2026-11-09",
        "type": "amelioration",
        "domaine": "documents",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "PowerPoint : pause, reprise, annulation",
            "resume": "Gardez la main sur une traduction longue.",
            "detail": "Une traduction en cours peut être suspendue, reprise plus tard ou annulée.",
        },
        "en": {
            "titre": "PowerPoint: pause, resume, cancel",
            "resume": "Stay in control of a long translation.",
            "detail": "A running translation can be paused, resumed later or cancelled.",
        },
    },
    {
        "id": "pdf-polices-manquantes",
        "date": "2026-10-20",
        "type": "amelioration",
        "domaine": "documents",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "PDF : polices manquantes retrouvées",
            "resume": "Une police absente du fichier est remplacée par la même ou la plus proche.",
            "detail": "La famille de police (avec ou sans empattements) est respectée.",
        },
        "en": {
            "titre": "PDF: missing fonts found",
            "resume": "A font missing from the file is replaced by the same one or the closest match.",
            "detail": "The font family (serif or sans-serif) is respected.",
        },
    },
    {
        "id": "visionneuse-navigation",
        "date": "2026-11-09",
        "type": "amelioration",
        "domaine": "visionneuse",
        "importance": 2,
        "phare": False,
        "fr": {
            "titre": "Navigation, zoom et vignettes",
            "resume": "Page par page, zoom à la molette, vue de l'original.",
            "detail": "Les vignettes permettent d'aller directement à une page.",
        },
        "en": {
            "titre": "Navigation, zoom and thumbnails",
            "resume": "Page by page, scroll-wheel zoom, original view.",
            "detail": "Thumbnails take you straight to a page.",
        },
    },
    {
        "id": "carte-beta-simplifiee",
        "date": "2026-10-20",
        "type": "amelioration",
        "domaine": "compte",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Carte du programme bêta simplifiée",
            "resume": "Moins d'informations, plus lisibles.",
            "detail": "La carte ne montre que ce qui sert au testeur.",
        },
        "en": {
            "titre": "Simpler beta programme card",
            "resume": "Less information, easier to read.",
            "detail": "The card only shows what testers need.",
        },
    },
    # ── Correctifs ──────────────────────────────────────────────────────
    {
        "id": "apercu-diapositives",
        "date": "2026-11-09",
        "type": "correctif",
        "domaine": "documents",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Aperçu des diapositives plus fidèle",
            "resume": "La prévisualisation PowerPoint correspond mieux au fichier.",
            "detail": "Corrections apportées à l'aperçu des présentations.",
        },
        "en": {
            "titre": "More faithful slide preview",
            "resume": "The PowerPoint preview matches the file more closely.",
            "detail": "Fixes to the presentation preview.",
        },
    },
    {
        "id": "pdf-gras-italique",
        "date": "2026-10-20",
        "type": "correctif",
        "domaine": "documents",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "PDF : gras et italique conservés",
            "resume": "Les styles simulés par le fichier sont reproduits.",
            "detail": "Certains PDF penchent ou épaississent une police droite pour imiter l'italique ou le gras : ce rendu est désormais repris.",
        },
        "en": {
            "titre": "PDF: bold and italic kept",
            "resume": "Styles simulated by the file are reproduced.",
            "detail": "Some PDFs slant or thicken an upright font to imitate italic or bold: this rendering is now carried over.",
        },
    },
    {
        "id": "meme-libelle-meme-traduction",
        "date": "2026-10-20",
        "type": "correctif",
        "domaine": "documents",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Même libellé, même traduction",
            "resume": "Un libellé répété est traduit de la même façon d'une page à l'autre.",
            "detail": "Un fragment revenu inchangé est retraduit.",
        },
        "en": {
            "titre": "Same label, same translation",
            "resume": "A repeated label is translated the same way from one page to the next.",
            "detail": "A fragment that comes back unchanged is translated again.",
        },
    },
    {
        "id": "periode-facturation",
        "date": "2026-10-21",
        "type": "correctif",
        "domaine": "compte",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Période de facturation fiable",
            "resume": "Le choix mensuel ou annuel fonctionne aussi au clavier.",
            "detail": "Le sélecteur de période est plus fiable et accessible.",
        },
        "en": {
            "titre": "Reliable billing period",
            "resume": "Choosing monthly or yearly also works with the keyboard.",
            "detail": "The period selector is more reliable and accessible.",
        },
    },
    {
        "id": "cartes-forfait-allegees",
        "date": "2026-10-21",
        "type": "correctif",
        "domaine": "compte",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Cartes de forfait allégées",
            "resume": "Les cartes de forfait sont plus courtes.",
            "detail": "Une mention superflue a été retirée des cartes.",
        },
        "en": {
            "titre": "Lighter plan cards",
            "resume": "Plan cards are shorter.",
            "detail": "An unnecessary note was removed from the cards.",
        },
    },
    {
        "id": "un-seul-essai-beta",
        "date": "2026-10-20",
        "type": "correctif",
        "domaine": "compte",
        "importance": 3,
        "phare": False,
        "fr": {
            "titre": "Un seul essai bêta",
            "resume": "Les essais répétés du programme bêta sont empêchés.",
            "detail": "Ce contrôle concerne l'inscription au programme bêta.",
        },
        "en": {
            "titre": "One beta trial only",
            "resume": "Repeated beta programme trials are prevented.",
            "detail": "This check applies to beta programme sign-up.",
        },
    },
]


def elements(lang: str) -> list[dict]:
    """Éléments à plat dans une langue (repli sur le français), plus récents d'abord."""
    lang = lang if lang in LANGUES else "fr"
    sortie = []
    for e in FONCTIONNALITES:
        textes = e[lang]
        sortie.append({
            "id": e["id"],
            "date": e["date"],
            "type": e["type"],
            "domaine": e["domaine"],
            "importance": e["importance"],
            "phare": e["phare"],
            "icone": e.get("icone"),
            "lien": e.get("lien"),
            "titre": textes["titre"],
            "resume": textes["resume"],
            "detail": textes["detail"],
            "titre_court": textes.get("titre_court"),
            "resume_court": textes.get("resume_court"),
        })
    sortie.sort(key=lambda x: x["date"], reverse=True)
    return sortie


def phares(lang: str, limite: int = 4) -> list[dict]:
    """Éléments de la fenêtre d'accueil, par importance puis date récente."""
    choix = [e for e in elements(lang) if e["phare"]]
    choix.sort(key=lambda x: x["importance"])  # tri stable : la date reste décroissante
    return choix[:limite]
