"""Database repositories for accessing and manipulating data."""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from models import SignalHistoryDB, UserPreferencesDB, ErrorLogDB, TradeDB, BinanceCredentialsDB, AutoExecutionAuditDB, Signal, SignalDirection, TradeStatus
from logging_config import get_logger

logger = get_logger(__name__)


class SignalRepository:
    """Repository for signal history operations."""

    @staticmethod
    def store_signal(db: Session, signal: Signal) -> SignalHistoryDB:
        """Store a generated signal in the database."""
        db_signal = SignalHistoryDB(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction.value,
            confidence=signal.confidence,
            ai_probability=signal.ai_probability,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profits=[tp.dict() for tp in signal.take_profits],
            rr_ratio=signal.rr_ratio,
            indicators=[ind.dict() for ind in signal.indicators],
            sentiment_score=signal.sentiment_score,
            volume_ratio=signal.volume_ratio,
            atr=signal.atr,
        )
        db.add(db_signal)
        db.commit()
        db.refresh(db_signal)
        logger.info(
            f"Signal stored: {signal.symbol} {signal.direction.value}",
            action="signal_stored",
            signal_id=db_signal.id,
            symbol=signal.symbol,
            direction=signal.direction.value,
        )
        return db_signal

    @staticmethod
    def get_recent_signals(
        db: Session, symbol: Optional[str] = None, limit: int = 100
    ) -> List[SignalHistoryDB]:
        """Get recent signals, optionally filtered by symbol."""
        query = db.query(SignalHistoryDB).order_by(
            SignalHistoryDB.created_at.desc()
        )
        if symbol:
            query = query.filter(SignalHistoryDB.symbol == symbol)
        return query.limit(limit).all()

    @staticmethod
    def get_signal_by_id(db: Session, signal_id: int) -> Optional[SignalHistoryDB]:
        """Get a signal by ID."""
        return db.query(SignalHistoryDB).filter(SignalHistoryDB.id == signal_id).first()

    @staticmethod
    def update_signal_exit(
        db: Session,
        signal_id: int,
        exit_price: float,
        exit_reason: str,
        pnl_pct: float,
    ) -> SignalHistoryDB:
        """Update signal with exit information."""
        db_signal = db.query(SignalHistoryDB).filter(
            SignalHistoryDB.id == signal_id
        ).first()
        if db_signal:
            db_signal.exit_price = exit_price
            db_signal.exit_reason = exit_reason
            db_signal.pnl_pct = pnl_pct
            db_signal.is_closed = True
            db_signal.closed_at = datetime.utcnow()
            db.commit()
            db.refresh(db_signal)
            logger.info(
                f"Signal closed with PnL {pnl_pct}%",
                action="signal_closed",
                signal_id=signal_id,
                pnl_pct=pnl_pct,
            )
        return db_signal

    @staticmethod
    def get_performance_stats(
        db: Session, symbol: Optional[str] = None
    ) -> dict:
        """Calculate performance statistics from closed signals."""
        query = db.query(SignalHistoryDB).filter(SignalHistoryDB.is_closed == True)
        if symbol:
            query = query.filter(SignalHistoryDB.symbol == symbol)

        signals = query.all()
        if not signals:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "best_trade": 0,
                "worst_trade": 0,
            }

        closed_signals = [s for s in signals if s.pnl_pct is not None]
        wins = [s for s in closed_signals if s.pnl_pct > 0]
        losses = [s for s in closed_signals if s.pnl_pct <= 0]

        total_pnl = sum(s.pnl_pct for s in closed_signals)
        avg_pnl = total_pnl / len(closed_signals) if closed_signals else 0

        return {
            "total_trades": len(closed_signals),
            "win_rate": (len(wins) / len(closed_signals) * 100)
            if closed_signals
            else 0,
            "avg_pnl": avg_pnl,
            "best_trade": max((s.pnl_pct for s in closed_signals), default=0),
            "worst_trade": min((s.pnl_pct for s in closed_signals), default=0),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
        }


