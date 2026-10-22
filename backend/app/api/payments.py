"""
Routes de paiement — achat de pages à l'unité (forfait Gratuit).

Règle du produit, telle que décidée : le forfait Gratuit a droit à UNE
traduction offerte par mois, qu'il peut lancer et regarder en aperçu masqué.
Tout le reste se paie À LA PAGE, et se paie AVANT. Ce qui est payé devient
visible en clair et téléchargeable ; rien d'autre ne l'est.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User, Document, Payment, get_plan_storage
from app.core.security import require_auth
from app.core.pricing import (zone_for_country, CURRENCY, page_price,
                               billable_pages, min_payment_amount, plan_price,
                               PLAN_RANK, SELF_SERVE_PLANS, transaction_fee)
from app.services.usage import add_months
from app.services.documents import count_pages
from app.core.payment_gateway import (campay, CampayError, ProviderError,
                                      fapshi, normalize_phone, paddle)
from app.core.payment_methods import (CARD, MTN_MOMO, PHONE_METHODS, PROVIDERS,
                                      list_methods, method_of_phone, needs_phone,
                                      provider_for)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Paiements"])

# Garde-fou : un achat porte sur un document réel, pas sur une commande d'un
# million de pages tapée dans la console du navigateur.
MAX_PAGES_PER_PAYMENT = 500


def _zone_of(request: Request, override: str | None = None) -> str:
    return zone_for_country(
        override
        or request.headers.get("CF-IPCountry")
        or request.headers.get("X-Country")
    )


async def _owned_unpaid_document(db: AsyncSession, user: User,
                                 document_id: str | None) -> Document | None:
    if not document_id:
        return None
    doc = await db.get(Document, document_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if doc.paid:
        raise HTTPException(status_code=409, detail="Ce document est déjà payé.")
    return doc


async def _document_pages(db: AsyncSession, doc: Document) -> int | None:
    """Taille du document selon le SERVEUR, recomptée depuis le fichier si
    elle n'a jamais été enregistrée.

    Sans elle, le prix retomberait sur le nombre envoyé par le navigateur, et
    `_apply_credit` ne saurait plus quelle part du paiement dépasse le
    document : le surplus serait perdu pour le client.
    """
    if doc.page_count:
        return doc.page_count
    path = doc.original_path
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()

    def _lire() -> int:
        with open(path, "rb") as f:
            return count_pages(f.read(), ext)

    try:
        doc.page_count = await run_in_threadpool(_lire)
    except ValueError as exc:
        # Même réponse qu'au dépôt (`translate.py`) : fichier sans texte ou
        # Office invalide, rien à chiffrer.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return doc.page_count


class QuoteBody(BaseModel):
    pages: int = Field(..., ge=1, le=MAX_PAGES_PER_PAYMENT)
    # Même règle qu'à l'encaissement : un document identifié se chiffre à SA
    # taille, sinon le devis et le débit divergeraient.
    document_id: str | None = None


@router.post("/quote")
async def quote(body: QuoteBody, request: Request, user: User = Depends(require_auth),
                db: AsyncSession = Depends(get_db)):
    """Ce que coûtera la traduction, AVANT de la lancer.

    Le prix est annoncé ici et refacturé à l'identique à l'encaissement : le
    montant que l'utilisateur voit est celui qui sera débité, jamais un autre.
    """
    zone = _zone_of(request)
    unit = page_price(zone)
    doc = await _owned_unpaid_document(db, user, body.document_id)
    pages = (await _document_pages(db, doc) if doc is not None else None) or body.pages
    billed = billable_pages(zone, pages)
    card_billed = billable_pages(zone, pages, CARD)
    return {
        "pages": pages,
        # Peut dépasser `pages` : le montant minimum de l'opérateur l'impose.
        # Le surplus est crédité au compte (cf. `_apply_credit`).
        "billed_pages": billed,
        "unit_price": unit,
        # `amount` = ce qui sera DÉBITÉ, frais compris ; `subtotal` + `fee` le
        # détaillent. Même calcul que `POST /` : le devis ne promet rien d'autre.
        **_with_fee(unit * billed, zone),
        "min_amount": min_payment_amount(zone),
        # Minimum et frais de la carte (Paddle) sont plus hauts : la fenêtre
        # bascule sur ces chiffres quand la carte est choisie, sans redemander
        # de devis.
        "card": {
            "billed_pages": card_billed,
            **_with_fee(unit * card_billed, zone, CARD),
            "min_amount": min_payment_amount(zone, CARD),
        },
        "currency": CURRENCY[zone],
        "zone": zone,
    }


@router.get("/methods")
async def methods(request: Request, user: User = Depends(require_auth)):
    """Moyens de paiement de la zone du client, disponibles ou non.

    Tous sont listés : un moyen indisponible s'affiche grisé « pas encore
    disponible » plutôt que de disparaître, le client sait ce qui viendra."""
    currency = CURRENCY[_zone_of(request)]
    return {"currency": currency, "methods": list_methods(currency)}


class CollectBody(BaseModel):
    pages: int = Field(..., ge=1, le=MAX_PAGES_PER_PAYMENT)
    # Moyen choisi par le client (cf. `payment_methods.METHODS`). Absent :
    # ancien client, mobile money — Campay ne distingue pas MTN d'Orange,
    # c'est le numéro qui décide de l'opérateur.
    method: str = MTN_MOMO
    # Numéro au format international sans « + » (ex. 237670000000). Exigé
    # pour le mobile money seulement.
    phone: str | None = Field(None, min_length=9, max_length=15)
    # Paiement destiné à débloquer un document DÉJÀ traduit (la traduction
    # offerte, typiquement). Absent = achat de pages d'avance.
    document_id: str | None = None


@router.post("/collect")
async def collect(body: CollectBody, request: Request,
                  user: User = Depends(require_auth),
                  db: AsyncSession = Depends(get_db)):
    """Déclenche l'invite de paiement mobile money sur le téléphone du client.

    Rend la main IMMÉDIATEMENT : la saisie du code USSD prend souvent plus
    d'une minute, attendre le résultat ici bloquerait la requête et l'écran.
    Le client interroge ensuite `GET /api/payments/{id}`.
    """
    zone = _zone_of(request)
    method, phone, provider = _resolve_method(body.method, body.phone, zone)

    doc = await _owned_unpaid_document(db, user, body.document_id)

    # Le document se paie à SA taille, connue du serveur : le nombre de pages
    # envoyé par le navigateur ne fait pas le prix d'un document identifié.
    pages = (await _document_pages(db, doc) if doc is not None else None) or body.pages
    # Arrondi au montant minimum de l'opérateur ; `_apply_credit` reverse au
    # compte les pages payées au-delà du document.
    billed = billable_pages(zone, pages, method)
    amount = _with_fee(page_price(zone) * billed, zone, method)["amount"]

    payment = Payment(
        user_id=user.id, document_id=body.document_id, pages=billed,
        amount=amount, currency=CURRENCY[zone], zone=zone,
        phone=phone, status="PENDING", provider=provider.name, method=method,
    )
    return await _start_payment(db, provider, payment, f"Précis — {billed} page(s)",
                                email=user.email)


def _resolve_method(method: str, raw_phone: str | None, zone: str):
    """Moyen choisi → (moyen retenu, numéro normalisé, prestataire). Lève
    l'erreur HTTP à renvoyer quand le moyen n'est pas ouvert."""
    # Normalisé ICI, une fois : ce qui part chez Campay et ce qu'on enregistre
    # doivent être le même numéro. Le faire côté navigateur laisserait les deux
    # diverger dès qu'un autre client appellerait l'API.
    phone = normalize_phone(raw_phone) if raw_phone else None
    if method in PHONE_METHODS and phone:
        # Le numéro, pas la tuile cochée, décide de l'opérateur chez le
        # prestataire : un numéro Orange envoyé sous « MTN » sera encaissé par
        # Orange Money, c'est donc ce moyen-là qui doit être ouvert.
        method = method_of_phone(phone) or method
    provider, reason = provider_for(method, CURRENCY[zone])
    if provider is None:
        # Moyen affiché grisé dans l'interface : n'y arriver que par l'API.
        # Une devise que le prestataire n'encaisse pas se refuse franchement,
        # plutôt que de convertir en douce un prix affiché en euros.
        logger.info("Moyen %s refusé (%s, zone %s)", method, reason, zone)
        raise HTTPException(
            status_code=501 if reason == "currency" else 409,
            detail="Ce moyen de paiement n'est pas encore disponible.",
        )
    # Exigé seulement quand c'est nous qui le transmettons : sur une page
    # hébergée, le client le saisit chez le prestataire.
    if method in PHONE_METHODS and not phone and needs_phone(method, CURRENCY[zone]):
        raise HTTPException(status_code=422, detail="Numéro de téléphone requis.")
    return method, phone, provider


async def _start_payment(db: AsyncSession, provider, payment: Payment,
                         description: str, email: str | None = None) -> dict:
    """Enregistre le paiement PUIS sollicite le prestataire."""
    # La trace existe AVANT l'appel. Si le réseau coupe juste après que Campay
    # a débité le client, on a de quoi réconcilier ; l'inverse perd l'argent
    # du client sans laisser la moindre trace chez nous.
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    try:
        res = await provider.start(
            amount=payment.amount, currency=payment.currency, phone=payment.phone,
            description=description, reference=payment.id,
            email=email, user_id=payment.user_id,
        )
    except ProviderError as e:
        # On journalise le détail, on n'en montre rien : la réponse d'un
        # fournisseur de paiement peut contenir des éléments de compte.
        logger.warning("%s : encaissement échoué (paiement %s) : %s",
                       provider.name, payment.id, e)
        payment.status = "FAILED"
        await db.commit()
        raise HTTPException(status_code=502, detail=e.user_message)

    payment.provider_ref = res.get("provider_ref")
    await db.commit()

    return {
        "payment_id": payment.id,
        "status": "PENDING",
        "amount": payment.amount,
        "currency": payment.currency,
        # À afficher : sur certains téléphones l'invite n'arrive pas et il faut
        # composer ce code à la main.
        "ussd_code": res.get("ussd_code"),
        "operator": res.get("operator"),
        # Page de paiement du prestataire, quand c'est là que le client paie
        # (Fapshi `initiate-pay`) ; absent pour une invite poussée.
        "checkout_url": res.get("checkout_url"),
    }


# Une invite Campay reste ouverte environ 3 min (le client cesse d'interroger
# au même terme) : un second achat de forfait pendant ce temps est un double
# clic ou un deuxième onglet, pas une intention. Un checkout carte Paddle reste
# payable bien plus longtemps : on le rouvre (même offre) pendant ce délai.
PENDING_PLAN_WINDOW = timedelta(minutes=3)
PENDING_CARD_WINDOW = timedelta(minutes=15)


def _with_fee(subtotal: int, zone: str, method: str | None = None) -> dict:
    """Montant net → détail encaissé : les frais de transaction du moyen
    choisi sont à la charge du client (`pricing.transaction_fee`)."""
    fee = transaction_fee(subtotal, CURRENCY[zone], method)
    return {"subtotal": subtotal, "fee": fee, "amount": subtotal + fee}


def _plan_offer(plan: str, annual: bool, zone: str) -> tuple[int, int]:
    """(prix mensuel, nombre de mois). L'annuel se paie d'avance : douze fois
    le prix mensuel affiché sur la carte. Frais : `_with_fee(monthly * months)`."""
    if plan not in SELF_SERVE_PLANS:
        raise HTTPException(status_code=422, detail="Ce forfait ne s'achète pas en ligne.")
    monthly = plan_price(plan, zone, annual=annual)
    if not monthly:
        raise HTTPException(status_code=422, detail="Ce forfait ne s'achète pas en ligne.")
    months = 12 if annual else 1
    return monthly, months


def _loses_rights(user: User, plan: str, now: datetime | None = None) -> bool:
    """L'achat de `plan` ferait-il PERDRE des droits au compte ?

    Entreprise / admin, un plan supérieur en cours, ou ce même plan attribué
    sans échéance : l'achat le remplacerait par moins. Un abonnement échu
    (pas encore ramené au Gratuit) compte comme le Gratuit. Vérifié à l'achat
    ET au crédit : le compte peut changer entre l'invite et la validation."""
    now = now or datetime.now(timezone.utc)
    current = user.plan
    if user.plan_expires_at is not None and user.plan_expires_at <= now:
        current = "free"
    rank = PLAN_RANK.get(current)
    return rank is None or rank > PLAN_RANK[plan] or (
        current == plan and user.plan_expires_at is None)


