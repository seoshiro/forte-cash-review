# Rule mapping and exclusion audit

This is a source-code audit independent of video predictions. It does not establish that the dataset's labels correspond to the selected rule families.

The enabled registry entries are taken only from `config/rules.json`. Model output is constrained to these rule IDs, then validated again by `parse_observation`. The final API type and source citation come from the registry, not from a generated legal citation. A model cannot add an unregistered paragraph through its rule ID.

The native detail parser accepts an event only after validating the structured fields. It sets `all_conditions_visible` to the conjunction of the model's applicability flag and `exclusion == absent`. The final pipeline then requires that flag and the configured confidence threshold. A negative short gate skips detail generation. Technical parsing failures propagate as failures rather than a clean negative.

The new synthetic code tests exercise the actual final pipeline with unknown/present exclusions, false applicability and low confidence; none may reach evidence generation or the result list. A separate test rejects an invented rule ID. These checks establish implementation behavior, not the truth of a model's applicability assessment.

| Rule family | Relevant code/registry limitation |
|---|---|
| R20 | The source has separate provisions about counting in the client's presence and storage of previously accepted cash. The current visual-conditions field concentrates on distinguishing previous/current operations. A prompt requiring every listed condition may consequently overrestrict the counting branch. No automatic relaxation was made during the frozen diagnostic. |
| R22 | Leaving a seated position alone does not establish leaving the workplace before service finishes. The registry requires observable service context and workplace boundaries; the primitive question is deliberately weaker. |
| R31 | An unobserved count in sparse samples cannot prove omission throughout the procedure. Intact packaging exceptions must be considered. The registry's requirement for a visible full sequence can cause abstention when temporal coverage is sparse. |
| R42 | Internal sorting/counting must be distinguished from client receipt or payout, which the source excludes. The presence of another person does not prove a designated controlling worker, nor does absence in a partial view prove lack of control. |

The model is currently asked to assess these conditions; the code does not independently verify them. The primitive diagnostic therefore requests observable signs separately from legal judgment. A supervised primitive head is only a diagnostic of visual signal. It cannot replace the verified applicability and exclusion checks or make a legal rule out of a correlated object.

No rule registry or production prompt was changed during ORACLE-01. If label-to-rule mismatch remains unresolved, a human must review the selected TRAIN cases locally, record applicable rule/conditions/exclusions or an explicit mismatch, and keep all footage and observations local. A cloud chat must not receive descriptions of individual cases.

## Catalogue breadth

The cached official current text contains additional provisions that the enabled catalogue does not cover. This is a scope gap, not evidence that the dataset contains those events. The source is [NB231](https://adilet.zan.kz/rus/docs/V1900019680), whose edition and cached text hash are recorded in `config/rules.json`.

| Public provision outside the enabled catalogue | Limits on a possible visual check |
|---|---|
| Paragraph 12: storage of employees' personal items outside the cash unit; expressly allowed communication devices lack photo/video functions | This is not a blanket ban on every telephone. A phone-like object alone does not establish ownership, exact zone boundaries or camera capability. The primitive question is not a legal finding. |
| Paragraph 19(2): per-note/per-coin counting and authenticity/payment-fitness checking during receipt | A partial view or sparse sampling cannot prove that the check was omitted. Device presence alone does not prove use, and numerical cash reconciliation is outside visual proof. |
| Paragraph 24(3)-(4): bag integrity and sealing checks in the specified cash-collection intake context | The intake context and relevant bag/closure must be established. A generic bundle or bag is not sufficient; missing a check in sampled frames is not proof of omission. |

These entries remain disabled and were not added to either diagnostic prompt. A narrow catalogue may produce conservative negatives even if a visual model detects physical actions. The current diagnostic cannot by itself distinguish catalogue mismatch from incorrect applicability judgments; local human annotations would resolve that distinction.
