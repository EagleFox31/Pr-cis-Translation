"""
Client Campay — encaissement mobile money (MTN MoMo, Orange Money).

**Pourquoi pas le SDK officiel `campay` (PyPI).** Il appelle `requests` avec
`verify=False` sur *tous* ses endpoints, jeton d'authentification compris : la
vérification du certificat TLS est désactivée, donc n'importe qui en position
d'intercepter le trafic peut lire nos identifiants marchand et rejouer nos
encaissements. Il est aussi entièrement synchrone et attend en boucle bloquante
(`while status == "PENDING"`), ce qui figerait la boucle d'événements — le
problème même qu'on vient de corriger ailleurs.

Ce client parle donc directement à la même API HTTP, en asynchrone et avec la
vérification TLS active.

Endpoints (relevés dans le SDK officiel v1.1.0, 19/07/2026) :
  POST /api/token/            {username, password}          → {token}
  POST /api/collect/          {amount, currency, from, description, external_reference}
                                                            → {reference, ussd_code, operator}
  GET  /api/transaction/<ref> Authorization: Token <token>   → {status, ...}
"""
from __future__ import annotations

import functools
import hmac
import logging
import os
import time

import httpx
import jwt

logger = logging.getLogger(__name__)

# Codes d'erreur Campay, traduits pour l'utilisateur. Renvoyer « ER101 » à
# quelqu'un qui vient de taper son numéro ne l'aide pas à le corriger.
ERROR_MESSAGES = {
    "ER101": "Numéro invalide — indiquez l'indicatif pays (237…).",
    "ER102": "Opérateur non pris en charge : seuls MTN et Orange sont acceptés.",
    "ER201": "Montant invalide : les centimes ne sont pas acceptés en FCFA.",
    "ER301": "Solde insuffisant.",
}

DEMO_HOST = "https://demo.campay.net"
PROD_HOST = "https://www.campay.net"

# Campay ne connaît que le franc CFA. Une zone tarifaire qui facture en EUR ou
# en USD ne peut PAS être encaissée ici — il lui faut un autre fournisseur.
SUPPORTED_CURRENCY = "XAF"


def normalize_phone(raw: str, default_cc: str = "237") -> str:
    """Met un numéro saisi à la main au format attendu par Campay.

    Campay exige l'indicatif pays et refuse tout le reste par ER101 — mesuré :
    `698358935` (la façon dont un Camerounais écrit son numéro) est rejeté,
    `237698358935` passe. Laisser l'utilisateur découvrir ça par un message
    d'erreur, c'est perdre un paiement sur un détail de présentation.

    On ne devine RIEN d'ambigu : seuls les 9 chiffres du plan de numérotation
    camerounais (commençant par 6) reçoivent l'indicatif. Un numéro déjà
    préfixé, ou d'un autre pays, passe intact — mieux vaut une erreur de Campay
    qu'un préfixe inventé qui enverrait l'argent ailleurs.
    """
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 9 and digits.startswith("6"):
        return default_cc + digits
    return digits


