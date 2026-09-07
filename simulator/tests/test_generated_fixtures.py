from __future__ import annotations

from stackchan_simulator.fixtures import generate_synthetic_jpeg


def test_synthetic_capture_fixture_is_generated_without_a_tracked_image() -> None:
    jpeg = generate_synthetic_jpeg()

    assert jpeg.startswith(b"\xff\xd8\xff")
    assert jpeg.endswith(b"\xff\xd9")
    assert 100 < len(jpeg) < 2_097_152
