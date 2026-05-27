"""
Auto-Execution Engine.

Automatically executes trades on VERY_HIGH confidence signals (85+) with:
- User enable/disable toggle
- Drawdown recovery protocol integration
- Multi-level confidence thresholds
- Execution history tracking
- Dry-run/paper mode before live execution
- Position size scaling based on confidence

Auto-execution rules:
1. Signal confidence >= 85 (VERY_HIGH) → Auto-execute at 100% position size
2. Signal confidence >= 75 (HIGH) + no recovery → Auto-execute at 80% position size
3. Recovery mode (15-25% drawdown) → Skip unless VERY_HIGH (execute 50% size)
4. Pause mode (>25% drawdown) → All auto-execution disabled
5. User disabled auto-execution → Manual only

Execution priority:
1. Validate signal (not stale, valid symbol, price fresh)
2. Check recovery state (ACTIVE/CAUTION/RECOVERY/PAUSED)
3. Check user settings (auto-execution enabled, paper/live mode)
4. Calculate position size (base × confidence multiplier × recovery multiplier)
5. Execute trade (paper or live)
6. Log execution + store in database
7. Return confirmation to user
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ExecutionTrigger(str, Enum):
    """Why a trade was auto-executed."""
    VERY_HIGH_CONFIDENCE = "VERY_HIGH_CONFIDENCE"
    HIGH_CONFIDENCE_ACTIVE = "HIGH_CONFIDENCE_ACTIVE"
    MANUAL = "MANUAL"
    SKIPPED_LOW_CONFIDENCE = "SKIPPED_LOW_CONFIDENCE"
    SKIPPED_RECOVERY_MODE = "SKIPPED_RECOVERY_MODE"
    SKIPPED_PAUSED = "SKIPPED_PAUSED"
    SKIPPED_DISABLED = "SKIPPED_DISABLED"


@dataclass
class ExecutionDecision:
    """Decision to execute or skip a trade."""
    should_execute: bool
    trigger: ExecutionTrigger
    position_size_multiplier: float  # How much of base position to execute
    reason: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL


class AutoExecutionEngine:
    """
    Automatically executes trades based on signal confidence and recovery state.

    Integrates three components:
    1. Confidence Scorer: Signal quality assessment (0-100)
    2. Adaptive Position Sizer: Dynamic position sizing
    3. Drawdown Recovery: Risk management during losses
    """

    # Auto-execution thresholds
    VERY_HIGH_CONFIDENCE_THRESHOLD = 85
    HIGH_CONFIDENCE_THRESHOLD = 75
    MEDIUM_CONFIDENCE_THRESHOLD = 55

    @staticmethod
    def should_auto_execute(
        signal_confidence: int,
        recovery_state: str,
        auto_execution_enabled: bool,
        user_mode: str = "PAPER",
    ) -> ExecutionDecision:
        """
        Determine if a signal should be auto-executed.

        Args:
            signal_confidence: Signal confidence score (0-100)
            recovery_state: Current drawdown recovery state (ACTIVE, CAUTION, RECOVERY, PAUSED)
            auto_execution_enabled: User setting to allow auto-execution
            user_mode: Trading mode (PAPER or LIVE)

        Returns:
            ExecutionDecision with execute flag and multiplier
        """

        # Check 1: User disabled auto-execution
        if not auto_execution_enabled:
            return ExecutionDecision(
                should_execute=False,
                trigger=ExecutionTrigger.SKIPPED_DISABLED,
                position_size_multiplier=0.0,
                reason="Auto-execution disabled by user",
                risk_level="LOW",
            )

        # Check 2: PAUSED mode (>25% drawdown) - No auto-execution
        if recovery_state == "PAUSED":
            return ExecutionDecision(
                should_execute=False,
                trigger=ExecutionTrigger.SKIPPED_PAUSED,
                position_size_multiplier=0.0,
                reason="Account in pause mode (>25% drawdown). All auto-execution disabled.",
                risk_level="CRITICAL",
            )

        # Check 3: RECOVERY mode (15-25% drawdown) - Only VERY_HIGH executes (50% size)
        if recovery_state == "RECOVERY":
            if signal_confidence >= AutoExecutionEngine.VERY_HIGH_CONFIDENCE_THRESHOLD:
                return ExecutionDecision(
                    should_execute=True,
                    trigger=ExecutionTrigger.VERY_HIGH_CONFIDENCE,
                    position_size_multiplier=0.5,  # Half size in recovery
                    reason=f"VERY_HIGH confidence ({signal_confidence}) in recovery mode. Auto-executing at 50% size.",
                    risk_level="HIGH",
                )
            else:
                return ExecutionDecision(
                    should_execute=False,
                    trigger=ExecutionTrigger.SKIPPED_RECOVERY_MODE,
                    position_size_multiplier=0.0,
                    reason=f"Account in recovery mode (15-25% drawdown). Requires VERY_HIGH confidence (85+), got {signal_confidence}.",
                    risk_level="HIGH",
                )

        # Check 4: CAUTION mode (5-15% drawdown) - HIGH+ executes (80% size)
        if recovery_state == "CAUTION":
            if signal_confidence >= AutoExecutionEngine.VERY_HIGH_CONFIDENCE_THRESHOLD:
                return ExecutionDecision(
                    should_execute=True,
                    trigger=ExecutionTrigger.VERY_HIGH_CONFIDENCE,
                    position_size_multiplier=1.0,  # Full size for VERY_HIGH even in caution
                    reason=f"VERY_HIGH confidence ({signal_confidence}) in caution mode. Auto-executing at 100% size.",
                    risk_level="MEDIUM",
                )
            elif signal_confidence >= AutoExecutionEngine.HIGH_CONFIDENCE_THRESHOLD:
                return ExecutionDecision(
                    should_execute=True,
                    trigger=ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE,
                    position_size_multiplier=0.8,  # 80% size for HIGH in caution
                    reason=f"HIGH confidence ({signal_confidence}) in caution mode. Auto-executing at 80% size.",
                    risk_level="MEDIUM",
                )
            else:
                return ExecutionDecision(
                    should_execute=False,
                    trigger=ExecutionTrigger.SKIPPED_LOW_CONFIDENCE,
                    position_size_multiplier=0.0,
                    reason=f"Caution mode active (5-15% drawdown). Requires HIGH+ confidence (75+), got {signal_confidence}.",
                    risk_level="MEDIUM",
                )

        # Check 5: ACTIVE state (0-5% drawdown) - Normal thresholds
        if recovery_state == "ACTIVE":
            if signal_confidence >= AutoExecutionEngine.VERY_HIGH_CONFIDENCE_THRESHOLD:
                return ExecutionDecision(
                    should_execute=True,
                    trigger=ExecutionTrigger.VERY_HIGH_CONFIDENCE,
                    position_size_multiplier=1.0,  # Full size for VERY_HIGH
                    reason=f"VERY_HIGH confidence ({signal_confidence}). Auto-executing at 100% size.",
                    risk_level="LOW",
                )
            elif signal_confidence >= AutoExecutionEngine.HIGH_CONFIDENCE_THRESHOLD:
                return ExecutionDecision(
                    should_execute=True,
                    trigger=ExecutionTrigger.HIGH_CONFIDENCE_ACTIVE,
                    position_size_multiplier=1.0,  # Full size for HIGH in active
                    reason=f"HIGH confidence ({signal_confidence}). Auto-executing at 100% size.",
                    risk_level="LOW",
                )
            else:
                return ExecutionDecision(
                    should_execute=False,
                    trigger=ExecutionTrigger.SKIPPED_LOW_CONFIDENCE,
                    position_size_multiplier=0.0,
                    reason=f"Confidence score {signal_confidence} below auto-execute threshold (75+). Manual execution required.",
                    risk_level="LOW",
                )

        # Fallback (unknown state)
        return ExecutionDecision(
            should_execute=False,
            trigger=ExecutionTrigger.SKIPPED_LOW_CONFIDENCE,
            position_size_multiplier=0.0,
            reason="Unknown recovery state. Manual execution required.",
            risk_level="MEDIUM",
        )

    @staticmethod
    def validate_signal_freshness(
        signal_timestamp: datetime,
        max_age_minutes: int = 5,
    ) -> Tuple[bool, str]:
        """
        Check if signal is fresh enough to auto-execute.

        Args:
            signal_timestamp: When signal was generated
            max_age_minutes: Max age in minutes (default 5)

        Returns:
            Tuple (is_fresh, reason)
        """
        age = datetime.utcnow() - signal_timestamp
        age_minutes = age.total_seconds() / 60

        if age_minutes > max_age_minutes:
            return False, f"Signal too old ({age_minutes:.1f}m). Max {max_age_minutes}m allowed."

        return True, f"Signal fresh ({age_minutes:.1f}m old)"

    @staticmethod
    def validate_entry_price_freshness(
        signal_entry_price: float,
        current_market_price: float,
        max_slippage_pct: float = 2.0,
    ) -> Tuple[bool, str]:
        """
        Check if entry price hasn't slipped too much.

        Args:
            signal_entry_price: Entry price from signal
            current_market_price: Current market price
            max_slippage_pct: Max allowed slippage %

        Returns:
            Tuple (is_valid, reason)
        """
        slippage_pct = abs(current_market_price - signal_entry_price) / signal_entry_price * 100

        if slippage_pct > max_slippage_pct:
            return (
                False,
                f"Price slippage {slippage_pct:.2f}% exceeds max {max_slippage_pct}%. "
                f"Signal: ${signal_entry_price}, Current: ${current_market_price}",
            )

        return True, f"Price slippage acceptable ({slippage_pct:.2f}%)"

    @staticmethod
    def get_execution_summary(
        decision: ExecutionDecision,
        signal_symbol: str,
        signal_direction: str,
        base_position_size: float,
    ) -> Dict[str, any]:
        """
        Generate human-readable execution summary.

        Returns:
            Dictionary with execution details
        """
        final_position_size = base_position_size * decision.position_size_multiplier

        return {
            "auto_execute": decision.should_execute,
            "trigger": decision.trigger.value,
            "reason": decision.reason,
            "risk_level": decision.risk_level,
            "symbol": signal_symbol,
            "direction": signal_direction,
            "base_position_size": base_position_size,
            "position_size_multiplier": decision.position_size_multiplier,
            "final_position_size": final_position_size,
            "timestamp": datetime.utcnow().isoformat(),
        }


class ExecutionPolicyBuilder:
    """
    Builder for custom auto-execution policies.

    Example:
        policy = (ExecutionPolicyBuilder()
            .with_very_high_confidence_threshold(90)
            .with_max_signal_age_minutes(3)
            .with_max_slippage_pct(1.5)
            .build())
    """

    def __init__(self):
        self.very_high_threshold = 85
        self.high_threshold = 75
        self.medium_threshold = 55
        self.max_signal_age_minutes = 5
        self.max_slippage_pct = 2.0
        self.require_paper_first = True

    def with_very_high_confidence_threshold(self, threshold: int) -> "ExecutionPolicyBuilder":
        """Set VERY_HIGH confidence threshold (default 85)."""
        self.very_high_threshold = threshold
        return self

    def with_high_confidence_threshold(self, threshold: int) -> "ExecutionPolicyBuilder":
        """Set HIGH confidence threshold (default 75)."""
        self.high_threshold = threshold
        return self

    def with_max_signal_age(self, minutes: int) -> "ExecutionPolicyBuilder":
        """Set max signal age in minutes (default 5)."""
        self.max_signal_age_minutes = minutes
        return self

    def with_max_slippage(self, pct: float) -> "ExecutionPolicyBuilder":
        """Set max price slippage % (default 2.0)."""
        self.max_slippage_pct = pct
        return self

    def with_paper_first_requirement(self, required: bool) -> "ExecutionPolicyBuilder":
        """Require paper trading before live (default True)."""
        self.require_paper_first = required
        return self

    def build(self) -> Dict[str, any]:
        """Build the policy dictionary."""
        return {
            "very_high_threshold": self.very_high_threshold,
            "high_threshold": self.high_threshold,
            "medium_threshold": self.medium_threshold,
            "max_signal_age_minutes": self.max_signal_age_minutes,
            "max_slippage_pct": self.max_slippage_pct,
            "require_paper_first": self.require_paper_first,
        }
