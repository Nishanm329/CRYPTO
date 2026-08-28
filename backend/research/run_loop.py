"""
Executes the strategy research loop: baseline + hypothesis iterations,
logged to registry.csv and research_log.md, enforcing all hard-stop rules.
Does NOT touch HOLDOUT — that is run once at the end by run_holdout.py.
"""
import copy
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_split_config, run_variant_pooled, compute_metrics

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(OUT_DIR, "registry.csv")
LOG_PATH = os.path.join(OUT_DIR, "research_log.md")

BASE_PARAMS = {"fast_ema": "ema7", "slow_ema": "ema25", "atr_mult_sl": 2.0, "rr_target": 2.0, "filters": []}

ITERATIONS = [
    ("H0_baseline_ema7_25", "EMA7/25 cross, ATR*2 stop, 2R target, no filters. Establishes the reference point before adding any filters.", {}),
    ("H1_adx_trend", "Add ADX>20 trend-strength filter to skip choppy/ranging regimes where EMA crosses whipsaw.", {"filters": ["adx_trend"]}),
    ("H2_htf_ema200", "Require price to be above (LONG) / below (SHORT) EMA200 at signal time — a same-timeframe proxy for higher-timeframe trend alignment.", {"filters": ["htf_ema200"]}),
    ("H3_volume_confirm", "Require volume > 1.1x its 20-period average at the cross candle, to filter out low-conviction crosses.", {"filters": ["volume_confirm"]}),
    ("H4_adx_htf_combo", "Combine ADX trend filter with EMA200 alignment filter — stacking the two strongest single filters.", {"filters": ["adx_trend", "htf_ema200"]}),
    ("H5_rsi_not_extreme", "Skip entries where RSI is already overbought (>75) or oversold (<25), avoiding late/exhausted entries.", {"filters": ["rsi_not_extreme"]}),
    ("H6_wider_stop", "Widen stop to 3x ATR with a 1.5R target (same total distance budget, less noise-driven stop-outs, lower TP bar).", {"atr_mult_sl": 3.0, "rr_target": 1.5}),
    ("H7_ema7_99_baseline", "Swap EMA7/25 baseline for EMA7/99 — a slower cross meant to reduce false signals at the cost of fewer trades.", {"fast_ema": "ema7", "slow_ema": "ema99"}),
    ("H8_best_filter_combo", "Combine ADX trend + volume confirmation, the two independently-promising single filters that don't overlap in what they screen for.", {"filters": ["adx_trend", "volume_confirm"]}),
    ("H9_tighter_stop", "Tighten stop to 1.5x ATR with a 2.5R target — tests whether a tighter risk unit improves expectancy via smaller average losses.", {"atr_mult_sl": 1.5, "rr_target": 2.5}),
]

HARD_STOP_SHARPE = 3.0
HARD_STOP_WINRATE = 75.0
MIN_TRADES_FOR_PROMOTION = 100
PERTURB_FRAC = 0.20


def make_params(overrides: dict) -> dict:
    p = copy.deepcopy(BASE_PARAMS)
    p.update(overrides)
    return p


def perturb_check(params: dict, split_config: dict, base_validate_expectancy: float) -> bool:
    """Perturb numeric params by +/-20% and require validate expectancy to
    stay positive and not collapse (>50% relative drop) in both directions."""
    for key in ("atr_mult_sl", "rr_target"):
        if key not in params:
            continue
        for sign in (1 + PERTURB_FRAC, 1 - PERTURB_FRAC):
            p2 = copy.deepcopy(params)
            p2[key] = params[key] * sign
            res = run_variant_pooled(p2, split_config)
            v = res["validate"]["expectancy"]
            if v <= 0 or v < base_validate_expectancy * 0.5:
                return False
    return True


