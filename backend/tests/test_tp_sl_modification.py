"""
Unit tests for Stop Loss / Take Profit Modification.
Tests validation, boundary conditions, and modification logic.
"""

import pytest
from datetime import datetime
from tp_sl_modifier import TPSLModifier, TPSLModificationError


class MockTrade:
    """Mock trade for testing modification logic."""

    def __init__(
        self,
        id=1,
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        stop_loss=39000.0,
        take_profit_1=41000.0,
        take_profit_2=42000.0,
        take_profit_3=43000.0,
        status="OPEN",
        created_at=None,
        updated_at=None,
    ):
        self.id = id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2
        self.take_profit_3 = take_profit_3
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()


class TestLongTradeValidation:
    """Tests for LONG trade TP/SL validation."""

    def test_valid_sl_below_entry(self):
        """Valid LONG SL below entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        result = TPSLModifier.validate_new_levels(
            trade, new_stop_loss=39000.0  # 2.5% below entry
        )
        assert result["valid"] == True

    def test_invalid_sl_at_entry(self):
        """LONG SL cannot be at entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=40000.0)
        assert "must be below entry" in str(exc.value)

    def test_invalid_sl_above_entry(self):
        """LONG SL cannot be above entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=41000.0)
        assert "must be below entry" in str(exc.value)

    def test_valid_tp_above_entry(self):
        """Valid LONG TP above entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        result = TPSLModifier.validate_new_levels(
            trade, new_tp1=41000.0  # 2.5% above entry
        )
        assert result["valid"] == True

    def test_invalid_tp_at_entry(self):
        """LONG TP cannot be at entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_tp1=40000.0)
        assert "must be above entry" in str(exc.value)

    def test_invalid_tp_below_entry(self):
        """LONG TP cannot be below entry price."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_tp1=39000.0)
        assert "must be above entry" in str(exc.value)

    def test_sl_too_close_to_entry(self):
        """LONG SL less than 0.1% gap rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            # 39999 is only 0.0025% below entry
            TPSLModifier.validate_new_levels(trade, new_stop_loss=39999.0)
        assert "too close to entry" in str(exc.value)

    def test_tp_too_close_to_entry(self):
        """LONG TP less than 0.1% gap rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            # 40001 is only 0.0025% above entry
            TPSLModifier.validate_new_levels(trade, new_tp1=40001.0)
        assert "too close to entry" in str(exc.value)

    def test_sl_too_far_from_entry(self):
        """LONG SL more than 50% away rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            # 19000 is 52.5% below entry
            TPSLModifier.validate_new_levels(trade, new_stop_loss=19000.0)
        assert "too far from entry" in str(exc.value)

    def test_tp_too_far_from_entry(self):
        """LONG TP more than 200% away rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            # 160000 is 300% above entry
            TPSLModifier.validate_new_levels(trade, new_tp1=160000.0)
        assert "too far from entry" in str(exc.value)

    def test_valid_tp_ordering_long(self):
        """LONG TP1 < TP2 < TP3 ordering."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        result = TPSLModifier.validate_new_levels(
            trade,
            new_tp1=41000.0,
            new_tp2=42000.0,
            new_tp3=43000.0,
        )
        assert result["valid"] == True

    def test_invalid_tp_ordering_long_tp1_tp2(self):
        """LONG TP1 must be < TP2."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(
                trade,
                new_tp1=42000.0,  # TP1 > TP2
                new_tp2=41000.0,
            )
        assert "TP1 must be < TP2" in str(exc.value)

    def test_invalid_tp_ordering_long_tp2_tp3(self):
        """LONG TP2 must be < TP3."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(
                trade,
                new_tp2=43000.0,  # TP2 > TP3
                new_tp3=42000.0,
            )
        assert "TP2 must be < TP3" in str(exc.value)


class TestShortTradeValidation:
    """Tests for SHORT trade TP/SL validation."""

    def test_valid_sl_above_entry(self):
        """Valid SHORT SL above entry price."""
        trade = MockTrade(
            direction="SHORT",
            entry_price=40000.0,
            take_profit_1=39000.0,  # SHORT: TP decreases
            take_profit_2=38000.0,
            take_profit_3=37000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade, new_stop_loss=41000.0  # 2.5% above entry
        )
        assert result["valid"] == True

    def test_invalid_sl_at_entry(self):
        """SHORT SL cannot be at entry price."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=40000.0)
        assert "must be above entry" in str(exc.value)

    def test_invalid_sl_below_entry(self):
        """SHORT SL cannot be below entry price."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=39000.0)
        assert "must be above entry" in str(exc.value)

    def test_valid_tp_below_entry(self):
        """Valid SHORT TP below entry price."""
        trade = MockTrade(
            direction="SHORT",
            entry_price=40000.0,
            take_profit_1=39000.0,  # SHORT: TP decreases
            take_profit_2=38000.0,
            take_profit_3=37000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade, new_tp1=39000.0  # 2.5% below entry
        )
        assert result["valid"] == True

    def test_invalid_tp_at_entry(self):
        """SHORT TP cannot be at entry price."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_tp1=40000.0)
        assert "must be below entry" in str(exc.value)

    def test_invalid_tp_above_entry(self):
        """SHORT TP cannot be above entry price."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_tp1=41000.0)
        assert "must be below entry" in str(exc.value)

    def test_valid_tp_ordering_short(self):
        """SHORT TP1 > TP2 > TP3 ordering."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        result = TPSLModifier.validate_new_levels(
            trade,
            new_tp1=39000.0,
            new_tp2=38000.0,
            new_tp3=37000.0,
        )
        assert result["valid"] == True

    def test_invalid_tp_ordering_short_tp1_tp2(self):
        """SHORT TP1 must be > TP2."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(
                trade,
                new_tp1=38000.0,  # TP1 < TP2
                new_tp2=39000.0,
            )
        assert "TP1 must be > TP2" in str(exc.value)

    def test_invalid_tp_ordering_short_tp2_tp3(self):
        """SHORT TP2 must be > TP3."""
        trade = MockTrade(direction="SHORT", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(
                trade,
                new_tp2=37000.0,  # TP2 < TP3
                new_tp3=38000.0,
            )
        assert "TP2 must be > TP3" in str(exc.value)


class TestClosedTradeRestriction:
    """Tests that TP/SL cannot be modified on closed trades."""

    def test_cannot_modify_closed_trade(self):
        """Cannot modify TP/SL on CLOSED trade."""
        trade = MockTrade(status="CLOSED", direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=39000.0)
        assert "Only OPEN trades" in str(exc.value)

    def test_cannot_modify_cancelled_trade(self):
        """Cannot modify TP/SL on CANCELLED trade."""
        trade = MockTrade(status="CANCELLED", direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=39000.0)
        assert "Only OPEN trades" in str(exc.value)


class TestRiskRewardCalculation:
    """Tests for Risk/Reward ratio calculation."""

    def test_rr_ratio_long_trade(self):
        """Calculate RR ratio for LONG trade."""
        entry = 40000.0
        stop_loss = 39000.0  # 1000 risk
        take_profit = 42000.0  # 2000 reward
        direction = "LONG"

        rr = TPSLModifier.calculate_new_rr_ratio(entry, stop_loss, take_profit, direction)

        # RR = reward / risk = 2000 / 1000 = 2.0
        assert rr == pytest.approx(2.0, rel=1e-4)

    def test_rr_ratio_short_trade(self):
        """Calculate RR ratio for SHORT trade."""
        entry = 40000.0
        stop_loss = 41000.0  # 1000 risk
        take_profit = 38000.0  # 2000 reward
        direction = "SHORT"

        rr = TPSLModifier.calculate_new_rr_ratio(entry, stop_loss, take_profit, direction)

        # RR = reward / risk = 2000 / 1000 = 2.0
        assert rr == pytest.approx(2.0, rel=1e-4)

    def test_rr_ratio_even_risk_reward(self):
        """Calculate RR ratio with equal risk and reward."""
        entry = 40000.0
        stop_loss = 39500.0  # 500 risk
        take_profit = 40500.0  # 500 reward
        direction = "LONG"

        rr = TPSLModifier.calculate_new_rr_ratio(entry, stop_loss, take_profit, direction)

        # RR = 500 / 500 = 1.0
        assert rr == pytest.approx(1.0, rel=1e-4)

    def test_rr_ratio_high_reward(self):
        """Calculate RR ratio with high reward vs risk."""
        entry = 40000.0
        stop_loss = 39900.0  # 100 risk
        take_profit = 50000.0  # 10000 reward
        direction = "LONG"

        rr = TPSLModifier.calculate_new_rr_ratio(entry, stop_loss, take_profit, direction)

        # RR = 10000 / 100 = 100.0
        assert rr == pytest.approx(100.0, rel=1e-4)

    def test_rr_ratio_none_when_missing_levels(self):
        """RR ratio is None if SL or TP not set."""
        entry = 40000.0

        # No SL
        rr = TPSLModifier.calculate_new_rr_ratio(entry, None, 42000.0, "LONG")
        assert rr is None

        # No TP
        rr = TPSLModifier.calculate_new_rr_ratio(entry, 39000.0, None, "LONG")
        assert rr is None


class TestPartialModification:
    """Tests for modifying only some levels."""

    def test_modify_only_sl(self):
        """Modify only SL, keep TP levels."""
        trade = MockTrade(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
            take_profit_2=42000.0,
            take_profit_3=43000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade, new_stop_loss=38500.0  # Only modify SL
        )
        assert result["valid"] == True

    def test_modify_only_tp1(self):
        """Modify only TP1, keep others."""
        trade = MockTrade(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
            take_profit_2=42000.0,
            take_profit_3=43000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade, new_tp1=41500.0  # Only modify TP1
        )
        assert result["valid"] == True

    def test_modify_sl_and_tp1(self):
        """Modify both SL and TP1."""
        trade = MockTrade(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade,
            new_stop_loss=38500.0,
            new_tp1=41500.0,
        )
        assert result["valid"] == True

    def test_modify_all_levels(self):
        """Modify all TP/SL levels at once."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        result = TPSLModifier.validate_new_levels(
            trade,
            new_stop_loss=38000.0,
            new_tp1=42000.0,
            new_tp2=44000.0,
            new_tp3=46000.0,
        )
        assert result["valid"] == True


