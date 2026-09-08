from __future__ import annotations

import importlib.util
import json
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def prepare(firmware: Path, output: Path) -> None:
    path = ROOT / "firmware/tools/prepare_local_wifi.py"
    spec = importlib.util.spec_from_file_location("prepare_local_wifi", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare(firmware, output)


@pytest.fixture
def wifi_firmware(tmp_path: Path) -> Path:
    firmware = tmp_path / "firmware"
    component = "managed_components/test-wifi"
    relative = "assets/wifi_configuration.html"
    original = '<input id="ssid">\n<input id="password">\n<input id="ota_url">\n'
    patched = '<input id="ssid">\n<input id="password">\n'
    source = firmware / component / relative
    source.parent.mkdir(parents=True)
    source.write_text(original)
    patch = "".join(
        unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )
    patches = firmware / "patches"
    patches.mkdir()
    (patches / "esp-wifi-connect.patch").write_text(patch)
    (patches / "esp-wifi-connect.json").write_text(
        json.dumps(
            {
                "component": component,
                "patch_sha256": sha256(patch.encode()).hexdigest(),
                "files": [
                    {
                        "source": relative,
                        "output": "assets/wifi_local.html",
                        "source_sha256": sha256(original.encode()).hexdigest(),
                        "output_sha256": sha256(patched.encode()).hexdigest(),
                    }
                ],
            }
        )
    )
    return firmware


def test_wifi_patch_writes_renamed_output_without_changing_source(
    wifi_firmware: Path, tmp_path: Path
) -> None:
    source = wifi_firmware / "managed_components/test-wifi/assets/wifi_configuration.html"
    original = source.read_bytes()
    output = tmp_path / "output"

    prepare(wifi_firmware, output)

    assert (output / "assets/wifi_local.html").read_text() == (
        '<input id="ssid">\n<input id="password">\n'
    )
    assert not (output / "assets/wifi_configuration.html").exists()
    assert source.read_bytes() == original


def test_wifi_patch_rejects_changed_source_before_writing_output(tmp_path: Path) -> None:
    firmware = tmp_path / "firmware"
    (firmware / "patches").mkdir(parents=True)
    manifest_path = ROOT / "firmware/patches/esp-wifi-connect.json"
    manifest = json.loads(manifest_path.read_text())
    (firmware / "patches/esp-wifi-connect.json").write_text(manifest_path.read_text())
    patch = ROOT / "firmware/patches/esp-wifi-connect.patch"
    (firmware / "patches/esp-wifi-connect.patch").write_bytes(patch.read_bytes())
    for record in manifest["files"]:
        source = firmware / manifest["component"] / record["source"]
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("unexpected source")
    with pytest.raises(ValueError, match="source"):
        prepare(firmware, tmp_path / "output")
    assert not (tmp_path / "output").exists()
