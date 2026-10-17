# API review

This is an engineering review with synthetic inputs, not a detector-quality score or a public availability test. The manual TRAIN form and its server were not changed or restarted.

Confirmed and corrected:

- Bad result JSON now returns `failed`; a result whose `job_id` differs from the requested job is rejected.
- Invalid/missing owner metadata returns unknown job, rather than an exception.
- A job-store file lock prevents two idle API instances from independently admitting GPU work.
- A failed worker kill no longer waits indefinitely. Cleanup waits are bounded; unconfirmed termination blocks new admission with service unavailable.
- The upload/worker deadline uses monotonic time from admission. A wall-clock adjustment cannot extend it.
- Cleanup tolerates malformed metadata, verifies a direct opaque child of the job root, rejects symlinks/junctions and skips active/unrelated folders. Invalid metadata falls back to the directory modification time for retention.
- Startup reaps verified orphan workers even when a result was already written before the old parent exited.
- Receive-side multipart overflow retains its payload-too-large response instead of becoming generic bad multipart input.

Output schemas require strict finite values. The official successful JSON fields, two verdicts and three job statuses remain unchanged. Technical failures never become `no_violation`.

| Check | Verified scope |
|---|---|
| Upload | Default 128 MiB file / 129 MiB whole multipart cap. Declared, chunked and file-level overflow branches were tested with reduced limits, without allocating full-size uploads. |
| Admission | Authentication/capacity reservation before multipart parsing; one admitted job, overlap 429, no waiting inference queue. Idle-store double startup is rejected. |
| Deadline | Configured budget at most 295 seconds from admission; bounded termination/reap after expiry. Accelerated tests cover stalled upload, clock adjustment, actual Windows worker-tree termination and unconfirmed termination. This is not a measured external SLA. |
| Isolation | Opaque random folders and fixed `input.mov`; foreign owner remains unknown. Traversal-like uploaded names do not select storage paths. Server API key and selected cloud/HF tokens are stripped from the child environment. |
| Retention | Default one-hour retention with periodic retry. Removal stays within the job root and never traverses dataset or manual-review folders. Deletion remains best effort if filesystem errors or file locks prevent it. |
| Failure/restart | Corrupt input/result/metadata, wrong result ID, incomplete work, orphan worker and live-owner protection covered by synthetic regression. |
| Locality | Current worker selects local baseline/budget engines, enables offline flags/network guard and loads local weights; no cloud AI client or request-time weight download is invoked. The experimental native HTTP client is loopback-only and not integrated into this worker. |
| Media | Forced MOV demuxer, file-only protocol and disabled external data references. A generated renamed HTTP playlist makes no HTTP request. PTS/VFR/rotation and JPEG/evidence regressions remain covered. |
| Privacy | Worker stdout/stderr are discarded. No real clips, frames, predictions or manual comments were read for this review. The only manual data inspected were aggregate completion counts. |

The first added regression set failed before the fixes; the corrected full suite passes. Exact counts/timings, configuration values and source digests are recorded in `.private/api-final-review/safe-summary.json` and `claim-ledger.csv`. Partial upload spool cleanup was also inspected in the installed patched framework source.

Remaining dependencies:

- Wait for the user's explicit completion signal, then validate the manual TRAIN proposals locally. Do not use unfinished annotations.
- Establish useful detection and event/rule grounding. ORACLE-01R1 and its head remain diagnostic and rejected for production; engineering passes do not change that decision.
- A future native API integration needs the correct narrow loopback allowance and explicit owned-child shutdown. It is not enabled here.
- With the final accepted engine, rerun full upload-to-result/evidence/rename/concurrency/longest-input checks, local offline operation, and authorized external HTTPS separately. Network/proxy behavior before ASGI admission and physical internet-disconnect operation are outside this code review.
- Permanent API credentials and a tunnel still need direct user confirmation. No key, tunnel, firewall change, remote publication or submission was made. API source fixes were saved; running services were not restarted.
