from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import get_current_user
from app.db.models import User
from app.schemas.market import HoldingChartResponse, ChartPoint

router = APIRouter(prefix="/market", tags=["market"])

RANGE_MAP: dict[str, tuple[str, str]] = {
    "1d": ("1d", "5m"),
    "1w": ("5d", "15m"),
    "1m": ("1mo", "1d"),
    "3m": ("3mo", "1d"),
    "ytd": ("ytd", "1d"),
    "1y": ("1y", "1d"),
}

PERIOD_LABEL: dict[str, str] = {
    "1d": "Today",
    "1w": "Past week",
    "1m": "Past month",
    "3m": "Past 3 months",
    "ytd": "Year to date",
    "1y": "Past year",
}

# Simple in-memory cache to avoid Yahoo rate-limit spikes.
# key -> (cached_at_epoch_seconds, response_payload_dict)
CHART_CACHE: dict[str, tuple[int, dict]] = {}
CACHE_TTL_SECONDS = 60


@router.get("/chart/{symbol}", response_model=HoldingChartResponse)
def get_holding_chart(
    symbol: str,
    range: str = Query("1d", pattern="^(1d|1w|1m|3m|ytd|1y)$"),
    _: User = Depends(get_current_user),
):
    normalized = symbol.upper().strip()
    yahoo_range, interval = RANGE_MAP[range]
    cache_key = f"{normalized}:{range}"
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Return fresh cached payload when available.
    cached = CHART_CACHE.get(cache_key)
    if cached and (now_ts - cached[0] <= CACHE_TTL_SECONDS):
        return HoldingChartResponse(**cached[1])

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{normalized}"
    include_pre_post = "true" if range == "1d" else "false"
    params = {"range": yahoo_range, "interval": interval, "includePrePost": include_pre_post}
    headers = {
        "User-Agent": "Mozilla/5.0 (AIStockAssistant/1.0)",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)

        # If rate-limited, fall back to stale cache.
        if resp.status_code == 429:
            if cached:
                return HoldingChartResponse(**cached[1])
            raise HTTPException(status_code=429, detail="Market data provider rate-limited. Please retry in 1 minute.")

        resp.raise_for_status()
        payload = resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        if cached:
            return HoldingChartResponse(**cached[1])
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {exc}")

    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        if cached:
            return HoldingChartResponse(**cached[1])
        raise HTTPException(status_code=404, detail="No market data found")

    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    closes = quote.get("close") or []

    points: list[ChartPoint] = []
    for ts, px in zip(timestamps, closes):
        if ts is None or px is None:
            continue
        points.append(ChartPoint(ts=int(ts), price=float(px)))

    if not points:
        if cached:
            return HoldingChartResponse(**cached[1])
        raise HTTPException(status_code=404, detail="No chart points available")

    previous_close = float(meta.get("previousClose") or points[0].price)
    current_price = float(meta.get("regularMarketPrice") or points[-1].price)

    # Robinhood-like behavior: 1D compares vs previous close, other ranges compare
    # current price vs first visible point in selected time window.
    reference_price = previous_close if range == "1d" else float(points[0].price)
    change = current_price - reference_price
    change_pct = (change / reference_price * 100.0) if reference_price else 0.0

    response_dict = {
        "symbol": normalized,
        "range": range,
        "period_label": PERIOD_LABEL.get(range, "Period"),
        "currency": str(meta.get("currency") or "USD"),
        "current_price": current_price,
        "previous_close": previous_close,
        "reference_price": reference_price,
        "change": change,
        "change_percent": change_pct,
        "points": [p.model_dump() for p in points],
    }

    CHART_CACHE[cache_key] = (now_ts, response_dict)
    return HoldingChartResponse(**response_dict)
