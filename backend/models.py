from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# SQLAlchemy base for ORM models
Base = declarative_base()


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, Enum):
    """Status of a trade throughout its lifecycle."""
    OPEN = "OPEN"
    CLOSING = "CLOSING"  # Partially closed
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class IndicatorStatus(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class IndicatorConfirmation(BaseModel):
    name: str
    value: float
    status: IndicatorStatus
    description: str


class TakeProfitLevel(BaseModel):
    level: int
    price: float
    rr_ratio: float
    pct_gain: float


class Signal(BaseModel):
    symbol: str
    timeframe: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profits: List[TakeProfitLevel]
    confidence: int  # 0-100
    ai_probability: float  # 0.0-1.0
    rr_ratio: float
    indicators: List[IndicatorConfirmation]
    sentiment_score: float  # -1 to 1
    volume_ratio: float
    atr: float
    timestamp: str
    candles_since_cross: int = 0
    position_size_1pct: Optional[float] = None  # position size based on 1% risk


class ScanResult(BaseModel):
    symbol: str
    timeframe: str
    direction: SignalDirection
    confidence: int
    ai_probability: float
    price: float
    change_24h: float
    volume_24h: float
    rr_ratio: float
    timestamp: str


class MarketScanResponse(BaseModel):
    signals: List[ScanResult]
    total_scanned: int
    long_count: int
    short_count: int
    scan_duration_ms: float


class FearGreedData(BaseModel):
    value: int
    classification: str
    timestamp: str


class SentimentResponse(BaseModel):
    fear_greed: FearGreedData
    overall_score: float  # -1 bearish to +1 bullish
    classification: str
    positive_pct: int = 0
    negative_pct: int = 0
    neutral_pct: int = 0
    components: dict


class BacktestResult(BaseModel):
    strategy: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    avg_trade_duration_hours: float
    total_return_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    trades: List[dict]


class CombinationResult(BaseModel):
    rank: int
    id: str
    name: str
    description: str
    filter_count: int
    filters: List[str]
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    total_return_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    avg_bars: float
    equity_curve: List[float]


class CombinationBacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    years_tested: int
    start_date: str
    end_date: str
    total_bars: int
    combinations_tested: int
    results: List[CombinationResult]
    best_combination: Optional[str]
    best_sharpe: float
    generated_at: str


class OHLCVBar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartDataResponse(BaseModel):
    symbol: str
    timeframe: str
    bars: List[OHLCVBar]
    # Main chart overlays
    ema7: List[Dict[str, Any]]
    ema25: List[Dict[str, Any]]
    bb_upper: List[Dict[str, Any]] = []
    bb_middle: List[Dict[str, Any]] = []
    bb_lower: List[Dict[str, Any]] = []
    vwap: List[Dict[str, Any]] = []
    # Sub-chart indicator data
    rsi: List[Dict[str, Any]] = []
    macd: List[Dict[str, Any]] = []
    macd_signal: List[Dict[str, Any]] = []
    macd_hist: List[Dict[str, Any]] = []
    stoch_k: List[Dict[str, Any]] = []
    stoch_d: List[Dict[str, Any]] = []
    # Volume
    volume: List[Dict[str, Any]] = []
    vol_ma: List[Dict[str, Any]] = []
    # EMA cross markers
    signals: List[Dict[str, Any]]
    # Latest snapshot for legend overlay
    latest_values: Dict[str, Any] = {}


# ============================================================================
# Trading Models (Pydantic - Request/Response)
# ============================================================================

class TradeExecutionRequest(BaseModel):
    """Request to execute a trade based on a signal."""
    symbol: str  # e.g., "BTCUSDT"
    direction: SignalDirection  # LONG or SHORT
    risk_pct: float = 2.0  # Risk as % of wallet (1-5%)
    entry_price: float  # Signal's suggested entry price
    stop_loss: Optional[float] = None  # Optional SL override
    take_profit_1: Optional[float] = None  # TP1 price level
    take_profit_2: Optional[float] = None  # TP2 price level
    take_profit_3: Optional[float] = None  # TP3 price level
    take_profits: Optional[List[TakeProfitLevel]] = None  # Optional TP override (legacy)
    signal_id: Optional[int] = None  # Link to generated signal
    auto_close_enabled: bool = True  # Enable TP/SL auto-close


class TradeResponse(BaseModel):
    """Response when trade is executed."""
    order_id: str  # Binance order ID
    symbol: str
    direction: SignalDirection
    entry_price: float
    quantity: float
    total_value: float  # quantity * entry_price
    status: str  # "EXECUTED", "PENDING", etc.
    timestamp: str
    message: str


class APIKeyValidationRequest(BaseModel):
    """Request to validate Binance API keys."""
    api_key: str
    api_secret: str


class APIKeyValidationResponse(BaseModel):
    """Response from API key validation."""
    valid: bool
    balance_usdt: Optional[float] = None
    connected: bool
    error: Optional[str] = None


class OpenOrderResponse(BaseModel):
    """Open trade/order details."""
    id: int  # Database trade ID
    order_id: str  # Binance order ID
    symbol: str
    direction: SignalDirection
    entry_price: float
    quantity: float
    entry_value: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_timestamp: str
    status: str


class TradeHistoryResponse(BaseModel):
    """Closed trade details."""
    id: int
    symbol: str
    direction: SignalDirection
    entry_price: float
    exit_price: float
    quantity: float
    entry_value: float
    exit_value: float
    realized_pnl: float
    realized_pnl_pct: float
    exit_reason: Optional[str]
    entry_timestamp: str
    exit_timestamp: str
    duration_hours: float


class CloseTradeRequest(BaseModel):
    """Request to close an open trade."""
    trade_id: int
    exit_price: Optional[float] = None  # If None, use market close at current price
    exit_reason: str = "MANUAL_EXIT"  # e.g., "MANUAL_EXIT", "TP1", "TP2", "TP3", "STOP_LOSS"


class CloseTradeResponse(BaseModel):
    """Response when trade is closed."""
    id: int
    symbol: str
    direction: SignalDirection
    entry_price: float
    exit_price: float
    quantity: float
    entry_value: float
    exit_value: float
    realized_pnl: float
    realized_pnl_pct: float
    exit_reason: str
    duration_hours: float
    status: str  # "CLOSED"
    timestamp: str
    message: str


class ModifyTPSLRequest(BaseModel):
    """Request to modify TP/SL levels."""
    trade_id: int
    stop_loss: Optional[float] = None  # New SL price (or None to keep)
    take_profit_1: Optional[float] = None  # New TP1 price
    take_profit_2: Optional[float] = None  # New TP2 price
    take_profit_3: Optional[float] = None  # New TP3 price


class ModifyTPSLResponse(BaseModel):
    """Response when TP/SL levels are modified."""
    id: int
    symbol: str
    direction: SignalDirection
    entry_price: float
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    status: str
    timestamp: str
    message: str


# ============================================================================
# Database ORM Models (SQLAlchemy)
# ============================================================================

class SignalHistoryDB(Base):
    """Stores all generated signals for performance tracking and analysis."""
    __tablename__ = "signals_history"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)  # LONG or SHORT
    confidence = Column(Integer, nullable=False)  # 0-100
    ai_probability = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profits = Column(JSON, nullable=False)  # List of TP levels
    rr_ratio = Column(Float, nullable=False)
    indicators = Column(JSON, nullable=False)  # List of indicator confirmations
    sentiment_score = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)

    # Performance tracking (updated when signal resolves)
    entry_executed_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True)  # STOP_LOSS, TP1, TP2, etc.
    pnl_pct = Column(Float, nullable=True)  # Realized P&L as percentage
    is_closed = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<SignalHistoryDB {self.symbol} {self.direction} @{self.entry_price}>"


