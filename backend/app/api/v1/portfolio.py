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
    service = SnapTradeService()
    summary = service.build_portfolio_summary(snapshots=snapshots)

    # Better today return approximation: sum position delta vs previous close.
    today_return = 0.0
    for account in snapshots:
        for p in (account.get("positions") or []):
            sym = service._extract_symbol(p)
            units = float(p.get("units") or 0.0)
            if not sym or units <= 0:
                continue
            try:
                from app.api.v1.market import _load_chart_payload  # local import to avoid cycles
                c = _load_chart_payload(sym, "1d")
                today_return += units * (float(c.get("current_price") or 0.0) - float(c.get("previous_close") or 0.0))
            except Exception:
                continue

    total_value = float(summary.get("total_value") or 0.0)
    today_return_pct = (today_return / (total_value - today_return) * 100.0) if (total_value - today_return) else 0.0
    summary["today_return"] = today_return
    summary["today_return_pct"] = today_return_pct

    return PortfolioSummaryResponse(**summary)


@router.get("/position/{symbol}", response_model=PositionDetailResponse)
def position_detail(symbol: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    snapshots = _load_snaptrade_snapshots(db, current_user.id)
    service = SnapTradeService()
    detail = service.build_position_detail(snapshots=snapshots, symbol=symbol)
    if not detail:
        raise HTTPException(status_code=404, detail="Position not found")

    # Better today-return from 1D quote baseline.
    units = detail["shares"]
    try:
        from app.api.v1.market import _load_chart_payload
        c = _load_chart_payload(symbol, "1d")
        today_return = units * (float(c.get("current_price") or 0.0) - float(c.get("previous_close") or 0.0))
        baseline = units * float(c.get("previous_close") or 0.0)
        detail["today_return"] = today_return
        detail["today_return_pct"] = (today_return / baseline * 100.0) if baseline else 0.0
    except Exception:
        pass

    return PositionDetailResponse(symbol=symbol.upper(), **detail)


@router.get("/position/{symbol}/history", response_model=PositionHistoryResponse)
def position_history(
    symbol: str,
    limit: int = Query(50, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshots = _load_snaptrade_snapshots(db, current_user.id)
    service = SnapTradeService()
    broker = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == current_user.id, BrokerAccount.broker == "robinhood")
        .first()
    )
    activities = []
    try:
        if broker and broker.external_user_id and broker.access_token:
            activities = service.fetch_activities(snap_user_id=broker.external_user_id, user_secret=broker.access_token)
    except Exception:
        activities = []

    rows = service.build_position_history(activities=activities, symbol=symbol, limit=limit)
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
