from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
import stackchan_bridge
import stackchan_bridge.cli as bridge_cli
import stackchan_bridge.mcp_server.cli as mcp_cli
from stackchan_bridge.config import BridgeSettings
from stackchan_bridge.doctor import (
    CheckStatus,
    faster_whisper_model_is_cached,
    firmware_backup_is_verified,
    inspect_host,
)
from stackchan_bridge.security.tokens import verify_device_token

ROOT = Path(__file__).resolve().parents[2]


def test_private_capture_output_ignore_does_not_hide_the_capture_source_package() -> None:
    def ignored(path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode in {0, 1}
        return result.returncode == 0

    assert ignored("captures/private.jpg")
    assert not ignored("bridge/src/stackchan_bridge/captures/store.py")


def test_documentation_register_is_complete_and_current() -> None:
    required_documents = (
        "requirements.md",
        "architecture.md",
        "protocol-v1.md",
        "state-machines.md",
        "security.md",
        "operations.md",
        "hardware-setup.md",
        "hardware-test-report.md",
        "verification-report.md",
        "traceability.md",
        "upstream-baseline.md",
        "progress.md",
        "implementation-plan.md",
    )
    for filename in required_documents:
        assert (ROOT / "docs" / filename).is_file(), filename

    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirement_ids = re.findall(r"^## ([A-Z]+-\d{3}) —", requirements, re.MULTILINE)
    traced_ids = re.findall(r"^\| ([A-Z]+-\d{3}) \|", traceability, re.MULTILINE)

    assert len(requirement_ids) == 27
    assert len(requirement_ids) == len(set(requirement_ids))
    assert traced_ids == requirement_ids

    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    stale_claim = "Phase 3\u201312 implementation and requirement promotion remain necessary"
    assert stale_claim not in verification


def test_hardware_documents_match_the_latest_attended_body_evidence() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")

    assert "HW-05 reconnect presentation is PASS" in hardware_setup
    assert "brightness and dim-blue LEDs are physically confirmed" in hardware_setup
    assert "the happy expression is physically confirmed" in hardware_setup
    assert "the happy expression remained absent" not in hardware_setup
    assert (
        "Touch, reconnect presentation and acknowledged safe-command effects remain unverified."
        not in hardware_setup
    )
    assert "Date | 2026-09-01 (Asia/Tokyo)" in hardware_report
    assert "build-hermes-expression-bd49497/stack-chan.bin" in hardware_report
    candidate_row = next(
        line for line in hardware_report.splitlines() if "| Retained expression candidate |" in line
    )
    assert re.search(r"SHA-256 `[0-9a-f]{64}`", candidate_row)
    assert "physically flashed and digest-verified" in candidate_row
    assert re.search(r"operator independently\s+saw the happy eyes", hardware_report)
    assert "expression physically Green" in progress


def test_hardware_documents_record_corrected_fixed_japanese_audio_output() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    assert "HW-06 audio output is PASS" in hardware_setup
    assert "SAFE CHECKPOINT — HW-01 through HW-13 PASS" in hardware_report
    assert "| HW-06 Audio output | **PASS** |" in hardware_report
    audio_sha256 = (
        "ffb45d626fcbf1c15058dd839658fd27"  # pragma: allowlist secret
        "535b64d8a9dea5ce226e526975346148"  # pragma: allowlist secret
    )
    assert audio_sha256 in hardware_report
    assert "Windows PowerShell 5.1" in hardware_report
    assert "BOM-less UTF-8" in hardware_report
    assert "confidence `0.9625`" in hardware_report
    assert "30 Opus frames" in hardware_report
    assert "properly audible" in hardware_report
    assert "physical speaker path untested" not in hardware_report
    assert "HW-06 audio output is PASS" in verification
    assert "HW-06 PASS" in progress
    assert "fixed Japanese audio output Green" in traceability
    assert "HW-09 live Hermes Responses API is PASS" in requirements
    assert "Complete (HW-06 audio output, 2026-09-01)" in implementation_plan


def test_hardware_documents_record_the_no_touch_input_safety_finding() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    firmware_tests = (ROOT / "firmware" / "tests" / "README.md").read_text(encoding="utf-8")

    assert "no-touch volume comparison" in hardware_setup
    assert "## No-touch volume comparison and input-safety finding" in hardware_report
    assert "operator confirmed touching nothing" in hardware_report
    assert "`audio.input.start` / `audio.input.end`" in hardware_report
    assert (
        "No incoming audio content was saved, printed, transcribed or analyzed." in hardware_report
    )
    assert "At the time, this was not HW-07 acceptance" in hardware_report
    assert "`HeadTouchDebouncer`" in progress
    assert "no-touch regression is physically Green" in progress
    assert "stable touch did not emit a press" in verification
    firmware_sha256 = (
        "f35c24a94d20860d0a70997382803592"  # pragma: allowlist secret
        "0997e38b1ed934a6d1fbbf3bcc54e43d"  # pragma: allowlist secret
    )
    assert firmware_sha256 in verification
    assert "20 Firmware CTest" in traceability
    assert "no-touch false activation correction is physically Green" in requirements
    assert "Twenty-four host C++ tests" in implementation_plan
    assert "24 host C++ tests" in requirements
    assert "24 CTest targets" in firmware_tests


def test_hardware_documents_record_the_retained_head_touch_candidate() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    firmware_readme = (ROOT / "firmware" / "README.md").read_text(encoding="utf-8")

    candidate_path = "firmware/build-hermes-head-touch-fffaba3/stack-chan.bin"
    candidate_sha256 = (
        "cf122cd787fae325e38ba3caa2b743e2"  # pragma: allowlist secret
        "c4386559d2e46f94e93333d69f8e4551"  # pragma: allowlist secret
    )
    assert candidate_path in hardware_report
    assert candidate_path in verification
    assert candidate_path in progress
    assert candidate_sha256 in hardware_report
    assert candidate_sha256 in verification
    assert candidate_sha256 in progress
    assert "source HEAD `fffaba3`" in verification
    assert "`0x20000 stack-chan.bin` only" in verification
    assert "19 host C++ tests" in firmware_readme


def test_hardware_documents_record_confirmed_volume_and_app_preflight() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    confirmation = "second volume-85 play was clearly louder"
    assert confirmation in hardware_report
    assert confirmation in verification
    assert confirmation in progress
    assert "current expression app still matched" in hardware_report
    assert "current expression app still matched" in verification
    assert "app-only flash remains unapproved" not in hardware_report
    assert "comparative volume Green" in traceability


def test_hardware_documents_record_the_verified_head_touch_app_flash() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    assert "app-only flash was explicitly approved" in hardware_report
    assert "`verify OK (digest matched)`" in hardware_report
    assert "12,679 bytes" in hardware_report
    assert "`verify OK (digest matched)`" in verification
    assert "12,679 bytes" in verification
    assert "physically flashed and digest-verified" in progress
    assert "no-touch regression is physically Green" in progress
    assert "correction flashed / no-touch regression Green" in traceability
    assert "app-only flash is digest-verified" in hardware_setup


def test_hardware_documents_record_the_green_no_touch_regression() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    operator_confirmation = "operator confirmed touching neither the device, desk nor cable"
    zero_evidence = (
        "audio-input start/end, frames, discarded bytes and device events all remained zero"
    )
    for document in (hardware_report, verification, progress):
        assert "60.03 seconds" in document
        assert operator_confirmation in document
        assert zero_evidence in document
    assert "60.03-second attended no-touch regression is physically Green" in hardware_setup
    assert "`quiet=true`" in hardware_report
    assert "no audio content was received" in hardware_report
    assert "correction flashed / no-touch regression Green" in traceability
    assert "no-touch false activation correction is physically Green" in requirements
    assert "separately consented deliberate touch" in implementation_plan


def test_hardware_documents_record_the_green_deliberate_touch_observation() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    operator_confirmation = (
        "operator confirmed one approximately one-second touch/release and no speech"
    )
    lifecycle_evidence = "25 Opus frames and 3,617 bytes were counted and immediately discarded"
    for document in (hardware_report, verification, progress):
        assert "51.11 seconds" in document
        assert operator_confirmation in document
        assert lifecycle_evidence in document
    assert "HW-02 boot is PASS" in hardware_setup
    assert "## Verified deliberate-touch observation after correction" in hardware_report
    assert "`single_touch_green=true`" in hardware_report
    assert "one `touch` start and one `silence` end" in hardware_report
    assert (
        "No audio content was saved, printed, replayed, transcribed or analyzed." in hardware_report
    )
    assert "HW-02 Boot | **PASS**" in hardware_report
    assert "HW-07 Audio input | **PASS**" in hardware_report
    assert "deliberate direct touch-to-audio lifecycle Green" in traceability
    assert "physical `touch_events_total` increase remains pending" in traceability
    assert "HW-09 live Hermes Responses API is PASS" in requirements
    assert "Complete (HW-02 deliberate touch, 2026-09-01)" in implementation_plan


def test_hardware_documents_record_verified_physical_audio_input() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    operator_confirmation = (
        "operator confirmed approximately 20 seconds of touch, no speech and a final release"
    )
    for document in (hardware_report, verification, progress):
        assert "68 Opus frames / 9,946 bytes" in document
        assert "248 Opus frames / 36,329 bytes" in document
        assert "4.08 seconds" in document
        assert "14.88 seconds" in document
        assert "SNR 24.1991 dB" in document
        assert "400 ms" in document
        assert operator_confirmation in document
        assert "wav_deleted=true" in document
        assert "private_files_remaining=0" in document
        assert "hw07_green=true" in document
    assert "## Verified HW-07 physical audio input" in hardware_report
    assert "mode `0600`" in hardware_report
    assert "no replay, transcription, external service, cloud service or Hermes" in hardware_report
    assert "| HW-07 Audio input | **PASS** |" in hardware_report
    assert "| HW-08 STT | **PASS** |" in hardware_report
    assert "| HW-09 Hermes | **PASS** |" in hardware_report
    assert "| HW-10 Full voice turn | **PASS** |" in hardware_report
    assert "| HW-13 Failure handling | **PASS** |" in hardware_report
    assert "HW-07 physical audio input is PASS" in hardware_setup
    assert "Host, physical audio paths, live local STT and full voice Green" in traceability
    assert "physical audio input and output" in requirements
    assert "HW-09 live Hermes Responses API is PASS" in requirements
    assert "Complete (HW-07 physical audio input, 2026-09-01)" in implementation_plan


def test_hardware_documents_record_verified_physical_cancellation() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    candidate_path = "firmware/build-hermes-hw11-e824ef4/stack-chan.bin"
    candidate_sha256 = (
        "6167fec5380d78fbc6026d6a931169e"  # pragma: allowlist secret
        "1f39d0dd5eef12a9897a84f393860cfec"  # pragma: allowlist secret
    )
    for document in (hardware_report, verification, progress):
        assert candidate_path in document
        assert candidate_sha256 in document
        assert "source commit `e824ef4`" in document
    assert "HW-11 physical cancellation is PASS" in hardware_setup
    assert "## Verified HW-11 physical cancellation" in hardware_report
    assert "| HW-11 Cancel | **PASS** |" in hardware_report
    assert "first 30-frame 880 Hz stream" in hardware_report
    assert "second distinct 20-frame 880 Hz stream" in hardware_report
    assert "cancel latency was 1279.7 ms" in hardware_report
    assert "short first beep followed by a longer second beep" in hardware_report
    assert "audio_underrun_events=0" in hardware_report
    assert "audio_overflow_events=0" in hardware_report
    assert "operator touched neither the device, desk nor cable" in hardware_report
    assert "isolated 440 Hz" in hardware_report
    assert "44 input frames" in hardware_report
    assert "not accepted as HW-11 evidence" in hardware_report
    for document in (hardware_report, verification, progress):
        assert "historical intermittent no-contact input-safety finding" in document
    assert "20/20 Firmware CTest" in verification
    assert "363 tests passed" in verification
    assert "363 tests passed" in progress
    assert "HW-11 PASS" in progress
    assert "physical cancellation/new-turn Green" in traceability
    assert "HW-11/HW-12/HW-13 PASS" in requirements
    assert "Complete (HW-11 physical cancel, 2026-09-01)" in implementation_plan


def test_hardware_documents_record_green_bounded_no_contact_input_safety_followup() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    for document in (
        hardware_setup,
        hardware_report,
        verification,
        progress,
        requirements,
        implementation_plan,
    ):
        assert "bounded silent/440/880 comparison" in document

    operator_confirmation = (
        "operator heard two separated 880 Hz tones and confirmed touching neither the device, "
        "desk nor cable"
    )
    zero_input_evidence = "input starts, frames and ends all remained zero"
    for document in (hardware_report, verification, progress):
        assert "six 1.2-second, 20-frame phases" in document
        assert zero_input_evidence in document
        assert operator_confirmation in document
        assert "historical intermittent no-contact input-safety finding" in document
        assert "not reproduced in this bounded comparison" in document

    assert "## Verified bounded no-contact silent/440/880 comparison" in hardware_report
    assert "silent_a → 440_a → 880_a → silent_b → 880_b → 440_b" in hardware_report
    assert "touch_event_count=0" in hardware_report
    assert "no incoming audio content existed to retain or process" in hardware_report
    assert "input-safety follow-up Green" in traceability
    assert (
        "Complete (bounded no-contact input-safety comparison, 2026-09-01)" in implementation_plan
    )
    assert "remains a separate unresolved no-contact input-safety finding" not in progress


def test_hardware_documents_record_the_completed_firewall_lifecycle() -> None:
    operations = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")

    assert "retained until final Goal cleanup" in operations
    assert 'Remove-NetFirewallHyperVRule -Name "StackChanHermesBridge8765"' in operations
    for document in (hardware_report, verification, progress):
        assert "Final Goal cleanup is complete" in document
        assert "`StackChanHermesBridge8765` rules=0" in document
    assert "remove that exact name when the run ends" not in operations
    for document in (hardware_report, verification, progress):
        assert "no listener on 8765/8766" in document

    assert "removed after each" not in hardware_report
    assert "removed after each" not in progress


def test_hardware_documents_record_the_failed_hw12_diagnostic_and_followup() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    candidate_path = "firmware/build-hermes-hw12-8bfc589/stack-chan.bin"
    candidate_sha256 = (
        "319006f5c9aa0ed06eb2de906c3da43"  # pragma: allowlist secret
        "a1aa022c9606789e816b0044124d6cd60"  # pragma: allowlist secret
    )
    privacy_boundary = "No image was displayed, viewed, externally processed or retained."

    for document in (hardware_report, verification, progress):
        assert candidate_path in document
        assert candidate_sha256 in document
        assert "source commit `8bfc589`" in document
        assert "12,627 bytes" in document
        assert "`COMMAND_TIMEOUT`" in document
        assert "`CAPTURE_TIMEOUT`" in document
        assert privacy_boundary in document
        assert "HW-12 remains NOT RUN" in document
        assert "369 tests passed" in document
        assert "85.26%" in document

    for document in (hardware_report, verification, progress, traceability, implementation_plan):
        assert "`517011a`" in document
        assert "`camera.completed(ok=false)`" in document
        assert "`CAPTURE_FAILED`" in document

    assert "## Failed HW-12 camera diagnostic" in hardware_report
    assert "| HW-12 Camera | **PASS** |" in hardware_report


def test_hardware_documents_record_the_second_failed_hw12_diagnostic() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    diagnostic_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in diagnostic_documents:
        assert "`device_reconnected_or_disconnected`" in document
        assert "`f6f0d2d`" in document
        assert "does not prove stack exhaustion" in document
        assert "HW-12 remains NOT RUN" in document

    for document in (hardware_report, verification, progress):
        assert "45,227 ms" in document
        assert "`capture_completed_events=0`" in document
        assert "3,072-byte" in document
        assert "12 KiB" in document
        assert privacy_boundary in document

    assert "371 tests passed" in verification
    assert "85.20%" in verification
    assert "3,919,712 bytes" in verification
    verification_sha256 = (
        "31a000e291428d17b746b07747ae7858e"  # pragma: allowlist secret
        "89c6ab026b7ba1c3075dff4f04dd581"  # pragma: allowlist secret
    )
    assert verification_sha256 in verification


def test_hardware_documents_record_the_scoped_stack_candidate_flash() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    candidate_path = "firmware/build-hermes-hw12-stack-64062cd/stack-chan.bin"
    candidate_sha256 = (
        "f984c5181a48a3cf86a97f9cac59c058"  # pragma: allowlist secret
        "4d7c4eeb8a4ad8b81226c972f0cf92a6"  # pragma: allowlist secret
    )
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert candidate_path in document
        assert "source commit `64062cd`" in document
        assert "`f6f0d2d`" in document
        assert "16,037 bytes" in document
        assert "HW-12 remains NOT RUN" in document
        assert "fresh explicit camera consent" in document

    for document in (hardware_report, verification, progress):
        assert candidate_sha256 in document
        assert "3,919,712 bytes" in document
        assert "`0x20000`" in document
        assert "independent read-only digest" in document
        assert "panic/watchdog/assert" in document

    current_image_row = next(
        line for line in hardware_report.splitlines() if "| Current flashed image |" in line
    )
    assert "firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin" in current_image_row
    assert "app-only write" in current_image_row
    assert "attended Wi-Fi diagnostic disabled" in current_image_row
    for document in (verification, progress):
        assert "373 tests passed" in document
        assert "30.01 seconds" in document


def test_hardware_documents_record_the_post_stack_hw12_diagnostic() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "post-stack diagnostic" in document
        assert "45,091 ms" in document
        assert "`device_reconnected_or_disconnected`" in document
        assert "12 KiB mitigation did not resolve the physical failure" in document
        assert "HW-12 remains NOT RUN" in document
        assert privacy_boundary in document

    for document in (hardware_report, verification, progress):
        assert "exactly one camera command" in document
        assert "no automatic retry" in document
        assert "`capture_completed_events=0`" in document
        assert "`connection_stable=false`" in document
        assert "zero owned capture media" in document
        assert "374 tests passed" in document
        assert "28.12 seconds" in document
        assert "85.20%" in document


def test_hardware_documents_record_the_content_free_serial_hw12_diagnostic() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "content-free serial diagnostic" in document
        assert "`panic_observed`" in document
        assert "45,016 ms" in document
        assert "panic before the existing frame-copy marker" in document
        assert "does not identify the exact panic site" in document
        assert "HW-12 remains NOT RUN" in document
        assert privacy_boundary in document

    for document in (hardware_report, verification, progress):
        assert "exactly one camera command" in document
        assert "no automatic retry" in document
        assert "`serial_panic_markers=2`" in document
        assert "`serial_boot_markers=1`" in document
        assert "`serial_reset_markers=1`" in document
        assert "`serial_camera_frame_markers=0`" in document
        assert "`serial_camera_error_markers=0`" in document
        assert "`serial_brownout_markers=0`" in document
        assert "`serial_watchdog_markers=0`" in document
        assert "`serial_stack_markers=0`" in document
        assert "`serial_heap_markers=0`" in document
        assert "zero owned capture media" in document
        assert "375 tests passed" in document
        assert "28.01 seconds" in document
        assert "85.20%" in document


def test_hardware_documents_record_the_content_free_backtrace_hw12_diagnostic() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "content-free backtrace diagnostic" in document
        assert "`shutter_audio_path`" in document
        assert "45,020 ms" in document
        assert "nine bounded code addresses" in document
        assert "does not identify the exact faulting instruction" in document
        assert "HW-12 remains NOT RUN" in document
        assert privacy_boundary in document

    for document in (hardware_report, verification, progress):
        assert "exactly one camera command" in document
        assert "no automatic retry" in document
        assert "`serial_backtrace_addresses=9`" in document
        assert "`serial_panic_markers=2`" in document
        assert "`serial_boot_markers=1`" in document
        assert "`serial_reset_markers=1`" in document
        assert "`serial_camera_frame_markers=0`" in document
        assert "`serial_camera_error_markers=0`" in document
        assert "13,726 serial bytes" in document
        assert "zero owned capture media" in document
        assert "exact addresses, raw symbols or raw serial" in document
        assert "376 tests passed" in document
        assert "30.29 seconds" in document
        assert "85.26%" in document


def test_hardware_documents_record_the_main_task_shutter_audio_candidate_and_flash() -> None:
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "main-task shutter-audio correction" in document
        assert "`8ad0489`" in document
        assert "no camera command" in document
        assert "fresh explicit camera consent" in document
        assert "HW-12 remains NOT RUN" in document
        assert privacy_boundary in document

    for document in (hardware_report, verification, progress):
        assert "`firmware/build-hermes-hw12-shutter-8ad0489/stack-chan.bin`" in document
        assert "3,919,968 bytes" in document
        assert "`8b55b48a84e71820456dee68d16a2e73a7eb5ab836a8a3e8bd0638fe4686e296`" in document
        assert "`0x20000`-only" in document
        assert "independent read-only digest" in document
        assert "three consecutive clean boot" in document
        assert "one transient FreeRTOS stack-overflow" in document
        assert "did not reproduce" in document
        assert "377 tests passed" in document
        assert "30.88 seconds" in document
        assert "85.26%" in document
        assert "378 tests passed" in document
        assert "31.48 seconds" in document


def test_hardware_documents_record_the_successful_post_correction_hw12_capture() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    privacy_boundary = "No image was displayed, viewed, externally processed or retained."
    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "successful post-correction HW-12 capture" in document
        assert "exactly one camera command" in document
        assert "no automatic retry" in document
        assert "`local_capture_green=true`" in document
        assert "`machine_valid=true`" in document
        assert "`serial_camera_frame_markers=1`" in document
        assert "shutter sound was not heard" in document
        assert "no screen change was seen" in document
        assert privacy_boundary in document

    for document in (hardware_report, verification, progress):
        assert "HTTP `201` / `200` / `404`" in document
        assert "`capture_completed_events=1`" in document
        assert "`capture_failure_total=0.0`" in document
        assert "320 x 240" in document
        assert "directory mode `0700`" in document
        assert "file mode `0600`" in document
        assert "`files_remaining=0`" in document
        assert "227 serial bytes" in document
        assert (
            "zero panic, watchdog, stack, heap, brownout, reset and disconnect markers" in document
        )
        assert "no listener on 8765/8766" in document
        assert "379 tests passed" in document
        assert "31.94 seconds" in document
        assert "85.20%" in document

    assert "| HW-12 Camera | **PASS** |" in hardware_report
    assert "HW-12 physical camera capture is PASS" in hardware_setup
    assert "camera capture remain unverified" not in hardware_setup
    assert "physical camera lifecycle Green" in requirements
    assert "CAM-002 live physical vision turn is PASS" in requirements
    assert "HW-12 camera PASS" in traceability
    assert "Complete (HW-12 camera, 2026-09-02)" in implementation_plan


def test_hardware_documents_record_successful_hw13_wrong_token_recovery() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "successful HW-13 wrong-token recovery" in document
        assert "`wrong_auth_failures=5.0`" in document
        assert "`wrong_phase_registered=false`" in document
        assert "`recovery_elapsed_ms=26890`" in document
        assert "`final_state_idle=true`" in document
        assert "`Connecting Bridge`" in document
        assert "`Bridge connected`" in document
        assert "no camera, audio or actuator command" in document
        assert "No token or raw serial was displayed or retained in host evidence." in document

    for document in (hardware_report, verification, progress):
        assert "`status_commands=2`" in document
        assert "1,066 serial bytes" in document
        assert "zero boot, panic, watchdog, stack, heap, brownout and reset markers" in document
        assert "zero input, touch, queue and device-error events" in document
        assert "no listener on 8765/8766" in document
        assert "USB attached" in document
        assert "scoped firewall rule retained" in document
        assert "HW-13 evidence host gate" in document
        assert "380 tests passed" in document
        assert "32.06 seconds" in document
        assert "85.26% branch coverage" in document

    assert "| HW-13 Failure handling | **PASS** |" in hardware_report
    assert "HW-13 wrong-token recovery is Green" in hardware_setup
    assert "HW-13 PASS" in requirements
    assert "HW-13 wrong-token recovery Green" in traceability
    assert "Complete (HW-13 wrong-token recovery, 2026-09-02)" in implementation_plan


def test_hardware_documents_record_successful_hw13_hermes_stop_recovery() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "successful HW-13 Hermes-stop recovery" in document
        assert "`HERMES OFFLINE`" in document
        assert "`lv_font_montserrat_20`" in document
        assert "`failure_error_code=HERMES_FAILED`" in document
        assert "`failure_notification_successes=1`" in document
        assert "`failure_audio_frames=0.0`" in document
        assert "`failure_turn_released=true`" in document
        assert "`recovery_probe_ready=true`" in document
        assert "`recovery_turn_completed=true`" in document
        assert "`recovery_output_streams=1`" in document
        assert "`recovery_audio_frames=20.0`" in document
        assert "`recovery_elapsed_ms=35`" in document
        assert "`recovery_device_idle=true`" in document
        assert "1,412 serial bytes" in document
        assert "zero input, touch, queue and device-error events" in document
        assert "zero boot, panic, watchdog, stack, heap, brownout and reset markers" in document
        assert "no camera, microphone or actuator command" in document
        assert "one bounded recovery audio stream" in document
        assert "one 880 Hz recovery tone" in document
        assert "no other screen change" in document
        assert "no physical contact" in document
        assert "local Mock Hermes" in document
        assert "production public HTTP/SSE client" in document
        assert "live HW-09 remains NOT RUN" in document

    for document in (hardware_report, verification, progress):
        assert "blank Japanese toast" in document
        assert "inaudible 440 Hz" in document
        assert "no automatic retry" in document
        assert "WSL serial enumeration was absent" in document
        assert "USB attached" in document
        assert "scoped firewall rule retained" in document
        assert "HW-13 Hermes-stop evidence host gate" in document
        assert "389 tests passed" in document
        assert "31.83 seconds" in document
        assert "85.26% branch coverage" in document

    assert "HW-13 Hermes-stop recovery is Green" in hardware_setup
    assert "HW-13 PASS" in requirements
    assert "HW-13 Hermes-stop recovery Green" in traceability
    assert "Complete (HW-13 Hermes-stop recovery, 2026-09-02)" in implementation_plan


def test_hardware_documents_record_successful_hw13_tts_stop_recovery() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        assert "successful HW-13 TTS-stop recovery" in document
        assert "13-test temporary harness" in document
        assert "`TTS OFFLINE`" in document
        assert "`GenericHttpWavTtsAdapter`" in document
        assert "`failure_error_code=TTS_FAILED`" in document
        assert "`failure_notification_successes=1`" in document
        assert "`failure_audio_frames=0.0`" in document
        assert "`failure_turn_released=true`" in document
        assert "`tts_baseline_ready=true`" in document
        assert "`tts_stop_phases=1`" in document
        assert "`recovery_tts_ready=true`" in document
        assert "`recovery_turn_completed=true`" in document
        assert "`recovery_output_streams=1`" in document
        assert "`recovery_audio_frames=20.0`" in document
        assert "`recovery_elapsed_ms=35`" in document
        assert "`recovery_device_idle=true`" in document
        assert "23,728 serial bytes" in document
        assert "zero input, touch, queue and device-error events" in document
        assert "zero boot, panic, watchdog, stack, heap, brownout and reset markers" in document
        assert "no camera, physical microphone or actuator command" in document
        assert "one bounded recovery audio stream" in document
        assert "one 880 Hz recovery tone" in document
        assert "no abnormal screen change" in document
        assert "no physical contact" in document
        assert "local HTTP WAV provider" in document
        assert "production TTS adapter" in document
        assert "At that TTS-stop checkpoint, live HW-10 was NOT RUN" in " ".join(document.split())

    for document in (hardware_report, verification, progress):
        assert "one TTS stop phase" in document
        assert "no automatic retry" in document
        assert "one free serial device" in document
        assert "USB attached" in document
        assert "no listener on 8765/8766/18767/18768" in document
        assert "scoped firewall rule retained" in document
        assert "HW-13 TTS-stop evidence host gate" in document
        assert "390 tests passed" in document
        assert "33.34 seconds" in document
        assert "85.26% branch coverage" in document

    assert "HW-13 TTS-stop recovery is Green" in hardware_setup
    assert "HW-13 PASS" in requirements
    assert "HW-13 TTS-stop recovery Green" in traceability
    assert "Complete (HW-13 TTS-stop recovery, 2026-09-02)" in implementation_plan


def test_hardware_documents_record_successful_hw13_camera_failure_recovery() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        document = " ".join(document.split())
        assert "successful HW-13 camera-failure recovery" in document
        assert "21-test temporary harness" in document
        assert "Fresh explicit privacy approval" in document
        assert "exactly one camera command and no host-side retry" in document
        assert "three bounded Firmware upload attempts" in document
        assert "`capture_store=None`" in document
        assert "before request form/body parsing" in document
        assert "`capture_store_unavailable_responses=3`" in document
        assert "`capture_completed_events=1`" in document
        assert "`capture_completed_ok=0`" in document
        assert "`failure_event_forwarded=true`" in document
        assert "`control_status=409`" in document
        assert "`control_error_code=CAPTURE_FAILED`" in document
        assert "`reservations=1`" in document
        assert "`reservation_cancels=1`" in document
        assert "`capture_total=0.0`" in document
        assert "`files_remaining=0`" in document
        assert "`temporary_directory_removed=true`" in document
        assert "`final_state_idle=true`" in document
        assert "`status_commands=2`" in document
        assert "`elapsed_ms=505`" in document
        assert "`serial_camera_frame_markers=1`" in document
        assert "2,924 serial bytes" in document
        assert (
            "no raw image bytes, exact image hash or capture ID were displayed or retained"
            in document
        )
        assert "no shutter sound" in document
        assert "screen presentation was not observed" in document
        assert "no physical contact" in document

    for document in (hardware_report, verification, progress):
        document = " ".join(document.split())
        assert "stable authenticated connection" in document
        assert "zero input, touch, queue and device-error events" in document
        assert (
            "zero camera-error, boot, panic, watchdog, stack, heap, brownout and reset markers"
            in document
        )
        assert "one free serial device" in document
        assert "USB attached" in document
        assert "no listener on 8765/8766/18767/18768" in document
        assert "scoped firewall rule retained" in document
        assert "HW-13 camera-failure evidence host gate" in document
        assert "391 tests passed" in document
        assert "34.60 seconds" in document
        assert "85.26% branch coverage" in document

    assert "HW-13 camera-failure recovery is machine Green" in " ".join(hardware_setup.split())
    assert "HW-13 PASS" in requirements
    assert "HW-13 camera-failure recovery machine Green" in traceability
    assert "Complete (HW-13 camera-failure recovery, 2026-09-02)" in implementation_plan
    assert "| HW-13 Failure handling | **PASS** |" in hardware_report


def test_progress_current_sections_do_not_regress_to_historical_hardware_state() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    remaining = " ".join(
        progress.split("## Remaining stop conditions", maxsplit=1)[1]
        .split("## Latest verification evidence", maxsplit=1)[0]
        .split()
    )
    latest = " ".join(progress.split("## Latest verification evidence", maxsplit=1)[1].split())

    assert "HW-12 remains NOT RUN" not in remaining
    assert "HW-12 remains NOT RUN" not in latest
    assert "HW-12 is **PASS**" in remaining
    assert "HW-13 is **PASS**" in remaining
    assert "HW-13 remains PARTIAL solely because temporary Wi-Fi loss is NOT RUN" not in remaining
    assert "Current flashed HW-12 diagnostic candidate from source commit `8bfc589`" not in latest
    assert "Current flashed HW-12 acceptance candidate from source commit `8ad0489`" not in latest
    assert "Current pre-flash full Firmware-bearing" in latest
    assert "source commit `d88f6df`" in latest
    assert "successful post-correction HW-12 capture" in latest
    assert "377 tests passed in 30.88 seconds" in latest
    assert "20/20 Firmware CTests" in latest
    assert "392 tests passed" not in latest
    assert "415 tests passed" not in latest
    assert "438 tests passed" in latest
    assert "22/22 Firmware CTests" in latest
    assert "actual temporary Wi-Fi link loss" not in latest
    assert "a separate motion-enabled build, flash and attended approval" not in latest
    assert "Final Goal cleanup is complete" in latest
    assert "HW-04 is **PASS**" in remaining


def test_hardware_documents_record_successful_hw13_wifi_loss_recovery() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    evidence_documents = (
        hardware_report,
        verification,
        progress,
        traceability,
        implementation_plan,
    )
    for document in evidence_documents:
        document = " ".join(document.split())
        assert "successful HW-13 Wi-Fi-loss recovery" in document
        assert "`wifi_cycle_commands=1`" in document
        assert "`cycle_duration_seconds=15`" in document
        assert "`cycle_start_acks=1`" in document
        assert "`cycle_restart_acks=1`" in document
        assert "`websocket_disconnects=1.0`" in document
        assert "`recovery_connection_replaced=true`" in document
        assert "`recovery_elapsed_ms=11329`" in document
        assert "`recovery_idle=true`" in document
        assert "`recovery_wifi_connected=true`" in document
        assert "1,286 serial bytes" in document
        assert "zero input, touch, queue and device-error events" in document
        assert "zero boot, panic, watchdog, stack, heap, brownout and reset markers" in document
        assert "no camera, audio or actuator command" in document
        assert "`Connecting Bridge`" in document
        assert "`Bridge connected`" in document
        assert "no abnormal movement or sound" in document
        assert "no physical contact" in document

    diagnostic_sha256 = (
        "137d140de9f4279c86654949307003df"  # pragma: allowlist secret
        "b6d216648e923cc84130057cd1acf4f3"  # pragma: allowlist secret
    )
    normal_sha256 = (
        "32988d0d66eea2a44e690c1b593182"  # pragma: allowlist secret
        "b411f1b1408c23eeb2d0aa59a59aca7e71"  # pragma: allowlist secret
    )
    for document in (hardware_report, verification, progress):
        document = " ".join(document.split())
        assert "source commit `3f3ee40`" in document
        assert diagnostic_sha256 in document
        assert normal_sha256 in document
        assert "written only at `0x20000`" in document
        assert "independent read-only digest" in document
        assert "clean 30-second boot" in document
        assert "diagnostic feature disabled" in document
        assert (
            "HW-13 Wi-Fi-loss evidence host gate was Green with 429 tests passed in "
            "33.69 seconds at 85.32% branch coverage"
        ) in document

    assert "HW-13 failure handling is PASS" in hardware_setup
    assert "| HW-13 Failure handling | **PASS** |" in hardware_report
    assert "HW-13 PASS" in requirements
    assert "HW-13 Wi-Fi-loss recovery Green" in traceability
    assert "Complete (HW-13 Wi-Fi loss, 2026-09-03)" in implementation_plan

    for document in (
        hardware_report,
        verification,
        progress,
        traceability,
        requirements,
        implementation_plan,
    ):
        normalized = " ".join(document.split())
        assert "HW-13 remains PARTIAL" not in normalized
        assert "HW-13 stays PARTIAL" not in normalized
        assert "HW-13 is still PARTIAL" not in normalized
        assert "remaining HW-13 temporary Wi-Fi failure" not in normalized


def test_documents_record_the_k151_motion_profile_and_physical_completion() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    upstream = (ROOT / "firmware" / "UPSTREAM.md").read_text(encoding="utf-8")

    profile = (
        "K151 conservative motion profile: yaw `-45..45` degrees, pitch `5..85` degrees, "
        "speed `1..30` (default `15`), home `0/45` degrees."
    )
    for document in (hardware_setup, verification, progress, requirements, upstream):
        assert profile in " ".join(document.split())

    official_url = "https://docs.m5stack.com/ja/arduino/stackchan/servo"
    assert official_url in hardware_setup
    assert official_url in upstream
    assert "release motion lock remains enabled" in hardware_report
    assert "Physical servo limits remain unknown" not in hardware_report
    assert "K151 yaw-pitch-home Green" in traceability
    assert "CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y" in hardware_report
    assert "Flash and attended motion require distinct explicit approvals" in hardware_report
    assert "| HW-04 Body | **PASS** |" in hardware_report
    assert "| HW-04 Body | **PARTIAL** |" not in hardware_report


def test_requirements_register_records_the_current_hardware_state() -> None:
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    normalized = " ".join(requirements.split())

    assert "HW-10 live physical full voice turn is PASS" in normalized
    assert "CAM-002 live physical vision turn is PASS" in normalized
    assert "24 host C++ tests" in normalized
    assert "current device contains the motion-locked `d88f6df` release" in normalized
    assert "K151 yaw-pitch-home physical sequence is Green and HW-04 is PASS" in normalized
    assert "Final Goal cleanup is complete" in normalized
    assert "The current device instead contains the separately approved" not in normalized
    assert "direction-specific yaw/pitch and home remain incomplete" not in normalized
    assert "further direction-specific yaw/pitch and home commands require" not in normalized


def test_live_hermes_hw09_evidence_is_recorded() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    current_marker = "HW-09 live Hermes Responses API is PASS"

    for document in (progress, verification, hardware_report, requirements):
        assert current_marker in " ".join(document.split())

    assert "| HW-09 Hermes | **PASS** |" in hardware_report
    assert "2,721 ms" in hardware_report
    assert "5,665 ms" in hardware_report
    assert "8,590 ms" in hardware_report
    assert "`skill_view` twice" in hardware_report
    for document in (progress, verification):
        normalized = " ".join(document.split())
        assert "`8cb295e`" in normalized
        assert "433 tests passed in 35.02 seconds" in normalized
        assert "85.32%" in normalized
    assert "CAM-002 live physical vision turn is PASS" in " ".join(progress.split())
    assert "Live Responses API Green" in traceability


def test_live_local_stt_hw08_evidence_is_recorded() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    current_marker = "HW-08 live local faster-whisper STT is PASS"

    for document in (progress, verification, hardware_report, requirements):
        assert current_marker in " ".join(document.split())

    assert "| HW-08 STT | **PASS** |" in hardware_report
    for expected_latency in ("3,689 ms", "2,150 ms", "2,238 ms", "10,961 ms"):
        assert expected_latency in hardware_report
    assert "`small`/CPU/INT8" in hardware_report
    assert "`こんにちは`" in hardware_report
    assert "`今日の日付を教えて`" in hardware_report
    assert "`スタックちゃん、元気ですか?`" in hardware_report
    assert "empty speech returned an empty result" in hardware_report
    assert "no audio retained" in hardware_report
    assert "CAM-002 live physical vision turn is PASS" in " ".join(progress.split())
    assert "Live local STT Green" in traceability


def test_live_physical_full_voice_hw10_evidence_is_recorded() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    evidence_documents = (hardware_report, verification, progress)
    current_marker = "HW-10 live physical full voice turn is PASS"

    for document in (
        hardware_setup,
        hardware_report,
        verification,
        progress,
        requirements,
    ):
        assert current_marker in " ".join(document.split())

    for document in evidence_documents:
        normalized = " ".join(document.split())
        assert "historical duplicate-turn and underrun finding" in normalized
        assert "112 input frames" in normalized
        assert "121 output frames" in normalized
        assert "two turn outcomes" in normalized
        assert "five playback underruns" in normalized
        assert "`9f42b92`" in normalized
        assert "`f73ff28`" in normalized
        assert "63 input frames" in normalized
        assert "129 output frames" in normalized
        assert "one STT, one Hermes and one completed turn" in normalized
        assert "two TTS segments" in normalized
        assert (
            "zero connection, disconnection, underrun, overflow, decode, auth and timeout deltas"
            in normalized
        )
        assert "operator heard and understood the answer" in normalized
        assert "no `Connecting Bridge` toast, abnormality or additional contact" in normalized
        assert "no recording was retained" in normalized.lower()

    candidate_path = "firmware/build-hermes-hw10-final-f73ff28/stack-chan.bin"
    candidate_sha256 = (
        "41cd8affc309006f7fc1adaaeafe5f50"  # pragma: allowlist secret
        "cf1b1bc2e4daf1322cff6b29cac6489c"  # pragma: allowlist secret
    )
    assert candidate_path in hardware_report
    assert candidate_sha256 in hardware_report
    assert "3,920,864 bytes" in hardware_report
    assert "436 tests passed" in verification
    assert "85.45%" in verification
    assert "22/22 Firmware CTest" in verification
    assert "| HW-10 Full voice turn | **PASS** |" in hardware_report
    assert "HW-10 physical full voice Green" in traceability
    assert "CAM-002 live physical vision turn is PASS" in " ".join(requirements.split())
    assert "Complete (HW-10 physical full voice, 2026-09-04)" in implementation_plan


def test_live_physical_cam002_and_sustained_touch_evidence_are_recorded() -> None:
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    protocol = (ROOT / "docs" / "protocol-v1.md").read_text(encoding="utf-8")
    state_machines = (ROOT / "docs" / "state-machines.md").read_text(encoding="utf-8")
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    evidence_documents = (hardware_report, verification, progress)
    status_documents = (
        architecture,
        protocol,
        state_machines,
        hardware_setup,
        hardware_report,
        verification,
        progress,
        requirements,
    )
    current_marker = "CAM-002 live physical vision turn is PASS"

    for document in status_documents:
        assert current_marker in " ".join(document.split())

    for document in evidence_documents:
        normalized = " ".join(document.split())
        assert "one capture, one live Hermes vision request and one spoken response" in normalized
        assert "`capture_total +1`" in normalized
        assert "100 output frames" in normalized
        assert "DELETE returned 204" in normalized
        assert "`files_remaining=0`" in normalized
        assert "operator heard and understood the answer" in normalized
        assert "description matched the camera scene" in normalized
        assert (
            "no `Connecting Bridge` toast, unexpected display change, physical contact or "
            "abnormality" in normalized
        )
        assert "one no-contact input frame" in normalized
        assert "no STT request" in normalized
        assert "six consecutive 50 ms press samples" in normalized
        assert "three consecutive release/idle samples" in normalized
        assert "60.000-second no-touch window" in normalized
        assert "20 Opus frames and 2,878 bytes" in normalized
        assert "10.001-second post-touch quiet window" in normalized
        assert "`connection_stable=false`" in normalized
        assert "not used as connection-stability evidence" in normalized
        assert "no automatic retry" in normalized

    candidate_path = "firmware/build-hermes-touch-filter-d88f6df/stack-chan.bin"
    candidate_sha256 = (
        "32ec714f11a7c906e6ff73f3c7813f"  # pragma: allowlist secret
        "3ed5a0fb06328df1b6db0acba1ae54d881"  # pragma: allowlist secret
    )
    for document in evidence_documents:
        normalized = " ".join(document.split())
        assert candidate_path in normalized
        assert candidate_sha256 in normalized
        assert "3,920,848 bytes" in normalized
        assert "source commit `d88f6df`" in normalized
        assert "13,251 serial bytes" in normalized
        assert "438 tests passed" in normalized
        assert "85.45%" in normalized
        assert "22/22 Firmware CTest" in normalized

    final_gate_sha256 = (
        "fb4193c340c29fc9e5861b81de85a113"  # pragma: allowlist secret
        "da91bedd96969ab3d44a7550873f09ac"  # pragma: allowlist secret
    )
    for document in evidence_documents:
        normalized = " ".join(document.split())
        assert "final documentation full gate" in normalized
        assert "439 tests passed in 32.52 seconds" in normalized
        assert final_gate_sha256 in normalized

    assert "CAM-002 physical vision Green" in traceability
    assert "sustained-touch physical regression Green" in traceability
    assert "Complete (CAM-002 physical vision, 2026-09-04)" in implementation_plan
    assert "Complete (sustained-touch safety regression, 2026-09-04)" in implementation_plan


def test_final_goal_cleanup_is_recorded() -> None:
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    status_documents = (
        hardware_setup,
        hardware_report,
        verification,
        progress,
        requirements,
        traceability,
        implementation_plan,
    )
    evidence_documents = (hardware_report, verification, progress)

    for document in status_documents:
        assert "Final Goal cleanup is complete" in " ".join(document.split())

    for document in evidence_documents:
        normalized = " ".join(document.split())
        assert "evidence commit `a49adc8`" in normalized
        assert "`StackChanHermesBridge8765` rules=0" in normalized
        assert "all WSL Hyper-V `DefaultInboundAction=Block`" in normalized
        assert "The reviewed USB device is `Shared`, not `Attached`" in normalized
        assert "no WSL serial directory" in normalized
        assert "no listener on 8765/8766/8642/50031" in normalized
        assert "temporary TTS and SSH tunnel processes are absent" in normalized
        assert "SSH control socket is absent" in normalized
        assert "temporary touch harness and Goal-owned `/tmp` artifacts are absent" in normalized
        assert "no capture or audio media" in normalized

    assert "Complete (final Goal cleanup, 2026-09-04)" in implementation_plan


def test_current_design_document_statuses_match_completed_physical_evidence() -> None:
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    protocol = (ROOT / "docs" / "protocol-v1.md").read_text(encoding="utf-8")
    state_machines = (ROOT / "docs" / "state-machines.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    hardware_setup = (ROOT / "docs" / "hardware-setup.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    protocol_adr = (ROOT / "docs" / "adr" / "ADR-0002-device-protocol.md").read_text(
        encoding="utf-8"
    )
    audio_adr = (ROOT / "docs" / "adr" / "ADR-0004-audio-pipeline.md").read_text(encoding="utf-8")
    verification_normalized = " ".join(verification.split())
    hardware_setup_normalized = " ".join(hardware_setup.split())
    progress_normalized = " ".join(progress.split())

    assert "remaining physical media/motion" not in architecture
    assert "motion-locked `d88f6df` release" in architecture
    assert "Media paths remain pending physical acceptance" not in protocol
    assert "Physical audio and camera media paths are Green" in protocol
    assert "physical transitions remain NOT RUN" not in state_machines
    assert (
        "Physical connection, input, output, cancellation, camera, motion and failure-recovery"
        in (state_machines)
    )
    assert "`HW-01` through `HW-13` are PASS" in verification
    assert "current device contains the separately approved attended candidate" not in verification
    assert "current device contains the motion-locked `d88f6df` release" in (
        verification_normalized
    )
    assert "K151 yaw-pitch-home physical sequence is Green" in hardware_setup_normalized
    assert "direction-specific yaw/pitch and home remain incomplete" not in hardware_setup
    assert "The current device contains the separately approved" not in hardware_setup
    assert "Twenty-four host C++ tests" in implementation_plan
    assert "- Status: Accepted and implemented for Protocol v1" in protocol_adr
    assert "- Status: Accepted and implemented; codec paths are tested" in audio_adr
    assert "Final Goal cleanup is complete" in progress_normalized


def test_current_k151_motion_profile_gate_evidence_is_recorded() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    expected_sha256 = (
        "32ec714f11a7c906e6ff73f3c7813f"  # pragma: allowlist secret
        "3ed5a0fb06328df1b6db0acba1ae54d881"  # pragma: allowlist secret
    )
    candidate_sha256 = (
        "af98e32ce32aa21214d4c8e29440fb27"  # pragma: allowlist secret
        "85b1f2f020f405ae2e049a332ebd7d7d"  # pragma: allowlist secret
    )

    for document in (progress, verification):
        normalized = " ".join(document.split())
        assert "438 tests passed" in normalized
        assert "85.45%" in normalized
        assert "22/22 Firmware CTest" in normalized
        assert "3,920,848" in normalized
        assert expected_sha256 in normalized
        assert "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y" in normalized
        assert "`d88f6df`" in normalized
        assert "3,921,232" in normalized
        assert candidate_sha256 in normalized
        assert "CONFIG_STACKCHAN_HERMES_LOCAL_MOTION_LOCK=y" in normalized


def test_documents_record_current_attended_motion_candidate_preflight_without_flash() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended motion-candidate preflight"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "no flash write or physical head command" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "current motion-locked app digest matched" in normalized_report
    assert "Secure Boot and Flash Encryption remained disabled" in normalized_report
    assert "explicit flash approval remains pending" in normalized_report


def test_documents_record_attended_motion_candidate_flash_without_motion() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended motion-candidate app-only flash"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        checkpoint = normalized.split(marker, 1)[1].split(
            "2026-09-03 attended initial K151 motion", 1
        )[0]
        assert "no physical head command has been sent" in checkpoint.lower()

    normalized_report = " ".join(hardware_report.split())
    assert "write hash and independent digest both matched" in normalized_report
    assert "35.09-second content-suppressed boot window" in normalized_report
    assert "physical motion approval remains pending" in normalized_report


def test_documents_record_attended_initial_k151_motion_without_claiming_full_body_pass() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended initial K151 motion"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "physical yaw/pitch/home sequence remains incomplete" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "exactly one `head.set_angles` command" in normalized_report
    assert "`yaw=5`, `pitch=45`, `speed=10`" in normalized_report
    assert "operator observed motion" in normalized_report
    assert "no abnormal sound, vibration or heat" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report
    assert "motion_commands=1" in normalized_report


def test_documents_record_inconclusive_attended_home_without_claiming_home_green() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended K151 home attempt"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "home remains unestablished" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "exactly one `head.home` command" in normalized_report
    assert "`motion_commands=1`, `home_commands=1`, `angle_commands=0`" in normalized_report
    assert "`machine_valid=false`" in normalized_report
    assert "`input_starts=1`, `input_frames=41`, `input_ends=1`" in normalized_report
    assert "no retry or additional motion command" in normalized_report
    assert "did not observe movement" in normalized_report
    assert "reported no abnormal sound, vibration or heat" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report
    assert "K151 home Green" not in traceability


def test_documents_record_attended_positive_yaw_without_claiming_pitch_or_home() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended K151 positive-yaw observation"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "positive yaw direction is physically established" in normalized
        assert "pitch and home remain unestablished" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "exactly one `head.set_angles` command" in normalized_report
    assert "`yaw=10`, `pitch=45`, `speed=10`" in normalized_report
    assert "`motion_commands=1`, `angle_commands=1`, `home_commands=0`" in normalized_report
    assert "`exact_yaw_commands=1`" in normalized_report
    assert "`machine_valid=true`" in normalized_report
    assert "`input_starts=0`, `input_frames=0`, `input_ends=0`" in normalized_report
    assert "no retry or home command" in normalized_report
    assert "slightly to the left when viewed from the front" in normalized_report
    assert "reported no abnormal sound, vibration or heat" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report


def test_documents_record_observed_return_home_without_claiming_machine_green() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended K151 return-home observation"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "physical return-to-home motion was observed" in normalized
        assert "machine-valid home completion remains unestablished" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "all preceding starts stopped before a motion command" in normalized_report
    assert "released exactly one `head.home` command" in normalized_report
    assert "`unexpected_error`" in normalized_report
    assert "`machine_valid=false`" in normalized_report
    assert "`position_home=true`, `position_offset=false`" in normalized_report
    assert "rightward return to center" in normalized_report
    assert "reported no abnormality" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report


def test_documents_record_attended_pitch_without_claiming_machine_valid_home() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended K151 pitch observation"
    for document in (progress, hardware_report, verification, traceability):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "decreasing pitch direction is physically established" in normalized
        assert "machine-valid home completion remains unestablished" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "exactly one `head.set_angles` command" in normalized_report
    assert "`yaw=0`, `pitch=40`, `speed=10`" in normalized_report
    assert "`motion_commands=1`, `angle_commands=1`, `home_commands=0`" in normalized_report
    assert "`exact_pitch_commands=1`" in normalized_report
    assert "`machine_valid=true`" in normalized_report
    assert "`initial_pitch=45.3`, `final_pitch=40.3`" in normalized_report
    assert "`input_starts=0`, `input_frames=0`, `input_ends=0`" in normalized_report
    assert "no retry or home command" in normalized_report
    assert "downward when viewed from the front" in normalized_report
    assert "reported no abnormal sound, vibration or heat" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report


def test_documents_record_attended_machine_valid_home_and_complete_hw04() -> None:
    progress = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    hardware_report = (ROOT / "docs" / "hardware-test-report.md").read_text(encoding="utf-8")
    verification = (ROOT / "docs" / "verification-report.md").read_text(encoding="utf-8")
    traceability = (ROOT / "docs" / "traceability.md").read_text(encoding="utf-8")
    requirements = (ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")
    implementation_plan = (ROOT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")

    marker = "2026-09-03 attended K151 machine-valid home"
    for document in (
        progress,
        hardware_report,
        verification,
        traceability,
        requirements,
        implementation_plan,
    ):
        normalized = " ".join(document.split())
        assert marker in normalized
        assert "machine-valid home completion is established" in normalized

    normalized_report = " ".join(hardware_report.split())
    assert "exactly one `head.home` command" in normalized_report
    assert "`motion_commands=1`, `home_commands=1`, `angle_commands=0`" in normalized_report
    assert "`exact_home_commands=1`" in normalized_report
    assert "`machine_valid=true`" in normalized_report
    assert "`initial_pitch=40.3`, `final_pitch=44.3`" in normalized_report
    assert "`final_yaw=0.6`" in normalized_report
    assert "`position_reads=3`" in normalized_report
    assert "`input_starts=0`, `input_frames=0`, `input_ends=0`" in normalized_report
    assert "no retry or additional motion command" in normalized_report
    assert "one upward movement when viewed from the front" in normalized_report
    assert "did not independently judge the fine final angle by eye" in normalized_report
    assert "reported no abnormal sound, vibration or heat" in normalized_report
    assert "touched neither the device, desk nor cable" in normalized_report
    assert "| HW-04 Body | **PASS** |" in hardware_report
    assert "| HW-04 Body | **PARTIAL** |" not in hardware_report
    assert "K151 yaw-pitch-home Green" in traceability
    assert "HW-04 PARTIAL" not in requirements
    assert "Complete (K151 physical motion, 2026-09-03)" in implementation_plan


def test_goal_defers_the_temporary_hyper_v_firewall_cleanup_until_final_cleanup() -> None:
    goal = (ROOT / "Goal.md").read_text(encoding="utf-8")

    assert "連続した実機検証中は各シナリオ後に削除しない" in goal
    assert "Goal 全体の終了時に一度だけ削除する" in goal
    assert "StackChanHermesBridge8765" in goal
    assert "規則数が0件" in goal
    assert "DefaultInboundAction=Block" in goal


def test_protocol_status_reflects_physical_transport_evidence() -> None:
    protocol = (ROOT / "docs" / "protocol-v1.md").read_text(encoding="utf-8")

    assert "physical authenticated transport is Green" in protocol
    assert "physical transport remains NOT RUN" not in protocol


def test_package_exposes_initial_version() -> None:
    assert stackchan_bridge.__version__ == "0.1.0"


def test_offline_doctor_reports_required_and_optional_prerequisites() -> None:
    installed = {
        "ffmpeg": "/usr/bin/ffmpeg",
        "git": "/usr/bin/git",
        "python3.12": "/usr/bin/python3.12",
        "uv": "/usr/bin/uv",
    }

    def which(command: str) -> str | None:
        return installed.get(command)

    def find_library(name: str) -> str | None:
        return "libopus.so.0" if name == "opus" else None

    checks = inspect_host(which=which, find_library=find_library)
    status_by_name = {check.name: check.status for check in checks}

    assert status_by_name["python3.12"] is CheckStatus.AVAILABLE
    assert status_by_name["uv"] is CheckStatus.AVAILABLE
    assert status_by_name["ffmpeg"] is CheckStatus.AVAILABLE
    assert status_by_name["libopus"] is CheckStatus.AVAILABLE
    assert status_by_name["idf.py"] is CheckStatus.MISSING
    assert status_by_name["hermes"] is CheckStatus.MISSING


def test_doctor_json_exit_code_only_depends_on_required_checks(
    capsys: object,
) -> None:
    paths = {
        "ffmpeg": "/usr/bin/ffmpeg",
        "git": "/usr/bin/git",
        "python3.12": "/usr/bin/python3.12",
        "uv": "/usr/bin/uv",
    }

    which: Callable[[str], str | None] = paths.get
    exit_code = bridge_cli.main(
        ["doctor", "--offline", "--json"],
        which=which,
        find_library=lambda name: "libopus.so.0" if name == "opus" else None,
    )

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["mode"] == "offline"
    assert payload["ready"] is True
    assert payload["checks"]["idf.py"]["required"] is False
    assert payload["checks"]["idf.py"]["status"] == "missing"


def test_doctor_human_output_fails_when_a_required_check_is_missing(
    capsys: object,
) -> None:
    exit_code = bridge_cli.main(
        ["doctor", "--offline"],
        which=lambda _command: None,
        find_library=lambda _name: None,
    )

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 1
    assert "python3.12: missing [required]" in captured.out
    assert "idf.py: missing [optional]" in captured.out


def test_online_doctor_checks_public_services_and_local_runtime_contracts(
    tmp_path: Path,
    capsys: object,
) -> None:
    config_path = tmp_path / "doctor.toml"
    capture_directory = tmp_path / "captures"
    capture_directory.mkdir()
    config_path.write_text(
        "\n".join(
            (
                "[hermes]",
                'model = "hermes-agent"',
                "[captures]",
                f'directory = "{capture_directory}"',
                "[security]",
                'allowed_devices = ["sim-001"]',
            )
        ),
        encoding="utf-8",
    )
    requested_paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/capabilities":
            assert request.headers["authorization"] == "Bearer doctor-hermes-key"
            return httpx.Response(
                200,
                json={
                    "object": "hermes.api_server.capabilities",
                    "platform": "hermes-agent",
                    "model": "hermes-agent",
                    "auth": {"type": "bearer", "required": True},
                    "features": {
                        "responses_api": True,
                        "responses_streaming": True,
                        "session_key_header": "X-Hermes-Session-Key",
                        "skills_api": True,
                    },
                    "endpoints": {
                        "responses": {"method": "POST", "path": "/v1/responses"},
                        "skills": {"method": "GET", "path": "/v1/skills"},
                        "toolsets": {"method": "GET", "path": "/v1/toolsets"},
                    },
                },
            )
        if request.url.path == "/health/ready":
            return httpx.Response(
                200,
                json={
                    "ready": True,
                    "connected_devices": 0,
                    "checks": {
                        "configuration": True,
                        "capture_store": True,
                        "libopus": True,
                        "hermes": True,
                        "stt": True,
                        "tts": True,
                    },
                },
            )
        raise AssertionError(f"unexpected doctor request: {request.url}")

    paths = {
        "ffmpeg": "/usr/bin/ffmpeg",
        "git": "/usr/bin/git",
        "python3.12": "/usr/bin/python3.12",
        "uv": "/usr/bin/uv",
    }
    exit_code = bridge_cli.main(
        ["doctor", "--config", str(config_path), "--json"],
        environment={
            "HERMES_API_KEY": "doctor-hermes-key",  # pragma: allowlist secret
            "STACKCHAN_DEVICE_TOKEN": "doctor-device-token",  # pragma: allowlist secret
        },
        which=paths.get,
        find_library=lambda name: "libopus.so.0" if name == "opus" else None,
        doctor_transport=httpx.MockTransport(handle),
        doctor_port_checker=lambda _host, _port: True,
    )

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert exit_code == 0
    assert payload["mode"] == "online"
    assert payload["ready"] is True
    assert payload["checks"]["configuration"]["status"] == "available"
    assert payload["checks"]["hermes_health"]["status"] == "available"
    assert payload["checks"]["hermes_capabilities"]["status"] == "available"
    assert payload["checks"]["responses_api"]["status"] == "available"
    assert payload["checks"]["stt"]["status"] == "available"
    assert payload["checks"]["tts"]["status"] == "available"
    assert payload["checks"]["connected_device"]["required"] is False
    assert payload["checks"]["firmware_backup"]["required"] is False
    assert requested_paths == ["/health/ready", "/health", "/v1/capabilities"]
    assert "doctor-hermes-key" not in json.dumps(payload)


def test_online_doctor_continues_independent_checks_after_bridge_failure(
    tmp_path: Path,
    capsys: object,
) -> None:
    capture_directory = tmp_path / "captures"
    capture_directory.mkdir()
    config_path = tmp_path / "doctor.toml"
    config_path.write_text(
        "\n".join(
            (
                "[hermes]",
                'model = "hermes-agent"',
                "[captures]",
                f'directory = "{capture_directory}"',
            )
        ),
        encoding="utf-8",
    )
    requested_paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/health/ready":
            return httpx.Response(503, content=b"private-bridge-diagnostic")
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "responses_api": True,
                "streaming": True,
                "session_key_header": True,
                "input_image": True,
                "models": ["hermes-agent"],
            },
        )

    required_paths = {
        "ffmpeg": "/usr/bin/ffmpeg",
        "git": "/usr/bin/git",
        "python3.12": "/usr/bin/python3.12",
        "uv": "/usr/bin/uv",
    }
    exit_code = bridge_cli.main(
        ["doctor", "--config", str(config_path), "--json"],
        environment={"HERMES_API_KEY": "doctor-hermes-key"},  # pragma: allowlist secret
        which=required_paths.get,
        find_library=lambda name: "libopus.so.0" if name == "opus" else None,
        doctor_transport=httpx.MockTransport(handle),
        doctor_port_checker=lambda _host, _port: True,
    )

    output = capsys.readouterr().out  # type: ignore[attr-defined]
    payload = json.loads(output)
    assert exit_code == 1
    assert payload["checks"]["bridge_readiness"]["status"] == "missing"
    assert payload["checks"]["stt"]["status"] == "missing"
    assert payload["checks"]["hermes_health"]["status"] == "available"
    assert payload["checks"]["hermes_capabilities"]["status"] == "available"
    assert payload["checks"]["responses_api"]["status"] == "missing"
    assert requested_paths == ["/health/ready", "/health", "/v1/capabilities"]
    assert "private-bridge-diagnostic" not in output


def test_doctor_only_accepts_a_16_mib_backup_with_a_matching_sha256(tmp_path: Path) -> None:
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    backup = backup_directory / "factory.bin"
    backup.write_bytes(b"\x00" * (16 * 1024 * 1024))
    checksum = backup_directory / "factory.bin.sha256"
    checksum.write_text("0" * 64, encoding="ascii")

    assert firmware_backup_is_verified(backup_directory) is False

    digest = sha256(backup.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  factory.bin\n", encoding="ascii")

    assert firmware_backup_is_verified(backup_directory) is True


def test_doctor_finds_a_verified_backup_in_one_private_subdirectory(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    backup_directory = backup_root / "reviewed-device"
    backup_directory.mkdir(parents=True, mode=0o700)
    backup = backup_directory / "factory.bin"
    backup.write_bytes(b"\x00" * (16 * 1024 * 1024))
    digest = sha256(backup.read_bytes()).hexdigest()
    backup.with_suffix(".bin.sha256").write_text(
        f"{digest}  factory.bin\n",
        encoding="ascii",
    )

    assert firmware_backup_is_verified(backup_root) is True


def test_doctor_detects_faster_whisper_first_download_without_network_access(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "huggingface" / "hub"
    environment = {"HF_HUB_CACHE": str(cache)}

    assert faster_whisper_model_is_cached("small", environment=environment) is False

    model = (
        cache
        / "models--Systran--faster-whisper-small"
        / "snapshots"
        / "offline-test-revision"
        / "model.bin"
    )
    model.parent.mkdir(parents=True)
    model.write_bytes(b"cached-model")

    assert faster_whisper_model_is_cached("small", environment=environment) is True

    local_model = tmp_path / "local-model"
    local_model.mkdir()
    (local_model / "model.bin").write_bytes(b"local-model")
    assert faster_whisper_model_is_cached(str(local_model), environment={}) is True


def test_bridge_entrypoint_uses_main_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge_cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as error:
        bridge_cli.entrypoint()

    assert error.value.code == 7


def test_serve_cli_applies_named_overrides_before_calling_the_runner() -> None:
    received: list[BridgeSettings] = []

    exit_code = bridge_cli.main(
        [
            "serve",
            "--config",
            str(ROOT / "config.example.toml"),
            "--device-port",
            "9875",
            "--control-port",
            "9876",
        ],
        environment={
            "STACKCHAN_DEVICE_TOKEN": "runtime-token",  # pragma: allowlist secret
        },
        serve_runner=lambda settings, _environment: received.append(settings) or 0,
    )

    assert exit_code == 0
    assert received[0].device_gateway.port == 9875
    assert received[0].control_api.port == 9876
    assert received[0].device_gateway.host == "0.0.0.0"


def test_devices_cli_loads_control_settings_and_output_mode() -> None:
    received: list[tuple[BridgeSettings, bool]] = []

    exit_code = bridge_cli.main(
        [
            "devices",
            "--config",
            str(ROOT / "config.example.toml"),
            "--control-port",
            "9988",
            "--json",
        ],
        environment={},
        devices_runner=lambda settings, as_json: received.append((settings, as_json)) or 0,
    )

    assert exit_code == 0
    assert received[0][0].control_api.host == "127.0.0.1"
    assert received[0][0].control_api.port == 9988
    assert received[0][1] is True


def test_devices_http_runner_prints_bounded_control_response(capsys: object) -> None:
    settings = BridgeSettings()

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:8766/v1/control/devices"
        return httpx.Response(
            200,
            json={
                "devices": [
                    {
                        "device_id": "sim-001",
                        "firmware_version": "0.1.0",
                    }
                ]
            },
        )

    exit_code = bridge_cli.list_devices(
        settings,
        as_json=True,
        transport=httpx.MockTransport(handle),
    )

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert exit_code == 0
    assert payload["devices"][0]["device_id"] == "sim-001"


@pytest.mark.parametrize("action", ["list", "purge"])
def test_captures_cli_routes_configured_storage_action(action: str) -> None:
    received: list[tuple[BridgeSettings, str, bool]] = []

    exit_code = bridge_cli.main(
        [
            "captures",
            action,
            "--config",
            str(ROOT / "config.example.toml"),
            "--json",
        ],
        environment={},
        captures_runner=lambda settings, selected_action, as_json: (
            received.append((settings, selected_action, as_json)) or 0
        ),
    )

    assert exit_code == 0
    assert received[0][0].captures.directory == Path(".local/captures")
    assert received[0][1:] == (action, True)


def test_capture_purge_only_deletes_expired_generated_files(
    tmp_path: Path,
    capsys: object,
) -> None:
    expired = tmp_path / "11111111111111111111111111111111.jpg"
    active = tmp_path / "22222222222222222222222222222222.jpg"
    unknown = tmp_path / "keep-me.jpg"
    linked = tmp_path / "33333333333333333333333333333333.jpg"
    for path in (expired, active, unknown):
        path.write_bytes(b"jpeg")
    linked.symlink_to(unknown)
    os.utime(expired, (80, 80))
    os.utime(active, (95, 95))
    settings = BridgeSettings.model_validate(
        {"captures": {"directory": tmp_path, "ttl_seconds": 10}}
    )

    assert bridge_cli.manage_captures(settings, "list", True, clock=lambda: 100) == 0
    listed = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert [record["capture_id"] for record in listed["captures"]] == [
        "11111111111111111111111111111111",
        "22222222222222222222222222222222",
    ]

    assert bridge_cli.manage_captures(settings, "purge", True, clock=lambda: 100) == 0
    purged = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert purged == {"purged": 1}
    assert not expired.exists()
    assert active.exists()
    assert unknown.exists()
    assert linked.is_symlink()


def test_token_create_prints_a_one_time_token_and_storage_hash(capsys: object) -> None:
    raw_token = "deterministic-one-time-token"  # pragma: allowlist secret

    exit_code = bridge_cli.main(
        ["token", "create", "--device-id", "sim-002", "--json"],
        token_factory=lambda: raw_token,
    )

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["device_id"] == "sim-002"
    assert payload["token"] == raw_token
    assert verify_device_token(raw_token, payload["token_hash"])
    assert captured.out.count(raw_token) == 1


def test_mcp_cli_uses_stdio_with_a_loopback_control_url(capsys: object) -> None:
    received: list[str] = []

    exit_code = mcp_cli.main(
        ["--control-url", "http://127.0.0.1:8766"],
        runner=lambda url: received.append(url) or 0,
    )

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert exit_code == 0
    assert received == ["http://127.0.0.1:8766"]
    assert captured.out == ""


def test_mcp_cli_reads_control_url_from_environment() -> None:
    received: list[str] = []

    exit_code = mcp_cli.main(
        [],
        environment={"STACKCHAN_CONTROL_URL": "http://localhost:9876"},
        runner=lambda url: received.append(url) or 0,
    )

    assert exit_code == 0
    assert received == ["http://localhost:9876"]


def test_mcp_cli_rejects_a_non_loopback_control_url() -> None:
    called = False

    def runner(_url: str) -> int:
        nonlocal called
        called = True
        return 0

    with pytest.raises(SystemExit) as raised:
        mcp_cli.main(["--control-url", "http://192.0.2.1:8766"], runner=runner)

    assert raised.value.code == 2
    assert called is False


@pytest.mark.parametrize(
    "control_url",
    [
        "ftp://127.0.0.1:8766",
        "http://user:password@127.0.0.1:8766",  # pragma: allowlist secret
        "http://127.0.0.1:8766/v1/control",
        "http://127.0.0.1:8766?redirect=http://example.com",
        "http://127.0.0.1:8766#fragment",
    ],
)
def test_mcp_cli_rejects_unsafe_loopback_url_shapes(control_url: str) -> None:
    with pytest.raises(SystemExit) as raised:
        mcp_cli.main(["--control-url", control_url], runner=lambda _url: 0)

    assert raised.value.code == 2
