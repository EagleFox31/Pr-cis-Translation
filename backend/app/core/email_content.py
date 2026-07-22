"""Ce que disent les e-mails, et dans quelle langue.

SÉPARÉ DE L'ENVOI, ET C'EST VOULU
---------------------------------
`email.py` sait parler à un serveur SMTP. Ce module-ci sait ce qu'on écrit. Les
mélanger obligeait à relire une fonction d'envoi pour corriger une virgule, et
rendait les textes intestables sans serveur.

LA LANGUE
---------
Celle de l'INTERFACE au moment où l'utilisateur a agi, transmise par l'en-tête
`Accept-Language`. Pas celle du navigateur : quelqu'un dont le système est en
anglais mais qui a mis Précis en français attend un e-mail en français — c'est
la langue dans laquelle il vient de lire le bouton sur lequel il a cliqué.

Repli sur le français, langue par défaut de l'interface.

DES MESSAGES COURTS
-------------------
Un e-mail transactionnel a UN travail : faire agir. Chaque phrase qui n'y
concourt pas éloigne du code. L'ancien message expliquait en trois paragraphes
ce que le code affiché disait déjà.
"""
from __future__ import annotations

LANGUE_DEFAUT = "fr"
LANGUES = ("fr", "en")

#: Identité de marque, alignée sur l'interface (`frontend/src`).
MARQUE = {
    "nom": "Précis",
    "bleu": "#1a4dc7",
    "bleu_clair": "#3b82f6",
    "encre": "#0f172a",
    "gris": "#64748b",
    "gris_clair": "#94a3b8",
    "trait": "#e2e8f0",
    "fond": "#f1f5f9",
}

TEXTES: dict[str, dict[str, str]] = {
    "fr": {
        "sujet_verification": "{code} — votre code Précis",
        "bandeau": "Vérification",
        "titre": "Votre code de connexion",
        "sous_titre": "Il expire dans 15 minutes.",
        "bouton": "Se connecter",
        "ou": "ou saisissez ce code",
        "ignorer": "Vous n'avez rien demandé ? Ignorez cet e-mail.",
        "auto": "Message automatique — merci de ne pas y répondre.",
        "texte_brut": (
            "Votre code Précis : {code}\n"
            "Il expire dans 15 minutes.\n\n"
            "Se connecter : {url}\n\n"
            "Vous n'avez rien demandé ? Ignorez cet e-mail."
        ),
    },
    "en": {
        "sujet_verification": "{code} — your Précis code",
        "bandeau": "Verification",
        "titre": "Your sign-in code",
        "sous_titre": "It expires in 15 minutes.",
        "bouton": "Sign in",
        "ou": "or enter this code",
        "ignorer": "Didn't request this? Just ignore this email.",
        "auto": "Automated message — please do not reply.",
        "texte_brut": (
            "Your Précis code: {code}\n"
            "It expires in 15 minutes.\n\n"
            "Sign in: {url}\n\n"
            "Didn't request this? Just ignore this email."
        ),
    },
}


def normaliser_langue(accept_language: str | None) -> str:
    """Langue à employer, depuis un en-tête `Accept-Language`.

    On lit la PREMIÈRE langue proposée et on ne garde que son code primaire :
    `fr-CA` comme `fr-FR` reçoivent le français. Les facteurs de qualité (`;q=`)
    sont ignorés à dessein — le frontend envoie SA langue, une seule, et
    trancher entre `q=0.9` et `q=0.8` sur une valeur que nous produisons
    nous-mêmes serait de la complexité sans objet.

    Toute langue inconnue retombe sur le français.
    """
    if not accept_language:
        return LANGUE_DEFAUT
    premier = accept_language.split(",")[0].split(";")[0].strip().lower()
    primaire = premier.split("-")[0]
    return primaire if primaire in LANGUES else LANGUE_DEFAUT


def textes(langue: str) -> dict[str, str]:
    """Les textes d'une langue, français par défaut."""
    return TEXTES.get(langue, TEXTES[LANGUE_DEFAUT])
