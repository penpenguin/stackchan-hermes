# Image fixtures

Only synthetic, generated, or explicitly redistributable JPEG fixtures may be added. Never commit
user photos. `stackchan_simulator.fixtures.generate_synthetic_jpeg()` creates the Phase 2 320×240
capture fixture at runtime from ffmpeg's built-in `color` source, so no image bytes are tracked.