def _check_can_buy(user: User, plan: str) -> None:
    if _loses_rights(user, plan):
        raise HTTPException(status_code=409,
                            detail="Votre forfait actuel couvre déjà cette offre.")


class PlanQuoteBody(BaseModel):
    plan: str
    annual: bool = False


@router.post("/plan/quote")
async def plan_quote(body: PlanQuoteBody, request: Request,
                     user: User = Depends(require_auth)):
    """Prix d'un abonnement, tel qu'il sera encaissé par `POST /plan`."""
    zone = _zone_of(request)
    monthly, months = _plan_offer(body.plan, body.annual, zone)
    _check_can_buy(user, body.plan)
    return {"plan": body.plan, "annual": body.annual, "months": months,
            "monthly_price": monthly, **_with_fee(monthly * months, zone),
            # Frais propres à la carte : même bascule que `/quote`.
            "card": _with_fee(monthly * months, zone, CARD),
            "currency": CURRENCY[zone], "zone": zone}


class PlanBody(PlanQuoteBody):
    method: str = MTN_MOMO
    phone: str | None = Field(None, min_length=9, max_length=15)


@router.post("/plan")
async def buy_plan(body: PlanBody, request: Request,
                   user: User = Depends(require_auth),
                   db: AsyncSession = Depends(get_db)):
    """Achète (ou renouvelle) un abonnement Starter / Pro.

    Même chemin que l'achat de pages : trace AVANT l'appel, invite sur le
    téléphone, puis `GET /{id}` jusqu'à l'issue. Le prix vient de
    `pricing.py`, jamais du navigateur. Campay ne prélève pas de lui-même :
    chaque mois (ou année) est un nouveau paiement, qui prolonge l'échéance.
    """
    zone = _zone_of(request)
    monthly, months = _plan_offer(body.plan, body.annual, zone)
    _check_can_buy(user, body.plan)
    maintenant = datetime.now(timezone.utc)
    if body.method == CARD:
        reprise = await _resume_card_plan(db, user, body.plan, months, maintenant)
        if reprise:
            return reprise
    # Une invite Mobile Money en cours bloque une seconde demande. Pas un
    # paiement par carte : rien n'est débité sans saisie du client, et sa
    # transaction reste en attente (le webhook la créditerait encore).
    en_attente = await db.scalar(
        select(func.count()).select_from(Payment).where(
            Payment.user_id == user.id, Payment.plan.is_not(None),
            Payment.status == "PENDING",
            or_(Payment.method.is_(None), Payment.method != CARD),
            Payment.created_at >= maintenant - PENDING_PLAN_WINDOW,
        ))
    if en_attente:
        raise HTTPException(
            status_code=409,
            detail="Un paiement de forfait est déjà en cours ; terminez-le ou patientez quelques minutes.")
    method, phone, provider = _resolve_method(body.method, body.phone, zone)
    amount = _with_fee(monthly * months, zone, method)["amount"]
    payment = Payment(
        user_id=user.id, pages=0, amount=amount, currency=CURRENCY[zone],
        zone=zone, phone=phone, status="PENDING", provider=provider.name,
        method=method, plan=body.plan, months=months,
    )
    return await _start_payment(db, provider, payment,
                                f"Précis — forfait {body.plan} ({months} mois)",
                                email=user.email)


