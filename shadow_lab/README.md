# Seven-theme prospective Shadow runtime (Draft; no production release)

This is executable research, separate from immutable v1 design registration.
No formal STEP1/STEP2 module, prediction, settlement, HTML/PDF or old proof is
rewritten. New records live under `shadow_lab/evidence/`. Derived staging
progress lives in `docs/data/jra_shadow_experiment_status_v1.json` (`runtime`)
and `docs/lab/data/shadow-runtime.json`. The existing staging roadmap renders
these on its seven existing cards; `all-experiments.html` redirects there.

## Daily operation

After the ordinary manual morning / research / evening workflows finish,
`jra-shadow-runtime.yml` runs separately via `workflow_run`. Formal completion
does not depend on Shadow. Once the workflow exists on the default branch this
hook is active; a Draft branch alone cannot activate default-branch events.
Its only push destination is `experiment/jra-shadow-evidence-main-20261102`, never main. The older `experiment/jra-shadow-evidence-v1` branch is retained unchanged; its old baseline tree must not be merged into the newer main checkout.
The workflow artifact is a staging preview, not a production Pages deployment.

For a Draft checkout or a local manual instruction:

```sh
python -m shadow_lab.operations morning
python -m shadow_lab.operations research
python -m shadow_lab.operations evening
python -m shadow_lab.runtime prepare --packet shadow_lab/requests/DATE/RACE.json
python -m shadow_lab.runtime seal --branch experiment/BRANCH
python e2e_validation/validate_all_experiment_designs_v1.py
```

`operations` uses the current JST date. It automatically finds canonical formal
forecasts, original model files, exact recovered inputs, existing fixed sample
plans and experience snapshots. It never chooses a race by its result. Missing
forecasts / probabilities / full-field scenario features are recorded as gaps.
Research-only snapshots containing horse numbers and career starts are **not**
converted into invented probabilities. A genuine full-field forecast can enter
through the existing `experience_regime_v1/step1_frozen/WEEK/RACE.json` capture.
All three groups accept such forecasts without requiring a formal STEP2 or a
nine-horse field. Existing weekly hash sampling config and plans are unchanged.

## Frozen runtime1 hypotheses

| Theme | Candidate | Preserved / required inputs |
|---|---|---|
| Pace | Expected S/M/H factor② grade; multiply win weight by exp(0.1 × grade delta) | Other eight grades; full-field scenario grades and source |
| Track | Stage B official-input pilot probabilities × per-going factor③ grades, bounded bias ±0.5; same 0.1 tilt | Other eight grades; Tokyo/Kyoto only; source-backed inner/outer evidence required |
| Tickets | Original current purchase lines with positive low-scenario EV, equal 100 yen, at most 6000 yen | STEP1/marks; original exact quotes; eight-type evaluations and rejection list |
| Young horses | Uniform-prior shrinkage E0 .20 / E1 .10 / E2 .05 | Other grades; all career starts; formal observation screen must pass |
| E0/E1/E2 | Same respective win-probability shrinkage, recompute PL top3 marginals | Independent fixed-sample research; all collateral groups reported |

These coefficients are hypotheses, not calibrated superiority claims. A code or
candidate version change invalidates combination with runtime1 evidence; old
files remain available and are reported as a different-version blocker. No
result-dependent parameter tuning. Model code hash is saved in every pair.
V1 design records remain immutable provenance, not the runtime's progress source.
Track Stage B is explicitly still an unvalidated pilot.

The current canonical purchase overlay (v3.15 / v3.16, when present) is required
as baseline. Factor candidates reuse the current STEP2 algorithm in memory.
Internal pending/source-shaped values are never written as formal predictions.
Candidate execution has a 60-second deadline and a prestart deadline; timeouts
are blockers. It never delays the formal workflow or backfills a missed race.

## Packet contract

Formal packet: `baseline_path`, `input_path`, `official_purchase_path` (required
if current canonical publication has an overlay), `information_cutoff_at`
(exactly current formal final-bet freeze), `conditions` (venue, surface, rain,
meeting_week; absent values disclosed as unknown), `features`.

