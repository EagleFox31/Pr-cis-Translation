"""Langue probable d'un document déposé, avant toute traduction.

Sert uniquement à prévenir l'utilisateur quand la langue d'arrivée choisie est
déjà celle du document (revue UX de l'aperçu, point S4). Ce n'est jamais un
blocage : en cas de doute, on ne répond rien (`None`) plutôt que de se tromper.

Méthode volontairement simple, sans dépendance : les alphabets non latins se
reconnaissent à leurs caractères, les langues latines à leurs mots les plus
fréquents (articles, prépositions), comptés sur un échantillon du début.
"""
import io
import re
import zipfile

ECHANTILLON = 4000   # caractères lus : assez pour trancher, rapide sur un gros fichier
MOTS_MINIMUM = 20    # en dessous, le texte est trop court pour conclure

MOTS_FREQUENTS: dict[str, set[str]] = {
    "en": {"the", "and", "of", "to", "is", "in", "that", "for", "with", "was", "are", "this", "on", "by", "we", "our", "will", "it", "be", "from"},
    "fr": {"le", "la", "les", "et", "des", "est", "une", "dans", "pour", "que", "qui", "du", "sur", "pas", "au", "avec", "nous", "sont", "ce", "aux"},
    "es": {"el", "la", "los", "las", "y", "de", "que", "en", "es", "por", "para", "con", "una", "del", "se", "al", "como", "más", "pero", "su"},
    "de": {"der", "die", "das", "und", "ist", "nicht", "mit", "den", "ein", "eine", "zu", "von", "für", "auf", "wir", "sich", "dem", "des", "im", "auch"},
    "it": {"il", "di", "che", "è", "e", "la", "per", "un", "una", "non", "sono", "del", "della", "con", "gli", "le", "nel", "da", "anche", "più"},
    "pt": {"o", "os", "as", "e", "de", "que", "não", "em", "um", "uma", "para", "com", "do", "da", "dos", "das", "por", "são", "mais", "foi"},
    "nl": {"de", "het", "een", "en", "van", "is", "dat", "niet", "op", "met", "voor", "zijn", "wij", "ook", "aan", "er", "bij", "naar", "deze", "worden"},
}

ALPHABETS = [
    ("zh", re.compile(r"[一-鿿]")),
    ("ja", re.compile(r"[぀-ヿ]")),
    ("ko", re.compile(r"[가-힯]")),
    ("ar", re.compile(r"[؀-ۿ]")),
    ("el", re.compile(r"[Ͱ-Ͽ]")),
    ("ru", re.compile(r"[Ѐ-ӿ]")),
]


def _texte_office(file_bytes: bytes) -> str:
    """Texte brut d'un docx/pptx/xlsx : contenu des balises de texte XML."""
    morceaux: list[str] = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        for nom in sorted(z.namelist()):
            if not nom.endswith(".xml") or not nom.startswith(("word/document", "ppt/slides/slide", "xl/sharedStrings")):
                continue
            xml = z.read(nom).decode("utf-8", errors="replace")
            morceaux += re.findall(r"<(?:w:t|a:t|t)(?:\s[^>]*)?>([^<]*)<", xml)
            if sum(len(m) for m in morceaux) > ECHANTILLON:
                break
    return " ".join(morceaux)


def extraire_echantillon(file_bytes: bytes, ext: str) -> str:
    if ext == "txt":
        return file_bytes[: ECHANTILLON * 4].decode("utf-8-sig", errors="replace")
    if ext == "pdf":
        import fitz
        texte = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                texte += page.get_text() + " "
                if len(texte) > ECHANTILLON:
                    break
        return texte
    if ext in ("docx", "pptx", "xlsx"):
        return _texte_office(file_bytes)
    return ""


def detecter_langue(texte: str) -> str | None:
    """Code de base ('en', 'fr'…) de la langue du texte, ou None si incertain."""
    texte = texte[:ECHANTILLON]
    lettres = sum(1 for c in texte if c.isalpha())
    if lettres < 40:
        return None
    for code, motif in ALPHABETS:
        if len(motif.findall(texte)) > lettres * 0.3:
            return code
    mots = re.findall(r"[^\W\d_]+", texte.lower())
    if len(mots) < MOTS_MINIMUM:
        return None
    scores = {code: sum(1 for m in mots if m in liste) for code, liste in MOTS_FREQUENTS.items()}
    classes = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (meilleure, s1), (_, s2) = classes[0], classes[1]
    # Assez de mots reconnus, et une avance nette sur la deuxième langue.
    if s1 < max(5, len(mots) * 0.08) or s1 < s2 * 1.5:
        return None
    return meilleure


def langue_du_document(file_bytes: bytes, ext: str) -> str | None:
    try:
        return detecter_langue(extraire_echantillon(file_bytes, ext))
    except Exception:
        return None
