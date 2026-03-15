from pydantic import BaseModel


class ChartPoint(BaseModel):
    ts: int
    price: float


class HoldingChartResponse(BaseModel):
    symbol: str
    range: str
    period_label: str
    currency: str
    current_price: float
    previous_close: float
    reference_price: float
    change: float
    change_percent: float
    points: list[ChartPoint]