class UserPreferencesDB(Base):
    """Stores user settings and preferences."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)

    # Notification preferences
    alert_symbols = Column(JSON, default=list)  # List of symbols to alert on
    alert_timeframes = Column(JSON, default=list)  # List of timeframes (1h, 4h, 1d, etc.)
    alert_min_confidence = Column(Integer, default=60)  # Only alert if confidence >= this

    # Display preferences
    preferred_timeframes = Column(JSON, default=lambda: ["1h", "4h", "1d"])
    preferred_symbols = Column(JSON, default=list)
    chart_type = Column(String(20), default="candlestick")
    dark_mode = Column(Boolean, default=False)

    # Strategy preferences
    preferred_strategy = Column(String(50), default="ema_cross")
    max_drawdown_tolerance = Column(Float, default=20.0)  # Max acceptable drawdown %
    min_win_rate = Column(Float, default=40.0)  # Min acceptable win rate %

    # API preferences
    api_key_last_used = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<UserPreferencesDB {self.user_id}>"


class ErrorLogDB(Base):
    """Stores frontend and backend errors for monitoring and debugging."""
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True)
    error_code = Column(String(50), nullable=False)
    error_message = Column(String(500), nullable=False)
    error_stack = Column(String(5000), nullable=True)

    source = Column(String(20), nullable=False)  # frontend or backend
    endpoint = Column(String(200), nullable=True)
    user_id = Column(String(100), nullable=True, index=True)
    request_id = Column(String(36), nullable=True, index=True)

    context = Column(JSON, default=dict)  # Additional context (user agent, browser, etc.)
    status_code = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<ErrorLogDB {self.error_code} {self.source}>"


class TradeDB(Base):
    """Stores executed trades for performance tracking and P&L calculation."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    signal_id = Column(Integer, nullable=True, index=True)  # Link to original signal (if any)

    # Entry details
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # LONG or SHORT
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)  # Amount of asset traded
    entry_value = Column(Float, nullable=False)  # price * quantity (in USDT)
    entry_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    order_id = Column(String(50), nullable=False, unique=True)  # Binance order ID

    # Stop Loss & Take Profit levels
    stop_loss = Column(Float, nullable=True)  # SL price
    take_profit_1 = Column(Float, nullable=True)  # TP1 price
    take_profit_2 = Column(Float, nullable=True)  # TP2 price
    take_profit_3 = Column(Float, nullable=True)  # TP3 price
    tp_triggered = Column(String(10), nullable=True)  # Which TP level was hit (TP1, TP2, TP3)

    # Exit details (nullable until trade is closed)
    exit_price = Column(Float, nullable=True)
    exit_quantity = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime(timezone=True), nullable=True)
    exit_reason = Column(String(50), nullable=True)  # TP1, TP2, TP3, STOP_LOSS, MANUAL_EXIT

    # P&L calculation
    realized_pnl = Column(Float, nullable=True)  # Gross profit/loss in USDT
    realized_pnl_pct = Column(Float, nullable=True)  # Percentage return

    # Status and metadata
    status = Column(String(20), nullable=False, default="OPEN", index=True)  # OPEN, CLOSED, CANCELLED
    risk_pct = Column(Float, nullable=True)  # User's risk % setting at time of trade
    fees = Column(Float, default=0.0)  # Trading fees paid
    notes = Column(String(500), nullable=True)  # Additional trade notes
    auto_close_enabled = Column(Boolean, default=True)  # Enable TP/SL auto-close

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        status_indicator = "✓" if self.status == "CLOSED" else "○"
        return f"<TradeDB {status_indicator} {self.symbol} {self.direction} @{self.entry_price}>"


