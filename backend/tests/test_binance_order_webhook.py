"""
Unit tests for Binance order webhook handler.

Tests cover:
- Order update parsing
- Trade status updates
- Connection management
- Reconnection logic
- Error handling
- Multi-user support
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from binance_order_webhook import (
    OrderUpdateProcessor,
    BinanceOrderWebSocketHandler,
    OrderUpdateHandler,
    WebSocketManager,
    BinanceOrderStatus,
)
from models import TradeDB, TradeStatus
from db import SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    from models import Base

    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_trade(db):
    """Create mock trade in database."""
    trade = TradeDB(
        id=1,
        user_id="test_user",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        quantity=0.001,
        entry_value=40.0,
        order_id="12345",
        status=TradeStatus.OPEN.value,
        entry_timestamp=datetime.utcnow(),
        auto_close_enabled=True,
        stop_loss=39000.0,
        take_profit_1=41000.0,
        take_profit_2=42000.0,
        take_profit_3=43000.0,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@pytest.fixture
def execution_report_filled():
    """Create a filled order execution report."""
    return {
        "e": "executionReport",
        "E": 1565245913483,
        "s": "BTCUSDT",
        "c": 1234567,
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.10000000",
        "p": "0.00000000",
        "P": "0.00000000",
        "F": "0.00000000",
        "g": -1,
        "C": "",
        "x": "TRADE",
        "X": "FILLED",
        "r": "NONE",
        "i": 12345,
        "l": "0.10000000",
        "z": "0.10000000",
        "L": "41234.56",
        "n": "0.10200000",
        "N": "BNB",
        "T": 1565245913000,
        "t": 28457,
        "I": 8641984,
        "w": True,
        "m": False,
        "O": 1565245913483,
        "Z": "4123.456000",
        "Y": "0.00000000",
        "Q": "0.00000000",
    }


@pytest.fixture
def execution_report_partial():
    """Create a partially filled order execution report."""
    return {
        "e": "executionReport",
        "E": 1565245913483,
        "s": "BTCUSDT",
        "c": 1234567,
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.10000000",
        "p": "0.00000000",
        "P": "0.00000000",
        "F": "0.00000000",
        "g": -1,
        "C": "",
        "x": "TRADE",
        "X": "PARTIALLY_FILLED",
        "r": "NONE",
        "i": 12345,
        "l": "0.05000000",
        "z": "0.05000000",
        "L": "41234.56",
        "n": "0.05100000",
        "N": "BNB",
        "T": 1565245913000,
        "t": 28457,
        "I": 8641984,
        "w": True,
        "m": False,
        "O": 1565245913483,
        "Z": "2061.728000",
        "Y": "0.00000000",
        "Q": "0.00000000",
    }


@pytest.fixture
def execution_report_cancelled():
    """Create a cancelled order execution report."""
    return {
        "e": "executionReport",
        "E": 1565245913483,
        "s": "BTCUSDT",
        "c": 1234567,
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.10000000",
        "p": "0.00000000",
        "P": "0.00000000",
        "F": "0.00000000",
        "g": -1,
        "C": "",
        "x": "CANCELED",
        "X": "CANCELED",
        "r": "USER_REQUESTED",
        "i": 12345,
        "l": "0.00000000",
        "z": "0.00000000",
        "L": "0.00000000",
        "n": "0.00000000",
        "N": "BNB",
        "T": 1565245913000,
        "t": 0,
        "I": 8641984,
        "w": False,
        "m": False,
        "O": 1565245913483,
        "Z": "0.00000000",
        "Y": "0.00000000",
        "Q": "0.00000000",
    }


@pytest.fixture
def non_execution_report():
    """Create a non-execution report event."""
    return {
        "e": "outboundAccountPosition",
        "E": 1565245913483,
        "u": 1565245913483,
        "B": [
            {"a": "USDT", "f": "100.0", "l": "0.0"},
            {"a": "BTC", "f": "0.001", "l": "0.0"},
        ],
    }


# ============================================================================
# Tests: OrderUpdateProcessor
# ============================================================================


class TestOrderUpdateProcessor:
    """Test order update parsing."""

    def test_parse_execution_report_filled(self, execution_report_filled):
        """Test parsing filled order execution report."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_filled)

        assert report is not None
        assert report["symbol"] == "BTCUSDT"
        assert report["order_id"] == 12345
        assert report["order_status"] == "FILLED"
        assert report["execution_type"] == "TRADE"
        assert report["cumulative_quantity"] == 0.1
        assert report["cumulative_quote"] == 4123.456
        assert report["executed_price"] == 41234.56
        assert report["commission"] == 0.102

    def test_parse_execution_report_partial(self, execution_report_partial):
        """Test parsing partially filled execution report."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_partial)

        assert report is not None
        assert report["order_status"] == "PARTIALLY_FILLED"
        assert report["cumulative_quantity"] == 0.05
        assert report["order_quantity"] == 0.1

    def test_parse_execution_report_cancelled(self, execution_report_cancelled):
        """Test parsing cancelled execution report."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_cancelled)

        assert report is not None
        assert report["order_status"] == "CANCELED"
        assert report["execution_type"] == "CANCELED"
        assert report["cumulative_quantity"] == 0.0
        assert report["reject_reason"] == "USER_REQUESTED"

    def test_parse_non_execution_report(self, non_execution_report):
        """Test that non-execution reports are ignored."""
        report = OrderUpdateProcessor.parse_execution_report(non_execution_report)
        assert report is None

    def test_parse_malformed_execution_report(self):
        """Test parsing malformed execution report."""
        malformed = {
            "e": "executionReport",
            "s": "BTCUSDT",
            # Missing required fields
        }
        report = OrderUpdateProcessor.parse_execution_report(malformed)

        # Should still parse but with default values
        assert report is not None
        assert report["symbol"] == "BTCUSDT"

    def test_parse_execution_report_with_missing_optional_fields(self):
        """Test parsing execution report with missing optional fields."""
        report_data = {
            "e": "executionReport",
            "s": "ETHUSDT",
            "i": 9999,
            "X": "FILLED",
            # Missing most fields
        }
        report = OrderUpdateProcessor.parse_execution_report(report_data)

        assert report is not None
        assert report["symbol"] == "ETHUSDT"
        assert report["executed_price"] is None
        assert report["commission"] == 0.0

    def test_calculate_average_price_normal(self):
        """Test average price calculation for normal fill."""
        avg = OrderUpdateProcessor.calculate_average_price(1.0, 41234.56)
        assert avg == pytest.approx(41234.56, rel=1e-4)

    def test_calculate_average_price_partial_fill(self):
        """Test average price calculation for partial fill."""
        avg = OrderUpdateProcessor.calculate_average_price(0.5, 20617.28)
        assert avg == pytest.approx(41234.56, rel=1e-4)

    def test_calculate_average_price_zero_quantity(self):
        """Test average price calculation with zero quantity."""
        avg = OrderUpdateProcessor.calculate_average_price(0.0, 41234.56)
        assert avg == 0.0

    def test_calculate_average_price_multiple_fills(self):
        """Test average price with multiple trade fills."""
        # 0.05 BTC @ 41000 + 0.05 BTC @ 41500 = 0.10 BTC @ 41250
        avg = OrderUpdateProcessor.calculate_average_price(0.1, 4125.0)
        assert avg == pytest.approx(41250.0, rel=1e-4)


