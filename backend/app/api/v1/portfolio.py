from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Holding, User, BrokerAccount
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.portfolio import HoldingCreate, HoldingResponse
from app.schemas.portfolio_insights import (
    PortfolioSummaryResponse,
    PositionDetailResponse,
    PositionHistoryResponse,
    PositionHistoryItem,
)
from app.services.snaptrade_service import SnapTradeService


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _load_snaptrade_snapshots(db: Session, user_id: int) -> list[dict]:
    broker = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user_id, BrokerAccount.broker == "robinhood")
        .first()
    )
    if not broker or not broker.external_user_id or not broker.access_token:
        raise HTTPException(status_code=400, detail="Broker not connected")

    try:
        return SnapTradeService().fetch_account_snapshots(
            snap_user_id=broker.external_user_id,
            user_secret=broker.access_token,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load broker snapshots: {exc}")


@router.get("/holdings", response_model=List[HoldingResponse])
def list_holdings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Holding).filter(Holding.user_id == current_user.id).all()


@router.get("/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    snapshots = _load_snaptrade_snapshots(db, current_user.id)
    summary = SnapTradeService().build_portfolio_summary(snapshots=snapshots)
    return PortfolioSummaryResponse(**summary)


@router.get("/position/{symbol}", response_model=PositionDetailResponse)
def position_detail(symbol: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    snapshots = _load_snaptrade_snapshots(db, current_user.id)
    detail = SnapTradeService().build_position_detail(snapshots=snapshots, symbol=symbol)
    if not detail:
        raise HTTPException(status_code=404, detail="Position not found")
    return PositionDetailResponse(symbol=symbol.upper(), **detail)


@router.get("/position/{symbol}/history", response_model=PositionHistoryResponse)
def position_history(
    symbol: str,
    limit: int = Query(50, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshots = _load_snaptrade_snapshots(db, current_user.id)
    rows = SnapTradeService().build_position_history(snapshots=snapshots, symbol=symbol, limit=limit)
    return PositionHistoryResponse(
        symbol=symbol.upper(),
        items=[PositionHistoryItem(**row) for row in rows],
    )


@router.post("/holdings", response_model=HoldingResponse)
def create_holding(payload: HoldingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if settings.PORTFOLIO_READ_ONLY:
        raise HTTPException(status_code=403, detail="Portfolio is read-only. Use broker sync to refresh real holdings.")

    holding = Holding(user_id=current_user.id, symbol=payload.symbol.upper(), shares=payload.shares, avg_cost=payload.avg_cost)
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if settings.PORTFOLIO_READ_ONLY:
        raise HTTPException(status_code=403, detail="Portfolio is read-only. Use broker sync to refresh real holdings.")

    holding = db.query(Holding).filter(Holding.id == holding_id, Holding.user_id == current_user.id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(holding)
    db.commit()
    return {"success": True}
