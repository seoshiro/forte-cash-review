# One frozen TUNE assessment

The preserved cosine candidate performs poorly on TUNE. This is development evidence against release, not an official jury score or a final test. No threshold, prompt, window, prototype or model changes followed this result. HOLDOUT remains closed.

## Freeze and scope

`XCLIP-TUNE-01` was newly authorized for one assessment of all original TUNE videos. A bounded audit found no saved TUNE assessment of this candidate. Registration SHA256: `18fb782a8b53ff2a46c9e8ecc0c9d4e82787ae6128bcd356074ae05761d35b64`. Registered source hashes remain unchanged.

The preserved `.private/xclip-experimental-v2` pack uses schema 2, ordered features, max pooling and threshold 0. Prototype SHA256: `98e918daef003f0d4ce824b54f3d632b1d1a1dd517c568ab8d388fdf66d168b6`. Native XCLIP inference is unchanged, including the existing repeated arm computation. Parameters: [protocol](../config/xclip-tune-protocol.json), [original feature protocol](../config/xclip-protocol.json). No new training occurs.

There are **9 original rows and 8 exact unique contents**. All original rows were assessed as requested; the duplicate means these are not nine independent examples. Automatic scene grouping was not validated by a local expert. Workers receive opaque copied inputs and label-free identities; names, row numbers and ground truth are not inference inputs.

## Aggregate result

| Measurement | Value | Denominator / meaning |
|---|---:|---|
| TN / FP / FN / TP | 1 / 3 / 4 / 1 | All 9 completed original videos |
| Precision / recall | 0.25 / 0.20 | TP/(TP+FP), TP/(TP+FN) |
| F1 | 0.222222 | 2TP/(2TP+FP+FN) |
| Specificity / balanced accuracy | 0.25 / 0.225 | Completed video verdicts |
| Failures or refusals / not attempted | 0 / 0 | Requested 9 |
| TP-only candidate point MAE / median | 3.0 s / 3.0 s | **1 true-positive video only** |

The point error compares a candidate source-frame timestamp with the supplied single point. It does not validate event boundaries, event type, observation accuracy or evidence relevance. No per-video results, frames or semantic descriptions are public.

## Full local wall time

| Statistic | Seconds |
|---|---:|
| Count | 9 videos |
| Minimum | 21.703 |
| p25 | 23.781 |
| Median | 29.938 |
| p75 | 36.938 |
| p95 | 41.4782 |
| Maximum | 42.547 |
| Mean | 30.446222 |
| Sum | 274.016 |
| Entire assessment | 276.703 |

Each video starts a cold owned worker. Wall time includes source hashing/copy, process/import/model load, decoding/features/scoring, conditional candidate JPEG/schema, cleanup and local case persistence. It **excludes HTTP upload and public transport**. No completed video exceeded the configured full-wall limit. The child deadline is enforced; driver I/O/full-wall checks are retrospective. RAM checks occur at defined boundaries and do not guarantee continuous allocation bounds.

Arithmetic and hashes are checked by [summarize_xclip_tune.py](../scripts/summarize_xclip_tune.py). It reads aggregate summaries, technical terminal reports, and the frozen registration to check registered source hashes and derive original/unique counts from source digests. The registration itself contains local paths and ground truth; neither is emitted or used for a new prediction. Its SHA is bound to the original run summary before use. Local evidence: `.private/xclip-tune-control/{safe-summary,calculation-safe-summary}.json`. [Claim ledger](claim-ledger-index.md). This helper performs no model evaluation. No repeat, rescue search or HOLDOUT use is authorized by this run.