# ============================================================================
# Tests: OrderUpdateHandler
# ============================================================================


class TestOrderUpdateHandler:
    """Test database updates from order events."""

    @pytest.mark.asyncio
    async def test_handle_order_update_filled(self, db, mock_trade, execution_report_filled):
        """Test updating trade when order is filled."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_filled)

        await OrderUpdateHandler.handle_order_update(db, "test_user", report)

        # Verify trade updated
        updated_trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert updated_trade.quantity == 0.1
        assert updated_trade.entry_price == pytest.approx(41234.56, rel=1e-4)
        assert updated_trade.status == TradeStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_handle_order_update_partial(self, db, mock_trade, execution_report_partial):
        """Test updating trade when order is partially filled."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_partial)

        await OrderUpdateHandler.handle_order_update(db, "test_user", report)

        updated_trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert updated_trade.quantity == 0.05
        assert updated_trade.status == TradeStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_handle_order_update_cancelled(self, db, mock_trade, execution_report_cancelled):
        """Test updating trade when order is cancelled."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_cancelled)

        await OrderUpdateHandler.handle_order_update(db, "test_user", report)

        updated_trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert updated_trade.status == TradeStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_handle_order_update_trade_not_found(self, db, execution_report_filled):
        """Test handling update for non-existent trade."""
        report = OrderUpdateProcessor.parse_execution_report(execution_report_filled)

        # Should not raise exception
        await OrderUpdateHandler.handle_order_update(db, "unknown_user", report)

        # Database should be unchanged
        trades = db.query(TradeDB).all()
        assert len(trades) == 0

    @pytest.mark.asyncio
    async def test_handle_order_update_updates_timestamp(self, db, mock_trade):
        """Test that update timestamp is set."""
        original_timestamp = mock_trade.updated_at

        report_data = {
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 12345,
            "c": 1234567,
            "S": "BUY",
            "X": "FILLED",
            "q": "0.1",
            "l": "0.1",
            "z": "0.1",
            "Z": "4123.456",
            "L": "41234.56",
            "n": "0.1",
            "N": "BNB",
        }
        report = OrderUpdateProcessor.parse_execution_report(report_data)

        await asyncio.sleep(0.01)  # Small delay to ensure timestamp difference
        await OrderUpdateHandler.handle_order_update(db, "test_user", report)

        updated_trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert updated_trade.updated_at > original_timestamp


# ============================================================================
# Tests: BinanceOrderWebSocketHandler
# ============================================================================


class TestBinanceOrderWebSocketHandler:
    """Test WebSocket connection and management."""

    @pytest.mark.asyncio
    async def test_handler_initialization(self):
        """Test handler initialization."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        assert handler.api_key == "key"
        assert handler.api_secret == "secret"
        assert handler.user_id == "user1"
        assert handler.is_connected is False
        assert handler.reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_add_update_callback(self):
        """Test registering update callback."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        async def callback(report):
            pass

        handler.add_update_callback(callback)

        assert len(handler.update_callbacks) == 1
        assert handler.update_callbacks[0] == callback

    @pytest.mark.asyncio
    async def test_add_multiple_callbacks(self):
        """Test registering multiple callbacks."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        async def callback1(report):
            pass

        async def callback2(report):
            pass

        handler.add_update_callback(callback1)
        handler.add_update_callback(callback2)

        assert len(handler.update_callbacks) == 2

    @pytest.mark.asyncio
    async def test_handle_message_execution_report(self):
        """Test handling execution report message."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        callback_called = False
        received_report = None

        async def test_callback(report):
            nonlocal callback_called, received_report
            callback_called = True
            received_report = report

        handler.add_update_callback(test_callback)

        msg = json.dumps({
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 12345,
            "X": "FILLED",
            "q": "0.1",
            "l": "0.1",
            "z": "0.1",
            "Z": "4123.456",
            "L": "41234.56",
            "n": "0.1",
            "N": "BNB",
        })

        await handler._handle_message(msg)

        assert callback_called
        assert received_report["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_handle_message_non_execution_report(self):
        """Test handling non-execution report message (should be ignored)."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        callback_called = False

        async def test_callback(report):
            nonlocal callback_called
            callback_called = True

        handler.add_update_callback(test_callback)

        msg = json.dumps({
            "e": "outboundAccountPosition",
            "B": [],
        })

        await handler._handle_message(msg)

        assert not callback_called

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self):
        """Test handling invalid JSON message."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        callback_called = False

        async def test_callback(report):
            nonlocal callback_called
            callback_called = True

        handler.add_update_callback(test_callback)

        msg = "invalid json {"

        await handler._handle_message(msg)

        assert not callback_called

    @pytest.mark.asyncio
    async def test_handle_message_callback_exception(self):
        """Test that callback exception doesn't break handler."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        async def failing_callback(report):
            raise Exception("Callback error")

        handler.add_update_callback(failing_callback)

        msg = json.dumps({
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 12345,
            "X": "FILLED",
            "q": "0.1",
            "l": "0.1",
            "z": "0.1",
            "Z": "4123.456",
            "L": "41234.56",
            "n": "0.1",
            "N": "BNB",
        })

        # Should not raise
        await handler._handle_message(msg)

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting WebSocket."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")
        handler.is_connected = True
        handler.socket_manager = MagicMock()

        await handler.disconnect()

        assert handler.is_connected is False
        assert handler.socket_manager is None


