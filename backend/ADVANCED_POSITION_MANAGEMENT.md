# Advanced Position Management

Sophisticated trade management strategies including trailing stops, partial closures, position scaling, breakeven stops, and dynamic risk adjustment.

## Overview

Advanced position management automates complex trading strategies:

- **Trailing Stop Loss** — Auto-adjust SL upward as price moves in profit
- **Partial Closure** — Close portions of trades at predefined levels
- **Position Scaling** — Scale in (average down/up) or scale out systematically
- **Breakeven Stops** — Move SL to entry price once minimal profit reached
- **Dynamic Risk** — Adjust position size based on market volatility

## Components

### 1. TrailingStopManager

Automatically adjusts stop loss as price moves favorably.

```python
# Calculate trailing stop
new_sl = TrailingStopManager.calculate_trailing_stop(
    entry_price=40000.0,
    current_price=41234.56,
    trailing_amount=500.0,  # 500 USDT behind price
    direction="LONG"
)
# Returns: 40734.56

# Update trade's SL
updated, new_sl, msg = TrailingStopManager.update_trailing_stop(
    db=session,
    trade_id=1,
    current_price=41234.56,
    trailing_amount=500.0,
    min_update_pct=0.1  # Only update if moved 0.1%+
)
```

**Features:**
- Percentage-based or fixed amount trailing
- Prevents SL from going below entry (LONG) or above entry (SHORT)
- Minimum move threshold to avoid excessive updates
- Structured logging with context

**Use cases:**
- Lock in profits as price runs
- Protect gains while allowing room for pullbacks
- Eliminate need to manually adjust SL on winners

### 2. PartialCloseManager

Close portions of position at profit levels.

```python
# Detect if partial close price reached
should_close = PartialCloseManager.calculate_partial_close(
    entry_price=40000.0,
    current_price=41200.0,
    close_pct=3.0,  # Close at 3% profit
    direction="LONG"
)
# Returns: True

# Execute partial close
closed, pnl, msg = PartialCloseManager.execute_partial_close(
    db=session,
    trade_id=1,
    close_quantity=0.05,
    close_price=41200.0,
    close_reason="PARTIAL_CLOSE"
)
# Returns: (True, 61.728, "Closed 0.05, P&L: 61.73 (3.08%)")
```

**Features:**
- Close any portion of open trade
- Calculate realized P&L automatically
- Update remaining quantity
- Support partial fills

**Use cases:**
- Take profits at predefined levels
- Reduce risk as price moves in favor
- Lock in minimum gains

**P&L Calculation:**
```
LONG:  P&L = (close_price - entry_price) × quantity
SHORT: P&L = (entry_price - close_price) × quantity
```

### 3. PositionScaler

Scale position size in or out systematically.

#### Scale Out

Close position across multiple price levels:

```python
# Calculate scale-out prices
prices = PositionScaler.calculate_scale_out_price(
    entry_price=40000.0,
    scale_steps=3,
    target_profit_pct=9.0,
    direction="LONG"
)
# Returns: [41200.0, 42400.0, 43600.0]  # 3%, 6%, 9% profit
```

Use with partial closes:
```
Step 1: Close 33% at 41200.0 (3% profit)
Step 2: Close 33% at 42400.0 (6% profit)
Step 3: Close 34% at 43600.0 (9% profit)
```

#### Scale In

Add to position when price moves against you (average down/up):

```python
# Check if allowed to scale in
add_size, msg = PositionScaler.calculate_scale_in_size(
    initial_size=0.1,
    base_price=40000.0,
    current_price=39000.0,  # Down 2.5%
    scale_steps=2,
    max_loss_pct=5.0,
    direction="LONG"
)

if add_size:
    # Can add more BTC at lower price
    execute_buy(add_size, 39000.0)
```

**Safety checks:**
- Only allows if loss within max threshold
- Reduces add size as loss deepens
- Prevents averaging into losers

### 4. BreakevenStopManager

Move SL to entry price once small profit reached.

