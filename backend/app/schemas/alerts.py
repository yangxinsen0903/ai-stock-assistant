from pydantic import BaseModel


class AlertRuleCreate(BaseModel):
    symbol: str
    target_price: float
    direction: str


class AlertRuleResponse(BaseModel):
    id: int
    symbol: str
    target_price: float
    direction: str
    is_enabled: bool

    class Config:
        from_attributes = True
