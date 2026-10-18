"""Presentation captures of the real research UI with generated geometric media.

All HTTP is fulfilled by this fixture in an offline, fresh browser context.
No service is opened and no model, bank media or saved result is read.
The only DOM addition is a permanent, explicit synthetic presentation label.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".private" / "presentation-ui"
BASE = "http://127.0.0.1:18779"
KEY = "temporary-presentation-fixture-only"
JOB = "f" * 32
SOURCES = (
    "static/research.html", "static/research.css",
    "static/research.js", "static/style.css",
)
SHOT_WIDTHS = {"empty-desktop.png": 1440, "candidate-desktop.png": 1440, "candidate-mobile.png": 390}
CHECK_NAMES = (
    "empty_state_from_current_ui", "empty-desktop_no_horizontal_overflow",
    "empty-desktop_label_visible_and_uncut", "three_generated_jpeg_frames_decoded",
    "timeline_seeks_generated_video", "context_control_plays_generated_video",
    "current_ui_has_unverified_type_and_rule_text", "actual_candidate_text_is_manual_review",
    "candidate-desktop_no_horizontal_overflow", "candidate-desktop_label_visible_and_uncut",
    "candidate-mobile_no_horizontal_overflow", "candidate-mobile_label_visible_and_uncut",
    "no_browser_storage_or_cookies", "source_files_unchanged",
)
LABEL = (
    "\u0421\u0418\u041d\u0422\u0415\u0422\u0418\u0427\u0415\u0421\u041a\u0418\u0419 "
    "\u041f\u0420\u0418\u041c\u0415\u0420 "
    "\u0418\u041d\u0422\u0415\u0420\u0424\u0415\u0419\u0421\u0410; "
    "\u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e "
    "\u0434\u0435\u0442\u0435\u043a\u0442\u043e\u0440\u0430 "
    "\u043d\u0435 \u0434\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0438\u0440\u0443\u0435\u0442\u0441\u044f"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def read_safe_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536, "invalid_safe_report_file")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(type(value) is dict, "invalid_safe_report_object")
    return value


def verify_artifact_hashes(pending: dict, root: Path, output: Path) -> dict:
    """Read only the fixed public UI sources and our three synthetic PNGs."""
    require(set(pending.get("source_sha256", {})) == set(SOURCES), "unexpected_source_inventory")
    for name in SOURCES:
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2097152, "invalid_source_file")
        require(digest(path) == pending["source_sha256"][name], "source_hash_mismatch")
    shots = pending.get("screenshots")
    require(type(shots) is list and len(shots) == 3, "invalid_screenshot_inventory")
    require({shot.get("file") for shot in shots} == set(SHOT_WIDTHS), "unexpected_screenshot_name")
    for shot in shots:
        require(set(shot) == {"file", "width_px", "height_px", "bytes", "sha256"}, "invalid_screenshot_metadata")
        path = output / shot["file"]
        require(path.is_file() and not path.is_symlink() and 24 <= path.stat().st_size <= 33554432, "invalid_screenshot_file")
        with path.open("rb") as stream:
            header = stream.read(24)
        require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", "invalid_png_header")
        dimensions = struct.unpack(">II", header[16:24])
        require(dimensions == (shot["width_px"], shot["height_px"]), "png_dimension_mismatch")
        require(dimensions[0] == SHOT_WIDTHS[shot["file"]] and 1 <= dimensions[1] <= 6000, "unexpected_png_dimensions")
        require(path.stat().st_size == shot["bytes"] and digest(path) == shot["sha256"], "png_hash_or_size_mismatch")
    return {"source_files_checked": 4, "synthetic_png_files_checked": 3, "all_hashes_and_png_headers_match": True}


def build_final_report(pending: dict, terminal: dict, status: dict, worker: dict, artifact_checks: dict) -> dict:
    """Pure decision: a worker's capture report alone can never authorize PASS."""
    require(pending.get("status") == "PENDING" and pending.get("capture_checks_passed") is True, "capture_not_pending_or_failed")
    require(set(pending.get("checks", {})) == set(CHECK_NAMES) and all(pending["checks"][name] is True for name in CHECK_NAMES), "capture_checks_failed")
    require(pending.get("page_errors") == 0 and pending.get("external_or_unexpected_requests") == 0, "browser_errors_or_requests")
    require(pending.get("fixture_request_counts") == {"static": 4, "fixture_post": 1, "fixture_poll": 2}, "unexpected_fixture_counts")
    for name in ("fresh_headless_edge_context", "gpu_rendering_disabled", "offline_context_with_all_http_intercepted", "all_media_generated_in_this_run", "synthetic_label_added_only_in_browser", "fixture_has_no_human_or_banking_action"):
        require(pending.get(name) is True, "synthetic_safety_check_failed")
    for name in ("server_opened", "bank_material_or_saved_result_opened", "model_inference_executed", "model_quality_tested", "actual_api_transport_tested"):
        require(pending.get(name) is False, "synthetic_scope_changed")
    require(terminal.get("status") == "completed" and terminal.get("reason") == "completed", "monitor_not_completed")
    require(terminal.get("worker_exit_code") == 0 and terminal.get("server_exit_code") in (None, 0), "worker_not_successful")
    for name in ("cleanup_complete", "worker_report_valid", "quality_gate_passed"):
        require(terminal.get(name) is True, "monitor_cleanup_or_report_not_valid")
    for name in ("deadline_exceeded", "stdout_collected", "raw_private_content_emitted"):
        require(terminal.get(name) is False, "monitor_budget_or_privacy_failed")
    require(all(terminal.get(name) == 3 for name in ("completed_cases", "passed_cases", "expected_cases")), "monitor_case_count_mismatch")
    elapsed = terminal.get("elapsed_sec")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 90 and terminal.get("budget_sec") == 90, "invalid_monitor_budget")
    require(status == {"status": "completed", "reason": "completed", "authority": "terminal-safe-summary.json"}, "status_authority_mismatch")
    require(worker.get("status") == "completed" and worker.get("failure") == "none" and worker.get("server_exit_code") in (None, 0), "worker_report_failed")
    require(all(worker.get(name) == 3 for name in ("completed_cases", "passed_cases", "total_cases")), "worker_report_case_count_mismatch")
    require(artifact_checks == {"source_files_checked": 4, "synthetic_png_files_checked": 3, "all_hashes_and_png_headers_match": True}, "artifact_verification_failed")
    result = dict(pending)
    result.update(status="PASS", owned_90_sec_monitor=terminal)
    result["authority"] = {"schema_version": 2, "terminal_cleanup_and_disk_reports_verified": True, **artifact_checks}
    return result


