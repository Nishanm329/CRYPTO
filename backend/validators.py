"""
Input validation and sanitization for API endpoints.
"""
import re
from typing import Optional


def validate_symbol(symbol: str, allow_base: bool = False) -> str:
    """
    Validate and sanitize trading symbol.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        allow_base: If True, allow base symbol (e.g., 'BTC'). If False, require pair (e.g., 'BTCUSDT')

    Returns:
        Validated and normalized symbol (uppercase)

    Raises:
        ValueError: If symbol is invalid
    """
    if not symbol:
        raise ValueError("Symbol cannot be empty")

    # Normalize to uppercase
    symbol = symbol.strip().upper()

    # Check length
    if len(symbol) < 3 or len(symbol) > 20:
        raise ValueError(f"Symbol length must be 3-20 characters, got {len(symbol)}")

    # Only allow alphanumeric characters
    if not re.match(r"^[A-Z0-9]+$", symbol):
        raise ValueError(f"Symbol must contain only letters and numbers, got: {symbol}")

    # If requiring pair format, ensure it ends with USDT or other common quotes
    if not allow_base:
        valid_quotes = ["USDT", "USDC", "BUSD", "TUSD", "DAI"]
        if not any(symbol.endswith(q) for q in valid_quotes):
            raise ValueError(f"Symbol must end with a quote currency ({', '.join(valid_quotes)})")

    return symbol


def validate_timeframe(timeframe: str) -> str:
    """
    Validate timeframe parameter.

    Args:
        timeframe: Timeframe string (e.g., '1h', '5m', '1d')

    Returns:
        Validated timeframe

    Raises:
        ValueError: If timeframe is invalid
    """
    valid_timeframes = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"}

    timeframe = timeframe.strip().lower()

    if timeframe not in valid_timeframes:
        raise ValueError(f"Invalid timeframe '{timeframe}'. Must be one of: {', '.join(sorted(valid_timeframes))}")

    return timeframe


def validate_limit(limit: int, min_val: int = 10, max_val: int = 1000) -> int:
    """
    Validate numeric limit parameter.

    Args:
        limit: Limit value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated limit

    Raises:
        ValueError: If limit is invalid
    """
    if not isinstance(limit, int):
        raise ValueError(f"Limit must be an integer, got {type(limit).__name__}")

    if limit < min_val or limit > max_val:
        raise ValueError(f"Limit must be between {min_val} and {max_val}, got {limit}")

    return limit


def validate_max_pairs(max_pairs: int) -> int:
    """Validate max_pairs parameter for scan endpoint."""
    return validate_limit(max_pairs, min_val=10, max_val=500)
