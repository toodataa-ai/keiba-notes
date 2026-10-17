# AGENTS.md — toodataa-ai/keiba-notes

## Read the durable website-change skill before any changes
Always first open .github/skills/keiba-site-change-routing/SKILL.md and its references/release-checklist.md when asked to modify website UI, release changes, create features or develop the simulator.

Decide the environment by whether a feature is actually available on the current production user-facing website, not by whether its files merely exist in the repository or LAB URL is public.

- Existing production feature: develop the UI change in STAGING (docs/staging/), verify, request explicit user production approval, then selectively apply the approved UI delta to PRODUCTION.
- Not present in production (for example, race simulator, unapproved course designs): develop ONLY in LAB (docs/lab/). Move LAB to STAGING only after a separate promotion decision; move STAGING to PRODUCTION only with user approval.
- Official predictions/results/reviews/final_bets/PDF/proof: use the independent canonical DATA workflows with their strict evidence gates. Never overwrite via UI release.
- Mixed request: split the LAB, STAGING and DATA scopes. Do not mix their approvals or commits.

As of 2026-10-17, GitHub Pages production is main/docs, and normal staging UI pages mirror the production template via .github/scripts/staging-baseline-v2.py. The mirror workflow may overwrite an unapproved staging candidate; preserve any such candidate separately before a baseline sync.

"Staging then directly to production" means the same approved appearance/behavior, NOT copying entire staging files including STAGING banners, noindex, base links or prototype data replacements. Never copy full staging or LAB directories to production.

Explicit user approval is always required for PRODUCTION UI. Verify an exact UI-file allowlist, unchanged Git tree SHA for docs/data, docs/reports, docs/pdfs, e2e_validation and local_racing_shadow_v1, live production HTTP byte parity, and latest prediction/settlement integrity. Preserve all current race archives and avoid rolling back concurrent data updates.

The old jra-site-ui-release-v1 workflow is v1.01-specific and currently gated by a branch-composition activation file. Do not remove that gate or treat the old branch as the production release path.

Record feature state in .github/lab/feature-registry.json. Git commits do not imply user approval. If legacy docs contradict this routing skill, follow the skill and report the conflict.
