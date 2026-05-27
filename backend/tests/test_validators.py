"""
Unit tests for input validators.
"""
import pytest
from validators import (
    validate_symbol,
    validate_timeframe,
    validate_limit,
    validate_max_pairs,
)


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_symbol_with_quote(self):
        """Valid symbol with quote currency."""
        assert validate_symbol("BTCUSDT") == "BTCUSDT"
        assert validate_symbol("ETHUSDC") == "ETHUSDC"
        assert validate_symbol("bnbusdt") == "BNBUSDT"  # Case insensitive

    def test_valid_symbol_without_quote(self):
        """Valid base symbol when allow_base=True."""
        assert validate_symbol("BTC", allow_base=True) == "BTC"
        assert validate_symbol("eth", allow_base=True) == "ETH"

    def test_empty_symbol(self):
        """Empty symbol should raise error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_symbol("")

    def test_symbol_too_short(self):
        """Symbol shorter than 3 chars should raise error."""
        with pytest.raises(ValueError, match="length must be 3-20"):
            validate_symbol("AB")

    def test_symbol_too_long(self):
        """Symbol longer than 20 chars should raise error."""
        with pytest.raises(ValueError, match="length must be 3-20"):
            validate_symbol("VERYLONGSYMBOLTHATEXCEEDSMAX")

    def test_symbol_with_special_chars(self):
        """Symbol with special characters should raise error."""
        with pytest.raises(ValueError, match="only letters and numbers"):
            validate_symbol("BTC-USDT")

    def test_symbol_without_quote_when_required(self):
        """Symbol without quote currency should raise error when allow_base=False."""
        with pytest.raises(ValueError, match="must end with a quote currency"):
            validate_symbol("BTC", allow_base=False)

    def test_symbol_with_whitespace(self):
        """Symbol with leading/trailing whitespace should be stripped."""
        assert validate_symbol("  BTCUSDT  ") == "BTCUSDT"

    @pytest.mark.parametrize("invalid_quote", ["USD", "EUR", "GBP"])
    def test_symbol_with_invalid_quote(self, invalid_quote):
        """Symbol with invalid quote currency should raise error."""
        with pytest.raises(ValueError, match="must end with a quote currency"):
            validate_symbol(f"BTC{invalid_quote}")


class TestValidateTimeframe:
    """Tests for timeframe validation."""

    @pytest.mark.parametrize(
        "valid_tf",
        ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"],
    )
    def test_valid_timeframes(self, valid_tf):
        """Valid timeframes should be accepted."""
        assert validate_timeframe(valid_tf) == valid_tf

    def test_timeframe_case_insensitive(self):
        """Timeframe validation should be case insensitive."""
        assert validate_timeframe("1H") == "1h"
        assert validate_timeframe("1D") == "1d"

    def test_timeframe_with_whitespace(self):
        """Timeframe with whitespace should be stripped."""
        assert validate_timeframe("  1h  ") == "1h"

    @pytest.mark.parametrize("invalid_tf", ["2m", "10m", "8h", "2d", "invalid"])
    def test_invalid_timeframes(self, invalid_tf):
        """Invalid timeframes should raise error."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            validate_timeframe(invalid_tf)


class TestValidateLimit:
    """Tests for limit validation."""

    def test_valid_limit(self):
        """Valid limit within range."""
        assert validate_limit(100, min_val=10, max_val=1000) == 100

    def test_limit_at_minimum(self):
        """Limit at minimum boundary."""
        assert validate_limit(10, min_val=10, max_val=1000) == 10

    def test_limit_at_maximum(self):
        """Limit at maximum boundary."""
        assert validate_limit(1000, min_val=10, max_val=1000) == 1000

    def test_limit_below_minimum(self):
        """Limit below minimum should raise error."""
        with pytest.raises(ValueError, match="must be between"):
            validate_limit(5, min_val=10, max_val=1000)

    def test_limit_above_maximum(self):
        """Limit above maximum should raise error."""
        with pytest.raises(ValueError, match="must be between"):
            validate_limit(2000, min_val=10, max_val=1000)

    def test_limit_not_integer(self):
        """Non-integer limit should raise error."""
        with pytest.raises(ValueError, match="must be an integer"):
            validate_limit("100", min_val=10, max_val=1000)

    def test_limit_defaults(self):
        """Default min/max values should work."""
        assert validate_limit(50) == 50  # Default 10-1000


class TestValidateMaxPairs:
    """Tests for max_pairs validation."""

    def test_valid_max_pairs(self):
        """Valid max_pairs value."""
        assert validate_max_pairs(100) == 100

    def test_max_pairs_below_minimum(self):
        """max_pairs below minimum (10) should raise error."""
        with pytest.raises(ValueError, match="must be between 10 and 500"):
            validate_max_pairs(5)

    def test_max_pairs_above_maximum(self):
        """max_pairs above maximum (500) should raise error."""
        with pytest.raises(ValueError, match="must be between 10 and 500"):
            validate_max_pairs(1000)

    def test_max_pairs_boundary_values(self):
        """Boundary values should be accepted."""
        assert validate_max_pairs(10) == 10
        assert validate_max_pairs(500) == 500
