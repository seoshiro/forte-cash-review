# Isolated binary research API

This mode integrates the best saved comparative XCLIP candidate without fabricating event semantics. The original baseline, source caches, group OOF results and threshold remain unchanged. Deployment prototypes fit all exact-unique TRAIN contents from the verified frozen feature cache; this is not a new independent quality evaluation or an in-sample score.

`CASH_MODE=xclip_experimental` requires `CASH_ENGINE=xclip_experimental`; selecting this engine under the ordinary mode is rejected. The default store and localhost port are separate. A store-contract marker is checked under the instance lock before orphan reconciliation or job mutation. Known other-mode stores are rejected.

- `POST /api/experimental/xclip/analyze`: multipart MOV in `file`, returns job ID.
- `GET /api/experimental/xclip/jobs/{job_id}`: processing/done/failed, requires the owner key.
- Both require `X-API-Key`; unknown and other-owner jobs return404.
- Competition `/api/v1/*` and ordinary result/review `/api/ui/*` are unavailable in this mode. The normal service hides experimental routes.

The result contains `binary_decision` (`violation` or `no_violation`), raw signed cosine margin at threshold0, candidate time and1–3 original JPEG candidate frames for a positive binary result. They are candidate support, not independently verified proof of a legal breach. `event_type_status=unverified`, `rule_application_status=not_assessed`, `release_eligible=false` are fixed. No inferred category, scene description or normative link is manufactured. This schema is deliberately separate from the official jury JSON.

Inference receives the opaque job input, fixed model/config and two learned prototypes. It reads no filename lookup, official labels, source-video IDs or training caches. Models load local-only and socket connections are blocked in the inference worker. The API includes upload in its existing monotonic processing budget and kills/reaps an overdue worker; a technical error is failed, not a negative classification.

Prototype schema2 freezes the exact five-file model directory and actual SHA256 digests for weights, model config, preprocessor config, provenance and model card. Preparation checks these against the original feature registration before and after fitting. Alternate added configs/code and changed files are rejected. The private v2 directory preserves the original v1 pack. Model and library versions must match; runtime inference never reads training caches.

Code/synthetic tests validate the API, owner isolation, schema, credential filtering, deadline handoff and artifact integrity without loading the encoder. A separate bounded actual-XCLIP smoke completed two uploads of the same newly generated rectangles MOV under different names. Upload-to-result times were22.375 and18.36 seconds; the owned monitor completed in43.796 seconds with actual worker exit0 and cleanup confirmed. Filename invariance, strict schema, authorization and disabled official routes passed. The synthetic outputs contained no candidate frames, so this smoke did not exercise the positive branch's actual source-JPEG path. JPEG/schema/source-time mechanics have separate synthetic tests; evidence relevance is unverified.

These checks do not measure bank-event quality. New real-input API integration, complete long-video API latency, event-type accuracy, generalization and physical network-disconnection checks remain unverified for this integration. UI demonstration remains the separate synthetic mode; this research API is not advertised as a complete checker workspace. The monitor's field `quality_gate_passed` in this technical fixture refers only to successful smoke assertions, not detector quality.

A later [controlled positive fixture](positive-evidence-plumbing.md) exercised the real score/evidence path with fixed synthetic features and a generated VFR MOV: three actual source JPEGs, decoded PTS and owner/auth/schema checks passed. It did not run learned weights or change production scores. The official contract was separately checked through the actual synthetic worker. This closes controlled positive plumbing while leaving learned positive selection/evidence relevance unverified.

The launcher binds127.0.0.1 only and uses a fixed temporary test value. It generates no permanent key and opens no tunnel. Never publish this test mode.