class UserRepository:
    """Repository for user preferences operations."""

    @staticmethod
    def get_or_create_preferences(db: Session, user_id: str) -> UserPreferencesDB:
        """Get user preferences or create defaults."""
        user_prefs = db.query(UserPreferencesDB).filter(
            UserPreferencesDB.user_id == user_id
        ).first()

        if not user_prefs:
            user_prefs = UserPreferencesDB(user_id=user_id)
            db.add(user_prefs)
            db.commit()
            db.refresh(user_prefs)
            logger.info(
                f"User preferences created: {user_id}",
                action="user_preferences_created",
                user_id=user_id,
            )

        return user_prefs

    @staticmethod
    def update_alert_symbols(
        db: Session, user_id: str, symbols: List[str]
    ) -> UserPreferencesDB:
        """Update user's alert symbols."""
        user_prefs = UserRepository.get_or_create_preferences(db, user_id)
        user_prefs.alert_symbols = symbols
        db.commit()
        db.refresh(user_prefs)
        return user_prefs

    @staticmethod
    def update_alert_timeframes(
        db: Session, user_id: str, timeframes: List[str]
    ) -> UserPreferencesDB:
        """Update user's alert timeframes."""
        user_prefs = UserRepository.get_or_create_preferences(db, user_id)
        user_prefs.alert_timeframes = timeframes
        db.commit()
        db.refresh(user_prefs)
        return user_prefs

    @staticmethod
    def update_alert_min_confidence(
        db: Session, user_id: str, min_confidence: int
    ) -> UserPreferencesDB:
        """Update minimum confidence for alerts."""
        user_prefs = UserRepository.get_or_create_preferences(db, user_id)
        user_prefs.alert_min_confidence = max(0, min(100, min_confidence))
        db.commit()
        db.refresh(user_prefs)
        return user_prefs

    @staticmethod
    def update_display_preferences(
        db: Session,
        user_id: str,
        dark_mode: Optional[bool] = None,
        chart_type: Optional[str] = None,
    ) -> UserPreferencesDB:
        """Update display preferences."""
        user_prefs = UserRepository.get_or_create_preferences(db, user_id)
        if dark_mode is not None:
            user_prefs.dark_mode = dark_mode
        if chart_type:
            user_prefs.chart_type = chart_type
        db.commit()
        db.refresh(user_prefs)
        return user_prefs


