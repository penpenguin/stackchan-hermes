from __future__ import annotations

import importlib.util
import json
import re
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


def test_incremental_asset_build_removes_deleted_cloud_icons(tmp_path: Path) -> None:
    cmake = (ROOT / "firmware/main/CMakeLists.txt").read_text()
    build_function = re.search(
        r"function\(build_default_assets_bin\).*?endfunction\(\)", cmake, re.DOTALL
    )
    assert build_function is not None
    (tmp_path / "main").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "cbin").mkdir()
    (tmp_path / "cbin/font_stackchan_common_20_4.bin").write_bytes(b"font")
    (tmp_path / "sdkconfig").write_text("")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "local.bin").write_bytes(b"local")
    cloud = assets / "cloud.bin"
    cloud.write_bytes(b"cloud")
    (tmp_path / "scripts/build_default_assets.py").write_text(
        "import argparse\nfrom pathlib import Path\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--output')\np.add_argument('--extra_files')\n"
        "a, _ = p.parse_known_args()\n"
        "Path(a.output).write_text(','.join(sorted(\n"
        "    f.name for f in Path(a.extra_files).iterdir())))\n"
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\nproject(asset_test NONE)\n"
        f'set(XIAOZHI_MAIN_DIR "{tmp_path}/main")\n'
        f'set(SDKCONFIG "{tmp_path}/sdkconfig")\n'
        f'set(STACKCHAN_RELEASE_FONTS "{tmp_path}")\n'
        f'set(DEFAULT_ASSETS_EXTRA_FILES "{assets}")\n'
        + build_function.group()
        + "\nbuild_default_assets_bin()\n"
    )
    build = tmp_path / "build"
    subprocess.run(["cmake", "-S", str(tmp_path), "-B", str(build)], check=True)
    subprocess.run(["cmake", "--build", str(build)], check=True)
    assert (build / "generated_assets.bin").read_text() == "cloud.bin,local.bin"
    cloud.unlink()
    subprocess.run(["cmake", "--build", str(build)], check=True)
    assert (build / "generated_assets.bin").read_text() == "local.bin"


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


@pytest.mark.parametrize(
    "source",
    [
        "xiaozhi-esp32/main/application.cc",
        "xiaozhi-esp32/main/ota.cc",
        "xiaozhi-esp32/main/mcp_server.cc",
        "xiaozhi-esp32/main/protocols/mqtt_protocol.cc",
        "xiaozhi-esp32/main/protocols/websocket_protocol.cc",
        "xiaozhi-esp32/main/boards/common/esp32_camera.cc",
        "main/hal/hal_ws_avatar.cpp",
        "main/hal/hal_account.cpp",
        "main/hal/hal_ezdata.cpp",
        "main/hal/utils/ota/ota.c",
        "main/apps/app_app_center/app_app_center.cpp",
        "managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc",
        "managed_components/78__esp-ml307/src/esp/esp_mqtt.cc",
        "managed_components/78__esp-ml307/src/ml307/ml307_mqtt.cc",
    ],
)
def test_release_rejects_legacy_cloud_translation_units(source: str) -> None:
    with pytest.raises(ValueError, match="cloud"):
        _verifier().verify_network_sources([{"file": str(ROOT / "firmware" / source)}])


def test_release_allows_local_hardware_and_bridge_sources() -> None:
    _verifier().verify_network_sources(
        [
            {"file": str(ROOT / "firmware" / source)}
            for source in (
                "main/hal/stackchan_bridge_camera.cpp",
                "main/hal/board/stackchan_camera.cc",
                "xiaozhi-esp32/main/audio/audio_service.cc",
                "components/stackchan_bridge_client/web_socket.cpp",
            )
        ]
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "Application::Initialize()",
        "Ota::CheckVersion()",
        "MqttProtocol::Start()",
        "WebsocketProtocol::Start()",
        "McpServer::SendMessage()",
        "Hal::startEzDataService()",
        "StackChanCamera::Explain(std::string const&)",
        "Assets::Download(std::string)",
        "EspMqtt::Publish(std::string)",
        "esp_mqtt_client_publish",
    ],
)
def test_release_rejects_linked_cloud_symbols(symbol: str) -> None:
    with pytest.raises(ValueError, match="cloud"):
        _verifier().verify_network_symbols("42001000 T " + symbol)


def test_release_allows_local_audio_camera_and_bridge_symbols() -> None:
    _verifier().verify_network_symbols(
        "42001000 T AudioService::PlaySound()\n42002000 T StackChanCamera::Capture()\n"
        "42003000 T stackchan::bridge_client::BridgeClient::update()\n"
    )


def test_firmware_source_selection_excludes_cloud_implementations() -> None:
    firmware = ROOT / "firmware"
    cmake = (firmware / "main/CMakeLists.txt").read_text()
    sources = [
        {"file": str(path)}
        for path in (firmware / "main").rglob("*")
        if path.suffix in {".c", ".cc", ".cpp"}
    ]
    for path in re.findall(r'"([^"\n]+\.(?:cc|cpp|c))"', cmake):
        if path.startswith("${XIAOZHI_MAIN_DIR}/"):
            path = path.replace("${XIAOZHI_MAIN_DIR}", str(firmware / "xiaozhi-esp32/main"))
        elif not path.startswith("$"):
            path = str(firmware / "xiaozhi-esp32/main" / path)
        sources.append({"file": path})
    _verifier().verify_network_sources(sources)


@pytest.mark.parametrize(
    "forbidden", [b"ota_url\0", b"boot_ai\0", b"api.tenclass.net", b"47.113.125.164"]
)
def test_release_rejects_old_cloud_configuration_in_elf(forbidden: bytes) -> None:
    with pytest.raises(ValueError, match="cloud"):
        _verifier().verify_network_strings(b"ELF content\0" + forbidden)
