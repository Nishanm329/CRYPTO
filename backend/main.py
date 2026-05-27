"""
FastAPI backend — CryptoSignal AI
All routes serve the Next.js frontend.
"""
from fastapi import FastAPI, HTTPException, Query, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio
import json
import pandas as pd
from datetime import datetime
from typing import Optional
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from binance_client import (
    get_klines,
    get_fear_greed_index,
    get_top_volume_pairs,
    batch_get_tickers,
    get_all_usdt_pairs,
)
from indicators import add_all_indicators, calculate_stoch_rsi
from signals import generate_signal
from scanner import scan_market
from backtester import run_backtest
from combination_backtester import run_combination_backtest
from auto_execution_engine import AutoExecutionEngine
from drawdown_recovery import DrawdownCalculator, RecoveryProtocol
from crypto_utils import APIKeyVault
from binance_trade_client import BinanceTradeClient
from trade_validator import TradeValidator, PaperTradingSimulator, TradeValidationError
from tp_sl_automation import initialize_tp_sl_automation, shutdown_tp_sl_automation
from order_status_poller import initialize_order_status_poller, shutdown_order_status_poller
from tp_sl_modifier import TPSLModifier, TPSLModificationError
from binance_order_webhook import WebSocketManager
from models import (
    ChartDataResponse,
    OHLCVBar,
    SentimentResponse,
    FearGreedData,
    CombinationBacktestResponse,
    Signal,
    TradeExecutionRequest,
    TradeResponse,
    APIKeyValidationRequest,
    APIKeyValidationResponse,
    OpenOrderResponse,
    TradeHistoryResponse,
    CloseTradeRequest,
    CloseTradeResponse,
    ModifyTPSLRequest,
    ModifyTPSLResponse,
    TradeStatus,
)
from validators import validate_symbol, validate_timeframe, validate_max_pairs
from logging_config import setup_logging, get_logger
from request_tracing import RequestTracingMiddleware, get_request_id
from metrics import MetricsMiddleware, registry, track_signal, track_scan
from db import init_db, get_db, SessionLocal
from repositories import SignalRepository, UserRepository, ErrorRepository, TradeRepository, BinanceCredentialsRepository, AutoExecutionAuditRepository
from security import authenticate_request, APIKeyManager
from config import config

# Initialize structured logging
setup_logging()
logger = get_logger(__name__)

# Validate configuration on startup
try:
    config.validate()
    logger.info(
        "Configuration validated",
        action="config_validated",
        environment=config.ENV,
    )
except ValueError as e:
    logger.error(f"Configuration validation failed: {e}", action="config_validation_failed", exc_info=True)
    raise

