"""
Runs the single crowned champion exactly once on the locked HOLDOUT set.
Applies multiple-testing correction commentary and issues exactly one
verdict: EDGE PLAUSIBLE / INCONCLUSIVE / NO EDGE.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import load_split_config, run_variant_pooled, monte_carlo

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(OUT_DIR, "champion.json")) as f:
    champion = json.load(f)

if champion is None:
    print("No champion — nothing to run on holdout.")
    sys.exit(0)

N_VARIANTS_TRIED = 9  # iterations actually run before the loop stopped (see registry.csv)

split_config = load_split_config()
result = run_variant_pooled(champion["params"], split_config)
val_m, hold_m = result["validate"], result["holdout"]

validate_expectancy = val_m["expectancy"]
holdout_expectancy = hold_m["expectancy"]

# Multiple-testing correction: with N variants tried and no correction for
# multiplicity, some fraction of "winners" are expected to be noise. We do
# not compute a formal p-value here (trade returns are autocorrelated/non-iid
# so a naive t-test would be misleading) — instead we widen the bar: holdout
# must not just be positive, it must retain a meaningful fraction of the
# validate edge, specifically to guard against the champion being the best
# of N=9 noisy draws.
ratio = (holdout_expectancy / validate_expectancy) if validate_expectancy != 0 else 0

if holdout_expectancy > 0 and ratio >= 0.60:
    verdict = "EDGE PLAUSIBLE"
    recommendation = "Promote to 60-day paper trading only. Do not go live with real capital yet."
elif holdout_expectancy > 0:
    verdict = "INCONCLUSIVE"
    recommendation = "Extend paper trading further before any promotion decision; do not re-loop or re-tune on this holdout."
else:
    verdict = "NO EDGE"
    recommendation = "Do not deploy. Report honestly; do not rescue with further tweaks."

# Note: SPEC.md's "within 40% of validate expectancy" bar means ratio >= 0.60;
# kept consistent with the ratio check above.

report = {
    "champion": champion,
    "n_variants_tried": N_VARIANTS_TRIED,
    "validate": val_m,
    "holdout": hold_m,
    "ratio_holdout_to_validate": round(ratio, 3),
    "verdict": verdict,
    "recommendation": recommendation,
    "monte_carlo_validate_plus_holdout": monte_carlo(
        [t["r_multiple"] for t in result["trades_validate_raw"] + result["trades_holdout_raw"]]
    ),
}

with open(os.path.join(OUT_DIR, "holdout_result.json"), "w") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
