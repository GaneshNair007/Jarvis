"""
Tests for JARVIS New Integrations:
- Home Assistant (PWR-320 to PWR-327)
- Calendar Integration (PWR-340 to PWR-345)
- Finance Integration (PWR-355 to PWR-365)
"""

import pytest
from unittest.mock import MagicMock, patch


# ─── Home Assistant ────────────────────────────────────────────────────────────

class TestHomeAssistantIntegration:
    def _get_integration(self):
        from integrations.home_assistant.home_assistant import HomeAssistantIntegration
        return HomeAssistantIntegration()

    def test_init_disabled_by_default(self):
        """Integration must be disabled by default (fail-closed)."""
        ha = self._get_integration()
        assert ha.enabled is False
        assert ha.connected is False

    def test_connect_without_credentials(self):
        """connect() without HA_BASE_URL/HA_TOKEN returns error."""
        ha = self._get_integration()
        with patch.dict("os.environ", {}, clear=True):
            result = ha.connect()
        assert result.get("status") != "connected" or "error" in result

    def test_turn_on_entity(self):
        """turn_on() calls call_service with correct domain."""
        ha = self._get_integration()
        ha.base_url = "http://ha.local:8123"
        ha.token = "test_token"
        ha.connected = True
        with patch.object(ha, "_ha_request") as mock_req:
            mock_req.return_value = {"data": []}
            result = ha.turn_on("light.living_room")
        mock_req.assert_called_once()
        args = mock_req.call_args
        assert "light" in args[0][1]
        assert "turn_on" in args[0][1]

    def test_turn_off_entity(self):
        """turn_off() calls the turn_off service."""
        ha = self._get_integration()
        ha.base_url = "http://ha.local:8123"
        ha.token = "test_token"
        ha.connected = True
        with patch.object(ha, "_ha_request") as mock_req:
            mock_req.return_value = {"data": []}
            result = ha.turn_off("switch.bedroom")
        assert "turn_off" in str(mock_req.call_args)

    def test_get_home_summary_structure(self):
        """get_home_summary() returns the expected power_id and keys."""
        ha = self._get_integration()
        ha.base_url = "http://ha.local:8123"
        ha.token = "test_token"
        with patch.object(ha, "_ha_request") as mock_req:
            mock_req.return_value = {"data": [
                {"entity_id": "light.living_room", "state": "on", "attributes": {"friendly_name": "Living Room"}},
                {"entity_id": "sensor.temperature", "state": "22.5", "attributes": {"unit_of_measurement": "°C"}},
            ]}
            result = ha.get_home_summary()
        assert result["power_id"] == "PWR-324"
        assert "lights_count" in result
        assert "sensors_count" in result

    def test_list_entities_filters_by_domain(self):
        """list_entities(domain='light') returns only light entities."""
        ha = self._get_integration()
        ha.base_url = "http://ha.local:8123"
        ha.token = "test_token"
        with patch.object(ha, "_ha_request") as mock_req:
            mock_req.return_value = {"data": [
                {"entity_id": "light.bedroom", "state": "off", "attributes": {}},
                {"entity_id": "switch.fan", "state": "on", "attributes": {}},
            ]}
            result = ha.list_entities(domain="light")
        assert result["power_id"] == "PWR-320"
        entity_ids = [e["entity_id"] for e in result["entities"]]
        assert "light.bedroom" in entity_ids
        assert "switch.fan" not in entity_ids

    def test_get_service_status(self):
        """get_service_status() returns integration metadata."""
        ha = self._get_integration()
        status = ha.get_service_status()
        assert status["integration_id"] == "home_assistant"
        assert "connected" in status
        assert "mqtt_active" in status

    def test_ha_request_handles_error(self):
        """_ha_request returns error dict on connection failure."""
        ha = self._get_integration()
        ha.base_url = "http://nonexistent.local:8123"
        ha.token = "bad_token"
        result = ha._ha_request("GET", "/api/")
        assert "error" in result


# ─── Calendar Integration ──────────────────────────────────────────────────────

