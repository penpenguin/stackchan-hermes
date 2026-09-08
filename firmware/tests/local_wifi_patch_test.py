from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tools.prepare_local_wifi import prepare

FIRMWARE = Path(__file__).resolve().parents[1]


class LocalWifiPatchTest(TestCase):
    def test_reviewed_patch_removes_ota_and_keeps_local_wifi_setup(self) -> None:
        with TemporaryDirectory(prefix="stackchan-wifi-test-") as temporary:
            output = Path(temporary)
            prepare(FIRMWARE, output)
            for name in (
                "wifi_configuration_ap.cc",
                "include/wifi_configuration_ap.h",
                "assets/wifi_local.html",
            ):
                text = (output / name).read_text()
                self.assertNotIn("ota_url", text)
                self.assertNotIn("clearOtaUrl", text)
            cpp = (output / "wifi_configuration_ap.cc").read_text()
            self.assertIn('"max_tx_power"', cpp)
            self.assertIn('"/submit"', cpp)
            html = (output / "assets/wifi_local.html").read_text()
            self.assertIn('id="ssid"', html)
            self.assertIn('id="password"', html)