def revoke_and_fail(output: Path, writer, reason: str) -> dict:
    """Revoke first, including a PASS committed by a writer that then raises."""
    target = output / "safe-summary.json"
    target.unlink(missing_ok=True)
    failed = {"status": "FAIL", "reason": reason, "authority": {"schema_version": 2}, "raw_private_content_emitted": False}
    try:
        writer(target, failed)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return failed


def finalize_owned_report(root: Path, output: Path, controlled: Path, pending_path: Path, *, owned: bool, writer, returned_monitor=None) -> dict:
    """Only a run owner may publish/revoke; a rejected repeat preserves old output."""
    if not owned:
        raise PermissionError("report_finalization_requires_run_ownership")
    try:
        require(not (controlled / "emergency-safe-summary.json").exists(), "emergency_monitor_authority")
        pending = read_safe_json(pending_path)
        terminal = read_safe_json(controlled / "terminal-safe-summary.json")
        status = read_safe_json(controlled / "status.json")
        worker = read_safe_json(controlled / "worker-safe-summary.json")
        if returned_monitor is not None:
            require(terminal == returned_monitor, "returned_monitor_disk_mismatch")
        artifact_checks = verify_artifact_hashes(pending, root, output)
        result = build_final_report(pending, terminal, status, worker, artifact_checks)
        result["authority"].update({
            "control_directory": controlled.relative_to(output).as_posix(),
            "terminal_sha256": digest(controlled / "terminal-safe-summary.json"),
            "status_sha256": digest(controlled / "status.json"),
            "worker_report_sha256": digest(controlled / "worker-safe-summary.json"),
            "capture_pending_sha256": digest(pending_path),
        })
        writer(output / "safe-summary.json", result)
        return result
    except Exception:
        return revoke_and_fail(output, writer, "authority_validation_or_publication_failed")


def claim_run(run_directory: Path) -> None:
    """An existing run rejection occurs before any shared report mutation."""
    run_directory.parent.mkdir(parents=True, exist_ok=True)
    run_directory.mkdir(exist_ok=False)


