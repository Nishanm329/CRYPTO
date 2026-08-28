"""
Characterization tests for EMA 7/25 cross detection and pre-cross convergence.

These lock in the behaviour of the core signal primitives — everything else in
the scanner keys off them, and the index arithmetic (candles_since, the
spread.iloc[-4] narrowing check) is exactly the kind of thing that breaks
silently under refactoring.

Frames are built with explicit ema7/ema25 columns rather than engineered price
series, so each test states the crossing geometry directly.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import (  # noqa: E402
    add_all_indicators,
    add_ema_columns,
    add_rsi_columns,
    detect_ema_cross,
    detect_ema_precross,
)


def frame(ema7, ema25):
    """Build a frame with the given EMA paths plus a derived ema_spread."""
    ema7 = np.asarray(ema7, dtype=float)
    ema25 = np.asarray(ema25, dtype=float)
    df = pd.DataFrame({
        "close": ema7,
        "ema7": ema7,
        "ema25": ema25,
    })
    df["ema_spread"] = (df["ema7"] - df["ema25"]) / df["ema25"] * 100
    return df


# ── detect_ema_cross ────────────────────────────────────────────────────────

class TestDetectEmaCross:
    def test_bullish_cross_on_latest_candle(self):
        # ema7 climbs through a flat ema25 on the final bar.
        df = frame([90, 92, 94, 96, 101], [100] * 5)
        assert detect_ema_cross(df) == ("LONG", 0)

    def test_bearish_cross_on_latest_candle(self):
        df = frame([110, 108, 106, 104, 99], [100] * 5)
        assert detect_ema_cross(df) == ("SHORT", 0)

    def test_reports_how_many_candles_since_the_cross(self):
        # Cross happens on the 3rd bar, then two more bars print above.
        df = frame([90, 95, 101, 102, 103], [100] * 5)
        direction, candles_since = detect_ema_cross(df)
        assert direction == "LONG"
        assert candles_since == 2

    def test_no_cross_when_consistently_above(self):
        df = frame([101, 102, 103, 104, 105], [100] * 5)
        assert detect_ema_cross(df) == (None, -1)

    def test_no_cross_when_consistently_below(self):
        df = frame([99, 98, 97, 96, 95], [100] * 5)
        assert detect_ema_cross(df) == (None, -1)

    def test_ignores_a_cross_older_than_the_lookback(self):
        # Cross on bar 1, then 8 bars above — beyond the 5-candle window.
        df = frame([90, 101, 102, 103, 104, 105, 106, 107, 108, 109], [100] * 10)
        assert detect_ema_cross(df) == (None, -1)

    def test_returns_the_most_recent_cross_when_several_occur(self):
        # Up, back down, up again — the latest (bullish) cross wins.
        df = frame([99, 101, 99, 98, 101], [100] * 5)
        direction, candles_since = detect_ema_cross(df)
        assert direction == "LONG"
        assert candles_since == 0

    def test_handles_a_short_frame_without_indexing_off_the_end(self):
        df = frame([99, 101], [100, 100])
        direction, _ = detect_ema_cross(df)
        assert direction in ("LONG", None)


# ── detect_ema_precross ─────────────────────────────────────────────────────

class TestDetectEmaPrecross:
    def test_flags_a_narrowing_gap_from_below_as_an_approaching_long(self):
        # ema7 stays under ema25 but closes the gap steadily.
        df = frame([90, 92, 94, 96, 98], [100] * 5)
        result = detect_ema_precross(df, threshold_pct=5.0)
        assert result is not None
        assert result["direction"] == "LONG"
        assert result["spread_pct"] == pytest.approx(2.0, abs=0.01)

    def test_flags_a_narrowing_gap_from_above_as_an_approaching_short(self):
        df = frame([110, 108, 106, 104, 102], [100] * 5)
        result = detect_ema_precross(df, threshold_pct=5.0)
        assert result is not None
        assert result["direction"] == "SHORT"

    def test_ignores_a_widening_gap(self):
        # Moving apart — no cross is coming.
        df = frame([98, 96, 94, 92, 90], [100] * 5)
        assert detect_ema_precross(df, threshold_pct=5.0) is None

    def test_ignores_a_gap_wider_than_the_threshold(self):
        # Narrowing, but still 10% apart with a 5% threshold.
        df = frame([80, 83, 86, 88, 90], [100] * 5)
        assert detect_ema_precross(df, threshold_pct=5.0) is None

    def test_threshold_is_configurable(self):
        df = frame([80, 83, 86, 88, 90], [100] * 5)
        assert detect_ema_precross(df, threshold_pct=15.0) is not None

    def test_skips_symbols_that_already_crossed(self):
        # A fresh cross is a Signal, not a pre-cross.
        df = frame([94, 96, 98, 99, 101], [100] * 5)
        assert detect_ema_precross(df, threshold_pct=5.0) is None

    def test_returns_none_without_the_spread_column(self):
        df = pd.DataFrame({
            "close": [1, 2, 3, 4, 5],
            "ema7": [1, 2, 3, 4, 5],
            "ema25": [2, 3, 4, 5, 6],
        })
        assert detect_ema_precross(df) is None

    def test_returns_none_on_a_too_short_frame(self):
        df = frame([98, 99], [100, 100])
        assert detect_ema_precross(df) is None

    def test_returns_none_when_the_spread_is_nan(self):
        df = frame([90, 92, 94, 96, 98], [100] * 5)
        df.loc[df.index[-1], "ema_spread"] = np.nan
        assert detect_ema_precross(df) is None


# ── integration with the real indicator pipeline ────────────────────────────

class TestAgainstRealIndicatorPipeline:
    """The detectors must work on frames produced by add_all_indicators,
    not just hand-built ones."""

    @staticmethod
    def ohlc(closes):
        closes = np.asarray(closes, dtype=float)
        return pd.DataFrame({
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(len(closes), 1_000.0),
        })

    def test_pipeline_produces_the_columns_the_detectors_need(self):
        df = add_all_indicators(self.ohlc(np.linspace(100, 120, 120)))
        for col in ("ema7", "ema25", "ema_spread"):
            assert col in df.columns
        assert not np.isnan(df["ema_spread"].iloc[-1])

    def test_a_recent_rally_after_a_dip_produces_a_bullish_cross(self):
        # Down-trend then a sharp rally that crosses within the lookback.
        closes = np.concatenate([np.linspace(120, 90, 60), np.linspace(90, 130, 7)])
        df = add_all_indicators(self.ohlc(closes))
        direction, candles_since = detect_ema_cross(df)
        assert direction == "LONG"
        assert candles_since < 5

    def test_a_recent_selloff_after_a_rally_produces_a_bearish_cross(self):
        closes = np.concatenate([np.linspace(90, 120, 60), np.linspace(120, 85, 7)])
        df = add_all_indicators(self.ohlc(closes))
        direction, candles_since = detect_ema_cross(df)
        assert direction == "SHORT"
        assert candles_since < 5

    def test_lightweight_ema_path_matches_the_full_suite_exactly(self):
        """The scan paths use add_ema_columns instead of add_all_indicators for
        speed. That is only safe if the columns are bit-for-bit identical."""
        rng = np.random.default_rng(7)
        closes = 100 + np.cumsum(rng.normal(0, 1, 200))
        raw = self.ohlc(closes)

        full = add_all_indicators(raw)
        light = add_ema_columns(raw)

        for col in ("ema7", "ema25", "ema_spread"):
            pd.testing.assert_series_equal(full[col], light[col], check_names=False)

        # And therefore the detectors agree on both frames.
        assert detect_ema_cross(full) == detect_ema_cross(light)
        assert detect_ema_precross(full) == detect_ema_precross(light)

    def test_lightweight_rsi_path_matches_the_full_suite_exactly(self):
        rng = np.random.default_rng(11)
        closes = 100 + np.cumsum(rng.normal(0, 1, 200))
        raw = self.ohlc(closes)
        pd.testing.assert_series_equal(
            add_all_indicators(raw)["rsi"], add_rsi_columns(raw)["rsi"], check_names=False
        )

    def test_a_cross_that_has_gone_stale_is_not_reported(self):
        """Documents the deliberate 5-candle recency window: a cross from ~14
        bars ago is no longer actionable, so the detector stays silent even
        though ema7 is clearly above ema25."""
        closes = np.concatenate([np.linspace(120, 90, 60), np.linspace(90, 130, 20)])
        df = add_all_indicators(self.ohlc(closes))
        assert df["ema7"].iloc[-1] > df["ema25"].iloc[-1]  # still above...
        assert detect_ema_cross(df) == (None, -1)          # ...but stale
