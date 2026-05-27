"""
Unit tests for signal confidence scoring.

Tests cover:
- Base score calculation
- Confluence bonus (indicator agreement)
- Volume confirmation
- Trend strength scoring
- Sentiment alignment
- Risk/reward ratio bonus
- Rating classification
- Recommendations
"""

import pytest
from confidence_scorer import ConfidenceScorer, ConfidenceScore


class TestConfidenceScorer:
    """Test confidence scoring algorithm."""

    def test_perfect_score(self):
        """Test maximum confidence score."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=100.0,
            indicator_confirmations=[
                {"aligned": True},
                {"aligned": True},
                {"aligned": True},
                {"aligned": True},
            ],
            current_volume=300.0,
            volume_20d_avg=200.0,  # 1.5x
            trend_strength=80.0,
            fear_greed_index=25,  # Extreme fear (bullish for LONG)
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=42000.0,  # RR = 2:1
        )

        assert score.total_score >= 90.0
        assert score.rating == "VERY_HIGH"
        assert score.ai_probability == 100.0
        assert score.technical_confluence == 15.0  # 4/4 indicators
        assert score.volume_confirmation == 10.0  # 1.5x volume
        assert score.trend_strength == 10.0  # 80% trend
        assert score.sentiment_alignment == 10.0  # Extreme fear
        assert score.rr_ratio_bonus == 5.0  # 2:1 ratio

    def test_very_high_confidence(self):
        """Test VERY_HIGH rating (>85)."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=85.0,
            indicator_confirmations=[
                {"aligned": True},
                {"aligned": True},
                {"aligned": True},
            ],
            current_volume=250.0,
            volume_20d_avg=200.0,  # 1.25x
            trend_strength=75.0,
            fear_greed_index=30,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39200.0,
            take_profit=41600.0,  # RR = 2:1
        )

        assert score.rating == "VERY_HIGH"
        assert score.total_score >= 85.0

    def test_high_confidence(self):
        """Test HIGH rating (70-85)."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=62.0,
            indicator_confirmations=[
                {"aligned": True},
                {"aligned": False},
            ],
            current_volume=200.0,
            volume_20d_avg=200.0,  # 1.0x
            trend_strength=40.0,
            fear_greed_index=45,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39500.0,
            take_profit=41500.0,  # RR = 2:1
        )

        assert score.rating == "HIGH"
        assert 70.0 <= score.total_score < 85.0

    def test_medium_confidence(self):
        """Test MEDIUM rating (55-70)."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=55.0,
            indicator_confirmations=[
                {"aligned": True},
                {"aligned": False},
                {"aligned": False},
            ],
            current_volume=150.0,
            volume_20d_avg=200.0,  # 0.75x
            trend_strength=30.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39750.0,
            take_profit=41250.0,  # RR = 2:1
        )

        assert score.rating == "MEDIUM"
        assert 55.0 <= score.total_score < 70.0

    def test_low_confidence(self):
        """Test LOW rating (40-55)."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=45.0,
            indicator_confirmations=[
                {"aligned": False},
                {"aligned": False},
                {"aligned": False},
            ],
            current_volume=100.0,
            volume_20d_avg=200.0,  # 0.5x
            trend_strength=20.0,
            fear_greed_index=60,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39900.0,
            take_profit=40100.0,  # RR = 0.2:1
        )

        assert score.rating == "LOW"
        assert 40.0 <= score.total_score < 55.0

    def test_very_low_confidence(self):
        """Test VERY_LOW rating (<40)."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=30.0,
            indicator_confirmations=[
                {"aligned": False},
                {"aligned": False},
            ],
            current_volume=50.0,
            volume_20d_avg=200.0,  # 0.25x
            trend_strength=10.0,
            fear_greed_index=80,  # Extreme greed (bad for LONG)
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39950.0,
            take_profit=40050.0,  # RR = 0.5:1
        )

        assert score.rating == "VERY_LOW"
        assert score.total_score < 40.0

    def test_short_signal_sentiment_alignment(self):
        """Test sentiment alignment for SHORT signals."""
        # SHORT + Extreme Greed = HIGH bonus
        score_greed = ConfidenceScorer.calculate_score(
            ai_probability=70.0,
            indicator_confirmations=[{"aligned": True}, {"aligned": True}],
            current_volume=220.0,
            volume_20d_avg=200.0,
            trend_strength=50.0,
            fear_greed_index=75,  # Extreme greed (good for SHORT)
            signal_direction="SHORT",
            entry_price=40000.0,
            stop_loss=41000.0,
            take_profit=39000.0,  # RR = 2:1
        )

        # SHORT + Extreme Fear = HIGH bonus
        score_fear = ConfidenceScorer.calculate_score(
            ai_probability=70.0,
            indicator_confirmations=[{"aligned": True}, {"aligned": True}],
            current_volume=220.0,
            volume_20d_avg=200.0,
            trend_strength=50.0,
            fear_greed_index=25,  # Extreme fear (panic = good for SHORT)
            signal_direction="SHORT",
            entry_price=40000.0,
            stop_loss=41000.0,
            take_profit=39000.0,  # RR = 2:1
        )

        assert score_greed.sentiment_alignment == 10.0
        assert score_fear.sentiment_alignment == 8.0  # Panic bonus

    def test_volume_confirmation_levels(self):
        """Test volume bonus at different levels."""
        # >1.5x volume
        score_high_vol = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=300.0,
            volume_20d_avg=200.0,  # 1.5x
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39900.0,
            take_profit=40100.0,
        )
        assert score_high_vol.volume_confirmation == 10.0

        # 1.2-1.5x volume
        score_med_vol = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=260.0,
            volume_20d_avg=200.0,  # 1.3x
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39900.0,
            take_profit=40100.0,
        )
        assert score_med_vol.volume_confirmation == 7.0

        # 0.8-1.2x volume
        score_low_vol = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=180.0,
            volume_20d_avg=200.0,  # 0.9x
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39900.0,
            take_profit=40100.0,
        )
        assert score_low_vol.volume_confirmation == 3.0

        # <0.8x volume
        score_very_low_vol = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=100.0,
            volume_20d_avg=200.0,  # 0.5x
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39900.0,
            take_profit=40100.0,
        )
        assert score_very_low_vol.volume_confirmation == 0.0

    def test_rr_ratio_bonus(self):
        """Test risk/reward ratio bonus."""
        # RR >= 2:1
        score_2_1 = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=200.0,
            volume_20d_avg=200.0,
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=42000.0,  # Risk: 1000, Reward: 2000 = 2:1
        )
        assert score_2_1.rr_ratio_bonus == 5.0

        # RR 1.5:1
        score_1_5_1 = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=200.0,
            volume_20d_avg=200.0,
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=41500.0,  # Risk: 1000, Reward: 1500 = 1.5:1
        )
        assert score_1_5_1.rr_ratio_bonus == 3.0

        # RR 1:1
        score_1_1 = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=200.0,
            volume_20d_avg=200.0,
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=41000.0,  # Risk: 1000, Reward: 1000 = 1:1
        )
        assert score_1_1.rr_ratio_bonus == 1.0

        # RR <1:1
        score_below_1 = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[],
            current_volume=200.0,
            volume_20d_avg=200.0,
            trend_strength=0.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=40500.0,  # Risk: 1000, Reward: 500 = 0.5:1
        )
        assert score_below_1.rr_ratio_bonus == 0.0

    def test_recommendation_generation(self):
        """Test recommendation text based on rating."""
        very_high = ConfidenceScorer.calculate_score(
            ai_probability=90.0,
            indicator_confirmations=[{"aligned": True}],
            current_volume=250.0,
            volume_20d_avg=200.0,
            trend_strength=70.0,
            fear_greed_index=30,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=42000.0,
        )
        assert "AUTO-EXECUTE" in very_high.recommendation
        assert "High confidence" in very_high.recommendation

        medium = ConfidenceScorer.calculate_score(
            ai_probability=50.0,
            indicator_confirmations=[{"aligned": True}, {"aligned": False}],
            current_volume=160.0,
            volume_20d_avg=200.0,
            trend_strength=30.0,
            fear_greed_index=50,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39800.0,
            take_profit=40200.0,
        )
        assert "MANUAL CONFIRMATION" in medium.recommendation

        very_low = ConfidenceScorer.calculate_score(
            ai_probability=30.0,
            indicator_confirmations=[{"aligned": False}],
            current_volume=100.0,
            volume_20d_avg=200.0,
            trend_strength=10.0,
            fear_greed_index=80,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39950.0,
            take_profit=40050.0,
        )
        assert "SKIP" in very_low.recommendation

    def test_score_components_breakdown(self):
        """Test that components are properly formatted."""
        score = ConfidenceScorer.calculate_score(
            ai_probability=75.0,
            indicator_confirmations=[
                {"aligned": True},
                {"aligned": True},
                {"aligned": False},
            ],
            current_volume=250.0,
            volume_20d_avg=200.0,
            trend_strength=65.0,
            fear_greed_index=35,
            signal_direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit=42000.0,
        )

        assert "ai_probability" in score.components
        assert "technical_confluence" in score.components
        assert "volume_confirmation" in score.components
        assert "trend_strength" in score.components
        assert "sentiment_alignment" in score.components
        assert "rr_ratio_bonus" in score.components

        # Verify components are descriptive
        assert "%" in score.components["ai_probability"]
        assert "x 20-day avg" in score.components["volume_confirmation"]
