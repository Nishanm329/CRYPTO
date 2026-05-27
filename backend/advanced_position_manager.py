"""
Advanced Position Management

Enables sophisticated trade management:
1. Trailing stop losses - auto-adjust SL as price moves in profit
2. Partial position closure - close portions at predefined levels
3. Scale in/out - dynamically adjust position size
4. Breakeven stops - move SL to entry once profitable
5. Dynamic risk adjustment - adjust size based on volatility
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository

logger = get_logger(__name__)


class PositionManagementMode(str, Enum):
    """Position management strategy modes."""
    TRAILING_STOP = "TRAILING_STOP"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    SCALE_IN = "SCALE_IN"
    SCALE_OUT = "SCALE_OUT"
    BREAKEVEN = "BREAKEVEN"
    DYNAMIC_RISK = "DYNAMIC_RISK"


class TrailingStopManager:
    """Manages trailing stop losses that adjust as price moves in profit."""

    @staticmethod
    def calculate_trailing_stop(
        entry_price: float,
        current_price: float,
        trailing_amount: float,
        trailing_pct: Optional[float] = None,
        direction: str = "LONG",
    ) -> Optional[float]:
        """
        Calculate new trailing stop loss.

        Args:
            entry_price: Trade entry price
            current_price: Current market price
            trailing_amount: Trailing distance in points
            trailing_pct: Trailing percentage (overrides amount if set)
            direction: LONG or SHORT

        Returns:
            New SL price or None if below entry (no profit)
        """
        if direction == "LONG":
            # For LONG: SL = current_price - trailing_distance
            if current_price <= entry_price:
                return None  # No profit yet

            trailing_distance = trailing_pct * current_price / 100 if trailing_pct else trailing_amount
            new_sl = current_price - trailing_distance

            # SL must be above entry price for LONG
            if new_sl <= entry_price:
                return entry_price + 0.001  # Minimal gap above entry

            return new_sl

        else:  # SHORT
            # For SHORT: SL = current_price + trailing_distance
            if current_price >= entry_price:
                return None  # No profit yet

            trailing_distance = trailing_pct * entry_price / 100 if trailing_pct else trailing_amount
            new_sl = current_price + trailing_distance

            # SL must be below entry price for SHORT
            if new_sl >= entry_price:
                return entry_price - 0.001  # Minimal gap below entry

            return new_sl

    @staticmethod
    def update_trailing_stop(
        db: SessionLocal,
        trade_id: int,
        current_price: float,
        trailing_amount: float,
        trailing_pct: Optional[float] = None,
        min_update_pct: float = 0.1,
    ) -> Tuple[bool, Optional[float], str]:
        """
        Update trade's stop loss if price moved in profit.

        Args:
            db: Database session
            trade_id: Trade ID to update
            current_price: Current market price
            trailing_amount: Trailing distance in points
            trailing_pct: Trailing percentage (overrides amount)
            min_update_pct: Minimum % move before updating SL

        Returns:
            (updated: bool, new_sl: float or None, message: str)
        """
        try:
            trade = TradeRepository.get_trade_by_id(db, trade_id)
            if not trade:
                return False, None, f"Trade {trade_id} not found"

            if trade.status != TradeStatus.OPEN.value:
                return False, None, f"Trade {trade_id} is {trade.status}, cannot update"

            # Calculate new SL
            new_sl = TrailingStopManager.calculate_trailing_stop(
                entry_price=trade.entry_price,
                current_price=current_price,
                trailing_amount=trailing_amount,
                trailing_pct=trailing_pct,
                direction=trade.direction,
            )

            if new_sl is None:
                return False, None, f"No profit yet (entry: {trade.entry_price}, current: {current_price})"

            # Check if move is significant enough
            if trade.stop_loss:
                current_move = abs(new_sl - trade.stop_loss) / trade.stop_loss * 100
                if current_move < min_update_pct:
                    return False, None, f"Move too small ({current_move:.2f}% < {min_update_pct}%)"

            # Update SL
            old_sl = trade.stop_loss
            trade.stop_loss = new_sl
            trade.updated_at = datetime.utcnow()

            db.add(trade)
            db.commit()
            db.refresh(trade)

            logger.info(
                f"Trailing stop updated for trade {trade_id}",
                action="trailing_stop_updated",
                trade_id=trade_id,
                symbol=trade.symbol,
                direction=trade.direction,
                old_sl=old_sl,
                new_sl=new_sl,
                current_price=current_price,
            )

            return True, new_sl, f"SL updated: {old_sl} → {new_sl}"

        except Exception as e:
            logger.error(
                f"Failed to update trailing stop for trade {trade_id}",
                action="trailing_stop_update_failed",
                trade_id=trade_id,
                error=str(e),
            )
            return False, None, str(e)


class PartialCloseManager:
    """Manages closing portions of trades at predefined price levels."""

    @staticmethod
    def calculate_partial_close(
        entry_price: float,
        current_price: float,
        close_pct: float,
        direction: str = "LONG",
    ) -> bool:
        """
        Check if price hit partial close level.

        Args:
            entry_price: Trade entry price
            current_price: Current market price
            close_pct: Profit % at which to close portion
            direction: LONG or SHORT

        Returns:
            True if close level reached
        """
        if direction == "LONG":
            close_price = entry_price * (1 + close_pct / 100)
            return current_price >= close_price
        else:  # SHORT
            close_price = entry_price * (1 - close_pct / 100)
            return current_price <= close_price

    @staticmethod
    def execute_partial_close(
        db: SessionLocal,
        trade_id: int,
        close_quantity: float,
        close_price: float,
        close_reason: str = "PARTIAL_CLOSE",
    ) -> Tuple[bool, Optional[float], str]:
        """
        Close a portion of an open trade.

        Args:
            db: Database session
            trade_id: Trade ID
            close_quantity: Quantity to close
            close_price: Close price
            close_reason: Reason for closure

        Returns:
            (closed: bool, realized_pnl: float or None, message: str)
        """
        try:
            trade = TradeRepository.get_trade_by_id(db, trade_id)
            if not trade:
                return False, None, f"Trade {trade_id} not found"

            if trade.status != TradeStatus.OPEN.value:
                return False, None, f"Trade {trade_id} is {trade.status}"

            # Validate quantity
            if close_quantity <= 0 or close_quantity > trade.quantity:
                return False, None, f"Invalid close quantity {close_quantity} (available: {trade.quantity})"

            # Calculate P&L for this portion
            if trade.direction == "LONG":
                pnl = (close_price - trade.entry_price) * close_quantity
            else:  # SHORT
                pnl = (trade.entry_price - close_price) * close_quantity

            pnl_pct = (pnl / (trade.entry_price * close_quantity)) * 100

            # Create partial close record (could store in separate table)
            # For now, log the closure
            remaining_quantity = trade.quantity - close_quantity

            logger.info(
                f"Partial close executed for trade {trade_id}",
                action="partial_close_executed",
                trade_id=trade_id,
                symbol=trade.symbol,
                direction=trade.direction,
                close_quantity=close_quantity,
                close_price=close_price,
                realized_pnl=pnl,
                realized_pnl_pct=pnl_pct,
                remaining_qty=remaining_quantity,
                close_reason=close_reason,
            )

            # Update trade quantity
            trade.quantity = remaining_quantity
            trade.updated_at = datetime.utcnow()

            db.add(trade)
            db.commit()
            db.refresh(trade)

            return True, pnl, f"Closed {close_quantity}, P&L: {pnl:.2f} ({pnl_pct:.2f}%)"

        except Exception as e:
            logger.error(
                f"Failed to execute partial close for trade {trade_id}",
                action="partial_close_failed",
                trade_id=trade_id,
                error=str(e),
            )
            return False, None, str(e)


class PositionScaler:
    """Manages scaling position size in/out based on conditions."""

    @staticmethod
    def calculate_scale_out_price(
        entry_price: float,
        scale_steps: int,
        target_profit_pct: float,
        direction: str = "LONG",
    ) -> List[float]:
        """
        Calculate prices to scale out of position.

        Args:
            entry_price: Entry price
            scale_steps: Number of scale-out steps
            target_profit_pct: Target profit % to reach
            direction: LONG or SHORT

        Returns:
            List of scale-out prices
        """
        prices = []

        for step in range(1, scale_steps + 1):
            # Interpolate profit level across steps
            step_profit_pct = (target_profit_pct / scale_steps) * step

            if direction == "LONG":
                scale_price = entry_price * (1 + step_profit_pct / 100)
            else:  # SHORT
                scale_price = entry_price * (1 - step_profit_pct / 100)

            prices.append(scale_price)

        return prices

    @staticmethod
    def calculate_scale_in_size(
        initial_size: float,
        base_price: float,
        current_price: float,
        scale_steps: int,
        max_loss_pct: float,
        direction: str = "LONG",
    ) -> Tuple[Optional[float], str]:
        """
        Calculate size for adding to position (averaging down/up).

        Args:
            initial_size: Initial position size
            base_price: Base entry price
            current_price: Current market price
            scale_steps: Total steps planned
            max_loss_pct: Max % loss allowed
            direction: LONG or SHORT

        Returns:
            (add_size: float or None, message: str)
        """
        if direction == "LONG":
            # Price went down (bad for LONG), consider adding
            if current_price >= base_price:
                return None, "Price above entry, don't scale in"

            loss_pct = (base_price - current_price) / base_price * 100
            if loss_pct > max_loss_pct:
                return None, f"Loss too deep ({loss_pct:.2f}% > {max_loss_pct}%)"

            # Add more at lower price (but less than initial)
            add_size = initial_size * (1 - loss_pct / 100) / scale_steps
            return add_size, f"Can add {add_size:.6f} at {current_price}"

        else:  # SHORT
            # Price went up (bad for SHORT), consider adding
            if current_price <= base_price:
                return None, "Price below entry, don't scale in"

            loss_pct = (current_price - base_price) / base_price * 100
            if loss_pct > max_loss_pct:
                return None, f"Loss too deep ({loss_pct:.2f}% > {max_loss_pct}%)"

            # Add more at higher price (but less than initial)
            add_size = initial_size * (1 - loss_pct / 100) / scale_steps
            return add_size, f"Can add {add_size:.6f} at {current_price}"


class BreakevenStopManager:
    """Moves stop loss to entry price once position becomes profitable."""

    @staticmethod
    def calculate_breakeven_stop(
        entry_price: float,
        current_price: float,
        min_profit_pct: float,
        direction: str = "LONG",
    ) -> Tuple[bool, Optional[float], str]:
        """
        Check if should move SL to breakeven.

        Args:
            entry_price: Entry price
            current_price: Current market price
            min_profit_pct: Minimum profit % before moving SL
            direction: LONG or SHORT

        Returns:
            (should_update: bool, new_sl: float or None, message: str)
        """
        if direction == "LONG":
            profit_pct = (current_price - entry_price) / entry_price * 100
            if profit_pct >= min_profit_pct:
                # Move SL to entry + small buffer
                new_sl = entry_price + 0.001
                return True, new_sl, f"Moving SL to breakeven at {new_sl}"
            else:
                return False, None, f"Profit {profit_pct:.2f}% < {min_profit_pct}%"

        else:  # SHORT
            profit_pct = (entry_price - current_price) / entry_price * 100
            if profit_pct >= min_profit_pct:
                # Move SL to entry - small buffer
                new_sl = entry_price - 0.001
                return True, new_sl, f"Moving SL to breakeven at {new_sl}"
            else:
                return False, None, f"Profit {profit_pct:.2f}% < {min_profit_pct}%"

    @staticmethod
    async def update_to_breakeven(
        db: SessionLocal,
        trade_id: int,
        current_price: float,
        min_profit_pct: float = 2.0,
    ) -> Tuple[bool, str]:
        """
        Update trade SL to breakeven if conditions met.

        Args:
            db: Database session
            trade_id: Trade ID
            current_price: Current market price
            min_profit_pct: Min profit % to trigger move

        Returns:
            (updated: bool, message: str)
        """
        try:
            trade = TradeRepository.get_trade_by_id(db, trade_id)
            if not trade:
                return False, f"Trade {trade_id} not found"

            should_update, new_sl, message = BreakevenStopManager.calculate_breakeven_stop(
                entry_price=trade.entry_price,
                current_price=current_price,
                min_profit_pct=min_profit_pct,
                direction=trade.direction,
            )

            if not should_update:
                return False, message

            old_sl = trade.stop_loss
            trade.stop_loss = new_sl
            trade.updated_at = datetime.utcnow()

            db.add(trade)
            db.commit()
            db.refresh(trade)

            logger.info(
                f"Breakeven stop activated for trade {trade_id}",
                action="breakeven_activated",
                trade_id=trade_id,
                symbol=trade.symbol,
                old_sl=old_sl,
                new_sl=new_sl,
            )

            return True, f"SL moved to breakeven: {new_sl}"

        except Exception as e:
            logger.error(
                f"Failed to update breakeven SL for trade {trade_id}",
                action="breakeven_update_failed",
                trade_id=trade_id,
                error=str(e),
            )
            return False, str(e)


class DynamicRiskManager:
    """Adjusts position size based on market volatility."""

    @staticmethod
    def calculate_adjusted_size(
        base_size: float,
        atr: float,
        base_atr: float,
        volatility_multiplier: float = 1.0,
        min_size_pct: float = 50.0,
    ) -> float:
        """
        Calculate position size adjusted for current volatility.

        Args:
            base_size: Base position size
            atr: Current Average True Range
            base_atr: Base/reference ATR
            volatility_multiplier: Multiplier for ATR changes
            min_size_pct: Minimum size as % of base

        Returns:
            Adjusted position size
        """
        if base_atr <= 0 or atr <= 0:
            return base_size

        # If volatility higher, reduce size. If lower, increase size.
        volatility_ratio = atr / base_atr
        size_multiplier = 1.0 / volatility_ratio

        # Apply multiplier
        adjusted = base_size * (1 + (size_multiplier - 1) * volatility_multiplier)

        # Apply minimum
        min_size = base_size * (min_size_pct / 100)
        return max(adjusted, min_size)

    @staticmethod
    def calculate_adjusted_risk_pct(
        base_risk_pct: float,
        current_volatility: float,
        avg_volatility: float,
        max_risk_pct: float = 5.0,
    ) -> float:
        """
        Calculate position risk % adjusted for volatility.

        Args:
            base_risk_pct: Base risk percentage
            current_volatility: Current market volatility (0-1)
            avg_volatility: Average volatility for comparison
            max_risk_pct: Maximum risk allowed

        Returns:
            Adjusted risk percentage
        """
        if avg_volatility <= 0:
            return base_risk_pct

        # Inverse relationship: high volatility = lower risk
        vol_multiplier = avg_volatility / current_volatility
        adjusted = base_risk_pct * vol_multiplier

        # Cap at maximum
        return min(adjusted, max_risk_pct)


class PositionManagementEngine:
    """Coordinates all position management strategies."""

    def __init__(self, db: SessionLocal):
        """Initialize engine with database connection."""
        self.db = db
        self.trailing_stop = TrailingStopManager()
        self.partial_close = PartialCloseManager()
        self.position_scaler = PositionScaler()
        self.breakeven = BreakevenStopManager()
        self.dynamic_risk = DynamicRiskManager()

    async def process_position(
        self,
        trade_id: int,
        current_price: float,
        atr: Optional[float] = None,
        volatility: Optional[float] = None,
        modes: Optional[List[PositionManagementMode]] = None,
    ) -> Dict[str, Any]:
        """
        Process a trade with all enabled management strategies.

        Args:
            trade_id: Trade ID to manage
            current_price: Current market price
            atr: Current ATR (for dynamic risk)
            volatility: Current volatility (for dynamic risk)
            modes: List of modes to apply (default: all)

        Returns:
            Dict with results from each management mode
        """
        if modes is None:
            modes = list(PositionManagementMode)

        results = {
            "trade_id": trade_id,
            "timestamp": datetime.utcnow().isoformat(),
            "updates": {},
            "errors": [],
        }

        trade = TradeRepository.get_trade_by_id(self.db, trade_id)
        if not trade:
            results["errors"].append(f"Trade {trade_id} not found")
            return results

        # Apply each enabled mode
        if PositionManagementMode.TRAILING_STOP in modes:
            success, new_sl, msg = TrailingStopManager.update_trailing_stop(
                self.db, trade_id, current_price, trailing_amount=100
            )
            results["updates"]["trailing_stop"] = {"success": success, "message": msg}

        if PositionManagementMode.BREAKEVEN in modes:
            success, msg = await BreakevenStopManager.update_to_breakeven(
                self.db, trade_id, current_price, min_profit_pct=2.0
            )
            results["updates"]["breakeven"] = {"success": success, "message": msg}

        if PositionManagementMode.DYNAMIC_RISK in modes and atr is not None:
            adjusted_size = DynamicRiskManager.calculate_adjusted_size(
                base_size=trade.quantity, atr=atr, base_atr=atr * 1.2
            )
            results["updates"]["dynamic_risk"] = {
                "original_size": trade.quantity,
                "adjusted_size": adjusted_size,
            }

        return results
