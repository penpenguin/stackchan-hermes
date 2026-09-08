from __future__ import annotations

import importlib.util
import json
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


def test_wifi_patch_removes_ota_settings_from_code_and_page(tmp_path: Path) -> None:
    prepare(ROOT / "firmware", tmp_path)
    for name in (
        "wifi_configuration_ap.cc",
        "include/wifi_configuration_ap.h",
        "assets/wifi_local.html",
    ):
        text = (tmp_path / name).read_text()
        assert "ota_url" not in text
        assert "clearOtaUrl" not in text
    cpp = (tmp_path / "wifi_configuration_ap.cc").read_text()
    assert '"max_tx_power"' in cpp
    assert '"/submit"' in cpp
    html = (tmp_path / "assets/wifi_local.html").read_text()
    assert 'id="ssid"' in html
    assert 'id="password"' in html


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
