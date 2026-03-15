from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import AlertRule, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.alerts import AlertRuleCreate, AlertRuleResponse


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertRuleResponse])
def list_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(AlertRule).filter(AlertRule.user_id == current_user.id).all()


@router.post("", response_model=AlertRuleResponse)
def create_alert(payload: AlertRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    direction = payload.direction.lower()
    if direction not in {"above", "below"}:
        raise HTTPException(status_code=400, detail="direction must be 'above' or 'below'")
    rule = AlertRule(user_id=current_user.id, symbol=payload.symbol.upper(), target_price=payload.target_price, direction=direction)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_alert(rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.user_id == current_user.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(rule)
    db.commit()
    return {"success": True}
