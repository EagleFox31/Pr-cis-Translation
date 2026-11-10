"""Routes de l'extension navigateur (étude extension §6).

Le texte des pages n'est pas conservé. Les images traduites (hors vidéo)
entrent 30 jours dans un cache partagé, retrouvable seulement en renvoyant
la même image (services/cache_images.py, étude vitesse-images-extension).
Aucun crédit n'est débité : l'extension est limitée par page selon le forfait
(services/limites_page.py, étude extension-gratuite-forfaits) ; seuls des
compteurs par page sont gardés en base, sans contenu.
L'extension appelle depuis son service de fond (permissions d'hôte) : le
CORS du site n'est pas en jeu.
"""
from __future__ import annotations

import re
import base64
import hashlib
import hmac
import secrets
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import EXTENSION_OFFRE, OCR_DELAI_EXTENSION_S, logger
from app.core.database import get_db
from app.api.auth import _aware, _issue
from app.core.security import hash_token, require_auth, revoke_refresh_token
from app.models import ExtensionAuthCode, User, get_plan_priority
from app.rate_limit import rate_limit_decorator
from app.services import extension as ext
from app.services import cache_images, limites_page, ocr_file
from app.services.ocr_v2.detect import LectureEchouee
from app.services.ocr_v2.image import OCTETS_MAX, ImageRefusee, lire_image, traduire_image, verifier

router = APIRouter(prefix="/api/extension", tags=["Extension"])

# Deux images à la fois par utilisateur (étude vitesse-images-extension ;
# auparavant une seule, étude §6) : chacune occupe un cœur pour l'OCR.
PARALLELE = 2
_en_cours: dict[str, int] = {}

_REFUS = {"taille": 413, "pixels": 413, "type": 415, "animee": 415}


class Segments(BaseModel):
    textes: list[str]
    langue: str = "fr"
    titre: str = ""
    contexte: list[str] = []


def _page(request: Request) -> str:
    return limites_page.cle_page(request and request.headers.get("x-page"))


# Limites qu'un forfait supérieur lève (les bornes techniques valent pour tous).
_PAR_FORFAIT = ("texte", "images", "texte_image", "pages_jour")


def _offre(plan, nom: str | None) -> bool:
    """Proposer Starter ou Pro ? Seulement hors bêta, pour une limite que le
    forfait relève, et à qui n'a pas déjà le plus large."""
    return bool(EXTENSION_OFFRE and nom in _PAR_FORFAIT
                and limites_page.bornes(plan) != limites_page.FORFAITS["pro"])


def _refus(nom: str, plan):
    """413 : la limite `nom` est atteinte (étude extension-gratuite-forfaits)."""
    return JSONResponse(status_code=413, content={
        "reason": "page_limit", "limite": nom, "offre": _offre(plan, nom),
        "detail": ("Limite de pages par jour atteinte." if nom == "pages_jour"
                   else "Limite atteinte pour cette page."),
    })


def _limite(request: Request, user: User, **quantites):
    """413 si la page a épuisé une borne technique (lots, analyses, captures)."""
    nom = limites_page.prendre(user.id, _page(request), **quantites)
    return None if nom is None else _refus(nom, user.plan)


@router.post("/segments")
@rate_limit_decorator("60/minute")
async def traduire_segments(request: Request, corps: Segments,
                            current_user: User = Depends(require_auth),
                            db: AsyncSession = Depends(get_db)):
    textes = corps.textes
    if not textes:
        return {"traductions": [], "pages": 0}
    if (len(textes) > ext.SEGMENTS_MAX or sum(map(len, textes)) > ext.CARACTERES_MAX
            or len(corps.titre) + sum(map(len, corps.contexte)) > ext.CONTEXTE_MAX):
        raise HTTPException(status_code=413, detail="Trop de texte pour un seul appel.")
    if refus := _limite(request, current_user, lots=1):
        return refus
    uid, plan, page = current_user.id, current_user.plan, _page(request)
    # Volume de chaque texte nu (sans balises) : la limite du forfait coupe le
    # lot après les premiers blocs qu'elle couvre, le reste reste en original.
    # Un texte que ce compte a déjà fait traduire (page revisitée) ne compte plus.
    vus = await limites_page.deja_vus(db, uid, corps.langue, textes)
    volumes = [0 if t in vus else ext.caracteres([t]) for t in textes]
    total = sum(volumes)
    accorde, limite = 0, None
    if total:
        accorde, _, limite = await limites_page.reserver(db, current_user, page, texte=total)
    n, somme = 0, 0
    for v in volumes:
        if somme + v > accorde:
            break
        somme += v
        n += 1
    if n == 0 and (limite == "pages_jour" or not accorde):
        return _refus(limite, plan)
    try:
        traduits = await run_in_threadpool(
            ext.traduire_textes, textes[:n], corps.langue, None, corps.titre,
            corps.contexte) if n else []
    except ext.TraductionIndisponible as e:
        logger.warning(f"Extension, segments non traduits : {e}")
        await limites_page.rendre(db, uid, page, texte=accorde)
        raise HTTPException(status_code=503, detail="Traduction indisponible. Réessayez.")
    except Exception:
        await limites_page.rendre(db, uid, page, texte=accorde)
        raise
    if accorde > somme:
        # Réservé et pas utilisé (bloc trop gros pour le reste de la limite).
        await limites_page.rendre(db, uid, page, texte=accorde - somme)
    await limites_page.marquer_vus(db, uid, corps.langue, textes[:n])
    limite = limite if n < len(textes) else None
    return {"traductions": traduits + textes[n:], "traduits": n, "limite": limite,
            "offre": _offre(plan, limite), "pages": 0}


