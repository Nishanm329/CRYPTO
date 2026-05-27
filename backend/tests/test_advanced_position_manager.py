"""
Unit tests for advanced position management.

Tests cover:
- Trailing stop loss calculations
- Partial position closures
- Position scaling (in/out)
- Breakeven stops
- Dynamic risk adjustment
- Integration scenarios
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from advanced_position_manager import (
    TrailingStopManager,
    PartialCloseManager,
    PositionScaler,
    BreakevenStopManager,
    DynamicRiskManager,
    PositionManagementEngine,
    PositionManagementMode,
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
def long_trade(db):
    """Create LONG trade for testing."""
    trade = TradeDB(
        id=1,
        user_id="test_user",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        quantity=0.1,
        entry_value=4000.0,
        order_id="order1",
        status=TradeStatus.OPEN.value,
        entry_timestamp=datetime.utcnow(),
        auto_close_enabled=True,
        stop_loss=39000.0,
        take_profit_1=42000.0,
        take_profit_2=44000.0,
        take_profit_3=46000.0,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@pytest.fixture
def short_trade(db):
    """Create SHORT trade for testing."""
    trade = TradeDB(
        id=2,
        user_id="test_user",
        symbol="ETHUSDT",
        direction="SHORT",
        entry_price=2500.0,
        quantity=1.0,
        entry_value=2500.0,
        order_id="order2",
        status=TradeStatus.OPEN.value,
        entry_timestamp=datetime.utcnow(),
        auto_close_enabled=True,
        stop_loss=2600.0,
        take_profit_1=2400.0,
        take_profit_2=2300.0,
        take_profit_3=2200.0,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


# ============================================================================
# Tests: TrailingStopManager
# ============================================================================


class TestTrailingStopManager:
    """Test trailing stop loss functionality."""

    def test_trailing_stop_long_no_profit(self):
        """Test trailing stop calculation when LONG trade has no profit."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=40000.0,
            current_price=39500.0,  # Below entry
            trailing_amount=500.0,
            direction="LONG",
        )
        assert sl is None

    def test_trailing_stop_long_with_profit(self):
        """Test trailing stop calculation for profitable LONG trade."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=40000.0,
            current_price=41234.56,  # Above entry
            trailing_amount=500.0,
            direction="LONG",
        )
        assert sl == pytest.approx(40734.56, rel=1e-4)

    def test_trailing_stop_long_with_pct(self):
        """Test trailing stop with percentage instead of amount."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=40000.0,
            current_price=41000.0,
            trailing_amount=0.0,
            trailing_pct=2.0,  # 2% of current price
            direction="LONG",
        )
        assert sl == pytest.approx(40180.0, rel=1e-4)

    def test_trailing_stop_short_no_profit(self):
        """Test trailing stop for SHORT with no profit."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=2500.0,
            current_price=2600.0,  # Above entry
            trailing_amount=50.0,
            direction="SHORT",
        )
        assert sl is None

    def test_trailing_stop_short_with_profit(self):
        """Test trailing stop calculation for profitable SHORT trade."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=2500.0,
            current_price=2400.0,  # Below entry
            trailing_amount=50.0,
            direction="SHORT",
        )
        assert sl == pytest.approx(2450.0, rel=1e-4)

    def test_trailing_stop_prevents_below_entry_long(self):
        """Test that trailing stop doesn't go below entry for LONG."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=40000.0,
            current_price=40100.0,  # Minimal profit
            trailing_amount=200.0,  # Would go below entry
            direction="LONG",
        )
        # Should be at entry + small buffer
        assert sl > 40000.0
        assert sl < 40100.0

    def test_trailing_stop_prevents_above_entry_short(self):
        """Test that trailing stop doesn't go above entry for SHORT."""
        sl = TrailingStopManager.calculate_trailing_stop(
            entry_price=2500.0,
            current_price=2480.0,  # Minimal profit
            trailing_amount=50.0,  # Would go above entry
            direction="SHORT",
        )
        # Should be at entry - small buffer
        assert sl < 2500.0
        assert sl > 2480.0

    def test_update_trailing_stop_long(self, db, long_trade):
        """Test updating trailing stop for LONG trade."""
        updated, new_sl, msg = TrailingStopManager.update_trailing_stop(
            db=db,
            trade_id=1,
            current_price=41234.56,
            trailing_amount=500.0,
            min_update_pct=0.1,
        )

        assert updated is True
        assert new_sl == pytest.approx(40734.56, rel=1e-4)

        # Verify trade updated
        trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert trade.stop_loss == pytest.approx(40734.56, rel=1e-4)

    def test_update_trailing_stop_no_profit(self, db, long_trade):
        """Test that trailing stop doesn't update when no profit."""
        updated, new_sl, msg = TrailingStopManager.update_trailing_stop(
            db=db,
            trade_id=1,
            current_price=39500.0,  # Below entry
            trailing_amount=500.0,
        )

        assert updated is False
        assert new_sl is None

    def test_update_trailing_stop_insufficient_move(self, db, long_trade):
        """Test that trailing stop requires minimum move."""
        # Set initial SL close to current
        long_trade.stop_loss = 41000.0
        db.add(long_trade)
        db.commit()

        updated, new_sl, msg = TrailingStopManager.update_trailing_stop(
            db=db,
            trade_id=1,
            current_price=41200.0,
            trailing_amount=150.0,
            min_update_pct=1.0,  # Require 1% move
        )

        assert updated is False