# ============================================================================
# Tests: WebSocketManager
# ============================================================================


class TestWebSocketManager:
    """Test WebSocket connection management."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = WebSocketManager()

        assert len(manager.connections) == 0
        assert len(manager.tasks) == 0

    @pytest.mark.asyncio
    async def test_get_connection_status_empty(self):
        """Test getting status with no connections."""
        manager = WebSocketManager()

        status = manager.get_connection_status()

        assert status == {}

    @pytest.mark.asyncio
    async def test_get_connection_status_multiple(self, db):
        """Test getting status with multiple connections."""
        manager = WebSocketManager()

        # Create mock handlers
        handler1 = MagicMock(spec=BinanceOrderWebSocketHandler)
        handler1.is_connected = True
        handler1.reconnect_attempts = 0

        handler2 = MagicMock(spec=BinanceOrderWebSocketHandler)
        handler2.is_connected = False
        handler2.reconnect_attempts = 3

        manager.connections["user1"] = handler1
        manager.connections["user2"] = handler2

        status = manager.get_connection_status()

        assert status["user1"]["connected"] is True
        assert status["user1"]["reconnect_attempts"] == 0
        assert status["user2"]["connected"] is False
        assert status["user2"]["reconnect_attempts"] == 3

    @pytest.mark.asyncio
    async def test_stop_connection_not_found(self):
        """Test stopping connection that doesn't exist."""
        manager = WebSocketManager()

        # Should not raise
        await manager.stop_connection("unknown_user")

    @pytest.mark.asyncio
    async def test_stop_connection_integration(self):
        """Test stopping a single connection with real handler."""
        manager = WebSocketManager()

        # Use real handler but mock the socket internals
        handler = BinanceOrderWebSocketHandler("test_key", "test_secret", "test_user")
        handler.is_connected = True
        handler.socket_manager = MagicMock()
        handler.socket_manager.close = MagicMock()

        # Create a real task that we can manage
        async def dummy_listen():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_listen())

        manager.connections["test_user"] = handler
        manager.tasks["test_user"] = task

        # Manually stop just the connection without tasks
        await manager.stop_connection("test_user")

        # Connection should be removed
        assert "test_user" not in manager.connections
        assert "test_user" not in manager.tasks


