from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from snaptrade_client.exceptions import ApiException
from sqlalchemy.orm import Session

from app.db.models import BrokerAccount, Holding, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.broker import BrokerConnectResponse, BrokerStatusResponse, BrokerSyncResponse
from app.services.snaptrade_service import SnapTradeService

router = APIRouter(prefix="/broker", tags=["broker"])

BROKER_NAME = "robinhood"
SNAP_BROKER = "robinhood"


def _snap_user_id(user_id: int) -> str:
    return f"aistock-{user_id}"


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
def robinhood_connect(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = _get_or_create_account(db, current_user.id)
    snap = SnapTradeService()

    try:
        existing_secret = account.access_token
        if existing_secret and existing_secret.startswith("demo_token_"):
            existing_secret = None

        connection = snap.ensure_user_and_link(
            snap_user_id=account.external_user_id or _snap_user_id(current_user.id),
            existing_user_secret=existing_secret,
        )
    except (ApiException, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"SnapTrade connect failed: {exc}")

    account.external_user_id = connection.user_id
    account.access_token = connection.user_secret  # stores SnapTrade userSecret
    db.commit()

    return BrokerConnectResponse(broker=BROKER_NAME, connect_url=connection.redirect_uri)


@router.get("/robinhood/callback")
def robinhood_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    # SnapTrade connection portal finalizes authorization remotely.
    # Callback is kept for compatibility with earlier app flow.
    if state and state.startswith("user-"):
        user_id = int(state.split("user-")[-1])
        account = _get_or_create_account(db, user_id)
        account.is_connected = True
        if code:
            account.refresh_token = code
        db.commit()

    return {
        "success": True,
        "message": "Connection flow completed. Return to the app and tap Sync Portfolio.",
    }


@router.post("/robinhood/sync", response_model=BrokerSyncResponse)
def robinhood_sync(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = _get_or_create_account(db, current_user.id)
    if not account.access_token:
        raise HTTPException(status_code=400, detail="Broker is not connected")

    snap = SnapTradeService()
    try:
        positions = snap.fetch_all_holdings(
            snap_user_id=account.external_user_id or _snap_user_id(current_user.id),
            user_secret=account.access_token,
        )
    except ApiException as exc:
        if exc.status == 401:
            account.is_connected = False
            db.commit()
            raise HTTPException(status_code=400, detail="SnapTrade sync failed: authorization expired or invalid. Please tap Connect Robinhood again.")
        raise HTTPException(status_code=400, detail=f"SnapTrade sync failed: {exc}")

    # Read-only synchronization: mirror broker positions into local holdings for display only.
    db.query(Holding).filter(Holding.user_id == current_user.id).delete()
    for item in positions:
        db.add(
            Holding(
                user_id=current_user.id,
                symbol=item["symbol"],
                shares=item["shares"],
                avg_cost=item["avg_cost"],
            )
        )

    account.is_connected = True
    account.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    return BrokerSyncResponse(
        broker=BROKER_NAME,
        synced_positions=len(positions),
        message="Portfolio synced from connected brokerage (read-only).",
    )
