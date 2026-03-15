from pydantic import BaseModel


class HoldingCreate(BaseModel):
    symbol: str
    shares: float
    avg_cost: float


class HoldingResponse(BaseModel):
    id: int
    symbol: str
    shares: float
    avg_cost: float

    class Config:
        from_attributes = True