app = FastAPI(
    title="CryptoSignal AI",
    version="2.0.0",
    description="Expert crypto trading signals — 7/25 EMA + multi-indicator confluence",
)

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add gzip compression middleware (min size 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Add request tracing middleware
app.add_middleware(RequestTracingMiddleware)

# Add metrics collection middleware
app.add_middleware(MetricsMiddleware)

VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"}

# Global WebSocket manager for real-time order updates
websocket_manager = WebSocketManager()


# ── Database Initialization ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize database, API keys, and TP/SL automation on startup."""
    try:
        init_db()
    except Exception as e:
        logger.warning(
            f"Database initialization failed (continuing without DB): {e}",
            action="db_init_failed",
            error=str(e),
        )
    try:
        APIKeyManager.load_keys()
    except Exception as e:
        logger.warning(
            f"API key loading failed: {e}",
            action="api_key_load_failed",
            error=str(e),
        )

    # Initialize TP/SL automation engine (checks trades every 60 seconds)
    try:
        await initialize_tp_sl_automation(check_interval_seconds=60)
    except Exception as e:
        logger.warning(
            f"TP/SL automation initialization failed: {e}",
            action="tp_sl_init_failed",
            error=str(e),
        )

    # Initialize order status poller (checks order fills every 30 seconds)
    try:
        await initialize_order_status_poller(check_interval_seconds=30, max_age_minutes=60)
    except Exception as e:
        logger.warning(
            f"Order status poller initialization failed: {e}",
            action="poller_init_failed",
            error=str(e),
        )

    logger.info("Application startup", action="app_startup", status="initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    try:
        await shutdown_tp_sl_automation()
    except Exception as e:
        logger.warning(
            f"TP/SL automation shutdown failed: {e}",
            action="tp_sl_shutdown_failed",
            error=str(e),
        )

    try:
        await shutdown_order_status_poller()
    except Exception as e:
        logger.warning(
            f"Order status poller shutdown failed: {e}",
            action="poller_shutdown_failed",
            error=str(e),
        )

    try:
        await websocket_manager.stop_all()
    except Exception as e:
        logger.warning(
            f"WebSocket manager shutdown failed: {e}",
            action="websocket_shutdown_failed",
            error=str(e),
        )

    logger.info("Application shutdown", action="app_shutdown", status="complete")


# ── Authentication Dependency ───────────────────────────────────────────────

async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> tuple[str, dict]:
    """
    Dependency for authenticating API requests.
    Extracts and validates API key from Authorization header.

    Returns:
        (user_id, quota_info)
    """
    return authenticate_request(authorization)


# ── Health & Monitoring ─────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/errors")
async def log_frontend_error(
    request: Request,
    error_data: dict,
    authorization: Optional[str] = Header(None),
):
    """
    Endpoint for frontend error logging (Sentry alternative).
    Logs client-side errors to the backend for centralized tracking.
    Optional authentication for per-user tracking.
    """
    request_id = get_request_id(request)
    user_id = None

    # Try to authenticate, but don't fail if missing
    if authorization:
        try:
            user_id, _ = authenticate_request(authorization)
        except:
            pass  # Error logging should not require auth

    logger.error(
        f"Frontend error: {error_data.get('message', 'Unknown error')}",
        request_id=request_id,
        user_id=user_id,
        error_type=error_data.get('type'),
        url=error_data.get('url'),
        stack=error_data.get('stack')[:200] if error_data.get('stack') else None,
    )

    # Store in database if user authenticated
    if user_id:
        try:
            db = SessionLocal()
            ErrorRepository.store_error(
                db,
                error_code=error_data.get('type', 'UNKNOWN'),
                error_message=error_data.get('message', 'Unknown error'),
                source="frontend",
                user_id=user_id,
                request_id=request_id,
                error_stack=error_data.get('stack'),
                context={"url": error_data.get('url')},
            )
            db.close()
        except Exception as e:
            logger.warning(f"Failed to store error in DB: {e}")

    return {"status": "logged", "request_id": request_id}


# ── Market Scanner ──────────────────────────────────────────────────────────

@app.get("/api/scan")
@limiter.limit("30/minute")
async def scan_endpoint(
    request: Request,
    timeframe: str = Query("1h", description="Candle interval"),
    max_pairs: int = Query(50, ge=10, le=200),
    min_confidence: int = Query(45, ge=0, le=100),
):
    # Validate inputs
    try:
        timeframe = validate_timeframe(timeframe)
        max_pairs = validate_max_pairs(max_pairs)
        if not (0 <= min_confidence <= 100):
            raise ValueError("min_confidence must be between 0 and 100")
    except ValueError as e:
        raise HTTPException(400, str(e))

    result = await scan_market(timeframe, max_pairs, min_confidence, use_cache=True)
    return result


# ── Single Symbol Signal ─────────────────────────────────────────────────────

@app.get("/api/signal/{symbol}")
@limiter.limit("60/minute")
async def signal_endpoint(
    request: Request,
    symbol: str,
    timeframe: str = Query("1h"),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    user_id, quota_info = auth
    request_id = get_request_id(request)

    # Validate inputs
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        df = await get_klines(symbol, timeframe, limit=300)
    except Exception as e:
        print(f"[signal] Error fetching klines for {symbol}/{timeframe}: {e}", flush=True)
        raise HTTPException(404, f"Symbol {symbol} not found: {e}")

    try:
        fg = await get_fear_greed_index()
    except Exception as e:
        print(f"[signal] Error fetching fear/greed: {e}", flush=True)
        fg = {"value": 50, "classification": "Neutral"}

    sentiment_score = (fg.get("value", 50) - 50) / 50

    signal = generate_signal(df, symbol, timeframe, sentiment_score)
    if signal is None:
        print(f"[signal] No EMA cross signal for {symbol}/{timeframe}", flush=True)
        raise HTTPException(
            404, f"No EMA cross signal detected for {symbol} on {timeframe}"
        )

    # Store signal in database for performance tracking
    try:
        SignalRepository.store_signal(db, signal)
        track_signal(signal.symbol, signal.direction.value)
    except Exception as e:
        logger.warning(
            f"Signal storage failed for {signal.symbol}: {e}",
            action="signal_storage_failed",
            symbol=signal.symbol,
            error=str(e),
        )

    # ─── Auto-Execution Logic ──────────────────────────────────────────────────
    auto_execution_decision = None
    auto_executed = False
    auto_execution_error = None
    audit_repo = AutoExecutionAuditRepository()

    try:
        # Get user's trading settings and auto-execution preference
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)

        if trading_settings and trading_settings.auto_execution_enabled and trading_settings.trading_enabled:
            # Calculate current drawdown recovery state
            user_repo = UserRepository()
            closed_trades = user_repo.get_user_trades(db, user_id, status="CLOSED")
            current_balance = trading_settings.wallet_balance

            # Get drawdown metrics from closed trades
            drawdown_metrics = DrawdownCalculator.calculate_metrics(
                trades=[
                    {
                        "pnl": t.pnl if hasattr(t, 'pnl') else 0,
                        "pnl_pct": (t.pnl / t.entry_value * 100) if hasattr(t, 'pnl') and t.entry_value else 0,
                        "entry_timestamp": t.entry_timestamp if hasattr(t, 'entry_timestamp') else datetime.utcnow(),
                        "exit_timestamp": t.exit_timestamp if hasattr(t, 'exit_timestamp') else datetime.utcnow(),
                    }
                    for t in (closed_trades or [])
                ],
                current_balance=current_balance,
            )

            # Get recovery state
            recovery_state = RecoveryProtocol.get_state(drawdown_metrics.current_drawdown_pct).value

            # Determine if signal should auto-execute
            auto_execution_decision = AutoExecutionEngine.should_auto_execute(
                signal_confidence=signal.confidence,
                recovery_state=recovery_state,
                auto_execution_enabled=True,
                user_mode=trading_settings.trading_mode,
            )

            # Execute trade if decision is positive
            if auto_execution_decision.should_execute:
                try:
                    trade_req = TradeExecutionRequest(
                        symbol=signal.symbol,
                        direction=signal.direction,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profits[0].price if signal.take_profits else signal.entry_price * 1.02,
                        risk_pct=2.0,  # Default 2% risk per auto-executed trade
                        confidence=signal.confidence,
                    )

                    # Execute the trade (using same logic as POST /api/trading/execute)
                    trading_mode = trading_settings.trading_mode

                    if trading_mode == "PAPER":
                        # Simulate market order execution
                        simulated_order = PaperTradingSimulator.simulate_market_order(
                            symbol=signal.symbol,
                            side="BUY" if signal.direction.value == "LONG" else "SELL",
                            quantity=int(current_balance * (2.0 / 100) / signal.entry_price),
                            current_price=signal.entry_price,
                        )
                        order_id = simulated_order["clientOrderId"]
                    else:  # LIVE mode
                        # Execute real market order on Binance
                        decrypted_secret = APIKeyVault.retrieve_credentials(db, user_id)
                        if decrypted_secret:
                            trade_client = BinanceTradeClient(decrypted_secret["api_key"], decrypted_secret["api_secret"])
                            quantity = int(current_balance * (2.0 / 100) / signal.entry_price)
                            order_response = trade_client.place_market_order(
                                symbol=signal.symbol,
                                side="BUY" if signal.direction.value == "LONG" else "SELL",
                                quantity=quantity,
                            )
                            order_id = order_response.get("orderId", "unknown")
                        else:
                            raise HTTPException(400, "Failed to retrieve trading credentials.")

                    auto_executed = True
                    logger.info(
                        f"Auto-execution triggered: {signal.direction.value} {signal.symbol} (Confidence: {signal.confidence})",
                        action="auto_execution_triggered",
                        user_id=user_id,
                        symbol=signal.symbol,
                        confidence=signal.confidence,
                        recovery_state=recovery_state,
                        order_id=order_id if auto_executed else None,
                        request_id=request_id,
                    )

                except Exception as e:
                    auto_execution_error = str(e)
                    logger.warning(
                        f"Auto-execution failed: {e}",
                        action="auto_execution_failed",
                        user_id=user_id,
                        symbol=signal.symbol,
                        error=str(e),
                        request_id=request_id,
                    )

    except Exception as e:
        logger.warning(
            f"Auto-execution check failed: {e}",
            action="auto_execution_check_error",
            user_id=user_id,
            symbol=signal.symbol,
            error=str(e),
            request_id=request_id,
        )

    # ─── Log Auto-Execution Attempt to Audit Table ────────────────────────────
    if auto_execution_decision and trading_settings:
        try:
            audit_repo.log_auto_execution(
                db=db,
                user_id=user_id,
                symbol=signal.symbol,
                direction=signal.direction.value,
                confidence_score=signal.confidence,
                recovery_state=recovery_state if 'recovery_state' in locals() else "UNKNOWN",
                position_size_multiplier=auto_execution_decision.position_size_multiplier,
                execution_trigger=auto_execution_decision.trigger.value,
                executed=auto_executed,
                order_id=None if not auto_executed else getattr(locals().get('order_id'), None),
                entry_price=signal.entry_price,
                quantity=None,  # TODO: Calculate from position size
                trading_mode=trading_settings.trading_mode if trading_settings else None,
                execution_error=auto_execution_error,
            )
        except Exception as e:
            logger.warning(
                f"Failed to log auto-execution audit: {e}",
                action="auto_execution_audit_failed",
                user_id=user_id,
                symbol=signal.symbol,
                error=str(e),
            )

    # Add auto-execution metadata to response
    response = signal.dict()
    if auto_execution_decision:
        response["auto_execution"] = {
            "enabled": trading_settings.auto_execution_enabled if trading_settings else False,
            "should_execute": auto_execution_decision.should_execute,
            "trigger": auto_execution_decision.trigger.value,
            "position_size_multiplier": auto_execution_decision.position_size_multiplier,
            "reason": auto_execution_decision.reason,
            "risk_level": auto_execution_decision.risk_level,
            "executed": auto_executed,
            "error": auto_execution_error,
        }

    return response


# ── Chart Data ───────────────────────────────────────────────────────────────

@app.get("/api/chart/{symbol}")
@limiter.limit("60/minute")
async def chart_endpoint(
    request: Request,
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(100, ge=50, le=500),
    auth: tuple = Depends(get_current_user),
):
    user_id, quota_info = auth
    # Validate inputs
    try:
        symbol = validate_symbol(symbol)
        timeframe = validate_timeframe(timeframe)
        if not (50 <= limit <= 500):
            raise ValueError("limit must be between 50 and 500")
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        df = await get_klines(symbol, timeframe, limit=limit)
    except Exception as e:
        raise HTTPException(404, str(e))

    df = add_all_indicators(df)

    # Add StochRSI
    stoch_k, stoch_d = calculate_stoch_rsi(df["rsi"])
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d

    # Convert index back to column for serialization
    df_reset = df.reset_index()

    def safe_val(v, decimals=6):
        """Return rounded float or None for NaN values."""
        if pd.isna(v):
            return None
        return round(float(v), decimals)

    bars = []
    ema7_data = []
    ema25_data = []
    bb_upper_data = []
    bb_middle_data = []
    bb_lower_data = []
    vwap_data = []
    rsi_data = []
    macd_data = []
    macd_signal_data = []
    macd_hist_data = []
    stoch_k_data = []
    stoch_d_data = []
    volume_data = []
    vol_ma_data = []
    signal_markers = []

    for _, row in df_reset.iterrows():
        ts = int(row["timestamp"].timestamp())

        bars.append(OHLCVBar(
            time=ts,
            open=round(row["open"], 6),
            high=round(row["high"], 6),
            low=round(row["low"], 6),
            close=round(row["close"], 6),
            volume=round(row["volume"], 2),
        ))

        # Volume histogram (color by up/down candle)
        is_up = row["close"] >= row["open"]
        volume_data.append({
            "time": ts,
            "value": round(row["volume"], 2),
            "color": "rgba(34,197,94,0.5)" if is_up else "rgba(239,68,68,0.5)",
        })

        # EMA lines
        if safe_val(row["ema7"]) is not None:
            ema7_data.append({"time": ts, "value": safe_val(row["ema7"])})
        if safe_val(row["ema25"]) is not None:
            ema25_data.append({"time": ts, "value": safe_val(row["ema25"])})

        # Bollinger Bands
        if safe_val(row["bb_upper"]) is not None:
            bb_upper_data.append({"time": ts, "value": safe_val(row["bb_upper"])})
            bb_middle_data.append({"time": ts, "value": safe_val(row["bb_middle"])})
            bb_lower_data.append({"time": ts, "value": safe_val(row["bb_lower"])})

        # VWAP
        if safe_val(row["vwap"]) is not None:
            vwap_data.append({"time": ts, "value": safe_val(row["vwap"])})

        # RSI
        if safe_val(row["rsi"], 2) is not None:
            rsi_data.append({"time": ts, "value": safe_val(row["rsi"], 2)})

        # MACD
        if safe_val(row["macd"], 8) is not None:
            macd_data.append({"time": ts, "value": safe_val(row["macd"], 8)})
            macd_signal_data.append({"time": ts, "value": safe_val(row["macd_signal"], 8)})
            hist_val = safe_val(row["macd_hist"], 8)
            macd_hist_data.append({
                "time": ts,
                "value": hist_val,
                "color": "#22c55e" if (hist_val or 0) >= 0 else "#ef4444",
            })

        # StochRSI
        if safe_val(row["stoch_k"], 2) is not None:
            stoch_k_data.append({"time": ts, "value": safe_val(row["stoch_k"], 2)})
        if safe_val(row["stoch_d"], 2) is not None:
            stoch_d_data.append({"time": ts, "value": safe_val(row["stoch_d"], 2)})

        # Volume MA
        if safe_val(row["vol_ma20"], 2) is not None:
            vol_ma_data.append({"time": ts, "value": safe_val(row["vol_ma20"], 2)})

    # Detect EMA cross markers
    for i in range(1, len(df_reset)):
        prev = df_reset.iloc[i - 1]
        curr = df_reset.iloc[i]
        if pd.isna(prev["ema7"]) or pd.isna(curr["ema7"]):
            continue
        prev_above = prev["ema7"] > prev["ema25"]
        curr_above = curr["ema7"] > curr["ema25"]
        ts = int(curr["timestamp"].timestamp())
        if not prev_above and curr_above:
            signal_markers.append({
                "time": ts,
                "position": "belowBar",
                "color": "#22c55e",
                "shape": "arrowUp",
                "text": "LONG",
            })
        elif prev_above and not curr_above:
            signal_markers.append({
                "time": ts,
                "position": "aboveBar",
                "color": "#ef4444",
                "shape": "arrowDown",
                "text": "SHORT",
            })

    # Latest values for overlay legend
    latest = df_reset.iloc[-1]
    latest_values = {
        "ema7": safe_val(latest.get("ema7")),
        "ema25": safe_val(latest.get("ema25")),
        "vwap": safe_val(latest.get("vwap")),
        "bb_upper": safe_val(latest.get("bb_upper")),
        "bb_middle": safe_val(latest.get("bb_middle")),
        "bb_lower": safe_val(latest.get("bb_lower")),
        "rsi": safe_val(latest.get("rsi"), 2),
        "macd": safe_val(latest.get("macd"), 8),
        "macd_signal": safe_val(latest.get("macd_signal"), 8),
        "macd_hist": safe_val(latest.get("macd_hist"), 8),
        "stoch_k": safe_val(latest.get("stoch_k"), 2),
        "stoch_d": safe_val(latest.get("stoch_d"), 2),
        "vol_ratio": safe_val(latest.get("vol_ratio"), 2),
        "atr": safe_val(latest.get("atr")),
    }

    response_data = ChartDataResponse(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        ema7=ema7_data,
        ema25=ema25_data,
        bb_upper=bb_upper_data,
        bb_middle=bb_middle_data,
        bb_lower=bb_lower_data,
        vwap=vwap_data,
        rsi=rsi_data,
        macd=macd_data,
        macd_signal=macd_signal_data,
        macd_hist=macd_hist_data,
        stoch_k=stoch_k_data,
        stoch_d=stoch_d_data,
        volume=volume_data,
        vol_ma=vol_ma_data,
        signals=signal_markers,
        latest_values=latest_values,
    )

    # Return with aggressive caching headers (30 minutes for stable data)
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": "public, max-age=1800, stale-while-revalidate=3600"}
    )


# ── Sentiment ─────────────────────────────────────────────────────────────────

@app.get("/api/sentiment")
async def sentiment_endpoint():
    fg = await get_fear_greed_index()
    fg_value = fg.get("value", 50)
    fg_class = fg.get("classification", "Neutral")

    fg_normalized = (fg_value - 50) / 50  # -1 to +1

    if fg_normalized > 0.3:
        classification = "Bullish"
    elif fg_normalized < -0.3:
        classification = "Bearish"
    else:
        classification = "Neutral"

    # Estimate positive/negative/neutral breakdown from fear/greed
    positive_pct = max(10, min(90, fg_value))
    negative_pct = max(10, min(90, 100 - fg_value))
    neutral_pct = max(0, 100 - positive_pct - negative_pct // 2)

    response_data = SentimentResponse(
        fear_greed=FearGreedData(
            value=fg_value,
            classification=fg_class,
            timestamp=fg.get("timestamp", datetime.utcnow().isoformat()),
        ),
        overall_score=round(fg_normalized, 3),
        classification=classification,
        positive_pct=positive_pct,
        negative_pct=negative_pct // 2,
        neutral_pct=neutral_pct,
        components={
            "fear_greed": {"value": fg_value, "weight": 0.4},
            "social_media": {"value": "N/A", "weight": 0.3},
            "news": {"value": "N/A", "weight": 0.3},
        },
    )

    # Cache sentiment data (5 minutes - updates hourly from external source)
    return JSONResponse(
        content=response_data.model_dump(),
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=600"}
    )


# ── Market Overview ───────────────────────────────────────────────────────────

@app.get("/api/market-overview")
@limiter.limit("20/minute")
async def market_overview_endpoint(request: Request):
    """Get BTC, ETH, and global market stats. Returns partial data if some sources fail."""
    ticker_data = {}
    fg = {"value": 50, "classification": "Neutral"}

    # Fetch ticker data with graceful fallback
    try:
        ticker_data = await batch_get_tickers(["BTCUSDT", "ETHUSDT"])
    except Exception as e:
        print(f"[market-overview] Error fetching tickers: {e}", flush=True)
        ticker_data = {"BTCUSDT": {}, "ETHUSDT": {}}

    # Fetch fear/greed with graceful fallback
    try:
        fg = await get_fear_greed_index()
    except Exception as e:
        print(f"[market-overview] Error fetching fear/greed: {e}", flush=True)

    btc = ticker_data.get("BTCUSDT", {})
    eth = ticker_data.get("ETHUSDT", {})

    # BTC.D approximation: use a fixed estimate since we can't get on-chain data
    btc_price = float(btc.get("lastPrice", 0)) or 0
    btc_change = float(btc.get("priceChangePercent", 0)) or 0
    eth_price = float(eth.get("lastPrice", 0)) or 0
    eth_change = float(eth.get("priceChangePercent", 0)) or 0

    # Rough BTC dominance estimate
    btc_d = 54.0 + (btc_change - eth_change) * 0.2 if (btc_price and eth_price) else 54.0
    btc_d = round(max(40, min(70, btc_d)), 2)

    # Total crypto market cap estimate
    total_mcap = round(btc_price * 19700000 / btc_d * 100 / 1e12, 2) if btc_d else 0

    response_data = {
        "btc": {
            "price": round(btc_price, 2),
            "change_24h": round(btc_change, 2),
            "volume_24h": round(float(btc.get("quoteVolume", 0) or 0) / 1e9, 2),
        },
        "eth": {
            "price": round(eth_price, 2),
            "change_24h": round(eth_change, 2),
            "volume_24h": round(float(eth.get("quoteVolume", 0) or 0) / 1e9, 2),
        },
        "btc_dominance": btc_d,
        "btc_dominance_change": round((btc_change - eth_change) * 0.1, 2),
        "total_mcap_trillions": total_mcap,
        "total_mcap_change": round((btc_change + eth_change) / 2, 2),
        "fear_greed": fg.get("value", 50),
        "fear_greed_label": fg.get("classification", "Neutral"),
    }

    # Cache market overview (2 minutes - updates frequently)
    return JSONResponse(
        content=response_data,
        headers={"Cache-Control": "public, max-age=120, stale-while-revalidate=240"}
    )


# ── Backtesting ──────────────────────────────────────────────────────────────

@app.get("/api/backtest/{symbol}")
async def backtest_endpoint(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(500, ge=100, le=1000),
    atr_sl: float = Query(2.0, ge=0.5, le=5.0),
    atr_tp: float = Query(3.0, ge=1.0, le=10.0),
):
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, "Invalid timeframe")

    symbol = symbol.upper()
    try:
        result = await run_backtest(symbol, timeframe, atr_sl, atr_tp, limit)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Combination Backtest ─────────────────────────────────────────────────────

@app.get("/api/backtest/combinations/{symbol}", response_model=CombinationBacktestResponse)
async def combination_backtest_endpoint(
    symbol: str,
    timeframe: str = Query("1d", description="Candle interval (1d or 4h recommended)"),
    years: int = Query(6, ge=1, le=10, description="Years of history to test (1-10)"),
    atr_sl: float = Query(2.0, ge=0.5, le=5.0),
    atr_tp: float = Query(3.0, ge=1.0, le=10.0),
):
    """
    Run 12 indicator filter combinations on historical data and return
    a ranked leaderboard sorted by Sharpe ratio.
    Note: fetching years of daily data from Binance API typically completes in 10–30 seconds.
    """
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, "Invalid timeframe")

    symbol = symbol.upper()
    try:
        result = await run_combination_backtest(symbol, timeframe, years, atr_sl, atr_tp)
        return result
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Ticker / Prices ──────────────────────────────────────────────────────────

