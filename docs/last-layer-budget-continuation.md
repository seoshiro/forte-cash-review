# Authorized last-layer wall-budget continuation

The first run stopped at the registered 600-second learning budget after 27 of 48 CV fits. That was a technical timeout; it did not establish adapter quality. Its original source, configuration, registration, reports and artifacts are preserved.

The user explicitly authorized continuation with a 1800-second cap, unchanged model/steps/folds/threshold/regularization and no partial-metric selection. Source inspection found no durable optimizer, RNG or completed-fit checkpoints, so this stage is one complete restart from step zero. No resume is claimed.

New registration SHA: `66bd2c2ab9f49ee073c37e31b7379035e3e76bd0f64b5d6381b3efa1e6dcca36`; prior SHA: `f0aabcef076d54fe7997a8abd27aa0dccb50abede8a6a651b3fb2e0137a8d077`.

Only protocol identity and two wall caps changed: owned monitor cap and learning-phase cap are now 1800 seconds. The owned monitor cap includes prefix regeneration, replay, all 48 CV fits, two fullTRAIN diagnostic fits, persistence and cleanup; its deadline always dominates the phase cap. Prefix cap 900 seconds, GPU reserved cap 5000 MiB, host working-set cap 4096 MiB, CPU threads two and one worker remain unchanged. No computational optimization or altered training trajectory was introduced.

All 26 TRAIN prefixes and both views are regenerated and must pass the same zero-adapter replay before training. The same original 24 groups, 500 steps, fixed seeds, matched frozen head, cosine baseline, thresholds and acceptance gates apply. TUNE and HOLDOUT remain closed. Binary decisions cannot validate action types, descriptions, rules or evidence relevance.

Run artifacts are private in `.private/xclip-last-layer-budget1800`. The current baseline and research UI 8768 stay unchanged. Presentation screenshots remain in `.private/presentation-ui`, with synthetic labels, until final handoff.

The new adapter pack is not connected to UI 8768: that service intentionally still uses the original cosine prototype engine. Even passing all exploratory OOF gates would require a separately verified live adapter/head inference path and a fixed independent assessment plan before any deployment or semantic claim.

The authorized restart failed with `RuntimeError` after 37 of 48 CV fits. Monitor wall was 1064.078 seconds, below the 1800-second cap; worker exit code 1, deadline_exceeded=false, cleanup_complete=true. The failure report did not persist an allowlisted cause code or runtime resource high-water marks. Its exact origin cannot be reconstructed from the saved reports. It must not be called another timeout, an established memory failure, or a model-quality failure.

Replay again passed all 26 TRAIN inputs / 678 windows / two views: maximum same-forward and historical embedding error 0, PTS error 0, minimum historical cosine 0.9999999999999998; phase wall 252.094 seconds. The integrity helper verified the original registered sources, source/cache bytes, saved prefix hashes and cleanup after failure.

There is still no complete OOF, complete comparison with matched head/baseline, final adapter pack, or valid quality-based acceptance/rejection. Partial fit metrics were not inspected or used for selection. Operational decision: preserve the original baseline and do not promote the adapter. No additional fit, replay, restart, weight audit, TUNE or HOLDOUT analysis was launched after this failure.

Exact blocker: obtaining the complete registered OOF in `.private/xclip-last-layer-budget1800` is blocked by the recorded RuntimeError, whose origin was not saved. The single authorized full restart executed and has a known failed outcome; no approval denial is involved. Further computation would need a separately fixed continuation stage. The narrow technical next step is allowlisted failure-origin and resource telemetry, followed by a targeted identical-fit diagnostic, with immutable completed-fit/optimizer/RNG checkpoints before any further full run. Preserve ML choices; do not infer a cause from post-run free RAM/VRAM snapshots.

Types, physical explanations, rule applicability, evidence relevance, independent camera quality, live competition API and jury readiness remain unaccepted. Source/synthetic regression results are reported separately in the checkpoint; they do not validate detector quality.

Final regression: 407 source/synthetic tests passed, zero failures/errors/skips. JUnit SHA: `714491a32f97ac054192d42da7101e3286385ddb611dfb94f39da172fd08af85`. The first regression attempt found one report-directory default-binding bug; it was corrected and the complete suite passed. This did not modify any registered ML file or repeat bank-video computation.
