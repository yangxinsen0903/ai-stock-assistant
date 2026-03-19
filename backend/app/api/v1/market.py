from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.db.models import User, Holding, BrokerAccount
from app.db.session import get_db
from app.schemas.market import HoldingChartResponse, PortfolioChartResponse, ChartPoint
from app.services.snaptrade_service import SnapTradeService

router = APIRouter(prefix="/market", tags=["market"])

RANGE_MAP: dict[str, tuple[str, str]] = {
    # Requested cadence profile:
    # 1D minute-level, 1W hour-level, 1M hour-level,
    # 3M day-level, 1Y+ day-level.
    "1d": ("1d", "1m"),
    "1w": ("5d", "60m"),
    "1m": ("1mo", "60m"),
    "3m": ("3mo", "1d"),
    "ytd": ("ytd", "1d"),
    "1y": ("1y", "1d"),
    "all": ("max", "1d"),
}

PERIOD_LABEL: dict[str, str] = {
    "1d": "Today",
    "1w": "Past week",
    "1m": "Past month",
    "3m": "Past 3 months",
    "ytd": "Year to date",
    "1y": "Past year",
    "all": "All time",
}

# key -> (cached_at_epoch_seconds, response_payload_dict)
CHART_CACHE: dict[str, tuple[int, dict]] = {}
CACHE_TTL_SECONDS = 60


def _normalize_points(raw_points: list[ChartPoint], range_key: str) -> list[ChartPoint]:
    # Robinhood-like look: keep shape crisp (no curve smoothing), only clean ordering and density.
    sorted_points = sorted(raw_points, key=lambda p: p.ts)
    dedup: dict[int, float] = {}
    for p in sorted_points:
        dedup[p.ts] = p.price
    points = [ChartPoint(ts=ts, price=px) for ts, px in sorted(dedup.items(), key=lambda x: x[0])]

    if len(points) < 3:
        return points

    # For dense ranges, bucket by fixed cadence and keep LAST trade in bucket
    # to preserve directional steps (instead of averaging curves).
    target_step = {
        "1d": 60,      # 1 minute
        "1w": 3600,    # 1 hour
        "1m": 3600,    # 1 hour
        "3m": 86400,   # 1 day
        "ytd": 86400,
        "1y": 86400,
        "all": 86400,
    }.get(range_key)
    if target_step:
        bucket_last: dict[int, ChartPoint] = {}
        for p in points:
            b = (p.ts // target_step) * target_step
            bucket_last[b] = p
        points = [bucket_last[k] for k in sorted(bucket_last.keys())]

    return points


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

    raw_points: list[ChartPoint] = []
    for ts, px in zip(timestamps, closes):
        if ts is None or px is None:
            continue
        raw_points.append(ChartPoint(ts=int(ts), price=float(px)))

    points = _normalize_points(raw_points, range_key)

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
    range: str = Query("1d", pattern="^(1d|1w|1m|3m|ytd|1y|all)$"),
    _: User = Depends(get_current_user),
):
    return HoldingChartResponse(**_load_chart_payload(symbol=symbol, range_key=range))


@router.get("/portfolio/chart", response_model=PortfolioChartResponse)
def get_portfolio_chart(
    range: str = Query("1d", pattern="^(1d|1w|1m|3m|ytd|1y|all)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Prefer SnapTrade account snapshots for more accurate current portfolio value.
    broker = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == current_user.id, BrokerAccount.broker == "robinhood")
        .first()
    )

    snapshots: list[dict] = []
    if broker and broker.external_user_id and broker.access_token:
        try:
            snapshots = SnapTradeService().fetch_account_snapshots(
                snap_user_id=broker.external_user_id,
                user_secret=broker.access_token,
            )
        except Exception:
            snapshots = []

    symbol_units: dict[str, float] = {}
    symbol_current_price: dict[str, float] = {}
    total_current_value = 0.0
    positions_current_value = 0.0
    total_open_pnl = 0.0

    # Build from snapshots when possible.
    for account in snapshots:
        if not isinstance(account, dict):
            continue

        total_value_obj = account.get("total_value") or {}
        if isinstance(total_value_obj, dict):
            total_current_value += float(total_value_obj.get("value") or 0.0)

        positions = account.get("positions") or []
        if isinstance(positions, list):
            for p in positions:
                if not isinstance(p, dict):
                    continue
                # symbol extraction
                symbol = None
                sym_obj = p.get("symbol")
                if isinstance(sym_obj, dict):
                    inner = sym_obj.get("symbol")
                    if isinstance(inner, dict):
                        symbol = inner.get("symbol") or inner.get("raw_symbol")
                    elif isinstance(inner, str):
                        symbol = inner
                symbol = (symbol or "").upper()
                if not symbol:
                    continue

                units = float(p.get("units") or 0.0)
                price = float(p.get("price") or 0.0)
                if units <= 0 or price <= 0:
                    continue

                symbol_units[symbol] = symbol_units.get(symbol, 0.0) + units
                symbol_current_price[symbol] = price
                positions_current_value += units * price
                total_open_pnl += float(p.get("open_pnl") or 0.0)

    # Fallback to local holdings if snapshot unavailable.
    if not symbol_units:
        holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
        if not holdings:
            raise HTTPException(status_code=404, detail="No holdings available")
        for h in holdings:
            symbol_units[h.symbol.upper()] = symbol_units.get(h.symbol.upper(), 0.0) + float(h.shares)

    curves: list[tuple[float, list[dict], float]] = []
    for symbol, units in symbol_units.items():
        try:
            chart = _load_chart_payload(symbol=symbol, range_key=range)
        except HTTPException:
            continue

        points = chart.get("points") or []
        current_price = symbol_current_price.get(symbol) or float(chart.get("current_price") or 0.0)
        if not points or current_price <= 0:
            continue

        position_value = units * current_price
        curves.append((position_value, points, current_price))

    if not curves:
        raise HTTPException(status_code=404, detail="No portfolio chart data")

    # Include cash/non-position residual so current value aligns closer to broker total.
    cash_component = 0.0
    if total_current_value > 0:
        cash_component = max(total_current_value - positions_current_value, 0.0)

    ref_points = curves[0][1]
    portfolio_points: list[ChartPoint] = []

    for rp in ref_points:
        ts = int(rp["ts"])
        total_value = cash_component
        for position_value, points, current_price in curves:
            nearest = min(points, key=lambda p: abs(int(p["ts"]) - ts))
            nearest_price = float(nearest["price"])
            ratio = nearest_price / current_price if current_price else 0.0
            total_value += position_value * ratio
        portfolio_points.append(ChartPoint(ts=ts, price=total_value))

    if not portfolio_points:
        raise HTTPException(status_code=404, detail="No portfolio points available")

    current_value = float(total_current_value if total_current_value > 0 else portfolio_points[-1].price)

    if range == "all" and total_current_value > 0 and total_open_pnl != 0:
        # Robinhood-like all-time gain/loss: current value vs invested cost basis proxy.
        change = float(total_open_pnl)
        reference_value = float(max(current_value - change, 1e-6))

        # Re-anchor reconstructed curve to match all-time endpoints.
        actual_ref = float(portfolio_points[0].price)
        actual_cur = float(portfolio_points[-1].price)
        if actual_cur != actual_ref:
            a = (current_value - reference_value) / (actual_cur - actual_ref)
            b = current_value - a * actual_cur
            portfolio_points = [ChartPoint(ts=p.ts, price=a * p.price + b) for p in portfolio_points]
    else:
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
