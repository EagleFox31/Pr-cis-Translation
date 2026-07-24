"""Le contrat que tout moteur de traduction doit honorer.

CE QU'EST UN MOTEUR
-------------------
Un moteur sait faire deux choses sur UN format de fichier, et rien d'autre :

  1. `extract_text`  — sortir le texte d'un document en préservant tout ce qui
     permettra de le remettre exactement à sa place (balises de runs, styles,
     géométrie). Il écrit ce relevé dans un JSON.
  2. `inject_translation` — reprendre ce JSON une fois traduit et reconstruire
     un document identique à l'original, au texte près.

CE QU'UN MOTEUR NE FAIT JAMAIS
------------------------------
Il n'importe pas l'application, ne lit pas la base, n'écrit pas en session, ne
connaît ni les comptes ni les forfaits, et ne décide de rien qui concerne le
service. C'était pourtant le cas : le moteur PPTX faisait `from app import
_preview_lock`, avec un import tardif pour éviter le cycle. Un moteur qui
importe son application ne peut plus en sortir — ni pour un autre projet, ni
pour un banc d'essai.

Les dépendances vont donc dans UN seul sens :

    app.api  ->  app.services  ->  engines  ->  (rien du projet)

Un moteur qui a besoin d'une ressource partagée — LibreOffice, par exemple —
la reçoit d'`app.services.office`, qui ne dépend de personne.

UNE INSTANCE PAR OPÉRATION
--------------------------
`self.temp_dir` fait de chaque moteur un objet à ÉTAT. Une instance partagée
entre deux traductions simultanées les fait écrire dans le même dossier : on a
demandé l'anglais et reçu le portugais, et un aperçu ouvert pendant une
traduction supprimait le dossier temporaire du travail en cours. Le registre
ci-dessous ne rend donc jamais une instance, seulement une CLASSE — c'est à
l'appelant d'en construire une, et de n'en construire qu'une par opération.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

ProgressCallback = Callable[[str], None]


class TranslationEngine(ABC):
    """Interface commune aux moteurs PDF, PPTX et DOCX."""

    #: Extension de fichier prise en charge, sans point (« pptx »).
    extension: str = ""

    @abstractmethod
    def extract_text(self, input_path: str, output_json: str,
                     filters: dict | None = None,
                     progress_callback: ProgressCallback | None = None):
        """Relève le texte de `input_path` dans `output_json`.

        Retourne `(extraction, chemin_json)`. Le relevé doit contenir tout ce
        qu'il faut pour reconstruire : perdre une information ici, c'est la
        perdre définitivement — l'injection ne relit jamais l'original pour
        rattraper ce que l'extraction a laissé.
        """

    @abstractmethod
    def inject_translation(self, original_path: str, translated_json: str,
                           output_path: str,
                           format_options: dict | None = None,
                           progress_callback: ProgressCallback | None = None
                           ) -> tuple[bool, str]:
        """Reconstruit le document traduit dans `output_path`.

        Retourne `(succès, message)`. Le message est destiné à l'utilisateur en
        cas d'échec : il doit dire ce qui s'est passé, pas où.
        """
