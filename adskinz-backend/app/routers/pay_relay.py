"""
AdsKinz — Relais de dépôts Mobile Money pour JessiKaPay
============================================================

Ce routeur N'A RIEN à voir avec la facturation adskinz (voir billing.py).
Il existe uniquement parce que MoneyFusion refuse les projets hébergés
sur domaine gratuit (jkpay.vercel.app) et qu'adskinz.me est un domaine
payant. AdsKinz sert ici de simple façade technique pour les dépôts
JessiKaPay — jamais de payout, jamais de logique métier JessiKaPay.

Flux complet :
  1. JessiKaPay signe un token (montant, tx_id, tgid...) et redirige
     l'utilisateur vers GET /pay/{token} (page adskinz dédiée).
  2. Le frontend adskinz appelle POST /pay/{token}/init → on vérifie le
     token, on enregistre un RelayDeposit "pending", on appelle MoneyFusion
     avec l'identité adskinz.me, on renvoie payment_url au frontend qui
     redirige l'utilisateur dessus.
  3. MoneyFusion notifie POST /webhooks/moneyfusion/relay → on met à jour
     le RelayDeposit et on notifie le backend JessiKaPay (HMAC signé).
  4. Le frontend adskinz poll GET /pay/{token}/status pour afficher
     succès/échec avant que l'utilisateur ne revienne sur Telegram.

Sécurité :
  - Le montant vient UNIQUEMENT du token signé, jamais du corps de la
    requête POST /init — impossible pour l'utilisateur de le changer.
  - Le webhook MoneyFusion est vérifié par IP (best-effort) + idempotence
    DB (statut déjà != pending ⇒ ignoré).
  - La notification à JessiKaPay est elle-même signée HMAC + retentée
    avec backoff si JessiKaPay ne répond pas 200 (jkpay_notify_attempts).
"""

from __future__ import annotations

import json
import logging
import time

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import settings
from app.core.deps import SessionDep, client_ip
from app.models.relay import RelayDeposit
from app.services.moneyfusion_relay import (
    check_relay_payment_status,
    create_relay_payment,
    is_moneyfusion_ip,
)
from app.services.relay_token import RelayTokenError, sign_outgoing_notification, verify_relay_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pay", tags=["jkpay-relay"])

MAX_NOTIFY_ATTEMPTS = 5

# Chemin réel de la route webhook ci-dessous, PRÉFIXE INCLUS (le routeur a
# prefix="/pay"). Une seule source de vérité pour éviter que l'URL envoyée
# à MoneyFusion et l'URL réellement servie divergent à nouveau.
RELAY_WEBHOOK_PATH = "/pay/webhooks/moneyfusion/relay"


@router.post("/{token}/init")
async def init_relay_payment(token: str, request: Request, session: SessionDep) -> dict:
    """Vérifie le token, crée (ou réutilise) le RelayDeposit, appelle MoneyFusion."""
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    # Idempotence : si ce tx_id a déjà été initié (rafraîchissement de page,
    # double-clic...), on ne recrée pas de session MoneyFusion, on renvoie
    # l'état existant.
    existing = (
        await session.execute(
            select(RelayDeposit).where(RelayDeposit.jkpay_tx_id == payload.tx_id)
        )
    ).scalar_one_or_none()

    if existing:
        return {
            "status": existing.status,
            "already_initiated": True,
        }

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
    await session.flush()  # obtient relay.id sans committer prématurément

    # ATTENTION : ce routeur a prefix="/pay" (voir plus bas), donc le chemin
    # réel de la route webhook est /pay/webhooks/moneyfusion/relay. Un oubli
    # du préfixe ici = MoneyFusion appelle une URL 404 = jamais de crédit
    # côté JessiKaPay alors que l'argent est bien arrivé. Vérifié une fois
    # pour toutes en le mettant dans une constante en haut du fichier.
    webhook_url = f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}{RELAY_WEBHOOK_PATH}"
    # return_url : simple page de statut adskinz, l'utilisateur y atterrit
    # après MoneyFusion avant d'être renvoyé vers Telegram par le frontend.
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
async def relay_status(token: str, session: SessionDep) -> dict:
    """Poll du statut par la page adskinz pendant que l'utilisateur paie."""
    try:
        payload = verify_relay_token(token)
    except RelayTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    relay = (
        await session.execute(
            select(RelayDeposit).where(RelayDeposit.jkpay_tx_id == payload.tx_id)
        )
    ).scalar_one_or_none()

    if not relay:
        raise HTTPException(status_code=404, detail="Dépôt introuvable")

    return {"status": relay.status, "amount": relay.amount}


