"""Offline-Tests: python3 -I -m unittest discover -s tests"""
import io, os, sys, unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
for d in ("power-dashboard", "desk-dashboards"):
    sys.path.insert(0, os.path.join(ROOT, d))
import shelly, claude_view, git_view  # noqa: E402

SAMPLE = (b'{"a_current":1.0,"a_voltage":230.0,"a_act_power":200.0,"a_aprt_power":250.0,"a_pf":0.8,"a_freq":50.0,'
          b'"b_current":0,"b_voltage":231.0,"b_act_power":0.0,"b_aprt_power":0.0,"b_pf":0,"b_freq":50.0,'
          b'"c_current":0.5,"c_voltage":229.0,"c_act_power":100.0,"c_aprt_power":120.0,"c_pf":0.8,"c_freq":50.0,'
          b'"total_current":1.5,"total_act_power":300.0,"total_aprt_power":370.0}')


class Shelly(unittest.TestCase):
    def test_host_gueltig(self):
        for h in ("192.168.1.5", "shelly.local", "shelly-pro:80"):
            with mock.patch.dict(os.environ, {"SHELLY_HOST": h}):
                self.assertEqual(shelly.host(), h)

    def test_host_ungueltig(self):
        for h in ("a b", "x/y", "user@host", "-evil", "http://x"):
            with mock.patch.dict(os.environ, {"SHELLY_HOST": h}):
                with self.assertRaises((ValueError, KeyError, OSError)):
                    shelly.host()

    def test_fetch_rechnet_blindleistung(self):
        with mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value = io.BytesIO(SAMPLE)
            d = shelly.fetch("x")
        self.assertAlmostEqual(d["phases"][0]["q"], 150.0)          # sqrt(250^2 - 200^2)
        self.assertEqual(d["total"]["p"], 300.0)
        self.assertAlmostEqual(d["total"]["pf"], 300.0 / 370.0)

    def test_antwort_zu_gross(self):
        with mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value = io.BytesIO(b"x" * (shelly.MAX_BYTES + 5))
            with self.assertRaises(ValueError):
                shelly.fetch("x")


class Helpers(unittest.TestCase):
    def test_ago(self):
        self.assertEqual(claude_view.ago(5), "5s")
        self.assertEqual(claude_view.ago(125), "2m")
        self.assertEqual(claude_view.ago(3700), "1h01")

    def test_short_home(self):
        home = claude_view.HOME
        self.assertEqual(claude_view.short(home + "/Work"), "~/Work")
        self.assertEqual(claude_view.short("/etc"), "/etc")

    def test_git_ago_alter(self):
        self.assertTrue(git_view.ago(0).endswith("d"))


if __name__ == "__main__":
    unittest.main()
