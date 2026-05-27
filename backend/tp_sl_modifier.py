"""
Stop Loss / Take Profit Modification Handler

Allows users to adjust TP/SL levels after a trade is opened.
Validates new levels and updates them in the database.
"""

from datetime import datetime
from typing import Optional, Dict, Tuple
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository

logger = get_logger(__name__)


class TPSLModificationError(Exception):
    """Raised when TP/SL modification validation fails."""
    pass


class TPSLModifier:
    """Handles Stop Loss and Take Profit level modifications."""

    @staticmethod
    def validate_new_levels(
        trade: TradeDB,
        new_stop_loss: Optional[float] = None,
        new_tp1: Optional[float] = None,
        new_tp2: Optional[float] = None,
        new_tp3: Optional[float] = None,
    ) -> Dict[str, any]:
        """
        Validate new TP/SL levels before modification.

        Args:
            trade: Trade object to modify
            new_stop_loss: New SL price (or None to keep current)
            new_tp1, new_tp2, new_tp3: New TP prices (or None to keep current)

        Returns:
            Dictionary with validation result and details

        Raises:
            TPSLModificationError: If validation fails
        """
        if trade.status != TradeStatus.OPEN.value:
            raise TPSLModificationError(
                f"Cannot modify TP/SL on {trade.status} trade. Only OPEN trades can be modified."
            )

        entry_price = trade.entry_price
        direction = trade.direction

        # Validate SL
        if new_stop_loss is not None:
            if direction == "LONG":
                # For LONG: SL must be BELOW entry price (SL is a lower boundary)
                if new_stop_loss >= entry_price:
                    raise TPSLModificationError(
                        f"For LONG trade, SL ({new_stop_loss}) must be below entry ({entry_price})"
                    )
                # SL must be positive
                if new_stop_loss <= 0:
                    raise TPSLModificationError("SL must be positive")
                # Calculate max loss %
                loss_pct = ((entry_price - new_stop_loss) / entry_price) * 100
                if loss_pct < 0.1:
                    raise TPSLModificationError("SL too close to entry (min 0.1% gap)")
                if loss_pct > 50:
                    raise TPSLModificationError("SL too far from entry (max 50% gap)")

            else:  # SHORT
                # For SHORT: SL must be ABOVE entry price (SL is an upper boundary)
                if new_stop_loss <= entry_price:
                    raise TPSLModificationError(
                        f"For SHORT trade, SL ({new_stop_loss}) must be above entry ({entry_price})"
                    )
                # Calculate max loss %
                loss_pct = ((new_stop_loss - entry_price) / entry_price) * 100
                if loss_pct < 0.1:
                    raise TPSLModificationError("SL too close to entry (min 0.1% gap)")
                if loss_pct > 50:
                    raise TPSLModificationError("SL too far from entry (max 50% gap)")

        # Validate TPs
        tp_levels = [new_tp1, new_tp2, new_tp3]
        tp_names = ["TP1", "TP2", "TP3"]

        for i, (tp_price, tp_name) in enumerate(zip(tp_levels, tp_names)):
            if tp_price is not None:
                if direction == "LONG":
                    # For LONG: TP must be ABOVE entry price (TP is an upper boundary)
                    if tp_price <= entry_price:
                        raise TPSLModificationError(
                            f"For LONG trade, {tp_name} ({tp_price}) must be above entry ({entry_price})"
                        )
                    # Calculate gain %
                    gain_pct = ((tp_price - entry_price) / entry_price) * 100
                    if gain_pct < 0.1:
                        raise TPSLModificationError(f"{tp_name} too close to entry (min 0.1% gap)")
                    if gain_pct > 200:
                        raise TPSLModificationError(f"{tp_name} too far from entry (max 200% gain)")

                else:  # SHORT
                    # For SHORT: TP must be BELOW entry price (TP is a lower boundary)
                    if tp_price >= entry_price:
                        raise TPSLModificationError(
                            f"For SHORT trade, {tp_name} ({tp_price}) must be below entry ({entry_price})"
                        )
                    # Calculate gain %
                    gain_pct = ((entry_price - tp_price) / entry_price) * 100
                    if gain_pct < 0.1:
                        raise TPSLModificationError(f"{tp_name} too close to entry (min 0.1% gap)")
                    if gain_pct > 200:
                        raise TPSLModificationError(f"{tp_name} too far from entry (max 200% gain)")

        # Validate TP ordering (TP1 < TP2 < TP3)
        if direction == "LONG":
            # For LONG: TP1 < TP2 < TP3 (increasing)
            current_tp1 = new_tp1 if new_tp1 is not None else trade.take_profit_1
            current_tp2 = new_tp2 if new_tp2 is not None else trade.take_profit_2
            current_tp3 = new_tp3 if new_tp3 is not None else trade.take_profit_3

            if (
                current_tp1 and current_tp2 and current_tp1 >= current_tp2
            ):
                raise TPSLModificationError("For LONG: TP1 must be < TP2")
            if (
                current_tp2 and current_tp3 and current_tp2 >= current_tp3
            ):
                raise TPSLModificationError("For LONG: TP2 must be < TP3")

        else:  # SHORT
            # For SHORT: TP1 > TP2 > TP3 (decreasing)
            current_tp1 = new_tp1 if new_tp1 is not None else trade.take_profit_1
            current_tp2 = new_tp2 if new_tp2 is not None else trade.take_profit_2
            current_tp3 = new_tp3 if new_tp3 is not None else trade.take_profit_3

            if (
                current_tp1 and current_tp2 and current_tp1 <= current_tp2
            ):
                raise TPSLModificationError("For SHORT: TP1 must be > TP2")
            if (
                current_tp2 and current_tp3 and current_tp2 <= current_tp3
            ):
                raise TPSLModificationError("For SHORT: TP2 must be > TP3")

        return {
            "valid": True,
            "entry_price": entry_price,
            "direction": direction,
        }

    @staticmethod
    def modify_levels(
        db: SessionLocal,
        trade_id: int,
        new_stop_loss: Optional[float] = None,
        new_tp1: Optional[float] = None,
        new_tp2: Optional[float] = None,
        new_tp3: Optional[float] = None,
    ) -> TradeDB:
        """
        Modify TP/SL levels for an open trade.

        Args:
            db: Database session
            trade_id: Trade ID to modify
            new_stop_loss: New SL price (or None to keep)
            new_tp1, new_tp2, new_tp3: New TP prices (or None to keep)

        Returns:
            Updated trade object

        Raises:
            TPSLModificationError: If trade not found or validation fails
        """
        # Get trade
        trade = TradeRepository.get_trade_by_id(db, trade_id)
        if not trade:
            raise TPSLModificationError(f"Trade {trade_id} not found")

        # Validate new levels
        TPSLModifier.validate_new_levels(
            trade,
            new_stop_loss=new_stop_loss,
            new_tp1=new_tp1,
            new_tp2=new_tp2,
            new_tp3=new_tp3,
        )

        # Store old values for logging
        old_values = {
            "stop_loss": trade.stop_loss,
            "take_profit_1": trade.take_profit_1,
            "take_profit_2": trade.take_profit_2,
            "take_profit_3": trade.take_profit_3,
        }

        # Update trade with new values
        if new_stop_loss is not None:
            trade.stop_loss = new_stop_loss
        if new_tp1 is not None:
            trade.take_profit_1 = new_tp1
        if new_tp2 is not None:
            trade.take_profit_2 = new_tp2
        if new_tp3 is not None:
            trade.take_profit_3 = new_tp3

        # Update modification timestamp
        trade.updated_at = datetime.utcnow()

        db.add(trade)
        db.commit()
        db.refresh(trade)

        logger.info(
            f"Trade {trade_id} TP/SL modified",
            action="tp_sl_modified",
            trade_id=trade_id,
            symbol=trade.symbol,
            direction=trade.direction,
            old_values=old_values,
            new_values={
                "stop_loss": trade.stop_loss,
                "take_profit_1": trade.take_profit_1,
                "take_profit_2": trade.take_profit_2,
                "take_profit_3": trade.take_profit_3,
            },
        )

        return trade

    @staticmethod
    def calculate_new_rr_ratio(
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        direction: str,
    ) -> Optional[float]:
        """
        Calculate Risk/Reward ratio for new levels.

        Args:
            entry_price: Entry price
            stop_loss: SL price
            take_profit: TP price
            direction: LONG or SHORT

        Returns:
            RR ratio or None if levels not set
        """
        if not stop_loss or not take_profit:
            return None

        if direction == "LONG":
            risk = entry_price - stop_loss  # How much we lose if SL hit
            reward = take_profit - entry_price  # How much we gain if TP hit
        else:  # SHORT
            risk = stop_loss - entry_price  # How much we lose if SL hit
            reward = entry_price - take_profit  # How much we gain if TP hit

        if risk <= 0:
            return None

        return reward / risk

    @staticmethod
    def get_modification_history(
        db: SessionLocal,
        trade_id: int,
    ) -> Dict[str, any]:
        """
        Get TP/SL modification history for a trade.

        Current implementation returns current levels.
        Future: Store audit trail in separate table.

        Args:
            db: Database session
            trade_id: Trade ID

        Returns:
            Dictionary with current TP/SL levels and modification timestamp
        """
        trade = TradeRepository.get_trade_by_id(db, trade_id)
        if not trade:
            raise TPSLModificationError(f"Trade {trade_id} not found")

        return {
            "trade_id": trade_id,
            "stop_loss": trade.stop_loss,
            "take_profit_1": trade.take_profit_1,
            "take_profit_2": trade.take_profit_2,
            "take_profit_3": trade.take_profit_3,
            "last_modified": trade.updated_at,
            "created_at": trade.created_at,
        }
