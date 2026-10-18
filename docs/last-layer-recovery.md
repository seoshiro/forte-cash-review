# Complete fixed last-layer recovery

The checkpointed pass completed all 48 grouped CV fits and the two unchanged fullTRAIN diagnostic fits. All50 complete-fit checkpoints are retained privately. Adapter is rejected by the predeclared joint gate; the preserved cosine baseline remains in the research service. TUNE/HOLDOUT were not used.

Registration SHA: `2a45f0817659f5b1ce7ead9c05a1bbdfb92f6cf95cb0ef270e333da4792b5328`. Same original 26 unique TRAIN videos, 24 automatic groups, 500 steps, seeds/optimizer/loss/views/threshold/PCA/matched control/gates; no search or partial-metric selection. Existing hash-verified prefixes were reused after exact two-view zero-adapter replay (678 windows, maximum absolute error 0), without new decoding. This is adaptive exploratory reused-TRAIN OOF, not independent validation or an official score.

| Arm | TN | FP | FN | TP | Precision | Recall | F1 | All-positive point MAE,s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 6 | 6 | 2 | 12 | 0.666667 | 0.857143 | 0.750000 | 9.000000 |
| regularized_frozen_head | 7 | 5 | 5 | 9 | 0.642857 | 0.642857 | 0.642857 | 9.500000 |
| last_layer_adapter | 6 | 6 | 7 | 7 | 0.538462 | 0.500000 | 0.518519 | 5.285714 |

Binary gate FAIL, point gate PASS, joint gate FAIL. Adapter adds five false negatives versus baseline and does not beat matched head F1. Time-point error improves on the same 14 positive videos:9.0→5.285714 seconds. On the same 7 common true positives it improves10.428571→5.714286 seconds. This cannot compensate for the detection regression. The point is nonexhaustive annotation, not an independently established event boundary or evidence relevance. FullTRAIN adapter F1=1.0 is an in-sample diagnostic, not acceptance evidence.

Monitor wall 982.797 seconds (cap 1800); worker wall 981.125 seconds, learning/fullTRAIN phase 966.156 seconds. Peak process working set 1854.05078125 MiB, Torch peak reserved 242 MiB, minimum available RAM 1362.58984375 MiB, minimum free GPU 4756 MiB. These resource figures cover this cached-prefix training/replay pass; they are not full encoder or new-video inference costs. No historical cause is inferred for the prior RuntimeError merely because this recovery completed.

Checkpoint payloads are safe-tensors plus projection and post-fit CPU/CUDA RNG, hashes, fixed fold/arm/source provenance and completed optimizer-step count. Payloads are flushed, commit marker is last, and an owned same-directory atomic rename publishes the complete fit. No pickle or partial-optimizer resume is used; an interrupted fit restarts at original seed/step zero while finished fits load without retraining. CPU and CUDA synthetic tests verified equal restored weights/RNG and an equal next fresh fit; disk-commit fault injection verified prior checkpoints survive and pending payloads are ignored.

425 source/synthetic regression tests passed. The independent arithmetic/provenance helper verified all 50 checkpoint identities and the aggregate gates. Original dataset/cache/split/baseline/UI8768 remain preserved. Private training outputs/checkpoints/weights, bank media, labels and credentials are excluded from Git. Types/rules/multi-event explanations and camera robustness remain unaccepted; competition API stays closed 503.

[Live research access](research-delivery-runbook.md) | [Claim ledger](claim-ledger-index.md).
