from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _workflow_job(workflow: str, job_name: str, next_job_name: str | None = None) -> str:
    job = workflow.split(f"\n  {job_name}:\n", 1)[1]
    if next_job_name is not None:
        job = job.split(f"\n  {next_job_name}:\n", 1)[0]
    return job


def test_ci_uses_pinned_actions_and_the_local_host_gate() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "pull_request_target" not in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9" in workflow
    assert 'version: "0.12.6"' in workflow
    assert "./scripts/verify-host.sh" in workflow
    assert "firmware/UPSTREAM.md" in workflow
    assert "container: espressif/idf:v5.5.4" in workflow
    assert "python3 ./fetch_repos.py" in workflow
    assert "idf.py reconfigure" in workflow
    assert "./scripts/verify-firmware.sh" in workflow
    assert "build pending source import" not in workflow


def test_ci_runs_push_workflow_only_for_main_while_checking_pull_requests() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "on:\n  push:\n    branches:\n      - main\n  pull_request:\n" in workflow


def test_host_ci_fetches_ignored_firmware_dependencies_before_contract_tests() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    host_job = _workflow_job(workflow, "host", "firmware")

    fetch = "working-directory: firmware\n        run: python3 ./fetch_repos.py"
    assert fetch in host_job
    assert host_job.index(fetch) < host_job.index("./scripts/verify-host.sh")


def test_firmware_ci_activates_the_container_toolchain_for_each_idf_command() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    firmware_job = _workflow_job(workflow, "firmware")

    assert "/opt/esp/entrypoint.sh idf.py reconfigure" in firmware_job
    assert "/opt/esp/entrypoint.sh ./scripts/verify-firmware.sh" in firmware_job
