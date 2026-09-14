"""
AdsKinz — Client MoneyFusion pour le relais de dépôts JessiKaPay
=====================================================================

VOLONTAIREMENT LIMITÉ AU PAYIN. Pas de fonction de payout ici : les
retraits JessiKaPay restent gérés exclusivement par jessicapay-backend,
comme décidé. Ce module ne fait que créer des paiements et vérifier
leur statut — jamais de transfert d'argent sortant.

Ce client est distinct de tout futur client MoneyFusion "adskinz natif"
qui servirait aux dépôts mobile money des annonceurs/éditeurs adskinz
eux-mêmes (fonctionnalité séparée, avec ses propres webhook_url et
tx_id — à ne jamais mélanger avec ceux du relais JessiKaPay).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MONEYFUSION_CREATE_PAYMENT_URL = "https://www.pay.moneyfusion.net/api/v1"  # à ajuster selon ton API_URL MoneyFusion réel
MONEYFUSION_STATUS_URL = "https://payin.moneyfusion.net/api/v1/pay/payment/{token}"

# IPs officielles MoneyFusion pour vérifier les webhooks entrants côté adskinz.
# Garder synchronisé avec jessicapay-backend/app/services/moneyfusion.py.
MONEYFUSION_WEBHOOK_IPS: set[str] = {
    "66.29.149.126",
}


def is_moneyfusion_ip(ip: str) -> bool:
    return ip in MONEYFUSION_WEBHOOK_IPS


async def create_relay_payment(
    *,
    amount: int,
    tx_id: str,
    customer_name: str,
    customer_phone: str,
    operator: str,
    country: str,
    webhook_url: str,
    return_url: str,
) -> dict[str, Any]:
    """
    Crée une session de paiement MoneyFusion sous l'identité du domaine
    adskinz.me (Origin/Referer). C'est tout l'intérêt du relais : MoneyFusion
    voit une requête provenant d'adskinz.me, un domaine payant qu'il accepte.
    """
    payload = {
        "totalPrice": amount,
        "typepaie": operator,
        "article": [{f"Depot JessiKaPay {tx_id}": amount}],
        "personal_Info": [{"userId": tx_id, "orderId": tx_id}],
        "numeroSend": customer_phone,
        "nomclient": customer_name,
        "return_url": return_url,
        "webhook_url": webhook_url,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Origin": settings.PUBLIC_BASE_URL,   # https://adskinz.me
        "Referer": f"{settings.PUBLIC_BASE_URL}/",
    }

    logger.info("Relay MoneyFusion create_payment: tx_id=%s amount=%s operator=%s", tx_id, amount, operator)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.MONEYFUSION_RELAY_API_URL, json=payload, headers=headers
            )
            try:
                data = response.json()
            except Exception:
                logger.error(
                    "Relay MoneyFusion: réponse non-JSON status=%s body=%s",
                    response.status_code, response.text[:500],
                )
                return {"error": True, "message": f"Erreur MoneyFusion (HTTP {response.status_code})"}

            if not data.get("statut"):
                return {"error": True, "message": data.get("message", "Erreur MoneyFusion")}

            return {"error": False, "token": data.get("token"), "payment_url": data.get("url")}

    except httpx.TimeoutException:
        logger.error("Relay MoneyFusion timeout tx_id=%s", tx_id)
        return {"error": True, "message": "Timeout MoneyFusion"}
    except Exception as e:
        logger.error("Relay MoneyFusion error tx_id=%s: %s", tx_id, e)
        return {"error": True, "message": str(e)}


async def check_relay_payment_status(token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(MONEYFUSION_STATUS_URL.format(token=token))
            return response.json()
    except Exception as e:
        logger.error("Relay MoneyFusion status check error token=%s: %s", token, e)
        return {"error": True, "message": str(e)}