class TestEdgeCases:
    """Tests for edge cases in modification."""

    def test_exact_minimum_gap_sl(self):
        """SL exactly 0.1% from entry (minimum allowed)."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        # 0.1% below = 39960
        result = TPSLModifier.validate_new_levels(trade, new_stop_loss=39960.0)
        assert result["valid"] == True

    def test_exact_minimum_gap_tp(self):
        """TP exactly 0.1% from entry (minimum allowed)."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        # 0.1% above = 40040
        result = TPSLModifier.validate_new_levels(trade, new_tp1=40040.0)
        assert result["valid"] == True

    def test_exact_maximum_sl_gap(self):
        """SL exactly 50% from entry (maximum allowed)."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        # 50% below = 20000
        result = TPSLModifier.validate_new_levels(trade, new_stop_loss=20000.0)
        assert result["valid"] == True

    def test_exact_maximum_tp_gap(self):
        """TP exactly 200% from entry (maximum allowed)."""
        trade = MockTrade(
            direction="LONG",
            entry_price=40000.0,
            take_profit_1=100000.0,
            take_profit_2=150000.0,
            take_profit_3=200000.0,
        )

        # 200% above = 120000
        result = TPSLModifier.validate_new_levels(trade, new_tp1=120000.0)
        assert result["valid"] == True

    def test_very_small_entry_price(self):
        """Validation works with very small entry prices."""
        trade = MockTrade(direction="LONG", entry_price=0.0001)

        result = TPSLModifier.validate_new_levels(
            trade,
            new_stop_loss=0.00009,  # Below entry
            new_tp1=0.00011,  # Above entry
        )
        assert result["valid"] == True

    def test_very_large_entry_price(self):
        """Validation works with very large entry prices."""
        trade = MockTrade(
            direction="LONG",
            entry_price=100000.0,
            take_profit_1=101000.0,
            take_profit_2=102000.0,
            take_profit_3=103000.0,
        )

        result = TPSLModifier.validate_new_levels(
            trade,
            new_stop_loss=99000.0,
            new_tp1=101000.0,
        )
        assert result["valid"] == True

    def test_negative_stop_loss_rejected(self):
        """Negative SL prices rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=-1000.0)
        assert "must be positive" in str(exc.value)

    def test_zero_stop_loss_rejected(self):
        """Zero SL price rejected."""
        trade = MockTrade(direction="LONG", entry_price=40000.0)

        with pytest.raises(TPSLModificationError) as exc:
            TPSLModifier.validate_new_levels(trade, new_stop_loss=0.0)
        assert "must be positive" in str(exc.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
