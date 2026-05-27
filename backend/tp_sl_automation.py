"""
Stop Loss / Take Profit Automation Engine

Monitors open trades and automatically closes them when TP or SL levels are reached.
Runs as a background job that checks trades periodically.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository
from binance_client import get_klines

logger = get_logger(__name__)


class TPSLAutomationEngine:
    """Handles Stop Loss and Take Profit automation for open trades."""

    def __init__(self, check_interval_seconds: int = 60):
        """
        Initialize the automation engine.

        Args:
            check_interval_seconds: How often to check open trades (default 60 seconds)
        """
        self.check_interval = check_interval_seconds
        self.running = False

    async def start(self):
        """Start the automation loop."""
        self.running = True
        logger.info(
            "TP/SL Automation Engine started",
            action="automation_started",
            check_interval_seconds=self.check_interval,
        )
        while self.running:
            try:
                await self.check_and_close_trades()
            except Exception as e:
                logger.error(
                    f"Error in TP/SL automation loop: {e}",
                    action="automation_error",
                    exc_info=True,
                )
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Stop the automation loop."""
        self.running = False
        logger.info("TP/SL Automation Engine stopped", action="automation_stopped")

    async def check_and_close_trades(self) -> Dict[str, int]:
        """
        Check all open trades and close any that hit TP or SL levels.

        Returns:
            Dictionary with counts: {"tp_closed": N, "sl_closed": N, "errors": N}
        """
        db = SessionLocal()
        results = {"tp_closed": 0, "sl_closed": 0, "errors": 0}

        try:
            # Get all open trades
            open_trades = db.query(TradeDB).filter(
                TradeDB.status == TradeStatus.OPEN,
                TradeDB.auto_close_enabled == True,
            ).all()

            if not open_trades:
                return results

            logger.debug(
                f"Checking {len(open_trades)} open trades for TP/SL",
                action="tp_sl_check_started",
                trade_count=len(open_trades),
            )

            # Fetch prices for all unique symbols
            symbols = list(set([t.symbol for t in open_trades]))
            current_prices = await self._fetch_current_prices(symbols)

            # Check each trade
            for trade in open_trades:
                try:
                    current_price = current_prices.get(trade.symbol)
                    if current_price is None:
                        results["errors"] += 1
                        logger.warning(
                            f"Could not fetch price for {trade.symbol}",
                            action="price_fetch_failed",
                            symbol=trade.symbol,
                            trade_id=trade.id,
                        )
                        continue

                    # Check SL first (priority over TP)
                    if trade.stop_loss and self._check_stop_loss_hit(
                        trade.direction, trade.stop_loss, current_price
                    ):
                        await self._close_trade_for_sl(db, trade, current_price)
                        results["sl_closed"] += 1
                        logger.info(
                            f"Trade {trade.id} closed by STOP_LOSS at {current_price}",
                            action="trade_closed_sl",
                            trade_id=trade.id,
                            symbol=trade.symbol,
                            current_price=current_price,
                        )
                        continue

                    # Check TP levels (TP1, TP2, TP3 in order)
                    tp_triggered = self._check_take_profit_hit(
                        trade.direction,
                        trade.take_profit_1,
                        trade.take_profit_2,
                        trade.take_profit_3,
                        current_price,
                    )

                    if tp_triggered:
                        await self._close_trade_for_tp(
                            db, trade, current_price, tp_triggered
                        )
                        results["tp_closed"] += 1
                        logger.info(
                            f"Trade {trade.id} closed by {tp_triggered} at {current_price}",
                            action="trade_closed_tp",
                            trade_id=trade.id,
                            symbol=trade.symbol,
                            tp_level=tp_triggered,
                            current_price=current_price,
                        )

                except Exception as e:
                    results["errors"] += 1
                    logger.error(
                        f"Error processing trade {trade.id}: {e}",
                        action="trade_processing_error",
                        trade_id=trade.id,
                        exc_info=True,
                    )

            db.commit()
            logger.debug(
                f"TP/SL check complete",
                action="tp_sl_check_complete",
                tp_closed=results["tp_closed"],
                sl_closed=results["sl_closed"],
                errors=results["errors"],
            )

        except Exception as e:
            logger.error(
                f"Fatal error in check_and_close_trades: {e}",
                action="fatal_automation_error",
                exc_info=True,
            )
            db.rollback()
        finally:
            db.close()

        return results

    async def _fetch_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch current prices for multiple symbols from Binance.

        Args:
            symbols: List of symbols to fetch (e.g., ["BTCUSDT", "ETHUSDT"])

        Returns:
            Dictionary mapping symbol to current price
        """
        prices = {}

        for symbol in symbols:
            try:
                # Fetch latest 1-minute candle
                klines = await get_klines(symbol, "1m", limit=1)
                if klines and len(klines) > 0:
                    # klines format: [time, open, high, low, close, volume, ...]
                    # close price is at index 4
                    close_price = float(klines[0][4])
                    prices[symbol] = close_price
                else:
                    logger.warning(
                        f"No kline data returned for {symbol}",
                        action="no_kline_data",
                        symbol=symbol,
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch price for {symbol}: {e}",
                    action="price_fetch_error",
                    symbol=symbol,
                    exc_info=True,
                )

        return prices

    def _check_stop_loss_hit(
        self, direction: str, stop_loss: Optional[float], current_price: float
    ) -> bool:
        """
        Check if current price has hit the stop loss level.

        For LONG: SL is hit when current_price <= stop_loss
        For SHORT: SL is hit when current_price >= stop_loss

        Args:
            direction: Trade direction ("LONG" or "SHORT")
            stop_loss: Stop loss price level (None if not set)
            current_price: Current market price

        Returns:
            True if stop loss is hit, False if no SL set or not hit
        """
        if stop_loss is None:
            return False

        if direction == "LONG":
            # For long, we lose money if price drops below SL
            return current_price <= stop_loss
        else:  # SHORT
            # For short, we lose money if price rises above SL
            return current_price >= stop_loss

    def _check_take_profit_hit(
        self,
        direction: str,
        tp1: Optional[float],
        tp2: Optional[float],
        tp3: Optional[float],
        current_price: float,
    ) -> Optional[str]:
        """
        Check if current price has hit any take profit level.
        Returns the first TP level hit (TP1, TP2, TP3), or None.

        For LONG: TP is hit when current_price >= tp_level
        For SHORT: TP is hit when current_price <= tp_level

        Args:
            direction: Trade direction ("LONG" or "SHORT")
            tp1, tp2, tp3: Take profit price levels
            current_price: Current market price

        Returns:
            "TP1", "TP2", "TP3", or None
        """
        if direction == "LONG":
            # For long, we make money if price rises above TP
            if tp1 and current_price >= tp1:
                return "TP1"
            if tp2 and current_price >= tp2:
                return "TP2"
            if tp3 and current_price >= tp3:
                return "TP3"
        else:  # SHORT
            # For short, we make money if price drops below TP
            if tp1 and current_price <= tp1:
                return "TP1"
            if tp2 and current_price <= tp2:
                return "TP2"
            if tp3 and current_price <= tp3:
                return "TP3"

        return None

    async def _close_trade_for_sl(
        self, db, trade: TradeDB, exit_price: float
    ) -> None:
        """Close a trade due to stop loss being hit."""
        # Calculate P&L
        if trade.direction == "LONG":
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # SHORT
            pnl = (trade.entry_price - exit_price) * trade.quantity

        pnl -= trade.fees  # Subtract fees from P&L
        pnl_pct = (pnl / trade.entry_value) * 100 if trade.entry_value > 0 else 0

        # Update trade
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.utcnow()
        trade.exit_reason = "STOP_LOSS"
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pnl_pct
        trade.status = TradeStatus.CLOSED

        db.add(trade)

    async def _close_trade_for_tp(
        self, db, trade: TradeDB, exit_price: float, tp_level: str
    ) -> None:
        """Close a trade due to take profit being hit."""
        # Calculate P&L
        if trade.direction == "LONG":
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # SHORT
            pnl = (trade.entry_price - exit_price) * trade.quantity

        pnl -= trade.fees  # Subtract fees from P&L
        pnl_pct = (pnl / trade.entry_value) * 100 if trade.entry_value > 0 else 0

        # Update trade
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.utcnow()
        trade.exit_reason = tp_level  # e.g., "TP1", "TP2", "TP3"
        trade.tp_triggered = tp_level
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pnl_pct
        trade.status = TradeStatus.CLOSED

        db.add(trade)


# Global engine instance
_engine: Optional[TPSLAutomationEngine] = None


async def initialize_tp_sl_automation(check_interval_seconds: int = 60):
    """Initialize and start the TP/SL automation engine."""
    global _engine
    _engine = TPSLAutomationEngine(check_interval_seconds)
    # Start in background
    asyncio.create_task(_engine.start())


async def shutdown_tp_sl_automation():
    """Shutdown the TP/SL automation engine."""
    global _engine
    if _engine:
        await _engine.stop()


def get_tp_sl_engine() -> Optional[TPSLAutomationEngine]:
    """Get the global TP/SL automation engine."""
    return _engine