# Lectures récentes (analyse puis traduction) : l'analyse ne fait que l'OCR et
# garde les lignes lues ; la traduction et le rendu n'ont lieu que si
# l'utilisateur accepte, sans refaire l'OCR. Un seul worker. Propres à chaque
# compte : une lecture tronquée par le délai ne passe pas d'un compte à l'autre.
RECENTS_MAX = 64
RECENTS_S = 15 * 60
_recents: OrderedDict[str, tuple[float, list]] = OrderedDict()


def _cle_recente(user: User, data: bytes) -> str:
    # Sans la langue : la lecture ne dépend que de l'image.
    return f"{user.id}-{hashlib.sha256(data).hexdigest()}"


def _recent(cle: str) -> list | None:
    entree = _recents.get(cle)
    if entree is None or time.monotonic() - entree[0] > RECENTS_S:
        _recents.pop(cle, None)
        return None
    return entree[1]


def _garder(cle: str, lus: list) -> None:
    maintenant = time.monotonic()
    _recents[cle] = (maintenant, lus)
    _recents.move_to_end(cle)
    # Les plus anciennes en tête : les expirées partent sans attendre d'être relues.
    while _recents and maintenant - next(iter(_recents.values()))[0] > RECENTS_S:
        _recents.popitem(last=False)
    while len(_recents) > RECENTS_MAX:
        _recents.popitem(last=False)


async def _lire_image(file: UploadFile) -> bytes:
    data = await file.read(OCTETS_MAX + 1)
    try:
        verifier(data)
    except ImageRefusee as e:
        raise HTTPException(status_code=_REFUS[e.code], detail=f"Image refusée : {e.code}.")
    return data


def _place_libre(user: User) -> None:
    """429 avant de compter le budget : la reprise ne le consomme pas deux fois."""
    if _en_cours.get(user.id, 0) >= PARALLELE:
        raise HTTPException(status_code=429, detail="Deux images sont déjà en cours.")


def _tour(user: User):
    """Tour au guichet OCR, pris DANS le fil de travail (l'attente ne bloque pas
    la boucle async) ; la traduction réseau se fait hors du guichet."""
    priorite = get_plan_priority(user.plan)
    return lambda: ocr_file.tour(priorite=priorite, delai=OCR_DELAI_EXTENSION_S)


async def _occupe(user: User, fn, *args, **kwargs):
    """Travail d'image (OCR, rendu) : deux à la fois par utilisateur."""
    _place_libre(user)
    _en_cours[user.id] = _en_cours.get(user.id, 0) + 1
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except (LectureEchouee, ext.TraductionIndisponible, ocr_file.OCROccupe) as e:
        logger.warning(f"Extension, image non traduite : {e}")
        raise HTTPException(status_code=503, detail="Image non traduite. Réessayez.")
    finally:
        if (n := _en_cours.pop(user.id, 1) - 1) > 0:
            _en_cours[user.id] = n


async def _produire(user: User, data: bytes, langue: str, cle: str | None,
                    lus: list | None = None) -> dict:
    """Traduction et rendu (OCR aussi si `lus` manque) ; sans débit."""
    rendu = await _occupe(user, traduire_image, data,
                          lambda t: ext.traduire_textes(t, langue), lus=lus,
                          tour=_tour(user))
    logger.info("Extension, image : " + ", ".join(
        f"{k} {v:.1f} s" for k, v in rendu.durees.items()))
    blocs = [{"texte": b.texte, "traduction": b.traduction,
              "boite": list(b.boite), "remplace": b.remplace} for b in rendu.blocs]
    if rendu.remplacee and rendu.complet and cle:
        await run_in_threadpool(cache_images.ecrire, cle, rendu.mime, blocs, rendu.data)
    return {"remplacee": rendu.remplacee, "mime": rendu.mime,
            "image": rendu.data if rendu.remplacee else None, "blocs": blocs}