@app.get("/api/tickers")
async def tickers_endpoint(symbols: Optional[str] = None):
    """Get 24h ticker data for a comma-separated list of symbols."""
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        sym_list = await get_top_volume_pairs(20)

    data = await batch_get_tickers(sym_list)
    return {
        s: {
            "price": float(data[s]["lastPrice"]),
            "change_24h": float(data[s]["priceChangePercent"]),
            "volume_24h": float(data[s]["quoteVolume"]),
            "high_24h": float(data[s]["highPrice"]),
            "low_24h": float(data[s]["lowPrice"]),
        }
        for s in sym_list
        if s in data
    }


@app.get("/api/pairs")
async def pairs_endpoint():
    """Return all available USDT pairs."""
    pairs = await get_all_usdt_pairs()
    return {"pairs": pairs, "total": len(pairs)}


# ── Signal History & User Preferences ───────────────────────────────────────

@app.get("/api/signals/history")
@limiter.limit("120/minute")
async def signals_history(
    request: Request,
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    user_id, quota_info = auth
    """Get historical signals with optional symbol filter."""
    signals = SignalRepository.get_recent_signals(db, symbol=symbol, limit=limit)
    return {
        "signals": [
            {
                "id": s.id,
                "symbol": s.symbol,
                "timeframe": s.timeframe,
                "direction": s.direction,
                "confidence": s.confidence,
                "entry_price": s.entry_price,
                "created_at": s.created_at.isoformat(),
                "is_closed": s.is_closed,
                "pnl_pct": s.pnl_pct,
            }
            for s in signals
        ],
        "total": len(signals),
    }


@app.get("/api/signals/performance")
@limiter.limit("120/minute")
async def signals_performance(
    request: Request,
    symbol: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    user_id, quota_info = auth
    """Get performance statistics from closed signals."""
    stats = SignalRepository.get_performance_stats(db, symbol=symbol)
    return stats


@app.get("/api/preferences/{user_id}")
@limiter.limit("120/minute")
async def get_preferences(
    request: Request,
    user_id: str,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    current_user_id, quota_info = auth
    # Only allow users to view their own preferences
    if current_user_id != user_id:
        raise HTTPException(403, "Not authorized to view this user's preferences")
    """Get user preferences."""
    prefs = UserRepository.get_or_create_preferences(db, user_id)
    return {
        "user_id": prefs.user_id,
        "alert_symbols": prefs.alert_symbols,
        "alert_timeframes": prefs.alert_timeframes,
        "alert_min_confidence": prefs.alert_min_confidence,
        "preferred_timeframes": prefs.preferred_timeframes,
        "dark_mode": prefs.dark_mode,
        "chart_type": prefs.chart_type,
    }


@app.post("/api/preferences/{user_id}/alerts")
@limiter.limit("120/minute")
async def update_alerts(
    request: Request,
    user_id: str,
    alert_symbols: Optional[list] = Query(None),
    alert_timeframes: Optional[list] = Query(None),
    alert_min_confidence: Optional[int] = Query(None),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    current_user_id, quota_info = auth
    if current_user_id != user_id:
        raise HTTPException(403, "Not authorized to update this user's preferences")
    """Update user alert preferences."""
    if alert_symbols is not None:
        UserRepository.update_alert_symbols(db, user_id, alert_symbols)
    if alert_timeframes is not None:
        UserRepository.update_alert_timeframes(db, user_id, alert_timeframes)
    if alert_min_confidence is not None:
        UserRepository.update_alert_min_confidence(db, user_id, alert_min_confidence)

    prefs = UserRepository.get_or_create_preferences(db, user_id)
    return {"status": "updated", "preferences": prefs}


@app.post("/api/preferences/{user_id}/display")
@limiter.limit("120/minute")
async def update_display_prefs(
    request: Request,
    user_id: str,
    dark_mode: Optional[bool] = Query(None),
    chart_type: Optional[str] = Query(None),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    current_user_id, quota_info = auth
    if current_user_id != user_id:
        raise HTTPException(403, "Not authorized to update this user's preferences")
    """Update user display preferences."""
    prefs = UserRepository.update_display_preferences(
        db, user_id, dark_mode=dark_mode, chart_type=chart_type
    )
    return {
        "status": "updated",
        "dark_mode": prefs.dark_mode,
        "chart_type": prefs.chart_type,
    }


# ── Trading Endpoints ────────────────────────────────────────────────────────

@app.post("/api/trading/execute")
@limiter.limit("60/minute")
async def execute_trade(
    request: Request,
    trade_req: TradeExecutionRequest,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Execute a trade based on a signal.

    Implements comprehensive validation:
    - Symbol format (USDT pairs only)
    - Direction (LONG/SHORT)
    - Risk percentage (1-5%)
    - Signal confidence (>= 45%)
    - Position size (>= $10 minimum notional)
    - Entry price validation

    Execution modes:
    - PAPER: Simulates order execution without real capital
    - LIVE: Executes real orders on Binance (requires valid API keys)
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        # Get user's trading settings
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)

        if not trading_settings:
            raise HTTPException(400, "Trading not configured. Please set up API keys in settings.")

        trading_mode = trading_settings.trading_mode  # PAPER or LIVE
        trading_enabled = trading_settings.trading_enabled

        if not trading_enabled:
            raise HTTPException(400, "Trading is disabled. Enable trading in settings to proceed.")

        logger.info(
            f"Trade execution initiated: {trade_req.direction.value} {trade_req.symbol}",
            action="trade_execution_initiated",
            user_id=user_id,
            symbol=trade_req.symbol,
            trading_mode=trading_mode,
            request_id=request_id,
        )

        # ─── Comprehensive Pre-Flight Validation ────────────────────────────────
        # Use TradeValidator for all checks (symbol, direction, risk %, confidence, position size)
        symbol = trade_req.symbol.upper()

        # Get wallet balance (for LIVE: from Binance; for PAPER: use default)
        if trading_mode == "LIVE":
            # Decrypt credentials and get balance from Binance
            decrypted_secret = APIKeyVault.retrieve_credentials(db, user_id)
            if not decrypted_secret:
                raise HTTPException(400, "Failed to retrieve trading credentials.")

            trade_client = BinanceTradeClient(decrypted_secret["api_key"], decrypted_secret["api_secret"])
            wallet_balance = trade_client.get_wallet_balance()
        else:
            # PAPER mode: use wallet balance from settings (default 10,000 USDT)
            wallet_balance = trading_settings.wallet_balance or 10000.0

        # Comprehensive validation using TradeValidator
        validation_result = TradeValidator.validate_trade_request(
            symbol=symbol,
            direction=trade_req.direction.value,
            entry_price=trade_req.entry_price,
            quantity=0,  # Will be calculated from risk_pct
            risk_pct=trade_req.risk_pct,
            wallet_balance=wallet_balance,
            confidence=trade_req.confidence or 50,  # Default to 50 if not provided
        )

        # Extract validated parameters
        validated_quantity = validation_result["quantity"]
        order_value = validation_result["order_value"]

        logger.info(
            f"Trade validation passed: {trade_req.direction.value} {validated_quantity:.8f} {symbol}",
            action="trade_validated",
            user_id=user_id,
            symbol=symbol,
            direction=trade_req.direction.value,
            quantity=validated_quantity,
            order_value=order_value,
            risk_pct=trade_req.risk_pct,
            request_id=request_id,
        )

        # ─── Execute Trade Based on Mode ──────────────────────────────────────────
        if trading_mode == "PAPER":
            # Simulate market order execution
            simulated_order = PaperTradingSimulator.simulate_market_order(
                symbol=symbol,
                side="BUY" if trade_req.direction.value == "LONG" else "SELL",
                quantity=validated_quantity,
                current_price=trade_req.entry_price,
            )

            order_id = simulated_order["clientOrderId"]
            execution_mode_label = "[SIMULATED]"

        else:  # LIVE mode
            # Execute real market order on Binance
            decrypted_secret = APIKeyVault.retrieve_credentials(db, user_id)
            trade_client = BinanceTradeClient(decrypted_secret["api_key"], decrypted_secret["api_secret"])

            order_response = trade_client.place_market_order(
                symbol=symbol,
                side="BUY" if trade_req.direction.value == "LONG" else "SELL",
                quantity=validated_quantity,
            )

            order_id = order_response["orderId"]
            execution_mode_label = "[LIVE]"

        # Store trade in database with TP/SL levels
        trade_db = TradeRepository.store_trade(
            db=db,
            user_id=user_id,
            symbol=symbol,
            direction=trade_req.direction.value,
            entry_price=trade_req.entry_price,
            quantity=validated_quantity,
            order_id=str(order_id),
            signal_id=trade_req.signal_id,
            risk_pct=trade_req.risk_pct,
            stop_loss=trade_req.stop_loss,
            take_profit_1=trade_req.take_profit_1,
            take_profit_2=trade_req.take_profit_2,
            take_profit_3=trade_req.take_profit_3,
            auto_close_enabled=trade_req.auto_close_enabled,
        )

        logger.info(
            f"Trade executed {execution_mode_label}: {trade_req.direction.value} {validated_quantity:.8f} {symbol} @ ${trade_req.entry_price}",
            action="trade_executed",
            user_id=user_id,
            trade_id=trade_db.id,
            order_id=order_id,
            symbol=symbol,
            trading_mode=trading_mode,
            request_id=request_id,
        )

        return TradeResponse(
            order_id=str(order_id),
            symbol=symbol,
            direction=trade_req.direction,
            entry_price=trade_req.entry_price,
            quantity=validated_quantity,
            total_value=order_value,
            status="EXECUTED",
            timestamp=datetime.utcnow().isoformat(),
            message=f"Trade executed {execution_mode_label}: {trade_req.direction.value} {validated_quantity:.8f} {symbol} @ ${trade_req.entry_price}",
        )

    except TradeValidationError as e:
        logger.warning(
            f"Trade validation failed: {str(e)}",
            action="trade_validation_failed",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(400, str(e))
    except ValueError as e:
        logger.warning(
            f"Trade execution validation failed: {str(e)}",
            action="trade_execution_failed",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(
            f"Trade execution error: {str(e)}",
            action="trade_execution_error",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to execute trade. Please check your API keys and try again.")


@app.get("/api/trading/orders")
@limiter.limit("120/minute")
async def get_open_orders(
    request: Request,
    symbol: Optional[str] = None,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Get all open trades for the authenticated user.
    Optionally filter by symbol.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        symbol = symbol.upper() if symbol else None

        # Get open trades from database
        open_trades = TradeRepository.get_open_trades(db, user_id, symbol)

        logger.info(
            f"Retrieved {len(open_trades)} open trades",
            action="open_orders_retrieved",
            user_id=user_id,
            count=len(open_trades),
            request_id=request_id,
        )

        # Fetch current prices from Binance for all unique symbols
        price_cache = {}
        unique_symbols = set(trade.symbol for trade in open_trades)

        for symbol in unique_symbols:
            try:
                current_price = await get_klines(symbol, "1m", limit=1)
                if current_price and len(current_price) > 0:
                    # Extract close price from latest candle
                    price_cache[symbol] = float(current_price[0][4])  # Close price
                else:
                    price_cache[symbol] = None
            except Exception as e:
                logger.warning(
                    f"Failed to fetch price for {symbol}: {str(e)}",
                    action="price_fetch_failed",
                    symbol=symbol,
                    error=str(e),
                )
                price_cache[symbol] = None

        # Build response with current prices
        orders = []
        for trade in open_trades:
            current_price = price_cache.get(trade.symbol) or trade.entry_price

            unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
            unrealized_pnl_pct = ((current_price - trade.entry_price) / trade.entry_price * 100) if trade.entry_price > 0 else 0

            orders.append(OpenOrderResponse(
                id=trade.id,
                order_id=trade.order_id,
                symbol=trade.symbol,
                direction=trade.direction,
                entry_price=trade.entry_price,
                quantity=trade.quantity,
                entry_value=trade.entry_value,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                entry_timestamp=trade.entry_timestamp.isoformat(),
                status=trade.status,
            ))

        return {"orders": orders, "count": len(orders)}

    except Exception as e:
        logger.error(
            f"Failed to retrieve open orders: {str(e)}",
            action="open_orders_error",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to retrieve open orders")


@app.get("/api/prices")
@limiter.limit("600/minute")
async def get_prices(
    request: Request,
    symbols: str = Query(...),
    auth: tuple = Depends(get_current_user),
):
    """
    Fetch current prices for multiple symbols.

    Query parameter: symbols (comma-separated, e.g., "BTCUSDT,ETHUSDT,BNBUSDT")
    Returns: {symbol: current_price}

    Rate-limited to 600/minute (10 requests/sec) for high-frequency price updates.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        # Parse and validate symbols
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        if not symbol_list:
            raise HTTPException(400, "No symbols provided")

        if len(symbol_list) > 50:
            raise HTTPException(400, "Maximum 50 symbols per request")

        logger.debug(
            f"Fetching prices for {len(symbol_list)} symbols",
            action="prices_requested",
            user_id=user_id,
            symbols=symbol_list,
            request_id=request_id,
        )

        # Fetch current prices
        prices = {}
        for symbol in symbol_list:
            try:
                klines = await get_klines(symbol, "1m", limit=1)
                if klines and len(klines) > 0:
                    # Extract close price from latest 1m candle
                    prices[symbol] = {
                        "price": float(klines[0][4]),  # Close price
                        "timestamp": int(klines[0][6]),  # Close time
                    }
                else:
                    prices[symbol] = {
                        "price": None,
                        "error": "No data available",
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to fetch price for {symbol}: {str(e)}",
                    action="price_fetch_error",
                    symbol=symbol,
                    error=str(e),
                )
                prices[symbol] = {
                    "price": None,
                    "error": str(e),
                }

        logger.debug(
            f"Fetched prices for {len([p for p in prices.values() if p.get('price')])} symbols",
            action="prices_fetched",
            user_id=user_id,
            count=len(prices),
            request_id=request_id,
        )

        return {
            "prices": prices,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(prices),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to fetch prices: {str(e)}",
            action="prices_error",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(500, f"Failed to fetch prices: {str(e)}")


@app.get("/api/trading/history")
@limiter.limit("120/minute")
async def get_trade_history(
    request: Request,
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Get closed trades for the authenticated user.
    Optionally filter by symbol and limit results.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        symbol = symbol.upper() if symbol else None

        # Get closed trades from database
        closed_trades = TradeRepository.get_closed_trades(db, user_id, symbol, limit)

        logger.info(
            f"Retrieved {len(closed_trades)} closed trades",
            action="trade_history_retrieved",
            user_id=user_id,
            count=len(closed_trades),
            request_id=request_id,
        )

        history = []
        for trade in closed_trades:
            if trade.exit_price is not None and trade.exit_timestamp is not None:
                duration_hours = (trade.exit_timestamp - trade.entry_timestamp).total_seconds() / 3600

                history.append(TradeHistoryResponse(
                    id=trade.id,
                    symbol=trade.symbol,
                    direction=trade.direction,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    quantity=trade.quantity,
                    entry_value=trade.entry_value,
                    exit_value=trade.exit_price * (trade.exit_quantity or trade.quantity),
                    realized_pnl=trade.realized_pnl or 0,
                    realized_pnl_pct=trade.realized_pnl_pct or 0,
                    exit_reason=trade.exit_reason,
                    entry_timestamp=trade.entry_timestamp.isoformat(),
                    exit_timestamp=trade.exit_timestamp.isoformat(),
                    duration_hours=duration_hours,
                ))

        # Get performance stats
        perf = TradeRepository.get_trading_performance(db, user_id)

        return {
            "history": history,
            "count": len(history),
            "performance": perf,
        }

    except Exception as e:
        logger.error(
            f"Failed to retrieve trade history: {str(e)}",
            action="trade_history_error",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to retrieve trade history")


@app.post("/api/trading/close")
@limiter.limit("60/minute")
async def close_trade(
    request: Request,
    close_req: CloseTradeRequest,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Close an open trade at current market price or specified exit price.

    Calculates realized P&L and updates trade status to CLOSED.
    Supports both PAPER and LIVE trading modes.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        # Retrieve the trade
        trade = db.query(__import__('models').TradeDB).filter(
            __import__('models').TradeDB.id == close_req.trade_id,
            __import__('models').TradeDB.user_id == user_id,
            __import__('models').TradeDB.status == "OPEN"
        ).first()

        if not trade:
            logger.warning(
                f"Trade not found or already closed: {close_req.trade_id}",
                action="trade_not_found",
                user_id=user_id,
                trade_id=close_req.trade_id,
                request_id=request_id,
            )
            raise HTTPException(404, f"Trade {close_req.trade_id} not found or already closed")

        # Get user's trading settings
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)
        trading_mode = trading_settings.trading_mode if trading_settings else "PAPER"

        logger.info(
            f"Close trade initiated: {trade.symbol} {trade.direction}",
            action="close_trade_initiated",
            user_id=user_id,
            trade_id=trade.id,
            trading_mode=trading_mode,
            request_id=request_id,
        )

        # Determine exit price
        if close_req.exit_price is not None:
            exit_price = close_req.exit_price
        else:
            # Market close: fetch current price
            if trading_mode == "LIVE":
                decrypted_secret = APIKeyVault.retrieve_credentials(db, user_id)
                if decrypted_secret:
                    trade_client = BinanceTradeClient(decrypted_secret["api_key"], decrypted_secret["api_secret"])
                    current_price = await trade_client.get_current_price(trade.symbol)
                    exit_price = current_price
                else:
                    exit_price = trade.entry_price  # Fallback
            else:
                # PAPER mode: use current_price from request or fallback to entry price
                exit_price = trade.entry_price  # TODO: fetch from Binance API

        # Calculate P&L using the validator's simulator
        pnl_data = PaperTradingSimulator.calculate_pnl(
            entry_price=trade.entry_price,
            exit_price=exit_price,
            quantity=trade.quantity,
            direction=trade.direction,
            fees=0.0,  # TODO: fetch actual fees from Binance
        )

        # Update trade with exit details
        trade.exit_price = exit_price
        trade.exit_quantity = trade.quantity
        trade.exit_timestamp = datetime.utcnow()
        trade.exit_reason = close_req.exit_reason
        trade.realized_pnl = pnl_data["net_pnl"]
        trade.realized_pnl_pct = pnl_data["pnl_pct"]
        trade.status = "CLOSED"

        db.commit()

        # Calculate duration
        duration_hours = (trade.exit_timestamp - trade.entry_timestamp).total_seconds() / 3600

        logger.info(
            f"Trade closed: {trade.symbol} P&L {pnl_data['net_pnl']:.2f} USDT ({pnl_data['pnl_pct']:.2f}%)",
            action="trade_closed",
            user_id=user_id,
            trade_id=trade.id,
            exit_price=exit_price,
            realized_pnl=pnl_data["net_pnl"],
            realized_pnl_pct=pnl_data["pnl_pct"],
            exit_reason=close_req.exit_reason,
            request_id=request_id,
        )

        return CloseTradeResponse(
            id=trade.id,
            symbol=trade.symbol,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            quantity=trade.quantity,
            entry_value=trade.entry_value,
            exit_value=exit_price * trade.quantity,
            realized_pnl=pnl_data["net_pnl"],
            realized_pnl_pct=pnl_data["pnl_pct"],
            exit_reason=close_req.exit_reason,
            duration_hours=duration_hours,
            status="CLOSED",
            timestamp=datetime.utcnow().isoformat(),
            message=f"Trade closed: {trade.symbol} {pnl_data['net_pnl']:+.2f} USDT ({pnl_data['pnl_pct']:+.2f}%)",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to close trade: {str(e)}",
            action="close_trade_error",
            user_id=user_id,
            trade_id=close_req.trade_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(500, f"Failed to close trade: {str(e)}")


@app.post("/api/trading/modify-tp-sl")
@limiter.limit("120/minute")
async def modify_tp_sl(
    request: Request,
    modify_req: ModifyTPSLRequest,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Modify Stop Loss and/or Take Profit levels for an open trade.

    Validates new levels before updating:
    - SL must be on wrong side of entry (loss boundary)
    - TP must be on right side of entry (profit boundary)
    - Gaps must be at least 0.1% from entry
    - Max loss: 50%, Max gain: 200%
    - TP levels must be in correct order (TP1 < TP2 < TP3)
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        # Verify user owns this trade
        trade = db.query(__import__('models').TradeDB).filter(
            __import__('models').TradeDB.id == modify_req.trade_id,
            __import__('models').TradeDB.user_id == user_id,
        ).first()

        if not trade:
            logger.warning(
                f"Trade not found: {modify_req.trade_id}",
                action="trade_not_found_for_modification",
                user_id=user_id,
                trade_id=modify_req.trade_id,
                request_id=request_id,
            )
            raise HTTPException(404, f"Trade {modify_req.trade_id} not found")

        logger.info(
            f"Modify TP/SL initiated: {trade.symbol}",
            action="modify_tp_sl_initiated",
            user_id=user_id,
            trade_id=trade.id,
            request_id=request_id,
        )

        # Modify TP/SL levels
        updated_trade = TPSLModifier.modify_levels(
            db=db,
            trade_id=modify_req.trade_id,
            new_stop_loss=modify_req.stop_loss,
            new_tp1=modify_req.take_profit_1,
            new_tp2=modify_req.take_profit_2,
            new_tp3=modify_req.take_profit_3,
        )

        logger.info(
            f"TP/SL modified: {updated_trade.symbol}",
            action="tp_sl_modified_success",
            user_id=user_id,
            trade_id=updated_trade.id,
            stop_loss=updated_trade.stop_loss,
            tp1=updated_trade.take_profit_1,
            tp2=updated_trade.take_profit_2,
            tp3=updated_trade.take_profit_3,
            request_id=request_id,
        )

        return ModifyTPSLResponse(
            id=updated_trade.id,
            symbol=updated_trade.symbol,
            direction=updated_trade.direction,
            entry_price=updated_trade.entry_price,
            stop_loss=updated_trade.stop_loss,
            take_profit_1=updated_trade.take_profit_1,
            take_profit_2=updated_trade.take_profit_2,
            take_profit_3=updated_trade.take_profit_3,
            status=updated_trade.status,
            timestamp=datetime.utcnow().isoformat(),
            message=f"TP/SL levels updated for {updated_trade.symbol}",
        )

    except TPSLModificationError as e:
        logger.warning(
            f"TP/SL modification validation failed: {str(e)}",
            action="tp_sl_validation_failed",
            user_id=user_id,
            trade_id=modify_req.trade_id,
            error=str(e),
            request_id=request_id,
        )
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to modify TP/SL: {str(e)}",
            action="modify_tp_sl_error",
            user_id=user_id,
            trade_id=modify_req.trade_id,
            error=str(e),
            request_id=request_id,
            exc_info=True,
        )
        raise HTTPException(500, f"Failed to modify TP/SL: {str(e)}")


@app.post("/api/trading/validate-keys")
@limiter.limit("10/minute")
async def validate_api_keys(
    request: Request,
    keys_req: APIKeyValidationRequest,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Validate Binance API keys by testing a connection.
    Rate-limited to 10/minute to prevent abuse.
    If valid, encrypts and stores the keys securely.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        # Validate inputs
        if not keys_req.api_key or not keys_req.api_secret:
            raise ValueError("API key and secret are required")

        logger.info(
            "API key validation requested",
            action="api_key_validation_requested",
            user_id=user_id,
            request_id=request_id,
        )

        # Test connection with Binance
        try:
            client = BinanceTradeClient(keys_req.api_key, keys_req.api_secret)
            is_valid = await client.validate_credentials()

            if not is_valid:
                logger.warning(
                    "Invalid Binance credentials",
                    action="invalid_credentials",
                    user_id=user_id,
                    request_id=request_id,
                )
                return APIKeyValidationResponse(
                    valid=False,
                    connected=False,
                    error="Invalid API key or secret",
                )

            # Get wallet balance to confirm access
            balance = await client.get_wallet_balance()

            # Credentials are valid - encrypt and store them
            encrypted_data = APIKeyVault.store_credentials(
                user_id,
                keys_req.api_key,
                keys_req.api_secret,
            )

            # Store encrypted credentials in database
            BinanceCredentialsRepository.store_credentials(
                db,
                user_id,
                encrypted_data["api_key_encrypted"],
                encrypted_data["api_secret_encrypted"],
                encrypted_data["key_hash"],
            )

            # Update validation status to VERIFIED
            BinanceCredentialsRepository.update_validation_status(db, user_id, True)

            logger.info(
                f"API keys validated and stored for user {user_id}",
                action="api_keys_validated_and_stored",
                user_id=user_id,
                balance=balance,
                request_id=request_id,
            )

            return APIKeyValidationResponse(
                valid=True,
                balance_usdt=balance,
                connected=True,
                error=None,
            )

        except Exception as e:
            logger.error(
                f"Binance connection failed: {str(e)}",
                action="binance_connection_failed",
                user_id=user_id,
                error=str(e),
            )
            return APIKeyValidationResponse(
                valid=False,
                connected=False,
                error=f"Failed to connect to Binance: {str(e)}",
            )

    except ValueError as e:
        logger.warning(
            f"Validation request error: {str(e)}",
            action="validation_request_error",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(
            f"API key validation error: {str(e)}",
            action="api_key_validation_error",
            user_id=user_id,
            request_id=request_id,
            error=str(e),
        )
        return APIKeyValidationResponse(
            valid=False,
            connected=False,
            error="Internal server error",
        )


@app.post("/api/trading/keys/store")
@limiter.limit("30/minute")
async def store_trading_keys(
    request: Request,
    keys_req: APIKeyValidationRequest,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Securely store Binance API keys (after validation).
    Keys are encrypted before storage.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        if not keys_req.api_key or not keys_req.api_secret:
            raise ValueError("API key and secret are required")

        # Encrypt the credentials
        encrypted_data = APIKeyVault.store_credentials(
            user_id,
            keys_req.api_key,
            keys_req.api_secret,
        )

        # Store in database
        BinanceCredentialsRepository.store_credentials(
            db,
            user_id,
            encrypted_data["api_key_encrypted"],
            encrypted_data["api_secret_encrypted"],
            encrypted_data["key_hash"],
        )

        logger.info(
            "Trading keys stored securely",
            action="trading_keys_stored",
            user_id=user_id,
            request_id=request_id,
        )

        return {
            "status": "stored",
            "message": "API keys stored securely",
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(
            f"Failed to store keys: {str(e)}",
            action="key_storage_failed",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to store API keys")


@app.post("/api/trading/keys/revoke")
@limiter.limit("30/minute")
async def revoke_trading_keys(
    request: Request,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Revoke/delete stored Binance API keys for a user.
    This disables trading for that user.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        success = BinanceCredentialsRepository.delete_credentials(db, user_id)

        if success:
            logger.info(
                "Trading keys revoked",
                action="trading_keys_revoked",
                user_id=user_id,
                request_id=request_id,
            )
            return {
                "status": "revoked",
                "message": "API keys have been revoked",
            }
        else:
            return HTTPException(404, "No stored API keys found")

    except Exception as e:
        logger.error(
            f"Failed to revoke keys: {str(e)}",
            action="key_revocation_failed",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to revoke API keys")


@app.get("/api/trading/keys/status")
@limiter.limit("60/minute")
async def get_trading_keys_status(
    request: Request,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Check if user has stored Binance credentials and their validation status.
    Does NOT return the actual keys.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        creds = BinanceCredentialsRepository.get_credentials(db, user_id)

        if not creds:
            return {
                "has_credentials": False,
                "validation_status": None,
                "trading_enabled": False,
                "trading_mode": None,
            }

        logger.debug(
            "Trading keys status retrieved",
            action="trading_keys_status_retrieved",
            user_id=user_id,
            status=creds.validation_status,
        )

        return {
            "has_credentials": True,
            "validation_status": creds.validation_status,
            "trading_enabled": creds.trading_enabled,
            "trading_mode": creds.trading_mode,
            "last_validated_at": creds.last_validated_at.isoformat() if creds.last_validated_at else None,
        }

    except Exception as e:
        logger.error(
            f"Failed to get keys status: {str(e)}",
            action="keys_status_failed",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(500, "Failed to retrieve key status")


# ── Auto-Execution Settings ──────────────────────────────────────────────────

@app.put("/api/trading/auto-execution")
@limiter.limit("30/minute")
async def update_auto_execution_settings(
    request: Request,
    auto_execution_enabled: bool = Query(...),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Enable or disable auto-execution of high-confidence signals.

    Auto-execution rules:
    - Confidence >= 85 (VERY_HIGH): Auto-execute at 100% position size
    - Confidence >= 75 (HIGH): Auto-execute at 80% position size (if not in recovery)
    - Recovery mode (15-25% DD): Only VERY_HIGH executes at 50% size
    - Pause mode (>25% DD): All auto-execution disabled
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)

        if not trading_settings:
            raise HTTPException(400, "Trading not configured. Set up API keys first.")

        # Update auto-execution setting
        trading_settings.auto_execution_enabled = auto_execution_enabled
        db.commit()
        db.refresh(trading_settings)

        logger.info(
            f"Auto-execution setting updated: {auto_execution_enabled}",
            action="auto_execution_setting_updated",
            user_id=user_id,
            auto_execution_enabled=auto_execution_enabled,
            request_id=request_id,
        )

        return {
            "success": True,
            "auto_execution_enabled": auto_execution_enabled,
            "trading_mode": trading_settings.trading_mode,
            "trading_enabled": trading_settings.trading_enabled,
        }

    except Exception as e:
        logger.error(
            f"Failed to update auto-execution settings: {str(e)}",
            action="auto_execution_update_failed",
            user_id=user_id,
            error=str(e),
            request_id=request_id,
        )
        raise HTTPException(500, "Failed to update auto-execution settings")


@app.get("/api/trading/auto-execution/status")
@limiter.limit("60/minute")
async def get_auto_execution_status(
    request: Request,
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Get current auto-execution status and recent activity.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    try:
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)

        if not trading_settings:
            return {
                "auto_execution_enabled": False,
                "trading_enabled": False,
                "recent_activity": [],
                "stats": {},
            }

        # Get recent auto-executions
        audit_repo = AutoExecutionAuditRepository()
        recent_executions = audit_repo.get_user_auto_executions(db, user_id, limit=20)
        stats = audit_repo.get_auto_execution_stats(db, user_id, days=7)

        logger.debug(
            "Auto-execution status retrieved",
            action="auto_execution_status_retrieved",
            user_id=user_id,
            request_id=request_id,
        )

        return {
            "auto_execution_enabled": trading_settings.auto_execution_enabled,
            "trading_enabled": trading_settings.trading_enabled,
            "trading_mode": trading_settings.trading_mode,
            "wallet_balance": trading_settings.wallet_balance,
            "recent_activity": [
                {
                    "id": e.id,
                    "symbol": e.symbol,
                    "direction": e.direction,
                    "confidence": e.confidence_score,
                    "recovery_state": e.recovery_state,
                    "executed": e.executed,
                    "trigger": e.execution_trigger,
                    "error": e.execution_error,
                    "timestamp": e.created_at.isoformat(),
                }
                for e in recent_executions
            ],
            "stats": stats,
        }

    except Exception as e:
        logger.error(
            f"Failed to get auto-execution status: {str(e)}",
            action="auto_execution_status_failed",
            user_id=user_id,
            error=str(e),
            request_id=request_id,
        )
        raise HTTPException(500, "Failed to retrieve auto-execution status")


@app.post("/api/trading/wallet/balance")
@limiter.limit("30/minute")
async def update_wallet_balance(
    request: Request,
    wallet_balance: float = Query(..., gt=0),
    auth: tuple = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Update virtual wallet balance for paper trading.
    This is used to calculate position sizes in paper/demo mode.
    """
    user_id, quota_info = auth
    request_id = get_request_id(request)

    if wallet_balance < 10:
        raise HTTPException(400, "Wallet balance must be at least $10")

    if wallet_balance > 10000000:
        raise HTTPException(400, "Wallet balance cannot exceed $10M")

    try:
        creds_repo = BinanceCredentialsRepository()
        trading_settings = creds_repo.get_credentials(db, user_id)

        if not trading_settings:
            raise HTTPException(400, "Trading not configured. Set up API keys first.")

        trading_settings.wallet_balance = wallet_balance
        db.commit()
        db.refresh(trading_settings)

        logger.info(
            f"Wallet balance updated: ${wallet_balance:,.2f}",
            action="wallet_balance_updated",
            user_id=user_id,
            wallet_balance=wallet_balance,
            request_id=request_id,
        )

        return {
            "success": True,
            "wallet_balance": trading_settings.wallet_balance,
        }

    except Exception as e:
        logger.error(
            f"Failed to update wallet balance: {str(e)}",
            action="wallet_balance_update_failed",
            user_id=user_id,
            error=str(e),
            request_id=request_id,
        )
        raise HTTPException(500, "Failed to update wallet balance")


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


# ── SSE Live Price Stream ─────────────────────────────────────────────────────

@app.get("/api/stream/{symbol}")
async def price_stream(symbol: str, timeframe: str = Query("1h")):
    """Server-Sent Events endpoint — pushes price + indicator updates every 10s."""
    symbol = symbol.upper()

    async def event_generator():
        while True:
            try:
                df = await get_klines(symbol, timeframe, limit=50)
                df = add_all_indicators(df)
                latest = df.iloc[-1]
                data = {
                    "symbol": symbol,
                    "price": round(float(latest["close"]), 6),
                    "open": round(float(latest["open"]), 6),
                    "high": round(float(latest["high"]), 6),
                    "low": round(float(latest["low"]), 6),
                    "volume": round(float(latest["volume"]), 2),
                    "rsi": round(float(latest["rsi"]), 1) if not pd.isna(latest["rsi"]) else None,
                    "ema7": round(float(latest["ema7"]), 6) if not pd.isna(latest["ema7"]) else None,
                    "ema25": round(float(latest["ema25"]), 6) if not pd.isna(latest["ema25"]) else None,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
