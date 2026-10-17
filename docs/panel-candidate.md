# Chronological panel experiment

PANEL-01 changes the native model's input adapter. Four chronological sampled frames are pasted into one fixed canvas, with each original presentation timestamp in its own header. Two panels cover the same coarse samples used previously. The legal gate, detail prompt, confidence threshold, extraction schedule and global event cap remain unchanged. This is an input/runtime experiment, not a newly trained detector.

The reason for this experiment is a reproducible synthetic positional failure of the earlier multi-image input. A red region was detected in the last image but missed in earlier positions. Increasing the native vision batch alone reproduced the same failure pattern. That observation does not establish its exact internal cause.

The adapter preserves the pixels of each already sampled source image when composing the panel: no additional crop or resize. The native transport subsequently encodes the panel as JPEG, and the model still performs its normal image preprocessing. The registered canvas, pixel budget and small-object dimensions are in `config/panel-protocol.json`; these are configuration values, not quality measurements. Public evidence continues to use actual original-video JPEG frames with original PTS, never the diagnostic panel.

Each panel is evaluated separately. A coarse gate uses the logical OR across panels; it does not jointly reason about an action spanning the boundary between them. Sparse temporal coverage and the absence of cross-panel context remain limitations. Reading frame labels and selecting a precise event frame are not established by the simple red-region controls.

Before real TRAIN inference, generated controls must pass for an absent object, an object in every panel position, smaller objects in several positions, and a domain-negative empty scene. These controls test input observability and a basic negative, not banking actions, legal reasoning or generalization.

If synthetic controls pass, the experiment reuses the exact seeded balanced TRAIN selection from GATE-01. This development control has already been observed and is not independent evidence. All acceptance criteria were retained. A failed control stops before TUNE. HOLDOUT stays closed. Full upload-to-result latency and actual event/frame localization require separate checks before deployment.

Machine-readable source registration and results remain local under `.private/panel-control`. Only fixed-schema summaries and aggregate measurements feed `docs/claim-ledger.csv`. No bank-video observations or employee transcript are exported to the code repository.

## Completed measurement

The generated controls passed 9 of 9 cases, including all large-object positions and the registered small-object stresses. This confirms a limited synthetic input improvement over the previous multi-image failure; it does not show useful bank-video detection.

The same reused TRAIN development control completed 8 of 8 videos with no technical failures. TN / FP / FN / TP = 4 / 0 / 4 / 0; recall 0.000, specificity 1.000, balanced accuracy 0.500, F1 0.000. Both coarse gate and final output were always negative. The candidate failed its frozen acceptance criteria and is rejected for deployment. TUNE was not run; HOLDOUT remains closed.

Complete engine calls averaged 29.375250 seconds, maximum 29.829000 seconds. These exclude upload, queue and model load. The separate model-load measurement was 10.281000 seconds. Device-wide sampled GPU memory peaked at 4105 MiB, including other processes. These are not a public API SLA or a per-process allocation measurement. No true-positive timestamp error can be computed.

Source checksums and frozen inference code/configuration were unchanged. The full implementation suite passed 49 tests; those tests do not measure detection quality. All numerical results are reproduced in the claim ledger from typed safe summaries. Further transcript work was cancelled by the user, with private ASR files retained.