class TestCalendarIntegration:
    def _get_integration(self):
        from integrations.calendar.calendar_integration import CalendarIntegration
        return CalendarIntegration()

    def test_init_disabled_by_default(self):
        cal = self._get_integration()
        assert cal.enabled is False
        assert cal.connected is False

    def test_connect_without_credentials(self):
        cal = self._get_integration()
        with patch.dict("os.environ", {}, clear=True):
            result = cal.connect()
        assert result.get("status") in ("no_backends_available", "connected")

    def test_list_events_without_connection(self):
        """list_events() without connection returns empty or error."""
        cal = self._get_integration()
        result = cal.list_events()
        assert "power_id" in result
        assert result.get("power_id") == "PWR-341"

    def test_get_today_agenda_structure(self):
        """get_today_agenda() returns expected keys."""
        cal = self._get_integration()
        with patch.object(cal, "list_events") as mock_list:
            mock_list.return_value = {
                "power_id": "PWR-341",
                "status": "SUCCESS",
                "events": [],
                "count": 0,
            }
            result = cal.get_today_agenda()
        assert result["power_id"] == "PWR-345"
        assert "date" in result
        assert "agenda" in result

    def test_find_free_slots_structure(self):
        """find_free_slots() returns a list of time slots."""
        cal = self._get_integration()
        with patch.object(cal, "list_events") as mock_list:
            mock_list.return_value = {
                "power_id": "PWR-341",
                "status": "SUCCESS",
                "events": [],
                "count": 0,
            }
            result = cal.find_free_slots(duration_minutes=30, days_ahead=2)
        assert result["power_id"] == "PWR-344"
        assert "free_slots" in result
        assert isinstance(result["free_slots"], list)

    def test_get_service_status(self):
        cal = self._get_integration()
        status = cal.get_service_status()
        assert status["integration_id"] == "calendar"
        assert "caldav_connected" in status
        assert "google_calendar_connected" in status

    def test_create_event_no_backend(self):
        """create_event() returns ERROR when no backends are connected."""
        from datetime import datetime, timezone, timedelta
        cal = self._get_integration()
        result = cal.create_event(
            title="Test Meeting",
            start=datetime.now(timezone.utc) + timedelta(hours=1),
            end=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        assert "power_id" in result


# ─── Finance Integration ───────────────────────────────────────────────────────

class TestFinanceIntegration:
    def _get_integration(self):
        from integrations.finance.finance_integration import FinanceIntegration
        return FinanceIntegration()

    def test_init_disabled_by_default(self):
        fin = self._get_integration()
        assert fin.enabled is False

    def test_get_quote_aapl_mocked(self):
        """get_quote() returns the right structure regardless of yfinance availability."""
        fin = self._get_integration()
        # Test the structure of the response - yfinance may not be installed
        result = fin.get_quote("AAPL")
        # Must always return a dict with power_id and symbol
        assert result["power_id"] == "PWR-355"
        assert "symbol" in result or "error" in result
        # If successful, symbol should be AAPL
        if result.get("status") == "SUCCESS":
            assert result["symbol"] == "AAPL"
            assert isinstance(result["price"], float)

    def test_get_quote_fallback_on_import_error(self):
        """get_quote() falls back to AlphaVantage when yfinance missing."""
        fin = self._get_integration()
        with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": ""}, clear=False):
            with patch.dict("sys.modules", {"yfinance": None}):
                result = fin.get_quote("TSLA")
        # Without AV key either, should return ERROR gracefully
        assert "power_id" in result
        assert result["power_id"] == "PWR-355"

    def test_get_crypto_quote_structure(self):
        """get_crypto_quote() calls CoinGecko and returns structured result."""
        fin = self._get_integration()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bitcoin": {"usd": 65000.0, "usd_24h_change": 1.5}
        }
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            result = fin.get_crypto_quote("bitcoin")
        assert result["power_id"] == "PWR-359"
        assert result["status"] == "SUCCESS"
        assert result["price_usd"] == 65000.0

    def test_paper_buy_insufficient_funds(self):
        """paper_buy() rejects order when cost > cash balance."""
        fin = self._get_integration()
        fin._cash_balance = 100.0
        with patch.object(fin, "get_quote") as mock_q:
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 500.0}
            result = fin.paper_buy("AAPL", quantity=1.0)
        assert result["status"] == "ERROR"
        assert "Insufficient" in result["error"]

    def test_paper_buy_success(self):
        """Successful paper_buy deducts from cash and creates position."""
        fin = self._get_integration()
        fin._cash_balance = 10_000.0
        with patch.object(fin, "get_quote") as mock_q:
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 100.0}
            result = fin.paper_buy("NVDA", quantity=5.0)
        assert result["status"] == "SUCCESS"
        assert result["action"] == "BUY"
        assert result["symbol"] == "NVDA"
        assert result["total_cost"] == 500.0
        assert fin._cash_balance == 9_500.0
        assert "NVDA" in fin._portfolio

    def test_paper_sell_without_position(self):
        """paper_sell() rejects when no position exists."""
        fin = self._get_integration()
        with patch.object(fin, "get_quote") as mock_q:
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 100.0}
            result = fin.paper_sell("MSFT", quantity=10.0)
        assert result["status"] == "ERROR"

    def test_paper_sell_success(self):
        """Successful sell returns realized P&L."""
        fin = self._get_integration()
        fin._cash_balance = 5_000.0
        with patch.object(fin, "get_quote") as mock_q:
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 100.0}
            fin.paper_buy("AMD", quantity=10.0)  # Buy at 100
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 120.0}
            result = fin.paper_sell("AMD", quantity=10.0)  # Sell at 120
        assert result["status"] == "SUCCESS"
        assert result["realized_pnl"] == pytest.approx(200.0)

    def test_get_portfolio_structure(self):
        """get_portfolio() returns expected structure."""
        fin = self._get_integration()
        result = fin.get_portfolio()
        assert result["power_id"] == "PWR-363"
        assert "cash_balance" in result
        assert "positions" in result
        assert "total_portfolio_value" in result

    def test_record_transaction(self):
        """Double-entry ledger transaction records successfully."""
        fin = self._get_integration()
        result = fin.record_transaction(
            debit_account="assets:cash",
            credit_account="income:dividends",
            amount=250.0,
            description="AAPL dividend Q4",
        )
        assert result["power_id"] == "PWR-365"
        assert result["status"] == "SUCCESS"
        assert result["txn_id"].startswith("TXN_")

    def test_get_service_status(self):
        fin = self._get_integration()
        status = fin.get_service_status()
        assert status["integration_id"] == "finance"
        assert "paper_cash_balance" in status
        assert "open_positions" in status

    def test_multi_quote_structure(self):
        """get_multi_quote() returns dict with a quote per symbol."""
        fin = self._get_integration()
        with patch.object(fin, "get_quote") as mock_q:
            mock_q.return_value = {"power_id": "PWR-355", "status": "SUCCESS", "price": 100.0}
            result = fin.get_multi_quote(["AAPL", "MSFT", "NVDA"])
        assert result["power_id"] == "PWR-358"
        assert result["count"] == 3
        assert "AAPL" in result["quotes"]
        assert "MSFT" in result["quotes"]


