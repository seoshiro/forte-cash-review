# Runtime template audit: completed without generation

All six synthetic message fixtures rendered byte-for-byte as expected from the pinned Qwen3VL Instruct GGUF template. Roles, image marker counts/order, unique fixture sentinels and the assistant generation suffix passed. This includes the actual single typed-text-part shape used by the failing text-coordinate action control, system/user and multi-turn messages, four separate generated images, one generated montage, and an explicitly disabled generation suffix.

The original strict report remains **6/7 checks passed**: its additional `/props` check required the source string to equal the GGUF byte-for-byte. Vision was enabled, but the source hash differed. A separate **post-hoc public-header calculation**, without another server run, exactly explains that difference: the original has5292 characters and ends with LF; the lexer-normalized source has5291 characters. Removing that one terminal LF gives the exact observed `/props` hash:

| Source | SHA256 |
|---|---|
| Original GGUF template | `3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4` |
| Normalized GGUF / actual props | `9d879ef91075acbfb2df7e441fd79d60bacfca989cf6d511d2af45c681e94f10` |

The pinned [lexer](https://github.com/ggml-org/llama.cpp/blob/b11712/common/jinja/lexer.cpp#L29-L53) normalizes line endings and removes one terminal LF; the [constructor](https://github.com/ggml-org/llama.cpp/blob/b11712/common/chat.cpp#L1164-L1169) stores the resulting source. The original run/report, failed strict comparison and registration were preserved. This interpretation is not a rewritten passing gate.

Registration SHA256: `dcaed4f1abadc995eaa9adbf46bbfb9368677b2d5605bf781923d3113726a66c`. Code and native/model artifact identities were verified before and after the run. The worker used a fresh owned process tree, offline native runtime, loopback, temporary test authentication and an allowlist permitting only health, props and apply-template. No generation endpoint was reachable through that wrapper. Bank videos, user notes, previous responses and annotations were not read. Raw props, prompts and native logs were not emitted or persisted.

Native startup took10.609 seconds, worker time including cleanup41.078 seconds, monitor/terminal completion43.344 seconds within the180-second budget. The worker exited0. The native process remained alive before requested shutdown and exited15 afterward; native and process-tree cleanup completed. The Windows tool connection briefly dropped after execution had started; persisted terminal and safe reports later confirmed completion. No duplicate run was launched.

The server's [apply-template path](https://github.com/ggml-org/llama.cpp/blob/b11712/tools/server/server-context.cpp#L5194-L5207) uses the chat request parser and returns the rendered prompt without generation. Image parts become media markers before template rendering ([server-common](https://github.com/ggml-org/llama.cpp/blob/b11712/tools/server/server-common.cpp#L1121-L1135), [content normalization](https://github.com/ggml-org/llama.cpp/blob/b11712/common/chat.cpp#L142-L173)). This audit checks that stage. It does **not** validate the later vision embedding expansion, tokenization/numerical backend, response-schema grammar, model capacity, action semantics or bank-event quality. No rendering defect was observed in these fixtures. The earlier action-control weakness remains unexplained; another legal/bank gate or spatial search is not justified by this result.

Evidence: `.private/runtime-template-audit/safe-summary.json`, `run/terminal-safe-summary.json`, and `source-normalization-safe-summary.json`; numeric claims regenerate through `scripts/claims.py`. See [the action diagnostic](qwen-action-diagnostic.md) and [local hypotheses policy](user-hypotheses-policy.md).