def revalidate_legacy_capture() -> dict:
    """One explicit, local recovery of our already captured owned-run-01 files."""
    from cashreview.supervision import atomic_json
    controlled = OUT / "owned-run-01"
    # Exclusive recovery ownership. A second invocation cannot revoke a report.
    with (controlled / "report-revalidation-owner.json").open("x", encoding="ascii") as stream:
        json.dump({"scope": "existing_synthetic_capture_report_only", "browser_or_model_run": False}, stream)
    try:
        prior = read_safe_json(OUT / "safe-summary.json")
        prior.pop("owned_90_sec_monitor", None)
        prior.pop("authority", None)
        prior.update(status="PENDING", capture_checks_passed=prior.get("status") == "PASS")
        pending_path = controlled / "capture-pending-summary.json"
        atomic_json(pending_path, prior)
        atomic_json(OUT / "safe-summary.json", {"status": "PENDING", "authority": {"schema_version": 2}, "browser_or_model_run": False})
        result = finalize_owned_report(ROOT, OUT, controlled, pending_path, owned=True, writer=atomic_json)
        result["legacy_capture_revalidated_without_browser_or_model_run"] = True
        if result["status"] == "PASS":
            try:
                atomic_json(OUT / "safe-summary.json", result)
            except Exception:
                return revoke_and_fail(OUT, atomic_json, "revalidation_publication_failed")
        return result
    except Exception:
        return revoke_and_fail(OUT, atomic_json, "legacy_revalidation_failed")


