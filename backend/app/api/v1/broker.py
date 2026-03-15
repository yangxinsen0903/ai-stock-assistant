from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import BrokerAccount, Holding, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.broker import BrokerConnectResponse, BrokerStatusResponse, BrokerSyncResponse

router = APIRouter(prefix="/broker", tags=["broker"])

BROKER_NAME = "robinhood"


def _get_or_create_account(db: Session, user_id: int) -> BrokerAccount:
    account = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user_id, BrokerAccount.broker == BROKER_NAME)
        .first()
    )
    if not account:
        account = BrokerAccount(user_id=user_id, broker=BROKER_NAME, is_connected=False)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


@router.get("/robinhood/status", response_model=BrokerStatusResponse)
def robinhood_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == current_user.id, BrokerAccount.broker == BROKER_NAME)
        .first()
    )
    return BrokerStatusResponse(
        broker=BROKER_NAME,
        connected=bool(account and account.is_connected),
        last_synced_at=account.last_synced_at.isoformat() if account and account.last_synced_at else None,
    )


@router.get("/robinhood/connect", response_model=BrokerConnectResponse)
def robinhood_connect(current_user: User = Depends(get_current_user)):
    # Production: replace this with Robinhood OAuth authorize endpoint when available.
    state = f"user-{current_user.id}"
    callback = settings.ROBINHOOD_REDIRECT_URI
    params = urlencode({"state": state, "client_id": settings.ROBINHOOD_CLIENT_ID or "demo-client"})
    connect_url = f"{settings.APP_PUBLIC_URL}/api/v1/broker/robinhood/callback?code=demo_auth_code&{params}&redirect_uri={callback}"
    return BrokerConnectResponse(broker=BROKER_NAME, connect_url=connect_url)


@router.get("/robinhood/callback")
def robinhood_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    if not state.startswith("user-"):
        raise HTTPException(status_code=400, detail="Invalid state")

    user_id = int(state.split("user-")[-1])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    account = _get_or_create_account(db, user_id)
    account.access_token = f"demo_token_{code}"
    account.refresh_token = "demo_refresh_token"
    account.external_user_id = str(user_id)
    account.is_connected = True
    db.commit()

    return {
        "success": True,
        "message": "Robinhood connected. You can return to the app and tap Sync Portfolio.",
    }


@router.post("/robinhood/sync", response_model=BrokerSyncResponse)
def robinhood_sync(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = _get_or_create_account(db, current_user.id)
    if not account.is_connected:
        raise HTTPException(status_code=400, detail="Robinhood is not connected")

    # Read-only sync mode: do not write placeholder/demo holdings.
    # Real broker position ingestion should be implemented here.
    synced_positions = db.query(Holding).filter(Holding.user_id == current_user.id).count()

    account.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    return BrokerSyncResponse(
        broker=BROKER_NAME,
        synced_positions=synced_positions,
        message="Broker connected. Real Robinhood positions sync is not configured yet; no holdings were modified.",
    )
