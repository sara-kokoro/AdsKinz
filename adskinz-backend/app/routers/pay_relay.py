"""
AdsKinz — Relais de création de dépôts Mobile Money pour JessiKaPay
========================================================================

Ce routeur N'A RIEN à voir avec la facturation adskinz (voir billing.py).
Il existe uniquement parce que MoneyFusion refuse les projets hébergés
sur domaine gratuit (jkpay.vercel.app) et qu'adskinz.me est un domaine
payant. AdsKinz sert ici de simple façade technique pour les dépôts
JessiKaPay — jamais de payout, jamais de logique métier JessiKaPay.

VERSION GÉNÉRIQUE : adskinz ne connaît plus aucun chemin JessiKaPay en
dur. Le token signé (voir services/relay_token.py) transporte lui-même
`webhook_path` (où MoneyFusion doit notifier) et `status_path` (où
adskinz doit interroger le statut pour le polling). Ça permet à
JessiKaPay de brancher plusieurs flux différents (dépôt normal vers le
solde de l'utilisateur payeur, dépôt externe vers le solde du
propriétaire d'une app tierce, etc.) sans qu'adskinz ait besoin d'être
modifié à chaque fois — adskinz ne fait que créer le paiement MoneyFusion
sous l'identité adskinz.me et relayer les deux chemins fournis.

Flux complet :
  1. JessiKaPay signe un token (montant, tx_id, webhook_path, status_path...)
     et redirige l'utilisateur vers GET /pay/{token} (page adskinz dédiée).
  2. Le frontend adskinz appelle POST /pay/{token}/init → on vérifie le
     token, on enregistre un RelayDeposit "pending" (pour trace/audit),
     on appelle MoneyFusion avec l'identité adskinz.me et un webhook_url
     construit à partir de payload.webhook_path, puis on renvoie
     payment_url au frontend qui redirige l'utilisateur dessus.
  3. MoneyFusion notifie JessiKaPay directement (webhook_path) — adskinz
     n'est plus dans la boucle de crédit.
  4. Le frontend adskinz poll GET /pay/{token}/status, qui relaie la
     question à payload.status_path côté JessiKaPay serveur-à-serveur.

Sécurité :
  - Le montant vient UNIQUEMENT du token signé, jamais du corps de la
    requête POST /init — impossible pour l'utilisateur de le changer.
  - webhook_path/status_path viennent aussi UNIQUEMENT du token signé
    par JessiKaPay — adskinz ne fait jamais confiance à une valeur
    fournie par le frontend ou l'utilisateur pour ces champs.
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

# Surtaxe fixe ajoutée par adskinz sur chaque dépôt relayé, pour couvrir ses
# propres frais d'infra (Neon, etc.). Ajoutée UNIQUEMENT au montant facturé
# à MoneyFusion — le montant crédité côté JessiKaPay reste basé sur
# payload.amount (celui signé par JessiKaPay), totalement inchangé.
RELAY_SURCHARGE_FCFA = 100


@router.post("/{token}/init")
async def init_relay_payment(token: str, request: Request, session: SessionDep) -> dict:
    """Vérifie le token, crée (ou réutilise) le RelayDeposit, appelle MoneyFusion."""
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

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

    # webhook_path est fourni et signé par JessiKaPay — adskinz ne fait que
    # préfixer avec son URL de backend JessiKaPay connue (JKPAY_BACKEND_URL).
    webhook_url = f"{settings.JKPAY_BACKEND_URL.rstrip('/')}{payload.webhook_path}"
    return_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/pay/{token}/return"

    result = await create_relay_payment(
        amount=payload.amount + RELAY_SURCHARGE_FCFA,
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
    Poll du statut par la page adskinz. adskinz ne stocke pas le résultat
    lui-même — il redemande à JessiKaPay, via status_path (signé dans le
    token), seule source de vérité, à chaque appel.
    """
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    url = f"{settings.JKPAY_BACKEND_URL.rstrip('/')}{payload.status_path}"
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
    jk_status = data.get("status")
    normalized = "success" if jk_status == "completed" else ("failed" if jk_status == "failed" else "pending")

    return {"status": normalized, "amount": data.get("amount")}
