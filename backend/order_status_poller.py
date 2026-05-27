"""
Order Status Polling Engine

Monitors LIVE trades and verifies order fills with Binance.
Handles partial fills, rejections, and cancellations.
Runs as a background job that checks order status periodically.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from enum import Enum
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository
from binance_trade_client import BinanceTradeClient
from crypto_utils import APIKeyVault

logger = get_logger(__name__)


class OrderStatusEnum(str, Enum):
    """Binance order statuses."""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderStatusPoller:
    """Monitors LIVE orders and verifies fills with Binance."""

    def __init__(self, check_interval_seconds: int = 30, max_age_minutes: int = 60):
        """
        Initialize the order status poller.

        Args:
            check_interval_seconds: How often to check order status (default 30s)
            max_age_minutes: Only check orders created within this time (default 60m)
        """
        self.check_interval = check_interval_seconds
        self.max_age_minutes = max_age_minutes
        self.running = False

    async def start(self):
        """Start the polling loop."""
        self.running = True
        logger.info(
            "Order Status Poller started",
            action="poller_started",
            check_interval_seconds=self.check_interval,
            max_age_minutes=self.max_age_minutes,
        )
        while self.running:
            try:
                await self.check_order_status()
            except Exception as e:
                logger.error(
                    f"Error in order status polling loop: {e}",
                    action="poller_error",
                    exc_info=True,
                )
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Stop the polling loop."""
        self.running = False
        logger.info("Order Status Poller stopped", action="poller_stopped")

    async def check_order_status(self) -> Dict[str, int]:
        """
        Check status of all open LIVE orders with Binance.

        Returns:
            Dictionary with counts: {"verified": N, "partial_fills": N, "failed": N, "errors": N}
        """
        db = SessionLocal()
        results = {"verified": 0, "partial_fills": 0, "failed": 0, "errors": 0}

        try:
            # Get all open trades created within max_age_minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.max_age_minutes)
            open_trades = db.query(TradeDB).filter(
                TradeDB.status == TradeStatus.OPEN.value,
                TradeDB.created_at >= cutoff_time,
            ).all()

            if not open_trades:
                return results

            logger.debug(
                f"Checking status of {len(open_trades)} orders",
                action="order_status_check_started",
                trade_count=len(open_trades),
            )

            # Group trades by user_id (to reuse trade clients)
            trades_by_user = {}
            for trade in open_trades:
                if trade.user_id not in trades_by_user:
                    trades_by_user[trade.user_id] = []
                trades_by_user[trade.user_id].append(trade)

            # Check each user's orders
            for user_id, user_trades in trades_by_user.items():
                try:
                    # Get user's credentials
                    decrypted_creds = APIKeyVault.retrieve_credentials(db, user_id)
                    if not decrypted_creds:
                        logger.warning(
                            f"Could not retrieve credentials for user {user_id}",
                            action="credentials_not_found",
                            user_id=user_id,
                        )
                        results["errors"] += len(user_trades)
                        continue

                    # Create trade client
                    trade_client = BinanceTradeClient(
                        decrypted_creds["api_key"],
                        decrypted_creds["api_secret"],
                    )

                    # Check each trade
                    for trade in user_trades:
                        try:
                            order_status = await self._fetch_order_status(
                                trade_client, trade.symbol, trade.order_id
                            )

                            if order_status is None:
                                results["errors"] += 1
                                logger.warning(
                                    f"Could not fetch order status",
                                    action="order_status_fetch_failed",
                                    trade_id=trade.id,
                                    symbol=trade.symbol,
                                    order_id=trade.order_id,
                                )
                                continue

                            # Process order status
                            await self._process_order_status(
                                db, trade, order_status, results
                            )

                        except Exception as e:
                            results["errors"] += 1
                            logger.error(
                                f"Error checking order {trade.order_id}: {e}",
                                action="order_check_error",
                                trade_id=trade.id,
                                order_id=trade.order_id,
                                exc_info=True,
                            )

                except Exception as e:
                    results["errors"] += len(user_trades)
                    logger.error(
                        f"Error processing trades for user {user_id}: {e}",
                        action="user_trades_error",
                        user_id=user_id,
                        exc_info=True,
                    )

            db.commit()
            logger.debug(
                f"Order status check complete",
                action="order_status_check_complete",
                verified=results["verified"],
                partial_fills=results["partial_fills"],
                failed=results["failed"],
                errors=results["errors"],
            )

        except Exception as e:
            logger.error(
                f"Fatal error in check_order_status: {e}",
                action="fatal_poller_error",
                exc_info=True,
            )
            db.rollback()
        finally:
            db.close()

        return results

    async def _fetch_order_status(
        self, trade_client: BinanceTradeClient, symbol: str, order_id: str
    ) -> Optional[Dict]:
        """
        Fetch order status from Binance.

        Args:
            trade_client: Authenticated Binance trade client
            symbol: Trading pair (e.g., "BTCUSDT")
            order_id: Order ID to check

        Returns:
            Order status dict or None if fetch fails
        """
        try:
            order_info = await trade_client.get_order_status(symbol, int(order_id))
            return order_info
        except Exception as e:
            logger.warning(
                f"Failed to fetch order status from Binance: {e}",
                action="binance_order_fetch_error",
                symbol=symbol,
                order_id=order_id,
                exc_info=True,
            )
            return None

    async def _process_order_status(
        self, db, trade: TradeDB, order_info: Dict, results: Dict
    ) -> None:
        """
        Process order status and update trade if needed.

        Args:
            db: Database session
            trade: Trade object from DB
            order_info: Order info from Binance
            results: Results counter dict
        """
        status = order_info.get("status", "UNKNOWN")
        filled_qty = float(order_info.get("executedQty", 0))
        avg_price = float(order_info.get("cummulativeQuoteAssetTransactedQuantity", 0))

        if filled_qty > 0:
            avg_price = avg_price / filled_qty if filled_qty > 0 else trade.entry_price
        else:
            avg_price = trade.entry_price

        logger.debug(
            f"Order {trade.order_id} status: {status}",
            action="order_status_retrieved",
            trade_id=trade.id,
            order_id=trade.order_id,
            status=status,
            filled_qty=filled_qty,
            avg_price=avg_price,
        )

        # Handle FILLED orders
        if status == OrderStatusEnum.FILLED.value:
            # Verify fill quantity matches our expectation
            if filled_qty >= trade.quantity * 0.99:  # Allow 1% tolerance
                results["verified"] += 1
                logger.info(
                    f"Order {trade.order_id} confirmed FILLED",
                    action="order_verified_filled",
                    trade_id=trade.id,
                    order_id=trade.order_id,
                    filled_qty=filled_qty,
                )
                # Trade is already in OPEN status, no action needed
            else:
                # Partial fill with less than expected
                results["partial_fills"] += 1
                await self._handle_partial_fill(db, trade, filled_qty, avg_price)

        # Handle PARTIALLY_FILLED orders
        elif status == OrderStatusEnum.PARTIALLY_FILLED.value:
            results["partial_fills"] += 1
            logger.warning(
                f"Order {trade.order_id} is PARTIALLY_FILLED",
                action="order_partial_fill",
                trade_id=trade.id,
                order_id=trade.order_id,
                filled_qty=filled_qty,
                total_qty=trade.quantity,
                filled_pct=(filled_qty / trade.quantity * 100) if trade.quantity > 0 else 0,
            )
            await self._handle_partial_fill(db, trade, filled_qty, avg_price)

        # Handle CANCELED orders
        elif status == OrderStatusEnum.CANCELED.value:
            results["failed"] += 1
            logger.warning(
                f"Order {trade.order_id} was CANCELED",
                action="order_canceled",
                trade_id=trade.id,
                order_id=trade.order_id,
                filled_qty=filled_qty,
            )
            await self._handle_order_failure(
                db, trade, "ORDER_CANCELED", filled_qty, avg_price
            )

        # Handle REJECTED orders
        elif status == OrderStatusEnum.REJECTED.value:
            results["failed"] += 1
            logger.error(
                f"Order {trade.order_id} was REJECTED by Binance",
                action="order_rejected",
                trade_id=trade.id,
                order_id=trade.order_id,
            )
            await self._handle_order_failure(
                db, trade, "ORDER_REJECTED", 0, trade.entry_price
            )

        # Handle EXPIRED orders
        elif status == OrderStatusEnum.EXPIRED.value:
            results["failed"] += 1
            logger.warning(
                f"Order {trade.order_id} EXPIRED",
                action="order_expired",
                trade_id=trade.id,
                order_id=trade.order_id,
            )
            await self._handle_order_failure(
                db, trade, "ORDER_EXPIRED", filled_qty, avg_price
            )

        # Pending or other statuses: still waiting
        else:
            logger.debug(
                f"Order {trade.order_id} status: {status} (still pending)",
                action="order_pending",
                trade_id=trade.id,
                status=status,
            )

    async def _handle_partial_fill(
        self,
        db,
        trade: TradeDB,
        filled_qty: float,
        avg_fill_price: float,
    ) -> None:
        """
        Handle partial fill: update trade quantity to actual fill.

        Args:
            db: Database session
            trade: Trade object
            filled_qty: Actual filled quantity
            avg_fill_price: Average fill price from Binance
        """
        # Update trade with actual filled quantity
        original_qty = trade.quantity
        original_value = trade.entry_value

        trade.quantity = filled_qty
        trade.entry_price = avg_fill_price
        trade.entry_value = filled_qty * avg_fill_price
        trade.status = TradeStatus.CLOSING.value  # Mark as partial

        logger.info(
            f"Trade {trade.id} updated for partial fill",
            action="trade_partial_fill_updated",
            trade_id=trade.id,
            original_qty=original_qty,
            filled_qty=filled_qty,
            original_value=original_value,
            new_value=trade.entry_value,
            avg_price=avg_fill_price,
        )

        db.add(trade)

    async def _handle_order_failure(
        self,
        db,
        trade: TradeDB,
        failure_reason: str,
        filled_qty: float,
        fill_price: float,
    ) -> None:
        """
        Handle failed orders (rejected, expired, canceled).

        Args:
            db: Database session
            trade: Trade object
            failure_reason: Reason for failure
            filled_qty: Any quantity that was filled before failure
            fill_price: Price at which any fill occurred
        """
        if filled_qty > 0:
            # Partial fill before cancellation
            trade.quantity = filled_qty
            trade.entry_price = fill_price
            trade.entry_value = filled_qty * fill_price
            trade.status = TradeStatus.CLOSING.value
            logger.warning(
                f"Trade {trade.id} closed with partial fill due to {failure_reason}",
                action="trade_partial_failure",
                trade_id=trade.id,
                failure_reason=failure_reason,
                filled_qty=filled_qty,
                fill_price=fill_price,
            )
        else:
            # No fill at all: cancel the trade
            trade.status = TradeStatus.CANCELLED.value
            logger.error(
                f"Trade {trade.id} CANCELLED due to {failure_reason}",
                action="trade_cancelled",
                trade_id=trade.id,
                failure_reason=failure_reason,
            )

        trade.exit_timestamp = datetime.utcnow()
        trade.exit_reason = failure_reason

        db.add(trade)


# Global poller instance
_poller: Optional[OrderStatusPoller] = None


async def initialize_order_status_poller(
    check_interval_seconds: int = 30, max_age_minutes: int = 60
):
    """Initialize and start the order status poller."""
    global _poller
    _poller = OrderStatusPoller(check_interval_seconds, max_age_minutes)
    # Start in background
    asyncio.create_task(_poller.start())


async def shutdown_order_status_poller():
    """Shutdown the order status poller."""
    global _poller
    if _poller:
        await _poller.stop()


def get_order_status_poller() -> Optional[OrderStatusPoller]:
    """Get the global order status poller."""
    return _poller
