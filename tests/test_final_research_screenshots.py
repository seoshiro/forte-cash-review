"""Pure synthetic finalization regressions. No browser, GPU or service is used."""
import copy
import json
import struct
from pathlib import Path

import pytest

from scripts import final_research_screenshots as capture


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def valid_capture(tmp_path):
    root, output = tmp_path / "public-code", tmp_path / "synthetic-output"
    output.mkdir()
    controlled = output / "owned-run-test"
    controlled.mkdir()
    pending = {
        "status": "PENDING", "capture_checks_passed": True,
        "checks": {name: True for name in capture.CHECK_NAMES},
        "page_errors": 0, "external_or_unexpected_requests": 0,
        "fixture_request_counts": {"static": 4, "fixture_post": 1, "fixture_poll": 2},
        "source_sha256": {}, "screenshots": [],
    }
    for name in ("fresh_headless_edge_context", "gpu_rendering_disabled", "offline_context_with_all_http_intercepted", "all_media_generated_in_this_run", "synthetic_label_added_only_in_browser", "fixture_has_no_human_or_banking_action"):
        pending[name] = True
    for name in ("server_opened", "bank_material_or_saved_result_opened", "model_inference_executed", "model_quality_tested", "actual_api_transport_tested"):
        pending[name] = False
    for name in capture.SOURCES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic public source " + name, encoding="ascii")
        pending["source_sha256"][name] = capture.digest(path)
    for name, width in capture.SHOT_WIDTHS.items():
        path = output / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", width, 1000))
        pending["screenshots"].append({"file": name, "width_px": width, "height_px": 1000, "bytes": path.stat().st_size, "sha256": capture.digest(path)})
    terminal = {
        "status": "completed", "reason": "completed", "worker_exit_code": 0,
        "server_exit_code": None, "completed_cases": 3, "passed_cases": 3,
        "expected_cases": 3, "quality_gate_passed": True, "budget_sec": 90,
        "deadline_exceeded": False, "cleanup_complete": True, "worker_report_valid": True,
        "stdout_collected": False, "raw_private_content_emitted": False, "elapsed_sec": 6.7,
    }
    status = {"status": "completed", "reason": "completed", "authority": "terminal-safe-summary.json"}
    worker = {"status": "completed", "completed_cases": 3, "passed_cases": 3, "total_cases": 3, "failure": "none"}
    pending_path = controlled / "capture-pending-summary.json"
    write_json(pending_path, pending)
    write_json(controlled / "terminal-safe-summary.json", terminal)
    write_json(controlled / "status.json", status)
    write_json(controlled / "worker-safe-summary.json", worker)
    write_json(output / "safe-summary.json", {"status": "PASS", "old_report": True})
    return root, output, controlled, pending_path, pending, terminal, status, worker


def finalize(fixture, **kwargs):
    root, output, controlled, pending_path, *_ = fixture
    return capture.finalize_owned_report(root, output, controlled, pending_path, owned=True, writer=write_json, **kwargs)


def test_pass_requires_disk_authority_and_verified_artifacts(valid_capture):
    result = finalize(valid_capture, returned_monitor=valid_capture[5])
    assert result["status"] == "PASS"
    assert result["authority"]["terminal_cleanup_and_disk_reports_verified"] is True
    assert result["authority"]["source_files_checked"] == 4
    assert result["authority"]["synthetic_png_files_checked"] == 3
    assert result["authority"]["terminal_sha256"] == capture.digest(valid_capture[2] / "terminal-safe-summary.json")
    assert capture.read_safe_json(valid_capture[1] / "safe-summary.json") == result


@pytest.mark.parametrize("field,value", [("cleanup_complete", False), ("deadline_exceeded", True), ("worker_exit_code", 1), ("worker_report_valid", False), ("elapsed_sec", 91)])
def test_failed_monitor_revokes_prior_pass(valid_capture, field, value):
    terminal = dict(valid_capture[5], **{field: value})
    write_json(valid_capture[2] / "terminal-safe-summary.json", terminal)
    assert finalize(valid_capture)["status"] == "FAIL"
    assert capture.read_safe_json(valid_capture[1] / "safe-summary.json")["status"] == "FAIL"