# ============================================================================
# Tests: Integration scenarios
# ============================================================================


class TestWebhookIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_order_lifecycle_filled(self, db, mock_trade):
        """Test complete order lifecycle: partial → filled."""
        # First partial fill
        partial_report = {
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 12345,
            "c": 1234567,
            "S": "BUY",
            "X": "PARTIALLY_FILLED",
            "q": "0.1",
            "l": "0.05",
            "z": "0.05",
            "Z": "2061.728",
            "L": "41234.56",
            "n": "0.05",
            "N": "BNB",
        }
        parsed = OrderUpdateProcessor.parse_execution_report(partial_report)
        await OrderUpdateHandler.handle_order_update(db, "test_user", parsed)

        trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert trade.quantity == 0.05
        assert trade.status == TradeStatus.OPEN.value

        # Then full fill
        filled_report = {
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 12345,
            "c": 1234567,
            "S": "BUY",
            "X": "FILLED",
            "q": "0.1",
            "l": "0.05",
            "z": "0.1",
            "Z": "4123.456",
            "L": "41234.56",
            "n": "0.1",
            "N": "BNB",
        }
        parsed = OrderUpdateProcessor.parse_execution_report(filled_report)
        await OrderUpdateHandler.handle_order_update(db, "test_user", parsed)

        trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert trade.quantity == 0.1
        assert trade.status == TradeStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_handler_with_multiple_callbacks(self):
        """Test handler with multiple update callbacks."""
        handler = BinanceOrderWebSocketHandler("key", "secret", "user1")

        results = []

        async def callback1(report):
            results.append(("callback1", report["symbol"]))

        async def callback2(report):
            results.append(("callback2", report["symbol"]))

        handler.add_update_callback(callback1)
        handler.add_update_callback(callback2)

        msg = json.dumps({
            "e": "executionReport",
            "s": "ETHUSDT",
            "i": 12345,
            "X": "FILLED",
            "q": "1.0",
            "l": "1.0",
            "z": "1.0",
            "Z": "2500.0",
            "L": "2500.0",
            "n": "0.01",
            "N": "BNB",
        })

        await handler._handle_message(msg)

        assert len(results) == 2
        assert results[0] == ("callback1", "ETHUSDT")
        assert results[1] == ("callback2", "ETHUSDT")

    @pytest.mark.asyncio
    async def test_multiple_trades_same_symbol(self, db):
        """Test handling updates for multiple trades of same symbol."""
        # Create two trades with same symbol but different order IDs
        trade1 = TradeDB(
            user_id="test_user",
            symbol="BTCUSDT",
            direction="LONG",
            entry_price=40000.0,
            quantity=0.001,
            entry_value=40.0,
            order_id="11111",
            status=TradeStatus.OPEN.value,
            entry_timestamp=datetime.utcnow(),
            auto_close_enabled=True,
            stop_loss=39000.0,
            take_profit_1=41000.0,
        )

        trade2 = TradeDB(
            user_id="test_user",
            symbol="BTCUSDT",
            direction="SHORT",
            entry_price=41000.0,
            quantity=0.001,
            entry_value=41.0,
            order_id="22222",
            status=TradeStatus.OPEN.value,
            entry_timestamp=datetime.utcnow(),
            auto_close_enabled=True,
            stop_loss=42000.0,
            take_profit_1=40000.0,
        )

        db.add(trade1)
        db.add(trade2)
        db.commit()

        # Update first trade: 0.001 BTC at 40000 per BTC = 40.0 total
        report1 = {
            "e": "executionReport",
            "s": "BTCUSDT",
            "i": 11111,
            "X": "FILLED",
            "q": "0.001",
            "l": "0.001",
            "z": "0.001",
            "Z": "40.0",  # 0.001 BTC * 40000 = 40.0 USDT
            "L": "40000.0",
            "n": "0.04",
            "N": "BNB",
        }
        parsed = OrderUpdateProcessor.parse_execution_report(report1)
        await OrderUpdateHandler.handle_order_update(db, "test_user", parsed)

        # Verify only first trade updated
        updated1 = db.query(TradeDB).filter(TradeDB.order_id == "11111").first()
        updated2 = db.query(TradeDB).filter(TradeDB.order_id == "22222").first()

        assert updated1.entry_price == pytest.approx(40000.0, rel=1e-4)
        assert updated2.entry_price == 41000.0  # Unchanged
