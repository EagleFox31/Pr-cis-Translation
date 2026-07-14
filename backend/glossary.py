"""
backend.glossary — Expressions PIÈGES : le calque juste mais pragmatiquement faux.

Problème type : « BREAKING NEWS » en bandeau de journal, rendu « Dernières
minutes ». Le sens y est, l'usage non — un bandeau de presse dit « FLASH INFO »,
« EN DIRECT » ou « ALERTE INFO » selon l'urgence et la diffusion.

CAUSE — le modèle n'a pas le contexte, pas un défaut de connaissance :
chaque paragraphe part SEUL (`{"id": …, "text": "[[0]]BREAKING NEWS[[/0]]"}`),
sans voisins, sans type de document, sans corps de police — alors que le moteur
SAIT que c'est un titre de 60 pt. À température 0,1, le modèle rend donc
toujours le même calque littéral. D'où « systématiquement ».

RÉPONSE — deux régimes, selon ce qu'on peut garantir :

  1. Segment d'AFFICHAGE ISOLÉ (le paragraphe EST l'expression : un bandeau, un
     titre, un bouton) → substitution DÉTERMINISTE (`resolve`). Il n'y a pas de
     phrase à préserver : le rendu se déduit du support, de l'urgence et de la
     présence d'un direct. Testable hors ligne, jamais de régression.
  2. Expression DANS une phrase → consigne CONSULTATIVE (`consigne_for`) jointe
     à l'item : rendus autorisés, rendus interdits, et le POURQUOI. Le modèle
     tranche avec le contexte — une substitution aveugle casserait la phrase
     (« the breaking news was reported at 6pm » n'est pas un bandeau).

Dans les deux cas, `enforce` relit la sortie du modèle et refuse les rendus
`never` (le filet de sécurité : c'est lui qui rend l'erreur impossible, pas le
prompt).

La base est dans `glossary.json` — ajouter une expression = ajouter une entrée,
aucun code à toucher.
"""

import json
import os
import re

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary.json")
_CACHE = {}

# Mots qui font monter l'urgence d'un bandeau (score 1-10).
_URGENT = {
    "alert": 3, "alerte": 3, "urgent": 3, "emergency": 3, "warning": 2,
    "evacuate": 3, "evacuation": 3, "attack": 3, "killed": 3, "dead": 2,
    "crash": 2, "explosion": 3, "earthquake": 3, "storm": 2, "fire": 2,
    "breaking": 2, "just in": 2, "developing": 1, "update": 1,
}
# Marqueurs d'une diffusion EN COURS.
_LIVE = re.compile(
    r"\b(live|en\s+direct|on\s+air|streaming|watch\s+now|now\s+on|direct)\b",
    re.I)

_TAG_RE = re.compile(r"\[\[/?\d+\]\]")


def _plain(text):
    """Texte nu : balises `[[n]]` retirées, espaces normalisés."""
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text or "")).strip()


def load(path=None):
    """Charge (et met en cache) la base. Renvoie {} si elle est absente ou
    illisible — le glossaire est un BONUS, jamais un point de panne."""
    p = path or _PATH
    if p not in _CACHE:
        try:
            with open(p, encoding="utf-8") as f:
                _CACHE[p] = json.load(f)
        except Exception:
            _CACHE[p] = {}
    return _CACHE[p]


def _entries(src="en", tgt="fr", path=None):
    return load(path).get(f"{src}->{tgt}", [])


def _match_re(form):
    """Forme source bornée au mot (« issue » ne doit pas matcher « tissue »)."""
    return re.compile(r"(?<!\w)" + re.escape(form) + r"(?!\w)", re.I)


def find_traps(text, src="en", tgt="fr", path=None):
    """Entrées du glossaire présentes dans `text`. Le texte peut être balisé."""
    plain = _plain(text)
    if not plain:
        return []
    hits = []
    for e in _entries(src, tgt, path):
        if any(_match_re(f).search(plain) for f in e.get("match", [])):
            hits.append(e)
    return hits