# Écritures asiatiques (kana, kanji, hangul) : un seul caractère porte déjà du sens.
_ASIATIQUE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")



def a_des_mots(lus) -> bool:
    """Vrai si l'image porte au moins un mot à traduire. Les étiquettes et
    références (« G1 », « 04DID001 », numéros) ne justifient pas une traduction,
    pas plus qu'un mot latin isolé en capitales (marque, logo : « TOYOTA »)."""
    mots = []
    for texte, _ in lus:
        if _ASIATIQUE.search(texte):
            return True
        # Un mot : au moins deux lettres et aucun chiffre, dans n'importe quel alphabet.
        for jeton in texte.split():
            if not any(c.isdigit() for c in jeton) and sum(c.isalpha() for c in jeton) >= 2:
                mots.append(jeton)
    if len(mots) == 1 and mots[0].isupper() and mots[0].isascii():
        return False
    return bool(mots)


def _trop_de_texte(lus, plan) -> bool:
    """Le texte lu dans l'image dépasse le plafond du forfait."""
    plafond = limites_page.bornes(plan)["texte_image"]
    return plafond is not None and sum(len(t) for t, _ in lus) > plafond


def _verdict(lus, plan) -> dict:
    """Le texte lu accompagne le verdict : l'extension en détecte la langue,
    comme pour le texte des pages, et écarte ce qui est déjà dans la langue cible.
    Au-delà du plafond de texte par image du forfait : non traduisible."""
    if not a_des_mots(lus):
        return {"traduisible": False}
    if _trop_de_texte(lus, plan):
        return {"traduisible": False, "limite": "texte_image"}
    return {"traduisible": True, "texte": " ".join(t for t, _ in lus)[:1000]}


