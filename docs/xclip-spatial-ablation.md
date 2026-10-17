# XCLIP spatial ablation: useful gate failed

The single preregistered experiment compares full-field letterboxing with a fixed central expanded region to test object scale at a 224-pixel encoder input. The crop retains normalized x=[0.1,0.9], y=[0.05,0.95], then letterboxes. It is a geometric region, not an expert-confirmed cash desk, hand area or cashier. The same 768-side decoded frames, original PTS/grid, frozen encoder, processor and separate training-fold centroids are used for both views. The original historical baseline used a different center-crop preprocessing pipeline.

The third declared arm uses the crop's point when its video margin is nonnegative, otherwise the full-field point. Its binary decision is positive if either margin is nonnegative. The maximum margin supplies ROC ranking only; the selected branch supplies the time. Threshold0, centroids, geometry, fallback and stop rule were fixed before extraction. Registration SHA256: `359eb5e111ad1847e120fcc5cb0df8d3d330624b917a5351f2208169931aabaa`.

| Fixed arm | TN | FP | FN | TP | F1 | Recall | Point MAE, TP only |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full-field letterbox |3 |9 |2 |12 |0.685714 |0.857143 |6.416667 seconds, n=12 |
| Central crop |3 |9 |3 |11 |0.647059 |0.785714 |8.272727 seconds, n=11 |
| Central with full fallback |1 |11 |1 |13 |0.684211 |0.928571 |8.692308 seconds, n=13 |

The useful gate failed. Fallback missed one fewer positive than full field but added two false positives. Neither view/fusion demonstrated the required F1 benefit; neither replaces the preserved original baseline (F1 0.75). Conditional time errors have different TP subsets and must not be treated as a paired localization improvement. No alternate geometry, threshold or fusion search follows this result.

The run used the same 26 unique TRAIN contents in 24 automatic groups. Each group's videos were excluded from all prototype fitting in that fold. Actual CV caches were saved, hashed, registered, reloaded and rechecked. Original registration SHA, public code/config/runtime/model identity and actual source-video bytes were verified before/after. TUNE/HOLDOUT were not used; originals and deployment packs remained unchanged.

Measured worker compute was 282.656 seconds, and monitor/cleanup/terminal completion 287.484 seconds within the 600-second budget. Recorded load including initial verification was 23.656 seconds; complete per-video feature cost averaged 9.89 seconds, maximum 27.781 seconds. There were 678 windows per view and 4804 decoded sampled frames. Peak Torch reserved memory was 430 MiB and Windows process peak working set 2379.691406 MiB. There were zero technical failures, actual worker exit0 and cleanup confirmed. These are experiment costs, not upload-to-result API latency; outer final-summary publication follows the monitor.

Aggregates are in `.private/xclip-spatial-control/safe-summary.json` and `claim-ledger.csv`; individual vectors/scores/candidate times stay private. Reused exploratory TRAIN and unreviewed automatic groups prevent an independent generalization claim. The experiment validates no event type, legal description, evidence relevance, multiple-event recall or new camera.
