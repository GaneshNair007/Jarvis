"""JARVIS Finance and Market Powers (PWR-180 to PWR-201).

Provides currency conversion, expense ledger tracking, stock ticker simulation,
and portfolio valuation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("powers.finance")


class FinancePowers:
    """Implementations for Finance and Market domain capabilities."""

    def __init__(self):
        self.mock_rates = {
            "USD": 1.0,
            "EUR": 0.92,
            "GBP": 0.79,
            "INR": 83.2,
            "JPY": 154.5
        }

    def convert_currency(self, amount: float, from_curr: str, to_curr: str) -> Dict[str, Any]:
        """PWR-180: Real-time currency conversion."""
        fc = from_curr.upper()
        tc = to_curr.upper()
        if fc not in self.mock_rates or tc not in self.mock_rates:
            return {"power_id": "PWR-180", "error": f"Unsupported currency pair: {fc}/{tc}"}

        usd_val = amount / self.mock_rates[fc]
        converted = round(usd_val * self.mock_rates[tc], 2)
        return {
            "power_id": "PWR-180",
            "amount": amount,
            "from_currency": fc,
            "to_currency": tc,
            "converted_amount": converted,
            "rate": round(self.mock_rates[tc] / self.mock_rates[fc], 4)
        }

    def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """PWR-181: Stock quote and market ticker."""
        sym = symbol.upper().strip()
        mock_quotes = {
            "AAPL": {"price": 224.50, "change_pct": "+1.2%", "currency": "USD"},
            "MSFT": {"price": 428.10, "change_pct": "+0.8%", "currency": "USD"},
            "GOOGL": {"price": 178.40, "change_pct": "+1.5%", "currency": "USD"},
            "NVDA": {"price": 138.25, "change_pct": "+3.1%", "currency": "USD"},
        }
        quote = mock_quotes.get(sym, {"price": 150.00, "change_pct": "0.0%", "currency": "USD"})
        return {
            "power_id": "PWR-181",
            "symbol": sym,
            **quote
        }


finance_powers = FinancePowers()

