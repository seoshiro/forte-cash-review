# Protected research prototype delivery

Current working local prototype: http://127.0.0.1:8768/. It still uses the preserved cosine baseline and clearly marks event type/rule as unverified. It is a research binary candidate viewer; the competition `/api/v1` contract deliberately returns503. It is not a submission-ready detector. Do not use the local test key for public exposure.

A separate origin is prepared at loopback8769 by `scripts/serve_research_delivery.py`. It requires a separately provisioned user-scoped DPAPI credentials file: purpose `research-prototype-only`, distinct primary/other_owner random keys and a future expires_unix at most eight hours away. No keys or origin are created by preparing/importing this launcher. No permanent jury key is created here.

After authorized credential provisioning, local activation command:

```powershell
.\.venv-patched\Scripts\python.exe scripts/serve_research_delivery.py --credentials-file .private/research-delivery/credentials.dpapi
```

The key value stays in the private encrypted file/server process and is entered by the user into the UI; never put it into a URL, CLI argument, JS bundle, Git, cloud tool output or screenshot. Startup verifies the preserved prototype artifact, uses a separate private jobs directory, and loads no cloud model. All inference remains local/offline. Any public transport must use the previously authorized free portable Quick Tunnel without login, new grants, DNS/firewall/VPN/service/autostart changes. Recheck the existing pinned binary before activation; never expose the dataset directory.

The gateway permits only research static files and authenticated research upload/job routes. Duplicate/wrong/missing keys are rejected. Old UI/result routes and arbitrary static/private paths are blocked. Expiry closes every HTTP route. Backend owner isolation, upload/resource bounds, real PTS/JPEG validation and cleanup remain in the existing API. The research result never invents event types or legal conclusions.

Before handing out a public URL: test missing/wrong/duplicate keys, wrong owner/unknown job, expiry, unsupported paths, and a complete upload-to-done using generated safe.mov only. Decode returned JPEG bytes locally; emit only technical aggregate checks, never a real video's verdict/frame/description. External browser QA may show only synthetic media/results. A healthy localhost endpoint is not proof of public availability; a prepared gateway is not a running origin/tunnel.

This stage tested gateway controls with artificial HTTP fixtures only. It did not start8769 or a new tunnel, provision working credentials, test a new public URL, or submit anything to organizers. Current synthetic presentation PNGs remain private until final handoff.
