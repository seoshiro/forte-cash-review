# Normative and semantic capability inventory

**There is no accepted semantic detector.** The registry contains four enabled rule IDs from one public source; an enabled registry entry does not establish that a model recognizes its conditions. The binary XCLIP candidate emits `unverified` / `not_assessed`, is not release eligible, and deliberately returns 503 on the official competition API in research mode.

All registered references point to [NB RK Resolution 231 of 29 November 2019](https://adilet.zan.kz/rus/docs/V1900019680). The table records existing code/configuration, not new legal advice or a fresh verification of the current law.

| ID | Existing reference | What an accepted detector would need | Current limit |
|---|---|---|---|
| R20 | Paragraph 20 | Operation sequence, counting, prior cash and applicable storage state | No accepted counting, operation-boundary or storage detector. Registry conditions combine two branches and may overrestrict the first. |
| R22 | Paragraph 22 | Cashier/workstation identity by operational role, actual departure and ongoing customer service over time | Dedicated predicate requires a clear zone, departure, ongoing service, context and supporting frames; its input facts remain unvalidated model claims. Standing alone is insufficient. |
| R31 | Paragraph 31(4), paragraph 32 | Actual issue/counting sequence and packaging/exceptions | No accepted issue/count or package-integrity detector. Sparse frames do not establish an omitted action. |
| R42 | Paragraph 42 | Internal operation, control-worker role and applicable exceptions | No accepted internal-operation or control-role detector. A second person alone proves neither control nor its absence. |

No phone, device or bag category is a standalone accepted violation. Paragraphs 12, 19(2), 24(3–4) discussed in the earlier source audit are not registered detectors. Binary dataset labels do not provide type or applicability ground truth.

## Enforcement versus recognition

`cashreview/engine.py` checks registered IDs, timestamps, confidence and the model's `all_conditions_visible` claim. It fixes type/citation through the registry, but has no explicit exclusion field. The budget and GGUF candidates require `v=true` and `x=absent`; unknown or present exclusions are rejected. These checks validate asserted fields, not their visual truth. R22 has a separate predicate in `hybrid_candidate/observer.py` and metadata binding in `scripts/hybrid_experiment.py`.

## Source provenance gap

The recorded edition UUID, revision date and digest in `config/rules.json` are historical provenance. This review did not freshly establish current applicability from the official page, which returned an application shell. `scripts/verify_rules.py` checks current-version metadata from `nb231-document.json`, extracts quotes from a separate `nb231-plain.txt`, and stores the digest of `document.text_content` without verifying equality/linkage to that plain text. This is a chain-of-custody gap, not proof that the quoted paragraphs are wrong.

Before a competition semantic release, repair and verify that source linkage, confirm current applicability, validate visible conditions and exclusions locally, and obtain separate local event/type/evidence annotations. Do not send video observations or annotations to cloud tools. No source or semantic validation claim is inferred from the registry count.
