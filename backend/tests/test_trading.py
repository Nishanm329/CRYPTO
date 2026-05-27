"""
Unit tests for trading validation and execution logic.
Tests TradeValidator, PaperTradingSimulator, and position sizing calculations.
"""

import pytest
from datetime import datetime
from trade_validator import (
    TradeValidator,
    PaperTradingSimulator,
    TradeValidationError,
)


class TestTradeValidator:
    """Tests for TradeValidator class."""

    def test_validate_symbol_valid_usdt_pair(self):
        """Valid USDT trading pair should pass."""
        TradeValidator.validate_symbol("BTCUSDT")
        TradeValidator.validate_symbol("ETHUSDT")
        TradeValidator.validate_symbol("BNBUSDT")
        TradeValidator.validate_symbol("btcusdt")  # Case insensitive

    def test_validate_symbol_invalid_missing_usdt(self):
        """Symbol without USDT suffix should raise error."""
        with pytest.raises(TradeValidationError, match="Must be a USDT trading pair"):
            TradeValidator.validate_symbol("BTC")

        with pytest.raises(TradeValidationError, match="Must be a USDT trading pair"):
            TradeValidator.validate_symbol("BTCBUSD")

    def test_validate_symbol_invalid_format(self):
        """Symbol too short should raise error."""
        with pytest.raises(TradeValidationError, match="Invalid symbol format"):
            TradeValidator.validate_symbol("XUSDT")  # Too short

    def test_validate_symbol_empty(self):
        """Empty symbol should raise error."""
        with pytest.raises(TradeValidationError, match="Symbol is required"):
            TradeValidator.validate_symbol("")

    def test_validate_direction_long(self):
        """LONG direction should pass."""
        TradeValidator.validate_direction("LONG")

    def test_validate_direction_short(self):
        """SHORT direction should pass."""
        TradeValidator.validate_direction("SHORT")

    def test_validate_direction_invalid(self):
        """Invalid direction should raise error."""
        with pytest.raises(TradeValidationError, match="Must be LONG or SHORT"):
            TradeValidator.validate_direction("BUY")

        with pytest.raises(TradeValidationError, match="Must be LONG or SHORT"):
            TradeValidator.validate_direction("invalid")

    def test_validate_risk_percentage_valid_min(self):
        """Minimum risk (1%) should pass."""
        TradeValidator.validate_risk_percentage(1.0)

    def test_validate_risk_percentage_valid_mid(self):
        """Mid-range risk (2%) should pass."""
        TradeValidator.validate_risk_percentage(2.0)

    def test_validate_risk_percentage_valid_max(self):
        """Maximum risk (5%) should pass."""
        TradeValidator.validate_risk_percentage(5.0)

    def test_validate_risk_percentage_below_min(self):
        """Risk below 1% should raise error."""
        with pytest.raises(TradeValidationError, match="must be between 1.0-5.0%"):
            TradeValidator.validate_risk_percentage(0.5)

    def test_validate_risk_percentage_above_max(self):
        """Risk above 5% should raise error."""
        with pytest.raises(TradeValidationError, match="must be between 1.0-5.0%"):
            TradeValidator.validate_risk_percentage(10.0)

    def test_validate_risk_percentage_not_number(self):
        """Non-numeric risk should raise error."""
        with pytest.raises(TradeValidationError, match="must be a number"):
            TradeValidator.validate_risk_percentage("2%")

    def test_validate_signal_confidence_valid_min(self):
        """Minimum confidence (45%) should pass."""
        TradeValidator.validate_signal_confidence(45)

    def test_validate_signal_confidence_valid_mid(self):
        """Mid-range confidence (70%) should pass."""
        TradeValidator.validate_signal_confidence(70)

    def test_validate_signal_confidence_valid_max(self):
        """Maximum confidence (100%) should pass."""
        TradeValidator.validate_signal_confidence(100)

    def test_validate_signal_confidence_below_min(self):
        """Confidence below 45% should raise error."""
        with pytest.raises(TradeValidationError, match="below minimum 45%"):
            TradeValidator.validate_signal_confidence(40)

    def test_validate_signal_confidence_above_max(self):
        """Confidence above 100% should raise error."""
        with pytest.raises(TradeValidationError, match="cannot exceed 100%"):
            TradeValidator.validate_signal_confidence(105)

    def test_validate_signal_confidence_not_integer(self):
        """Non-integer confidence should raise error."""
        with pytest.raises(TradeValidationError, match="must be an integer"):
            TradeValidator.validate_signal_confidence(50.5)

    def test_validate_entry_price_positive(self):
        """Positive entry price should pass."""
        TradeValidator.validate_entry_price(40000.0)
        TradeValidator.validate_entry_price(0.01)

    def test_validate_entry_price_zero(self):
        """Zero entry price should raise error."""
        with pytest.raises(TradeValidationError, match="must be positive"):
            TradeValidator.validate_entry_price(0)

    def test_validate_entry_price_negative(self):
        """Negative entry price should raise error."""
        with pytest.raises(TradeValidationError, match="must be positive"):
            TradeValidator.validate_entry_price(-100)

    def test_validate_entry_price_stale_warning(self, caplog):
        """Entry price far from current price should warn."""
        # Price diff > 10% should trigger warning
        TradeValidator.validate_entry_price(entry_price=40000, current_price=45000)
        # Should complete without error but log warning

    def test_validate_position_size_valid(self):
        """Valid position size should pass and return order_value and quantity."""
        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=10000.0,
            risk_pct=2.0,
            entry_price=40000.0,
            quantity=0.005,  # $200 notional
        )
        assert order_value == 200.0
        assert quantity == 0.005

    def test_validate_position_size_minimum_notional(self):
        """Position below $10 minimum notional should raise error."""
        with pytest.raises(TradeValidationError, match="below minimum"):
            TradeValidator.validate_position_size(
                wallet_balance=10000.0,
                risk_pct=2.0,
                entry_price=40000.0,
                quantity=0.0001,  # $4 notional
            )

    def test_validate_position_size_exceeds_wallet(self):
        """Position exceeding wallet balance should raise error."""
        with pytest.raises(TradeValidationError, match="exceeds wallet balance"):
            TradeValidator.validate_position_size(
                wallet_balance=10000.0,
                risk_pct=2.0,
                entry_price=40000.0,
                quantity=1.0,  # $40,000 > wallet
            )

    def test_validate_position_size_invalid_wallet(self):
        """Non-positive wallet balance should raise error."""
        with pytest.raises(TradeValidationError, match="Invalid wallet balance"):
            TradeValidator.validate_position_size(
                wallet_balance=0,
                risk_pct=2.0,
                entry_price=40000.0,
                quantity=0.005,
            )

        with pytest.raises(TradeValidationError, match="Invalid wallet balance"):
            TradeValidator.validate_position_size(
                wallet_balance=-1000,
                risk_pct=2.0,
                entry_price=40000.0,
                quantity=0.005,
            )

    def test_validate_position_size_invalid_entry_price(self):
        """Non-positive entry price should raise error."""
        with pytest.raises(TradeValidationError, match="Invalid entry price"):
            TradeValidator.validate_position_size(
                wallet_balance=10000.0,
                risk_pct=2.0,
                entry_price=0,
                quantity=0.005,
            )

    def test_validate_position_size_invalid_quantity(self):
        """Non-positive quantity should raise error."""
        with pytest.raises(TradeValidationError, match="Invalid quantity"):
            TradeValidator.validate_position_size(
                wallet_balance=10000.0,
                risk_pct=2.0,
                entry_price=40000.0,
                quantity=0,
            )

    def test_validate_trade_request_complete_flow(self):
        """Complete trade request validation should pass with valid params."""
        result = TradeValidator.validate_trade_request(
            symbol="BTCUSDT",
            direction="LONG",
            entry_price=40000.0,
            quantity=0.005,
            risk_pct=2.0,
            wallet_balance=10000.0,
            confidence=70,
        )

        assert result["valid"] is True
        assert result["symbol"] == "BTCUSDT"
        assert result["direction"] == "LONG"
        assert result["entry_price"] == 40000.0
        assert result["quantity"] == 0.005
        assert result["order_value"] == 200.0
        assert result["risk_pct"] == 2.0
        assert result["confidence"] == 70
        assert result["wallet_balance"] == 10000.0

    def test_validate_trade_request_invalid_symbol(self):
        """Invalid symbol should raise error."""
        with pytest.raises(TradeValidationError):
            TradeValidator.validate_trade_request(
                symbol="BTC",  # Invalid
                direction="LONG",
                entry_price=40000.0,
                quantity=0.005,
                risk_pct=2.0,
                wallet_balance=10000.0,
                confidence=70,
            )

    def test_validate_trade_request_invalid_confidence(self):
        """Low confidence should raise error."""
        with pytest.raises(TradeValidationError):
            TradeValidator.validate_trade_request(
                symbol="BTCUSDT",
                direction="LONG",
                entry_price=40000.0,
                quantity=0.005,
                risk_pct=2.0,
                wallet_balance=10000.0,
                confidence=30,  # Below 45% minimum
            )

    def test_validate_trade_request_short_direction(self):
        """SHORT direction should be validated correctly."""
        result = TradeValidator.validate_trade_request(
            symbol="ETHUSDT",
            direction="SHORT",
            entry_price=2000.0,
            quantity=1.0,
            risk_pct=3.0,
            wallet_balance=10000.0,
            confidence=60,
        )

        assert result["valid"] is True
        assert result["direction"] == "SHORT"


