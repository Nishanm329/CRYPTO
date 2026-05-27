"""
Real-time Binance Order Webhook Handler

Maintains WebSocket connection to Binance for real-time order updates.
Eliminates need for polling by receiving push notifications from Binance.
Updates trade status immediately when orders are filled or rejected.

Connection Flow:
1. Establish authenticated WebSocket stream (requires API key)
2. Listen for allAccountData events from Binance
3. Parse order execution events (ExecutionReport)
4. Update trade status and quantity in database
5. Reconnect automatically on connection failure
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from binance.streams import BinanceSocketManager
from binance.client import Client
from binance.exceptions import BinanceAPIException
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository

logger = get_logger(__name__)


class BinanceOrderStatus(str, Enum):
    """Binance order statuses."""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderUpdateProcessor:
    """Processes and validates Binance order update events."""

    @staticmethod
    def parse_execution_report(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse ExecutionReport event from Binance allAccountData stream.

        ExecutionReport structure:
        {
            "e": "executionReport",
            "E": 1565245913483,
            "s": "BTCUSDT",
            "c": 1234567,      # clientOrderId
            "S": "BUY",         # side
            "o": "LIMIT",       # orderType
            "f": "GTC",         # timeInForce
            "q": "1.00000000",  # orderQty
            "p": "0.10264410",  # orderPrice
            "P": "0.00000000",  # stopPrice
            "F": "0.00000000",  # icebergQty
            "g": -1,            # orderListId
            "C": "",            # origClientOrderId
            "x": "TRADE",       # executionType
            "X": "FILLED",      # orderStatus
            "r": "NONE",        # orderRejectReason
            "i": 4293153618,    # orderId
            "l": "1.00000000",  # lastExecutedQuantity
            "z": "1.00000000",  # cumulativeFilledQuantity
            "L": "10264.41",    # lastExecutedPrice
            "n": "20.53288200", # commissionAmount
            "N": "BNB",         # commissionAsset
            "T": 1565245913000, # transactionTime
            "t": 28457,         # tradeId
            "I": 8641984,       # ignoreMe
            "w": true,          # isWorking
            "m": false,         # maker
            "O": 1565245913483, # orderCreationTime
            "Z": "10264.41000000", # cumulativeQuoteAssetTransactedQuantity
            "Y": "10264.41000000", # quoteOrderQty
            "Q": "0.00000000"   # quoteOrderQtyFilled
        }

        Args:
            event: Raw event dict from Binance stream

        Returns:
            Parsed execution report or None if not an executionReport event
        """
        if event.get("e") != "executionReport":
            return None

        try:
            return {
                "symbol": event.get("s"),
                "order_id": event.get("i"),
                "client_order_id": event.get("c"),
                "side": event.get("S"),  # BUY or SELL
                "order_type": event.get("o"),
                "order_status": event.get("X"),  # FILLED, PARTIALLY_FILLED, etc.
                "execution_type": event.get("x"),  # TRADE, CANCELED, etc.
                "order_quantity": float(event.get("q", 0)),
                "order_price": float(event.get("p", 0)),
                "executed_quantity": float(event.get("l", 0)),  # Last executed qty
                "cumulative_quantity": float(event.get("z", 0)),  # Total filled
                "cumulative_quote": float(event.get("Z", 0)),  # Total paid/received
                "executed_price": float(event.get("L", 0)) if event.get("L") else None,  # Last price
                "commission": float(event.get("n", 0)),
                "commission_asset": event.get("N"),
                "transaction_time": int(event.get("T", 0)),
                "trade_id": event.get("t"),
                "is_maker": event.get("m", False),
                "is_working": event.get("w", False),
                "reject_reason": event.get("r"),
                "order_creation_time": int(event.get("O", 0)),
            }
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "Failed to parse execution report",
                action="parse_execution_failed",
                error=str(e),
                event=event,
            )
            return None

    @staticmethod
    def calculate_average_price(
        cumulative_quantity: float,
        cumulative_quote: float,
    ) -> float:
        """
        Calculate average execution price.

        Args:
            cumulative_quantity: Total quantity filled
            cumulative_quote: Total quote asset spent/received

        Returns:
            Average price or 0.0 if no fills
        """
        if cumulative_quantity <= 0:
            return 0.0
        return cumulative_quote / cumulative_quantity


