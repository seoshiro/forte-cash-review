# Last-layer failure diagnosis

The isolated candidate next fit completed all 500 original optimizer steps. Original recipe, seed, loss, views, projection and TRAIN fold were unchanged. No predictions, training report, held-video inference or quality metrics were requested. The saved-prefix zero-adapter replay again had maximum absolute error 0.

The old counter is ambiguous: 37 completed fits identifies the next arm as adapter/group ordinal 19, fit ordinal 38, but the original counter was updated before the post-fit resource check. The historical exception could therefore have occurred at that boundary before fit38 started. The diagnostic does not claim to identify the exact historical throwing operation.

Diagnostic registration SHA: `16463126a8297f504975c5b7aaaf05f400f47a8dcf85d7bed0196b51034fda30`. Owned monitor wall: 47.079 seconds. Peak process working set: 1799.19140625 MiB; Torch peak reserved: 226 MiB; minimum available RAM: 2430.1171875 MiB; minimum free GPU: 4772 MiB. These are this isolated technical run's measured resources, not end-to-end API latency or costs for every fold.

The new error classifier returns only an allowlisted exception name/category, relative code-file/line/function locations and finite numeric resource fields. It never emits the raw error message, frame locals, tensor contents, source lines, clip filenames or observations. Categories distinguish CUDA OOM/runtime, host memory guard/OOM, GPU guard, shape, determinism, numerical instability, deadline and unknown technical errors. An error saves its traceback locally with capture_locals=false; those private files must never be read through cloud tools or published. The diagnostic also persists resource observations during the run.

Four generated-prefix fits of the same 500-step recipe produced exactly equal parameter values. All model-parameter weak references were already dead before explicit GC; GC collected zero objects in this probe, and Torch allocated memory remained 64 MiB before/after GC on every repeat. This small synthetic probe did not expose model-parameter lifetime leakage. It is not proof for every full-sized real fold and does not identify the historical failure cause. No cleanup patch or blind full repeat was applied.

The original failed full run remains unchanged: RuntimeError after 37/48 CV fits, wall1064.078 seconds below cap1800, known failed outcome and cleanup confirmed. Correct completed-fit predictions/weights/optimizer states were not persisted, so those 37 fits cannot be reliably resumed. There is still no full OOF/F1, final adapter pack or quality comparison. Baseline remains selected operationally; adapter is not promoted. TUNE/HOLDOUT remain closed.

Next diagnostic boundary, if separately chosen: reproduce the preceding fixed sequence up to the failure boundary with the new allowlisted diagnostics and atomic per-completed-fit checkpoints, preserving all ML choices. This is broader than the already completed single-fit diagnostic. Do not describe an unchanged full repeat as a known cause-specific repair, and do not claim numerical failure or resource leakage without evidence.

420 source/synthetic regression tests passed, zero failures/errors/skips. They validate implementation and gateway controls, not bank-event detection. The existing local research UI8768 is healthy; original videos, cache, baseline, UI and the three private synthetic presentation screenshots remain preserved. No new credentials, persistent grants, public origin/tunnel or OS settings were created/changed in this stage.

[Research delivery runbook](research-delivery-runbook.md) | [Failed full restart](last-layer-budget-continuation.md) | [Claim ledger](claim-ledger-index.md).
