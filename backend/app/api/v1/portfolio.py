from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Holding, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.portfolio import HoldingCreate, HoldingResponse


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=List[HoldingResponse])
def list_holdings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Holding).filter(Holding.user_id == current_user.id).all()


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
