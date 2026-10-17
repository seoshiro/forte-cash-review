# Fixed hard-negative diagnostic: no useful improvement

`XCLIP-HARDNEG-01` tested whether averaging every window in correct videos diluted visually confusing correct actions with background. It replaced the negative prototype with exactly two windows per negative training video, nearest the positive training-fold prototype and separated by at least three seconds. Positive fitting, encoder, ordered features, threshold0 and max pooling stayed fixed. Every fold fit used only its training groups.

The protocol/code/cache/source inventories were registered before the single run. Registration SHA256: `407966b35d8b0b0053f53f524a1c561068203a4ba8d57104e302ab4c2008bfbd`. Exact inputs and code were rechecked after group OOF. No video was opened, no GPU inference or external dataset download was performed. It used the same26 unique TRAIN contents in24 automatic groups. TUNE/HOLDOUT remained closed for this candidate. The groups lack expert review and TRAIN has already been reused for exploration, so this is not independent generalization evidence.

| Metric | Preserved baseline | Fixed hard-negative variant |
|---|---:|---:|
| TN / FP / FN / TP |6 /6 /2 /12 |6 /6 /2 /12 |
| Precision |0.666667 |0.666667 |
| Recall |0.857143 |0.857143 |
| F1 |0.75 |0.75 |
| ROC AUC |0.577381 |0.601190 |
| Point MAE on the12 true-positive videos, seconds |8.833333 |9.25 |

The saved baseline reproduced exactly. The predeclared useful gate required TP at least12, FP at most4 and F1 at least0.8; it failed. The branch stops here, without a threshold/head/pooling search or automatic replacement of the baseline/deployment prototypes. The small AUC change does not establish an operational advantage at the frozen decision threshold, and time localization worsened.

The cache-only measured wall time was1.625 seconds; the configured budget was30 seconds. Aggregate results are retained locally in `.private/xclip-hardneg-control/safe-summary.json` and generated into `claim-ledger.csv`; private per-video records remain excluded from Git and cloud output. This experiment validates neither event type, legal rule applicability, evidence relevance nor complete multiple-event detection.