@pytest.mark.parametrize("name", ["terminal-safe-summary.json", "status.json", "worker-safe-summary.json"])
def test_missing_authority_report_revokes_prior_pass(valid_capture, name):
    (valid_capture[2] / name).unlink()
    assert finalize(valid_capture)["status"] == "FAIL"
    assert capture.read_safe_json(valid_capture[1] / "safe-summary.json")["status"] == "FAIL"


def test_returned_monitor_cannot_override_different_disk_terminal(valid_capture):
    returned = dict(valid_capture[5], elapsed_sec=5.0)
    assert finalize(valid_capture, returned_monitor=returned)["status"] == "FAIL"


def test_emergency_authority_rejects_normal_terminal(valid_capture):
    write_json(valid_capture[2] / "emergency-safe-summary.json", {"status": "failed"})
    assert finalize(valid_capture)["status"] == "FAIL"


@pytest.mark.parametrize("artifact", ["source", "png"])
def test_changed_source_or_png_revokes_pass(valid_capture, artifact):
    target = valid_capture[0] / capture.SOURCES[0] if artifact == "source" else valid_capture[1] / "empty-desktop.png"
    target.write_bytes(target.read_bytes() + b"changed")
    assert finalize(valid_capture)["status"] == "FAIL"


def test_worker_pending_alone_never_publishes_pass(valid_capture):
    pending = dict(valid_capture[4], status="PASS")
    write_json(valid_capture[3], pending)
    assert finalize(valid_capture)["status"] == "FAIL"


def test_late_pass_write_failure_revokes_committed_pass(valid_capture):
    def fail_after_pass_replace(path, value):
        write_json(path, value)
        if value["status"] == "PASS":
            raise OSError("synthetic post-replace write failure")
    result = capture.finalize_owned_report(*valid_capture[:4], owned=True, writer=fail_after_pass_replace)
    assert result["status"] == "FAIL"
    assert capture.read_safe_json(valid_capture[1] / "safe-summary.json")["status"] == "FAIL"


def test_pass_and_failure_write_errors_leave_no_stale_pass(valid_capture):
    def fail_after_every_replace(path, value):
        write_json(path, value)
        raise OSError("synthetic write failure")
    with pytest.raises(OSError):
        capture.finalize_owned_report(*valid_capture[:4], owned=True, writer=fail_after_every_replace)
    assert not (valid_capture[1] / "safe-summary.json").exists()


def test_nonowner_cannot_revoke_previous_report(valid_capture):
    target = valid_capture[1] / "safe-summary.json"
    original = target.read_bytes()
    with pytest.raises(PermissionError):
        capture.finalize_owned_report(*valid_capture[:4], owned=False, writer=write_json)
    assert target.read_bytes() == original


def test_rejected_existing_run_claim_preserves_prior_report(valid_capture):
    target = valid_capture[1] / "safe-summary.json"
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        capture.claim_run(valid_capture[2])
    assert target.read_bytes() == original


def test_fresh_checkout_claim_creates_missing_parent_exclusively(tmp_path):
    output = tmp_path / "fresh-checkout" / ".private" / "presentation-ui"
    run_directory = output / "owned-run-02"
    assert not output.exists()
    capture.claim_run(run_directory)
    assert run_directory.is_dir()
    assert not (output / "safe-summary.json").exists()
    with pytest.raises(FileExistsError):
        capture.claim_run(run_directory)
    assert not (output / "safe-summary.json").exists()


def test_rejected_revalidation_repeat_preserves_prior_report(valid_capture, monkeypatch):
    output = valid_capture[1]
    controlled = output / "owned-run-01"
    controlled.mkdir()
    write_json(controlled / "report-revalidation-owner.json", {"already_owned": True})
    original = (output / "safe-summary.json").read_bytes()
    monkeypatch.setattr(capture, "OUT", output)
    with pytest.raises(FileExistsError):
        capture.revalidate_legacy_capture()
    assert (output / "safe-summary.json").read_bytes() == original


def test_pure_decision_does_not_mutate_pending(valid_capture):
    before = copy.deepcopy(valid_capture[4])
    checks = {"source_files_checked": 4, "synthetic_png_files_checked": 3, "all_hashes_and_png_headers_match": True}
    result = capture.build_final_report(valid_capture[4], *valid_capture[5:], checks)
    assert result["status"] == "PASS"
    assert valid_capture[4] == before
