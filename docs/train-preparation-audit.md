# Preparation audit before temporal learning

The code-only review found four validation defects. The read-only aggregate check found **no corresponding error in the current TRAIN preparation**. These are separate conclusions; the validation fixes are not a model improvement.

| Fixed defect | Change / regression |
|---|---|
| Partial timestamp matching could accept malformed input | Full supported numeric, colon or Russian-unit formats; negative/partial/unit-mismatch examples rejected |
| Positive row could have no point | Positive timestamp required; negative null stays unknown, not zero |
| Saved split insufficiently bound to inputs | Workbook SHA, exact source inventory, saved group map and group split consistency required |
| Nonmonotonic PTS merely reported | Decoding/PTS failures now block manifest acceptance |

Changes are in `scripts/manifest.py`; regressions in `tests/test_manifest_validation.py` and existing generated rotation/VFR tests. No original file, manifest, split, cache or prototype was regenerated or renamed.

## Actual aggregate checks

`scripts/audit_train_preparation.py` compares **all 42 official workbook rows with manifest metadata for integrity**, including non-TRAIN rows. It is not TRAIN-label-only reading. Model fitting and source/cache identity checks then select TRAIN only.

- No label/file mismatch, normalization collision, cross-split group or exact content crossing splits.
- Four numeric duplicate-predicate pairs remain in their original groups. This is an automatic dHash heuristic, without face identification or expert scene-family verification.
- TRAIN has 27 original rows, 26 exact unique contents, 24 groups; 14 positive and 12 negative unique videos.
- All 26 original source and cache digests verified. There are 678 ordered cached windows.
- Maximum cached center versus requested center discrepancy: **0.016979 s**. Maximum nearest-center distance to a positive label: **0 s**. A center is not necessarily one of the eight sampled frames; this does not prove exact annotated-frame coverage.
- Existing supervised baseline has one positive center per positive video, with **no other positive-video windows assigned a negative label**.
- A generated uniform RGB fixture agrees with the processor configuration to maximum absolute error **1.362392e-7**. This checks channel/scale consistency, not crop geometry, peripheral retention or upstream semantic suitability.

Parser reuse is not an independent proof of parsing correctness; targeted synthetic regressions cover the known identifier and timestamp cases, including Cyrillic/Latin X and the mixed minute/second format. No real frames were newly decoded or displayed, and no new model inference occurred in this audit. Single point annotations, center cropping and unreviewed automatic scene groups remain limits. [Claim ledger](claim-ledger-index.md).
