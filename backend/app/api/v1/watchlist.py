from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import User, WatchlistItem
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.watchlist import WatchlistCreate, WatchlistResponse


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=List[WatchlistResponse])
def list_watchlist(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(WatchlistItem).filter(WatchlistItem.user_id == current_user.id).all()


@router.post("", response_model=WatchlistResponse)
def create_watchlist_item(payload: WatchlistCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = WatchlistItem(user_id=current_user.id, symbol=payload.symbol.upper())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_watchlist_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return {"success": True}
