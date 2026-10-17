# One supervised temporal-learning attempt

**The candidate failed the binary task and is rejected.** The preserved cosine baseline remains available. No threshold, seed, step count, projection or architecture changes followed this result; no rerun, TUNE or HOLDOUT evaluation occurred.

This is prospective **post-TUNE exploratory TRAIN research**. The previous poor TUNE result motivated domain learning, so this reused TRAIN comparison is not independent quality evidence.

## Frozen method

Protocol [XCLIP-TEMPORAL-01](../config/xclip-temporal-protocol.json), registration SHA256 `80f7cf3102c365dd955d106986ae6c678f3b8a0632c57f9acc2864bd69c32f42`. All 25 registered source/input hashes remain unchanged.

The existing ordered XCLIP backbone/window embeddings stay frozen. Each train-fold fits equal-video weighted centered PCA with eight components and no whitening. A temporal convolution uses `8→8, kernel3, replicate boundaries → GELU → dropout0.5 → 8→1, kernel1`: **209 trainable parameters**. This adds nonlinear neighboring-window context instead of repeating the earlier affine logistic head.

There are 24 leave-one-group-out folds over 26 exact unique TRAIN contents. The complete excluded group is omitted from PCA, centroids and head fitting. AdamW uses learning rate 0.001, weight decay 0.1, seed 26101732 and 200 fixed full-batch steps. The final iterate is used; there is no early stopping or search.

Half the loss is mean positive-video BCE at the nearest official point center; half is mean negative-video BCE on each negative video's maximum valid logit. Other positive positions have no direct target/loss and remain context. Padding replicates each video's own endpoints. Inference accepts features/PTS only, uses max pooling, threshold logit0 and the earliest argmax. Unit regressions verify the loss mask, padding, deterministic fit, PCA scope and actual worker guard path.

## Aggregate TRAIN group-OOF result

| Metric | Preserved cosine baseline | Temporal head |
|---|---:|---:|
| TN / FP / FN / TP | 6 / 6 / 2 / 12 | **12 / 0 / 14 / 0** |
| Precision | 0.666667 | 0 |
| Recall | 0.857143 | **0** |
| F1 | 0.75 | **0** |
| Specificity / balanced accuracy | 0.5 / 0.678571 | 1 / 0.5 |
| ROC AUC | 0.577381 | 0.541667 |
| TP-only candidate point MAE | 8.833333 s, n=12 | Not applicable, n=0 |
| All-positive candidate point MAE | 9 s, n=14 | 9.642857 s, n=14 |
| Common-TP paired cohort | — | Empty, n=0 |

All binary decisions are negative; scores are not asserted to be identical. AUC numerically above chance does not establish useful signal. Predeclared binary targets were FN≤2, FP≤5 and F1≥0.8. Binary, point nonregression and joint useful gates all failed. The baseline reproduced exactly.

The final-step balanced training loss averaged 0.692228 across folds, close to ln(2). It was computed with dropout before the final optimizer update and is not an OOF metric or convergence proof. This experiment does not identify whether embeddings, projection, incomplete supervision, regularization or optimization caused failure.

## Measured resources and retention

The technical monitor completed **25 fits** (24 CV plus one fixed full-TRAIN pack) in **27.907 s including cleanup**. CV fitting sum: **18.742425 s**; full-TRAIN fit: **0.687 s**. Peak process working set before final persistence: **795.121094 MiB**; minimum sampled available RAM: **3772.878906 MiB**. CPU uses one thread; no GPU, backbone inference or bank decoding occurs. Head-only scoring mean/max is **0.0009122 / 0.0017922 s**, excluding feature extraction and HTTP upload. These are not end-to-end service timings.

The owned budget was 600 s, with discrete RAM/working-set checks and process cleanup. A technical PASS means the fixed protocol executed; it does not override the failed model gates. The final full-TRAIN pack is private, hash checked, `unverified/not_assessed/release_eligible=false`, with no in-sample quality claim or deployment promotion. Fold predictions remain private and unread by cloud tools. [Aggregate arithmetic helper](../scripts/summarize_xclip_temporal.py), [preparation audit](train-preparation-audit.md), [claim ledger](claim-ledger-index.md).
