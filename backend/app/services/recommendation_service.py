from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import AlertRule, BrokerAccount, Holding, RecommendationLog, User, WatchlistItem
from app.services.llm_service import LLMService
from app.services.market_data_service import MarketDataService
from app.services.market_intel_service import MarketIntelService
from app.services.snaptrade_service import SnapTradeService
from app.services.risk_guard import RiskGuard


class RecommendationService:
    @staticmethod
    def build_user_context(db: Session, user: User) -> dict:
        holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
        watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
        alerts = db.query(AlertRule).filter(AlertRule.user_id == user.id).all()

        # Prefer broker snapshot prices/costs when available to avoid stale or fabricated values.
        snapshot_by_symbol = {}
        broker = (
            db.query(BrokerAccount)
            .filter(BrokerAccount.user_id == user.id, BrokerAccount.broker == "robinhood")
            .first()
        )
        if broker and broker.external_user_id and broker.access_token:
            try:
                snapshots = SnapTradeService().fetch_account_snapshots(
                    snap_user_id=broker.external_user_id,
                    user_secret=broker.access_token,
                )
                for account in snapshots:
                    for p in (account.get("positions") or []):
                        if not isinstance(p, dict):
                            continue
                        sym = SnapTradeService._extract_symbol(p)
                        if not sym:
                            continue
                        sym = sym.upper()
                        snapshot_by_symbol[sym] = {
                            "shares": float(p.get("units") or 0.0),
                            "avg_cost": float(p.get("average_purchase_price") or 0.0),
                            "market_price": float(p.get("price") or 0.0),
                        }
            except Exception:
                snapshot_by_symbol = {}

        holding_payload = []
        for item in holdings:
            sym = item.symbol.upper()
            snap = snapshot_by_symbol.get(sym)
            if snap:
                market_price = snap.get("market_price") or None
                avg_cost = snap.get("avg_cost") or item.avg_cost
                shares = snap.get("shares") or item.shares
            else:
                quote = MarketDataService.get_quote(sym)
                market_price = quote.get("price")
                avg_cost = item.avg_cost
                shares = item.shares

            holding_payload.append({
                "symbol": sym,
                "shares": shares,
                "avg_cost": avg_cost,
                "market_price": market_price,
            })

        alert_payload = []
        for item in alerts:
            alert_payload.append({
                "symbol": item.symbol,
                "target_price": item.target_price,
                "direction": item.direction,
                "is_enabled": item.is_enabled,
            })

        symbols = sorted({h["symbol"] for h in holding_payload if h.get("symbol")})
        market_snapshot = MarketIntelService.market_snapshot()
        news = MarketIntelService.holdings_news(symbols)
        earnings = MarketIntelService.earnings_calendar(symbols)

        return {
            "risk_level": user.risk_level,
            "holdings": holding_payload,
            "watchlist": [item.symbol for item in watchlist],
            "alerts": alert_payload,
            "market_snapshot": market_snapshot,
            "news": news,
            "earnings": earnings,
        }

    @staticmethod
    def generate_reply(db: Session, user: User, message: str) -> str:
        context = RecommendationService.build_user_context(db, user)
        prompt = LLMService.build_prompt(context, message)
        raw_text = LLMService.generate(prompt, context=context, message=message)
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
