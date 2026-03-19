from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


class MarketIntelService:
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (AIStockAssistant/1.0)",
        "Accept": "application/json",
    }

    @classmethod
    def market_snapshot(cls) -> dict[str, Any]:
        symbols = ["SPY", "QQQ", "DIA", "^VIX", "^TNX"]
        quotes = cls._get_quotes(symbols)
        mapped = {q.get("symbol", ""): q for q in quotes}

        def item(symbol: str, label: str) -> dict[str, Any]:
            q = mapped.get(symbol, {})
            return {
                "symbol": symbol,
                "label": label,
                "price": q.get("regularMarketPrice"),
                "change_pct": q.get("regularMarketChangePercent"),
            }

        return {
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "indices": [
                item("SPY", "S&P 500 ETF"),
                item("QQQ", "Nasdaq 100 ETF"),
                item("DIA", "Dow 30 ETF"),
            ],
            "volatility": item("^VIX", "VIX"),
            "rates": item("^TNX", "US 10Y Yield"),
        }

    @classmethod
    def holdings_news(cls, symbols: list[str], limit_per_symbol: int = 3) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for s in symbols:
            normalized = s.upper().strip()
            if not normalized:
                continue
            out[normalized] = cls._search_news(normalized)[:limit_per_symbol]
        return out

    @classmethod
    def earnings_calendar(cls, symbols: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for s in symbols:
            normalized = s.upper().strip()
            if not normalized:
                continue
            out[normalized] = cls._earnings_for_symbol(normalized)
        return out

    @classmethod
    def _get_quotes(cls, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": ",".join(symbols)}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params=params, headers=cls._HEADERS)
            r.raise_for_status()
            body = r.json()
            return (((body.get("quoteResponse") or {}).get("result")) or [])
        except Exception:
            return []

    @classmethod
    def _search_news(cls, symbol: str) -> list[dict[str, Any]]:
        # Yahoo search endpoint includes a `news` array without auth for many symbols.
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {"q": symbol, "quotesCount": 1, "newsCount": 8}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params=params, headers=cls._HEADERS)
            r.raise_for_status()
            body = r.json()
            news = body.get("news") or []
            out = []
            for n in news:
                out.append(
                    {
                        "title": n.get("title"),
                        "publisher": n.get("publisher"),
                        "link": n.get("link"),
                        "published_utc": n.get("providerPublishTime"),
                    }
                )
            return out
        except Exception:
            return []

    @classmethod
    def _earnings_for_symbol(cls, symbol: str) -> dict[str, Any]:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
        params = {"modules": "calendarEvents,price"}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params=params, headers=cls._HEADERS)
            r.raise_for_status()
            body = r.json()
            result = (((body.get("quoteSummary") or {}).get("result")) or [None])[0] or {}
            cal = (result.get("calendarEvents") or {}).get("earnings") or {}
            ed = cal.get("earningsDate") or []
            next_earnings = None
            if ed and isinstance(ed, list):
                raw = ed[0] or {}
                next_earnings = raw.get("fmt") or raw.get("raw")

            return {
                "next_earnings": next_earnings,
                "eps_estimate": (cal.get("earningsAverage") or {}).get("raw"),
                "revenue_estimate": (cal.get("revenueAverage") or {}).get("raw"),
            }
        except Exception:
            return {
                "next_earnings": None,
                "eps_estimate": None,
                "revenue_estimate": None,
            }
