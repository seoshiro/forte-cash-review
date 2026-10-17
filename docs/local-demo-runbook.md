# Local synthetic demonstration and launcher

The repaired PowerShell launcher uses `.venv-patched` and delegates to the maintained Python entrypoint. It no longer runs the historical environment or duplicates synthetic whitelist construction. The existing Python entrypoint binds loopback, sets offline environment flags and creates both artificial MOV fixtures. No permanent environment, key or OS policy is changed.

From the project directory, use a process-local test value:

```powershell
$env:CASH_API_KEY='temporary-local-demo-only'
$env:CASH_PRIVATE=Join-Path $PWD '.private/demo-jobs'
& .\scripts\start.ps1 -SyntheticTest -Port 8792
```

Open `http://127.0.0.1:8792`, enter that test value in the local UI and use only generated `.private/synthetic/safe.mov` or `positive.mov`. Synthetic outcomes are scripted fixtures for engineering demonstration; do not present them as learned detections or upload bank/jury files. Stop this foreground process with Ctrl+C. If the port is occupied, choose a free local port; do not stop another service or change firewall/security policy.

A separate owned launcher smoke reached synthetic health, rejected an unauthenticated upload and stopped its process tree. The existing synthetic service's health was also reachable. These are local health/auth checks, not public reachability or learned quality. The actual-model XCLIP research integration is documented separately and deliberately leaves types unverified; it must not be confused with this scripted fixture mode.

Real-model mode is not approved as a competition release. Keep the current semantic gates, source/evidence validity and public-access decisions explicit. Do not use the launcher without synthetic mode as a shortcut around the failed prerequisite.