class BinanceOrderWebSocketHandler:
    """Maintains and manages Binance WebSocket connection for order updates."""

    def __init__(self, api_key: str, api_secret: str, user_id: str):
        """
        Initialize WebSocket handler.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            user_id: User ID for multi-user support
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.client = Client(api_key, api_secret, tld='com')
        self.socket_manager: Optional[BinanceSocketManager] = None
        self.socket_conn = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1  # seconds, exponential backoff
        self.update_callbacks: List[Callable] = []

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Binance.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.socket_manager = BinanceSocketManager(self.client)
            # Use user stream for authenticated account updates
            self.socket_conn = self.socket_manager.user_socket()

            logger.info(
                f"Binance WebSocket connecting for {self.user_id}",
                action="websocket_connecting",
                user_id=self.user_id,
            )

            # Start listening to socket
            self.socket_manager.start()
            self.is_connected = True
            self.reconnect_attempts = 0

            logger.info(
                f"Binance WebSocket connected for {self.user_id}",
                action="websocket_connected",
                user_id=self.user_id,
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to connect WebSocket for {self.user_id}",
                action="websocket_connection_failed",
                user_id=self.user_id,
                error=str(e),
            )
            self.is_connected = False
            return False

    async def disconnect(self):
        """Gracefully close WebSocket connection."""
        try:
            if self.socket_manager:
                self.socket_manager.close()
                self.socket_conn = None
                self.socket_manager = None
                self.is_connected = False

                logger.info(
                    f"Binance WebSocket disconnected for {self.user_id}",
                    action="websocket_disconnected",
                    user_id=self.user_id,
                )
        except Exception as e:
            logger.error(
                f"Error disconnecting WebSocket for {self.user_id}",
                action="websocket_disconnect_error",
                user_id=self.user_id,
                error=str(e),
            )

    def add_update_callback(self, callback: Callable):
        """
        Register callback to be called when order updates received.

        Args:
            callback: Async function(parsed_order_update) to call on new orders
        """
        self.update_callbacks.append(callback)

    async def start_listening(self):
        """
        Start listening to WebSocket events.
        Blocks until connection closes or error occurs.
        """
        if not self.is_connected:
            if not await self.connect():
                return

        try:
            async with self.socket_conn as socket:
                while self.is_connected:
                    try:
                        msg = await socket.recv()
                        if msg:
                            await self._handle_message(msg)
                    except asyncio.CancelledError:
                        logger.info(
                            "WebSocket listening cancelled",
                            action="websocket_listening_cancelled",
                            user_id=self.user_id,
                        )
                        break
                    except Exception as e:
                        logger.error(
                            "Error receiving WebSocket message",
                            action="websocket_recv_error",
                            user_id=self.user_id,
                            error=str(e),
                        )
                        await self._handle_reconnection()

        except Exception as e:
            logger.error(
                "WebSocket listening error",
                action="websocket_listening_error",
                user_id=self.user_id,
                error=str(e),
            )
            await self._handle_reconnection()

    async def _handle_message(self, msg: str):
        """
        Process incoming WebSocket message.

        Args:
            msg: Raw message from WebSocket
        """
        try:
            event = json.loads(msg)

            # Parse execution report
            report = OrderUpdateProcessor.parse_execution_report(event)
            if not report:
                return  # Not an order update event

            logger.debug(
                f"Order update received: {report['symbol']} {report['order_status']}",
                action="order_update_received",
                user_id=self.user_id,
                symbol=report['symbol'],
                order_id=report['order_id'],
                status=report['order_status'],
            )

            # Call registered callbacks
            for callback in self.update_callbacks:
                try:
                    await callback(report)
                except Exception as e:
                    logger.error(
                        "Error in update callback",
                        action="callback_error",
                        user_id=self.user_id,
                        error=str(e),
                    )

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse WebSocket message",
                action="websocket_parse_error",
                user_id=self.user_id,
                error=str(e),
            )

    async def _handle_reconnection(self):
        """Handle reconnection with exponential backoff."""
        await self.disconnect()

        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 60)

            logger.warning(
                f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})",
                action="websocket_reconnecting",
                user_id=self.user_id,
                reconnect_attempt=self.reconnect_attempts,
                delay_seconds=delay,
            )

            await asyncio.sleep(delay)
            await self.start_listening()
        else:
            logger.error(
                f"Max reconnection attempts reached for {self.user_id}",
                action="websocket_max_reconnect_reached",
                user_id=self.user_id,
                max_attempts=self.max_reconnect_attempts,
            )


class OrderUpdateHandler:
    """Handles database updates for order executions."""

    @staticmethod
    async def handle_order_update(
        db: SessionLocal,
        user_id: str,
        order_update: Dict[str, Any],
    ):
        """
        Update trade in database based on order execution report.

        Args:
            db: Database session
            user_id: User ID
            order_update: Parsed execution report from Binance
        """
        try:
            # Find trade by order_id and symbol
            trade = db.query(TradeDB).filter(
                TradeDB.user_id == user_id,
                TradeDB.order_id == str(order_update["order_id"]),
                TradeDB.symbol == order_update["symbol"],
            ).first()

            if not trade:
                logger.warning(
                    f"Trade not found for order {order_update['order_id']}",
                    action="trade_not_found",
                    user_id=user_id,
                    order_id=order_update["order_id"],
                )
                return

            # Update quantity with actual filled amount
            if order_update["cumulative_quantity"] > 0:
                trade.quantity = order_update["cumulative_quantity"]

            # Update entry price with average execution price
            if order_update["cumulative_quote"] > 0:
                avg_price = OrderUpdateProcessor.calculate_average_price(
                    order_update["cumulative_quantity"],
                    order_update["cumulative_quote"],
                )
                trade.entry_price = avg_price

            # Handle different order statuses
            status = order_update["order_status"]

            if status == BinanceOrderStatus.FILLED.value:
                trade.status = TradeStatus.OPEN.value
                trade.updated_at = datetime.utcnow()

                logger.info(
                    f"Order {order_update['order_id']} FILLED",
                    action="order_filled",
                    user_id=user_id,
                    symbol=trade.symbol,
                    order_id=order_update["order_id"],
                    quantity=trade.quantity,
                    entry_price=trade.entry_price,
                )

            elif status == BinanceOrderStatus.PARTIALLY_FILLED.value:
                trade.status = TradeStatus.OPEN.value
                trade.updated_at = datetime.utcnow()

                logger.info(
                    f"Order {order_update['order_id']} PARTIALLY FILLED",
                    action="order_partially_filled",
                    user_id=user_id,
                    symbol=trade.symbol,
                    order_id=order_update["order_id"],
                    filled_quantity=order_update["cumulative_quantity"],
                    total_quantity=order_update["order_quantity"],
                )

            elif status in [
                BinanceOrderStatus.CANCELED.value,
                BinanceOrderStatus.REJECTED.value,
                BinanceOrderStatus.EXPIRED.value,
            ]:
                trade.status = TradeStatus.CANCELLED.value
                trade.updated_at = datetime.utcnow()

                logger.warning(
                    f"Order {order_update['order_id']} {status}",
                    action="order_cancelled",
                    user_id=user_id,
                    symbol=trade.symbol,
                    order_id=order_update["order_id"],
                    status=status,
                    reject_reason=order_update.get("reject_reason"),
                )

            db.add(trade)
            db.commit()
            db.refresh(trade)

            logger.info(
                f"Trade {trade.id} updated from order webhook",
                action="trade_updated_webhook",
                user_id=user_id,
                trade_id=trade.id,
                symbol=trade.symbol,
                status=trade.status,
            )

        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to update trade from order webhook",
                action="webhook_update_failed",
                user_id=user_id,
                order_id=order_update.get("order_id"),
                error=str(e),
            )
            raise


class WebSocketManager:
    """Manages WebSocket connections for multiple users."""

    def __init__(self):
        """Initialize WebSocket manager."""
        self.connections: Dict[str, BinanceOrderWebSocketHandler] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    async def start_connection(
        self,
        user_id: str,
        api_key: str,
        api_secret: str,
        db: SessionLocal,
    ) -> bool:
        """
        Start WebSocket connection for a user.

        Args:
            user_id: User ID
            api_key: Binance API key
            api_secret: Binance API secret
            db: Database session

        Returns:
            True if connection started successfully
        """
        try:
            if user_id in self.connections:
                logger.warning(
                    f"WebSocket connection already exists for {user_id}",
                    action="connection_already_exists",
                    user_id=user_id,
                )
                return True

            # Create handler
            handler = BinanceOrderWebSocketHandler(api_key, api_secret, user_id)

            # Register update callback
            async def on_order_update(report):
                await OrderUpdateHandler.handle_order_update(db, user_id, report)

            handler.add_update_callback(on_order_update)

            # Store connection
            self.connections[user_id] = handler

            # Start listening in background task
            task = asyncio.create_task(handler.start_listening())
            self.tasks[user_id] = task

            logger.info(
                f"WebSocket connection started for {user_id}",
                action="websocket_started",
                user_id=user_id,
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to start WebSocket for {user_id}",
                action="websocket_start_failed",
                user_id=user_id,
                error=str(e),
            )
            return False

    async def stop_connection(self, user_id: str):
        """
        Stop WebSocket connection for a user.

        Args:
            user_id: User ID
        """
        try:
            if user_id not in self.connections:
                return

            handler = self.connections[user_id]
            await handler.disconnect()

            # Cancel listening task
            if user_id in self.tasks:
                self.tasks[user_id].cancel()
                try:
                    await self.tasks[user_id]
                except asyncio.CancelledError:
                    pass

            del self.connections[user_id]
            del self.tasks[user_id]

            logger.info(
                f"WebSocket connection stopped for {user_id}",
                action="websocket_stopped",
                user_id=user_id,
            )

        except Exception as e:
            logger.error(
                f"Error stopping WebSocket for {user_id}",
                action="websocket_stop_error",
                user_id=user_id,
                error=str(e),
            )

    async def stop_all(self):
        """Stop all WebSocket connections."""
        user_ids = list(self.connections.keys())
        for user_id in user_ids:
            await self.stop_connection(user_id)

        logger.info(
            "All WebSocket connections stopped",
            action="all_websockets_stopped",
            connection_count=len(user_ids),
        )

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get status of all WebSocket connections.

        Returns:
            Dict with connection statuses
        """
        return {
            user_id: {
                "connected": handler.is_connected,
                "reconnect_attempts": handler.reconnect_attempts,
            }
            for user_id, handler in self.connections.items()
        }
