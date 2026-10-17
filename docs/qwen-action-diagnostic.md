# Qwen action-control diagnostic and next choice

The new frozen probe completed all 18 calls on fully generated geometry. It loaded the existing official quantized 4B checkpoint and matching projector locally, with a fresh owned process tree, temporary test authentication and a 360-second absolute monitor. It did not open bank videos, previous answers, quarantined annotations or cloud-generated explanations. Raw model responses and native stdout/stderr were never saved or emitted.

EXIT and ENTER are the exact same four frames reversed. STAY keeps the red disk inside a black outlined region. There are no cashier/service/answer overlays. All cells use the same action definitions and JSON field. Registration SHA256: `cecdbd3e6b4a31d8066460aecbf1f83cb9fb6ae56a1ad96c40dab62d80222bda`.

| Frozen condition | Correct with stop | Valid JSON | Truncated / transport errors | Input tokens |
|---|---:|---:|---:|---|
| T: text coordinates, unconstrained JSON |1/3 |3/3 |0 /0 |161,161,160 |
| TC: identical T plus schema |1/3 |3/3 |0 /0 |161,161,160 |
| V: four images, short prompt, unconstrained JSON |1/3 |3/3 |0 /0 |378 each |
| VC: identical V plus schema |1/3 |3/3 |0 /0 |378 each |
| PC: same frames in montage, short prompt, schema |1/3 |3/3 |0 /0 |363 each |
| LC: four images, long physical prompt, schema |1/3 |3/3 |0 /0 |506 each |

All 18 responses ended with `stop`; none returned UNKNOWN or another finish reason. Aggregate correctness was 6/18. The montage has the same total source pixel area as four separate images, but actual input-token counts differ; do not claim an identical model token budget. Each condition has only three examples. Individual predicted labels and paired error identities were not retained; equal aggregate counts do not prove identical responses or a constant prediction.

This discriminates observed format/transport completion from action correctness. Schema on/off, long/short prompt and image packing produced the same aggregate correctness here. Text-only geometry also scored1/3, so image encoding alone cannot account for the observed failure. The exact cause remains unidentified. A single frozen4B model does not identify capacity; the prior2B used a different backend/precision. JPEG versus PNG and actual runtime chat-template rendering were not varied. The old partial16/10 is excluded from every denominator and causal claim.

Native load was9.828 seconds. Worker time including native cleanup was151.672 seconds; monitor/terminal completion153.703 seconds. The native process was still running before requested shutdown, exited with code15 afterward, and cleanup completed. The actual worker exited0. Code15 after intentional termination is not evidence of a spontaneous crash. The monitor field `quality_gate_passed=false` reflects6 of18 correct assertions; technical execution itself completed.

## Static audit already performed

The public official GGUF files match pinned SHA/size. Local header metadata identifies the language model as Qwen3VL4B Instruct and projector as matching4B Instruct with `qwen3vl_merger`. The language template has5292 characters, SHA256 `3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4`, ChatML/assistant/user/generation/image/vision markers, and no `<think>` or `enable_thinking` substring. The projector declares a768-pixel image size and16-pixel patch size. This is static public metadata, not proof of actual runtime rendering; no new server/model was started for this audit.

The [official pinned model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/blob/1cd86afb9a95c410a6038ab3b40d8b578c892266/README.md) identifies the Instruct base and separate language/projector artifacts. The pinned [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/b11712/tools/server/README.md) documents default-enabled Jinja, metadata-derived templates, `messages`/`image_url` data-URI parts and a no-inference `/apply-template` endpoint. The driver uses those message/image shapes and the source-verified nested schema shape. Documentation compatibility does not prove the binary rendered the intended input.

## Reasoned next choice

Perform one bounded expected-versus-actual template/request audit on synthetic messages before another action-quality run: inspect server `/props`, use `/apply-template` without generation, verify role boundaries, assistant generation suffix, image-marker multiplicity/order and response-schema handling against the pinned Instruct template/runtime source. Do not re-run the old legal gate, change prompts opportunistically or declare a mismatch causal without a discriminating check. This next runtime audit is prepared as a choice, not claimed executed.

`hybrid_candidate/observer.py` already separates physical Facts from deterministic `apply_rule`. Removing a legal prompt cannot itself supply a validated action classifier. The current one-field local classifier is technically functional but fails these elementary controls and is unsuitable for bank typing. After the runtime check, a defensible action-only evaluation needs a fresh licensed/staged/synthetic human-action set with whole-scene separation, reversed EXIT/ENTER, STAY, occlusion/missing-before UNKNOWN controls and independently specified ground truth. It would validate only visible person/zone crossing, not operator role, unfinished service, object counting or R22. Each additional rule condition needs separate evidence; binary XCLIP labels provide none of these types. Deterministic descriptions may be generated only from verified facts, with no invented invisible state.

All aggregates and timing derive from `.private/qwen-action-probe/safe-summary.json`, its monitor and `.private/qwen-static-audit/safe-summary.json`, and are added to `claim-ledger.csv`. No new public dataset, model dependency, cloud processing, permanent credential or external access was introduced.
