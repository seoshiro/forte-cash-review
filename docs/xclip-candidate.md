# XCLIP-PROTO-01

Result: completed, rejected by the predeclared TRAIN acceptance gate. TUNE and HOLDOUT media inference/model evaluation were not run. Do not deploy this as a useful detector or change its fixed threshold after inspecting the result.

This is one frozen TRAIN-only temporal representation experiment, not an API detector release. It follows the rejected QVT and weak cached-centroid diagnostics. A true pretrained temporal encoder is compared with repeated-center-frame inputs while keeping the prototype head, source split, grid and decision threshold fixed. Motion-BAG remains parked and has not run on real data.

## Provenance and execution

Official weights: [microsoft/xclip-base-patch32](https://huggingface.co/microsoft/xclip-base-patch32), revision a2e27a78a2b5d802e894b8a1ef14f3a8ce490963, MIT declaration in its model metadata/card. The only weight file is Safetensors, 786414772 bytes, SHA256 abf286e8cdd0612761c3e42d3a55eca998382dfa67a04a0f3fdcdfa4f150cdbb. Download, small public artifacts and SHA verification took 288.094 seconds, separate from computation. No data or credentials were transmitted.

The builtin Transformers XCLIP implementation is Apache-2.0; [Microsoft VideoX upstream](https://github.com/microsoft/VideoX/blob/master/LICENSE) is MIT and its license text is cached. No noncommercial VideoMAE weights were downloaded or used. The official processor happens to use the shared VideoMAEImageProcessorPil image-preprocessing class; that is not a VideoMAE model. No copied adapter code or remote model code is executed.

Existing isolated .venv-patched and requirements-patched-lock.txt are reused, with no new dependency installation or system changes. Actual versions, model/config/processor digests, code digests, dataset/split digests and selection hashes are recorded in .private/xclip-control/registration.json before any real feature extraction. Every resulting cache file is registered before CV, reloaded as the actual CV input and checked again afterward.

## Fixed method

Only 26 exact-unique TRAIN contents in the existing 24 automatic groups are learning/evaluation units, preserving all 27 original rows and multiplicity metadata. The official split is unchanged. No TUNE or HOLDOUT inference/evaluation occurs. Manual proposals and external AI explanations are excluded.

Two-second windows advance one second, with eight chronological decoded-PTS frames each. The official pinned processor resizes/crops and normalizes once; its center crop can exclude peripheral content. Ordered input is compared with frame index four repeated eight times after the same processing. get_video_features().pooler_output produces 512-dimensional vectors, L2-normalized. Weights stay frozen in eval mode, with FP16 and SDPA; no descriptions or face/audio outputs are generated.

Both class centroids are fitted inside each leave-one-group-out TRAIN fold. One nearest-fixed-grid window from each positive TRAIN point supplies positive supervision. Other positive-video windows remain unlabeled. Negative windows are averaged within each negative video, then averaged across videos with equal mass. No scaler or deep head is fitted. Inference scoring accepts features, PTS and centroids only, with no source name, label or known event point.

Score is cosine-positive minus cosine-negative, fixed threshold zero. Report all four arms: ordered_max, ordered_persistence, repeated_max, repeated_persistence. Persistence is max(min(score[i],score[i+1])); its candidate time is the mean of adjacent window centers. This requires two consecutive windows above threshold and is the single predeclared response to multiple-window false positives. It is not a calibrated probability or a validated semantic event time.

Primary acceptance is ordered_persistence: recall 1, specificity >=0.5, F1 >=0.8, balanced accuracy >=0.75, ordered-versus-repeated persistence balanced-accuracy gain >=0.05, no extra FN versus ordered_max and at least one fewer FP. All technical gates, immutable source checks and cache checks must pass. No arm, threshold, feature, seed or head is selected afterward. Even a pass establishes only exploratory binary proposal quality.

## Technical checks before quality

One code-only ECC-derived reviewer checked the source before registration. It found a PTS-tolerance mismatch and a transient-RSS gate gap. Both were fixed before any real inference: matching tolerance includes the shared sampler's 1e-4-second early-frame allowance, and Windows peak_wset is checked as a high-water mark. Final time checks follow all hash verification. Synthetic tests cover PTS correspondence, true gaps, whole-group exclusion, equal-video centroid weighting, fixed persistence, probe-count preservation and peak-memory semantics. The reviewer confirmed the repairs without accessing data.

The generated-image compatibility preflight passed: two artificial clips, 17.469 seconds loading, 18.703 seconds total, 450 MiB peak Torch reserved memory. It checks finite outputs, identical static ordered/repeated features, batch independence and nonzero moving-versus-repeated representation difference. These establish mechanics only, not recognition of banking actions.

The computational budget is 1800 seconds including this synthetic preflight, loading, decode, both arms, CV and final verification. Three label-blind shortest/median/longest TRAIN probes precede full extraction. Maximum complete per-video extraction cost is 220 seconds, Torch reserved limit 5000 MiB, Windows peak-working-set limit 6000 MiB. Source clips remain read-only. Raw embeddings, individual scores, time candidates and results remain private.

## Release boundary

Binary similarity cannot establish a type, rule, cashier role or omitted action. Genuine evidence, local semantic observation and all applicability/exclusion conditions remain separate requirements. No public service, permanent key, tunnel or submission is created by this experiment. Questions for organizers are in docs/official-taxonomy-and-questions.md and have not been sent.

## Measured results

| Fixed arm | TN | FP | FN | TP | Precision | Recall | Specificity | F1 | Balanced accuracy | Video AUC | Time MAE, matched positives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ordered max | 6 | 6 | 2 | 12 | 0.6667 | 0.8571 | 0.5000 | 0.7500 | 0.6786 | 0.5774 | 8.8333 s, n=12 |
| Ordered persistence, primary | 6 | 6 | 2 | 12 | 0.6667 | 0.8571 | 0.5000 | 0.7500 | 0.6786 | 0.5714 | 8.7500 s, n=12 |
| Repeated max | 6 | 6 | 2 | 12 | 0.6667 | 0.8571 | 0.5000 | 0.7500 | 0.6786 | 0.5952 | 7.8333 s, n=12 |
| Repeated persistence | 6 | 6 | 4 | 10 | 0.6250 | 0.7143 | 0.5000 | 0.6667 | 0.6071 | 0.5655 | 5.1000 s, n=10 |
| Constant positive | 0 | 12 | 0 | 14 | 0.5385 | 1.0000 | 0.0000 | 0.7000 | 0.5000 | Not applicable | Not applicable |
| Constant negative | 12 | 0 | 14 | 0 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.5000 | Not applicable | Not applicable |

The primary arm misses two positives and fails recall/F1 targets. Persistence reduces no false positives relative to ordered max. Ordered versus repeated max has identical confusion counts, and ordered AUC is lower. Ordered persistence's better recall than repeated persistence is not sufficient proof of a broadly useful temporal-action advantage. The stronger temporal-pretraining hypothesis has not been demonstrated at release quality on this case. It is not justified to grow the head, select an arm afterward or tune a new threshold on this result.

The experiment used 678 windows per arm and 4804 decoded sampled frames. Feature extraction including both arms averaged 7.9117 seconds per video, maximum 22.391 seconds. The registered run took 227.203 seconds; with the earlier generated-image compatibility probe, compute was 245.906 seconds. Download/hash time was separately 288.094 seconds. Peak Torch reserved memory was 450 MiB; Windows high-water working set was 1908.01 MiB. Device-wide sampled GPU memory peaked at 551 MiB across 362 samples; this includes other processes and is not per-model allocated VRAM. There were zero technical failures, all source hashes remained unchanged and actual CV cache inputs passed hash checks before/after CV.

Evidence and calculations: .private/xclip-control/safe-summary.json, registration.json, feature-registration.json and scripts/xclip_experiment.py / xclip_candidate/evaluate.py. Precision=TP/(TP+FP), recall=TP/(TP+FN), specificity=TN/(TN+FP), F1=2TP/(2TP+FP+FN), balanced accuracy=(recall+specificity)/2. AUC is computed from video margins. Time MAE uses absolute error against the official point only for TP; no frame relevance or event completeness claim is made. All numbers are traceable in docs/claim-ledger.csv. Individual vectors, scores, source names and time candidates stay private.

Full synthetic/API/security regressions: 101 passed, no failures; one existing nonblocking Starlette/httpx deprecation warning. The independent ECC-derived reviewer performed source-only checks and confirmed the two pre-registration fixes. These engineering passes do not repair the quality gap.

The next necessary distinction is substantive observation/rule semantics rather than another speculative runtime update. Preserve this failure, keep TUNE/HOLDOUT closed, and obtain official clarification of event/type matching and applicability. Generic video similarity and motion cannot supply verified rule conditions or omissions. Deployment clarification from participant discussion is tracked independently in docs/deployment-clarification.md and does not explain these quality results.
