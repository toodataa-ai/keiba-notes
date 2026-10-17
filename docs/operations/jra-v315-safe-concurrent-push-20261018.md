# JRA v3.15 fail-closed GitHub concurrency recovery (2026-10-18)

Scope: git push reliability only, in the already authoritative v3.15 purchase-only workflow. Does not alter predictors, purchase commands, marks, frozen historical sources, PDF renderer, CSS, or JRA/NAR data.

Root cause: workflow tests take ~1 minute while another process advances main. Git commit made on stale HEAD then direct push failed with non-fast-forward three times. This additively introduces bounded fetch/rebase/push for prestart proof and final publication. Force push never used; merge conflict stops workflow. After rebase use actual pushed HEAD as the prestart proof. All v3.15 source quote fresh-at-seal checks and reader-v1 strict CI remain unchanged.

Previous workflow Git blob: f9618054af98536314187f039a797974d13d4b37
Replacement current Git blob: 908ca58b7b357f6e4f43b194e9ae947e6de085b0
Policy updated solely to pin current workflow hash; original historical blob remains in policy's audit record.
