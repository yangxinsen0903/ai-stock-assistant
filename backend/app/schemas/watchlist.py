from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    symbol: str


class WatchlistResponse(BaseModel):
    id: int
    symbol: str

    class Config:
        from_attributes = True
