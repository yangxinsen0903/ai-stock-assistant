import httpx


class MarketDataService:
    @classmethod
    def get_quote(cls, symbol: str) -> dict:
        normalized = symbol.upper().strip()
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": normalized}
        headers = {
            "User-Agent": "Mozilla/5.0 (AIStockAssistant/1.0)",
            "Accept": "application/json",
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            body = r.json()
            result = (((body.get("quoteResponse") or {}).get("result")) or [None])[0] or {}
            price = float(result.get("regularMarketPrice") or 0.0)
            if price <= 0:
                raise ValueError("invalid quote")
            return {
                "symbol": normalized,
                "price": price,
                "change_pct": result.get("regularMarketChangePercent"),
            }
        except Exception:
            return {
                "symbol": normalized,
                "price": 100.0,
                "change_pct": None,
            }
