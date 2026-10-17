# Different VLM: fixed visual control and conditional TRAIN proxy pilot

## Selection and memory decision before inference

Candidate: [OpenGVLab/InternVL3_5-1B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-1B-HF), pinned revision `9191dbccf312b537016f041b25d61c72e7c5c9f3`. The official card declares Apache2 for the checkpoint and its Qwen3 component. The native [Transformers runtime](https://github.com/huggingface/transformers/blob/v5.20.1/LICENSE) is Apache2. This is a different VLM checkpoint, vision encoder and multimodal training path; its language-model family is still Qwen3. It is not a fully independent set of components. No earlier Qwen backend experiment is repeated.

The official [native integration](https://huggingface.co/docs/transformers/model_doc/internvl) supports multi-image/video input and SDPA; the model card specifies Transformers at least4.52.1. Native class import succeeded in the unchanged patched environment. Exact weights are2,121,890,856 bytes; all processor, tokenizer, template and config files are pinned separately. Documentation supports local CUDA/bf16 inference but does not certify this exact Windows6GB/16GB configuration: actual forward-pass, memory and time are the acceptance evidence. No FlashAttention installation, remote model code or quantization package is required for the selected native path.

SmolVLM2 was considered from its official card, whose Apache2 license permits commercial use but whose usage section lists individual/employment evaluation among prohibited/out-of-scope applications. It was not adopted for this workplace-oriented case. This selection does not invent additional bank rules or model capabilities.

After the earlier CPU worker cleanup, five current RAM samples showed at least5,700,579,328 bytes available. The older1,105,920-byte minimum was sampled during that CPU run; its cause was not isolated, and no OOM was observed in the owned run. Three earlier post-cleanup samples already showed over5,661,450,240 bytes available. These are whole-system observations, not proof of a memory leak or a specific foreign process. No foreign process was inspected or stopped.

Require4GiB available RAM before download/load,1.5GiB minimum available system RAM during work, sampled worker RSS at most4.5GiB, Torch reserved at most5000MiB, device-wide used VRAM at most5600MiB and at least4800MiB free VRAM before load. A watcher checks sampled resource values during import/load/generation and stops only the owned worker on breach. Two successive low-RAM samples trigger stop; sampling cannot guarantee absence of shorter excursions. The supervisor owns its Windows job and reclaims descendants on worker exit/deadline. No OS security, firewall, persistent environment, credential or foreign process change.

The existing `.venv-patched` remains unchanged. Isolation means a dedicated owned Python worker, fixed package/model inventory and process-local offline network guard; this stage does not claim to have copied every package into a new environment. Weights load with local_files_only and trust_remote_code false. Raw responses/native logs are never persisted or emitted.

## Prospective protocol

`config/internvl-protocol.json`, one registration/run. The complete model/tokenizer/processor/template inventory, source, runtime versions, manifest/split and private pilot selection are frozen before inference. No numerical-text prerequisite is imposed on visual recognition.

Eight fixed synthetic conditions: two layouts, each with EXIT/ENTER/STAY across four generated448-pixel frames, plus a no-image condition with the same question. ENTER is the exact reversed image sequence of EXIT. Definition order differs between layouts; each within-layout prompt is identical across physical classes. Figures contain no identity or realistic faces. Independent pixel tests verify the figure's relationship to the zone and sequence reversal; actual runtime asserts one448-pixel patch and256 image tokens per frame. Exact single-state JSON (optionally one surrounding JSON code fence) and normal EOS are required. The two no-image requests have different definition-order prompts; they are two conditions, not independent population samples.

Require6/6 visual and2/2 no-image UNKNOWN responses, normal EOS, valid format and no technical/resource failure. Complete all eight normal semantic attempts, then stop on failure without prompt rewrite, extra seed or compensation. This small geometry test measures an observed state/order prerequisite; a failure does not establish general visual incapacity, and a pass does not establish recognition of real people, bank procedures or a legal breach.

Only a passed synthetic gate permits six TRAIN videos,3+3 by official binary label, unique content/groups, selected deterministically by SHA before model execution. Source filenames, official binary labels, source sequence IDs and label points never enter model input. Within-request frame markers F0 through F7 intentionally preserve temporal order. Eight uniform positions from0.05 to0.95 are decoded with original PTS; full fields are letterboxed and one patch per frame is used. The inference boundary accepts only images, the fixed physical question and a deadline. Label points are used afterward solely for an aggregate distance, never to find candidate frames.

The fixed question asks whether a person initially at a workstation visibly moves away while another person remains near it; it does not infer identity, cashier role, service completion, intent or violation. YES/NO/UNKNOWN are internal observation outcomes, not a third jury verdict. UNKNOWN stays separate in a binary-label-by-observation table and coverage. Official labels do not supply person/zone/action truth: this pilot is **proxy association**, not physical-action, event-type, rule or evidence-relevance accuracy. Point distance cannot be called action localization accuracy.

Continuation only: technical completion6/6, at most one UNKNOWN, YES in at least2/3 positive-label sources and at most1/3 negative-label sources, max decode/inference70 seconds. These are exploratory screening targets on reused TRAIN, not release or official judging thresholds. Even a passed continuation requires independent local primitive/type/rule evidence. No model/prototype, legal registry or production inference setting changes automatically.

Total900 seconds includes identity checks, loading, controls, optional pilot, cleanup and report publication. Startup120 seconds, synthetic call30, pilot call45, pilot video70, pilot phase480. Technical/resource/deadline failure revokes gates; partial aggregates remain technical evidence. Only aggregate metrics are emitted; any structured pilot rows stay private and unread by cloud tools. TUNE/HOLDOUT and quarantined notes remain closed.

No public access, permanent key, external bank-data transmission or form submission is part of this stage.

## Registered outcome

Registration SHA256 `61a9724211c831446e72e13eefd5759f6e6a0b6fd074b7e252c5667b1fd64c89`. The source-only reviewer checked the native processor implementation and protocol. Before freezing, exact artifact coverage, outer deadlines and synchronous Torch high-water checks were repaired and tested. The complete suite passed286 tests, zero failures/errors/skips, JUnit28.824 seconds; the existing TestClient deprecation warning remains. No frozen source was changed after registration.

Artifact preparation initially hit its480-second configured download budget, leaving2,113,929,216 weight bytes. A bounded resume fetched the remaining7,961,640 bytes and verified the full official SHA. The final preparation report's13.218 seconds measures that resume/finalization attempt, not the complete fresh download. All13 selected model artifacts and the official model card have saved digests. No runtime package was installed or changed.

Actual processor-only checks, without a model forward or GPU, confirmed0/4/8 images produce0/1024/2048 image tokens and image tensors of N×3×448×448 when present. Full input lengths were130/1178/2226 tokens for those generated checks. The earlier legacy-kwargs warning is preserved separately; the registered runtime uses the native processor_kwargs API and its recheck passed.

| Fixed condition group | Correct | Format / normal EOS | Aggregate predictions |
|---|---:|---:|---|
| Ordered visual state |3/6 |6/6 | EXIT2, ENTER3, STAY1 |
| Same question without images |1/2 UNKNOWN |2/2 | UNKNOWN1, EXIT1 |

All eight planned calls completed, with no non-EOS response. The visual gate failed on actual images, independently of the old numerical-text control. One no-image response assigned a movement without visual input. The aggregate histograms do not identify a mechanism, per-layout confusion or per-case prediction identity. This small control does not prove general visual incapacity; it fails the predefined prerequisite for this candidate configuration. No adaptive prompt/seed/retry followed. **TRAIN pilot completed0; no real video/frame was read or passed to this model.** TUNE/HOLDOUT, notes, rules and the XCLIP baseline/prototypes remain unchanged.

The worker completed technically with exit0 and a failed compound continuation assertion. Processor/model loading5.640 seconds excludes Python imports; the synthetic phase34.797 seconds covers preprocessing/generation/scoring/persistence. Worker including cleanup55.343 seconds; authoritative monitor57.203 seconds, below900. Maximum visual call5.937 seconds, blank call2.344 seconds. These costs exclude fresh downloading and are not real-video API or five-minute judging measurements.

Actual Torch reserved high-water2266MiB. Sampled worker RSS2762.88671875MiB; minimum sampled system available RAM2.3337173461914062GiB; device-wide VRAM peak2367MiB and free minimum3554MiB. RAM/GPU samples78/77. No resource stop occurred; synchronous Torch checks and owned runtime/job cleanup passed. Three post-worker RAM samples showed available5,353,631,744–5,357,989,888 bytes. This establishes resource fit only for four generated frames or blank input per call. Eight-frame processor handling was checked, but eight-frame model forward and real-video memory/runtime remain unmeasured.

Safe evidence: `.private/internvl-prepare/*safe-summary.json`, `.private/internvl-control/safe-summary.json`, `calculation-safe-summary.json`, `tests-safe-summary.json`, `post-cleanup-memory-safe-summary.json`, `run/terminal-safe-summary.json`, `run/resource-safe-summary.json`. `scripts/summarize_internvl.py` verifies source hashes, fixed call/token counts and units without reading pilot rows/media/responses. The [claim ledger](claim-ledger.csv) distinguishes configured thresholds, artifact preparation, processor checks and actual inference measurements.

Decision: close this fixed candidate after its failed visual prerequisite. No semantic/type/rule release or TRAIN continuation is accepted. The demonstrated contribution is a bounded, actually measured different-VLM test with image-absence control and safe resource margin; it is not a detection-quality advantage or a competition-ready classifier.