# ============================================================================
# Tests: PartialCloseManager
# ============================================================================


class TestPartialCloseManager:
    """Test partial position closure."""

    def test_partial_close_detection_long(self):
        """Test detecting partial close level for LONG."""
        should_close = PartialCloseManager.calculate_partial_close(
            entry_price=40000.0,
            current_price=41200.0,
            close_pct=3.0,
            direction="LONG",
        )
        assert should_close is True

    def test_partial_close_no_trigger_long(self):
        """Test that partial close doesn't trigger below level."""
        should_close = PartialCloseManager.calculate_partial_close(
            entry_price=40000.0,
            current_price=41000.0,
            close_pct=3.0,  # Need 41200
            direction="LONG",
        )
        assert should_close is False

    def test_partial_close_detection_short(self):
        """Test detecting partial close level for SHORT."""
        should_close = PartialCloseManager.calculate_partial_close(
            entry_price=2500.0,
            current_price=2375.0,
            close_pct=5.0,  # 2500 * 0.95 = 2375
            direction="SHORT",
        )
        assert should_close is True

    def test_execute_partial_close_long(self, db, long_trade):
        """Test executing partial close for LONG trade."""
        closed, pnl, msg = PartialCloseManager.execute_partial_close(
            db=db,
            trade_id=1,
            close_quantity=0.05,
            close_price=41234.56,
            close_reason="PARTIAL_CLOSE",
        )

        assert closed is True
        # P&L = (41234.56 - 40000) * 0.05 = 61.728
        assert pnl == pytest.approx(61.728, rel=1e-2)

        # Verify quantity reduced
        trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert trade.quantity == pytest.approx(0.05, rel=1e-6)

    def test_execute_partial_close_short(self, db, short_trade):
        """Test executing partial close for SHORT trade."""
        closed, pnl, msg = PartialCloseManager.execute_partial_close(
            db=db,
            trade_id=2,
            close_quantity=0.5,
            close_price=2400.0,
            close_reason="PARTIAL_CLOSE",
        )

        assert closed is True
        # P&L = (2500 - 2400) * 0.5 = 50
        assert pnl == pytest.approx(50.0, rel=1e-2)

    def test_partial_close_invalid_quantity(self, db, long_trade):
        """Test partial close with invalid quantity."""
        closed, pnl, msg = PartialCloseManager.execute_partial_close(
            db=db,
            trade_id=1,
            close_quantity=0.2,  # More than available
            close_price=41000.0,
        )

        assert closed is False
        assert pnl is None

    def test_partial_close_closed_trade(self, db, long_trade):
        """Test that partial close rejects closed trades."""
        long_trade.status = TradeStatus.CLOSED.value
        db.add(long_trade)
        db.commit()

        closed, pnl, msg = PartialCloseManager.execute_partial_close(
            db=db,
            trade_id=1,
            close_quantity=0.05,
            close_price=41000.0,
        )

        assert closed is False


# ============================================================================
# Tests: PositionScaler
# ============================================================================


