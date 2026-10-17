# Authorized external-access checkpoint

The user approved a free Cloudflare tunnel to this service and a separate permanent jury key at **2026-10-17 22:02:55 UTC**. The parent then explicitly authorized an independent synthetic-only infrastructure test. That test is complete; the tunnel and its origin are now stopped. No permanent jury key was created and nothing was submitted.

## What was actually tested

The bounded run used a separate loopback origin, separate private job store, generated geometric MOV fixtures, and separate locally generated demo owner keys. Hash allowlisting rejects every other input before decoding/model use. Bank videos, annotations and model inference were not used.

Public HTTPS checks passed for the UI shell and required API routes: missing/wrong-key rejection, unknown-job handling, owner isolation on job/detail routes, strict synthetic results, source JPEG/PTS equality, corrupt MOV returning failed, and a close second upload returning 429 with Retry-After. Private paths, API docs and experimental routes are blocked. Raw connector logs are discarded without storage; only the temporary hostname is parsed locally. Keys remain encrypted using Windows DPAPI USER scope and never enter source, argv, logs, query strings or public JavaScript.

Aggregate evidence: **2 completed synthetic jobs, 3 source-JPEG checks**. Upload-to-result mean **11.8595 s**, maximum **11.922 s**, with an intentional **10 s synthetic delay** to exercise concurrent admission. The whole technical monitor took **41.719 s**. These are infrastructure timings, not model speed or competition quality.

The authoritative PASS depends on worker completion, owned-process cleanup and an external observation that the stopped origin no longer answers. All passed. `.private/access-synthetic/safe-summary.json` and `rollback-safe-summary.json` hold safe aggregate evidence. The private endpoint file marks `active_expected=false`. No public service is currently claimed from this run.

## Route, terms and rollback

Pinned portable connector: **cloudflared 2026.10.1**, official Windows x64 artifact, SHA256 `4d2490e74082c5d48dbfedaf92576fa5bd1702379ab88eb7faa0cfbe8dc891b6`; [artifact identity](../config/cloudflared-artifact.json). Code: [preparation](../scripts/prepare_cloudflared.py), [synthetic origin](../scripts/serve_synthetic_access.py), [bounded smoke](../scripts/synthetic_tunnel_smoke.py).

[Official Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) was checked on 17 October 2026. A temporary endpoint needs no account/domain and ends when its process stops. Quick Tunnels are for testing/development, have no uptime guarantee, change hostname on restart and do not support SSE. No paid resource, trial, billing/card action, account login, named tunnel, DNS record, persistent Cloudflare credential or new persistent grant was created. OS firewall, WARP, system services and security settings were not changed.

The origin binds only loopback; connector metrics bind loopback too. The explicit empty config avoids default account configuration, and an existing explicit certificate path fails closed. An owned Windows Job bounds and cleans up descendants. Restarting creates a new temporary URL and requires another explicit bounded operational action; do not reuse the stopped URL as a submission address.

To reproduce this synthetic test locally after preparation:

~~~powershell
.\.venv-patched\Scripts\python.exe scripts/synthetic_tunnel_smoke.py run
~~~

This command temporarily exposes only its separate synthetic origin and stops it automatically. It does not start the bank service. `show_synthetic_access_key.py` is a user-invoked local GUI for the demo key; do not execute it through cloud capture or treat that key as a jury key.

## Remaining release work

An accepted semantic detector, type/rule mapping, real new-input validation, reliable operating window and separately verified offline inference remain unresolved. The synthetic pilot does not satisfy those requirements. The permitted permanent jury key is still uncreated; when the service is ready, create/store it locally and hand it over only through the agreed private user channel. Keep it out of cloud context and code-only publication. New persistent grants or routes beyond existing authorization need a narrow decision immediately before the action. No organizer messages or form submission are authorized here.

Run repository/history audits and source review before any remote publication. Keep the official research API fail-closed until its semantic requirements pass. [Capability inventory](semantic-capability-inventory.md), [measurements](xclip-tune.md), [claim ledger](claim-ledger-index.md).
