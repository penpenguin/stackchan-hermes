from __future__ import annotations

import importlib.util
import json
import subprocess
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = ROOT / "firmware" / "verify_upstream_dependencies.py"
MANAGED_VERIFIER_PATH = ROOT / "firmware" / "verify_managed_components.py"


def _load_verifier(path: Path = VERIFIER_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _create_repository(path: Path) -> str:
    path.mkdir(parents=True)
    _git(path, "init", "--quiet")
    (path / "source.txt").write_text("baseline\n", encoding="utf-8")
    _git(path, "add", "source.txt")
    _git(
        path,
        "-c",
        "user.name=Firmware Test",
        "-c",
        "user.email=firmware-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "baseline",
    )
    return _git(path, "rev-parse", "HEAD")


def _write_lock(firmware_root: Path, dependency: dict[str, str]) -> None:
    (firmware_root / "upstream-lock.json").write_text(
        json.dumps({"fetched_repositories": [dependency]}),
        encoding="utf-8",
    )


def test_dependency_verifier_accepts_only_the_locked_commit(tmp_path: Path) -> None:
    verifier = _load_verifier()
    firmware_root = tmp_path / "firmware"
    dependency_path = firmware_root / "components" / "dependency"
    commit = _create_repository(dependency_path)
    dependency = {
        "path": "components/dependency",
        "commit": commit,
        "ref": "v1.0.0",
        "license": "MIT",
    }
    _write_lock(firmware_root, dependency)

    assert verifier.verify_dependencies(firmware_root) == ["components/dependency"]

    dependency["commit"] = "0" * 40
    _write_lock(firmware_root, dependency)
    with pytest.raises(verifier.DependencyVerificationError, match="commit mismatch"):
        verifier.verify_dependencies(firmware_root)


def test_dependency_verifier_accepts_only_the_locked_patch_diff(tmp_path: Path) -> None:
    verifier = _load_verifier()
    firmware_root = tmp_path / "firmware"
    dependency_path = firmware_root / "patched-dependency"
    commit = _create_repository(dependency_path)
    (dependency_path / "source.txt").write_text("patched\n", encoding="utf-8")
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(dependency_path),
            "diff",
            "HEAD",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
        ],
        check=True,
        capture_output=True,
    ).stdout
    dependency = {
        "path": "patched-dependency",
        "commit": commit,
        "ref": "v1.0.0",
        "license": "MIT",
        "patch": "patches/dependency.patch",
        "patched_diff_sha256": sha256(diff).hexdigest(),
    }
    patch_path = firmware_root / "patches" / "dependency.patch"
    patch_path.parent.mkdir()
    patch_path.write_bytes(diff)
    _write_lock(firmware_root, dependency)

    assert verifier.verify_dependencies(firmware_root) == ["patched-dependency"]

    (dependency_path / "source.txt").write_text("unexpected\n", encoding="utf-8")
    with pytest.raises(verifier.DependencyVerificationError, match="patch diff mismatch"):
        verifier.verify_dependencies(firmware_root)


def test_managed_component_verifier_recomputes_the_locked_content_hash(tmp_path: Path) -> None:
    verifier = _load_verifier(MANAGED_VERIFIER_PATH)
    firmware_root = tmp_path / "firmware"
    component = firmware_root / "managed_components" / "vendor__dependency"
    component.mkdir(parents=True)
    (component / ".component_hash").write_text("a" * 64, encoding="utf-8")
    source = component / "source.c"
    source.write_text("baseline\n", encoding="utf-8")
    lock = {
        "dependencies": {
            "vendor/dependency": {
                "component_hash": "a" * 64,
                "source": {"type": "service"},
            },
            "idf": {"source": {"type": "idf"}},
        }
    }

    def validate_hash(path: Path, expected_hash: str) -> None:
        assert path == component
        assert expected_hash == "a" * 64
        if source.read_text(encoding="utf-8") != "baseline\n":
            raise ValueError("content changed")

    assert verifier.verify_managed_components(firmware_root, lock, validate_hash) == [
        "vendor/dependency"
    ]

    source.write_text("modified\n", encoding="utf-8")
    with pytest.raises(verifier.ManagedComponentVerificationError, match="content mismatch"):
        verifier.verify_managed_components(firmware_root, lock, validate_hash)


def test_managed_component_verifier_rejects_directory_or_lock_hash_drift(tmp_path: Path) -> None:
    verifier = _load_verifier(MANAGED_VERIFIER_PATH)
    firmware_root = tmp_path / "firmware"
    component = firmware_root / "managed_components" / "vendor__dependency"
    component.mkdir(parents=True)
    hash_file = component / ".component_hash"
    hash_file.write_text("a" * 64, encoding="utf-8")
    lock = {
        "dependencies": {
            "vendor/dependency": {
                "component_hash": "a" * 64,
                "source": {"type": "service"},
            }
        }
    }

    extra = firmware_root / "managed_components" / "unexpected__component"
    extra.mkdir()
    with pytest.raises(verifier.ManagedComponentVerificationError, match="directory mismatch"):
        verifier.verify_managed_components(firmware_root, lock, lambda *_: None)

    extra.rmdir()
    hash_file.write_text("b" * 64, encoding="utf-8")
    with pytest.raises(verifier.ManagedComponentVerificationError, match="lock hash mismatch"):
        verifier.verify_managed_components(firmware_root, lock, lambda *_: None)


def test_firmware_gate_verifies_locked_dependencies_before_build() -> None:
    gate = (ROOT / "scripts" / "verify-firmware.sh").read_text(encoding="utf-8")

    verifier_call = "python3 ./verify_upstream_dependencies.py"
    managed_verifier_call = "python3 ./verify_managed_components.py"
    host_configure_call = "cmake -S tests -B build-host-tests"
    host_build_call = "cmake --build build-host-tests"
    host_test_call = "ctest --test-dir build-host-tests --output-on-failure"
    build_call = 'idf.py -B "$firmware_verify_dir/build"'
    assert verifier_call in gate
    assert managed_verifier_call in gate
    assert host_configure_call in gate
    assert host_build_call in gate
    assert host_test_call in gate
    assert build_call in gate
    assert (
        gate.index(verifier_call)
        < gate.index(managed_verifier_call)
        < gate.index(host_configure_call)
        < gate.index(host_build_call)
        < gate.index(host_test_call)
        < gate.index(build_call)
    )
