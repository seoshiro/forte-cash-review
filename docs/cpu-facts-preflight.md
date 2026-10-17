# Fixed alternative-path decision and CPU primitive control

## RT-DETR decision before weights

The public [pinned model config](https://huggingface.co/PekingU/rtdetr_v2_r18vd/blob/5650961749fa93567c0d46fc7f43ea4f9e914107/config.json) supplies80 COCO labels, including person, cell phone and ordinary bags. It supplies no money/banknote/coin, cashier, service-completion or cash-procedure classes. Its [model card](https://huggingface.co/PekingU/rtdetr_v2_r18vd/blob/5650961749fa93567c0d46fc7f43ea4f9e914107/README.md) declares COCO training and Apache2. The exact public label map and config SHA are preserved in `config/rtdetr-public-classes.json`; no model weights were downloaded.

Anonymous person presence is a genuine supported object primitive. Person crossing a region would additionally require tracking, locally reviewed boundaries and role/visibility checks. The official Excel provides a binary video label and nullable event point, not person/region/role/action truth. There is no accepted independent primitive annotation or justified correspondence from these binary labels to that event. A correlation would not establish a bank violation, a cashier role or R22 service context. Phone/bag detections have comparable applicability gaps. No bank media or quarantined notes were inspected to fill those gaps.

Therefore reject this detector as the next semantic replacement before download or state-machine implementation. This is a task-evidence decision, not a claim that generic person detection is impossible or the model could never be a future component. The XCLIP baseline, deployed private prototypes and source splits remain unchanged.

## Chosen one-run hypothesis

Use the existing commercially permitted [Qwen GGUF weights](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/blob/1cd86afb9a95c410a6038ab3b40d8b578c892266/README.md) and [MIT llama.cpp runtime](https://github.com/ggml-org/llama.cpp/blob/b11712/LICENSE), with a requested CPU backend. The pinned argument parser supports [mmproj device none](https://github.com/ggml-org/llama.cpp/blob/b11712/common/arg.cpp#L2505-L2514) and [device none](https://github.com/ggml-org/llama.cpp/blob/b11712/common/arg.cpp#L2634-L2641); register zero GPU layers as well. No new weights, dependencies, credentials or OS/network settings are needed.

Hypothesis: the requested CPU configuration may change exact primitive-fact correctness. This is a backend-sensitivity control on the same model/runtime binary, not an independent model family. It cannot isolate CUDA correctness: a different session and removal of interleaved direct tasks also differ from the historical GPU run. Effective native numerical implementation is not independently audited. No direct Qwen coordinate-to-label classifier is run again.

Frozen protocol: `config/qwen-cpu-facts-protocol.json`. Three old numeric-facts and three old ground-truth Boolean-binding requests retain the exact old message bodies, scorer, weights, template and sampling: temperature0, seed26101731, max_tokens48, no grammar/prefill/logit-bias/stop overrides. Per-request text timeout increases separately from20 to30 seconds, as a budget change. All six technically normal text calls complete even if a response is wrong. Ground-truth binding never consumes model fact responses.

Only6/6 exact valid-format normal-stop responses, including9/9 numeric Boolean fields, permit the three predefined visual-facts calls. Each supplies four generated JPEG images; no coordinates, expected facts or action labels are included in their prompt. It requests first_inside/last_inside/all_inside. A fixed deterministic mapping then derives the observed synthetic state. Pixel/coordinate oracle, actual mock HTTP payload and strict parser/gate checks run before registration. Register expected-answer and complete request-body digests, including generated JPEG bytes.

Visual acceptance requires3/3 exact fact responses and3/3 correct deterministic states. It establishes only the small generated geometry prerequisite; no bank type, operator role, legal applicability or robustness follows. Otherwise stop this candidate without prompt search, additional seeds, repeats or bank/TRAIN transition. TUNE/HOLDOUT stay closed in every outcome.

Total480 seconds includes source/artifact checks, startup, text/conditional images, cleanup and publication. Startup60 seconds, text call30, visual call45. Record sampled owned native/worker RSS peaks, minimum sampled available system RAM, device-wide sampled VRAM, complete wall time and terminal/cleanup status. RSS samples are not the Windows lifetime high-water or committed memory. Native stdout/stderr use DEVNULL; only fixed aggregates survive. Timeout, truncation, transport/native exit, parser failure or cleanup failure cannot be reported as complete semantic evidence. One supervisor compound assertion is distinct from model call counts.

No public service, permanent key, submission or external bank-data transfer is involved. The prior failed runs remain preserved.

## Registered execution and outcome

Registration SHA256 `40bd70b95c38efd17b51dc1b3b9d892da7ec42f56f95eced11f34a2646668ae5`. Prospective source review found an unsupported visual-progress phase before registration; it was corrected to the existing supervisor schema and both progress paths received regression checks. No frozen source changed afterward. The complete regression suite passed273 tests, zero failures/errors/skips, JUnit32.533 seconds, with the existing TestClient deprecation warning. Tests did not run bank inference.

| Synthetic task | Requested CPU result | Historical GPU decomposition |
|---|---:|---:|
| Numeric facts: complete exact answers |2/3 |2/3 |
| Numeric Boolean fields |8/9 |8/9 |
| Ground-truth Boolean-to-label binding |3/3 |3/3 |
| Valid format / normal stop |6/6 |6/6 for the matching tasks |
| Technical errors / truncation |0 /0 |0 /0 for the matching tasks |
| Conditional visual calls |0 |Not part of that historical protocol |

The CPU text gate failed and the conditional visual phase did not run. Direct coordinate-to-label classification was not repeated. These aggregate accuracies did not improve; neither a validated semantic candidate nor an image/bank transition is obtained. No claim about a CUDA bug, model capacity, exact per-case prediction identity or causal equality between backends follows from aggregate agreement. The session/order/interleaving caveats remain.

Native loading19.453 seconds, six-call text phase31.234 seconds, worker including cleanup80.547 seconds, authoritative monitor82.718 seconds within480. This is not a speed comparison with the earlier longer workload. Worker exit0; native was alive before intentional shutdown and exited15 afterward. Owned native/job cleanup completed. No timeout, crash or OOM was observed.

Observed sampled native RSS peak4916.0390625MiB; worker RSS128.70703125MiB; native RSS samples124. Sampled available whole-system RAM reached only0.00102996826171875GiB (1,105,920 bytes). Device-wide sampled VRAM peak0MiB across43 samples. This is the requested CPU configuration's observed memory profile, not a universal fit guarantee or a backend implementation audit. After native cleanup, three whole-system samples showed available RAM between5,661,450,240 and5,665,247,232 bytes. Other processes contribute to system availability; no foreign process was stopped and no causal OOM claim is made. The low observed RAM margin further argues against adoption or repeated CPU runs on the current machine state.

Evidence: `.private/qwen-cpu-facts/safe-summary.json`, `run/terminal-safe-summary.json`, `calculation-safe-summary.json`, `tests-safe-summary.json`, `post-cleanup-memory-safe-summary.json`; RT-DETR class inspection is `.private/rtdetr-class-audit/safe-summary.json`. `scripts/summarize_cpu_facts.py` reproduces counts, source identities and units; `scripts/claims.py` records only the safe aggregates/configuration. No raw responses, prompt transcripts, native logs or real-media results were saved by this run.

Decision: close this candidate after the single failed prerequisite. Preserve XCLIP unchanged and TUNE/HOLDOUT closed. RT-DETR remains rejected as a semantic replacement without independently justified primitive truth. There is still no accepted bank event-type/rule classifier; the next candidate requires a different, independently justified model or evidence path, not another direct-Qwen prompt or wrapper.
