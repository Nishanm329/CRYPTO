"""
Trade validation and safety checks before execution.
Implements pre-flight validation rules to prevent risky trades.
"""

from typing import Dict, Any, Optional, Tuple
from models import SignalDirection
from logging_config import get_logger

logger = get_logger(__name__)

# Constants
BINANCE_MIN_NOTIONAL = 10  # Minimum order value in USDT
MIN_SIGNAL_CONFIDENCE = 45  # Minimum confidence to trade
MAX_RISK_PCT = 5.0  # Maximum risk per trade
MIN_RISK_PCT = 1.0  # Minimum risk per trade


class TradeValidationError(Exception):
    """Raised when trade validation fails."""
    pass


class TradeValidator:
    """
    Validates trades before execution.
    Implements safety checks to prevent risky or invalid trades.
    """

    @staticmethod
    def validate_symbol(symbol: str) -> None:
        """
        Validate that symbol is in proper format.
        """
        if not symbol:
            raise TradeValidationError("Symbol is required")

        symbol = symbol.upper()

        # Must be USDT trading pair
        if not symbol.endswith("USDT"):
            raise TradeValidationError(
                f"Invalid symbol: {symbol}. Must be a USDT trading pair (e.g., BTCUSDT)"
            )

        # Must have base asset (at least 2 chars for BTC, SOL, etc.)
        if len(symbol) < 7:  # Minimum: XXUSDT
            raise TradeValidationError(f"Invalid symbol format: {symbol}")

        logger.debug(
            f"Symbol validated: {symbol}",
            action="symbol_validated",
            symbol=symbol,
        )

    @staticmethod
    def validate_direction(direction: str) -> None:
        """
        Validate trade direction.
        """
        if direction not in ["LONG", "SHORT"]:
            raise TradeValidationError(
                f"Invalid direction: {direction}. Must be LONG or SHORT"
            )

        logger.debug(
            f"Direction validated: {direction}",
            action="direction_validated",
            direction=direction,
        )

    @staticmethod
    def validate_risk_percentage(risk_pct: float) -> None:
        """
        Validate risk percentage is within safe bounds (1-5%).
        """
        if not isinstance(risk_pct, (int, float)):
            raise TradeValidationError("Risk percentage must be a number")

        if risk_pct < MIN_RISK_PCT or risk_pct > MAX_RISK_PCT:
            raise TradeValidationError(
                f"Risk percentage must be between {MIN_RISK_PCT}-{MAX_RISK_PCT}%, got {risk_pct}%"
            )

        logger.debug(
            f"Risk percentage validated: {risk_pct}%",
            action="risk_pct_validated",
            risk_pct=risk_pct,
        )

    @staticmethod
    def validate_signal_confidence(confidence: int) -> None:
        """
        Validate signal confidence is above minimum threshold.
        """
        if not isinstance(confidence, int):
            raise TradeValidationError("Confidence must be an integer")

        if confidence < MIN_SIGNAL_CONFIDENCE:
            raise TradeValidationError(
                f"Signal confidence {confidence}% is below minimum {MIN_SIGNAL_CONFIDENCE}%"
            )

        if confidence > 100:
            raise TradeValidationError("Signal confidence cannot exceed 100%")

        logger.debug(
            f"Signal confidence validated: {confidence}%",
            action="confidence_validated",
            confidence=confidence,
        )

    @staticmethod
    def validate_position_size(
        wallet_balance: float,
        risk_pct: float,
        entry_price: float,
        quantity: float,
    ) -> Tuple[float, float]:
        """
        Validate position size meets minimum notional requirements.

        Returns:
            Tuple of (order_value, position_size)

        Raises:
            TradeValidationError: If position is too small or balance insufficient
        """
        if wallet_balance <= 0:
            raise TradeValidationError(
                f"Invalid wallet balance: {wallet_balance}. Must be positive."
            )

        if entry_price <= 0:
            raise TradeValidationError(
                f"Invalid entry price: {entry_price}. Must be positive."
            )

        if quantity <= 0:
            raise TradeValidationError(
                f"Invalid quantity: {quantity}. Must be positive."
            )

        # Calculate position value
        order_value = quantity * entry_price

        # Check minimum notional
        if order_value < BINANCE_MIN_NOTIONAL:
            required_qty = BINANCE_MIN_NOTIONAL / entry_price
            raise TradeValidationError(
                f"Order value ${order_value:.2f} is below minimum ${BINANCE_MIN_NOTIONAL}. "
                f"Increase quantity to at least {required_qty:.8f} {entry_price}"
            )

        # Check position doesn't exceed wallet
        risk_amount = wallet_balance * (risk_pct / 100)
        if order_value > wallet_balance:
            raise TradeValidationError(
                f"Position value ${order_value:.2f} exceeds wallet balance ${wallet_balance:.2f}"
            )

        logger.debug(
            f"Position size validated",
            action="position_size_validated",
            order_value=order_value,
            quantity=quantity,
            wallet_balance=wallet_balance,
        )

        return (order_value, quantity)

    @staticmethod
    def validate_entry_price(entry_price: float, current_price: Optional[float] = None) -> None:
        """
        Validate entry price is reasonable.
        Optionally check it's not too far from current market price.
        """
        if entry_price <= 0:
            raise TradeValidationError(f"Entry price must be positive, got {entry_price}")

        # Optional: check entry price isn't stale (>5% off current price)
        if current_price and current_price > 0:
            price_diff_pct = abs(entry_price - current_price) / current_price * 100
            if price_diff_pct > 10:
                logger.warning(
                    f"Entry price differs from current price by {price_diff_pct:.1f}%",
                    action="entry_price_stale",
                    entry_price=entry_price,
                    current_price=current_price,
                    diff_pct=price_diff_pct,
                )

        logger.debug(
            f"Entry price validated: ${entry_price}",
            action="entry_price_validated",
            entry_price=entry_price,
        )

    @staticmethod
    def validate_trade_request(
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        risk_pct: float,
        wallet_balance: float,
        confidence: int,
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of all trade parameters.

        Returns:
            Dict with validation details

        Raises:
            TradeValidationError: If any validation fails
        """
        try:
            # Validate all components
            TradeValidator.validate_symbol(symbol)
            TradeValidator.validate_direction(direction)
            TradeValidator.validate_risk_percentage(risk_pct)
            TradeValidator.validate_signal_confidence(confidence)
            TradeValidator.validate_entry_price(entry_price)
            order_value, validated_qty = TradeValidator.validate_position_size(
                wallet_balance, risk_pct, entry_price, quantity
            )

            logger.info(
                f"Trade validation passed: {direction} {validated_qty:.8f} {symbol}",
                action="trade_validation_passed",
                symbol=symbol,
                direction=direction,
                quantity=validated_qty,
                order_value=order_value,
                confidence=confidence,
            )

            return {
                "valid": True,
                "symbol": symbol.upper(),
                "direction": direction,
                "entry_price": entry_price,
                "quantity": validated_qty,
                "order_value": order_value,
                "risk_pct": risk_pct,
                "confidence": confidence,
                "wallet_balance": wallet_balance,
            }

        except TradeValidationError as e:
            logger.warning(
                f"Trade validation failed: {str(e)}",
                action="trade_validation_failed",
                symbol=symbol,
                direction=direction,
                error=str(e),
            )
            raise


class PaperTradingSimulator:
    """
    Simulates trade execution for paper trading mode.
    Useful for testing without real money.
    """

    @staticmethod
    def simulate_market_order(
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
    ) -> Dict[str, Any]:
        """
        Simulate a market order execution.
        Returns a simulated Binance order response.
        """
        import time

        simulated_order = {
            "symbol": symbol,
            "orderId": int(time.time() * 1000),  # Unix timestamp as order ID
            "clientOrderId": f"paper_{int(time.time() * 1000)}",
            "transactTime": int(time.time() * 1000),
            "price": "0.00000000",
            "origQty": str(quantity),
            "executedQty": str(quantity),
            "cummulativeQuoteQty": str(quantity * current_price),
            "status": "FILLED",
            "timeInForce": "IOC",
            "type": "MARKET",
            "side": side,
            "fills": [
                {
                    "price": str(current_price),
                    "qty": str(quantity),
                    "commission": "0.001",  # 0.1% fee
                    "commissionAsset": "USDT",
                    "tradeId": int(time.time() * 1000),
                }
            ],
        }

        logger.info(
            f"Simulated {side} market order: {quantity} {symbol} @ ${current_price}",
            action="paper_trade_simulated",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            order_id=simulated_order["orderId"],
        )

        return simulated_order

    @staticmethod
    def calculate_pnl(
        entry_price: float,
        exit_price: float,
        quantity: float,
        direction: str,
        fees: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate P&L for a closed trade.

        Returns:
            Dict with pnl, pnl_pct, and fees
        """
        if direction == "LONG":
            gross_pnl = (exit_price - entry_price) * quantity
        else:  # SHORT
            gross_pnl = (entry_price - exit_price) * quantity

        net_pnl = gross_pnl - fees
        entry_value = entry_price * quantity
        pnl_pct = (net_pnl / entry_value * 100) if entry_value > 0 else 0

        logger.debug(
            f"P&L calculated: {net_pnl:.2f} USDT ({pnl_pct:.2f}%)",
            action="pnl_calculated",
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            pnl_pct=pnl_pct,
            fees=fees,
        )

        return {
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "fees": fees,
        }