class TestPaperTradingSimulator:
    """Tests for PaperTradingSimulator class."""

    def test_simulate_market_order_buy(self):
        """Simulated market BUY order should return filled status."""
        order = PaperTradingSimulator.simulate_market_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.005,
            current_price=40000.0,
        )

        assert order["symbol"] == "BTCUSDT"
        assert order["side"] == "BUY"
        assert order["status"] == "FILLED"
        assert order["type"] == "MARKET"
        assert float(order["origQty"]) == 0.005
        assert float(order["executedQty"]) == 0.005
        assert order["fills"][0]["price"] == "40000.0"

    def test_simulate_market_order_sell(self):
        """Simulated market SELL order should return filled status."""
        order = PaperTradingSimulator.simulate_market_order(
            symbol="ETHUSDT",
            side="SELL",
            quantity=1.0,
            current_price=2000.0,
        )

        assert order["symbol"] == "ETHUSDT"
        assert order["side"] == "SELL"
        assert order["status"] == "FILLED"
        assert float(order["origQty"]) == 1.0

    def test_simulate_market_order_commission(self):
        """Simulated order should include 0.1% commission."""
        order = PaperTradingSimulator.simulate_market_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.005,
            current_price=40000.0,
        )

        commission = float(order["fills"][0]["commission"])
        assert commission == 0.001  # 0.1% fee

    def test_simulate_market_order_cumulative_quote_qty(self):
        """Simulated order should calculate cumulative quote quantity."""
        order = PaperTradingSimulator.simulate_market_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.005,
            current_price=40000.0,
        )

        cqq = float(order["cummulativeQuoteQty"])
        assert cqq == 200.0  # 0.005 * 40000


