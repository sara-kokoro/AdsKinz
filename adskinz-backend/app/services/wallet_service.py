"""Watch-only wallet service.

Security model — this is the part of the system that must never be weakened:

* The service knows the **extended public keys** (``XPUB_TRC20``,
  ``XPUB_BEP20``) and one fixed ``TON_DEPOSIT_ADDRESS``. From an xpub it can
  derive receiving addresses, but it cannot derive any private key.
* The BIP-39 mnemonic seed is **never** present in this codebase, in the
  database, or in an environment variable. Consolidating deposits ("sweep") is
  a manual operation the operator runs locally with ``scripts/sweep.py``, which
  is deliberately excluded from the Docker image.
* No outgoing transaction is ever signed from a derived deposit address.
  Publisher payouts are sent from a completely separate hot wallet
  (``WALLET_2_PRIVATE_KEY``) that never receives advertiser deposits.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import ConfigurationError, ValidationError
from app.models.accounts import Advertiser
from app.models.finance import WalletAddress
from app.schemas.billing import (
    NETWORK_LABELS,
    NETWORK_WARNINGS,
    DepositAddressResponse,
)

logger = logging.getLogger(__name__)

TRC20_PATH = "m/44'/195'/0'/0/{index}"
BSC_PATH = "m/44'/60'/0'/0/{index}"

SUPPORTED_NETWORKS = ("ton", "trc20", "bnb")


# --------------------------------------------------------------------------- #
# Address derivation
# --------------------------------------------------------------------------- #
def _derive_tron(xpub: str, index: int) -> str:
    """Derive a TRON receiving address from the account-level xpub."""
    from bip_utils import Bip44, Bip44Changes, Bip44Coins

    ctx = Bip44.FromExtendedKey(xpub, Bip44Coins.TRON)
    return (
        ctx.Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
        .PublicKey()
        .ToAddress()
    )


def _derive_bsc(xpub: str, index: int) -> str:
    """Derive a BNB Smart Chain (BEP20) receiving address."""
    from bip_utils import Bip44, Bip44Changes, Bip44Coins

    ctx = Bip44.FromExtendedKey(xpub, Bip44Coins.BINANCE_SMART_CHAIN)
    return (
        ctx.Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
        .PublicKey()
        .ToAddress()
    )


def derive_address(network: str, index: int) -> str:
    """Public entry point for derivation. Never touches a private key."""
    if network == "trc20":
        if not settings.XPUB_TRC20:
            raise ConfigurationError("TRC20 deposits are not configured on this instance.")
        return _derive_tron(settings.XPUB_TRC20, index)
    if network == "bnb":
        if not settings.XPUB_BEP20:
            raise ConfigurationError("BNB deposits are not configured on this instance.")
        return _derive_bsc(settings.XPUB_BEP20, index)
    if network == "ton":
        if not settings.TON_DEPOSIT_ADDRESS:
            raise ConfigurationError("TON deposits are not configured on this instance.")
        # TON uses a single shared address; advertisers are told apart by memo.
        return settings.TON_DEPOSIT_ADDRESS
    raise ValidationError("Unsupported deposit network.")


def memo_for_advertiser(advertiser: Advertiser) -> str:
    """Deterministic, short, collision-free TON memo derived from the account.

    Using the HD index keeps it human-typable, which matters because the user
    copies it by hand into their wallet.
    """
    return f"AK{advertiser.hd_wallet_index:06d}"


def derivation_path(network: str, index: int) -> str | None:
    if network == "trc20":
        return TRC20_PATH.format(index=index)
    if network == "bnb":
        return BSC_PATH.format(index=index)
    return None


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
async def get_or_create_address(
    session: AsyncSession, advertiser: Advertiser, network: str
) -> WalletAddress:
    """Return the advertiser's deposit address for a network, deriving once.

    The row is a cache: derivation is deterministic, but persisting it lets the
    deposit watcher scan a small indexed table instead of re-deriving thousands
    of addresses on every poll.
    """
    network = network.strip().lower()
    if network not in SUPPORTED_NETWORKS:
        raise ValidationError("Unsupported deposit network. Use ton, trc20 or bnb.")

    existing = (
        await session.execute(
            select(WalletAddress).where(
                WalletAddress.advertiser_id == advertiser.id,
                WalletAddress.network == network,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    index = advertiser.hd_wallet_index
    record = WalletAddress(
        advertiser_id=advertiser.id,
        network=network,
        address=derive_address(network, index),
        memo=memo_for_advertiser(advertiser) if network == "ton" else None,
        derivation_path=derivation_path(network, index),
        derivation_index=index if network != "ton" else None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info(
        "wallet.address_derived advertiser=%s network=%s index=%s",
        advertiser.id, network, index,
    )
    return record


def _qr_payload(network: str, address: str, memo: str | None) -> str:
    """Wallet-scannable URI, so the user does not retype the address."""
    if network == "ton":
        base = f"ton://transfer/{address}"
        return f"{base}?text={memo}" if memo else base
    if network == "trc20":
        return f"tron:{address}"
    return f"ethereum:{address}@56"


async def build_deposit_address_response(
    session: AsyncSession, advertiser: Advertiser, network: str
) -> DepositAddressResponse:
    record = await get_or_create_address(session, advertiser, network)
    fee = settings.TRC20_DEPOSIT_FEE_USDT if network == "trc20" else Decimal("0.00")
    confirmations = {
        "ton": settings.DEPOSIT_MIN_CONFIRMATIONS_TON,
        "trc20": settings.DEPOSIT_MIN_CONFIRMATIONS_TRC20,
        "bnb": settings.DEPOSIT_MIN_CONFIRMATIONS_BEP20,
    }.get(network, 1)

    return DepositAddressResponse(
        network=network,  # type: ignore[arg-type]
        label=NETWORK_LABELS[network],
        address=record.address,
        memo=record.memo,
        memo_required=network == "ton",
        qr_payload=_qr_payload(network, record.address, record.memo),
        fee_usdt=fee,
        fee_note=(
            f"A {fee} USDT network fee is deducted from every TRC20 deposit."
            if fee > 0
            else None
        ),
        confirmations_required=confirmations,
        warning=NETWORK_WARNINGS[network],
    )


async def address_index(session: AsyncSession) -> dict[str, tuple[uuid.UUID, str]]:
    """Map ``address|memo`` -> ``(advertiser_id, network)`` for the watcher."""
    rows = (await session.execute(select(WalletAddress))).scalars().all()
    index: dict[str, tuple[uuid.UUID, str]] = {}
    for row in rows:
        if row.network == "ton":
            if row.memo:
                index[f"ton:{row.memo.lower()}"] = (row.advertiser_id, "ton")
        else:
            index[f"{row.network}:{row.address.lower()}"] = (row.advertiser_id, row.network)
    return index


def net_credited_amount(network: str, gross: Decimal) -> tuple[Decimal, Decimal]:
    """Split an on-chain amount into ``(net_credited, fee_withheld)``."""
    if network == "trc20":
        fee = settings.TRC20_DEPOSIT_FEE_USDT
        net = gross - fee
        if net <= 0:
            return Decimal("0.00"), gross
        return net.quantize(Decimal("0.01")), fee
    return gross.quantize(Decimal("0.01")), Decimal("0.00")


# --------------------------------------------------------------------------- #
# Payouts (Wallet 2 only)
# --------------------------------------------------------------------------- #
def payout_wallet_configured() -> bool:
    """Whether the dedicated payout wallet is available.

    This wallet is entirely separate from the deposit wallet: its key signs
    outgoing publisher payouts and nothing else, and it never holds the funds
    received on derived deposit addresses.
    """
    return bool(settings.WALLET_2_PRIVATE_KEY) and settings.ENABLE_AUTO_PAYOUT


def assert_never_sweeps_deposits() -> None:
    """Documented guard rail.

    Deposit addresses derived from Wallet 1 are watch-only in this service.
    Any attempt to build a spending transaction from them is a programming
    error: consolidation is manual, local, and outside the deployed container.
    """
    raise ConfigurationError(
        "Sweeping deposit addresses is a manual operation and is not available "
        "from the deployed service."
    )
