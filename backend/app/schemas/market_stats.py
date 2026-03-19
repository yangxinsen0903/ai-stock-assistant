from pydantic import BaseModel


class SymbolStatsResponse(BaseModel):
    symbol: str
    currency: str = "USD"
    previous_close: float | None = None
    day_low: float | None = None
    day_high: float | None = None
    fifty_two_week_low: float | None = None
    fifty_two_week_high: float | None = None
    volume: int | None = None
    avg_volume: int | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