class ProviderError(RuntimeError):
    """Échec d'un appel à un prestataire de paiement, quel qu'il soit.

    Les routes n'attrapent que celle-ci : un nouveau prestataire n'a pas à
    leur apprendre le nom de ses propres erreurs."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or (
            "Le paiement n'a pas pu être initié. Réessayez."
        )


class CampayError(ProviderError):
    """Échec d'un appel Campay.

    `message` va aux journaux (il peut contenir des détails de l'API) ;
    `user_message` est ce qu'on peut montrer sans rien divulguer — et surtout
    ce qui permet à l'utilisateur de CORRIGER. « ER101 » ne dit à personne
    qu'il a oublié l'indicatif pays.
    """


def _as_campay_error(fn):
    """Convertit toute panne de transport en `CampayError`.

    Mesuré, pas supposé : une interrogation d'état a levé `httpx.ReadTimeout`
    en conditions réelles. Or les appelants ne rattrapent que `CampayError` —
    ce timeout serait donc remonté en HTTP 500 au client, EN PLEIN paiement,
    au moment précis où il attend de savoir si son argent est parti.

    Un décorateur et pas trois `try` recopiés : la prochaine méthode ajoutée
    est couverte par construction, alors qu'une recopie s'oublie.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except CampayError:
            raise                                  # déjà qualifiée
        except httpx.HTTPError as e:
            # `HTTPError` couvre timeouts, connexions refusées, erreurs TLS et
            # réponses illisibles — tout ce que le réseau sait rater.
            raise CampayError(
                f"{type(e).__name__} vers Campay : {e}",
                "Le service de paiement ne répond pas. Réessayez dans un instant.",
            ) from e
        except ValueError as e:
            # `res.json()` sur une réponse qui n'est pas du JSON (page d'erreur
            # HTML d'un proxy, typiquement).
            raise CampayError(f"réponse Campay illisible : {e}") from e
    return wrapper


class CampayClient:
    def __init__(self) -> None:
        self.username = os.getenv("CAMPAY_USERNAME", "")
        self.password = os.getenv("CAMPAY_PASSWORD", "")
        # Production sur demande EXPLICITE. Un défaut à « PROD » ferait qu'un
        # oubli de configuration encaisse de l'argent réel pendant les tests ;
        # l'inverse ne fait rien de grave.
        self.host = PROD_HOST if os.getenv("CAMPAY_ENV") == "PROD" else DEMO_HOST
        self._token: str | None = None
        self._token_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)

    @_as_campay_error
    async def _get_token(self, client: httpx.AsyncClient) -> str:
        # Le jeton temporaire de Campay vit une heure. On le garde 50 minutes :
        # redemander un jeton à chaque encaissement double le nombre d'allers-
        # retours, et le garder jusqu'à la dernière seconde le fait expirer en
        # vol sur les paiements lents.
        if self._token and (time.monotonic() - self._token_at) < 3000:
            return self._token

        res = await client.post(
            f"{self.host}/api/token/",
            json={"username": self.username, "password": self.password},
        )
        if res.status_code != 200:
            raise CampayError(f"jeton refusé ({res.status_code})")
        token = res.json().get("token")
        if not token:
            raise CampayError("réponse de jeton sans champ `token`")
        self._token, self._token_at = token, time.monotonic()
        return token

    @_as_campay_error
    async def collect(self, *, amount: int, phone: str, description: str,
                      external_reference: str) -> dict:
        """Déclenche la demande de paiement. NE BLOQUE PAS jusqu'au résultat.

        L'utilisateur reçoit une invite USSD sur son téléphone et saisit son
        code. Ça prend le temps que ça prend — parfois plus d'une minute. On
        rend donc la main tout de suite avec la référence, et l'état se suit
        par `transaction_status` ou par le webhook.

        `amount` est en francs CFA entiers (le XAF n'a pas de subdivision).
        """
        if not self.configured:
            raise CampayError("CAMPAY_USERNAME / CAMPAY_PASSWORD absents")

        async with httpx.AsyncClient(timeout=30.0) as client:   # verify=True par défaut
            token = await self._get_token(client)
            res = await client.post(
                f"{self.host}/api/collect/",
                json={
                    "amount": str(amount),
                    "currency": SUPPORTED_CURRENCY,
                    "from": phone,
                    "description": description,
                    # Notre identifiant à nous. C'est lui qui permet de
                    # retrouver le paiement si la réponse se perd en route.
                    "external_reference": external_reference,
                },
                headers={"Authorization": f"Token {token}"},
            )
            if res.status_code != 200:
                # Campay renvoie un code (ER101…) qu'on traduit en conseil
                # actionnable ; tout le reste reste dans les journaux.
                brut = res.text[:200]
                code = next((c for c in ERROR_MESSAGES if c in brut), None)
                raise CampayError(
                    f"collect refusé ({res.status_code}) : {brut}",
                    ERROR_MESSAGES.get(code) if code else None,
                )
            data = res.json()
            if not data.get("reference"):
                raise CampayError("collect sans référence")
            return data

    @_as_campay_error
    async def transaction_status(self, reference: str) -> dict:
        """État d'une transaction. PENDING · SUCCESSFUL · FAILED."""
        if not self.configured:
            raise CampayError("CAMPAY_USERNAME / CAMPAY_PASSWORD absents")

        async with httpx.AsyncClient(timeout=20.0) as client:
            token = await self._get_token(client)
            # Barre oblique FINALE obligatoire : la doc écrit
            # `/api/transaction/(reference)/`. Le SDK officiel l'omet et s'en
            # tire parce que `requests` suit les redirections ; httpx ne les
            # suit PAS par défaut, on aurait donc lu un 301 comme un échec de
            # statut — c'est-à-dire un paiement réussi vu comme en attente,
            # jusqu'à l'expiration.
            res = await client.get(
                f"{self.host}/api/transaction/{reference}/",
                headers={"Authorization": f"Token {token}"},
            )
            if res.status_code != 200:
                raise CampayError(f"statut indisponible ({res.status_code})")
            return res.json()


    # ── Signature du webhook ────────────────────────────────────────────────

    def verify_webhook_signature(self, signature: str) -> bool:
        """La notification vient-elle BIEN de Campay ?

        Campay joint au rappel un JWT signé en HS256 avec la « webhook key » de
        l'application, dont la charge utile porte `source: "campay"`. C'est la
        seule preuve d'origine disponible : le point d'entrée est public, tout
        le reste du corps est déclaratif.

        Sans `CAMPAY_WEBHOOK_KEY` configurée, on renvoie False — donc on refuse.
        Traiter une clé absente comme « signature valide » transformerait un
        oubli de configuration en porte ouverte, silencieusement.
        """
        key = os.getenv("CAMPAY_WEBHOOK_KEY", "")
        if not key or not signature:
            return False
        try:
            # PyJWT vérifie la signature ET l'expiration (`exp`) ; on exige en
            # plus l'émetteur annoncé par la doc.
            payload = jwt.decode(signature, key, algorithms=["HS256"])
        except jwt.PyJWTError as e:
            logger.warning("Signature de webhook Campay rejetée : %s", e)
            return False
        return str(payload.get("source", "")).lower() == "campay"


