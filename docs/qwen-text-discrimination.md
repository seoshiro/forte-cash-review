# Synthetic input discrimination

Purpose: distinguish why the earlier action probe scored1/3 per cell, including text coordinates. Its aggregate counts cannot establish constant predictions or an index permutation. The runtime audit found no rendering defect in its tested inputs. Preserve the best XCLIP baseline and every earlier failed run; no TRAIN/TUNE/HOLDOUT, local notes or bank material enters this control.

Independent unit checks cover hardcoded region boundaries/radius, red-disk bounding boxes, text coordinates, forward/reverse order, actual mock HTTP payloads and perfect/permuted/constant scoring. The new scorer additionally rejects duplicate JSON keys, multiple/missing choices, invalid content and unexpected finish reasons. These permissiveness fixes are not established causes of the old result. The old registered probe remains unchanged.

| Alternative | Discriminating observation |
|---|---|
| Generator/scorer/mapping defect | Independent pixel/coordinate oracle or known mock outputs fail before GPU |
| Input missing from request/rendering | Captured request or actual apply-template comparison fails; literal-copy failure alone does not prove lost input |
| Label binding defect | Off-diagonal confusion and failed semantic mapping despite correct literal-copy; compare known unit mappings |
| JSON grammar influence | JSONplain and schema differ with literally identical prompt/body except response_format |
| Enum-position influence | Predictions change after only the schema enum order rotates |
| Prompt-order influence | Predictions change after reordering definitions/allowed labels while preserving mapping and geometry |
| Coordinate reasoning difficulty | Literal-copy succeeds while numeric motion fails; capacity/backend cause remains unidentifiable |

Frozen protocol: `config/qwen-text-discrimination.json`, one run. Registration SHA256: `dab7b9f6c438704e297bad9093d9115b47c025561e301d4ac666869d74f1a2c7`. Text has36 calls: literal-copy9 (three targets, bare/JSONplain/schema); geometry18 (three actions, two cyclic label maps, three modes); schema enum rotation3; prompt-order changes6 (bare and JSONplain). ALPHA/BETA/GAMMA outputs are mapped back to semantics independently. JSONplain/schema differ only by response_format. Bare versus JSON changes requested output format and is not a pure grammar ablation.

Every generation is preceded by an expected-versus-actual apply-template check of its complete synthetic input. This confirms request rendering, not numerical backend use of input or vision embeddings. Save aggregate per-cell confusion matrices, output-token histograms, valid format/stop/truncation counts, latency/token sums and paired-change counts. Do not retain or emit raw responses, prompts or native logs.

Only all36 correct strict-format normal-stop text responses permit the18 matching generated-image calls. Otherwise images are not run. Technical failures leave partial aggregates and semantics NOT_ASSESSED; truncation is not evidence of incapacity. No adaptive prompt changes, extra seeds or retries. One owned offline native GPU process, loopback only, temporary test key. Total budget480 seconds includes identity checks, loading, cleanup and report publication; text240 starts at native readiness, conditional images180 starts at their gate. Individual call budgets8 text/15 image seconds include rendering plus generation.

The supervisor evaluates one compound assertion (text gate and conditional image gate); its completed_cases is an assertion count, not model calls. Actual completed calls must equal the sum of aggregate cell counts. A semantic gate failure can complete technically; HTTP/native/deadline/cleanup/report failures cannot be converted into a model-quality finding.

## Completed result and interpretation

The registered run completed technically:36 generation calls,36 verified complete rendered inputs,36 valid expected-format responses,36 normal stops, no truncations or technical errors. Literal-copy passed9/9 across all three output modes. Numeric geometry passed9/27 and failed the frozen text gate; images were not run. The complete compound assertion is false, not a passed semantic control.

| Text condition group | Correct / calls | Observed aggregate behavior |
|---|---:|---|
| Literal-copy: bare / JSONplain / schema |9/9 | Each mode returned all three different target tokens correctly |
| Geometry map0, three modes |3/9 | Constant decoded EXIT; raw ALPHA |
| Geometry map1, three modes |3/9 | Constant decoded EXIT; raw GAMMA despite unchanged allowed-token list |
| Geometry map0, rotated schema enum |1/3 | Still ALPHA / EXIT |
| Geometry map0, reordered prompt, bare / JSONplain |2/6 | Constant BETA / ENTER |

Every geometry cell has constant decoded semantics across its three changed coordinate inputs. All27 geometry responses select the first stated definition in their condition. A globally fixed raw ALPHA answer and pure first-schema-enum selection do not explain this new run. The map1 condition also contradicts a universal first-allowed-token explanation. The reordered prompt changes both definition order and allowed-list order, so their interaction is not fully separated and the underlying arithmetic, binding, precision or backend mechanism remains unidentified. Do not call a prompt rewrite a proven fix.

Paired comparisons: schema on/off changed0/9 labels or semantics; enum rotation changed0/3; prompt reordering changed6/6, with exactly one correct in4/6 and neither correct in2/6; label mapping changed9/9 raw tokens and0/9 decoded semantics. All pairs had valid format and normal stop. These are observations of this small frozen set, not universal grammar/decoding guarantees. The earlier probe did not retain prediction identities; this run does not reconstruct them.

Literal-copy and mapping-dependent raw tokens show that text input is not discarded wholesale. Exact request/render checks and mock-body tests found no generator/scorer/transport defect here. That is weaker than verifying every coordinate comparison or numerical backend operation. The model failed to use the coordinates to distinguish these physical classes, even without JSON grammar and with a bare-label response. No TRAIN experiment or bank-action claim is justified.

Startup7.844 seconds; text phase150.328 seconds; worker including native cleanup185.907 seconds; authoritative monitor188.219 seconds within480. Actual worker exit0; native was alive before intentional shutdown and exited15 afterward; native and owned-tree cleanup completed. Device-wide sampled VRAM peak4041MiB,285 samples; this includes other processes and is not per-process allocation. Full synthetic/unit suite250 passed, zero failures/errors/skips, JUnit32.032 seconds; existing TestClient deprecation warning remains.

Evidence: `.private/qwen-text-discrimination/safe-summary.json`, `run/terminal-safe-summary.json`, `calculation-safe-summary.json`, `tests-safe-summary.json`; claim ledger regenerates from fixed safe reports and configuration. No raw responses/prompts/logs were retained, no user notes were reopened, and the best XCLIP baseline and dataset splits were not modified.

## Concrete next choice, not executed

Prefer one prospective **text-only decomposition control** before a backend comparison: three numeric-facts cases returning only first_inside/last_inside/all_inside; three symbolic Boolean-facts-to-label cases without arithmetic; twelve geometry cases separating definition order and allowed-list order independently. Total18 calls, JSONplain only, same physical cases, no images or prompt search. If numeric facts pass while direct labels fail, this supplies a testable basis for facts followed by deterministic action mapping; it does not validate visual extraction.

`config/qwen-decomposition-draft.json` is explicitly unregistered and unrun. Source-reviewer planning estimate20-30 minutes for implementation, independent checks, review and one run; unmeasured, with a proposed240-second run cap. No corrective rerun was claimed because the root cause and a validated correction have not been established.
