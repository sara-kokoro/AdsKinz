"""
AdsKinz — Vérification du token de relais JessiKaPay
=========================================================

Ce module authentifie les requêtes qui arrivent sur pay.adskinz.me/{token}.
Le token est généré côté JessiKaPay (voir jessicapay-backend/app/services/relay_token.py,
fonction `sign_relay_payload`) et contient toutes les infos du dépôt
(montant, téléphone, opérateur...) signées avec un secret partagé.

Pourquoi pas juste un JSON en clair dans l'URL ?
  Parce que l'utilisateur (ou n'importe qui interceptant le lien) pourrait
  modifier le montant avant qu'il n'arrive à MoneyFusion. La signature HMAC
  garantit qu'AdsKinz ne traite que des payloads que JessiKaPay a réellement
  émis, et l'expiration empêche de rejouer un vieux token.

Format du token : base64url(json_payload) + "." + hmac_sha256_hex(secret, json_payload)

Secret partagé : settings.JKPAY_RELAY_SECRET (variable d'env, JAMAIS de valeur
par défaut en dur — voir config.py). Ce secret doit être STRICTEMENT identique
des deux côtés (adskinz-backend et jessicapay-backend) et ne doit jamais
apparaître dans un log, un repo public ou une réponse HTTP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.core.errors import AuthenticationError


class RelayTokenError(AuthenticationError):
    code = "relay_token_invalid"
    message = "Lien de dépôt invalide ou expiré."


@dataclass(slots=True)
class RelayPayload:
    tx_id: str          # ID de transaction JessiKaPay (ex: JP-TXN-XXXXXXXX)
    amount: int          # Montant BRUT en FCFA, entier, jamais modifiable après signature
    phone: str
    operator: str
    country: str
    customer_name: str
    tgid: str            # Telegram user id JessiKaPay, pour traçabilité côté adskinz
    exp: int              # Timestamp Unix d'expiration


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def _compute_sig(secret: str, payload_b64: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_relay_token(token: str) -> RelayPayload:
    """
    Décode et vérifie un token de relais. Lève RelayTokenError si invalide,
    signature incorrecte, ou expiré. Ne fait AUCUNE requête DB — c'est une
    vérification cryptographique pure.
    """
    if not settings.JKPAY_RELAY_SECRET:
        # Fail-closed : si le secret n'est pas configuré, on refuse tout,
        # plutôt que de laisser passer des tokens non vérifiés.
        raise RelayTokenError("Service de relais non configuré.")

    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError:
        raise RelayTokenError("Format de token invalide.")

    expected_sig = _compute_sig(settings.JKPAY_RELAY_SECRET, payload_b64)
    if not hmac.compare_digest(expected_sig, sig):
        raise RelayTokenError("Signature invalide.")

    try:
        raw = _b64url_decode(payload_b64)
        data: dict[str, Any] = json.loads(raw)
    except Exception:
        raise RelayTokenError("Payload illisible.")

    exp = data.get("exp")
    if not isinstance(exp, int) or int(time.time()) > exp:
        raise RelayTokenError("Ce lien de dépôt a expiré, redemande-le depuis JessiKaPay.")

    amount = data.get("amount")
    if not isinstance(amount, int) or amount <= 0:
        raise RelayTokenError("Montant invalide dans le token.")

    try:
        return RelayPayload(
            tx_id=str(data["tx_id"]),
            amount=amount,
            phone=str(data["phone"]),
            operator=str(data["operator"]),
            country=str(data["country"]),
            customer_name=str(data.get("customer_name") or "Client"),
            tgid=str(data.get("tgid") or ""),
            exp=exp,
        )
    except KeyError as e:
        raise RelayTokenError(f"Champ manquant dans le token: {e}")


def sign_outgoing_notification(raw_body: bytes) -> tuple[str, str]:
    """
    Signe le corps de la requête envoyée à JessiKaPay pour notifier un dépôt.
    Réutilise EXACTEMENT le même algorithme que jessicapay-backend/app/services/
    hmac_signature.py (compute_signature), avec JKPAY_RELAY_SECRET comme clé
    partagée, pour que JessiKaPay puisse vérifier avec sa fonction existante
    verify_signature() sans rien dupliquer côté JessiKaPay.

    Retourne (timestamp, signature) à mettre dans les headers X-Timestamp / X-Signature.
    """
    timestamp = str(int(time.time()))
    payload = f"{timestamp}.{raw_body.decode('utf-8')}"
    signature = hmac.new(
        settings.JKPAY_RELAY_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return timestamp, signature
