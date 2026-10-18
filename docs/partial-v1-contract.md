# Experimental partial competition transport

**Historical profile: retired.** The current deployment retains this transport with a separately expiring/revocable jury session. Use [final handoff](final-handoff.md) for the sole current URL, actual limits and restart instructions. Earlier profile details below are historical.

The supplied official JSON contract makes `type` a free text string. It has no separate normative-source field: a verified source can be included in `description`. This permits structural serialization of the preserved real binary/time result, but does not waive the brief's requirements to classify a visible action and justify it against an applicable rule.

The opt-in `--partial-v1` origin therefore exposes `POST /api/v1/analyze` and `GET /api/v1/jobs/{job_id}` using the unchanged local cosine baseline. Upload, model execution, queue limits, owner authentication, private job storage, expiry and failure handling still belong to the native service. The outer bridge changes the response representation only. The original research origin keeps its default behavior, including authenticated v1 503.

For a positive binary result the bridge preserves the actual candidate timestamp and original candidate JPEGs, uses `type: unclassified_suspected_event`, and explicitly says that the action, type and applicable rule have not been established. It does not invent a visible action, paragraph, legal conclusion or evidence. For a negative result it returns `no_violation` with an empty list. Technical failures remain `failed`; invalid native output becomes a technical 502, never a negative verdict. The native result file is not modified. No filename/label lookup, prediction replacement, new model or threshold change is involved.

Successful v1 responses contain only the required JSON fields. Limitations are also disclosed in HTTP headers (`X-Experimental-Mode`, `X-Semantic-Contract`, `X-Rule-Application`, `X-Release-Eligible`) and `/healthz`. Default mode remains opt-out. Removing the partial profile or stopping its owned supervisor reverses this stage without altering the original research service.

**Structural contract: implemented and tested. Semantic contract: incomplete.** The description is engineering provenance, not a verified observation of a cash operation. Classification, legal applicability, complete multi-event detection, evidence relevance and new-camera quality remain unaccepted. The official evaluator's treatment of an unclassified type is unknown. This endpoint is an experimental partial result, not a complete contest submission.

## Verified session

The partial profile uses loopback port 8770, its own private job directory and its own free Quick Tunnel. Current URL is in `.private/partial-contract-access/endpoint.json`. It reuses the already authorized temporary DPAPI research credentials and their expiry, 2026-10-18 08:38:41 UTC; no permanent jury key, persistent grant or OS configuration change was created. The original port 8769 session is preserved.

Read the shared temporary key only through `.private/research-access-live/Open-research-access.cmd` on the selected Windows computer. The local window lists both URLs. Do not capture that window or put the key in Git, JavaScript, cloud messages or a URL.

```powershell
# Check safely; credentials/results are never printed by this client.
.venv-patched\Scripts\python.exe scripts/research_access.py verify-synthetic --partial-v1
```

After the owned partial profile was refreshed with the final bridge code, the real public upload-to-done cycle passed for one generated geometric MOV in 17.828 seconds. Timing ends at the terminal poll, before the separate authenticated native-result equivalence request. Required JSON schema, actual native binary/time/evidence preservation and other-owner 404 passed. A generated invalid MOV also completed as `failed`, with no negative verdict. No positive candidate JPEG was returned by the generated video; public positive-evidence transport was not exercised. Separate generated positive fixtures verify response schema, JPEG preservation, immutable native storage and technical failure handling. These are technical tests, not bank-event quality or a latency guarantee. The final regression suite passed 432 source/synthetic tests, without failures, errors or skips. Reports are `.private/partial-contract-access/*safe-summary.json` and `.private/partial-contract-checkpoint/tests-safe-summary.json`; numerical claims are indexed in the claim ledger.

The UI uses the existing research workstation and local assets. Browser screenshots use only generated media and controlled HTTP fixtures. The three presentation PNGs were saved separately in Library; they do not demonstrate detector quality. Deck work stopped for the user's separate presentation workflow.

To stop only this profile, create `.private/partial-contract-access/stop.request`. Keep the Windows computer and internet connection running while sharing either temporary address. No automatic renewal, stable hostname or availability guarantee is promised. Cloudflare documents temporary hostnames, no uptime guarantee, 200 in-flight requests and no SSE; this product uses polling. [Official Quick Tunnel limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), checked 2026-10-18.

No form, organizer message or formal submission was sent. Further model searches stopped after the rejected complete fixed OOF comparison.
