from pydantic import BaseModel


class BrokerConnectResponse(BaseModel):
    broker: str
    connect_url: str


class BrokerStatusResponse(BaseModel):
    broker: str
    connected: bool
    last_synced_at: str | None = None


class BrokerSyncResponse(BaseModel):
    broker: str
    synced_positions: int
    message: str