class TestPositionScaler:
    """Test position scaling functionality."""

    def test_scale_out_prices_long(self):
        """Test calculating scale-out prices for LONG."""
        prices = PositionScaler.calculate_scale_out_price(
            entry_price=40000.0,
            scale_steps=3,
            target_profit_pct=9.0,
            direction="LONG",
        )

        assert len(prices) == 3
        assert prices[0] == pytest.approx(41200.0, rel=1e-4)  # 3% profit
        assert prices[1] == pytest.approx(42400.0, rel=1e-4)  # 6% profit
        assert prices[2] == pytest.approx(43600.0, rel=1e-4)  # 9% profit

    def test_scale_out_prices_short(self):
        """Test calculating scale-out prices for SHORT."""
        prices = PositionScaler.calculate_scale_out_price(
            entry_price=2500.0,
            scale_steps=3,
            target_profit_pct=6.0,
            direction="SHORT",
        )

        assert len(prices) == 3
        assert prices[0] == pytest.approx(2450.0, rel=1e-4)  # 2% profit
        assert prices[1] == pytest.approx(2400.0, rel=1e-4)  # 4% profit
        assert prices[2] == pytest.approx(2350.0, rel=1e-4)  # 6% profit

    def test_scale_in_allowed_long(self):
        """Test that scale-in is allowed when price down for LONG."""
        add_size, msg = PositionScaler.calculate_scale_in_size(
            initial_size=0.1,
            base_price=40000.0,
            current_price=39000.0,
            scale_steps=2,
            max_loss_pct=5.0,
            direction="LONG",
        )

        assert add_size is not None
        assert add_size > 0

    def test_scale_in_blocked_loss_too_deep(self):
        """Test that scale-in blocked when loss too deep."""
        add_size, msg = PositionScaler.calculate_scale_in_size(
            initial_size=0.1,
            base_price=40000.0,
            current_price=37500.0,  # 6.25% loss
            scale_steps=2,
            max_loss_pct=5.0,
            direction="LONG",
        )

        assert add_size is None

    def test_scale_in_blocked_price_up_long(self):
        """Test that scale-in blocked if price up for LONG."""
        add_size, msg = PositionScaler.calculate_scale_in_size(
            initial_size=0.1,
            base_price=40000.0,
            current_price=41000.0,
            scale_steps=2,
            max_loss_pct=5.0,
            direction="LONG",
        )

        assert add_size is None


# ============================================================================
# Tests: BreakevenStopManager
# ============================================================================


class TestBreakevenStopManager:
    """Test breakeven stop functionality."""

    def test_breakeven_trigger_long(self):
        """Test breakeven stop trigger for LONG."""
        should_update, new_sl, msg = BreakevenStopManager.calculate_breakeven_stop(
            entry_price=40000.0,
            current_price=41000.0,  # 2.5% profit
            min_profit_pct=2.0,
            direction="LONG",
        )

        assert should_update is True
        assert new_sl > 40000.0
        assert new_sl < 40100.0

    def test_breakeven_no_trigger_long(self):
        """Test breakeven stop doesn't trigger without enough profit."""
        should_update, new_sl, msg = BreakevenStopManager.calculate_breakeven_stop(
            entry_price=40000.0,
            current_price=40500.0,  # 1.25% profit
            min_profit_pct=2.0,
            direction="LONG",
        )

        assert should_update is False
        assert new_sl is None

    def test_breakeven_trigger_short(self):
        """Test breakeven stop trigger for SHORT."""
        should_update, new_sl, msg = BreakevenStopManager.calculate_breakeven_stop(
            entry_price=2500.0,
            current_price=2425.0,  # 3% profit
            min_profit_pct=2.0,
            direction="SHORT",
        )

        assert should_update is True
        assert new_sl < 2500.0

    @pytest.mark.asyncio
    async def test_update_breakeven_long(self, db, long_trade):
        """Test updating trade to breakeven stop."""
        updated, msg = await BreakevenStopManager.update_to_breakeven(
            db=db,
            trade_id=1,
            current_price=41234.56,
            min_profit_pct=2.0,
        )

        assert updated is True

        trade = db.query(TradeDB).filter(TradeDB.id == 1).first()
        assert trade.stop_loss > 40000.0


# ============================================================================
# Tests: DynamicRiskManager
# ============================================================================


class TestDynamicRiskManager:
    """Test dynamic risk adjustment."""

    def test_adjusted_size_high_volatility(self):
        """Test position size reduced when volatility high."""
        adjusted = DynamicRiskManager.calculate_adjusted_size(
            base_size=1.0,
            atr=150.0,  # High ATR
            base_atr=100.0,
            volatility_multiplier=1.0,
        )

        assert adjusted < 1.0

    def test_adjusted_size_low_volatility(self):
        """Test position size increased when volatility low."""
        adjusted = DynamicRiskManager.calculate_adjusted_size(
            base_size=1.0,
            atr=50.0,  # Low ATR
            base_atr=100.0,
            volatility_multiplier=1.0,
        )

        assert adjusted > 1.0

    def test_adjusted_size_respects_minimum(self):
        """Test that adjusted size respects minimum."""
        adjusted = DynamicRiskManager.calculate_adjusted_size(
            base_size=1.0,
            atr=500.0,  # Very high volatility
            base_atr=100.0,
            volatility_multiplier=1.0,
            min_size_pct=50.0,
        )

        assert adjusted >= 0.5  # At least 50% of base

    def test_adjusted_risk_pct_high_volatility(self):
        """Test risk % reduced when volatility high."""
        adjusted = DynamicRiskManager.calculate_adjusted_risk_pct(
            base_risk_pct=2.0,
            current_volatility=0.08,
            avg_volatility=0.04,
            max_risk_pct=5.0,
        )

        assert adjusted < 2.0

    def test_adjusted_risk_pct_low_volatility(self):
        """Test risk % increased when volatility low."""
        adjusted = DynamicRiskManager.calculate_adjusted_risk_pct(
            base_risk_pct=2.0,
            current_volatility=0.02,
            avg_volatility=0.04,
            max_risk_pct=5.0,
        )

        assert adjusted > 2.0

    def test_adjusted_risk_respects_maximum(self):
        """Test that risk % respects maximum."""
        adjusted = DynamicRiskManager.calculate_adjusted_risk_pct(
            base_risk_pct=2.0,
            current_volatility=0.01,
            avg_volatility=0.1,
            max_risk_pct=5.0,
        )

        assert adjusted <= 5.0


