# Strategy Research Loop — Base System Spec

Goal: find out whether any variant of the EMA-cross signal has a real,
generalizable edge, using disciplined train/validate/holdout methodology.
This is a *research* system, kept separate from the production
`combination_backtester.py` (which is left untouched and still powers the
live `/api/backtest/*` endpoints).

## Data layer
- Source: Binance spot klines via `backend/binance_client.get_historical_klines`
  (auto-paginating, arbitrary date range).
- Symbol basket (pooled, to reach ≥100 trades per variant):
  BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, ADAUSDT.
- Timeframe: 4h (enough history for a real sample size, still tradeable).
- History window: as much as Binance has for each symbol, capped to the
  common overlap needed for a clean TRAIN/VALIDATE/HOLDOUT split.
- Cached to `backend/research/data/{symbol}_{tf}.csv` so repeated runs
  don't re-hit Binance (no pyarrow in the venv, plain CSV is fine here).

## Data split (time-based, per symbol, never shuffled)
- TRAIN: oldest 60% of candles
- VALIDATE: next 20%
- HOLDOUT: newest 20% — locked, touched exactly once, at the very end
- Boundaries (per symbol, as ISO timestamps) written to
  `backend/research/config/data_split.json` after the data pull.

## Baseline signal
- EMA7/25 cross (existing `detect_ema_cross` logic re-implemented locally
  for full control) and EMA7/99 cross as an alternate baseline.
- Signals are only generated on **closed candles** (no use of the
  in-progress bar).

## Execution model (fixes the lookahead bug in combination_backtester)
- A signal detected on the close of candle `i` is executed at the **open of
  candle `i+1`** — never at candle `i`'s own close.
- Stop-loss / take-profit are checked candle-by-candle from `i+1` onward.
  If a candle's range touches both SL and TP, SL counts first (conservative,
  matches `track_record.py` convention).
- Position sized in R-multiples: loss = -1.0R, TP1/TP2/TP3 = 1.0R/2.0R/3.0R
  (matches existing track-record convention for comparability).

## Costs
- Round-trip cost of 0.10% (taker fee) + 0.05% slippage = **0.15% per side,
  0.30% round trip**, deducted from every trade's R-outcome (converted to
  R using each trade's own risk distance so it scales correctly).
- Applied to every trade, every variant, no exceptions.

## Metrics (computed per split, never mixing splits)
- expectancy (avg R per trade), win rate, profit factor, max drawdown,
  Sharpe (per-trade R annualized by trade frequency), trade count.
- "Validate expectancy" is the only number used for promotion decisions.
- TRAIN metrics are never reported as "performance," only used to fit
  parameters.

## Monte Carlo
- Bootstrap resample (with replacement) the champion's VALIDATE+HOLDOUT
  trade sequence, 2,000 paths, to get a distribution of terminal equity /
  max drawdown, reported in the final HTML report only.

## Hard stops (checked after every iteration)
1. 4 consecutive iterations with no VALIDATE-expectancy improvement over
   the current champion → stop looping.
2. Champion's VALIDATE expectancy declines twice in a row across
   re-checks → stop.
3. Any variant with Sharpe > 3 or win rate > 75% → STOP immediately,
   do not log as a candidate, audit for lookahead bias / bugs first
   (assume bug until proven otherwise). This exact failure mode was
   already reproduced empirically with the legacy same-bar-close backtester
   (see research_log.md entry 0).
4. Data integrity issues (gaps, duplicate timestamps, timezone mismatch)
   → stop and fix data layer before continuing.

## Promotion rule
A variant becomes champion only if, on VALIDATE:
- expectancy beats the current champion, AND
- result is stable under ±20% perturbation of its own parameters, AND
- trade count ≥ 100 (pooled across the symbol basket).

## Final phase
- Run the single crowned champion exactly once on the locked HOLDOUT set.
- Apply multiple-testing correction: report how many variants were tried
  and judge the holdout result in that light (a lucky winner among N tries
  is expected some fraction of the time by chance alone).
- Verdict — exactly one of:
  - **EDGE PLAUSIBLE**: holdout expectancy positive and within 40% of
    validate expectancy → recommend 60-day paper trading only.
  - **INCONCLUSIVE**: holdout weaker but still positive → recommend
    extending paper trading, do not re-loop.
  - **NO EDGE**: holdout flat or negative → report honestly, do not
    rescue it with further tweaks.
- Produce `backend/research/report.html` with: registry table, champion
  equity curve (VALIDATE+HOLDOUT segments only), Monte Carlo distribution,
  verdict, and lessons-learned list.