campay = CampayClient()


# ── Fapshi ──────────────────────────────────────────────────────────────────
#
# Doc officielle relevée le 20/10/2026 (docs.fapshi.com/en) :
#   POST /direct-pay              {amount, phone, medium?, externalId?, message?}
#                                                     → {message, transId, dateInitiated}
#   GET  /payment-status/<transId>                    → transaction {status, amount, ...}
#   en-têtes `apiuser` / `apikey` sur chaque appel ; erreurs 4XX {"message": ...}
#
# Ce qu'on ne devine pas :
#   - `direct-pay` (invite USSD poussée) est DÉSACTIVÉ par défaut en live, il
#     s'active auprès de Fapshi ; sans lui, 4XX à chaque encaissement ;
#   - le téléphone s'écrit SANS indicatif (`67XXXXXXX`) ;
#   - `payment-status` est limité à 6 appels/minute par transaction (429 au-delà),
#     alors que l'écran d'attente interroge toutes les 3 s ;
#   - le webhook n'est pas signé : seul un secret partagé arrive en en-tête
#     `x-wh-secret`. Il ne sert donc qu'à savoir QUOI re-vérifier.

FAPSHI_SANDBOX_HOST = "https://sandbox.fapshi.com"
FAPSHI_LIVE_HOST = "https://live.fapshi.com"

# Statuts Fapshi → les trois que connaissent les routes et l'écran d'attente.
# CREATED : invite pas encore traitée ; EXPIRED : jamais payé, définitif.
FAPSHI_STATUS = {"CREATED": "PENDING", "PENDING": "PENDING",
                 "SUCCESSFUL": "SUCCESSFUL", "FAILED": "FAILED",
                 "EXPIRED": "FAILED"}

# Sous la limite de 6 appels/minute par transaction, webhook compris.
FAPSHI_STATUS_MIN_INTERVAL = 12.0


class FapshiError(ProviderError):
    """Échec d'un appel Fapshi (voir `CampayError` pour les deux messages)."""


def _as_fapshi_error(fn):
    """Même rôle que `_as_campay_error` : aucune panne réseau ne doit remonter
    en HTTP 500 pendant qu'un client attend de savoir si son argent est parti."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except FapshiError:
            raise
        except httpx.HTTPError as e:
            raise FapshiError(
                f"{type(e).__name__} vers Fapshi : {e}",
                "Le service de paiement ne répond pas. Réessayez dans un instant.",
            ) from e
        except ValueError as e:
            raise FapshiError(f"réponse Fapshi illisible : {e}") from e
    return wrapper


def fapshi_phone(phone: str) -> str:
    """Numéro au format Fapshi : les 9 chiffres nationaux, sans indicatif.
    `normalize_phone` l'a mis au format international pour notre base."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 12 and digits.startswith("237"):
        return digits[3:]
    return digits