# ============================================================================
# Tests: PositionManagementEngine
# ============================================================================


class TestPositionManagementEngine:
    """Test integrated position management engine."""

    def test_engine_initialization(self, db):
        """Test engine initialization."""
        engine = PositionManagementEngine(db)

        assert engine.db is db
        assert engine.trailing_stop is not None
        assert engine.partial_close is not None
        assert engine.position_scaler is not None
        assert engine.breakeven is not None
        assert engine.dynamic_risk is not None

    @pytest.mark.asyncio
    async def test_process_position_long(self, db, long_trade):
        """Test processing position with multiple modes."""
        engine = PositionManagementEngine(db)

        results = await engine.process_position(
            trade_id=1,
            current_price=41234.56,
            atr=100.0,
            volatility=0.05,
            modes=[
                PositionManagementMode.TRAILING_STOP,
                PositionManagementMode.DYNAMIC_RISK,
            ],
        )

        assert results["trade_id"] == 1
        assert "trailing_stop" in results["updates"]
        assert "dynamic_risk" in results["updates"]

    @pytest.mark.asyncio
    async def test_process_position_not_found(self, db):
        """Test processing non-existent position."""
        engine = PositionManagementEngine(db)

        results = await engine.process_position(
            trade_id=999,
            current_price=41000.0,
        )

        assert len(results["errors"]) > 0


# ============================================================================
# Tests: Integration Scenarios
# ============================================================================


class TestAdvancedPositionIntegration:
    """Test complex position management scenarios."""

    def test_breakeven_then_trailing_long(self, db, long_trade):
        """Test sequence: trigger breakeven, then trailing stop."""
        # Step 1: Move to breakeven
        should_be, new_sl1, _ = BreakevenStopManager.calculate_breakeven_stop(
            entry_price=40000.0,
            current_price=41000.0,
            min_profit_pct=2.0,
            direction="LONG",
        )
        assert should_be is True

        # Step 2: Price moves higher, trailing stop kicks in
        new_sl2 = TrailingStopManager.calculate_trailing_stop(
            entry_price=40000.0,
            current_price=42000.0,
            trailing_amount=500.0,
            direction="LONG",
        )

        # Trailing stop should be lower than previous
        assert new_sl2 > new_sl1

    def test_multi_partial_close_sequence(self, db):
        """Test closing position in multiple steps."""
        trade = TradeDB(
            user_id="test_user",
            symbol="BTCUSDT",
            direction="LONG",
            entry_price=40000.0,
            quantity=1.0,
            entry_value=40000.0,
            order_id="big_trade",
            status=TradeStatus.OPEN.value,
            entry_timestamp=datetime.utcnow(),
            auto_close_enabled=True,
            stop_loss=38000.0,
            take_profit_1=42000.0,
        )
        db.add(trade)
        db.commit()

        # Close 40% at TP1
        closed1, pnl1, _ = PartialCloseManager.execute_partial_close(
            db, trade.id, 0.4, 42000.0
        )
        assert closed1 is True

        # Close 30% at higher price
        closed2, pnl2, _ = PartialCloseManager.execute_partial_close(
            db, trade.id, 0.3, 43000.0
        )
        assert closed2 is True

        # Remaining 30% still open
        remaining = db.query(TradeDB).filter(TradeDB.id == trade.id).first()
        assert remaining.quantity == pytest.approx(0.3, rel=1e-6)

    def test_dynamic_risk_scale_out(self):
        """Test combining dynamic risk with scale-out levels."""
        # High volatility scenario
        base_size = 1.0
        adjusted_size = DynamicRiskManager.calculate_adjusted_size(
            base_size=base_size,
            atr=200.0,
            base_atr=100.0,
            volatility_multiplier=1.0,
            min_size_pct=50.0,
        )

        # Calculate scale-out from adjusted size
        scale_levels = PositionScaler.calculate_scale_out_price(
            entry_price=40000.0,
            scale_steps=3,
            target_profit_pct=6.0,
            direction="LONG",
        )

        assert adjusted_size < base_size
        assert len(scale_levels) == 3
        assert scale_levels[0] < scale_levels[1] < scale_levels[2]