class BinanceCredentialsDB(Base):
    """Stores encrypted Binance API credentials per user."""
    __tablename__ = "binance_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)

    # Encrypted credentials (stored as encrypted strings)
    api_key_encrypted = Column(String(1000), nullable=False)  # Encrypted API key
    api_secret_encrypted = Column(String(1000), nullable=False)  # Encrypted API secret
    key_hash = Column(String(64), nullable=False)  # SHA256 hash of API key for verification

    # Metadata
    trading_enabled = Column(Boolean, default=True)
    trading_mode = Column(String(10), default="PAPER")  # PAPER or LIVE
    auto_execution_enabled = Column(Boolean, default=False)  # Auto-execute signals >= 85 confidence
    wallet_balance = Column(Float, default=10000.0)  # Virtual balance for paper trading
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_status = Column(String(20), default="UNVERIFIED")  # VERIFIED, UNVERIFIED, INVALID

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        status = "✓" if self.validation_status == "VERIFIED" else "✗"
        return f"<BinanceCredentialsDB {status} {self.user_id} ({self.trading_mode})>"


class AutoExecutionAuditDB(Base):
    """Audit log for all auto-executed trades."""
    __tablename__ = "auto_execution_audit"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)  # LONG or SHORT
    confidence_score = Column(Integer, nullable=False)
    recovery_state = Column(String(20), nullable=False)  # ACTIVE, CAUTION, RECOVERY, PAUSED
    position_size_multiplier = Column(Float, nullable=False)
    execution_trigger = Column(String(50), nullable=False)  # ExecutionTrigger enum value
    executed = Column(Boolean, nullable=False, default=False)
    execution_error = Column(String(500), nullable=True)
    order_id = Column(String(100), nullable=True)
    entry_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    trading_mode = Column(String(10), nullable=True)  # PAPER or LIVE
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index('idx_auto_execution_user_symbol', 'user_id', 'symbol', 'created_at'),
    )

    def __repr__(self):
        status = "✓" if self.executed else "✗"
        return f"<AutoExecutionAudit {status} {self.user_id} {self.symbol} {self.direction} (Confidence: {self.confidence_score})>"
