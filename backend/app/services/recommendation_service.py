from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import AlertRule, Holding, RecommendationLog, User, WatchlistItem
from app.services.llm_service import LLMService
from app.services.market_data_service import MarketDataService
from app.services.risk_guard import RiskGuard


class RecommendationService:
    @staticmethod
    def build_user_context(db: Session, user: User) -> dict:
        holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
        watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
        alerts = db.query(AlertRule).filter(AlertRule.user_id == user.id).all()

        holding_payload = []
        for item in holdings:
            quote = MarketDataService.get_quote(item.symbol)
            holding_payload.append({
                "symbol": item.symbol,
                "shares": item.shares,
                "avg_cost": item.avg_cost,
                "market_price": quote["price"],
            })

        alert_payload = []
        for item in alerts:
            alert_payload.append({
                "symbol": item.symbol,
                "target_price": item.target_price,
                "direction": item.direction,
                "is_enabled": item.is_enabled,
            })

        return {
            "risk_level": user.risk_level,
            "holdings": holding_payload,
            "watchlist": [item.symbol for item in watchlist],
            "alerts": alert_payload,
        }

    @staticmethod
    def generate_reply(db: Session, user: User, message: str) -> str:
        context = RecommendationService.build_user_context(db, user)
        prompt = LLMService.build_prompt(context, message)
        raw_text = LLMService.generate(prompt)
        safe_text = RiskGuard.sanitize(raw_text)

        log = RecommendationLog(
            user_id=user.id,
            input_message=message,
            output_text=safe_text,
            model_name=settings.OPENAI_MODEL,
        )
        db.add(log)
        db.commit()
        return safe_text