async def _resume_card_plan(db: AsyncSession, user: User, plan: str,
                            months: int, now: datetime) -> dict | None:
    """Rouvre la transaction carte encore ouverte pour la même offre : fermer
    la fenêtre de paiement puis revenir ne doit ni bloquer ni en créer une
    seconde."""
    payment = await db.scalar(
        select(Payment).where(
            Payment.user_id == user.id, Payment.plan == plan,
            Payment.months == months, Payment.method == CARD,
            Payment.status == "PENDING", Payment.provider_ref.is_not(None),
            Payment.created_at >= now - PENDING_CARD_WINDOW,
        ).order_by(Payment.created_at.desc()).limit(1))
    provider = PROVIDERS.get(payment.provider) if payment else None
    if payment is None or not hasattr(provider, "resume"):
        return None
    try:
        status, url = await provider.resume(payment.provider_ref)
    except ProviderError as e:
        logger.warning("Reprise %s impossible (%s) : %s", payment.provider, payment.id, e)
        return None
    if status != "PENDING":
        payment.status = status
        await db.commit()
        await _apply_credit(db, payment)
        if status == "SUCCESSFUL":
            raise HTTPException(status_code=409,
                                detail="Ce paiement vient d'être reçu : votre forfait est actif.")
        return None
    if not url:
        return None
    return {"payment_id": payment.id, "status": "PENDING", "amount": payment.amount,
            "currency": payment.currency, "ussd_code": None, "operator": None,
            "checkout_url": url}


