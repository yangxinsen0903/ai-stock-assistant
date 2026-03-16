from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.db.models import User, Holding
from app.db.session import get_db
from app.schemas.market import HoldingChartResponse, PortfolioChartResponse, ChartPoint

router = APIRouter(prefix="/market", tags=["market"])

RANGE_MAP: dict[str, tuple[str, str]] = {
    "1d": ("1d", "5m"),
    "1w": ("5d", "15m"),
    "1m": ("1mo", "1d"),
    "3m": ("3mo", "1d"),
    "ytd": ("ytd", "1d"),
    "1y": ("1y", "1d"),
    "5y": ("5y", "1wk"),
    "max": ("max", "1mo"),
}

PERIOD_LABEL: dict[str, str] = {
    "1d": "Today",
    "1w": "Past week",
    "1m": "Past month",
    "3m": "Past 3 months",
    "ytd": "Year to date",
    "1y": "Past year",
    "5y": "Past 5 years",
    "max": "All time",
}

# key -> (cached_at_epoch_seconds, response_payload_dict)
CHART_CACHE: dict[str, tuple[int, dict]] = {}
CACHE_TTL_SECONDS = 60


def _load_chart_payload(symbol: str, range_key: str) -> dict:
    normalized = symbol.upper().strip()
    yahoo_range, interval = RANGE_MAP[range_key]
    cache_key = f"{normalized}:{range_key}"
    now_ts = int(datetime.now(timezone.utc).timestamp())

    cached = CHART_CACHE.get(cache_key)
    if cached and (now_ts - cached[0] <= CACHE_TTL_SECONDS):
        return cached[1]

    include_pre_post = "true" if range_key == "1d" else "false"
    params = {"range": yahoo_range, "interval": interval, "includePrePost": include_pre_post}
    headers = {
        "User-Agent": "Mozilla/5.0 (AIStockAssistant/1.0)",
        "Accept": "application/json",
    }

    def fetch_chart_payload(symbol_code: str) -> dict:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol_code}"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params=params, headers=headers)
        if r.status_code == 429:
            raise HTTPException(status_code=429, detail="Market data provider rate-limited. Please retry in 1 minute.")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No market data for {symbol_code}")
        r.raise_for_status()
        return r.json()

    try:
        payload = fetch_chart_payload(normalized)
    except HTTPException as exc:
        # Common crypto fallback for Yahoo symbols: DOGE -> DOGE-USD
        if exc.status_code == 404 and "-" not in normalized:
            try:
                payload = fetch_chart_payload(f"{normalized}-USD")
                normalized = f"{normalized}-USD"
                cache_key = f"{normalized}:{range_key}"
            except HTTPException:
                if cached:
                    return cached[1]
                raise
        else:
            if cached:
                return cached[1]
            raise
    except Exception as exc:
        if cached:
            return cached[1]
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {exc}")

    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        if cached:
            return cached[1]
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
            return cached[1]
        raise HTTPException(status_code=404, detail="No chart points available")

    previous_close = float(meta.get("previousClose") or points[0].price)
    current_price = float(meta.get("regularMarketPrice") or points[-1].price)
    reference_price = previous_close if range_key == "1d" else float(points[0].price)
    change = current_price - reference_price
    change_pct = (change / reference_price * 100.0) if reference_price else 0.0

    response_dict = {
        "symbol": normalized,
        "range": range_key,
        "period_label": PERIOD_LABEL.get(range_key, "Period"),
        "currency": str(meta.get("currency") or "USD"),
        "current_price": current_price,
        "previous_close": previous_close,
        "reference_price": reference_price,
        "change": change,
        "change_percent": change_pct,
        "points": [p.model_dump() for p in points],
    }

    CHART_CACHE[cache_key] = (now_ts, response_dict)
    return response_dict


@router.get("/chart/{symbol}", response_model=HoldingChartResponse)
def get_holding_chart(
    symbol: str,
    range: str = Query("1d", pattern="^(1d|1w|1m|3m|ytd|1y|5y|max)$"),
    _: User = Depends(get_current_user),
):
    return HoldingChartResponse(**_load_chart_payload(symbol=symbol, range_key=range))


@router.get("/portfolio/chart", response_model=PortfolioChartResponse)
def get_portfolio_chart(
    range: str = Query("1d", pattern="^(1d|1w|1m|3m|ytd|1y|5y|max)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
    if not holdings:
        raise HTTPException(status_code=404, detail="No holdings available")

    curves: list[tuple[float, list[dict], float]] = []
    # tuple: (position_current_value, chart_points, chart_current_price)
    for h in holdings:
        try:
            chart = _load_chart_payload(symbol=h.symbol, range_key=range)
        except HTTPException:
            # Skip symbols unavailable from market data provider for this timeframe.
            continue

        points = chart.get("points") or []
        current_price = float(chart.get("current_price") or 0.0)
        if not points or current_price <= 0:
            continue
        position_value = float(h.shares) * current_price
        curves.append((position_value, points, current_price))

    if not curves:
        raise HTTPException(status_code=404, detail="No portfolio chart data")

    # Use first series timestamps as reference timeline; map other series by nearest point.
    ref_points = curves[0][1]
    portfolio_points: list[ChartPoint] = []

    for rp in ref_points:
        ts = int(rp["ts"])
        total_value = 0.0
        for position_value, points, current_price in curves:
            # nearest by abs ts
            nearest = min(points, key=lambda p: abs(int(p["ts"]) - ts))
            nearest_price = float(nearest["price"])
            ratio = nearest_price / current_price if current_price else 0.0
            total_value += position_value * ratio
        portfolio_points.append(ChartPoint(ts=ts, price=total_value))

    if not portfolio_points:
        raise HTTPException(status_code=404, detail="No portfolio points available")

    current_value = float(portfolio_points[-1].price)
    reference_value = float(portfolio_points[0].price)
    change = current_value - reference_value
    change_pct = (change / reference_value * 100.0) if reference_value else 0.0

    return PortfolioChartResponse(
        range=range,
        period_label=PERIOD_LABEL.get(range, "Period"),
        currency="USD",
        current_value=current_value,
        reference_value=reference_value,
        change=change,
        change_percent=change_pct,
        points=portfolio_points,
    )
