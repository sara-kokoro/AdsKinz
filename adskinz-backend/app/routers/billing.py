"""Billing endpoints for advertisers.

    GET /billing/deposit-address?network=ton|trc20|bnb
    GET /billing/deposits
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import CurrentAdvertiserDep, PaginationDep, SessionDep, verify_deposit_rate_limit
from app.models.accounts import LedgerEntry
from app.models.finance import Deposit
from app.schemas.billing import (
    NETWORK_LABELS,
    BalanceResponse,
    DepositAddressResponse,
    DepositItem,
    DepositListResponse,
    LedgerItem,
    LedgerResponse,
)
from app.services import billing_service, wallet_service
from app.jobs.deposits import verify_deposit_address

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/deposit-address",
    response_model=DepositAddressResponse,
    summary="Deposit address for a network",
)
async def deposit_address(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
    network: Literal["ton", "trc20", "bnb"] = Query(
        ..., description="Blockchain network to deposit USDT on"
    ),
) -> DepositAddressResponse:
    """Return the advertiser's watch-only deposit address.

    TON reuses one platform address plus a per-advertiser memo; TRC20 and BNB
    get a dedicated address derived from the corresponding extended public key.
    No private key is involved at any point.
    """
    return await wallet_service.build_deposit_address_response(
        session, advertiser, network
    )


@router.post(
    "/deposit-address/verify",
    dependencies=[Depends(verify_deposit_rate_limit)],
    summary="Check the chain right now for a deposit on this network",
)
async def deposit_address_verify(
    advertiser: CurrentAdvertiserDep,
    network: Literal["ton", "trc20", "bnb"] = Query(
        ..., description="Blockchain network to check"
    ),
) -> dict:
    """On-demand check, for the "Verify" button on the deposit page — scans
    only this advertiser's own address instead of waiting for the next
    scheduled cycle (up to two minutes away)."""
    return await verify_deposit_address(advertiser.id, network)


@router.get(
    "/deposits",
    response_model=DepositListResponse,
    summary="Deposit history",
)
async def list_deposits(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
    page: PaginationDep,
) -> DepositListResponse:
    rows = (
        (
            await session.execute(
                select(Deposit)
                .where(Deposit.advertiser_id == advertiser.id)
                .order_by(Deposit.created_at.desc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )

    items = [
        DepositItem(
            id=str(row.id),
            network=row.network,  # type: ignore[arg-type]
            networkLabel=NETWORK_LABELS.get(row.network, row.network.upper()),
            amount=row.amount_usd,
            grossAmount=row.gross_amount_usd,
            fee=row.fee_usd,
            status=row.status,  # type: ignore[arg-type]
            txHash=row.tx_hash,
            address=row.derived_address,
            memo=row.memo,
            createdAt=row.created_at,
            confirmedAt=row.confirmed_at,
        )
        for row in rows
    ]
    return DepositListResponse(
        items=items, total=len(items), balance=advertiser.balance_usd
    )


@router.get("/balance", response_model=BalanceResponse, summary="Current balance")
async def balance(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> BalanceResponse:
    from app.config import settings

    committed = await billing_service.committed_active_budget(session, advertiser.id)
    threshold = billing_service.q2(committed * settings.LOW_BALANCE_ALERT_RATIO)
    return BalanceResponse(
        balance=advertiser.balance_usd,
        activeBudget=committed,
        lifetimeSpend=advertiser.lifetime_spend_usd,
        lowBalance=committed > 0 and advertiser.balance_usd < threshold,
        lowBalanceThreshold=threshold,
    )


@router.get("/ledger", response_model=LedgerResponse, summary="Balance movements")
async def ledger(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
    page: PaginationDep,
) -> LedgerResponse:
    rows = (
        (
            await session.execute(
                select(LedgerEntry)
                .where(
                    LedgerEntry.account_type == "advertiser",
                    LedgerEntry.account_id == advertiser.id,
                )
                .order_by(LedgerEntry.created_at.desc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .all()
    )
    return LedgerResponse(
        items=[
            LedgerItem(
                id=str(row.id),
                type=row.entry_type,
                amount=row.amount_usd,
                balanceAfter=row.balance_after_usd,
                description=row.description,
                createdAt=row.created_at,
            )
            for row in rows
        ],
        total=len(rows),
    )