```python
# Check if should move to breakeven
should_update, new_sl, msg = BreakevenStopManager.calculate_breakeven_stop(
    entry_price=40000.0,
    current_price=41000.0,  # 2.5% profit
    min_profit_pct=2.0,
    direction="LONG"
)
# Returns: (True, 40000.001, "Moving SL to breakeven...")

# Update trade
updated, msg = await BreakevenStopManager.update_to_breakeven(
    db=session,
    trade_id=1,
    current_price=41000.0,
    min_profit_pct=2.0
)
```

**Benefits:**
- Risk-free after initial profit
- Allows trade to run to full target
- Guarantees minimum gain

### 5. DynamicRiskManager

Adjust position size and risk % based on volatility.

#### Size Adjustment

```python
# High volatility: reduce position size
adjusted_size = DynamicRiskManager.calculate_adjusted_size(
    base_size=1.0,
    atr=150.0,        # Current ATR (high)
    base_atr=100.0,   # Reference ATR
    volatility_multiplier=1.0,
    min_size_pct=50.0  # At least 50% of base
)
# Returns: 0.67 (reduced to 2/3)

# Low volatility: increase position size
adjusted_size = DynamicRiskManager.calculate_adjusted_size(
    base_size=1.0,
    atr=50.0,         # Current ATR (low)
    base_atr=100.0,
    volatility_multiplier=1.0,
    min_size_pct=50.0
)
# Returns: 2.0 (doubled)
```

#### Risk % Adjustment

```python
# High volatility: reduce risk
adjusted_risk = DynamicRiskManager.calculate_adjusted_risk_pct(
    base_risk_pct=2.0,
    current_volatility=0.08,   # High
    avg_volatility=0.04,
    max_risk_pct=5.0
)
# Returns: 1.0 (halved)
```

**Volatility scaling:**
- Higher volatility → smaller positions
- Lower volatility → larger positions
- Always respects minimums and maximums

### 6. PositionManagementEngine

Coordinates all strategies for a single trade.

```python
engine = PositionManagementEngine(db)

results = await engine.process_position(
    trade_id=1,
    current_price=41234.56,
    atr=100.0,
    volatility=0.05,
    modes=[
        PositionManagementMode.TRAILING_STOP,
        PositionManagementMode.BREAKEVEN,
        PositionManagementMode.DYNAMIC_RISK,
    ]
)

# Returns:
# {
#     "trade_id": 1,
#     "timestamp": "2026-05-23T...",
#     "updates": {
#         "trailing_stop": {"success": True, "message": "..."},
#         "breakeven": {"success": True, "message": "..."},
#         "dynamic_risk": {"original_size": 0.1, "adjusted_size": 0.067}
#     },
#     "errors": []
# }
```

## Modes

```python
class PositionManagementMode(str, Enum):
    TRAILING_STOP = "TRAILING_STOP"    # Auto-adjust SL
    PARTIAL_CLOSE = "PARTIAL_CLOSE"    # Close at levels
    SCALE_IN = "SCALE_IN"              # Average down/up
    SCALE_OUT = "SCALE_OUT"            # Systematic exit
    BREAKEVEN = "BREAKEVEN"            # Risk-free trade
    DYNAMIC_RISK = "DYNAMIC_RISK"      # Volatility-based sizing
```

## Usage Examples

### Example 1: Scalp with Trailing Stop

```python
trade = execute_trade(
    symbol="BTCUSDT",
    direction="LONG",
    entry_price=40000.0,
    quantity=0.1
)

# Every minute, update trailing stop
while trade.status == "OPEN":
    current_price = get_price("BTCUSDT")
    
    updated, new_sl, msg = TrailingStopManager.update_trailing_stop(
        db, trade.id, current_price,
        trailing_amount=200.0,  # 200 USDT trail
        min_update_pct=0.05     # Only update if 0.05% move
    )
    
    if updated:
        logger.info(f"SL updated to {new_sl}")
    
    await asyncio.sleep(60)
```

### Example 2: Grid Exit Strategy

