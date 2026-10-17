# UI change management / transitional LAB (2026-10-17)

This is a *non-destructive transition*. LAB's new public gateway is \`docs/lab/index.html\`.
The underlying experimental files currently remain under \`docs/staging/\`; DO NOT
describe the physical environments as fully separated yet. Do not move existing
simulator image/JS paths while dependencies are unresolved.

## Three lanes
- PRODUCTION: \`main/docs\` legacy GitHub Pages, approved UI only.
- STAGING: \`docs/staging\`, eventually reserved for acceptance-tested release candidates.
- LAB: \`docs/lab\` dashboard linking to existing experiments without copying predictions.
  Existing paths will move here only in a separately approved, dependency-audited change.

The GitHub-owned manifest \`.github/lab/feature-registry.json\` lists individual UI
features, ownerless phase and manual approval status. The GitHub Action
\`.github/workflows/lab-change-board.yml\` automatically rebuilds
\`docs/lab/change-board.json\` from Git blob SHA and last-change commits on changes
to staging / config. **CI never changes approval status**.

## Safe UI-only release
1. Review source + candidate in staging and get explicit user approval.
2. Diff an exact allowlist of UI files; forbid staging-wide/branch-wide copying.
3. Assert SHA equality on all protected data/PDF/E2E proof trees pre/post release.
4. Validate live GitHub Pages byte-parity and prediction registry consistency.
5. If any check fails, report a blocker rather than mark success.
6. Data publication for JRA/NAR continues separately under its existing strict
   immutable-proof policies without human approval for ordinary data refreshes.

## Protected
Never overwrite: \`docs/data/races.json\`, \`docs/reports/\`, \`docs/pdfs/\`,
\`e2e_validation/\`, \`local_racing_shadow_v1/\`, and formal prediction sources.
The LAB dashboard and source registry are UI metadata only.

## Updating feature statuses
Modify \`.github/lab/feature-registry.json\` **only** based on explicit decision
or grounded completion. A changed Git SHA does not mean approved, tested, or
published. The board generator derives source facts and preserves manual phases.
