"""
Unit tests for auto-execution engine.

Tests cover:
- Auto-execution decision logic based on confidence and recovery state
- Position size multiplier calculation
- Signal freshness validation
- Entry price slippage detection
- Execution policy builder
"""

import pytest
from datetime import datetime, timedelta
from auto_execution_engine import (
    AutoExecutionEngine,
    ExecutionDecision,
    ExecutionTrigger,
    ExecutionPolicyBuilder,
)


class TestAutoExecutionDecision:
    """Tests for auto-execution decision logic."""

    def test_disabled_auto_execution_returns_skipped(self):
        """User disabled auto-execution should always skip."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=95,  # VERY_HIGH
            recovery_state="ACTIVE",
            auto_execution_enabled=False,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_DISABLED
        assert decision.position_size_multiplier == 0.0
        assert decision.risk_level == "LOW"

    def test_paused_state_blocks_all_execution(self):
        """PAUSED state (>25% DD) should block all trades."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=95,  # Even VERY_HIGH
            recovery_state="PAUSED",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_PAUSED
        assert decision.position_size_multiplier == 0.0
        assert decision.risk_level == "CRITICAL"

    def test_recovery_mode_requires_very_high_confidence(self):
        """RECOVERY state requires VERY_HIGH (85+) confidence."""
        # HIGH confidence should be skipped
        high_confidence = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="RECOVERY",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert high_confidence.should_execute is False
        assert high_confidence.trigger == ExecutionTrigger.SKIPPED_RECOVERY_MODE

        # VERY_HIGH confidence should execute at 50% size
        very_high_confidence = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="RECOVERY",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert very_high_confidence.should_execute is True
        assert very_high_confidence.trigger == ExecutionTrigger.VERY_HIGH_CONFIDENCE
        assert very_high_confidence.position_size_multiplier == 0.5
        assert very_high_confidence.risk_level == "HIGH"

    def test_recovery_mode_very_high_executes_at_50_percent(self):
        """RECOVERY mode executes VERY_HIGH at 50% position size."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=90,
            recovery_state="RECOVERY",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.position_size_multiplier == 0.5
        assert "50%" in decision.reason

    def test_caution_mode_very_high_at_100_percent(self):
        """CAUTION mode executes VERY_HIGH at 100% position size."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.VERY_HIGH_CONFIDENCE
        assert decision.position_size_multiplier == 1.0
        assert decision.risk_level == "MEDIUM"

    def test_caution_mode_high_at_80_percent(self):
        """CAUTION mode executes HIGH (75+) at 80% position size."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE
        assert decision.position_size_multiplier == 0.8
        assert decision.risk_level == "MEDIUM"

    def test_caution_mode_medium_confidence_skipped(self):
        """CAUTION mode skips MEDIUM (<75) confidence."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=55,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_LOW_CONFIDENCE
        assert decision.position_size_multiplier == 0.0

    def test_active_mode_very_high_at_100_percent(self):
        """ACTIVE mode executes VERY_HIGH at 100% position size."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.VERY_HIGH_CONFIDENCE
        assert decision.position_size_multiplier == 1.0
        assert decision.risk_level == "LOW"

    def test_active_mode_high_at_100_percent(self):
        """ACTIVE mode executes HIGH (75+) at 100% position size."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE
        assert decision.position_size_multiplier == 1.0
        assert decision.risk_level == "LOW"

    def test_active_mode_medium_confidence_skipped(self):
        """ACTIVE mode skips MEDIUM (<75) confidence."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=55,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_LOW_CONFIDENCE
        assert decision.position_size_multiplier == 0.0

    def test_very_high_boundary_exactly_85(self):
        """Signal at exactly 85 confidence should be VERY_HIGH."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.VERY_HIGH_CONFIDENCE
        assert decision.position_size_multiplier == 1.0

    def test_very_high_boundary_84_is_high(self):
        """Signal at 84 confidence should be HIGH, not VERY_HIGH."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=84,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE
        assert decision.position_size_multiplier == 1.0

    def test_high_boundary_exactly_75(self):
        """Signal at exactly 75 confidence should be HIGH."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE

    def test_high_boundary_74_skipped(self):
        """Signal at 74 confidence should be skipped in ACTIVE."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=74,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_LOW_CONFIDENCE

    def test_unknown_recovery_state_defaults_to_skip(self):
        """Unknown recovery state should default to skipped."""
        decision = AutoExecutionEngine.should_auto_execute(
            signal_confidence=95,
            recovery_state="UNKNOWN_STATE",
            auto_execution_enabled=True,
            user_mode="LIVE",
        )

        assert decision.should_execute is False
        assert decision.trigger == ExecutionTrigger.SKIPPED_LOW_CONFIDENCE


class TestSignalFreshnessValidation:
    """Tests for signal freshness validation."""

    def test_fresh_signal_5_minutes_old(self):
        """Signal just under 5 minutes old should be fresh."""
        signal_time = datetime.utcnow() - timedelta(minutes=4, seconds=59)
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=5
        )

        assert is_fresh is True
        assert "fresh" in reason.lower()

    def test_stale_signal_exceeds_max_age(self):
        """Signal older than max age should be stale."""
        signal_time = datetime.utcnow() - timedelta(minutes=6)
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=5
        )

        assert is_fresh is False
        assert "old" in reason.lower()

    def test_very_fresh_signal_less_than_1_minute(self):
        """Signal less than 1 minute old should be fresh."""
        signal_time = datetime.utcnow() - timedelta(seconds=30)
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=5
        )

        assert is_fresh is True

    def test_just_generated_signal(self):
        """Just-generated signal should be fresh."""
        signal_time = datetime.utcnow()
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=5
        )

        assert is_fresh is True

    def test_custom_max_age_1_minute(self):
        """Test custom max age of 1 minute."""
        signal_time = datetime.utcnow() - timedelta(seconds=59)
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=1
        )

        assert is_fresh is True

    def test_custom_max_age_exceeded_1_minute(self):
        """Signal exceeding 1 minute max age should be stale."""
        signal_time = datetime.utcnow() - timedelta(seconds=61)
        is_fresh, reason = AutoExecutionEngine.validate_signal_freshness(
            signal_time, max_age_minutes=1
        )

        assert is_fresh is False


class TestEntryPriceFreshnessValidation:
    """Tests for entry price slippage validation."""

    def test_no_slippage(self):
        """Entry price matching current price should be valid."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=40000.0,
            max_slippage_pct=2.0,
        )

        assert is_valid is True
        assert "acceptable" in reason.lower()

    def test_acceptable_slippage_1_percent(self):
        """1% slippage should be within 2% limit."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=40400.0,  # +1%
            max_slippage_pct=2.0,
        )

        assert is_valid is True

    def test_slippage_at_exact_limit(self):
        """2% slippage at exact 2% limit should be valid."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=40800.0,  # +2%
            max_slippage_pct=2.0,
        )

        assert is_valid is True

    def test_slippage_exceeds_limit(self):
        """Slippage exceeding limit should be invalid."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=41000.0,  # +2.5%
            max_slippage_pct=2.0,
        )

        assert is_valid is False
        assert "exceeds" in reason.lower()

    def test_negative_slippage_price_dropped(self):
        """Price drop should also be checked as slippage."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=39200.0,  # -2%
            max_slippage_pct=2.0,
        )

        assert is_valid is True

    def test_negative_slippage_exceeds_limit(self):
        """Price drop exceeding limit should be invalid."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=38900.0,  # -2.75%
            max_slippage_pct=2.0,
        )

        assert is_valid is False

    def test_strict_slippage_limit_0_5_percent(self):
        """Tight slippage limit should enforce tighter bounds."""
        is_valid, reason = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=40200.0,  # +0.5%
            max_slippage_pct=0.5,
        )

        assert is_valid is True

        is_valid_exceed, reason_exceed = AutoExecutionEngine.validate_entry_price_freshness(
            signal_entry_price=40000.0,
            current_market_price=40210.0,  # +0.525%
            max_slippage_pct=0.5,
        )

        assert is_valid_exceed is False


class TestExecutionSummary:
    """Tests for execution summary generation."""

    def test_summary_contains_all_fields(self):
        """Execution summary should include all required fields."""
        decision = ExecutionDecision(
            should_execute=True,
            trigger=ExecutionTrigger.VERY_HIGH_CONFIDENCE,
            position_size_multiplier=0.8,
            reason="VERY_HIGH confidence in CAUTION mode",
            risk_level="MEDIUM",
        )

        summary = AutoExecutionEngine.get_execution_summary(
            decision=decision,
            signal_symbol="BTCUSDT",
            signal_direction="LONG",
            base_position_size=1000.0,
        )

        assert summary["auto_execute"] is True
        assert summary["trigger"] == "VERY_HIGH_CONFIDENCE"
        assert summary["symbol"] == "BTCUSDT"
        assert summary["direction"] == "LONG"
        assert summary["base_position_size"] == 1000.0
        assert summary["position_size_multiplier"] == 0.8
        assert summary["final_position_size"] == 800.0
        assert summary["risk_level"] == "MEDIUM"
        assert "timestamp" in summary

    def test_summary_calculates_final_position_size(self):
        """Final position size should be base × multiplier."""
        decision = ExecutionDecision(
            should_execute=True,
            trigger=ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE,
            position_size_multiplier=0.5,
            reason="Recovery mode",
            risk_level="HIGH",
        )

        summary = AutoExecutionEngine.get_execution_summary(
            decision=decision,
            signal_symbol="ETHUSDT",
            signal_direction="SHORT",
            base_position_size=2000.0,
        )

        assert summary["final_position_size"] == pytest.approx(1000.0, rel=1e-6)

    def test_summary_zero_multiplier_zero_position(self):
        """Zero multiplier should result in zero position size."""
        decision = ExecutionDecision(
            should_execute=False,
            trigger=ExecutionTrigger.SKIPPED_DISABLED,
            position_size_multiplier=0.0,
            reason="Auto-execution disabled",
            risk_level="LOW",
        )

        summary = AutoExecutionEngine.get_execution_summary(
            decision=decision,
            signal_symbol="BNBUSDT",
            signal_direction="LONG",
            base_position_size=500.0,
        )

        assert summary["final_position_size"] == 0.0
        assert summary["auto_execute"] is False


class TestExecutionPolicyBuilder:
    """Tests for execution policy customization."""

    def test_default_policy_values(self):
        """Default policy should have standard thresholds."""
        policy = ExecutionPolicyBuilder().build()

        assert policy["very_high_threshold"] == 85
        assert policy["high_threshold"] == 75
        assert policy["medium_threshold"] == 55
        assert policy["max_signal_age_minutes"] == 5
        assert policy["max_slippage_pct"] == 2.0
        assert policy["require_paper_first"] is True

    def test_custom_very_high_threshold(self):
        """Should be able to customize VERY_HIGH threshold."""
        policy = (
            ExecutionPolicyBuilder()
            .with_very_high_confidence_threshold(90)
            .build()
        )

        assert policy["very_high_threshold"] == 90
        assert policy["high_threshold"] == 75  # Unchanged

    def test_custom_high_threshold(self):
        """Should be able to customize HIGH threshold."""
        policy = (
            ExecutionPolicyBuilder()
            .with_high_confidence_threshold(70)
            .build()
        )

        assert policy["high_threshold"] == 70
        assert policy["very_high_threshold"] == 85  # Unchanged

    def test_custom_max_signal_age(self):
        """Should be able to customize max signal age."""
        policy = (
            ExecutionPolicyBuilder()
            .with_max_signal_age(3)
            .build()
        )

        assert policy["max_signal_age_minutes"] == 3

    def test_custom_max_slippage(self):
        """Should be able to customize max slippage."""
        policy = (
            ExecutionPolicyBuilder()
            .with_max_slippage(1.0)
            .build()
        )

        assert policy["max_slippage_pct"] == 1.0

    def test_custom_paper_first_requirement(self):
        """Should be able to disable paper-first requirement."""
        policy = (
            ExecutionPolicyBuilder()
            .with_paper_first_requirement(False)
            .build()
        )

        assert policy["require_paper_first"] is False

    def test_builder_fluent_interface_all_settings(self):
        """Builder should support chaining all settings."""
        policy = (
            ExecutionPolicyBuilder()
            .with_very_high_confidence_threshold(92)
            .with_high_confidence_threshold(78)
            .with_max_signal_age(2)
            .with_max_slippage(0.5)
            .with_paper_first_requirement(False)
            .build()
        )

        assert policy["very_high_threshold"] == 92
        assert policy["high_threshold"] == 78
        assert policy["max_signal_age_minutes"] == 2
        assert policy["max_slippage_pct"] == 0.5
        assert policy["require_paper_first"] is False


class TestExecutionDecision:
    """Tests for ExecutionDecision dataclass."""

    def test_execution_decision_all_fields(self):
        """ExecutionDecision should contain all required fields."""
        decision = ExecutionDecision(
            should_execute=True,
            trigger=ExecutionTrigger.VERY_HIGH_CONFIDENCE,
            position_size_multiplier=1.0,
            reason="VERY_HIGH confidence signal",
            risk_level="LOW",
        )

        assert decision.should_execute is True
        assert decision.trigger == ExecutionTrigger.VERY_HIGH_CONFIDENCE
        assert decision.position_size_multiplier == 1.0
        assert decision.reason == "VERY_HIGH confidence signal"
        assert decision.risk_level == "LOW"

    def test_execution_trigger_enum_values(self):
        """ExecutionTrigger enum should have all expected values."""
        triggers = [
            ExecutionTrigger.VERY_HIGH_CONFIDENCE,
            ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE,
            ExecutionTrigger.MANUAL,
            ExecutionTrigger.SKIPPED_LOW_CONFIDENCE,
            ExecutionTrigger.SKIPPED_RECOVERY_MODE,
            ExecutionTrigger.SKIPPED_PAUSED,
            ExecutionTrigger.SKIPPED_DISABLED,
        ]

        assert len(triggers) == 7
        assert all(isinstance(t, ExecutionTrigger) for t in triggers)


class TestStateTransitionScenarios:
    """Tests for real-world state transition scenarios."""

    def test_drawdown_causes_mode_transition_active_to_caution(self):
        """Confidence stays same but mode changes due to drawdown."""
        active = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="ACTIVE",
            auto_execution_enabled=True,
        )

        caution = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
        )

        # Both execute, but multiplier differs
        assert active.should_execute is True
        assert active.position_size_multiplier == 1.0
        assert caution.should_execute is True
        assert caution.position_size_multiplier == 0.8

    def test_drawdown_causes_mode_transition_caution_to_recovery(self):
        """HIGH confidence gets rejected when entering RECOVERY."""
        caution = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
        )

        recovery = AutoExecutionEngine.should_auto_execute(
            signal_confidence=75,
            recovery_state="RECOVERY",
            auto_execution_enabled=True,
        )

        assert caution.should_execute is True
        assert recovery.should_execute is False

    def test_recovery_exit_when_drawdown_recovers(self):
        """Signal that was rejected in RECOVERY should execute in CAUTION."""
        recovery = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="RECOVERY",
            auto_execution_enabled=True,
        )

        caution = AutoExecutionEngine.should_auto_execute(
            signal_confidence=85,
            recovery_state="CAUTION",
            auto_execution_enabled=True,
        )

        # Same signal, different states
        assert recovery.position_size_multiplier == 0.5  # Recovery penalty
        assert caution.position_size_multiplier == 1.0  # Full size

    def test_pause_prevents_all_executions_regardless_of_confidence(self):
        """PAUSED state should reject all confidence levels."""
        for confidence in [55, 75, 85, 95]:
            decision = AutoExecutionEngine.should_auto_execute(
                signal_confidence=confidence,
                recovery_state="PAUSED",
                auto_execution_enabled=True,
            )

            assert decision.should_execute is False
            assert decision.trigger == ExecutionTrigger.SKIPPED_PAUSED