@router.post("/webhooks/moneyfusion/relay", include_in_schema=False)
async def moneyfusion_relay_webhook(request: Request, session: SessionDep) -> dict:
    ip = client_ip(request)
    if not is_moneyfusion_ip(ip):
        logger.warning("Relay webhook: IP non reconnue %s", ip)
        # On log mais on ne bloque pas encore — même choix que côté JessiKaPay,
        # au cas où MoneyFusion changerait ses IPs sans préavis.

    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}

    event = str(body.get("event", ""))
    statut = str(body.get("statut", "")).lower()
    token = body.get("tokenPay") or body.get("token")

    personal_info = body.get("personal_Info", [])
    tx_id = None
    if isinstance(personal_info, list) and personal_info:
        tx_id = personal_info[0].get("userId") or personal_info[0].get("orderId")

    if not tx_id and token:
        r = await session.execute(select(RelayDeposit).where(RelayDeposit.moneyfusion_token == token))
        tmp = r.scalar_one_or_none()
        tx_id = tmp.jkpay_tx_id if tmp else None

    if not tx_id:
        logger.warning("Relay webhook: pas de tx_id, ip=%s body=%s", ip, body)
        return {"status": "ignored"}

    relay = (
        await session.execute(
            select(RelayDeposit).where(RelayDeposit.jkpay_tx_id == tx_id).with_for_update()
        )
    ).scalar_one_or_none()

    if not relay:
        logger.warning("Relay webhook: RelayDeposit introuvable pour tx=%s", tx_id)
        return {"status": "ignored"}

    if relay.status != "pending":
        # Idempotence : webhook déjà traité (MoneyFusion peut renvoyer 2x).
        return {"status": "already_processed"}

    success_markers = ("paid", "completed", "success")
    failure_markers = ("failed", "cancelled", "error")

    if statut in success_markers or event.lower().endswith("completed"):
        relay.status = "success"
    elif statut in failure_markers or event.lower().endswith("cancelled"):
        relay.status = "failed"
    else:
        # Statut intermédiaire (pending) — rien à notifier à JessiKaPay pour l'instant.
        await session.commit()
        return {"status": "noted"}

    await session.commit()

    await _notify_jkpay(relay, session)
    return {"status": "processed"}


async def _notify_jkpay(relay: RelayDeposit, session: SessionDep) -> None:
    """
    Notifie JessiKaPay du résultat final. Best-effort avec incrément du
    compteur de tentatives — un job planifié (jobs/) peut relire les
    RelayDeposit avec jkpay_notified=False et status != pending pour
    retenter, plutôt que de bloquer la réponse au webhook MoneyFusion.
    """
    body = {
        "jkpay_tx_id": relay.jkpay_tx_id,
        "status": relay.status,  # "success" | "failed"
        "amount": relay.amount,
        "moneyfusion_token": relay.moneyfusion_token,
    }
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    timestamp, signature = sign_outgoing_notification(raw)

    url = f"{settings.JKPAY_BACKEND_URL.rstrip('/')}/internal/relay/credit"
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, content=raw, headers=headers)
            if resp.status_code < 400:
                relay.jkpay_notified = True
            else:
                logger.warning(
                    "Notification JessiKaPay refusée: tx=%s status=%s body=%s",
                    relay.jkpay_tx_id, resp.status_code, resp.text[:300],
                )
    except Exception as e:
        logger.error("Échec notification JessiKaPay pour tx=%s: %s", relay.jkpay_tx_id, e)
    finally:
        relay.jkpay_notify_attempts += 1
        await session.commit()


@router.post("/admin/reconcile/{jkpay_tx_id}")
async def admin_reconcile_relay(jkpay_tx_id: str, request: Request, session: SessionDep) -> dict:
    """
    Rattrapage manuel : re-vérifie directement auprès de MoneyFusion le
    statut d'un RelayDeposit resté bloqué en 'pending' (typiquement parce
    que le webhook n'est jamais arrivé — mauvaise URL, panne réseau...),
    et notifie JessiKaPay si MoneyFusion confirme que c'est payé.

    Protégé par un secret admin passé en query param (?secret=...), PAS
    par l'auth adskinz normale — ce endpoint doit rester utilisable même
    si le reste de l'admin est en panne. Change ADMIN_RECONCILE_SECRET
    régulièrement et ne le partage nulle part.
    """
    if request.query_params.get("secret") != settings.ADMIN_RECONCILE_SECRET or not settings.ADMIN_RECONCILE_SECRET:
        raise HTTPException(status_code=404)  # 404 plutôt que 401/403 : ne pas révéler que l'endpoint existe

    relay = (
        await session.execute(
            select(RelayDeposit).where(RelayDeposit.jkpay_tx_id == jkpay_tx_id).with_for_update()
        )
    ).scalar_one_or_none()

    if not relay:
        raise HTTPException(status_code=404, detail="RelayDeposit introuvable")

    if relay.status != "pending":
        return {"status": relay.status, "message": "Déjà résolu, rien à faire.", "jkpay_notified": relay.jkpay_notified}

    if not relay.moneyfusion_token:
        return {"status": "pending", "message": "Pas de token MoneyFusion enregistré, impossible de vérifier."}

    mf_result = await check_relay_payment_status(relay.moneyfusion_token)
    logger.info("Réconciliation manuelle tx=%s → réponse MoneyFusion: %s", jkpay_tx_id, mf_result)

    statut = str(mf_result.get("statut") or mf_result.get("data", {}).get("statut") or "").lower()

    if statut in ("paid", "completed", "success"):
        relay.status = "success"
    elif statut in ("failed", "cancelled", "error"):
        relay.status = "failed"
    else:
        return {"status": "pending", "message": f"MoneyFusion renvoie toujours un statut non-final: {mf_result}"}

    await session.commit()
    await _notify_jkpay(relay, session)

    return {
        "status": relay.status,
        "jkpay_notified": relay.jkpay_notified,
        "moneyfusion_raw": mf_result,
    }