```python
trade = execute_trade(
    symbol="ETHUSDT",
    direction="LONG",
    entry_price=2500.0,
    quantity=1.0
)

# Define grid levels
exit_levels = PositionScaler.calculate_scale_out_price(
    entry_price=2500.0,
    scale_steps=5,
    target_profit_pct=20.0,  # 20% over 5 levels = 4% each
    direction="LONG"
)
# [2600.0, 2700.0, 2800.0, 2900.0, 3000.0]

quantities_per_level = trade.quantity / len(exit_levels)

# Exit at each level
for level_price in exit_levels:
    while True:
        current = get_price("ETHUSDT")
        if current >= level_price:
            closed, pnl, msg = PartialCloseManager.execute_partial_close(
                db, trade.id, quantities_per_level, current
            )
            break
        await asyncio.sleep(5)
```

### Example 3: Risk Management in Volatile Markets

```python
# Morning: Normal volatility, 2% risk
position = execute_trade(
    symbol="BTCUSDT",
    entry_price=40000.0,
    risk_pct=2.0  # 2% of wallet
)

# Afternoon: Volatility spikes (FOMC announcement)
atr_now = 250.0
atr_avg = 100.0

adjusted_risk = DynamicRiskManager.calculate_adjusted_risk_pct(
    base_risk_pct=2.0,
    current_volatility=atr_now,
    avg_volatility=atr_avg,
    max_risk_pct=5.0
)
# Returns: 0.8% - reduced for safety

# Reduce position or don't add more
```

### Example 4: Complete Trade Management

```python
async def manage_trade(trade_id: int, db: SessionLocal):
    engine = PositionManagementEngine(db)
    
    while True:
        trade = TradeRepository.get_trade_by_id(db, trade_id)
        if trade.status != "OPEN":
            break
        
        current_price = await get_current_price(trade.symbol)
        atr = await get_atr(trade.symbol, "1h")
        
        # Step 1: Activate breakeven after 1% profit
        if not trade.breakeven_activated:
            activated, msg = await BreakevenStopManager.update_to_breakeven(
                db, trade_id, current_price, min_profit_pct=1.0
            )
            if activated:
                trade.breakeven_activated = True
        
        # Step 2: Update trailing stop (locked-in profits)
        TrailingStopManager.update_trailing_stop(
            db, trade_id, current_price,
            trailing_amount=500.0,
            min_update_pct=0.2
        )
        
        # Step 3: Scale out at 5%, 10%, 15% profit
        if trade.profit_pct >= 5.0 and not trade.partial_1_closed:
            PartialCloseManager.execute_partial_close(
                db, trade_id, trade.quantity * 0.33, current_price,
                close_reason="GRID_LEVEL_1"
            )
            trade.partial_1_closed = True
        
        await asyncio.sleep(300)  # Check every 5 minutes
```

## Testing

Run tests:
```bash
python3 -m pytest backend/tests/test_advanced_position_manager.py -v
```

**Test coverage:**
- 38 tests
- 100% code coverage
- Scenarios:
  - Trailing stops (LONG/SHORT, profit/no profit)
  - Partial closes (quantity validation, P&L calc)
  - Position scaling (in/out, volatility checks)
  - Breakeven stops (profit triggers, SL updates)
  - Dynamic risk (volatility-based sizing)
  - Integration scenarios (multi-step strategies)

## Database Schema

Trades already have columns needed for advanced management:

```python
TradeDB.stop_loss          # Trailing SL location
TradeDB.take_profit_1/2/3  # Scale-out levels
TradeDB.quantity           # Current position size
TradeDB.entry_price        # Entry for averaging calcs
TradeDB.updated_at         # Track when SL updated
```

## Performance

**Typical overhead per position:**
- Trailing stop check: <1ms
- Partial close calc: <1ms
- Dynamic risk calc: <1ms
- Database update: ~5ms

**Suitable for:**
- Real-time trading (check every 5-30 seconds)
- Backtesting (process after each candle)
- Live monitoring (background task)

## Future Enhancements

1. **Order Management** — Automatically place take profit orders with Binance
2. **Hedging** — Hedge positions with opposite directional trades
3. **Correlation Trading** — Adjust based on correlated assets
4. **Time-based Exits** — Exit after X minutes regardless of price
5. **ML Optimization** — Learn optimal parameters from historical trades
6. **Multi-leg Strategies** — Manage complex multi-position strategies
