from pydantic import BaseModel


class ChartPoint(BaseModel):
    ts: int
    price: float


class HoldingChartResponse(BaseModel):
    symbol: str
    range: str
    currency: str
    current_price: float
    previous_close: float
    change: float
    change_percent: float
    points: list[ChartPoint]