class FapshiClient:
    def __init__(self) -> None:
        self.api_user = os.getenv("FAPSHI_API_USER", "")
        self.api_key = os.getenv("FAPSHI_API_KEY", "")
        # Live sur demande EXPLICITE, comme Campay : un oubli ne doit pas
        # encaisser d'argent réel. Les clés sandbox et live sont distinctes.
        self.host = (FAPSHI_LIVE_HOST if os.getenv("FAPSHI_ENV", "").upper() == "LIVE"
                     else FAPSHI_SANDBOX_HOST)
        # transId → (instant, dernier statut) : de quoi répondre sans rappeler
        # Fapshi quand l'écran d'attente interroge plus vite que la limite.
        self._last_status: dict[str, tuple[float, dict]] = {}

    @property
    def configured(self) -> bool:
        return bool(self.api_user and self.api_key)

    def _headers(self) -> dict:
        return {"apiuser": self.api_user, "apikey": self.api_key}

    @staticmethod
    def _error(res: httpx.Response, what: str) -> FapshiError:
        try:
            detail = str(res.json().get("message", ""))[:200]
        except ValueError:
            detail = res.text[:200]
        user_message = None
        if res.status_code == 403:
            # Identifiants faux ou IP de serveur absente de la liste blanche :
            # rien que le client puisse corriger, mais l'exploitant doit le lire.
            logger.error("Fapshi refuse l'accès (403) : identifiants ou IP non autorisée")
        elif res.status_code == 400 and "phone" in detail.lower():
            user_message = "Numéro invalide : seuls les numéros MTN et Orange du Cameroun sont acceptés."
        return FapshiError(f"{what} refusé ({res.status_code}) : {detail}", user_message)

    @_as_fapshi_error
    async def direct_pay(self, *, amount: int, phone: str, message: str,
                         external_id: str) -> dict:
        """Pousse l'invite de paiement sur le téléphone. NE BLOQUE PAS : l'état
        se suit par `payment_status` ou par le webhook."""
        if not self.configured:
            raise FapshiError("FAPSHI_API_USER / FAPSHI_API_KEY absents")
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{self.host}/direct-pay",
                json={"amount": int(amount), "phone": fapshi_phone(phone),
                      "message": message,
                      # Notre identifiant : retrouver le paiement si la réponse
                      # se perd (motif imposé ^[a-zA-Z0-9\-_]{1,100}$, un UUID passe).
                      "externalId": external_id},
                headers=self._headers(),
            )
            if res.status_code != 200:
                raise self._error(res, "direct-pay")
            data = res.json()
            if not data.get("transId"):
                raise FapshiError("direct-pay sans transId")
            return data

    @_as_fapshi_error
    async def initiate_pay(self, *, amount: int, message: str,
                           external_id: str, email: str | None = None,
                           user_id: str | None = None) -> dict:
        """Crée un lien vers la page de paiement hébergée par Fapshi : le client
        y choisit MTN ou Orange et y saisit son numéro. Ouvert à tout compte,
        contrairement à `direct-pay` qui exige l'accord de Fapshi. Le lien
        expire au bout de 24 h ; l'état se suit comme pour direct-pay.
        L'e-mail fourni est le seul champ que la page sait pré-remplir (elle
        ne le redemande pas) ; le numéro, elle le demande toujours."""
        if not self.configured:
            raise FapshiError("FAPSHI_API_USER / FAPSHI_API_KEY absents")
        body = {"amount": int(amount), "message": message,
                "externalId": external_id}
        if email:
            body["email"] = email
        if user_id:
            body["userId"] = user_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{self.host}/initiate-pay",
                json=body,
                headers=self._headers(),
            )
            if res.status_code != 200:
                raise self._error(res, "initiate-pay")
            data = res.json()
            if not data.get("transId") or not data.get("link"):
                raise FapshiError("initiate-pay sans transId ou sans lien")
            return data

    @_as_fapshi_error
    async def payment_status(self, trans_id: str) -> dict:
        """Transaction Fapshi (statut brut CREATED · PENDING · SUCCESSFUL ·
        FAILED · EXPIRED). Mis en cache quelques secondes, voir la limite."""
        if not self.configured:
            raise FapshiError("FAPSHI_API_USER / FAPSHI_API_KEY absents")
        now = time.monotonic()
        cached = self._last_status.get(trans_id)
        if cached and now - cached[0] < FAPSHI_STATUS_MIN_INTERVAL:
            return cached[1]
        async with httpx.AsyncClient(timeout=20.0) as client:
            # GET SANS corps : Fapshi rejette un GET qui en porte un.
            res = await client.get(f"{self.host}/payment-status/{trans_id}",
                                   headers=self._headers())
            if res.status_code != 200:
                raise self._error(res, "payment-status")
            data = res.json()
        if FAPSHI_STATUS.get(data.get("status")) == "PENDING":
            self._last_status[trans_id] = (now, data)
        else:
            self._last_status.pop(trans_id, None)   # final : plus rien à mettre de côté
        return data

    def forget_status(self, trans_id: str) -> None:
        self._last_status.pop(trans_id, None)

    @staticmethod
    def verify_webhook_secret(received: str | None) -> bool:
        """L'en-tête `x-wh-secret` porte-t-il le secret du tableau de bord ?
        Sans `FAPSHI_WEBHOOK_SECRET`, on refuse (un oubli ne doit pas ouvrir la
        porte). Comparaison à temps constant."""
        secret = os.getenv("FAPSHI_WEBHOOK_SECRET", "")
        if not secret or not received:
            return False
        return hmac.compare_digest(received.encode(), secret.encode())


fapshi = FapshiClient()
