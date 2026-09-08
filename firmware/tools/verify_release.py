#!/usr/bin/env python3
"""Check the actual CoreS3 release inputs before bundling binaries and notices."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path


def read_assets(data: bytes) -> dict[str, bytes]:
    if len(data) < 12:
        raise ValueError("Asset header length is invalid")
    count, checksum, length = struct.unpack_from("<III", data)
    if length != len(data) - 12 or count * 44 > length:
        raise ValueError("Asset length is invalid")
    if sum(data[12:]) & 0xFFFF != checksum:
        raise ValueError("Asset checksum differs")
    payload_start = 12 + count * 44
    assets = {}
    for index in range(count):
        raw_name, size, offset, _, _ = struct.unpack_from("<32sIIHH", data, 12 + index * 44)
        name = raw_name.split(b"\0", 1)[0].decode("utf-8")
        start = payload_start + offset
        if start + 2 + size > len(data) or data[start : start + 2] != b"\x5a\x5a":
            raise ValueError(f"Asset bounds or marker is invalid: {name}")
        if not name or Path(name).name != name or name in assets:
            raise ValueError(f"Asset name is invalid: {name}")
        assets[name] = data[start + 2 : start + 2 + size]
    return assets


def verify_font_sources(commands: list[dict[str, str]], firmware: Path) -> None:
    upstream = (firmware / "managed_components/78__xiaozhi-fonts/src").resolve()
    helpers = {"cbin_font.c", "font_awesome.c", "font_emoji_32.c", "font_emoji_64.c"}
    for command in commands:
        source = Path(command["file"]).resolve()
        if source.is_relative_to(upstream):
            relative = source.relative_to(upstream)
            if relative.as_posix() not in helpers and relative.parent != Path("emoji"):
                raise ValueError(f"Unreviewed upstream glyph reached compilation: {relative}")


def verify_asset_files(assets: dict[str, bytes], sources: dict[str, Path]) -> None:
    for name, path in sources.items():
        if assets.get(name) != path.read_bytes():
            raise ValueError(f"Release asset differs from reviewed source: {name}")


def verify_models(data: bytes, model_root: Path) -> list[dict[str, str | int]]:
    def name_at(offset: int) -> str:
        name = data[offset : offset + 32].split(b"\0", 1)[0].decode("ascii")
        if not name or name in {".", ".."} or Path(name).name != name:
            raise ValueError(f"Invalid model name: {name}")
        return name

    if len(data) < 4:
        raise ValueError("Invalid model header")
    count = struct.unpack_from("<I", data)[0]
    cursor = 4
    entries = []
    for _ in range(count):
        if cursor + 36 > len(data):
            raise ValueError("Invalid model header length")
        model = name_at(cursor)
        file_count = struct.unpack_from("<I", data, cursor + 32)[0]
        cursor += 36
        roots = [path for path in model_root.rglob(model) if path.is_dir()]
        if len(roots) != 1:
            raise ValueError(f"Model must have one reviewed source: {model}")
        for _ in range(file_count):
            if cursor + 40 > len(data):
                raise ValueError("Invalid model file header length")
            name = name_at(cursor)
            offset, size = struct.unpack_from("<II", data, cursor + 32)
            cursor += 40
            entries.append((model, name, offset, size, roots[0] / name))
    result = []
    expected_offset = cursor
    for model, name, offset, size, source in entries:
        contents = data[offset : offset + size]
        if offset != expected_offset or len(contents) != size or contents != source.read_bytes():
            raise ValueError(f"Model bytes differ from reviewed source: {model}/{name}")
        result.append(
            {
                "path": f"{model}/{name}",
                "sha256": hashlib.sha256(contents).hexdigest(),
                "size": size,
            }
        )
        expected_offset += size
    if expected_offset != len(data):
        raise ValueError("Unexpected trailing model data")
    return result


def file_record(path: Path) -> dict[str, str | int]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def verify_flash_files(files: dict[str, str], build: Path) -> list[dict[str, str | int]]:
    expected = {
        "0x0": "bootloader/bootloader.bin",
        "0x8000": "partition_table/partition-table.bin",
        "0xd000": "ota_data_initial.bin",
        "0x20000": "stack-chan.bin",
        "0xa00000": "generated_assets.bin",
    }
    if files != expected:
        raise ValueError("Unexpected flash files: only the five reviewed CoreS3 images are allowed")
    return [
        {"offset": offset, "path": name, **file_record(build / name)}
        for offset, name in files.items()
    ]


def verify_notices(record: object, root: Path) -> None:
    if isinstance(record, dict):
        if "text" in record and "sha256" in record:
            path = root / record["text"]
            if file_record(path)["sha256"] != record["sha256"]:
                raise ValueError(f"Notice hash differs: {record['text']}")
        for value in record.values():
            verify_notices(value, root)
    elif isinstance(record, list):
        for value in record:
            verify_notices(value, root)


def verify_network_sources(commands: list[dict]) -> None:
    """Reject legacy senders even if the linker would discard their symbols."""
    forbidden = (
        "/main/application.cc",
        "/main/ota.cc",
        "/main/mcp_server.cc",
        "/main/protocols/",
        "/audio/processors/audio_debugger.cc",
        "/boards/common/esp32_camera.cc",
        "/boards/common/esp_video.cc",
        "/boards/common/press_to_talk_mcp_tool.cc",
        "/hal/hal_ws_avatar.cpp",
        "/hal/hal_account.cpp",
        "/hal/hal_ezdata.cpp",
        "/hal/hal_app_center.cpp",
        "/hal/hal_ota.cpp",
        "/hal/hal_mcp.cpp",
        "/utils/ota/",
        "/utils/ezdata/",
        "/utils/server/",
        "/apps/app_ai_agent/",
        "/apps/app_app_center/",
        "/apps/app_ezdata/",
        "/managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc",
        "/src/esp/esp_network.cc",
        "/src/esp/esp_mqtt.cc",
        "/src/esp/esp_udp.cc",
        "/src/ml307/",
        "/src/ec801e/",
        "/wifi_configuration.html.S",
    )
    for command in commands:
        source = Path(command["file"]).as_posix()
        if any(part in source for part in forbidden):
            raise ValueError(f"Legacy cloud source compiled: {source}")


def verify_network_symbols(symbols: str) -> None:
    forbidden = (
        "Application::",
        "Ota::",
        "MqttProtocol::",
        "WebsocketProtocol::",
        "McpServer::",
        "Hal::startEzDataService",
        "Hal::startXiaozhi",
        "Hal::startWebSocketAvatarService",
        "Hal::updateAccountInfo",
        "Hal::unbindAccount",
        "Hal::updateFirmware",
        "Hal::launchApp",
        "StackChanCamera::Explain",
        "StackChanCamera::SetExplainUrl",
        "Assets::Download",
        "AudioDebugger::",
        "EspMqtt::",
        "esp_mqtt_client_",
        "ezdata_",
        "ota_update",
    )
    for line in symbols.splitlines():
        if any(symbol in line for symbol in forbidden):
            raise ValueError(f"Legacy cloud symbol linked: {line.strip()}")


def verify_network_strings(elf: bytes) -> None:
    for forbidden in (b"ota_url\0", b"boot_ai\0", b"api.tenclass.net", b"47.113.125.164"):
        if forbidden in elf:
            raise ValueError(f"Legacy cloud configuration linked: {forbidden!r}")


def verify_build(build: Path, root: Path) -> dict:
    firmware = root / "firmware"
    project = json.loads((build / "project_description.json").read_text())
    if project["target"] != "esp32s3":
        raise ValueError("This release review covers esp32s3 only")
    config = Path(project["config_file"]).read_text().splitlines()
    for required in (
        "CONFIG_BOARD_TYPE_M5STACK_STACK_CHAN=y",
        "CONFIG_STACKCHAN_HERMES_HEAD_MOTION_LOCK=y",
        "CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
        'CONFIG_STACKCHAN_HERMES_DEFAULT_BRIDGE_URL=""',
    ):
        if required not in config:
            raise ValueError(f"Release configuration differs: {required}")
    records = {}
    for path in sorted((root / "LICENSES").glob("*.json")):
        records[path.stem] = json.loads(path.read_text())
        verify_notices(records[path.stem], root)
    managed = records["firmware-managed"]
    if file_record(firmware / "dependencies.lock")["sha256"] != managed["lock_sha256"]:
        raise ValueError("Managed dependency lock differs from license review")
    if any(not component["notices"] for component in managed["components"]):
        raise ValueError("A managed component is missing its notices")
    for script in ("verify_upstream_dependencies.py", "verify_managed_components.py"):
        subprocess.run([sys.executable, str(firmware / script)], check=True)
    sdk = Path(project["idf_path"])
    sdk_record = records["firmware-sdk"]
    commit = subprocess.check_output(
        ["git", "-C", str(sdk), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != sdk_record["sdk_commit"] or subprocess.check_output(
        ["git", "-C", str(sdk), "status", "--porcelain"], text=True
    ):
        raise ValueError("SDK differs from the reviewed commit")
    outputs = json.loads((firmware / "release-fonts/outputs.json").read_text())
    if outputs != records["firmware-fonts"]["outputs"]:
        raise ValueError("Generated font manifest differs from license review")
    commands = json.loads((build / "compile_commands.json").read_text())
    verify_font_sources(commands, firmware)
    verify_network_sources(commands)
    verify_network_strings((build / "stack-chan.elf").read_bytes())
    wifi_manifest = json.loads((firmware / "patches/esp-wifi-connect.json").read_text())
    for record in wifi_manifest["files"]:
        path = build / "local-wifi" / record["output"]
        if file_record(path)["sha256"] != record["output_sha256"]:
            raise ValueError("Local Wi-Fi output differs from reviewed patch")
    nm = Path(project["c_compiler"]).with_name("xtensa-esp32s3-elf-nm")
    verify_network_symbols(
        subprocess.check_output(
            [str(nm), "--demangle", "--defined-only", str(build / "stack-chan.elf")], text=True
        )
    )
    compiled = {Path(command["file"]).resolve() for command in commands}
    for output in outputs:
        path = firmware / output["path"]
        if file_record(path)["sha256"] != output["sha256"]:
            raise ValueError(f"Generated font hash differs: {output['path']}")
        if path.suffix == ".c" and path.resolve() not in compiled:
            raise ValueError(f"Reviewed font was not compiled: {output['path']}")
    assets = read_assets((build / "generated_assets.bin").read_bytes())
    index = json.loads(assets["index.json"])
    font_name = "font_stackchan_common_20_4.bin"
    if index["text_font"] != font_name or index["srmodels"] != "srmodels.bin":
        raise ValueError("Release asset index references an unreviewed font or model")
    sources = {font_name: firmware / "release-fonts/cbin" / font_name}
    sources.update(
        {
            path.name: path
            for path in (firmware / "main/assets/assets_bin").iterdir()
            if path.is_file()
        }
    )
    emoji_dir = firmware / "managed_components/78__xiaozhi-fonts/png/twemoji_64"
    for entry in index["emoji_collection"]:
        name = entry["file"]
        if Path(name).name != name:
            raise ValueError("Invalid emoji path")
        sources[name] = emoji_dir / name
    if set(assets) != set(sources) | {"index.json", "srmodels.bin"}:
        raise ValueError("Release contains unexpected assets")
    verify_asset_files(assets, sources)
    models = verify_models(
        assets["srmodels.bin"], firmware / "managed_components/espressif__esp-sr/model"
    )
    archives = []
    toolchain = Path(project["c_compiler"]).parents[2]
    for target, mapfile in (
        ("app", build / "stack-chan.map"),
        ("bootloader", build / "bootloader/bootloader.map"),
    ):
        prefix = mapfile.read_text().split("Discarded input sections", 1)[0]
        for name in sorted(set(re.findall(r"^([^\s]+\.a)\(", prefix, re.MULTILINE))):
            path = Path(name)
            if not path.is_absolute():
                path = mapfile.parent / path
            path = path.resolve()
            for base, label in (
                (build, "build"),
                (firmware, "firmware"),
                (sdk, "esp-idf"),
                (toolchain, "toolchain"),
            ):
                if path.is_relative_to(base):
                    portable = label + "/" + path.relative_to(base).as_posix()
                    break
            else:
                raise ValueError(f"Unreviewed archive location: {path.name}")
            archives.append({"target": target, "path": portable, **file_record(path)})
    expected_archives = {(row["target"], row["path"]): row for row in sdk_record["linked_archives"]}
    if {(row["target"], row["path"]) for row in archives} != set(expected_archives):
        raise ValueError("Linked archive set differs from license review")
    for row in archives:
        if (
            not row["path"].startswith("build/")
            and row["sha256"] != expected_archives[(row["target"], row["path"])]["sha256"]
        ):
            raise ValueError(f"Prebuilt archive differs: {row['path']}")
    flasher = json.loads((build / "flasher_args.json").read_text())
    return {
        "schema_version": 1,
        "target": project["target"],
        "sdk_commit": commit,
        "flash_settings": flasher["flash_settings"],
        "flash_files": verify_flash_files(flasher["flash_files"], build),
        "assets": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in sorted(assets.items())
        ],
        "models": models,
        "linked_archives": archives,
        "hardware_tested": False,
        "legacy_cloud_sources_and_symbols_absent": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument(
        "--output", type=Path, help="Write the verified binaries and notices to a ZIP"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        build = args.build.resolve()
        report = verify_build(build, root)
        if args.output:
            docs = [
                root / "README.md",
                root / "LICENSE",
                root / "THIRD_PARTY_NOTICES.md",
                root / "firmware/LICENSE",
                root / "firmware/UPSTREAM.md",
                root / "firmware/upstream-lock.json",
                root / "firmware/release-fonts/README.md",
                root / "docs/license-audit.md",
                root / "docs/licensing.md",
                root / "docs/hardware-setup.md",
                root / "docs/network-policy.md",
                root / "docs/operations.md",
            ]
            docs.extend(sorted(path for path in (root / "LICENSES").rglob("*") if path.is_file()))
            docs.extend(sorted((root / "docs/license-inventory").glob("*")))
            docs.extend(sorted((root / "firmware/release-fonts").glob("*.json")))
            docs.extend(sorted((root / "firmware/patches").glob("*")))
            report["notice_files"] = [
                {"path": path.relative_to(root).as_posix(), **file_record(path)} for path in docs
            ]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for entry in report["flash_files"]:
                    archive.write(build / entry["path"], entry["path"])
                for path in docs:
                    archive.write(path, path.relative_to(root).as_posix())
                archive.writestr(
                    "release-manifest.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                archive.writestr(
                    "README.txt",
                    "StackChan Hermes / M5Stack CoreS3 (ESP32-S3)\n\n"
                    "Keep LICENSE, THIRD_PARTY_NOTICES.md and LICENSES/ with these binaries.\n"
                    "Some Espressif libraries and models are restricted to Espressif products.\n"
                    "See docs/license-audit.md for the review scope.\n"
                    "Local apps and explicitly configured Hermes Bridge only; updates use USB.\n"
                    "See docs/network-policy.md for destinations and local setup.\n"
                    "release-manifest.json records image offsets, sizes and SHA-256 hashes.\n"
                    "This build has not been flashed or tested on hardware.\n"
                    "Before flashing, follow the project's docs/hardware-setup.md "
                    "backup and serial-port checks.\n",
                )
            print(f"Release ZIP: {args.output}")
        print(
            f"Verified CoreS3 release: {len(report['assets'])} assets, "
            f"{len(report['models'])} model files, "
            f"{len(report['linked_archives'])} linked archives, 5 flash images"
        )
        return 0
    except (OSError, ValueError, KeyError, struct.error, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