def urgency_score(text, context=""):
    """Urgence perçue du segment, de 1 (neutre) à 10 (alerte). Somme des poids
    des mots d'urgence trouvés, majorée si le segment est en CAPITALES (un
    bandeau crie) ou ponctué d'un point d'exclamation."""
    blob = f"{_plain(text)} {_plain(context)}".lower()
    score = 1
    for word, w in _URGENT.items():
        if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", blob):
            score += w
    core = _plain(text)
    letters = [c for c in core if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 2:
        score += 2                          # bandeau en capitales
    if "!" in core:
        score += 1
    return max(1, min(10, score))


def is_live(text, context=""):
    """Le segment annonce-t-il une diffusion EN COURS ?"""
    return bool(_LIVE.search(f"{_plain(text)} {_plain(context)}"))


def is_standalone(text, entry):
    """Le paragraphe EST-IL l'expression (à la ponctuation près) ? C'est la
    condition d'une substitution déterministe : il n'y a alors aucune phrase
    autour à préserver."""
    plain = _plain(text)
    for form in entry.get("match", []):
        stripped = re.sub(r"^[\W_]+|[\W_]+$", "", plain)
        if stripped.casefold() == form.casefold():
            return True
    return False


def resolve(entry, text, support="corps", context=""):
    """Rendu à retenir pour `entry`, d'après le support, l'urgence et le direct.

    Parcourt les options dans l'ordre (du plus spécifique au plus neutre) et
    retient la première dont TOUTES les conditions sont remplies. Une option
    sans condition est un repli et convient toujours.
    """
    live = is_live(text, context)
    score = urgency_score(text, context)
    for opt in entry.get("options", []):
        if opt.get("support") and opt["support"] != support:
            continue
        if opt.get("live") and not live:
            continue
        if opt.get("urgency_min") and score < opt["urgency_min"]:
            continue
        return opt["rendering"]
    return None


def _case_like(rendering, source_fragment):
    """Aligne la casse du rendu sur celle de la source (un bandeau tout en
    capitales reste en capitales)."""
    letters = [c for c in source_fragment if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 2:
        return rendering.upper()
    return rendering


def substitute(text, entry, support="corps", context=""):
    """Remplace l'expression par le rendu résolu, EN PLACE et en conservant les
    balises `[[n]]` (on ne touche qu'au texte entre elles). Retourne le texte
    inchangé si aucun rendu ne s'applique."""
    rendering = resolve(entry, text, support, context)
    if not rendering:
        return text
    out = text
    for form in entry.get("match", []):
        rx = _match_re(form)

        def _sub(m):
            return _case_like(rendering, m.group(0))

        # Ne substituer QUE hors des balises : on découpe sur les balises et on
        # ne traite que les tranches de texte.
        parts = _TAG_RE.split(out)
        tags = _TAG_RE.findall(out)
        parts = [rx.sub(_sub, p) for p in parts]
        rebuilt = parts[0]
        for i, t in enumerate(tags):
            rebuilt += t + parts[i + 1]
        out = rebuilt
    return out


def consigne_for(text, support="corps", context="", src="en", tgt="fr",
                 path=None):
    """Consigne CONSULTATIVE à joindre à l'item envoyé au modèle : pour chaque
    piège détecté, les rendus autorisés, les rendus interdits et la raison.
    Retourne None si le segment ne contient aucun piège (cas de l'immense
    majorité des paragraphes : coût nul)."""
    # `hint: false` = entrée MUETTE. Le banc d'essai (2026-07-13) a montré que le
    # modèle traduit seul, correctement et de façon stable (3/3), la plupart des
    # entrées : leur consigne ne fait que payer des jetons pour un conseil déjà
    # suivi. On ne fait donc parler que celles qui changent réellement la sortie
    # (`breaking-news` : sans elle, aucune distinction direct/alerte/affiche ;
    # `developing-story` : contresens 2 fois sur 3). Leur filet `never`, lui,
    # reste actif pour TOUTES — il ne coûte rien et couvre un changement de modèle.
    traps = [e for e in find_traps(text, src, tgt, path)
             if e.get("hint", True)]
    if not traps:
        return None
    live = is_live(text, context)
    score = urgency_score(text, context)
    lines = [
        "TERMINOLOGIE — ce fragment contient une expression PIÈGE dont la "
        "traduction littérale serait pragmatiquement fausse. "
        f"Support : {support}. Urgence : {score}/10. "
        f"Diffusion en direct : {'oui' if live else 'non'}."
    ]
    for e in traps:
        forms = " / ".join(e.get("match", []))
        opts = " · ".join(
            f"« {o['rendering'] } » ({o.get('when', '')})"
            for o in e.get("options", []))
        lines.append(f"— « {forms} » → choisis parmi : {opts}.")
        if e.get("never"):
            banned = ", ".join(f"« {n} »" for n in e["never"])
            lines.append(f"  INTERDIT : {banned}.")
        if e.get("note"):
            lines.append(f"  Raison : {e['note']}")
    return "\n".join(lines)


def enforce(src_text, out_text, support="corps", context="", src="en", tgt="fr",
            path=None):
    """FILET DE SÉCURITÉ — relit la traduction rendue par le modèle.

    Si elle contient un rendu INTERDIT (« dernières minutes »), on le remplace
    par le rendu résolu pour ce contexte. C'est cette passe, et non le prompt,
    qui rend l'erreur impossible : un prompt se néglige, une vérification non.

    Retourne (texte_corrigé, [ids des entrées corrigées]).
    """
    if not out_text:
        return out_text, []
    fixed = out_text
    touched = []
    for e in find_traps(src_text, src, tgt, path):
        rendering = resolve(e, src_text, support, context)
        if not rendering:
            continue
        for banned in e.get("never", []):
            rx = _match_re(banned)
            if rx.search(_plain(fixed)):
                parts = _TAG_RE.split(fixed)
                tags = _TAG_RE.findall(fixed)
                parts = [rx.sub(lambda m: _case_like(rendering, m.group(0)), p)
                         for p in parts]
                rebuilt = parts[0]
                for i, t in enumerate(tags):
                    rebuilt += t + parts[i + 1]
                fixed = rebuilt
                if e["id"] not in touched:
                    touched.append(e["id"])
    return fixed, touched
