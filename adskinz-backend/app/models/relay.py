"""AdsKinz — Table de suivi des dépôts JessiKaPay relayés via pay.adskinz.me.

Cette table N'A RIEN à voir avec les dépôts publicitaires d'adskinz
(voir models/finance.py::Deposit). Elle sert uniquement à tracer le
statut (pending/success/failed) des paiements MoneyFusion initiés pour
le compte de JessiKaPay, le temps que la notification soit bien
délivrée au backend JessiKaPay.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin


class RelayDeposit(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "relay_deposits"

    # tx_id JessiKaPay (ex: JP-TXN-XXXXXXXX) — clé de corrélation, unique.
    jkpay_tx_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    tgid: Mapped[str] = mapped_column(String(64), index=True, default="")
    amount: Mapped[int] = mapped_column(Integer)
    phone: Mapped[str] = mapped_column(String(32))
    operator: Mapped[str] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(8))

    # token MoneyFusion retourné par create_payment, sert à retrouver la
    # transaction quand le webhook MoneyFusion arrive.
    moneyfusion_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # pending | success | failed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # Devient True une fois que JessiKaPay a confirmé (200 OK) avoir reçu
    # et traité la notification de crédit — sert de garde anti-perte si
    # l'appel réseau vers JessiKaPay échoue et doit être retenté.
    jkpay_notified: Mapped[bool] = mapped_column(default=False)
    jkpay_notify_attempts: Mapped[int] = mapped_column(Integer, default=0)