def geometric_image(seconds: float):
    """This fixture has no human, cash, workstation or banking action."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (960, 540), "#163d35")
    draw = ImageDraw.Draw(image)
    for x in range(0, 960, 60):
        draw.line((x, 0, x, 540), fill="#214b41", width=1)
    for y in range(0, 540, 60):
        draw.line((0, y, 960, y), fill="#214b41", width=1)
    left = int(105 + seconds * 70)
    draw.rounded_rectangle((left, 210, left + 165, 375), 16, fill="#e9b95c")
    draw.ellipse((690, 225, 810, 345), fill="#b7d1b2")
    draw.rectangle((45, 45, 915, 122), fill="#102d27")
    draw.text((68, 68), "SYNTHETIC GEOMETRIC VIDEO - UI ONLY", fill="#ffffff", font_size=32)
    draw.text((46, 464), "Generated shapes | No detector inference | No banking event", fill="#d9e5d8", font_size=24)
    return image


def create_fixtures() -> tuple[Path, list[dict]]:
    import av
    OUT.mkdir(parents=True, exist_ok=True)
    movie = OUT / "synthetic-geometric-demo.mov"
    with av.open(str(movie), "w") as container:
        stream = container.add_stream("libx264", rate=12)
        stream.width = 960
        stream.height = 540
        stream.pix_fmt = "yuv420p"
        for index in range(72):
            frame = av.VideoFrame.from_image(geometric_image(index / 12))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    frames = []
    for second in (2.0, 3.0, 4.0):
        buffer = BytesIO()
        geometric_image(second).save(buffer, "JPEG", quality=94)
        frames.append({
            "timestamp_sec": second,
            "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        })
    return movie, frames


def main() -> int:
    from cashreview.supervision import await_start_gate, atomic_json
    controlled_directory, _ = await_start_gate()
    from PIL import Image
    from playwright.sync_api import expect, sync_playwright
    started = time.monotonic()
    source_hashes = {name: digest(ROOT / name) for name in SOURCES}
    movie, frames = create_fixtures()
    checks: dict[str, bool] = {}
    errors: list[str] = []
    blocked: list[str] = []
    route_counts = {"static": 0, "fixture_post": 0, "fixture_poll": 0}
    shots: list[dict] = []
    state = {"polls": 0}

    with sync_playwright() as playwright:
        atomic_json(OUT / "progress-safe-summary.json", {"phase": "launching_fresh_edge"})
        browser = playwright.chromium.launch(
            channel="msedge", headless=True, args=["--disable-gpu"], timeout=30000,
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=1, locale="ru-RU", reduced_motion="reduce",
            service_workers="block", offline=True,
        )

        def route(handler):
            request = handler.request
            parsed = urlsplit(request.url)
            if parsed.scheme in ("blob", "data"):
                handler.continue_()
                return
            if f"{parsed.scheme}://{parsed.netloc}" != BASE or parsed.query:
                blocked.append("non_fixture_origin_or_query")
                handler.abort()
                return
            path = parsed.path
            if path == "/":
                route_counts["static"] += 1
                handler.fulfill(path=str(ROOT / "static/research.html"), content_type="text/html; charset=utf-8")
                return
            if path in ("/static/style.css", "/static/research.css", "/static/research.js"):
                route_counts["static"] += 1
                content_type = "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8"
                handler.fulfill(path=str(ROOT / path.lstrip("/")), content_type=content_type)
                return
            if path == "/favicon.ico":
                handler.fulfill(status=204)
                return
            if request.headers.get("x-api-key") == KEY:
                if path == "/api/experimental/xclip/analyze" and request.method == "POST":
                    route_counts["fixture_post"] += 1
                    state["polls"] = 0
                    handler.fulfill(json={"job_id": JOB})
                    return
                if path == "/api/experimental/xclip/jobs/" + JOB and request.method == "GET":
                    route_counts["fixture_poll"] += 1
                    state["polls"] += 1
                    if state["polls"] == 1:
                        handler.fulfill(json={"job_id": JOB, "status": "processing"})
                        return
                    handler.fulfill(json={
                        "job_id": JOB, "status": "done", "mode": "xclip_experimental",
                        "binary_decision": "violation", "decision_margin": 0.2,
                        "threshold": 0.0, "event_type_status": "unverified",
                        "rule_application_status": "not_assessed", "release_eligible": False,
                        "duration_sec": 6.0, "elapsed_engine_sec": 0.1,
                        "candidate_timecode_sec": 3.0, "candidate_frames": frames,
                        "limitation": "Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.",
                    })
                    return
            blocked.append("unexpected_fixture_request")
            handler.abort()

        context.route("**/*", route)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(type(error).__name__))
        page.goto(BASE + "/", wait_until="networkidle")
        atomic_json(OUT / "progress-safe-summary.json", {"phase": "fixture_page_loaded"})
        page.evaluate("""label => {
            const banner = document.createElement('div');
            banner.id = 'synthetic-presentation-label';
            banner.textContent = label;
            banner.setAttribute('role', 'note');
            document.body.prepend(banner);
        }""", LABEL)
        page.add_style_tag(content="""
            body { padding-top: 60px; }
            #synthetic-presentation-label {
                position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
                min-height: 60px; padding: 17px 24px; background: #fff1c9;
                border-bottom: 2px solid #bb8b36; color: #553d15;
                font: 600 16px/1.5 'Segoe UI', sans-serif; text-align: center;
                box-shadow: 0 2px 10px #13271b16;
            }
            @media(max-width:800px) {
                body { padding-top: 112px; }
                #synthetic-presentation-label {
                    min-height: 112px; padding: 15px 16px; font-size: 14px;
                }
            }
        """)
        page.evaluate("document.fonts.ready")

        def capture(name: str, width: int, height: int) -> None:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("window.scrollTo(0, 0)")
            page.locator("#synthetic-presentation-label").wait_for(state="visible")
            expect(page.locator("#synthetic-presentation-label")).to_have_text(LABEL)
            checks[name + "_no_horizontal_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            checks[name + "_label_visible_and_uncut"] = page.locator("#synthetic-presentation-label").evaluate("e => { const r=e.getBoundingClientRect(); return r.top===0 && r.left===0 && r.right<=innerWidth && r.height>=60 && e.scrollHeight<=e.clientHeight; }")
            page.screenshot(path=str(OUT / (name + ".png")), full_page=True, animations="disabled")
            with Image.open(OUT / (name + ".png")) as image:
                dimensions = list(image.size)
            shots.append({
                "file": name + ".png", "width_px": dimensions[0], "height_px": dimensions[1],
                "bytes": (OUT / (name + ".png")).stat().st_size,
                "sha256": digest(OUT / (name + ".png")),
            })

        expect(page.locator("#empty")).to_be_visible()
        expect(page.locator("#workspace")).to_be_hidden()
        checks["empty_state_from_current_ui"] = True
        capture("empty-desktop", 1440, 1000)
        atomic_json(OUT / "progress-safe-summary.json", {"phase": "empty_captured"})
        page.locator("#access").click()
        page.locator("#key").fill(KEY)
        page.locator("#save-key").click()
        require(page.locator("#key").input_value() == "", "fixture_key_field_not_cleared")
        page.locator("#file").set_input_files(str(movie))
        page.locator("#submit").click()
        expect(page.locator("#workspace")).to_be_visible(timeout=15000)
        expect(page.locator("#frames img")).to_have_count(3)
        checks["three_generated_jpeg_frames_decoded"] = page.locator("#frames img").evaluate_all("xs => xs.every(x => x.complete && x.naturalWidth===960 && x.naturalHeight===540)")
        page.wait_for_function("document.getElementById('video').readyState >= 2")
        page.locator("#timeline button").click()
        page.wait_for_function("Math.abs(document.getElementById('video').currentTime-3) < .05 && !document.getElementById('video').seeking")
        checks["timeline_seeks_generated_video"] = True
        page.locator("#before").click()
        page.wait_for_function("document.getElementById('video').currentTime < .05")
        page.locator("#context").click()
        page.wait_for_function("document.getElementById('video').currentTime > .15")
        page.locator("#video").evaluate("v => v.pause()")
        checks["context_control_plays_generated_video"] = True
        page.locator("#timeline button").click()
        page.wait_for_function("Math.abs(document.getElementById('video').currentTime-3) < .05 && !document.getElementById('video').seeking")
        page.locator("#video").evaluate("v => v.pause()")
        checks["current_ui_has_unverified_type_and_rule_text"] = page.locator(".event").evaluate("e => e.textContent.includes('\u041d\u0435 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d') && e.textContent.includes('\u041d\u0435 \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d')")
        checks["actual_candidate_text_is_manual_review"] = page.locator("#verdict").evaluate("e => e.textContent === '\u0415\u0441\u0442\u044c \u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442 \u0434\u043b\u044f \u0440\u0443\u0447\u043d\u043e\u0439 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438'")
        capture("candidate-desktop", 1440, 1000)
        capture("candidate-mobile", 390, 844)
        atomic_json(OUT / "progress-safe-summary.json", {"phase": "three_captures_complete"})
        checks["no_browser_storage_or_cookies"] = page.evaluate("localStorage.length===0 && sessionStorage.length===0") and not context.cookies()
        checks["source_files_unchanged"] = source_hashes == {name: digest(ROOT / name) for name in SOURCES}
        browser.close()

    require(route_counts["fixture_post"] == 1 and route_counts["fixture_poll"] == 2, "unexpected_fixture_roundtrip_count")
    result = {
        "status": "PENDING", "capture_checks_passed": all(checks.values()) and not errors and not blocked,
        "checks": checks, "screenshots": shots, "source_sha256": source_hashes,
        "page_errors": len(errors), "external_or_unexpected_requests": len(blocked),
        "fixture_request_counts": route_counts,
        "fresh_headless_edge_context": True, "gpu_rendering_disabled": True,
        "offline_context_with_all_http_intercepted": True,
        "server_opened": False, "bank_material_or_saved_result_opened": False,
        "all_media_generated_in_this_run": True,
        "synthetic_label_added_only_in_browser": True,
        "fixture_has_no_human_or_banking_action": True,
        "model_inference_executed": False, "model_quality_tested": False,
        "actual_api_transport_tested": False,
        "elapsed_sec": round(time.monotonic() - started, 3),
    }
    atomic_json(controlled_directory / "capture-pending-summary.json", result)
    atomic_json(controlled_directory / "worker-safe-summary.json", {
        "status": "completed" if result["capture_checks_passed"] else "failed",
        "completed_cases": 3, "passed_cases": 3 if result["capture_checks_passed"] else 0,
        "total_cases": 3, "failure": "none" if result["capture_checks_passed"] else "exception",
    })
    return int(not result["capture_checks_passed"])


if __name__ == "__main__":
    owned = False
    try:
        sys.path.insert(0, str(ROOT))
        if sys.argv[1:] == ["--worker"]:
            sys.exit(main())
        if sys.argv[1:] == ["--revalidate-existing"]:
            result = revalidate_legacy_capture()
            print(json.dumps(result))
            sys.exit(int(result["status"] != "PASS"))
        require(not sys.argv[1:], "unsupported_arguments")
        from cashreview.supervision import supervise, atomic_json
        run_directory = OUT / "owned-run-02"
        claim_run(run_directory)
        owned = True
        atomic_json(OUT / "safe-summary.json", {"status": "PENDING", "authority": {"schema_version": 2}})
        controlled = run_directory / "monitor"
        monitor = supervise(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            controlled, budget_sec=90, expected_cases=3, cwd=ROOT,
        )
        result = finalize_owned_report(ROOT, OUT, controlled, controlled / "capture-pending-summary.json", owned=True, writer=atomic_json, returned_monitor=monitor)
        print(json.dumps(result))
        sys.exit(int(result["status"] != "PASS"))
    except Exception as error:
        revoked = False
        if owned:
            try:
                revoke_and_fail(OUT, atomic_json, "owned_controller_exception")
                revoked = True
            except Exception:
                revoked = not (OUT / "safe-summary.json").exists()
        print(json.dumps({"status": "FAIL", "technical_error_type": type(error).__name__, "owned_report_revoked": revoked, "nonowner_report_unchanged": not owned, "raw_content_emitted": False}))
        sys.exit(1)
