"""
Signal Confidence Scoring Engine.

Evaluates signal quality on a 0-100 scale based on:
- AI probability (base score)
- Technical indicator confluence
- Volume confirmation
- Trend strength
- Fear & Greed alignment
- Risk/Reward ratio

Scoring model:
Base (AI probability): 0-100 points
├─ Technical confluence: +15 points max (3+ indicators agree)
├─ Volume confirmation: +10 points max (volume > 20-day avg)
├─ Trend strength: +10 points max (strong trend established)
├─ Fear & Greed alignment: +10 points max (signal matches sentiment)
└─ Risk/Reward ratio: +5 points max (RR >= 2:1)

FINAL SCORE: 0-150 (normalized to 0-100)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class ConfidenceScore:
    """Signal confidence assessment."""
    total_score: float  # 0-100
    ai_probability: float  # Base score
    technical_confluence: float  # 0-15
    volume_confirmation: float  # 0-10
    trend_strength: float  # 0-10
    sentiment_alignment: float  # 0-10
    rr_ratio_bonus: float  # 0-5
    components: Dict[str, str]  # Human-readable breakdown
    rating: str  # "VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"
    recommendation: str  # Action to take


class ConfidenceScorer:
    """Scores signal quality for execution decisions."""

    @staticmethod
    def calculate_score(
        ai_probability: float,
        indicator_confirmations: List[Dict],
        current_volume: float,
        volume_20d_avg: float,
        trend_strength: float,  # 0-100 (percentage)
        fear_greed_index: int,  # 0-100
        signal_direction: str,  # "LONG" or "SHORT"
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> ConfidenceScore:
        """
        Calculate comprehensive confidence score for a signal.

        Args:
            ai_probability: ML model confidence (0-100)
            indicator_confirmations: List of indicator results
            current_volume: Current candle volume
            volume_20d_avg: 20-day average volume
            trend_strength: How strong the trend is (0-100)
            fear_greed_index: Market sentiment (0-100, 0=extreme fear, 100=extreme greed)
            signal_direction: LONG or SHORT
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            ConfidenceScore object with breakdown
        """

        # 1. BASE SCORE: AI Probability (0-100)
        base_score = float(ai_probability)

        # 2. TECHNICAL CONFLUENCE (0-15 bonus points)
        confluence_bonus = ConfidenceScorer._calculate_confluence_bonus(
            indicator_confirmations, signal_direction
        )

        # 3. VOLUME CONFIRMATION (0-10 bonus points)
        volume_bonus = ConfidenceScorer._calculate_volume_bonus(
            current_volume, volume_20d_avg
        )

        # 4. TREND STRENGTH (0-10 bonus points)
        trend_bonus = ConfidenceScorer._calculate_trend_bonus(trend_strength)

        # 5. SENTIMENT ALIGNMENT (0-10 bonus points)
        sentiment_bonus = ConfidenceScorer._calculate_sentiment_bonus(
            fear_greed_index, signal_direction
        )

        # 6. RISK/REWARD RATIO (0-5 bonus points)
        rr_bonus = ConfidenceScorer._calculate_rr_bonus(
            entry_price, stop_loss, take_profit, signal_direction
        )

        # TOTAL SCORE (capped at 100)
        raw_total = base_score + confluence_bonus + volume_bonus + trend_bonus + sentiment_bonus + rr_bonus
        total_score = min(100.0, raw_total)

        # RATING
        rating = ConfidenceScorer._get_rating(total_score)

        # RECOMMENDATION
        recommendation = ConfidenceScorer._get_recommendation(total_score, rating)

        # COMPONENTS (human-readable)
        components = {
            "ai_probability": f"{ai_probability:.1f}% (base score)",
            "technical_confluence": f"+{confluence_bonus:.1f} ({len([c for c in indicator_confirmations if c.get('aligned')])} indicators aligned)",
            "volume_confirmation": f"+{volume_bonus:.1f} ({current_volume/volume_20d_avg:.1f}x 20-day avg)",
            "trend_strength": f"+{trend_bonus:.1f} ({trend_strength:.0f}% trend)",
            "sentiment_alignment": f"+{sentiment_bonus:.1f} (Fear & Greed: {fear_greed_index})",
            "rr_ratio_bonus": f"+{rr_bonus:.1f} (R:R = 1:{ConfidenceScorer._calculate_rr_ratio(entry_price, stop_loss, take_profit, signal_direction):.2f})",
        }

        return ConfidenceScore(
            total_score=total_score,
            ai_probability=base_score,
            technical_confluence=confluence_bonus,
            volume_confirmation=volume_bonus,
            trend_strength=trend_bonus,
            sentiment_alignment=sentiment_bonus,
            rr_ratio_bonus=rr_bonus,
            components=components,
            rating=rating,
            recommendation=recommendation,
        )

    @staticmethod
    def _calculate_confluence_bonus(
        confirmations: List[Dict], direction: str
    ) -> float:
        """Calculate bonus for indicator confluence (0-15)."""
        if not confirmations:
            return 0.0

        aligned_count = len([c for c in confirmations if c.get("aligned", False)])
        total_indicators = len(confirmations)

        if total_indicators == 0:
            return 0.0

        alignment_pct = aligned_count / total_indicators

        # Scoring:
        # 100% aligned: +15
        # 75% aligned: +12
        # 50% aligned: +6
        # <50%: 0
        if alignment_pct >= 0.75:
            return 15.0
        elif alignment_pct >= 0.5:
            return 12.0 * alignment_pct
        else:
            return 0.0

    @staticmethod
    def _calculate_volume_bonus(current_vol: float, avg_vol: float) -> float:
        """Calculate bonus for volume confirmation (0-10)."""
        if avg_vol == 0:
            return 0.0

        vol_ratio = current_vol / avg_vol

        # Scoring:
        # >=1.5x: +10
        # >1.2x and <1.5x: +7
        # 0.8-1.2x: +3
        # <0.8x: 0
        if vol_ratio >= 1.5:
            return 10.0
        elif vol_ratio > 1.2:
            return 7.0
        elif vol_ratio >= 0.8:
            return 3.0
        else:
            return 0.0

    @staticmethod
    def _calculate_trend_bonus(trend_strength: float) -> float:
        """Calculate bonus for trend strength (0-10)."""
        # trend_strength is 0-100 percentage
        # >70%: +10
        # 50-70%: +6
        # 30-50%: +3
        # <30%: 0
        if trend_strength > 70:
            return 10.0
        elif trend_strength > 50:
            return 6.0
        elif trend_strength > 30:
            return 3.0
        else:
            return 0.0

    @staticmethod
    def _calculate_sentiment_bonus(fear_greed: int, direction: str) -> float:
        """Calculate bonus for sentiment alignment (0-10)."""
        # fear_greed: 0-100 (0=extreme fear, 100=extreme greed)

        if direction == "LONG":
            # Bullish when fear is low (contrarian) or greed is high (momentum)
            if fear_greed < 30:  # Extreme fear = good buying opportunity
                return 10.0
            elif fear_greed < 45:  # Fear
                return 7.0
            elif fear_greed > 70:  # Greed = momentum
                return 8.0
            else:
                return 3.0
        else:  # SHORT
            # Bearish when greed is high (mean reversion) or fear is low (panic)
            if fear_greed > 70:  # Extreme greed = good shorting
                return 10.0
            elif fear_greed > 55:  # Greed
                return 7.0
            elif fear_greed < 30:  # Extreme fear = panic
                return 8.0
            else:
                return 3.0

    @staticmethod
    def _calculate_rr_bonus(
        entry: float, stop_loss: float, take_profit: float, direction: str
    ) -> float:
        """Calculate bonus for risk/reward ratio (0-5)."""
        if direction == "LONG":
            risk = entry - stop_loss
            reward = take_profit - entry
        else:  # SHORT
            risk = stop_loss - entry
            reward = entry - take_profit

        if risk <= 0 or reward <= 0:
            return 0.0

        rr_ratio = reward / risk

        # Scoring:
        # RR >= 2:1: +5
        # RR >= 1.5:1: +3
        # RR >= 1:1: +1
        # <1:1: 0
        if rr_ratio >= 2.0:
            return 5.0
        elif rr_ratio >= 1.5:
            return 3.0
        elif rr_ratio >= 1.0:
            return 1.0
        else:
            return 0.0

    @staticmethod
    def _calculate_rr_ratio(
        entry: float, stop_loss: float, take_profit: float, direction: str
    ) -> float:
        """Calculate actual risk/reward ratio."""
        if direction == "LONG":
            risk = entry - stop_loss
            reward = take_profit - entry
        else:
            risk = stop_loss - entry
            reward = entry - take_profit

        if risk <= 0:
            return 0.0
        return reward / risk

    @staticmethod
    def _get_rating(score: float) -> str:
        """Convert score to rating."""
        if score >= 85:
            return "VERY_HIGH"
        elif score >= 70:
            return "HIGH"
        elif score >= 55:
            return "MEDIUM"
        elif score >= 40:
            return "LOW"
        else:
            return "VERY_LOW"

    @staticmethod
    def _get_recommendation(score: float, rating: str) -> str:
        """Get execution recommendation based on score."""
        if rating == "VERY_HIGH":
            return "✅ AUTO-EXECUTE: High confidence signal, ready for automation"
        elif rating == "HIGH":
            return "✅ AUTO-EXECUTE: Strong signal, execute at full position size"
        elif rating == "MEDIUM":
            return "⚠️ MANUAL CONFIRMATION: Review signal before executing"
        elif rating == "LOW":
            return "⚠️ PROCEED WITH CAUTION: Weak signal, consider partial size or skip"
        else:
            return "❌ SKIP: Very low confidence, wait for better setup"
