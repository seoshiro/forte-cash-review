# Normative and semantic capability inventory

**There is no accepted semantic detector.** The registry contains four enabled rule IDs from one public source; an enabled registry entry does not establish that a model recognizes its conditions. The binary XCLIP candidate emits `unverified` / `not_assessed`, is not release eligible, and deliberately returns 503 on the official competition API in research mode.

All registered references point to [NB RK Resolution 231 of 29 November 2019](https://adilet.zan.kz/rus/docs/V1900019680). The table records existing code/configuration, not new legal advice or a fresh verification of the current law.

| ID | Existing reference | What an accepted detector would need | Current limit |
|---|---|---|---|
| R20 | Paragraph 20 | Operation sequence, counting, prior cash and applicable storage state | No accepted counting, operation-boundary or storage detector. Two independent branches are recorded; the current hypothesis is storage only. Unknown device purpose/ownership blocks a conclusion. |
| R22 | Paragraph 22 | Cashier/workstation identity by operational role, actual departure and ongoing customer service over time | The registry conservatively limits this to receipt; the dedicated predicate requires a clear zone, departure, ongoing service, context and supporting frames; its input facts remain unvalidated model claims. Standing alone is insufficient. |
| R31 | Paragraph 31(4), paragraph 32 | Actual issue/counting sequence and packaging/exceptions | No accepted issue/count or package-integrity detector. Sparse frames do not establish an omitted action. |
| R42 | Paragraph 42 | Internal operation, control-worker role and applicable exceptions | No accepted internal-operation or control-role detector. A second person alone proves neither control nor its absence. |

No phone, device or bag category is a standalone accepted violation. Paragraphs 12, 19(2), 24(3–4) discussed in the earlier source audit are not registered detectors. Binary dataset labels do not provide type or applicability ground truth.

## Enforcement versus recognition

`cashreview/engine.py` checks registered IDs, timestamps, confidence and the model's `all_conditions_visible` claim. It fixes type/citation through the registry, but has no explicit exclusion field. The budget and GGUF candidates require `v=true` and `x=absent`; unknown or present exclusions are rejected. These checks validate asserted fields, not their visual truth. R22 has a separate predicate in `hybrid_candidate/observer.py` and metadata binding in `scripts/hybrid_experiment.py`.

## Source provenance — gap closed

Fresh official API/document history and direct HTML paragraph extraction verified the current recorded edition and all four unchanged canonical quotations. The separate-plaintext input has been removed. Raw responses, exact HTML, source URLs, edition metadata, anchors, quote hashes and parser/code identity are now linked and checked offline. The verifier rejects missing/duplicate rule IDs and modified provenance fields. See [the exact provenance and applicability report](legal-source-provenance.md).

This closes a technical source-chain gap. It does not validate visible conditions, exclusions, event types or evidence relevance. Those require separate local annotations and evaluation. Do not send video observations or annotations to cloud tools. Accepted semantic detectors remain zero.