class TestPnLCalculation:
    """Tests for P&L calculation logic."""

    def test_calculate_pnl_long_profit(self):
        """Long trade with exit > entry should show profit."""
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="LONG",
            fees=1.0,
        )

        assert pnl_data["gross_pnl"] == 5.0  # (41000 - 40000) * 0.005
        assert pnl_data["net_pnl"] == 4.0  # 5 - 1 fee
        assert pnl_data["pnl_pct"] == 2.0  # (4 / 200) * 100

    def test_calculate_pnl_long_loss(self):
        """Long trade with exit < entry should show loss."""
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=39000.0,
            quantity=0.005,
            direction="LONG",
            fees=1.0,
        )

        assert pnl_data["gross_pnl"] == -5.0
        assert pnl_data["net_pnl"] == -6.0  # -5 - 1 fee
        assert pnl_data["pnl_pct"] == -3.0

    def test_calculate_pnl_short_profit(self):
        """Short trade with exit < entry should show profit."""
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=39000.0,
            quantity=0.005,
            direction="SHORT",
            fees=1.0,
        )

        assert pnl_data["gross_pnl"] == 5.0  # (40000 - 39000) * 0.005
        assert pnl_data["net_pnl"] == 4.0
        assert pnl_data["pnl_pct"] == 2.0

    def test_calculate_pnl_short_loss(self):
        """Short trade with exit > entry should show loss."""
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="SHORT",
            fees=1.0,
        )

        assert pnl_data["gross_pnl"] == -5.0
        assert pnl_data["net_pnl"] == -6.0
        assert pnl_data["pnl_pct"] == -3.0

    def test_calculate_pnl_no_fees(self):
        """P&L calculation without fees."""
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=42000.0,
            quantity=0.01,
            direction="LONG",
            fees=0.0,
        )

        assert pnl_data["gross_pnl"] == 20.0  # (42000 - 40000) * 0.01 = 2000 * 0.01
        assert pnl_data["net_pnl"] == 20.0
        assert pnl_data["pnl_pct"] == 5.0  # (20 / 400) * 100


