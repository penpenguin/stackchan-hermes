from __future__ import annotations

import importlib.util
import json
import re
import struct
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FONT_CMAKE = ROOT / "firmware/cmake/release_fonts.cmake"


def test_release_build_compiles_only_reviewed_font_sources(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    generated = tmp_path / "generated"
    (upstream / "src/emoji").mkdir(parents=True)
    generated.mkdir()
    approved = [
        "src/cbin_font.c",
        "src/font_awesome.c",
        "src/font_emoji_32.c",
        "src/font_emoji_64.c",
        "src/emoji/emoji_1f642_64.c",
    ]
    for index, relative in enumerate(approved):
        (upstream / relative).write_text(f"int approved_{index}(void) {{ return 1; }}\n")
    for relative in ("src/font_puhui_basic_20_4.c", "src/font_awesome_30_4.c"):
        (upstream / relative).write_text('#error "unreviewed font reached compiler"\n')
    (generated / "stackchan_text_20.c").write_text("int replacement(void) { return 1; }\n")
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(release_font_test C)\n"
        f'file(GLOB_RECURSE ORIGINAL "{upstream}/src/*.c")\n'
        "add_library(fonts STATIC ${ORIGINAL})\n"
        f'include("{FONT_CMAKE}")\n'
        f'stackchan_use_release_fonts(fonts "{upstream}" "{generated}")\n'
    )

    configured = subprocess.run(
        ["cmake", "-S", str(tmp_path), "-B", str(tmp_path / "build")],
        capture_output=True,
        text=True,
    )
    assert configured.returncode == 0, configured.stdout + configured.stderr
    built = subprocess.run(
        ["cmake", "--build", str(tmp_path / "build")], capture_output=True, text=True
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assert (tmp_path / "build/libfonts.a").is_file()


def test_font_generation_rejects_changed_input_before_running_converter(tmp_path: Path) -> None:
    script = ROOT / "firmware/tools/generate_release_fonts.py"
    spec = importlib.util.spec_from_file_location("generate_release_fonts", script)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    source = tmp_path / "font.ttf"
    source.write_bytes(b"reviewed font")
    inputs = {"font.ttf": {"sha256": sha256(source.read_bytes()).hexdigest()}}
    generator.verify_inputs(tmp_path, inputs)

    source.write_bytes(b"different font")
    with pytest.raises(ValueError, match=r"font\.ttf"):
        generator.verify_inputs(tmp_path, inputs)


def test_icon_generation_refuses_a_missing_material_glyph() -> None:
    script = ROOT / "firmware/tools/generate_release_fonts.py"
    spec = importlib.util.spec_from_file_location("generate_release_fonts", script)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    with pytest.raises(ValueError, match="wifi_1_bar"):
        generator.icon_ranges([{"codepoint": "f6aa", "material": "wifi_1_bar"}], {"wifi": "e63e"})
    assert (
        generator.icon_ranges(
            [{"codepoint": "f6aa", "material": "wifi_1_bar"}], {"wifi_1_bar": "e4ca"}
        )
        == "0xe4ca=>0xf6aa"
    )


def test_distributed_fonts_cover_text_and_distinct_device_status_icons() -> None:
    fonts = ROOT / "firmware/release-fonts"
    data = (fonts / "cbin/font_stackchan_common_20_4.bin").read_bytes()
    descriptor = struct.unpack_from("<I", data, 24)[0]
    cmaps = descriptor + struct.unpack_from("<I", data, descriptor + 8)[0]
    count = struct.unpack_from("<H", data, descriptor + 18)[0] & 0x1FF
    covered = set()
    for index in range(count):
        start, length, _, unicode_list, offsets, size, kind = struct.unpack_from(
            "<IHHIIHB", data, cmaps + index * 20
        )
        if kind in (1, 3):
            covered.update(
                start + value
                for value in struct.unpack_from(f"<{size}H", data, cmaps + unicode_list)
            )
        elif kind == 2:
            covered.update(range(start, start + length))
        else:
            covered.update(
                start + offset
                for offset in range(length)
                if offset == 0 or data[cmaps + offsets + offset] != 0
            )
    assert set(map(ord, "日本語の表示・漢字かなカナ、。\uff01\uff1fHelloสวัสดี")) <= covered
    requested = json.loads((fonts / "font-codepoints.json").read_text())
    assert {cp for codepoints in requested.values() for cp in codepoints} <= covered

    icons = json.loads((fonts / "icons.json").read_text())
    expected = {int(icon["codepoint"], 16) for icon in icons}
    for filename in ("font_awesome_20_4.c", "font_awesome_30_4.c", "font_awesome_30_1.c"):
        rendered = {
            int(value, 16)
            for value in re.findall(r"U\+([0-9A-Fa-f]+)", (fonts / "src" / filename).read_text())
        }
        assert expected <= rendered
    by_name = {icon["name"]: icon["material"] for icon in icons}
    assert len({by_name[name] for name in ("wifi", "wifi_fair", "wifi_weak", "wifi_slash")}) == 4
    battery_states = ("full", "three_quarters", "half", "quarter", "empty", "bolt")
    assert len({by_name[f"battery_{state}"] for state in battery_states}) == 6
