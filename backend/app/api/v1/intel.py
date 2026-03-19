from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Holding, User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.services.market_intel_service import MarketIntelService

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("/daily-summary")
def daily_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
    symbols = sorted({h.symbol.upper() for h in holdings})

    return {
        "market": MarketIntelService.market_snapshot(),
        "earnings": MarketIntelService.earnings_calendar(symbols),
        "news": MarketIntelService.holdings_news(symbols, limit_per_symbol=3),
    }
