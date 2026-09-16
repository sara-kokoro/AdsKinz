"""
AdsKinz — Relais de création de dépôts Mobile Money pour JessiKaPay
========================================================================

Ce routeur N'A RIEN à voir avec la facturation adskinz (voir billing.py).
Il existe uniquement parce que MoneyFusion refuse les projets hébergés
sur domaine gratuit (jkpay.vercel.app) et qu'adskinz.me est un domaine
payant. AdsKinz sert ici de simple façade technique pour les dépôts
JessiKaPay — jamais de payout, jamais de logique métier JessiKaPay.

VERSION SIMPLIFIÉE : adskinz ne fait plus que CRÉER le paiement MoneyFusion
sous l'identité adskinz.me (Origin/Referer). La confirmation MoneyFusion
(webhook) part DIRECTEMENT vers jessicapay-backend/webhooks/moneyfusion.py
— le code déjà existant et déjà éprouvé côté JessiKaPay. adskinz ne relaie
plus aucune notification : il n'est dans la boucle que pour la création.

Ce qui a disparu par rapport à la première version (et pourquoi c'est mieux) :
  - Le webhook /pay/webhooks/moneyfusion/relay : plus la peine, MoneyFusion
    parle directement à JessiKaPay.
  - _notify_jkpay (notification HMAC adskinz → JessiKaPay) : supprimé, un
    maillon de moins qui peut mal tourner (secret désynchronisé, URL fausse,
    panne réseau entre les deux backends...).
  - JKPAY_RELAY_SECRET : plus nécessaire, plus rien à garder identique des
    deux côtés.

Flux complet :
  1. JessiKaPay signe un token et redirige l'utilisateur vers
     GET /pay/{token} (page adskinz dédiée).
  2. Le frontend adskinz appelle POST /pay/{token}/init → on vérifie le
     token, on enregistre un RelayDeposit "pending" (pour trace/audit),
     on appelle MoneyFusion avec l'identité adskinz.me MAIS un
     webhook_url qui pointe directement sur jessicapay-backend, puis on
     renvoie payment_url au frontend qui redirige l'utilisateur dessus.
  3. MoneyFusion notifie JessiKaPay directement — adskinz n'est plus
     dans la boucle. JessiKaPay crédite via son code existant.
  4. Le frontend adskinz poll GET /pay/{token}/status, qui relaie la
     question à JessiKaPay (GET /deposit/status/{tx_id}) côté serveur —
     adskinz ne connaît jamais lui-même le vrai statut, il le redemande
     à chaque fois à la seule source de vérité : JessiKaPay.

Sécurité :
  - Le montant vient UNIQUEMENT du token signé, jamais du corps de la
    requête POST /init — impossible pour l'utilisateur de le changer.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import settings
from app.core.deps import SessionDep
from app.models.relay import RelayDeposit
from app.services.moneyfusion_relay import create_relay_payment
from app.services.relay_token import RelayTokenError, verify_relay_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pay", tags=["jkpay-relay"])


@router.post("/{token}/init")
async def init_relay_payment(token: str, request: Request, session: SessionDep) -> dict:
    """Vérifie le token, crée (ou réutilise) le RelayDeposit, appelle MoneyFusion."""
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    # Idempotence : si ce tx_id a déjà été initié (rafraîchissement de page,
    # double-clic...), on ne recrée pas de session MoneyFusion.
    existing = (
        await session.execute(
            select(RelayDeposit).where(RelayDeposit.jkpay_tx_id == payload.tx_id)
        )
    ).scalar_one_or_none()

    if existing:
        return {"status": "pending", "already_initiated": True}

    relay = RelayDeposit(
        jkpay_tx_id=payload.tx_id,
        tgid=payload.tgid,
        amount=payload.amount,
        phone=payload.phone,
        operator=payload.operator,
        country=payload.country,
        status="pending",
    )
    session.add(relay)
    await session.flush()

    # ── LE POINT CLÉ ──────────────────────────────────────────────────
    # webhook_url pointe DIRECTEMENT sur jessicapay-backend, pas sur
    # adskinz. MoneyFusion n'a aucune restriction sur la destination du
    # webhook (ce n'est pas une page visitée par un navigateur) — seule
    # la création du paiement doit émaner d'adskinz.me.
    webhook_url = f"{settings.JKPAY_BACKEND_URL.rstrip('/')}/webhooks/moneyfusion/deposit"
    return_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/pay/{token}/return"

    result = await create_relay_payment(
        amount=payload.amount,
        tx_id=payload.tx_id,
        customer_name=payload.customer_name,
        customer_phone=payload.phone,
        operator=payload.operator,
        country=payload.country,
        webhook_url=webhook_url,
        return_url=return_url,
    )

    if result.get("error"):
        relay.status = "failed"
        await session.commit()
        logger.error("Relay init failed for tx=%s: %s", payload.tx_id, result)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("message"))

    relay.moneyfusion_token = result.get("token")
    await session.commit()

    return {
        "status": "pending",
        "payment_url": result.get("payment_url"),
        "already_initiated": False,
    }


@router.get("/{token}/status")
async def relay_status(token: str) -> dict:
    """
    Poll du statut par la page adskinz. adskinz ne stocke plus le
    résultat lui-même (il ne reçoit plus le webhook) — il redemande à
    JessiKaPay, seule source de vérité, à chaque appel.
    """
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    url = f"{settings.JKPAY_BACKEND_URL.rstrip('/')}/deposit/status/{payload.tx_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
    except Exception as e:
        logger.error("Relay status: échec appel JessiKaPay pour tx=%s: %s", payload.tx_id, e)
        raise HTTPException(status_code=502, detail="Impossible de vérifier le statut pour le moment")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Dépôt introuvable côté JessiKaPay")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Erreur JessiKaPay")

    data = resp.json()
    # data = {"tx_id", "status", "amount", "fee", "credited", "moneyfusion_status"}
    # status JessiKaPay est déjà "pending" | "completed" | "failed" — on le
    # renvoie tel quel, la page adskinz sait déjà interpréter "success"/
    # "failed"/autre comme pending, donc on normalise juste "completed".
    jk_status = data.get("status")
    normalized = "success" if jk_status == "completed" else ("failed" if jk_status == "failed" else "pending")

    return {"status": normalized, "amount": data.get("amount")}
