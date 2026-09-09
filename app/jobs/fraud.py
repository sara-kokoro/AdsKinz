"""Periodic fraud and anomaly scans."""

from __future__ import annotations

from app.database import session_scope
from app.services import fraud_service


async def fraud_scan() -> dict:
    """Run all conservative fraud detectors in one database transaction."""
    async with session_scope() as session:
        campaign_ctr = await fraud_service.scan_campaign_ctr(session)
        channel_spikes = await fraud_service.scan_channel_view_spikes(session)
        unbilled_clicks = await fraud_service.scan_unbilled_click_ratio(session)
        ctr_baseline = await fraud_service.scan_channel_ctr_baseline(session)
        view_bursts = await fraud_service.scan_view_bursts(session)
    return {
        "campaign_ctr_flagged": campaign_ctr,
        "channel_view_spikes_flagged": channel_spikes,
        "unbilled_click_ratio_flagged": unbilled_clicks,
        "channel_ctr_baseline_flagged": ctr_baseline,
        "view_bursts_flagged": view_bursts,
    }
