"""富途 OpenD 访问层。未安装 futu-api 或未开 OpenD 时给出明确错误，便于测试注入假后端。"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from config import settings

log = logging.getLogger("lobster.futu")

_ALLOWED_PREFIXES = ("US.", "HK.", "SH.", "SZ.")


class FutuQuoteBackend(Protocol):
    def snapshots(self, codes: list[str]) -> list[dict[str, Any]]: ...

    def positions(self) -> list[dict[str, Any]]: ...

    def account(self) -> dict[str, Any]: ...

    def place_order(
        self,
        *,
        code: str,
        side: str,
        qty: float,
        price: float,
        order_type: str,
    ) -> dict[str, Any]: ...


def normalize_code(code: str) -> str:
    symbol = code.strip().upper()
    if not any(symbol.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        raise ValueError("Stock code must look like US.AAPL, HK.00700, SH.600519, or SZ.000001.")
    return symbol


def resolve_trd_env() -> str:
    env = settings.futu.TRD_ENV.strip().upper()
    if env not in {"SIMULATE", "REAL"}:
        raise ValueError("FUTU_TRD_ENV must be SIMULATE or REAL.")
    if env == "REAL" and not settings.futu.ALLOW_LIVE:
        raise ValueError("Live trading is blocked. Set FUTU_ALLOW_LIVE=true and FUTU_TRD_ENV=REAL together.")
    return env


def live_trading_allowed() -> bool:
    return settings.futu.ENABLED and resolve_trd_env() == "REAL" and settings.futu.ALLOW_LIVE


class LiveFutuBackend:
    """通过本机 Futu OpenD 拉行情和下单。"""

    def __init__(self):
        try:
            from futu import (
                OpenQuoteContext,
                OpenSecTradeContext,
                OrderType,
                RET_OK,
                TrdEnv,
                TrdMarket,
                TrdSide,
            )
        except ImportError as exc:
            raise RuntimeError(
                "futu-api is not installed. Run: pip install futu-api  and start Futu OpenD."
            ) from exc

        self._OpenQuoteContext = OpenQuoteContext
        self._OpenSecTradeContext = OpenSecTradeContext
        self._OrderType = OrderType
        self._RET_OK = RET_OK
        self._TrdEnv = TrdEnv
        self._TrdMarket = TrdMarket
        self._TrdSide = TrdSide

    def _trd_env(self):
        return self._TrdEnv.REAL if resolve_trd_env() == "REAL" else self._TrdEnv.SIMULATE

    def _market(self):
        market = settings.futu.MARKET.strip().upper()
        mapping = {
            "US": self._TrdMarket.US,
            "HK": self._TrdMarket.HK,
            "CN": getattr(self._TrdMarket, "CN", self._TrdMarket.HK),
            "NONE": self._TrdMarket.NONE,
        }
        if market not in mapping:
            raise ValueError("FUTU_MARKET must be US, HK, CN, or NONE.")
        return mapping[market]

    def snapshots(self, codes: list[str]) -> list[dict[str, Any]]:
        quote_ctx = self._OpenQuoteContext(host=settings.futu.HOST, port=settings.futu.PORT)
        try:
            ret, data = quote_ctx.get_market_snapshot(codes)
            if ret != self._RET_OK:
                raise RuntimeError(f"Futu snapshot failed: {data}")
            rows: list[dict[str, Any]] = []
            for _, row in data.iterrows():
                last = float(row.get("last_price") or 0)
                prev = float(row.get("prev_close_price") or 0)
                change_rate = ((last - prev) / prev) if prev else 0.0
                rows.append(
                    {
                        "code": str(row.get("code") or ""),
                        "name": str(row.get("name") or ""),
                        "last_price": last,
                        "open_price": float(row.get("open_price") or 0),
                        "high_price": float(row.get("high_price") or 0),
                        "low_price": float(row.get("low_price") or 0),
                        "prev_close_price": prev,
                        "volume": float(row.get("volume") or 0),
                        "change_rate": change_rate,
                    }
                )
            return rows
        finally:
            quote_ctx.close()

    def _trade_ctx(self):
        return self._OpenSecTradeContext(
            filter_trdmarket=self._market(),
            host=settings.futu.HOST,
            port=settings.futu.PORT,
        )

    def _unlock(self, trd_ctx) -> None:
        password = settings.futu.UNLOCK_PASSWORD
        if not password:
            raise RuntimeError("FUTU_UNLOCK_PASSWORD is required to query positions or place orders.")
        ret, data = trd_ctx.unlock_trade(password)
        if ret != self._RET_OK:
            raise RuntimeError(f"Futu unlock failed: {data}")

    def _acc_id(self):
        raw = settings.futu.ACC_ID
        if not raw:
            return 0
        try:
            return int(raw)
        except ValueError:
            return raw

    def positions(self) -> list[dict[str, Any]]:
        trd_ctx = self._trade_ctx()
        try:
            self._unlock(trd_ctx)
            ret, data = trd_ctx.position_list_query(trd_env=self._trd_env(), acc_id=self._acc_id())
            if ret != self._RET_OK:
                raise RuntimeError(f"Futu positions failed: {data}")
            rows = []
            for _, row in data.iterrows():
                rows.append(
                    {
                        "code": str(row.get("code") or ""),
                        "qty": float(row.get("qty") or 0),
                        "can_sell_qty": float(row.get("can_sell_qty") or 0),
                        "cost_price": float(row.get("cost_price") or 0),
                        "market_val": float(row.get("market_val") or 0),
                    }
                )
            return rows
        finally:
            trd_ctx.close()

    def account(self) -> dict[str, Any]:
        trd_ctx = self._trade_ctx()
        try:
            self._unlock(trd_ctx)
            ret, data = trd_ctx.accinfo_query(trd_env=self._trd_env(), acc_id=self._acc_id())
            if ret != self._RET_OK:
                raise RuntimeError(f"Futu account query failed: {data}")
            if data is None or data.empty:
                return {"trd_env": resolve_trd_env(), "empty": True}
            row = data.iloc[0].to_dict()
            return {
                "trd_env": resolve_trd_env(),
                "power": row.get("power"),
                "total_assets": row.get("total_assets"),
                "cash": row.get("cash"),
                "market_val": row.get("market_val"),
            }
        finally:
            trd_ctx.close()

    def place_order(
        self,
        *,
        code: str,
        side: str,
        qty: float,
        price: float,
        order_type: str,
    ) -> dict[str, Any]:
        trd_ctx = self._trade_ctx()
        try:
            self._unlock(trd_ctx)
            trd_side = self._TrdSide.BUY if side == "BUY" else self._TrdSide.SELL
            futu_order_type = self._OrderType.MARKET if order_type == "MARKET" else self._OrderType.NORMAL
            ret, data = trd_ctx.place_order(
                price=price,
                qty=qty,
                code=code,
                trd_side=trd_side,
                order_type=futu_order_type,
                trd_env=self._trd_env(),
                acc_id=self._acc_id(),
            )
            if ret != self._RET_OK:
                raise RuntimeError(f"Futu place_order failed: {data}")
            row = data.iloc[0].to_dict() if data is not None and not data.empty else {}
            return {
                "order_id": str(row.get("order_id") or ""),
                "code": code,
                "side": side,
                "qty": qty,
                "price": price,
                "trd_env": resolve_trd_env(),
            }
        finally:
            trd_ctx.close()


def get_backend() -> FutuQuoteBackend:
    if not settings.futu.ENABLED:
        raise RuntimeError("Futu trading is disabled. Set FUTU_ENABLED=true after OpenD is running.")
    return LiveFutuBackend()
