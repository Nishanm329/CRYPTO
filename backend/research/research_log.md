# Strategy Research Log

### Iteration 0 (prior session, empirical pre-check via legacy combination_backtester)
- Tried: Naive in-sample "best combo per symbol" selection using the existing combination_backtester (same-bar-close entry, no train/validate/holdout split).
- Happened: The "winning" combo differed per symbol (e.g. ema_rsi_macd_vol won on BTCUSDT but was the WORST performer on ETHUSDT); low-trade-count combos (full_confluence, n=1-4) produced spurious 75-100% win rates.
- Implies: naive in-sample combo picking is pure overfitting — this is exactly why this loop enforces TRAIN/VALIDATE/HOLDOUT discipline and a hard stop on any result with Sharpe>3 or win-rate>75%, treating such results as bugs until proven otherwise.

### Iteration 1: H0_baseline_ema7_25
- Tried: EMA7/25 cross, ATR*2 stop, 2R target, no filters. Establishes the reference point before adding any filters.
- Happened: TRAIN expectancy=-0.0399R, VALIDATE expectancy=0.0031R, win_rate=38.39%, PF=1.005, sharpe=0.035, trades=831, maxDD=29.615R.
- Implies: beat current champion on VALIDATE but failed the ±20% parameter-perturbation stability check — not promoted.

### Iteration 2: H1_adx_trend
- Tried: Add ADX>20 trend-strength filter to skip choppy/ranging regimes where EMA crosses whipsaw.
- Happened: TRAIN expectancy=-0.0149R, VALIDATE expectancy=-0.0007R, win_rate=38.56%, PF=0.999, sharpe=-0.008, trades=376, maxDD=22.767R.
- Implies: beat current champion on VALIDATE but failed the ±20% parameter-perturbation stability check — not promoted.

### Iteration 3: H2_htf_ema200
- Tried: Require price to be above (LONG) / below (SHORT) EMA200 at signal time — a same-timeframe proxy for higher-timeframe trend alignment.
- Happened: TRAIN expectancy=0.0666R, VALIDATE expectancy=0.0404R, win_rate=39.86%, PF=1.063, sharpe=0.461, trades=429, maxDD=20.595R.
- Implies: beat current champion on VALIDATE but failed the ±20% parameter-perturbation stability check — not promoted.

### Iteration 4: H3_volume_confirm
- Tried: Require volume > 1.1x its 20-period average at the cross candle, to filter out low-conviction crosses.
- Happened: TRAIN expectancy=0.0687R, VALIDATE expectancy=0.122R, win_rate=42.41%, PF=1.197, sharpe=1.358, trades=382, maxDD=11.071R.
- Implies: new champion — beats prior best on VALIDATE expectancy and passed perturbation stability check.

### Iteration 5: H4_adx_htf_combo
- Tried: Combine ADX trend filter with EMA200 alignment filter — stacking the two strongest single filters.
- Happened: TRAIN expectancy=0.1409R, VALIDATE expectancy=0.0377R, win_rate=39.79%, PF=1.061, sharpe=0.438, trades=191, maxDD=13.337R.
- Implies: did not improve on current champion's VALIDATE expectancy.

### Iteration 6: H5_rsi_not_extreme
- Tried: Skip entries where RSI is already overbought (>75) or oversold (<25), avoiding late/exhausted entries.
- Happened: TRAIN expectancy=-0.0404R, VALIDATE expectancy=0.0026R, win_rate=38.4%, PF=1.004, sharpe=0.03, trades=823, maxDD=30.281R.
- Implies: did not improve on current champion's VALIDATE expectancy.

### Iteration 7: H6_wider_stop
- Tried: Widen stop to 3x ATR with a 1.5R target (same total distance budget, less noise-driven stop-outs, lower TP bar).
- Happened: TRAIN expectancy=-0.0087R, VALIDATE expectancy=0.0068R, win_rate=45.25%, PF=1.013, sharpe=0.095, trades=831, maxDD=30.637R.
- Implies: did not improve on current champion's VALIDATE expectancy.

### Iteration 8: H7_ema7_99_baseline
- Tried: Swap EMA7/25 baseline for EMA7/99 — a slower cross meant to reduce false signals at the cost of fewer trades.
- Happened: TRAIN expectancy=0.0514R, VALIDATE expectancy=0.0629R, win_rate=40.82%, PF=1.1, sharpe=0.715, trades=392, maxDD=23.536R.
- Implies: did not improve on current champion's VALIDATE expectancy.

## Loop stopped early: 4 consecutive iterations without VALIDATE-expectancy improvement (stopped after iteration 8).

## Champion: H3_volume_confirm (iteration 4), VALIDATE expectancy = 0.122R

Note on the "champion validate-expectancy declining twice in a row" hard stop: this engine is deterministic (same CSV data, same code) so a bare re-run cannot produce a different result. That rule is enforced instead via the no-improvement-for-4-iterations stop above, which is the deterministic-engine equivalent of catching a decaying/non-robust champion.