def _carry_over(user: User, payment: Payment, now: datetime) -> timedelta:
    """Reste payé de l'ancien plan, converti au prix du nouveau.

    Passer de Starter à Pro avec 20 jours restants ne les jette pas : ils
    valent 20 × prix Starter / prix Pro jours de Pro, ajoutés à l'échéance."""
    if (user.plan == payment.plan or user.plan_expires_at is None
            or user.plan_expires_at <= now):
        return timedelta(0)
    old = plan_price(user.plan, payment.zone)
    new = plan_price(payment.plan, payment.zone)
    if not old or not new:
        return timedelta(0)
    return (user.plan_expires_at - now) * (old / new)


async def _apply_plan(db: AsyncSession, payment: Payment) -> None:
    """Ouvre ou prolonge l'abonnement payé (dans la transaction du drapeau)."""
    # Verrou de ligne : deux renouvellements du même compte crédités en même
    # temps liraient la même échéance et n'en ajouteraient qu'un.
    user = (await db.execute(
        select(User).where(User.id == payment.user_id).with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if user is None:
        return
    now = datetime.now(timezone.utc)
    if _loses_rights(user, payment.plan, now):
        # Le compte a changé entre l'invite et la validation (passé entreprise,
        # plan supérieur acheté ou attribué) : ne pas le rétrograder. L'argent
        # est encaissé : le paiement est marqué dû, le client en est averti.
        logger.warning("Paiement de plan %s sur un compte %s : non appliqué, "
                       "à rembourser", payment.id, user.plan)
        await db.execute(update(Payment).where(Payment.id == payment.id)
                         .values(refund_due=True))
        return
    if (user.plan == payment.plan and user.plan_expires_at
            and user.plan_expires_at > now):
        # Renouvellement anticipé du même plan : la durée s'AJOUTE à ce qui
        # reste, et la période de quota garde son jour.
        start = user.plan_expires_at
        user.plan_started_at = user.plan_started_at or now
    else:
        # Nouveau plan : il commence maintenant, avec le reste de l'ancien.
        start = now + _carry_over(user, payment, now)
        user.plan_started_at = now
    user.plan = payment.plan
    user.plan_expires_at = add_months(start, payment.months or 1)
    user.storage_limit = get_plan_storage(payment.plan)


async def _apply_credit(db: AsyncSession, payment: Payment) -> None:
    """Porte les pages achetées au compte — UNE SEULE FOIS.

    Le webhook de Campay et l'interrogation d'état par le client arrivent tous
    les deux, souvent simultanément, parfois plusieurs fois. Sans le drapeau
    `credited`, le même paiement créditerait deux ou trois fois : le client
    recevrait des pages qu'il n'a pas achetées, et le total ne se raccorderait
    à rien.
    """
    if payment.credited or payment.status != "SUCCESSFUL":
        return

    # Le drapeau se PREND par une écriture atomique, il ne se lit pas : le
    # webhook et l'interrogation d'état ont chacun leur session, et chacune
    # aurait lu `credited=False` avant que l'autre ne commite. Une seule des
    # deux voit `rowcount == 1` ; l'autre s'arrête sans rien créditer. Le
    # crédit et le drapeau partent dans la MÊME transaction.
    pris = await db.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.credited.is_(False),
               Payment.status == "SUCCESSFUL")
        .values(credited=True)
        .execution_options(synchronize_session=False)
    )
    if pris.rowcount != 1:
        await db.rollback()
        return

    if payment.plan:
        await _apply_plan(db, payment)
        await db.commit()
        payment.credited = True
        return

    surplus = payment.pages
    if payment.document_id:
        # Paiement ciblé : il débloque CE document. Les pages payées au-delà
        # de sa taille (montant minimum de l'opérateur) vont au compte.
        await db.execute(update(Document)
                         .where(Document.id == payment.document_id)
                         .values(paid=True))
        doc = await db.get(Document, payment.document_id)
        # Document supprimé entre-temps : rien à débloquer, tout le paiement
        # revient au compte plutôt que de disparaître.
        if doc is not None:
            surplus = max(0, payment.pages - (doc.page_count or payment.pages))
    if surplus:
        # Incrément en SQL : deux paiements du même compte qui se croisent ne
        # doivent pas s'écraser l'un l'autre.
        await db.execute(update(User).where(User.id == payment.user_id)
                         .values(page_credits=User.page_credits + surplus))

    await db.commit()
    payment.credited = True


