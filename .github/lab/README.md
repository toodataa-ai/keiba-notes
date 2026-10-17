# LAB / STAGING / PRODUCTION — permanent site routing policy

Mandatory persistent skill: .github/skills/keiba-site-change-routing/SKILL.md
Mandatory agent entrypoint: AGENTS.md
Operational checklist: .github/skills/keiba-site-change-routing/references/release-checklist.md

As of 2026-10-17:
- PRODUCTION: main/docs user-approved UI and independent latest canonical DATA.
- STAGING: docs/staging/ ordinary 11 HTML pages are generated from the current
  production UI via .github/scripts/staging-baseline-v2.py with stage-only
  identification and links. Any changes to features already present in production
  are first staged and verified here, then require explicit release approval.
- LAB: docs/lab/ has active copies of unpublished simulators, course layout
  research, purchase prototypes and historical previews. Changes to features
  not yet in production must first go here, not to STAGING or production.
- DATA: formal prediction, result, review, settled bets, PDF and proof remain
  on the independent canonical evidence-validated publishing workflow.

LAB change inventory: .github/lab/feature-registry.json
Generated Git evidence board: docs/lab/change-board.json
LAB browser page: docs/lab/index.html
Prebaseline archive: docs/lab/archive/staging-prebaseline/
Legacy experimental URLs under staging redirect to LAB; keep compatibility
assets for rollback rather than deleting them.

Promote existing production features as exact user-approved UI behavior and
a selective reviewed code delta, NEVER as a bulk staging directory copy.
Staging wrappers (banner, noindex, base tag, staging links, prototype data
overrides) are not production UI. LAB requires a distinct decision to promote
a feature to STAGING first; production still requires explicit user approval.

WARNING: jra-staging-week-mirror-publish.yml regenerates staging from
production on production template changes. Preserve unrelated unapproved
staging candidates in LAB or a separate immutable Git snapshot before
allowing any such regeneration; never let mirror erase outstanding work.

The old jra-site-ui-release-v1 workflow has a branch-composition gate and
v1.01-specific assumptions; do not bypass it. Current Pages source remains
main/docs. Older staging instructions are historical reference, not current
general-purpose release commands.

Never overwrite or roll back docs/data, docs/reports, docs/pdfs,
e2e_validation, local_racing_shadow_v1, sealed prediction, final_bets
or proof via UI release. Validate protected tree SHAs and live HTTP bytes.
The registry tracks approval MANUALLY: a source SHA update is not approval.
