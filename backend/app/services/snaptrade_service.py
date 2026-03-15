from __future__ import annotations

from dataclasses import dataclass
from typing import Any
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

    def fetch_all_holdings(self, *, snap_user_id: str, user_secret: str) -> list[dict[str, Any]]:
        response = self.account_api.get_all_user_holdings(user_id=snap_user_id, user_secret=user_secret)
        account_rows = response.body or []

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