@router.get("/{payment_id}")
async def payment_status(payment_id: str, user: User = Depends(require_auth),
                         db: AsyncSession = Depends(get_db)):
    """État d'un paiement. C'est ce que le client interroge pendant l'attente."""
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Paiement introuvable.")

    # Tant que c'est en attente, on redemande au fournisseur : le webhook peut
    # ne jamais arriver (pare-feu, environnement de développement sans URL
    # publique). Ne dépendre QUE du webhook, c'est laisser des clients payés
    # sans rien recevoir.
    provider = PROVIDERS.get(payment.provider)
    if payment.status == "PENDING" and payment.provider_ref and provider:
        try:
            new_status = await provider.status(payment.provider_ref)
            if new_status != payment.status:
                payment.status = new_status
                await db.commit()
                await _apply_credit(db, payment)
        except ProviderError as e:
            logger.warning("Statut %s indisponible (%s) : %s",
                           payment.provider, payment_id, e)

    return {
        "payment_id": payment.id,
        "status": payment.status,
        "pages": payment.pages,
        "amount": payment.amount,
        "currency": payment.currency,
        "document_id": payment.document_id,
        "plan": payment.plan,
        "refund_due": payment.refund_due,
    }


@router.api_route(
    "/campay/webhook", methods=["GET", "POST"],
    # `operation_id` explicite : sans lui, les deux methodes derivent le MEME
    # identifiant du nom de la fonction, l'OpenAPI devient ambigu et tout
    # generateur de client s'en plaint (avertissement au demarrage).
    operation_id="campay_webhook",
    summary="Notification de paiement Campay",
    include_in_schema=False,   # endpoint appele par Campay, pas par le client
)
async def campay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Notification de Campay.

    GET **et** POST : la méthode se choisit dans les réglages de l'application
    Campay. N'en accepter qu'une, c'est laisser un réglage du tableau de bord
    couper silencieusement les notifications.

    DEUX barrières, et la seconde suffirait :
      1. la `signature` (JWT HS256 signé avec la webhook key de l'application)
         prouve que l'appel vient de Campay ;
      2. l'état retenu n'est jamais celui annoncé dans le corps, mais celui que
         l'API de Campay confirme quand NOUS l'interrogeons, sur une référence
         que nous avons nous-mêmes émise.

    On garde les deux : la signature évite d'appeler Campay pour chaque
    sollicitation d'un inconnu, la re-vérification protège même si la clé fuit.
    """
    if request.method == "POST":
        try:
            body = dict(await request.json())
        except Exception:
            raise HTTPException(status_code=400, detail="Corps illisible.")
    else:
        body = dict(request.query_params)

    # Barrière 1 : origine prouvée.
    if not campay.verify_webhook_signature(body.get("signature", "")):
        # 403 et pas 400 : ce n'est pas une requête malformée, c'est une
        # requête non authentifiée. Le journal garde la trace de la tentative.
        logger.warning("Webhook Campay sans signature valide (ref=%s)",
                       body.get("reference"))
        raise HTTPException(status_code=403, detail="Signature invalide.")

    reference = body.get("reference") or body.get("external_reference")
    if not reference:
        raise HTTPException(status_code=400, detail="Référence absente.")

    stmt = select(Payment).where(
        (Payment.provider_ref == reference) | (Payment.id == reference)
    )
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        # 200 volontaire : un 404 inviterait Campay à réessayer indéfiniment
        # une référence qui ne nous concerne pas.
        logger.info("Webhook Campay pour une référence inconnue : %s", reference)
        return {"ok": True}

    if payment.status != "PENDING" or not payment.provider_ref:
        return {"ok": True}
    if payment.provider != "campay":
        # Campay n'a rien à dire d'un paiement d'un autre prestataire.
        logger.warning("Webhook Campay pour un paiement %s : %s",
                       payment.provider, payment.id)
        return {"ok": True}

    try:
        res = await campay.transaction_status(payment.provider_ref)
    except CampayError as e:
        logger.warning("Webhook : statut Campay indisponible (%s) : %s", reference, e)
        raise HTTPException(status_code=503, detail="Réessayez.")

    payment.status = res.get("status", "PENDING")
    await db.commit()
    await _apply_credit(db, payment)
    return {"ok": True}


@router.post("/fapshi/webhook", operation_id="fapshi_webhook",
             summary="Notification de paiement Fapshi", include_in_schema=False)
async def fapshi_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Notification de Fapshi (POST, corps = la transaction, envoyé quand elle
    devient SUCCESSFUL, FAILED ou EXPIRED).

    Mêmes deux barrières que pour Campay, la seconde suffisant seule :
      1. l'en-tête `x-wh-secret` égal au secret du tableau de bord ;
      2. l'état retenu est celui que `payment-status` confirme quand NOUS
         l'interrogeons, jamais celui annoncé dans le corps.
    """
    if not fapshi.verify_webhook_secret(request.headers.get("x-wh-secret")):
        logger.warning("Webhook Fapshi sans secret valide")
        raise HTTPException(status_code=403, detail="Secret invalide.")
    try:
        body = dict(await request.json())
    except Exception:
        raise HTTPException(status_code=400, detail="Corps illisible.")

    trans_id = body.get("transId")
    if not trans_id:
        raise HTTPException(status_code=400, detail="Référence absente.")

    stmt = select(Payment).where(Payment.provider == "fapshi",
                                 Payment.provider_ref == str(trans_id))
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        logger.info("Webhook Fapshi pour une transaction inconnue : %s", trans_id)
        return {"ok": True}
    if payment.status != "PENDING":
        return {"ok": True}

    # Un PENDING mis en cache par l'écran d'attente masquerait le changement
    # que ce webhook annonce : si l'utilisateur a fermé la page, plus rien ne
    # réinterrogerait Fapshi et le crédit ne viendrait jamais.
    fapshi.forget_status(payment.provider_ref)
    try:
        new_status = await PROVIDERS["fapshi"].status(payment.provider_ref)
    except ProviderError as e:
        logger.warning("Webhook : statut Fapshi indisponible (%s) : %s", trans_id, e)
        raise HTTPException(status_code=503, detail="Réessayez.")

    payment.status = new_status
    await db.commit()
    await _apply_credit(db, payment)
    return {"ok": True}


@router.post("/paddle/webhook", operation_id="paddle_webhook",
             summary="Notification de paiement Paddle", include_in_schema=False)
async def paddle_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Notification de Paddle (`transaction.*` : corps = {event_type, data}).

    Mêmes deux barrières que pour Campay, la seconde suffisant seule :
      1. l'en-tête `Paddle-Signature`, HMAC du corps BRUT (relu avant tout
         décodage : un JSON re-sérialisé ne donnerait plus la même empreinte) ;
      2. l'état retenu est celui que `GET /transactions/<id>` confirme quand
         NOUS l'interrogeons, jamais celui annoncé dans le corps.
    """
    raw = await request.body()
    if not paddle.verify_webhook_signature(request.headers.get("paddle-signature"), raw):
        logger.warning("Webhook Paddle sans signature valide")
        raise HTTPException(status_code=403, detail="Signature invalide.")
    try:
        body = json.loads(raw)
        txn_id = (body.get("data") or {}).get("id")
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Corps illisible.")
    if not str(body.get("event_type", "")).startswith("transaction."):
        # Autres événements abonnés par erreur : 200, sinon Paddle réessaie.
        return {"ok": True}
    if not txn_id:
        raise HTTPException(status_code=400, detail="Référence absente.")

    stmt = select(Payment).where(Payment.provider == "paddle",
                                 Payment.provider_ref == str(txn_id))
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        logger.info("Webhook Paddle pour une transaction inconnue : %s", txn_id)
        return {"ok": True}
    if payment.status != "PENDING":
        return {"ok": True}

    try:
        new_status = await PROVIDERS["paddle"].status(payment.provider_ref)
    except ProviderError as e:
        logger.warning("Webhook : statut Paddle indisponible (%s) : %s", txn_id, e)
        raise HTTPException(status_code=503, detail="Réessayez.")

    payment.status = new_status
    await db.commit()
    await _apply_credit(db, payment)
    return {"ok": True}
