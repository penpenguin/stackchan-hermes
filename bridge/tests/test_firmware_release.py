from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _verifier() -> ModuleType:
    path = ROOT / "firmware/tools/verify_release.py"
    spec = importlib.util.spec_from_file_location("verify_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_asset_reader_checks_payload_integrity_and_bounds() -> None:
    verifier = _verifier()
    entry = struct.pack("<32sIIHH", b"font.bin", 4, 0, 0, 0)
    contents = entry + b"\x5a\x5aFONT"
    data = struct.pack("<III", 1, sum(contents) & 0xFFFF, len(contents)) + contents
    assert verifier.read_assets(data) == {"font.bin": b"FONT"}

    with pytest.raises(ValueError, match="checksum"):
        verifier.read_assets(data[:-1] + b"X")
    with pytest.raises(ValueError, match="length"):
        verifier.read_assets(data[:-1])


def test_release_rejects_upstream_glyphs_even_when_replacement_is_also_compiled() -> None:
    verifier = _verifier()
    firmware = ROOT / "firmware"
    replacement = firmware / "release-fonts/src/font_awesome_20_4.c"
    old = firmware / "managed_components/78__xiaozhi-fonts/src/font_awesome_20_4.c"
    verifier.verify_font_sources([{"file": str(replacement)}], firmware)
    with pytest.raises(ValueError, match="upstream glyph"):
        verifier.verify_font_sources([{"file": str(replacement)}, {"file": str(old)}], firmware)


def test_release_checks_actual_asset_bytes_against_reviewed_source(tmp_path: Path) -> None:
    verifier = _verifier()
    font = tmp_path / "font.bin"
    font.write_bytes(b"reviewed glyphs")
    verifier.verify_asset_files({"font.bin": b"reviewed glyphs"}, {"font.bin": font})
    with pytest.raises(ValueError, match=r"font\.bin"):
        verifier.verify_asset_files({"font.bin": b"old glyphs"}, {"font.bin": font})


def test_release_models_must_match_the_locked_component_bytes(tmp_path: Path) -> None:
    verifier = _verifier()
    model = tmp_path / "wakenet_model" / "test_model"
    model.mkdir(parents=True)
    (model / "weights").write_bytes(b"model weights")
    header_size = 4 + 36 + 40
    data = (
        struct.pack("<I32sI32sII", 1, b"test_model", 1, b"weights", header_size, 13)
        + b"model weights"
    )
    assert verifier.verify_models(data, tmp_path)[0]["path"] == "test_model/weights"
    with pytest.raises(ValueError, match="weights"):
        verifier.verify_models(data[:-1] + b"X", tmp_path)


def test_release_rejects_personal_nvs_or_unexpected_flash_inputs(tmp_path: Path) -> None:
    verifier = _verifier()
    files = {
        "0x0": "bootloader/bootloader.bin",
        "0x8000": "partition_table/partition-table.bin",
        "0xd000": "ota_data_initial.bin",
        "0x20000": "stack-chan.bin",
        "0xa00000": "generated_assets.bin",
    }
    for name in files.values():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"build output")
    assert len(verifier.verify_flash_files(files, tmp_path)) == 5
    with pytest.raises(ValueError, match="flash files"):
        verifier.verify_flash_files({**files, "0x9000": "personal-nvs.bin"}, tmp_path)


def test_release_rejects_a_changed_notice(tmp_path: Path) -> None:
    verifier = _verifier()
    notice = tmp_path / "notice.txt"
    notice.write_text("changed terms")
    record = {"notices": [{"text": "notice.txt", "sha256": "0" * 64}]}
    with pytest.raises(ValueError, match=r"notice\.txt"):
        verifier.verify_notices(record, tmp_path)


def test_release_command_rejects_a_different_chip(tmp_path: Path) -> None:
    (tmp_path / "project_description.json").write_text(json.dumps({"target": "esp32"}))
    result = subprocess.run(
        [sys.executable, str(ROOT / "firmware/tools/verify_release.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "esp32s3" in result.stderr


def test_firmware_gate_verifies_the_built_release_before_temporary_files_are_removed() -> None:
    gate = (ROOT / "scripts/verify-firmware.sh").read_text()
    assert 'python3 tools/verify_release.py "$firmware_verify_dir/build"' in gate