@router.post("/image/analyse")
@rate_limit_decorator("60/minute")
async def analyser_une_image(request: Request, file: UploadFile = File(...),
                             langue: str = Form("fr"),
                             current_user: User = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    """Texte présent ou non (OCR seul : ni traduction, ni rendu, rien de compté).
    L'accord n'annonce que les images à texte ; la lecture est gardée pour la
    traduction, faite seulement si l'utilisateur accepte."""
    data = await _lire_image(file)
    plan = current_user.plan
    recente = _cle_recente(current_user, data)
    if (lus := _recent(recente)) is not None:
        return _verdict(lus, plan)
    cle = cache_images.cle(data, langue) if cache_images.ACTIF else None
    if cle and await run_in_threadpool(cache_images.lire, cle):
        return {"traduisible": True}
    _place_libre(current_user)
    if refus := _limite(request, current_user, analyses=1):
        return refus
    if nom := await limites_page.verifier(db, current_user, _page(request), images=True):
        return _refus(nom, plan)
    lus = await _occupe(current_user, lire_image, data, tour=_tour(current_user))
    _garder(recente, lus)
    return _verdict(lus, plan)


@router.post("/image")
# 60 : les images déjà en cache reviennent en quelques ms, deux à la fois.
@rate_limit_decorator("60/minute")
async def traduire_une_image(request: Request, file: UploadFile = File(...),
                             langue: str = Form("fr"), video: bool = Form(False),
                             current_user: User = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    data = await _lire_image(file)
    uid, plan, page = current_user.id, current_user.plan, _page(request)
    cle = cache_images.cle(data, langue) if cache_images.ACTIF and video is not True else None
    recente = _cle_recente(current_user, data) if video is not True else None
    lus = _recent(recente) if recente else None
    connue = (await run_in_threadpool(cache_images.lire, cle)) if cle else None
    if video is True:
        # Vidéo : seule la borne technique des captures, rien en base.
        _place_libre(current_user)
        if refus := _limite(request, current_user, captures=1):
            return refus
        rendu = await _produire(current_user, data, langue, None)
        return _reponse(rendu)
    if connue is not None:
        # Déjà traduite (page revisitée) : ni OCR, ni traduction, rien de compté.
        return _reponse({"remplacee": True, "mime": connue["mime"], "image": connue["image"],
                         "blocs": connue["blocs"]})
    _place_libre(current_user)
    # Une lecture récente est déjà comptée comme analyse ; sinon l'analyse
    # consomme la borne « analyses », plus large que celle des images.
    if lus is None and (refus := _limite(request, current_user, analyses=1)):
        return refus
    # Réservé avant tout rendu : deux envois simultanés ne dépassent pas la
    # limite de la page. Rendu si l'image n'est finalement pas remplacée ou si
    # le travail échoue.
    _, images, limite = await limites_page.reserver(db, current_user, page, images=1)
    if not images:
        return _refus(limite, plan)
    try:
        if lus is None:
            # OCR d'abord, pour appliquer le plafond de texte avant de traduire.
            lus = await _occupe(current_user, lire_image, data, tour=_tour(current_user))
            _garder(recente, lus)
        if _trop_de_texte(lus, plan):
            await limites_page.rendre(db, uid, page, images=1)
            return _reponse({"remplacee": False, "mime": None, "image": None,
                             "blocs": []}, limite="texte_image")
        rendu = await _produire(current_user, data, langue, cle, lus)
    except Exception:
        await limites_page.rendre(db, uid, page, images=1)
        raise
    # Honnêteté : une image non remplacée n'est pas comptée.
    if not rendu["remplacee"]:
        await limites_page.rendre(db, uid, page, images=1)
    return _reponse(rendu)


def _reponse(rendu: dict, limite: str | None = None) -> dict:
    corps = {
        "remplacee": rendu["remplacee"],
        "pages": 0,
        "mime": rendu["mime"],
        "image": base64.b64encode(rendu["image"]).decode() if rendu["remplacee"] else None,
        "blocs": rendu["blocs"],
    }
    if limite:
        corps["limite"] = limite
    return corps


# ── Connexion de l'extension par le site (étude connexion-extension §4) ──────
#
# L'extension ne voit jamais le mot de passe : elle ouvre le site, l'utilisateur
# y autorise le compte, le site délivre un code de 60 s lié au `challenge` (PKCE
# S256) que seule l'extension peut racheter avec son `verifier`.

CODE_VALIDITE_S = 60
_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_VERIFIER = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


class DemandeCode(BaseModel):
    code_challenge: str


class EchangeCode(BaseModel):
    code: str
    code_verifier: str


class Deconnexion(BaseModel):
    refresh_token: str


def _challenge_de(verifier: str) -> str:
    """base64url sans remplissage de SHA-256(verifier) (RFC 7636, méthode S256)."""
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@router.post("/auth/code")
@rate_limit_decorator("10/minute")
async def creer_code(request: Request, corps: DemandeCode,
                     current_user: User = Depends(require_auth),
                     db: AsyncSession = Depends(get_db)):
    """Code à usage unique, après l'accord de l'utilisateur sur le site."""
    if not _CHALLENGE.match(corps.code_challenge):
        raise HTTPException(status_code=400, detail="Requête invalide.")
    if not current_user.email_verified:
        raise HTTPException(status_code=403,
                            detail="Email non vérifié. Vérifiez votre boîte de réception.")
    maintenant = datetime.now(timezone.utc)
    # Les codes périmés ne servent plus à rien : purge au passage.
    await db.execute(delete(ExtensionAuthCode)
                     .where(ExtensionAuthCode.expires_at < maintenant))
    code = secrets.token_urlsafe(32)
    db.add(ExtensionAuthCode(
        code_hash=hash_token(code), user_id=current_user.id,
        code_challenge=corps.code_challenge,
        expires_at=maintenant + timedelta(seconds=CODE_VALIDITE_S)))
    await db.commit()
    return {"code": code, "expires_in": CODE_VALIDITE_S}


@router.post("/auth/token")
@rate_limit_decorator("10/minute")
async def echanger_code(request: Request, corps: EchangeCode,
                        db: AsyncSession = Depends(get_db)):
    """Session de l'extension contre un code et le secret qui l'a engendré."""
    refus = HTTPException(status_code=400, detail="Code invalide ou expiré.")
    if not _VERIFIER.match(corps.code_verifier) or not corps.code or len(corps.code) > 128:
        raise refus
    ligne = (await db.execute(select(ExtensionAuthCode).where(
        ExtensionAuthCode.code_hash == hash_token(corps.code)))).scalar_one_or_none()
    if ligne is None:
        raise refus
    # Usage unique : le code disparaît dès sa première présentation, valide ou non.
    user_id, challenge, echeance = ligne.user_id, ligne.code_challenge, ligne.expires_at
    await db.delete(ligne)
    await db.commit()
    if (_aware(echeance) < datetime.now(timezone.utc)
            or not hmac.compare_digest(_challenge_de(corps.code_verifier), challenge)):
        raise refus
    user = await db.get(User, user_id)
    # L'état du compte a pu changer pendant les 60 s du code.
    if user is None or not user.email_verified:
        raise refus
    return await _issue(db, user, "extension")


@router.post("/auth/deconnexion")
@rate_limit_decorator("20/minute")
async def deconnecter(request: Request, corps: Deconnexion,
                      db: AsyncSession = Depends(get_db)):
    """Ferme la seule session de l'extension ; la réponse ne dit rien du jeton."""
    await revoke_refresh_token(db, corps.refresh_token)
    return {"ok": True}
