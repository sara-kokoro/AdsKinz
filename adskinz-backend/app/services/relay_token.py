"""
AdsKinz — Vérification du token de relais JessiKaPay
=========================================================

Ce module authentifie les requêtes qui arrivent sur pay.adskinz.me/{token}.
Le token est généré côté JessiKaPay (voir jessicapay-backend/app/services/
relay_token.py, fonction sign_relay_payload) et contient toutes les infos
du dépôt (montant, téléphone, opérateur, ET DEPUIS PEU webhook_path)
signées avec un secret partagé.

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

── webhook_path ──────────────────────────────────────────────────────
JessiKaPay décide, via ce champ signé, quel endpoint chez lui MoneyFusion
doit notifier (dépôt normal vs dépôt externe pour une app tierce). adskinz
fait confiance à cette valeur exactement comme il fait confiance à `amount`
— elle est signée par JessiKaPay, adskinz ne fait que la relayer. Une
validation basique (préfixe "/webhooks/") reste appliquée par précaution.
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

DEFAULT_WEBHOOK_PATH = "/webhooks/moneyfusion/deposit"


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
    tgid: str             # Telegram user id JessiKaPay, pour traçabilité côté adskinz
    webhook_path: str     # Chemin JessiKaPay à notifier une fois payé (voir docstring)
    status_path: str      # Chemin JessiKaPay à interroger pour le polling de statut
    exp: int               # Timestamp Unix d'expiration


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

    webhook_path = str(data.get("webhook_path") or DEFAULT_WEBHOOK_PATH)
    if not webhook_path.startswith("/webhooks/"):
        # Précaution : un token malformé ou d'une version antérieure ne doit
        # jamais faire pointer le webhook MoneyFusion n'importe où.
        webhook_path = DEFAULT_WEBHOOK_PATH

    tx_id_str = str(data.get("tx_id", ""))
    status_path = str(data.get("status_path") or f"/deposit/status/{tx_id_str}")

    try:
        return RelayPayload(
            tx_id=str(data["tx_id"]),
            amount=amount,
            phone=str(data["phone"]),
            operator=str(data["operator"]),
            country=str(data["country"]),
            customer_name=str(data.get("customer_name") or "Client"),
            tgid=str(data.get("tgid") or ""),
            webhook_path=webhook_path,
            status_path=status_path,
            exp=exp,
        )
    except KeyError as e:
        raise RelayTokenError(f"Champ manquant dans le token: {e}")
