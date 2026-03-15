class MarketDataService:
    demo_prices = {
        "AAPL": 210.15,
        "NVDA": 143.20,
        "TSLA": 188.60,
        "MSFT": 428.05,
        "META": 512.40,
    }

    @classmethod
    def get_quote(cls, symbol: str) -> dict:
        normalized = symbol.upper()
        return {
            "symbol": normalized,
            "price": cls.demo_prices.get(normalized, 100.0),
        }
