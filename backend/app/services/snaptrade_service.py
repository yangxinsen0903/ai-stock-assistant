from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import datetime
import uuid

import snaptrade_client
from snaptrade_client.apis.tags.account_information_api import AccountInformationApi
from snaptrade_client.apis.tags.authentication_api import AuthenticationApi
from snaptrade_client.exceptions import ApiException

from app.config import settings


@dataclass
class SnapTradeConnection:
    user_id: str
    user_secret: str
    redirect_uri: str


class SnapTradeService:
    def __init__(self) -> None:
        cfg = snaptrade_client.Configuration(
            host=settings.SNAPTRADE_BASE_URL,
            client_id=settings.SNAPTRADE_CLIENT_ID,
            consumer_key=settings.SNAPTRADE_CONSUMER_KEY,
        )
        client = snaptrade_client.ApiClient(cfg)
        self.auth_api = AuthenticationApi(client)
        self.account_api = AccountInformationApi(client)

    def ensure_user_and_link(self, *, snap_user_id: str, existing_user_secret: str | None) -> SnapTradeConnection:
        """
        Ensure we have a valid SnapTrade user + secret and return a connection portal link.
        If an old/stale secret exists (common after switching from demo tokens), we auto-recover
        by creating a fresh SnapTrade user id suffix.
        """

        def _register(user_id: str) -> str:
            register = self.auth_api.register_snap_trade_user(user_id=user_id)
            body = register.body or {}
            secret = body.get("userSecret")
            if not secret:
                raise ValueError("Unable to obtain SnapTrade user secret")
            return secret

        candidate_user_id = snap_user_id
        user_secret = existing_user_secret

        # If there is no stored secret, create/register first.
        if not user_secret:
            try:
                user_secret = _register(candidate_user_id)
            except ApiException as exc:
                if exc.status == 400 and "one user" in str(exc).lower():
                    users = self.auth_api.list_snap_trade_users().body or []
                    raise ValueError(
                        f"SnapTrade personal keys allow one user and one already exists ({users}). "
                        "Please rotate SnapTrade API keys (or provide existing user secret) and try again."
                    )
                raise

        # Try to create login link with existing credentials.
        try:
            login = self.auth_api.login_snap_trade_user(user_id=candidate_user_id, user_secret=user_secret)
        except ApiException as exc:
            # Recover from invalid/missing userSecret by creating a fresh SnapTrade user id.
            if exc.status == 401:
                candidate_user_id = f"{snap_user_id}-{uuid.uuid4().hex[:6]}"
                user_secret = _register(candidate_user_id)
                login = self.auth_api.login_snap_trade_user(user_id=candidate_user_id, user_secret=user_secret)
            else:
                raise

        body = login.body or {}
        redirect_uri = body.get("redirectURI")
        if not redirect_uri:
            raise ValueError("SnapTrade did not return redirect URI")

        return SnapTradeConnection(user_id=candidate_user_id, user_secret=user_secret, redirect_uri=redirect_uri)

    def fetch_account_snapshots(self, *, snap_user_id: str, user_secret: str) -> list[dict[str, Any]]:
        response = self.account_api.get_all_user_holdings(user_id=snap_user_id, user_secret=user_secret)
        return response.body or []

    def fetch_all_holdings(self, *, snap_user_id: str, user_secret: str) -> list[dict[str, Any]]:
        account_rows = self.fetch_account_snapshots(snap_user_id=snap_user_id, user_secret=user_secret)

        # SnapTrade returns a list of account snapshots; each item contains `positions`.
        position_rows: list[dict[str, Any]] = []
        for account in account_rows:
            if isinstance(account, dict):
                positions = account.get("positions") or []
                if isinstance(positions, list):
                    for p in positions:
                        if isinstance(p, dict):
                            position_rows.append(p)

        holdings: list[dict[str, Any]] = []
        for row in position_rows:
            symbol = self._extract_symbol(row)
            shares = self._extract_shares(row)
            avg_cost = self._extract_avg_cost(row)
            if not symbol or shares is None:
                continue
            holdings.append(
                {
                    "symbol": symbol.upper(),
                    "shares": float(shares),
                    "avg_cost": float(avg_cost or 0.0),
                }
            )

        return holdings

    def build_portfolio_summary(self, *, snapshots: list[dict[str, Any]]) -> dict[str, float]:
        total_value = 0.0
        total_cost = 0.0
        total_open_pnl = 0.0

        for account in snapshots:
            if not isinstance(account, dict):
                continue

            total_val_obj = account.get("total_value") or {}
            if isinstance(total_val_obj, dict):
                total_value += float(total_val_obj.get("value") or 0.0)

            for position in (account.get("positions") or []):
                if not isinstance(position, dict):
                    continue
                units = float(position.get("units") or 0.0)
                avg_cost = float(position.get("average_purchase_price") or 0.0)
                total_cost += units * avg_cost
                total_open_pnl += float(position.get("open_pnl") or 0.0)

        # Approximation: invested principal = current value - open pnl.
        invested_principal = max(total_value - total_open_pnl, 1e-6)
        total_return = total_open_pnl
        total_return_pct = (total_return / invested_principal) * 100.0 if invested_principal else 0.0

        # Daily return proxy from position-level open_pnl is not available separately in this payload.
        # Keep 0.0 until intraday delta is computed from time-series aggregation.
        today_return = 0.0
        today_return_pct = 0.0

        net_deposits = invested_principal

        return {
            "total_value": total_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "today_return": today_return,
            "today_return_pct": today_return_pct,
            "net_deposits": net_deposits,
        }

    def build_position_detail(self, *, snapshots: list[dict[str, Any]], symbol: str) -> dict[str, float] | None:
        target = symbol.upper()
        total_portfolio_value = 0.0
        market_value = 0.0
        shares = 0.0
        weighted_cost_sum = 0.0
        total_open_pnl = 0.0

        for account in snapshots:
            if not isinstance(account, dict):
                continue

            total_val_obj = account.get("total_value") or {}
            if isinstance(total_val_obj, dict):
                total_portfolio_value += float(total_val_obj.get("value") or 0.0)

            for p in (account.get("positions") or []):
                if not isinstance(p, dict):
                    continue
                sym = self._extract_symbol(p)
                if not sym or sym.upper() != target:
                    continue

                units = float(p.get("units") or 0.0)
                price = float(p.get("price") or 0.0)
                avg_cost = float(p.get("average_purchase_price") or 0.0)
                open_pnl = float(p.get("open_pnl") or 0.0)

                shares += units
                market_value += units * price
                weighted_cost_sum += units * avg_cost
                total_open_pnl += open_pnl

        if shares <= 0:
            return None

        average_cost = weighted_cost_sum / shares if shares else 0.0
        total_cost_value = weighted_cost_sum
        total_return = total_open_pnl
        total_return_pct = (total_return / total_cost_value * 100.0) if total_cost_value else 0.0

        today_return = 0.0
        today_return_pct = 0.0
        portfolio_diversity_pct = (market_value / total_portfolio_value * 100.0) if total_portfolio_value else 0.0

        return {
            "market_value": market_value,
            "average_cost": average_cost,
            "shares": shares,
            "portfolio_diversity_pct": portfolio_diversity_pct,
            "today_return": today_return,
            "today_return_pct": today_return_pct,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
        }

    def build_position_history(self, *, snapshots: list[dict[str, Any]], symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        target = symbol.upper()
        items: list[dict[str, Any]] = []

        for account in snapshots:
            if not isinstance(account, dict):
                continue
            for order in (account.get("orders") or []):
                if not isinstance(order, dict):
                    continue

                order_symbol = str(order.get("symbol") or "").upper()
                # Some payloads use universal_symbol with nested symbol string.
                uni = order.get("universal_symbol") or {}
                if isinstance(uni, dict):
                    order_symbol = str(uni.get("symbol") or order_symbol).upper()

                if order_symbol != target:
                    continue

                ts = order.get("time_executed") or order.get("time_updated") or order.get("time_placed")
                qty = float(order.get("filled_quantity") or order.get("total_quantity") or 0.0)
                px = order.get("execution_price") or order.get("limit_price")
                price = float(px) if px not in (None, "") else None

                items.append(
                    {
                        "timestamp": str(ts or datetime.utcnow().isoformat()),
                        "side": str(order.get("action") or "UNKNOWN"),
                        "quantity": qty,
                        "price": price,
                        "order_type": str(order.get("order_type") or ""),
                    }
                )

        items.sort(key=lambda x: x["timestamp"], reverse=True)
        return items[:limit]

    @staticmethod
    def _extract_symbol(row: dict[str, Any]) -> str | None:
        if not isinstance(row, dict):
            return None

        # Flat variants
        if isinstance(row.get("symbol"), str):
            return row.get("symbol")

        # Nested SnapTrade payload often looks like:
        # row["symbol"]["symbol"]["symbol"] == "AAPL"
        symbol_obj = row.get("symbol") or row.get("security") or row.get("instrument")
        if isinstance(symbol_obj, dict):
            for key in ("symbol", "ticker", "rawSymbol", "raw_symbol"):
                val = symbol_obj.get(key)
                if isinstance(val, str) and val:
                    return val
                if isinstance(val, dict):
                    nested = val.get("symbol") or val.get("ticker") or val.get("rawSymbol") or val.get("raw_symbol")
                    if isinstance(nested, str) and nested:
                        return nested

            # Another common nested shape: symbol_obj["symbol"] is dict with raw_symbol
            if isinstance(symbol_obj.get("symbol"), dict):
                inner = symbol_obj.get("symbol")
                for key in ("symbol", "ticker", "raw_symbol", "rawSymbol"):
                    val = inner.get(key)
                    if isinstance(val, str) and val:
                        return val

        for key in ("ticker", "raw_symbol", "rawSymbol"):
            val = row.get(key)
            if isinstance(val, str) and val:
                return val

        return None

    @staticmethod
    def _extract_shares(row: dict[str, Any]) -> float | None:
        for key in ("units", "quantity", "shares"):
            val = row.get(key)
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return float(val)
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_avg_cost(row: dict[str, Any]) -> float | None:
        # Cost basis can be represented in different shapes.
        for key in ("averagePurchasePrice", "average_purchase_price", "avgCost", "average_price", "price"):
            val = row.get(key)
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return float(val)
                except ValueError:
                    pass
            if isinstance(val, dict):
                for nested in ("amount", "value"):
                    nested_val = val.get(nested)
                    if isinstance(nested_val, (int, float)):
                        return float(nested_val)
                    if isinstance(nested_val, str):
                        try:
                            return float(nested_val)
                        except ValueError:
                            pass
        return None
