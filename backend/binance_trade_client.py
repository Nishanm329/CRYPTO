"""
Binance authenticated API client for trading operations.
Requires API Key and Secret for Binance account.
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from typing import Optional, Dict, Any
from decimal import Decimal, ROUND_DOWN
from logging_config import get_logger

logger = get_logger(__name__)

# Binance constraints for spot trading
BINANCE_MIN_NOTIONAL = 10  # Minimum order value in USDT
BINANCE_LOT_SIZE_PRECISION = 8  # Max decimal places for order quantity


class BinanceTradeClient:
    """Authenticated Binance API client for spot trading."""

    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize Binance API client with authentication credentials.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        self.client = Client(api_key, api_secret, tld='com')
        self.api_key = api_key
        self.api_secret = api_secret
        logger.info("BinanceTradeClient initialized", action="binance_client_init")

    async def validate_credentials(self) -> bool:
        """
        Test API credentials by fetching account info.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            self.client.get_account()
            logger.info("Binance credentials validated", action="credentials_validated")
            return True
        except BinanceAPIException as e:
            logger.error(
                "Binance credential validation failed",
                action="credentials_invalid",
                error_code=e.status_code,
                error_message=str(e),
            )
            return False

    async def get_wallet_balance(self) -> float:
        """
        Get total USDT balance in trading wallet.

        Returns:
            Balance in USDT as float

        Raises:
            BinanceAPIException: If API call fails
        """
        try:
            account = self.client.get_account()

            # Find USDT balance
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = float(balance['free'])
                    logger.info(
                        "Wallet balance retrieved",
                        action="wallet_balance_fetched",
                        usdt_balance=usdt_balance,
                    )
                    return usdt_balance

            # No USDT balance found
            logger.warning("No USDT balance found in account", action="no_usdt_balance")
            return 0.0

        except BinanceAPIException as e:
            logger.error(
                "Failed to get wallet balance",
                action="wallet_balance_failed",
                error_code=e.status_code,
                error_message=str(e),
            )
            raise

    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """
        Get all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter by (e.g., "BTCUSDT")

        Returns:
            List of open order dicts

        Raises:
            BinanceAPIException: If API call fails
        """
        try:
            if symbol:
                orders = self.client.get_open_orders(symbol=symbol)
                logger.info(
                    f"Open orders retrieved for {symbol}",
                    action="open_orders_fetched",
                    symbol=symbol,
                    count=len(orders),
                )
            else:
                orders = self.client.get_open_orders()
                logger.info(
                    "All open orders retrieved",
                    action="all_open_orders_fetched",
                    count=len(orders),
                )
            return orders

        except BinanceAPIException as e:
            logger.error(
                "Failed to get open orders",
                action="open_orders_failed",
                symbol=symbol,
                error_code=e.status_code,
                error_message=str(e),
            )
            raise

    async def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")

        Returns:
            Current price as float

        Raises:
            BinanceAPIException: If API call fails
        """
        try:
            ticker = self.client.get_symbol_info(symbol)
            price_data = self.client.get_recent_trades(symbol=symbol, limit=1)
            if price_data:
                price = float(price_data[0]['price'])
                logger.debug(
                    "Current price retrieved",
                    action="current_price_fetched",
                    symbol=symbol,
                    price=price,
                )
                return price

            # Fallback: use last trade price from ticker
            return float(ticker['lastPrice']) if ticker else 0.0

        except BinanceAPIException as e:
            logger.error(
                "Failed to get current price",
                action="current_price_failed",
                symbol=symbol,
                error_code=e.status_code,
                error_message=str(e),
            )
            raise

    def _validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        """
        Validate order parameters before placing.

        Args:
            symbol: Trading symbol
            side: "BUY" or "SELL"
            quantity: Order quantity
            price: Current price (for calculation)

        Returns:
            Dict with validation result and error message if invalid

        Raises:
            ValueError: If validation fails
        """
        # Validate side
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")

        # Validate quantity is positive
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")

        # Validate order value meets minimum notional
        order_value = quantity * price
        if order_value < BINANCE_MIN_NOTIONAL:
            raise ValueError(
                f"Order value ${order_value:.2f} is below minimum ${BINANCE_MIN_NOTIONAL}. "
                f"Increase quantity or symbol price."
            )

        # Round quantity to appropriate precision
        quantity_rounded = self._round_to_precision(quantity, BINANCE_LOT_SIZE_PRECISION)

        logger.info(
            "Order validation passed",
            action="order_validated",
            symbol=symbol,
            side=side,
            quantity=quantity_rounded,
            order_value=order_value,
        )

        return {
            "valid": True,
            "quantity": quantity_rounded,
            "order_value": order_value,
        }

    def _round_to_precision(self, value: float, decimals: int) -> float:
        """
        Round value to specified decimal precision.
        Uses ROUND_DOWN to be conservative with quantities.

        Args:
            value: Value to round
            decimals: Number of decimal places

        Returns:
            Rounded value
        """
        d = Decimal(str(value))
        return float(d.quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN))

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> Dict[str, Any]:
        """
        Place a market order to buy or sell immediately.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Amount to trade

        Returns:
            Order response from Binance

        Raises:
            ValueError: If validation fails
            BinanceOrderException: If order placement fails
        """
        try:
            # Get current price for validation
            current_price = await self.get_current_price(symbol)

            # Validate order
            validation = self._validate_order(symbol, side, quantity, current_price)
            quantity = validation["quantity"]

            # Place market order
            order = self.client.order_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
            )

            logger.info(
                f"Market order placed: {side} {quantity} {symbol}",
                action="market_order_placed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_id=order.get('orderId'),
                status=order.get('status'),
            )

            return order

        except (BinanceAPIException, BinanceOrderException) as e:
            logger.error(
                "Failed to place market order",
                action="market_order_failed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                error_code=getattr(e, 'status_code', None),
                error_message=str(e),
            )
            raise
        except ValueError as e:
            logger.warning(
                "Market order validation failed",
                action="market_order_validation_failed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                error=str(e),
            )
            raise

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        """
        Place a limit order at a specified price.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Amount to trade
            price: Limit price

        Returns:
            Order response from Binance

        Raises:
            ValueError: If validation fails
            BinanceOrderException: If order placement fails
        """
        try:
            # Validate order
            validation = self._validate_order(symbol, side, quantity, price)
            quantity = validation["quantity"]

            # Place limit order
            order = self.client.order_limit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
            )

            logger.info(
                f"Limit order placed: {side} {quantity} {symbol} @ ${price}",
                action="limit_order_placed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_id=order.get('orderId'),
            )

            return order

        except (BinanceAPIException, BinanceOrderException) as e:
            logger.error(
                "Failed to place limit order",
                action="limit_order_failed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                error_message=str(e),
            )
            raise

    async def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an existing order.

        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel

        Returns:
            Cancelled order response

        Raises:
            BinanceAPIException: If cancellation fails
        """
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)

            logger.info(
                f"Order cancelled: {order_id} for {symbol}",
                action="order_cancelled",
                symbol=symbol,
                order_id=order_id,
                status=result.get('status'),
            )

            return result

        except BinanceAPIException as e:
            logger.error(
                "Failed to cancel order",
                action="order_cancel_failed",
                symbol=symbol,
                order_id=order_id,
                error_code=e.status_code,
                error_message=str(e),
            )
            raise

    async def get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Get status of a specific order.

        Args:
            symbol: Trading symbol
            order_id: Order ID

        Returns:
            Order details

        Raises:
            BinanceAPIException: If query fails
        """
        try:
            order = self.client.get_order(symbol=symbol, orderId=order_id)

            logger.debug(
                "Order status retrieved",
                action="order_status_fetched",
                symbol=symbol,
                order_id=order_id,
                status=order.get('status'),
            )

            return order

        except BinanceAPIException as e:
            logger.error(
                "Failed to get order status",
                action="order_status_failed",
                symbol=symbol,
                order_id=order_id,
                error_code=e.status_code,
                error_message=str(e),
            )
            raise

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get trading rules and constraints for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Symbol info dict or None if not found
        """
        try:
            info = self.client.get_symbol_info(symbol)
            return info
        except BinanceAPIException:
            logger.warning(
                f"Symbol info not found: {symbol}",
                action="symbol_info_not_found",
                symbol=symbol,
            )
            return None
