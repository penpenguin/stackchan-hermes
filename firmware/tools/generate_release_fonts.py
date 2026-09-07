#!/usr/bin/env python3
"""Generate StackChan fonts from reviewed inputs; never consume upstream glyph data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from hashlib import sha256
from pathlib import Path


def verify_inputs(directory: Path, inputs: dict[str, dict[str, str]]) -> None:
    for name, record in inputs.items():
        if sha256((directory / name).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Font input differs from the reviewed pin: {name}")


def icon_ranges(icons: list[dict[str, str]], material: dict[str, str]) -> str:
    ranges = []
    for icon in icons:
        name = icon["material"]
        if name not in material:
            raise ValueError(f"Material icon is missing: {name}")
        ranges.append(f"0x{material[name]}=>0x{icon['codepoint']}")
    return ",".join(ranges)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--converter", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    firmware = Path(__file__).resolve().parents[1]
    output = firmware / "release-fonts"
    lock = json.loads((output / "input-lock.json").read_text())
    inputs = args.inputs.resolve()
    converter = args.converter.resolve()
    inputs.mkdir(parents=True, exist_ok=True)
    if args.download:
        for name, record in lock["inputs"].items():
            destination = inputs / name
            if not destination.exists():
                with urllib.request.urlopen(record["url"], timeout=90) as response:
                    data = response.read()
                if sha256(data).hexdigest() != record["sha256"]:
                    raise ValueError(f"Downloaded font differs from the pin: {name}")
                destination.write_bytes(data)
    verify_inputs(inputs, lock["inputs"])
    commit = subprocess.check_output(
        ["git", "-C", str(converter), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != lock["converter"]["commit"]:
        raise ValueError("Font converter commit differs from the reviewed pin")
    subprocess.run(["git", "-C", str(converter), "diff", "--quiet", "HEAD"], check=True)
    expected_lock = lock["converter"]["package_lock_sha256"]
    if sha256((converter / "package-lock.json").read_bytes()).hexdigest() != expected_lock:
        raise ValueError("Font converter dependency lock differs from the reviewed pin")

    for directory in (output / "src", output / "cbin"):
        directory.mkdir(exist_ok=True)
    icons = json.loads((output / "icons.json").read_text())
    material = dict(
        line.split()
        for line in (inputs / "MaterialIcons-Regular.codepoints").read_text().splitlines()
    )
    mapped_icons = icon_ranges(icons, material)
    font_charsets = json.loads((output / "font-codepoints.json").read_text())
    outputs = []

    def convert(destination: Path, size: int, bpp: int, fonts: list[str], license: str) -> None:
        command = [
            "node",
            str(converter / "lv_font_conv.js"),
            "--size",
            str(size),
            "--bpp",
            str(bpp),
            "--no-compress",
            "--no-prefilter",
            "--force-fast-kern-format",
            *fonts,
            "--format",
            "cbin" if destination.suffix == ".bin" else "lvgl",
            "-o",
            str(destination),
        ]
        if destination.suffix == ".c":
            command.extend(["--lv-include", "lvgl.h", "--lv-font-name", destination.stem])
        else:
            # The pinned cbin writer cannot encode the combined fonts' kerning classes.
            # Glyph advances remain intact; disable pair kerning for this asset font.
            command.append("--no-kerning")
        subprocess.run(command, cwd=inputs, check=True)
        if destination.suffix == ".c":
            text = destination.read_text()
            text = re.sub(r"\A/\*{3,}.*?\*/\s*", "", text, count=1, flags=re.DOTALL)
            header = (
                f"/* SPDX-License-Identifier: {license} AND MIT\n"
                " * Generated for StackChan: subset, rasterized and (icons only) remapped.\n"
                " * Input versions, rights holders and notices: firmware/release-fonts/README.md.\n"
                " * Reproduce with firmware/tools/generate_release_fonts.py.\n"
                " */\n"
            )
            destination.write_text(header + text.rstrip() + "\n")
        outputs.append(
            {
                "path": destination.relative_to(firmware).as_posix(),
                "sha256": sha256(destination.read_bytes()).hexdigest(),
                "size": destination.stat().st_size,
                "license": license,
            }
        )

    for size, bpp in ((20, 4), (30, 4), (30, 1)):
        convert(
            output / "src" / f"font_awesome_{size}_{bpp}.c",
            size,
            bpp,
            ["--font", "MaterialIcons-Regular.ttf", "--range", mapped_icons],
            "Apache-2.0",
        )
    convert(
        output / "src/font_stackchan_basic_20_4.c",
        20,
        4,
        ["--font", "NotoSans-Regular.ttf", "--range", "0x20-0x7e,0xa0-0xff"],
        "OFL-1.1",
    )
    fonts = []
    for name, codepoints in font_charsets.items():
        if codepoints:
            ranges = ",".join(f"0x{cp:x}" for cp in codepoints)
            fonts.extend(["--font", name, "--range", ranges])
    convert(output / "cbin/font_stackchan_common_20_4.bin", 20, 4, fonts, "OFL-1.1")
    convert(
        firmware / "main/assets/fonts/MontserratSemiBold26.c",
        26,
        2,
        ["--font", "Montserrat-SemiBold.ttf", "--range", "0x20-0x7e"],
        "OFL-1.1",
    )
    (output / "outputs.json").write_text(json.dumps(outputs, indent=2) + "\n")
    print(f"Generated {len(outputs)} reviewed fonts")


if __name__ == "__main__":
    main()
