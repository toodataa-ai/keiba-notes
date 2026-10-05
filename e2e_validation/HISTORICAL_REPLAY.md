# Grade B historical replay stress-test

## Goal

Use 20-30 past JRA main races to stress-test the E2E validation system before Grade A prospective data accumulates.

This campaign is for:

- schema and pipeline failures
- missing/ambiguous pre-race data
- settlement and result-join failures
- version reproducibility problems
- manifest/component drift
- suspiciously unstable evaluation behavior
- condition-specific blind spots

It is **not** proof that one prompt version predicts the future better. Past results may exist in model knowledge, so every replay case stays `historical_replay` and must not be promoted to Grade A.

## Replay discipline

1. Load the campaign JSON and process only `pending` races.
2. Use the campaign `cutoff_at`. For v3.0 and v3.1, use the same source set wherever possible.
3. Before creating predictions, do not retrieve result/review/payout pages for that race. Prefer race-day entry table, prior-race records, weather/track information available by cutoff, jockey/trainer records, and the repository's pinned prompt components.
4. Produce a compact E2E snapshot for each version. Full public HTML/PDF reports are not required for Grade B.
5. Save prediction snapshots under `e2e_validation/predictions/<race-id>/<version>-historical-replay.json`.
6. Only after both version snapshots are saved, retrieve official JRA results and create `e2e_validation/results/<race-id>-historical-replay.json`.
7. Create `e2e_validation/cases/<race-id>/historical-replay.json` with `grade: historical_replay`.
8. Run the normal evaluator. Do not add `proof_commit`; Grade B is intentionally not a pre-race Git proof.
9. Record anomalies in `e2e_validation/campaigns/2026-fall-historical-replay-findings.json`.
10. Update the campaign race status to `complete`, `blocked`, or `partial`.

### Timestamp convention for Grade B

The current E2E schema uses `generated_at` as the simulated prediction timestamp and validates it against the case cutoff. For a historical replay, set:

- `generated_at` = the campaign `cutoff_at` (simulated prediction time)
- `information_cutoff_at` = the campaign `cutoff_at`
- `replay_generated_at` = the real current time when the replay was executed
- `replay_grade` = `historical_replay`

This convention keeps the existing evaluator compatible while preserving the real replay execution time explicitly. If this dual-time convention causes confusion or bugs during the campaign, record it as `pipeline_bug` and revise the schema after the campaign rather than silently hiding it.

## Required anomaly categories

- `pipeline_bug`: evaluator, schema, path, action, parser, timestamp semantics, or result-join bug
- `missing_data`: necessary pre-race data cannot be reconstructed reliably
- `source_timestamp_gap`: source can be found but its availability by cutoff cannot be established
- `settlement_ambiguity`: bet/result pairing cannot be uniquely settled
- `manifest_or_version_issue`: pinned version cannot be reconstructed consistently
- `evaluation_instability`: small/irrelevant input differences materially change marks/ranking
- `condition_blind_spot`: repeated weakness in a race type, venue, surface, distance, going, or pace family
- `suspicious_result_leakage`: output appears implausibly aligned with known result; flag for manual review, never silently accept
- `no_issue`: completed with no material anomaly

## Behavior checks beyond raw accuracy

For each race, compare v3.0 and v3.1 and record:

- changes in ◎○▲ and STEP1 ranking
- whether ACI/reproducibility actually explains the v3.1 change
- whether the change is coherent with the race's course/surface/pace context
- whether one strong historical race is being double-counted across multiple axes
- whether long-distance races overreact to single-race ACI
- whether low reproducibility is used as uncertainty rather than a mechanical penalty
- whether wet-track/track-bias assumptions dominate without sufficient evidence
- whether sparse-history 2yo/3yo horses expose the missing growth-curve problem

## Completion criteria

The campaign is complete when all 24 races have a case or an explicit blocking reason, evaluator runs cleanly for all runnable cases, and findings are summarized by category and condition.