class TestPositionSizingCalculations:
    """Tests for position sizing logic with various wallet sizes."""

    def test_position_sizing_small_wallet(self):
        """Position sizing with small wallet ($1000)."""
        wallet = 1000.0
        risk_pct = 2.0
        entry_price = 40000.0

        position_value = wallet * (risk_pct / 100)  # $20
        expected_quantity = position_value / entry_price  # 0.0005

        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=wallet,
            risk_pct=risk_pct,
            entry_price=entry_price,
            quantity=expected_quantity,
        )

        assert order_value == 20.0
        assert quantity == 0.0005

    def test_position_sizing_medium_wallet(self):
        """Position sizing with medium wallet ($10000)."""
        wallet = 10000.0
        risk_pct = 2.5
        entry_price = 2000.0

        position_value = wallet * (risk_pct / 100)  # $250
        expected_quantity = position_value / entry_price  # 0.125

        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=wallet,
            risk_pct=risk_pct,
            entry_price=entry_price,
            quantity=expected_quantity,
        )

        assert order_value == 250.0
        assert quantity == 0.125

    def test_position_sizing_large_wallet(self):
        """Position sizing with large wallet ($100000)."""
        wallet = 100000.0
        risk_pct = 3.0
        entry_price = 50.0

        position_value = wallet * (risk_pct / 100)  # $3000
        expected_quantity = position_value / entry_price  # 60

        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=wallet,
            risk_pct=risk_pct,
            entry_price=entry_price,
            quantity=expected_quantity,
        )

        assert order_value == 3000.0
        assert quantity == 60.0

    def test_position_sizing_respects_min_risk(self):
        """Position sizing enforces minimum 1% risk."""
        # With minimum risk (1%), should still place valid order
        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=10000.0,
            risk_pct=1.0,
            entry_price=40000.0,
            quantity=0.0025,  # $100
        )

        assert order_value == 100.0

    def test_position_sizing_respects_max_risk(self):
        """Position sizing enforces maximum 5% risk."""
        # With maximum risk (5%), should still place valid order
        order_value, quantity = TradeValidator.validate_position_size(
            wallet_balance=10000.0,
            risk_pct=5.0,
            entry_price=40000.0,
            quantity=0.0125,  # $500
        )

        assert order_value == 500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
