# TRAIN oracle-window diagnostic

ORACLE-01R1 compares the existing uniform coarse extraction with a short window around each selected positive TRAIN point annotation. Negative examples have no event timestamp: their pseudo-window centers are matched one-to-one to the positive relative times by a fixed seeded pairing. Missing negative timestamps are never interpreted as zero. Both modes use actual decoded PTS, the same sampled image size and chronological panel adapter.

This deliberately uses TRAIN labels for diagnostic frame selection. Oracle results cannot be used as production quality, an independent validation score, a localization result, or evidence that an event would have been found without the supplied timestamp. The selected development control has already been used. TUNE and HOLDOUT are excluded regardless of the outcome.

The frozen visual questions are in `config/oracle-diagnostic.json`. They concern physical objects and actions and do not request a legal conclusion. Raw answers remain private. A single pre-registered logistic head evaluates whether the pooled answers have any label signal. Its training fit and leave-one-automatic-group-out predictions are reported separately. There is no threshold, feature or hyperparameter search. Constant positive and negative controls are also reported; high recall from an all-positive output is not success. A primitive classifier cannot by itself establish a rule or an exception.

An unchanged legal gate is run separately for both extraction modes. In the revised experiment both modes use the same corrected schema transport, so the earlier and revised transport are not mixed in their comparison. Diagnostic timings include all primitive and gate calls; they are not deployment latency measurements.

The initial ORACLE-01 stopped on generated gray panels before reading bank frames. A synthetic format probe showed valid JSON with the wrong object structure, without reaching the token limit. Inspection of the [actual pinned b11712 parser](https://github.com/ggml-org/llama.cpp/blob/b11712/tools/server/server-common.cpp#L1218-L1235) showed that its `json_schema` format requires the nested schema field. The README's flat example differs. The adapter was corrected, prior reports were retained, and the revised experiment was registered separately under `.private/oracle-diagnostic-r1` before inference.

Before the revised TRAIN run, an adversarial synthetic request had to obey the schema despite conflicting text, followed by the generated-negative primitive control. Both passed. This establishes limited schema transport behavior, not visual/domain quality. Exact source URLs and content hashes are in `config/native-schema-provenance.json`; source copies are cached privately for offline inspection.

Point coverage is calculated separately at fixed tolerances from actual decoded sample PTS to each positive point annotation. It is not evidence-frame relevance or coverage of an entire action. One timestamp in the supplied labels is not exhaustive event annotation. The independent rule/exclusion implementation audit is in [rule-code-audit.md](rule-code-audit.md).

All observations, primitive vectors, label associations and per-case details stay in `.private`. Only aggregate confusion matrices, point-coverage rates and timing enter the report and claim ledger. No employee recording is used.

## Completed decision

Completed paired TRAIN cases: 8 / 8; technical failures: 0. Frozen code/configuration and source hashes were unchanged. TUNE and HOLDOUT were not used.

Matrices below are TN / FP / FN / TP.

- regular: legal gate 4 / 0 / 4 / 0; primitive head training fit 1 / 3 / 0 / 4; group-LOO 0 / 4 / 1 / 3; point coverage within 1 second 3 / 4; diagnostic mean 84.529125 s, maximum 85.547000 s.
- oracle: legal gate 4 / 0 / 4 / 0; primitive head training fit 2 / 2 / 0 / 4; group-LOO 2 / 2 / 1 / 3; point coverage within 1 second 4 / 4; diagnostic mean 42.570375 s, maximum 43.656000 s.

Decision: improving point coverage alone did not repair the legal gate. The oracle primitive head has limited label signal but still makes false positives and a false negative; its regular-extraction counterpart is worse than a constant-positive control. Neither is accepted for production. Oracle input uses known labels, so its apparent improvement is a capability diagnostic only. The current configuration has not demonstrated sufficient visual/domain capability. Catalogue mismatch remains unresolved; no blanket claim that the underlying model cannot see these actions is justified.

Do not continue blind gate/prompt variation. The prepared TRAIN-only local human review packet is under .private/oracle-diagnostic-r1: review-selection.csv and local-review-instructions.txt. It asks for applicable public rule/visible conditions/exclusions or explicit mismatch, and contains no model answers. Existing private viewer saves annotations under .private/annotations. No footage or per-case descriptions should be sent to chat. No human review is claimed to have happened.