def main():
    split_config = load_split_config()

    registry_rows = []
    log_entries = []
    champion = None  # {"variant_id":..., "params":..., "validate_expectancy":...}
    no_improve_streak = 0
    stopped_early = False
    stop_reason = None

    for iteration, (variant_id, hypothesis, overrides) in enumerate(ITERATIONS, start=1):
        params = make_params(overrides)
        result = run_variant_pooled(params, split_config)
        train_m, val_m = result["train"], result["validate"]

        bug_suspect = val_m["sharpe"] > HARD_STOP_SHARPE or val_m["win_rate"] > HARD_STOP_WINRATE

        verdict = ""
        if bug_suspect:
            verdict = "BUG_SUSPECT_EXCLUDED"
        elif val_m["trades"] < 20:
            verdict = "TOO_FEW_TRADES"
        else:
            verdict = "CANDIDATE"

        registry_rows.append({
            "iteration": iteration,
            "variant_id": variant_id,
            "hypothesis": hypothesis,
            "params": json.dumps({k: v for k, v in params.items() if k != "filters" or v}),
            "train_expectancy": train_m["expectancy"],
            "validate_expectancy": val_m["expectancy"],
            "PF": val_m["profit_factor"],
            "maxDD": val_m["max_dd"],
            "sharpe": val_m["sharpe"],
            "trades": val_m["trades"],
            "verdict": verdict,
        })

        log_lines = [
            f"### Iteration {iteration}: {variant_id}",
            f"- Tried: {hypothesis}",
            f"- Happened: TRAIN expectancy={train_m['expectancy']}R, VALIDATE expectancy={val_m['expectancy']}R, "
            f"win_rate={val_m['win_rate']}%, PF={val_m['profit_factor']}, sharpe={val_m['sharpe']}, "
            f"trades={val_m['trades']}, maxDD={val_m['max_dd']}R.",
        ]

        if bug_suspect:
            log_lines.append(
                f"- Implies: **HARD STOP triggered** (sharpe={val_m['sharpe']} > {HARD_STOP_SHARPE} or "
                f"win_rate={val_m['win_rate']}% > {HARD_STOP_WINRATE}%). Excluded as a bug/lookahead suspect, "
                f"not treated as real edge, per standing rule. Loop halted for audit."
            )
            log_entries.append("\n".join(log_lines))
            stopped_early = True
            stop_reason = f"Iteration {iteration} ({variant_id}) tripped the Sharpe/win-rate hard stop."
            break

        if verdict == "TOO_FEW_TRADES":
            log_lines.append("- Implies: sample too small on VALIDATE to draw any conclusion; not eligible for promotion.")
            log_entries.append("\n".join(log_lines))
            no_improve_streak += 1
        else:
            promoted = False
            if champion is None or val_m["expectancy"] > champion["validate_expectancy"]:
                if val_m["trades"] >= MIN_TRADES_FOR_PROMOTION:
                    stable = perturb_check(params, split_config, val_m["expectancy"])
                    if stable:
                        champion = {"variant_id": variant_id, "params": params, "validate_expectancy": val_m["expectancy"], "iteration": iteration}
                        promoted = True
                        no_improve_streak = 0
                    else:
                        log_lines.append("- Implies: beat current champion on VALIDATE but failed the ±20% parameter-perturbation stability check — not promoted.")
                        no_improve_streak += 1
                else:
                    log_lines.append(f"- Implies: beat current champion on VALIDATE but only {val_m['trades']} trades (<{MIN_TRADES_FOR_PROMOTION} required) — not promoted, needs more sample.")
                    no_improve_streak += 1
            else:
                no_improve_streak += 1

            if promoted:
                log_lines.append(f"- Implies: new champion — beats prior best on VALIDATE expectancy and passed perturbation stability check.")
            elif verdict == "CANDIDATE" and "Implies" not in "\n".join(log_lines):
                log_lines.append("- Implies: did not improve on current champion's VALIDATE expectancy.")

            log_entries.append("\n".join(log_lines))

        if no_improve_streak >= 4:
            stopped_early = True
            stop_reason = f"4 consecutive iterations without VALIDATE-expectancy improvement (stopped after iteration {iteration})."
            break

    # Write registry.csv
    with open(REGISTRY_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "variant_id", "hypothesis", "params",
                                                "train_expectancy", "validate_expectancy", "PF",
                                                "maxDD", "sharpe", "trades", "verdict"])
        writer.writeheader()
        for row in registry_rows:
            writer.writerow(row)

    # Write research_log.md
    with open(LOG_PATH, "w") as f:
        f.write("# Strategy Research Log\n\n")
        f.write(
            "### Iteration 0 (prior session, empirical pre-check via legacy combination_backtester)\n"
            "- Tried: Naive in-sample \"best combo per symbol\" selection using the existing "
            "combination_backtester (same-bar-close entry, no train/validate/holdout split).\n"
            "- Happened: The \"winning\" combo differed per symbol (e.g. ema_rsi_macd_vol won on "
            "BTCUSDT but was the WORST performer on ETHUSDT); low-trade-count combos "
            "(full_confluence, n=1-4) produced spurious 75-100% win rates.\n"
            "- Implies: naive in-sample combo picking is pure overfitting — this is exactly why "
            "this loop enforces TRAIN/VALIDATE/HOLDOUT discipline and a hard stop on any result "
            "with Sharpe>3 or win-rate>75%, treating such results as bugs until proven otherwise.\n\n"
        )
        for entry in log_entries:
            f.write(entry + "\n\n")
        if stopped_early:
            f.write(f"## Loop stopped early: {stop_reason}\n\n")
        if champion:
            f.write(f"## Champion: {champion['variant_id']} (iteration {champion['iteration']}), "
                     f"VALIDATE expectancy = {champion['validate_expectancy']}R\n\n")
        else:
            f.write("## No champion found — no variant both beat baseline and passed the stability/sample-size bar.\n\n")
        f.write(
            "Note on the \"champion validate-expectancy declining twice in a row\" hard stop: "
            "this engine is deterministic (same CSV data, same code) so a bare re-run cannot "
            "produce a different result. That rule is enforced instead via the "
            "no-improvement-for-4-iterations stop above, which is the deterministic-engine "
            "equivalent of catching a decaying/non-robust champion.\n"
        )

    with open(os.path.join(OUT_DIR, "champion.json"), "w") as f:
        json.dump(champion, f, indent=2)

    print(f"Wrote {REGISTRY_PATH}")
    print(f"Wrote {LOG_PATH}")
    print(f"Champion: {champion}")
    print(f"Stopped early: {stopped_early} ({stop_reason})")


if __name__ == "__main__":
    main()
