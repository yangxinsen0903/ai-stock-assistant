from pydantic import BaseModel


class PortfolioSummaryResponse(BaseModel):
    currency: str = "USD"
    total_value: float
    total_return: float
    total_return_pct: float
    today_return: float
    today_return_pct: float
    net_deposits: float


class PositionDetailResponse(BaseModel):
    symbol: str
    currency: str = "USD"
    market_value: float
    average_cost: float
    shares: float
    portfolio_diversity_pct: float
    today_return: float
    today_return_pct: float
    total_return: float
    total_return_pct: float


class PositionHistoryItem(BaseModel):
    timestamp: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str | None = None


class PositionHistoryResponse(BaseModel):
    symbol: str
    items: list[PositionHistoryItem]
