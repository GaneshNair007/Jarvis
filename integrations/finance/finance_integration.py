"""
JARVIS Finance Integration (PWR-355 to PWR-370)
PDF Spec: Pages 249-265 — Finance Powers

Provides:
- Real-time & historical quotes (Yahoo Finance via yfinance, no API key needed)
- Fundamental data: P/E, market cap, revenue, EPS
- AlphaVantage: technical indicators (RSI, MACD, SMA, EMA)
- Portfolio tracking: positions, P&L, allocation
- Paper trading: simulated buy/sell/hold orders with P&L tracking
- Ledger accounting: double-entry transactions in SQLite
- Crypto quotes via CoinGecko free API
- Cost governor: all actions default to $0.00 (free APIs)

All financial transactions (even paper trades) are Tier 2 — require approval.
Read-only market data is Tier 0.

Credentials (AlphaVantage only):
  ALPHAVANTAGE_API_KEY   Free key from alphavantage.co
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from integrations.base.base_integration import BaseIntegration
from jarvis.core.logger import get_logger

logger = get_logger("integrations.finance")

PAPER_TRADING_DB = Path("data/paper_trading.db")


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return ((self.current_price - self.avg_cost) / self.avg_cost) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
        }


class FinanceIntegration(BaseIntegration):
    """
    Unified finance integration combining free market data APIs,
    portfolio tracking, paper trading, and double-entry accounting.
    """

    INTEGRATION_ID = "finance"

    def __init__(self):
        super().__init__(
            integration_id=self.INTEGRATION_ID,
            display_name="Finance & Markets",
            category="finance",
            description=(
                "Real-time stock/crypto quotes, portfolio tracking, paper trading, "
                "and ledger accounting via Yahoo Finance and AlphaVantage."
            ),
            required_credentials=[],   # Yahoo Finance needs no key
            danger_level="medium",
            default_approval_tier=0,   # reads are Tier 0
            rate_limit_rpm=30,
            cost_model="free",
            data_sensitivity="high",
            documentation_url="https://finance.yahoo.com",
        )
        self._av_key = os.environ.get("ALPHAVANTAGE_API_KEY", "")
        self._portfolio: Dict[str, Position] = {}
        self._cash_balance: float = 100_000.0  # paper trading starting capital
        self._init_db()

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> Dict[str, Any]:
        # Test Yahoo Finance (no auth needed)
        test = self.get_quote("AAPL")
        if test.get("status") == "SUCCESS":
            self.connected = True
            self.enabled = True
            return {
                "status": "connected",
                "yahoo_finance": "available",
                "alphavantage": "available" if self._av_key else "no_key",
                "test_quote": test.get("price"),
            }
        return {"status": "degraded", "error": test.get("error", "unknown")}

    def disconnect(self) -> Dict[str, Any]:
        self.connected = False
        self.enabled = False
        return {"status": "disconnected"}

    def health_check(self) -> Dict[str, Any]:
        test = self.get_quote("MSFT")
        return {
            "status": "healthy" if test.get("status") == "SUCCESS" else "degraded",
            "test_symbol": "MSFT",
            "test_price": test.get("price"),
        }

    # ── Market Data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time quote for a stock symbol via Yahoo Finance.
        Tier 0 — free, no approval needed.
        """
        try:
            import yfinance as yf  # type: ignore
            ticker = yf.Ticker(symbol.upper())
            info = ticker.fast_info
            price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
            if price is None:
                hist = ticker.history(period="1d")
                price = float(hist["Close"].iloc[-1]) if not hist.empty else None

            if price is None:
                return {"power_id": "PWR-355", "status": "ERROR", "error": f"No price data for {symbol}"}

            return {
                "power_id": "PWR-355",
                "status": "SUCCESS",
                "symbol": symbol.upper(),
                "price": round(float(price), 4),
                "currency": getattr(info, "currency", "USD"),
                "market_cap": getattr(info, "market_cap", None),
                "volume": getattr(info, "three_month_average_volume", None),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "yahoo_finance",
            }
        except ImportError:
            return self._av_quote(symbol)
        except Exception as exc:
            logger.warning(f"get_quote({symbol}): {exc}")
            return self._av_quote(symbol)

    def get_historical(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> Dict[str, Any]:
        """Historical OHLCV data. period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y."""
        try:
            import yfinance as yf  # type: ignore
            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                return {"power_id": "PWR-356", "status": "ERROR", "error": "No data"}
            records = []
            for dt, row in hist.iterrows():
                records.append({
                    "date": str(dt.date()),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                })
            return {
                "power_id": "PWR-356",
                "status": "SUCCESS",
                "symbol": symbol.upper(),
                "period": period,
                "interval": interval,
                "bars_count": len(records),
                "data": records,
            }
        except ImportError:
            return {"power_id": "PWR-356", "status": "ERROR", "error": "yfinance not installed"}
        except Exception as exc:
            return {"power_id": "PWR-356", "status": "ERROR", "error": str(exc)}

    def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Get fundamental data: P/E, EPS, market cap, revenue, dividend yield."""
        try:
            import yfinance as yf  # type: ignore
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            return {
                "power_id": "PWR-357",
                "status": "SUCCESS",
                "symbol": symbol.upper(),
                "name": info.get("longName", symbol),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "eps": info.get("trailingEps"),
                "dividend_yield": info.get("dividendYield"),
                "revenue": info.get("totalRevenue"),
                "gross_margins": info.get("grossMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "beta": info.get("beta"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "analyst_rating": info.get("recommendationKey"),
            }
        except ImportError:
            return {"power_id": "PWR-357", "status": "ERROR", "error": "yfinance not installed"}
        except Exception as exc:
            return {"power_id": "PWR-357", "status": "ERROR", "error": str(exc)}

    def get_multi_quote(self, symbols: List[str]) -> Dict[str, Any]:
        """Batch quote for multiple symbols."""
        quotes = {}
        for sym in symbols:
            quotes[sym] = self.get_quote(sym)
        return {
            "power_id": "PWR-358",
            "status": "SUCCESS",
            "count": len(quotes),
            "quotes": quotes,
        }

    # ── Crypto ────────────────────────────────────────────────────────────────

    def get_crypto_quote(self, coin_id: str = "bitcoin") -> Dict[str, Any]:
        """Get crypto price from CoinGecko free API (no key needed)."""
        try:
            import httpx
            url = (
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
            )
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            coin = data.get(coin_id, {})
            return {
                "power_id": "PWR-359",
                "status": "SUCCESS",
                "coin_id": coin_id,
                "price_usd": coin.get("usd"),
                "change_24h": coin.get("usd_24h_change"),
                "source": "coingecko",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {"power_id": "PWR-359", "status": "ERROR", "error": str(exc)}

    # ── AlphaVantage Technical Indicators ─────────────────────────────────────

    def get_rsi(self, symbol: str, period: int = 14) -> Dict[str, Any]:
        """RSI technical indicator via AlphaVantage."""
        return self._av_indicator("RSI", symbol, {"time_period": period, "series_type": "close"})

    def get_macd(self, symbol: str) -> Dict[str, Any]:
        """MACD indicator via AlphaVantage."""
        return self._av_indicator("MACD", symbol, {"series_type": "close"})

    def get_sma(self, symbol: str, period: int = 20) -> Dict[str, Any]:
        """Simple Moving Average via AlphaVantage."""
        return self._av_indicator("SMA", symbol, {"time_period": period, "series_type": "close"})

    def _av_indicator(
        self, function: str, symbol: str, extra_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self._av_key:
            return {"power_id": "PWR-360", "status": "ERROR", "error": "ALPHAVANTAGE_API_KEY not set"}
        try:
            import httpx
            params = {
                "function": function,
                "symbol": symbol.upper(),
                "interval": "daily",
                "apikey": self._av_key,
                **extra_params,
            }
            with httpx.Client(timeout=15) as client:
                resp = client.get("https://www.alphavantage.co/query", params=params)
                resp.raise_for_status()
                data = resp.json()
            return {
                "power_id": "PWR-360",
                "status": "SUCCESS",
                "indicator": function,
                "symbol": symbol.upper(),
                "data": data,
            }
        except Exception as exc:
            return {"power_id": "PWR-360", "status": "ERROR", "error": str(exc)}

    def _av_quote(self, symbol: str) -> Dict[str, Any]:
        """AlphaVantage fallback quote."""
        if not self._av_key:
            return {"power_id": "PWR-355", "status": "ERROR", "error": "No quote source available"}
        try:
            import httpx
            params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self._av_key}
            with httpx.Client(timeout=10) as client:
                resp = client.get("https://www.alphavantage.co/query", params=params)
                data = resp.json()
            quote = data.get("Global Quote", {})
            price = quote.get("05. price")
            if not price:
                return {"power_id": "PWR-355", "status": "ERROR", "error": "No price from AlphaVantage"}
            return {
                "power_id": "PWR-355",
                "status": "SUCCESS",
                "symbol": symbol.upper(),
                "price": float(price),
                "source": "alphavantage",
            }
        except Exception as exc:
            return {"power_id": "PWR-355", "status": "ERROR", "error": str(exc)}

    # ── Paper Trading ─────────────────────────────────────────────────────────

    def paper_buy(
        self, symbol: str, quantity: float, reason: str = ""
    ) -> Dict[str, Any]:
        """
        Simulated market buy order. Tier 2 — requires approval token.
        """
        quote = self.get_quote(symbol)
        if quote.get("status") != "SUCCESS":
            return {"power_id": "PWR-361", "status": "ERROR", "error": f"Cannot price {symbol}"}

        price = quote["price"]
        cost = price * quantity

        if cost > self._cash_balance:
            return {
                "power_id": "PWR-361",
                "status": "ERROR",
                "error": f"Insufficient paper capital. Need ${cost:.2f}, have ${self._cash_balance:.2f}",
            }

        self._cash_balance -= cost
        sym = symbol.upper()
        if sym in self._portfolio:
            pos = self._portfolio[sym]
            total_cost = pos.avg_cost * pos.quantity + cost
            total_qty = pos.quantity + quantity
            pos.avg_cost = total_cost / total_qty
            pos.quantity = total_qty
        else:
            self._portfolio[sym] = Position(sym, quantity, price, price)

        order_id = f"ORDER_{uuid.uuid4().hex[:8].upper()}"
        self._record_trade(order_id, "BUY", sym, quantity, price, reason)

        logger.info(f"PaperTrade BUY: {quantity} {sym} @ ${price:.2f} (order={order_id})")
        return {
            "power_id": "PWR-361",
            "status": "SUCCESS",
            "order_id": order_id,
            "action": "BUY",
            "symbol": sym,
            "quantity": quantity,
            "price": price,
            "total_cost": round(cost, 2),
            "remaining_cash": round(self._cash_balance, 2),
        }

    def paper_sell(
        self, symbol: str, quantity: float, reason: str = ""
    ) -> Dict[str, Any]:
        """Simulated market sell order. Tier 2 — requires approval token."""
        sym = symbol.upper()
        if sym not in self._portfolio or self._portfolio[sym].quantity < quantity:
            return {
                "power_id": "PWR-362",
                "status": "ERROR",
                "error": f"Insufficient position. Have {self._portfolio.get(sym, Position(sym, 0, 0)).quantity} {sym}",
            }

        quote = self.get_quote(sym)
        if quote.get("status") != "SUCCESS":
            return {"power_id": "PWR-362", "status": "ERROR", "error": f"Cannot price {sym}"}

        price = quote["price"]
        proceeds = price * quantity
        pos = self._portfolio[sym]
        realized_pnl = (price - pos.avg_cost) * quantity

        pos.quantity -= quantity
        self._cash_balance += proceeds
        if pos.quantity <= 0:
            del self._portfolio[sym]

        order_id = f"ORDER_{uuid.uuid4().hex[:8].upper()}"
        self._record_trade(order_id, "SELL", sym, quantity, price, reason)

        logger.info(f"PaperTrade SELL: {quantity} {sym} @ ${price:.2f} PnL=${realized_pnl:.2f}")
        return {
            "power_id": "PWR-362",
            "status": "SUCCESS",
            "order_id": order_id,
            "action": "SELL",
            "symbol": sym,
            "quantity": quantity,
            "price": price,
            "proceeds": round(proceeds, 2),
            "realized_pnl": round(realized_pnl, 2),
            "remaining_cash": round(self._cash_balance, 2),
        }

    def get_portfolio(self) -> Dict[str, Any]:
        """Return current paper trading portfolio with live P&L."""
        positions = []
        total_market_value = 0.0
        total_pnl = 0.0

        for sym, pos in self._portfolio.items():
            quote = self.get_quote(sym)
            if quote.get("status") == "SUCCESS":
                pos.current_price = quote["price"]
            positions.append(pos.to_dict())
            total_market_value += pos.market_value
            total_pnl += pos.unrealized_pnl

        return {
            "power_id": "PWR-363",
            "status": "SUCCESS",
            "cash_balance": round(self._cash_balance, 2),
            "total_market_value": round(total_market_value, 2),
            "total_portfolio_value": round(self._cash_balance + total_market_value, 2),
            "total_unrealized_pnl": round(total_pnl, 2),
            "positions_count": len(positions),
            "positions": positions,
        }

    def get_trade_history(self, limit: int = 50) -> Dict[str, Any]:
        """Retrieve paper trade history from SQLite ledger."""
        try:
            conn = sqlite3.connect(str(PAPER_TRADING_DB))
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            rows = cur.fetchall()
            conn.close()
            return {
                "power_id": "PWR-364",
                "status": "SUCCESS",
                "count": len(rows),
                "trades": [
                    {
                        "order_id": r[0], "action": r[1], "symbol": r[2],
                        "quantity": r[3], "price": r[4], "reason": r[5], "timestamp": r[6],
                    }
                    for r in rows
                ],
            }
        except Exception as exc:
            return {"power_id": "PWR-364", "status": "ERROR", "error": str(exc)}

    # ── Ledger accounting ─────────────────────────────────────────────────────

    def record_transaction(
        self,
        debit_account: str,
        credit_account: str,
        amount: float,
        description: str,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """Double-entry ledger transaction."""
        txn_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
        try:
            conn = sqlite3.connect(str(PAPER_TRADING_DB))
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ledger (txn_id, debit, credit, amount, currency, description, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (txn_id, debit_account, credit_account, amount, currency,
                 description, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
            return {
                "power_id": "PWR-365",
                "status": "SUCCESS",
                "txn_id": txn_id,
                "debit": debit_account,
                "credit": credit_account,
                "amount": amount,
                "currency": currency,
            }
        except Exception as exc:
            return {"power_id": "PWR-365", "status": "ERROR", "error": str(exc)}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _init_db(self):
        try:
            PAPER_TRADING_DB.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(PAPER_TRADING_DB))
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    order_id TEXT PRIMARY KEY,
                    action TEXT,
                    symbol TEXT,
                    quantity REAL,
                    price REAL,
                    reason TEXT,
                    timestamp TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    txn_id TEXT PRIMARY KEY,
                    debit TEXT,
                    credit TEXT,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    timestamp TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning(f"FinanceIntegration: DB init failed — {exc}")

    def _record_trade(
        self, order_id: str, action: str, symbol: str,
        quantity: float, price: float, reason: str
    ):
        try:
            conn = sqlite3.connect(str(PAPER_TRADING_DB))
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_id, action, symbol, quantity, price, reason,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning(f"_record_trade: {exc}")

    def get_service_status(self) -> Dict[str, Any]:
        return {
            "integration_id": self.INTEGRATION_ID,
            "display_name": self.display_name,
            "connected": self.connected,
            "enabled": self.enabled,
            "alphavantage_configured": bool(self._av_key),
            "paper_cash_balance": round(self._cash_balance, 2),
            "open_positions": len(self._portfolio),
        }

    def list_powers(self):
        return [
            {"power_id": "PWR-355", "name": "Get Quote", "tier": 0},
            {"power_id": "PWR-356", "name": "Get Historical Data", "tier": 0},
            {"power_id": "PWR-357", "name": "Get Fundamentals", "tier": 0},
            {"power_id": "PWR-358", "name": "Multi Quote", "tier": 0},
            {"power_id": "PWR-359", "name": "Crypto Quote", "tier": 0},
            {"power_id": "PWR-360", "name": "Technical Indicator", "tier": 0},
            {"power_id": "PWR-361", "name": "Paper Buy", "tier": 2},
            {"power_id": "PWR-362", "name": "Paper Sell", "tier": 2},
            {"power_id": "PWR-363", "name": "Get Portfolio", "tier": 0},
            {"power_id": "PWR-364", "name": "Trade History", "tier": 0},
            {"power_id": "PWR-365", "name": "Record Transaction", "tier": 1},
        ]

    def _execute_power_impl(self, power_id: str, payload: dict, approval_token=None):
        dispatch = {
            "PWR-355": lambda p: self.get_quote(p["symbol"]),
            "PWR-356": lambda p: self.get_historical(p["symbol"], p.get("period", "1mo")),
            "PWR-357": lambda p: self.get_fundamentals(p["symbol"]),
            "PWR-358": lambda p: self.get_multi_quote(p["symbols"]),
            "PWR-359": lambda p: self.get_crypto_quote(p.get("coin_id", "bitcoin")),
            "PWR-360": lambda p: self.get_rsi(p["symbol"], p.get("period", 14)),
            "PWR-361": lambda p: self.paper_buy(p["symbol"], p["quantity"], p.get("reason", "")),
            "PWR-362": lambda p: self.paper_sell(p["symbol"], p["quantity"], p.get("reason", "")),
            "PWR-363": lambda p: self.get_portfolio(),
            "PWR-364": lambda p: self.get_trade_history(p.get("limit", 50)),
            "PWR-365": lambda p: self.record_transaction(
                p["debit"], p["credit"], p["amount"], p.get("description", "")
            ),
        }
        handler = dispatch.get(power_id)
        if not handler:
            return {"status": "ERROR", "error": f"Unknown power_id: {power_id}"}
        return handler(payload)


# ── Singleton ─────────────────────────────────────────────────────────────────
finance_integration = FinanceIntegration()

__all__ = ["FinanceIntegration", "Position", "finance_integration"]