Every feature block has `path`, `sha256`, official `url`, `observed_at` <= cutoff.
The referenced file must contain the evidence before seal.

- `pace`: `scenario_probabilities` keys S/M/H sum 1; `by_horse[no]` maps S/M/H
  to C/B-/B/B+/A/A+ grades. Use prestart queue evidence; do not infer from result.
- `track`: `pilot_input` follows `tokyo_kyoto_going_shadow_v1.capture` including
  official moisture/JMA weather time and matching race/venue/surface/cutoff;
  `by_horse[no]` contains `going_grades` and `bias_adjustment` in [-.5,.5].
- `experience`: `starts_by_horse` covers the whole field. Exact 0 / 1–3 / >=4
  classification; canonical collection snapshots supply this automatically.
- Research packet instead has `research_snapshot_path`, `sample_plan_path`,
  the same cutoff and experience feature. Full forecast must contain each
  runner's genuine `predicted_win_probability` and `predicted_top3_probability`,
  fixed timestamp, `no_odds_used: true`, `no_synthetic_predictions: true`.

## Proof and reconciliation

`prepare` writes one exclusive pair per (theme, race_id), both complete forecasts,
shared cutoff, hashes and fixed code version. It refuses overwrite or late runs.
`seal` pushes a Git proof tree before start, then creates a GitHub commit status
`shadow/prestart-sealed`. Its immutable server `created_at`, status ID and SHA
go in a separate receipt. Git author dates alone never prove prestart presence.
Any push/status/deadline failure leaves the record uncounted and visible.
The postrace audit queries that actual GitHub status and reads original bytes
from `proof_commit`, not a mutable working copy. Both sides and input evidence
must be in that tree. Offline/API failures count zero with explicit blockers.

Evening imports canonical official result extracts into new Shadow-only captures
and checks race, complete field, result/payout source and hashes. Scratches,
incomplete results or dead heats require review and cannot silently enter Grade A.
No archive, original result, bet or original ROI is changed.

Formal targets: 20 **distinct** valid races per theme. Research targets: >=30
same-horse win+top3 probabilities with results, >=3 races, >=2 ISO Monday weeks,
separately for each group. Duplicate receipts never increase counts. Missing
results remain sealed-awaiting-result, not valid comparisons.

Metrics include Brier/log loss, calibration gap, top-three capture, honmei top3,
ROI from actual official per-100-yen payouts and maximum per-race loss. Venue,
surface, rain and meeting-week splits disclose unknown inputs. Frozen rules,
all seven themes, independent weeks and a later holdout review guard against
overfitting. Thresholds only open A/B/C **manual review**; adoption stays false.
No automatic approval or production release command exists in this runtime.

## Verification

```sh
python -m unittest shadow_lab.test_runtime -v
node shadow_lab/test_candidate.mjs
python shadow_lab/browser_audit.py
python e2e_validation/validate_all_experiment_designs_v1.py
```

Engine E2E uses explicitly synthetic future timing and a bounded synthetic quote
universe. Its temporary quote file is deleted and is never an evidence pair.
Real execution attempts and their unmet prerequisites are saved separately.
The CI release-history fix copies only the existing pending-v1.06 record into
the private registry. Published releases, their SHAs and pending verification
state remain unchanged; no new release is asserted.

## Manual decision records

After reviewing the metrics, save a new `shadow_lab/evidence/reviews/THEME.json`
with `decision` (theme, candidate, classification A/B/C, decision, metrics_sha256),
`report_path`, `report_sha256`, `github_comment_id`, and all checks
(accuracy, expected_value, side_effects, holdout, overfit, conditions).
The repository owner must explicitly post one line beginning `SHADOW_DECISION `
followed by exactly the sorted, compact JSON decision object. The audit queries
that real GitHub comment, verifies owner identity and report/metric hashes, and
then displays rejected / continue_collecting / approved_for_release, or research
only diagnostic_reviewed. A changed report or new metrics require fresh review.
This records approval judgment only: adoption remains false until an independent
approved production release. No production-changing API is present here.
