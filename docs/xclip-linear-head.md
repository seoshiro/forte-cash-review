# XCLIP-LINEAR-01

One predeclared cache-only TRAIN experiment. No real-media decoding, new encoder inference, TUNE/HOLDOUT evaluation, manual annotations or cloud inference. Frozen features retain the original registered XCLIP encoder, processor, windows and PTS. This is exploratory reuse of TRAIN, not independent validation.

## Why this is a different experiment

Source-only ECC/public-ledger review found XCLIP cosine centroids, a hard-negative prototype and spatial centroids. It found no discriminatively optimized linear/temporal head specifically on XCLIP. QVT's earlier LogisticRegression used Qwen visual features. The cosine margin was already supervised and linear in the normalized feature vector; novelty is an optimized regularized affine boundary, not the existence of supervision or linear scoring.

## Fixed method before execution

Use the same26 exact-unique TRAIN contents in24 existing automatic groups,14 positive. Hold out one whole group at a time. All windows and duplicate/adjacent-group sources stay together. Automatic grouping lacks expert confirmation; undiscovered related scenes can still make this estimate optimistic.

Inside each train fold only, use one nearest cached PTS-window to each positive official point and all windows of each negative video. Other positive windows are unlabeled and excluded from fitting. L2-normalize individual vectors without fitted statistics. Fit a weighted StandardScaler and L2 LogisticRegression on exactly the same fold-only samples and weights. Each unique video has equal initial mass, balanced across the two classes: `n_train_videos / (2 * n_train_videos_in_class * selected_windows_in_video)`. No second class weighting.

Fixed classifier: C0.01, lbfgs, intercept enabled, class_weight=None, tolerance1e-6, maximum2000 iterations, seed26101731. Score every held-out window and max-pool exactly as the baseline, with logit threshold0 and first-maximum tie policy. Prediction accepts only features, decoded times and the fixed threshold. A convergence warning/nonfinite output is technical failure, with no rescue refit or parameter changes.

Reproduce saved ordered-max cosine baseline exactly: TN6/FP6/FN2/TP12, F1.75. The candidate binary gate is FN<=2, FP<=5, F1>=.8. Report precision/recall/F1/confusion/AUC, conditional TP point MAE, all14-positive candidate-point MAE and paired MAE on the common true-positive cohort with denominators. The joint useful gate additionally requires no increase in all-positive and paired common-TP point MAE. These point diagnostics do not validate event boundaries, types, evidence relevance or rule applicability.

One CPU thread;180-second supervised wall budget including integrity checks and persistence; minimum available RAM2GiB before fit,1GiB during, worker peak RSS<=1536MiB. Cache-only fit and score costs exclude the encoder, decoding, upload and evidence preparation. No full API timing or GPU-fit claim follows.

Registration pins code, configuration, original registrations, cache file hashes and installed numerical-library versions before execution. Recheck sources/cache after CV. Save individual OOF rows privately; emit only fixed aggregate metrics. Preserve the old baseline and deployment pack. No full-data deployment fit is part of this experiment.

Official APIs checked: [StandardScaler sample weights](https://scikit-learn.org/1.6/modules/generated/sklearn.preprocessing.StandardScaler.html), [LogisticRegression](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.LogisticRegression.html). The installed signatures were checked at scikit-learn1.6.1; no packages changed.

## Completed result — rejected

Registration SHA256: `2aad535fbd6983b632e34b246741b99e50e50f55c9a1dadb9692738468e1b97e`. All14 registered source files remained unchanged. The original cache/registration passed before/after checks and all saved baseline anchors reproduced. One run completed all24 folds and26 OOF videos, with normal worker exit and owned cleanup. TUNE/HOLDOUT stayed closed. No media or new GPU inference.

| Metric | Preserved cosine baseline | Fixed logistic head |
|---|---:|---:|
| TN / FP / FN / TP | 6 / 6 / 2 / 12 | 4 / 8 / 4 / 10 |
| Precision | .666667 | .555556 |
| Recall | .857143 | .714286 |
| F1 | .75 | .625 |
| Specificity | .5 | .333333 |
| Balanced accuracy | .678571 | .523810 |
| AUC | .577381 | .494048 |
| Conditional TP point MAE, different cohorts | 8.833333s, n12 | 8.2s, n10 |
| All-positive candidate-point MAE, same14 positives | 9s | 8.928571s |
| Common-TP candidate-point MAE, same10 positives | 8.7s | 8.2s |

F1 fell by.125; both FP and FN increased by2. The binary and joint useful gates failed. The point non-regression gate passed, with only.071429s lower all-positive point MAE and.5s lower common-TP point MAE. This does not offset worse detection and is not semantic localization validation. Conditional TP MAEs have different denominators and are not a paired improvement comparison.

One CPU thread: cache evaluation wall.437s; complete process monitor3.75s including imports/integrity/cleanup. Sum of24 fold fits was.028270s baseline versus.327161s head; sum of26 video scores.002492s versus.012598s. Tiny cache-only costs do not include decoding/encoder/API/evidence and establish no new real-video speed. Optimizer maximum20 iterations. Windows lifetime peak working set123.179688MiB; sampled minimum whole-system available RAM4766.292969MiB. No resource stop or convergence failure observed in this owned run. Tests on installed sklearn/scipy report the known ignored iprint verbosity option; no solver/package change was made.

The full synthetic/unit/integration suite passed294 tests, zero failures/errors/skips, JUnit28.066s. These tests establish engineering behavior only. Source-only ECC review found no fold/oracle leakage and required a late-resource persistence regression, which was fixed before registration. It read no private data and ran no tests/models.

Private safe sources: `.private/xclip-linear-control/safe-summary.json`, `run/terminal-safe-summary.json`, `calculation-safe-summary.json`, `tests-safe-summary.json`. The arithmetic report validates confusion totals, F1, source hashes and comparison denominators; no private OOF rows were read for this report. Numerical claims are regenerated into [claim-ledger.csv](claim-ledger.csv).

**Decision:** close this fixed candidate without parameter/pooling/threshold search. Preserve the old baseline and deployment pack. No full-TRAIN deployment fit, accepted semantic classifier, new API SLA or competition release follows.