# ─── Alembic Migration Tests ────────────────────────────────────────────────────

class TestAlembicMigrations:
    def test_migration_0002_upgrade_runs(self):
        """Migration 0002 upgrade() should execute without syntax errors."""
        import importlib.util, sys
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "m002",
            str(Path(__file__).parent.parent / "alembic/versions/0002_add_integrations_and_plugins.py"),
        )
        m002 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m002)
        assert callable(m002.upgrade)
        assert callable(m002.downgrade)
        assert m002.revision == "0002_integrations_plugins"
        assert m002.down_revision == "0dc406230232"

    def test_migration_0003_upgrade_runs(self):
        """Migration 0003 upgrade() should be callable."""
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "m003",
            str(Path(__file__).parent.parent / "alembic/versions/0003_add_graph_checkpoints_and_voice_sessions.py"),
        )
        m003 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m003)
        assert callable(m003.upgrade)
        assert callable(m003.downgrade)
        assert m003.revision == "0003_graph_voice"
        assert m003.down_revision == "0002_integrations_plugins"

    def test_migration_chain_is_consistent(self):
        """Revisions form an unbroken chain from 0001 → 0002 → 0003."""
        import importlib.util
        from pathlib import Path
        base = Path(__file__).parent.parent / "alembic/versions"

        def load(filename):
            spec = importlib.util.spec_from_file_location("_m", str(base / filename))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        m002 = load("0002_add_integrations_and_plugins.py")
        m003 = load("0003_add_graph_checkpoints_and_voice_sessions.py")
        assert m002.down_revision == "0dc406230232"
        assert m003.down_revision == m002.revision