class ErrorRepository:
    """Repository for error logging operations."""

    @staticmethod
    def store_error(
        db: Session,
        error_code: str,
        error_message: str,
        source: str,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        error_stack: Optional[str] = None,
        context: Optional[dict] = None,
        status_code: Optional[int] = None,
    ) -> ErrorLogDB:
        """Store an error log."""
        error_log = ErrorLogDB(
            error_code=error_code,
            error_message=error_message,
            source=source,
            endpoint=endpoint,
            user_id=user_id,
            request_id=request_id,
            error_stack=error_stack,
            context=context or {},
            status_code=status_code,
        )
        db.add(error_log)
        db.commit()
        db.refresh(error_log)
        return error_log

    @staticmethod
    def get_recent_errors(
        db: Session,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[ErrorLogDB]:
        """Get recent errors, optionally filtered by source."""
        query = db.query(ErrorLogDB).order_by(ErrorLogDB.created_at.desc())
        if source:
            query = query.filter(ErrorLogDB.source == source)
        return query.limit(limit).all()

    @staticmethod
    def get_error_frequency(db: Session, hours: int = 24) -> dict:
        """Get error frequency in the last N hours."""
        from sqlalchemy import func
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        errors = db.query(
            ErrorLogDB.error_code, func.count(ErrorLogDB.id)
        ).filter(ErrorLogDB.created_at >= cutoff_time).group_by(
            ErrorLogDB.error_code
        ).all()

        return {error_code: count for error_code, count in errors}


class TradeRepository:
    """Repository for trading operations."""

    @staticmethod
    def store_trade(
        db: Session,
        user_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        order_id: str,
        signal_id: Optional[int] = None,
        risk_pct: Optional[float] = None,
        fees: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit_1: Optional[float] = None,
        take_profit_2: Optional[float] = None,
        take_profit_3: Optional[float] = None,
        auto_close_enabled: bool = True,
    ) -> TradeDB:
        """Store a newly executed trade with TP/SL levels."""
        trade = TradeDB(
            user_id=user_id,
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            entry_value=entry_price * quantity,
            entry_timestamp=datetime.utcnow(),
            order_id=order_id,
            status=TradeStatus.OPEN.value,
            risk_pct=risk_pct,
            fees=fees,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            auto_close_enabled=auto_close_enabled,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        logger.info(
            f"Trade stored: {direction} {quantity} {symbol} @ ${entry_price} (SL: {stop_loss}, TP1: {take_profit_1}, TP2: {take_profit_2}, TP3: {take_profit_3})",
            action="trade_stored",
            trade_id=trade.id,
            user_id=user_id,
            symbol=symbol,
            order_id=order_id,
            stop_loss=stop_loss,
            take_profits=[take_profit_1, take_profit_2, take_profit_3],
        )
        return trade

    @staticmethod
    def get_open_trades(db: Session, user_id: str, symbol: Optional[str] = None) -> List[TradeDB]:
        """Get all open trades for a user, optionally filtered by symbol."""
        query = db.query(TradeDB).filter(
            TradeDB.user_id == user_id,
            TradeDB.status.in_([TradeStatus.OPEN.value, TradeStatus.CLOSING.value]),
        ).order_by(TradeDB.created_at.desc())

        if symbol:
            query = query.filter(TradeDB.symbol == symbol)

        return query.all()

    @staticmethod
    def get_closed_trades(
        db: Session,
        user_id: str,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[TradeDB]:
        """Get closed trades for a user, optionally filtered by symbol."""
        query = db.query(TradeDB).filter(
            TradeDB.user_id == user_id,
            TradeDB.status == TradeStatus.CLOSED.value,
        ).order_by(TradeDB.closed_at.desc())

        if symbol:
            query = query.filter(TradeDB.symbol == symbol)

        return query.limit(limit).all()

    @staticmethod
    def get_trade_by_id(db: Session, trade_id: int) -> Optional[TradeDB]:
        """Get a trade by ID."""
        return db.query(TradeDB).filter(TradeDB.id == trade_id).first()

    @staticmethod
    def get_trade_by_order_id(db: Session, order_id: str) -> Optional[TradeDB]:
        """Get a trade by Binance order ID."""
        return db.query(TradeDB).filter(TradeDB.order_id == order_id).first()

    @staticmethod
    def close_trade(
        db: Session,
        trade_id: int,
        exit_price: float,
        exit_reason: str,
        exit_quantity: Optional[float] = None,
    ) -> Optional[TradeDB]:
        """Close a trade with exit price and reason."""
        trade = db.query(TradeDB).filter(TradeDB.id == trade_id).first()
        if not trade:
            return None

        exit_qty = exit_quantity or trade.quantity
        exit_value = exit_price * exit_qty

        # Calculate P&L
        realized_pnl = exit_value - (trade.entry_price * exit_qty) - trade.fees
        realized_pnl_pct = (realized_pnl / (trade.entry_price * exit_qty)) * 100 if trade.entry_price > 0 else 0

        # Update trade
        trade.exit_price = exit_price
        trade.exit_quantity = exit_qty
        trade.exit_timestamp = datetime.utcnow()
        trade.exit_reason = exit_reason
        trade.realized_pnl = realized_pnl
        trade.realized_pnl_pct = realized_pnl_pct
        trade.status = TradeStatus.CLOSED.value

        db.commit()
        db.refresh(trade)

        logger.info(
            f"Trade closed with PnL ${realized_pnl:.2f} ({realized_pnl_pct:.2f}%)",
            action="trade_closed",
            trade_id=trade_id,
            realized_pnl=realized_pnl,
            realized_pnl_pct=realized_pnl_pct,
            exit_reason=exit_reason,
        )

        return trade

    @staticmethod
    def get_trading_performance(db: Session, user_id: str) -> dict:
        """Calculate trading performance statistics for a user."""
        closed_trades = db.query(TradeDB).filter(
            TradeDB.user_id == user_id,
            TradeDB.status == TradeStatus.CLOSED.value,
        ).all()

        if not closed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "best_trade": 0,
                "worst_trade": 0,
                "total_pnl": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "profit_factor": 0,
            }

        # Calculate statistics
        winning_trades = [t for t in closed_trades if (t.realized_pnl_pct or 0) > 0]
        losing_trades = [t for t in closed_trades if (t.realized_pnl_pct or 0) <= 0]

        total_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
        winning_pnl = sum(t.realized_pnl or 0 for t in winning_trades)
        losing_pnl = sum(abs(t.realized_pnl or 0) for t in losing_trades)

        return {
            "total_trades": len(closed_trades),
            "win_rate": (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0,
            "avg_pnl": total_pnl / len(closed_trades) if closed_trades else 0,
            "best_trade": max((t.realized_pnl_pct or 0 for t in closed_trades), default=0),
            "worst_trade": min((t.realized_pnl_pct or 0 for t in closed_trades), default=0),
            "total_pnl": total_pnl,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "profit_factor": winning_pnl / losing_pnl if losing_pnl > 0 else 0,
        }

    @staticmethod
    def get_trades_this_week(db: Session, user_id: str) -> List[TradeDB]:
        """Get trades from the last 7 days."""
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        return db.query(TradeDB).filter(
            TradeDB.user_id == user_id,
            TradeDB.created_at >= cutoff_date,
        ).order_by(TradeDB.created_at.desc()).all()


class BinanceCredentialsRepository:
    """Repository for managing encrypted Binance API credentials."""

    @staticmethod
    def store_credentials(
        db: Session,
        user_id: str,
        api_key_encrypted: str,
        api_secret_encrypted: str,
        key_hash: str,
    ) -> BinanceCredentialsDB:
        """Store or update encrypted Binance credentials for a user."""
        creds = db.query(BinanceCredentialsDB).filter(
            BinanceCredentialsDB.user_id == user_id
        ).first()

        if creds:
            # Update existing
            creds.api_key_encrypted = api_key_encrypted
            creds.api_secret_encrypted = api_secret_encrypted
            creds.key_hash = key_hash
            creds.validation_status = "UNVERIFIED"  # Reset validation status
        else:
            # Create new
            creds = BinanceCredentialsDB(
                user_id=user_id,
                api_key_encrypted=api_key_encrypted,
                api_secret_encrypted=api_secret_encrypted,
                key_hash=key_hash,
            )
            db.add(creds)

        db.commit()
        db.refresh(creds)

        logger.info(
            "Binance credentials stored",
            action="credentials_stored",
            user_id=user_id,
        )

        return creds

    @staticmethod
    def get_credentials(db: Session, user_id: str) -> Optional[BinanceCredentialsDB]:
        """Retrieve encrypted Binance credentials for a user."""
        return db.query(BinanceCredentialsDB).filter(
            BinanceCredentialsDB.user_id == user_id
        ).first()

    @staticmethod
    def update_validation_status(
        db: Session,
        user_id: str,
        is_valid: bool,
    ) -> Optional[BinanceCredentialsDB]:
        """Update validation status after testing credentials."""
        creds = db.query(BinanceCredentialsDB).filter(
            BinanceCredentialsDB.user_id == user_id
        ).first()

        if creds:
            creds.validation_status = "VERIFIED" if is_valid else "INVALID"
            creds.last_validated_at = datetime.utcnow()
            db.commit()
            db.refresh(creds)

            logger.info(
                f"Credentials validation status updated: {creds.validation_status}",
                action="credentials_validated",
                user_id=user_id,
                status=creds.validation_status,
            )

        return creds

    @staticmethod
    def update_trading_settings(
        db: Session,
        user_id: str,
        trading_enabled: Optional[bool] = None,
        trading_mode: Optional[str] = None,
    ) -> Optional[BinanceCredentialsDB]:
        """Update trading settings (enabled/disabled, paper/live mode)."""
        creds = db.query(BinanceCredentialsDB).filter(
            BinanceCredentialsDB.user_id == user_id
        ).first()

        if creds:
            if trading_enabled is not None:
                creds.trading_enabled = trading_enabled
            if trading_mode is not None and trading_mode in ["PAPER", "LIVE"]:
                creds.trading_mode = trading_mode
            db.commit()
            db.refresh(creds)

            logger.info(
                "Trading settings updated",
                action="trading_settings_updated",
                user_id=user_id,
                enabled=creds.trading_enabled,
                mode=creds.trading_mode,
            )

        return creds

    @staticmethod
    def delete_credentials(db: Session, user_id: str) -> bool:
        """Delete credentials for a user (revoke access)."""
        creds = db.query(BinanceCredentialsDB).filter(
            BinanceCredentialsDB.user_id == user_id
        ).first()

        if creds:
            db.delete(creds)
            db.commit()

            logger.info(
                "Binance credentials deleted",
                action="credentials_deleted",
                user_id=user_id,
            )

            return True

        return False


class AutoExecutionAuditRepository:
    """Repository for auto-execution audit logging."""

    @staticmethod
    def log_auto_execution(
        db: Session,
        user_id: str,
        symbol: str,
        direction: str,
        confidence_score: int,
        recovery_state: str,
        position_size_multiplier: float,
        execution_trigger: str,
        executed: bool,
        order_id: Optional[str] = None,
        entry_price: Optional[float] = None,
        quantity: Optional[float] = None,
        trading_mode: Optional[str] = None,
        execution_error: Optional[str] = None,
    ) -> AutoExecutionAuditDB:
        """Log an auto-execution attempt."""
        audit_entry = AutoExecutionAuditDB(
            user_id=user_id,
            symbol=symbol,
            direction=direction,
            confidence_score=confidence_score,
            recovery_state=recovery_state,
            position_size_multiplier=position_size_multiplier,
            execution_trigger=execution_trigger,
            executed=executed,
            order_id=order_id,
            entry_price=entry_price,
            quantity=quantity,
            trading_mode=trading_mode,
            execution_error=execution_error,
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        logger.info(
            f"Auto-execution logged: {direction} {symbol} (Confidence: {confidence_score}, Executed: {executed})",
            action="auto_execution_logged",
            user_id=user_id,
            symbol=symbol,
            confidence=confidence_score,
            executed=executed,
            audit_id=audit_entry.id,
        )

        return audit_entry

    @staticmethod
    def get_user_auto_executions(
        db: Session,
        user_id: str,
        limit: int = 100,
        days: int = 30,
    ) -> List[AutoExecutionAuditDB]:
        """Get recent auto-executions for a user."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return (
            db.query(AutoExecutionAuditDB)
            .filter(
                AutoExecutionAuditDB.user_id == user_id,
                AutoExecutionAuditDB.created_at >= cutoff_date,
            )
            .order_by(AutoExecutionAuditDB.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_auto_execution_stats(
        db: Session,
        user_id: str,
        days: int = 30,
    ) -> dict:
        """Get auto-execution statistics for a user."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        executions = (
            db.query(AutoExecutionAuditDB)
            .filter(
                AutoExecutionAuditDB.user_id == user_id,
                AutoExecutionAuditDB.created_at >= cutoff_date,
            )
            .all()
        )

        if not executions:
            return {
                "total_attempts": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "success_rate": 0.0,
                "avg_confidence": 0,
                "by_state": {},
            }

        total = len(executions)
        successful = sum(1 for e in executions if e.executed)
        failed = total - successful
        avg_confidence = sum(e.confidence_score for e in executions) / total if total > 0 else 0

        # Group by recovery state
        by_state = {}
        for execution in executions:
            state = execution.recovery_state
            if state not in by_state:
                by_state[state] = {"total": 0, "successful": 0}
            by_state[state]["total"] += 1
            if execution.executed:
                by_state[state]["successful"] += 1

        return {
            "total_attempts": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "avg_confidence": round(avg_confidence, 2),
            "by_state": by_state,
        }

    @staticmethod
    def cleanup_old_audits(db: Session, days: int = 90) -> int:
        """Delete audit logs older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = (
            db.query(AutoExecutionAuditDB)
            .filter(AutoExecutionAuditDB.created_at < cutoff_date)
            .delete()
        )
        db.commit()

        logger.info(
            f"Cleaned up {deleted} old auto-execution audit records",
            action="audit_cleanup",
            deleted_count=deleted,
            cutoff_days=days,
        )

        return deleted
